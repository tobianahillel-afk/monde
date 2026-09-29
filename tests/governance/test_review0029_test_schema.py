from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]


def validator() -> Draft202012Validator:
    schema = json.loads((ROOT / "schemas/registry/tests.schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def base_record(status: str) -> dict:
    return {
        "id": "TEST-9999",
        "name": "schema regression",
        "status": status,
        "type": "MANUAL_E2E",
        "protects": {"contracts": ["contract"]},
        "cases": {"happy_path": ["x"]},
        "execution": {
            "command_or_workflow": "manual",
            "commit_sha": None,
            "result": "PASS_WITH_FINDINGS_RESOLVED",
            "evidence": ["historical evidence"],
        },
    }


def test_non_pass_historical_execution_may_preserve_unknown_sha() -> None:
    record = base_record("SUPERSEDED")
    assert list(validator().iter_errors(record)) == []


def test_pass_requires_revision_bound_sha_and_exact_pass_result() -> None:
    record = base_record("PASS")
    errors = list(validator().iter_errors(record))
    assert errors

    record["execution"]["commit_sha"] = "a" * 40
    record["execution"]["result"] = "PASS"
    assert list(validator().iter_errors(record)) == []
