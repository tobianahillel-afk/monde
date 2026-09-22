from __future__ import annotations

import unittest
from unittest import mock

from test_stale_green_bootstrap_pr_snapshot import gate_run, pr, snapshot


class ProgressFallthroughTests(unittest.TestCase):
    def test_clean_shared_head_falls_through_to_next_head(self) -> None:
        first = pr(1, branch="first", head="head-1")
        second = pr(2, branch="second", head="head-2")
        first_run = gate_run(401, 1, branch="first", head="head-1")
        second_run = gate_run(402, 2, branch="second", head="head-2")

        def latest_runs(_repo: str, _token: str, by_number: dict[int, dict]) -> dict[int, dict]:
            number = next(iter(by_number))
            return {number: first_run if number == 1 else second_run}

        with (
            mock.patch.object(snapshot, "_fairness_slot", return_value=0),
            mock.patch.object(
                snapshot,
                "open_pull_requests",
                side_effect=[[first, second], [first, second], [first, second]],
            ),
            mock.patch.object(
                snapshot.core,
                "latest_required_check",
                return_value={"status": "completed", "conclusion": "success"},
            ),
            mock.patch.object(snapshot, "_latest_runs_by_pr", side_effect=latest_runs),
            mock.patch.object(snapshot.core, "required_merge_gate_conclusion", return_value="success"),
            mock.patch.object(snapshot.core, "unresolved_review_threads", side_effect=[False, True]),
            mock.patch.object(snapshot.core, "rerun_workflow") as rerun,
        ):
            self.assertEqual(snapshot.poll("o/r", "t"), [402])

        rerun.assert_called_once_with("o/r", 402, "t")


if __name__ == "__main__":
    unittest.main()
