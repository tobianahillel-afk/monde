from __future__ import annotations

import json
import os
import runpy
import unittest
from unittest import mock

from test_stale_green_bootstrap_authority_review0070 import (
    draft_ack,
    guard_pr,
)

import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0049 as pending
import stale_green_bootstrap_authority_review0051_recovery as recovery
import stale_green_bootstrap_authority_review0070 as previous
import stale_green_bootstrap_authority_review0071 as subject


def page_pr(
    number: int,
    *,
    draft: bool = True,
    state: str = "open",
) -> dict:
    item = guard_pr(number, draft=draft)
    item["state"] = state
    return item


class Review0071SuccessorTests(unittest.TestCase):
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

    def test_page_membership_requires_exact_ordered_pr_identity_and_state(self) -> None:
        page = [page_pr(1), page_pr(2, state="closed")]
        self.assertEqual(
            subject._page_membership(page),
            ((1, "PR_node_1"), (2, "PR_node_2")),
        )
        malformed = [
            "not-a-list",
            [page_pr(2), page_pr(1)],
            [{**page_pr(1), "number": True}],
            [{**page_pr(1), "node_id": ""}],
            [{**page_pr(1), "draft": 0}],
            [{**page_pr(1), "state": "mystery"}],
            [page_pr(1), page_pr(1)],
            [page_pr(i) for i in range(1, subject.DISCOVERY_PAGE_SIZE + 2)],
        ]
        for value in malformed:
            with self.subTest(value=type(value).__name__):
                with self.assertRaisesRegex(RuntimeError, "bounded PR discovery"):
                    subject._page_membership(value)

    def test_read_discovery_page_is_single_explicit_page_not_core_paged(self) -> None:
        payload = [page_pr(2001)]
        with (
            mock.patch.object(core, "request_data", return_value=payload) as req,
            mock.patch.object(core, "paged") as paged,
        ):
            self.assertEqual(subject._read_discovery_page("o/r", "t", 21), payload)
        paged.assert_not_called()
        self.assertIn("state=all", req.call_args.args[0])
        self.assertIn("sort=created", req.call_args.args[0])
        self.assertIn("direction=asc", req.call_args.args[0])
        self.assertIn("per_page=100", req.call_args.args[0])
        self.assertIn("page=21", req.call_args.args[0])

        for bad in (0, -1, True, 1.5):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(RuntimeError, "page number"):
                    subject._read_discovery_page("o/r", "t", bad)

    def test_prefix_resume_allows_append_only_growth_and_rejects_processed_drift(self) -> None:
        page = [page_pr(i) for i in range(1, 41)]
        membership = subject._page_membership(page)
        anchor = subject._prefix_digest(membership, 32)
        state = pending.SchedulerStateV4(
            cursor_pr=32,
            scan_pr=32,
            scan_page=1,
            scan_anchor=anchor,
        )
        grown = page + [page_pr(41)]
        subject._validate_discovery_resume(state, subject._page_membership(grown))

        drifted = [dict(item) for item in grown]
        drifted[9]["node_id"] = "changed-node"
        with self.assertRaisesRegex(RuntimeError, "prefix drifted"):
            subject._validate_discovery_resume(
                state,
                subject._page_membership(drifted),
            )

        with self.assertRaisesRegex(RuntimeError, "cursor is no longer present"):
            subject._prefix_digest(membership, 999)

    def test_new_page_must_not_overlap_previous_numeric_cursor(self) -> None:
        state = pending.SchedulerStateV4(
            cursor_pr=100,
            scan_pr=100,
            scan_page=2,
            scan_anchor="-",
        )
        subject._validate_discovery_resume(
            state,
            subject._page_membership([page_pr(101), page_pr(102)]),
        )
        with self.assertRaisesRegex(RuntimeError, "overlaps"):
            subject._validate_discovery_resume(
                state,
                subject._page_membership([page_pr(100), page_pr(101)]),
            )

    def test_guard_rechecks_even_when_first_observation_is_resolved(self) -> None:
        ready = guard_pr(5)
        with (
            mock.patch.object(
                previous,
                "_thread_state",
                side_effect=["RESOLVED", "UNRESOLVED"],
            ) as threads,
            mock.patch.object(previous, "_direct_pr", side_effect=[ready, ready]),
            mock.patch.object(subject, "_convert_to_draft") as convert,
        ):
            self.assertTrue(subject._guard_one("o/r", "t", ready))
        self.assertEqual(threads.call_count, 2)
        convert.assert_called_once_with("o/r", "t", ready)

    def test_guard_latest_resolved_observation_avoids_unnecessary_draft(self) -> None:
        ready = guard_pr(5)
        for first in ("UNRESOLVED", "AMBIGUOUS", "RESOLVED"):
            with (
                self.subTest(first=first),
                mock.patch.object(
                    previous,
                    "_thread_state",
                    side_effect=[first, "RESOLVED"],
                ),
                mock.patch.object(previous, "_direct_pr", return_value=ready),
                mock.patch.object(subject, "_convert_to_draft") as convert,
            ):
                self.assertFalse(subject._guard_one("o/r", "t", ready))
            convert.assert_not_called()

    def test_guard_suppresses_mutation_if_pr_closes_or_becomes_draft_on_rechecks(self) -> None:
        ready = guard_pr(5)
        drafted = guard_pr(5, draft=True)
        with (
            mock.patch.object(previous, "_thread_state", return_value="UNRESOLVED"),
            mock.patch.object(previous, "_direct_pr", return_value=None),
            mock.patch.object(subject, "_convert_to_draft") as convert,
        ):
            self.assertFalse(subject._guard_one("o/r", "t", ready))
        convert.assert_not_called()

        with (
            mock.patch.object(previous, "_thread_state", return_value="UNRESOLVED"),
            mock.patch.object(previous, "_direct_pr", return_value=drafted),
            mock.patch.object(subject, "_convert_to_draft") as convert,
        ):
            self.assertFalse(subject._guard_one("o/r", "t", ready))
        convert.assert_not_called()

        with (
            mock.patch.object(previous, "_thread_state", return_value="UNRESOLVED"),
            mock.patch.object(previous, "_direct_pr", side_effect=[ready, None]),
            mock.patch.object(subject, "_convert_to_draft") as convert,
        ):
            self.assertFalse(subject._guard_one("o/r", "t", ready))
        convert.assert_not_called()

    def test_draft_ack_requires_positive_non_boolean_integer_number(self) -> None:
        ready = guard_pr(5)
        for malformed_number in (True, 5.0, "5", 0, -5):
            ack = draft_ack(ready)
            ack["data"]["convertPullRequestToDraft"]["pullRequest"]["number"] = malformed_number
            with (
                self.subTest(number=malformed_number),
                mock.patch.object(core, "request_data", return_value=ack),
            ):
                with self.assertRaisesRegex(RuntimeError, "acknowledgement is not exact"):
                    subject._convert_to_draft("o/r", "t", ready)

    def test_draft_ack_success_still_requires_exact_postcondition(self) -> None:
        ready = guard_pr(5)
        drafted = guard_pr(5, draft=True)
        with mock.patch.object(
            core,
            "request_data",
            side_effect=[draft_ack(ready), drafted],
        ):
            subject._convert_to_draft("o/r", "t", ready)

    def test_page_state_advances_and_wraps_without_max_pages(self) -> None:
        pages: dict[int, list[dict]] = {}
        number = 1
        for page_number in range(1, 21):
            pages[page_number] = [
                page_pr(i, draft=True)
                for i in range(number, number + 100)
            ]
            number += 100
        pages[21] = [page_pr(2001, draft=True)]

        state_box = [pending.SchedulerStateV4(0)]
        seen_pages: list[int] = []

        def read_state(_repo: str, _token: str) -> pending.SchedulerStateV4:
            return state_box[0]

        def write_state(
            _repo: str,
            _token: str,
            state: pending.SchedulerStateV4,
        ) -> None:
            state_box[0] = state

        def read_page(_repo: str, _token: str, page_number: int) -> list[dict]:
            seen_pages.append(page_number)
            return pages.get(page_number, [])

        with (
            mock.patch.object(pending, "_read_state", side_effect=read_state),
            mock.patch.object(pending, "_write_state", side_effect=write_state),
            mock.patch.object(subject, "_read_discovery_page", side_effect=read_page),
            mock.patch.object(base, "_remaining_request_budget", return_value=100),
            mock.patch.object(subject, "_guard_one") as guard,
        ):
            for _ in range(100):
                subject._draft_guard_poll("o/r", "t")
                if 21 in seen_pages and state_box[0].scan_page == 1 and state_box[0].scan_pr == 0:
                    break
            else:
                self.fail("durable discovery did not traverse page 21 and wrap")

        guard.assert_not_called()
        self.assertGreaterEqual(max(seen_pages), 21)
        self.assertEqual(state_box[0].cursor_pr, 2001)
        self.assertEqual(state_box[0].scan_page, 1)
        self.assertEqual(state_box[0].scan_pr, 0)

    def test_partial_page_resume_accepts_new_appended_records(self) -> None:
        first = [page_pr(i, draft=True) for i in range(1, 41)]
        grown = first + [page_pr(41, draft=True)]
        state_box = [pending.SchedulerStateV4(0)]
        calls = [0]

        def read_page(_repo: str, _token: str, _page: int) -> list[dict]:
            calls[0] += 1
            return first if calls[0] == 1 else grown

        with (
            mock.patch.object(pending, "_read_state", side_effect=lambda *_: state_box[0]),
            mock.patch.object(
                pending,
                "_write_state",
                side_effect=lambda _r, _t, s: state_box.__setitem__(0, s),
            ),
            mock.patch.object(subject, "_read_discovery_page", side_effect=read_page),
            mock.patch.object(base, "_remaining_request_budget", return_value=100),
            mock.patch.object(subject, "MAX_GUARD_PRS_PER_INVOCATION", 32),
        ):
            subject._draft_guard_poll("o/r", "t")
            self.assertEqual(state_box[0].scan_pr, 32)
            self.assertNotEqual(state_box[0].scan_anchor, "-")
            subject._draft_guard_poll("o/r", "t")

        self.assertEqual(state_box[0].scan_page, 1)
        self.assertEqual(state_box[0].scan_pr, 0)
        self.assertEqual(state_box[0].cursor_pr, 41)

    def test_full_page_advances_to_next_page_with_durable_lower_bound(self) -> None:
        page = [page_pr(i, draft=True) for i in range(1, 101)]
        state = pending.SchedulerStateV4(
            cursor_pr=96,
            scan_pr=96,
            scan_page=1,
            scan_anchor=subject._prefix_digest(subject._page_membership(page), 96),
        )
        writes: list[pending.SchedulerStateV4] = []
        with (
            mock.patch.object(pending, "_read_state", return_value=state),
            mock.patch.object(pending, "_write_state", side_effect=lambda _r, _t, s: writes.append(s)),
            mock.patch.object(subject, "_read_discovery_page", return_value=page),
            mock.patch.object(base, "_remaining_request_budget", return_value=100),
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

    def test_empty_terminal_page_wraps_without_losing_cursor(self) -> None:
        state = pending.SchedulerStateV4(
            cursor_pr=2000,
            scan_pr=2000,
            scan_page=21,
            scan_anchor="-",
        )
        with (
            mock.patch.object(pending, "_read_state", return_value=state),
            mock.patch.object(subject, "_read_discovery_page", return_value=[]),
            mock.patch.object(pending, "_write_state") as write,
        ):
            self.assertEqual(subject._draft_guard_poll("o/r", "t"), [])
        write.assert_called_once_with("o/r", "t", pending.SchedulerStateV4(2000))

    def test_legacy_pending_still_preempts_discovery(self) -> None:
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
            mock.patch.object(subject, "_read_discovery_page") as discovery,
        ):
            self.assertEqual(subject._draft_guard_poll("o/r", "t"), [10])
        resume.assert_called_once_with("o/r", "t", state)
        discovery.assert_not_called()

    def test_validate_contract_reads_exact_target_without_repository_enumeration(self) -> None:
        target = guard_pr(2)
        with (
            mock.patch.object(previous, "_direct_pr", return_value=target) as direct,
            mock.patch.object(previous, "_thread_state", return_value="UNRESOLVED"),
            mock.patch.object(subject, "_read_discovery_page") as discovery,
        ):
            self.assertEqual(subject._validate_guard_contract("o/r", 2, "t"), (1, 1, True))
        direct.assert_called_once_with("o/r", 2, "t")
        discovery.assert_not_called()

        with mock.patch.object(previous, "_direct_pr", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "expected open PR"):
                subject._validate_guard_contract("o/r", 2, "t")

    def test_page_membership_rejects_non_dict_entry(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "malformed bounded PR discovery page"):
            subject._page_membership([page_pr(1), "bad"])

    def test_page_item_requires_exact_identity(self) -> None:
        page = [page_pr(1), page_pr(2)]
        self.assertEqual(subject._page_item_for_number(page, 2)["number"], 2)
        with self.assertRaisesRegex(RuntimeError, "lost exact PR identity"):
            subject._page_item_for_number(page, 3)
        duplicate = [page_pr(2), page_pr(2)]
        with self.assertRaisesRegex(RuntimeError, "lost exact PR identity"):
            subject._page_item_for_number(duplicate, 2)

    def test_convert_to_draft_defensive_paths(self) -> None:
        ready = guard_pr(5)
        drafted = guard_pr(5, draft=True)

        with mock.patch.object(core, "request_data") as req:
            subject._convert_to_draft("o/r", "t", drafted)
        req.assert_not_called()

        malformed_results = [
            [],
            {"errors": [{"message": "bad"}]},
            {"data": {}},
        ]
        for result in malformed_results:
            with self.subTest(result=result), mock.patch.object(
                core, "request_data", return_value=result
            ):
                with self.assertRaisesRegex(RuntimeError, "draft conversion returned malformed"):
                    subject._convert_to_draft("o/r", "t", ready)

        with mock.patch.object(
            core,
            "request_data",
            side_effect=[draft_ack(ready), []],
        ):
            with self.assertRaisesRegex(RuntimeError, "postcondition is malformed"):
                subject._convert_to_draft("o/r", "t", ready)

        closed = {**drafted, "state": "closed"}
        with mock.patch.object(
            core,
            "request_data",
            side_effect=[draft_ack(ready), closed],
        ):
            subject._convert_to_draft("o/r", "t", ready)

        wrong = {**ready, "draft": False}
        with mock.patch.object(
            core,
            "request_data",
            side_effect=[draft_ack(ready), wrong],
        ):
            with self.assertRaisesRegex(RuntimeError, "did not durably expose"):
                subject._convert_to_draft("o/r", "t", ready)

    def test_guard_skips_existing_draft(self) -> None:
        drafted = guard_pr(5, draft=True)
        with mock.patch.object(previous, "_thread_state") as threads:
            self.assertFalse(subject._guard_one("o/r", "t", drafted))
        threads.assert_not_called()

    def test_empty_idle_page_needs_no_state_write(self) -> None:
        state = pending.SchedulerStateV4(0)
        with (
            mock.patch.object(pending, "_read_state", return_value=state),
            mock.patch.object(subject, "_read_discovery_page", return_value=[]),
            mock.patch.object(pending, "_write_state") as write,
        ):
            self.assertEqual(subject._draft_guard_poll("o/r", "t"), [])
        write.assert_not_called()

    def test_poll_budget_break_preserves_checkpoint(self) -> None:
        state = pending.SchedulerStateV4(0)
        page = [page_pr(1, draft=False)]
        with (
            mock.patch.object(pending, "_read_state", return_value=state),
            mock.patch.object(subject, "_read_discovery_page", return_value=page),
            mock.patch.object(
                base,
                "_remaining_request_budget",
                return_value=previous.DRAFT_GUARD_REQUEST_RESERVE + 1,
            ),
            mock.patch.object(subject, "_guard_one") as guard,
            mock.patch.object(pending, "_write_state") as write,
        ):
            self.assertEqual(subject._draft_guard_poll("o/r", "t"), [])
        guard.assert_not_called()
        write.assert_not_called()

    def test_poll_processes_ready_pr_without_draft_when_guard_returns_false(self) -> None:
        state = pending.SchedulerStateV4(0)
        page = [page_pr(1, draft=False)]
        writes: list[pending.SchedulerStateV4] = []
        with (
            mock.patch.object(pending, "_read_state", return_value=state),
            mock.patch.object(subject, "_read_discovery_page", return_value=page),
            mock.patch.object(base, "_remaining_request_budget", return_value=100),
            mock.patch.object(subject, "_guard_one", return_value=False) as guard,
            mock.patch.object(
                pending, "_write_state", side_effect=lambda _r, _t, st: writes.append(st)
            ),
        ):
            self.assertEqual(subject._draft_guard_poll("o/r", "t"), [])
        guard.assert_called_once()
        self.assertEqual(writes[-1], pending.SchedulerStateV4(1))

    def test_poll_records_successful_draft_and_state_progress(self) -> None:
        state = pending.SchedulerStateV4(0)
        page = [page_pr(1, draft=False)]
        writes: list[pending.SchedulerStateV4] = []
        with (
            mock.patch.object(pending, "_read_state", return_value=state),
            mock.patch.object(subject, "_read_discovery_page", return_value=page),
            mock.patch.object(base, "_remaining_request_budget", return_value=100),
            mock.patch.object(subject, "_guard_one", return_value=True) as guard,
            mock.patch.object(
                pending, "_write_state", side_effect=lambda _r, _t, st: writes.append(st)
            ),
        ):
            self.assertEqual(subject._draft_guard_poll("o/r", "t"), [1])
        guard.assert_called_once()
        self.assertEqual(writes[-1], pending.SchedulerStateV4(1))

    def test_poll_skips_redundant_state_write_if_next_state_is_identical(self) -> None:
        state = pending.SchedulerStateV4(7)
        page = [page_pr(8, draft=True)]
        with (
            mock.patch.object(pending, "_read_state", return_value=state),
            mock.patch.object(subject, "_read_discovery_page", return_value=page),
            mock.patch.object(base, "_remaining_request_budget", return_value=100),
            mock.patch.object(subject, "_next_discovery_state", return_value=state),
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
