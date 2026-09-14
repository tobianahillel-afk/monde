from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SHA = "a" * 40


def load_gate():
    hardening_path = ROOT / ".github/scripts/governance_l2_hardening.py"
    if "governance_l2_hardening" not in sys.modules:
        spec_h = importlib.util.spec_from_file_location("governance_l2_hardening", hardening_path)
        assert spec_h is not None and spec_h.loader is not None
        module_h = importlib.util.module_from_spec(spec_h)
        sys.modules["governance_l2_hardening"] = module_h
        spec_h.loader.exec_module(module_h)
    followup_path = ROOT / ".github/scripts/governance_l2_followup.py"
    if "governance_l2_followup" not in sys.modules:
        spec_f = importlib.util.spec_from_file_location("governance_l2_followup", followup_path)
        assert spec_f is not None and spec_f.loader is not None
        module_f = importlib.util.module_from_spec(spec_f)
        sys.modules["governance_l2_followup"] = module_f
        spec_f.loader.exec_module(module_f)
    if "governance_l2_gate" in sys.modules:
        return sys.modules["governance_l2_gate"]
    path = ROOT / ".github/scripts/governance_l2_gate.py"
    spec = importlib.util.spec_from_file_location("governance_l2_gate", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["governance_l2_gate"] = module
    spec.loader.exec_module(module)
    return module


def test_progress_adoption_returns_none_when_no_matching_rule(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    gate = load_gate()
    monkeypatch.setattr(
        gate.h,
        "load_mapping",
        lambda *a: {"enforcement_adoptions": [{"rule_id": "OTHER_RULE"}]},
    )
    assert gate.progress_adoption_sha(tmp_path, SHA) is None
