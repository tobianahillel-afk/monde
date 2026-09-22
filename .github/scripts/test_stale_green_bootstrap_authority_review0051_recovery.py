from __future__ import annotations

import os
import runpy
import unittest
from unittest import mock

from test_stale_green_bootstrap_pr_snapshot import SHA
from test_stale_green_bootstrap_authority import gate_run, pr
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0050 as v5
import stale_green_bootstrap_authority_review0050_recovery as previous
import stale_green_bootstrap_authority_review0051_recovery as subject


class Review0051RecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        base._reset_request_budget()
        self.addCleanup(base._reset_request_budget)
        self.current = pr(1, state="open", branch="shared", head=SHA)
        self.state = v5._pending_state(v5.SchedulerStateV5(0), self.current, 101, 2, 601)

    def _env(self) -> dict[str, str]:
        return {
            "BOOTSTRAP_RECOVERY_CONFIRMATION": subject.RECOVERY_CONFIRMATION,
            "BOOTSTRAP_RECOVERY_REASON": "ticket OPS-51 proves the original POST never occurred",
            "BOOTSTRAP_RECOVERY_PENDING_PR": "1",
            "BOOTSTRAP_RECOVERY_PENDING_HEAD": SHA,
            "BOOTSTRAP_RECOVERY_RUN_ID": "101",
            "BOOTSTRAP_RECOVERY_BASELINE_ATTEMPT": "2",
            "BOOTSTRAP_RECOVERY_CHECK_ID": "601",
        }

    @staticmethod
    def _baseline_run() -> dict:
        run = gate_run(101, 1, head=SHA)
        run.update({"run_attempt": 2, "status": "completed", "conclusion": "success"})
        return run

    def test_inspection_preserves_pending_and_never_mutates(self) -> None:
        latest = {"id": 601, "status": "completed", "conclusion": "success"}
        with (
            mock.patch.dict(os.environ, self._env(), clear=True),
            mock.patch.object(v5, "_read_state", return_value=self.state),
            mock.patch.object(subject.core, "request_data", return_value=self._baseline_run()),
            mock.patch.object(subject.core, "latest_required_check", return_value=latest),
            mock.patch.object(v5, "_write_state") as writer,
            mock.patch.object(subject.core, "rerun_workflow") as rerun,
            mock.patch("builtins.print") as printer,
        ):
            self.assertEqual(subject._inspect_confirmed_unposted("o/r", "t"), 0)
        writer.assert_not_called()
        rerun.assert_not_called()
        output = printer.call_args.args[0]
        self.assertIn("durable pending mutation preserved", output)
        self.assertIn("manually rerun canonical run 101", output)
        self.assertIn("do not clear issue #7", output)
        self.assertIn("OPS-51", output)

    def test_inspection_refuses_malformed_or_changed_run(self) -> None:
        with (
            mock.patch.dict(os.environ, self._env(), clear=True),
            mock.patch.object(v5, "_read_state", return_value=self.state),
            mock.patch.object(subject.core, "request_data", return_value=[]),
        ):
            with self.assertRaisesRegex(RuntimeError, "malformed pending workflow run"):
                subject._inspect_confirmed_unposted("o/r", "t")

        advanced = self._baseline_run()
        advanced["run_attempt"] = 3
        with (
            mock.patch.dict(os.environ, self._env(), clear=True),
            mock.patch.object(v5, "_read_state", return_value=self.state),
            mock.patch.object(subject.core, "request_data", return_value=advanced),
        ):
            with self.assertRaisesRegex(RuntimeError, "attempt changed"):
                subject._inspect_confirmed_unposted("o/r", "t")

    def test_inspection_refuses_check_identity_drift(self) -> None:
        for latest in (None, {"id": True}, {"id": 601.0}, {"id": 999}):
            with (
                self.subTest(latest=latest),
                mock.patch.dict(os.environ, self._env(), clear=True),
                mock.patch.object(v5, "_read_state", return_value=self.state),
                mock.patch.object(subject.core, "request_data", return_value=self._baseline_run()),
                mock.patch.object(subject.core, "latest_required_check", return_value=latest),
            ):
                with self.assertRaisesRegex(RuntimeError, "check identity changed"):
                    subject._inspect_confirmed_unposted("o/r", "t")

    def test_install_and_main_route_normal_and_inspection_modes(self) -> None:
        with mock.patch.object(previous, "install") as predecessor_install:
            subject.install()
        predecessor_install.assert_called_once_with()

        with (
            mock.patch.object(subject, "install"),
            mock.patch.object(base, "main", return_value=7),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            self.assertEqual(subject.main(), 7)

        with (
            mock.patch.object(subject, "install"),
            mock.patch.dict(os.environ, {"BOOTSTRAP_RECOVERY_ACTION": "bad"}, clear=True),
        ):
            with self.assertRaisesRegex(RuntimeError, "unsupported"):
                subject.main()

        with (
            mock.patch.object(subject, "install"),
            mock.patch.dict(
                os.environ,
                {"BOOTSTRAP_RECOVERY_ACTION": subject.RECOVERY_ACTION},
                clear=True,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "GITHUB_REPOSITORY"):
                subject.main()

        with (
            mock.patch.object(subject, "install"),
            mock.patch.object(subject, "_inspect_confirmed_unposted", return_value=0) as inspect,
            mock.patch.dict(
                os.environ,
                {
                    "BOOTSTRAP_RECOVERY_ACTION": subject.RECOVERY_ACTION,
                    "GITHUB_REPOSITORY": "o/r",
                    "GITHUB_TOKEN": "t",
                },
                clear=True,
            ),
        ):
            self.assertEqual(subject.main(), 0)
        inspect.assert_called_once_with("o/r", "t")

    def test_workflow_routes_recovery_to_read_only_inspection(self) -> None:
        workflow = (subject.__file__.replace(
            ".github/scripts/stale_green_bootstrap_authority_review0051_recovery.py",
            ".github/workflows/monde-stale-green-bootstrap.yml",
        ))
        from pathlib import Path
        text = Path(workflow).read_text(encoding="utf-8")
        section = text.split("  pending-recovery:", 1)[1]
        self.assertIn("inspect-unposted-pending", section)
        self.assertIn("issues: read", section)
        self.assertIn("actions: read", section)
        self.assertNotIn("issues: write", section)
        self.assertNotIn("actions: write", section)
        self.assertIn("stale_green_bootstrap_authority_review0051_recovery.py", section)

    def test_script_entrypoint(self) -> None:
        with (
            mock.patch.object(previous, "install") as predecessor_install,
            mock.patch.object(base, "main", return_value=0),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            with self.assertRaises(SystemExit) as exited:
                runpy.run_path(subject.__file__, run_name="__main__")
        self.assertEqual(exited.exception.code, 0)
        predecessor_install.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
