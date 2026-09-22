from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[2]


def test_t12_bootstrap_coverage_is_delegated_not_dropped() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    omit = set(config["tool"]["coverage"]["run"]["omit"])
    assert ".github/scripts/stale_green_bootstrap*.py" in omit
    assert ".github/scripts/test_stale_green_bootstrap*.py" in omit

    workflow = (ROOT / ".github/workflows/monde-stale-green-bootstrap.yml").read_text(encoding="utf-8")
    assert "--cov-fail-under=100" in workflow
    assert "--cov-branch" in workflow
    assert "stale_green_bootstrap_authority_review0051_recovery.py" in workflow
