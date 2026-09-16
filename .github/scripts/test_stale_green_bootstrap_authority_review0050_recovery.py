from __future__ import annotations

import os
import runpy
import unittest
from unittest import mock

from test_stale_green_bootstrap_pr_snapshot import SHA
from test_stale_green_bootstrap_authority import gate_run, pr
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0048 as observation
import stale_green_bootstrap_authority_review0050 as v5
import stale_green_bootstrap_authority_review0050_recovery as subject


class Review0050RecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        base._reset_request_budget()
        self.addCleanup(base._reset_request_budget)

    @staticmethod
    def _current(number: int = 1, *, state: str = "open") -> dict:
        return pr(number, state=state, branch="shared", head=SHA)

    def _state(self) -> v5.SchedulerStateV5:
        return v5._pending_state(v5.SchedulerStateV5(0), self._current(), 101, 1, 601)

    @staticmethod
    def _env(state: v5.SchedulerStateV5) -> dict[str, str]:
        return {
            "BOOTSTRAP_RECOVERY_CONFIRMATION": subject.RECOVERY_CONFIRMATION,
            "BOOTSTRAP_RECOVERY_REASON": "operator inspected Actions and confirmed no rerun",
            "BOOTSTRAP_RECOVERY_PENDING_PR": str(state.pending_pr),
            "BOOTSTRAP_RECOVERY_PENDING_HEAD": state.pending_head,
            "BOOTSTRAP_RECOVERY_RUN_ID": str(state.pending_run_id),
            "BOOTSTRAP_RECOVERY_BASELINE_ATTEMPT": str(state.pending_baseline_attempt),
            "BOOTSTRAP_RECOVERY_CHECK_ID": str(state.pending_check_id),
        }

    def test_resume_pending_timeout_is_loud_and_keeps_state(self) -> None:
        current = self._current()
        state = self._state()
        run = gate_run(101, 1, head=SHA)
        run.update({"run_attempt": 1, "status": "completed", "conclusion": "success"})
        with (
            mock.patch.object(v5, "_pending_origin_pr", return_value=current),
            mock.patch.object(subject.core, "request_data", return_value=run),
            mock.patch.object(
                observation,
                "_wait_for_terminal_invalidation",
                side_effect=base.DeferredObservation("later"),
            ),
            mock.patch.object(v5, "_write_state") as writer,
        ):
            with self.assertRaisesRegex(subject.PendingRecoveryRequired, "workflow_dispatch recovery"):
                subject._resume_pending("o/r", "t", state)
        writer.assert_not_called()

    def test_resume_pending_terminal_paths_delegate_v5_semantics(self) -> None:
        current = self._current()
        state = self._state()
        run = gate_run(101, 1, head=SHA)
        run.update({"run_attempt": 2, "status": "completed", "conclusion": "failure"})
        with (
            mock.patch.object(v5, "_pending_origin_pr", return_value=current),
            mock.patch.object(subject.core, "request_data", return_value=run),
            mock.patch.object(observation, "_wait_for_terminal_invalidation", return_value=True),
            mock.patch.object(v5, "_write_state") as writer,
        ):
            self.assertEqual(subject._resume_pending("o/r", "t", state), [])
        self.assertEqual(writer.call_args.args[2], v5.SchedulerStateV5(0))

        with self.assertRaisesRegex(RuntimeError, "idle scheduler"):
            subject._resume_pending("o/r", "t", v5.SchedulerStateV5(0))

    def test_validate_recovery_request_is_closed_world(self) -> None:
        state = self._state()
        with mock.patch.dict(os.environ, self._env(state), clear=True):
            self.assertIn("operator inspected", subject._validate_recovery_request(state))

        bad_cases = [
            {"BOOTSTRAP_RECOVERY_CONFIRMATION": "wrong"},
            {"BOOTSTRAP_RECOVERY_REASON": ""},
            {"BOOTSTRAP_RECOVERY_PENDING_PR": "0"},
            {"BOOTSTRAP_RECOVERY_RUN_ID": "101.0"},
            {"BOOTSTRAP_RECOVERY_PENDING_HEAD": "d" * 40},
        ]
        base_env = self._env(state)
        for overrides in bad_cases:
            env = dict(base_env)
            env.update(overrides)
            with self.subTest(overrides=overrides), mock.patch.dict(os.environ, env, clear=True):
                with self.assertRaises(RuntimeError):
                    subject._validate_recovery_request(state)
        with self.assertRaisesRegex(RuntimeError, "no pending mutation"):
            subject._validate_recovery_request(v5.SchedulerStateV5(0))

    def test_operator_recovery_revalidates_and_requeues_unresolved_sibling(self) -> None:
        origin = self._current(state="closed")
        sibling = self._current(2)
        state = self._state()
        run = gate_run(101, 1, head=SHA)
        run.update({"run_attempt": 1, "status": "completed", "conclusion": "success"})
        latest = {"id": 601, "status": "completed", "conclusion": "success"}
        with (
            mock.patch.dict(os.environ, self._env(state), clear=True),
            mock.patch.object(v5, "_read_state", return_value=state),
            mock.patch.object(v5, "_pending_origin_pr", return_value=origin),
            mock.patch.object(subject.core, "request_data", return_value=run),
            mock.patch.object(subject.core, "latest_required_check", return_value=latest),
            mock.patch.object(v5, "_unresolved_same_head", return_value=[sibling]),
            mock.patch.object(v5, "_write_state") as writer,
            mock.patch("builtins.print") as printer,
        ):
            self.assertEqual(subject._recover_confirmed_unposted("o/r", "t"), 0)
        written = writer.call_args.args[2]
        self.assertEqual(written.pending_pr, 0)
        self.assertEqual(written.scan_pr, 2)
        self.assertIn("operator-confirmed", printer.call_args.args[0])

    def test_operator_recovery_refuses_visible_mutation_or_check_drift(self) -> None:
        current = self._current()
        state = self._state()
        advanced = gate_run(101, 1, head=SHA)
        advanced.update({"run_attempt": 2, "status": "completed", "conclusion": "failure"})
        env = self._env(state)
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch.object(v5, "_read_state", return_value=state),
            mock.patch.object(v5, "_pending_origin_pr", return_value=current),
            mock.patch.object(subject.core, "request_data", return_value=advanced),
        ):
            with self.assertRaisesRegex(RuntimeError, "attempt changed"):
                subject._recover_confirmed_unposted("o/r", "t")

        baseline = gate_run(101, 1, head=SHA)
        baseline.update({"run_attempt": 1, "status": "completed", "conclusion": "success"})
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch.object(v5, "_read_state", return_value=state),
            mock.patch.object(v5, "_pending_origin_pr", return_value=current),
            mock.patch.object(subject.core, "request_data", return_value=baseline),
            mock.patch.object(
                subject.core,
                "latest_required_check",
                return_value={"id": 999, "status": "completed", "conclusion": "success"},
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "check identity changed"):
                subject._recover_confirmed_unposted("o/r", "t")

    def test_install_and_main_routes_normal_and_recovery_modes(self) -> None:
        saved = {
            "resume": v5.previous._resume_pending,
            "base_poll": base.poll,
            "core_poll": subject.core.poll,
        }
        try:
            with mock.patch.object(v5, "install") as predecessor_install:
                subject.install()
            predecessor_install.assert_called_once_with()
            self.assertIs(v5.previous._resume_pending, subject._resume_pending)
            self.assertIs(base.poll, v5.previous.poll)

            with (
                mock.patch.object(subject, "install"),
                mock.patch.object(base, "main", return_value=7),
                mock.patch.dict(os.environ, {}, clear=True),
            ):
                self.assertEqual(subject.main(), 7)

            with (
                mock.patch.object(subject, "install"),
                mock.patch.dict(os.environ, {"BOOTSTRAP_RECOVERY_ACTION": "bad"}, clear=True),
            ):
                with self.assertRaisesRegex(RuntimeError, "unsupported"):
                    subject.main()

            with (
                mock.patch.object(subject, "install"),
                mock.patch.dict(
                    os.environ,
                    {"BOOTSTRAP_RECOVERY_ACTION": subject.RECOVERY_ACTION},
                    clear=True,
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "GITHUB_REPOSITORY"):
                    subject.main()

            with (
                mock.patch.object(subject, "install"),
                mock.patch.object(subject, "_recover_confirmed_unposted", return_value=0) as recover,
                mock.patch.dict(
                    os.environ,
                    {
                        "BOOTSTRAP_RECOVERY_ACTION": subject.RECOVERY_ACTION,
                        "GITHUB_REPOSITORY": "o/r",
                        "GITHUB_TOKEN": "t",
                    },
                    clear=True,
                ),
            ):
                self.assertEqual(subject.main(), 0)
            recover.assert_called_once_with("o/r", "t")
        finally:
            v5.previous._resume_pending = saved["resume"]
            base.poll = saved["base_poll"]
            subject.core.poll = saved["core_poll"]

    def test_script_entrypoint(self) -> None:
        with (
            mock.patch.object(subject, "install"),
            mock.patch.object(base, "main", return_value=0),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            with self.assertRaises(SystemExit) as exited:
                runpy.run_path(subject.__file__, run_name="__main__")
        self.assertEqual(exited.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
