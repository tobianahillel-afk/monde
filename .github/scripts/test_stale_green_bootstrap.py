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


def pull_request(
    number: int,
    head: str,
    *,
    branch: str | None = None,
    repo_name: str = "o/r",
    created_at: str = "2026-09-15T14:00:00Z",
    state: str = "open",
    closed_at: str | None = None,
):
    return {
        "number": number,
        "state": state,
        "created_at": created_at,
        "closed_at": closed_at,
        "head": {
            "sha": head,
            "ref": branch or f"branch-{number}",
            "repo": {"full_name": repo_name},
        },
    }


def gate_run(
    *,
    event,
    head: str,
    run_number: int,
    run_id: int,
    conclusion: str = "success",
    workflow_id: int | None = None,
    path: str | None = None,
    branch: str = "branch-2",
    repo_name: str = "o/r",
    created_at: str | None = None,
    updated_at: str | None = None,
    pull_requests=None,
):
    return {
        "workflow_id": bootstrap.CANONICAL_WORKFLOW_ID if workflow_id is None else workflow_id,
        "path": bootstrap.CANONICAL_WORKFLOW_PATH if path is None else path,
        "event": event,
        "head_sha": head,
        "head_branch": branch,
        "head_repository": {"full_name": repo_name},
        "run_number": run_number,
        "id": run_id,
        "conclusion": conclusion,
        "created_at": created_at or f"2026-09-15T14:30:{run_id % 60:02d}Z",
        "updated_at": updated_at or f"2026-09-15T15:00:{run_id % 60:02d}Z",
        "pull_requests": [] if pull_requests is None else pull_requests,
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
            self.assertEqual(
                bootstrap.paged("https://example.invalid/runs?status=completed", "t", "workflow_runs"),
                [{"id": 1}],
            )
        self.assertIn("&per_page=100&page=1", req.call_args.args[0])

    def test_paged_rejects_malformed_and_unbounded_collections(self) -> None:
        for payload in ([{"id": 1}, None], {"wrong": []}, "bad"):
            with self.subTest(payload=payload), mock.patch.object(bootstrap, "request_data", return_value=payload):
                with self.assertRaisesRegex(RuntimeError, "malformed paginated JSON"):
                    bootstrap.paged(
                        "https://example.invalid/items",
                        "t",
                        "workflow_runs" if not isinstance(payload, list) else None,
                    )
        with mock.patch.object(bootstrap, "MAX_PAGES", 1), mock.patch.object(
            bootstrap, "request_data", return_value=[{} for _ in range(100)]
        ):
            with self.assertRaisesRegex(RuntimeError, "pagination exceeded"):
                bootstrap.paged("https://example.invalid/items", "t")

    def test_scalar_helpers(self) -> None:
        self.assertTrue(bootstrap._positive_int(1))
        for value in (True, False, 0, -1, "1", None):
            with self.subTest(value=value):
                self.assertFalse(bootstrap._positive_int(value))
        self.assertTrue(bootstrap._nonempty_string("x"))
        for value in ("", None, 1, False):
            with self.subTest(value=value):
                self.assertFalse(bootstrap._nonempty_string(value))

    def test_pr_head_identity_and_open_pr_validation(self) -> None:
        good = pull_request(2, "h", branch="feature", repo_name="owner/repo")
        self.assertEqual(bootstrap._pr_head_identity(good), ("owner/repo", "feature", "h"))
        with mock.patch.object(bootstrap, "paged", return_value=[good]):
            self.assertEqual(bootstrap.open_pull_requests("o/r", "t"), [good])

        malformed = [
            {"number": "2", "head": good["head"]},
            {"number": True, "head": good["head"]},
            {"number": 2, "head": "bad"},
            {"number": 2, "head": {"sha": "h", "ref": "feature", "repo": None}},
            {"number": 2, "head": {"sha": "", "ref": "feature", "repo": {"full_name": "o/r"}}},
            {"number": 2, "head": {"sha": "h", "ref": "", "repo": {"full_name": "o/r"}}},
            {"number": 2, "head": {"sha": "h", "ref": "feature", "repo": {"full_name": ""}}},
        ]
        for bad in malformed:
            with self.subTest(bad=bad), mock.patch.object(bootstrap, "paged", return_value=[bad]):
                with self.assertRaisesRegex(RuntimeError, "malformed .*pull request|malformed pull request"):
                    bootstrap.open_pull_requests("o/r", "t")

        same_identity = [pull_request(2, "same", branch="same"), pull_request(5, "same", branch="same")]
        with mock.patch.object(bootstrap, "paged", return_value=same_identity):
            with self.assertRaisesRegex(RuntimeError, "indistinguishable head identity"):
                bootstrap.open_pull_requests("o/r", "t")

    def test_run_head_identity_requires_server_head_metadata(self) -> None:
        good = gate_run(event="pull_request", head="h", run_number=1, run_id=1, branch="feature", repo_name="owner/repo")
        self.assertEqual(bootstrap._run_head_identity(good), ("owner/repo", "feature", "h"))
        for field, value in (
            ("head_repository", None),
            ("head_branch", ""),
            ("head_sha", ""),
        ):
            bad = dict(good)
            bad[field] = value
            with self.subTest(field=field):
                with self.assertRaisesRegex(RuntimeError, "malformed canonical MONDE Gate head identity"):
                    bootstrap._run_head_identity(bad)

    def test_updated_at_requires_valid_aware_timestamp(self) -> None:
        self.assertIsNotNone(bootstrap._updated_at("2026-09-15T15:00:00Z").tzinfo)
        for value in (None, "", "not-a-date", "2026-09-15T15:00:00"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(RuntimeError, "malformed canonical MONDE Gate updated_at"):
                    bootstrap._updated_at(value)

    def test_latest_gate_runs_bind_to_trusted_head_identity_not_association_list(self) -> None:
        rows = [
            gate_run(
                event="pull_request",
                head="shared",
                branch="alpha",
                run_number=1,
                run_id=10,
                pull_requests=[{"number": 2}, {"number": 5}],
            ),
            gate_run(
                event="pull_request_review",
                head="shared",
                branch="alpha",
                run_number=2,
                run_id=20,
                pull_requests=[],
            ),
            gate_run(
                event="pull_request_review_comment",
                head="shared",
                branch="beta",
                run_number=3,
                run_id=30,
                pull_requests=[{"number": 999}],
            ),
            gate_run(event="push", head="ignored", branch="main", run_number=99, run_id=99),
        ]
        with mock.patch.object(bootstrap, "paged", return_value=rows) as paged:
            latest = bootstrap.latest_completed_gate_runs("o/r", "t")
        self.assertEqual(latest[("o/r", "alpha", "shared")]["id"], 20)
        self.assertEqual(latest[("o/r", "beta", "shared")]["id"], 30)
        self.assertNotIn(("o/r", "main", "ignored"), latest)
        self.assertIn(
            f"actions/workflows/{bootstrap.CANONICAL_WORKFLOW_ID}/runs?status=completed",
            paged.call_args.args[0],
        )

    def test_latest_gate_runs_rejects_wrong_identity_malformed_event_run_time_and_head(self) -> None:
        for bad in (
            gate_run(event="pull_request", head="h", run_number=1, run_id=10, workflow_id=999),
            gate_run(event="pull_request", head="h", run_number=1, run_id=10, path=".github/workflows/impostor.yml"),
        ):
            with self.subTest(bad=bad), mock.patch.object(bootstrap, "paged", return_value=[bad]):
                with self.assertRaisesRegex(RuntimeError, "mismatched workflow identity"):
                    bootstrap.latest_completed_gate_runs("o/r", "t")

        malformed_event = gate_run(event=None, head="h", run_number=1, run_id=10)
        with mock.patch.object(bootstrap, "paged", return_value=[malformed_event]):
            with self.assertRaisesRegex(RuntimeError, "malformed canonical MONDE Gate event"):
                bootstrap.latest_completed_gate_runs("o/r", "t")

        for field, value in (
            ("id", "not-int"),
            ("id", True),
            ("run_number", True),
            ("conclusion", ""),
            ("conclusion", "mystery"),
        ):
            malformed = gate_run(event="pull_request", head="h", run_number=1, run_id=10)
            malformed[field] = value
            with self.subTest(field=field), mock.patch.object(bootstrap, "paged", return_value=[malformed]):
                with self.assertRaisesRegex(RuntimeError, "malformed canonical MONDE Gate run"):
                    bootstrap.latest_completed_gate_runs("o/r", "t")

        bad_time = gate_run(event="pull_request", head="h", run_number=1, run_id=10, updated_at="not-a-date")
        with mock.patch.object(bootstrap, "paged", return_value=[bad_time]):
            with self.assertRaisesRegex(RuntimeError, "malformed canonical MONDE Gate updated_at"):
                bootstrap.latest_completed_gate_runs("o/r", "t")

        bad_head = gate_run(event="pull_request", head="h", run_number=1, run_id=10)
        bad_head["head_repository"] = None
        with mock.patch.object(bootstrap, "paged", return_value=[bad_head]):
            with self.assertRaisesRegex(RuntimeError, "malformed canonical MONDE Gate head identity"):
                bootstrap.latest_completed_gate_runs("o/r", "t")

    def test_all_supported_terminal_conclusions_are_accepted(self) -> None:
        rows = [
            gate_run(
                event="pull_request",
                head=f"h-{index}",
                branch=f"b-{index}",
                run_number=index + 1,
                run_id=index + 1,
                conclusion=conclusion,
            )
            for index, conclusion in enumerate(sorted(bootstrap.TERMINAL_CONCLUSIONS))
        ]
        with mock.patch.object(bootstrap, "paged", return_value=rows):
            self.assertEqual(len(bootstrap.latest_completed_gate_runs("o/r", "t")), len(rows))

    def test_run_recency_replaces_only_with_newer_record(self) -> None:
        older = gate_run(
            event="pull_request",
            head="h",
            branch="feature",
            run_number=10,
            run_id=10,
            updated_at="2026-09-15T15:01:00Z",
        )
        newer = gate_run(
            event="pull_request_review",
            head="h",
            branch="feature",
            run_number=11,
            run_id=11,
            updated_at="2026-09-15T15:02:00Z",
        )
        stale_late_item = gate_run(
            event="pull_request",
            head="h",
            branch="feature",
            run_number=9,
            run_id=9,
            updated_at="2026-09-15T15:00:00Z",
        )
        with mock.patch.object(bootstrap, "paged", return_value=[older, newer, stale_late_item]):
            latest = bootstrap.latest_completed_gate_runs("o/r", "t")
        self.assertEqual(latest[("o/r", "feature", "h")]["id"], 11)

    def test_effective_shared_sha_uses_latest_run_across_distinct_heads(self) -> None:
        runs = {
            ("o/r", "alpha", "shared"): gate_run(
                event="pull_request",
                head="shared",
                branch="alpha",
                run_number=20,
                run_id=20,
                conclusion="failure",
                updated_at="2026-09-15T15:02:00Z",
            ),
            ("o/r", "beta", "shared"): gate_run(
                event="pull_request_review",
                head="shared",
                branch="beta",
                run_number=21,
                run_id=21,
                conclusion="success",
                updated_at="2026-09-15T15:01:00Z",
            ),
        }
        self.assertEqual(bootstrap.effective_gate_runs_by_head(runs)["shared"]["id"], 20)
        runs[("o/r", "beta", "shared")]["updated_at"] = "2026-09-15T15:03:00Z"
        self.assertEqual(bootstrap.effective_gate_runs_by_head(runs)["shared"]["id"], 21)

    def test_review_threads_false_true_and_pagination(self) -> None:
        false_payload = {
            "data": {"repository": {"pullRequest": {"reviewThreads": {
                "nodes": [{"isResolved": True}],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            }}}}
        }
        with mock.patch.object(bootstrap, "request_data", return_value=false_payload):
            self.assertFalse(bootstrap.unresolved_review_threads("o/r", 2, "t"))

        true_payload = {
            "data": {"repository": {"pullRequest": {"reviewThreads": {
                "nodes": [{"isResolved": False}],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            }}}}
        }
        with mock.patch.object(bootstrap, "request_data", return_value=true_payload):
            self.assertTrue(bootstrap.unresolved_review_threads("o/r", 2, "t"))

        page1 = {
            "data": {"repository": {"pullRequest": {"reviewThreads": {
                "nodes": [{"isResolved": True}],
                "pageInfo": {"hasNextPage": True, "endCursor": "next"},
            }}}}
        }
        with mock.patch.object(bootstrap, "request_data", side_effect=[page1, false_payload]) as req:
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

        bad_node = {
            "data": {"repository": {"pullRequest": {"reviewThreads": {
                "nodes": [{}], "pageInfo": {"hasNextPage": False}
            }}}}
        }
        with mock.patch.object(bootstrap, "request_data", return_value=bad_node):
            with self.assertRaisesRegex(RuntimeError, "malformed reviewThreads nodes"):
                bootstrap.unresolved_review_threads("o/r", 2, "t")

        bad_info = {
            "data": {"repository": {"pullRequest": {"reviewThreads": {
                "nodes": [], "pageInfo": {}
            }}}}
        }
        with mock.patch.object(bootstrap, "request_data", return_value=bad_info):
            with self.assertRaisesRegex(RuntimeError, "malformed reviewThreads pageInfo"):
                bootstrap.unresolved_review_threads("o/r", 2, "t")

        bad_cursor = {
            "data": {"repository": {"pullRequest": {"reviewThreads": {
                "nodes": [], "pageInfo": {"hasNextPage": True, "endCursor": None}
            }}}}
        }
        with mock.patch.object(bootstrap, "request_data", return_value=bad_cursor):
            with self.assertRaisesRegex(RuntimeError, "pagination missing cursor"):
                bootstrap.unresolved_review_threads("o/r", 2, "t")

    def test_review_threads_reject_repeated_cursor_and_page_exhaustion(self) -> None:
        repeated = {
            "data": {"repository": {"pullRequest": {"reviewThreads": {
                "nodes": [], "pageInfo": {"hasNextPage": True, "endCursor": "same"}
            }}}}
        }
        with mock.patch.object(bootstrap, "request_data", side_effect=[repeated, repeated]):
            with self.assertRaisesRegex(RuntimeError, "repeated cursor"):
                bootstrap.unresolved_review_threads("o/r", 2, "t")

        first = {
            "data": {"repository": {"pullRequest": {"reviewThreads": {
                "nodes": [], "pageInfo": {"hasNextPage": True, "endCursor": "next"}
            }}}}
        }
        with mock.patch.object(bootstrap, "MAX_PAGES", 1), mock.patch.object(
            bootstrap, "request_data", return_value=first
        ):
            with self.assertRaisesRegex(RuntimeError, "pagination exceeded"):
                bootstrap.unresolved_review_threads("o/r", 2, "t")

    def test_rerun_workflow_posts_to_exact_run(self) -> None:
        with mock.patch.object(bootstrap, "request_data", return_value={}) as req:
            bootstrap.rerun_workflow("o/r", 123, "t")
        self.assertEqual(
            req.call_args.args,
            ("https://api.github.com/repos/o/r/actions/runs/123/rerun", "t", "POST", {}),
        )

    def test_poll_reinvalidates_target_when_other_branch_has_newer_shared_sha_success(self) -> None:
        prs = [
            pull_request(4, "shared", branch="alpha"),
            pull_request(5, "shared", branch="beta"),
        ]
        runs = {
            ("o/r", "alpha", "shared"): gate_run(
                event="pull_request",
                head="shared",
                branch="alpha",
                run_number=20,
                run_id=4,
                conclusion="failure",
                updated_at="2026-09-15T15:01:00Z",
            ),
            ("o/r", "beta", "shared"): gate_run(
                event="pull_request_review",
                head="shared",
                branch="beta",
                run_number=21,
                run_id=5,
                conclusion="success",
                updated_at="2026-09-15T15:02:00Z",
            ),
        }
        with mock.patch.object(bootstrap, "open_pull_requests", return_value=prs), mock.patch.object(
            bootstrap, "overlapping_closed_pr_windows", return_value={}
        ), mock.patch.object(
            bootstrap, "latest_completed_gate_runs", return_value=runs
        ), mock.patch.object(
            bootstrap, "unresolved_review_threads", side_effect=lambda _repo, n, _token: n == 4
        ), mock.patch.object(bootstrap, "rerun_workflow") as rerun:
            self.assertEqual(bootstrap.poll("o/r", "t"), [4])
        rerun.assert_called_once_with("o/r", 4, "t")

    def test_poll_stops_when_effective_state_is_missing_or_failure(self) -> None:
        prs = [pull_request(4, "missing", branch="m"), pull_request(5, "failed", branch="f")]
        runs = {
            ("o/r", "f", "failed"): gate_run(
                event="pull_request",
                head="failed",
                branch="f",
                run_number=1,
                run_id=5,
                conclusion="failure",
            )
        }
        with mock.patch.object(bootstrap, "open_pull_requests", return_value=prs), mock.patch.object(
            bootstrap, "overlapping_closed_pr_windows", return_value={}
        ), mock.patch.object(
            bootstrap, "latest_completed_gate_runs", return_value=runs
        ), mock.patch.object(bootstrap, "unresolved_review_threads") as threads, mock.patch.object(
            bootstrap, "rerun_workflow"
        ) as rerun:
            self.assertEqual(bootstrap.poll("o/r", "t"), [])
        threads.assert_not_called()
        rerun.assert_not_called()

    def test_poll_skips_clean_pr_and_fails_closed_without_target_head_run(self) -> None:
        clean_pr = pull_request(3, "clean", branch="clean")
        clean_runs = {
            ("o/r", "clean", "clean"): gate_run(
                event="pull_request", head="clean", branch="clean", run_number=1, run_id=3
            )
        }
        with mock.patch.object(bootstrap, "open_pull_requests", return_value=[clean_pr]), mock.patch.object(
            bootstrap, "overlapping_closed_pr_windows", return_value={}
        ), mock.patch.object(
            bootstrap, "latest_completed_gate_runs", return_value=clean_runs
        ), mock.patch.object(bootstrap, "unresolved_review_threads", return_value=False), mock.patch.object(
            bootstrap, "rerun_workflow"
        ) as rerun:
            self.assertEqual(bootstrap.poll("o/r", "t"), [])
        rerun.assert_not_called()

        target = pull_request(4, "shared", branch="alpha")
        only_other = {
            ("o/r", "beta", "shared"): gate_run(
                event="pull_request", head="shared", branch="beta", run_number=1, run_id=5
            )
        }
        with mock.patch.object(bootstrap, "open_pull_requests", return_value=[target]), mock.patch.object(
            bootstrap, "overlapping_closed_pr_windows", return_value={}
        ), mock.patch.object(
            bootstrap, "latest_completed_gate_runs", return_value=only_other
        ):
            with self.assertRaisesRegex(RuntimeError, "no unambiguous run bound to open PR #4"):
                bootstrap.poll("o/r", "t")

    def test_validate_github_contract(self) -> None:
        target = pull_request(5, "h", branch="feature")
        other = pull_request(2, "x", branch="other")
        runs = {
            ("o/r", "feature", "h"): gate_run(
                event="pull_request", head="h", branch="feature", run_number=2, run_id=5
            ),
            ("o/r", "other", "x"): gate_run(
                event="pull_request", head="x", branch="other", run_number=1, run_id=2
            ),
        }
        with mock.patch.object(bootstrap, "open_pull_requests", return_value=[target, other]), mock.patch.object(
            bootstrap, "overlapping_closed_pr_windows", return_value={}
        ), mock.patch.object(
            bootstrap, "latest_completed_gate_runs", return_value=runs
        ), mock.patch.object(bootstrap, "unresolved_review_threads", return_value=True):
            self.assertEqual(bootstrap.validate_github_contract("o/r", 5, "t"), (2, 2, True))

        with mock.patch.object(bootstrap, "open_pull_requests", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "exactly one open PR"):
                bootstrap.validate_github_contract("o/r", 5, "t")

        with mock.patch.object(bootstrap, "open_pull_requests", return_value=[target]), mock.patch.object(
            bootstrap, "overlapping_closed_pr_windows", return_value={}
        ), mock.patch.object(
            bootstrap, "latest_completed_gate_runs", return_value={}
        ):
            with self.assertRaisesRegex(RuntimeError, "no unambiguous canonical MONDE Gate run"):
                bootstrap.validate_github_contract("o/r", 5, "t")

    def test_main_missing_env_poll_success_and_error(self) -> None:
        with mock.patch.dict(bootstrap.os.environ, {}, clear=True):
            self.assertEqual(bootstrap.main(), 2)
        with mock.patch.dict(
            bootstrap.os.environ,
            {"GITHUB_REPOSITORY": "o/r", "GITHUB_TOKEN": "t"},
            clear=True,
        ), mock.patch.object(bootstrap, "poll", return_value=[1, 2]):
            self.assertEqual(bootstrap.main(), 0)
        with mock.patch.dict(
            bootstrap.os.environ,
            {"GITHUB_REPOSITORY": "o/r", "GITHUB_TOKEN": "t"},
            clear=True,
        ), mock.patch.object(bootstrap, "poll", side_effect=RuntimeError("boom")):
            self.assertEqual(bootstrap.main(), 2)

    def test_main_validation_mode_success_and_invalid_number(self) -> None:
        env = {"GITHUB_REPOSITORY": "o/r", "GITHUB_TOKEN": "t", "BOOTSTRAP_VALIDATE_PR": "5"}
        with mock.patch.dict(bootstrap.os.environ, env, clear=True), mock.patch.object(
            bootstrap, "validate_github_contract", return_value=(2, 3, False)
        ) as validate:
            self.assertEqual(bootstrap.main(), 0)
        validate.assert_called_once_with("o/r", 5, "t")

        for value in ("0", "not-int"):
            with self.subTest(value=value), mock.patch.dict(
                bootstrap.os.environ, {**env, "BOOTSTRAP_VALIDATE_PR": value}, clear=True
            ):
                self.assertEqual(bootstrap.main(), 2)

    def test_script_entrypoint_exits_through_main(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(SystemExit) as ctx:
                runpy.run_path(str(SCRIPT), run_name="__main__")
        self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
