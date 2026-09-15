from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest
from unittest import mock

SCRIPT = Path(__file__).with_name("stale_green_bootstrap.py")
SPEC = importlib.util.spec_from_file_location("stale_green_bootstrap_incarnation", SCRIPT)
assert SPEC and SPEC.loader
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)


def pr(created_at: str = "2026-09-15T16:00:00Z") -> dict:
    return {
        "number": 7,
        "created_at": created_at,
        "head": {
            "sha": "shared",
            "ref": "feature",
            "repo": {"full_name": "o/r"},
        },
    }


def run(
    *,
    run_id: int,
    created_at: str,
    updated_at: str,
    conclusion: str = "success",
) -> dict:
    return {
        "workflow_id": bootstrap.CANONICAL_WORKFLOW_ID,
        "path": bootstrap.CANONICAL_WORKFLOW_PATH,
        "event": "pull_request",
        "head_sha": "shared",
        "head_branch": "feature",
        "head_repository": {"full_name": "o/r"},
        "run_number": run_id,
        "id": run_id,
        "conclusion": conclusion,
        "created_at": created_at,
        "updated_at": updated_at,
        "pull_requests": [{"number": 1}, {"number": 7}],
    }


def resolved_payload(*, errors_marker=object()) -> dict:
    payload = {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "nodes": [{"isResolved": True}],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }
    }
    if errors_marker.__class__ is not object:
        payload["errors"] = errors_marker
    return payload


class BootstrapIncarnationTests(unittest.TestCase):
    def test_current_pr_filter_rejects_older_incarnation_even_if_rerun_is_newer(self) -> None:
        old = run(
            run_id=10,
            created_at="2026-09-15T15:00:00Z",
            updated_at="2026-09-15T16:10:00Z",
        )
        current = run(
            run_id=11,
            created_at="2026-09-15T16:01:00Z",
            updated_at="2026-09-15T16:05:00Z",
            conclusion="failure",
        )
        with mock.patch.object(bootstrap, "paged", return_value=[old, current]):
            effective = bootstrap.latest_completed_gate_runs("o/r", "t")
        self.assertEqual(effective[("o/r", "feature", "shared")]["id"], 10)

        current_pr = pr()
        with mock.patch.object(bootstrap, "paged", return_value=[old, current]):
            target = bootstrap.latest_completed_gate_runs(
                "o/r",
                "t",
                bootstrap._current_prs([current_pr]),
            )
        self.assertEqual(target[("o/r", "feature", "shared")]["id"], 11)

    def test_current_pr_filter_fails_closed_on_missing_or_invalid_temporal_boundary(self) -> None:
        current = run(
            run_id=11,
            created_at="2026-09-15T16:01:00Z",
            updated_at="2026-09-15T16:05:00Z",
        )
        for bad_pr_time in (None, "", "not-a-date", "2026-09-15T16:00:00"):
            current_pr = pr()
            current_pr["created_at"] = bad_pr_time
            with self.subTest(pr_created_at=bad_pr_time), mock.patch.object(bootstrap, "paged", return_value=[current]):
                with self.assertRaisesRegex(RuntimeError, "open pull request created_at"):
                    bootstrap.latest_completed_gate_runs(
                        "o/r",
                        "t",
                        bootstrap._current_prs([current_pr]),
                    )

        for bad_run_time in (None, "", "not-a-date", "2026-09-15T16:01:00"):
            bad_run = dict(current)
            bad_run["created_at"] = bad_run_time
            with self.subTest(run_created_at=bad_run_time), mock.patch.object(bootstrap, "paged", return_value=[bad_run]):
                with self.assertRaisesRegex(RuntimeError, "canonical MONDE Gate created_at"):
                    bootstrap.latest_completed_gate_runs(
                        "o/r",
                        "t",
                        bootstrap._current_prs([pr()]),
                    )

    def test_current_pr_filter_ignores_runs_for_other_head_identity(self) -> None:
        other = run(
            run_id=12,
            created_at="2026-09-15T16:01:00Z",
            updated_at="2026-09-15T16:05:00Z",
        )
        other["head_branch"] = "other"
        with mock.patch.object(bootstrap, "paged", return_value=[other]):
            self.assertEqual(
                bootstrap.latest_completed_gate_runs("o/r", "t", bootstrap._current_prs([pr()])),
                {},
            )

    def test_falsey_graphql_errors_members_are_rejected(self) -> None:
        for errors in ({}, "", 0, None):
            with self.subTest(errors=errors), mock.patch.object(
                bootstrap,
                "request_data",
                return_value=resolved_payload(errors_marker=errors),
            ):
                with self.assertRaisesRegex(RuntimeError, "malformed GraphQL response"):
                    bootstrap.unresolved_review_threads("o/r", 7, "t")

    def test_empty_graphql_errors_list_is_accepted(self) -> None:
        with mock.patch.object(
            bootstrap,
            "request_data",
            return_value=resolved_payload(errors_marker=[]),
        ):
            self.assertFalse(bootstrap.unresolved_review_threads("o/r", 7, "t"))

    def test_poll_reruns_current_incarnation_when_old_rerun_is_effective_success(self) -> None:
        current_pr = pr()
        old = run(
            run_id=10,
            created_at="2026-09-15T15:00:00Z",
            updated_at="2026-09-15T16:10:00Z",
        )
        current = run(
            run_id=11,
            created_at="2026-09-15T16:01:00Z",
            updated_at="2026-09-15T16:05:00Z",
            conclusion="failure",
        )
        effective = {("o/r", "feature", "shared"): old}
        current_only = {("o/r", "feature", "shared"): current}
        with mock.patch.object(bootstrap, "open_pull_requests", return_value=[current_pr]), mock.patch.object(
            bootstrap,
            "latest_completed_gate_runs",
            side_effect=[effective, current_only],
        ), mock.patch.object(bootstrap, "unresolved_review_threads", return_value=True), mock.patch.object(
            bootstrap,
            "rerun_workflow",
        ) as rerun:
            self.assertEqual(bootstrap.poll("o/r", "t"), [11])
        rerun.assert_called_once_with("o/r", 11, "t")


if __name__ == "__main__":
    unittest.main()
