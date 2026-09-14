from __future__ import annotations

from pathlib import Path

import tools.governance.change_guard as cg


def test_external_test_authorization_never_becomes_initial_state_exception(monkeypatch, tmp_path: Path) -> None:
    """A TEST import authorization applies to an existing-record edge only.

    If the TEST-specific introduction branch is removed, the generic import helper
    below would return True and incorrectly authorize direct PASS materialization.
    """

    monkeypatch.setattr(
        cg,
        "canonical_machine_spec",
        lambda *args: {"initial": "PLANNED", "historical_import_exceptions": []},
    )
    monkeypatch.setattr(cg, "historical_import_allowed", lambda *args: True)

    assert not cg.record_introduction_allowed(
        tmp_path,
        "parent",
        "materialize",
        "policy",
        "tests",
        {
            "id": "TEST-NEW",
            "status": "PASS",
            "external_import": {
                "authorization_source": "registry/status-machines.yaml@" + "a" * 40 + "#registry_machines.tests.external_execution_import_authorizations.TEST-NEW"
            },
        },
    )
