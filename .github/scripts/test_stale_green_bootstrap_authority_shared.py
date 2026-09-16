from __future__ import annotations

import unittest
from unittest import mock

from test_stale_green_bootstrap_authority import check
from test_stale_green_bootstrap_pr_snapshot import gate_run, pr
import stale_green_bootstrap_authority as authority


class SharedHeadContinuationTests(unittest.TestCase):
    def setUp(self) -> None:
        authority._reset_request_budget()
        self.addCleanup(authority._reset_request_budget)

    def test_clean_green_first_sibling_falls_through_to_unresolved_second_sibling(self) -> None:
        first = pr(1, branch="shared", head="shared-head")
        second = pr(2, branch="shared", head="shared-head")
        first_run = gate_run(201, 1)
        second_run = gate_run(202, 2)
        initial = check(600, 300)
        still_green = check(601, 301)

        with (
            mock.patch.object(
                authority.core,
                "latest_required_check",
                side_effect=[initial, initial, still_green, still_green],
            ),
            mock.patch.object(
                authority.core,
                "unresolved_review_threads",
                side_effect=[True, True, False, True, True],
            ),
            mock.patch.object(
                authority,
                "_direct_target_for_pr",
                side_effect=[(first_run, check(501, 201)), (second_run, check(502, 202))],
            ),
            mock.patch.object(authority, "_current_pr", side_effect=[first, second]),
            mock.patch.object(authority.core, "rerun_workflow") as rerun,
            mock.patch.object(authority, "_wait_for_invalidation", side_effect=[False, True]),
        ):
            self.assertEqual(authority._process_head_group("o/r", "t", [first, second]), ([202], []))

        self.assertEqual(
            [call.args[1] for call in rerun.call_args_list],
            [201, 202],
        )


if __name__ == "__main__":
    unittest.main()
