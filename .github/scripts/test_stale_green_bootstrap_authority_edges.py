from __future__ import annotations

import unittest
from unittest import mock

from test_stale_green_bootstrap_authority import check, job
from test_stale_green_bootstrap_pr_snapshot import gate_run, pr
import stale_green_bootstrap_authority as authority


class AuthorityEdgeCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        authority._reset_request_budget()
        self.addCleanup(authority._reset_request_budget)

    def test_direct_target_defers_mid_scan_and_rejects_non_dict_payloads(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        candidate = check(501, 101)

        def spend_budget(*_args, **_kwargs):
            authority._request_count = authority.MAX_GITHUB_REQUESTS_PER_INVOCATION - (
                authority.STATE_WRITE_REQUEST_RESERVE + authority.MAX_POSTCONDITION_POLLS + 6
            )
            return [candidate]

        with mock.patch.object(authority, "_candidate_gate_checks", side_effect=spend_budget):
            with self.assertRaises(authority.DeferredForBudget):
                authority._direct_target_for_pr("o/r", "t", current)
        authority._reset_request_budget()

        with (
            mock.patch.object(authority, "_candidate_gate_checks", return_value=[candidate]),
            mock.patch.object(authority.core, "request_data", return_value=[]),
        ):
            with self.assertRaisesRegex(RuntimeError, "malformed canonical MONDE Gate run"):
                authority._direct_target_for_pr("o/r", "t", current)

        run = gate_run(101, 1)
        with (
            mock.patch.object(authority, "_candidate_gate_checks", return_value=[candidate]),
            mock.patch.object(authority.core, "request_data", side_effect=[run, []]),
        ):
            with self.assertRaisesRegex(RuntimeError, "malformed protected MONDE Gate job"):
                authority._direct_target_for_pr("o/r", "t", current)

    def test_direct_target_skips_wrong_identity_and_old_run(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        candidate = check(501, 101)
        wrong_identity = gate_run(101, 1, branch="other")
        with (
            mock.patch.object(authority, "_candidate_gate_checks", return_value=[candidate]),
            mock.patch.object(authority.core, "request_data", return_value=wrong_identity),
        ):
            self.assertIsNone(authority._direct_target_for_pr("o/r", "t", current))

        old = gate_run(
            101,
            1,
            created_at="2026-09-15T13:00:00Z",
            updated_at="2026-09-15T13:10:00Z",
        )
        with (
            mock.patch.object(authority, "_candidate_gate_checks", return_value=[candidate]),
            mock.patch.object(authority.core, "request_data", return_value=old),
        ):
            self.assertIsNone(authority._direct_target_for_pr("o/r", "t", current))

    def test_process_head_budget_revalidation_and_green_resolution_paths(self) -> None:
        p1 = pr(1, branch="shared", head="shared-head")
        latest = check(600, 200)
        run = gate_run(101, 1)
        target = (run, check(501, 101))

        authority._request_count = authority.MAX_GITHUB_REQUESTS_PER_INVOCATION - (
            authority.MIN_TARGET_REQUEST_HEADROOM + authority.STATE_WRITE_REQUEST_RESERVE
        ) + 1
        with mock.patch.object(authority.core, "latest_required_check", return_value=latest):
            with self.assertRaises(authority.DeferredForBudget):
                authority._process_head_group("o/r", "t", [p1])
        authority._reset_request_budget()

        with (
            mock.patch.object(authority.core, "latest_required_check", return_value=latest),
            mock.patch.object(authority.core, "unresolved_review_threads", side_effect=[True, False]),
            mock.patch.object(authority, "_direct_target_for_pr", return_value=target),
            mock.patch.object(authority, "_current_pr", return_value=p1),
        ):
            self.assertEqual(authority._process_head_group("o/r", "t", [p1]), ([], []))

        with (
            mock.patch.object(
                authority.core,
                "latest_required_check",
                side_effect=[latest, {"id": 601, "status": "completed", "conclusion": "failure"}],
            ),
            mock.patch.object(authority.core, "unresolved_review_threads", side_effect=[True, True]),
            mock.patch.object(authority, "_direct_target_for_pr", return_value=target),
            mock.patch.object(authority, "_current_pr", return_value=p1),
        ):
            self.assertEqual(authority._process_head_group("o/r", "t", [p1]), ([], []))

        def exhaust_before_post(*_args, **_kwargs):
            authority._request_count = authority.MAX_GITHUB_REQUESTS_PER_INVOCATION - (
                authority.MAX_POSTCONDITION_POLLS + authority.STATE_WRITE_REQUEST_RESERVE
            )
            return p1

        with (
            mock.patch.object(authority.core, "latest_required_check", side_effect=[latest, latest]),
            mock.patch.object(authority.core, "unresolved_review_threads", side_effect=[True, True]),
            mock.patch.object(authority, "_direct_target_for_pr", return_value=target),
            mock.patch.object(authority, "_current_pr", side_effect=exhaust_before_post),
        ):
            with self.assertRaises(authority.DeferredForBudget):
                authority._process_head_group("o/r", "t", [p1])
        authority._reset_request_budget()

        with (
            mock.patch.object(
                authority.core,
                "latest_required_check",
                side_effect=[latest, latest, {"id": 602, "status": "completed", "conclusion": "failure"}],
            ),
            mock.patch.object(authority.core, "unresolved_review_threads", side_effect=[True, True, False]),
            mock.patch.object(authority, "_direct_target_for_pr", return_value=target),
            mock.patch.object(authority, "_current_pr", return_value=p1),
            mock.patch.object(authority.core, "rerun_workflow"),
            mock.patch.object(authority, "_wait_for_invalidation", return_value=False),
        ):
            self.assertEqual(authority._process_head_group("o/r", "t", [p1]), ([101], []))

    def test_poll_covers_limits_deferred_head_and_empty_zero_cursor(self) -> None:
        p1, p2 = pr(1), pr(2)
        with (
            mock.patch.object(authority, "_read_scheduler_cursor", return_value=0),
            mock.patch.object(authority.snapshot, "open_pull_requests", return_value=[p1, p2]),
            mock.patch.object(authority, "MAX_HEADS_PER_INVOCATION", 1),
            mock.patch.object(authority, "_process_head_group", return_value=([], [])) as processor,
            mock.patch.object(authority, "_write_scheduler_cursor") as writer,
        ):
            self.assertEqual(authority.poll("o/r", "t"), [])
        self.assertEqual(processor.call_count, 1)
        writer.assert_called_once_with("o/r", "t", 1)

        with (
            mock.patch.object(authority, "_read_scheduler_cursor", return_value=0),
            mock.patch.object(authority.snapshot, "open_pull_requests", return_value=[p1, p2]),
            mock.patch.object(authority, "_process_head_group", side_effect=authority.DeferredForBudget("later")),
            mock.patch.object(authority, "_write_scheduler_cursor") as writer,
        ):
            self.assertEqual(authority.poll("o/r", "t"), [])
        writer.assert_called_once_with("o/r", "t", 1)

        with (
            mock.patch.object(authority, "_read_scheduler_cursor", return_value=0),
            mock.patch.object(authority.snapshot, "open_pull_requests", return_value=[]),
            mock.patch.object(authority, "_write_scheduler_cursor") as writer,
        ):
            self.assertEqual(authority.poll("o/r", "t"), [])
        writer.assert_not_called()

    def test_poll_stops_at_rerun_limit(self) -> None:
        prs = [pr(number) for number in range(1, 6)]
        with (
            mock.patch.object(authority, "_read_scheduler_cursor", return_value=0),
            mock.patch.object(authority.snapshot, "open_pull_requests", return_value=prs),
            mock.patch.object(authority, "MAX_RERUNS_PER_INVOCATION", 1),
            mock.patch.object(authority, "_process_head_group", return_value=([999], [])) as processor,
            mock.patch.object(authority, "_write_scheduler_cursor") as writer,
        ):
            self.assertEqual(authority.poll("o/r", "t"), [999])
        self.assertEqual(processor.call_count, 1)
        writer.assert_called_once_with("o/r", "t", 1)


if __name__ == "__main__":
    unittest.main()
