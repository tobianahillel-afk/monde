from __future__ import annotations

import os
import runpy
import unittest
from unittest import mock

from test_stale_green_bootstrap_authority import check, gate_run, pr
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0049 as pending
import stale_green_bootstrap_authority_review0051_recovery as recovery
import stale_green_bootstrap_authority_review0055 as previous
import stale_green_bootstrap_authority_review0056 as subject


class Review0056PendingWriteAckTests(unittest.TestCase):
    def tearDown(self) -> None:
        pending._process_head_group = previous._pending_lifetime_process

    def test_ambiguous_pending_write_ack_is_uncertain_before_post(self) -> None:
        current = pr(1, branch="shared", head="a" * 40)
        latest = check(601, 201)
        target = (gate_run(101, 1), check(501, 101))
        writer = mock.Mock(side_effect=RuntimeError("scheduler V5 state update was not durably acknowledged"))
        rerun = mock.Mock()
        with (
            mock.patch.object(pending.core, "latest_required_check", return_value=latest),
            mock.patch.object(pending.core, "unresolved_review_threads", return_value=True),
            mock.patch.object(pending.previous, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(pending.base, "_current_pr", return_value=current),
            mock.patch.object(pending.previous, "_mutation_baseline", return_value=1),
            mock.patch.object(pending, "_write_state", writer),
            mock.patch.object(pending.core, "rerun_workflow", rerun),
        ):
            with self.assertRaisesRegex(
                pending.PendingMutationUncertain,
                "write-ahead pending-state acknowledgement is ambiguous",
            ) as raised:
                subject._pending_write_ack_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                )
        self.assertIsInstance(raised.exception.__cause__, RuntimeError)
        writer.assert_called_once()
        rerun.assert_not_called()

    def test_nonpending_write_failure_is_not_reclassified(self) -> None:
        state = pending.SchedulerStateV4(1)
        writer = mock.Mock(side_effect=RuntimeError("idle write failed"))
        with (
            mock.patch.object(pending, "_write_state", writer),
            mock.patch.object(previous, "_pending_lifetime_process") as process,
        ):
            def invoke(*_args, **_kwargs):
                pending._write_state("o/r", "t", state)
            process.side_effect = invoke
            with self.assertRaisesRegex(RuntimeError, "idle write failed") as raised:
                subject._pending_write_ack_process("o/r", "t", [], 3, state)
        self.assertNotIsInstance(raised.exception, pending.PendingMutationUncertain)

    def test_successful_pending_write_delegates_to_review0055_lifetime_protection(self) -> None:
        state = pending.SchedulerStateV4(
            0, 1, 1, "-", 1, "b" * 64, 101, 1, 601
        )
        writer = mock.Mock()
        with (
            mock.patch.object(pending, "_write_state", writer),
            mock.patch.object(previous, "_pending_lifetime_process") as process,
        ):
            def invoke(*_args, **_kwargs):
                pending._write_state("o/r", "t", state)
                return ([101], [], None)
            process.side_effect = invoke
            self.assertEqual(
                subject._pending_write_ack_process("o/r", "t", [], 3, pending.SchedulerStateV4(0)),
                ([101], [], None),
            )
        writer.assert_called_once()

    def test_existing_pending_exception_from_writer_is_preserved(self) -> None:
        state = pending.SchedulerStateV4(
            0, 1, 1, "-", 1, "b" * 64, 101, 1, 601
        )
        exc = pending.PendingMutationUncertain("already uncertain")
        with (
            mock.patch.object(pending, "_write_state", side_effect=exc),
            mock.patch.object(previous, "_pending_lifetime_process") as process,
        ):
            def invoke(*_args, **_kwargs):
                pending._write_state("o/r", "t", state)
            process.side_effect = invoke
            with self.assertRaises(pending.PendingMutationUncertain) as raised:
                subject._pending_write_ack_process("o/r", "t", [], 3, pending.SchedulerStateV4(0))
        self.assertIs(raised.exception, exc)

    def test_install_and_main_guards(self) -> None:
        with mock.patch.object(previous, "install") as install:
            subject.install()
        install.assert_called_once()
        self.assertIs(pending._process_head_group, subject._pending_write_ack_process)

        with (
            mock.patch.object(subject, "install"),
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(base, "main", return_value=17) as base_main,
        ):
            self.assertEqual(subject.main(), 17)
        base_main.assert_called_once()

        with (
            mock.patch.object(subject, "install"),
            mock.patch.dict(os.environ, {"BOOTSTRAP_RECOVERY_ACTION": "bad"}, clear=True),
        ):
            with self.assertRaisesRegex(RuntimeError, "unsupported bootstrap recovery action"):
                subject.main()

        with (
            mock.patch.object(subject, "install"),
            mock.patch.dict(os.environ, {"BOOTSTRAP_RECOVERY_ACTION": subject.RECOVERY_ACTION}, clear=True),
        ):
            with self.assertRaisesRegex(RuntimeError, "GITHUB_REPOSITORY and GITHUB_TOKEN"):
                subject.main()

        env = {
            "BOOTSTRAP_RECOVERY_ACTION": subject.RECOVERY_ACTION,
            "GITHUB_REPOSITORY": "o/r",
            "GITHUB_TOKEN": "t",
        }
        with (
            mock.patch.object(subject, "install"),
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch.object(recovery, "_inspect_confirmed_unposted", return_value=0) as inspect,
        ):
            self.assertEqual(subject.main(), 0)
        inspect.assert_called_once_with("o/r", "t")

    def test_module_entrypoint(self) -> None:
        with (
            mock.patch.object(previous, "install") as predecessor_install,
            mock.patch.object(base, "main", return_value=0),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            with self.assertRaises(SystemExit) as raised:
                runpy.run_path(subject.__file__, run_name="__main__")
        self.assertEqual(raised.exception.code, 0)
        predecessor_install.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
