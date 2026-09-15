from __future__ import annotations

from pathlib import Path

import tools.governance.t10_closure as t10


def test_integration_provenance_requires_base_preexisting_authority(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t10, "t10_adoption_sha", lambda *_: "adopt")
    monkeypatch.setattr(t10.cg, "pr_commit_edges", lambda *a, **k: ([], [("pre", "post")]))
    monkeypatch.setattr(t10.cg, "changed_files", lambda *_: [t10.INTEGRATION_PROVENANCE_PATH])
    monkeypatch.setattr(t10.cg, "is_ancestor", lambda *_: True)
    monkeypatch.setattr(t10.t9, "base_preexisting_work_covers", lambda *_: False)
    findings = t10.validate_integration_provenance_trust_anchor(tmp_path, "base", "head")
    assert [item.rule for item in findings] == ["INTEGRATION_PROVENANCE_BASE_AUTHORITY"]

    monkeypatch.setattr(t10.t9, "base_preexisting_work_covers", lambda *_: True)
    assert t10.validate_integration_provenance_trust_anchor(tmp_path, "base", "head") == []

    monkeypatch.setattr(t10.cg, "pr_commit_edges", lambda *a, **k: ([], [("pre", "adopt")]))
    assert [item.rule for item in t10.validate_integration_provenance_trust_anchor(tmp_path, "base", "head")] == [
        "INTEGRATION_PROVENANCE_SELF_AUTHORIZATION"
    ]


def test_global_acceptance_revalidation_catches_dependency_only_changes(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t10, "t10_adoption_sha", lambda *_: "adopt")
    monkeypatch.setattr(t10.cg, "pr_commit_edges", lambda *a, **k: ([], [("adopt", "after")]))
    monkeypatch.setattr(t10, "edge_is_enforced", lambda *_: True)

    def records(_root: Path, _sha: str, kind: str):
        if kind == "requirements":
            return iter([("registry/requirements/REQ-1.yaml", {"id": "REQ-1", "status": "ACCEPTED"})])
        return iter([("registry/risks/RISK-1.yaml", {"id": "RISK-1", "status": "ACCEPTED"})])

    monkeypatch.setattr(t10, "registry_records", records)
    monkeypatch.setattr(t10.t9, "requirement_acceptance_invariant", lambda *_: False)
    monkeypatch.setattr(t10.cg, "risk_acceptance_satisfied", lambda *_: False)

    findings = t10.validate_acceptance_dependencies(tmp_path, "base", "head")
    assert {item.rule for item in findings} == {
        "REQ_ACCEPTED_DEPENDENCY_INVARIANT",
        "RISK_ACCEPTED_DEPENDENCY_INVARIANT",
    }

    monkeypatch.setattr(t10.t9, "requirement_acceptance_invariant", lambda *_: True)
    monkeypatch.setattr(t10.cg, "risk_acceptance_satisfied", lambda *_: True)
    assert t10.validate_acceptance_dependencies(tmp_path, "base", "head") == []


def test_pre_adoption_edges_do_not_retroactively_revalidate(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t10, "t10_adoption_sha", lambda *_: "adopt")
    monkeypatch.setattr(t10.cg, "pr_commit_edges", lambda *a, **k: ([], [("old", "older")]))
    monkeypatch.setattr(t10, "edge_is_enforced", lambda *_: False)
    monkeypatch.setattr(t10, "registry_records", lambda *_: (_ for _ in ()))
    assert t10.validate_acceptance_dependencies(tmp_path, "base", "head") == []


def test_repository_workflow_has_review_state_reruns_and_t10_wiring() -> None:
    root = Path(__file__).resolve().parents[2]
    assert t10.validate_workflow_review_triggers(root) == []


def test_workflow_trigger_validator_fails_closed(tmp_path: Path) -> None:
    workflow = tmp_path / t10.WORKFLOW_PATH
    core = tmp_path / t10.CORE_WORKFLOW_PATH
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(
        "on:\n  pull_request_review:\n    types: [submitted, edited, dismissed]\n"
        "jobs:\n  x:\n    if: startsWith(github.event_name, 'pull_request')\n",
        encoding="utf-8",
    )
    core.write_text("python -m tools.governance.t10_closure .\n", encoding="utf-8")
    findings = t10.validate_workflow_review_triggers(tmp_path)
    assert [item.rule for item in findings] == ["LIVE_GATE_REVIEW_TRIGGER"]

    workflow.write_text(
        "on:\n"
        "  pull_request_review:\n    types: [submitted, edited, dismissed]\n"
        "  pull_request_review_comment:\n    types: [created, edited, deleted]\n",
        encoding="utf-8",
    )
    findings = t10.validate_workflow_review_triggers(tmp_path)
    assert [item.rule for item in findings] == ["LIVE_GATE_PR_FAMILY"]


def test_run_and_main(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(t10, "validate_integration_provenance_trust_anchor", lambda *_: [t10.Finding("x", "A", "bad")])
    monkeypatch.setattr(t10, "validate_acceptance_dependencies", lambda *_: [])
    monkeypatch.setattr(t10, "validate_workflow_review_triggers", lambda *_: [])
    assert len(t10.run(tmp_path, "base", "head")) == 1

    output = tmp_path / "t10.json"
    assert t10.main([str(tmp_path), "--base", "base", "--head", "head", "--json-out", str(output)]) == 1
    assert output.exists()
    assert "ERROR A" in capsys.readouterr().err

    monkeypatch.setattr(t10, "validate_integration_provenance_trust_anchor", lambda *_: [])
    assert t10.main([str(tmp_path), "--base", "base", "--head", "head"]) == 0


def test_missing_adoption_fails_closed(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t10, "t10_adoption_sha", lambda *_: None)
    assert t10.validate_integration_provenance_trust_anchor(tmp_path, "base", "head")[0].rule == "T10_ADOPTION"
    assert t10.validate_acceptance_dependencies(tmp_path, "base", "head")[0].rule == "T10_ADOPTION"
