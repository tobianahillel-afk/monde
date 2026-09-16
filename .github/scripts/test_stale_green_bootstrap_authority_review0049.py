from __future__ import annotations

import unittest
from unittest import mock

from test_stale_green_bootstrap_authority import check, gate_run, pr
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0048 as previous
import stale_green_bootstrap_authority_review0049 as subject


class Review0049PendingMutationTests(unittest.TestCase):
    def setUp(self) -> None:
        base._reset_request_budget()
        self.addCleanup(base._reset_request_budget)

    def _issue(self, body: str) -> dict:
        return {
            "number": 7,
            "title": base.SCHEDULER_STATE_TITLE,
            "state": "open",
            "body": body,
        }

    def test_state_round_trip_and_legacy_migration(self) -> None:
        legacy = self._issue(
            "MONDE_STALE_GREEN_SCHEDULER_V1\n"
            "cursor_pr: 4\n\n"
            "Machine-managed durable cursor for the trusted default-branch stale-green bootstrap. "
            "Do not edit manually. The scheduled bootstrap validates this exact marker before reading or updating the cursor."
        )
        self.assertEqual(subject._parse_state(legacy, 7), subject.SchedulerStateV4(4))

        current = pr(1, branch="shared", head="shared-head")
        pending = subject._pending_state(
            subject.SchedulerStateV4(3), current, 101, 2, 501
        )
        parsed = subject._parse_state(self._issue(subject._scheduler_body(pending)), 7)
        self.assertEqual(parsed, pending)
        self.assertEqual(parsed.pending_pr, 1)
        self.assertEqual(len(parsed.pending_authority), 64)

    def test_state_rejects_partial_pending_or_malformed_issue(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "partial pending"):
            subject._validate_state(
                subject.SchedulerStateV4(0, pending_run_id=1)
            )
        with self.assertRaisesRegex(RuntimeError, "pending scheduler"):
            subject._validate_state(
                subject.SchedulerStateV4(
                    0, 1, 1, "-", 1, "bad", 101, 1, 501
                )
            )
        malformed = self._issue(subject._scheduler_body(subject.SchedulerStateV4(0)))
        malformed["title"] = "other"
        with self.assertRaisesRegex(RuntimeError, "identity"):
            subject._parse_state(malformed, 7)

    def test_write_state_requires_durable_ack(self) -> None:
        state = subject.SchedulerStateV4(3)
        ack = self._issue(subject._scheduler_body(state))
        with (
            mock.patch.object(base, "_scheduler_issue_number", return_value=7),
            mock.patch.object(subject.core, "request_data", return_value=ack) as request,
        ):
            subject._write_state("o/r", "t", state)
        self.assertEqual(request.call_args.args[2], "PATCH")

        with (
            mock.patch.object(base, "_scheduler_issue_number", return_value=7),
            mock.patch.object(subject.core, "request_data", return_value={}),
        ):
            with self.assertRaisesRegex(RuntimeError, "identity"):
                subject._write_state("o/r", "t", state)

    def test_resume_pending_never_posts_and_retains_unobserved_mutation(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        state = subject._pending_state(subject.SchedulerStateV4(0), current, 101, 1, 601)
        run = gate_run(101, 1)
        run.update({"run_attempt": 1, "status": "completed", "conclusion": "success"})
        with (
            mock.patch.object(subject, "_current_pending_pr", return_value=current),
            mock.patch.object(subject.core, "request_data", return_value=run),
            mock.patch.object(
                previous,
                "_wait_for_terminal_invalidation",
                side_effect=base.DeferredObservation("not visible"),
            ),
            mock.patch.object(subject.core, "rerun_workflow") as rerun,
            mock.patch.object(subject, "_write_state") as writer,
        ):
            self.assertEqual(subject._resume_pending("o/r", "t", state), [])
        rerun.assert_not_called()
        writer.assert_not_called()

    def test_resume_pending_clears_only_after_terminal_observation(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        state = subject._pending_state(subject.SchedulerStateV4(0), current, 101, 1, 601)
        run = gate_run(101, 1)
        run.update({"run_attempt": 2, "status": "completed", "conclusion": "failure"})
        with (
            mock.patch.object(subject, "_current_pending_pr", return_value=current),
            mock.patch.object(subject.core, "request_data", return_value=run),
            mock.patch.object(previous, "_wait_for_terminal_invalidation", return_value=True),
            mock.patch.object(subject.core, "unresolved_review_threads", return_value=True),
            mock.patch.object(subject, "_write_state") as writer,
        ):
            self.assertEqual(subject._resume_pending("o/r", "t", state), [])
        written = writer.call_args.args[2]
        self.assertEqual(written.pending_pr, 0)
        self.assertEqual(written.scan_pr, 1)

    def test_resume_pending_rejects_attempt_jump_and_authority_change(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        state = subject._pending_state(subject.SchedulerStateV4(0), current, 101, 1, 601)
        jumped = gate_run(101, 1)
        jumped.update({"run_attempt": 3, "status": "completed", "conclusion": "failure"})
        with (
            mock.patch.object(subject, "_current_pending_pr", return_value=current),
            mock.patch.object(subject.core, "request_data", return_value=jumped),
        ):
            with self.assertRaises(subject.PendingMutationUncertain):
                subject._resume_pending("o/r", "t", state)

        changed = pr(1, branch="shared", head="shared-head", merge_sha="b" * 40)
        with mock.patch.object(subject.core, "request_data", return_value=changed):
            with self.assertRaisesRegex(RuntimeError, "authority changed"):
                subject._current_pending_pr("o/r", "t", state)

    def test_process_writes_pending_before_post_and_keeps_it_on_timeout(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        latest = check(601, 201)
        target = (gate_run(101, 1), check(501, 101))
        events: list[str] = []
        with (
            mock.patch.object(subject.core, "latest_required_check", return_value=latest),
            mock.patch.object(subject.core, "unresolved_review_threads", return_value=True),
            mock.patch.object(previous, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(base, "_current_pr", return_value=current),
            mock.patch.object(previous, "_mutation_baseline", return_value=1),
            mock.patch.object(
                subject,
                "_write_state",
                side_effect=lambda *args: events.append("state"),
            ),
            mock.patch.object(
                subject.core,
                "rerun_workflow",
                side_effect=lambda *args: events.append("post"),
            ),
            mock.patch.object(
                previous,
                "_wait_for_terminal_invalidation",
                side_effect=base.DeferredObservation("later"),
            ),
        ):
            with self.assertRaises(subject.PendingMutationObservation):
                subject._process_head_group(
                    "o/r", "t", [current], 3, subject.SchedulerStateV4(0)
                )
        self.assertEqual(events, ["state", "post"])

    def test_process_keeps_write_ahead_state_when_post_outcome_is_ambiguous(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        latest = check(601, 201)
        target = (gate_run(101, 1), check(501, 101))
        with (
            mock.patch.object(subject.core, "latest_required_check", return_value=latest),
            mock.patch.object(subject.core, "unresolved_review_threads", return_value=True),
            mock.patch.object(previous, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(base, "_current_pr", return_value=current),
            mock.patch.object(previous, "_mutation_baseline", return_value=1),
            mock.patch.object(subject, "_write_state") as writer,
            mock.patch.object(subject.core, "rerun_workflow", side_effect=RuntimeError("network")),
        ):
            with self.assertRaises(subject.PendingMutationUncertain):
                subject._process_head_group(
                    "o/r", "t", [current], 3, subject.SchedulerStateV4(0)
                )
        self.assertEqual(writer.call_count, 1)
        self.assertEqual(writer.call_args.args[2].pending_run_id, 101)

    def test_process_clears_pending_after_terminal_result(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        latest = check(601, 201)
        target = (gate_run(101, 1), check(501, 101))
        with (
            mock.patch.object(subject.core, "latest_required_check", return_value=latest),
            mock.patch.object(subject.core, "unresolved_review_threads", return_value=True),
            mock.patch.object(previous, "_direct_target_for_pr", return_value=(target, None)),
            mock.patch.object(base, "_current_pr", return_value=current),
            mock.patch.object(previous, "_mutation_baseline", return_value=1),
            mock.patch.object(subject, "_write_state") as writer,
            mock.patch.object(subject.core, "rerun_workflow"),
            mock.patch.object(previous, "_wait_for_terminal_invalidation", return_value=True),
        ):
            self.assertEqual(
                subject._process_head_group(
                    "o/r", "t", [current], 3, subject.SchedulerStateV4(0)
                ),
                ([101], [], None),
            )
        self.assertEqual(writer.call_count, 2)
        self.assertEqual(writer.call_args_list[0].args[2].pending_run_id, 101)
        self.assertEqual(writer.call_args_list[1].args[2].pending_run_id, 0)

    def test_poll_resumes_pending_before_scanning_or_posting(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        state = subject._pending_state(subject.SchedulerStateV4(0), current, 101, 1, 601)
        with (
            mock.patch.object(subject, "_read_state", return_value=state),
            mock.patch.object(subject, "_resume_pending", return_value=[]) as resume,
            mock.patch.object(base.snapshot, "open_pull_requests") as open_prs,
        ):
            self.assertEqual(subject.poll("o/r", "t"), [])
        resume.assert_called_once_with("o/r", "t", state)
        open_prs.assert_not_called()

    def test_poll_preserves_pending_state_on_deferred_post_observation(self) -> None:
        current = pr(1, branch="shared", head="shared-head")
        state = subject.SchedulerStateV4(0)
        with (
            mock.patch.object(subject, "_read_state", return_value=state),
            mock.patch.object(base.snapshot, "open_pull_requests", return_value=[current]),
            mock.patch.object(
                subject,
                "_process_head_group",
                side_effect=subject.PendingMutationObservation(101),
            ),
            mock.patch.object(subject, "_write_state") as writer,
        ):
            self.assertEqual(subject.poll("o/r", "t"), [101])
        writer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
