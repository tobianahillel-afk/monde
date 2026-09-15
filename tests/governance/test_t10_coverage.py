from __future__ import annotations

from pathlib import Path

import tools.governance.t10_closure as t10


def test_text_and_adoption_helpers_cover_success_failure_and_history(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t10.cg, "git", lambda *_: "body")
    assert t10.text_at(tmp_path, "a", "p") == "body"

    def fail_git(*_args):
        raise RuntimeError("missing")

    monkeypatch.setattr(t10.cg, "git", fail_git)
    assert t10.text_at(tmp_path, "a", "p") is None

    monkeypatch.setattr(t10.cg, "git", lambda *_: "\na\nb\n")
    monkeypatch.setattr(t10, "text_at", lambda _r, sha, _p: "no marker" if sha == "a" else "marker")
    monkeypatch.setattr(t10.cg, "commit_parents", lambda _r, sha: [] if sha == "b" else ["p"])
    assert t10.first_commit_matching(tmp_path, "head", "p", "marker") == "b"

    monkeypatch.setattr(t10, "text_at", lambda _r, sha, _p: "marker" if sha in {"a", "p"} else "")
    monkeypatch.setattr(t10.cg, "commit_parents", lambda *_: ["p"])
    assert t10.first_commit_matching(tmp_path, "head", "p", "marker") is None

    monkeypatch.setattr(t10, "first_commit_matching", lambda *_: "adopt")
    assert t10.t10_adoption_sha(tmp_path, "head") == "adopt"


def test_edge_enforcement_short_circuit_and_ancestry(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t10.cg, "is_ancestor", lambda *_: False)
    assert t10.edge_is_enforced(tmp_path, "adopt", "x", "adopt")
    assert not t10.edge_is_enforced(tmp_path, "adopt", "x", "y")
    monkeypatch.setattr(t10.cg, "is_ancestor", lambda *_: True)
    assert t10.edge_is_enforced(tmp_path, "adopt", "x", "y")


def test_integration_anchor_ignores_unrelated_and_pre_adoption_edges(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t10, "t10_adoption_sha", lambda *_: "adopt")
    monkeypatch.setattr(t10.cg, "pr_commit_edges", lambda *a, **k: ([], [("old", "mid"), ("adopt", "new")]))
    monkeypatch.setattr(
        t10.cg,
        "changed_files",
        lambda _r, before, _after: [t10.INTEGRATION_PROVENANCE_PATH] if before == "old" else ["README.md"],
    )
    monkeypatch.setattr(t10.cg, "is_ancestor", lambda *_: False)
    monkeypatch.setattr(t10.t9, "base_preexisting_work_covers", lambda *_: False)
    assert t10.validate_integration_provenance_trust_anchor(tmp_path, "base", "head") == []


def test_registry_records_filters_templates_and_non_mappings(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        t10.cg,
        "git",
        lambda *_: "registry/requirements/_TEMPLATE.yaml\nregistry/requirements/REQ-1.yaml\nregistry/requirements/REQ-2.yaml\nregistry/requirements/note.txt",
    )
    monkeypatch.setattr(
        t10.cg,
        "show_yaml",
        lambda _r, _s, path: {"id": "REQ-1"} if path.endswith("REQ-1.yaml") else ["not", "mapping"],
    )
    assert list(t10.registry_records(tmp_path, "head", "requirements")) == [
        ("registry/requirements/REQ-1.yaml", {"id": "REQ-1"})
    ]


def test_dependency_revalidation_skips_nonaccepted_records(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t10, "t10_adoption_sha", lambda *_: "adopt")
    monkeypatch.setattr(t10.cg, "pr_commit_edges", lambda *a, **k: ([], [("adopt", "after")]))
    monkeypatch.setattr(t10, "edge_is_enforced", lambda *_: True)

    def records(_root: Path, _sha: str, kind: str):
        status = "PROPOSED" if kind == "requirements" else "OPEN"
        return iter([(f"registry/{kind}/X.yaml", {"status": status})])

    monkeypatch.setattr(t10, "registry_records", records)
    monkeypatch.setattr(t10.t9, "requirement_acceptance_invariant", lambda *_: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(t10.cg, "risk_acceptance_satisfied", lambda *_: (_ for _ in ()).throw(AssertionError()))
    assert t10.validate_acceptance_dependencies(tmp_path, "base", "head") == []


def test_workflow_validator_covers_missing_files_and_missing_t10_wiring(tmp_path: Path) -> None:
    assert t10.validate_workflow_review_triggers(tmp_path)[0].rule == "LIVE_GATE_REVIEW_TRIGGER"

    workflow = tmp_path / t10.WORKFLOW_PATH
    core = tmp_path / t10.CORE_WORKFLOW_PATH
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(
        "on:\n"
        "  pull_request_review:\n    types: [submitted, edited, dismissed]\n"
        "  pull_request_review_comment:\n    types: [created, edited, deleted]\n"
        "jobs:\n  x:\n    if: startsWith(github.event_name, 'pull_request')\n",
        encoding="utf-8",
    )
    core.write_text("no t10 gate\n", encoding="utf-8")
    assert [item.rule for item in t10.validate_workflow_review_triggers(tmp_path)] == ["T10_GATE_WIRING"]


def test_main_runtime_error_is_fail_closed(monkeypatch, tmp_path: Path, capsys) -> None:
    def boom(*_args):
        raise RuntimeError("git failure")

    monkeypatch.setattr(t10, "run", boom)
    assert t10.main([str(tmp_path), "--base", "base", "--head", "head"]) == 2
    assert "ERROR T10_CLOSURE git failure" in capsys.readouterr().err
