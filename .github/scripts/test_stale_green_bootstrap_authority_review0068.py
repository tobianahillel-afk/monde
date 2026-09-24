from __future__ import annotations

import os
import runpy
import unittest
from unittest import mock

from test_stale_green_bootstrap_authority import check, gate_run, job, pr
import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0049 as pending
import stale_green_bootstrap_authority_review0051_recovery as recovery
import stale_green_bootstrap_authority_review0060 as attempt
import stale_green_bootstrap_authority_review0061 as chronology
import stale_green_bootstrap_authority_review0062 as terminal
import stale_green_bootstrap_authority_review0064 as temporal
import stale_green_bootstrap_authority_review0067 as previous
import stale_green_bootstrap_authority_review0068 as subject


HEAD = "a" * 40


def run_row(
    run_id: int,
    *,
    created: str = "2026-09-23T08:00:00Z",
    started: str = "2026-09-23T08:01:00Z",
    updated: str = "2026-09-23T08:02:00Z",
    run_number: int | None = None,
) -> dict:
    item = gate_run(
        run_id,
        1,
        branch="shared",
        head=HEAD,
        created_at=created,
        updated_at=updated,
        run_number=run_number or run_id,
    )
    item["run_started_at"] = started
    return item


def candidate_run() -> dict:
    return run_row(
        116,
        created="2026-09-23T10:00:00Z",
        started="2026-09-23T10:01:00Z",
        updated="2026-09-23T10:10:00Z",
    )


def candidate_check() -> dict:
    item = check(
        616,
        116,
        head=HEAD,
        completed_at="2026-09-23T10:05:00Z",
    )
    item["started_at"] = "2026-09-23T10:02:00Z"
    return item


def candidate_job() -> dict:
    item = job(616, 116, head=HEAD)
    item["started_at"] = "2026-09-23T10:02:00Z"
    item["completed_at"] = "2026-09-23T10:05:00Z"
    return item


def overlap_job(job_id: int, run_id: int, started: str) -> dict:
    item = job(job_id, run_id, head=HEAD)
    item["started_at"] = started
    item["completed_at"] = "2026-09-23T10:06:00Z"
    return item


class Review0068WitnessTests(unittest.TestCase):
    def setUp(self) -> None:
        base._reset_request_budget()
        self._original_core_request = core.request_data
        self._original_core_latest = core.latest_required_check
        self._original_pending_process = pending._process_head_group
        self._original_terminal_prove = terminal._ORIGINAL_CHRONOLOGY_PROVE
        self._original_chronology_prove = chronology._chronology_prove_candidate_attempt_frontier
        self._original_chronology_validator = chronology._validate_attempt_job_chronology
        self._original_network = base._ORIGINAL_REQUEST_DATA

    def tearDown(self) -> None:
        core.request_data = self._original_core_request
        core.latest_required_check = self._original_core_latest
        pending._process_head_group = self._original_pending_process
        terminal._ORIGINAL_CHRONOLOGY_PROVE = self._original_terminal_prove
        chronology._chronology_prove_candidate_attempt_frontier = self._original_chronology_prove
        chronology._validate_attempt_job_chronology = self._original_chronology_validator
        base._ORIGINAL_REQUEST_DATA = self._original_network
        base._reset_request_budget()

    def test_snapshots_validate_and_bind_identity(self) -> None:
        run = candidate_run()
        chk = candidate_check()
        jb = candidate_job()
        self.assertEqual(subject._check_snapshot(chk, HEAD)[0], 616)
        self.assertEqual(subject._run_snapshot(run, HEAD)[0], 116)
        self.assertEqual(subject._job_snapshot(jb, run, HEAD)[:2], (616, 116))
        rows = subject._frontier_snapshot([run], HEAD)
        self.assertEqual(rows[0][0], 116)

        with self.assertRaisesRegex(RuntimeError, "duplicate run identity"):
            subject._frontier_snapshot([run, dict(run)], HEAD)

        malformed_run = dict(run)
        malformed_run["id"] = True
        with self.assertRaisesRegex(RuntimeError, "malformed canonical.*run id"):
            subject._run_snapshot(malformed_run, HEAD)

        bad_job = dict(jb)
        bad_job["id"] = True
        with self.assertRaisesRegex(RuntimeError, "malformed protected.*job id"):
            subject._job_snapshot(bad_job, run, HEAD)

    def test_bounded_overlap_skips_old_jobs_and_accepts_candidate(self) -> None:
        cand_run = candidate_run()
        cand_check = candidate_check()
        cand_job = candidate_job()
        old = [run_row(i) for i in range(101, 116)]
        rows = old + [cand_run]

        def request(url: str, _token: str):
            if url.endswith("/actions/runs/116"):
                return cand_run
            if url.endswith("/actions/jobs/616"):
                return cand_job
            raise AssertionError(url)

        with (
            mock.patch.object(core, "request_data", side_effect=request),
            mock.patch.object(attempt, "_attempt_frontier_runs", return_value=rows),
            mock.patch.object(
                chronology,
                "_chronology_protected_gate_job",
                return_value=cand_job,
            ) as protected,
        ):
            subject._bounded_overlap_prove(
                "o/r",
                HEAD,
                "t",
                cand_check,
                core._timestamp("2026-09-23T10:20:00Z", "frontier"),
            )
        protected.assert_called_once()
        self.assertEqual(protected.call_args.args[2]["id"], 116)

    def test_bounded_overlap_rejects_newer_attempt_without_job_lookup(self) -> None:
        cand_run = candidate_run()
        cand_check = candidate_check()
        cand_job = candidate_job()
        newer = run_row(
            117,
            created="2026-09-23T10:02:30Z",
            started="2026-09-23T10:03:00Z",
            updated="2026-09-23T10:04:00Z",
        )

        def request(url: str, _token: str):
            if url.endswith("/actions/runs/116"):
                return cand_run
            if url.endswith("/actions/jobs/616"):
                return cand_job
            raise AssertionError(url)

        with (
            mock.patch.object(core, "request_data", side_effect=request),
            mock.patch.object(
                attempt, "_attempt_frontier_runs", return_value=[cand_run, newer]
            ),
            mock.patch.object(
                chronology,
                "_chronology_protected_gate_job",
                return_value=cand_job,
            ) as protected,
        ):
            with self.assertRaisesRegex(RuntimeError, "newer canonical.*attempt"):
                subject._bounded_overlap_prove(
                    "o/r",
                    HEAD,
                    "t",
                    cand_check,
                    core._timestamp("2026-09-23T10:20:00Z", "frontier"),
                )
        self.assertEqual(protected.call_count, 1)
        self.assertEqual(protected.call_args.args[2]["id"], 116)

    def test_bounded_overlap_reads_competitor_and_rejects_newer_job(self) -> None:
        cand_run = candidate_run()
        cand_check = candidate_check()
        cand_job = candidate_job()
        competitor = run_row(
            117,
            created="2026-09-23T09:50:00Z",
            started="2026-09-23T10:00:30Z",
            updated="2026-09-23T10:08:00Z",
        )
        competitor_job = overlap_job(617, 117, "2026-09-23T10:03:00Z")

        def request(url: str, _token: str):
            if url.endswith("/actions/runs/116"):
                return cand_run
            if url.endswith("/actions/jobs/616"):
                return cand_job
            raise AssertionError(url)

        def protected(_repo, _token, run, _head):
            return cand_job if run["id"] == 116 else competitor_job

        with (
            mock.patch.object(core, "request_data", side_effect=request),
            mock.patch.object(
                attempt,
                "_attempt_frontier_runs",
                return_value=[cand_run, competitor],
            ),
            mock.patch.object(
                chronology,
                "_chronology_protected_gate_job",
                side_effect=protected,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "newer protected.*job"):
                subject._bounded_overlap_prove(
                    "o/r",
                    HEAD,
                    "t",
                    cand_check,
                    core._timestamp("2026-09-23T10:20:00Z", "frontier"),
                )

    def test_bounded_overlap_fail_closed_candidate_shapes(self) -> None:
        cand_run = candidate_run()
        cand_check = candidate_check()
        cand_job = candidate_job()
        frontier = core._timestamp("2026-09-23T10:20:00Z", "frontier")

        with mock.patch.object(core, "request_data", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "malformed candidate canonical"):
                subject._bounded_overlap_prove("o/r", HEAD, "t", cand_check, frontier)

        with (
            mock.patch.object(
                core, "request_data", side_effect=[cand_run, cand_job]
            ),
            mock.patch.object(attempt, "_attempt_frontier_runs", return_value=[]),
        ):
            with self.assertRaisesRegex(RuntimeError, "absent from attempt frontier"):
                subject._bounded_overlap_prove("o/r", HEAD, "t", cand_check, frontier)

        changed = dict(cand_run)
        changed["run_attempt"] = 2
        changed["run_started_at"] = "2026-09-23T10:01:00Z"
        with (
            mock.patch.object(
                core, "request_data", side_effect=[cand_run, cand_job]
            ),
            mock.patch.object(
                attempt, "_attempt_frontier_runs", return_value=[changed]
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "changed during authority proof"):
                subject._bounded_overlap_prove("o/r", HEAD, "t", cand_check, frontier)

    def test_prove_with_witness_captures_frontier_and_overlap_jobs(self) -> None:
        cand = candidate_check()
        run = candidate_run()
        jb = candidate_job()

        def latest(_repo, _head, _token):
            rows = attempt._attempt_frontier_runs(
                "o/r",
                HEAD,
                "t",
                core._timestamp("2026-09-23T10:20:00Z", "frontier"),
            )
            self.assertEqual(rows[0]["id"], 116)
            chronology._chronology_protected_gate_job("o/r", "t", rows[0], HEAD)
            return cand

        with (
            mock.patch.object(core, "latest_required_check", side_effect=latest),
            mock.patch.object(attempt, "_attempt_frontier_runs", return_value=[run]),
            mock.patch.object(
                chronology,
                "_chronology_protected_gate_job",
                return_value=jb,
            ),
        ):
            candidate, witness = subject._prove_with_witness("o/r", HEAD, "t")
        self.assertIs(candidate, cand)
        self.assertIsNotNone(witness)
        assert witness is not None
        self.assertEqual(witness.candidate_check[0], 616)
        self.assertEqual(witness.frontier_runs[0][0], 116)
        self.assertEqual(witness.overlap_jobs[0][0], 116)

        with mock.patch.object(
            core,
            "latest_required_check",
            return_value={**cand, "conclusion": "failure"},
        ):
            nonmerge, no_witness = subject._prove_with_witness("o/r", HEAD, "t")
        self.assertEqual(nonmerge["conclusion"], "failure")
        self.assertIsNone(no_witness)

        with mock.patch.object(core, "latest_required_check", return_value=cand):
            with self.assertRaisesRegex(RuntimeError, "did not expose its Actions frontier"):
                subject._prove_with_witness("o/r", HEAD, "t")

    def test_revalidate_witness_accepts_exact_snapshot_and_rejects_drift(self) -> None:
        cand = candidate_check()
        run = candidate_run()
        jb = candidate_job()
        witness = subject.AuthorityWitness(
            candidate_check=subject._check_snapshot(cand, HEAD),
            frontier_runs=subject._frontier_snapshot([run], HEAD),
            overlap_jobs=((116, subject._job_snapshot(jb, run, HEAD)),),
        )

        with (
            mock.patch.object(
                attempt.previous,
                "_authority_frontier",
                return_value=core._timestamp("2026-09-23T10:21:00Z", "frontier"),
            ),
            mock.patch.object(attempt, "_attempt_frontier_runs", return_value=[run]),
            mock.patch.object(
                chronology, "_chronology_protected_gate_job", return_value=jb
            ),
            mock.patch.object(core, "request_data", return_value=cand),
        ):
            subject._revalidate_witness("o/r", HEAD, "t", witness)

        changed_run = dict(run)
        changed_run["updated_at"] = "2026-09-23T10:11:00Z"
        with (
            mock.patch.object(
                attempt.previous,
                "_authority_frontier",
                return_value=core._timestamp("2026-09-23T10:21:00Z", "frontier"),
            ),
            mock.patch.object(
                attempt, "_attempt_frontier_runs", return_value=[changed_run]
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "frontier changed"):
                subject._revalidate_witness("o/r", HEAD, "t", witness)

        with (
            mock.patch.object(
                attempt.previous,
                "_authority_frontier",
                return_value=core._timestamp("2026-09-23T10:21:00Z", "frontier"),
            ),
            mock.patch.object(attempt, "_attempt_frontier_runs", return_value=[]),
        ):
            with self.assertRaisesRegex(RuntimeError, "frontier changed"):
                subject._revalidate_witness("o/r", HEAD, "t", witness)

        drifted_job = dict(jb)
        drifted_job["completed_at"] = "2026-09-23T10:06:00Z"
        drifted_witness = subject.AuthorityWitness(
            candidate_check=witness.candidate_check,
            frontier_runs=witness.frontier_runs,
            overlap_jobs=((116, witness.overlap_jobs[0][1]),),
        )
        with (
            mock.patch.object(
                attempt.previous,
                "_authority_frontier",
                return_value=core._timestamp("2026-09-23T10:21:00Z", "frontier"),
            ),
            mock.patch.object(attempt, "_attempt_frontier_runs", return_value=[run]),
            mock.patch.object(
                chronology,
                "_chronology_protected_gate_job",
                return_value=drifted_job,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "job changed"):
                subject._revalidate_witness(
                    "o/r", HEAD, "t", drifted_witness
                )

        with (
            mock.patch.object(
                attempt.previous,
                "_authority_frontier",
                return_value=core._timestamp("2026-09-23T10:21:00Z", "frontier"),
            ),
            mock.patch.object(attempt, "_attempt_frontier_runs", return_value=[run]),
            mock.patch.object(
                chronology, "_chronology_protected_gate_job", return_value=jb
            ),
            mock.patch.object(
                core,
                "request_data",
                return_value={**cand, "conclusion": "neutral"},
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "check changed"):
                subject._revalidate_witness("o/r", HEAD, "t", witness)

    def test_two_stage_process_positive_and_gate_outcomes(self) -> None:
        current = pr(1, branch="shared", head=HEAD)
        target_run = candidate_run()
        target = (target_run, candidate_check())
        cand = candidate_check()
        witness = subject.AuthorityWitness(
            candidate_check=subject._check_snapshot(cand, HEAD),
            frontier_runs=subject._frontier_snapshot([target_run], HEAD),
            overlap_jobs=(),
        )

        with (
            mock.patch.object(core, "unresolved_review_threads", return_value=True),
            mock.patch.object(
                pending.previous,
                "_direct_target_for_pr",
                return_value=(target, None),
            ),
            mock.patch.object(base, "_current_pr", return_value=current),
            mock.patch.object(
                pending.previous, "_mutation_baseline", return_value=1
            ),
            mock.patch.object(
                subject, "_prove_with_witness", return_value=(cand, witness)
            ),
            mock.patch.object(
                pending, "_current_pending_pr", return_value=current
            ),
            mock.patch.object(subject, "_revalidate_witness"),
            mock.patch.object(
                subject.base,
                "_remaining_request_budget",
                side_effect=[
                    subject.base.MAX_GITHUB_REQUESTS_PER_INVOCATION,
                    pending.MUTATION_REQUEST_RESERVE,
                ],
            ),
            mock.patch.object(pending, "_write_state") as writer,
            mock.patch.object(core, "rerun_workflow") as rerun,
            mock.patch.object(
                pending.previous,
                "_wait_for_terminal_invalidation",
                return_value=True,
            ),
        ):
            result = subject._two_stage_process(
                "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
            )
        self.assertEqual(result, ([116], [], None))
        self.assertEqual(writer.call_count, 2)
        rerun.assert_called_once_with("o/r", 116, "t")

        for candidate, expected in (
            (None, ([], [], None)),
            ({**cand, "status": "in_progress", "conclusion": None}, ([], [], (1, base.ScanPage(1)))),
            ({**cand, "conclusion": "failure"}, ([], [], None)),
        ):
            with (
                self.subTest(candidate=candidate),
                mock.patch.object(core, "unresolved_review_threads", return_value=True),
                mock.patch.object(
                    pending.previous,
                    "_direct_target_for_pr",
                    return_value=(target, None),
                ),
                mock.patch.object(base, "_current_pr", return_value=current),
                mock.patch.object(
                    pending.previous, "_mutation_baseline", return_value=1
                ),
                mock.patch.object(
                    subject,
                    "_prove_with_witness",
                    return_value=(candidate, None),
                ),
            ):
                self.assertEqual(
                    subject._two_stage_process(
                        "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                    ),
                    expected,
                )

    def test_two_stage_process_fail_closed_pre_mutation_paths(self) -> None:
        current = pr(1, branch="shared", head=HEAD)
        target = (candidate_run(), candidate_check())
        cand = candidate_check()
        witness = subject.AuthorityWitness(
            subject._check_snapshot(cand, HEAD),
            subject._frontier_snapshot([candidate_run()], HEAD),
            (),
        )

        with mock.patch.object(core, "unresolved_review_threads", return_value=False):
            self.assertEqual(
                subject._two_stage_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                ),
                ([], [], None),
            )

        with (
            mock.patch.object(core, "unresolved_review_threads", return_value=True),
            mock.patch.object(
                pending.previous,
                "_direct_target_for_pr",
                return_value=(None, None),
            ),
        ):
            result = subject._two_stage_process(
                "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
            )
        self.assertEqual(result[0], [])
        self.assertIn("no canonical rerun target", result[1][0])

        with (
            mock.patch.object(core, "unresolved_review_threads", return_value=True),
            mock.patch.object(
                pending.previous,
                "_direct_target_for_pr",
                return_value=(target, base.ScanPage(2, "f" * 64)),
            ),
        ):
            result = subject._two_stage_process(
                "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
            )
        self.assertEqual(int(result[2][1]), 2)

        for current_pr, baseline in ((None, 1), (current, None)):
            with (
                mock.patch.object(core, "unresolved_review_threads", return_value=True),
                mock.patch.object(
                    pending.previous,
                    "_direct_target_for_pr",
                    return_value=(target, None),
                ),
                mock.patch.object(base, "_current_pr", return_value=current_pr),
                mock.patch.object(
                    pending.previous,
                    "_mutation_baseline",
                    return_value=baseline,
                ),
            ):
                result = subject._two_stage_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                )
            self.assertEqual(result[0], [])

        with (
            mock.patch.object(core, "unresolved_review_threads", return_value=True),
            mock.patch.object(
                pending.previous,
                "_direct_target_for_pr",
                return_value=(target, None),
            ),
            mock.patch.object(base, "_current_pr", return_value=current),
            mock.patch.object(
                pending.previous, "_mutation_baseline", return_value=1
            ),
            mock.patch.object(
                subject, "_prove_with_witness", return_value=(cand, None)
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "lacks reusable"):
                subject._two_stage_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                )

        with (
            mock.patch.object(core, "unresolved_review_threads", return_value=True),
            mock.patch.object(
                pending.previous,
                "_direct_target_for_pr",
                return_value=(target, None),
            ),
            mock.patch.object(base, "_current_pr", return_value=current),
            mock.patch.object(
                pending.previous, "_mutation_baseline", return_value=1
            ),
            mock.patch.object(
                subject, "_prove_with_witness", return_value=(cand, witness)
            ),
            mock.patch.object(
                pending, "_current_pending_pr", side_effect=[current, None]
            ),
        ):
            result = subject._two_stage_process(
                "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
            )
        self.assertIsNotNone(result[2])

        with (
            mock.patch.object(core, "unresolved_review_threads", return_value=True),
            mock.patch.object(
                pending.previous,
                "_direct_target_for_pr",
                return_value=(target, None),
            ),
            mock.patch.object(base, "_current_pr", return_value=current),
            mock.patch.object(
                pending.previous, "_mutation_baseline", return_value=1
            ),
            mock.patch.object(
                subject, "_prove_with_witness", return_value=(cand, witness)
            ),
            mock.patch.object(
                pending, "_current_pending_pr", return_value=current
            ),
            mock.patch.object(subject, "_revalidate_witness"),
            mock.patch.object(
                subject.base,
                "_remaining_request_budget",
                side_effect=[
                    subject.base.MAX_GITHUB_REQUESTS_PER_INVOCATION,
                    pending.MUTATION_REQUEST_RESERVE - 1,
                ],
            ),
        ):
            with self.assertRaisesRegex(
                subject.base.DeferredForBudget, "after reusable Gate witness"
            ):
                subject._two_stage_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                )

    def test_safe_wrapper_preserves_pending_lifetime_and_write_ack(self) -> None:
        current = pr(1, branch="shared", head=HEAD)
        state = pending._pending_state(
            pending.SchedulerStateV4(0), current, 116, 1, 616
        )

        with (
            mock.patch.object(
                subject,
                "_two_stage_process",
                side_effect=lambda *_a, **_k: pending._write_state(
                    "o/r", "t", state
                ),
            ),
            mock.patch.object(
                pending, "_write_state", side_effect=RuntimeError("ack lost")
            ),
        ):
            with self.assertRaisesRegex(
                pending.PendingMutationUncertain, "acknowledgement is ambiguous"
            ):
                subject._safe_two_stage_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                )

        writer = mock.Mock()
        def active_then_fail(*_a, **_k):
            pending._write_state("o/r", "t", state)
            raise RuntimeError("later failed")

        with (
            mock.patch.object(subject, "_two_stage_process", side_effect=active_then_fail),
            mock.patch.object(pending, "_write_state", writer),
        ):
            with self.assertRaisesRegex(
                pending.PendingMutationUncertain, "durable pending mutation remained active"
            ):
                subject._safe_two_stage_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                )

        existing = pending.PendingMutationObservation(116)
        with mock.patch.object(
            subject, "_two_stage_process", side_effect=existing
        ):
            with self.assertRaises(pending.PendingMutationObservation) as raised:
                subject._safe_two_stage_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                )
        self.assertIs(raised.exception, existing)

    def test_real_budget_sixteen_historical_runs_reaches_pending_write(self) -> None:
        current = pr(1, branch="shared", head=HEAD)
        cand_run = candidate_run()
        cand_check = candidate_check()
        cand_job = candidate_job()
        rows = [run_row(i) for i in range(101, 116)] + [cand_run]
        target = (cand_run, cand_check)
        pending_write_budget: list[int] = []

        def network(url: str, _token: str, method: str = "GET", body=None):
            if "/commits/" in url and "/check-runs?" in url:
                return {"total_count": 1, "check_runs": [cand_check]}
            if url.endswith("/actions/runs/116"):
                return cand_run
            if url.endswith("/actions/jobs/616"):
                return cand_job
            if "/actions/workflows/" in url and "/runs?" in url:
                return {"total_count": len(rows), "workflow_runs": rows}
            if "/actions/runs/116/jobs?" in url:
                return {"total_count": 1, "jobs": [cand_job]}
            if url.endswith("/check-runs/616"):
                return cand_check
            raise AssertionError(f"unexpected live-budget fixture request: {method} {url}")

        original_latest = core.latest_required_check
        original_terminal = terminal._ORIGINAL_CHRONOLOGY_PROVE
        original_chronology_prove = chronology._chronology_prove_candidate_attempt_frontier
        original_request = core.request_data
        original_network = base._ORIGINAL_REQUEST_DATA
        original_validator = chronology._validate_attempt_job_chronology
        try:
            import stale_green_bootstrap_authority_review0063 as containment

            # Install only the authority chain needed by the liveness proof.
            # Do not call subject.install(): that recursively rewires global
            # scheduler hooks and would contaminate unrelated unit tests.
            terminal._ORIGINAL_CHRONOLOGY_PROVE = subject._bounded_overlap_prove
            chronology._chronology_prove_candidate_attempt_frontier = (
                temporal._temporal_prove_candidate_attempt_frontier
            )
            chronology._validate_attempt_job_chronology = (
                containment._validate_full_run_job_containment
            )
            core.latest_required_check = temporal._temporal_latest_required_check
            base._reset_request_budget()
            base._ORIGINAL_REQUEST_DATA = network
            core.request_data = base._budgeted_request_data

            def writer(_repo, _token, state):
                if state.pending_pr:
                    pending_write_budget.append(base._request_count)

            with (
                mock.patch.object(core, "unresolved_review_threads", return_value=True),
                mock.patch.object(
                    pending.previous,
                    "_direct_target_for_pr",
                    return_value=(target, None),
                ),
                mock.patch.object(base, "_current_pr", return_value=current),
                mock.patch.object(
                    pending.previous, "_mutation_baseline", return_value=1
                ),
                mock.patch.object(
                    pending, "_current_pending_pr", return_value=current
                ),
                mock.patch.object(pending, "_write_state", side_effect=writer),
                mock.patch.object(core, "rerun_workflow"),
                mock.patch.object(
                    pending.previous,
                    "_wait_for_terminal_invalidation",
                    return_value=True,
                ),
            ):
                result = subject._safe_two_stage_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                )
            self.assertEqual(result[0], [116])
            self.assertEqual(len(pending_write_budget), 1)
            self.assertLessEqual(
                pending_write_budget[0],
                base.MAX_GITHUB_REQUESTS_PER_INVOCATION
                - pending.MUTATION_REQUEST_RESERVE,
            )
            self.assertLess(base._request_count, base.MAX_GITHUB_REQUESTS_PER_INVOCATION)
        finally:
            core.latest_required_check = original_latest
            terminal._ORIGINAL_CHRONOLOGY_PROVE = original_terminal
            chronology._chronology_prove_candidate_attempt_frontier = (
                original_chronology_prove
            )
            core.request_data = original_request
            base._ORIGINAL_REQUEST_DATA = original_network
            chronology._validate_attempt_job_chronology = original_validator
            base._reset_request_budget()

    def test_defensive_snapshot_and_authority_fail_closed_edges(self) -> None:
        cand_run = candidate_run()
        cand_check = candidate_check()
        cand_job = candidate_job()
        frontier = core._timestamp("2026-09-23T10:20:00Z", "frontier")

        inconsistent = dict(cand_run)
        inconsistent["updated_at"] = "2026-09-23T10:00:30Z"
        with mock.patch.object(
            subject.attempt,
            "_run_attempt_started_at",
            return_value=core._timestamp("2026-09-23T10:01:00Z", "started"),
        ):
            with self.assertRaisesRegex(RuntimeError, "updated before current attempt"):
                subject._run_snapshot(inconsistent, HEAD)

        bad_run = dict(cand_run)
        bad_run["id"] = True
        with self.assertRaisesRegex(RuntimeError, "malformed canonical.*run id"):
            subject._job_snapshot(cand_job, bad_run, HEAD)

        with self.assertRaisesRegex(RuntimeError, "frontier precedes candidate check"):
            subject._bounded_overlap_prove(
                "o/r",
                HEAD,
                "t",
                cand_check,
                core._timestamp("2026-09-23T10:01:00Z", "frontier"),
            )

        run_after = run_row(
            116,
            created="2026-09-23T10:00:00Z",
            started="2026-09-23T10:21:00Z",
            updated="2026-09-23T10:22:00Z",
        )
        with mock.patch.object(core, "request_data", return_value=run_after):
            with self.assertRaisesRegex(RuntimeError, "attempt started after authority frontier"):
                subject._bounded_overlap_prove("o/r", HEAD, "t", cand_check, frontier)

        with mock.patch.object(
            core, "request_data", side_effect=[cand_run, []]
        ):
            with self.assertRaisesRegex(RuntimeError, "malformed candidate protected"):
                subject._bounded_overlap_prove("o/r", HEAD, "t", cand_check, frontier)

        start_mismatch = dict(cand_job)
        start_mismatch["started_at"] = "2026-09-23T10:03:00Z"
        conclusion_mismatch = dict(cand_job)
        conclusion_mismatch["conclusion"] = "failure"
        for direct_job, message in (
            (start_mismatch, "start identity"),
            (conclusion_mismatch, "protected job conclusion"),
        ):
            with (
                self.subTest(message=message),
                mock.patch.object(
                    core, "request_data", side_effect=[cand_run, direct_job]
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, message):
                    subject._bounded_overlap_prove(
                        "o/r", HEAD, "t", cand_check, frontier
                    )

        frontier_after = run_row(
            117,
            created="2026-09-23T10:10:00Z",
            started="2026-09-23T10:21:00Z",
            updated="2026-09-23T10:22:00Z",
        )
        with (
            mock.patch.object(
                core, "request_data", side_effect=[cand_run, cand_job]
            ),
            mock.patch.object(
                attempt,
                "_attempt_frontier_runs",
                return_value=[cand_run, frontier_after],
            ),
            mock.patch.object(
                chronology,
                "_chronology_protected_gate_job",
                return_value=cand_job,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "attempt started after authority frontier"):
                subject._bounded_overlap_prove("o/r", HEAD, "t", cand_check, frontier)

        late_job = dict(cand_job)
        late_job["started_at"] = "2026-09-23T10:21:00Z"
        late_job["completed_at"] = "2026-09-23T10:21:30Z"
        with (
            mock.patch.object(
                core, "request_data", side_effect=[cand_run, cand_job]
            ),
            mock.patch.object(
                attempt, "_attempt_frontier_runs", return_value=[cand_run]
            ),
            mock.patch.object(
                chronology,
                "_chronology_protected_gate_job",
                return_value=late_job,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "job started after authority frontier"):
                subject._bounded_overlap_prove("o/r", HEAD, "t", cand_check, frontier)

        old = run_row(101)
        with (
            mock.patch.object(
                core, "request_data", side_effect=[cand_run, cand_job]
            ),
            mock.patch.object(attempt, "_attempt_frontier_runs", return_value=[old]),
        ):
            with self.assertRaisesRegex(RuntimeError, "absent or ambiguous"):
                subject._bounded_overlap_prove("o/r", HEAD, "t", cand_check, frontier)

        frontier_candidate = dict(cand_run)
        frontier_candidate["updated_at"] = "2026-09-23T10:01:30Z"
        with (
            mock.patch.object(
                core, "request_data", side_effect=[cand_run, cand_job]
            ),
            mock.patch.object(
                attempt,
                "_attempt_frontier_runs",
                return_value=[frontier_candidate],
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "protected job is absent"):
                subject._bounded_overlap_prove("o/r", HEAD, "t", cand_check, frontier)

    def test_witness_capture_and_revalidation_defensive_edges(self) -> None:
        nonmerge = {**candidate_check(), "conclusion": "failure"}
        original_job = mock.Mock(return_value={})

        def latest_with_invalid_capture(_repo, _head, _token):
            chronology._chronology_protected_gate_job(
                "o/r", "t", {"id": 0}, HEAD
            )
            return nonmerge

        with (
            mock.patch.object(
                chronology,
                "_chronology_protected_gate_job",
                original_job,
            ),
            mock.patch.object(
                core,
                "latest_required_check",
                side_effect=latest_with_invalid_capture,
            ),
        ):
            candidate, witness = subject._prove_with_witness("o/r", HEAD, "t")
        self.assertEqual(candidate["conclusion"], "failure")
        self.assertIsNone(witness)
        original_job.assert_called_once()

        cand = candidate_check()
        run = candidate_run()
        jb = candidate_job()
        base_witness = subject.AuthorityWitness(
            candidate_check=subject._check_snapshot(cand, HEAD),
            frontier_runs=subject._frontier_snapshot([run], HEAD),
            overlap_jobs=((999, subject._job_snapshot(jb, run, HEAD)),),
        )
        with (
            mock.patch.object(
                attempt.previous,
                "_authority_frontier",
                return_value=core._timestamp("2026-09-23T10:21:00Z", "frontier"),
            ),
            mock.patch.object(attempt, "_attempt_frontier_runs", return_value=[run]),
        ):
            with self.assertRaisesRegex(RuntimeError, "run disappeared"):
                subject._revalidate_witness("o/r", HEAD, "t", base_witness)

        no_overlap = subject.AuthorityWitness(
            candidate_check=subject._check_snapshot(cand, HEAD),
            frontier_runs=subject._frontier_snapshot([run], HEAD),
            overlap_jobs=(),
        )
        with (
            mock.patch.object(
                attempt.previous,
                "_authority_frontier",
                return_value=core._timestamp("2026-09-23T10:21:00Z", "frontier"),
            ),
            mock.patch.object(attempt, "_attempt_frontier_runs", return_value=[run]),
            mock.patch.object(core, "request_data", return_value=[]),
        ):
            with self.assertRaisesRegex(RuntimeError, "malformed direct required"):
                subject._revalidate_witness("o/r", HEAD, "t", no_overlap)

    def test_two_stage_processor_control_flow_edges(self) -> None:
        current = pr(1, branch="shared", head=HEAD)
        target = (candidate_run(), candidate_check())
        cand = candidate_check()
        witness = subject.AuthorityWitness(
            subject._check_snapshot(cand, HEAD),
            subject._frontier_snapshot([candidate_run()], HEAD),
            (),
        )

        self.assertEqual(
            subject._two_stage_process(
                "o/r", "t", [], 3, pending.SchedulerStateV4(0)
            ),
            ([], [], None),
        )
        self.assertEqual(
            subject._two_stage_process(
                "o/r", "t", [current], 0, pending.SchedulerStateV4(0)
            ),
            ([], [], None),
        )
        with mock.patch.object(
            subject.base, "_remaining_request_budget", return_value=0
        ):
            with self.assertRaisesRegex(
                subject.base.DeferredForBudget, "before sibling evaluation"
            ):
                subject._two_stage_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                )

        continuation = base.ScanPage(3, "e" * 64)
        with (
            mock.patch.object(
                subject.base,
                "_remaining_request_budget",
                return_value=subject.base.MAX_GITHUB_REQUESTS_PER_INVOCATION,
            ),
            mock.patch.object(core, "unresolved_review_threads", return_value=True),
            mock.patch.object(
                pending.previous,
                "_direct_target_for_pr",
                return_value=(target, continuation),
            ) as direct,
        ):
            result = subject._two_stage_process(
                "o/r",
                "t",
                [current],
                3,
                pending.SchedulerStateV4(0),
                1,
                2,
                "f" * 64,
            )
        self.assertEqual(int(result[2][1]), 3)
        self.assertEqual(direct.call_args.args[3:], (2, "f" * 64))

        with (
            mock.patch.object(
                subject.base,
                "_remaining_request_budget",
                return_value=subject.base.MAX_GITHUB_REQUESTS_PER_INVOCATION,
            ),
            mock.patch.object(
                core,
                "unresolved_review_threads",
                side_effect=[True, False],
            ),
            mock.patch.object(
                pending.previous,
                "_direct_target_for_pr",
                return_value=(target, None),
            ),
            mock.patch.object(base, "_current_pr", return_value=current),
        ):
            self.assertEqual(
                subject._two_stage_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                ),
                ([], [], None),
            )

        with (
            mock.patch.object(
                subject.base,
                "_remaining_request_budget",
                return_value=subject.base.MAX_GITHUB_REQUESTS_PER_INVOCATION,
            ),
            mock.patch.object(core, "unresolved_review_threads", return_value=True),
            mock.patch.object(
                pending.previous,
                "_direct_target_for_pr",
                return_value=(target, None),
            ),
            mock.patch.object(base, "_current_pr", side_effect=[current, None]),
            mock.patch.object(
                pending.previous, "_mutation_baseline", return_value=1
            ),
        ):
            result = subject._two_stage_process(
                "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
            )
        self.assertEqual(result[2][0], 1)

        with (
            mock.patch.object(
                subject.base,
                "_remaining_request_budget",
                return_value=subject.base.MAX_GITHUB_REQUESTS_PER_INVOCATION,
            ),
            mock.patch.object(
                core,
                "unresolved_review_threads",
                side_effect=[True, True, False],
            ),
            mock.patch.object(
                pending.previous,
                "_direct_target_for_pr",
                return_value=(target, None),
            ),
            mock.patch.object(base, "_current_pr", return_value=current),
            mock.patch.object(
                pending.previous, "_mutation_baseline", return_value=1
            ),
        ):
            self.assertEqual(
                subject._two_stage_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                ),
                ([], [], None),
            )

        with (
            mock.patch.object(
                subject.base,
                "_remaining_request_budget",
                return_value=subject.base.MAX_GITHUB_REQUESTS_PER_INVOCATION,
            ),
            mock.patch.object(core, "unresolved_review_threads", return_value=True),
            mock.patch.object(
                pending.previous,
                "_direct_target_for_pr",
                return_value=(target, None),
            ),
            mock.patch.object(base, "_current_pr", return_value=current),
            mock.patch.object(
                pending.previous, "_mutation_baseline", return_value=1
            ),
            mock.patch.object(
                subject, "_prove_with_witness", return_value=(cand, witness)
            ),
            mock.patch.object(pending, "_current_pending_pr", return_value=None),
        ):
            result = subject._two_stage_process(
                "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
            )
        self.assertEqual(result[2][0], 1)

        with (
            mock.patch.object(
                subject.base,
                "_remaining_request_budget",
                return_value=subject.base.MAX_GITHUB_REQUESTS_PER_INVOCATION,
            ),
            mock.patch.object(
                core,
                "unresolved_review_threads",
                side_effect=[True, True, True, False],
            ),
            mock.patch.object(
                pending.previous,
                "_direct_target_for_pr",
                return_value=(target, None),
            ),
            mock.patch.object(base, "_current_pr", return_value=current),
            mock.patch.object(
                pending.previous, "_mutation_baseline", return_value=1
            ),
            mock.patch.object(
                subject, "_prove_with_witness", return_value=(cand, witness)
            ),
            mock.patch.object(
                pending, "_current_pending_pr", return_value=current
            ),
        ):
            self.assertEqual(
                subject._two_stage_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                ),
                ([], [], None),
            )

    def test_two_stage_mutation_and_postcondition_edges(self) -> None:
        current = pr(1, branch="shared", head=HEAD)
        target = (candidate_run(), candidate_check())
        cand = candidate_check()
        witness = subject.AuthorityWitness(
            subject._check_snapshot(cand, HEAD),
            subject._frontier_snapshot([candidate_run()], HEAD),
            (),
        )

        def common_context(*, threads=True):
            return (
                mock.patch.object(
                    subject.base,
                    "_remaining_request_budget",
                    side_effect=[
                        subject.base.MAX_GITHUB_REQUESTS_PER_INVOCATION,
                        pending.MUTATION_REQUEST_RESERVE,
                    ],
                ),
                mock.patch.object(
                    core, "unresolved_review_threads", return_value=threads
                ),
                mock.patch.object(
                    pending.previous,
                    "_direct_target_for_pr",
                    return_value=(target, None),
                ),
                mock.patch.object(base, "_current_pr", return_value=current),
                mock.patch.object(
                    pending.previous, "_mutation_baseline", return_value=1
                ),
                mock.patch.object(
                    subject, "_prove_with_witness", return_value=(cand, witness)
                ),
                mock.patch.object(
                    pending, "_current_pending_pr", return_value=current
                ),
                mock.patch.object(subject, "_revalidate_witness"),
                mock.patch.object(pending, "_write_state"),
            )

        contexts = common_context()
        with (
            contexts[0], contexts[1], contexts[2], contexts[3], contexts[4],
            contexts[5], contexts[6], contexts[7], contexts[8],
            mock.patch.object(
                core, "rerun_workflow", side_effect=RuntimeError("post lost")
            ),
        ):
            with self.assertRaisesRegex(
                pending.PendingMutationUncertain, "POST outcome is ambiguous"
            ):
                subject._two_stage_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                )

        contexts = common_context()
        with (
            contexts[0], contexts[1], contexts[2], contexts[3], contexts[4],
            contexts[5], contexts[6], contexts[7], contexts[8],
            mock.patch.object(core, "rerun_workflow"),
            mock.patch.object(
                pending.previous,
                "_wait_for_terminal_invalidation",
                side_effect=subject.base.DeferredObservation("later"),
            ),
        ):
            with self.assertRaises(pending.PendingMutationObservation):
                subject._two_stage_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                )

        contexts = common_context()
        with (
            contexts[0], contexts[1], contexts[2], contexts[3], contexts[4],
            contexts[5], contexts[6], contexts[7], contexts[8],
            mock.patch.object(core, "rerun_workflow"),
            mock.patch.object(
                pending.previous,
                "_wait_for_terminal_invalidation",
                return_value=False,
            ),
        ):
            result = subject._two_stage_process(
                "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
            )
        self.assertEqual(result[0], [116])
        self.assertEqual(result[2][0], 1)

        contexts = common_context()
        with (
            contexts[0],
            mock.patch.object(
                core,
                "unresolved_review_threads",
                side_effect=[True, True, True, True, False],
            ),
            contexts[2], contexts[3], contexts[4], contexts[5], contexts[6],
            contexts[7], contexts[8],
            mock.patch.object(core, "rerun_workflow"),
            mock.patch.object(
                pending.previous,
                "_wait_for_terminal_invalidation",
                return_value=False,
            ),
        ):
            result = subject._two_stage_process(
                "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
            )
        self.assertEqual(result, ([116], [], None))

    def test_safe_wrapper_existing_pending_and_prewrite_error_edges(self) -> None:
        current = pr(1, branch="shared", head=HEAD)
        state = pending._pending_state(
            pending.SchedulerStateV4(0), current, 116, 1, 616
        )
        existing = pending.PendingMutationUncertain("already uncertain")

        with (
            mock.patch.object(
                subject,
                "_two_stage_process",
                side_effect=lambda *_a, **_k: pending._write_state(
                    "o/r", "t", state
                ),
            ),
            mock.patch.object(pending, "_write_state", side_effect=existing),
        ):
            with self.assertRaises(pending.PendingMutationUncertain) as raised:
                subject._safe_two_stage_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                )
        self.assertIs(raised.exception, existing)

        ordinary = RuntimeError("before pending")
        with mock.patch.object(subject, "_two_stage_process", side_effect=ordinary):
            with self.assertRaises(RuntimeError) as raised:
                subject._safe_two_stage_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                )
        self.assertIs(raised.exception, ordinary)

    def test_install_main_and_entrypoint(self) -> None:
        with (
            mock.patch.object(previous, "install") as install,
            mock.patch.object(terminal, "_ORIGINAL_CHRONOLOGY_PROVE", create=True),
        ):
            subject.install()
        install.assert_called_once()
        self.assertIs(
            pending._process_head_group,
            subject._safe_two_stage_process,
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
            mock.patch.dict(
                os.environ, {"BOOTSTRAP_RECOVERY_ACTION": "bad"}, clear=True
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "unsupported bootstrap recovery action"
            ):
                subject.main()

        with (
            mock.patch.object(subject, "install"),
            mock.patch.dict(
                os.environ,
                {"BOOTSTRAP_RECOVERY_ACTION": subject.RECOVERY_ACTION},
                clear=True,
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "GITHUB_REPOSITORY and GITHUB_TOKEN"
            ):
                subject.main()

        env = {
            "BOOTSTRAP_RECOVERY_ACTION": subject.RECOVERY_ACTION,
            "GITHUB_REPOSITORY": "o/r",
            "GITHUB_TOKEN": "t",
        }
        with (
            mock.patch.object(subject, "install"),
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch.object(
                recovery,
                "_inspect_confirmed_unposted",
                return_value=0,
            ) as inspect,
        ):
            self.assertEqual(subject.main(), 0)
        inspect.assert_called_once_with("o/r", "t")

        with (
            mock.patch.object(previous, "install"),
            mock.patch.object(base, "main", return_value=0),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            with self.assertRaises(SystemExit) as raised:
                runpy.run_path(subject.__file__, run_name="__main__")
        self.assertEqual(raised.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
