from __future__ import annotations

import unittest
from unittest import mock

from test_stale_green_bootstrap_authority import check, gate_run, pr
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0048 as subject


class Review0048FinalCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        base._reset_request_budget()
        self.addCleanup(base._reset_request_budget)

    def test_target_scan_defensively_skips_head_mismatch_after_validator(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        candidate = check(501, 101)
        wrong_head = gate_run(101, 1, head="other-head")
        with (
            mock.patch.object(
                base,
                "_candidate_gate_check_page",
                return_value=([candidate], False),
            ),
            mock.patch.object(subject.core, "request_data", return_value=wrong_head),
            mock.patch.object(base, "_validate_canonical_run", return_value=1),
        ):
            self.assertEqual(
                subject._direct_target_for_pr("o/r", "t", current),
                (None, None),
            )

    def test_waiter_handles_unchanged_check_and_rejects_conclusion_mismatch(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        terminal = gate_run(101, 1)
        terminal.update(
            {"run_attempt": 2, "status": "completed", "conclusion": "failure"}
        )
        unchanged = check(10, 101, conclusion="failure")
        with (
            mock.patch.object(subject.core, "request_data", return_value=terminal),
            mock.patch.object(
                subject.core,
                "required_merge_gate_conclusion",
                return_value="failure",
            ),
            mock.patch.object(
                subject.core, "latest_required_check", return_value=unchanged
            ),
            mock.patch.object(subject.time, "sleep") as sleeper,
        ):
            with self.assertRaises(base.DeferredObservation):
                subject._wait_for_terminal_invalidation(
                    "o/r", "shared-head", "t", 101, 1, 10, current, False
                )
        self.assertEqual(sleeper.call_count, base.MAX_POSTCONDITION_POLLS - 1)

        mismatched = check(11, 101, conclusion="success")
        with (
            mock.patch.object(subject.core, "request_data", return_value=terminal),
            mock.patch.object(
                subject.core,
                "required_merge_gate_conclusion",
                return_value="failure",
            ),
            mock.patch.object(
                subject.core, "latest_required_check", return_value=mismatched
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "disagree"):
                subject._wait_for_terminal_invalidation(
                    "o/r", "shared-head", "t", 101, 1, 10, current, False
                )

    def test_process_uses_persisted_scan_anchor(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        success = check(601, 201)
        anchor = "a" * 64
        with (
            mock.patch.object(
                subject.core, "latest_required_check", return_value=success
            ),
            mock.patch.object(
                subject.core, "unresolved_review_threads", return_value=True
            ),
            mock.patch.object(
                subject, "_direct_target_for_pr", return_value=(None, None)
            ) as target_reader,
        ):
            posted, errors, continuation = subject._process_head_group(
                "o/r", "t", [current], 3, 1, 2, anchor
            )
        self.assertEqual(posted, [])
        self.assertEqual(len(errors), 1)
        self.assertIsNone(continuation)
        target_reader.assert_called_once_with("o/r", "t", current, 2, anchor)

    def test_process_reserves_postcondition_budget_and_retains_disappearing_pr(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        success = check(601, 201)
        target = (gate_run(101, 1), check(501, 101))
        first_budget = (
            base.MIN_TARGET_REQUEST_HEADROOM + base.STATE_WRITE_REQUEST_RESERVE + 10
        )
        with (
            mock.patch.object(
                subject.core,
                "latest_required_check",
                side_effect=[success, success],
            ),
            mock.patch.object(
                subject.core, "unresolved_review_threads", return_value=True
            ),
            mock.patch.object(
                subject, "_direct_target_for_pr", return_value=(target, None)
            ),
            mock.patch.object(base, "_current_pr", return_value=current),
            mock.patch.object(
                base,
                "_remaining_request_budget",
                side_effect=[first_budget, base.POSTCONDITION_REQUEST_RESERVE],
            ),
        ):
            with self.assertRaises(base.DeferredForBudget):
                subject._process_head_group("o/r", "t", [current], 3)

        with (
            mock.patch.object(
                subject.core,
                "latest_required_check",
                side_effect=[success, success],
            ),
            mock.patch.object(
                subject.core,
                "unresolved_review_threads",
                side_effect=[True, True],
            ),
            mock.patch.object(
                subject, "_direct_target_for_pr", return_value=(target, None)
            ),
            mock.patch.object(
                base, "_current_pr", side_effect=[current, current, None]
            ),
            mock.patch.object(subject, "_mutation_baseline", return_value=1),
        ):
            self.assertEqual(
                subject._process_head_group("o/r", "t", [current], 3),
                ([], [], (1, 1)),
            )

    def test_process_persists_continuation_when_waiter_defers(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        success = check(601, 201)
        target = (gate_run(101, 1), check(501, 101))
        with (
            mock.patch.object(
                subject.core,
                "latest_required_check",
                side_effect=[success, success],
            ),
            mock.patch.object(
                subject.core,
                "unresolved_review_threads",
                side_effect=[True, True, True],
            ),
            mock.patch.object(
                subject, "_direct_target_for_pr", return_value=(target, None)
            ),
            mock.patch.object(base, "_current_pr", return_value=current),
            mock.patch.object(subject, "_mutation_baseline", return_value=1),
            mock.patch.object(subject.core, "rerun_workflow") as rerun,
            mock.patch.object(
                subject,
                "_wait_for_terminal_invalidation",
                side_effect=base.DeferredObservation("still pending"),
            ),
        ):
            self.assertEqual(
                subject._process_head_group("o/r", "t", [current], 3),
                ([101], [], (1, 1)),
            )
        rerun.assert_called_once_with("o/r", 101, "t")


if __name__ == "__main__":
    unittest.main()
