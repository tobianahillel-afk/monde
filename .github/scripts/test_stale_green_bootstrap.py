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
    workflow_id: int | float | bool | None = None,
    path: str | None = None,
    branch: str = "branch-2",
    repo_name: str = "o/r",
    created_at: str | None = None,
    updated_at: str | None = None,
    pull_requests=None,
    run_attempt: int = 1,
):
    return {
        "workflow_id": bootstrap.CANONICAL_WORKFLOW_ID if workflow_id is None else workflow_id,
        "path": bootstrap.CANONICAL_WORKFLOW_PATH if path is None else path,
        "event": event,
        "head_sha": head,
        "head_branch": branch,
        "head_repository": {"full_name": repo_name},
        "run_number": run_number,
        "run_attempt": run_attempt,
        "id": run_id,
        "status": "completed",
        "conclusion": conclusion,
        "created_at": created_at or f"2026-09-15T14:30:{run_id % 60:02d}Z",
        "updated_at": updated_at or f"2026-09-15T15:00:{run_id % 60:02d}Z",
        "pull_requests": [] if pull_requests is None else pull_requests,
    }


def check_run(
    head: str,
    *,
    conclusion: str | None = "success",
    status: str = "completed",
    check_id: int | bool = 40,
    name: str | None = None,
    app_id: int | float | bool = bootstrap.GITHUB_ACTIONS_APP_ID,
    app_slug: str = "github-actions",
) -> dict:
    return {
        "id": check_id,
        "name": bootstrap.REQUIRED_GATE_JOB_NAME if name is None else name,
        "head_sha": head,
        "status": status,
        "conclusion": conclusion,
        "app": {"id": app_id, "slug": app_slug},
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

        for state in ("closed", None, ""):
            bad_state = pull_request(2, "h", branch="feature", repo_name="owner/repo", state=state)
            with self.subTest(state=state), mock.patch.object(bootstrap, "paged", return_value=[bad_state]):
                with self.assertRaisesRegex(RuntimeError, "malformed open pull request state"):
                    bootstrap.open_pull_requests("o/r", "t")

        same_identity = [pull_request(2, "same", branch="same"), pull_request(5, "same", branch="same")]
        with mock.patch.object(bootstrap, "paged", return_value=same_identity):
            with self.assertRaisesRegex(RuntimeError, "indistinguishable head identity"):
                bootstrap.open_pull_requests("o/r", "t")

    def test_run_head_identity_requires_server_head_metadata(self) -> None:
        good = gate_run(event="pull_request", head="h", run_number=1, run_id=1, branch="feature", repo_name="owner/repo")
        self.assertEqual(bootstrap._run_head_identity(good), ("owner/repo", "feature", "h"))
        for field, value in (("head_repository", None), ("head_branch", ""), ("head_sha", "")):
            bad = dict(good)
            bad[field] = value
            with self.subTest(field=field):
                with self.assertRaisesRegex(RuntimeError, "malformed canonical MONDE Gate head identity"):
                    bootstrap._run_head_identity(bad)
        for repo_name in ("malformed", "owner/", "/repo", "owner/repo/extra"):
            bad_repo = gate_run(event="pull_request", head="h", run_number=1, run_id=1, repo_name=repo_name)
            with self.subTest(repo_name=repo_name):
                with self.assertRaisesRegex(RuntimeError, "head repository full_name"):
                    bootstrap._run_head_identity(bad_repo)

    def test_updated_at_requires_valid_aware_timestamp(self) -> None:
        self.assertIsNotNone(bootstrap._updated_at("2026-09-15T15:00:00Z").tzinfo)
        for value in (None, "", "not-a-date", "2026-09-15T15:00:00"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(RuntimeError, "malformed canonical MONDE Gate updated_at"):
                    bootstrap._updated_at(value)

    def test_latest_gate_runs_bind_to_trusted_head_identity_not_association_list(self) -> None:
        rows = [
            gate_run(event="pull_request", head="shared", branch="alpha", run_number=1, run_id=10, pull_requests=[{"number": 2}, {"number": 5}]),
            gate_run(event="pull_request_review", head="shared", branch="alpha", run_number=2, run_id=20, pull_requests=[]),
            gate_run(event="pull_request_review_comment", head="shared", branch="beta", run_number=3, run_id=30, pull_requests=[{"number": 999}]),
            gate_run(event="push", head="ignored", branch="main", run_number=99, run_id=99),
        ]
        with mock.patch.object(bootstrap, "paged", return_value=rows) as paged:
            latest = bootstrap.latest_completed_gate_runs("o/r", "t")
        self.assertEqual(latest[("o/r", "alpha", "shared")]["id"], 20)
        self.assertEqual(latest[("o/r", "beta", "shared")]["id"], 30)
        self.assertNotIn(("o/r", "main", "ignored"), latest)
        self.assertIn(f"actions/workflows/{bootstrap.CANONICAL_WORKFLOW_ID}/runs?status=completed", paged.call_args.args[0])
        self.assertEqual(paged.call_args.kwargs["unique_id_field"], "id")

    def test_latest_gate_runs_rejects_wrong_identity_malformed_event_run_time_and_head(self) -> None:
        for bad in (
            gate_run(event="pull_request", head="h", run_number=1, run_id=10, workflow_id=999),
            gate_run(event="pull_request", head="h", run_number=1, run_id=10, workflow_id=float(bootstrap.CANONICAL_WORKFLOW_ID)),
            gate_run(event="pull_request", head="h", run_number=1, run_id=10, workflow_id=True),
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
            ("name", "other"),
            ("run_number", True),
            ("status", None),
            ("status", "in_progress"),
            ("conclusion", ""),
            ("conclusion", "mystery"),
        ):
            malformed = gate_run(event="pull_request", head="h", run_number=1, run_id=10)
            malformed[field] = value
            with self.subTest(field=field, value=value), mock.patch.object(bootstrap, "paged", return_value=[malformed]):
                with self.assertRaisesRegex(RuntimeError, "malformed canonical MONDE Gate run"):
                    bootstrap.latest_completed_gate_runs("o/r", "t")

        bad_time = gate_run(event="pull_request", head="h", run_number=1, run_id=10, updated_at="not-a-date")
        with mock.patch.object(bootstrap, "paged", return_value=[bad_time]):
            with self.assertRaisesRegex(RuntimeError, "malformed canonical MONDE Gate updated_at"):
                bootstrap.latest_completed_gate_runs("o/r", "t")

        backwards_time = gate_run(
            event="pull_request",
            head="h",
            run_number=1,
            run_id=10,
            created_at="2026-09-15T15:01:00Z",
            updated_at="2026-09-15T15:00:00Z",
        )
        with mock.patch.object(bootstrap, "paged", return_value=[backwards_time]):
            with self.assertRaisesRegex(RuntimeError, "invalid lifetime"):
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
        older = gate_run(event="pull_request", head="h", branch="feature", run_number=10, run_id=10, updated_at="2026-09-15T15:01:00Z")
        newer = gate_run(event="pull_request_review", head="h", branch="feature", run_number=11, run_id=11, updated_at="2026-09-15T15:02:00Z")
        stale_late_item = gate_run(event="pull_request", head="h", branch="feature", run_number=9, run_id=9, updated_at="2026-09-15T15:00:00Z")
        with mock.patch.object(bootstrap, "paged", return_value=[older, newer, stale_late_item]):
            latest = bootstrap.latest_completed_gate_runs("o/r", "t")
        self.assertEqual(latest[("o/r", "feature", "h")]["id"], 11)

    def test_latest_required_check_accepts_only_exact_github_actions_check(self) -> None:
        good = check_run("h")
        payload = {"total_count": 1, "check_runs": [good]}
        with mock.patch.object(bootstrap, "request_data", return_value=payload) as request:
            self.assertEqual(bootstrap.latest_required_check("o/r", "h", "t"), good)
        url = request.call_args.args[0]
        self.assertIn("commits/h/check-runs?", url)
        self.assertIn("check_name=MONDE+%2F+Merge+Gate", url)
        self.assertIn("filter=latest", url)
        self.assertIn(f"app_id={bootstrap.GITHUB_ACTIONS_APP_ID}", url)

        with mock.patch.object(bootstrap, "request_data", return_value={"total_count": 0, "check_runs": []}):
            self.assertIsNone(bootstrap.latest_required_check("o/r", "h", "t"))

    def test_latest_required_check_fails_closed_on_response_and_identity(self) -> None:
        good = check_run("h")
        malformed_payloads = [
            [],
            {"total_count": True, "check_runs": []},
            {"total_count": -1, "check_runs": []},
            {"total_count": 1, "check_runs": "bad"},
            {"total_count": 1, "check_runs": []},
            {"total_count": 1, "check_runs": [None]},
            {"total_count": 2, "check_runs": [good, dict(good)]},
        ]
        for payload in malformed_payloads:
            with self.subTest(payload=payload), mock.patch.object(bootstrap, "request_data", return_value=payload):
                with self.assertRaises(RuntimeError):
                    bootstrap.latest_required_check("o/r", "h", "t")

        mutations = [
            ("id", True),
            ("name", "other"),
            ("head_sha", "other"),
            ("app", None),
            ("app", {"id": float(bootstrap.GITHUB_ACTIONS_APP_ID), "slug": "github-actions"}),
            ("app", {"id": bootstrap.GITHUB_ACTIONS_APP_ID, "slug": "other"}),
            ("status", "mystery"),
        ]
        for field, value in mutations:
            bad = dict(good)
            bad[field] = value
            with self.subTest(field=field), mock.patch.object(
                bootstrap, "request_data", return_value={"total_count": 1, "check_runs": [bad]}
            ):
                with self.assertRaisesRegex(RuntimeError, "malformed required MONDE"):
                    bootstrap.latest_required_check("o/r", "h", "t")

        bad_id = dict(good)
        bad_id["id"] = True
        with mock.patch.object(
            bootstrap,
            "request_data",
            return_value={"total_count": 1, "check_runs": [bad_id]},
        ):
            with self.assertRaisesRegex(RuntimeError, "malformed paginated record identity"):
                bootstrap.latest_required_check("o/r", "h", "t")

    def test_latest_required_check_paginates_complete_filtered_collection(self) -> None:
        checks = []
        for check_id in range(1, 102):
            item = check_run("h", check_id=check_id)
            item["started_at"] = f"2026-09-22T09:{check_id % 60:02d}:00Z"
            checks.append(item)
        newest = checks[-1]
        newest["started_at"] = "2026-09-22T10:59:59Z"

        calls = {"page1": 0}

        def response(url: str, _token: str):
            if "&page=2" in url:
                return {"total_count": 101, "check_runs": checks[100:]}
            if "&page=1" in url:
                calls["page1"] += 1
                return {"total_count": 101, "check_runs": checks[:100]}
            raise AssertionError(url)

        with mock.patch.object(bootstrap, "request_data", side_effect=response) as request:
            self.assertEqual(bootstrap.latest_required_check("o/r", "h", "t"), newest)
        urls = [call.args[0] for call in request.call_args_list]
        self.assertEqual(len(urls), 3)
        self.assertIn("page=1", urls[0])
        self.assertIn("page=2", urls[1])
        self.assertIn("page=1", urls[2])
        self.assertEqual(calls["page1"], 2)

    def test_latest_required_check_pagination_fails_closed_on_drift_and_cross_page_duplicate(self) -> None:
        first = [check_run("h", check_id=i) for i in range(1, 101)]
        second = check_run("h", check_id=101)

        cases = [
            (
                {"total_count": 101, "check_runs": first},
                {"total_count": 102, "check_runs": [second]},
                "inconsistent paginated total_count",
            ),
            (
                {"total_count": 101, "check_runs": first},
                {"total_count": 101, "check_runs": [dict(first[-1])]},
                "duplicate paginated record identity",
            ),
            (
                {"total_count": 101, "check_runs": first},
                {"total_count": 101, "check_runs": []},
                "incomplete paginated collection",
            ),
        ]
        for page1, page2, message in cases:
            with self.subTest(message=message):
                responses = iter([page1, page2])
                with mock.patch.object(bootstrap, "request_data", side_effect=lambda *_args: next(responses)):
                    with self.assertRaisesRegex(RuntimeError, message):
                        bootstrap.latest_required_check("o/r", "h", "t")

    def test_latest_required_check_fails_closed_on_count_stable_page_membership_drift(self) -> None:
        initial = [check_run("h", check_id=i) for i in range(1, 102)]
        changed_page1 = [check_run("h", check_id=999)] + [
            item for item in initial[:100] if item["id"] != 50
        ]
        self.assertEqual(len(changed_page1), 100)
        responses = iter(
            [
                {"total_count": 101, "check_runs": initial[:100]},
                {"total_count": 101, "check_runs": initial[100:]},
                {"total_count": 101, "check_runs": changed_page1},
            ]
        )
        with mock.patch.object(
            bootstrap,
            "request_data",
            side_effect=lambda *_args: next(responses),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "paginated page membership changed during traversal",
            ):
                bootstrap.latest_required_check("o/r", "h", "t")

    def test_latest_required_check_selects_newest_legitimate_check_across_suites(self) -> None:
        older = check_run("h", check_id=40)
        older["started_at"] = "2026-09-22T09:42:31Z"
        newer = check_run("h", check_id=41, conclusion="failure")
        newer["started_at"] = "2026-09-22T09:47:36Z"
        payload = {"total_count": 2, "check_runs": [newer, older]}
        with mock.patch.object(bootstrap, "request_data", return_value=payload):
            self.assertEqual(bootstrap.latest_required_check("o/r", "h", "t"), newer)

        same_second_newer_id = check_run("h", check_id=42, conclusion="neutral")
        same_second_newer_id["started_at"] = newer["started_at"]
        payload = {"total_count": 2, "check_runs": [newer, same_second_newer_id]}
        with mock.patch.object(bootstrap, "request_data", return_value=payload):
            self.assertEqual(bootstrap.latest_required_check("o/r", "h", "t"), same_second_newer_id)

    def test_latest_required_check_multiple_candidates_require_valid_recency(self) -> None:
        good = check_run("h", check_id=40)
        good["started_at"] = "2026-09-22T09:42:31Z"
        for started_at in (None, "", "not-a-time"):
            bad = check_run("h", check_id=41)
            bad["started_at"] = started_at
            with self.subTest(started_at=started_at), mock.patch.object(
                bootstrap,
                "request_data",
                return_value={"total_count": 2, "check_runs": [good, bad]},
            ):
                with self.assertRaises(RuntimeError):
                    bootstrap.latest_required_check("o/r", "h", "t")

    def test_latest_required_check_validates_status_conclusion_contract(self) -> None:
        for conclusion in sorted(bootstrap.TERMINAL_CONCLUSIONS):
            good = check_run("h", conclusion=conclusion)
            with self.subTest(conclusion=conclusion), mock.patch.object(
                bootstrap, "request_data", return_value={"total_count": 1, "check_runs": [good]}
            ):
                self.assertEqual(bootstrap.latest_required_check("o/r", "h", "t")["conclusion"], conclusion)

        for bad_conclusion in (None, "mystery"):
            bad = check_run("h", conclusion=bad_conclusion)
            with self.subTest(bad_conclusion=bad_conclusion), mock.patch.object(
                bootstrap, "request_data", return_value={"total_count": 1, "check_runs": [bad]}
            ):
                with self.assertRaisesRegex(RuntimeError, "malformed completed required"):
                    bootstrap.latest_required_check("o/r", "h", "t")

        for status in sorted(bootstrap.CHECK_RUN_STATUSES - {"completed"}):
            pending = check_run("h", status=status, conclusion=None)
            with self.subTest(status=status), mock.patch.object(
                bootstrap, "request_data", return_value={"total_count": 1, "check_runs": [pending]}
            ):
                self.assertEqual(bootstrap.latest_required_check("o/r", "h", "t")["status"], status)

            bad = check_run("h", status=status, conclusion="success")
            with mock.patch.object(bootstrap, "request_data", return_value={"total_count": 1, "check_runs": [bad]}):
                with self.assertRaisesRegex(RuntimeError, "incomplete required"):
                    bootstrap.latest_required_check("o/r", "h", "t")

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
                "nodes": [{}], "pageInfo": {"hasNextPage": False, "endCursor": None}
            }}}}
        }
        with mock.patch.object(bootstrap, "request_data", return_value=bad_node):
            with self.assertRaisesRegex(RuntimeError, "malformed reviewThreads nodes"):
                bootstrap.unresolved_review_threads("o/r", 2, "t")

        bad_info = {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [], "pageInfo": {}}}}}}
        with mock.patch.object(bootstrap, "request_data", return_value=bad_info):
            with self.assertRaisesRegex(RuntimeError, "malformed reviewThreads pageInfo"):
                bootstrap.unresolved_review_threads("o/r", 2, "t")

        for bad_end_cursor in ({"hasNextPage": False}, {"hasNextPage": False, "endCursor": 7}, {"hasNextPage": False, "endCursor": {}}):
            payload = {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [], "pageInfo": bad_end_cursor}}}}}
            with self.subTest(pageInfo=bad_end_cursor), mock.patch.object(bootstrap, "request_data", return_value=payload):
                with self.assertRaisesRegex(RuntimeError, "malformed reviewThreads pageInfo"):
                    bootstrap.unresolved_review_threads("o/r", 2, "t")

        bad_cursor = {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [], "pageInfo": {"hasNextPage": True, "endCursor": None}}}}}}
        with mock.patch.object(bootstrap, "request_data", return_value=bad_cursor):
            with self.assertRaisesRegex(RuntimeError, "pagination missing cursor"):
                bootstrap.unresolved_review_threads("o/r", 2, "t")

    def test_review_threads_reject_repeated_cursor_and_page_exhaustion(self) -> None:
        repeated = {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [], "pageInfo": {"hasNextPage": True, "endCursor": "same"}}}}}}
        with mock.patch.object(bootstrap, "request_data", side_effect=[repeated, repeated]):
            with self.assertRaisesRegex(RuntimeError, "repeated cursor"):
                bootstrap.unresolved_review_threads("o/r", 2, "t")

        first = {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [], "pageInfo": {"hasNextPage": True, "endCursor": "next"}}}}}}
        with mock.patch.object(bootstrap, "MAX_PAGES", 1), mock.patch.object(bootstrap, "request_data", return_value=first):
            with self.assertRaisesRegex(RuntimeError, "pagination exceeded"):
                bootstrap.unresolved_review_threads("o/r", 2, "t")

    def test_rerun_workflow_posts_to_exact_run(self) -> None:
        with mock.patch.object(bootstrap, "request_data", return_value={}) as req:
            bootstrap.rerun_workflow("o/r", 123, "t")
        self.assertEqual(req.call_args.args, ("https://api.github.com/repos/o/r/actions/runs/123/rerun", "t", "POST", {}))

    def test_poll_uses_direct_check_once_per_shared_sha_and_only_validates_unresolved_target(self) -> None:
        prs = [pull_request(4, "shared", branch="alpha"), pull_request(5, "shared", branch="beta")]
        alpha = gate_run(event="pull_request", head="shared", branch="alpha", run_number=20, run_id=4)
        beta = gate_run(event="pull_request", head="shared", branch="beta", run_number=21, run_id=5)
        runs = {("o/r", "alpha", "shared"): alpha, ("o/r", "beta", "shared"): beta}
        direct = check_run("shared")
        with mock.patch.object(bootstrap, "open_pull_requests", return_value=prs), mock.patch.object(
            bootstrap, "overlapping_closed_pr_windows", return_value={}
        ), mock.patch.object(
            bootstrap, "latest_completed_gate_runs", return_value=runs
        ), mock.patch.object(
            bootstrap, "latest_required_check", return_value=direct
        ) as latest_check, mock.patch.object(
            bootstrap, "required_merge_gate_conclusion", return_value="success"
        ) as target_job, mock.patch.object(
            bootstrap, "unresolved_review_threads", side_effect=lambda _repo, n, _token: n == 4
        ), mock.patch.object(
            bootstrap, "rerun_workflow"
        ) as rerun:
            self.assertEqual(bootstrap.poll("o/r", "t"), [4])
        latest_check.assert_called_once_with("o/r", "shared", "t")
        target_job.assert_called_once_with("o/r", alpha, "t")
        rerun.assert_called_once_with("o/r", 4, "t")

    def test_poll_skips_missing_incomplete_and_non_merge_acceptable_direct_checks(self) -> None:
        prs = [
            pull_request(4, "missing", branch="m"),
            pull_request(5, "pending", branch="p"),
            pull_request(6, "failed", branch="f"),
        ]
        runs = {
            ("o/r", "m", "missing"): gate_run(event="pull_request", head="missing", branch="m", run_number=1, run_id=4),
            ("o/r", "p", "pending"): gate_run(event="pull_request", head="pending", branch="p", run_number=1, run_id=5),
            ("o/r", "f", "failed"): gate_run(event="pull_request", head="failed", branch="f", run_number=1, run_id=6),
        }
        with mock.patch.object(bootstrap, "open_pull_requests", return_value=prs), mock.patch.object(
            bootstrap, "overlapping_closed_pr_windows", return_value={}
        ), mock.patch.object(
            bootstrap, "latest_completed_gate_runs", return_value=runs
        ), mock.patch.object(
            bootstrap,
            "latest_required_check",
            side_effect=[None, {"status": "in_progress", "conclusion": None}, {"status": "completed", "conclusion": "failure"}],
        ), mock.patch.object(bootstrap, "unresolved_review_threads") as threads, mock.patch.object(
            bootstrap, "required_merge_gate_conclusion"
        ) as target_job, mock.patch.object(bootstrap, "rerun_workflow") as rerun:
            self.assertEqual(bootstrap.poll("o/r", "t"), [])
        threads.assert_not_called()
        target_job.assert_not_called()
        rerun.assert_not_called()

    def test_poll_skips_clean_pr_and_fails_closed_without_target_run_only_when_thread_unresolved(self) -> None:
        clean_pr = pull_request(3, "clean", branch="clean")
        clean_runs = {("o/r", "clean", "clean"): gate_run(event="pull_request", head="clean", branch="clean", run_number=1, run_id=3)}
        with mock.patch.object(bootstrap, "open_pull_requests", return_value=[clean_pr]), mock.patch.object(
            bootstrap, "overlapping_closed_pr_windows", return_value={}
        ), mock.patch.object(
            bootstrap, "latest_completed_gate_runs", return_value=clean_runs
        ), mock.patch.object(
            bootstrap, "latest_required_check", return_value=check_run("clean")
        ), mock.patch.object(
            bootstrap, "unresolved_review_threads", return_value=False
        ), mock.patch.object(bootstrap, "required_merge_gate_conclusion") as target_job, mock.patch.object(
            bootstrap, "rerun_workflow"
        ) as rerun:
            self.assertEqual(bootstrap.poll("o/r", "t"), [])
        target_job.assert_not_called()
        rerun.assert_not_called()

        target = pull_request(4, "shared", branch="alpha")
        only_other = {("o/r", "beta", "shared"): gate_run(event="pull_request", head="shared", branch="beta", run_number=1, run_id=5)}
        with mock.patch.object(bootstrap, "open_pull_requests", return_value=[target]), mock.patch.object(
            bootstrap, "overlapping_closed_pr_windows", return_value={}
        ), mock.patch.object(
            bootstrap, "latest_completed_gate_runs", return_value=only_other
        ), mock.patch.object(
            bootstrap, "latest_required_check", return_value=check_run("shared")
        ), mock.patch.object(
            bootstrap, "unresolved_review_threads", return_value=True
        ):
            with self.assertRaisesRegex(RuntimeError, "no unambiguous run bound to open PR #4"):
                bootstrap.poll("o/r", "t")

    def test_validate_github_contract(self) -> None:
        target = pull_request(5, "h", branch="feature")
        other = pull_request(2, "x", branch="other")
        target_run = gate_run(event="pull_request", head="h", branch="feature", run_number=2, run_id=5)
        runs = {("o/r", "feature", "h"): target_run, ("o/r", "other", "x"): gate_run(event="pull_request", head="x", branch="other", run_number=1, run_id=2)}
        with mock.patch.object(bootstrap, "open_pull_requests", return_value=[target, other]), mock.patch.object(
            bootstrap, "overlapping_closed_pr_windows", return_value={}
        ), mock.patch.object(
            bootstrap, "latest_completed_gate_runs", return_value=runs
        ), mock.patch.object(
            bootstrap, "latest_required_check", return_value=check_run("h")
        ), mock.patch.object(
            bootstrap, "required_merge_gate_conclusion", return_value="failure"
        ) as job, mock.patch.object(
            bootstrap, "unresolved_review_threads", return_value=True
        ):
            self.assertEqual(bootstrap.validate_github_contract("o/r", 5, "t"), (2, 2, True))
        job.assert_called_once_with("o/r", target_run, "t")

        with mock.patch.object(bootstrap, "open_pull_requests", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "exactly one open PR"):
                bootstrap.validate_github_contract("o/r", 5, "t")

        with mock.patch.object(bootstrap, "open_pull_requests", return_value=[target]), mock.patch.object(
            bootstrap, "overlapping_closed_pr_windows", return_value={}
        ), mock.patch.object(bootstrap, "latest_completed_gate_runs", return_value={}):
            with self.assertRaisesRegex(RuntimeError, "no unambiguous canonical MONDE Gate run"):
                bootstrap.validate_github_contract("o/r", 5, "t")

        with mock.patch.object(bootstrap, "open_pull_requests", return_value=[target]), mock.patch.object(
            bootstrap, "overlapping_closed_pr_windows", return_value={}
        ), mock.patch.object(
            bootstrap, "latest_completed_gate_runs", return_value={("o/r", "feature", "h"): target_run}
        ), mock.patch.object(bootstrap, "latest_required_check", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "no latest .* check"):
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
            with self.subTest(value=value), mock.patch.dict(bootstrap.os.environ, {**env, "BOOTSTRAP_VALIDATE_PR": value}, clear=True):
                self.assertEqual(bootstrap.main(), 2)

    def test_script_entrypoint_exits_through_main(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(SystemExit) as ctx:
                runpy.run_path(str(SCRIPT), run_name="__main__")
        self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
