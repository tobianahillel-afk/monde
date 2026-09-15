from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest
from unittest import mock

SCRIPT = Path(__file__).with_name("stale_green_bootstrap.py")
SPEC = importlib.util.spec_from_file_location("stale_green_bootstrap_run_created_at", SCRIPT)
assert SPEC and SPEC.loader
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)


def gate_run(*, branch: str, run_id: int, conclusion: str, created_at: object) -> dict:
    return {
        "workflow_id": bootstrap.CANONICAL_WORKFLOW_ID,
        "path": bootstrap.CANONICAL_WORKFLOW_PATH,
        "event": "pull_request",
        "head_sha": "shared",
        "head_branch": branch,
        "head_repository": {"full_name": "o/r"},
        "run_number": run_id,
        "id": run_id,
        "conclusion": conclusion,
        "created_at": created_at,
        "updated_at": f"2026-09-15T17:00:{run_id:02d}Z",
        "pull_requests": [],
    }


def current_pr() -> dict:
    return {
        "number": 7,
        "state": "open",
        "created_at": "2026-09-15T16:00:00Z",
        "closed_at": None,
        "head": {
            "sha": "shared",
            "ref": "alpha",
            "repo": {"full_name": "o/r"},
        },
    }


class RunCreatedAtValidationTests(unittest.TestCase):
    def test_created_at_is_validated_before_head_identity_filtering(self) -> None:
        valid_target = gate_run(
            branch="alpha",
            run_id=10,
            conclusion="success",
            created_at="2026-09-15T16:30:00Z",
        )
        malformed_other_branch = gate_run(
            branch="beta",
            run_id=11,
            conclusion="failure",
            created_at="not-a-date",
        )
        rows = [valid_target, malformed_other_branch]

        with mock.patch.object(bootstrap, "paged", return_value=rows):
            with self.assertRaisesRegex(RuntimeError, "canonical MONDE Gate created_at"):
                bootstrap.latest_completed_gate_runs("o/r", "t")

        identity = ("o/r", "alpha", "shared")
        with mock.patch.object(bootstrap, "paged", return_value=rows):
            with self.assertRaisesRegex(RuntimeError, "canonical MONDE Gate created_at"):
                bootstrap.latest_completed_gate_runs(
                    "o/r",
                    "t",
                    {identity: current_pr()},
                    {identity: []},
                )

    def test_created_at_rejects_missing_or_naive_values_for_nonmatching_runs(self) -> None:
        identity = ("o/r", "alpha", "shared")
        for value in (None, "", "2026-09-15T16:30:00"):
            malformed = gate_run(
                branch="beta",
                run_id=12,
                conclusion="failure",
                created_at=value,
            )
            with self.subTest(created_at=value), mock.patch.object(bootstrap, "paged", return_value=[malformed]):
                with self.assertRaisesRegex(RuntimeError, "canonical MONDE Gate created_at"):
                    bootstrap.latest_completed_gate_runs(
                        "o/r",
                        "t",
                        {identity: current_pr()},
                        {identity: []},
                    )


if __name__ == "__main__":
    unittest.main()
