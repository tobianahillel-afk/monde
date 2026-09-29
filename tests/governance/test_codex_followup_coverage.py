from __future__ import annotations

from pathlib import Path

import tools.governance.change_guard as cg
from tools.governance.strict_contracts import test_external_import_bound_and_consumed


def imported_test() -> dict:
    return {
        "id": "TEST-1",
        "status": "PASS",
        "external_import": {
            "authorization_source": "registry/status-machines.yaml@" + "a" * 40 + "#registry_machines.tests.external_execution_import_authorizations.TEST-1",
            "import_commit": None,
        },
        "acceptance_cold_read": {
            "source": {"source_id": "RUN", "submitted_at": "2026-09-14T00:00:00Z"},
            "executor": {"context_id": "ctx"},
        },
        "execution": {"commit_sha": "b" * 40, "result": "PASS"},
    }


def test_external_test_transition_rejects_missing_or_malformed_authorization(monkeypatch, tmp_path: Path) -> None:
    previous = {"id": "TEST-1", "status": "PLANNED"}
    current = imported_test()

    monkeypatch.setattr(cg, "commit_exists", lambda root, sha: False)
    assert not cg.test_external_execution_transition_allowed(tmp_path, "parent", "transition", previous, current)

    monkeypatch.setattr(cg, "commit_exists", lambda root, sha: True)
    monkeypatch.setattr(cg, "is_ancestor", lambda root, ancestor, descendant: True)
    monkeypatch.setattr(
        cg,
        "canonical_machine_spec",
        lambda *args: {
            "external_execution_import_authorizations": [
                "not-a-mapping",
                {"record_id": "TEST-OTHER", "from_status": "PLANNED", "imported_status": "PASS"},
            ]
        },
    )
    assert not cg.test_external_execution_transition_allowed(tmp_path, "parent", "transition", previous, current)


def test_delegation_rejects_non_mapping_scope(monkeypatch, tmp_path: Path) -> None:
    risk = {
        "id": "RISK-1",
        "scope": {"work_items": ["WORK-1"]},
        "resolution": {
            "accepted": True,
            "accepted_by": "alice",
            "authority_role": "DESIGNATED_RISK_AUTHORITY",
            "authority_evidence_type": "GOVERNANCE_DELEGATION",
            "authority_evidence_ref": "registry/delegation.yaml",
            "authority_matrix_version": 1,
            "authority_rule_id": "RULE",
        },
    }
    policy = {
        "version": 1,
        "governed_repository": {"full_name": "owner/monde"},
        "vocabulary": {
            "authority_roles": {
                "DESIGNATED_RISK_AUTHORITY": {"allowed_evidence_types": ["GOVERNANCE_DELEGATION"]}
            }
        },
    }
    records = {
        "registry/status-machines.yaml": {"registry_machines": {"risks": {"acceptance_preconditions": {"required_fields": []}}}},
        "registry/acceptance-authority.yaml": policy,
        "registry/delegation.yaml": {
            "actor": "alice",
            "role": "DESIGNATED_RISK_AUTHORITY",
            "scope": "not-a-mapping",
        },
    }
    monkeypatch.setattr(cg, "show_yaml", lambda root, sha, path: records.get(path))
    monkeypatch.setattr(cg, "resolve_risk_authority_rule", lambda *args, **kwargs: ("RULE", ["DESIGNATED_RISK_AUTHORITY"]))
    assert not cg.risk_acceptance_satisfied(tmp_path, "sha", risk)


def test_strict_test_import_rejects_structured_bad_binding() -> None:
    bad = {
        "status": "PASS",
        "external_import": {"authorization_source": "not-canonical", "import_commit": "c" * 40},
    }
    assert not test_external_import_bound_and_consumed(bad, {})
