from __future__ import annotations

from pathlib import Path

from tools.governance.validate_repo import Record, Validator


def work_with_review(*, target: str) -> Record:
    return Record(
        "work-items",
        Path("registry/work-items/WORK-1.yaml"),
        {
            "id": "WORK-1",
            "review_plan": {
                "required_hats": [],
                "independence_level": target,
                "completed_reviews": ["REVIEW-1"],
            },
        },
    )


def review(*, level: str, outcome: str) -> Record:
    return Record(
        "reviews",
        Path("registry/reviews/REVIEW-1.yaml"),
        {
            "id": "REVIEW-1",
            "status": "COMPLETE",
            "outcome": outcome,
            "roles": [],
            "reviewer": {"independence_level": level},
            "findings": [],
        },
    )


def test_l3_target_requires_l3_evidence_only() -> None:
    validator = Validator(Path("."))
    validator.by_id = {"REVIEW-1": review(level="L2", outcome="APPROVE")}

    validator.validate_review_evidence(work_with_review(target="L3_TARGET"))

    assert len(validator.issues) == 1
    assert validator.issues[0].rule == "DONE_REVIEW"
    assert "independence" in validator.issues[0].message


def test_nonapproving_outcome_is_rejected_in_isolation() -> None:
    validator = Validator(Path("."))
    validator.by_id = {"REVIEW-1": review(level="L2", outcome="REJECT")}

    validator.validate_review_evidence(work_with_review(target="L2_TARGET"))

    assert len(validator.issues) == 1
    assert validator.issues[0].rule == "DONE_REVIEW"
    assert "outcome" in validator.issues[0].message
