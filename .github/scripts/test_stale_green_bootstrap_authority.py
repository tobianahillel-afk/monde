from __future__ import annotations

import os
import runpy
import unittest
from unittest import mock

from test_stale_green_bootstrap_pr_snapshot import gate_run, pr, snapshot
import stale_green_bootstrap_authority as authority


def check(check_id: int, run_id: int, *, head: str = "shared-head", status: str = "completed", conclusion: str | None = "success") -> dict:
    return {
        "id": check_id,
        "name": authority.core.REQUIRED_GATE_JOB_NAME,
        "head_sha": head,
        "details_url": f"https://github.com/o/r/actions/runs/{run_id}/job/{check_id}",
        "status": status,
        "conclusion": conclusion,
        "completed_at": "2026-09-15T14:30:00Z",
        "app": {"id": authority.core.GITHUB_ACTIONS_APP_ID, "slug": "github-actions"},
    }


def job(check_id: int, run_id: int, *, head: str = "shared-head", attempt: int = 1) -> dict:
    return {
        "id": check_id,
        "run_id": run_id,
        "run_attempt": attempt,
        "name": authority.core.REQUIRED_GATE_JOB_NAME,
        "head_sha": head,
        "status": "completed",
        "conclusion": "success",
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

        issue = {
            "number": 7,
            "title": authority.SCHEDULER_STATE_TITLE,
            "state": "open",
            "body": authority._scheduler_body(42),
        }
        self.assertEqual(authority._parse_scheduler_cursor(issue, 7), 42)
        for bad in [
            {**issue, "number": 8},
            {**issue, "title": "bad"},
            {**issue, "state": "closed"},
            {**issue, "pull_request": {}},
            {**issue, "body": None},
            {**issue, "body": "tampered"},
        ]:
            with self.assertRaises(RuntimeError):
                authority._parse_scheduler_cursor(bad, 7)

        with mock.patch.dict(os.environ, {"BOOTSTRAP_STATE_ISSUE": "7"}, clear=True):
            with mock.patch.object(authority.core, "request_data", return_value=issue):
                self.assertEqual(authority._read_scheduler_cursor("o/r", "t"), 42)
            with mock.patch.object(authority.core, "request_data", return_value=[]):
                with self.assertRaisesRegex(RuntimeError, "response is malformed"):
                    authority._read_scheduler_cursor("o/r", "t")
            updated = {**issue, "body": authority._scheduler_body(9)}
            with mock.patch.object(authority.core, "request_data", return_value=updated) as request_data:
                authority._write_scheduler_cursor("o/r", "t", 9)
            self.assertEqual(request_data.call_args.args[2], "PATCH")
            with self.assertRaisesRegex(RuntimeError, "cannot be negative"):
                authority._write_scheduler_cursor("o/r", "t", -1)
            with mock.patch.object(authority.core, "request_data", return_value={**updated, "body": authority._scheduler_body(8)}):
                with self.assertRaisesRegex(RuntimeError, "not durably acknowledged"):
                    authority._write_scheduler_cursor("o/r", "t", 9)

    def test_head_rotation_and_current_pr_revalidation(self) -> None:
        shared_a = pr(1, branch="shared", head="same")
        shared_b = pr(2, branch="shared", head="same")
        p3 = pr(3)
        p4 = pr(4)
        groups = authority._head_groups_after_cursor([p4, shared_b, p3, shared_a], 1)
        self.assertEqual([[item["number"] for item in group] for group in groups], [[3], [4], [1, 2]])
        self.assertEqual(authority._head_groups_after_cursor([], 10), [])
        self.assertEqual([[x["number"] for x in g] for g in authority._head_groups_after_cursor([shared_a, p3], 99)], [[1], [3]])

        with mock.patch.object(authority.core, "request_data", return_value=shared_a):
            self.assertEqual(authority._current_pr("o/r", "t", shared_a), shared_a)
        with mock.patch.object(authority.core, "request_data", return_value={**shared_a, "state": "closed"}):
            self.assertIsNone(authority._current_pr("o/r", "t", shared_a))
        changed = pr(1, branch="changed", head="new")
        with mock.patch.object(authority.core, "request_data", return_value=changed):
            self.assertIsNone(authority._current_pr("o/r", "t", shared_a))
        with mock.patch.object(authority.core, "request_data", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "malformed direct pull request"):
                authority._current_pr("o/r", "t", shared_a)

    def test_check_candidate_validation_and_bounded_target(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        current_run = gate_run(101, 1)
        good_check = check(501, 101)
        self.assertEqual(authority._validate_gate_check(good_check, "shared-head"), (101, 501))
        malformed = [
            {**good_check, "id": True},
            {**good_check, "name": "other"},
            {**good_check, "head_sha": "other"},
            {**good_check, "app": {}},
            {**good_check, "details_url": None},
            {**good_check, "details_url": "https://example.com/x"},
            {**good_check, "details_url": "https://github.com/o/r/actions/runs/101/job/999"},
        ]
        for candidate in malformed:
            with self.assertRaises(RuntimeError):
                authority._validate_gate_check(candidate, "shared-head")

        payload = {"total_count": 2, "check_runs": [good_check, check(502, 102, status="in_progress", conclusion=None)]}
        with mock.patch.object(authority.core, "request_data", return_value=payload):
            self.assertEqual(authority._candidate_gate_checks("o/r", "shared-head", "t"), [good_check])
        for bad_payload in [None, {}, {"total_count": True, "check_runs": []}, {"total_count": 0, "check_runs": [good_check]}]:
            with mock.patch.object(authority.core, "request_data", return_value=bad_payload):
                with self.assertRaises(RuntimeError):
                    authority._candidate_gate_checks("o/r", "shared-head", "t")

        responses = [payload, current_run, job(501, 101)]
        with mock.patch.object(authority.core, "request_data", side_effect=responses):
            target = authority._direct_target_for_pr("o/r", "t", current)
        self.assertIsNotNone(target)
        assert target is not None
        self.assertEqual(target[0]["id"], 101)

        wrong_pr_run = gate_run(101, 9)
        with mock.patch.object(authority.core, "request_data", side_effect=[payload, wrong_pr_run]):
            self.assertIsNone(authority._direct_target_for_pr("o/r", "t", current))

        authority._request_count = authority.MAX_GITHUB_REQUESTS_PER_INVOCATION - authority.MIN_TARGET_REQUEST_HEADROOM + 1
        with self.assertRaises(authority.DeferredForBudget):
            authority._direct_target_for_pr("o/r", "t", current)

    def test_direct_target_rejects_malformed_run_and_job(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        good_check = check(501, 101)
        payload = {"total_count": 1, "check_runs": [good_check]}
        run = gate_run(101, 1)
        variants = []
        for field, value in [
            ("id", 999),
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

        bad_job = job(501, 101)
        bad_job["run_attempt"] = 2
        with mock.patch.object(authority.core, "request_data", side_effect=[payload, run, bad_job]):
            with self.assertRaisesRegex(RuntimeError, "malformed protected"):
                authority._direct_target_for_pr("o/r", "t", current)

    def test_wait_for_invalidation_observes_new_nonmergeable_or_green(self) -> None:
        old = check(10, 1)
        queued = check(11, 2, status="in_progress", conclusion=None)
        with mock.patch.object(authority.core, "latest_required_check", side_effect=[old, queued]), mock.patch.object(
            authority.time, "sleep"
        ):
            self.assertTrue(authority._wait_for_invalidation("o/r", "h", "t", 10))
        green = check(12, 3)
        with mock.patch.object(authority.core, "latest_required_check", return_value=green):
            self.assertFalse(authority._wait_for_invalidation("o/r", "h", "t", 10))
        with mock.patch.object(authority.core, "latest_required_check", return_value=old), mock.patch.object(
            authority.time, "sleep"
        ) as sleeper:
            with self.assertRaisesRegex(RuntimeError, "bounded observation window"):
                authority._wait_for_invalidation("o/r", "h", "t", 10)
        self.assertEqual(sleeper.call_count, authority.MAX_POSTCONDITION_POLLS - 1)

    def test_process_head_revalidates_threads_and_confirms_postcondition(self) -> None:
        p1 = pr(1, branch="shared", head="shared-head")
        run = gate_run(101, 1)
        target_check = check(501, 101)
        latest = check(600, 200)
        with (
            mock.patch.object(authority.core, "latest_required_check", side_effect=[latest, latest]),
            mock.patch.object(authority.core, "unresolved_review_threads", side_effect=[True, True]),
            mock.patch.object(authority, "_direct_target_for_pr", return_value=(run, target_check)),
            mock.patch.object(authority, "_current_pr", return_value=p1),
            mock.patch.object(authority.core, "rerun_workflow") as rerun,
            mock.patch.object(authority, "_wait_for_invalidation", return_value=True),
        ):
            self.assertEqual(authority._process_head_group("o/r", "t", [p1]), ([101], []))
        rerun.assert_called_once_with("o/r", 101, "t")

        with mock.patch.object(authority.core, "latest_required_check", return_value=None):
            self.assertEqual(authority._process_head_group("o/r", "t", [p1]), ([], []))

        with (
            mock.patch.object(authority.core, "latest_required_check", return_value=latest),
            mock.patch.object(authority.core, "unresolved_review_threads", return_value=False),
        ):
            self.assertEqual(authority._process_head_group("o/r", "t", [p1]), ([], []))

        with (
            mock.patch.object(authority.core, "latest_required_check", return_value=latest),
            mock.patch.object(authority.core, "unresolved_review_threads", return_value=True),
            mock.patch.object(authority, "_direct_target_for_pr", return_value=None),
        ):
            self.assertEqual(len(authority._process_head_group("o/r", "t", [p1])[1]), 1)

    def test_process_head_handles_authority_change_and_green_rerun(self) -> None:
        p1 = pr(1, branch="shared", head="shared-head")
        run = gate_run(101, 1)
        target_check = check(501, 101)
        latest = check(600, 200)
        with (
            mock.patch.object(authority.core, "latest_required_check", return_value=latest),
            mock.patch.object(authority.core, "unresolved_review_threads", side_effect=[True]),
            mock.patch.object(authority, "_direct_target_for_pr", return_value=(run, target_check)),
            mock.patch.object(authority, "_current_pr", return_value=None),
        ):
            self.assertEqual(authority._process_head_group("o/r", "t", [p1]), ([], []))

        with (
            mock.patch.object(authority.core, "latest_required_check", side_effect=[latest, {"status": "in_progress", "conclusion": None}]),
            mock.patch.object(authority.core, "unresolved_review_threads", side_effect=[True, True]),
            mock.patch.object(authority, "_direct_target_for_pr", return_value=(run, target_check)),
            mock.patch.object(authority, "_current_pr", return_value=p1),
        ):
            self.assertEqual(authority._process_head_group("o/r", "t", [p1]), ([], []))

        with (
            mock.patch.object(authority.core, "latest_required_check", side_effect=[latest, latest, latest]),
            mock.patch.object(authority.core, "unresolved_review_threads", side_effect=[True, True, True]),
            mock.patch.object(authority, "_direct_target_for_pr", return_value=(run, target_check)),
            mock.patch.object(authority, "_current_pr", return_value=p1),
            mock.patch.object(authority.core, "rerun_workflow"),
            mock.patch.object(authority, "_wait_for_invalidation", return_value=False),
        ):
            with self.assertRaisesRegex(RuntimeError, "completed merge-acceptable"):
                authority._process_head_group("o/r", "t", [p1])

    def test_poll_uses_durable_cursor_and_makes_progress_without_global_refresh(self) -> None:
        p1, p2, p3 = pr(1), pr(2), pr(3)
        with (
            mock.patch.object(authority, "_read_scheduler_cursor", return_value=1),
            mock.patch.object(authority.snapshot, "open_pull_requests", return_value=[p1, p2, p3]) as open_reader,
            mock.patch.object(authority, "_process_head_group", side_effect=[([202], []), ([], [])]) as processor,
            mock.patch.object(authority, "_write_scheduler_cursor") as writer,
        ):
            self.assertEqual(authority.poll("o/r", "t"), [202])
        open_reader.assert_called_once_with("o/r", "t")
        self.assertEqual(processor.call_args_list[0].args[2][0]["number"], 2)
        writer.assert_called_once_with("o/r", "t", 1)

        with (
            mock.patch.object(authority, "_read_scheduler_cursor", return_value=4),
            mock.patch.object(authority.snapshot, "open_pull_requests", return_value=[]),
            mock.patch.object(authority, "_write_scheduler_cursor") as writer,
        ):
            self.assertEqual(authority.poll("o/r", "t"), [])
        writer.assert_called_once_with("o/r", "t", 0)

    def test_poll_preserves_progress_on_head_error_and_budget_deferral(self) -> None:
        p1, p2 = pr(1), pr(2)
        with (
            mock.patch.object(authority, "_read_scheduler_cursor", return_value=0),
            mock.patch.object(authority.snapshot, "open_pull_requests", return_value=[p1, p2]),
            mock.patch.object(authority, "_process_head_group", side_effect=[RuntimeError("boom"), ([], [])]),
            mock.patch.object(authority, "_write_scheduler_cursor") as writer,
        ):
            with self.assertRaisesRegex(RuntimeError, "boom"):
                authority.poll("o/r", "t")
        writer.assert_called_once_with("o/r", "t", 2)

        authority._request_count = authority.MAX_GITHUB_REQUESTS_PER_INVOCATION - authority.MIN_TARGET_REQUEST_HEADROOM
        with (
            mock.patch.object(authority, "_read_scheduler_cursor", return_value=0),
            mock.patch.object(authority.snapshot, "open_pull_requests", return_value=[p1]),
            mock.patch.object(authority, "_write_scheduler_cursor") as writer,
        ):
            self.assertEqual(authority.poll("o/r", "t"), [])
        writer.assert_called_once_with("o/r", "t", 0)

    def test_validate_contract_and_install_main(self) -> None:
        p1 = pr(2, branch="shared", head="shared-head")
        target = (gate_run(101, 2), check(501, 101))
        with (
            mock.patch.object(authority.snapshot, "open_pull_requests", return_value=[p1]),
            mock.patch.object(authority, "_direct_target_for_pr", return_value=target),
            mock.patch.object(authority.core, "latest_required_check", return_value=check(600, 200)),
            mock.patch.object(authority.core, "unresolved_review_threads", return_value=True),
        ):
            self.assertEqual(authority.validate_github_contract("o/r", 2, "t"), (1, 1, True))
        with mock.patch.object(authority.snapshot, "open_pull_requests", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "expected exactly one"):
                authority.validate_github_contract("o/r", 2, "t")
        with (
            mock.patch.object(authority.snapshot, "open_pull_requests", return_value=[p1]),
            mock.patch.object(authority, "_direct_target_for_pr", return_value=None),
        ):
            with self.assertRaisesRegex(RuntimeError, "no bounded canonical"):
                authority.validate_github_contract("o/r", 2, "t")
        with (
            mock.patch.object(authority.snapshot, "open_pull_requests", return_value=[p1]),
            mock.patch.object(authority, "_direct_target_for_pr", return_value=target),
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
