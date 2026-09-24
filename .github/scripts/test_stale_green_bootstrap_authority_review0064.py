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
)
import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0051_recovery as recovery
import stale_green_bootstrap_authority_review0061 as chronology
import stale_green_bootstrap_authority_review0062 as terminal
import stale_green_bootstrap_authority_review0064 as subject


def valid_candidate(
    *,
    check_id: int = 501,
    run_id: int = 101,
    started_at: str = "2026-09-22T21:01:00Z",
    completed_at: str = "2026-09-22T21:10:00Z",
):
    item = candidate_check(
        check_id=check_id,
        run_id=run_id,
        started_at=started_at,
    )
    item["completed_at"] = completed_at
    return item


class Review0064CheckTemporalAuthorityTests(unittest.TestCase):
    def tearDown(self) -> None:
        core.latest_required_check = subject._ORIGINAL_ACTIVE_LATEST
        chronology._chronology_prove_candidate_attempt_frontier = (
            subject._ORIGINAL_TERMINAL_PROVE
        )

    def test_completed_check_requires_parseable_ordered_completion(self) -> None:
        good = valid_candidate()
        started, completed = subject._required_check_temporal_snapshot(good)
        self.assertLessEqual(started, completed)

        missing = valid_candidate()
        missing["completed_at"] = None
        with self.assertRaisesRegex(RuntimeError, "completed_at"):
            subject._required_check_temporal_snapshot(missing)

        malformed = valid_candidate()
        malformed["completed_at"] = "not-a-time"
        with self.assertRaisesRegex(RuntimeError, "completed_at"):
            subject._required_check_temporal_snapshot(malformed)

        inherited_bad_fixture = candidate_check()
        with self.assertRaisesRegex(RuntimeError, "completing before it started"):
            subject._required_check_temporal_snapshot(inherited_bad_fixture)

    def test_incomplete_check_rejects_completion_and_accepts_null(self) -> None:
        active = valid_candidate()
        active["status"] = "in_progress"
        active["conclusion"] = None
        with self.assertRaisesRegex(RuntimeError, "incomplete.*completed_at"):
            subject._required_check_temporal_snapshot(active)

        active["completed_at"] = None
        started, completed = subject._required_check_temporal_snapshot(active)
        self.assertIsNotNone(started)
        self.assertIsNone(completed)

    def test_latest_wrapper_rejects_hidden_malformed_candidate_and_restores_paged(self) -> None:
        good = valid_candidate()
        bad = valid_candidate(
            check_id=502,
            run_id=102,
            started_at="2026-09-22T20:00:00Z",
            completed_at="2026-09-22T19:59:59Z",
        )
        original = mock.Mock(side_effect=[[], [good, bad]])

        def active(_repo: str, _head: str, _token: str):
            core.paged("https://api.github.com/repos/o/r/actions/runs", "t")
            rows = core.paged(
                f"https://api.github.com/repos/o/r/commits/{HEAD}/check-runs?filter=latest",
                "t",
            )
            return rows[0]

        with (
            mock.patch.object(core, "paged", original),
            mock.patch.object(subject, "_ORIGINAL_ACTIVE_LATEST", side_effect=active),
        ):
            with self.assertRaisesRegex(RuntimeError, "completing before it started"):
                subject._temporal_latest_required_check("o/r", HEAD, "t")
            self.assertIs(core.paged, original)
        self.assertEqual(original.call_count, 2)

    def test_latest_wrapper_valid_collection_delegates_without_extra_request(self) -> None:
        good = valid_candidate()
        original = mock.Mock(return_value=[good])

        def active(_repo: str, _head: str, _token: str):
            return core.paged(
                f"https://api.github.com/repos/o/r/commits/{HEAD}/check-runs?filter=latest",
                "t",
            )[0]

        with (
            mock.patch.object(core, "paged", original),
            mock.patch.object(subject, "_ORIGINAL_ACTIVE_LATEST", side_effect=active),
        ):
            self.assertIs(
                subject._temporal_latest_required_check("o/r", HEAD, "t"),
                good,
            )
            self.assertIs(core.paged, original)
        original.assert_called_once()

    def test_candidate_completion_after_frontier_fails_before_predecessor(self) -> None:
        candidate = valid_candidate(completed_at="2026-09-22T22:00:00Z")
        with mock.patch.object(subject, "_ORIGINAL_TERMINAL_PROVE") as prove:
            with self.assertRaisesRegex(RuntimeError, "frontier precedes candidate check completion"):
                subject._temporal_prove_candidate_attempt_frontier(
                    "o/r", HEAD, "t", candidate, FRONTIER
                )
        prove.assert_not_called()

    def _run_temporal_prove(
        self,
        candidate: dict,
        direct_job: dict | None,
    ) -> None:
        def predecessor(*_args, **_kwargs):
            if direct_job is not None:
                self.assertIs(
                    core.request_data(
                        "https://api.github.com/repos/o/r/actions/jobs/501",
                        "t",
                    ),
                    direct_job,
                )

        request = mock.Mock(return_value=direct_job)
        with (
            mock.patch.object(core, "request_data", request),
            mock.patch.object(
                subject,
                "_ORIGINAL_TERMINAL_PROVE",
                side_effect=predecessor,
            ),
        ):
            subject._temporal_prove_candidate_attempt_frontier(
                "o/r", HEAD, "t", candidate, FRONTIER
            )
            self.assertIs(core.request_data, request)

    def test_candidate_timing_must_match_direct_protected_job(self) -> None:
        candidate = valid_candidate()
        direct_job = gate_job(
            501,
            101,
            attempt=2,
            started_at="2026-09-22T21:01:00Z",
            status="completed",
            conclusion="success",
        )
        direct_job["completed_at"] = "2026-09-22T21:10:00Z"
        self._run_temporal_prove(candidate, direct_job)

        bad_start = dict(direct_job)
        bad_start["started_at"] = "2026-09-22T21:01:01Z"
        with self.assertRaisesRegex(RuntimeError, "start timing"):
            self._run_temporal_prove(candidate, bad_start)

        bad_completion = dict(direct_job)
        bad_completion["completed_at"] = "2026-09-22T21:10:01Z"
        with self.assertRaisesRegex(RuntimeError, "completion timing"):
            self._run_temporal_prove(candidate, bad_completion)

    def test_missing_direct_job_timing_observation_fails_closed(self) -> None:
        candidate = valid_candidate()
        with (
            mock.patch.object(core, "request_data", return_value={}),
            mock.patch.object(subject, "_ORIGINAL_TERMINAL_PROVE", return_value=None),
        ):
            with self.assertRaisesRegex(RuntimeError, "timing was not observed"):
                subject._temporal_prove_candidate_attempt_frontier(
                    "o/r", HEAD, "t", candidate, FRONTIER
                )

    def test_merge_acceptable_proof_requires_terminal_completion(self) -> None:
        candidate = valid_candidate()
        candidate["status"] = "in_progress"
        candidate["conclusion"] = None
        candidate["completed_at"] = None
        with self.assertRaisesRegex(RuntimeError, "lacks terminal completion"):
            subject._temporal_prove_candidate_attempt_frontier(
                "o/r", HEAD, "t", candidate, FRONTIER
            )

    def test_guarded_request_ignores_unrelated_and_non_dict_job_payload(self) -> None:
        candidate = valid_candidate()
        direct_job = gate_job(
            501,
            101,
            attempt=2,
            started_at="2026-09-22T21:01:00Z",
            status="completed",
            conclusion="success",
        )
        direct_job["completed_at"] = "2026-09-22T21:10:00Z"

        def valid_predecessor(*_args, **_kwargs):
            self.assertEqual(
                core.request_data(
                    "https://api.github.com/repos/o/r/actions/runs/999",
                    "t",
                ),
                {"ok": True},
            )
            self.assertIs(
                core.request_data(
                    "https://api.github.com/repos/o/r/actions/jobs/501",
                    "t",
                ),
                direct_job,
            )

        with (
            mock.patch.object(
                core,
                "request_data",
                side_effect=[{"ok": True}, direct_job],
            ),
            mock.patch.object(
                subject,
                "_ORIGINAL_TERMINAL_PROVE",
                side_effect=valid_predecessor,
            ),
        ):
            subject._temporal_prove_candidate_attempt_frontier(
                "o/r", HEAD, "t", candidate, FRONTIER
            )

        def malformed_predecessor(*_args, **_kwargs):
            self.assertEqual(
                core.request_data(
                    "https://api.github.com/repos/o/r/actions/jobs/501",
                    "t",
                ),
                [],
            )

        with (
            mock.patch.object(core, "request_data", return_value=[]),
            mock.patch.object(
                subject,
                "_ORIGINAL_TERMINAL_PROVE",
                side_effect=malformed_predecessor,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "timing was not observed"):
                subject._temporal_prove_candidate_attempt_frontier(
                    "o/r", HEAD, "t", candidate, FRONTIER
                )

    def test_predecessor_error_restores_request_hook(self) -> None:
        candidate = valid_candidate()
        original = core.request_data
        with mock.patch.object(
            subject,
            "_ORIGINAL_TERMINAL_PROVE",
            side_effect=RuntimeError("predecessor rejected"),
        ):
            with self.assertRaisesRegex(RuntimeError, "predecessor rejected"):
                subject._temporal_prove_candidate_attempt_frontier(
                    "o/r", HEAD, "t", candidate, FRONTIER
                )
        self.assertIs(core.request_data, original)

    def test_install_and_main_guards(self) -> None:
        with mock.patch.object(subject.previous, "install") as install:
            subject.install()
        install.assert_called_once()
        self.assertIs(
            chronology._chronology_prove_candidate_attempt_frontier,
            subject._temporal_prove_candidate_attempt_frontier,
        )
        self.assertIs(core.latest_required_check, subject._temporal_latest_required_check)

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

    def test_module_entrypoint(self) -> None:
        with (
            mock.patch.object(subject.previous, "install") as predecessor_install,
            mock.patch.object(base, "main", return_value=0),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            with self.assertRaises(SystemExit) as raised:
                runpy.run_path(subject.__file__, run_name="__main__")
        self.assertEqual(raised.exception.code, 0)
        predecessor_install.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
