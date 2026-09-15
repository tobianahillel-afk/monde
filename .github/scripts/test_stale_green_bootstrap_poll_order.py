from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest
from unittest import mock

SCRIPT = Path(__file__).with_name("stale_green_bootstrap.py")
SPEC = importlib.util.spec_from_file_location("stale_green_bootstrap_poll_order", SCRIPT)
assert SPEC and SPEC.loader
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)


def pr(number: int, *, head: str, branch: str) -> dict:
    return {
        "number": number,
        "state": "open",
        "created_at": "2026-09-15T16:00:00Z",
        "closed_at": None,
        "head": {
            "sha": head,
            "ref": branch,
            "repo": {"full_name": "o/r"},
        },
    }


def direct_check(head: str, conclusion: str = "success") -> dict:
    return {
        "id": 900,
        "name": bootstrap.REQUIRED_GATE_JOB_NAME,
        "head_sha": head,
        "status": "completed",
        "conclusion": conclusion,
        "app": {"id": bootstrap.GITHUB_ACTIONS_APP_ID, "slug": "github-actions"},
    }


def target_run(*, run_id: int, head: str, branch: str) -> dict:
    return {
        "workflow_id": bootstrap.CANONICAL_WORKFLOW_ID,
        "path": bootstrap.CANONICAL_WORKFLOW_PATH,
        "event": "pull_request",
        "head_sha": head,
        "head_branch": branch,
        "head_repository": {"full_name": "o/r"},
        "run_number": run_id,
        "run_attempt": 1,
        "id": run_id,
        "status": "completed",
        "conclusion": "success",
        "created_at": "2026-09-15T16:01:00Z",
        "updated_at": "2026-09-15T16:02:00Z",
        "pull_requests": [],
    }


class PollOrderingTests(unittest.TestCase):
    def test_target_history_is_discovered_only_after_stale_green_is_proven(self) -> None:
        current = pr(4, head="h", branch="feature")
        identity = ("o/r", "feature", "h")
        run = target_run(run_id=44, head="h", branch="feature")
        events: list[str] = []

        def latest_check(repo: str, head: str, token: str) -> dict:
            self.assertEqual((repo, head, token), ("o/r", "h", "t"))
            events.append("check")
            return direct_check(head)

        def threads(repo: str, number: int, token: str) -> bool:
            self.assertEqual((repo, number, token), ("o/r", 4, "t"))
            events.append("threads")
            return True

        def overlap(repo: str, token: str, current_prs: dict) -> dict:
            self.assertEqual(events, ["check", "threads"])
            self.assertEqual((repo, token), ("o/r", "t"))
            self.assertEqual(list(current_prs), [identity])
            events.append("overlap")
            return {identity: []}

        def runs(repo: str, token: str, current_prs: dict, windows: dict, *, active_prs: dict) -> dict:
            self.assertEqual(events, ["check", "threads", "overlap"])
            self.assertEqual((repo, token), ("o/r", "t"))
            self.assertEqual(list(current_prs), [identity])
            self.assertEqual(list(active_prs), [identity])
            self.assertEqual(windows, {identity: []})
            events.append("runs")
            return {identity: run}

        def target_job(repo: str, selected: dict, token: str) -> str:
            self.assertEqual(events, ["check", "threads", "overlap", "runs"])
            self.assertIs(selected, run)
            events.append("job")
            return "success"

        def rerun(repo: str, run_id: int, token: str) -> None:
            self.assertEqual(events, ["check", "threads", "overlap", "runs", "job"])
            self.assertEqual((repo, run_id, token), ("o/r", 44, "t"))
            events.append("rerun")

        with mock.patch.object(bootstrap, "open_pull_requests", return_value=[current]), mock.patch.object(
            bootstrap, "latest_required_check", side_effect=latest_check
        ), mock.patch.object(
            bootstrap, "unresolved_review_threads", side_effect=threads
        ), mock.patch.object(
            bootstrap, "overlapping_closed_pr_windows", side_effect=overlap
        ), mock.patch.object(
            bootstrap, "latest_completed_gate_runs", side_effect=runs
        ), mock.patch.object(
            bootstrap, "required_merge_gate_conclusion", side_effect=target_job
        ), mock.patch.object(
            bootstrap, "rerun_workflow", side_effect=rerun
        ):
            self.assertEqual(bootstrap.poll("o/r", "t"), [44])

        self.assertEqual(events, ["check", "threads", "overlap", "runs", "job", "rerun"])

    def test_clean_or_non_merge_acceptable_prs_do_not_trigger_target_history(self) -> None:
        clean = pr(4, head="clean", branch="clean")
        blocked = pr(5, head="blocked", branch="blocked")

        def check(_repo: str, head: str, _token: str) -> dict:
            if head == "clean":
                return direct_check(head, "success")
            if head == "blocked":
                return direct_check(head, "failure")
            raise AssertionError(head)

        def threads(_repo: str, number: int, _token: str) -> bool:
            self.assertEqual(number, 4)
            return False

        with mock.patch.object(bootstrap, "open_pull_requests", return_value=[clean, blocked]), mock.patch.object(
            bootstrap, "latest_required_check", side_effect=check
        ), mock.patch.object(
            bootstrap, "unresolved_review_threads", side_effect=threads
        ) as thread_lookup, mock.patch.object(
            bootstrap, "overlapping_closed_pr_windows"
        ) as overlap, mock.patch.object(
            bootstrap, "latest_completed_gate_runs"
        ) as runs, mock.patch.object(
            bootstrap, "required_merge_gate_conclusion"
        ) as target_job, mock.patch.object(
            bootstrap, "rerun_workflow"
        ) as rerun:
            self.assertEqual(bootstrap.poll("o/r", "t"), [])

        thread_lookup.assert_called_once_with("o/r", 4, "t")
        overlap.assert_not_called()
        runs.assert_not_called()
        target_job.assert_not_called()
        rerun.assert_not_called()


if __name__ == "__main__":
    unittest.main()
