from __future__ import annotations

from pathlib import Path

import tools.governance.t9_closure as t9


def review() -> dict:
    return {
        "id": "REVIEW-1",
        "status": "COMPLETE",
        "outcome": "APPROVE",
        "artifact": {"commit_sha": "c" * 40},
        "reviewer": {"context_id": "ctx"},
        "external_import": {
            "mode": "PREAUTHORIZED_EXTERNAL_COMPLETION",
            "authorization_commit": "a" * 40,
            "source_review_id": "PRR-1",
            "source_submitted_at": "time",
            "import_commit": "b" * 40,
        },
    }


def authorization() -> dict:
    return {
        "record_id": "REVIEW-1",
        "imported_status": "COMPLETE",
        "artifact_commit_sha": "c" * 40,
        "source_review_id": "PRR-1",
        "source_submitted_at": "time",
        "reviewer_context_id": "ctx",
        "expected_outcome": "APPROVE",
        "one_shot": True,
        "consumed_by_commit": None,
    }


def configure_positive(monkeypatch, root: Path) -> None:
    monkeypatch.setattr(t9.cg, "commit_exists", lambda *_: True)
    monkeypatch.setattr(t9, "_first_status_commit", lambda *_: "b" * 40)
    monkeypatch.setattr(t9.cg, "is_ancestor", lambda *_: True)

    materialized = review()
    materialized["external_import"] = {**materialized["external_import"], "import_commit": None}
    machine = {
        "registry_machines": {
            "reviews": {"external_import_authorizations": [authorization()]}
        }
    }

    def show_yaml(_root: Path, sha: str, path: str):
        if path == "registry/reviews/REVIEW-1.yaml" and sha == "b" * 40:
            return materialized
        if path == "registry/status-machines.yaml" and sha == "a" * 40:
            return machine
        return {}

    monkeypatch.setattr(t9.cg, "show_yaml", show_yaml)


def test_binding_accepts_exact_materialization_with_prior_unconsumed_auth(monkeypatch, tmp_path: Path) -> None:
    configure_positive(monkeypatch, tmp_path)
    assert t9.review_import_binding_allowed(tmp_path, review(), "d" * 40, "registry/reviews/REVIEW-1.yaml")


def test_binding_rejects_bad_shape_and_missing_commits(monkeypatch, tmp_path: Path) -> None:
    value = review()
    value["external_import"] = "bad"
    assert not t9.review_import_binding_allowed(tmp_path, value, "d" * 40, "p")

    value = review()
    value["external_import"]["mode"] = "bad"
    assert not t9.review_import_binding_allowed(tmp_path, value, "d" * 40, "p")

    value = review()
    value["external_import"]["import_commit"] = "short"
    assert not t9.review_import_binding_allowed(tmp_path, value, "d" * 40, "p")

    value = review()
    monkeypatch.setattr(t9.cg, "commit_exists", lambda _r, sha: sha == "a" * 40)
    assert not t9.review_import_binding_allowed(tmp_path, value, "d" * 40, "p")


def test_binding_rejects_wrong_materialization_or_ancestry(monkeypatch, tmp_path: Path) -> None:
    value = review()
    monkeypatch.setattr(t9.cg, "commit_exists", lambda *_: True)
    monkeypatch.setattr(t9, "_first_status_commit", lambda *_: "e" * 40)
    assert not t9.review_import_binding_allowed(tmp_path, value, "d" * 40, "p")

    monkeypatch.setattr(t9, "_first_status_commit", lambda *_: "b" * 40)
    monkeypatch.setattr(t9.cg, "is_ancestor", lambda _r, a, b: not (a == "b" * 40 and b == "d" * 40))
    assert not t9.review_import_binding_allowed(tmp_path, value, "d" * 40, "p")

    monkeypatch.setattr(t9.cg, "is_ancestor", lambda _r, a, b: not (a == "a" * 40 and b == "b" * 40))
    assert not t9.review_import_binding_allowed(tmp_path, value, "d" * 40, "p")

    value["external_import"]["authorization_commit"] = "b" * 40
    monkeypatch.setattr(t9.cg, "is_ancestor", lambda *_: True)
    assert not t9.review_import_binding_allowed(tmp_path, value, "d" * 40, "p")


def test_binding_rejects_already_bound_or_changed_materialization(monkeypatch, tmp_path: Path) -> None:
    configure_positive(monkeypatch, tmp_path)
    value = review()

    materialized = review()
    monkeypatch.setattr(
        t9.cg,
        "show_yaml",
        lambda _r, sha, path: materialized if path == "registry/reviews/REVIEW-1.yaml" else {
            "registry_machines": {"reviews": {"external_import_authorizations": [authorization()]}}
        },
    )
    assert not t9.review_import_binding_allowed(tmp_path, value, "d" * 40, "registry/reviews/REVIEW-1.yaml")

    materialized["external_import"]["import_commit"] = None
    materialized["external_import"]["source_review_id"] = "OTHER"
    assert not t9.review_import_binding_allowed(tmp_path, value, "d" * 40, "registry/reviews/REVIEW-1.yaml")


def test_binding_rejects_missing_matching_preauthorization(monkeypatch, tmp_path: Path) -> None:
    configure_positive(monkeypatch, tmp_path)
    value = review()
    materialized = review()
    materialized["external_import"]["import_commit"] = None
    monkeypatch.setattr(
        t9.cg,
        "show_yaml",
        lambda _r, sha, path: materialized if path == "registry/reviews/REVIEW-1.yaml" else {
            "registry_machines": {"reviews": {"external_import_authorizations": []}}
        },
    )
    assert not t9.review_import_binding_allowed(tmp_path, value, "d" * 40, "registry/reviews/REVIEW-1.yaml")


def test_immutability_rejects_arbitrary_null_to_string_binding(monkeypatch, tmp_path: Path) -> None:
    path = "registry/reviews/REVIEW-1.yaml"
    before = {"status": "COMPLETE", "external_import": {"import_commit": None}}
    after = {"status": "COMPLETE", "external_import": {"import_commit": "f" * 40}}
    monkeypatch.setattr(t9.cg, "changed_files", lambda *_: [path])
    monkeypatch.setattr(t9.cg, "show_yaml", lambda _r, sha, _p: before if sha == "before" else after)
    monkeypatch.setattr(t9, "review_import_binding_allowed", lambda *_: False)
    monkeypatch.setattr(t9, "review_import_finalized", lambda *_: False)
    findings = t9.validate_import_commit_immutability(tmp_path, [("before", "after")])
    assert [item.rule for item in findings] == ["REVIEW_IMPORT_COMMIT_IMMUTABLE"]
