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
import stale_green_bootstrap_authority_review0064 as previous
import stale_green_bootstrap_authority_review0065 as subject


class Review0065MutationBoundAuthorityTests(unittest.TestCase):
    def setUp(self) -> None:
        base._reset_request_budget()
        self.addCleanup(base._reset_request_budget)

    def tearDown(self) -> None:
        pending._process_head_group = lifetime._pending_lifetime_process

    def _process_fixture(self):
        current = pr(1, branch="shared", head="a" * 40)
        latest = check(601, 201)
        target = (gate_run(101, 1), check(501, 101))
        return current, latest, target

    def test_different_newer_gate_before_pending_write_fails_closed(self) -> None:
        current, latest, target = self._process_fixture()
        advanced = check(602, 202)
        writer = mock.Mock()
        rerun = mock.Mock()
        with (
            mock.patch.object(
                pending.core,
                "latest_required_check",
                side_effect=[latest, latest, advanced],
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
            mock.patch.object(
                pending.previous,
                "_mutation_baseline",
                return_value=1,
            ),
            mock.patch.object(pending, "_write_state", writer),
            mock.patch.object(pending.core, "rerun_workflow", rerun),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "authority advanced before mutation boundary",
            ):
                subject._mutation_bound_authority_process(
                    "o/r",
                    "t",
                    [current],
                    3,
                    pending.SchedulerStateV4(0),
                )
        writer.assert_not_called()
        rerun.assert_not_called()

    def test_same_exact_gate_is_reproved_before_pending_write_and_post(self) -> None:
        current, latest, target = self._process_fixture()
        writer = mock.Mock()
        rerun = mock.Mock()
        with (
            mock.patch.object(
                pending.core,
                "latest_required_check",
                side_effect=[latest, latest, latest],
            ) as latest_read,
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
            mock.patch.object(
                pending.previous,
                "_mutation_baseline",
                return_value=1,
            ),
            mock.patch.object(pending, "_write_state", writer),
            mock.patch.object(pending.core, "rerun_workflow", rerun),
            mock.patch.object(
                pending.previous,
                "_wait_for_terminal_invalidation",
                return_value=True,
            ),
        ):
            self.assertEqual(
                subject._mutation_bound_authority_process(
                    "o/r",
                    "t",
                    [current],
                    3,
                    pending.SchedulerStateV4(0),
                ),
                ([101], [], None),
            )
        self.assertEqual(latest_read.call_count, 3)
        self.assertEqual(writer.call_count, 2)
        self.assertNotEqual(writer.call_args_list[0].args[2].pending_pr, 0)
        self.assertEqual(writer.call_args_list[1].args[2].pending_pr, 0)
        rerun.assert_called_once_with("o/r", 101, "t")

    def test_final_nonacceptable_or_missing_gate_writes_nothing(self) -> None:
        current, latest, _target = self._process_fixture()
        pending_state = pending._pending_state(
            pending.SchedulerStateV4(0),
            current,
            101,
            1,
            latest["id"],
        )
        for final in (None, {**latest, "conclusion": "failure"}):
            writer = mock.Mock()
            with (
                mock.patch.object(pending, "_write_state", writer),
                mock.patch.object(
                    lifetime,
                    "_pending_lifetime_process",
                ) as process,
                mock.patch.object(core, "latest_required_check", return_value=final),
            ):
                def invoke(*_args, **_kwargs):
                    pending._write_state("o/r", "t", pending_state)

                process.side_effect = invoke
                with self.assertRaisesRegex(
                    RuntimeError,
                    "no longer merge-acceptable",
                ):
                    subject._mutation_bound_authority_process(
                        "o/r",
                        "t",
                        [current],
                        3,
                        pending.SchedulerStateV4(0),
                    )
            writer.assert_not_called()

    def test_invalid_pending_check_identity_fails_before_reproof(self) -> None:
        current, _latest, _target = self._process_fixture()
        malformed = pending.SchedulerStateV4(
            0,
            1,
            1,
            "-",
            1,
            "b" * 64,
            101,
            1,
            0,
        )
        writer = mock.Mock()
        latest_read = mock.Mock()
        with (
            mock.patch.object(pending, "_write_state", writer),
            mock.patch.object(lifetime, "_pending_lifetime_process") as process,
            mock.patch.object(core, "latest_required_check", latest_read),
        ):
            def invoke(*_args, **_kwargs):
                pending._write_state("o/r", "t", malformed)

            process.side_effect = invoke
            with self.assertRaisesRegex(
                RuntimeError,
                "lacks exact prior required-check identity",
            ):
                subject._mutation_bound_authority_process(
                    "o/r",
                    "t",
                    [current],
                    3,
                    pending.SchedulerStateV4(0),
                )
        latest_read.assert_not_called()
        writer.assert_not_called()

    def test_final_proof_preserves_full_mutation_reserve_before_write(self) -> None:
        current, latest, _target = self._process_fixture()
        pending_state = pending._pending_state(
            pending.SchedulerStateV4(0),
            current,
            101,
            1,
            latest["id"],
        )
        writer = mock.Mock()
        with (
            mock.patch.object(pending, "_write_state", writer),
            mock.patch.object(lifetime, "_pending_lifetime_process") as process,
            mock.patch.object(core, "latest_required_check", return_value=latest),
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
                "after final mutation-bound Gate authority proof",
            ):
                subject._mutation_bound_authority_process(
                    "o/r",
                    "t",
                    [current],
                    3,
                    pending.SchedulerStateV4(0),
                )
        writer.assert_not_called()

    def test_actual_pending_write_ack_ambiguity_remains_uncertain(self) -> None:
        current, latest, _target = self._process_fixture()
        pending_state = pending._pending_state(
            pending.SchedulerStateV4(0),
            current,
            101,
            1,
            latest["id"],
        )
        writer = mock.Mock(side_effect=RuntimeError("ack lost"))
        with (
            mock.patch.object(pending, "_write_state", writer),
            mock.patch.object(lifetime, "_pending_lifetime_process") as process,
            mock.patch.object(core, "latest_required_check", return_value=latest),
            mock.patch.object(
                base,
                "_remaining_request_budget",
                return_value=pending.MUTATION_REQUEST_RESERVE,
            ),
        ):
            def invoke(*_args, **_kwargs):
                pending._write_state("o/r", "t", pending_state)

            process.side_effect = invoke
            with self.assertRaisesRegex(
                pending.PendingMutationUncertain,
                "acknowledgement is ambiguous",
            ) as raised:
                subject._mutation_bound_authority_process(
                    "o/r",
                    "t",
                    [current],
                    3,
                    pending.SchedulerStateV4(0),
                )
        self.assertIsInstance(raised.exception.__cause__, RuntimeError)
        writer.assert_called_once()

    def test_existing_pending_exception_and_nonpending_writes_are_preserved(self) -> None:
        current, latest, _target = self._process_fixture()
        pending_state = pending._pending_state(
            pending.SchedulerStateV4(0),
            current,
            101,
            1,
            latest["id"],
        )
        existing = pending.PendingMutationUncertain("already uncertain")
        with (
            mock.patch.object(pending, "_write_state", side_effect=existing),
            mock.patch.object(lifetime, "_pending_lifetime_process") as process,
            mock.patch.object(core, "latest_required_check", return_value=latest),
            mock.patch.object(
                base,
                "_remaining_request_budget",
                return_value=pending.MUTATION_REQUEST_RESERVE,
            ),
        ):
            def invoke_pending(*_args, **_kwargs):
                pending._write_state("o/r", "t", pending_state)

            process.side_effect = invoke_pending
            with self.assertRaises(pending.PendingMutationUncertain) as raised:
                subject._mutation_bound_authority_process(
                    "o/r",
                    "t",
                    [current],
                    3,
                    pending.SchedulerStateV4(0),
                )
        self.assertIs(raised.exception, existing)

        idle = pending.SchedulerStateV4(1)
        writer = mock.Mock()
        latest_read = mock.Mock()
        with (
            mock.patch.object(pending, "_write_state", writer),
            mock.patch.object(lifetime, "_pending_lifetime_process") as process,
            mock.patch.object(core, "latest_required_check", latest_read),
        ):
            def invoke_idle(*_args, **_kwargs):
                pending._write_state("o/r", "t", idle)
                return ([], [], None)

            process.side_effect = invoke_idle
            self.assertEqual(
                subject._mutation_bound_authority_process(
                    "o/r", "t", [current], 3, idle
                ),
                ([], [], None),
            )
        latest_read.assert_not_called()
        writer.assert_called_once_with("o/r", "t", idle)

    def test_empty_group_delegates_without_installing_write_guard(self) -> None:
        state = pending.SchedulerStateV4(0)
        with mock.patch.object(
            lifetime,
            "_pending_lifetime_process",
            return_value=([], [], None),
        ) as process:
            self.assertEqual(
                subject._mutation_bound_authority_process(
                    "o/r", "t", [], 3, state
                ),
                ([], [], None),
            )
        process.assert_called_once()

    def test_install_main_and_entrypoint(self) -> None:
        with mock.patch.object(previous, "install") as install:
            subject.install()
        install.assert_called_once()
        self.assertIs(
            pending._process_head_group,
            subject._mutation_bound_authority_process,
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
