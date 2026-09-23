from __future__ import annotations

from datetime import datetime, timezone
import os
import runpy
import unittest
from unittest import mock

from test_stale_green_bootstrap_authority_review0060 import (
    FRONTIER,
    HEAD,
    candidate_check,
    gate_job,
    run_row,
)
import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0051_recovery as recovery
import stale_green_bootstrap_authority_review0060 as previous
import stale_green_bootstrap_authority_review0061 as subject


class Review0061CrossChronologyTests(unittest.TestCase):
    def tearDown(self) -> None:
        core.latest_required_check = subject._ORIGINAL_LATEST_REQUIRED_CHECK
        previous._protected_gate_job = subject._ORIGINAL_PROTECTED_GATE_JOB

    def test_attempt_job_chronology_rejects_job_before_attempt(self) -> None:
        run = run_row(
            101, 10, attempt=2,
            created_at="2026-09-23T07:00:00Z",
            run_started_at="2026-09-23T07:10:00Z",
            updated_at="2026-09-23T07:20:00Z",
        )
        bad = gate_job(
            501, 101, attempt=2,
            started_at="2026-09-23T07:09:59Z",
        )
        with self.assertRaisesRegex(RuntimeError, "starting before current workflow attempt"):
            subject._validate_attempt_job_chronology(run, bad)

        good = dict(bad)
        good["started_at"] = "2026-09-23T07:10:00Z"
        subject._validate_attempt_job_chronology(run, good)

    def test_direct_candidate_cross_chronology_fails_closed(self) -> None:
        candidate = candidate_check(started_at="2026-09-22T21:01:00Z")
        run = run_row(
            101, 10, attempt=2,
            created_at="2026-09-22T20:00:00Z",
            run_started_at="2026-09-22T21:02:00Z",
            updated_at="2026-09-22T21:10:00Z",
        )
        bad_job = gate_job(
            501, 101, attempt=2,
            started_at="2026-09-22T21:01:00Z",
        )
        with mock.patch.object(core, "request_data", side_effect=[run, bad_job]):
            with self.assertRaisesRegex(RuntimeError, "starting before current workflow attempt"):
                subject._chronology_prove_candidate_attempt_frontier(
                    "o/r", HEAD, "t", candidate, FRONTIER
                )

    def test_newer_competitor_attempt_cannot_be_under_ranked_by_old_job_timestamp(self) -> None:
        candidate = candidate_check()
        run_a = run_row(
            101, 10, attempt=2,
            created_at="2026-09-22T20:00:00Z",
            run_started_at="2026-09-22T21:00:00Z",
            updated_at="2026-09-22T21:10:00Z",
        )
        run_b = run_row(
            102, 11, attempt=2,
            created_at="2026-09-22T20:10:00Z",
            run_started_at="2026-09-22T21:02:00Z",
            updated_at="2026-09-22T21:12:00Z",
        )
        job_a = gate_job(501, 101, attempt=2, started_at="2026-09-22T21:01:00Z")
        malformed_b = gate_job(502, 102, attempt=2, started_at="2026-09-22T20:11:00Z")

        def request(url: str, _token: str):
            if url.endswith("/actions/runs/101"):
                return run_a
            if url.endswith("/actions/jobs/501"):
                return job_a
            raise AssertionError(url)

        def paged(url: str, *_args, **_kwargs):
            if "/actions/runs/101/jobs" in url:
                return [job_a]
            if "/actions/runs/102/jobs" in url:
                return [malformed_b]
            raise AssertionError(url)

        with (
            mock.patch.object(core, "request_data", side_effect=request),
            mock.patch.object(core, "paged", side_effect=paged),
            mock.patch.object(previous, "_attempt_frontier_runs", return_value=[run_a, run_b]),
        ):
            with self.assertRaisesRegex(RuntimeError, "starting before current workflow attempt"):
                subject._chronology_prove_candidate_attempt_frontier(
                    "o/r", HEAD, "t", candidate, FRONTIER
                )

    def test_valid_cross_chronology_preserves_review0060_authority(self) -> None:
        candidate = candidate_check()
        run_a = run_row(
            101, 10, attempt=2,
            created_at="2026-09-22T20:00:00Z",
            run_started_at="2026-09-22T21:00:00Z",
            updated_at="2026-09-22T21:10:00Z",
        )
        job_a = gate_job(501, 101, attempt=2, started_at="2026-09-22T21:01:00Z")

        def request(url: str, _token: str):
            if url.endswith("/actions/runs/101"):
                return run_a
            if url.endswith("/actions/jobs/501"):
                return job_a
            raise AssertionError(url)

        with (
            mock.patch.object(core, "request_data", side_effect=request),
            mock.patch.object(core, "paged", return_value=[job_a]),
            mock.patch.object(previous, "_attempt_frontier_runs", return_value=[run_a]),
        ):
            subject._chronology_prove_candidate_attempt_frontier(
                "o/r", HEAD, "t", candidate, FRONTIER
            )

    def test_wrapper_restores_request_and_protected_job_hooks_on_error(self) -> None:
        candidate = candidate_check()
        original_request = core.request_data
        original_protected = previous._protected_gate_job
        with mock.patch.object(subject, "_ORIGINAL_PROVE", side_effect=RuntimeError("boom")):
            with self.assertRaisesRegex(RuntimeError, "boom"):
                subject._chronology_prove_candidate_attempt_frontier(
                    "o/r", HEAD, "t", candidate, FRONTIER
                )
        self.assertIs(core.request_data, original_request)
        self.assertIs(previous._protected_gate_job, original_protected)

    def test_non_merge_candidate_skips_chronology_frontier(self) -> None:
        for candidate in (None, candidate_check(conclusion="failure")):
            with (
                self.subTest(candidate=candidate),
                mock.patch.object(subject, "_ORIGINAL_LATEST_REQUIRED_CHECK", return_value=candidate),
                mock.patch.object(subject, "_chronology_prove_candidate_attempt_frontier") as prove,
            ):
                self.assertIs(subject._chronology_latest_required_check("o/r", HEAD, "t"), candidate)
            prove.assert_not_called()

    def test_merge_candidate_captures_frontier_and_proves_chronology(self) -> None:
        candidate = candidate_check()
        frontier = datetime(2026, 9, 23, 7, 30, 0, tzinfo=timezone.utc)
        with (
            mock.patch.object(subject, "_ORIGINAL_LATEST_REQUIRED_CHECK", return_value=candidate),
            mock.patch.object(previous.previous, "_authority_frontier", return_value=frontier),
            mock.patch.object(subject, "_chronology_prove_candidate_attempt_frontier") as prove,
        ):
            self.assertIs(subject._chronology_latest_required_check("o/r", HEAD, "t"), candidate)
        prove.assert_called_once_with("o/r", HEAD, "t", candidate, frontier)

    def test_install_and_main_guards(self) -> None:
        with mock.patch.object(previous, "install") as install:
            subject.install()
        install.assert_called_once()
        self.assertIs(core.latest_required_check, subject._chronology_latest_required_check)

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
