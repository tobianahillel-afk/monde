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


def gate_run(*, event: str, head: str, run_number: int, run_id: int, conclusion: str = "success", workflow_id: int | None = None, path: str | None = None):
    return {
        "workflow_id": bootstrap.CANONICAL_WORKFLOW_ID if workflow_id is None else workflow_id,
        "path": bootstrap.CANONICAL_WORKFLOW_PATH if path is None else path,
        "event": event,
        "head_sha": head,
        "run_number": run_number,
        "id": run_id,
        "conclusion": conclusion,
    }


class BootstrapPollTests(unittest.TestCase):
    def test_paged_rejects_non_object_collection_members(self) -> None:
        with mock.patch.object(bootstrap, "request_data", return_value=[{"id": 1}, None]):
            with self.assertRaisesRegex(RuntimeError, "malformed paginated JSON"):
                bootstrap.paged("https://example.invalid/items", "t")

    def test_open_pull_requests_validates_required_fields(self) -> None:
        with mock.patch.object(bootstrap, "paged", return_value=[{"number": 2, "head": {"sha": "h"}}]):
            self.assertEqual(bootstrap.open_pull_requests("o/r", "t")[0]["number"], 2)
        for bad in ({"number": "2", "head": {"sha": "h"}}, {"number": 2, "head": {}}, {"number": 2, "head": "bad"}):
            with self.subTest(bad=bad), mock.patch.object(bootstrap, "paged", return_value=[bad]):
                with self.assertRaisesRegex(RuntimeError, "malformed open pull request"):
                    bootstrap.open_pull_requests("o/r", "t")

    def test_latest_gate_runs_bind_stable_workflow_identity_and_review_family(self) -> None:
        rows = [
            gate_run(event="pull_request", head="h", run_number=1, run_id=10),
            gate_run(event="pull_request_review", head="h", run_number=2, run_id=20),
            gate_run(event="pull_request_review_comment", head="c", run_number=3, run_id=30),
            gate_run(event="push", head="h", run_number=99, run_id=99),
            gate_run(event="pull_request_review", head="h", run_number=100, run_id=100, workflow_id=999),
            gate_run(event="pull_request_review", head="h", run_number=101, run_id=101, path=".github/workflows/impostor.yml"),
        ]
        with mock.patch.object(bootstrap, "paged", return_value=rows) as paged:
            latest = bootstrap.latest_completed_gate_runs("o/r", "t")
        self.assertEqual(latest["h"]["id"], 20)
        self.assertEqual(latest["c"]["id"], 30)
        self.assertIn("actions/runs?status=completed", paged.call_args.args[0])

    def test_latest_gate_runs_rejects_malformed_canonical_run(self) -> None:
        bad = gate_run(event="pull_request", head="h", run_number=1, run_id=10)
        bad["id"] = "not-int"
        with mock.patch.object(bootstrap, "paged", return_value=[bad]):
            with self.assertRaisesRegex(RuntimeError, "malformed canonical MONDE Gate run"):
                bootstrap.latest_completed_gate_runs("o/r", "t")

    def test_review_threads_fail_closed_on_bad_nodes_and_page_info(self) -> None:
        good = {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [{"isResolved": True}], "pageInfo": {"hasNextPage": False, "endCursor": None}}}}}}
        with mock.patch.object(bootstrap, "request_data", return_value=good):
            self.assertFalse(bootstrap.unresolved_review_threads("o/r", 2, "t"))

        bad_node = {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [{}], "pageInfo": {"hasNextPage": False}}}}}}
        with mock.patch.object(bootstrap, "request_data", return_value=bad_node):
            with self.assertRaisesRegex(RuntimeError, "malformed reviewThreads nodes"):
                bootstrap.unresolved_review_threads("o/r", 2, "t")

        bad_info = {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [], "pageInfo": {}}}}}}
        with mock.patch.object(bootstrap, "request_data", return_value=bad_info):
            with self.assertRaisesRegex(RuntimeError, "malformed reviewThreads pageInfo"):
                bootstrap.unresolved_review_threads("o/r", 2, "t")

    def test_review_threads_require_cursor_when_pagination_continues(self) -> None:
        bad = {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [], "pageInfo": {"hasNextPage": True, "endCursor": None}}}}}}
        with mock.patch.object(bootstrap, "request_data", return_value=bad):
            with self.assertRaisesRegex(RuntimeError, "pagination missing cursor"):
                bootstrap.unresolved_review_threads("o/r", 2, "t")

    def test_poll_reruns_latest_success_when_thread_is_unresolved(self) -> None:
        prs = [{"number": 2, "head": {"sha": "h"}}]
        runs = {"h": gate_run(event="pull_request_review", head="h", run_number=2, run_id=20)}
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
            "failed": gate_run(event="pull_request", head="failed", run_number=1, run_id=1, conclusion="failure"),
            "clean": gate_run(event="pull_request", head="clean", run_number=1, run_id=2),
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
