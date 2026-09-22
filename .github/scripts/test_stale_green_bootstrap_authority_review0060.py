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
import stale_green_bootstrap_authority_review0059 as previous
import stale_green_bootstrap_authority_review0060 as subject


HEAD = "a" * 40
FRONTIER = datetime(2026, 9, 22, 21, 30, 0, tzinfo=timezone.utc)


def candidate_check(*, check_id: int = 501, run_id: int = 101, started_at: str = "2026-09-22T21:01:00Z", conclusion: str = "success"):
    item = check(check_id, run_id, head=HEAD, conclusion=conclusion)
    item["started_at"] = started_at
    return item


def run_row(
    run_id: int,
    run_number: int,
    *,
    attempt: int = 1,
    created_at: str,
    run_started_at: str,
    updated_at: str,
):
    item = gate_run(
        run_id,
        2,
        head=HEAD,
        branch="feature",
        run_number=run_number,
        created_at=created_at,
        updated_at=updated_at,
    )
    item["run_attempt"] = attempt
    item["run_started_at"] = run_started_at
    return item


def gate_job(
    job_id: int,
    run_id: int,
    *,
    attempt: int = 1,
    started_at: str,
    status: str = "completed",
    conclusion: str | None = "success",
):
    item = job(job_id, run_id, head=HEAD, attempt=attempt, conclusion=conclusion or "success")
    item["status"] = status
    item["conclusion"] = conclusion
    item["started_at"] = started_at
    item["completed_at"] = "2026-09-22T21:10:00Z" if status == "completed" else None
    return item


class Review0060AttemptAuthorityTests(unittest.TestCase):
    def tearDown(self) -> None:
        core.latest_required_check = subject._ORIGINAL_LATEST_REQUIRED_CHECK

    def test_older_run_rerun_attempt_can_be_newest_effective_authority(self) -> None:
        candidate = candidate_check()
        run_a = run_row(
            101, 10, attempt=2,
            created_at="2026-09-22T20:00:00Z",
            run_started_at="2026-09-22T21:00:00Z",
            updated_at="2026-09-22T21:10:00Z",
        )
        run_b = run_row(
            102, 11,
            created_at="2026-09-22T20:10:00Z",
            run_started_at="2026-09-22T20:10:00Z",
            updated_at="2026-09-22T20:20:00Z",
        )
        job_a = gate_job(501, 101, attempt=2, started_at="2026-09-22T21:01:00Z")
        job_b = gate_job(502, 102, started_at="2026-09-22T20:11:00Z")

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
                return [job_b]
            raise AssertionError(url)

        with (
            mock.patch.object(core, "request_data", side_effect=request),
            mock.patch.object(core, "paged", side_effect=paged),
            mock.patch.object(subject, "_attempt_frontier_runs", return_value=[run_a, run_b]),
        ):
            subject._prove_candidate_attempt_frontier("o/r", HEAD, "t", candidate, FRONTIER)

    def test_newer_protected_job_before_frontier_rejects_candidate(self) -> None:
        candidate = candidate_check()
        run_a = run_row(101, 10, attempt=2, created_at="2026-09-22T20:00:00Z", run_started_at="2026-09-22T21:00:00Z", updated_at="2026-09-22T21:10:00Z")
        run_b = run_row(102, 11, created_at="2026-09-22T20:10:00Z", run_started_at="2026-09-22T21:02:00Z", updated_at="2026-09-22T21:12:00Z")
        job_a = gate_job(501, 101, attempt=2, started_at="2026-09-22T21:01:00Z")
        job_b = gate_job(502, 102, started_at="2026-09-22T21:03:00Z")

        def request(url: str, _token: str):
            return run_a if url.endswith("/actions/runs/101") else job_a

        def paged(url: str, *_args, **_kwargs):
            return [job_a] if "/101/jobs" in url else [job_b]

        with (
            mock.patch.object(core, "request_data", side_effect=request),
            mock.patch.object(core, "paged", side_effect=paged),
            mock.patch.object(subject, "_attempt_frontier_runs", return_value=[run_a, run_b]),
        ):
            with self.assertRaisesRegex(RuntimeError, "authority advanced"):
                subject._prove_candidate_attempt_frontier("o/r", HEAD, "t", candidate, FRONTIER)

    def test_candidate_check_must_match_job_start_and_conclusion(self) -> None:
        run_a = run_row(101, 10, attempt=2, created_at="2026-09-22T20:00:00Z", run_started_at="2026-09-22T21:00:00Z", updated_at="2026-09-22T21:10:00Z")
        job_a = gate_job(501, 101, attempt=2, started_at="2026-09-22T21:01:00Z")
        for candidate, message in (
            (candidate_check(started_at="2026-09-22T21:01:01Z"), "start identity"),
            (candidate_check(conclusion="neutral"), "conclusion"),
        ):
            with (
                self.subTest(message=message),
                mock.patch.object(core, "request_data", side_effect=[run_a, job_a]),
            ):
                with self.assertRaisesRegex(RuntimeError, message):
                    subject._prove_candidate_attempt_frontier("o/r", HEAD, "t", candidate, FRONTIER)

    def test_current_attempt_or_job_after_frontier_fails_closed(self) -> None:
        candidate = candidate_check()
        run_after = run_row(101, 10, attempt=2, created_at="2026-09-22T20:00:00Z", run_started_at="2026-09-22T21:31:00Z", updated_at="2026-09-22T21:40:00Z")
        with mock.patch.object(core, "request_data", return_value=run_after):
            with self.assertRaisesRegex(RuntimeError, "attempt started after"):
                subject._prove_candidate_attempt_frontier("o/r", HEAD, "t", candidate, FRONTIER)

        run_a = run_row(101, 10, attempt=2, created_at="2026-09-22T20:00:00Z", run_started_at="2026-09-22T21:00:00Z", updated_at="2026-09-22T21:40:00Z")
        job_after = gate_job(501, 101, attempt=2, started_at="2026-09-22T21:31:00Z")
        candidate_after = candidate_check(started_at="2026-09-22T21:31:00Z")
        with mock.patch.object(core, "request_data", side_effect=[run_a, job_after]):
            with self.assertRaisesRegex(RuntimeError, "frontier precedes candidate check"):
                subject._prove_candidate_attempt_frontier("o/r", HEAD, "t", candidate_after, FRONTIER)

    def test_run_attempt_lifetime_and_job_shape_fail_closed(self) -> None:
        bad_run = run_row(101, 10, created_at="2026-09-22T20:00:00Z", run_started_at="2026-09-22T19:59:00Z", updated_at="2026-09-22T21:00:00Z")
        with self.assertRaisesRegex(RuntimeError, "invalid attempt lifetime"):
            subject._run_attempt_started_at(bad_run)

        good_run = run_row(101, 10, created_at="2026-09-22T20:00:00Z", run_started_at="2026-09-22T20:01:00Z", updated_at="2026-09-22T21:00:00Z")
        for rows, message in (
            ([], "exposes 0"),
            ([gate_job(501, 101, started_at="2026-09-22T20:02:00Z"), gate_job(502, 101, started_at="2026-09-22T20:03:00Z")], "exposes 2"),
        ):
            with self.subTest(message=message), mock.patch.object(core, "paged", return_value=rows):
                with self.assertRaisesRegex(RuntimeError, message):
                    subject._protected_gate_job("o/r", "t", good_run, HEAD)

    def test_frontier_row_candidate_must_remain_identical(self) -> None:
        candidate = candidate_check()
        direct = run_row(101, 10, attempt=2, created_at="2026-09-22T20:00:00Z", run_started_at="2026-09-22T21:00:00Z", updated_at="2026-09-22T21:10:00Z")
        changed = dict(direct)
        changed["run_attempt"] = 3
        job_a = gate_job(501, 101, attempt=2, started_at="2026-09-22T21:01:00Z")
        job_changed = gate_job(501, 101, attempt=3, started_at="2026-09-22T21:01:00Z")

        def request(url: str, _token: str):
            return direct if url.endswith("/actions/runs/101") else job_a

        with (
            mock.patch.object(core, "request_data", side_effect=request),
            mock.patch.object(core, "paged", return_value=[job_changed]),
            mock.patch.object(subject, "_attempt_frontier_runs", return_value=[changed]),
        ):
            with self.assertRaisesRegex(RuntimeError, "changed during authority proof"):
                subject._prove_candidate_attempt_frontier("o/r", HEAD, "t", candidate, FRONTIER)

    def test_non_merge_candidate_skips_attempt_frontier(self) -> None:
        for candidate in (None, candidate_check(conclusion="failure")):
            with (
                self.subTest(candidate=candidate),
                mock.patch.object(subject, "_ORIGINAL_LATEST_REQUIRED_CHECK", return_value=candidate),
                mock.patch.object(subject, "_prove_candidate_attempt_frontier") as prove,
            ):
                self.assertIs(subject._attempt_latest_required_check("o/r", HEAD, "t"), candidate)
            prove.assert_not_called()

    def test_attempt_frontier_uses_epoch_to_capture_old_rerunnable_runs(self) -> None:
        with mock.patch.object(previous, "_bounded_frontier_runs", return_value=[]) as bounded:
            self.assertEqual(subject._attempt_frontier_runs("o/r", HEAD, "t", FRONTIER), [])
        self.assertEqual(bounded.call_args.args[3], subject._ACTIONS_EPOCH)
        self.assertEqual(bounded.call_args.args[4], FRONTIER)

    def test_protected_gate_job_fail_closed_shapes(self) -> None:
        good_run = run_row(
            101, 10,
            created_at="2026-09-22T20:00:00Z",
            run_started_at="2026-09-22T20:01:00Z",
            updated_at="2026-09-22T20:10:00Z",
        )
        bad_id_run = dict(good_run)
        bad_id_run["id"] = True
        with self.assertRaisesRegex(RuntimeError, "malformed canonical MONDE Gate run id"):
            subject._protected_gate_job("o/r", "t", bad_id_run, HEAD)

        nongate = gate_job(700, 101, started_at="2026-09-22T20:02:00Z")
        nongate["name"] = "CodeQL"
        with mock.patch.object(core, "paged", return_value=[nongate]):
            with self.assertRaisesRegex(RuntimeError, "exposes 0"):
                subject._protected_gate_job("o/r", "t", good_run, HEAD)

        malformed = gate_job(501, 101, started_at="2026-09-22T20:02:00Z")
        malformed["run_attempt"] = 2
        with mock.patch.object(core, "paged", return_value=[malformed]):
            with self.assertRaisesRegex(RuntimeError, "malformed current protected"):
                subject._protected_gate_job("o/r", "t", good_run, HEAD)

        bad_completed = gate_job(501, 101, started_at="2026-09-22T20:02:00Z")
        bad_completed["conclusion"] = "mystery"
        with mock.patch.object(core, "paged", return_value=[bad_completed]):
            with self.assertRaisesRegex(RuntimeError, "malformed completed"):
                subject._protected_gate_job("o/r", "t", good_run, HEAD)

        active = gate_job(
            501, 101,
            started_at="2026-09-22T20:02:00Z",
            status="in_progress",
            conclusion=None,
        )
        active["conclusion"] = "success"
        with mock.patch.object(core, "paged", return_value=[active]):
            with self.assertRaisesRegex(RuntimeError, "incomplete current"):
                subject._protected_gate_job("o/r", "t", good_run, HEAD)

        reversed_lifetime = gate_job(501, 101, started_at="2026-09-22T20:09:00Z")
        reversed_lifetime["completed_at"] = "2026-09-22T20:08:00Z"
        with mock.patch.object(core, "paged", return_value=[reversed_lifetime]):
            with self.assertRaisesRegex(RuntimeError, "invalid lifetime"):
                subject._protected_gate_job("o/r", "t", good_run, HEAD)

        active_completed_at = gate_job(
            501, 101,
            started_at="2026-09-22T20:02:00Z",
            status="in_progress",
            conclusion=None,
        )
        active_completed_at["completed_at"] = "2026-09-22T20:03:00Z"
        with mock.patch.object(core, "paged", return_value=[active_completed_at]):
            with self.assertRaisesRegex(RuntimeError, "with completed_at"):
                subject._protected_gate_job("o/r", "t", good_run, HEAD)

    def test_attempt_authority_key_and_direct_payload_guards(self) -> None:
        bad_job = gate_job(501, 101, started_at="2026-09-22T20:02:00Z")
        bad_job["id"] = True
        with self.assertRaisesRegex(RuntimeError, "protected MONDE Gate job id"):
            subject._attempt_authority_key(bad_job)

        candidate = candidate_check()
        with mock.patch.object(core, "request_data", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "malformed candidate canonical"):
                subject._prove_candidate_attempt_frontier("o/r", HEAD, "t", candidate, FRONTIER)

        run_a = run_row(
            101, 10, attempt=2,
            created_at="2026-09-22T20:00:00Z",
            run_started_at="2026-09-22T21:00:00Z",
            updated_at="2026-09-22T21:10:00Z",
        )
        with mock.patch.object(core, "request_data", side_effect=[run_a, []]):
            with self.assertRaisesRegex(RuntimeError, "malformed candidate protected"):
                subject._prove_candidate_attempt_frontier("o/r", HEAD, "t", candidate, FRONTIER)

    def test_frontier_collection_guards(self) -> None:
        candidate = candidate_check()
        run_a = run_row(
            101, 10, attempt=2,
            created_at="2026-09-22T20:00:00Z",
            run_started_at="2026-09-22T21:00:00Z",
            updated_at="2026-09-22T21:10:00Z",
        )
        job_a = gate_job(501, 101, attempt=2, started_at="2026-09-22T21:01:00Z")

        def direct_request(url: str, _token: str):
            return run_a if url.endswith("/actions/runs/101") else job_a

        with (
            mock.patch.object(core, "request_data", side_effect=direct_request),
            mock.patch.object(subject, "_attempt_frontier_runs", return_value=[]),
        ):
            with self.assertRaisesRegex(RuntimeError, "absent from attempt frontier"):
                subject._prove_candidate_attempt_frontier("o/r", HEAD, "t", candidate, FRONTIER)

        malformed_row = dict(run_a)
        malformed_row["id"] = True
        with (
            mock.patch.object(core, "request_data", side_effect=direct_request),
            mock.patch.object(subject, "_attempt_frontier_runs", return_value=[malformed_row]),
        ):
            with self.assertRaisesRegex(RuntimeError, "frontier run id"):
                subject._prove_candidate_attempt_frontier("o/r", HEAD, "t", candidate, FRONTIER)

        post_frontier = dict(run_a)
        post_frontier["run_started_at"] = "2026-09-22T21:31:00Z"
        post_frontier["updated_at"] = "2026-09-22T21:40:00Z"
        with (
            mock.patch.object(core, "request_data", side_effect=direct_request),
            mock.patch.object(subject, "_attempt_frontier_runs", return_value=[post_frontier]),
        ):
            with self.assertRaisesRegex(RuntimeError, "current attempt started after"):
                subject._prove_candidate_attempt_frontier("o/r", HEAD, "t", candidate, FRONTIER)

        other = run_row(
            102, 11,
            created_at="2026-09-22T20:10:00Z",
            run_started_at="2026-09-22T20:10:00Z",
            updated_at="2026-09-22T21:40:00Z",
        )
        other_job = gate_job(502, 102, started_at="2026-09-22T21:31:00Z")
        other_job["completed_at"] = "2026-09-22T21:40:00Z"
        def paged(url: str, *_args, **_kwargs):
            return [other_job] if "/102/jobs" in url else [job_a]
        with (
            mock.patch.object(core, "request_data", side_effect=direct_request),
            mock.patch.object(core, "paged", side_effect=paged),
            mock.patch.object(subject, "_attempt_frontier_runs", return_value=[run_a, other]),
        ):
            with self.assertRaisesRegex(RuntimeError, "protected job started after"):
                subject._prove_candidate_attempt_frontier("o/r", HEAD, "t", candidate, FRONTIER)

        unrelated = run_row(
            102, 11,
            created_at="2026-09-22T20:10:00Z",
            run_started_at="2026-09-22T20:10:00Z",
            updated_at="2026-09-22T20:20:00Z",
        )
        unrelated_job = gate_job(502, 102, started_at="2026-09-22T20:11:00Z")
        def only_other(url: str, *_args, **_kwargs):
            return [unrelated_job]
        with (
            mock.patch.object(core, "request_data", side_effect=direct_request),
            mock.patch.object(core, "paged", side_effect=only_other),
            mock.patch.object(subject, "_attempt_frontier_runs", return_value=[unrelated]),
        ):
            with self.assertRaisesRegex(RuntimeError, "absent or ambiguous"):
                subject._prove_candidate_attempt_frontier("o/r", HEAD, "t", candidate, FRONTIER)

    def test_main_recovery_guards(self) -> None:
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

    def test_install_and_main_guards(self) -> None:
        with mock.patch.object(previous, "install") as install:
            subject.install()
        install.assert_called_once()
        self.assertIs(core.latest_required_check, subject._attempt_latest_required_check)

        with (
            mock.patch.object(subject, "install"),
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(base, "main", return_value=17) as base_main,
        ):
            self.assertEqual(subject.main(), 17)
        base_main.assert_called_once()

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
