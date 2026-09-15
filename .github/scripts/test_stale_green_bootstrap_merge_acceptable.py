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
        "head_sha": "h",
        "updated_at": "2026-09-15T16:05:00Z",
        "conclusion": conclusion,
    }


def job(
    conclusion: str,
    *,
    job_id: int = 40,
    run_id: int = 4,
    name: str | None = None,
    status: str = "completed",
    head_sha: str = "h",
) -> dict:
    return {
        "id": job_id,
        "run_id": run_id,
        "name": bootstrap.REQUIRED_GATE_JOB_NAME if name is None else name,
        "status": status,
        "conclusion": conclusion,
        "head_sha": head_sha,
    }


class MergeAcceptableConclusionTests(unittest.TestCase):
    def test_required_merge_gate_conclusion_reads_exact_job_not_workflow_conclusion(self) -> None:
        run = effective_run("failure")
        rows = [
            job("failure", job_id=39, name="CodeQL"),
            job("neutral", job_id=40),
        ]
        with mock.patch.object(bootstrap, "paged", return_value=rows) as paged:
            self.assertEqual(bootstrap.required_merge_gate_conclusion("o/r", run, "t"), "neutral")
        self.assertEqual(paged.call_args.args[2], "jobs")
        self.assertIn("actions/runs/4/jobs?filter=latest", paged.call_args.args[0])

    def test_required_merge_gate_conclusion_fails_closed_on_lookup_and_job_shape(self) -> None:
        for bad_run in (
            {**effective_run("failure"), "id": True},
            {**effective_run("failure"), "head_sha": ""},
        ):
            with self.subTest(bad_run=bad_run):
                with self.assertRaisesRegex(RuntimeError, "required-check lookup"):
                    bootstrap.required_merge_gate_conclusion("o/r", bad_run, "t")

        malformed_jobs = [
            [job("success", name="CodeQL")],
            [job("success"), job("neutral", job_id=41)],
            [job("success", job_id=True)],
            [job("success", run_id=99)],
            [job("success", name="")],
            [job("success", status="in_progress")],
            [job("mystery")],
            [job("success", head_sha="other")],
            [job("success"), job("success", job_id=41, name="CodeQL", status="in_progress")],
        ]
        for rows in malformed_jobs:
            with self.subTest(rows=rows), mock.patch.object(bootstrap, "paged", return_value=rows):
                with self.assertRaises(RuntimeError):
                    bootstrap.required_merge_gate_conclusion("o/r", effective_run("failure"), "t")

    def test_all_required_check_merge_acceptable_conclusions_revalidate_even_if_workflow_failed(self) -> None:
        self.assertEqual(bootstrap.MERGE_ACCEPTABLE_CONCLUSIONS, {"success", "neutral", "skipped"})
        identity = ("o/r", "feature", "h")
        pr = current_pr()
        runs = {identity: effective_run("failure")}

        for conclusion in sorted(bootstrap.MERGE_ACCEPTABLE_CONCLUSIONS):
            with self.subTest(conclusion=conclusion), mock.patch.object(
                bootstrap, "open_pull_requests", return_value=[pr]
            ), mock.patch.object(
                bootstrap, "overlapping_closed_pr_windows", return_value={}
            ), mock.patch.object(
                bootstrap, "latest_completed_gate_runs", return_value=runs
            ), mock.patch.object(
                bootstrap, "required_merge_gate_conclusion", return_value=conclusion
            ) as required, mock.patch.object(
                bootstrap, "unresolved_review_threads", return_value=True
            ) as threads, mock.patch.object(
                bootstrap, "rerun_workflow"
            ) as rerun:
                self.assertEqual(bootstrap.poll("o/r", "t"), [4])
            required.assert_called_once_with("o/r", runs[identity], "t")
            threads.assert_called_once_with("o/r", 4, "t")
            rerun.assert_called_once_with("o/r", 4, "t")

    def test_non_merge_acceptable_required_check_blocks_revalidation_even_if_workflow_success_metadata_is_stale(self) -> None:
        identity = ("o/r", "feature", "h")
        pr = current_pr()
        runs = {identity: effective_run("success")}
        with mock.patch.object(bootstrap, "open_pull_requests", return_value=[pr]), mock.patch.object(
            bootstrap, "overlapping_closed_pr_windows", return_value={}
        ), mock.patch.object(
            bootstrap, "latest_completed_gate_runs", return_value=runs
        ), mock.patch.object(
            bootstrap, "required_merge_gate_conclusion", return_value="failure"
        ), mock.patch.object(
            bootstrap, "unresolved_review_threads"
        ) as threads, mock.patch.object(
            bootstrap, "rerun_workflow"
        ) as rerun:
            self.assertEqual(bootstrap.poll("o/r", "t"), [])
        threads.assert_not_called()
        rerun.assert_not_called()


if __name__ == "__main__":
    unittest.main()
