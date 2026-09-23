from __future__ import annotations

import os
import runpy
import unittest
from unittest import mock

from test_stale_green_bootstrap_authority import check, job, pr
from test_stale_green_bootstrap_authority_review0068 import (
    HEAD,
    candidate_check as old_candidate_check,
    candidate_job as old_candidate_job,
    candidate_run as old_candidate_run,
    run_row,
)
import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0049 as pending
import stale_green_bootstrap_authority_review0051_recovery as recovery
import stale_green_bootstrap_authority_review0060 as attempt
import stale_green_bootstrap_authority_review0068 as previous
import stale_green_bootstrap_authority_review0069 as subject


def bulk_run(
    run_id: int,
    *,
    suite_id: int | None = None,
    created: str = "2026-09-23T10:00:00Z",
    started: str = "2026-09-23T10:00:30Z",
    updated: str = "2026-09-23T10:10:00Z",
) -> dict:
    item = run_row(
        run_id,
        created=created,
        started=started,
        updated=updated,
        run_number=run_id,
    )
    item["check_suite_id"] = suite_id or (900000 + run_id)
    return item


def bulk_check(
    check_id: int,
    run_id: int,
    *,
    suite_id: int | None = None,
    started: str = "2026-09-23T10:01:00Z",
    completed: str | None = "2026-09-23T10:02:00Z",
    status: str = "completed",
    conclusion: str | None = "success",
) -> dict:
    item = check(
        check_id,
        run_id,
        head=HEAD,
        status=status,
        conclusion=conclusion,
        completed_at=completed or "2026-09-23T10:02:00Z",
    )
    item["started_at"] = started
    item["completed_at"] = completed
    item["check_suite"] = {"id": suite_id or (900000 + run_id)}
    return item


def candidate_run() -> dict:
    return bulk_run(135, suite_id=900135)


def candidate_check() -> dict:
    return bulk_check(
        635,
        135,
        suite_id=900135,
        started="2026-09-23T10:02:00Z",
        completed="2026-09-23T10:05:00Z",
    )


def candidate_job() -> dict:
    item = job(635, 135, head=HEAD)
    item["started_at"] = "2026-09-23T10:02:00Z"
    item["completed_at"] = "2026-09-23T10:05:00Z"
    return item


class Review0069BulkAuthorityTests(unittest.TestCase):
    def setUp(self) -> None:
        subject.base._reset_request_budget()
        self._core_request = subject.core.request_data
        self._network = subject.base._ORIGINAL_REQUEST_DATA
        self._prove = previous._prove_with_witness
        self._revalidate = previous._revalidate_witness
        self._process = pending._process_head_group

    def tearDown(self) -> None:
        subject.core.request_data = self._core_request
        subject.base._ORIGINAL_REQUEST_DATA = self._network
        previous._prove_with_witness = self._prove
        previous._revalidate_witness = self._revalidate
        pending._process_head_group = self._process
        subject.base._reset_request_budget()

    def test_suite_identity_and_bulk_snapshots(self) -> None:
        run = candidate_run()
        chk = candidate_check()
        self.assertEqual(subject._suite_id_from_run(run), 900135)
        self.assertEqual(subject._suite_id_from_check(chk), 900135)
        self.assertEqual(subject._bulk_check_snapshot(chk, HEAD)[:4], (635, 900135, 135, 635))
        self.assertEqual(subject._bulk_run_snapshot(run, HEAD)[-1], 900135)

        for bad in ({}, {"check_suite": {"id": True}}):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(RuntimeError, "check-suite identity"):
                    subject._suite_id_from_check(bad)
        for bad in ({}, {"check_suite_id": False}):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(RuntimeError, "check-suite identity"):
                    subject._suite_id_from_run(bad)

    def test_bulk_check_status_contract(self) -> None:
        for bad, message in (
            ({**candidate_check(), "status": "mystery"}, "malformed bulk.*status"),
            ({**candidate_check(), "conclusion": None}, "malformed completed"),
            (
                bulk_check(
                    635,
                    135,
                    suite_id=900135,
                    status="in_progress",
                    conclusion="success",
                    completed=None,
                ),
                "incomplete bulk.*conclusion",
            ),
        ):
            with self.subTest(message=message):
                with self.assertRaisesRegex(RuntimeError, message):
                    subject._bulk_check_snapshot(bad, HEAD)

        active = bulk_check(
            635,
            135,
            suite_id=900135,
            status="in_progress",
            conclusion=None,
            completed=None,
        )
        snap = subject._bulk_check_snapshot(active, HEAD)
        self.assertEqual(snap[4:8], ("in_progress", None, "2026-09-23T10:01:00+00:00", None))

    def test_bulk_required_checks_and_candidate_selection(self) -> None:
        c1 = bulk_check(601, 101, suite_id=900101, started="2026-09-23T10:01:00Z")
        c2 = candidate_check()
        with mock.patch.object(core, "paged", return_value=[c2, c1]) as paged:
            checks, snapshot = subject._bulk_required_checks("o/r", HEAD, "t")
        self.assertEqual([x["id"] for x in checks], [635, 601])
        self.assertEqual([x[0] for x in snapshot], [601, 635])
        self.assertTrue(paged.call_args.kwargs["verify_previous_page"])
        self.assertIs(subject._candidate_from_checks(checks, HEAD), c2)
        self.assertIsNone(subject._candidate_from_checks([], HEAD))

        dup = bulk_check(602, 102, suite_id=900101)
        with mock.patch.object(core, "paged", return_value=[c1, dup]):
            with self.assertRaisesRegex(RuntimeError, "multiple latest"):
                subject._bulk_required_checks("o/r", HEAD, "t")

    def test_bulk_frontier_identity_contract(self) -> None:
        r1 = bulk_run(101, suite_id=900101)
        r2 = bulk_run(102, suite_id=900102)
        with mock.patch.object(attempt, "_attempt_frontier_runs", return_value=[r2, r1]):
            rows, snapshot = subject._bulk_frontier_runs(
                "o/r",
                HEAD,
                "t",
                core._timestamp("2026-09-23T10:20:00Z", "frontier"),
            )
        self.assertEqual([row["id"] for row in rows], [102, 101])
        self.assertEqual([row[0] for row in snapshot], [101, 102])

        with mock.patch.object(attempt, "_attempt_frontier_runs", return_value=[r1, dict(r1)]):
            with self.assertRaisesRegex(RuntimeError, "duplicate run identity"):
                subject._bulk_frontier_runs(
                    "o/r", HEAD, "t", core._timestamp("2026-09-23T10:20:00Z", "frontier")
                )
        rdup = bulk_run(102, suite_id=900101)
        with mock.patch.object(attempt, "_attempt_frontier_runs", return_value=[r1, rdup]):
            with self.assertRaisesRegex(RuntimeError, "duplicate check-suite"):
                subject._bulk_frontier_runs(
                    "o/r", HEAD, "t", core._timestamp("2026-09-23T10:20:00Z", "frontier")
                )

    def test_run_check_binding_and_suite_lookup(self) -> None:
        run = candidate_run()
        chk = candidate_check()
        self.assertEqual(subject._check_for_suite({900135: chk}, 900135), chk)
        with self.assertRaisesRegex(RuntimeError, "lacks one latest"):
            subject._check_for_suite({}, 900135)
        self.assertEqual(subject._validate_bulk_run_check_binding(run, chk, HEAD)[0], 635)

        wrong_suite = bulk_check(635, 135, suite_id=999999, started="2026-09-23T10:02:00Z", completed="2026-09-23T10:05:00Z")
        with self.assertRaisesRegex(RuntimeError, "run/check-suite identity"):
            subject._validate_bulk_run_check_binding(run, wrong_suite, HEAD)

        early = bulk_check(635, 135, suite_id=900135, started="2026-09-23T09:59:00Z", completed="2026-09-23T10:05:00Z")
        with self.assertRaisesRegex(RuntimeError, "start falls outside"):
            subject._validate_bulk_run_check_binding(run, early, HEAD)

        late = bulk_check(635, 135, suite_id=900135, started="2026-09-23T10:02:00Z", completed="2026-09-23T10:11:00Z")
        with self.assertRaisesRegex(RuntimeError, "completion exceeds"):
            subject._validate_bulk_run_check_binding(run, late, HEAD)

    def test_direct_candidate_job_binding(self) -> None:
        run = candidate_run()
        chk = candidate_check()
        jb = candidate_job()
        with mock.patch.object(core, "request_data", side_effect=[run, jb]):
            snap = subject._direct_candidate_job_snapshot("o/r", HEAD, "t", chk, run)
        self.assertEqual(snap[:2], (635, 135))

        changed = dict(run)
        changed["updated_at"] = "2026-09-23T10:09:00Z"
        with mock.patch.object(core, "request_data", return_value=changed):
            with self.assertRaisesRegex(RuntimeError, "run changed"):
                subject._direct_candidate_job_snapshot("o/r", HEAD, "t", chk, run)

        with mock.patch.object(core, "request_data", side_effect=[run, []]):
            with self.assertRaisesRegex(RuntimeError, "malformed direct candidate protected"):
                subject._direct_candidate_job_snapshot("o/r", HEAD, "t", chk, run)

        mismatch = dict(jb)
        mismatch["started_at"] = "2026-09-23T10:03:00Z"
        with mock.patch.object(core, "request_data", side_effect=[run, mismatch]):
            with self.assertRaisesRegex(RuntimeError, "start timing"):
                subject._direct_candidate_job_snapshot("o/r", HEAD, "t", chk, run)

        mismatch = dict(jb)
        mismatch["completed_at"] = "2026-09-23T10:06:00Z"
        with mock.patch.object(core, "request_data", side_effect=[run, mismatch]):
            with self.assertRaisesRegex(RuntimeError, "completion timing"):
                subject._direct_candidate_job_snapshot("o/r", HEAD, "t", chk, run)

        mismatch = dict(jb)
        mismatch["conclusion"] = "failure"
        with mock.patch.object(core, "request_data", side_effect=[run, mismatch]):
            with self.assertRaisesRegex(RuntimeError, "job conclusion"):
                subject._direct_candidate_job_snapshot("o/r", HEAD, "t", chk, run)

    def test_prove_bulk_witness_happy_path_and_nonmerge(self) -> None:
        run = candidate_run()
        chk = candidate_check()
        jb = candidate_job()
        with (
            mock.patch.object(subject, "_bulk_required_checks", return_value=([chk], (subject._bulk_check_snapshot(chk, HEAD),))),
            mock.patch.object(
                subject,
                "_bulk_frontier_runs",
                return_value=([run], (subject._bulk_run_snapshot(run, HEAD),)),
            ),
            mock.patch.object(
                attempt.previous,
                "_authority_frontier",
                return_value=core._timestamp("2026-09-23T10:20:00Z", "frontier"),
            ),
            mock.patch.object(subject, "_direct_candidate_job_snapshot", return_value=previous._job_snapshot(jb, run, HEAD)),
        ):
            candidate, witness = subject._prove_bulk_witness("o/r", HEAD, "t")
        self.assertIs(candidate, chk)
        self.assertIsNotNone(witness)
        assert witness is not None
        self.assertEqual(witness.candidate_check[0], 635)

        failed = {**chk, "conclusion": "failure"}
        with mock.patch.object(
            subject,
            "_bulk_required_checks",
            return_value=([failed], (subject._bulk_check_snapshot(failed, HEAD),)),
        ):
            candidate, witness = subject._prove_bulk_witness("o/r", HEAD, "t")
        self.assertEqual(candidate["conclusion"], "failure")
        self.assertIsNone(witness)

    def test_prove_bulk_witness_fail_closed_frontier_cases(self) -> None:
        run = candidate_run()
        chk = candidate_check()
        snapshot = (subject._bulk_check_snapshot(chk, HEAD),)
        frontier = core._timestamp("2026-09-23T10:20:00Z", "frontier")

        with (
            mock.patch.object(subject, "_bulk_required_checks", return_value=([chk], snapshot)),
            mock.patch.object(subject, "_bulk_frontier_runs", return_value=([], ())),
            mock.patch.object(attempt.previous, "_authority_frontier", return_value=frontier),
        ):
            with self.assertRaisesRegex(RuntimeError, "absent from bulk Actions frontier"):
                subject._prove_bulk_witness("o/r", HEAD, "t")

        with (
            mock.patch.object(subject, "_bulk_required_checks", return_value=([chk], snapshot)),
            mock.patch.object(
                subject,
                "_bulk_frontier_runs",
                return_value=([run], (subject._bulk_run_snapshot(run, HEAD),)),
            ),
            mock.patch.object(
                attempt.previous,
                "_authority_frontier",
                return_value=core._timestamp("2026-09-23T10:04:00Z", "frontier"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "frontier precedes candidate check completion"):
                subject._prove_bulk_witness("o/r", HEAD, "t")

        other = bulk_run(101, suite_id=900101)
        with (
            mock.patch.object(subject, "_bulk_required_checks", return_value=([chk], snapshot)),
            mock.patch.object(
                subject,
                "_bulk_frontier_runs",
                return_value=([other], (subject._bulk_run_snapshot(other, HEAD),)),
            ),
            mock.patch.object(attempt.previous, "_authority_frontier", return_value=frontier),
        ):
            with self.assertRaisesRegex(RuntimeError, "not bound to the canonical Actions frontier"):
                subject._prove_bulk_witness("o/r", HEAD, "t")

        wrong_suite_run = candidate_run()
        wrong_suite_run["check_suite_id"] = 999999
        with (
            mock.patch.object(subject, "_bulk_required_checks", return_value=([chk], snapshot)),
            mock.patch.object(
                subject,
                "_bulk_frontier_runs",
                return_value=([wrong_suite_run], (subject._bulk_run_snapshot(wrong_suite_run, HEAD),)),
            ),
            mock.patch.object(attempt.previous, "_authority_frontier", return_value=frontier),
        ):
            with self.assertRaisesRegex(RuntimeError, "disagrees with canonical Actions check suite"):
                subject._prove_bulk_witness("o/r", HEAD, "t")

    def test_prove_bulk_witness_competitor_edges(self) -> None:
        cand_run = candidate_run()
        cand = candidate_check()
        old_run = bulk_run(101, suite_id=900101, updated="2026-09-23T10:01:30Z")
        new_attempt = bulk_run(102, suite_id=900102, started="2026-09-23T10:03:00Z")
        frontier = core._timestamp("2026-09-23T10:20:00Z", "frontier")
        cand_snap = subject._bulk_check_snapshot(cand, HEAD)

        with (
            mock.patch.object(subject, "_bulk_required_checks", return_value=([cand], (cand_snap,))),
            mock.patch.object(
                subject,
                "_bulk_frontier_runs",
                return_value=(
                    [old_run, cand_run],
                    tuple(sorted([subject._bulk_run_snapshot(old_run, HEAD), subject._bulk_run_snapshot(cand_run, HEAD)], key=lambda x:x[0])),
                ),
            ),
            mock.patch.object(attempt.previous, "_authority_frontier", return_value=frontier),
            mock.patch.object(subject, "_direct_candidate_job_snapshot", return_value=("ok",)),
        ):
            _, witness = subject._prove_bulk_witness("o/r", HEAD, "t")
        self.assertIsNotNone(witness)

        with (
            mock.patch.object(subject, "_bulk_required_checks", return_value=([cand], (cand_snap,))),
            mock.patch.object(
                subject,
                "_bulk_frontier_runs",
                return_value=(
                    [cand_run, new_attempt],
                    tuple(sorted([subject._bulk_run_snapshot(cand_run, HEAD), subject._bulk_run_snapshot(new_attempt, HEAD)], key=lambda x:x[0])),
                ),
            ),
            mock.patch.object(attempt.previous, "_authority_frontier", return_value=frontier),
        ):
            with self.assertRaisesRegex(RuntimeError, "newer canonical.*attempt"):
                subject._prove_bulk_witness("o/r", HEAD, "t")

        competitor = bulk_run(101, suite_id=900101)
        newer_check = bulk_check(601, 101, suite_id=900101, started="2026-09-23T10:03:00Z", completed="2026-09-23T10:04:00Z")
        checks = [cand, newer_check]
        snaps = tuple(sorted([subject._bulk_check_snapshot(x, HEAD) for x in checks], key=lambda x:(x[6],x[0])))
        rows = [competitor, cand_run]
        run_snaps = tuple(sorted([subject._bulk_run_snapshot(x, HEAD) for x in rows], key=lambda x:x[0]))
        with (
            mock.patch.object(subject, "_bulk_required_checks", return_value=(checks, snaps)),
            mock.patch.object(subject, "_bulk_frontier_runs", return_value=(rows, run_snaps)),
            mock.patch.object(attempt.previous, "_authority_frontier", return_value=frontier),
        ):
            with self.assertRaisesRegex(RuntimeError, "newer protected.*check"):
                subject._prove_bulk_witness("o/r", HEAD, "t")

    def test_revalidate_bulk_witness_detects_every_snapshot_drift(self) -> None:
        run = candidate_run()
        chk = candidate_check()
        jb = candidate_job()
        witness = subject.BulkAuthorityWitness(
            candidate_check=subject._bulk_check_snapshot(chk, HEAD),
            frontier_runs=(subject._bulk_run_snapshot(run, HEAD),),
            gate_checks=(subject._bulk_check_snapshot(chk, HEAD),),
            candidate_job=previous._job_snapshot(jb, run, HEAD),
        )
        frontier = core._timestamp("2026-09-23T10:20:00Z", "frontier")
        with (
            mock.patch.object(subject, "_bulk_required_checks", return_value=([chk], witness.gate_checks)),
            mock.patch.object(subject, "_bulk_frontier_runs", return_value=([run], witness.frontier_runs)),
            mock.patch.object(attempt.previous, "_authority_frontier", return_value=frontier),
            mock.patch.object(subject, "_direct_candidate_job_snapshot", return_value=witness.candidate_job),
        ):
            subject._revalidate_bulk_witness("o/r", HEAD, "t", witness)

        changed_check = (("changed",),)
        with mock.patch.object(subject, "_bulk_required_checks", return_value=([chk], changed_check)):
            with self.assertRaisesRegex(RuntimeError, "Check Run snapshot changed"):
                subject._revalidate_bulk_witness("o/r", HEAD, "t", witness)

        with (
            mock.patch.object(subject, "_bulk_required_checks", return_value=([chk], witness.gate_checks)),
            mock.patch.object(subject, "_bulk_frontier_runs", return_value=([run], (("changed",),))),
            mock.patch.object(attempt.previous, "_authority_frontier", return_value=frontier),
        ):
            with self.assertRaisesRegex(RuntimeError, "Actions frontier changed"):
                subject._revalidate_bulk_witness("o/r", HEAD, "t", witness)

        with (
            mock.patch.object(subject, "_bulk_required_checks", return_value=([], witness.gate_checks)),
            mock.patch.object(subject, "_bulk_frontier_runs", return_value=([run], witness.frontier_runs)),
            mock.patch.object(attempt.previous, "_authority_frontier", return_value=frontier),
        ):
            with self.assertRaisesRegex(RuntimeError, "disappeared or became ambiguous"):
                subject._revalidate_bulk_witness("o/r", HEAD, "t", witness)

        with (
            mock.patch.object(subject, "_bulk_required_checks", return_value=([chk], witness.gate_checks)),
            mock.patch.object(subject, "_bulk_frontier_runs", return_value=([], witness.frontier_runs)),
            mock.patch.object(attempt.previous, "_authority_frontier", return_value=frontier),
        ):
            with self.assertRaisesRegex(RuntimeError, "run disappeared"):
                subject._revalidate_bulk_witness("o/r", HEAD, "t", witness)

        with (
            mock.patch.object(subject, "_bulk_required_checks", return_value=([chk], witness.gate_checks)),
            mock.patch.object(subject, "_bulk_frontier_runs", return_value=([run], witness.frontier_runs)),
            mock.patch.object(attempt.previous, "_authority_frontier", return_value=frontier),
            mock.patch.object(subject, "_direct_candidate_job_snapshot", return_value=("changed",)),
        ):
            with self.assertRaisesRegex(RuntimeError, "job changed"):
                subject._revalidate_bulk_witness("o/r", HEAD, "t", witness)

    def test_real_budget_thirty_five_overlapping_runs_reaches_pending_write(self) -> None:
        current = pr(1, branch="shared", head=HEAD)
        rows = [bulk_run(run_id, suite_id=900000 + run_id) for run_id in range(101, 136)]
        checks = [
            bulk_check(
                500 + run_id,
                run_id,
                suite_id=900000 + run_id,
                started="2026-09-23T10:01:00Z",
                completed="2026-09-23T10:01:30Z",
            )
            for run_id in range(101, 135)
        ] + [candidate_check()]
        cand_run = rows[-1]
        cand = checks[-1]
        cand_job = candidate_job()
        target = (cand_run, cand)
        pending_budget: list[int] = []

        def network(url: str, _token: str, method: str = "GET", body=None):
            if "/commits/" in url and "/check-runs?" in url:
                return {"total_count": len(checks), "check_runs": checks}
            if "/actions/workflows/" in url and "/runs?" in url:
                return {"total_count": len(rows), "workflow_runs": rows}
            if url.endswith("/actions/runs/135"):
                return cand_run
            if url.endswith("/actions/jobs/635"):
                return cand_job
            raise AssertionError(f"unexpected bulk liveness request: {method} {url}")

        old_request = subject.core.request_data
        old_network = subject.base._ORIGINAL_REQUEST_DATA
        old_prove = previous._prove_with_witness
        old_revalidate = previous._revalidate_witness
        try:
            subject.base._reset_request_budget()
            subject.base._ORIGINAL_REQUEST_DATA = network
            subject.core.request_data = subject.base._budgeted_request_data
            previous._prove_with_witness = subject._prove_bulk_witness
            previous._revalidate_witness = subject._revalidate_bulk_witness

            def writer(_repo, _token, state):
                if state.pending_pr:
                    pending_budget.append(subject.base._request_count)

            with (
                mock.patch.object(previous.core, "unresolved_review_threads", return_value=True),
                mock.patch.object(
                    previous.pending.previous,
                    "_direct_target_for_pr",
                    return_value=(target, None),
                ),
                mock.patch.object(previous.base, "_current_pr", return_value=current),
                mock.patch.object(
                    previous.pending.previous,
                    "_mutation_baseline",
                    return_value=1,
                ),
                mock.patch.object(
                    previous.pending,
                    "_current_pending_pr",
                    return_value=current,
                ),
                mock.patch.object(previous.pending, "_write_state", side_effect=writer),
                mock.patch.object(previous.core, "rerun_workflow"),
                mock.patch.object(
                    previous.pending.previous,
                    "_wait_for_terminal_invalidation",
                    return_value=True,
                ),
            ):
                result = previous._two_stage_process(
                    "o/r", "t", [current], 3, pending.SchedulerStateV4(0)
                )

            self.assertEqual(result[0], [135])
            self.assertEqual(len(pending_budget), 1)
            self.assertLessEqual(
                pending_budget[0],
                subject.base.MAX_GITHUB_REQUESTS_PER_INVOCATION
                - pending.MUTATION_REQUEST_RESERVE,
            )
            self.assertLess(
                subject.base._request_count,
                subject.base.MAX_GITHUB_REQUESTS_PER_INVOCATION,
            )
            # G1/G2 each use one bulk checks page, one bulk Actions page,
            # and only the selected candidate's direct run/job. No competitor
            # incurs a /jobs request.
            self.assertLessEqual(pending_budget[0], 12)
        finally:
            subject.core.request_data = old_request
            subject.base._ORIGINAL_REQUEST_DATA = old_network
            previous._prove_with_witness = old_prove
            previous._revalidate_witness = old_revalidate
            subject.base._reset_request_budget()

    def test_install_main_and_entrypoint(self) -> None:
        with mock.patch.object(previous, "install") as install:
            subject.install()
        install.assert_called_once()
        self.assertIs(previous._prove_with_witness, subject._prove_bulk_witness)
        self.assertIs(previous._revalidate_witness, subject._revalidate_bulk_witness)

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
