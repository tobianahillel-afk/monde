from __future__ import annotations

import unittest
from unittest import mock

from test_stale_green_bootstrap_authority import check, gate_run, pr
import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0048 as previous
import stale_green_bootstrap_authority_review0049 as subject


class Review0049FinalEdgeCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        base._reset_request_budget()
        self.addCleanup(base._reset_request_budget)

    @staticmethod
    def _issue(state: subject.SchedulerStateV4) -> dict:
        return {
            "number": 7,
            "title": base.SCHEDULER_STATE_TITLE,
            "state": "open",
            "body": subject._scheduler_body(state),
        }

    @staticmethod
    def _current(number: int = 1) -> dict:
        return pr(number, branch="shared", head="shared-head")

    def test_write_state_rejects_valid_but_different_ack(self) -> None:
        expected = subject.SchedulerStateV4(3)
        different = subject.SchedulerStateV4(4)
        with (
            mock.patch.object(base, "_scheduler_issue_number", return_value=7),
            mock.patch.object(core, "request_data", return_value=self._issue(different)),
        ):
            with self.assertRaisesRegex(RuntimeError, "not durably acknowledged"):
                subject._write_state("o/r", "t", expected)

    def test_current_pending_pr_rejects_malformed_state_and_returns_valid_open(self) -> None:
        current = self._current()
        state = subject._pending_state(subject.SchedulerStateV4(0), current, 101, 1, 601)

        malformed = dict(current)
        malformed["state"] = "mystery"
        with mock.patch.object(core, "request_data", return_value=malformed):
            with self.assertRaisesRegex(RuntimeError, "malformed pending pull-request state"):
                subject._current_pending_pr("o/r", "t", state)

        with mock.patch.object(core, "request_data", return_value=current):
            self.assertEqual(subject._current_pending_pr("o/r", "t", state), current)

    def test_resume_pending_terminal_still_unresolved_clears_pending(self) -> None:
        current = self._current()
        state = subject._pending_state(subject.SchedulerStateV4(0), current, 101, 1, 601)
        run = gate_run(101, 1)
        run.update({"run_attempt": 2, "status": "completed", "conclusion": "success"})
        with (
            mock.patch.object(subject, "_current_pending_pr", return_value=current),
            mock.patch.object(core, "request_data", return_value=run),
            mock.patch.object(previous, "_wait_for_terminal_invalidation", return_value=False),
            mock.patch.object(core, "unresolved_review_threads", return_value=True),
            mock.patch.object(subject, "_write_state") as writer,
        ):
            self.assertEqual(subject._resume_pending("o/r", "t", state), [])
        self.assertEqual(writer.call_args.args[2].pending_pr, 0)
        self.assertEqual(writer.call_args.args[2].scan_pr, 1)

    def test_process_stops_when_thread_resolves_after_first_pr_refresh(self) -> None:
        current = self._current()
        latest = check(601, 201)
        target = (gate_run(101, 1), check(501, 101))
        with (
            mock.patch.object(core, "latest_required_check", return_value=latest),
            mock.patch.object(core, "unresolved_review_threads", side_effect=[True, False]),
            mock.patch.object(previous, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(base, "_current_pr", return_value=current),
            mock.patch.object(core, "rerun_workflow") as rerun,
        ):
            self.assertEqual(
                subject._process_head_group(
                    "o/r", "t", [current], 3, subject.SchedulerStateV4(0)
                ),
                ([], [], None),
            )
        rerun.assert_not_called()

    def test_process_continues_to_second_shared_head_sibling(self) -> None:
        first = self._current(1)
        second = self._current(2)
        latest = check(601, 201)
        first_target = (gate_run(101, 1), check(501, 101))

        def target_for_pr(repo, token, original, *args):
            if original["number"] == 1:
                return first_target, None
            return None, None

        # First sibling is stale, reruns, becomes clean while the effective gate
        # remains merge-acceptable; the loop must then continue to sibling #2.
        # Sibling #2 has no unresolved thread, so processing ends normally.
        with (
            mock.patch.object(core, "latest_required_check", return_value=latest),
            mock.patch.object(
                core,
                "unresolved_review_threads",
                side_effect=[True, True, True, False, False],
            ) as threads,
            mock.patch.object(previous, "_direct_target_for_pr", side_effect=target_for_pr),
            mock.patch.object(base, "_current_pr", return_value=first),
            mock.patch.object(previous, "_mutation_baseline", return_value=1),
            mock.patch.object(subject, "_write_state"),
            mock.patch.object(core, "rerun_workflow"),
            mock.patch.object(previous, "_wait_for_terminal_invalidation", return_value=False),
        ):
            result = subject._process_head_group(
                "o/r", "t", [first, second], 3, subject.SchedulerStateV4(0)
            )
        self.assertEqual(result, ([101], [], None))
        self.assertGreaterEqual(threads.call_count, 5)


if __name__ == "__main__":
    unittest.main()
