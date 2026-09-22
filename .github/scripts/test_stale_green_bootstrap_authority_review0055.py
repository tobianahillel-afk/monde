from __future__ import annotations

import os
import runpy
import unittest
from unittest import mock

from test_stale_green_bootstrap_authority import check, gate_run, pr
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0049 as pending
import stale_green_bootstrap_authority_review0051_recovery as recovery
import stale_green_bootstrap_authority_review0054 as previous
import stale_green_bootstrap_authority_review0055 as subject


class Review0055PendingLifetimeTests(unittest.TestCase):
    def tearDown(self) -> None:
        pending._process_head_group = subject._ORIGINAL_PROCESS

    def _process_context(self, *, unresolved, latest=None, writer=None, wait_result=False):
        current = pr(1, branch="shared", head="shared-head")
        latest = latest or check(601, 201)
        target = (gate_run(101, 1), check(501, 101))
        return (
            current,
            (
                mock.patch.object(pending.core, "latest_required_check", return_value=latest),
                mock.patch.object(pending.core, "unresolved_review_threads", side_effect=unresolved),
                mock.patch.object(pending.previous, "_direct_target_for_pr", return_value=(target, None)),
                mock.patch.object(pending.base, "_current_pr", return_value=current),
                mock.patch.object(pending.previous, "_mutation_baseline", return_value=1),
                mock.patch.object(pending, "_write_state", writer or mock.Mock()),
                mock.patch.object(pending.core, "rerun_workflow"),
                mock.patch.object(pending.previous, "_wait_for_terminal_invalidation", return_value=wait_result),
            ),
        )

    def test_runtime_error_while_pending_active_becomes_uncertainty_and_keeps_write_ahead(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        latest = check(601, 201)
        target = (gate_run(101, 1), check(501, 101))
        writer = mock.Mock()
        with (
            mock.patch.object(pending.core, "latest_required_check", return_value=latest),
            mock.patch.object(
                pending.core,
                "unresolved_review_threads",
                side_effect=[True, True, True, RuntimeError("graphql reclassification failed")],
            ),
            mock.patch.object(pending.previous, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(pending.base, "_current_pr", return_value=current),
            mock.patch.object(pending.previous, "_mutation_baseline", return_value=1),
            mock.patch.object(pending, "_write_state", writer),
            mock.patch.object(pending.core, "rerun_workflow"),
            mock.patch.object(pending.previous, "_wait_for_terminal_invalidation", return_value=False),
        ):
            with self.assertRaisesRegex(
                pending.PendingMutationUncertain,
                "durable pending mutation remained active",
            ) as raised:
                subject._pending_lifetime_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                )
        self.assertIsInstance(raised.exception.__cause__, RuntimeError)
        self.assertEqual(writer.call_count, 1)
        self.assertEqual(writer.call_args.args[2].pending_run_id, 101)

    def test_failed_clear_ack_keeps_pending_active_and_fails_uncertain(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        latest = check(601, 201)
        target = (gate_run(101, 1), check(501, 101))
        writer = mock.Mock(side_effect=[None, RuntimeError("clear acknowledgement failed")])
        with (
            mock.patch.object(pending.core, "latest_required_check", return_value=latest),
            mock.patch.object(pending.core, "unresolved_review_threads", side_effect=[True, True, True, False]),
            mock.patch.object(pending.previous, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(pending.base, "_current_pr", return_value=current),
            mock.patch.object(pending.previous, "_mutation_baseline", return_value=1),
            mock.patch.object(pending, "_write_state", writer),
            mock.patch.object(pending.core, "rerun_workflow"),
            mock.patch.object(pending.previous, "_wait_for_terminal_invalidation", return_value=False),
        ):
            with self.assertRaises(pending.PendingMutationUncertain):
                subject._pending_lifetime_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                )
        self.assertEqual(writer.call_count, 2)
        self.assertGreater(writer.call_args_list[0].args[2].pending_pr, 0)

    def test_runtime_error_after_acknowledged_clear_stays_ordinary(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        latest = check(601, 201)
        target = (gate_run(101, 1), check(501, 101))
        writer = mock.Mock()
        with (
            mock.patch.object(
                pending.core,
                "latest_required_check",
                side_effect=[latest, latest, RuntimeError("late check lookup failed")],
            ),
            mock.patch.object(pending.core, "unresolved_review_threads", side_effect=[True, True, True, False]),
            mock.patch.object(pending.previous, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(pending.base, "_current_pr", return_value=current),
            mock.patch.object(pending.previous, "_mutation_baseline", return_value=1),
            mock.patch.object(pending, "_write_state", writer),
            mock.patch.object(pending.core, "rerun_workflow"),
            mock.patch.object(pending.previous, "_wait_for_terminal_invalidation", return_value=False),
        ):
            with self.assertRaisesRegex(RuntimeError, "late check lookup failed") as raised:
                subject._pending_lifetime_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                )
        self.assertNotIsInstance(raised.exception, pending.PendingMutationUncertain)
        self.assertEqual(writer.call_count, 2)
        self.assertEqual(writer.call_args_list[1].args[2].pending_pr, 0)

    def test_pre_pending_runtime_error_stays_ordinary(self) -> None:
        current = pr(1)
        with (
            mock.patch.object(pending.core, "latest_required_check", side_effect=RuntimeError("early")),
            mock.patch.object(pending, "_write_state") as writer,
        ):
            with self.assertRaisesRegex(RuntimeError, "early") as raised:
                subject._pending_lifetime_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                )
        self.assertNotIsInstance(raised.exception, pending.PendingMutationUncertain)
        writer.assert_not_called()

    def test_existing_pending_exceptions_are_preserved(self) -> None:
        current = pr(1)
        for exc in (
            pending.PendingMutationObservation(101),
            pending.PendingMutationUncertain("already uncertain"),
        ):
            with (
                mock.patch.object(subject, "_ORIGINAL_PROCESS", side_effect=exc),
                mock.patch.object(pending, "_write_state"),
            ):
                with self.assertRaises(type(exc)) as raised:
                    subject._pending_lifetime_process(
                        "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                    )
            self.assertIs(raised.exception, exc)

    def test_install_and_main(self) -> None:
        with mock.patch.object(previous, "install") as install:
            subject.install()
        install.assert_called_once()
        self.assertIs(pending._process_head_group, subject._pending_lifetime_process)

        with (
            mock.patch.object(subject, "install"),
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(base, "main", return_value=17) as base_main,
        ):
            self.assertEqual(subject.main(), 17)
        base_main.assert_called_once()

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
