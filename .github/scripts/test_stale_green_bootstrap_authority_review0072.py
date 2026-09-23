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
import stale_green_bootstrap_authority_review0071 as previous
import stale_green_bootstrap_authority_review0072 as subject


class Review0072CurrentPrRevalidationTests(unittest.TestCase):
    def setUp(self) -> None:
        base._reset_request_budget()
        self._core_request = core.request_data
        self._base_poll = base.poll
        self._core_poll = core.poll
        self._base_validate = base.validate_github_contract
        self._core_validate = core.validate_github_contract

    def tearDown(self) -> None:
        core.request_data = self._core_request
        base.poll = self._base_poll
        core.poll = self._core_poll
        base.validate_github_contract = self._base_validate
        core.validate_github_contract = self._core_validate
        base._reset_request_budget()

    def test_page_snapshot_draft_but_current_ready_is_guarded_before_cursor_advance(self) -> None:
        state = pending.SchedulerStateV4(0)
        page = [page_pr(1, draft=True)]
        current = guard_pr(1, draft=False)
        writes: list[pending.SchedulerStateV4] = []
        with (
            mock.patch.object(pending, "_read_state", return_value=state),
            mock.patch.object(previous, "_read_discovery_page", return_value=page),
            mock.patch.object(base, "_remaining_request_budget", return_value=100),
            mock.patch.object(guardbase, "_direct_pr", return_value=current) as direct,
            mock.patch.object(previous, "_guard_one", return_value=True) as guard,
            mock.patch.object(
                pending, "_write_state", side_effect=lambda _r, _t, st: writes.append(st)
            ),
        ):
            self.assertEqual(subject._draft_guard_poll("o/r", "t"), [1])
        direct.assert_called_once_with("o/r", 1, "t")
        guard.assert_called_once_with("o/r", "t", current)
        self.assertEqual(writes[-1], pending.SchedulerStateV4(1))

    def test_page_snapshot_closed_but_current_ready_is_guarded(self) -> None:
        state = pending.SchedulerStateV4(0)
        page = [page_pr(1, draft=False, state="closed")]
        current = guard_pr(1, draft=False)
        with (
            mock.patch.object(pending, "_read_state", return_value=state),
            mock.patch.object(previous, "_read_discovery_page", return_value=page),
            mock.patch.object(base, "_remaining_request_budget", return_value=100),
            mock.patch.object(guardbase, "_direct_pr", return_value=current),
            mock.patch.object(previous, "_guard_one", return_value=True) as guard,
            mock.patch.object(pending, "_write_state"),
        ):
            self.assertEqual(subject._draft_guard_poll("o/r", "t"), [1])
        guard.assert_called_once_with("o/r", "t", current)

    def test_page_snapshot_ready_but_current_closed_skips_guard_after_direct_read(self) -> None:
        state = pending.SchedulerStateV4(0)
        page = [page_pr(1, draft=False)]
        with (
            mock.patch.object(pending, "_read_state", return_value=state),
            mock.patch.object(previous, "_read_discovery_page", return_value=page),
            mock.patch.object(base, "_remaining_request_budget", return_value=100),
            mock.patch.object(guardbase, "_direct_pr", return_value=None) as direct,
            mock.patch.object(previous, "_guard_one") as guard,
            mock.patch.object(pending, "_write_state"),
        ):
            self.assertEqual(subject._draft_guard_poll("o/r", "t"), [])
        direct.assert_called_once_with("o/r", 1, "t")
        guard.assert_not_called()

    def test_page_snapshot_ready_but_current_draft_skips_guard(self) -> None:
        state = pending.SchedulerStateV4(0)
        page = [page_pr(1, draft=False)]
        current = guard_pr(1, draft=True)
        with (
            mock.patch.object(pending, "_read_state", return_value=state),
            mock.patch.object(previous, "_read_discovery_page", return_value=page),
            mock.patch.object(base, "_remaining_request_budget", return_value=100),
            mock.patch.object(guardbase, "_direct_pr", return_value=current),
            mock.patch.object(previous, "_guard_one") as guard,
            mock.patch.object(pending, "_write_state"),
        ):
            self.assertEqual(subject._draft_guard_poll("o/r", "t"), [])
        guard.assert_not_called()

    def test_current_ready_without_draft_result_still_advances_durable_cursor(self) -> None:
        state = pending.SchedulerStateV4(0)
        page = [page_pr(1, draft=True)]
        current = guard_pr(1, draft=False)
        writes: list[pending.SchedulerStateV4] = []
        with (
            mock.patch.object(pending, "_read_state", return_value=state),
            mock.patch.object(previous, "_read_discovery_page", return_value=page),
            mock.patch.object(base, "_remaining_request_budget", return_value=100),
            mock.patch.object(guardbase, "_direct_pr", return_value=current),
            mock.patch.object(previous, "_guard_one", return_value=False),
            mock.patch.object(
                pending, "_write_state", side_effect=lambda _r, _t, st: writes.append(st)
            ),
        ):
            self.assertEqual(subject._draft_guard_poll("o/r", "t"), [])
        self.assertEqual(writes[-1], pending.SchedulerStateV4(1))

    def test_budget_floor_prevents_direct_read_and_cursor_advance(self) -> None:
        state = pending.SchedulerStateV4(0)
        page = [page_pr(1, draft=True)]
        with (
            mock.patch.object(pending, "_read_state", return_value=state),
            mock.patch.object(previous, "_read_discovery_page", return_value=page),
            mock.patch.object(
                base,
                "_remaining_request_budget",
                return_value=subject.DRAFT_GUARD_REQUEST_RESERVE + 2,
            ),
            mock.patch.object(guardbase, "_direct_pr") as direct,
            mock.patch.object(pending, "_write_state") as write,
        ):
            self.assertEqual(subject._draft_guard_poll("o/r", "t"), [])
        direct.assert_not_called()
        write.assert_not_called()

    def test_budget_one_above_floor_permits_current_revalidation(self) -> None:
        state = pending.SchedulerStateV4(0)
        page = [page_pr(1, draft=True)]
        with (
            mock.patch.object(pending, "_read_state", return_value=state),
            mock.patch.object(previous, "_read_discovery_page", return_value=page),
            mock.patch.object(
                base,
                "_remaining_request_budget",
                return_value=subject.DRAFT_GUARD_REQUEST_RESERVE + 3,
            ),
            mock.patch.object(guardbase, "_direct_pr", return_value=None) as direct,
            mock.patch.object(pending, "_write_state"),
        ):
            subject._draft_guard_poll("o/r", "t")
        direct.assert_called_once_with("o/r", 1, "t")

    def test_thirty_two_safe_records_progress_boundedly_with_direct_revalidation(self) -> None:
        state = pending.SchedulerStateV4(0)
        page = [page_pr(i, draft=True) for i in range(1, 41)]
        writes: list[pending.SchedulerStateV4] = []
        with (
            mock.patch.object(pending, "_read_state", return_value=state),
            mock.patch.object(previous, "_read_discovery_page", return_value=page),
            mock.patch.object(base, "_remaining_request_budget", return_value=100),
            mock.patch.object(guardbase, "_direct_pr", return_value=None) as direct,
            mock.patch.object(previous, "_guard_one") as guard,
            mock.patch.object(
                pending, "_write_state", side_effect=lambda _r, _t, st: writes.append(st)
            ),
        ):
            self.assertEqual(subject._draft_guard_poll("o/r", "t"), [])
        self.assertEqual(direct.call_count, subject.MAX_GUARD_PRS_PER_INVOCATION)
        guard.assert_not_called()
        self.assertEqual(writes[-1].scan_pr, 32)
        self.assertNotEqual(writes[-1].scan_anchor, "-")

    def test_legacy_pending_preempts_discovery(self) -> None:
        state = pending.SchedulerStateV4(
            cursor_pr=1,
            scan_pr=2,
            pending_pr=2,
            pending_authority="a" * 64,
            pending_run_id=10,
            pending_baseline_attempt=1,
            pending_check_id=20,
        )
        with (
            mock.patch.object(pending, "_read_state", return_value=state),
            mock.patch.object(pending, "_resume_pending", return_value=[10]) as resume,
            mock.patch.object(previous, "_read_discovery_page") as discovery,
        ):
            self.assertEqual(subject._draft_guard_poll("o/r", "t"), [10])
        resume.assert_called_once_with("o/r", "t", state)
        discovery.assert_not_called()

    def test_empty_page_wraps_or_remains_idle(self) -> None:
        active = pending.SchedulerStateV4(
            cursor_pr=2000,
            scan_pr=2000,
            scan_page=21,
            scan_anchor="-",
        )
        with (
            mock.patch.object(pending, "_read_state", return_value=active),
            mock.patch.object(previous, "_read_discovery_page", return_value=[]),
            mock.patch.object(pending, "_write_state") as write,
        ):
            self.assertEqual(subject._draft_guard_poll("o/r", "t"), [])
        write.assert_called_once_with("o/r", "t", pending.SchedulerStateV4(2000))

        idle = pending.SchedulerStateV4(0)
        with (
            mock.patch.object(pending, "_read_state", return_value=idle),
            mock.patch.object(previous, "_read_discovery_page", return_value=[]),
            mock.patch.object(pending, "_write_state") as write,
        ):
            self.assertEqual(subject._draft_guard_poll("o/r", "t"), [])
        write.assert_not_called()

    def test_full_page_completion_and_partial_page_progress_reuse_review0071_state_logic(self) -> None:
        page = [page_pr(i, draft=True) for i in range(1, 101)]
        state = pending.SchedulerStateV4(
            cursor_pr=99,
            scan_pr=99,
            scan_page=1,
            scan_anchor=previous._prefix_digest(previous._page_membership(page), 99),
        )
        writes: list[pending.SchedulerStateV4] = []
        with (
            mock.patch.object(pending, "_read_state", return_value=state),
            mock.patch.object(previous, "_read_discovery_page", return_value=page),
            mock.patch.object(base, "_remaining_request_budget", return_value=100),
            mock.patch.object(guardbase, "_direct_pr", return_value=None),
            mock.patch.object(
                pending, "_write_state", side_effect=lambda _r, _t, st: writes.append(st)
            ),
        ):
            subject._draft_guard_poll("o/r", "t")
        self.assertEqual(
            writes[-1],
            pending.SchedulerStateV4(
                cursor_pr=100,
                scan_pr=100,
                scan_page=2,
                scan_anchor="-",
            ),
        )

    def test_identical_next_state_avoids_redundant_write(self) -> None:
        state = pending.SchedulerStateV4(7)
        page = [page_pr(8, draft=True)]
        with (
            mock.patch.object(pending, "_read_state", return_value=state),
            mock.patch.object(previous, "_read_discovery_page", return_value=page),
            mock.patch.object(base, "_remaining_request_budget", return_value=100),
            mock.patch.object(guardbase, "_direct_pr", return_value=None),
            mock.patch.object(previous, "_next_discovery_state", return_value=state),
            mock.patch.object(pending, "_write_state") as write,
        ):
            self.assertEqual(subject._draft_guard_poll("o/r", "t"), [])
        write.assert_not_called()

    def test_install_main_and_entrypoint(self) -> None:
        with mock.patch.object(previous, "install") as install:
            subject.install()
        install.assert_called_once()
        self.assertIs(base.poll, subject._draft_guard_poll)
        self.assertIs(core.poll, subject._draft_guard_poll)
        self.assertIs(base.validate_github_contract, previous._validate_guard_contract)
        self.assertIs(core.validate_github_contract, previous._validate_guard_contract)

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
