from __future__ import annotations

import os
import runpy
import unittest
from unittest import mock

from test_stale_green_bootstrap_authority import check, gate_run, pr
import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0049 as pending
import stale_green_bootstrap_authority_review0051_recovery as recovery
import stale_green_bootstrap_authority_review0055 as lifetime
import stale_green_bootstrap_authority_review0065 as previous
import stale_green_bootstrap_authority_review0066 as subject


class Review0066CoherentMutationSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        base._reset_request_budget()
        self.addCleanup(base._reset_request_budget)

    def tearDown(self) -> None:
        pending._process_head_group = lifetime._pending_lifetime_process

    def _fixture(self):
        current = pr(1, branch="shared", head="a" * 40)
        latest = check(601, 201)
        target = (gate_run(101, 1), check(501, 101))
        pending_state = pending._pending_state(
            pending.SchedulerStateV4(0),
            current,
            101,
            1,
            latest["id"],
        )
        return current, latest, target, pending_state

    def test_gate_helper_requires_merge_acceptable_exact_identity(self) -> None:
        _current, latest, _target, _state = self._fixture()
        with mock.patch.object(core, "latest_required_check", return_value=latest):
            self.assertIs(
                subject._require_expected_gate("o/r", "a" * 40, "t", 601, "G1"),
                latest,
            )

        with mock.patch.object(core, "latest_required_check", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "not merge-acceptable.*G1"):
                subject._require_expected_gate("o/r", "a" * 40, "t", 601, "G1")

        with mock.patch.object(
            core,
            "latest_required_check",
            return_value={**latest, "id": 602},
        ):
            with self.assertRaisesRegex(RuntimeError, "authority changed.*G2"):
                subject._require_expected_gate("o/r", "a" * 40, "t", 601, "G2")

    def _invoke_guarded_pending(
        self,
        current,
        latest,
        pending_state,
        *,
        gates=None,
        current_pr=mock.DEFAULT,
        unresolved=True,
        remaining=None,
        writer=None,
    ):
        writer = writer or mock.Mock()
        gates = gates or [latest, latest]
        if current_pr is mock.DEFAULT:
            current_pr = current
        patches = [
            mock.patch.object(pending, "_write_state", writer),
            mock.patch.object(lifetime, "_pending_lifetime_process"),
            mock.patch.object(core, "latest_required_check", side_effect=gates),
            mock.patch.object(pending, "_current_pending_pr", return_value=current_pr),
            mock.patch.object(core, "unresolved_review_threads", return_value=unresolved),
        ]
        if remaining is not None:
            patches.append(
                mock.patch.object(base, "_remaining_request_budget", return_value=remaining)
            )
        with patches[0], patches[1] as process, patches[2] as gate_read, patches[3] as pr_read, patches[4] as threads:
            extra = patches[5] if len(patches) > 5 else None
            if extra is not None:
                extra.start()
            try:
                def invoke(*_args, **_kwargs):
                    pending._write_state("o/r", "t", pending_state)
                process.side_effect = invoke
                result = subject._coherent_mutation_snapshot_process(
                    "o/r",
                    "t",
                    [current],
                    3,
                    pending.SchedulerStateV4(0),
                )
                return result, writer, gate_read, pr_read, threads
            finally:
                if extra is not None:
                    extra.stop()

    def test_coherent_g1_pr_threads_g2_allows_pending_write(self) -> None:
        current, latest, _target, pending_state = self._fixture()
        result, writer, gate_read, pr_read, threads = self._invoke_guarded_pending(
            current,
            latest,
            pending_state,
            remaining=pending.MUTATION_REQUEST_RESERVE,
        )
        self.assertIsNone(result)
        self.assertEqual(gate_read.call_count, 2)
        pr_read.assert_called_once_with("o/r", "t", pending_state)
        threads.assert_called_once_with("o/r", 1, "t")
        writer.assert_called_once_with("o/r", "t", pending_state)

    def test_pr_closure_or_authority_drift_fails_before_g2_and_write(self) -> None:
        current, latest, _target, pending_state = self._fixture()
        writer = mock.Mock()
        with (
            mock.patch.object(pending, "_write_state", writer),
            mock.patch.object(lifetime, "_pending_lifetime_process") as process,
            mock.patch.object(core, "latest_required_check", return_value=latest) as gate_read,
            mock.patch.object(pending, "_current_pending_pr", return_value=None),
            mock.patch.object(core, "unresolved_review_threads") as threads,
        ):
            def invoke(*_args, **_kwargs):
                pending._write_state("o/r", "t", pending_state)
            process.side_effect = invoke
            with self.assertRaisesRegex(RuntimeError, "closed during mutation snapshot"):
                subject._coherent_mutation_snapshot_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                )
        self.assertEqual(gate_read.call_count, 1)
        threads.assert_not_called()
        writer.assert_not_called()

        changed = RuntimeError("pending pull-request authority changed before mutation observation completed")
        with (
            mock.patch.object(pending, "_write_state", writer),
            mock.patch.object(lifetime, "_pending_lifetime_process") as process,
            mock.patch.object(core, "latest_required_check", return_value=latest),
            mock.patch.object(pending, "_current_pending_pr", side_effect=changed),
        ):
            def invoke_changed(*_args, **_kwargs):
                pending._write_state("o/r", "t", pending_state)
            process.side_effect = invoke_changed
            with self.assertRaisesRegex(RuntimeError, "authority changed"):
                subject._coherent_mutation_snapshot_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                )
        writer.assert_not_called()

    def test_thread_resolution_inside_sandwich_fails_before_g2_and_write(self) -> None:
        current, latest, _target, pending_state = self._fixture()
        writer = mock.Mock()
        with (
            mock.patch.object(pending, "_write_state", writer),
            mock.patch.object(lifetime, "_pending_lifetime_process") as process,
            mock.patch.object(core, "latest_required_check", return_value=latest) as gate_read,
            mock.patch.object(pending, "_current_pending_pr", return_value=current),
            mock.patch.object(core, "unresolved_review_threads", return_value=False),
        ):
            def invoke(*_args, **_kwargs):
                pending._write_state("o/r", "t", pending_state)
            process.side_effect = invoke
            with self.assertRaisesRegex(RuntimeError, "review-thread authority resolved"):
                subject._coherent_mutation_snapshot_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                )
        self.assertEqual(gate_read.call_count, 1)
        writer.assert_not_called()

    def test_gate_advancement_at_g2_fails_without_write(self) -> None:
        current, latest, _target, pending_state = self._fixture()
        advanced = {**latest, "id": 602}
        writer = mock.Mock()
        with (
            mock.patch.object(pending, "_write_state", writer),
            mock.patch.object(lifetime, "_pending_lifetime_process") as process,
            mock.patch.object(
                core,
                "latest_required_check",
                side_effect=[latest, advanced],
            ),
            mock.patch.object(pending, "_current_pending_pr", return_value=current),
            mock.patch.object(core, "unresolved_review_threads", return_value=True),
        ):
            def invoke(*_args, **_kwargs):
                pending._write_state("o/r", "t", pending_state)
            process.side_effect = invoke
            with self.assertRaisesRegex(RuntimeError, "authority changed.*G2"):
                subject._coherent_mutation_snapshot_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                )
        writer.assert_not_called()

    def test_invalid_pending_identity_and_g1_failure_short_circuit_snapshot(self) -> None:
        current, latest, _target, _pending_state = self._fixture()
        malformed = pending.SchedulerStateV4(
            0, 1, 1, "-", 1, "b" * 64, 101, 1, 0
        )
        writer = mock.Mock()
        gate_read = mock.Mock()
        with (
            mock.patch.object(pending, "_write_state", writer),
            mock.patch.object(lifetime, "_pending_lifetime_process") as process,
            mock.patch.object(core, "latest_required_check", gate_read),
            mock.patch.object(pending, "_current_pending_pr") as pr_read,
        ):
            def invoke(*_args, **_kwargs):
                pending._write_state("o/r", "t", malformed)
            process.side_effect = invoke
            with self.assertRaisesRegex(RuntimeError, "lacks exact prior required-check identity"):
                subject._coherent_mutation_snapshot_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                )
        gate_read.assert_not_called()
        pr_read.assert_not_called()
        writer.assert_not_called()

        bad = {**latest, "conclusion": "failure"}
        _current, _latest, _target, pending_state = self._fixture()
        with (
            mock.patch.object(pending, "_write_state", writer),
            mock.patch.object(lifetime, "_pending_lifetime_process") as process,
            mock.patch.object(core, "latest_required_check", return_value=bad),
            mock.patch.object(pending, "_current_pending_pr") as pr_read,
        ):
            def invoke_bad(*_args, **_kwargs):
                pending._write_state("o/r", "t", pending_state)
            process.side_effect = invoke_bad
            with self.assertRaisesRegex(RuntimeError, "not merge-acceptable.*G1"):
                subject._coherent_mutation_snapshot_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                )
        pr_read.assert_not_called()
        writer.assert_not_called()

    def test_reserve_is_checked_after_g2_before_actual_write(self) -> None:
        current, latest, _target, pending_state = self._fixture()
        writer = mock.Mock()
        with (
            mock.patch.object(pending, "_write_state", writer),
            mock.patch.object(lifetime, "_pending_lifetime_process") as process,
            mock.patch.object(core, "latest_required_check", side_effect=[latest, latest]),
            mock.patch.object(pending, "_current_pending_pr", return_value=current),
            mock.patch.object(core, "unresolved_review_threads", return_value=True),
            mock.patch.object(
                base,
                "_remaining_request_budget",
                return_value=pending.MUTATION_REQUEST_RESERVE - 1,
            ),
        ):
            def invoke(*_args, **_kwargs):
                pending._write_state("o/r", "t", pending_state)
            process.side_effect = invoke
            with self.assertRaisesRegex(
                base.DeferredForBudget,
                "after coherent mutation snapshot",
            ):
                subject._coherent_mutation_snapshot_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                )
        writer.assert_not_called()

    def test_actual_write_ack_and_existing_pending_exceptions_preserved(self) -> None:
        current, latest, _target, pending_state = self._fixture()
        writer = mock.Mock(side_effect=RuntimeError("ack lost"))
        common = (
            mock.patch.object(core, "latest_required_check", side_effect=[latest, latest]),
            mock.patch.object(pending, "_current_pending_pr", return_value=current),
            mock.patch.object(core, "unresolved_review_threads", return_value=True),
            mock.patch.object(
                base,
                "_remaining_request_budget",
                return_value=pending.MUTATION_REQUEST_RESERVE,
            ),
        )
        with (
            mock.patch.object(pending, "_write_state", writer),
            mock.patch.object(lifetime, "_pending_lifetime_process") as process,
            common[0], common[1], common[2], common[3],
        ):
            def invoke(*_args, **_kwargs):
                pending._write_state("o/r", "t", pending_state)
            process.side_effect = invoke
            with self.assertRaisesRegex(
                pending.PendingMutationUncertain,
                "acknowledgement is ambiguous",
            ) as raised:
                subject._coherent_mutation_snapshot_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                )
        self.assertIsInstance(raised.exception.__cause__, RuntimeError)

        existing = pending.PendingMutationUncertain("already uncertain")
        with (
            mock.patch.object(pending, "_write_state", side_effect=existing),
            mock.patch.object(lifetime, "_pending_lifetime_process") as process,
            mock.patch.object(core, "latest_required_check", side_effect=[latest, latest]),
            mock.patch.object(pending, "_current_pending_pr", return_value=current),
            mock.patch.object(core, "unresolved_review_threads", return_value=True),
            mock.patch.object(
                base,
                "_remaining_request_budget",
                return_value=pending.MUTATION_REQUEST_RESERVE,
            ),
        ):
            def invoke_existing(*_args, **_kwargs):
                pending._write_state("o/r", "t", pending_state)
            process.side_effect = invoke_existing
            with self.assertRaises(pending.PendingMutationUncertain) as raised_existing:
                subject._coherent_mutation_snapshot_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                )
        self.assertIs(raised_existing.exception, existing)

    def test_nonpending_write_and_empty_group_are_transparent(self) -> None:
        current, _latest, _target, _pending_state = self._fixture()
        idle = pending.SchedulerStateV4(1)
        writer = mock.Mock()
        gate_read = mock.Mock()
        with (
            mock.patch.object(pending, "_write_state", writer),
            mock.patch.object(lifetime, "_pending_lifetime_process") as process,
            mock.patch.object(core, "latest_required_check", gate_read),
        ):
            def invoke_idle(*_args, **_kwargs):
                pending._write_state("o/r", "t", idle)
                return ([], [], None)
            process.side_effect = invoke_idle
            self.assertEqual(
                subject._coherent_mutation_snapshot_process(
                    "o/r", "t", [current], 3, idle
                ),
                ([], [], None),
            )
        gate_read.assert_not_called()
        writer.assert_called_once_with("o/r", "t", idle)

        with mock.patch.object(
            lifetime,
            "_pending_lifetime_process",
            return_value=([], [], None),
        ) as delegate:
            self.assertEqual(
                subject._coherent_mutation_snapshot_process(
                    "o/r", "t", [], 3, pending.SchedulerStateV4(0)
                ),
                ([], [], None),
            )
        delegate.assert_called_once()

    def test_full_processor_rechecks_gate_around_current_pr_and_threads_before_post(self) -> None:
        current, latest, target, _pending_state = self._fixture()
        writer = mock.Mock()
        rerun = mock.Mock()
        with (
            mock.patch.object(
                pending.core,
                "latest_required_check",
                side_effect=[latest, latest, latest, latest],
            ) as gate_read,
            mock.patch.object(
                pending.core,
                "unresolved_review_threads",
                return_value=True,
            ) as threads,
            mock.patch.object(
                pending.previous,
                "_direct_target_for_pr",
                return_value=(target, None),
            ),
            mock.patch.object(pending.base, "_current_pr", return_value=current),
            mock.patch.object(
                pending.previous,
                "_mutation_baseline",
                return_value=1,
            ),
            mock.patch.object(pending, "_current_pending_pr", return_value=current) as pr_read,
            mock.patch.object(pending, "_write_state", writer),
            mock.patch.object(pending.core, "rerun_workflow", rerun),
            mock.patch.object(
                pending.previous,
                "_wait_for_terminal_invalidation",
                return_value=True,
            ),
        ):
            self.assertEqual(
                subject._coherent_mutation_snapshot_process(
                    "o/r",
                    "t",
                    [current],
                    3,
                    pending.SchedulerStateV4(0),
                ),
                ([101], [], None),
            )
        self.assertEqual(gate_read.call_count, 4)
        pr_read.assert_called_once()
        self.assertGreaterEqual(threads.call_count, 4)
        self.assertEqual(writer.call_count, 2)
        rerun.assert_called_once_with("o/r", 101, "t")

    def test_install_main_and_entrypoint(self) -> None:
        with mock.patch.object(previous, "install") as install:
            subject.install()
        install.assert_called_once()
        self.assertIs(
            pending._process_head_group,
            subject._coherent_mutation_snapshot_process,
        )

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
            mock.patch.dict(
                os.environ,
                {"BOOTSTRAP_RECOVERY_ACTION": subject.RECOVERY_ACTION},
                clear=True,
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "GITHUB_REPOSITORY and GITHUB_TOKEN",
            ):
                subject.main()

        env = {
            "BOOTSTRAP_RECOVERY_ACTION": subject.RECOVERY_ACTION,
            "GITHUB_REPOSITORY": "o/r",
            "GITHUB_TOKEN": "t",
        }
        with (
            mock.patch.object(subject, "install"),
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch.object(
                recovery,
                "_inspect_confirmed_unposted",
                return_value=0,
            ) as inspect,
        ):
            self.assertEqual(subject.main(), 0)
        inspect.assert_called_once_with("o/r", "t")

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
