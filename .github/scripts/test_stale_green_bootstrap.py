from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest
from unittest import mock

SCRIPT = Path(__file__).with_name("stale_green_bootstrap.py")
SPEC = importlib.util.spec_from_file_location("stale_green_bootstrap", SCRIPT)
assert SPEC and SPEC.loader
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)


class BootstrapPollTests(unittest.TestCase):
    def test_latest_gate_runs_includes_review_family_and_excludes_other_runs(self) -> None:
        rows = [
            {"name": "MONDE Gate", "event": "pull_request", "head_sha": "h", "run_number": 1, "id": 10},
            {"name": "MONDE Gate", "event": "pull_request_review", "head_sha": "h", "run_number": 2, "id": 20},
            {"name": "MONDE Gate", "event": "pull_request_review_comment", "head_sha": "c", "run_number": 3, "id": 30},
            {"name": "MONDE Gate", "event": "push", "head_sha": "h", "run_number": 99, "id": 99},
            {"name": "Other", "event": "pull_request_review", "head_sha": "h", "run_number": 100, "id": 100},
        ]
        with mock.patch.object(bootstrap, "paged", return_value=rows) as paged:
            latest = bootstrap.latest_completed_gate_runs("o/r", "t")
        self.assertEqual(latest["h"]["id"], 20)
        self.assertEqual(latest["c"]["id"], 30)
        self.assertNotIn("event=pull_request", paged.call_args.args[0])

    def test_poll_reruns_latest_success_when_thread_is_unresolved(self) -> None:
        prs = [{"number": 2, "head": {"sha": "h"}}]
        runs = {"h": {"id": 20, "conclusion": "success"}}
        with mock.patch.object(bootstrap, "open_pull_requests", return_value=prs), \
             mock.patch.object(bootstrap, "latest_completed_gate_runs", return_value=runs), \
             mock.patch.object(bootstrap, "unresolved_review_threads", return_value=True), \
             mock.patch.object(bootstrap, "rerun_workflow") as rerun:
            self.assertEqual(bootstrap.poll("o/r", "t"), [20])
        rerun.assert_called_once_with("o/r", 20, "t")

    def test_poll_ignores_failed_or_clean_heads(self) -> None:
        prs = [
            {"number": 1, "head": {"sha": "failed"}},
            {"number": 2, "head": {"sha": "clean"}},
        ]
        runs = {
            "failed": {"id": 1, "conclusion": "failure"},
            "clean": {"id": 2, "conclusion": "success"},
        }
        with mock.patch.object(bootstrap, "open_pull_requests", return_value=prs), \
             mock.patch.object(bootstrap, "latest_completed_gate_runs", return_value=runs), \
             mock.patch.object(bootstrap, "unresolved_review_threads", return_value=False), \
             mock.patch.object(bootstrap, "rerun_workflow") as rerun:
            self.assertEqual(bootstrap.poll("o/r", "t"), [])
        rerun.assert_not_called()

    def test_main_fails_closed_without_environment(self) -> None:
        with mock.patch.dict(bootstrap.os.environ, {}, clear=True):
            self.assertEqual(bootstrap.main(), 2)


if __name__ == "__main__":
    unittest.main()
