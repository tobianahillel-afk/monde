from __future__ import annotations

from pathlib import Path

import pytest

from tools.governance import review_closure_gate as gate

SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40


def valid_entry() -> dict:
    return {
        "rule_id": gate.RULE_ID,
        "adoption_commit_sha": SHA_A,
        "guard_path": gate.GUARD_PATH,
        "activation_path": gate.ACTIVATION_PATH,
        "historical_only": True,
        "future_reuse_forbidden": True,
    }


def install_valid_git(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate.cg, "commit_exists", lambda *a: True)
    monkeypatch.setattr(gate.cg, "file_exists_at", lambda *a: True)
    monkeypatch.setattr(gate.cg, "is_ancestor", lambda *a: True)
    monkeypatch.setattr(gate.cg, "commit_parents", lambda *a: [SHA_B])
    monkeypatch.setattr(gate.cg, "changed_files", lambda *a: [gate.ACTIVATION_PATH])


def test_adoption_valid(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(gate.rc, "load_mapping", lambda *a: {"enforcement_adoptions": [valid_entry()]})
    install_valid_git(monkeypatch)
    assert gate.adoption_sha(tmp_path, SHA_C) == SHA_A


@pytest.mark.parametrize(
    "entries",
    [[], [{"rule_id": "OTHER"}], [valid_entry(), valid_entry()]],
)
def test_adoption_requires_exactly_one_match(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, entries: list[dict]) -> None:
    monkeypatch.setattr(gate.rc, "load_mapping", lambda *a: {"enforcement_adoptions": entries})
    assert gate.adoption_sha(tmp_path, SHA_C) is None


def test_adoption_field_and_git_failures(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def check(entry: dict, setup=None) -> None:
        monkeypatch.setattr(gate.rc, "load_mapping", lambda *a, entry=entry: {"enforcement_adoptions": [entry]})
        install_valid_git(monkeypatch)
        if setup:
            setup()
        assert gate.adoption_sha(tmp_path, SHA_C) is None

    entry = valid_entry(); entry["adoption_commit_sha"] = "bad"; check(entry)
    entry = valid_entry(); entry["guard_path"] = "wrong"; check(entry)
    entry = valid_entry(); entry["activation_path"] = "wrong"; check(entry)
    entry = valid_entry(); entry["historical_only"] = False; check(entry)
    entry = valid_entry(); entry["future_reuse_forbidden"] = False; check(entry)
    check(valid_entry(), lambda: monkeypatch.setattr(gate.cg, "commit_exists", lambda *a: False))
    check(valid_entry(), lambda: monkeypatch.setattr(gate.cg, "file_exists_at", lambda root, sha, path: path != gate.GUARD_PATH))
    check(valid_entry(), lambda: monkeypatch.setattr(gate.cg, "file_exists_at", lambda root, sha, path: path != gate.ACTIVATION_PATH))
    check(valid_entry(), lambda: monkeypatch.setattr(gate.cg, "is_ancestor", lambda *a: False))
    check(valid_entry(), lambda: monkeypatch.setattr(gate.cg, "commit_parents", lambda *a: []))
    check(valid_entry(), lambda: monkeypatch.setattr(gate.cg, "changed_files", lambda *a: []))
    check(valid_entry(), lambda: monkeypatch.setattr(gate.cg, "changed_files", lambda *a: [gate.ACTIVATION_PATH, gate.PROVENANCE_PATH]))


def test_run_missing_adoption_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(gate.cg, "pr_commit_edges", lambda *a, **k: ([], [(SHA_A, SHA_B)]))
    monkeypatch.setattr(gate.rc, "validate_done_review_substance", lambda *a: [])
    monkeypatch.setattr(gate.rc, "validate_requirement_acceptance", lambda *a: [])
    monkeypatch.setattr(gate.rc, "validate_historical_import_authorization", lambda *a: [])
    monkeypatch.setattr(gate, "adoption_sha", lambda *a: None)
    findings = gate.run(tmp_path, SHA_A, SHA_B)
    assert [item.rule for item in findings] == ["ENFORCEMENT_ADOPTION"]


def test_run_filters_progress_to_post_adoption_edges(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    edges = [(SHA_B, SHA_A), (SHA_A, SHA_C)]
    monkeypatch.setattr(gate.cg, "pr_commit_edges", lambda *a, **k: ([], edges))
    monkeypatch.setattr(gate.rc, "validate_done_review_substance", lambda *a: [])
    monkeypatch.setattr(gate.rc, "validate_requirement_acceptance", lambda *a: [])
    monkeypatch.setattr(gate.rc, "validate_historical_import_authorization", lambda *a: [])
    monkeypatch.setattr(gate, "adoption_sha", lambda *a: SHA_A)
    monkeypatch.setattr(gate.cg, "is_ancestor", lambda root, adoption, before: before == SHA_A)
    seen = []
    monkeypatch.setattr(gate.rc, "validate_progress_reopening", lambda root, progress_edges: seen.extend(progress_edges) or [])
    assert gate.run(tmp_path, SHA_B, SHA_C) == []
    assert seen == [(SHA_A, SHA_C)]


def test_main_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "findings.json"
    monkeypatch.setattr(gate, "run", lambda *a: [gate.rc.Finding("p", "R", "m")])
    assert gate.main([str(tmp_path), "--base", SHA_A, "--head", SHA_B, "--json-out", str(out)]) == 1
    assert out.exists()
    assert "ERROR R p: m" in capsys.readouterr().err
    monkeypatch.setattr(gate, "run", lambda *a: [])
    assert gate.main([str(tmp_path), "--base", SHA_A, "--head", SHA_B]) == 0
    monkeypatch.setattr(gate, "run", lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))
    assert gate.main([str(tmp_path), "--base", SHA_A, "--head", SHA_B]) == 2
