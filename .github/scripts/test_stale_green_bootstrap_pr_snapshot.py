from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import runpy
import sys
import unittest
from unittest import mock

SCRIPT_DIR = Path(__file__).parent
CORE_SCRIPT = SCRIPT_DIR / "stale_green_bootstrap.py"
SNAPSHOT_SCRIPT = SCRIPT_DIR / "stale_green_bootstrap_pr_snapshot.py"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

CORE_SPEC = importlib.util.spec_from_file_location("stale_green_bootstrap", CORE_SCRIPT)
assert CORE_SPEC and CORE_SPEC.loader
core = importlib.util.module_from_spec(CORE_SPEC)
sys.modules["stale_green_bootstrap"] = core
CORE_SPEC.loader.exec_module(core)

SNAPSHOT_SPEC = importlib.util.spec_from_file_location("stale_green_bootstrap_pr_snapshot", SNAPSHOT_SCRIPT)
assert SNAPSHOT_SPEC and SNAPSHOT_SPEC.loader
snapshot = importlib.util.module_from_spec(SNAPSHOT_SPEC)
SNAPSHOT_SPEC.loader.exec_module(snapshot)

SHA = "a" * 40


def pr(
    number: int,
    *,
    state: str = "open",
    branch: str | None = None,
    head: str | None = None,
    created_at: str = "2026-09-15T14:00:00Z",
    closed_at: str | None = None,
    updated_at: str | None = None,
) -> dict:
    item = {
        "number": number,
        "state": state,
        "created_at": created_at,
        "head": {
            "ref": branch or f"branch-{number}",
            "sha": head or f"head-{number}",
            "repo": {"full_name": "o/r"},
        },
    }
    if closed_at is not None:
        item["closed_at"] = closed_at
    if updated_at is not None:
        item["updated_at"] = updated_at
    return item


def closed_pr(number: int, **kwargs) -> dict:
    return pr(
        number,
        state="closed",
        closed_at=kwargs.pop("closed_at", "2026-09-15T15:00:00Z"),
        updated_at=kwargs.pop("updated_at", "2026-09-15T16:00:00Z"),
        **kwargs,
    )


def gate_run(
    run_id: int,
    pr_number: int,
    *,
    branch: str = "shared",
    head: str = "shared-head",
    created_at: str = "2026-09-15T14:10:00Z",
    updated_at: str = "2026-09-15T14:20:00Z",
    run_number: int | None = None,
    event: str = "pull_request",
) -> dict:
    return {
        "id": run_id,
        "run_number": run_number or run_id,
        "workflow_id": core.CANONICAL_WORKFLOW_ID,
        "path": core.CANONICAL_WORKFLOW_PATH,
        "event": event,
        "status": "completed",
        "conclusion": "success",
        "created_at": created_at,
        "updated_at": updated_at,
        "head_branch": branch,
        "head_sha": head,
        "head_repository": {"full_name": "o/r"},
        "referenced_workflows": [
            {
                "path": f"o/r/{snapshot._REUSABLE_WORKFLOW_PATH}@{SHA}",
                "sha": SHA,
                "ref": f"refs/pull/{pr_number}/merge",
            }
        ],
        "run_attempt": 1,
    }


class PullRequestSnapshotTests(unittest.TestCase):
    def test_fingerprint_binds_open_and_closed_authority_fields(self) -> None:
        first = pr(2, branch="b", head="h2")
        second = pr(1, branch="a", head="h1")
        fingerprint = snapshot._pr_snapshot_fingerprint([first, second], closed=False)
        self.assertEqual([row[0] for row in fingerprint], [1, 2])
        self.assertEqual(fingerprint[0][1:5], ("open", "o/r", "a", "h1"))
        self.assertEqual(fingerprint[0][5], "2026-09-15T14:00:00+00:00")

        item = closed_pr(3)
        self.assertEqual(
            snapshot._pr_snapshot_fingerprint([item], closed=True)[0],
            (
                3,
                "closed",
                "o/r",
                "branch-3",
                "head-3",
                "2026-09-15T14:00:00+00:00",
                "2026-09-15T15:00:00+00:00",
                "2026-09-15T16:00:00+00:00",
            ),
        )

    def test_fingerprint_rejects_bad_number_duplicate_state_and_lifetime(self) -> None:
        malformed_number = pr(1)
        malformed_number["number"] = True
        with self.assertRaisesRegex(RuntimeError, "malformed pull request identity"):
            snapshot._pr_snapshot_fingerprint([malformed_number], closed=False)
        with self.assertRaisesRegex(RuntimeError, "duplicate pull request identity"):
            snapshot._pr_snapshot_fingerprint([pr(1), pr(1, branch="other")], closed=False)
        with self.assertRaisesRegex(RuntimeError, "malformed open pull request state"):
            snapshot._pr_snapshot_fingerprint([closed_pr(1)], closed=False)
        with self.assertRaisesRegex(RuntimeError, "malformed closed pull request state"):
            snapshot._pr_snapshot_fingerprint([pr(1)], closed=True)

        bad_lifetime = closed_pr(1, closed_at="2026-09-15T13:00:00Z")
        with self.assertRaisesRegex(RuntimeError, "invalid lifetime"):
            snapshot._pr_snapshot_fingerprint([bad_lifetime], closed=True)
        bad_update = closed_pr(1, updated_at="2026-09-15T14:30:00Z")
        with self.assertRaisesRegex(RuntimeError, "invalid lifetime"):
            snapshot._pr_snapshot_fingerprint([bad_update], closed=True)

    def test_open_snapshot_is_stable_and_allows_duplicate_head_identity(self) -> None:
        shared_a = pr(2, branch="shared", head="h")
        shared_b = pr(3, branch="shared", head="h")
        with mock.patch.object(
            snapshot.core,
            "paged",
            side_effect=[[shared_a, shared_b], [shared_b, shared_a]],
        ) as reader:
            self.assertEqual(snapshot.open_pull_requests("o/r", "t"), [shared_a, shared_b])
        self.assertEqual(reader.call_count, 2)
        self.assertIn("state=open", reader.call_args_list[0].args[0])
        self.assertEqual(reader.call_args_list[0].kwargs["unique_id_field"], "number")

        with mock.patch.object(
            snapshot.core,
            "paged",
            side_effect=[[pr(2), pr(3)], [pr(2), pr(4)]],
        ):
            with self.assertRaisesRegex(RuntimeError, "unstable open pull request snapshot"):
                snapshot.open_pull_requests("o/r", "t")

        duplicate = [pr(2), pr(2, branch="duplicate")]
        with mock.patch.object(snapshot.core, "paged", side_effect=[duplicate, duplicate]):
            with self.assertRaisesRegex(RuntimeError, "duplicate pull request identity"):
                snapshot.open_pull_requests("o/r", "t")

    def test_closed_snapshot_requires_two_identical_unique_authority_reads(self) -> None:
        cutoff = datetime(2026, 9, 15, 14, 0, tzinfo=timezone.utc)
        stable_first = [closed_pr(2), closed_pr(3)]
        stable_second = [closed_pr(3), closed_pr(2)]
        with mock.patch.object(
            snapshot,
            "_ORIGINAL_CLOSED_PR_HISTORY",
            side_effect=[stable_first, stable_second],
        ) as reader:
            self.assertIs(snapshot.closed_pr_history("o/r", "t", "o", "branch", cutoff), stable_first)
        self.assertEqual(reader.call_count, 2)

        with mock.patch.object(
            snapshot,
            "_ORIGINAL_CLOSED_PR_HISTORY",
            side_effect=[stable_first, [closed_pr(2), closed_pr(4)]],
        ):
            with self.assertRaisesRegex(RuntimeError, "unstable bounded closed pull request snapshot"):
                snapshot.closed_pr_history("o/r", "t", "o", "branch", cutoff)

    def test_triggering_pr_number_uses_canonical_reusable_workflow_ref(self) -> None:
        run = gate_run(10, 7)
        run["referenced_workflows"].append(
            {"path": f"o/r/.github/workflows/other.yml@{SHA}", "sha": SHA, "ref": "refs/heads/main"}
        )
        self.assertEqual(snapshot._triggering_pr_number("o/r", run), 7)

        malformed_cases = [
            None,
            [],
            ["bad"],
            [{"path": 1, "sha": SHA, "ref": "refs/pull/7/merge"}],
            [{"path": f"o/r/{snapshot._REUSABLE_WORKFLOW_PATH}@{SHA}", "sha": SHA, "ref": None}],
            [{"path": f"o/r/{snapshot._REUSABLE_WORKFLOW_PATH}@bad", "sha": "bad", "ref": "refs/pull/7/merge"}],
        ]
        for refs in malformed_cases:
            candidate = gate_run(11, 7)
            candidate["referenced_workflows"] = refs
            with self.assertRaises(RuntimeError):
                snapshot._triggering_pr_number("o/r", candidate)

        wrong_path = gate_run(12, 7)
        wrong_path["referenced_workflows"][0]["path"] = f"o/r/.github/workflows/other.yml@{SHA}"
        with self.assertRaisesRegex(RuntimeError, "ambiguous reusable-workflow PR authority"):
            snapshot._triggering_pr_number("o/r", wrong_path)

        bad_ref = gate_run(13, 7)
        bad_ref["referenced_workflows"][0]["ref"] = "refs/heads/main"
        with self.assertRaisesRegex(RuntimeError, "exact pull-request merge ref"):
            snapshot._triggering_pr_number("o/r", bad_ref)

        ambiguous = gate_run(14, 7)
        ambiguous["referenced_workflows"].append(dict(ambiguous["referenced_workflows"][0]))
        with self.assertRaisesRegex(RuntimeError, "ambiguous reusable-workflow PR authority"):
            snapshot._triggering_pr_number("o/r", ambiguous)

    def test_active_representatives_keep_earliest_same_identity_incarnation_bound(self) -> None:
        newer = pr(2, branch="shared", head="h", created_at="2026-09-15T15:00:00Z")
        older = pr(1, branch="shared", head="h", created_at="2026-09-15T14:00:00Z")
        reps = snapshot._active_representatives({2: newer, 1: older})
        self.assertEqual(reps[("o/r", "shared", "h")]["number"], 1)

    def test_latest_runs_by_pr_binds_same_head_runs_to_triggering_pr(self) -> None:
        p1 = pr(1, branch="shared", head="shared-head")
        p2 = pr(2, branch="shared", head="shared-head")
        old1 = gate_run(20, 1, run_number=20)
        new1 = gate_run(22, 1, run_number=22, updated_at="2026-09-15T14:30:00Z")
        p2run = gate_run(23, 2, run_number=23, updated_at="2026-09-15T14:40:00Z")
        ignored_event = gate_run(24, 1, event="schedule")
        unknown_pr = gate_run(25, 9)
        wrong_identity = gate_run(26, 1, branch="other")
        too_old = gate_run(27, 1, created_at="2026-09-15T13:00:00Z", updated_at="2026-09-15T13:10:00Z")
        with mock.patch.object(
            snapshot.core,
            "_scoped_completed_gate_runs",
            return_value=[old1, new1, old1, p2run, ignored_event, unknown_pr, wrong_identity, too_old],
        ):
            latest = snapshot._latest_runs_by_pr("o/r", "t", {1: p1, 2: p2})
        self.assertEqual(latest[1]["id"], 22)
        self.assertEqual(latest[2]["id"], 23)
        self.assertEqual(snapshot._latest_runs_by_pr("o/r", "t", {}), {})

    def test_latest_runs_by_pr_rejects_malformed_run_authority(self) -> None:
        current = {1: pr(1, branch="shared", head="shared-head")}
        variants = []
        for field, value in [
            ("workflow_id", True),
            ("path", ".github/workflows/other.yml"),
            ("event", None),
            ("run_number", True),
            ("id", True),
            ("status", "in_progress"),
            ("conclusion", None),
            ("conclusion", "unknown"),
        ]:
            candidate = gate_run(30 + len(variants), 1)
            candidate[field] = value
            variants.append(candidate)
        variants.append(gate_run(50, 1, updated_at="2026-09-15T14:00:00Z"))
        for candidate in variants:
            with mock.patch.object(snapshot.core, "_scoped_completed_gate_runs", return_value=[candidate]):
                with self.assertRaises(RuntimeError):
                    snapshot._latest_runs_by_pr("o/r", "t", current)

    def test_revalidate_stale_prs_keeps_only_same_open_authority(self) -> None:
        same = pr(1, branch="a", head="h1")
        changed = pr(2, branch="b", head="h2")
        missing = pr(3, branch="c", head="h3")
        fresh_changed = pr(2, branch="b", head="new")
        self.assertEqual(
            snapshot._revalidate_stale_prs([same, changed, missing], [same, fresh_changed]),
            [same],
        )

    def test_poll_handles_shared_head_per_pr_and_revalidates_open_authority(self) -> None:
        p1 = pr(1, branch="shared", head="shared-head")
        p2 = pr(2, branch="shared", head="shared-head")
        target = gate_run(60, 1)
        with (
            mock.patch.object(snapshot, "open_pull_requests", side_effect=[[p1, p2], [p1, p2]]) as open_reader,
            mock.patch.object(
                snapshot.core,
                "latest_required_check",
                return_value={"status": "completed", "conclusion": "success"},
            ) as check_reader,
            mock.patch.object(snapshot.core, "unresolved_review_threads", side_effect=[True, False]),
            mock.patch.object(snapshot, "_latest_runs_by_pr", return_value={1: target}) as run_reader,
            mock.patch.object(snapshot.core, "required_merge_gate_conclusion", return_value="success") as job_reader,
            mock.patch.object(snapshot.core, "rerun_workflow") as rerun,
        ):
            self.assertEqual(snapshot.poll("o/r", "t"), [60])
        self.assertEqual(open_reader.call_count, 2)
        check_reader.assert_called_once_with("o/r", "shared-head", "t")
        self.assertEqual(run_reader.call_args.args[2], {1: p1})
        job_reader.assert_called_once_with("o/r", target, "t")
        rerun.assert_called_once_with("o/r", 60, "t")

    def test_poll_skips_non_stale_or_disappeared_pr_and_rejects_missing_target(self) -> None:
        p1 = pr(1, branch="shared", head="shared-head")
        non_stale_checks = [
            None,
            {"status": "in_progress", "conclusion": None},
            {"status": "completed", "conclusion": "failure"},
        ]
        for check in non_stale_checks:
            with (
                mock.patch.object(snapshot, "open_pull_requests", return_value=[p1]),
                mock.patch.object(snapshot.core, "latest_required_check", return_value=check),
                mock.patch.object(snapshot.core, "unresolved_review_threads") as threads,
            ):
                self.assertEqual(snapshot.poll("o/r", "t"), [])
                threads.assert_not_called()

        with (
            mock.patch.object(snapshot, "open_pull_requests", side_effect=[[p1], []]),
            mock.patch.object(
                snapshot.core,
                "latest_required_check",
                return_value={"status": "completed", "conclusion": "success"},
            ),
            mock.patch.object(snapshot.core, "unresolved_review_threads", return_value=True),
        ):
            self.assertEqual(snapshot.poll("o/r", "t"), [])

        with (
            mock.patch.object(snapshot, "open_pull_requests", side_effect=[[p1], [p1]]),
            mock.patch.object(
                snapshot.core,
                "latest_required_check",
                return_value={"status": "completed", "conclusion": "success"},
            ),
            mock.patch.object(snapshot.core, "unresolved_review_threads", return_value=True),
            mock.patch.object(snapshot, "_latest_runs_by_pr", return_value={}),
        ):
            with self.assertRaisesRegex(RuntimeError, "no unambiguous run"):
                snapshot.poll("o/r", "t")

    def test_validate_contract_success_and_failures(self) -> None:
        p1 = pr(1, branch="shared", head="shared-head")
        target = gate_run(70, 1)
        with mock.patch.object(snapshot, "open_pull_requests", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "expected exactly one"):
                snapshot.validate_github_contract("o/r", 1, "t")

        with (
            mock.patch.object(snapshot, "open_pull_requests", return_value=[p1]),
            mock.patch.object(snapshot, "_latest_runs_by_pr", return_value={}),
        ):
            with self.assertRaisesRegex(RuntimeError, "no unambiguous canonical"):
                snapshot.validate_github_contract("o/r", 1, "t")

        with (
            mock.patch.object(snapshot, "open_pull_requests", return_value=[p1]),
            mock.patch.object(snapshot, "_latest_runs_by_pr", return_value={1: target}),
            mock.patch.object(snapshot.core, "latest_required_check", return_value=None),
        ):
            with self.assertRaisesRegex(RuntimeError, "no latest"):
                snapshot.validate_github_contract("o/r", 1, "t")

        with (
            mock.patch.object(snapshot, "open_pull_requests", return_value=[p1]),
            mock.patch.object(snapshot, "_latest_runs_by_pr", return_value={1: target}),
            mock.patch.object(snapshot.core, "latest_required_check", return_value={"status": "completed", "conclusion": "failure"}),
            mock.patch.object(snapshot.core, "required_merge_gate_conclusion", return_value="failure") as required,
            mock.patch.object(snapshot.core, "unresolved_review_threads", return_value=True),
        ):
            self.assertEqual(snapshot.validate_github_contract("o/r", 1, "t"), (1, 1, True))
        required.assert_called_once_with("o/r", target, "t")

    def test_install_and_main_replace_runtime_authority(self) -> None:
        originals = (
            snapshot.core.open_pull_requests,
            snapshot.core._closed_pr_history,
            snapshot.core.poll,
            snapshot.core.validate_github_contract,
        )
        self.addCleanup(setattr, snapshot.core, "open_pull_requests", originals[0])
        self.addCleanup(setattr, snapshot.core, "_closed_pr_history", originals[1])
        self.addCleanup(setattr, snapshot.core, "poll", originals[2])
        self.addCleanup(setattr, snapshot.core, "validate_github_contract", originals[3])
        with mock.patch.object(snapshot.core, "main", return_value=7) as core_main:
            self.assertEqual(snapshot.main(), 7)
        self.assertIs(snapshot.core.open_pull_requests, snapshot.open_pull_requests)
        self.assertIs(snapshot.core._closed_pr_history, snapshot.closed_pr_history)
        self.assertIs(snapshot.core.poll, snapshot.poll)
        self.assertIs(snapshot.core.validate_github_contract, snapshot.validate_github_contract)
        core_main.assert_called_once_with()

    def test_script_entrypoint_delegates_to_core_main(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(SystemExit) as ctx:
                runpy.run_path(str(SNAPSHOT_SCRIPT), run_name="__main__")
        self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
