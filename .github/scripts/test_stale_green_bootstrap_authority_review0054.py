from __future__ import annotations

import os
import runpy
import unittest
from unittest import mock

import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0048 as observation
import stale_green_bootstrap_authority_review0049 as pending
import stale_green_bootstrap_authority_review0051_recovery as previous
import stale_green_bootstrap_authority_review0054 as subject


class Review0054PendingRetentionTests(unittest.TestCase):
    def tearDown(self) -> None:
        observation._wait_for_terminal_invalidation = subject._ORIGINAL_WAIT

    def test_wrapper_preserves_success_deferred_and_existing_uncertainty(self) -> None:
        with mock.patch.object(subject, "_ORIGINAL_WAIT", return_value=True):
            self.assertTrue(subject._pending_preserving_wait("o/r", "h", "t", 1, 1, 1))

        deferred = base.DeferredObservation("later")
        with mock.patch.object(subject, "_ORIGINAL_WAIT", side_effect=deferred):
            with self.assertRaises(base.DeferredObservation) as raised:
                subject._pending_preserving_wait("o/r", "h", "t", 1, 1, 1)
        self.assertIs(raised.exception, deferred)

        uncertain = pending.PendingMutationUncertain("already uncertain")
        with mock.patch.object(subject, "_ORIGINAL_WAIT", side_effect=uncertain):
            with self.assertRaises(pending.PendingMutationUncertain) as raised:
                subject._pending_preserving_wait("o/r", "h", "t", 1, 1, 1)
        self.assertIs(raised.exception, uncertain)

    def test_wrapper_converts_post_condition_runtime_error_to_pending_uncertainty(self) -> None:
        cause = RuntimeError("bootstrap GitHub request budget exceeded (100/100)")
        with mock.patch.object(subject, "_ORIGINAL_WAIT", side_effect=cause):
            with self.assertRaisesRegex(
                pending.PendingMutationUncertain,
                "durable pending state retained",
            ) as raised:
                subject._pending_preserving_wait("o/r", "h", "t", 1, 1, 1)
        self.assertIs(raised.exception.__cause__, cause)

    def test_review0049_process_keeps_only_write_ahead_state_on_runtime_observation_failure(self) -> None:
        from test_stale_green_bootstrap_authority import check, gate_run, pr

        current = pr(1, branch="shared", head="shared-head")
        latest = check(601, 201)
        target = (gate_run(101, 1), check(501, 101))
        with (
            mock.patch.object(
                observation,
                "_wait_for_terminal_invalidation",
                subject._pending_preserving_wait,
            ),
            mock.patch.object(pending.core, "latest_required_check", return_value=latest),
            mock.patch.object(pending.core, "unresolved_review_threads", return_value=True),
            mock.patch.object(pending.previous, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(pending.base, "_current_pr", return_value=current),
            mock.patch.object(pending.previous, "_mutation_baseline", return_value=1),
            mock.patch.object(pending, "_write_state") as writer,
            mock.patch.object(pending.core, "rerun_workflow"),
            mock.patch.object(
                subject,
                "_ORIGINAL_WAIT",
                side_effect=RuntimeError("malformed post-condition"),
            ),
        ):
            with self.assertRaises(pending.PendingMutationUncertain):
                pending._process_head_group(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                )
        self.assertEqual(writer.call_count, 1)
        written = writer.call_args.args[2]
        self.assertEqual((written.pending_pr, written.pending_run_id), (1, 101))

    def test_poll_rethrows_pending_uncertainty_without_idle_state_write(self) -> None:
        from test_stale_green_bootstrap_authority import pr

        current = pr(1)
        with (
            mock.patch.object(pending, "_read_state", return_value=pending.SchedulerStateV4(0)),
            mock.patch.object(pending.base.snapshot, "open_pull_requests", return_value=[current]),
            mock.patch.object(
                pending,
                "_process_head_group",
                side_effect=pending.PendingMutationUncertain("post-condition failed"),
            ),
            mock.patch.object(pending, "_write_state") as writer,
        ):
            with self.assertRaises(pending.PendingMutationUncertain):
                pending.poll("o/r", "t")
        writer.assert_not_called()

    def test_install_and_main_route_poll_and_recovery(self) -> None:
        with mock.patch.object(previous, "install") as install:
            subject.install()
        install.assert_called_once()
        self.assertIs(observation._wait_for_terminal_invalidation, subject._pending_preserving_wait)

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
            mock.patch.object(previous, "_inspect_confirmed_unposted", return_value=0) as inspect,
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
