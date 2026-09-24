from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any

import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0049 as pending
import stale_green_bootstrap_authority_review0051_recovery as recovery
import stale_green_bootstrap_authority_review0060 as attempt
import stale_green_bootstrap_authority_review0061 as chronology
import stale_green_bootstrap_authority_review0062 as terminal
import stale_green_bootstrap_authority_review0064 as temporal
import stale_green_bootstrap_authority_review0067 as previous


RECOVERY_ACTION = recovery.RECOVERY_ACTION


@dataclass(frozen=True)
class AuthorityWitness:
    candidate_check: tuple[Any, ...]
    frontier_runs: tuple[tuple[Any, ...], ...]
    overlap_jobs: tuple[tuple[int, tuple[Any, ...]], ...]


def _check_snapshot(check: dict[str, Any], head: str) -> tuple[Any, ...]:
    base._validate_gate_check(check, head)
    started, completed = temporal._required_check_temporal_snapshot(check)
    return (
        int(check["id"]),
        check.get("status"),
        check.get("conclusion"),
        started.isoformat(),
        completed.isoformat() if completed is not None else None,
        check.get("details_url"),
    )


def _run_snapshot(run: dict[str, Any], head: str) -> tuple[Any, ...]:
    run_id = run.get("id")
    if not core._positive_int(run_id):
        raise RuntimeError("GitHub returned malformed canonical MONDE Gate frontier run id")
    attempt_number = base._validate_canonical_run(
        run, int(run_id), head, require_completed=False
    )
    created = core._run_created_at(run)
    started = attempt._run_attempt_started_at(run)
    updated = core._updated_at(run.get("updated_at"))
    if updated < started:
        raise RuntimeError(
            "GitHub returned canonical MONDE Gate run updated before current attempt start"
        )
    return (
        int(run_id),
        run.get("run_number"),
        attempt_number,
        created.isoformat(),
        started.isoformat(),
        updated.isoformat(),
        run.get("status"),
        run.get("conclusion"),
        core._run_head_identity(run),
    )


def _frontier_snapshot(
    rows: list[dict[str, Any]],
    head: str,
) -> tuple[tuple[Any, ...], ...]:
    snapshots = [_run_snapshot(run, head) for run in rows]
    ids = [row[0] for row in snapshots]
    if len(ids) != len(set(ids)):
        raise RuntimeError("canonical MONDE Gate frontier contains duplicate run identity")
    return tuple(sorted(snapshots, key=lambda row: row[0]))


def _job_snapshot(
    job: dict[str, Any],
    run: dict[str, Any],
    head: str,
) -> tuple[Any, ...]:
    run_id = run.get("id")
    if not core._positive_int(run_id):
        raise RuntimeError("GitHub returned malformed canonical MONDE Gate run id")
    job_id = job.get("id")
    if not core._positive_int(job_id):
        raise RuntimeError("GitHub returned malformed protected MONDE Gate job id")
    attempt_number = base._validate_canonical_run(
        run, int(run_id), head, require_completed=False
    )
    base._validate_protected_job(
        job,
        job_id=int(job_id),
        run_id=int(run_id),
        run_attempt=attempt_number,
        head=head,
    )
    chronology._validate_attempt_job_chronology(run, job)
    started = core._timestamp(
        job.get("started_at"),
        "protected MONDE Gate job started_at",
    )
    completed = core._timestamp(
        job.get("completed_at"),
        "protected MONDE Gate job completed_at",
    )
    return (
        int(job_id),
        int(run_id),
        attempt_number,
        job.get("status"),
        job.get("conclusion"),
        started.isoformat(),
        completed.isoformat(),
        job.get("head_sha"),
        job.get("name"),
    )


def _bounded_overlap_prove(
    repo: str,
    head: str,
    token: str,
    candidate: dict[str, Any],
    frontier: Any,
) -> None:
    run_id, job_id = base._validate_gate_check(candidate, head)
    candidate_started = core._timestamp(
        candidate.get("started_at"),
        "required MONDE Merge Gate started_at",
    )
    normalized_frontier = core._utc_second(frontier)
    if candidate_started > normalized_frontier:
        raise RuntimeError("required-check authority frontier precedes candidate check start")

    direct_run = core.request_data(
        f"https://api.github.com/repos/{repo}/actions/runs/{run_id}",
        token,
    )
    if not isinstance(direct_run, dict):
        raise RuntimeError("GitHub returned malformed candidate canonical MONDE Gate run")
    direct_attempt = base._validate_canonical_run(
        direct_run, run_id, head, require_completed=False
    )
    direct_started = attempt._run_attempt_started_at(direct_run)
    if direct_started > normalized_frontier:
        raise RuntimeError("candidate current workflow attempt started after authority frontier")

    direct_job = core.request_data(
        f"https://api.github.com/repos/{repo}/actions/jobs/{job_id}",
        token,
    )
    if not isinstance(direct_job, dict):
        raise RuntimeError("GitHub returned malformed candidate protected MONDE Gate job")
    base._validate_protected_job(
        direct_job,
        job_id=job_id,
        run_id=run_id,
        run_attempt=direct_attempt,
        head=head,
    )
    chronology._validate_attempt_job_chronology(direct_run, direct_job)
    direct_job_started = core._timestamp(
        direct_job.get("started_at"),
        "candidate protected MONDE Gate job started_at",
    )
    if direct_job_started != candidate_started:
        raise RuntimeError(
            "candidate required check disagrees with protected job start identity"
        )
    if direct_job.get("conclusion") != candidate.get("conclusion"):
        raise RuntimeError(
            "candidate required check disagrees with protected job conclusion"
        )

    rows = attempt._attempt_frontier_runs(repo, head, token, normalized_frontier)
    if not rows:
        raise RuntimeError("candidate canonical MONDE Gate run is absent from attempt frontier")

    authority: list[tuple[tuple[Any, int], dict[str, Any], dict[str, Any]]] = []
    matched = 0
    for run in rows:
        snapshot = _run_snapshot(run, head)
        row_id = int(snapshot[0])
        run_started = core._timestamp(
            snapshot[4],
            "canonical MONDE Gate run_started_at",
        )
        run_updated = core._timestamp(
            snapshot[5],
            "canonical MONDE Gate updated_at",
        )
        if run_started > normalized_frontier:
            raise RuntimeError(
                "canonical MONDE Gate current attempt started after authority frontier"
            )

        if row_id == run_id:
            matched += 1
            if (
                run.get("run_number") != direct_run.get("run_number")
                or run.get("run_attempt") != direct_attempt
                or core._run_created_at(run) != core._run_created_at(direct_run)
                or run_started != direct_started
            ):
                raise RuntimeError(
                    "candidate canonical MONDE Gate attempt changed during authority proof"
                )

        # REVIEW-0061/0063 prove that a valid protected job must start inside
        # its current run lifetime. A run whose lifetime ended before the
        # candidate started therefore cannot contain an authority-bearing job
        # that outranks the candidate.
        if run_updated < candidate_started:
            continue

        # Conversely, if the current attempt itself started after the
        # candidate, any valid protected job is necessarily newer. Fail closed
        # without paying for a per-run job lookup.
        if run_started > candidate_started:
            raise RuntimeError(
                "required-check authority advanced to a newer canonical MONDE Gate attempt"
            )

        job = chronology._chronology_protected_gate_job(repo, token, run, head)
        job_started = core._timestamp(
            job.get("started_at"),
            "protected MONDE Gate job started_at",
        )
        if job_started > normalized_frontier:
            raise RuntimeError(
                "canonical MONDE Gate protected job started after authority frontier"
            )
        authority.append((attempt._attempt_authority_key(job), run, job))

    if matched != 1:
        raise RuntimeError(
            "candidate canonical MONDE Gate run is absent or ambiguous in attempt frontier"
        )
    if not authority:
        raise RuntimeError(
            "candidate canonical MONDE Gate protected job is absent from overlapping authority frontier"
        )

    _latest_key, latest_run, latest_job = max(authority, key=lambda item: item[0])
    if int(latest_run["id"]) != run_id or int(latest_job["id"]) != job_id:
        raise RuntimeError(
            "required-check authority advanced to a newer protected MONDE Gate job before the captured frontier"
        )


def _prove_with_witness(
    repo: str,
    head: str,
    token: str,
) -> tuple[dict[str, Any] | None, AuthorityWitness | None]:
    captured_rows: list[dict[str, Any]] | None = None
    captured_jobs: dict[int, tuple[dict[str, Any], dict[str, Any]]] = {}

    original_frontier = attempt._attempt_frontier_runs
    original_job = chronology._chronology_protected_gate_job

    def capture_frontier(
        capture_repo: str,
        capture_head: str,
        capture_token: str,
        frontier: Any,
    ) -> list[dict[str, Any]]:
        nonlocal captured_rows
        rows = original_frontier(capture_repo, capture_head, capture_token, frontier)
        captured_rows = [dict(row) for row in rows]
        return rows

    def capture_job(
        capture_repo: str,
        capture_token: str,
        run: dict[str, Any],
        capture_head: str,
    ) -> dict[str, Any]:
        job = original_job(capture_repo, capture_token, run, capture_head)
        run_id = run.get("id")
        if core._positive_int(run_id):
            captured_jobs[int(run_id)] = (dict(run), dict(job))
        return job

    attempt._attempt_frontier_runs = capture_frontier
    chronology._chronology_protected_gate_job = capture_job
    try:
        candidate = core.latest_required_check(repo, head, token)
    finally:
        chronology._chronology_protected_gate_job = original_job
        attempt._attempt_frontier_runs = original_frontier

    if not base._latest_check_is_merge_acceptable(candidate):
        return candidate, None
    assert candidate is not None
    if captured_rows is None:
        raise RuntimeError(
            "merge-acceptable Gate authority proof did not expose its Actions frontier"
        )

    overlap = tuple(
        sorted(
            (
                run_id,
                _job_snapshot(job, run, head),
            )
            for run_id, (run, job) in captured_jobs.items()
        )
    )
    return candidate, AuthorityWitness(
        candidate_check=_check_snapshot(candidate, head),
        frontier_runs=_frontier_snapshot(captured_rows, head),
        overlap_jobs=overlap,
    )


def _revalidate_witness(
    repo: str,
    head: str,
    token: str,
    witness: AuthorityWitness,
) -> None:
    frontier = attempt.previous._authority_frontier()
    rows = attempt._attempt_frontier_runs(repo, head, token, frontier)
    current_frontier = _frontier_snapshot(rows, head)
    if current_frontier != witness.frontier_runs:
        raise RuntimeError(
            "canonical MONDE Gate authority frontier changed before mutation boundary"
        )

    rows_by_id = {int(run["id"]): run for run in rows}
    for run_id, expected_job in witness.overlap_jobs:
        run = rows_by_id.get(run_id)
        if run is None:
            raise RuntimeError(
                "overlapping canonical MONDE Gate run disappeared before mutation boundary"
            )
        job = chronology._chronology_protected_gate_job(repo, token, run, head)
        if _job_snapshot(job, run, head) != expected_job:
            raise RuntimeError(
                "overlapping protected MONDE Gate job changed before mutation boundary"
            )

    check_id = int(witness.candidate_check[0])
    current_check = core.request_data(
        f"https://api.github.com/repos/{repo}/check-runs/{check_id}",
        token,
    )
    if not isinstance(current_check, dict):
        raise RuntimeError(
            "GitHub returned malformed direct required MONDE Merge Gate check"
        )
    if _check_snapshot(current_check, head) != witness.candidate_check:
        raise RuntimeError(
            "required MONDE Merge Gate check changed before mutation boundary"
        )


def _two_stage_process(
    repo: str,
    token: str,
    group: list[dict[str, Any]],
    rerun_slots: int,
    state: pending.SchedulerStateV4,
    scan_pr: int = 0,
    scan_page: int = 1,
    scan_anchor: str = "-",
):
    if not group:
        return [], [], None

    head = core._pr_head_identity(group[0])[2]
    errors: list[str] = []
    posted: list[int] = []

    for original in base._ordered_group_for_scan(group, scan_pr):
        number = original["number"]
        if len(posted) >= rerun_slots:
            return posted, errors, None
        if (
            base._remaining_request_budget()
            < base.MIN_TARGET_REQUEST_HEADROOM + base.STATE_WRITE_REQUEST_RESERVE
        ):
            raise base.DeferredForBudget(
                "insufficient request headroom before sibling evaluation"
            )
        if not core.unresolved_review_threads(repo, number, token):
            continue

        start_page = scan_page if number == scan_pr else 1
        if number == scan_pr and scan_anchor != "-":
            target, next_page = pending.previous._direct_target_for_pr(
                repo, token, original, start_page, scan_anchor
            )
        else:
            target, next_page = pending.previous._direct_target_for_pr(
                repo, token, original, start_page
            )
        if next_page is not None:
            return posted, errors, (number, next_page)
        if target is None:
            errors.append(
                f"open PR #{number} has unresolved threads but no canonical rerun target in complete check history"
            )
            continue

        run, _target_check = target
        fresh = base._current_pr(repo, token, original)
        if fresh is None:
            continue
        if not core.unresolved_review_threads(repo, number, token):
            continue

        run_id = int(run["id"])
        baseline_attempt = pending.previous._mutation_baseline(
            repo, token, fresh, run_id
        )
        if baseline_attempt is None:
            return posted, errors, (number, base.ScanPage(1))

        final_pr = base._current_pr(repo, token, original)
        if final_pr is None:
            return posted, errors, (number, base.ScanPage(1))
        if not core.unresolved_review_threads(repo, number, token):
            continue

        candidate, witness = _prove_with_witness(repo, head, token)
        if candidate is None:
            return posted, errors, None
        if candidate.get("status") != "completed":
            return posted, errors, (number, base.ScanPage(1))
        if not base._latest_check_is_merge_acceptable(candidate):
            return posted, errors, None
        if witness is None:
            raise RuntimeError("merge-acceptable Gate lacks reusable authority witness")

        pending_state = pending._pending_state(
            state,
            final_pr,
            run_id,
            baseline_attempt,
            int(candidate["id"]),
        )

        first_pr = pending._current_pending_pr(repo, token, pending_state)
        if first_pr is None:
            return posted, errors, (number, base.ScanPage(1))
        if not core.unresolved_review_threads(repo, number, token):
            continue
        second_pr = pending._current_pending_pr(repo, token, pending_state)
        if second_pr is None:
            return posted, errors, (number, base.ScanPage(1))

        _revalidate_witness(repo, head, token, witness)
        if base._remaining_request_budget() < pending.MUTATION_REQUEST_RESERVE:
            raise base.DeferredForBudget(
                "insufficient request headroom after reusable Gate witness revalidation"
            )

        pending._write_state(repo, token, pending_state)
        try:
            core.rerun_workflow(repo, run_id, token)
        except Exception as exc:
            raise pending.PendingMutationUncertain(
                "rerun POST outcome is ambiguous; durable pending state retained and automatic retry forbidden"
            ) from exc
        posted.append(run_id)

        try:
            invalidated = pending.previous._wait_for_terminal_invalidation(
                repo,
                head,
                token,
                run_id,
                baseline_attempt,
                int(candidate["id"]),
                final_pr,
                True,
            )
        except base.DeferredObservation as exc:
            raise pending.PendingMutationObservation(run_id) from exc

        unresolved = core.unresolved_review_threads(repo, number, token)
        cleared = pending._clear_pending(pending_state, scan_pr=number)
        pending._write_state(repo, token, cleared)
        if invalidated:
            return posted, errors, None
        if unresolved:
            return posted, errors, (number, base.ScanPage(1))

    return posted, errors, None


def _safe_two_stage_process(*args: Any, **kwargs: Any):
    original_write = pending._write_state
    pending_active = False

    def guarded_write(repo: str, token: str, state: Any) -> None:
        nonlocal pending_active
        is_pending = bool(getattr(state, "pending_pr", 0))
        if is_pending:
            try:
                original_write(repo, token, state)
            except (
                pending.PendingMutationObservation,
                pending.PendingMutationUncertain,
            ):
                raise
            except Exception as exc:
                raise pending.PendingMutationUncertain(
                    "write-ahead pending-state acknowledgement is ambiguous; "
                    "automatic rerun and same-invocation idle overwrite are forbidden"
                ) from exc
        else:
            original_write(repo, token, state)
        pending_active = is_pending

    pending._write_state = guarded_write
    try:
        return _two_stage_process(*args, **kwargs)
    except (pending.PendingMutationObservation, pending.PendingMutationUncertain):
        raise
    except RuntimeError as exc:
        if pending_active:
            raise pending.PendingMutationUncertain(
                "scheduler operation failed while durable pending mutation remained active; "
                "pending authority retained and automatic retry forbidden"
            ) from exc
        raise
    finally:
        pending._write_state = original_write


def install() -> None:
    previous.install()
    terminal._ORIGINAL_CHRONOLOGY_PROVE = _bounded_overlap_prove
    pending._process_head_group = _safe_two_stage_process


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
