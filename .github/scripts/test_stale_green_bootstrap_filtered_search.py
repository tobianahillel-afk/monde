from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import unittest
from unittest import mock

SCRIPT = Path(__file__).with_name("stale_green_bootstrap.py")
SPEC = importlib.util.spec_from_file_location("stale_green_bootstrap_filtered_search", SCRIPT)
assert SPEC and SPEC.loader
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)


def dt(second: int, *, microsecond: int = 0) -> datetime:
    return datetime(2026, 9, 15, 16, 0, second, microsecond=microsecond, tzinfo=timezone.utc)


def run(run_id: int, *, conclusion: str = "success") -> dict:
    return {
        "id": run_id,
        "run_number": run_id,
        "run_attempt": 1,
        "workflow_id": bootstrap.CANONICAL_WORKFLOW_ID,
        "path": bootstrap.CANONICAL_WORKFLOW_PATH,
        "event": "pull_request",
        "head_sha": "h",
        "head_branch": "feature",
        "head_repository": {"full_name": "o/r"},
        "status": "completed",
        "conclusion": conclusion,
        "created_at": f"2026-09-15T16:00:{run_id:02d}Z",
        "updated_at": f"2026-09-15T16:00:{run_id:02d}Z",
    }


class FilteredWorkflowSearchTests(unittest.TestCase):
    def test_paged_rejects_filtered_search_at_server_ceiling(self) -> None:
        payload = {"total_count": bootstrap.FILTERED_WORKFLOW_RUN_SEARCH_LIMIT, "workflow_runs": []}
        with mock.patch.object(bootstrap, "request_data", return_value=payload):
            with self.assertRaisesRegex(bootstrap.FilteredSearchLimitExceeded, "reaches supported search limit"):
                bootstrap.paged(
                    "https://example.invalid/runs",
                    "t",
                    "workflow_runs",
                    require_total_count=True,
                    max_total_count=bootstrap.FILTERED_WORKFLOW_RUN_SEARCH_LIMIT,
                )

        payload = {"total_count": 1, "workflow_runs": [{"id": 1}]}
        with mock.patch.object(bootstrap, "request_data", return_value=payload):
            self.assertEqual(
                bootstrap.paged(
                    "https://example.invalid/runs",
                    "t",
                    "workflow_runs",
                    require_total_count=True,
                    max_total_count=bootstrap.FILTERED_WORKFLOW_RUN_SEARCH_LIMIT,
                ),
                [{"id": 1}],
            )

    def test_search_time_normalizes_to_utc_whole_seconds(self) -> None:
        source = datetime(2026, 9, 15, 18, 0, 3, 999999, tzinfo=timezone(timedelta(hours=2)))
        self.assertEqual(bootstrap._utc_second(source), dt(3))
        self.assertEqual(bootstrap._github_search_time(source), "2026-09-15T16:00:03Z")

    def test_snapshot_fingerprint_is_order_independent_and_unique(self) -> None:
        first = bootstrap._run_snapshot_fingerprint([run(2), run(1)])
        second = bootstrap._run_snapshot_fingerprint([run(1), run(2)])
        self.assertEqual(first, second)

        for bad_id in (True, 0, "1", None):
            with self.subTest(bad_id=bad_id):
                bad = run(1)
                bad["id"] = bad_id
                with self.assertRaisesRegex(RuntimeError, "malformed .* run id"):
                    bootstrap._run_snapshot_fingerprint([bad])

        with self.assertRaisesRegex(RuntimeError, "duplicate .* run id"):
            bootstrap._run_snapshot_fingerprint([run(1), run(1)])

        bad_value = run(1)
        bad_value["unsupported"] = object()
        with self.assertRaisesRegex(RuntimeError, "non-canonicalizable"):
            bootstrap._run_snapshot_fingerprint([bad_value])

    def test_read_window_uses_closed_created_range_and_search_limit(self) -> None:
        with mock.patch.object(bootstrap, "paged", return_value=[]) as paged:
            self.assertEqual(bootstrap._read_completed_gate_window("o/r", "t", "h", dt(1), dt(9)), [])
        url = paged.call_args.args[0]
        self.assertIn(f"actions/workflows/{bootstrap.CANONICAL_WORKFLOW_ID}/runs?", url)
        self.assertIn("status=completed", url)
        self.assertIn("head_sha=h", url)
        self.assertIn("created=2026-09-15T16%3A00%3A01Z..2026-09-15T16%3A00%3A09Z", url)
        self.assertEqual(paged.call_args.args[2], "workflow_runs")
        self.assertTrue(paged.call_args.kwargs["require_total_count"])
        self.assertEqual(
            paged.call_args.kwargs["max_total_count"],
            bootstrap.FILTERED_WORKFLOW_RUN_SEARCH_LIMIT,
        )

    def test_bounded_window_requires_two_identical_snapshots(self) -> None:
        rows = [run(1), run(2)]
        with mock.patch.object(bootstrap, "_read_completed_gate_window", side_effect=[rows, list(rows)]) as read:
            self.assertEqual(bootstrap._bounded_completed_gate_runs("o/r", "t", "h", dt(0), dt(9)), rows)
        self.assertEqual(read.call_count, 2)

        changed = [run(1), run(2, conclusion="failure")]
        with mock.patch.object(bootstrap, "_read_completed_gate_window", side_effect=[rows, changed]):
            with self.assertRaisesRegex(RuntimeError, "unstable .* filtered snapshot"):
                bootstrap._bounded_completed_gate_runs("o/r", "t", "h", dt(0), dt(9))

    def test_bounded_window_partitions_non_overlapping_seconds_on_first_read_limit(self) -> None:
        left = [run(1)]
        right = [run(2)]
        calls: list[tuple[datetime, datetime]] = []

        def read(_repo, _token, _head, start, end):
            calls.append((start, end))
            if (start, end) == (dt(0), dt(3)):
                raise bootstrap.FilteredSearchLimitExceeded("cap")
            if (start, end) == (dt(0), dt(1)):
                return left
            if (start, end) == (dt(2), dt(3)):
                return right
            raise AssertionError((start, end))

        with mock.patch.object(bootstrap, "_read_completed_gate_window", side_effect=read):
            self.assertEqual(bootstrap._bounded_completed_gate_runs("o/r", "t", "h", dt(0), dt(3)), left + right)

        self.assertEqual(
            calls,
            [
                (dt(0), dt(3)),
                (dt(0), dt(1)),
                (dt(0), dt(1)),
                (dt(2), dt(3)),
                (dt(2), dt(3)),
            ],
        )

    def test_bounded_window_repartitions_if_second_snapshot_hits_limit(self) -> None:
        calls = 0

        def read(_repo, _token, _head, start, end):
            nonlocal calls
            calls += 1
            if (start, end) == (dt(0), dt(1)):
                if calls == 1:
                    return [run(1)]
                if calls == 2:
                    raise bootstrap.FilteredSearchLimitExceeded("cap")
            if start == end == dt(0):
                return [run(1)]
            if start == end == dt(1):
                return [run(2)]
            raise AssertionError((calls, start, end))

        with mock.patch.object(bootstrap, "_read_completed_gate_window", side_effect=read):
            self.assertEqual(
                bootstrap._bounded_completed_gate_runs("o/r", "t", "h", dt(0), dt(1)),
                [run(1), run(2)],
            )
        self.assertEqual(calls, 6)

    def test_bounded_window_fails_closed_when_one_timestamp_second_is_saturated(self) -> None:
        with mock.patch.object(
            bootstrap,
            "_read_completed_gate_window",
            side_effect=bootstrap.FilteredSearchLimitExceeded("cap"),
        ):
            with self.assertRaisesRegex(RuntimeError, "within one timestamp second"):
                bootstrap._bounded_completed_gate_runs("o/r", "t", "h", dt(0), dt(0))

    def test_bounded_window_normalizes_fractional_bounds_and_handles_empty_range(self) -> None:
        rows = [run(1)]
        with mock.patch.object(bootstrap, "_read_completed_gate_window", side_effect=[rows, rows]) as read:
            self.assertEqual(
                bootstrap._bounded_completed_gate_runs(
                    "o/r",
                    "t",
                    "h",
                    dt(0, microsecond=900000),
                    dt(1, microsecond=900000),
                ),
                rows,
            )
        self.assertEqual(read.call_args_list[0].args[3:], (dt(0), dt(1)))

        self.assertEqual(bootstrap._bounded_completed_gate_runs("o/r", "t", "h", dt(2), dt(1)), [])


if __name__ == "__main__":
    unittest.main()
