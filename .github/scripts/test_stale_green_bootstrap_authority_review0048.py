from __future__ import annotations

import unittest
from unittest import mock

from test_stale_green_bootstrap_authority import check, gate_run, job, pr
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0048 as subject


class Review0048RegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        base._reset_request_budget()
        self.addCleanup(base._reset_request_budget)

    def test_target_scan_restarts_when_pages_drift_inside_one_invocation(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        first = [check(701, 301)]
        changed = [check(702, 302)]
        with mock.patch.object(
            base,
            "_candidate_gate_check_page",
            side_effect=[(first, True), ([], False), (changed, True)],
        ) as pages:
            target, continuation = subject._direct_target_for_pr(
                "o/r", "t", current
            )
        self.assertIsNone(target)
        self.assertEqual(continuation, 1)
        self.assertEqual([call.args[3] for call in pages.call_args_list], [1, 2, 1])

    def test_target_scan_accepts_stable_second_page_and_validates_target(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        first = [check(701, 301)]
        target_check = check(501, 101)
        target_run = gate_run(101, 1)
        target_job = job(501, 101)
        with (
            mock.patch.object(
                base,
                "_candidate_gate_check_page",
                side_effect=[(first, True), ([target_check], False), (first, True)],
            ) as pages,
            mock.patch.object(
                subject.core,
                "request_data",
                side_effect=[target_run, target_job],
            ),
        ):
            target, continuation = subject._direct_target_for_pr(
                "o/r", "t", current
            )
        self.assertEqual(target, (target_run, target_check))
        self.assertIsNone(continuation)
        self.assertEqual([call.args[3] for call in pages.call_args_list], [1, 2, 1])

    def test_target_scan_resume_anchor_and_bounded_continuation(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        prior = [check(701, 301)]
        anchor = base._check_page_anchor(prior, True)
        with mock.patch.object(
            base,
            "_candidate_gate_check_page",
            side_effect=[(prior, True), ([], True), (prior, True), ([], True), ([], True)],
        ):
            target, continuation = subject._direct_target_for_pr(
                "o/r", "t", current, 2, anchor
            )
        self.assertIsNone(target)
        self.assertEqual(continuation, 4)
        assert continuation is not None
        self.assertNotEqual(continuation.anchor, "-")

        with mock.patch.object(
            base, "_candidate_gate_check_page", return_value=(prior, False)
        ):
            self.assertEqual(
                subject._direct_target_for_pr("o/r", "t", current, 2, anchor),
                (None, None),
            )

    def test_waiter_requires_exact_single_next_attempt(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        jumped = gate_run(101, 1)
        jumped.update({"run_attempt": 3, "status": "completed", "conclusion": "failure"})
        with mock.patch.object(subject.core, "request_data", return_value=jumped):
            with self.assertRaises(base.DeferredObservation):
                subject._wait_for_terminal_invalidation(
                    "o/r", "shared-head", "t", 101, 1, 10, current, True
                )

        pending = gate_run(101, 1)
        pending.update({"run_attempt": 1, "status": "completed", "conclusion": "success"})
        terminal = gate_run(101, 1)
        terminal.update({"run_attempt": 2, "status": "completed", "conclusion": "failure"})
        failed = check(11, 101, conclusion="failure")
        failed_job = job(11, 101, attempt=2, conclusion="failure")
        with (
            mock.patch.object(
                subject.core,
                "request_data",
                side_effect=[pending, terminal, failed_job],
            ),
            mock.patch.object(
                subject.core, "required_merge_gate_conclusion", return_value="failure"
            ),
            mock.patch.object(subject.core, "latest_required_check", return_value=failed),
            mock.patch.object(base, "_current_pr", return_value=current),
            mock.patch.object(subject.time, "sleep") as sleeper,
        ):
            self.assertTrue(
                subject._wait_for_terminal_invalidation(
                    "o/r", "shared-head", "t", 101, 1, 10, current, True
                )
            )
        self.assertEqual(sleeper.call_count, 1)

    def test_waiter_defers_unrelated_or_missing_terminal_postcondition(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        terminal = gate_run(101, 1)
        terminal.update({"run_attempt": 2, "status": "completed", "conclusion": "failure"})
        unrelated = check(12, 999, conclusion="failure")
        with (
            mock.patch.object(subject.core, "request_data", return_value=terminal),
            mock.patch.object(
                subject.core, "required_merge_gate_conclusion", return_value="failure"
            ),
            mock.patch.object(subject.core, "latest_required_check", return_value=unrelated),
            mock.patch.object(subject.time, "sleep"),
        ):
            with self.assertRaises(base.DeferredObservation):
                subject._wait_for_terminal_invalidation(
                    "o/r", "shared-head", "t", 101, 1, 10, current, True
                )

    def test_mutation_baseline_defers_pending_and_binds_pr(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        pending = gate_run(101, 1)
        pending.update({"run_attempt": 2, "status": "in_progress", "conclusion": None})
        with mock.patch.object(subject.core, "request_data", return_value=pending):
            self.assertIsNone(subject._mutation_baseline("o/r", "t", current, 101))

        completed = gate_run(101, 1)
        completed.update({"run_attempt": 2, "status": "completed", "conclusion": "success"})
        with mock.patch.object(subject.core, "request_data", return_value=completed):
            self.assertEqual(subject._mutation_baseline("o/r", "t", current, 101), 2)

        wrong = gate_run(101, 2)
        wrong.update({"run_attempt": 2, "status": "completed", "conclusion": "success"})
        with mock.patch.object(subject.core, "request_data", return_value=wrong):
            with self.assertRaisesRegex(RuntimeError, "current PR authority"):
                subject._mutation_baseline("o/r", "t", current, 101)

    def test_process_preserves_continuation_for_pending_and_re_stale_rerun(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        latest = check(601, 201)
        target_run = gate_run(101, 1)
        target = (target_run, check(501, 101))

        with (
            mock.patch.object(subject.core, "latest_required_check", side_effect=[latest, latest]),
            mock.patch.object(subject.core, "unresolved_review_threads", side_effect=[True, True]),
            mock.patch.object(subject, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(base, "_current_pr", return_value=current),
            mock.patch.object(subject, "_mutation_baseline", return_value=None),
            mock.patch.object(subject.core, "rerun_workflow") as rerun,
        ):
            self.assertEqual(
                subject._process_head_group("o/r", "t", [current], 3),
                ([], [], (1, 1)),
            )
        rerun.assert_not_called()

        with (
            mock.patch.object(subject.core, "latest_required_check", side_effect=[latest, latest]),
            mock.patch.object(
                subject.core,
                "unresolved_review_threads",
                side_effect=[True, True, True, True],
            ),
            mock.patch.object(subject, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(base, "_current_pr", return_value=current),
            mock.patch.object(subject, "_mutation_baseline", return_value=1),
            mock.patch.object(subject.core, "rerun_workflow") as rerun,
            mock.patch.object(subject, "_wait_for_terminal_invalidation", return_value=False),
        ):
            posted, errors, continuation = subject._process_head_group(
                "o/r", "t", [current], 3
            )
        self.assertEqual(posted, [101])
        self.assertEqual(errors, [])
        self.assertEqual(continuation, (1, 1))
        rerun.assert_called_once()

    def test_process_uses_exact_refreshed_baseline_before_post(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        latest = check(601, 201)
        target = (gate_run(101, 1), check(501, 101))
        with (
            mock.patch.object(subject.core, "latest_required_check", side_effect=[latest, latest]),
            mock.patch.object(
                subject.core,
                "unresolved_review_threads",
                side_effect=[True, True, True],
            ),
            mock.patch.object(subject, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(base, "_current_pr", return_value=current),
            mock.patch.object(subject, "_mutation_baseline", return_value=4),
            mock.patch.object(subject.core, "rerun_workflow") as rerun,
            mock.patch.object(subject, "_wait_for_terminal_invalidation", return_value=True) as waiter,
        ):
            self.assertEqual(
                subject._process_head_group("o/r", "t", [current], 3),
                ([101], [], None),
            )
        rerun.assert_called_once_with("o/r", 101, "t")
        self.assertEqual(waiter.call_args.args[4], 4)

    def test_install_and_main_delegate_to_proven_base_runtime(self) -> None:
        original_target = base._direct_target_for_pr
        original_waiter = base._wait_for_terminal_invalidation
        original_processor = base._process_head_group
        try:
            with mock.patch.object(base, "install") as base_install:
                subject.install()
            base_install.assert_called_once()
            self.assertIs(base._direct_target_for_pr, subject._direct_target_for_pr)
            self.assertIs(base._wait_for_terminal_invalidation, subject._wait_for_terminal_invalidation)
            self.assertIs(base._process_head_group, subject._process_head_group)
        finally:
            base._direct_target_for_pr = original_target
            base._wait_for_terminal_invalidation = original_waiter
            base._process_head_group = original_processor

        with (
            mock.patch.object(subject, "install") as installer,
            mock.patch.object(base, "main", return_value=0) as base_main,
        ):
            self.assertEqual(subject.main(), 0)
        installer.assert_called_once()
        base_main.assert_called_once()


if __name__ == "__main__":
    unittest.main()
