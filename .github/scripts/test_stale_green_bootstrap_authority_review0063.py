from __future__ import annotations

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
import stale_green_bootstrap_authority_review0061 as chronology
import stale_green_bootstrap_authority_review0062 as previous
import stale_green_bootstrap_authority_review0063 as subject


class Review0063FullChronologyTests(unittest.TestCase):
    def tearDown(self) -> None:
        chronology._validate_attempt_job_chronology = subject._ORIGINAL_VALIDATE_CHRONOLOGY

    def test_job_start_after_run_update_fails_closed(self) -> None:
        run = run_row(
            101,
            10,
            attempt=2,
            created_at="2026-09-22T20:00:00Z",
            run_started_at="2026-09-22T21:00:00Z",
            updated_at="2026-09-22T21:02:00Z",
        )
        job = gate_job(
            501,
            101,
            attempt=2,
            started_at="2026-09-22T21:10:00Z",
            status="completed",
            conclusion="success",
        )
        job["completed_at"] = "2026-09-22T21:10:00Z"
        with self.assertRaisesRegex(RuntimeError, "starting after current workflow run update"):
            subject._validate_full_run_job_containment(run, job)

    def test_completed_after_run_update_fails_closed(self) -> None:
        run = run_row(
            101,
            10,
            attempt=2,
            created_at="2026-09-22T20:00:00Z",
            run_started_at="2026-09-22T21:00:00Z",
            updated_at="2026-09-22T21:05:00Z",
        )
        job = gate_job(
            501,
            101,
            attempt=2,
            started_at="2026-09-22T21:01:00Z",
            status="completed",
            conclusion="success",
        )
        job["completed_at"] = "2026-09-22T21:06:00Z"
        with self.assertRaisesRegex(RuntimeError, "completing after current workflow run update"):
            subject._validate_full_run_job_containment(run, job)

    def test_equal_upper_bounds_are_valid(self) -> None:
        run = run_row(
            101,
            10,
            attempt=2,
            created_at="2026-09-22T20:00:00Z",
            run_started_at="2026-09-22T21:00:00Z",
            updated_at="2026-09-22T21:05:00Z",
        )
        job = gate_job(
            501,
            101,
            attempt=2,
            started_at="2026-09-22T21:05:00Z",
            status="completed",
            conclusion="success",
        )
        job["completed_at"] = "2026-09-22T21:05:00Z"
        subject._validate_full_run_job_containment(run, job)

    def test_active_job_only_requires_start_within_run_lifetime(self) -> None:
        run = run_row(
            101,
            10,
            attempt=2,
            created_at="2026-09-22T20:00:00Z",
            run_started_at="2026-09-22T21:00:00Z",
            updated_at="2026-09-22T21:05:00Z",
        )
        job = gate_job(
            501,
            101,
            attempt=2,
            started_at="2026-09-22T21:04:00Z",
            status="in_progress",
            conclusion=None,
        )
        job["completed_at"] = None
        subject._validate_full_run_job_containment(run, job)

    def test_predecessor_lower_bound_remains_fail_closed(self) -> None:
        run = run_row(
            101,
            10,
            attempt=2,
            created_at="2026-09-22T20:00:00Z",
            run_started_at="2026-09-22T21:00:00Z",
            updated_at="2026-09-22T21:05:00Z",
        )
        job = gate_job(
            501,
            101,
            attempt=2,
            started_at="2026-09-22T20:59:59Z",
        )
        with self.assertRaisesRegex(RuntimeError, "starting before current workflow attempt"):
            subject._validate_full_run_job_containment(run, job)

    def test_impossible_candidate_cannot_overrank_valid_competitor(self) -> None:
        candidate = candidate_check(started_at="2026-09-22T21:10:00Z")
        run_a = run_row(
            101,
            10,
            attempt=2,
            created_at="2026-09-22T20:00:00Z",
            run_started_at="2026-09-22T21:00:00Z",
            updated_at="2026-09-22T21:02:00Z",
        )
        bad_a = gate_job(
            501,
            101,
            attempt=2,
            started_at="2026-09-22T21:10:00Z",
        )
        bad_a["completed_at"] = "2026-09-22T21:10:00Z"
        run_b = run_row(
            102,
            11,
            attempt=1,
            created_at="2026-09-22T20:10:00Z",
            run_started_at="2026-09-22T21:03:00Z",
            updated_at="2026-09-22T21:06:00Z",
        )
        good_b = gate_job(
            502,
            102,
            attempt=1,
            started_at="2026-09-22T21:05:00Z",
        )
        good_b["completed_at"] = "2026-09-22T21:06:00Z"

        def request(url: str, _token: str):
            if url.endswith("/actions/runs/101"):
                return run_a
            if url.endswith("/actions/jobs/501"):
                return bad_a
            raise AssertionError(url)

        def paged(url: str, *_args, **_kwargs):
            if "/actions/runs/101/jobs" in url:
                return [bad_a]
            if "/actions/runs/102/jobs" in url:
                return [good_b]
            raise AssertionError(url)

        with (
            mock.patch.object(core, "request_data", side_effect=request),
            mock.patch.object(core, "paged", side_effect=paged),
            mock.patch.object(
                chronology.previous,
                "_attempt_frontier_runs",
                return_value=[run_a, run_b],
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "starting after current workflow run update"):
                previous._terminal_stability_prove(
                    "o/r", HEAD, "t", candidate, FRONTIER
                )

    def test_install_and_main_guards(self) -> None:
        with mock.patch.object(previous, "install") as install:
            subject.install()
        install.assert_called_once()
        self.assertIs(
            chronology._validate_attempt_job_chronology,
            subject._validate_full_run_job_containment,
        )

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
            mock.patch.dict(
                os.environ,
                {"BOOTSTRAP_RECOVERY_ACTION": subject.RECOVERY_ACTION},
                clear=True,
            ),
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
