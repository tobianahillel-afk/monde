from pathlib import Path

import yaml

from tools.governance.validate_repo import Record, Validator


def test_template_continue_has_following_record(tmp_path: Path) -> None:
    d = tmp_path / "registry/work-items"
    d.mkdir(parents=True)
    (d / "_TEMPLATE.yaml").write_text("id: WORK-999\nstatus: BOGUS\n", encoding="utf-8")
    (d / "z.yaml").write_text("id: WORK-1\nstatus: IN_PROGRESS\n", encoding="utf-8")
    v = Validator(tmp_path)
    v.discover_records()
    assert [r.id for r in v.records] == ["WORK-1"]


def test_missing_review_continue_then_valid_review(tmp_path: Path) -> None:
    v = Validator(tmp_path)
    work_path = tmp_path / "work.yaml"
    review_path = tmp_path / "review.yaml"
    work = Record("work-items", work_path, {
        "id": "WORK-1",
        "review_plan": {
            "required_hats": ["SECURITY"],
            "independence_level": "L2_TARGET",
            "completed_reviews": ["REVIEW-404", "REVIEW-1"],
        },
    })
    good = Record("reviews", review_path, {
        "id": "REVIEW-1",
        "status": "COMPLETE",
        "outcome": "APPROVED",
        "roles": ["SECURITY"],
        "reviewer": {"independence_level": "L2"},
        "findings": [],
    })
    v.by_id = {"REVIEW-1": good}
    v.validate_review_evidence(work)
    assert any(x.rule == "DONE_REVIEW" and "REVIEW-404" in x.message for x in v.issues)


def test_git_markdown_skip_continues_to_normal_file(tmp_path: Path) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "bad.md").write_text("Status: Accepted\nCanonical: Yes\nTODO\n", encoding="utf-8")
    (tmp_path / "z.md").write_text("# ok\n", encoding="utf-8")
    v = Validator(tmp_path)
    v.validate_markdown()
    assert not v.issues


def test_bad_workflow_yaml_continue_to_next_workflow(tmp_path: Path) -> None:
    d = tmp_path / ".github/workflows"
    d.mkdir(parents=True)
    (d / "a.yml").write_text("jobs: [", encoding="utf-8")
    (d / "z.yml").write_text(yaml.safe_dump({"jobs": {}}), encoding="utf-8")
    v = Validator(tmp_path)
    v.validate_action_pins()
    assert not v.issues
