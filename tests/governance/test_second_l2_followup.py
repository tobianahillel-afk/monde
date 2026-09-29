from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

import tools.governance.change_guard as cg
import tools.governance.review_closure as rc


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True).stdout.strip()


def init_git(root: Path) -> None:
    git(root, "init")
    git(root, "config", "user.email", "second-l2@example.invalid")
    git(root, "config", "user.name", "second-l2")


def commit(root: Path, message: str) -> str:
    git(root, "add", "-A")
    git(root, "commit", "-m", message)
    return git(root, "rev-parse", "HEAD")


def good_review(rank: str = "L2") -> dict:
    return {
        "id": "REVIEW-1",
        "status": "COMPLETE",
        "outcome": "APPROVE",
        "artifact": {"commit_sha": "a" * 40},
        "reviewer": {"actor": "independent", "context_id": "ctx-1", "independence_level": rank},
        "roles": ["VERIFICATION_VALIDATION"],
        "checks": {"assumptions_challenged": ["x"]},
        "completed_at": "2026-09-14T00:00:00Z",
        "external_import": {"source_review_id": "SRC-1", "source_submitted_at": "2026-09-14T00:00:00Z"},
    }


def good_cold(rank: str = "L2") -> dict:
    return {
        "id": "TEST-1",
        "status": "PASS",
        "acceptance_cold_read": {
            "source": {"source_id": "RUN-1", "submitted_at": "2026-09-14T00:00:00Z"},
            "executor": {
                "context_id": "ctx-cold",
                "independence_level": rank,
                "fresh_context": True,
                "authoring_context_separated": True,
            },
        },
    }


def test_load_mapping_and_basic_helpers(tmp_path: Path) -> None:
    missing = tmp_path / "missing.yaml"
    assert rc.load_mapping(missing) == {}
    bad = tmp_path / "bad.yaml"
    bad.write_text("[", encoding="utf-8")
    assert rc.load_mapping(bad) == {}
    scalar = tmp_path / "scalar.yaml"
    scalar.write_text("x", encoding="utf-8")
    assert rc.load_mapping(scalar) == {}
    mapping = tmp_path / "map.yaml"
    dump(mapping, {"x": 1})
    assert rc.load_mapping(mapping) == {"x": 1}
    assert rc.nonempty(" x ")
    assert not rc.nonempty(3)
    assert not rc.nonempty("  ")
    assert rc.Finding("p", "R", "m").render() == "ERROR R p: m"


def test_review_source_and_substantive_review_branches() -> None:
    review = good_review()
    assert rc.review_source_provenance(review)
    assert rc.substantive_review(review, 2)
    via_verification = good_review()
    via_verification["external_import"] = None
    via_verification["verification_result"] = {
        "source": {"source_id": "RUN", "submitted_at": "now"},
        "executor": {"context_id": "ctx"},
    }
    assert rc.review_source_provenance(via_verification)
    bad = good_review(); bad["external_import"] = None; bad["verification_result"] = "bad"
    assert not rc.review_source_provenance(bad)
    bad = good_review(); bad["external_import"] = None; bad["verification_result"] = {"source": "bad", "executor": {}}
    assert not rc.review_source_provenance(bad)
    for key in ("actor", "context_id"):
        bad = good_review(); bad["reviewer"][key] = ""
        assert not rc.substantive_review(bad)
    bad = good_review(); bad["completed_at"] = ""
    assert not rc.substantive_review(bad)
    bad = good_review(); bad["checks"] = {}
    assert not rc.substantive_review(bad)
    bad = good_review(); bad["roles"] = []
    assert not rc.substantive_review(bad)
    bad = good_review("L1")
    assert not rc.substantive_review(bad, 2)
    bad = good_review(); bad["outcome"] = "CHANGES_REQUIRED"
    assert not rc.substantive_review(bad)


def test_requirement_floor_and_cold_read_provenance(monkeypatch, tmp_path: Path) -> None:
    records = {
        "registry/work-items/WORK-1.yaml": {"assurance": {"level": "A3"}, "review_plan": {"independence_level": "L2_TARGET"}},
        "registry/work-items/WORK-2.yaml": {"assurance": {"level": "A4"}, "review_plan": {"independence_level": "L3_TARGET"}},
        "registry/work-items/WORK-3.yaml": {"assurance": {"level": "A2"}, "review_plan": {"independence_level": "L3_TARGET"}},
    }
    monkeypatch.setattr(cg, "show_yaml", lambda root, sha, path: records.get(path))
    assert rc.requirement_review_floor(tmp_path, "h", {"origin": {"introduced_by_work": "WORK-1"}}) == (2, "WORK-1")
    assert rc.requirement_review_floor(tmp_path, "h", {"origin": {"introduced_by_work": "WORK-2"}}) == (3, "WORK-2")
    assert rc.requirement_review_floor(tmp_path, "h", {"origin": {"introduced_by_work": "WORK-3"}}) == (3, "WORK-3")
    assert rc.requirement_review_floor(tmp_path, "h", {}) == (3, None)
    assert rc.requirement_review_floor(tmp_path, "h", {"origin": "bad"}) == (3, None)
    assert rc.cold_read_has_provenance(good_cold("L2"), 2)
    assert not rc.cold_read_has_provenance(good_cold("L2"), 3)
    bad = good_cold(); bad["acceptance_cold_read"]["source"]["source_id"] = ""
    assert not rc.cold_read_has_provenance(bad, 2)
    bad = good_cold(); bad["acceptance_cold_read"]["source"]["submitted_at"] = ""
    assert not rc.cold_read_has_provenance(bad, 2)
    bad = good_cold(); bad["acceptance_cold_read"]["executor"]["context_id"] = ""
    assert not rc.cold_read_has_provenance(bad, 2)
    bad = good_cold(); bad["acceptance_cold_read"]["executor"]["fresh_context"] = False
    assert not rc.cold_read_has_provenance(bad, 2)


def test_requirement_acceptance_uses_owning_work_floor_and_provenance(monkeypatch, tmp_path: Path) -> None:
    requirement = {
        "id": "REQ-1",
        "status": "ACCEPTED",
        "origin": {"introduced_by_work": "WORK-1"},
        "verification": {"acceptance_evidence": ["junk", "REVIEW-1"], "acceptance_cold_read_test_ids": ["junk", "TEST-1"]},
    }
    previous = dict(requirement); previous["status"] = "PROPOSED"
    records = {
        ("before", "registry/requirements/REQ-1.yaml"): previous,
        ("after", "registry/requirements/REQ-1.yaml"): requirement,
        ("after", "registry/work-items/WORK-1.yaml"): {"assurance": {"level": "A4"}, "review_plan": {"independence_level": "L3_TARGET"}},
        ("after", "registry/reviews/REVIEW-1.yaml"): good_review("L2"),
        ("after", "registry/tests/TEST-1.yaml"): good_cold("L2"),
    }
    monkeypatch.setattr(cg, "changed_files", lambda root, before, after: ["README.md", "registry/requirements/REQ-1.yaml"])
    monkeypatch.setattr(cg, "show_yaml", lambda root, sha, path: records.get((sha, path)))
    rules = {x.rule for x in rc.validate_requirement_acceptance(tmp_path, [("before", "after")])}
    assert rules == {"REQ_REVIEW_ASSURANCE", "REQ_COLD_READ_PROVENANCE"}
    records[("after", "registry/reviews/REVIEW-1.yaml")] = good_review("L3")
    records[("after", "registry/tests/TEST-1.yaml")] = good_cold("L3")
    assert rc.validate_requirement_acceptance(tmp_path, [("before", "after")]) == []


def test_historical_exception_matching_and_preauthorization(monkeypatch, tmp_path: Path) -> None:
    record = {"id": "REQ-9", "status": "ACCEPTED"}
    good = {"historical_import_exceptions": [{
        "record_id": "REQ-9", "imported_status": "ACCEPTED", "import_commit": "after",
        "historical_only": True, "future_reuse_forbidden": True, "review_origin": "REVIEW-9/F-1",
    }]}
    assert rc.historical_exception_match(good, record, "after")
    for key in ("historical_only", "future_reuse_forbidden"):
        bad = yaml.safe_load(yaml.safe_dump(good)); bad["historical_import_exceptions"][0][key] = False
        assert not rc.historical_exception_match(bad, record, "after")
    bad = yaml.safe_load(yaml.safe_dump(good)); bad["historical_import_exceptions"][0]["review_origin"] = ""
    assert not rc.historical_exception_match(bad, record, "after")

    monkeypatch.setattr(cg, "file_exists_at", lambda root, sha, path: sha != "pre-adoption")
    monkeypatch.setattr(cg, "changed_files", lambda root, before, after: ["registry/requirements/REQ-9.yaml"])
    monkeypatch.setattr(cg, "registry_kind", lambda path: "requirements")
    monkeypatch.setattr(cg, "show_yaml", lambda root, sha, path: None if sha in {"pre-adoption", "before"} else record)
    monkeypatch.setattr(cg, "canonical_machine_spec", lambda root, sha, kind: {"initial": "PROPOSED", **(good if sha == "before-with-policy" else {})})
    assert rc.validate_historical_import_authorization(tmp_path, [("pre-adoption", "after")]) == []
    findings = rc.validate_historical_import_authorization(tmp_path, [("before", "after")])
    assert {x.rule for x in findings} == {"HISTORICAL_IMPORT_PREAUTH"}


def matrix(status: str = "IN_REVIEW") -> dict:
    return {
        "phases": {
            "PHASE-1": {
                "status": status,
                "lots": {
                    "LOT-1": {
                        "status": status,
                        "sublots": {
                            "SUB-1": {
                                "status": status,
                                "work_items": {"WORK-1": {"status": status, "tests": status}},
                            }
                        },
                    }
                },
            }
        },
        "quality_dimensions": {"security": status},
    }


def test_progress_flatten_descendants_and_reopening(monkeypatch, tmp_path: Path) -> None:
    after_matrix = matrix("IN_REVIEW")
    flat = rc.flatten_progress(after_matrix)
    assert flat["work:WORK-1"] == "IN_REVIEW"
    assert flat["progress:work:WORK-1:tests"] == "IN_REVIEW"
    assert flat["progress:quality:security"] == "IN_REVIEW"
    assert rc.descendant_works(after_matrix, "progress:phase:PHASE-1") == {"WORK-1"}
    assert rc.descendant_works(after_matrix, "progress:lot:PHASE-1/LOT-1") == {"WORK-1"}
    assert rc.descendant_works(after_matrix, "progress:sublot:PHASE-1/LOT-1/SUB-1") == {"WORK-1"}
    assert rc.descendant_works(after_matrix, "progress:work:WORK-1:tests") == {"WORK-1"}
    assert rc.descendant_works(after_matrix, "work:WORK-1") == {"WORK-1"}
    assert rc.descendant_works(after_matrix, "progress:quality:security") == set()

    before_matrix = matrix("DONE")
    records = {
        ("before", "registry/progress/matrix.yaml"): before_matrix,
        ("after", "registry/progress/matrix.yaml"): after_matrix,
        ("after", "registry/work-items/WORK-1.yaml"): {"id": "WORK-1", "review_plan": {"open_findings": ["x"]}},
    }
    monkeypatch.setattr(cg, "changed_files", lambda root, before, after: ["registry/progress/matrix.yaml", "registry/work-items/WORK-1.yaml"])
    monkeypatch.setattr(cg, "show_yaml", lambda root, sha, path: records.get((sha, path)))
    findings = rc.validate_progress_reopening(tmp_path, [("before", "after")])
    assert findings and all(x.rule == "PROGRESS_REOPENING_EVIDENCE" for x in findings)

    records[("after", "registry/work-items/WORK-1.yaml")] = {
        "id": "WORK-1",
        "scope_change": {"approved": True, "rationale": "affected", "evidence": ["REVIEW-1"]},
    }
    assert rc.reopening_evidence_valid(tmp_path, "before", "after", "progress:work:WORK-1:tests", after_matrix)

    records[("after", "registry/work-items/WORK-1.yaml")] = {"id": "WORK-1"}
    records[("after", "registry/reviews/REVIEW-1.yaml")] = {
        "status": "COMPLETE", "outcome": "CHANGES_REQUIRED", "scope": {"work_items": ["WORK-1"]}
    }
    monkeypatch.setattr(cg, "changed_files", lambda root, before, after: ["registry/reviews/REVIEW-1.yaml"])
    assert rc.reopening_evidence_valid(tmp_path, "before", "after", "progress:work:WORK-1:tests", after_matrix)
    records[("after", "registry/reviews/REVIEW-1.yaml")]["scope"] = {"progress_keys": ["progress:quality:security"]}
    assert rc.reopening_evidence_valid(tmp_path, "before", "after", "progress:quality:security", after_matrix)


def test_done_review_substance(tmp_path: Path) -> None:
    dump(tmp_path / "registry/work-items/WORK-1.yaml", {
        "id": "WORK-1", "status": "DONE", "assurance": {"level": "A3"},
        "review_plan": {"independence_level": "L2_TARGET", "completed_reviews": ["REVIEW-1"]},
    })
    bad = good_review(); bad["reviewer"]["actor"] = ""
    dump(tmp_path / "registry/reviews/REVIEW-1.yaml", bad)
    assert {x.rule for x in rc.validate_done_review_substance(tmp_path)} == {"REVIEW_SUBSTANTIVE_L2"}
    dump(tmp_path / "registry/reviews/REVIEW-1.yaml", good_review())
    assert rc.validate_done_review_substance(tmp_path) == []
    dump(tmp_path / "registry/work-items/WORK-2.yaml", {
        "id": "WORK-2", "status": "DONE", "assurance": {"level": "A1"},
        "review_plan": {"independence_level": "L0", "completed_reviews": []},
    })
    assert rc.validate_done_review_substance(tmp_path) == []


def test_run_aggregates_validators(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cg, "pr_commit_edges", lambda root, base, head, require_guard=False: (["h"], [("b", "h")]))
    monkeypatch.setattr(rc, "validate_done_review_substance", lambda root: [rc.Finding("a", "A", "a")])
    monkeypatch.setattr(rc, "validate_requirement_acceptance", lambda root, edges: [rc.Finding("b", "B", "b")])
    monkeypatch.setattr(rc, "validate_historical_import_authorization", lambda root, edges: [rc.Finding("c", "C", "c")])
    monkeypatch.setattr(rc, "validate_progress_reopening", lambda root, edges: [rc.Finding("d", "D", "d")])
    assert [x.rule for x in rc.run(tmp_path, "b", "h")] == ["A", "B", "C", "D"]
