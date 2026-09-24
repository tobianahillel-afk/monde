from __future__ import annotations

import os
import runpy
import unittest
from unittest import mock

from test_stale_green_bootstrap_authority_review0070 import guard_pr
from test_stale_green_bootstrap_authority_review0071 import page_pr

import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0049 as pending
import stale_green_bootstrap_authority_review0051_recovery as recovery
import stale_green_bootstrap_authority_review0070 as guardbase
import stale_green_bootstrap_authority_review0071 as discovery
import stale_green_bootstrap_authority_review0073 as previous
import stale_green_bootstrap_authority_review0074 as subject


class Review0074Tests(unittest.TestCase):
    def setUp(self) -> None:
        base._reset_request_budget()
        self.saved = (
            core.request_data,
            base.poll,
            core.poll,
            base.validate_github_contract,
            core.validate_github_contract,
        )

    def tearDown(self) -> None:
        (
            core.request_data,
            base.poll,
            core.poll,
            base.validate_github_contract,
            core.validate_github_contract,
        ) = self.saved
        base._reset_request_budget()

    def test_identity_seed_uses_strict_open_guard(self) -> None:
        current = guard_pr(5, draft=False)
        self.assertEqual(
            subject._identity_seed(current),
            {"number": 5, "node_id": "PR_node_5"},
        )
        malformed = dict(current)
        malformed["number"] = True
        with self.assertRaisesRegex(RuntimeError, "malformed draft-guard"):
            subject._identity_seed(malformed)

    def test_strict_guard_skips_existing_draft(self) -> None:
        drafted = guard_pr(5, draft=True)
        with mock.patch.object(guardbase, "_thread_state") as threads:
            self.assertFalse(subject._strict_guard_one("o/r", "t", drafted))
        threads.assert_not_called()

    def test_strict_guard_rejects_malformed_first_internal_reread(self) -> None:
        ready = guard_pr(5, draft=False)
        with (
            mock.patch.object(guardbase, "_thread_state", return_value="RESOLVED"),
            mock.patch.object(
                previous,
                "_strict_discovered_pr",
                side_effect=RuntimeError("malformed direct pull request #5"),
            ),
            mock.patch.object(discovery, "_convert_to_draft") as convert,
        ):
            with self.assertRaisesRegex(RuntimeError, "malformed direct"):
                subject._strict_guard_one("o/r", "t", ready)
        convert.assert_not_called()

    def test_strict_guard_rejects_malformed_second_internal_reread(self) -> None:
        ready = guard_pr(5, draft=False)
        with (
            mock.patch.object(
                guardbase,
                "_thread_state",
                side_effect=["RESOLVED", "UNRESOLVED"],
            ),
            mock.patch.object(
                previous,
                "_strict_discovered_pr",
                side_effect=[ready, RuntimeError("malformed direct pull request #5")],
            ),
            mock.patch.object(discovery, "_convert_to_draft") as convert,
        ):
            with self.assertRaisesRegex(RuntimeError, "malformed direct"):
                subject._strict_guard_one("o/r", "t", ready)
        convert.assert_not_called()

    def test_strict_guard_closed_draft_and_resolved_paths(self) -> None:
        ready = guard_pr(5, draft=False)
        drafted = guard_pr(5, draft=True)

        with (
            mock.patch.object(guardbase, "_thread_state", return_value="UNRESOLVED"),
            mock.patch.object(previous, "_strict_discovered_pr", return_value=None),
        ):
            self.assertFalse(subject._strict_guard_one("o/r", "t", ready))

        with (
            mock.patch.object(guardbase, "_thread_state", return_value="UNRESOLVED"),
            mock.patch.object(previous, "_strict_discovered_pr", return_value=drafted),
        ):
            self.assertFalse(subject._strict_guard_one("o/r", "t", ready))

        with (
            mock.patch.object(
                guardbase,
                "_thread_state",
                side_effect=["UNRESOLVED", "RESOLVED"],
            ),
            mock.patch.object(previous, "_strict_discovered_pr", return_value=ready),
            mock.patch.object(discovery, "_convert_to_draft") as convert,
        ):
            self.assertFalse(subject._strict_guard_one("o/r", "t", ready))
        convert.assert_not_called()

        with (
            mock.patch.object(
                guardbase,
                "_thread_state",
                side_effect=["RESOLVED", "UNRESOLVED"],
            ),
            mock.patch.object(
                previous,
                "_strict_discovered_pr",
                side_effect=[ready, None],
            ),
        ):
            self.assertFalse(subject._strict_guard_one("o/r", "t", ready))

        with (
            mock.patch.object(
                guardbase,
                "_thread_state",
                side_effect=["RESOLVED", "AMBIGUOUS"],
            ),
            mock.patch.object(
                previous,
                "_strict_discovered_pr",
                side_effect=[ready, drafted],
            ),
        ):
            self.assertFalse(subject._strict_guard_one("o/r", "t", ready))

    def test_strict_guard_resolved_then_unresolved_drafts(self) -> None:
        ready = guard_pr(5, draft=False)
        with (
            mock.patch.object(
                guardbase,
                "_thread_state",
                side_effect=["RESOLVED", "UNRESOLVED"],
            ) as threads,
            mock.patch.object(
                previous,
                "_strict_discovered_pr",
                side_effect=[ready, ready],
            ) as direct,
            mock.patch.object(discovery, "_convert_to_draft") as convert,
        ):
            self.assertTrue(subject._strict_guard_one("o/r", "t", ready))
        self.assertEqual(threads.call_count, 2)
        self.assertEqual(direct.call_count, 2)
        expected = {"number": 5, "node_id": "PR_node_5"}
        self.assertEqual(direct.call_args_list[0].args, ("o/r", "t", expected))
        self.assertEqual(direct.call_args_list[1].args, ("o/r", "t", expected))
        convert.assert_called_once_with("o/r", "t", ready)

    def test_poll_pending_empty_budget_and_progress(self) -> None:
        legacy = pending.SchedulerStateV4(
            cursor_pr=1,
            scan_pr=2,
            pending_pr=2,
            pending_authority="a" * 64,
            pending_run_id=10,
            pending_baseline_attempt=1,
            pending_check_id=20,
        )
        with (
            mock.patch.object(pending, "_read_state", return_value=legacy),
            mock.patch.object(pending, "_resume_pending", return_value=[10]) as resume,
            mock.patch.object(discovery, "_read_discovery_page") as read,
        ):
            self.assertEqual(subject._draft_guard_poll("o/r", "t"), [10])
        resume.assert_called_once_with("o/r", "t", legacy)
        read.assert_not_called()

        active = pending.SchedulerStateV4(2000, 2000, 21, "-")
        with (
            mock.patch.object(pending, "_read_state", return_value=active),
            mock.patch.object(discovery, "_read_discovery_page", return_value=[]),
            mock.patch.object(pending, "_write_state") as write,
        ):
            self.assertEqual(subject._draft_guard_poll("o/r", "t"), [])
        write.assert_called_once_with("o/r", "t", pending.SchedulerStateV4(2000))

        idle = pending.SchedulerStateV4(0)
        with (
            mock.patch.object(pending, "_read_state", return_value=idle),
            mock.patch.object(discovery, "_read_discovery_page", return_value=[]),
            mock.patch.object(pending, "_write_state") as write,
        ):
            subject._draft_guard_poll("o/r", "t")
        write.assert_not_called()

        page = [page_pr(1, draft=False)]
        with (
            mock.patch.object(pending, "_read_state", return_value=idle),
            mock.patch.object(discovery, "_read_discovery_page", return_value=page),
            mock.patch.object(
                base,
                "_remaining_request_budget",
                return_value=subject.DRAFT_GUARD_REQUEST_RESERVE + 2,
            ),
            mock.patch.object(previous, "_strict_discovered_pr") as direct,
            mock.patch.object(pending, "_write_state") as write,
        ):
            self.assertEqual(subject._draft_guard_poll("o/r", "t"), [])
        direct.assert_not_called()
        write.assert_not_called()

    def test_poll_uses_local_strict_guard_and_advances(self) -> None:
        state = pending.SchedulerStateV4(0)
        page = [page_pr(1, draft=True)]
        ready = guard_pr(1, draft=False)
        writes: list[pending.SchedulerStateV4] = []
        with (
            mock.patch.object(pending, "_read_state", return_value=state),
            mock.patch.object(discovery, "_read_discovery_page", return_value=page),
            mock.patch.object(base, "_remaining_request_budget", return_value=100),
            mock.patch.object(previous, "_strict_discovered_pr", return_value=ready),
            mock.patch.object(subject, "_strict_guard_one", return_value=True) as guard,
            mock.patch.object(
                pending,
                "_write_state",
                side_effect=lambda _r, _t, st: writes.append(st),
            ),
        ):
            self.assertEqual(subject._draft_guard_poll("o/r", "t"), [1])
        guard.assert_called_once_with("o/r", "t", ready)
        self.assertEqual(writes[-1], pending.SchedulerStateV4(1))

    def test_poll_current_closed_draft_false_guard_and_max_bound(self) -> None:
        state = pending.SchedulerStateV4(0)
        page = [page_pr(i, draft=True) for i in range(1, 41)]

        writes: list[pending.SchedulerStateV4] = []
        with (
            mock.patch.object(pending, "_read_state", return_value=state),
            mock.patch.object(discovery, "_read_discovery_page", return_value=page),
            mock.patch.object(base, "_remaining_request_budget", return_value=100),
            mock.patch.object(previous, "_strict_discovered_pr", return_value=None) as direct,
            mock.patch.object(subject, "_strict_guard_one") as guard,
            mock.patch.object(
                pending,
                "_write_state",
                side_effect=lambda _r, _t, st: writes.append(st),
            ),
        ):
            subject._draft_guard_poll("o/r", "t")
        self.assertEqual(direct.call_count, subject.MAX_GUARD_PRS_PER_INVOCATION)
        guard.assert_not_called()
        self.assertEqual(writes[-1].scan_pr, 32)

        drafted = guard_pr(1, draft=True)
        with (
            mock.patch.object(pending, "_read_state", return_value=state),
            mock.patch.object(discovery, "_read_discovery_page", return_value=[page_pr(1)]),
            mock.patch.object(base, "_remaining_request_budget", return_value=100),
            mock.patch.object(previous, "_strict_discovered_pr", return_value=drafted),
            mock.patch.object(subject, "_strict_guard_one") as guard,
            mock.patch.object(pending, "_write_state"),
        ):
            subject._draft_guard_poll("o/r", "t")
        guard.assert_not_called()

        ready = guard_pr(1, draft=False)
        with (
            mock.patch.object(pending, "_read_state", return_value=state),
            mock.patch.object(discovery, "_read_discovery_page", return_value=[page_pr(1)]),
            mock.patch.object(base, "_remaining_request_budget", return_value=100),
            mock.patch.object(previous, "_strict_discovered_pr", return_value=ready),
            mock.patch.object(subject, "_strict_guard_one", return_value=False) as guard,
            mock.patch.object(pending, "_write_state"),
        ):
            self.assertEqual(subject._draft_guard_poll("o/r", "t"), [])
        guard.assert_called_once()

    def test_poll_full_page_and_same_state_no_write(self) -> None:
        full = [page_pr(i, draft=True) for i in range(1, 101)]
        membership = discovery._page_membership(full)
        state = pending.SchedulerStateV4(
            99,
            99,
            1,
            discovery._prefix_digest(membership, 99),
        )
        writes: list[pending.SchedulerStateV4] = []
        with (
            mock.patch.object(pending, "_read_state", return_value=state),
            mock.patch.object(discovery, "_read_discovery_page", return_value=full),
            mock.patch.object(base, "_remaining_request_budget", return_value=100),
            mock.patch.object(previous, "_strict_discovered_pr", return_value=None),
            mock.patch.object(
                pending,
                "_write_state",
                side_effect=lambda _r, _t, st: writes.append(st),
            ),
        ):
            subject._draft_guard_poll("o/r", "t")
        self.assertEqual(writes[-1], pending.SchedulerStateV4(100, 100, 2, "-"))

        state = pending.SchedulerStateV4(7)
        page = [page_pr(8, draft=True)]
        with (
            mock.patch.object(pending, "_read_state", return_value=state),
            mock.patch.object(discovery, "_read_discovery_page", return_value=page),
            mock.patch.object(base, "_remaining_request_budget", return_value=100),
            mock.patch.object(previous, "_strict_discovered_pr", return_value=None),
            mock.patch.object(discovery, "_next_discovery_state", return_value=state),
            mock.patch.object(pending, "_write_state") as write,
        ):
            subject._draft_guard_poll("o/r", "t")
        write.assert_not_called()

    def test_strict_target_pr_and_live_validator(self) -> None:
        for bad in (True, 0, -1, 1.0):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(RuntimeError, "target pull-request number"):
                    subject._strict_target_pr("o/r", bad, "t")

        with mock.patch.object(core, "request_data", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "malformed target"):
                subject._strict_target_pr("o/r", 2, "t")

        seed = guard_pr(2, draft=False)
        wrong = guard_pr(3, draft=False)
        wrong["number"] = 3
        with mock.patch.object(core, "request_data", return_value=wrong):
            with self.assertRaisesRegex(RuntimeError, "malformed target"):
                subject._strict_target_pr("o/r", 2, "t")

        with (
            mock.patch.object(core, "request_data", return_value=seed),
            mock.patch.object(previous, "_strict_discovered_pr", return_value=None),
        ):
            with self.assertRaisesRegex(RuntimeError, "expected open PR"):
                subject._strict_target_pr("o/r", 2, "t")

        current = guard_pr(2, draft=False)
        with (
            mock.patch.object(core, "request_data", return_value=seed),
            mock.patch.object(previous, "_strict_discovered_pr", return_value=current) as strict,
        ):
            self.assertEqual(subject._strict_target_pr("o/r", 2, "t"), current)
        strict.assert_called_once_with(
            "o/r",
            "t",
            {"number": 2, "node_id": "PR_node_2"},
        )

        with (
            mock.patch.object(subject, "_strict_target_pr", return_value=current),
            mock.patch.object(guardbase, "_thread_state", return_value="UNRESOLVED"),
        ):
            self.assertEqual(
                subject._validate_guard_contract("o/r", 2, "t"),
                (1, 1, True),
            )

        drafted = guard_pr(2, draft=True)
        with (
            mock.patch.object(subject, "_strict_target_pr", return_value=drafted),
            mock.patch.object(guardbase, "_thread_state", return_value="UNRESOLVED"),
        ):
            self.assertEqual(
                subject._validate_guard_contract("o/r", 2, "t"),
                (1, 1, False),
            )

        with (
            mock.patch.object(subject, "_strict_target_pr", return_value=current),
            mock.patch.object(guardbase, "_thread_state", return_value="RESOLVED"),
        ):
            self.assertEqual(
                subject._validate_guard_contract("o/r", 2, "t"),
                (1, 1, False),
            )

    def test_install_main_and_entrypoint(self) -> None:
        with mock.patch.object(previous, "install") as install:
            subject.install()
        install.assert_called_once()
        self.assertIs(base.poll, subject._draft_guard_poll)
        self.assertIs(core.poll, subject._draft_guard_poll)
        self.assertIs(base.validate_github_contract, subject._validate_guard_contract)
        self.assertIs(core.validate_github_contract, subject._validate_guard_contract)

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
            mock.patch.object(
                recovery,
                "_inspect_confirmed_unposted",
                return_value=0,
            ) as inspect,
        ):
            self.assertEqual(subject.main(), 0)
        inspect.assert_called_once_with("o/r", "t")

        with (
            mock.patch.object(previous, "install"),
            mock.patch.object(base, "main", return_value=0),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            with self.assertRaises(SystemExit) as raised:
                runpy.run_path(subject.__file__, run_name="__main__")
        self.assertEqual(raised.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
