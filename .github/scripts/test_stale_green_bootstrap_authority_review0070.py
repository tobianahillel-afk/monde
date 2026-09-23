from __future__ import annotations

import json
import os
import runpy
import unittest
import urllib.error
from unittest import mock

from test_stale_green_bootstrap_authority_review0068 import HEAD, pr

import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0049 as pending
import stale_green_bootstrap_authority_review0051_recovery as recovery
import stale_green_bootstrap_authority_review0069 as previous
import stale_green_bootstrap_authority_review0070 as subject


def guard_pr(
    number: int,
    *,
    head: str = HEAD,
    draft: bool = False,
    node_id: str | None = None,
) -> dict:
    item = pr(number, branch=f"b{number}", head=head)
    item["node_id"] = node_id or f"PR_node_{number}"
    item["draft"] = draft
    item["state"] = "open"
    return item


def thread_page(
    resolved: list[bool],
    *,
    has_next: bool = False,
    cursor: str | None = None,
) -> dict:
    return {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "nodes": [{"isResolved": value} for value in resolved],
                        "pageInfo": {
                            "hasNextPage": has_next,
                            "endCursor": cursor,
                        },
                    }
                }
            }
        }
    }


def draft_ack(pr_item: dict) -> dict:
    return {
        "data": {
            "convertPullRequestToDraft": {
                "pullRequest": {
                    "id": pr_item["node_id"],
                    "number": pr_item["number"],
                    "isDraft": True,
                    "headRefOid": pr_item["head"]["sha"],
                    "baseRefOid": pr_item["base"]["sha"],
                }
            }
        }
    }


class Review0070DraftGuardTests(unittest.TestCase):
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

    def test_guard_pr_requires_exact_identity(self) -> None:
        item = guard_pr(1)
        guard = subject._guard_pr(item)
        self.assertEqual((guard.number, guard.node_id, guard.draft), (1, "PR_node_1", False))

        for bad in (
            {**item, "number": True},
            {**item, "node_id": ""},
            {**item, "draft": 0},
            {**item, "state": "closed"},
        ):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(RuntimeError, "malformed draft-guard"):
                    subject._guard_pr(bad)

    def test_guard_snapshot_rejects_duplicates_and_drift(self) -> None:
        p1 = guard_pr(1)
        p2 = guard_pr(2, draft=True)
        snap = subject._guard_snapshot([p2, p1])
        self.assertEqual([row[0] for row in snap], [1, 2])
        with self.assertRaisesRegex(RuntimeError, "duplicate draft-guard"):
            subject._guard_snapshot([p1, dict(p1)])

        with mock.patch.object(subject, "_read_open_prs", side_effect=[[p1], [{**p1, "draft": True}]]):
            with self.assertRaisesRegex(RuntimeError, "unstable draft-guard"):
                subject._stable_guard_prs("o/r", "t")

        with mock.patch.object(subject, "_read_open_prs", side_effect=[[p1], [dict(p1)]]):
            self.assertEqual(subject._stable_guard_prs("o/r", "t"), [p1])

    def test_read_open_prs_uses_unique_pr_identity(self) -> None:
        with mock.patch.object(core, "paged", return_value=[guard_pr(1)]) as paged:
            self.assertEqual(len(subject._read_open_prs("o/r", "t")), 1)
        self.assertEqual(paged.call_args.kwargs["unique_id_field"], "number")

    def test_thread_state_resolved_unresolved_and_pagination(self) -> None:
        base._request_count = 0
        with mock.patch.object(core, "request_data", return_value=thread_page([True, True])):
            self.assertEqual(subject._thread_state("o/r", 1, "t"), "RESOLVED")

        base._request_count = 0
        with mock.patch.object(core, "request_data", return_value=thread_page([True, False])):
            self.assertEqual(subject._thread_state("o/r", 1, "t"), "UNRESOLVED")

        base._request_count = 0
        pages = [
            thread_page([True], has_next=True, cursor="a"),
            thread_page([False], has_next=False, cursor=None),
        ]
        with mock.patch.object(core, "request_data", side_effect=pages) as req:
            self.assertEqual(subject._thread_state("o/r", 1, "t"), "UNRESOLVED")
        self.assertEqual(req.call_count, 2)
        self.assertIsNone(req.call_args_list[0].args[3]["variables"]["cursor"])
        self.assertEqual(req.call_args_list[1].args[3]["variables"]["cursor"], "a")

    def test_thread_state_ambiguity_is_fail_closed(self) -> None:
        cases = [
            RuntimeError("boom"),
            urllib.error.URLError("offline"),
            json.JSONDecodeError("bad", "x", 0),
            [],
            {"errors": [{"message": "x"}]},
            {"data": {}},
            {"data": {"repository": {"pullRequest": {"reviewThreads": []}}}},
            thread_page([True], has_next=True, cursor=None),
            thread_page([True], has_next=True, cursor="same"),
        ]
        for value in cases:
            base._request_count = 0
            with self.subTest(value=type(value).__name__):
                if isinstance(value, BaseException):
                    patch = mock.patch.object(core, "request_data", side_effect=value)
                elif value == thread_page([True], has_next=True, cursor="same"):
                    patch = mock.patch.object(
                        core,
                        "request_data",
                        side_effect=[
                            thread_page([True], has_next=True, cursor="same"),
                            thread_page([True], has_next=True, cursor="same"),
                        ],
                    )
                else:
                    patch = mock.patch.object(core, "request_data", return_value=value)
                with patch:
                    self.assertEqual(subject._thread_state("o/r", 1, "t"), "AMBIGUOUS")

        base._request_count = base.MAX_GITHUB_REQUESTS_PER_INVOCATION - subject.DRAFT_GUARD_REQUEST_RESERVE
        with mock.patch.object(core, "request_data") as req:
            self.assertEqual(subject._thread_state("o/r", 1, "t"), "AMBIGUOUS")
        req.assert_not_called()

    def test_thread_state_page_limit_becomes_ambiguous_not_error(self) -> None:
        base._request_count = 0
        pages = [
            thread_page([True], has_next=True, cursor=f"c{i}")
            for i in range(subject.THREAD_SCAN_PAGE_LIMIT)
        ]
        with mock.patch.object(core, "request_data", side_effect=pages):
            self.assertEqual(subject._thread_state("o/r", 1, "t"), "AMBIGUOUS")

    def test_thread_state_malformed_nodes_and_pageinfo_are_ambiguous(self) -> None:
        malformed = [
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "reviewThreads": {
                                "nodes": [{"isResolved": 1}],
                                "pageInfo": {"hasNextPage": False, "endCursor": None},
                            }
                        }
                    }
                }
            },
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "reviewThreads": {
                                "nodes": [],
                                "pageInfo": {"hasNextPage": "no", "endCursor": None},
                            }
                        }
                    }
                }
            },
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "reviewThreads": {
                                "nodes": [],
                                "pageInfo": {"hasNextPage": False},
                            }
                        }
                    }
                }
            },
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "reviewThreads": {
                                "nodes": [],
                                "pageInfo": {"hasNextPage": False, "endCursor": 7},
                            }
                        }
                    }
                }
            },
        ]
        for payload in malformed:
            base._request_count = 0
            with self.subTest(payload=payload), mock.patch.object(
                core, "request_data", return_value=payload
            ):
                self.assertEqual(subject._thread_state("o/r", 1, "t"), "AMBIGUOUS")

    def test_direct_pr_closed_and_malformed_contract(self) -> None:
        p1 = guard_pr(1)
        with mock.patch.object(core, "request_data", return_value=p1):
            self.assertEqual(subject._direct_pr("o/r", 1, "t"), p1)

        closed = {**p1, "state": "closed"}
        with mock.patch.object(core, "request_data", return_value=closed):
            self.assertIsNone(subject._direct_pr("o/r", 1, "t"))

        for bad, message in (
            ([], "malformed direct"),
            ({**p1, "number": 2}, "malformed direct"),
            ({**p1, "state": "mystery"}, "malformed direct.*state"),
        ):
            with self.subTest(message=message), mock.patch.object(
                core, "request_data", return_value=bad
            ):
                with self.assertRaisesRegex(RuntimeError, message):
                    subject._direct_pr("o/r", 1, "t")

    def test_convert_to_draft_exact_ack_and_postcondition(self) -> None:
        ready = guard_pr(1)
        drafted = {**ready, "draft": True}
        with mock.patch.object(
            core,
            "request_data",
            side_effect=[draft_ack(ready), drafted],
        ) as req:
            subject._convert_to_draft("o/r", "t", ready)
        self.assertEqual(req.call_count, 2)
        mutation = req.call_args_list[0]
        self.assertEqual(mutation.args[:3], ("https://api.github.com/graphql", "t", "POST"))
        self.assertEqual(mutation.args[3]["variables"]["id"], ready["node_id"])

        with mock.patch.object(core, "request_data") as req:
            subject._convert_to_draft("o/r", "t", drafted)
        req.assert_not_called()

        closed = {**drafted, "state": "closed"}
        with mock.patch.object(core, "request_data", side_effect=[draft_ack(ready), closed]):
            subject._convert_to_draft("o/r", "t", ready)

    def test_convert_to_draft_rejects_bad_ack_and_postcondition(self) -> None:
        ready = guard_pr(1)
        bad_acks = [
            [],
            {"errors": [{"message": "x"}]},
            {"data": {}},
            {
                "data": {
                    "convertPullRequestToDraft": {
                        "pullRequest": {
                            "id": "wrong",
                            "number": 1,
                            "isDraft": True,
                        }
                    }
                }
            },
        ]
        for ack in bad_acks:
            with self.subTest(ack=ack), mock.patch.object(
                core, "request_data", return_value=ack
            ):
                with self.assertRaisesRegex(RuntimeError, "draft conversion"):
                    subject._convert_to_draft("o/r", "t", ready)

        with mock.patch.object(
            core, "request_data", side_effect=[draft_ack(ready), []]
        ):
            with self.assertRaisesRegex(RuntimeError, "postcondition is malformed"):
                subject._convert_to_draft("o/r", "t", ready)

        wrong = {**ready, "draft": False}
        with mock.patch.object(
            core,
            "request_data",
            side_effect=[draft_ack(ready), wrong],
        ):
            with self.assertRaisesRegex(RuntimeError, "did not durably expose"):
                subject._convert_to_draft("o/r", "t", ready)

        wrong_node = {**ready, "draft": True, "node_id": "other"}
        with mock.patch.object(
            core,
            "request_data",
            side_effect=[draft_ack(ready), wrong_node],
        ):
            with self.assertRaisesRegex(RuntimeError, "did not durably expose"):
                subject._convert_to_draft("o/r", "t", ready)

    def test_guard_one_never_mutates_user_draft_or_resolved_pr(self) -> None:
        drafted = guard_pr(1, draft=True)
        with mock.patch.object(subject, "_thread_state") as threads:
            self.assertFalse(subject._guard_one("o/r", "t", drafted))
        threads.assert_not_called()

        ready = guard_pr(1)
        with mock.patch.object(subject, "_thread_state", return_value="RESOLVED"), mock.patch.object(
            subject, "_convert_to_draft"
        ) as convert:
            self.assertFalse(subject._guard_one("o/r", "t", ready))
        convert.assert_not_called()

    def test_guard_one_rechecks_threads_before_mutation(self) -> None:
        ready = guard_pr(1)
        drafted = {**ready, "draft": True}

        with (
            mock.patch.object(
                subject, "_thread_state", side_effect=["UNRESOLVED", "RESOLVED"]
            ),
            mock.patch.object(subject, "_direct_pr", return_value=ready),
            mock.patch.object(subject, "_convert_to_draft") as convert,
        ):
            self.assertFalse(subject._guard_one("o/r", "t", ready))
        convert.assert_not_called()

        with (
            mock.patch.object(
                subject, "_thread_state", side_effect=["UNRESOLVED", "UNRESOLVED"]
            ),
            mock.patch.object(subject, "_direct_pr", return_value=None),
            mock.patch.object(subject, "_convert_to_draft") as convert,
        ):
            self.assertFalse(subject._guard_one("o/r", "t", ready))
        convert.assert_not_called()

        with (
            mock.patch.object(
                subject, "_thread_state", side_effect=["UNRESOLVED", "UNRESOLVED"]
            ),
            mock.patch.object(subject, "_direct_pr", return_value=drafted),
            mock.patch.object(subject, "_convert_to_draft") as convert,
        ):
            self.assertFalse(subject._guard_one("o/r", "t", ready))
        convert.assert_not_called()

    def test_guard_one_drafts_unresolved_or_ambiguous_exact_current_pr(self) -> None:
        ready = guard_pr(1)
        changed = guard_pr(1, head="b" * 40)
        with (
            mock.patch.object(
                subject, "_thread_state", side_effect=["AMBIGUOUS", "UNRESOLVED"]
            ),
            mock.patch.object(subject, "_direct_pr", side_effect=[ready, changed]),
            mock.patch.object(subject, "_convert_to_draft") as convert,
        ):
            self.assertTrue(subject._guard_one("o/r", "t", ready))
        convert.assert_called_once_with("o/r", "t", changed)

    def test_ordered_after_cursor_wraps_deterministically(self) -> None:
        prs = [guard_pr(3), guard_pr(1), guard_pr(2)]
        self.assertEqual(
            [p["number"] for p in subject._ordered_after_cursor(prs, 1)],
            [2, 3, 1],
        )
        self.assertEqual(
            [p["number"] for p in subject._ordered_after_cursor(prs, 9)],
            [1, 2, 3],
        )
        self.assertEqual(subject._ordered_after_cursor([], 0), [])

    def test_poll_preserves_legacy_pending_before_draft_guard(self) -> None:
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
            mock.patch.object(subject, "_stable_guard_prs") as prs,
        ):
            self.assertEqual(subject._draft_guard_poll("o/r", "t"), [10])
        resume.assert_called_once_with("o/r", "t", state)
        prs.assert_not_called()

    def test_poll_fairness_cursor_and_draft_results(self) -> None:
        p1, p2, p3 = guard_pr(1), guard_pr(2), guard_pr(3)
        state = pending.SchedulerStateV4(cursor_pr=1)
        writes = []
        with (
            mock.patch.object(pending, "_read_state", return_value=state),
            mock.patch.object(subject, "_stable_guard_prs", return_value=[p1, p2, p3]),
            mock.patch.object(base, "_remaining_request_budget", return_value=100),
            mock.patch.object(subject, "_guard_one", side_effect=[True, False, True]) as guard,
            mock.patch.object(
                pending, "_write_state", side_effect=lambda _r, _t, s: writes.append(s)
            ),
        ):
            self.assertEqual(subject._draft_guard_poll("o/r", "t"), [2, 1])
        self.assertEqual([call.args[2]["number"] for call in guard.call_args_list], [2, 3, 1])
        self.assertEqual(writes[-1], pending.SchedulerStateV4(1))

    def test_poll_budget_and_max_pr_bound(self) -> None:
        prs = [guard_pr(i) for i in range(1, 40)]
        state = pending.SchedulerStateV4(0)
        with (
            mock.patch.object(pending, "_read_state", return_value=state),
            mock.patch.object(subject, "_stable_guard_prs", return_value=prs),
            mock.patch.object(base, "_remaining_request_budget", return_value=100),
            mock.patch.object(subject, "_guard_one", return_value=False) as guard,
            mock.patch.object(pending, "_write_state"),
        ):
            subject._draft_guard_poll("o/r", "t")
        self.assertEqual(guard.call_count, subject.MAX_GUARD_PRS_PER_INVOCATION)

        with (
            mock.patch.object(pending, "_read_state", return_value=state),
            mock.patch.object(subject, "_stable_guard_prs", return_value=[guard_pr(1)]),
            mock.patch.object(
                base,
                "_remaining_request_budget",
                return_value=subject.DRAFT_GUARD_REQUEST_RESERVE + 1,
            ),
            mock.patch.object(subject, "_guard_one") as guard,
            mock.patch.object(pending, "_write_state"),
        ):
            self.assertEqual(subject._draft_guard_poll("o/r", "t"), [])
        guard.assert_not_called()

    def test_poll_resets_idle_cursor_when_no_prs(self) -> None:
        state = pending.SchedulerStateV4(7)
        with (
            mock.patch.object(pending, "_read_state", return_value=state),
            mock.patch.object(subject, "_stable_guard_prs", return_value=[]),
            mock.patch.object(pending, "_write_state") as write,
        ):
            self.assertEqual(subject._draft_guard_poll("o/r", "t"), [])
        write.assert_called_once_with("o/r", "t", pending.SchedulerStateV4(0))

        state = pending.SchedulerStateV4(0)
        with (
            mock.patch.object(pending, "_read_state", return_value=state),
            mock.patch.object(subject, "_stable_guard_prs", return_value=[]),
            mock.patch.object(pending, "_write_state") as write,
        ):
            self.assertEqual(subject._draft_guard_poll("o/r", "t"), [])
        write.assert_not_called()

    def test_validate_guard_contract_is_read_only(self) -> None:
        target = guard_pr(2)
        other = guard_pr(3, draft=True)
        with (
            mock.patch.object(subject, "_stable_guard_prs", return_value=[target, other]),
            mock.patch.object(subject, "_thread_state", return_value="UNRESOLVED"),
            mock.patch.object(subject, "_convert_to_draft") as convert,
        ):
            self.assertEqual(subject._validate_guard_contract("o/r", 2, "t"), (2, 1, True))
        convert.assert_not_called()

        drafted = {**target, "draft": True}
        with (
            mock.patch.object(subject, "_stable_guard_prs", return_value=[drafted]),
            mock.patch.object(subject, "_thread_state", return_value="UNRESOLVED"),
        ):
            self.assertEqual(subject._validate_guard_contract("o/r", 2, "t"), (1, 1, False))

        with mock.patch.object(subject, "_stable_guard_prs", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "expected exactly one open PR"):
                subject._validate_guard_contract("o/r", 2, "t")

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
