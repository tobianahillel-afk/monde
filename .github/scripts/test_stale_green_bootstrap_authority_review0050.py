from __future__ import annotations

import runpy
import unittest
from unittest import mock

from test_stale_green_bootstrap_pr_snapshot import SHA
from test_stale_green_bootstrap_authority import gate_run, pr
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0048 as observation
import stale_green_bootstrap_authority_review0049 as previous
import stale_green_bootstrap_authority_review0050 as subject


OTHER_SHA = "c" * 40


class Review0050ClosedOriginPendingTests(unittest.TestCase):
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
    def _current(number: int = 1, *, state: str = "open", head: str = SHA) -> dict:
        return pr(number, state=state, branch="shared", head=head)

    def test_state_round_trip_and_idle_v4_migration(self) -> None:
        legacy = previous.SchedulerStateV4(4, 2, 3, "a" * 64)
        parsed_legacy = subject._parse_state(
            self._issue(previous._scheduler_body(legacy)), 7
        )
        self.assertEqual(
            parsed_legacy,
            subject.SchedulerStateV5(4, 2, 3, "a" * 64),
        )

        pending = subject._pending_state(
            subject.SchedulerStateV5(3), self._current(), 101, 2, 501
        )
        parsed = subject._parse_state(
            self._issue(subject._scheduler_body(pending)), 7
        )
        self.assertEqual(parsed, pending)
        self.assertEqual(parsed.pending_head, SHA)
        self.assertEqual(len(parsed.pending_authority), 64)

    def test_active_v4_pending_migration_fails_closed(self) -> None:
        old_pending = previous._pending_state(
            previous.SchedulerStateV4(0), self._current(), 101, 1, 601
        )
        with self.assertRaisesRegex(RuntimeError, "lacks reversible pending head"):
            subject._parse_state(
                self._issue(previous._scheduler_body(old_pending)), 7
            )

    def test_state_validation_and_coercion_fail_closed(self) -> None:
        invalid = [
            subject.SchedulerStateV5(True),
            subject.SchedulerStateV5(0, 0, 2, "-"),
            subject.SchedulerStateV5(0, 1, 1, "bad"),
            subject.SchedulerStateV5(0, pending_run_id=1),
            subject.SchedulerStateV5(
                0, 1, 1, "-", 1, "a" * 64, "bad", 101, 1, 501
            ),
        ]
        for state in invalid:
            with self.subTest(state=state):
                with self.assertRaises(RuntimeError):
                    subject._validate_state(state)

        with self.assertRaisesRegex(RuntimeError, "cannot be coerced"):
            subject._coerce_state(object())
        active_v4 = previous._pending_state(
            previous.SchedulerStateV4(0), self._current(), 101, 1, 601
        )
        with self.assertRaisesRegex(RuntimeError, "pre-V5 pending"):
            subject._coerce_state(active_v4)

        malformed = self._issue(subject._scheduler_body(subject.SchedulerStateV5(0)))
        malformed["body"] = malformed["body"].replace("pending_head: -", "pending_head: xyz")
        with self.assertRaisesRegex(RuntimeError, "closed-world"):
            subject._parse_state(malformed, 7)

    def test_read_write_state_and_ack_contract(self) -> None:
        state = subject.SchedulerStateV5(3)
        issue = self._issue(subject._scheduler_body(state))
        with (
            mock.patch.object(base, "_scheduler_issue_number", return_value=7),
            mock.patch.object(subject.core, "request_data", return_value=issue) as request,
        ):
            self.assertEqual(subject._read_state("o/r", "t"), state)
        self.assertIn("/issues/7", request.call_args.args[0])

        with (
            mock.patch.object(base, "_scheduler_issue_number", return_value=7),
            mock.patch.object(subject.core, "request_data", return_value=[]),
        ):
            with self.assertRaisesRegex(RuntimeError, "response is malformed"):
                subject._read_state("o/r", "t")

        with (
            mock.patch.object(base, "_scheduler_issue_number", return_value=7),
            mock.patch.object(subject.core, "request_data", return_value=issue) as request,
        ):
            subject._write_state("o/r", "t", previous.SchedulerStateV4(3))
        self.assertEqual(request.call_args.args[2], "PATCH")

        different = self._issue(subject._scheduler_body(subject.SchedulerStateV5(4)))
        with (
            mock.patch.object(base, "_scheduler_issue_number", return_value=7),
            mock.patch.object(subject.core, "request_data", return_value=different),
        ):
            with self.assertRaisesRegex(RuntimeError, "not durably acknowledged"):
                subject._write_state("o/r", "t", state)

    def test_pending_state_requires_reversible_head_identity(self) -> None:
        pending = subject._pending_state(
            previous.SchedulerStateV4(7), self._current(), 101, 1, 601
        )
        self.assertEqual(pending.pending_head, SHA)
        self.assertEqual(pending.scan_pr, 1)

        with self.assertRaisesRegex(RuntimeError, "malformed reversible identity"):
            subject._pending_state(
                subject.SchedulerStateV5(0),
                self._current(head="not-a-sha"),
                101,
                1,
                601,
            )

    def test_pending_origin_open_validates_authority_but_closed_survives(self) -> None:
        current = self._current()
        state = subject._pending_state(subject.SchedulerStateV5(0), current, 101, 1, 601)
        with mock.patch.object(subject.core, "request_data", return_value=current):
            self.assertEqual(subject._pending_origin_pr("o/r", "t", state), current)

        closed = self._current(state="closed")
        with mock.patch.object(subject.core, "request_data", return_value=closed):
            self.assertEqual(subject._pending_origin_pr("o/r", "t", state), closed)

        changed = self._current()
        changed["merge_commit_sha"] = "d" * 40
        with mock.patch.object(subject.core, "request_data", return_value=changed):
            with self.assertRaisesRegex(RuntimeError, "authority changed"):
                subject._pending_origin_pr("o/r", "t", state)

        malformed = dict(current)
        malformed["state"] = "mystery"
        with mock.patch.object(subject.core, "request_data", return_value=malformed):
            with self.assertRaisesRegex(RuntimeError, "malformed pending pull-request state"):
                subject._pending_origin_pr("o/r", "t", state)

    def test_unresolved_same_head_uses_stable_open_snapshot(self) -> None:
        one = self._current(1)
        two = self._current(2)
        other = self._current(3, head=OTHER_SHA)
        with (
            mock.patch.object(base.snapshot, "open_pull_requests", return_value=[two, other, one]),
            mock.patch.object(
                subject.core,
                "unresolved_review_threads",
                side_effect=lambda repo, number, token: number == 2,
            ),
        ):
            result = subject._unresolved_same_head("o/r", "t", SHA)
        self.assertEqual([item["number"] for item in result], [2])

    def test_resume_pending_rejects_idle_malformed_regression_and_jump(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "idle scheduler"):
            subject._resume_pending("o/r", "t", subject.SchedulerStateV5(0))

        current = self._current()
        state = subject._pending_state(subject.SchedulerStateV5(0), current, 101, 2, 601)
        with (
            mock.patch.object(subject, "_pending_origin_pr", return_value=current),
            mock.patch.object(subject.core, "request_data", return_value=[]),
        ):
            with self.assertRaisesRegex(RuntimeError, "malformed pending workflow"):
                subject._resume_pending("o/r", "t", state)

        regressed = gate_run(101, 1, head=SHA)
        regressed.update({"run_attempt": 1, "status": "completed", "conclusion": "success"})
        with (
            mock.patch.object(subject, "_pending_origin_pr", return_value=current),
            mock.patch.object(subject.core, "request_data", return_value=regressed),
        ):
            with self.assertRaisesRegex(RuntimeError, "regressed"):
                subject._resume_pending("o/r", "t", state)

        jumped = gate_run(101, 1, head=SHA)
        jumped.update({"run_attempt": 4, "status": "completed", "conclusion": "success"})
        with (
            mock.patch.object(subject, "_pending_origin_pr", return_value=current),
            mock.patch.object(subject.core, "request_data", return_value=jumped),
        ):
            with self.assertRaises(previous.PendingMutationUncertain):
                subject._resume_pending("o/r", "t", state)

    def test_resume_pending_retains_state_while_observation_is_deferred(self) -> None:
        current = self._current()
        state = subject._pending_state(subject.SchedulerStateV5(0), current, 101, 1, 601)
        run = gate_run(101, 1, head=SHA)
        run.update({"run_attempt": 1, "status": "completed", "conclusion": "success"})
        with (
            mock.patch.object(subject, "_pending_origin_pr", return_value=current),
            mock.patch.object(subject.core, "request_data", return_value=run),
            mock.patch.object(
                observation,
                "_wait_for_terminal_invalidation",
                side_effect=base.DeferredObservation("later"),
            ),
            mock.patch.object(subject, "_write_state") as writer,
        ):
            self.assertEqual(subject._resume_pending("o/r", "t", state), [])
        writer.assert_not_called()

    def test_resume_closed_origin_observes_terminal_failure_before_clear(self) -> None:
        current = self._current()
        closed = self._current(state="closed")
        state = subject._pending_state(subject.SchedulerStateV5(0), current, 101, 1, 601)
        run = gate_run(101, 1, head=SHA)
        run.update({"run_attempt": 2, "status": "completed", "conclusion": "failure"})
        with (
            mock.patch.object(subject, "_pending_origin_pr", return_value=closed),
            mock.patch.object(subject.core, "request_data", return_value=run),
            mock.patch.object(observation, "_wait_for_terminal_invalidation", return_value=True) as wait,
            mock.patch.object(subject, "_unresolved_same_head") as siblings,
            mock.patch.object(subject, "_write_state") as writer,
        ):
            self.assertEqual(subject._resume_pending("o/r", "t", state), [])
        self.assertIsNone(wait.call_args.args[6])
        siblings.assert_not_called()
        self.assertEqual(writer.call_args.args[2], subject.SchedulerStateV5(0))

    def test_resume_closed_origin_green_retains_unresolved_sibling(self) -> None:
        origin = self._current()
        closed = self._current(state="closed")
        sibling = self._current(2)
        state = subject._pending_state(subject.SchedulerStateV5(7), origin, 101, 1, 601)
        run = gate_run(101, 1, head=SHA)
        run.update({"run_attempt": 2, "status": "completed", "conclusion": "success"})
        with (
            mock.patch.object(subject, "_pending_origin_pr", return_value=closed),
            mock.patch.object(subject.core, "request_data", return_value=run),
            mock.patch.object(observation, "_wait_for_terminal_invalidation", return_value=False),
            mock.patch.object(subject, "_unresolved_same_head", return_value=[sibling]),
            mock.patch.object(subject, "_write_state") as writer,
        ):
            self.assertEqual(subject._resume_pending("o/r", "t", state), [])
        written = writer.call_args.args[2]
        self.assertEqual(written.pending_pr, 0)
        self.assertEqual(written.scan_pr, 2)
        self.assertEqual(written.cursor_pr, 7)

    def test_resume_green_clears_when_no_same_head_thread_is_unresolved(self) -> None:
        current = self._current()
        state = subject._pending_state(subject.SchedulerStateV5(0), current, 101, 1, 601)
        run = gate_run(101, 1, head=SHA)
        run.update({"run_attempt": 2, "status": "completed", "conclusion": "success"})
        with (
            mock.patch.object(subject, "_pending_origin_pr", return_value=current),
            mock.patch.object(subject.core, "request_data", return_value=run),
            mock.patch.object(observation, "_wait_for_terminal_invalidation", return_value=False) as wait,
            mock.patch.object(subject, "_unresolved_same_head", return_value=[]),
            mock.patch.object(subject, "_write_state") as writer,
        ):
            self.assertEqual(subject._resume_pending("o/r", "t", state), [])
        self.assertEqual(wait.call_args.args[6], current)
        self.assertEqual(writer.call_args.args[2], subject.SchedulerStateV5(0))

    def test_install_reuses_v4_poller_with_v5_state_hooks(self) -> None:
        saved = {
            "read": previous._read_state,
            "write": previous._write_state,
            "clear": previous._clear_pending,
            "pending": previous._pending_state,
            "resume": previous._resume_pending,
            "base_poll": base.poll,
            "core_poll": subject.core.poll,
        }
        try:
            with mock.patch.object(previous, "install") as predecessor_install:
                subject.install()
            predecessor_install.assert_called_once_with()
            self.assertIs(previous._read_state, subject._read_state)
            self.assertIs(previous._resume_pending, subject._resume_pending)
            self.assertIs(base.poll, previous.poll)
            self.assertIs(subject.core.poll, previous.poll)
        finally:
            previous._read_state = saved["read"]
            previous._write_state = saved["write"]
            previous._clear_pending = saved["clear"]
            previous._pending_state = saved["pending"]
            previous._resume_pending = saved["resume"]
            base.poll = saved["base_poll"]
            subject.core.poll = saved["core_poll"]

    def test_main_delegates_after_install(self) -> None:
        with (
            mock.patch.object(subject, "install") as install,
            mock.patch.object(base, "main", return_value=17),
        ):
            self.assertEqual(subject.main(), 17)
        install.assert_called_once_with()

    def test_z_script_entrypoint(self) -> None:
        saved = {
            "read": previous._read_state,
            "write": previous._write_state,
            "clear": previous._clear_pending,
            "pending": previous._pending_state,
            "resume": previous._resume_pending,
            "base_poll": base.poll,
            "core_poll": subject.core.poll,
        }
        try:
            with (
                mock.patch.object(previous, "install"),
                mock.patch.object(base, "main", return_value=0),
            ):
                with self.assertRaises(SystemExit) as exited:
                    runpy.run_path(subject.__file__, run_name="__main__")
            self.assertEqual(exited.exception.code, 0)
        finally:
            previous._read_state = saved["read"]
            previous._write_state = saved["write"]
            previous._clear_pending = saved["clear"]
            previous._pending_state = saved["pending"]
            previous._resume_pending = saved["resume"]
            base.poll = saved["base_poll"]
            subject.core.poll = saved["core_poll"]


if __name__ == "__main__":
    unittest.main()
