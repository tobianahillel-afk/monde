from __future__ import annotations

import unittest
from unittest import mock

from test_stale_green_bootstrap_authority import check, gate_run, pr
import stale_green_bootstrap_authority as authority


class Review0046CoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        authority._reset_request_budget()
        self.addCleanup(authority._reset_request_budget)

    def test_check_page_filters_nonterminal_and_reference_metadata_fails_closed(self) -> None:
        pending = check(501, 101, status="in_progress", conclusion=None)
        payload = {"total_count": 1, "check_runs": [pending]}
        with mock.patch.object(authority.core, "request_data", return_value=payload):
            self.assertEqual(
                authority._candidate_gate_check_page("o/r", "shared-head", "t", 1),
                ([], False),
            )

        malformed = gate_run(101, 1)
        malformed["referenced_workflows"][0]["sha"] = "bad"
        with self.assertRaisesRegex(RuntimeError, "malformed referenced workflow metadata"):
            authority._triggering_pr_authority("o/r", malformed)

        mixed = gate_run(101, 1)
        unrelated = dict(mixed["referenced_workflows"][0])
        unrelated["path"] = f"other/r/{authority._REUSABLE_WORKFLOW_PATH}@{unrelated['sha']}"
        mixed["referenced_workflows"] = [unrelated, mixed["referenced_workflows"][0]]
        self.assertEqual(authority._triggering_pr_authority("o/r", mixed), (1, mixed["referenced_workflows"][1]["sha"]))

    def test_noncompleted_run_validation_fails_closed(self) -> None:
        base = gate_run(101, 1)

        missing_status = dict(base)
        missing_status["status"] = ""
        missing_status["conclusion"] = None
        with self.assertRaisesRegex(RuntimeError, "malformed canonical"):
            authority._validate_canonical_run(
                missing_status, 101, "shared-head", require_completed=False
            )

        completed_without_conclusion = dict(base)
        completed_without_conclusion["conclusion"] = None
        with self.assertRaisesRegex(RuntimeError, "malformed canonical"):
            authority._validate_canonical_run(
                completed_without_conclusion, 101, "shared-head", require_completed=False
            )

        incomplete_with_conclusion = dict(base)
        incomplete_with_conclusion["status"] = "in_progress"
        incomplete_with_conclusion["conclusion"] = "success"
        with self.assertRaisesRegex(RuntimeError, "incomplete canonical"):
            authority._validate_canonical_run(
                incomplete_with_conclusion, 101, "shared-head", require_completed=False
            )

    def test_target_scan_defers_between_pages_and_waiter_requires_terminal_causality(self) -> None:
        current = pr(1, branch="shared", head="shared-head")

        def exhaust_after_page(*_args, **_kwargs):
            authority._request_count = (
                authority.MAX_GITHUB_REQUESTS_PER_INVOCATION
                - authority.MIN_TARGET_REQUEST_HEADROOM
                + 1
            )
            return [], True

        with mock.patch.object(
            authority, "_candidate_gate_check_page", side_effect=exhaust_after_page
        ):
            with self.assertRaisesRegex(authority.DeferredForBudget, "before target check page"):
                authority._direct_target_for_pr("o/r", "t", current)
        authority._reset_request_budget()

        with mock.patch.object(authority.core, "request_data", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "malformed rerun post-condition"):
                authority._wait_for_terminal_invalidation(
                    "o/r", "shared-head", "t", 101, 1, 10
                )

        terminal = gate_run(101, 1)
        terminal.update({"run_attempt": 2, "status": "completed", "conclusion": "failure"})
        previous = check(10, 101)
        failed = check(11, 101, conclusion="failure")
        with (
            mock.patch.object(authority.core, "request_data", return_value=terminal) as run_read,
            mock.patch.object(
                authority.core, "required_merge_gate_conclusion", return_value="failure"
            ),
            mock.patch.object(
                authority.core, "latest_required_check", side_effect=[previous, failed]
            ),
            mock.patch.object(authority.time, "sleep") as sleeper,
        ):
            self.assertTrue(
                authority._wait_for_terminal_invalidation(
                    "o/r", "shared-head", "t", 101, 1, 10
                )
            )
        run_read.assert_called_once()
        sleeper.assert_called_once()

        with (
            mock.patch.object(authority.core, "request_data", return_value=terminal),
            mock.patch.object(
                authority.core, "required_merge_gate_conclusion", return_value="failure"
            ),
            mock.patch.object(
                authority.core, "latest_required_check", side_effect=[None, failed]
            ),
            mock.patch.object(authority.time, "sleep"),
        ):
            self.assertTrue(
                authority._wait_for_terminal_invalidation(
                    "o/r", "shared-head", "t", 101, 1, 10
                )
            )

    def test_scan_order_and_head_group_failure_paths(self) -> None:
        first = pr(1, branch="shared", head="shared-head")
        second = pr(2, branch="shared", head="shared-head")
        self.assertEqual(
            [item["number"] for item in authority._ordered_group_for_scan([second, first], 0)],
            [1, 2],
        )
        self.assertEqual(
            [item["number"] for item in authority._ordered_group_for_scan([second, first], 99)],
            [1, 2],
        )
        self.assertEqual(
            [item["number"] for item in authority._ordered_group_for_scan([second, first], 2)],
            [2, 1],
        )

        latest = check(600, 200)
        with (
            mock.patch.object(authority.core, "latest_required_check", return_value=latest),
            mock.patch.object(authority.core, "unresolved_review_threads", return_value=False),
        ):
            self.assertEqual(
                authority._process_head_group("o/r", "t", [first], 3),
                ([], [], None),
            )

        with (
            mock.patch.object(authority.core, "latest_required_check", return_value=latest),
            mock.patch.object(authority.core, "unresolved_review_threads", return_value=True),
            mock.patch.object(authority, "_direct_target_for_pr", return_value=(None, None)),
        ):
            posted, errors, continuation = authority._process_head_group(
                "o/r", "t", [first], 3
            )
        self.assertEqual(posted, [])
        self.assertEqual(continuation, None)
        self.assertEqual(len(errors), 1)

        target = (gate_run(101, 1), check(501, 101))
        with (
            mock.patch.object(authority.core, "latest_required_check", return_value=latest),
            mock.patch.object(authority.core, "unresolved_review_threads", return_value=True),
            mock.patch.object(authority, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(authority, "_current_pr", return_value=None),
        ):
            self.assertEqual(
                authority._process_head_group("o/r", "t", [first], 3),
                ([], [], None),
            )

        with (
            mock.patch.object(authority.core, "latest_required_check", side_effect=[latest, latest]),
            mock.patch.object(
                authority.core, "unresolved_review_threads", side_effect=[True, True, True]
            ),
            mock.patch.object(authority, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(authority, "_current_pr", return_value=first),
            mock.patch.object(authority.core, "rerun_workflow"),
            mock.patch.object(authority, "_wait_for_terminal_invalidation", return_value=False),
        ):
            with self.assertRaisesRegex(RuntimeError, "completed merge-acceptable"):
                authority._process_head_group("o/r", "t", [first], 3)

    def test_poll_continuation_with_prior_error_fails_after_persisting_state(self) -> None:
        first = pr(1)
        state = authority.SchedulerState(0, 0, 1)
        with (
            mock.patch.object(authority, "_read_scheduler_state", return_value=state),
            mock.patch.object(authority.snapshot, "open_pull_requests", return_value=[first]),
            mock.patch.object(
                authority,
                "_process_head_group",
                return_value=([], ["missing target"], (1, 3)),
            ),
            mock.patch.object(authority, "_write_scheduler_state") as writer,
        ):
            with self.assertRaisesRegex(RuntimeError, "missing target"):
                authority.poll("o/r", "t")
        writer.assert_called_once_with(
            "o/r", "t", authority.SchedulerState(0, 1, 3)
        )

        resumed = authority.SchedulerState(0, 9, 4)
        with (
            mock.patch.object(authority, "_read_scheduler_state", return_value=resumed),
            mock.patch.object(authority.snapshot, "open_pull_requests", return_value=[first]),
            mock.patch.object(
                authority, "_process_head_group", return_value=([], [], None)
            ),
            mock.patch.object(authority, "_write_scheduler_state") as writer,
        ):
            self.assertEqual(authority.poll("o/r", "t"), [])
        writer.assert_called_once_with(
            "o/r", "t", authority.SchedulerState(1, 0, 1)
        )


if __name__ == "__main__":
    unittest.main()
