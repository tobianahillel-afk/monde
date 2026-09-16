from __future__ import annotations

import unittest
from unittest import mock

from test_stale_green_bootstrap_authority import check, gate_run, job, pr
import stale_green_bootstrap_authority as authority


class Review0047RegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        authority._reset_request_budget()
        self.addCleanup(authority._reset_request_budget)

    def test_scheduler_v3_exact_issue_id_and_v2_migration(self) -> None:
        state = authority.SchedulerState(4, 2, 3, "a" * 64)
        issue = {
            "number": 7,
            "title": authority.SCHEDULER_STATE_TITLE,
            "state": "open",
            "body": authority._scheduler_body(*state),
        }
        self.assertEqual(authority._parse_scheduler_state(issue, 7), state)

        with self.assertRaisesRegex(RuntimeError, "identity"):
            authority._parse_scheduler_state({**issue, "number": 7.0}, 7)
        with self.assertRaisesRegex(RuntimeError, "scan anchor"):
            authority._validate_scheduler_state(authority.SchedulerState(4, 2, 3, "bad"))
        with self.assertRaisesRegex(RuntimeError, "idle scheduler"):
            authority._validate_scheduler_state(authority.SchedulerState(4, 0, 1, "b" * 64))

        v2 = {
            **issue,
            "body": (
                f"{authority.PREVIOUS_SCHEDULER_STATE_MARKER}\n"
                "cursor_pr: 4\nscan_pr: 2\nscan_page: 9\n\n"
                "Machine-managed durable cursor for the trusted default-branch stale-green bootstrap. "
                "Do not edit manually. The scheduled bootstrap validates this exact marker before reading or updating the cursor."
            ),
        }
        self.assertEqual(
            authority._parse_scheduler_state(v2, 7),
            authority.SchedulerState(4, 2, 1, "-"),
        )
        page = authority.ScanPage(5, "c" * 64)
        self.assertEqual(page, 5)
        self.assertEqual(page.anchor, "c" * 64)

    def test_target_scan_anchor_detects_drift_and_persists_new_boundary(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        prior = [check(701, 301)]
        anchor = authority._check_page_anchor(prior, True)

        with mock.patch.object(
            authority,
            "_candidate_gate_check_page",
            side_effect=[(prior, True), ([], False)],
        ) as pages:
            target, continuation = authority._direct_target_for_pr(
                "o/r", "t", current, 2, anchor
            )
        self.assertIsNone(target)
        self.assertIsNone(continuation)
        self.assertEqual([call.args[3] for call in pages.call_args_list], [1, 2])

        target_check = check(501, 101)
        target_run = gate_run(101, 1)
        target_job = job(501, 101)
        with (
            mock.patch.object(
                authority,
                "_candidate_gate_check_page",
                side_effect=[(prior, True), ([target_check], False)],
            ) as pages,
            mock.patch.object(
                authority.core,
                "request_data",
                side_effect=[target_run, target_job],
            ),
        ):
            target, continuation = authority._direct_target_for_pr(
                "o/r", "t", current, 3, "d" * 64
            )
        self.assertIsNotNone(target)
        self.assertIsNone(continuation)
        self.assertEqual([call.args[3] for call in pages.call_args_list], [2, 1])

        with mock.patch.object(
            authority,
            "_candidate_gate_check_page",
            side_effect=[(prior, False), ([], True), ([], True)],
        ) as pages:
            target, continuation = authority._direct_target_for_pr(
                "o/r", "t", current, 2, anchor
            )
        self.assertIsNone(target)
        self.assertEqual(continuation, 3)
        assert continuation is not None
        self.assertEqual(continuation.anchor, authority._check_page_anchor([], True))
        self.assertEqual([call.args[3] for call in pages.call_args_list], [1, 1, 2])

    def test_strict_terminal_binding_requires_exact_rerun_job_and_pr_authority(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        terminal = gate_run(101, 1)
        terminal.update({"run_attempt": 2, "status": "completed", "conclusion": "failure"})
        failed = check(11, 101, conclusion="failure")
        failed_job = job(11, 101, attempt=2, conclusion="failure")
        with (
            mock.patch.object(authority.core, "request_data", side_effect=[terminal, failed_job]),
            mock.patch.object(authority.core, "required_merge_gate_conclusion", return_value="failure"),
            mock.patch.object(authority.core, "latest_required_check", return_value=failed),
            mock.patch.object(authority, "_current_pr", return_value=current) as current_pr,
        ):
            self.assertTrue(
                authority._wait_for_terminal_invalidation(
                    "o/r", "shared-head", "t", 101, 1, 10, current, True
                )
            )
        current_pr.assert_called_once()

        unrelated = check(12, 999, conclusion="failure")
        with (
            mock.patch.object(authority.core, "request_data", return_value=terminal),
            mock.patch.object(authority.core, "required_merge_gate_conclusion", return_value="failure"),
            mock.patch.object(authority.core, "latest_required_check", return_value=unrelated),
            mock.patch.object(authority.time, "sleep") as sleeper,
        ):
            with self.assertRaises(authority.DeferredObservation):
                authority._wait_for_terminal_invalidation(
                    "o/r", "shared-head", "t", 101, 1, 10, current, True
                )
        self.assertEqual(sleeper.call_count, authority.MAX_POSTCONDITION_POLLS - 1)

        success_job = job(11, 101, attempt=2, conclusion="success")
        with (
            mock.patch.object(authority.core, "request_data", side_effect=[terminal, success_job]),
            mock.patch.object(authority.core, "required_merge_gate_conclusion", return_value="failure"),
            mock.patch.object(authority.core, "latest_required_check", return_value=failed),
        ):
            with self.assertRaisesRegex(RuntimeError, "disagree"):
                authority._wait_for_terminal_invalidation(
                    "o/r", "shared-head", "t", 101, 1, 10, current, True
                )

        with (
            mock.patch.object(authority.core, "request_data", side_effect=[terminal, failed_job]),
            mock.patch.object(authority.core, "required_merge_gate_conclusion", return_value="failure"),
            mock.patch.object(authority.core, "latest_required_check", return_value=failed),
            mock.patch.object(authority, "_current_pr", return_value=None),
        ):
            with self.assertRaises(authority.DeferredObservation):
                authority._wait_for_terminal_invalidation(
                    "o/r", "shared-head", "t", 101, 1, 10, current, True
                )

    def test_process_persists_delayed_observation_and_revalidates_at_mutation_boundary(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        in_progress = check(600, 200, status="in_progress", conclusion=None)
        with (
            mock.patch.object(authority.core, "latest_required_check", return_value=in_progress),
            mock.patch.object(authority.core, "unresolved_review_threads", return_value=True),
        ):
            self.assertEqual(
                authority._process_head_group("o/r", "t", [current], 3),
                ([], [], (1, 1)),
            )
        with (
            mock.patch.object(authority.core, "latest_required_check", return_value=in_progress),
            mock.patch.object(authority.core, "unresolved_review_threads", return_value=False),
        ):
            self.assertEqual(
                authority._process_head_group("o/r", "t", [current], 3),
                ([], [], None),
            )

        latest = check(601, 201)
        target = (gate_run(101, 1), check(501, 101))
        with (
            mock.patch.object(authority.core, "latest_required_check", side_effect=[latest, latest]),
            mock.patch.object(authority.core, "unresolved_review_threads", side_effect=[True, True]),
            mock.patch.object(authority, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(authority, "_current_pr", side_effect=[current, None]),
            mock.patch.object(authority.core, "rerun_workflow") as rerun,
        ):
            self.assertEqual(
                authority._process_head_group("o/r", "t", [current], 3),
                ([], [], (1, 1)),
            )
        rerun.assert_not_called()

        with (
            mock.patch.object(authority.core, "latest_required_check", side_effect=[latest, latest]),
            mock.patch.object(authority.core, "unresolved_review_threads", side_effect=[True, True]),
            mock.patch.object(authority, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(authority, "_current_pr", return_value=current),
            mock.patch.object(authority.core, "rerun_workflow") as rerun,
            mock.patch.object(
                authority,
                "_wait_for_terminal_invalidation",
                side_effect=authority.DeferredObservation("still pending"),
            ),
        ):
            posted, errors, continuation = authority._process_head_group(
                "o/r", "t", [current], 3
            )
        self.assertEqual(posted, [101])
        self.assertEqual(errors, [])
        self.assertEqual(continuation, (1, 1))
        rerun.assert_called_once()

    def test_poll_persists_scan_anchor(self) -> None:
        current = pr(1)
        anchor = "e" * 64
        state = authority.SchedulerState(0, 1, 3, anchor)
        next_page = authority.ScanPage(5, "f" * 64)
        with (
            mock.patch.object(authority, "_read_scheduler_state", return_value=state),
            mock.patch.object(authority.snapshot, "open_pull_requests", return_value=[current]),
            mock.patch.object(
                authority,
                "_process_head_group",
                return_value=([], [], (1, next_page)),
            ) as processor,
            mock.patch.object(authority, "_write_scheduler_state") as writer,
        ):
            self.assertEqual(authority.poll("o/r", "t"), [])
        self.assertEqual(processor.call_args.args[6], anchor)
        writer.assert_called_once_with(
            "o/r", "t", authority.SchedulerState(0, 1, 5, "f" * 64)
        )


if __name__ == "__main__":
    unittest.main()
