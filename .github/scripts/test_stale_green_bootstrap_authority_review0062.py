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
import stale_green_bootstrap_authority_review0061 as previous
import stale_green_bootstrap_authority_review0062 as subject


class Review0062TerminalSnapshotTests(unittest.TestCase):
    def tearDown(self) -> None:
        previous._chronology_prove_candidate_attempt_frontier = subject._ORIGINAL_CHRONOLOGY_PROVE

    def _prove_with_frontier_job(self, frontier_job: dict) -> None:
        candidate = candidate_check()
        run = run_row(
            101,
            10,
            attempt=2,
            created_at="2026-09-22T20:00:00Z",
            run_started_at="2026-09-22T21:00:00Z",
            updated_at="2026-09-22T21:15:00Z",
        )
        direct_job = gate_job(
            501,
            101,
            attempt=2,
            started_at="2026-09-22T21:01:00Z",
            status="completed",
            conclusion="success",
        )

        def request(url: str, _token: str):
            if url.endswith("/actions/runs/101"):
                return run
            if url.endswith("/actions/jobs/501"):
                return direct_job
            raise AssertionError(url)

        with (
            mock.patch.object(core, "request_data", side_effect=request),
            mock.patch.object(core, "paged", return_value=[frontier_job]),
            mock.patch.object(previous.previous, "_attempt_frontier_runs", return_value=[run]),
        ):
            subject._terminal_stability_prove("o/r", HEAD, "t", candidate, FRONTIER)

    def test_same_terminal_snapshot_preserves_review0061_authority(self) -> None:
        self._prove_with_frontier_job(
            gate_job(
                501,
                101,
                attempt=2,
                started_at="2026-09-22T21:01:00Z",
                status="completed",
                conclusion="success",
            )
        )

    def test_success_to_failure_drift_fails_closed(self) -> None:
        drifted = gate_job(
            501,
            101,
            attempt=2,
            started_at="2026-09-22T21:01:00Z",
            status="completed",
            conclusion="failure",
        )
        with self.assertRaisesRegex(RuntimeError, "terminal state changed"):
            self._prove_with_frontier_job(drifted)

    def test_completed_to_in_progress_drift_fails_closed(self) -> None:
        drifted = gate_job(
            501,
            101,
            attempt=2,
            started_at="2026-09-22T21:01:00Z",
            status="in_progress",
            conclusion=None,
        )
        with self.assertRaisesRegex(RuntimeError, "terminal state changed"):
            self._prove_with_frontier_job(drifted)

    def test_completed_at_drift_fails_closed(self) -> None:
        drifted = gate_job(
            501,
            101,
            attempt=2,
            started_at="2026-09-22T21:01:00Z",
            status="completed",
            conclusion="success",
        )
        drifted["completed_at"] = "2026-09-22T21:11:00Z"
        with self.assertRaisesRegex(RuntimeError, "terminal state changed"):
            self._prove_with_frontier_job(drifted)

    def test_missing_snapshot_fails_closed_and_restores_hooks(self) -> None:
        candidate = candidate_check()
        original_request = core.request_data
        original_job = previous._chronology_protected_gate_job
        with mock.patch.object(subject, "_ORIGINAL_CHRONOLOGY_PROVE", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "snapshot was not observed twice"):
                subject._terminal_stability_prove("o/r", HEAD, "t", candidate, FRONTIER)
        self.assertIs(core.request_data, original_request)
        self.assertIs(previous._chronology_protected_gate_job, original_job)

    def test_predecessor_error_restores_hooks(self) -> None:
        candidate = candidate_check()
        original_request = core.request_data
        original_job = previous._chronology_protected_gate_job
        with mock.patch.object(
            subject,
            "_ORIGINAL_CHRONOLOGY_PROVE",
            side_effect=RuntimeError("predecessor rejected"),
        ):
            with self.assertRaisesRegex(RuntimeError, "predecessor rejected"):
                subject._terminal_stability_prove("o/r", HEAD, "t", candidate, FRONTIER)
        self.assertIs(core.request_data, original_request)
        self.assertIs(previous._chronology_protected_gate_job, original_job)

    def test_terminal_snapshot_shape(self) -> None:
        job = {"status": "completed", "conclusion": "success", "completed_at": "t"}
        self.assertEqual(subject._terminal_snapshot(job), ("completed", "success", "t"))

    def test_install_and_main_guards(self) -> None:
        with mock.patch.object(previous, "install") as install:
            subject.install()
        install.assert_called_once()
        self.assertIs(
            previous._chronology_prove_candidate_attempt_frontier,
            subject._terminal_stability_prove,
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
