from pathlib import Path

import tools.governance.t11_closure as t11


def test_repository_t11_workflow_wiring_is_structurally_valid() -> None:
    root = Path(__file__).resolve().parents[2]
    assert t11.validate_workflow_structure(root) == []
