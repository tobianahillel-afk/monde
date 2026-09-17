from __future__ import annotations

import os
import unittest
from unittest import mock

from test_stale_green_bootstrap_pr_snapshot import SHA
from test_stale_green_bootstrap_authority import gate_run, pr
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0048 as observation
import stale_green_bootstrap_authority_review0050 as v5
import stale_green_bootstrap_authority_review0050_recovery as subject


class Review0050RecoveryEdgeTests(unittest.TestCase):
    def setUp(self) -> None:
        base._reset_request_budget()
        self.addCleanup(base._reset_request_budget)
        self.current = pr(1, state="open", branch="shared", head=SHA)
        self.state = v5._pending_state(v5.SchedulerStateV5(0), self.current, 101, 2, 601)

    def _env(self) -> dict[str, str]:
        return {
            "BOOTSTRAP_RECOVERY_CONFIRMATION": subject.RECOVERY_CONFIRMATION,
            "BOOTSTRAP_RECOVERY_REASON": "manual verification",
            "BOOTSTRAP_RECOVERY_PENDING_PR": "1",
            "BOOTSTRAP_RECOVERY_PENDING_HEAD": SHA,
            "BOOTSTRAP_RECOVERY_RUN_ID": "101",
            "BOOTSTRAP_RECOVERY_BASELINE_ATTEMPT": "2",
            "BOOTSTRAP_RECOVERY_CHECK_ID": "601",
        }

    def test_resume_rejects_malformed_regressed_and_jump_attempts(self) -> None:
        with (
            mock.patch.object(v5, "_pending_origin_pr", return_value=self.current),
            mock.patch.object(subject.core, "request_data", return_value=[]),
        ):
            with self.assertRaisesRegex(RuntimeError, "malformed pending workflow"):
                subject._resume_pending("o/r", "t", self.state)

        regressed = gate_run(101, 1, head=SHA)
        regressed.update({"run_attempt": 1, "status": "completed", "conclusion": "success"})
        with (
            mock.patch.object(v5, "_pending_origin_pr", return_value=self.current),
            mock.patch.object(subject.core, "request_data", return_value=regressed),
        ):
            with self.assertRaisesRegex(RuntimeError, "regressed"):
                subject._resume_pending("o/r", "t", self.state)

        jumped = gate_run(101, 1, head=SHA)
        jumped.update({"run_attempt": 4, "status": "completed", "conclusion": "success"})
        with (
            mock.patch.object(v5, "_pending_origin_pr", return_value=self.current),
            mock.patch.object(subject.core, "request_data", return_value=jumped),
        ):
            with self.assertRaises(v5.previous.PendingMutationUncertain):
                subject._resume_pending("o/r", "t", self.state)

    def test_resume_terminal_green_requeues_sibling_or_clears(self) -> None:
        run = gate_run(101, 1, head=SHA)
        run.update({"run_attempt": 3, "status": "completed", "conclusion": "success"})
        sibling = pr(2, state="open", branch="shared", head=SHA)
        with (
            mock.patch.object(v5, "_pending_origin_pr", return_value=self.current),
            mock.patch.object(subject.core, "request_data", return_value=run),
            mock.patch.object(observation, "_wait_for_terminal_invalidation", return_value=False),
            mock.patch.object(v5, "_unresolved_same_head", return_value=[sibling]),
            mock.patch.object(v5, "_write_state") as writer,
        ):
            self.assertEqual(subject._resume_pending("o/r", "t", self.state), [])
        self.assertEqual(writer.call_args.args[2].scan_pr, 2)

        with (
            mock.patch.object(v5, "_pending_origin_pr", return_value=self.current),
            mock.patch.object(subject.core, "request_data", return_value=run),
            mock.patch.object(observation, "_wait_for_terminal_invalidation", return_value=False),
            mock.patch.object(v5, "_unresolved_same_head", return_value=[]),
            mock.patch.object(v5, "_write_state") as writer,
        ):
            self.assertEqual(subject._resume_pending("o/r", "t", self.state), [])
        self.assertEqual(writer.call_args.args[2], v5.SchedulerStateV5(0))

    def test_recovery_rejects_malformed_run_and_invalid_check_shapes(self) -> None:
        with (
            mock.patch.dict(os.environ, self._env(), clear=True),
            mock.patch.object(v5, "_read_state", return_value=self.state),
            mock.patch.object(v5, "_pending_origin_pr", return_value=self.current),
            mock.patch.object(subject.core, "request_data", return_value=[]),
        ):
            with self.assertRaisesRegex(RuntimeError, "malformed pending workflow run during recovery"):
                subject._recover_confirmed_unposted("o/r", "t")

        baseline = gate_run(101, 1, head=SHA)
        baseline.update({"run_attempt": 2, "status": "completed", "conclusion": "success"})
        for latest in (None, {"id": True}, {"id": 601.0}):
            with (
                self.subTest(latest=latest),
                mock.patch.dict(os.environ, self._env(), clear=True),
                mock.patch.object(v5, "_read_state", return_value=self.state),
                mock.patch.object(v5, "_pending_origin_pr", return_value=self.current),
                mock.patch.object(subject.core, "request_data", return_value=baseline),
                mock.patch.object(subject.core, "latest_required_check", return_value=latest),
            ):
                with self.assertRaisesRegex(RuntimeError, "check identity changed"):
                    subject._recover_confirmed_unposted("o/r", "t")

    def test_recovery_scan_target_open_origin_or_closed_without_sibling(self) -> None:
        baseline = gate_run(101, 1, head=SHA)
        baseline.update({"run_attempt": 2, "status": "completed", "conclusion": "success"})
        latest = {"id": 601, "status": "completed", "conclusion": "success"}

        with (
            mock.patch.dict(os.environ, self._env(), clear=True),
            mock.patch.object(v5, "_read_state", return_value=self.state),
            mock.patch.object(v5, "_pending_origin_pr", return_value=self.current),
            mock.patch.object(subject.core, "request_data", return_value=baseline),
            mock.patch.object(subject.core, "latest_required_check", return_value=latest),
            mock.patch.object(v5, "_unresolved_same_head", return_value=[]),
            mock.patch.object(v5, "_write_state") as writer,
        ):
            subject._recover_confirmed_unposted("o/r", "t")
        self.assertEqual(writer.call_args.args[2].scan_pr, 1)

        closed = pr(1, state="closed", branch="shared", head=SHA)
        with (
            mock.patch.dict(os.environ, self._env(), clear=True),
            mock.patch.object(v5, "_read_state", return_value=self.state),
            mock.patch.object(v5, "_pending_origin_pr", return_value=closed),
            mock.patch.object(subject.core, "request_data", return_value=baseline),
            mock.patch.object(subject.core, "latest_required_check", return_value=latest),
            mock.patch.object(v5, "_unresolved_same_head", return_value=[]),
            mock.patch.object(v5, "_write_state") as writer,
        ):
            subject._recover_confirmed_unposted("o/r", "t")
        self.assertEqual(writer.call_args.args[2].scan_pr, 0)


if __name__ == "__main__":
    unittest.main()
