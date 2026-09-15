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
        "head": {"sha": "h", "ref": "feature", "repo": {"full_name": "o/r"}},
    }


def effective_run(
    conclusion: str,
    *,
    run_id: int = 4,
    run_number: int = 4,
    run_attempt: int = 1,
    updated_at: str = "2026-09-15T16:05:00Z",
    head_sha: str = "h",
) -> dict:
    return {
        "id": run_id,
        "run_number": run_number,
        "run_attempt": run_attempt,
        "head_sha": head_sha,
        "updated_at": updated_at,
        "conclusion": conclusion,
    }


def job(
    conclusion: str,
    *,
    job_id: int = 40,
    run_id: int = 4,
    run_attempt: int = 1,
    name: str | None = None,
    status: str = "completed",
    head_sha: str = "h",
) -> dict:
    return {
        "id": job_id,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "name": bootstrap.REQUIRED_GATE_JOB_NAME if name is None else name,
        "status": status,
        "conclusion": conclusion,
        "head_sha": head_sha,
    }


def direct_check(conclusion: str | None, *, status: str = "completed") -> dict:
    return {"status": status, "conclusion": conclusion}


class MergeAcceptableConclusionTests(unittest.TestCase):
    def test_required_merge_gate_conclusion_reads_exact_job_not_workflow_conclusion(self) -> None:
        run = effective_run("failure")
        rows = [job("failure", job_id=39, name="CodeQL"), job("neutral", job_id=40)]
        with mock.patch.object(bootstrap, "paged", return_value=rows) as paged:
            self.assertEqual(bootstrap.required_merge_gate_conclusion("o/r", run, "t"), "neutral")
        self.assertEqual(paged.call_args.args[2], "jobs")
        self.assertTrue(paged.call_args.kwargs["require_total_count"])
        self.assertEqual(paged.call_args.kwargs["unique_id_field"], "id")
        self.assertIn("actions/runs/4/jobs?filter=latest", paged.call_args.args[0])

    def test_required_merge_gate_conclusion_fails_closed_on_lookup_and_job_shape(self) -> None:
        for bad_run in (
            {**effective_run("failure"), "id": True},
            {**effective_run("failure"), "head_sha": ""},
            {**effective_run("failure"), "run_attempt": 0},
            {**effective_run("failure"), "run_attempt": True},
        ):
            with self.subTest(bad_run=bad_run):
                with self.assertRaisesRegex(RuntimeError, "required-check lookup"):
                    bootstrap.required_merge_gate_conclusion("o/r", bad_run, "t")

        malformed_jobs = [
            [job("success", name="CodeQL")],
            [job("success"), job("neutral", job_id=41)],
            [job("success", job_id=True)],
            [job("success", run_id=99)],
            [job("success", run_id=4.0)],
            [job("success", run_attempt=2)],
            [job("success", run_attempt=True)],
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

    def test_paged_total_count_is_required_for_sensitive_actions_collections(self) -> None:
        one = job("success")
        with mock.patch.object(bootstrap, "request_data", return_value={"total_count": 2, "jobs": [one]}):
            with self.assertRaisesRegex(RuntimeError, "incomplete paginated collection"):
                bootstrap.paged("https://example.invalid/jobs", "t", "jobs", require_total_count=True)

        for bad_count in (None, True, -1, "1"):
            with self.subTest(total_count=bad_count), mock.patch.object(
                bootstrap, "request_data", return_value={"total_count": bad_count, "jobs": [one]}
            ):
                with self.assertRaisesRegex(RuntimeError, "malformed paginated total_count"):
                    bootstrap.paged("https://example.invalid/jobs", "t", "jobs", require_total_count=True)

        with mock.patch.object(bootstrap, "request_data", return_value={"total_count": 0, "jobs": [one]}):
            with self.assertRaisesRegex(RuntimeError, "exceeds total_count"):
                bootstrap.paged("https://example.invalid/jobs", "t", "jobs", require_total_count=True)

        with mock.patch.object(bootstrap, "request_data", return_value={"total_count": 0, "jobs": []}):
            self.assertEqual(bootstrap.paged("https://example.invalid/jobs", "t", "jobs", require_total_count=True), [])

        consistent_first = {"total_count": 101, "jobs": [{"id": i} for i in range(100)]}
        consistent_second = {"total_count": 101, "jobs": [{"id": 100}]}
        with mock.patch.object(bootstrap, "request_data", side_effect=[consistent_first, consistent_second]):
            self.assertEqual(len(bootstrap.paged("https://example.invalid/jobs", "t", "jobs", require_total_count=True)), 101)

        first = {"total_count": 101, "jobs": [{"id": i} for i in range(100)]}
        second = {"total_count": 102, "jobs": [{"id": 100}]}
        with mock.patch.object(bootstrap, "request_data", side_effect=[first, second]):
            with self.assertRaisesRegex(RuntimeError, "inconsistent paginated total_count"):
                bootstrap.paged("https://example.invalid/jobs", "t", "jobs", require_total_count=True)

    def test_active_run_scope_uses_earliest_active_incarnation_bound_per_head(self) -> None:
        first = current_pr()
        same_sha_later = current_pr()
        same_sha_later["number"] = 5
        same_sha_later["created_at"] = "2026-09-15T17:00:00Z"
        same_sha_later["head"] = {"sha": "h", "ref": "other", "repo": {"full_name": "o/r"}}
        current = bootstrap._current_prs([first, same_sha_later])
        with mock.patch.object(bootstrap, "_bounded_completed_gate_runs", return_value=[]) as bounded:
            self.assertEqual(bootstrap.latest_completed_gate_runs("o/r", "t", active_prs=current), {})
        bounded.assert_called_once()
        repo, token, head, start, end = bounded.call_args.args
        self.assertEqual((repo, token, head), ("o/r", "t", "h"))
        self.assertEqual(start.isoformat(), "2026-09-15T16:00:00+00:00")
        self.assertGreaterEqual(end, start)

    def test_all_merge_acceptable_direct_checks_revalidate_even_if_target_workflow_failed(self) -> None:
        self.assertEqual(bootstrap.MERGE_ACCEPTABLE_CONCLUSIONS, {"success", "neutral", "skipped"})
        identity = ("o/r", "feature", "h")
        pr = current_pr()
        target = effective_run("failure")
        runs = {identity: target}

        for conclusion in sorted(bootstrap.MERGE_ACCEPTABLE_CONCLUSIONS):
            with self.subTest(conclusion=conclusion), mock.patch.object(
                bootstrap, "open_pull_requests", return_value=[pr]
            ), mock.patch.object(
                bootstrap, "overlapping_closed_pr_windows", return_value={}
            ), mock.patch.object(
                bootstrap, "latest_completed_gate_runs", return_value=runs
            ), mock.patch.object(
                bootstrap, "latest_required_check", return_value=direct_check(conclusion)
            ) as check, mock.patch.object(
                bootstrap, "required_merge_gate_conclusion", return_value="failure"
            ) as required, mock.patch.object(
                bootstrap, "unresolved_review_threads", return_value=True
            ) as threads, mock.patch.object(
                bootstrap, "rerun_workflow"
            ) as rerun:
                self.assertEqual(bootstrap.poll("o/r", "t"), [4])
            check.assert_called_once_with("o/r", "h", "t")
            required.assert_called_once_with("o/r", target, "t")
            threads.assert_called_once_with("o/r", 4, "t")
            rerun.assert_called_once_with("o/r", 4, "t")

    def test_target_required_job_is_validated_before_rerun(self) -> None:
        pr = current_pr()
        identity = ("o/r", "feature", "h")
        target = effective_run("failure", run_id=4, run_number=4, updated_at="2026-09-15T16:04:00Z")
        with mock.patch.object(bootstrap, "open_pull_requests", return_value=[pr]), mock.patch.object(
            bootstrap, "overlapping_closed_pr_windows", return_value={}
        ), mock.patch.object(
            bootstrap, "latest_completed_gate_runs", return_value={identity: target}
        ), mock.patch.object(
            bootstrap, "latest_required_check", return_value=direct_check("success")
        ), mock.patch.object(
            bootstrap, "unresolved_review_threads", return_value=True
        ), mock.patch.object(
            bootstrap, "required_merge_gate_conclusion", side_effect=RuntimeError("bad target job")
        ) as required, mock.patch.object(
            bootstrap, "rerun_workflow"
        ) as rerun:
            with self.assertRaisesRegex(RuntimeError, "bad target job"):
                bootstrap.poll("o/r", "t")
        required.assert_called_once_with("o/r", target, "t")
        rerun.assert_not_called()

    def test_target_job_cache_keys_exact_run_and_attempt(self) -> None:
        first = current_pr()
        second = current_pr()
        second["number"] = 5
        identity = ("o/r", "feature", "h")
        target = effective_run("failure", run_id=4, run_attempt=2)
        with mock.patch.object(bootstrap, "open_pull_requests", return_value=[first, second]), mock.patch.object(
            bootstrap, "overlapping_closed_pr_windows", return_value={}
        ), mock.patch.object(
            bootstrap, "latest_completed_gate_runs", return_value={identity: target}
        ), mock.patch.object(
            bootstrap, "latest_required_check", return_value=direct_check("success")
        ), mock.patch.object(
            bootstrap, "unresolved_review_threads", return_value=True
        ), mock.patch.object(
            bootstrap, "required_merge_gate_conclusion", return_value="failure"
        ) as required, mock.patch.object(
            bootstrap, "rerun_workflow"
        ) as rerun:
            self.assertEqual(bootstrap.poll("o/r", "t"), [4, 4])
        required.assert_called_once_with("o/r", target, "t")
        self.assertEqual(rerun.call_count, 2)

    def test_non_merge_acceptable_direct_check_blocks_revalidation(self) -> None:
        identity = ("o/r", "feature", "h")
        pr = current_pr()
        runs = {identity: effective_run("success")}
        with mock.patch.object(bootstrap, "open_pull_requests", return_value=[pr]), mock.patch.object(
            bootstrap, "overlapping_closed_pr_windows", return_value={}
        ), mock.patch.object(
            bootstrap, "latest_completed_gate_runs", return_value=runs
        ), mock.patch.object(
            bootstrap, "latest_required_check", return_value=direct_check("failure")
        ), mock.patch.object(
            bootstrap, "unresolved_review_threads"
        ) as threads, mock.patch.object(
            bootstrap, "required_merge_gate_conclusion"
        ) as target_job, mock.patch.object(
            bootstrap, "rerun_workflow"
        ) as rerun:
            self.assertEqual(bootstrap.poll("o/r", "t"), [])
        threads.assert_not_called()
        target_job.assert_not_called()
        rerun.assert_not_called()


if __name__ == "__main__":
    unittest.main()
