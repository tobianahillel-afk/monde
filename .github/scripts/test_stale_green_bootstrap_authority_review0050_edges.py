from __future__ import annotations

import unittest
from unittest import mock

from test_stale_green_bootstrap_pr_snapshot import SHA
from test_stale_green_bootstrap_authority import pr
import stale_green_bootstrap_authority_review0050 as subject


class Review0050FinalEdgeTests(unittest.TestCase):
    def test_pending_origin_rejects_malformed_identity(self) -> None:
        current = pr(1, branch="shared", head=SHA)
        state = subject._pending_state(subject.SchedulerStateV5(0), current, 101, 1, 601)

        malformed = dict(current)
        malformed["number"] = True
        with mock.patch.object(subject.core, "request_data", return_value=malformed):
            with self.assertRaisesRegex(RuntimeError, "malformed pending pull-request authority"):
                subject._pending_origin_pr("o/r", "t", state)


if __name__ == "__main__":
    unittest.main()
