from __future__ import annotations

from dataclasses import dataclass
import os
import urllib.parse
from typing import Any

import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0049 as pending
import stale_green_bootstrap_authority_review0051_recovery as recovery
import stale_green_bootstrap_authority_review0060 as attempt
import stale_green_bootstrap_authority_review0061 as chronology
import stale_green_bootstrap_authority_review0063 as containment
import stale_green_bootstrap_authority_review0064 as temporal
import stale_green_bootstrap_authority_review0068 as previous


RECOVERY_ACTION = recovery.RECOVERY_ACTION


@dataclass(frozen=True)
class BulkAuthorityWitness:
    candidate_check: tuple[Any, ...]
    frontier_runs: tuple[tuple[Any, ...], ...]
    gate_checks: tuple[tuple[Any, ...], ...]
    candidate_job: tuple[Any, ...]


def _suite_id_from_check(check: dict[str, Any]) -> int:
    suite = check.get("check_suite")
    suite_id = suite.get("id") if isinstance(suite, dict) else None
    if not core._positive_int(suite_id):
        raise RuntimeError("GitHub returned MONDE Gate check without exact check-suite identity")
    return int(suite_id)


def _suite_id_from_run(run: dict[str, Any]) -> int:
    suite_id = run.get("check_suite_id")
    if not core._positive_int(suite_id):
        raise RuntimeError("GitHub returned canonical MONDE Gate run without exact check-suite identity")
    return int(suite_id)


def _bulk_check_snapshot(check: dict[str, Any], head: str) -> tuple[Any, ...]:
    run_id, job_id = base._validate_gate_check(check, head)
    status = check.get("status")
    conclusion = check.get("conclusion")
    if status not in core.CHECK_RUN_STATUSES:
        raise RuntimeError("GitHub returned malformed bulk MONDE Gate check status")
    if status == "completed":
        if not isinstance(conclusion, str) or conclusion not in core.TERMINAL_CONCLUSIONS:
            raise RuntimeError("GitHub returned malformed completed bulk MONDE Gate check")
    elif conclusion is not None:
        raise RuntimeError("GitHub returned incomplete bulk MONDE Gate check with conclusion")
    started, completed = temporal._required_check_temporal_snapshot(check)
    return (
        int(check["id"]),
        _suite_id_from_check(check),
        run_id,
        job_id,
        status,
        conclusion,
        started.isoformat(),
        completed.isoformat() if completed is not None else None,
        check.get("details_url"),
    )


def _bulk_run_snapshot(run: dict[str, Any], head: str) -> tuple[Any, ...]:
    return (*previous._run_snapshot(run, head), _suite_id_from_run(run))


def _bulk_required_checks(
    repo: str,
    head: str,
    token: str,
) -> tuple[list[dict[str, Any]], tuple[tuple[Any, ...], ...]]:
    query = urllib.parse.urlencode(
        {
            "check_name": core.REQUIRED_GATE_JOB_NAME,
            "filter": "latest",
            "app_id": core.GITHUB_ACTIONS_APP_ID,
            "per_page": 100,
        }
    )
    checks = core.paged(
        f"https://api.github.com/repos/{repo}/commits/{head}/check-runs?{query}",
        token,
        "check_runs",
        require_total_count=True,
        unique_id_field="id",
        verify_previous_page=True,
    )
    snapshots = [_bulk_check_snapshot(check, head) for check in checks]
    suite_ids = [item[1] for item in snapshots]
    if len(suite_ids) != len(set(suite_ids)):
        raise RuntimeError(
            "GitHub returned multiple latest MONDE Gate checks for one check suite"
        )
    ordered = tuple(sorted(snapshots, key=lambda item: (item[6], item[0])))
    return checks, ordered


def _bulk_frontier_runs(
    repo: str,
    head: str,
    token: str,
    frontier: Any,
) -> tuple[list[dict[str, Any]], tuple[tuple[Any, ...], ...]]:
    rows = attempt._attempt_frontier_runs(repo, head, token, frontier)
    snapshots = [_bulk_run_snapshot(run, head) for run in rows]
    run_ids = [item[0] for item in snapshots]
    suite_ids = [item[-1] for item in snapshots]
    if len(run_ids) != len(set(run_ids)):
        raise RuntimeError("canonical MONDE Gate frontier contains duplicate run identity")
    if len(suite_ids) != len(set(suite_ids)):
        raise RuntimeError("canonical MONDE Gate frontier contains duplicate check-suite identity")
    return rows, tuple(sorted(snapshots, key=lambda item: item[0]))


def _candidate_from_checks(
    checks: list[dict[str, Any]],
    head: str,
) -> dict[str, Any] | None:
    if not checks:
        return None
    validated = [(_bulk_check_snapshot(check, head), check) for check in checks]
    _snapshot, candidate = max(
        validated,
        key=lambda item: (
            core._timestamp(
                item[0][6],
                "required MONDE Merge Gate started_at",
            ),
            int(item[0][0]),
        ),
    )
    return candidate


def _check_for_suite(
    checks_by_suite: dict[int, dict[str, Any]],
    suite_id: int,
) -> dict[str, Any]:
    check = checks_by_suite.get(suite_id)
    if check is None:
        raise RuntimeError(
            "overlapping canonical MONDE Gate run lacks one latest Gate Check Run"
        )
    return check


def _validate_bulk_run_check_binding(
    run: dict[str, Any],
    check: dict[str, Any],
    head: str,
) -> tuple[Any, ...]:
    run_snapshot = _bulk_run_snapshot(run, head)
    check_snapshot = _bulk_check_snapshot(check, head)
    run_id = int(run_snapshot[0])
    suite_id = int(run_snapshot[-1])
    if int(check_snapshot[1]) != suite_id or int(check_snapshot[2]) != run_id:
        raise RuntimeError("bulk MONDE Gate check disagrees with canonical run/check-suite identity")

    run_started = core._timestamp(
        run_snapshot[4],
        "canonical MONDE Gate run_started_at",
    )
    run_updated = core._timestamp(
        run_snapshot[5],
        "canonical MONDE Gate updated_at",
    )
    check_started = core._timestamp(
        check_snapshot[6],
        "bulk MONDE Gate check started_at",
    )
    if check_started < run_started or check_started > run_updated:
        raise RuntimeError(
            "bulk MONDE Gate check start falls outside current workflow run lifetime"
        )
    completed_raw = check_snapshot[7]
    if completed_raw is not None:
        completed = core._timestamp(
            completed_raw,
            "bulk MONDE Gate check completed_at",
        )
        if completed > run_updated:
            raise RuntimeError(
                "bulk MONDE Gate check completion exceeds current workflow run lifetime"
            )
    return check_snapshot


def _direct_candidate_job_snapshot(
    repo: str,
    head: str,
    token: str,
    candidate: dict[str, Any],
    frontier_run: dict[str, Any],
) -> tuple[Any, ...]:
    run_id, job_id = base._validate_gate_check(candidate, head)
    direct_run = core.request_data(
        f"https://api.github.com/repos/{repo}/actions/runs/{run_id}",
        token,
    )
    if not isinstance(direct_run, dict):
        raise RuntimeError("GitHub returned malformed direct candidate canonical MONDE Gate run")
    if _bulk_run_snapshot(direct_run, head) != _bulk_run_snapshot(frontier_run, head):
        raise RuntimeError("candidate canonical MONDE Gate run changed during bulk authority proof")

    direct_job = core.request_data(
        f"https://api.github.com/repos/{repo}/actions/jobs/{job_id}",
        token,
    )
    if not isinstance(direct_job, dict):
        raise RuntimeError("GitHub returned malformed direct candidate protected MONDE Gate job")
    run_attempt = base._validate_canonical_run(
        direct_run,
        run_id,
        head,
        require_completed=False,
    )
    base._validate_protected_job(
        direct_job,
        job_id=job_id,
        run_id=run_id,
        run_attempt=run_attempt,
        head=head,
    )
    containment._validate_full_run_job_containment(direct_run, direct_job)
    job_snapshot = previous._job_snapshot(direct_job, direct_run, head)

    candidate_snapshot = _bulk_check_snapshot(candidate, head)
    job_started = core._timestamp(
        direct_job.get("started_at"),
        "candidate protected MONDE Gate job started_at",
    )
    job_completed = core._timestamp(
        direct_job.get("completed_at"),
        "candidate protected MONDE Gate job completed_at",
    )
    if job_started.isoformat() != candidate_snapshot[6]:
        raise RuntimeError("candidate bulk Check Run disagrees with protected job start timing")
    if job_completed.isoformat() != candidate_snapshot[7]:
        raise RuntimeError("candidate bulk Check Run disagrees with protected job completion timing")
    if direct_job.get("conclusion") != candidate.get("conclusion"):
        raise RuntimeError("candidate bulk Check Run disagrees with protected job conclusion")
    return job_snapshot


def _prove_bulk_witness(
    repo: str,
    head: str,
    token: str,
) -> tuple[dict[str, Any] | None, BulkAuthorityWitness | None]:
    checks, check_snapshot = _bulk_required_checks(repo, head, token)
    candidate = _candidate_from_checks(checks, head)
    if not base._latest_check_is_merge_acceptable(candidate):
        return candidate, None
    assert candidate is not None

    frontier = attempt.previous._authority_frontier()
    rows, run_snapshot = _bulk_frontier_runs(repo, head, token, frontier)
    if not rows:
        raise RuntimeError("candidate canonical MONDE Gate run is absent from bulk Actions frontier")

    candidate_started, candidate_completed = temporal._required_check_temporal_snapshot(candidate)
    assert candidate_completed is not None
    normalized_frontier = core._utc_second(frontier)
    if candidate_completed > normalized_frontier:
        raise RuntimeError("bulk authority frontier precedes candidate check completion")

    checks_by_suite = {_suite_id_from_check(check): check for check in checks}
    runs_by_id = {int(run["id"]): run for run in rows}
    candidate_run_id, _candidate_job_id = base._validate_gate_check(candidate, head)
    candidate_run = runs_by_id.get(candidate_run_id)
    if candidate_run is None:
        raise RuntimeError("candidate Gate Check Run is not bound to the canonical Actions frontier")
    if _suite_id_from_run(candidate_run) != _suite_id_from_check(candidate):
        raise RuntimeError("candidate Gate Check Run disagrees with canonical Actions check suite")

    for run in rows:
        run_row = _bulk_run_snapshot(run, head)
        run_started = core._timestamp(
            run_row[4],
            "canonical MONDE Gate run_started_at",
        )
        run_updated = core._timestamp(
            run_row[5],
            "canonical MONDE Gate updated_at",
        )
        if run_started > normalized_frontier:
            raise RuntimeError("canonical MONDE Gate current attempt started after bulk authority frontier")
        if run_updated < candidate_started:
            continue
        if run_started > candidate_started:
            raise RuntimeError(
                "bulk required-check authority advanced to a newer canonical MONDE Gate attempt"
            )
        bound_check = _check_for_suite(checks_by_suite, int(run_row[-1]))
        bound_snapshot = _validate_bulk_run_check_binding(run, bound_check, head)
        # The candidate was selected as max(started_at, id) across this exact
        # bulk Check Run collection, so every bound check is necessarily no
        # newer than the candidate. candidate completion is already bounded by
        # the captured frontier, which also bounds every earlier check start.
        core._timestamp(
            bound_snapshot[6],
            "bulk MONDE Gate check started_at",
        )

    candidate_job = _direct_candidate_job_snapshot(
        repo,
        head,
        token,
        candidate,
        candidate_run,
    )
    return candidate, BulkAuthorityWitness(
        candidate_check=_bulk_check_snapshot(candidate, head),
        frontier_runs=run_snapshot,
        gate_checks=check_snapshot,
        candidate_job=candidate_job,
    )


def _revalidate_bulk_witness(
    repo: str,
    head: str,
    token: str,
    witness: BulkAuthorityWitness,
) -> None:
    checks, check_snapshot = _bulk_required_checks(repo, head, token)
    if check_snapshot != witness.gate_checks:
        raise RuntimeError(
            "bulk MONDE Gate Check Run snapshot changed before mutation boundary"
        )

    frontier = attempt.previous._authority_frontier()
    rows, run_snapshot = _bulk_frontier_runs(repo, head, token, frontier)
    if run_snapshot != witness.frontier_runs:
        raise RuntimeError(
            "bulk canonical MONDE Gate Actions frontier changed before mutation boundary"
        )

    candidate_id = int(witness.candidate_check[0])
    matches = [check for check in checks if check.get("id") == candidate_id]
    if len(matches) != 1:
        raise RuntimeError(
            "candidate MONDE Gate Check Run disappeared or became ambiguous before mutation boundary"
        )
    candidate = matches[0]
    candidate_run_id = int(witness.candidate_check[2])
    rows_by_id = {int(run["id"]): run for run in rows}
    candidate_run = rows_by_id.get(candidate_run_id)
    if candidate_run is None:
        raise RuntimeError(
            "candidate canonical MONDE Gate run disappeared before mutation boundary"
        )
    current_job = _direct_candidate_job_snapshot(
        repo,
        head,
        token,
        candidate,
        candidate_run,
    )
    if current_job != witness.candidate_job:
        raise RuntimeError(
            "candidate protected MONDE Gate job changed before mutation boundary"
        )


def install() -> None:
    previous.install()
    previous._prove_with_witness = _prove_bulk_witness
    previous._revalidate_witness = _revalidate_bulk_witness


def main() -> int:
    install()
    action = os.getenv("BOOTSTRAP_RECOVERY_ACTION", "").strip()
    if action:
        if action != RECOVERY_ACTION:
            raise RuntimeError(f"unsupported bootstrap recovery action: {action}")
        repo = os.getenv("GITHUB_REPOSITORY", "")
        token = os.getenv("GITHUB_TOKEN", "")
        if not repo or not token:
            raise RuntimeError("GITHUB_REPOSITORY and GITHUB_TOKEN are required")
        return recovery._inspect_confirmed_unposted(repo, token)
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
