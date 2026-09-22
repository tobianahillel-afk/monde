from configparser import ConfigParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_t12_bootstrap_coverage_is_delegated_not_dropped() -> None:
    config = ConfigParser()
    config.read(ROOT / ".coveragerc-governance", encoding="utf-8")
    omit = config["run"]["omit"].split()
    assert ".github/scripts/stale_green_bootstrap*.py" in omit
    assert ".github/scripts/test_stale_green_bootstrap*.py" in omit

    governance = (ROOT / ".github/workflows/_governance-core.yml").read_text(encoding="utf-8")
    assert "--cov-config=.coveragerc-governance" in governance
    assert "--cov-fail-under=100" in governance

    bootstrap = (ROOT / ".github/workflows/monde-stale-green-bootstrap.yml").read_text(encoding="utf-8")
    assert "--fail-under=100" in bootstrap
    assert "--branch" in bootstrap
    assert "stale_green_bootstrap_authority_review0051_recovery.py" in bootstrap
