from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest
from unittest import mock

SCRIPT = Path(__file__).with_name("stale_green_bootstrap.py")
SPEC = importlib.util.spec_from_file_location("stale_green_bootstrap_merge_acceptable", SCRIPT)
assert SPEC and SPEC.loader
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)


def current_pr() -> dict:
    return {
        "number": 4,
        "state": "open",
        "created_at": "2026-09-15T16:00:00Z",
        "closed_at": None,
        "head": {
            "sha": "h",
            "ref": "feature",
            "repo": {"full_name": "o/r"},
        },
    }


def effective_run(conclusion: str) -> dict:
    return {
        "id": 4,
        "run_number": 4,
        "updated_at": "2026-09-15T16:05:00Z",
        "conclusion": conclusion,
    }


class MergeAcceptableConclusionTests(unittest.TestCase):
    def test_all_github_merge_acceptable_conclusions_revalidate_unresolved_threads(self) -> None:
        self.assertEqual(bootstrap.MERGE_ACCEPTABLE_CONCLUSIONS, {"success", "neutral", "skipped"})
        identity = ("o/r", "feature", "h")
        pr = current_pr()

        for conclusion in sorted(bootstrap.MERGE_ACCEPTABLE_CONCLUSIONS):
            runs = {identity: effective_run(conclusion)}
            with self.subTest(conclusion=conclusion), mock.patch.object(
                bootstrap, "open_pull_requests", return_value=[pr]
            ), mock.patch.object(
                bootstrap, "overlapping_closed_pr_windows", return_value={}
            ), mock.patch.object(
                bootstrap, "latest_completed_gate_runs", return_value=runs
            ), mock.patch.object(
                bootstrap, "unresolved_review_threads", return_value=True
            ) as threads, mock.patch.object(
                bootstrap, "rerun_workflow"
            ) as rerun:
                self.assertEqual(bootstrap.poll("o/r", "t"), [4])
            threads.assert_called_once_with("o/r", 4, "t")
            rerun.assert_called_once_with("o/r", 4, "t")


if __name__ == "__main__":
    unittest.main()
