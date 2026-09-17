from __future__ import annotations

import unittest
from unittest import mock

from test_stale_green_bootstrap_pr_snapshot import gate_run, pr, snapshot


class ProgressSchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        snapshot._reset_request_budget()
        self.addCleanup(snapshot._reset_request_budget)

    def test_fair_head_groups_rotate_without_splitting_shared_heads(self) -> None:
        shared_a = pr(1, branch="shared", head="shared-head")
        shared_b = pr(2, branch="shared", head="shared-head")
        third = pr(3, branch="third", head="head-3")
        fourth = pr(4, branch="fourth", head="head-4")

        groups = snapshot._fair_head_groups([fourth, shared_b, third, shared_a], 1)
        self.assertEqual([[item["number"] for item in group] for group in groups], [[3], [4], [1, 2]])
        self.assertEqual(snapshot._fair_head_groups([], 5), [])

    def test_fourteen_stale_heads_make_progress_before_budget_exhaustion(self) -> None:
        prs = [pr(number, branch=f"branch-{number}", head=f"head-{number}") for number in range(1, 15)]
        rerun_request_counts: list[int] = []

        def spend(amount: int) -> None:
            snapshot._request_count += amount
            self.assertLessEqual(snapshot._request_count, snapshot.MAX_GITHUB_REQUESTS_PER_INVOCATION)

        def open_prs(_repo: str, _token: str) -> list[dict]:
            spend(2)
            return prs

        def latest_check(_repo: str, _head: str, _token: str) -> dict:
            spend(1)
            return {"status": "completed", "conclusion": "success"}

        def latest_runs(_repo: str, _token: str, by_number: dict[int, dict]) -> dict[int, dict]:
            spend(2)
            number, current = next(iter(by_number.items()))
            identity = snapshot.core._pr_head_identity(current)
            return {
                number: gate_run(
                    100 + number,
                    number,
                    branch=identity[1],
                    head=identity[2],
                )
            }

        def required_job(_repo: str, _run: dict, _token: str) -> str:
            spend(1)
            return "success"

        def unresolved(_repo: str, _number: int, _token: str) -> bool:
            spend(1)
            return True

        def rerun(_repo: str, _run_id: int, _token: str) -> None:
            spend(1)
            rerun_request_counts.append(snapshot._request_count)

        with (
            mock.patch.object(snapshot, "_fairness_slot", return_value=0),
            mock.patch.object(snapshot, "open_pull_requests", side_effect=open_prs),
            mock.patch.object(snapshot.core, "latest_required_check", side_effect=latest_check),
            mock.patch.object(snapshot, "_latest_runs_by_pr", side_effect=latest_runs),
            mock.patch.object(snapshot.core, "required_merge_gate_conclusion", side_effect=required_job),
            mock.patch.object(snapshot.core, "unresolved_review_threads", side_effect=unresolved),
            mock.patch.object(snapshot.core, "rerun_workflow", side_effect=rerun),
        ):
            self.assertEqual(snapshot.poll("o/r", "t"), [101, 102, 103])

        self.assertEqual(rerun_request_counts, [10, 18, 26])
        self.assertLess(snapshot._request_count, snapshot.MAX_GITHUB_REQUESTS_PER_INVOCATION)

    def test_shared_head_uses_current_thread_state_and_never_reruns_clean_sibling(self) -> None:
        first = pr(1, branch="shared", head="shared-head")
        second = pr(2, branch="shared", head="shared-head")
        first_run = gate_run(201, 1)
        second_run = gate_run(202, 2)

        with (
            mock.patch.object(snapshot, "_fairness_slot", return_value=0),
            mock.patch.object(snapshot, "open_pull_requests", side_effect=[[first, second], [first, second]]),
            mock.patch.object(
                snapshot.core,
                "latest_required_check",
                return_value={"status": "completed", "conclusion": "success"},
            ),
            mock.patch.object(snapshot, "_latest_runs_by_pr", return_value={1: first_run, 2: second_run}),
            mock.patch.object(snapshot.core, "required_merge_gate_conclusion", return_value="success") as jobs,
            mock.patch.object(snapshot.core, "unresolved_review_threads", side_effect=[False, True]) as threads,
            mock.patch.object(snapshot.core, "rerun_workflow") as rerun,
        ):
            self.assertEqual(snapshot.poll("o/r", "t"), [202])

        self.assertEqual(jobs.call_count, 2)
        self.assertEqual([call.args[1] for call in threads.call_args_list], [1, 2])
        rerun.assert_called_once_with("o/r", 202, "t")

    def test_clean_missing_target_does_not_block_unresolved_sibling(self) -> None:
        first = pr(1, branch="shared", head="shared-head")
        second = pr(2, branch="shared", head="shared-head")
        second_run = gate_run(302, 2)

        with (
            mock.patch.object(snapshot, "_fairness_slot", return_value=0),
            mock.patch.object(snapshot, "open_pull_requests", side_effect=[[first, second], [first, second]]),
            mock.patch.object(
                snapshot.core,
                "latest_required_check",
                return_value={"status": "completed", "conclusion": "success"},
            ),
            mock.patch.object(snapshot, "_latest_runs_by_pr", return_value={2: second_run}),
            mock.patch.object(snapshot.core, "required_merge_gate_conclusion", return_value="success"),
            mock.patch.object(snapshot.core, "unresolved_review_threads", side_effect=[False, True]),
            mock.patch.object(snapshot.core, "rerun_workflow") as rerun,
        ):
            self.assertEqual(snapshot.poll("o/r", "t"), [302])

        rerun.assert_called_once_with("o/r", 302, "t")

    def test_head_batch_is_bounded_even_when_every_check_is_non_mergeable(self) -> None:
        prs = [pr(number, branch=f"branch-{number}", head=f"head-{number}") for number in range(1, 15)]
        with (
            mock.patch.object(snapshot, "_fairness_slot", return_value=0),
            mock.patch.object(snapshot, "open_pull_requests", return_value=prs),
            mock.patch.object(
                snapshot.core,
                "latest_required_check",
                return_value={"status": "completed", "conclusion": "failure"},
            ) as checks,
            mock.patch.object(snapshot, "_latest_runs_by_pr") as runs,
        ):
            self.assertEqual(snapshot.poll("o/r", "t"), [])

        self.assertEqual(checks.call_count, snapshot.MAX_HEADS_PER_INVOCATION)
        runs.assert_not_called()


if __name__ == "__main__":
    unittest.main()
