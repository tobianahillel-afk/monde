from __future__ import annotations

import unittest
from unittest import mock

from test_stale_green_bootstrap_authority import check, gate_run
import stale_green_bootstrap_authority as authority


class TerminalWaitCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        authority._reset_request_budget()
        self.addCleanup(authority._reset_request_budget)

    def test_terminal_rerun_without_effective_check_change_times_out(self) -> None:
        terminal = gate_run(101, 1)
        terminal.update({"run_attempt": 2, "status": "completed", "conclusion": "failure"})
        previous = check(10, 101)
        with (
            mock.patch.object(authority.core, "request_data", return_value=terminal) as run_read,
            mock.patch.object(
                authority.core, "required_merge_gate_conclusion", return_value="failure"
            ),
            mock.patch.object(authority.core, "latest_required_check", return_value=previous),
            mock.patch.object(authority.time, "sleep") as sleeper,
        ):
            with self.assertRaisesRegex(RuntimeError, "terminal required-check post-condition"):
                authority._wait_for_terminal_invalidation(
                    "o/r", "shared-head", "t", 101, 1, 10
                )
        run_read.assert_called_once()
        self.assertEqual(sleeper.call_count, authority.MAX_POSTCONDITION_POLLS - 1)


if __name__ == "__main__":
    unittest.main()
