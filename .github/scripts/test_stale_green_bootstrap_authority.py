from __future__ import annotations

import os
import runpy
import unittest
from unittest import mock

from test_stale_green_bootstrap_pr_snapshot import SHA, gate_run as snapshot_gate_run, pr as snapshot_pr, snapshot
import stale_green_bootstrap_authority as authority


BASE_SHA = "b" * 40


def pr(
    number: int,
    *,
    state: str = "open",
    branch: str | None = None,
    head: str | None = None,
    created_at: str = "2026-09-15T14:00:00Z",
    base_ref: str = "main",
    base_sha: str = BASE_SHA,
    merge_sha: str | None = SHA,
) -> dict:
    item = snapshot_pr(
        number,
        state=state,
        branch=branch,
        head=head,
        created_at=created_at,
    )
    item["base"] = {
        "ref": base_ref,
        "sha": base_sha,
        "repo": {"full_name": "o/r"},
    }
    item["merge_commit_sha"] = merge_sha
    return item


def gate_run(
    run_id: int,
    pr_number: int,
    **kwargs,
) -> dict:
    item = snapshot_gate_run(run_id, pr_number, **kwargs)
    item["workflow_id"] = authority.core.CANONICAL_WORKFLOW_ID
    item["path"] = authority.core.CANONICAL_WORKFLOW_PATH
    return item


def check(
    check_id: int | float,
    run_id: int,
    *,
    head: str = "shared-head",
    status: str = "completed",
    conclusion: str | None = "success",
    completed_at: str = "2026-09-15T14:30:00Z",
    app_id: int | float = 15368,
) -> dict:
    return {
        "id": check_id,
        "name": authority.core.REQUIRED_GATE_JOB_NAME,
        "head_sha": head,
        "details_url": f"https://github.com/o/r/actions/runs/{run_id}/job/{int(check_id)}",
        "status": status,
        "conclusion": conclusion,
        "completed_at": completed_at,
        "app": {"id": app_id, "slug": "github-actions"},
    }


def job(
    check_id: int | float,
    run_id: int | float,
    *,
    head: str = "shared-head",
    attempt: int | float = 1,
    conclusion: str = "success",
) -> dict:
    return {
        "id": check_id,
        "run_id": run_id,
        "run_attempt": attempt,
        "name": authority.core.REQUIRED_GATE_JOB_NAME,
        "head_sha": head,
        "status": "completed",
        "conclusion": conclusion,
    }


class AuthorityBootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        authority._reset_request_budget()
        self.addCleanup(authority._reset_request_budget)

    def test_budget_and_scheduler_issue_contract(self) -> None:
        self.assertEqual(authority._remaining_request_budget(), authority.MAX_GITHUB_REQUESTS_PER_INVOCATION)
        with mock.patch.object(authority, "_ORIGINAL_REQUEST_DATA", return_value={"ok": True}) as request:
            self.assertEqual(authority._budgeted_request_data("https://api.github.com/x", "t"), {"ok": True})
            self.assertEqual(authority._request_count, 1)
            authority._request_count = authority.MAX_GITHUB_REQUESTS_PER_INVOCATION
            with self.assertRaisesRegex(RuntimeError, "request budget exceeded"):
                authority._budgeted_request_data("https://api.github.com/x", "t")
        request.assert_called_once()

        with mock.patch.dict(os.environ, {"BOOTSTRAP_STATE_ISSUE": "7"}, clear=True):
            self.assertEqual(authority._scheduler_issue_number(), 7)
        for value in ["", "0", "bad"]:
            with mock.patch.dict(os.environ, {"BOOTSTRAP_STATE_ISSUE": value}, clear=True):
                with self.assertRaisesRegex(RuntimeError, "positive integer"):
                    authority._scheduler_issue_number()

        state = authority.SchedulerState(42, 2, 3)
        issue = {
            "number": 7,
            "title": authority.SCHEDULER_STATE_TITLE,
            "state": "open",
            "body": authority._scheduler_body(*state),
        }
        self.assertEqual(authority._parse_scheduler_state(issue, 7), state)
        self.assertEqual(authority._parse_scheduler_cursor(issue, 7), 42)
        legacy = {
            **issue,
            "body": (
                f"{authority.LEGACY_SCHEDULER_STATE_MARKER}\ncursor_pr: 9\n\n"
                "Machine-managed durable cursor for the trusted default-branch stale-green bootstrap. "
                "Do not edit manually. The scheduled bootstrap validates this exact marker before reading or updating the cursor."
            ),
        }
        self.assertEqual(authority._parse_scheduler_state(legacy, 7), authority.SchedulerState(9, 0, 1))
        for bad in [
            {**issue, "number": 8},
            {**issue, "title": "bad"},
            {**issue, "state": "closed"},
            {**issue, "pull_request": {}},
            {**issue, "body": None},
            {**issue, "body": "tampered"},
        ]:
            with self.assertRaises(RuntimeError):
                authority._parse_scheduler_state(bad, 7)
        for bad_state in [
            authority.SchedulerState(-1, 0, 1),
            authority.SchedulerState(0, -1, 1),
            authority.SchedulerState(0, 0, 0),
            authority.SchedulerState(0, 0, 2),
        ]:
            with self.assertRaises(RuntimeError):
                authority._validate_scheduler_state(bad_state)

        with mock.patch.dict(os.environ, {"BOOTSTRAP_STATE_ISSUE": "7"}, clear=True):
            with mock.patch.object(authority.core, "request_data", return_value=issue):
                self.assertEqual(authority._read_scheduler_state("o/r", "t"), state)
                self.assertEqual(authority._read_scheduler_cursor("o/r", "t"), 42)
            with mock.patch.object(authority.core, "request_data", return_value=[]):
                with self.assertRaisesRegex(RuntimeError, "response is malformed"):
                    authority._read_scheduler_state("o/r", "t")
            updated = {**issue, "body": authority._scheduler_body(9)}
            with mock.patch.object(authority.core, "request_data", return_value=updated) as request_data:
                authority._write_scheduler_cursor("o/r", "t", 9)
            self.assertEqual(request_data.call_args.args[2], "PATCH")
            with mock.patch.object(authority.core, "request_data", return_value=issue):
                authority._write_scheduler_state("o/r", "t", state)
            with mock.patch.object(authority.core, "request_data", return_value={**updated, "body": authority._scheduler_body(8)}):
                with self.assertRaisesRegex(RuntimeError, "not durably acknowledged"):
                    authority._write_scheduler_cursor("o/r", "t", 9)

    def test_head_rotation_and_current_pr_revalidation_binds_base(self) -> None:
        shared_a = pr(1, branch="shared", head="same")
        shared_b = pr(2, branch="shared", head="same")
        p3 = pr(3)
        p4 = pr(4)
        groups = authority._head_groups_after_cursor([p4, shared_b, p3, shared_a], 1)
        self.assertEqual([[item["number"] for item in group] for group in groups], [[3], [4], [1, 2]])
        self.assertEqual(authority._head_groups_after_cursor([], 10), [])
        self.assertEqual([[x["number"] for x in g] for g in authority._head_groups_after_cursor([shared_a, p3], 99)], [[1], [3]])

        self.assertEqual(authority._pr_base_identity(shared_a), ("o/r", "main", BASE_SHA))
        self.assertEqual(authority._pr_merge_sha(shared_a), SHA)
        self.assertIsNone(authority._pr_merge_sha({**shared_a, "merge_commit_sha": None}))
        for bad in [
            {**shared_a, "base": None},
            {**shared_a, "base": {"repo": {}, "ref": "main", "sha": BASE_SHA}},
            {**shared_a, "base": {"repo": {"full_name": "bad"}, "ref": "main", "sha": BASE_SHA}},
            {**shared_a, "base": {"repo": {"full_name": "o/r"}, "ref": "", "sha": BASE_SHA}},
            {**shared_a, "base": {"repo": {"full_name": "o/r"}, "ref": "main", "sha": "bad"}},
        ]:
            with self.assertRaises(RuntimeError):
                authority._pr_base_identity(bad)
        with self.assertRaisesRegex(RuntimeError, "merge_commit_sha"):
            authority._pr_merge_sha({**shared_a, "merge_commit_sha": "bad"})

        with mock.patch.object(authority.core, "request_data", return_value=shared_a):
            self.assertEqual(authority._current_pr("o/r", "t", shared_a), shared_a)
        with mock.patch.object(authority.core, "request_data", return_value={**shared_a, "state": "closed"}):
            self.assertIsNone(authority._current_pr("o/r", "t", shared_a))
        changed_head = pr(1, branch="changed", head="new")
        with mock.patch.object(authority.core, "request_data", return_value=changed_head):
            self.assertIsNone(authority._current_pr("o/r", "t", shared_a))
        changed_base = pr(1, branch="shared", head="same", base_ref="release")
        with mock.patch.object(authority.core, "request_data", return_value=changed_base):
            self.assertIsNone(authority._current_pr("o/r", "t", shared_a))
        changed_merge = pr(1, branch="shared", head="same", merge_sha="c" * 40)
        with mock.patch.object(authority.core, "request_data", return_value=changed_merge):
            self.assertIsNone(authority._current_pr("o/r", "t", shared_a))
        with mock.patch.object(authority.core, "request_data", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "malformed direct pull request"):
                authority._current_pr("o/r", "t", shared_a)

    def test_check_page_validation_and_continuation_target(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        current_run = gate_run(101, 1)
        good_check = check(501, 101)
        self.assertEqual(authority._validate_gate_check(good_check, "shared-head"), (101, 501))
        malformed = [
            {**good_check, "id": True},
            {**good_check, "name": "other"},
            {**good_check, "head_sha": "other"},
            {**good_check, "app": {}},
            {**good_check, "app": {"id": 15368.0, "slug": "github-actions"}},
            {**good_check, "details_url": None},
            {**good_check, "details_url": "https://example.com/x"},
            {**good_check, "details_url": "https://github.com/o/r/actions/runs/101/job/999"},
        ]
        for candidate in malformed:
            with self.assertRaises(RuntimeError):
                authority._validate_gate_check(candidate, "shared-head")

        payload = {
            "total_count": 13,
            "check_runs": [good_check] + [check(600 + i, 200 + i) for i in range(11)],
        }
        with mock.patch.object(authority.core, "request_data", return_value=payload):
            rows, more = authority._candidate_gate_check_page("o/r", "shared-head", "t", 1)
        self.assertTrue(more)
        self.assertEqual(len(rows), 12)
        terminal = {"total_count": 13, "check_runs": [good_check]}
        with mock.patch.object(authority.core, "request_data", return_value=terminal):
            rows, more = authority._candidate_gate_check_page("o/r", "shared-head", "t", 2)
        self.assertFalse(more)
        self.assertEqual(rows, [good_check])
        for bad_payload in [
            None,
            {},
            {"total_count": True, "check_runs": []},
            {"total_count": 0, "check_runs": [good_check]},
            {"total_count": 20, "check_runs": [good_check]},
        ]:
            with mock.patch.object(authority.core, "request_data", return_value=bad_payload):
                with self.assertRaises(RuntimeError):
                    authority._candidate_gate_check_page("o/r", "shared-head", "t", 1)
        with self.assertRaisesRegex(RuntimeError, "positive integer"):
            authority._candidate_gate_check_page("o/r", "shared-head", "t", 0)

        one = {"total_count": 1, "check_runs": [good_check]}
        responses = [one, current_run, job(501, 101)]
        with mock.patch.object(authority.core, "request_data", side_effect=responses):
            target, next_page = authority._direct_target_for_pr("o/r", "t", current)
        self.assertIsNone(next_page)
        self.assertIsNotNone(target)
        assert target is not None
        self.assertEqual(target[0]["id"], 101)

        wrong_pr_run = gate_run(101, 9)
        with mock.patch.object(authority.core, "request_data", side_effect=[one, wrong_pr_run]):
            target, next_page = authority._direct_target_for_pr("o/r", "t", current)
        self.assertIsNone(target)
        self.assertIsNone(next_page)

        full_page = {"total_count": 30, "check_runs": [check(700 + i, 300 + i) for i in range(12)]}
        nonmatching_runs = [gate_run(300 + i, 9, run_number=300 + i) for i in reversed(range(12))]
        side_effect = [full_page]
        for run in nonmatching_runs:
            side_effect.append(run)
        side_effect.append(full_page)
        for run in nonmatching_runs:
            side_effect.append(run)
        with mock.patch.object(authority.core, "request_data", side_effect=side_effect):
            target, next_page = authority._direct_target_for_pr("o/r", "t", current)
        self.assertIsNone(target)
        self.assertEqual(next_page, 3)

        authority._request_count = authority.MAX_GITHUB_REQUESTS_PER_INVOCATION - authority.MIN_TARGET_REQUEST_HEADROOM + 1
        with self.assertRaises(authority.DeferredForBudget):
            authority._direct_target_for_pr("o/r", "t", current)

    def test_direct_target_rejects_bad_merge_authority_and_malformed_ids(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        good_check = check(501, 101)
        payload = {"total_count": 1, "check_runs": [good_check]}
        run = gate_run(101, 1)
        variants = []
        for field, value in [
            ("id", 101.0),
            ("workflow_id", float(authority.core.CANONICAL_WORKFLOW_ID)),
            ("workflow_id", 1),
            ("path", "other"),
            ("event", "schedule"),
            ("status", "in_progress"),
            ("conclusion", "unknown"),
            ("run_attempt", True),
        ]:
            candidate = dict(run)
            candidate[field] = value
            variants.append(candidate)
        for candidate in variants:
            with mock.patch.object(authority.core, "request_data", side_effect=[payload, candidate]):
                with self.assertRaises(RuntimeError):
                    authority._direct_target_for_pr("o/r", "t", current)

        wrong_merge = gate_run(101, 1)
        wrong_merge["referenced_workflows"][0]["sha"] = "c" * 40
        wrong_merge["referenced_workflows"][0]["path"] = f"o/r/{authority._REUSABLE_WORKFLOW_PATH}@{'c' * 40}"
        with mock.patch.object(authority.core, "request_data", side_effect=[payload, wrong_merge]):
            target, continuation = authority._direct_target_for_pr("o/r", "t", current)
        self.assertIsNone(target)
        self.assertIsNone(continuation)

        bad_job_variants = [
            {**job(501, 101), "id": 501.0},
            {**job(501, 101), "run_id": 101.0},
            {**job(501, 101), "run_attempt": 1.0},
            {**job(501, 101), "run_attempt": 2},
        ]
        for bad_job in bad_job_variants:
            with mock.patch.object(authority.core, "request_data", side_effect=[payload, run, bad_job]):
                with self.assertRaisesRegex(RuntimeError, "malformed protected"):
                    authority._direct_target_for_pr("o/r", "t", current)

        with self.assertRaisesRegex(RuntimeError, "merge-ref SHA"):
            authority._direct_target_for_pr("o/r", "t", pr(1, branch="shared", head="shared-head", merge_sha=None))

    def test_triggering_authority_is_exact_and_unambiguous(self) -> None:
        run = gate_run(101, 2)
        self.assertEqual(authority._triggering_pr_authority("o/r", run), (2, SHA))
        bad = dict(run)
        bad["referenced_workflows"] = None
        with self.assertRaises(RuntimeError):
            authority._triggering_pr_authority("o/r", bad)
        malformed = dict(run)
        malformed["referenced_workflows"] = [None]
        with self.assertRaises(RuntimeError):
            authority._triggering_pr_authority("o/r", malformed)
        no_match = gate_run(101, 2)
        no_match["referenced_workflows"][0]["path"] = f"other/r/{authority._REUSABLE_WORKFLOW_PATH}@{SHA}"
        with self.assertRaisesRegex(RuntimeError, "ambiguous"):
            authority._triggering_pr_authority("o/r", no_match)
        wrong_ref = gate_run(101, 2)
        wrong_ref["referenced_workflows"][0]["ref"] = "refs/heads/main"
        with self.assertRaisesRegex(RuntimeError, "merge ref"):
            authority._triggering_pr_authority("o/r", wrong_ref)
        duplicate = gate_run(101, 2)
        duplicate["referenced_workflows"] = duplicate["referenced_workflows"] * 2
        with self.assertRaisesRegex(RuntimeError, "ambiguous"):
            authority._triggering_pr_authority("o/r", duplicate)

    def test_terminal_waiter_does_not_accept_in_progress_and_tracks_run(self) -> None:
        queued_run = gate_run(101, 1)
        queued_run.update({"run_attempt": 1, "status": "completed"})
        rerun_in_progress = dict(queued_run)
        rerun_in_progress.update({"run_attempt": 2, "status": "in_progress", "conclusion": None})
        rerun_done = dict(queued_run)
        rerun_done.update({"run_attempt": 2, "status": "completed", "conclusion": "failure"})
        failed = check(11, 101, conclusion="failure")
        with (
            mock.patch.object(authority.core, "request_data", side_effect=[rerun_in_progress, rerun_done]),
            mock.patch.object(authority.core, "required_merge_gate_conclusion", return_value="failure") as job_check,
            mock.patch.object(authority.core, "latest_required_check", return_value=failed),
            mock.patch.object(authority.time, "sleep") as sleeper,
        ):
            self.assertTrue(authority._wait_for_terminal_invalidation("o/r", "shared-head", "t", 101, 1, 10))
        sleeper.assert_called_once()
        job_check.assert_called_once()

        green = check(12, 101)
        with (
            mock.patch.object(authority.core, "request_data", return_value=rerun_done),
            mock.patch.object(authority.core, "required_merge_gate_conclusion", return_value="success"),
            mock.patch.object(authority.core, "latest_required_check", return_value=green),
        ):
            self.assertFalse(authority._wait_for_terminal_invalidation("o/r", "shared-head", "t", 101, 1, 10))

        with (
            mock.patch.object(authority.core, "request_data", return_value=queued_run),
            mock.patch.object(authority.time, "sleep") as sleeper,
        ):
            with self.assertRaisesRegex(RuntimeError, "terminal required-check"):
                authority._wait_for_terminal_invalidation("o/r", "shared-head", "t", 101, 1, 10)
        self.assertEqual(sleeper.call_count, authority.MAX_POSTCONDITION_POLLS - 1)

    def test_process_head_global_post_cap_and_green_fallthrough(self) -> None:
        group = [pr(i, branch="shared", head="shared-head") for i in range(1, 6)]
        latest = check(600, 200)
        targets = {
            item["number"]: (gate_run(100 + item["number"], item["number"]), check(500 + item["number"], 100 + item["number"]))
            for item in group
        }

        def target(_repo: str, _token: str, item: dict, _page: int = 1):
            return targets[item["number"]], None

        with (
            mock.patch.object(authority.core, "latest_required_check", return_value=latest),
            mock.patch.object(authority.core, "unresolved_review_threads", side_effect=[True, True, False] * 3),
            mock.patch.object(authority, "_direct_target_for_pr", side_effect=target),
            mock.patch.object(authority, "_current_pr", side_effect=lambda _r, _t, item: item),
            mock.patch.object(authority.core, "rerun_workflow") as rerun,
            mock.patch.object(authority, "_wait_for_terminal_invalidation", return_value=False),
        ):
            posted, _errors, continuation = authority._process_head_group("o/r", "t", group, 3)
        self.assertLessEqual(len(posted), 3)
        self.assertLessEqual(rerun.call_count, 3)
        self.assertIsNone(continuation)

    def test_process_head_persists_target_scan_and_confirms_invalidation(self) -> None:
        p1 = pr(1, branch="shared", head="shared-head")
        latest = check(600, 200)
        with (
            mock.patch.object(authority.core, "latest_required_check", return_value=latest),
            mock.patch.object(authority.core, "unresolved_review_threads", return_value=True),
            mock.patch.object(authority, "_direct_target_for_pr", return_value=(None, 3)),
        ):
            self.assertEqual(authority._process_head_group("o/r", "t", [p1], 3), ([], [], (1, 3)))

        run = gate_run(101, 1)
        target_check = check(501, 101)
        with (
            mock.patch.object(authority.core, "latest_required_check", side_effect=[latest, latest]),
            mock.patch.object(authority.core, "unresolved_review_threads", side_effect=[True, True]),
            mock.patch.object(authority, "_direct_target_for_pr", return_value=((run, target_check), None)),
            mock.patch.object(authority, "_current_pr", return_value=p1),
            mock.patch.object(authority.core, "rerun_workflow") as rerun,
            mock.patch.object(authority, "_wait_for_terminal_invalidation", return_value=True),
        ):
            self.assertEqual(authority._process_head_group("o/r", "t", [p1], 3), ([101], [], None))
        rerun.assert_called_once()

        with mock.patch.object(authority.core, "latest_required_check", return_value=None):
            self.assertEqual(authority._process_head_group("o/r", "t", [p1], 3), ([], [], None))

    def test_poll_persists_scan_cursor_and_rerun_cap(self) -> None:
        p1, p2, p3 = pr(1), pr(2), pr(3)
        state = authority.SchedulerState(1, 2, 3)
        with (
            mock.patch.object(authority, "_read_scheduler_state", return_value=state),
            mock.patch.object(authority.snapshot, "open_pull_requests", return_value=[p1, p2, p3]) as open_reader,
            mock.patch.object(authority, "_process_head_group", return_value=([], [], (2, 5))) as processor,
            mock.patch.object(authority, "_write_scheduler_state") as writer,
        ):
            self.assertEqual(authority.poll("o/r", "t"), [])
        open_reader.assert_called_once()
        self.assertEqual(processor.call_args.args[4:6], (2, 3))
        writer.assert_called_once_with("o/r", "t", authority.SchedulerState(1, 2, 5))

        with (
            mock.patch.object(authority, "_read_scheduler_state", return_value=authority.SchedulerState(0, 0, 1)),
            mock.patch.object(authority.snapshot, "open_pull_requests", return_value=[p1, p2, p3]),
            mock.patch.object(authority, "_process_head_group", side_effect=[([101, 102, 103], [], None)]) as processor,
            mock.patch.object(authority, "_write_scheduler_state"),
        ):
            self.assertEqual(authority.poll("o/r", "t"), [101, 102, 103])
        self.assertEqual(processor.call_args.args[3], 3)

        with (
            mock.patch.object(authority, "_read_scheduler_state", return_value=authority.SchedulerState(4, 9, 2)),
            mock.patch.object(authority.snapshot, "open_pull_requests", return_value=[]),
            mock.patch.object(authority, "_write_scheduler_state") as writer,
        ):
            self.assertEqual(authority.poll("o/r", "t"), [])
        writer.assert_called_once_with("o/r", "t", authority.SchedulerState(0, 0, 1))

    def test_poll_preserves_progress_on_error_and_budget(self) -> None:
        p1, p2 = pr(1), pr(2)
        with (
            mock.patch.object(authority, "_read_scheduler_state", return_value=authority.SchedulerState(0, 0, 1)),
            mock.patch.object(authority.snapshot, "open_pull_requests", return_value=[p1, p2]),
            mock.patch.object(authority, "_process_head_group", side_effect=[RuntimeError("boom"), ([], [], None)]),
            mock.patch.object(authority, "_write_scheduler_state") as writer,
        ):
            with self.assertRaisesRegex(RuntimeError, "boom"):
                authority.poll("o/r", "t")
        writer.assert_called_once()

        authority._request_count = authority.MAX_GITHUB_REQUESTS_PER_INVOCATION - authority.MIN_TARGET_REQUEST_HEADROOM
        with (
            mock.patch.object(authority, "_read_scheduler_state", return_value=authority.SchedulerState(0, 0, 1)),
            mock.patch.object(authority.snapshot, "open_pull_requests", return_value=[p1]),
            mock.patch.object(authority, "_write_scheduler_state") as writer,
        ):
            self.assertEqual(authority.poll("o/r", "t"), [])
        writer.assert_called_once()

    def test_validate_contract_install_and_main(self) -> None:
        p1 = pr(2, branch="shared", head="shared-head")
        target = (gate_run(101, 2), check(501, 101))
        with (
            mock.patch.object(authority.snapshot, "open_pull_requests", return_value=[p1]),
            mock.patch.object(authority, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(authority.core, "latest_required_check", return_value=check(600, 200)),
            mock.patch.object(authority.core, "unresolved_review_threads", return_value=True),
        ):
            self.assertEqual(authority.validate_github_contract("o/r", 2, "t"), (1, 1, True))
        with mock.patch.object(authority.snapshot, "open_pull_requests", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "expected exactly one"):
                authority.validate_github_contract("o/r", 2, "t")
        with (
            mock.patch.object(authority.snapshot, "open_pull_requests", return_value=[p1]),
            mock.patch.object(authority, "_direct_target_for_pr", return_value=(None, 2)),
        ):
            with self.assertRaisesRegex(RuntimeError, "requires continuation"):
                authority.validate_github_contract("o/r", 2, "t")
        with (
            mock.patch.object(authority.snapshot, "open_pull_requests", return_value=[p1]),
            mock.patch.object(authority, "_direct_target_for_pr", return_value=(None, None)),
        ):
            with self.assertRaisesRegex(RuntimeError, "no canonical"):
                authority.validate_github_contract("o/r", 2, "t")
        with (
            mock.patch.object(authority.snapshot, "open_pull_requests", return_value=[p1]),
            mock.patch.object(authority, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(authority.core, "latest_required_check", return_value=None),
        ):
            with self.assertRaisesRegex(RuntimeError, "no latest"):
                authority.validate_github_contract("o/r", 2, "t")

        originals = (authority.core.request_data, authority.core.poll, authority.core.validate_github_contract)
        self.addCleanup(setattr, authority.core, "request_data", originals[0])
        self.addCleanup(setattr, authority.core, "poll", originals[1])
        self.addCleanup(setattr, authority.core, "validate_github_contract", originals[2])
        authority.install()
        self.assertIs(authority.core.request_data, authority._budgeted_request_data)
        self.assertIs(authority.core.poll, authority.poll)
        self.assertIs(authority.core.validate_github_contract, authority.validate_github_contract)

        authority._request_count = 7
        with mock.patch.object(authority.core, "main", return_value=5), mock.patch("builtins.print") as printer:
            self.assertEqual(authority.main(), 5)
        printer.assert_called_once_with("MONDE bootstrap GitHub request budget: 0/100")

    def test_script_entrypoint_delegates_to_core_main(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit) as ctx:
                runpy.run_path(authority.__file__, run_name="__main__")
        self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()