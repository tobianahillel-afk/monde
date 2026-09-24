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
import stale_green_bootstrap_authority_review0066 as previous
import stale_green_bootstrap_authority_review0067 as subject


class Review0067StablePrGateSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        base._reset_request_budget()
        self.addCleanup(base._reset_request_budget)

    def tearDown(self) -> None:
        pending._process_head_group = lifetime._pending_lifetime_process

    def fixture(self):
        current = pr(1, branch="shared", head="a" * 40)
        latest = check(601, 201)
        target = (gate_run(101, 1), check(501, 101))
        state = pending._pending_state(
            pending.SchedulerStateV4(0), current, 101, 1, latest["id"]
        )
        return current, latest, target, state

    def invoke_guard(
        self,
        current,
        latest,
        state,
        *,
        pr_reads=None,
        unresolved=True,
        remaining=None,
        writer=None,
        gates=None,
    ):
        writer = writer or mock.Mock()
        pr_reads = pr_reads if pr_reads is not None else [current, current]
        gates = gates if gates is not None else [latest, latest]
        with (
            mock.patch.object(pending, "_write_state", writer),
            mock.patch.object(lifetime, "_pending_lifetime_process") as process,
            mock.patch.object(previous, "_require_expected_gate", side_effect=gates) as gate_read,
            mock.patch.object(pending, "_current_pending_pr", side_effect=pr_reads) as pr_read,
            mock.patch.object(core, "unresolved_review_threads", return_value=unresolved) as threads,
            mock.patch.object(
                base,
                "_remaining_request_budget",
                return_value=(
                    pending.MUTATION_REQUEST_RESERVE
                    if remaining is None
                    else remaining
                ),
            ),
        ):
            def invoke(*_args, **_kwargs):
                pending._write_state("o/r", "t", state)

            process.side_effect = invoke
            result = subject._stable_pr_gate_snapshot_process(
                "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
            )
        return result, writer, gate_read, pr_read, threads

    def test_g1_p1_threads_p2_g2_success(self) -> None:
        current, latest, _target, state = self.fixture()
        result, writer, gates, prs, threads = self.invoke_guard(
            current, latest, state
        )
        self.assertIsNone(result)
        self.assertEqual(gates.call_count, 2)
        self.assertEqual(prs.call_count, 2)
        threads.assert_called_once_with("o/r", 1, "t")
        writer.assert_called_once_with("o/r", "t", state)

    def test_p1_closed_fails_before_threads_or_p2(self) -> None:
        current, latest, _target, state = self.fixture()
        writer = mock.Mock()
        with (
            mock.patch.object(pending, "_write_state", writer),
            mock.patch.object(lifetime, "_pending_lifetime_process") as process,
            mock.patch.object(previous, "_require_expected_gate", return_value=latest) as gates,
            mock.patch.object(pending, "_current_pending_pr", return_value=None) as prs,
            mock.patch.object(core, "unresolved_review_threads") as threads,
        ):
            process.side_effect = lambda *_a, **_k: pending._write_state("o/r", "t", state)
            with self.assertRaisesRegex(RuntimeError, "closed at mutation snapshot P1"):
                subject._stable_pr_gate_snapshot_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                )
        gates.assert_called_once()
        prs.assert_called_once()
        threads.assert_not_called()
        writer.assert_not_called()

    def test_threads_resolved_fails_between_pr_reads(self) -> None:
        current, latest, _target, state = self.fixture()
        writer = mock.Mock()
        with (
            mock.patch.object(pending, "_write_state", writer),
            mock.patch.object(lifetime, "_pending_lifetime_process") as process,
            mock.patch.object(previous, "_require_expected_gate", return_value=latest),
            mock.patch.object(pending, "_current_pending_pr", return_value=current) as prs,
            mock.patch.object(core, "unresolved_review_threads", return_value=False),
        ):
            process.side_effect = lambda *_a, **_k: pending._write_state("o/r", "t", state)
            with self.assertRaisesRegex(RuntimeError, "review-thread authority resolved"):
                subject._stable_pr_gate_snapshot_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                )
        prs.assert_called_once()
        writer.assert_not_called()

    def test_p2_closed_or_authority_drift_fails_before_g2(self) -> None:
        current, latest, _target, state = self.fixture()
        for second, pattern in (
            (None, "closed at mutation snapshot P2"),
            (
                RuntimeError(
                    "pending pull-request authority changed before mutation observation completed"
                ),
                "authority changed",
            ),
        ):
            writer = mock.Mock()
            reads = [current, second]
            if isinstance(second, Exception):
                pr_side_effect = [current, second]
            else:
                pr_side_effect = reads
            with (
                mock.patch.object(pending, "_write_state", writer),
                mock.patch.object(lifetime, "_pending_lifetime_process") as process,
                mock.patch.object(previous, "_require_expected_gate", return_value=latest) as gates,
                mock.patch.object(pending, "_current_pending_pr", side_effect=pr_side_effect),
                mock.patch.object(core, "unresolved_review_threads", return_value=True),
            ):
                process.side_effect = lambda *_a, **_k: pending._write_state("o/r", "t", state)
                with self.assertRaisesRegex(RuntimeError, pattern):
                    subject._stable_pr_gate_snapshot_process(
                        "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                    )
            self.assertEqual(gates.call_count, 1)
            writer.assert_not_called()

    def test_g1_and_g2_failures_write_nothing(self) -> None:
        current, latest, _target, state = self.fixture()
        for gates, expected_pr_reads, pattern in (
            ([RuntimeError("G1 failed")], 0, "G1 failed"),
            ([latest, RuntimeError("G2 failed")], 2, "G2 failed"),
        ):
            writer = mock.Mock()
            with (
                mock.patch.object(pending, "_write_state", writer),
                mock.patch.object(lifetime, "_pending_lifetime_process") as process,
                mock.patch.object(previous, "_require_expected_gate", side_effect=gates),
                mock.patch.object(
                    pending, "_current_pending_pr", side_effect=[current, current]
                ) as prs,
                mock.patch.object(core, "unresolved_review_threads", return_value=True),
            ):
                process.side_effect = lambda *_a, **_k: pending._write_state("o/r", "t", state)
                with self.assertRaisesRegex(RuntimeError, pattern):
                    subject._stable_pr_gate_snapshot_process(
                        "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                    )
            self.assertEqual(prs.call_count, expected_pr_reads)
            writer.assert_not_called()

    def test_invalid_pending_check_identity_short_circuits(self) -> None:
        current, _latest, _target, _state = self.fixture()
        malformed = pending.SchedulerStateV4(
            0, 1, 1, "-", 1, "b" * 64, 101, 1, 0
        )
        writer = mock.Mock()
        with (
            mock.patch.object(pending, "_write_state", writer),
            mock.patch.object(lifetime, "_pending_lifetime_process") as process,
            mock.patch.object(previous, "_require_expected_gate") as gates,
        ):
            process.side_effect = lambda *_a, **_k: pending._write_state(
                "o/r", "t", malformed
            )
            with self.assertRaisesRegex(
                RuntimeError, "lacks exact prior required-check identity"
            ):
                subject._stable_pr_gate_snapshot_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                )
        gates.assert_not_called()
        writer.assert_not_called()

    def test_post_g2_reserve_exhaustion_writes_nothing(self) -> None:
        current, latest, _target, state = self.fixture()
        writer = mock.Mock()
        with (
            mock.patch.object(pending, "_write_state", writer),
            mock.patch.object(lifetime, "_pending_lifetime_process") as process,
            mock.patch.object(
                previous, "_require_expected_gate", side_effect=[latest, latest]
            ),
            mock.patch.object(
                pending, "_current_pending_pr", side_effect=[current, current]
            ),
            mock.patch.object(core, "unresolved_review_threads", return_value=True),
            mock.patch.object(
                base,
                "_remaining_request_budget",
                return_value=pending.MUTATION_REQUEST_RESERVE - 1,
            ),
        ):
            process.side_effect = lambda *_a, **_k: pending._write_state("o/r", "t", state)
            with self.assertRaisesRegex(
                base.DeferredForBudget,
                "after stable PR/Gate mutation snapshot",
            ):
                subject._stable_pr_gate_snapshot_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                )
        writer.assert_not_called()

    def test_actual_write_ack_ambiguity_and_existing_pending_exception(self) -> None:
        current, latest, _target, state = self.fixture()
        for exc, same in (
            (RuntimeError("ack lost"), False),
            (pending.PendingMutationUncertain("already uncertain"), True),
        ):
            writer = mock.Mock(side_effect=exc)
            with (
                mock.patch.object(pending, "_write_state", writer),
                mock.patch.object(lifetime, "_pending_lifetime_process") as process,
                mock.patch.object(
                    previous, "_require_expected_gate", side_effect=[latest, latest]
                ),
                mock.patch.object(
                    pending, "_current_pending_pr", side_effect=[current, current]
                ),
                mock.patch.object(core, "unresolved_review_threads", return_value=True),
                mock.patch.object(
                    base,
                    "_remaining_request_budget",
                    return_value=pending.MUTATION_REQUEST_RESERVE,
                ),
            ):
                process.side_effect = lambda *_a, **_k: pending._write_state(
                    "o/r", "t", state
                )
                with self.assertRaises(pending.PendingMutationUncertain) as raised:
                    subject._stable_pr_gate_snapshot_process(
                        "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                    )
            if same:
                self.assertIs(raised.exception, exc)
            else:
                self.assertIsInstance(raised.exception.__cause__, RuntimeError)

    def test_nonpending_write_is_transparent(self) -> None:
        current, _latest, _target, _state = self.fixture()
        idle = pending.SchedulerStateV4(1)
        writer = mock.Mock()
        with (
            mock.patch.object(pending, "_write_state", writer),
            mock.patch.object(lifetime, "_pending_lifetime_process") as process,
            mock.patch.object(previous, "_require_expected_gate") as gates,
        ):
            def invoke(*_a, **_k):
                pending._write_state("o/r", "t", idle)
                return ([], [], None)

            process.side_effect = invoke
            self.assertEqual(
                subject._stable_pr_gate_snapshot_process(
                    "o/r", "t", [current], 3, idle
                ),
                ([], [], None),
            )
        gates.assert_not_called()
        writer.assert_called_once_with("o/r", "t", idle)

    def test_empty_group_delegates(self) -> None:
        state = pending.SchedulerStateV4(0)
        with mock.patch.object(
            lifetime,
            "_pending_lifetime_process",
            return_value=([], [], None),
        ) as delegate:
            self.assertEqual(
                subject._stable_pr_gate_snapshot_process(
                    "o/r", "t", [], 3, state
                ),
                ([], [], None),
            )
        delegate.assert_called_once()

    def test_full_processor_revalidates_p1_and_p2_before_post(self) -> None:
        current, latest, target, _state = self.fixture()
        writer = mock.Mock()
        rerun = mock.Mock()
        with (
            mock.patch.object(
                pending.core,
                "latest_required_check",
                side_effect=[latest, latest, latest, latest],
            ),
            mock.patch.object(
                pending.core,
                "unresolved_review_threads",
                return_value=True,
            ),
            mock.patch.object(
                pending.previous,
                "_direct_target_for_pr",
                return_value=(target, None),
            ),
            mock.patch.object(pending.base, "_current_pr", return_value=current),
            mock.patch.object(pending.previous, "_mutation_baseline", return_value=1),
            mock.patch.object(
                pending, "_current_pending_pr", side_effect=[current, current]
            ) as prs,
            mock.patch.object(pending, "_write_state", writer),
            mock.patch.object(pending.core, "rerun_workflow", rerun),
            mock.patch.object(
                pending.previous,
                "_wait_for_terminal_invalidation",
                return_value=True,
            ),
        ):
            self.assertEqual(
                subject._stable_pr_gate_snapshot_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                ),
                ([101], [], None),
            )
        self.assertEqual(prs.call_count, 2)
        self.assertEqual(writer.call_count, 2)
        rerun.assert_called_once_with("o/r", 101, "t")

    def test_install_main_and_entrypoint(self) -> None:
        with mock.patch.object(previous, "install") as install:
            subject.install()
        install.assert_called_once()
        self.assertIs(
            pending._process_head_group,
            subject._stable_pr_gate_snapshot_process,
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
            mock.patch.dict(
                os.environ,
                {"BOOTSTRAP_RECOVERY_ACTION": "bad"},
                clear=True,
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "unsupported bootstrap recovery action"
            ):
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
                RuntimeError, "GITHUB_REPOSITORY and GITHUB_TOKEN"
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
