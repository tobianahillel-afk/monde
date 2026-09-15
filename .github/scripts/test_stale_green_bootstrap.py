from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import runpy
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


class Response:
    def __init__(self, raw: bytes, status: int = 200):
        self.raw = raw
        self.status = status
    def __enter__(self):
        return self
    def __exit__(self, *_args):
        return False
    def read(self):
        return self.raw


class BootstrapPollTests(unittest.TestCase):
    def test_request_data_get_post_and_empty_body(self) -> None:
        seen = []
        responses = iter([Response(b'{"ok": true}'), Response(b"")])
        def fake_urlopen(request, timeout):
            seen.append((request, timeout))
            return next(responses)
        with mock.patch.object(bootstrap.urllib.request, "urlopen", side_effect=fake_urlopen):
            self.assertEqual(bootstrap.request_data("https://example.invalid/a", "tok"), {"ok": True})
            self.assertEqual(bootstrap.request_data("https://example.invalid/b", "tok", "POST", {"x": 1}), {})
        self.assertEqual(seen[0][0].method, "GET")
        self.assertIsNone(seen[0][0].data)
        self.assertEqual(seen[1][0].method, "POST")
        self.assertEqual(json.loads(seen[1][0].data.decode()), {"x": 1})
        self.assertEqual(seen[0][1], 20)

    def test_paged_list_collection_multiple_pages_and_query_separator(self) -> None:
        first = [{"id": i} for i in range(100)]
        with mock.patch.object(bootstrap, "request_data", side_effect=[first, [{"id": 100}]]) as req:
            self.assertEqual(len(bootstrap.paged("https://example.invalid/items", "t")), 101)
            calls = [call.args[0] for call in req.call_args_list]
        self.assertIn("?per_page=100&page=1", calls[0])
        self.assertIn("?per_page=100&page=2", calls[1])

        with mock.patch.object(bootstrap, "request_data", return_value={"workflow_runs": [{"id": 1}]}) as req:
            self.assertEqual(bootstrap.paged("https://example.invalid/runs?status=completed", "t", "workflow_runs"), [{"id": 1}])
        self.assertIn("&per_page=100&page=1", req.call_args.args[0])

    def test_paged_rejects_malformed_and_unbounded_collections(self) -> None:
        for payload in ([{"id": 1}, None], {"wrong": []}, "bad"):
            with self.subTest(payload=payload), mock.patch.object(bootstrap, "request_data", return_value=payload):
                with self.assertRaisesRegex(RuntimeError, "malformed paginated JSON"):
                    bootstrap.paged("https://example.invalid/items", "t", "workflow_runs" if not isinstance(payload, list) else None)
        with mock.patch.object(bootstrap, "MAX_PAGES", 1), mock.patch.object(bootstrap, "request_data", return_value=[{} for _ in range(100)]):
            with self.assertRaisesRegex(RuntimeError, "pagination exceeded"):
                bootstrap.paged("https://example.invalid/items", "t")

    def test_open_pull_requests_validates_required_fields(self) -> None:
        with mock.patch.object(bootstrap, "paged", return_value=[{"number": 2, "head": {"sha": "h"}}]):
            self.assertEqual(bootstrap.open_pull_requests("o/r", "t")[0]["number"], 2)
        for bad in (
            {"number": "2", "head": {"sha": "h"}},
            {"number": 2, "head": {}},
            {"number": 2, "head": "bad"},
            {"number": 2, "head": {"sha": ""}},
        ):
            with self.subTest(bad=bad), mock.patch.object(bootstrap, "paged", return_value=[bad]):
                with self.assertRaisesRegex(RuntimeError, "malformed open pull request"):
                    bootstrap.open_pull_requests("o/r", "t")

    def test_latest_gate_runs_scope_to_canonical_workflow_and_review_family(self) -> None:
        rows = [
            gate_run(event="pull_request", head="h", run_number=1, run_id=10),
            gate_run(event="pull_request_review", head="h", run_number=2, run_id=20),
            gate_run(event="pull_request", head="h", run_number=1, run_id=11),
            gate_run(event="pull_request_review_comment", head="c", run_number=3, run_id=30),
            gate_run(event="push", head="ignored", run_number=99, run_id=99),
        ]
        with mock.patch.object(bootstrap, "paged", return_value=rows) as paged:
            latest = bootstrap.latest_completed_gate_runs("o/r", "t")
        self.assertEqual(latest["h"]["id"], 20)
        self.assertEqual(latest["c"]["id"], 30)
        self.assertNotIn("ignored", latest)
        self.assertIn(f"actions/workflows/{bootstrap.CANONICAL_WORKFLOW_ID}/runs?status=completed", paged.call_args.args[0])

    def test_latest_gate_runs_rejects_wrong_identity_and_malformed_run(self) -> None:
        for bad in (
            gate_run(event="pull_request", head="h", run_number=1, run_id=10, workflow_id=999),
            gate_run(event="pull_request", head="h", run_number=1, run_id=10, path=".github/workflows/impostor.yml"),
        ):
            with self.subTest(bad=bad), mock.patch.object(bootstrap, "paged", return_value=[bad]):
                with self.assertRaisesRegex(RuntimeError, "mismatched workflow identity"):
                    bootstrap.latest_completed_gate_runs("o/r", "t")
        malformed = gate_run(event="pull_request", head="h", run_number=1, run_id=10)
        malformed["id"] = "not-int"
        with mock.patch.object(bootstrap, "paged", return_value=[malformed]):
            with self.assertRaisesRegex(RuntimeError, "malformed canonical MONDE Gate run"):
                bootstrap.latest_completed_gate_runs("o/r", "t")

    def test_review_threads_false_true_and_pagination(self) -> None:
        false_payload = {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [{"isResolved": True}], "pageInfo": {"hasNextPage": False, "endCursor": None}}}}}}
        with mock.patch.object(bootstrap, "request_data", return_value=false_payload):
            self.assertFalse(bootstrap.unresolved_review_threads("o/r", 2, "t"))

        true_payload = {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [{"isResolved": False}], "pageInfo": {"hasNextPage": False, "endCursor": None}}}}}}
        with mock.patch.object(bootstrap, "request_data", return_value=true_payload):
            self.assertTrue(bootstrap.unresolved_review_threads("o/r", 2, "t"))

        page1 = {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [{"isResolved": True}], "pageInfo": {"hasNextPage": True, "endCursor": "next"}}}}}}
        page2 = false_payload
        with mock.patch.object(bootstrap, "request_data", side_effect=[page1, page2]) as req:
            self.assertFalse(bootstrap.unresolved_review_threads("o/r", 2, "t"))
        self.assertEqual(req.call_count, 2)

    def test_review_threads_fail_closed_on_response_shape(self) -> None:
        payloads = [
            ["not-object"],
            {"errors": [{"message": "bad"}]},
            {"data": {}},
            {"data": {"repository": {"pullRequest": {"reviewThreads": []}}}},
        ]
        for payload in payloads:
            with self.subTest(payload=payload), mock.patch.object(bootstrap, "request_data", return_value=payload):
                with self.assertRaises(RuntimeError):
                    bootstrap.unresolved_review_threads("o/r", 2, "t")

        bad_node = {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [{}], "pageInfo": {"hasNextPage": False}}}}}}
        with mock.patch.object(bootstrap, "request_data", return_value=bad_node):
            with self.assertRaisesRegex(RuntimeError, "malformed reviewThreads nodes"):
                bootstrap.unresolved_review_threads("o/r", 2, "t")

        bad_info = {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [], "pageInfo": {}}}}}}
        with mock.patch.object(bootstrap, "request_data", return_value=bad_info):
            with self.assertRaisesRegex(RuntimeError, "malformed reviewThreads pageInfo"):
                bootstrap.unresolved_review_threads("o/r", 2, "t")

        bad_cursor = {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [], "pageInfo": {"hasNextPage": True, "endCursor": None}}}}}}
        with mock.patch.object(bootstrap, "request_data", return_value=bad_cursor):
            with self.assertRaisesRegex(RuntimeError, "pagination missing cursor"):
                bootstrap.unresolved_review_threads("o/r", 2, "t")

    def test_rerun_workflow_posts_to_exact_run(self) -> None:
        with mock.patch.object(bootstrap, "request_data", return_value={}) as req:
            bootstrap.rerun_workflow("o/r", 123, "t")
        self.assertEqual(req.call_args.args, ("https://api.github.com/repos/o/r/actions/runs/123/rerun", "t", "POST", {}))

    def test_poll_reruns_only_stale_success(self) -> None:
        prs = [
            {"number": 1, "head": {"sha": "missing"}},
            {"number": 2, "head": {"sha": "failed"}},
            {"number": 3, "head": {"sha": "clean"}},
            {"number": 4, "head": {"sha": "stale"}},
        ]
        runs = {
            "failed": gate_run(event="pull_request", head="failed", run_number=1, run_id=1, conclusion="failure"),
            "clean": gate_run(event="pull_request_review", head="clean", run_number=2, run_id=2),
            "stale": gate_run(event="pull_request_review", head="stale", run_number=3, run_id=3),
        }
        with mock.patch.object(bootstrap, "open_pull_requests", return_value=prs), \
             mock.patch.object(bootstrap, "latest_completed_gate_runs", return_value=runs), \
             mock.patch.object(bootstrap, "unresolved_review_threads", side_effect=lambda _repo, n, _token: n == 4), \
             mock.patch.object(bootstrap, "rerun_workflow") as rerun:
            self.assertEqual(bootstrap.poll("o/r", "t"), [3])
        rerun.assert_called_once_with("o/r", 3, "t")

    def test_validate_github_contract(self) -> None:
        prs = [{"number": 5, "head": {"sha": "h"}}, {"number": 2, "head": {"sha": "x"}}]
        with mock.patch.object(bootstrap, "open_pull_requests", return_value=prs), \
             mock.patch.object(bootstrap, "latest_completed_gate_runs", return_value={"x": {}}), \
             mock.patch.object(bootstrap, "unresolved_review_threads", return_value=True):
            self.assertEqual(bootstrap.validate_github_contract("o/r", 5, "t"), (2, 1, True))
        with mock.patch.object(bootstrap, "open_pull_requests", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "exactly one open PR"):
                bootstrap.validate_github_contract("o/r", 5, "t")

    def test_main_missing_env_poll_success_and_error(self) -> None:
        with mock.patch.dict(bootstrap.os.environ, {}, clear=True):
            self.assertEqual(bootstrap.main(), 2)
        with mock.patch.dict(bootstrap.os.environ, {"GITHUB_REPOSITORY": "o/r", "GITHUB_TOKEN": "t"}, clear=True), \
             mock.patch.object(bootstrap, "poll", return_value=[1, 2]):
            self.assertEqual(bootstrap.main(), 0)
        with mock.patch.dict(bootstrap.os.environ, {"GITHUB_REPOSITORY": "o/r", "GITHUB_TOKEN": "t"}, clear=True), \
             mock.patch.object(bootstrap, "poll", side_effect=RuntimeError("boom")):
            self.assertEqual(bootstrap.main(), 2)

    def test_main_validation_mode_success_and_invalid_number(self) -> None:
        env = {"GITHUB_REPOSITORY": "o/r", "GITHUB_TOKEN": "t", "BOOTSTRAP_VALIDATE_PR": "5"}
        with mock.patch.dict(bootstrap.os.environ, env, clear=True), \
             mock.patch.object(bootstrap, "validate_github_contract", return_value=(2, 3, False)) as validate:
            self.assertEqual(bootstrap.main(), 0)
        validate.assert_called_once_with("o/r", 5, "t")

        for value in ("0", "not-int"):
            with self.subTest(value=value), mock.patch.dict(bootstrap.os.environ, {**env, "BOOTSTRAP_VALIDATE_PR": value}, clear=True):
                self.assertEqual(bootstrap.main(), 2)

    def test_script_entrypoint_exits_through_main(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(SystemExit) as ctx:
                runpy.run_path(str(SCRIPT), run_name="__main__")
        self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
