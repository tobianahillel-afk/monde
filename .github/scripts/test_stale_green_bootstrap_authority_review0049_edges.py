from __future__ import annotations

import os
import runpy
import unittest
from unittest import mock

from test_stale_green_bootstrap_authority import check, gate_run, pr
import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0048 as previous
import stale_green_bootstrap_authority_review0049 as subject


class Review0049EdgeCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        base._reset_request_budget()
        self.addCleanup(base._reset_request_budget)

    @staticmethod
    def _issue(body: str) -> dict:
        return {
            "number": 7,
            "title": base.SCHEDULER_STATE_TITLE,
            "state": "open",
            "body": body,
        }

    @staticmethod
    def _current() -> dict:
        return pr(1, branch="shared", head="shared-head")

    def test_state_validation_rejects_scalar_anchor_and_idle_continuation(self) -> None:
        for state in [
            subject.SchedulerStateV4(-1),
            subject.SchedulerStateV4(0, -1),
            subject.SchedulerStateV4(0, 0, 0),
            subject.SchedulerStateV4(True),
        ]:
            with self.assertRaisesRegex(RuntimeError, "outside"):
                subject._validate_state(state)
        for state in [
            subject.SchedulerStateV4(0, 1, 1, "bad"),
            subject.SchedulerStateV4(0, 1, 1, 3),
        ]:
            with self.assertRaisesRegex(RuntimeError, "scan anchor"):
                subject._validate_state(state)
        with self.assertRaisesRegex(RuntimeError, "idle scheduler"):
            subject._validate_state(subject.SchedulerStateV4(0, 0, 2))

    def test_parse_v4_closed_world_and_read_state_contract(self) -> None:
        state = subject.SchedulerStateV4(4, 2, 3, "a" * 64)
        issue = self._issue(subject._scheduler_body(state))
        self.assertEqual(subject._parse_state(issue, 7), state)
        malformed = {**issue, "body": issue["body"].replace("cursor_pr: 4", "cursor_pr: nope")}
        with self.assertRaisesRegex(RuntimeError, "closed-world"):
            subject._parse_state(malformed, 7)

        with (
            mock.patch.object(base, "_scheduler_issue_number", return_value=7),
            mock.patch.object(core, "request_data", return_value=issue),
        ):
            self.assertEqual(subject._read_state("o/r", "t"), state)
        with (
            mock.patch.object(base, "_scheduler_issue_number", return_value=7),
            mock.patch.object(core, "request_data", return_value=[]),
        ):
            with self.assertRaisesRegex(RuntimeError, "response is malformed"):
                subject._read_state("o/r", "t")

    def test_pending_state_rejects_malformed_mutation_identity(self) -> None:
        current = self._current()
        for run_id, attempt, check_id in [(0, 1, 1), (1, 0, 1), (1, 1, 0), (True, 1, 1)]:
            with self.assertRaisesRegex(RuntimeError, "malformed identity"):
                subject._pending_state(subject.SchedulerStateV4(0), current, run_id, attempt, check_id)
        bad_pr = dict(current)
        bad_pr["number"] = 0
        with self.assertRaisesRegex(RuntimeError, "malformed identity"):
            subject._pending_state(subject.SchedulerStateV4(0), bad_pr, 1, 1, 1)

    def test_current_pending_pr_malformed_and_closed(self) -> None:
        current = self._current()
        state = subject._pending_state(subject.SchedulerStateV4(0), current, 101, 1, 601)
        for payload in [[], {"number": 2}, {"number": True}]:
            with mock.patch.object(core, "request_data", return_value=payload):
                with self.assertRaisesRegex(RuntimeError, "malformed pending"):
                    subject._current_pending_pr("o/r", "t", state)
        closed = dict(current)
        closed["state"] = "closed"
        with mock.patch.object(core, "request_data", return_value=closed):
            self.assertIsNone(subject._current_pending_pr("o/r", "t", state))

    def test_resume_pending_rejects_idle_malformed_and_regressed_run(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "idle scheduler"):
            subject._resume_pending("o/r", "t", subject.SchedulerStateV4(0))

        current = self._current()
        state = subject._pending_state(subject.SchedulerStateV4(0), current, 101, 2, 601)
        with (
            mock.patch.object(subject, "_current_pending_pr", return_value=current),
            mock.patch.object(core, "request_data", return_value=[]),
        ):
            with self.assertRaisesRegex(RuntimeError, "malformed pending workflow"):
                subject._resume_pending("o/r", "t", state)

        regressed = gate_run(101, 1)
        regressed.update({"run_attempt": 1, "status": "completed", "conclusion": "success"})
        with (
            mock.patch.object(subject, "_current_pending_pr", return_value=current),
            mock.patch.object(core, "request_data", return_value=regressed),
        ):
            with self.assertRaisesRegex(RuntimeError, "regressed"):
                subject._resume_pending("o/r", "t", state)

    def test_resume_pending_closed_pr_clears_and_terminal_clean_clears(self) -> None:
        current = self._current()
        state = subject._pending_state(subject.SchedulerStateV4(7), current, 101, 1, 601)
        with (
            mock.patch.object(subject, "_current_pending_pr", return_value=None),
            mock.patch.object(subject, "_write_state") as writer,
        ):
            self.assertEqual(subject._resume_pending("o/r", "t", state), [])
        self.assertEqual(writer.call_args.args[2], subject.SchedulerStateV4(7))

        run = gate_run(101, 1)
        run.update({"run_attempt": 2, "status": "completed", "conclusion": "success"})
        with (
            mock.patch.object(subject, "_current_pending_pr", return_value=current),
            mock.patch.object(core, "request_data", return_value=run),
            mock.patch.object(previous, "_wait_for_terminal_invalidation", return_value=False),
            mock.patch.object(core, "unresolved_review_threads", return_value=False),
            mock.patch.object(subject, "_write_state") as writer,
        ):
            self.assertEqual(subject._resume_pending("o/r", "t", state), [])
        self.assertEqual(writer.call_args.args[2].pending_pr, 0)
        self.assertEqual(writer.call_args.args[2].scan_pr, 1)

    def test_process_early_authority_outcomes(self) -> None:
        current = self._current()
        state = subject.SchedulerStateV4(0)
        with mock.patch.object(core, "latest_required_check", return_value=None):
            self.assertEqual(subject._process_head_group("o/r", "t", [current], 3, state), ([], [], None))

        queued = check(601, 201, status="in_progress", conclusion=None)
        with (
            mock.patch.object(core, "latest_required_check", return_value=queued),
            mock.patch.object(core, "unresolved_review_threads", return_value=True),
        ):
            result = subject._process_head_group("o/r", "t", [current], 3, state)
        self.assertEqual(result[2][0], 1)

        with (
            mock.patch.object(core, "latest_required_check", return_value=queued),
            mock.patch.object(core, "unresolved_review_threads", return_value=False),
        ):
            self.assertEqual(subject._process_head_group("o/r", "t", [current], 3, state), ([], [], None))

        failed = check(601, 201, conclusion="failure")
        with mock.patch.object(core, "latest_required_check", return_value=failed):
            self.assertEqual(subject._process_head_group("o/r", "t", [current], 3, state), ([], [], None))

    def test_process_slot_budget_clean_thread_and_target_outcomes(self) -> None:
        current = self._current()
        latest = check(601, 201)
        state = subject.SchedulerStateV4(0)
        with mock.patch.object(core, "latest_required_check", return_value=latest):
            self.assertEqual(subject._process_head_group("o/r", "t", [current], 0, state), ([], [], None))

        with (
            mock.patch.object(core, "latest_required_check", return_value=latest),
            mock.patch.object(base, "_remaining_request_budget", return_value=0),
        ):
            with self.assertRaises(base.DeferredForBudget):
                subject._process_head_group("o/r", "t", [current], 3, state)

        with (
            mock.patch.object(core, "latest_required_check", return_value=latest),
            mock.patch.object(core, "unresolved_review_threads", return_value=False),
        ):
            self.assertEqual(subject._process_head_group("o/r", "t", [current], 3, state), ([], [], None))

        next_page = base.ScanPage(2, "a" * 64)
        with (
            mock.patch.object(core, "latest_required_check", return_value=latest),
            mock.patch.object(core, "unresolved_review_threads", return_value=True),
            mock.patch.object(previous, "_direct_target_for_pr", return_value=(None, next_page)),
        ):
            result = subject._process_head_group("o/r", "t", [current], 3, state, 1, 2, "b" * 64)
        self.assertEqual(result[2], (1, next_page))

        with (
            mock.patch.object(core, "latest_required_check", return_value=latest),
            mock.patch.object(core, "unresolved_review_threads", return_value=True),
            mock.patch.object(previous, "_direct_target_for_pr", return_value=(None, None)),
        ):
            result = subject._process_head_group("o/r", "t", [current], 3, state)
        self.assertEqual(result[0], [])
        self.assertEqual(len(result[1]), 1)

    def test_process_revalidation_baseline_and_mutation_budget_outcomes(self) -> None:
        current = self._current()
        latest = check(601, 201)
        target = (gate_run(101, 1), check(501, 101))
        state = subject.SchedulerStateV4(0)

        common = [
            mock.patch.object(core, "latest_required_check", return_value=latest),
            mock.patch.object(core, "unresolved_review_threads", return_value=True),
            mock.patch.object(previous, "_direct_target_for_pr", return_value=(target, None)),
        ]
        with common[0], common[1], common[2], mock.patch.object(base, "_current_pr", return_value=None):
            self.assertEqual(subject._process_head_group("o/r", "t", [current], 3, state), ([], [], None))

        with (
            mock.patch.object(core, "latest_required_check", side_effect=[latest, check(602, 202, conclusion="failure")]),
            mock.patch.object(core, "unresolved_review_threads", return_value=True),
            mock.patch.object(previous, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(base, "_current_pr", return_value=current),
        ):
            self.assertEqual(subject._process_head_group("o/r", "t", [current], 3, state), ([], [], None))

        with (
            mock.patch.object(core, "latest_required_check", return_value=latest),
            mock.patch.object(core, "unresolved_review_threads", return_value=True),
            mock.patch.object(previous, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(base, "_current_pr", side_effect=[current, None]),
        ):
            result = subject._process_head_group("o/r", "t", [current], 3, state)
        self.assertEqual(result[2][0], 1)

        with (
            mock.patch.object(core, "latest_required_check", return_value=latest),
            mock.patch.object(core, "unresolved_review_threads", return_value=True),
            mock.patch.object(previous, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(base, "_current_pr", return_value=current),
            mock.patch.object(base, "_remaining_request_budget", side_effect=[100, 0]),
        ):
            with self.assertRaises(base.DeferredForBudget):
                subject._process_head_group("o/r", "t", [current], 3, state)

        with (
            mock.patch.object(core, "latest_required_check", return_value=latest),
            mock.patch.object(core, "unresolved_review_threads", return_value=True),
            mock.patch.object(previous, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(base, "_current_pr", return_value=current),
            mock.patch.object(previous, "_mutation_baseline", return_value=None),
        ):
            result = subject._process_head_group("o/r", "t", [current], 3, state)
        self.assertEqual(result[2][0], 1)

        with (
            mock.patch.object(core, "latest_required_check", return_value=latest),
            mock.patch.object(core, "unresolved_review_threads", return_value=True),
            mock.patch.object(previous, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(base, "_current_pr", side_effect=[current, current, None]),
            mock.patch.object(previous, "_mutation_baseline", return_value=1),
        ):
            result = subject._process_head_group("o/r", "t", [current], 3, state)
        self.assertEqual(result[2][0], 1)

    def test_process_resolved_before_post_and_post_terminal_followups(self) -> None:
        current = self._current()
        latest = check(601, 201)
        target = (gate_run(101, 1), check(501, 101))
        state = subject.SchedulerStateV4(0)

        with (
            mock.patch.object(core, "latest_required_check", return_value=latest),
            mock.patch.object(core, "unresolved_review_threads", side_effect=[True, True, False]),
            mock.patch.object(previous, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(base, "_current_pr", return_value=current),
            mock.patch.object(previous, "_mutation_baseline", return_value=1),
            mock.patch.object(core, "rerun_workflow") as rerun,
        ):
            self.assertEqual(subject._process_head_group("o/r", "t", [current], 3, state), ([], [], None))
        rerun.assert_not_called()

        with (
            mock.patch.object(core, "latest_required_check", return_value=latest),
            mock.patch.object(core, "unresolved_review_threads", side_effect=[True, True, True, True]),
            mock.patch.object(previous, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(base, "_current_pr", return_value=current),
            mock.patch.object(previous, "_mutation_baseline", return_value=1),
            mock.patch.object(subject, "_write_state"),
            mock.patch.object(core, "rerun_workflow"),
            mock.patch.object(previous, "_wait_for_terminal_invalidation", return_value=False),
        ):
            result = subject._process_head_group("o/r", "t", [current], 3, state)
        self.assertEqual(result[2][0], 1)

        final_failed = check(602, 202, conclusion="failure")
        with (
            mock.patch.object(core, "latest_required_check", side_effect=[latest, latest, final_failed]),
            mock.patch.object(core, "unresolved_review_threads", side_effect=[True, True, True, False]),
            mock.patch.object(previous, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(base, "_current_pr", return_value=current),
            mock.patch.object(previous, "_mutation_baseline", return_value=1),
            mock.patch.object(subject, "_write_state"),
            mock.patch.object(core, "rerun_workflow"),
            mock.patch.object(previous, "_wait_for_terminal_invalidation", return_value=False),
        ):
            result = subject._process_head_group("o/r", "t", [current], 3, state)
        self.assertEqual(result, ([101], [], None))

    def test_poll_rotation_continuation_budget_and_errors(self) -> None:
        p1 = self._current()
        p2 = pr(2, branch="two", head="head-two")

        state = subject.SchedulerStateV4(0, 9, 1)
        with (
            mock.patch.object(subject, "_read_state", return_value=state),
            mock.patch.object(base.snapshot, "open_pull_requests", return_value=[p1]),
            mock.patch.object(base, "_group_for_scan", return_value=None),
            mock.patch.object(subject, "_process_head_group", return_value=([], [], None)),
            mock.patch.object(subject, "_write_state") as writer,
        ):
            self.assertEqual(subject.poll("o/r", "t"), [])
        writer.assert_called()

        state = subject.SchedulerStateV4(0, 1, 1)
        with (
            mock.patch.object(subject, "_read_state", return_value=state),
            mock.patch.object(base.snapshot, "open_pull_requests", return_value=[p1, p2]),
            mock.patch.object(base, "_group_for_scan", return_value=[p1]),
            mock.patch.object(subject, "_process_head_group", return_value=([], [], None)),
            mock.patch.object(subject, "_write_state"),
        ):
            self.assertEqual(subject.poll("o/r", "t"), [])

        with (
            mock.patch.object(subject, "_read_state", return_value=subject.SchedulerStateV4(0)),
            mock.patch.object(base.snapshot, "open_pull_requests", return_value=[p1]),
            mock.patch.object(base, "MAX_HEADS_PER_INVOCATION", 0),
            mock.patch.object(subject, "_write_state") as writer,
        ):
            self.assertEqual(subject.poll("o/r", "t"), [])
        writer.assert_called_once()

        with (
            mock.patch.object(subject, "_read_state", return_value=subject.SchedulerStateV4(0)),
            mock.patch.object(base.snapshot, "open_pull_requests", return_value=[p1]),
            mock.patch.object(base, "_remaining_request_budget", return_value=0),
            mock.patch.object(subject, "_write_state"),
        ):
            self.assertEqual(subject.poll("o/r", "t"), [])

        continuation = (1, base.ScanPage(2, "a" * 64))
        with (
            mock.patch.object(subject, "_read_state", return_value=subject.SchedulerStateV4(0)),
            mock.patch.object(base.snapshot, "open_pull_requests", return_value=[p1]),
            mock.patch.object(subject, "_process_head_group", return_value=([], [], continuation)),
            mock.patch.object(subject, "_write_state") as writer,
        ):
            self.assertEqual(subject.poll("o/r", "t"), [])
        written = writer.call_args.args[2]
        self.assertEqual((written.scan_pr, written.scan_page, written.scan_anchor), (1, 2, "a" * 64))

        with (
            mock.patch.object(subject, "_read_state", return_value=subject.SchedulerStateV4(0)),
            mock.patch.object(base.snapshot, "open_pull_requests", return_value=[p1]),
            mock.patch.object(subject, "_process_head_group", return_value=([], ["bad"], continuation)),
            mock.patch.object(subject, "_write_state"),
        ):
            with self.assertRaisesRegex(RuntimeError, "bad"):
                subject.poll("o/r", "t")

    def test_poll_exception_paths_and_empty_reset(self) -> None:
        p1 = self._current()
        with (
            mock.patch.object(subject, "_read_state", return_value=subject.SchedulerStateV4(0)),
            mock.patch.object(base.snapshot, "open_pull_requests", return_value=[p1]),
            mock.patch.object(subject, "_process_head_group", side_effect=base.DeferredForBudget("later")),
            mock.patch.object(subject, "_write_state") as writer,
        ):
            self.assertEqual(subject.poll("o/r", "t"), [])
        writer.assert_called_once()

        with (
            mock.patch.object(subject, "_read_state", return_value=subject.SchedulerStateV4(0)),
            mock.patch.object(base.snapshot, "open_pull_requests", return_value=[p1]),
            mock.patch.object(subject, "_process_head_group", side_effect=RuntimeError("boom")),
            mock.patch.object(subject, "_write_state"),
        ):
            with self.assertRaisesRegex(RuntimeError, "boom"):
                subject.poll("o/r", "t")

        with (
            mock.patch.object(subject, "_read_state", return_value=subject.SchedulerStateV4(5)),
            mock.patch.object(base.snapshot, "open_pull_requests", return_value=[]),
            mock.patch.object(subject, "_write_state") as writer,
        ):
            self.assertEqual(subject.poll("o/r", "t"), [])
        writer.assert_called_once_with("o/r", "t", subject.SchedulerStateV4(0))

        with (
            mock.patch.object(subject, "_read_state", return_value=subject.SchedulerStateV4(0)),
            mock.patch.object(base.snapshot, "open_pull_requests", return_value=[]),
            mock.patch.object(subject, "_write_state") as writer,
        ):
            self.assertEqual(subject.poll("o/r", "t"), [])
        writer.assert_not_called()

        with (
            mock.patch.object(subject, "_read_state", return_value=subject.SchedulerStateV4(0)),
            mock.patch.object(base.snapshot, "open_pull_requests", return_value=[p1]),
            mock.patch.object(subject, "_process_head_group", side_effect=subject.PendingMutationUncertain("ambiguous")),
        ):
            with self.assertRaises(subject.PendingMutationUncertain):
                subject.poll("o/r", "t")

    def test_install_main_and_module_entrypoint(self) -> None:
        with (
            mock.patch.object(previous, "install") as previous_install,
            mock.patch.object(base, "main", return_value=17) as base_main,
        ):
            self.assertEqual(subject.main(), 17)
        previous_install.assert_called_once()
        base_main.assert_called_once()
        self.assertIs(base.poll, subject.poll)
        self.assertIs(core.poll, subject.poll)

        with (
            mock.patch.object(previous, "install"),
            mock.patch.object(base, "main", return_value=23),
        ):
            with self.assertRaises(SystemExit) as exited:
                runpy.run_path(subject.__file__, run_name="__main__")
        self.assertEqual(exited.exception.code, 23)


if __name__ == "__main__":
    unittest.main()
