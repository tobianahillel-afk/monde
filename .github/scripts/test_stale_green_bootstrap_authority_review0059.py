from __future__ import annotations

from datetime import datetime, timezone
import os
import runpy
import unittest
from unittest import mock

from test_stale_green_bootstrap_authority import check, gate_run, job
import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0051_recovery as recovery
import stale_green_bootstrap_authority_review0056 as previous
import stale_green_bootstrap_authority_review0059 as subject


HEAD = "a" * 40
FRONTIER = datetime(2026, 9, 22, 20, 30, 0, tzinfo=timezone.utc)


def candidate_check(*, conclusion: str = "success", status: str = "completed"):
    return check(501, 101, head=HEAD, status=status, conclusion=conclusion)


def candidate_run(*, run_id: int = 101, run_number: int = 10, attempt: int = 1, created_at: str = "2026-09-22T20:00:00Z"):
    return gate_run(
        run_id,
        2,
        head=HEAD,
        branch="feature",
        run_number=run_number,
        run_attempt=attempt,
        created_at=created_at,
        updated_at=created_at,
    )


class Review0059AuthorityFrontierTests(unittest.TestCase):
    def tearDown(self) -> None:
        core.latest_required_check = subject._ORIGINAL_LATEST_REQUIRED_CHECK

    def test_non_merge_acceptable_candidate_skips_frontier(self) -> None:
        for candidate in (
            None,
            candidate_check(status="in_progress", conclusion=None),
            candidate_check(conclusion="failure"),
        ):
            with (
                self.subTest(candidate=candidate),
                mock.patch.object(subject, "_ORIGINAL_LATEST_REQUIRED_CHECK", return_value=candidate),
                mock.patch.object(subject, "_prove_candidate_frontier") as prove,
            ):
                self.assertIs(subject._frontier_latest_required_check("o/r", HEAD, "t"), candidate)
            prove.assert_not_called()

    def test_merge_acceptable_candidate_binds_current_run_job_and_latest_frontier(self) -> None:
        candidate = candidate_check()
        run = candidate_run()
        protected_job = job(501, 101, head=HEAD, attempt=1, conclusion="success")

        def request(url: str, _token: str):
            if url.endswith("/actions/runs/101"):
                return run
            if url.endswith("/actions/jobs/501"):
                return protected_job
            raise AssertionError(url)

        with (
            mock.patch.object(subject, "_ORIGINAL_LATEST_REQUIRED_CHECK", return_value=candidate),
            mock.patch.object(subject, "_authority_frontier", return_value=FRONTIER),
            mock.patch.object(core, "request_data", side_effect=request),
            mock.patch.object(subject, "_bounded_frontier_runs", return_value=[run]),
        ):
            self.assertIs(subject._frontier_latest_required_check("o/r", HEAD, "t"), candidate)

    def test_newer_canonical_run_before_frontier_rejects_stale_candidate(self) -> None:
        candidate = candidate_check()
        run = candidate_run()
        newer = candidate_run(run_id=102, run_number=11, created_at="2026-09-22T20:10:00Z")
        protected_job = job(501, 101, head=HEAD, attempt=1, conclusion="success")

        def request(url: str, _token: str):
            if url.endswith("/actions/runs/101"):
                return run
            if url.endswith("/actions/jobs/501"):
                return protected_job
            raise AssertionError(url)

        with (
            mock.patch.object(subject, "_ORIGINAL_LATEST_REQUIRED_CHECK", return_value=candidate),
            mock.patch.object(subject, "_authority_frontier", return_value=FRONTIER),
            mock.patch.object(core, "request_data", side_effect=request),
            mock.patch.object(subject, "_bounded_frontier_runs", return_value=[run, newer]),
        ):
            with self.assertRaisesRegex(RuntimeError, "authority advanced"):
                subject._frontier_latest_required_check("o/r", HEAD, "t")

    def test_candidate_current_attempt_must_match_protected_job(self) -> None:
        candidate = candidate_check()
        run = candidate_run(attempt=2)
        stale_job = job(501, 101, head=HEAD, attempt=1, conclusion="success")

        def request(url: str, _token: str):
            return run if url.endswith("/actions/runs/101") else stale_job

        with (
            mock.patch.object(core, "request_data", side_effect=request),
            mock.patch.object(subject, "_bounded_frontier_runs", return_value=[run]),
        ):
            with self.assertRaisesRegex(RuntimeError, "malformed protected MONDE Gate job"):
                subject._prove_candidate_frontier("o/r", HEAD, "t", candidate, FRONTIER)

    def test_candidate_must_exist_and_match_frontier_identity(self) -> None:
        candidate = candidate_check()
        run = candidate_run()
        protected_job = job(501, 101, head=HEAD, attempt=1, conclusion="success")
        changed = dict(run)
        changed["run_attempt"] = 2

        def request(url: str, _token: str):
            return run if url.endswith("/actions/runs/101") else protected_job

        for rows, message in (
            ([], "absent"),
            ([candidate_run(run_id=102, run_number=11)], "absent"),
            ([changed], "changed during authority proof"),
        ):
            with (
                self.subTest(message=message),
                mock.patch.object(core, "request_data", side_effect=request),
                mock.patch.object(subject, "_bounded_frontier_runs", return_value=rows),
            ):
                with self.assertRaisesRegex(RuntimeError, message):
                    subject._prove_candidate_frontier("o/r", HEAD, "t", candidate, FRONTIER)

    def test_candidate_job_must_agree_with_check(self) -> None:
        candidate = candidate_check()
        run = candidate_run()
        protected_job = job(501, 101, head=HEAD, attempt=1, conclusion="failure")

        def request(url: str, _token: str):
            return run if url.endswith("/actions/runs/101") else protected_job

        with (
            mock.patch.object(core, "request_data", side_effect=request),
            mock.patch.object(subject, "_bounded_frontier_runs", return_value=[run]),
        ):
            with self.assertRaisesRegex(RuntimeError, "disagrees"):
                subject._prove_candidate_frontier("o/r", HEAD, "t", candidate, FRONTIER)

    def test_frontier_window_query_is_head_and_time_bounded(self) -> None:
        with mock.patch.object(core, "paged", return_value=[]) as paged:
            self.assertEqual(
                subject._read_frontier_window(
                    "o/r", HEAD, "t",
                    datetime(2026, 9, 22, 20, 0, tzinfo=timezone.utc),
                    FRONTIER,
                ),
                [],
            )
        url = paged.call_args.args[0]
        self.assertIn(f"head_sha={HEAD}", url)
        self.assertIn("created=2026-09-22T20%3A00%3A00Z..2026-09-22T20%3A30%3A00Z", url)
        self.assertEqual(paged.call_args.kwargs["max_total_count"], core.FILTERED_WORKFLOW_RUN_SEARCH_LIMIT)

    def test_frontier_search_splits_at_filtered_limit_and_fails_closed_within_one_second(self) -> None:
        left = candidate_run(run_id=101, run_number=10, created_at="2026-09-22T20:00:00Z")
        right = candidate_run(run_id=102, run_number=11, created_at="2026-09-22T20:30:00Z")
        with mock.patch.object(
            subject,
            "_read_frontier_window",
            side_effect=[core.FilteredSearchLimitExceeded("limit"), [left], [right]],
        ):
            self.assertEqual(
                [row["id"] for row in subject._bounded_frontier_runs(
                    "o/r", HEAD, "t",
                    datetime(2026, 9, 22, 20, 0, tzinfo=timezone.utc),
                    datetime(2026, 9, 22, 21, 0, tzinfo=timezone.utc),
                )],
                [101, 102],
            )

        instant = datetime(2026, 9, 22, 20, 0, tzinfo=timezone.utc)
        with mock.patch.object(
            subject,
            "_read_frontier_window",
            side_effect=core.FilteredSearchLimitExceeded("limit"),
        ):
            with self.assertRaisesRegex(RuntimeError, "within one timestamp second"):
                subject._bounded_frontier_runs("o/r", HEAD, "t", instant, instant)

    def test_frontier_split_rejects_duplicate_identity(self) -> None:
        row = candidate_run()
        with mock.patch.object(
            subject,
            "_read_frontier_window",
            side_effect=[core.FilteredSearchLimitExceeded("limit"), [row], [dict(row)]],
        ):
            with self.assertRaisesRegex(RuntimeError, "duplicate or malformed"):
                subject._bounded_frontier_runs(
                    "o/r", HEAD, "t",
                    datetime(2026, 9, 22, 20, 0, tzinfo=timezone.utc),
                    datetime(2026, 9, 22, 21, 0, tzinfo=timezone.utc),
                )

    def test_frontier_before_candidate_creation_fails_closed(self) -> None:
        candidate = candidate_check()
        run = candidate_run(created_at="2026-09-22T21:00:00Z")
        protected_job = job(501, 101, head=HEAD, attempt=1, conclusion="success")

        def request(url: str, _token: str):
            return run if url.endswith("/actions/runs/101") else protected_job

        with mock.patch.object(core, "request_data", side_effect=request):
            with self.assertRaisesRegex(RuntimeError, "frontier precedes"):
                subject._prove_candidate_frontier("o/r", HEAD, "t", candidate, FRONTIER)

    def test_install_and_main_guards(self) -> None:
        with mock.patch.object(previous, "install") as install:
            subject.install()
        install.assert_called_once()
        self.assertIs(core.latest_required_check, subject._frontier_latest_required_check)

        with (
            mock.patch.object(subject, "install"),
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(base, "main", return_value=17) as base_main,
        ):
            self.assertEqual(subject.main(), 17)
        base_main.assert_called_once()

        with (
            mock.patch.object(subject, "install"),
            mock.patch.dict(os.environ, {"BOOTSTRAP_RECOVERY_ACTION": "bad"}, clear=True),
        ):
            with self.assertRaisesRegex(RuntimeError, "unsupported bootstrap recovery action"):
                subject.main()

        with (
            mock.patch.object(subject, "install"),
            mock.patch.dict(os.environ, {"BOOTSTRAP_RECOVERY_ACTION": subject.RECOVERY_ACTION}, clear=True),
        ):
            with self.assertRaisesRegex(RuntimeError, "GITHUB_REPOSITORY and GITHUB_TOKEN"):
                subject.main()

        env = {
            "BOOTSTRAP_RECOVERY_ACTION": subject.RECOVERY_ACTION,
            "GITHUB_REPOSITORY": "o/r",
            "GITHUB_TOKEN": "t",
        }
        with (
            mock.patch.object(subject, "install"),
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch.object(recovery, "_inspect_confirmed_unposted", return_value=0) as inspect,
        ):
            self.assertEqual(subject.main(), 0)
        inspect.assert_called_once_with("o/r", "t")

    def test_module_entrypoint(self) -> None:
        with (
            mock.patch.object(previous, "install") as predecessor_install,
            mock.patch.object(base, "main", return_value=0),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            with self.assertRaises(SystemExit) as raised:
                runpy.run_path(subject.__file__, run_name="__main__")
        self.assertEqual(raised.exception.code, 0)
        predecessor_install.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
