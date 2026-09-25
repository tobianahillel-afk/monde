from __future__ import annotations

from pathlib import Path

import tools.governance.t9_closure as t9
from tools.governance import github_live_gate as live


def test_live_durable_ids_none_branch() -> None:
    assert live.durable_finding_ids(None) is None


def test_text_and_commit_search_branches(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t9.cg, "git", lambda *_: (_ for _ in ()).throw(RuntimeError("x")))
    assert t9.text_at(tmp_path, "a", "p") is None

    commits = "a\nb\nc\n"
    monkeypatch.setattr(t9.cg, "git", lambda *_: commits)
    values = {("a", "p"): None, ("b", "p"): "needle", ("c", "p"): "needle", ("pa", "p"): "needle"}
    monkeypatch.setattr(t9, "text_at", lambda _r, sha, path: values.get((sha, path), ""))
    monkeypatch.setattr(t9.cg, "commit_parents", lambda _r, sha: ["pa"] if sha == "b" else (["b"] if sha == "c" else []))
    assert t9.first_commit_matching(tmp_path, "h", "p", lambda text: "needle" in text) is None
    values[("pa", "p")] = "old"
    assert t9.first_commit_matching(tmp_path, "h", "p", lambda text: "needle" in text) == "b"
    assert t9.t9_adoption_sha(tmp_path, "h") is None


def test_policy_stability_positive_and_fail_closed(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t9.cg, "commit_exists", lambda _r, sha: sha != "missing")
    monkeypatch.setattr(t9.cg, "is_ancestor", lambda _r, a, b: a != "side")
    monkeypatch.setattr(t9.t7, "policy_blob", lambda _r, sha: {"e": "blob", "a": "blob", "diff": "other"}.get(sha))
    monkeypatch.setattr(t9.cg, "git", lambda *_: "")
    assert t9.policy_stable_full_history(tmp_path, "e", "a")
    assert not t9.policy_stable_full_history(tmp_path, "missing", "a")
    assert not t9.policy_stable_full_history(tmp_path, "side", "a")
    assert not t9.policy_stable_full_history(tmp_path, "diff", "a")
    monkeypatch.setattr(t9.cg, "git", lambda *_: "touch\n")
    assert not t9.policy_stable_full_history(tmp_path, "e", "a")


def test_first_status_commit_branches(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t9.cg, "git", lambda *_: "a\nb\nc")
    states = {("a", "p"): None, ("b", "p"): {"status": "PASS"}, ("c", "p"): {"status": "PASS"}, ("pb", "p"): {"status": "PASS"}}
    monkeypatch.setattr(t9.cg, "show_yaml", lambda _r, sha, path: states.get((sha, path)))
    monkeypatch.setattr(t9.cg, "commit_parents", lambda _r, sha: ["pb"] if sha == "b" else (["b"] if sha == "c" else []))
    assert t9._first_status_commit(tmp_path, "p", "PASS", "h") is None
    states[("pb", "p")] = {"status": "PLANNED"}
    assert t9._first_status_commit(tmp_path, "p", "PASS", "h") == "b"


def review_record() -> dict:
    return {
        "id": "REVIEW-1", "status": "COMPLETE", "outcome": "APPROVE",
        "artifact": {"commit_sha": "a" * 40}, "reviewer": {"context_id": "ctx"},
        "external_import": {
            "mode": "PREAUTHORIZED_EXTERNAL_COMPLETION", "import_commit": "b" * 40,
            "authorization_commit": "a" * 40, "source_review_id": "PRR", "source_submitted_at": "t",
        },
    }


def test_review_authorization_and_finalization_failures(monkeypatch, tmp_path: Path) -> None:
    review = review_record()
    auth = {
        "record_id": "REVIEW-1", "imported_status": "COMPLETE", "artifact_commit_sha": "a" * 40,
        "source_review_id": "PRR", "source_submitted_at": "t", "reviewer_context_id": "ctx",
        "expected_outcome": "APPROVE", "one_shot": True, "consumed_by_commit": "b" * 40,
    }
    assert t9._review_authorization_matches(auth, review, "b" * 40)
    assert not t9._review_authorization_matches({**auth, "record_id": "OTHER"}, review, "b" * 40)

    assert not t9.review_import_finalized(tmp_path, {**review, "external_import": {**review["external_import"], "mode": "bad"}}, "h", "p")
    bad_sha = {**review, "external_import": {**review["external_import"], "import_commit": "short"}}
    assert not t9.review_import_finalized(tmp_path, bad_sha, "h", "p")
    monkeypatch.setattr(t9.cg, "commit_exists", lambda _r, sha: sha == "a" * 40)
    assert not t9.review_import_finalized(tmp_path, review, "h", "p")
    monkeypatch.setattr(t9.cg, "commit_exists", lambda *_: True)
    monkeypatch.setattr(t9, "_first_status_commit", lambda *_: "c" * 40)
    assert not t9.review_import_finalized(tmp_path, review, "h", "p")
    monkeypatch.setattr(t9, "_first_status_commit", lambda *_: "b" * 40)
    monkeypatch.setattr(t9.cg, "is_ancestor", lambda *_: False)
    assert not t9.review_import_finalized(tmp_path, review, "h", "p")
    monkeypatch.setattr(t9.cg, "is_ancestor", lambda *_: True)
    monkeypatch.setattr(t9.cg, "show_yaml", lambda *_: {})
    assert not t9.review_import_finalized(tmp_path, review, "h", "p")


def test_test_authorization_and_finalization_failures(monkeypatch, tmp_path: Path) -> None:
    test = {
        "id": "TEST-1", "status": "PASS", "execution": {"commit_sha": "b" * 40, "result": "PASS"},
        "acceptance_cold_read": {"source": {"source_id": "s", "submitted_at": "t"}, "executor": {"context_id": "ctx"}},
        "external_import": {"authorization_source": f"registry/status-machines.yaml@{'a'*40}#x", "import_commit": "b" * 40},
    }
    auth = {"record_id": "TEST-1", "imported_status": "PASS", "execution_commit_sha": "b" * 40, "source_id": "s", "source_submitted_at": "t", "executor_context_id": "ctx", "expected_result": "PASS", "one_shot": True, "consumed_by_commit": "b" * 40}
    assert t9._test_authorization_matches(auth, test, "b" * 40)
    assert not t9._test_authorization_matches({**auth, "expected_result": "FAIL"}, test, "b" * 40)
    assert not t9.test_import_finalized(tmp_path, {**test, "external_import": {"authorization_source": "bad", "import_commit": "b" * 40}}, "h", "p")
    monkeypatch.setattr(t9.cg, "commit_exists", lambda *_: False)
    assert not t9.test_import_finalized(tmp_path, test, "h", "p")
    monkeypatch.setattr(t9.cg, "commit_exists", lambda *_: True)
    monkeypatch.setattr(t9, "_first_status_commit", lambda *_: "c" * 40)
    assert not t9.test_import_finalized(tmp_path, test, "h", "p")
    monkeypatch.setattr(t9, "_first_status_commit", lambda *_: "b" * 40)
    monkeypatch.setattr(t9.cg, "is_ancestor", lambda *_: False)
    assert not t9.test_import_finalized(tmp_path, test, "h", "p")
    monkeypatch.setattr(t9.cg, "is_ancestor", lambda *_: True)
    monkeypatch.setattr(t9.cg, "show_yaml", lambda *_: {})
    assert not t9.test_import_finalized(tmp_path, test, "h", "p")


def test_acceptance_validation_skip_branches(monkeypatch, tmp_path: Path) -> None:
    paths = ["README.md", "registry/requirements/REQ-1.yaml"]
    monkeypatch.setattr(t9.cg, "changed_files", lambda *_: paths)
    monkeypatch.setattr(t9.cg, "show_yaml", lambda _r, sha, p: None if sha == "a" else {"status": "PROPOSED"})
    assert t9.validate_requirement_acceptance(tmp_path, [("a", "b")]) == []
    monkeypatch.setattr(t9.cg, "show_yaml", lambda *_: {"status": "ACCEPTED"})
    monkeypatch.setattr(t9, "requirement_acceptance_invariant", lambda *_: False)
    assert len(t9.validate_requirement_acceptance(tmp_path, [("a", "b")])) == 1


def test_import_commit_immutability_extra_branches(monkeypatch, tmp_path: Path) -> None:
    path = "registry/reviews/REVIEW-1.yaml"
    monkeypatch.setattr(t9.cg, "changed_files", lambda *_: ["README.md", path])
    monkeypatch.setattr(t9.cg, "show_yaml", lambda _r, sha, _p: {"status": "COMPLETE", "external_import": "legacy"})
    assert t9.validate_import_commit_immutability(tmp_path, [("a", "b")]) == []
    same = {"status": "COMPLETE", "external_import": {"import_commit": "x"}}
    monkeypatch.setattr(t9.cg, "show_yaml", lambda *_: same)
    assert t9.validate_import_commit_immutability(tmp_path, [("a", "b")]) == []
    old = {"status": "COMPLETE", "external_import": {"import_commit": None}}
    new = {"status": "COMPLETE", "external_import": {"import_commit": "a" * 40}}
    monkeypatch.setattr(t9.cg, "show_yaml", lambda _r, sha, _p: old if sha == "a" else new)
    monkeypatch.setattr(t9, "review_import_finalized", lambda *_: False)
    assert len(t9.validate_import_commit_immutability(tmp_path, [("a", "b")])) == 1


def test_base_preexisting_work_covers_branches(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t9.cg, "git", lambda *_: "registry/work-items/_TEMPLATE.yaml\nregistry/work-items/W1.yaml\nregistry/work-items/W2.yaml")
    records = {
        "registry/work-items/W1.yaml": {"status": "PLANNED", "assurance": {"level": "A2"}},
        "registry/work-items/W2.yaml": {"status": "IN_REVIEW", "assurance": {"level": "A3"}, "scope_change": {"approved": True}, "affected_paths": ["registry/content-identity.yaml"]},
    }
    monkeypatch.setattr(t9.cg, "show_yaml", lambda _r, _s, path: records.get(path))
    assert t9.base_preexisting_work_covers(tmp_path, "base", "registry/content-identity.yaml")
    records["registry/work-items/W2.yaml"]["scope_change"] = {"approved": False}
    assert not t9.base_preexisting_work_covers(tmp_path, "base", "registry/content-identity.yaml")


def test_policy_authority_adoption_and_pre_adoption_branches(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t9, "t9_adoption_sha", lambda *_: "adopt")
    monkeypatch.setattr(t9.cg, "pr_commit_edges", lambda *a, **k: ([], [("pre", "adopt"), ("old", "later")]))
    monkeypatch.setattr(t9.cg, "changed_files", lambda _r, _a, b: ["registry/content-identity.yaml"] if b == "adopt" else ["registry/acceptance-authority.yaml"])
    monkeypatch.setattr(t9.cg, "is_ancestor", lambda *_: False)
    findings = t9.validate_base_preexisting_policy_authority(tmp_path, "base", "head")
    assert [x.rule for x in findings] == ["POLICY_T9_SELF_AUTHORIZATION"]


def test_new_review_trigger_and_reopening_fallthroughs(monkeypatch, tmp_path: Path) -> None:
    path = "registry/reviews/R.yaml"
    monkeypatch.setattr(t9.cg, "show_yaml", lambda _r, sha, _p: {"status": "IN_PROGRESS", "scope": {}} if sha == "a" else {"status": "COMPLETE", "outcome": "CHANGES_REQUIRED", "scope": {"work_items": ["WORK-1"]}})
    assert t9._new_review_trigger(tmp_path, "a", "b", "WORK-1", path)
    monkeypatch.setattr(t9.cg, "show_yaml", lambda *_: {"status": "COMPLETE", "outcome": "CHANGES_REQUIRED", "scope": {"work_items": ["WORK-1"]}})
    assert not t9._new_review_trigger(tmp_path, "a", "b", "WORK-1", path)
    monkeypatch.setattr(t9.cg, "changed_files", lambda *_: [path])
    monkeypatch.setattr(t9.cg, "show_yaml", lambda _r, sha, _p: {"status": "IN_PROGRESS", "scope": {}} if sha == "a" else {"status": "COMPLETE", "outcome": "BLOCKED", "scope": {"work_items": ["WORK-1"]}})
    assert t9.new_reopening_trigger(tmp_path, "a", "b", "WORK-1")
    monkeypatch.setattr(t9.cg, "changed_files", lambda *_: [])
    assert not t9.new_reopening_trigger(tmp_path, "a", "b", "WORK-1")


def test_validate_new_reopening_skip_branches(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t9, "t9_adoption_sha", lambda *_: None)
    assert t9.validate_new_reopening_triggers(tmp_path, "base", "head")[0].rule == "T9_ADOPTION"
    monkeypatch.setattr(t9, "t9_adoption_sha", lambda *_: "adopt")
    monkeypatch.setattr(t9.cg, "pr_commit_edges", lambda *a, **k: ([], [("pre", "post")]))
    monkeypatch.setattr(t9.cg, "is_ancestor", lambda *_: False)
    assert t9.validate_new_reopening_triggers(tmp_path, "base", "head") == []
    monkeypatch.setattr(t9.cg, "is_ancestor", lambda *_: True)
    monkeypatch.setattr(t9.cg, "changed_files", lambda *_: [])
    assert t9.validate_new_reopening_triggers(tmp_path, "base", "head") == []
