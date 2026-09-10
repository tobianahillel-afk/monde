from __future__ import annotations

from pathlib import Path

from tools.governance.strict_contracts import review_targets, validate_action_surfaces


def test_review_targets_rejects_nonmapping_scope() -> None:
    assert review_targets({"scope": ["WORK-0001"]}) == set()


def test_strict_action_surface_rejects_unpinned_docker(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    workflow = root / ".github/workflows/docker.yaml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(
        "jobs:\n  x:\n    steps:\n      - uses: docker://alpine:latest\n",
        encoding="utf-8",
    )

    issues = validate_action_surfaces(root)

    assert len(issues) == 1
    assert issues[0].rule == "ACTION_PIN"
    assert "sha256" in issues[0].message
