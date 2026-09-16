from __future__ import annotations

import os
import runpy
import unittest
from unittest import mock

from test_stale_green_bootstrap_authority import check, gate_run, job, pr
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0048 as subject


class Review0048EdgeTests(unittest.TestCase):
    def setUp(self) -> None:
        base._reset_request_budget()
        self.addCleanup(base._reset_request_budget)

    def test_target_scan_budget_anchor_and_metadata_guards(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        minimum = base.MIN_TARGET_REQUEST_HEADROOM

        with mock.patch.object(base, "_remaining_request_budget", return_value=minimum - 1):
            with self.assertRaises(base.DeferredForBudget):
                subject._direct_target_for_pr("o/r", "t", current)

        without_merge = pr(1, branch="shared", head="shared-head", merge_sha=None)
        with self.assertRaisesRegex(RuntimeError, "merge-ref SHA"):
            subject._direct_target_for_pr("o/r", "t", without_merge)

        with mock.patch.object(
            base, "_candidate_gate_check_page", return_value=([], False)
        ) as pages:
            self.assertEqual(
                subject._direct_target_for_pr("o/r", "t", current, 2, "bad"),
                (None, None),
            )
        pages.assert_called_once_with("o/r", "shared-head", "t", 1)

        anchor = base._check_page_anchor([], True)
        with mock.patch.object(
            base,
            "_candidate_gate_check_page",
            side_effect=[([], False), ([], False)],
        ) as pages:
            self.assertEqual(
                subject._direct_target_for_pr("o/r", "t", current, 2, anchor),
                (None, None),
            )
        self.assertEqual([call.args[3] for call in pages.call_args_list], [1, 1])

        with (
            mock.patch.object(
                base, "_remaining_request_budget", side_effect=[minimum, minimum - 1]
            ),
            mock.patch.object(base, "_candidate_gate_check_page") as pages,
        ):
            with self.assertRaises(base.DeferredForBudget):
                subject._direct_target_for_pr("o/r", "t", current)
        pages.assert_not_called()

        with (
            mock.patch.object(
                base,
                "_remaining_request_budget",
                side_effect=[minimum, minimum, minimum - 1],
            ),
            mock.patch.object(
                base,
                "_candidate_gate_check_page",
                side_effect=[([], True), ([], False)],
            ),
        ):
            with self.assertRaises(base.DeferredForBudget):
                subject._direct_target_for_pr("o/r", "t", current, 2, anchor)

        candidate = check(501, 101)
        with (
            mock.patch.object(
                base,
                "_remaining_request_budget",
                side_effect=[minimum, minimum, 0],
            ),
            mock.patch.object(
                base, "_candidate_gate_check_page", return_value=([candidate], False)
            ),
        ):
            with self.assertRaises(base.DeferredForBudget):
                subject._direct_target_for_pr("o/r", "t", current)

    def test_target_scan_filters_non_authoritative_runs_and_rejects_malformed_payloads(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        checks = [check(501, 101), check(502, 102), check(503, 103)]
        wrong_head = gate_run(101, 1, head="other-head")
        too_old = gate_run(102, 1, created_at="2026-09-15T13:00:00Z")
        wrong_pr = gate_run(103, 2)
        with (
            mock.patch.object(
                base, "_candidate_gate_check_page", return_value=(checks, False)
            ),
            mock.patch.object(
                subject.core,
                "request_data",
                side_effect=[wrong_head, too_old, wrong_pr],
            ),
        ):
            self.assertEqual(
                subject._direct_target_for_pr("o/r", "t", current), (None, None)
            )

        with (
            mock.patch.object(
                base,
                "_candidate_gate_check_page",
                return_value=([check(501, 101)], False),
            ),
            mock.patch.object(subject.core, "request_data", return_value=[]),
        ):
            with self.assertRaisesRegex(RuntimeError, "malformed canonical"):
                subject._direct_target_for_pr("o/r", "t", current)

        good_run = gate_run(101, 1)
        with (
            mock.patch.object(
                base,
                "_candidate_gate_check_page",
                return_value=([check(501, 101)], False),
            ),
            mock.patch.object(
                subject.core, "request_data", side_effect=[good_run, []]
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "malformed protected"):
                subject._direct_target_for_pr("o/r", "t", current)

    def test_waiter_fail_closed_paths(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        with mock.patch.object(subject.core, "request_data", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "malformed rerun"):
                subject._wait_for_terminal_invalidation(
                    "o/r", "shared-head", "t", 101, 1, 10, current, True
                )

        pending = gate_run(101, 1)
        pending.update({"run_attempt": 1, "status": "completed", "conclusion": "success"})
        with (
            mock.patch.object(subject.core, "request_data", return_value=pending),
            mock.patch.object(subject.time, "sleep") as sleeper,
        ):
            with self.assertRaises(base.DeferredObservation):
                subject._wait_for_terminal_invalidation(
                    "o/r", "shared-head", "t", 101, 1, 10, current, True
                )
        self.assertEqual(sleeper.call_count, base.MAX_POSTCONDITION_POLLS - 1)

        terminal = gate_run(101, 1)
        terminal.update({"run_attempt": 2, "status": "completed", "conclusion": "failure"})
        failed = check(11, 101, conclusion="failure")
        with (
            mock.patch.object(subject.core, "request_data", return_value=terminal),
            mock.patch.object(
                subject.core, "required_merge_gate_conclusion", return_value="failure"
            ),
            mock.patch.object(subject.core, "latest_required_check", return_value=failed),
        ):
            self.assertTrue(
                subject._wait_for_terminal_invalidation(
                    "o/r", "shared-head", "t", 101, 1, 10, None, False
                )
            )

        with (
            mock.patch.object(
                subject.core, "request_data", side_effect=[terminal, []]
            ),
            mock.patch.object(
                subject.core, "required_merge_gate_conclusion", return_value="failure"
            ),
            mock.patch.object(subject.core, "latest_required_check", return_value=failed),
        ):
            with self.assertRaisesRegex(RuntimeError, "malformed rerun protected-job"):
                subject._wait_for_terminal_invalidation(
                    "o/r", "shared-head", "t", 101, 1, 10, current, True
                )

        success_job = job(11, 101, attempt=2, conclusion="success")
        with (
            mock.patch.object(
                subject.core, "request_data", side_effect=[terminal, success_job]
            ),
            mock.patch.object(
                subject.core, "required_merge_gate_conclusion", return_value="failure"
            ),
            mock.patch.object(subject.core, "latest_required_check", return_value=failed),
        ):
            with self.assertRaisesRegex(RuntimeError, "disagree"):
                subject._wait_for_terminal_invalidation(
                    "o/r", "shared-head", "t", 101, 1, 10, current, True
                )

        failed_job = job(11, 101, attempt=2, conclusion="failure")
        with (
            mock.patch.object(
                subject.core, "request_data", side_effect=[terminal, failed_job]
            ),
            mock.patch.object(
                subject.core, "required_merge_gate_conclusion", return_value="failure"
            ),
            mock.patch.object(subject.core, "latest_required_check", return_value=failed),
            mock.patch.object(base, "_current_pr", return_value=None),
        ):
            with self.assertRaises(base.DeferredObservation):
                subject._wait_for_terminal_invalidation(
                    "o/r", "shared-head", "t", 101, 1, 10, current, True
                )

    def test_mutation_baseline_fail_closed_paths(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        with mock.patch.object(subject.core, "request_data", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "malformed mutation-bound"):
                subject._mutation_baseline("o/r", "t", current, 101)

        no_merge = pr(1, branch="shared", head="shared-head", merge_sha=None)
        completed = gate_run(101, 1)
        completed.update({"run_attempt": 2, "status": "completed", "conclusion": "success"})
        with mock.patch.object(subject.core, "request_data", return_value=completed):
            with self.assertRaisesRegex(RuntimeError, "current PR authority"):
                subject._mutation_baseline("o/r", "t", no_merge, 101)

    def test_process_head_group_early_and_failure_paths(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        success = check(601, 201)
        in_progress = check(601, 201, status="in_progress", conclusion=None)
        failure = check(601, 201, conclusion="failure")

        with mock.patch.object(subject.core, "latest_required_check", return_value=None):
            self.assertEqual(
                subject._process_head_group("o/r", "t", [current], 3),
                ([], [], None),
            )

        with (
            mock.patch.object(subject.core, "latest_required_check", return_value=in_progress),
            mock.patch.object(subject.core, "unresolved_review_threads", return_value=True),
        ):
            self.assertEqual(
                subject._process_head_group("o/r", "t", [current], 3),
                ([], [], (1, 1)),
            )
        with (
            mock.patch.object(subject.core, "latest_required_check", return_value=in_progress),
            mock.patch.object(subject.core, "unresolved_review_threads", return_value=False),
        ):
            self.assertEqual(
                subject._process_head_group("o/r", "t", [current], 3),
                ([], [], None),
            )
        with mock.patch.object(subject.core, "latest_required_check", return_value=failure):
            self.assertEqual(
                subject._process_head_group("o/r", "t", [current], 3),
                ([], [], None),
            )
        with mock.patch.object(subject.core, "latest_required_check", return_value=success):
            self.assertEqual(
                subject._process_head_group("o/r", "t", [current], 0),
                ([], [], None),
            )

        with (
            mock.patch.object(subject.core, "latest_required_check", return_value=success),
            mock.patch.object(
                base,
                "_remaining_request_budget",
                return_value=base.MIN_TARGET_REQUEST_HEADROOM,
            ),
        ):
            with self.assertRaises(base.DeferredForBudget):
                subject._process_head_group("o/r", "t", [current], 3)

        with (
            mock.patch.object(subject.core, "latest_required_check", return_value=success),
            mock.patch.object(subject.core, "unresolved_review_threads", return_value=False),
        ):
            self.assertEqual(
                subject._process_head_group("o/r", "t", [current], 3),
                ([], [], None),
            )

    def test_process_target_authority_and_postcondition_edges(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        success = check(601, 201)
        target = (gate_run(101, 1), check(501, 101))

        with (
            mock.patch.object(subject.core, "latest_required_check", return_value=success),
            mock.patch.object(subject.core, "unresolved_review_threads", return_value=True),
            mock.patch.object(
                subject, "_direct_target_for_pr", return_value=(None, base.ScanPage(4, "a" * 64))
            ),
        ):
            self.assertEqual(
                subject._process_head_group("o/r", "t", [current], 3),
                ([], [], (1, 4)),
            )

        with (
            mock.patch.object(subject.core, "latest_required_check", return_value=success),
            mock.patch.object(subject.core, "unresolved_review_threads", return_value=True),
            mock.patch.object(subject, "_direct_target_for_pr", return_value=(None, None)),
        ):
            posted, errors, continuation = subject._process_head_group(
                "o/r", "t", [current], 3
            )
        self.assertEqual(posted, [])
        self.assertEqual(len(errors), 1)
        self.assertIsNone(continuation)

        with (
            mock.patch.object(subject.core, "latest_required_check", return_value=success),
            mock.patch.object(subject.core, "unresolved_review_threads", return_value=True),
            mock.patch.object(subject, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(base, "_current_pr", return_value=None),
        ):
            self.assertEqual(
                subject._process_head_group("o/r", "t", [current], 3),
                ([], [], None),
            )

        with (
            mock.patch.object(subject.core, "latest_required_check", return_value=success),
            mock.patch.object(
                subject.core, "unresolved_review_threads", side_effect=[True, False]
            ),
            mock.patch.object(subject, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(base, "_current_pr", return_value=current),
        ):
            self.assertEqual(
                subject._process_head_group("o/r", "t", [current], 3),
                ([], [], None),
            )

        with (
            mock.patch.object(
                subject.core, "latest_required_check", side_effect=[success, failure := check(602, 202, conclusion="failure")]
            ),
            mock.patch.object(subject.core, "unresolved_review_threads", return_value=True),
            mock.patch.object(subject, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(base, "_current_pr", return_value=current),
        ):
            self.assertEqual(
                subject._process_head_group("o/r", "t", [current], 3),
                ([], [], None),
            )

        with (
            mock.patch.object(subject.core, "latest_required_check", return_value=success),
            mock.patch.object(subject.core, "unresolved_review_threads", return_value=True),
            mock.patch.object(subject, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(base, "_current_pr", side_effect=[current, None]),
        ):
            self.assertEqual(
                subject._process_head_group("o/r", "t", [current], 3),
                ([], [], (1, 1)),
            )

        with (
            mock.patch.object(subject.core, "latest_required_check", return_value=success),
            mock.patch.object(subject.core, "unresolved_review_threads", return_value=True),
            mock.patch.object(subject, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(base, "_current_pr", return_value=current),
            mock.patch.object(
                base,
                "_remaining_request_budget",
                return_value=base.POSTCONDITION_REQUEST_RESERVE,
            ),
        ):
            with self.assertRaises(base.DeferredForBudget):
                subject._process_head_group("o/r", "t", [current], 3)

        with (
            mock.patch.object(subject.core, "latest_required_check", return_value=success),
            mock.patch.object(subject.core, "unresolved_review_threads", return_value=True),
            mock.patch.object(subject, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(base, "_current_pr", return_value=current),
            mock.patch.object(subject, "_mutation_baseline", return_value=None),
        ):
            self.assertEqual(
                subject._process_head_group("o/r", "t", [current], 3),
                ([], [], (1, 1)),
            )

        with (
            mock.patch.object(subject.core, "latest_required_check", return_value=success),
            mock.patch.object(
                subject.core,
                "unresolved_review_threads",
                side_effect=[True, True, False],
            ),
            mock.patch.object(subject, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(base, "_current_pr", return_value=current),
            mock.patch.object(subject, "_mutation_baseline", return_value=1),
            mock.patch.object(subject.core, "rerun_workflow") as rerun,
        ):
            self.assertEqual(
                subject._process_head_group("o/r", "t", [current], 3),
                ([], [], None),
            )
        rerun.assert_not_called()

    def test_process_after_green_rerun_continues_or_finishes_safely(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        success = check(601, 201)
        failure = check(602, 202, conclusion="failure")
        target = (gate_run(101, 1), check(501, 101))

        common = [
            mock.patch.object(subject, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(base, "_current_pr", return_value=current),
            mock.patch.object(subject, "_mutation_baseline", return_value=1),
            mock.patch.object(subject.core, "rerun_workflow"),
            mock.patch.object(subject, "_wait_for_terminal_invalidation", return_value=False),
        ]
        with (
            *common,
            mock.patch.object(
                subject.core,
                "unresolved_review_threads",
                side_effect=[True, True, True, False],
            ),
            mock.patch.object(
                subject.core,
                "latest_required_check",
                side_effect=[success, success, failure],
            ),
        ):
            self.assertEqual(
                subject._process_head_group("o/r", "t", [current], 3),
                ([101], [], None),
            )

        common = [
            mock.patch.object(subject, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(base, "_current_pr", return_value=current),
            mock.patch.object(subject, "_mutation_baseline", return_value=1),
            mock.patch.object(subject.core, "rerun_workflow"),
            mock.patch.object(subject, "_wait_for_terminal_invalidation", return_value=False),
        ]
        with (
            *common,
            mock.patch.object(
                subject.core,
                "unresolved_review_threads",
                side_effect=[True, True, True, False],
            ),
            mock.patch.object(
                subject.core,
                "latest_required_check",
                side_effect=[success, success, success],
            ),
        ):
            self.assertEqual(
                subject._process_head_group("o/r", "t", [current], 3),
                ([101], [], None),
            )

    def test_module_main_guard(self) -> None:
        originals = (
            base._direct_target_for_pr,
            base._wait_for_terminal_invalidation,
            base._process_head_group,
        )
        try:
            with mock.patch.dict(os.environ, {}, clear=True):
                with self.assertRaises(SystemExit):
                    runpy.run_path(subject.__file__, run_name="__main__")
        finally:
            (
                base._direct_target_for_pr,
                base._wait_for_terminal_invalidation,
                base._process_head_group,
            ) = originals


if __name__ == "__main__":
    unittest.main()
