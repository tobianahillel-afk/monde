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


class PullRequestSnapshotTests(unittest.TestCase):
    def test_fingerprint_binds_open_authority_fields_and_sorts_by_number(self) -> None:
        first = pr(2, branch="b", head="h2")
        second = pr(1, branch="a", head="h1")
        fingerprint = snapshot._pr_snapshot_fingerprint([first, second], closed=False)
        self.assertEqual([row[0] for row in fingerprint], [1, 2])
        self.assertEqual(fingerprint[0][1:5], ("open", "o/r", "a", "h1"))
        self.assertEqual(fingerprint[0][5], "2026-09-15T14:00:00+00:00")

    def test_fingerprint_binds_closed_lifetime_fields(self) -> None:
        item = closed_pr(3)
        fingerprint = snapshot._pr_snapshot_fingerprint([item], closed=True)
        self.assertEqual(
            fingerprint[0],
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

        bad_lifetime = closed_pr(
            1,
            closed_at="2026-09-15T13:00:00Z",
            updated_at="2026-09-15T16:00:00Z",
        )
        with self.assertRaisesRegex(RuntimeError, "invalid lifetime"):
            snapshot._pr_snapshot_fingerprint([bad_lifetime], closed=True)

        bad_update = closed_pr(
            1,
            closed_at="2026-09-15T15:00:00Z",
            updated_at="2026-09-15T14:30:00Z",
        )
        with self.assertRaisesRegex(RuntimeError, "invalid lifetime"):
            snapshot._pr_snapshot_fingerprint([bad_update], closed=True)

    def test_open_snapshot_requires_two_identical_unique_authority_reads(self) -> None:
        stable_first = [pr(2), pr(3)]
        stable_second = [pr(3), pr(2)]
        with mock.patch.object(
            snapshot,
            "_ORIGINAL_OPEN_PULL_REQUESTS",
            side_effect=[stable_first, stable_second],
        ) as reader:
            self.assertIs(snapshot.open_pull_requests("o/r", "t"), stable_first)
        self.assertEqual(reader.call_count, 2)

        drifted = [pr(2), pr(4)]
        with mock.patch.object(
            snapshot,
            "_ORIGINAL_OPEN_PULL_REQUESTS",
            side_effect=[stable_first, drifted],
        ):
            with self.assertRaisesRegex(RuntimeError, "unstable open pull request snapshot"):
                snapshot.open_pull_requests("o/r", "t")

        duplicate = [pr(2), pr(2, branch="duplicate")]
        with mock.patch.object(
            snapshot,
            "_ORIGINAL_OPEN_PULL_REQUESTS",
            side_effect=[duplicate, duplicate],
        ):
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
        self.assertEqual(reader.call_args_list[0].args, ("o/r", "t", "o", "branch", cutoff))
        self.assertEqual(reader.call_count, 2)

        drifted = [closed_pr(2), closed_pr(4)]
        with mock.patch.object(
            snapshot,
            "_ORIGINAL_CLOSED_PR_HISTORY",
            side_effect=[stable_first, drifted],
        ):
            with self.assertRaisesRegex(RuntimeError, "unstable bounded closed pull request snapshot"):
                snapshot.closed_pr_history("o/r", "t", "o", "branch", cutoff)

        duplicate = [closed_pr(2), closed_pr(2, branch="duplicate")]
        with mock.patch.object(
            snapshot,
            "_ORIGINAL_CLOSED_PR_HISTORY",
            side_effect=[duplicate, duplicate],
        ):
            with self.assertRaisesRegex(RuntimeError, "duplicate pull request identity"):
                snapshot.closed_pr_history("o/r", "t", "o", "branch", cutoff)

    def test_install_and_main_replace_only_pr_authority_readers(self) -> None:
        original_open = snapshot.core.open_pull_requests
        original_closed = snapshot.core._closed_pr_history
        self.addCleanup(setattr, snapshot.core, "open_pull_requests", original_open)
        self.addCleanup(setattr, snapshot.core, "_closed_pr_history", original_closed)
        with mock.patch.object(snapshot.core, "main", return_value=7) as core_main:
            self.assertEqual(snapshot.main(), 7)
        self.assertIs(snapshot.core.open_pull_requests, snapshot.open_pull_requests)
        self.assertIs(snapshot.core._closed_pr_history, snapshot.closed_pr_history)
        core_main.assert_called_once_with()

    def test_script_entrypoint_delegates_to_core_main(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(SystemExit) as ctx:
                runpy.run_path(str(SNAPSHOT_SCRIPT), run_name="__main__")
        self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
