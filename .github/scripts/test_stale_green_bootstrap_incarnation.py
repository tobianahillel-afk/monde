from __future__ import annotations

from datetime import datetime
import importlib.util
from pathlib import Path
import unittest
from unittest import mock

SCRIPT = Path(__file__).with_name("stale_green_bootstrap.py")
SPEC = importlib.util.spec_from_file_location("stale_green_bootstrap_incarnation", SCRIPT)
assert SPEC and SPEC.loader
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)


def pr(
    created_at: str = "2026-09-15T16:00:00Z",
    *,
    number: int = 7,
    head: str = "shared",
    branch: str = "feature",
    repo_name: str = "o/r",
) -> dict:
    return {
        "number": number,
        "state": "open",
        "created_at": created_at,
        "closed_at": None,
        "head": {
            "sha": head,
            "ref": branch,
            "repo": {"full_name": repo_name},
        },
    }


def closed_pr(
    number: int,
    *,
    created_at: str,
    closed_at: str,
    head: str = "shared",
    branch: str = "feature",
    repo_name: str = "o/r",
    state: str = "closed",
) -> dict:
    return {
        "number": number,
        "state": state,
        "created_at": created_at,
        "closed_at": closed_at,
        "head": {
            "sha": head,
            "ref": branch,
            "repo": {"full_name": repo_name},
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
        "status": "completed",
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
                {("o/r", "feature", "shared"): []},
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
                with self.assertRaisesRegex(RuntimeError, "pull request created_at"):
                    bootstrap.latest_completed_gate_runs(
                        "o/r",
                        "t",
                        bootstrap._current_prs([current_pr]),
                        {("o/r", "feature", "shared"): []},
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
                        {("o/r", "feature", "shared"): []},
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
                bootstrap.latest_completed_gate_runs(
                    "o/r",
                    "t",
                    bootstrap._current_prs([pr()]),
                    {("o/r", "feature", "shared"): []},
                ),
                {},
            )

    def test_overlap_windows_capture_prior_and_later_overlapping_pr_lifetimes(self) -> None:
        current = pr()
        same_branch_other_sha = pr(number=8, head="current-other")
        histories = [
            closed_pr(
                1,
                created_at="2026-09-15T15:00:00Z",
                closed_at="2026-09-15T16:03:00Z",
            ),
            closed_pr(
                2,
                created_at="2026-09-15T16:02:00Z",
                closed_at="2026-09-15T16:05:00Z",
            ),
            closed_pr(
                3,
                created_at="2026-09-15T14:00:00Z",
                closed_at="2026-09-15T15:59:59Z",
            ),
            closed_pr(
                4,
                created_at="2026-09-15T15:00:00Z",
                closed_at="2026-09-15T16:05:00Z",
                head="different-sha",
            ),
        ]
        current_map = bootstrap._current_prs([current, same_branch_other_sha])
        with mock.patch.object(bootstrap, "paged", return_value=histories) as paged:
            windows = bootstrap.overlapping_closed_pr_windows("o/r", "t", current_map)
        expected = [
            (
                datetime.fromisoformat("2026-09-15T16:00:00+00:00"),
                datetime.fromisoformat("2026-09-15T16:03:00+00:00"),
            ),
            (
                datetime.fromisoformat("2026-09-15T16:02:00+00:00"),
                datetime.fromisoformat("2026-09-15T16:05:00+00:00"),
            ),
            (
                datetime.fromisoformat("2026-09-15T16:00:00+00:00"),
                datetime.fromisoformat("2026-09-15T16:05:00+00:00"),
            ),
        ]
        identity = ("o/r", "feature", "shared")
        self.assertEqual(windows[identity], expected)
        self.assertEqual(windows[("o/r", "feature", "current-other")], expected)
        self.assertEqual(paged.call_count, 1)
        self.assertIn("state=closed", paged.call_args.args[0])
        self.assertIn("head=o%3Afeature", paged.call_args.args[0])

    def test_branch_reset_history_excludes_old_run_when_closed_snapshot_sha_differs(self) -> None:
        current_pr = pr()
        identity = ("o/r", "feature", "shared")
        history = closed_pr(
            1,
            created_at="2026-09-15T15:00:00Z",
            closed_at="2026-09-15T16:05:00Z",
            head="different-sha",
        )
        with mock.patch.object(bootstrap, "paged", return_value=[history]):
            windows = bootstrap.overlapping_closed_pr_windows(
                "o/r",
                "t",
                bootstrap._current_prs([current_pr]),
            )
        self.assertEqual(
            windows[identity],
            [
                (
                    datetime.fromisoformat("2026-09-15T16:00:00+00:00"),
                    datetime.fromisoformat("2026-09-15T16:05:00+00:00"),
                )
            ],
        )

        ambiguous_old = run(
            run_id=10,
            created_at="2026-09-15T16:01:00Z",
            updated_at="2026-09-15T16:10:00Z",
        )
        current_after_overlap = run(
            run_id=11,
            created_at="2026-09-15T16:06:00Z",
            updated_at="2026-09-15T16:07:00Z",
            conclusion="failure",
        )
        with mock.patch.object(bootstrap, "paged", return_value=[ambiguous_old, current_after_overlap]):
            target = bootstrap.latest_completed_gate_runs(
                "o/r",
                "t",
                bootstrap._current_prs([current_pr]),
                windows,
            )
        self.assertEqual(target[identity]["id"], 11)

    def test_overlap_windows_fail_closed_on_malformed_closed_pr_history(self) -> None:
        identity_map = bootstrap._current_prs([pr()])
        malformed = [
            closed_pr(True, created_at="2026-09-15T15:00:00Z", closed_at="2026-09-15T16:01:00Z"),
            closed_pr(1, created_at="2026-09-15T15:00:00Z", closed_at="2026-09-15T16:01:00Z", state="open"),
        ]
        for row in malformed:
            with self.subTest(row=row), mock.patch.object(bootstrap, "paged", return_value=[row]):
                with self.assertRaisesRegex(RuntimeError, "malformed closed pull request"):
                    bootstrap.overlapping_closed_pr_windows("o/r", "t", identity_map)

        bad_closed = closed_pr(1, created_at="2026-09-15T15:00:00Z", closed_at="")
        with mock.patch.object(bootstrap, "paged", return_value=[bad_closed]):
            with self.assertRaisesRegex(RuntimeError, "closed pull request closed_at"):
                bootstrap.overlapping_closed_pr_windows("o/r", "t", identity_map)

        backwards = closed_pr(1, created_at="2026-09-15T16:02:00Z", closed_at="2026-09-15T16:01:00Z")
        with mock.patch.object(bootstrap, "paged", return_value=[backwards]):
            with self.assertRaisesRegex(RuntimeError, "invalid lifetime"):
                bootstrap.overlapping_closed_pr_windows("o/r", "t", identity_map)

        bad_repo = pr(repo_name="malformed")
        with self.assertRaisesRegex(RuntimeError, "repository full_name"):
            bootstrap.overlapping_closed_pr_windows("o/r", "t", bootstrap._current_prs([bad_repo]))

    def test_overlap_window_excludes_ambiguous_old_pr_run_but_preserves_pre_overlap_current_run(self) -> None:
        current_pr = pr()
        identity = ("o/r", "feature", "shared")
        windows = {
            identity: [
                (
                    datetime.fromisoformat("2026-09-15T16:00:00+00:00"),
                    datetime.fromisoformat("2026-09-15T16:03:00+00:00"),
                )
            ]
        }
        ambiguous_old = run(
            run_id=10,
            created_at="2026-09-15T16:01:00Z",
            updated_at="2026-09-15T16:10:00Z",
        )
        current_after_overlap = run(
            run_id=11,
            created_at="2026-09-15T16:04:00Z",
            updated_at="2026-09-15T16:05:00Z",
            conclusion="failure",
        )
        with mock.patch.object(bootstrap, "paged", return_value=[ambiguous_old, current_after_overlap]):
            effective = bootstrap.latest_completed_gate_runs("o/r", "t")
        self.assertEqual(effective[identity]["id"], 10)
        with mock.patch.object(bootstrap, "paged", return_value=[ambiguous_old, current_after_overlap]):
            target = bootstrap.latest_completed_gate_runs(
                "o/r",
                "t",
                bootstrap._current_prs([current_pr]),
                windows,
            )
        self.assertEqual(target[identity]["id"], 11)

        later_overlap = {
            identity: [
                (
                    datetime.fromisoformat("2026-09-15T17:00:00+00:00"),
                    datetime.fromisoformat("2026-09-15T17:05:00+00:00"),
                )
            ]
        }
        pre_overlap_current = run(
            run_id=12,
            created_at="2026-09-15T16:30:00Z",
            updated_at="2026-09-15T16:31:00Z",
        )
        with mock.patch.object(bootstrap, "paged", return_value=[pre_overlap_current]):
            target = bootstrap.latest_completed_gate_runs(
                "o/r",
                "t",
                bootstrap._current_prs([current_pr]),
                later_overlap,
            )
        self.assertEqual(target[identity]["id"], 12)

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
            "overlapping_closed_pr_windows",
            return_value={},
        ), mock.patch.object(
            bootstrap,
            "latest_completed_gate_runs",
            side_effect=[effective, current_only],
        ), mock.patch.object(
            bootstrap,
            "required_merge_gate_conclusion",
            return_value="success",
        ), mock.patch.object(bootstrap, "unresolved_review_threads", return_value=True), mock.patch.object(
            bootstrap,
            "rerun_workflow",
        ) as rerun:
            self.assertEqual(bootstrap.poll("o/r", "t"), [11])
        rerun.assert_called_once_with("o/r", 11, "t")


if __name__ == "__main__":
    unittest.main()
