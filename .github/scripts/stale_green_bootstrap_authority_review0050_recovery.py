from __future__ import annotations

import os
from typing import Any

import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0048 as observation
import stale_green_bootstrap_authority_review0050 as previous


RECOVERY_ACTION = "confirm-unposted-pending"
RECOVERY_CONFIRMATION = "I_CONFIRMED_NO_RERUN_POST_WAS_ISSUED"


class PendingRecoveryRequired(RuntimeError):
    pass


def _exact_positive_env(name: str) -> int:
    raw = os.getenv(name, "")
    if not raw.isdigit():
        raise RuntimeError(f"{name} must be an exact positive integer")
    value = int(raw)
    if value <= 0:
        raise RuntimeError(f"{name} must be an exact positive integer")
    return value


def _validate_recovery_request(state: previous.SchedulerStateV5) -> str:
    if state.pending_pr == 0:
        raise RuntimeError("no pending mutation exists to recover")
    if os.getenv("BOOTSTRAP_RECOVERY_CONFIRMATION", "") != RECOVERY_CONFIRMATION:
        raise RuntimeError("explicit recovery confirmation is required")
    reason = os.getenv("BOOTSTRAP_RECOVERY_REASON", "").strip()
    if not reason:
        raise RuntimeError("BOOTSTRAP_RECOVERY_REASON is required for auditability")
    expected = (
        _exact_positive_env("BOOTSTRAP_RECOVERY_PENDING_PR"),
        os.getenv("BOOTSTRAP_RECOVERY_PENDING_HEAD", ""),
        _exact_positive_env("BOOTSTRAP_RECOVERY_RUN_ID"),
        _exact_positive_env("BOOTSTRAP_RECOVERY_BASELINE_ATTEMPT"),
        _exact_positive_env("BOOTSTRAP_RECOVERY_CHECK_ID"),
    )
    actual = (
        state.pending_pr,
        state.pending_head,
        state.pending_run_id,
        state.pending_baseline_attempt,
        state.pending_check_id,
    )
    if expected != actual:
        raise RuntimeError("recovery tuple does not exactly match durable pending mutation state")
    return reason


def _resume_pending(
    repo: str, token: str, state: previous.SchedulerStateV5
) -> list[int]:
    state = previous._validate_state(state)
    if state.pending_pr == 0:
        raise RuntimeError("cannot resume an idle scheduler state")
    origin = previous._pending_origin_pr(repo, token, state)

    run = core.request_data(
        f"https://api.github.com/repos/{repo}/actions/runs/{state.pending_run_id}", token
    )
    if not isinstance(run, dict):
        raise RuntimeError("GitHub returned malformed pending workflow run")
    attempt = base._validate_canonical_run(
        run,
        state.pending_run_id,
        state.pending_head,
        require_completed=False,
    )
    expected_attempt = state.pending_baseline_attempt + 1
    if attempt < state.pending_baseline_attempt:
        raise RuntimeError("pending workflow run attempt regressed below its mutation baseline")
    if attempt > expected_attempt:
        raise previous.previous.PendingMutationUncertain(
            "pending rerun advanced beyond the single expected attempt; refusing another mutation"
        )

    original_pr = origin if origin["state"] == "open" else None
    try:
        invalidated = observation._wait_for_terminal_invalidation(
            repo,
            state.pending_head,
            token,
            state.pending_run_id,
            state.pending_baseline_attempt,
            state.pending_check_id,
            original_pr,
            True,
        )
    except base.DeferredObservation as exc:
        raise PendingRecoveryRequired(
            "pending mutation is still ambiguous after bounded observation; durable state was retained. "
            "If an operator can positively confirm that no rerun POST was issued, use the trusted "
            "workflow_dispatch recovery path with the exact pending tuple; automatic replay is forbidden."
        ) from exc

    if invalidated:
        previous._write_state(repo, token, previous._clear_pending(state))
        return []

    unresolved = previous._unresolved_same_head(repo, token, state.pending_head)
    if unresolved:
        previous._write_state(
            repo,
            token,
            previous._clear_pending(state, scan_pr=unresolved[0]["number"]),
        )
        return []

    previous._write_state(repo, token, previous._clear_pending(state))
    return []


def _recover_confirmed_unposted(repo: str, token: str) -> int:
    state = previous._read_state(repo, token)
    reason = _validate_recovery_request(state)
    origin = previous._pending_origin_pr(repo, token, state)

    run = core.request_data(
        f"https://api.github.com/repos/{repo}/actions/runs/{state.pending_run_id}", token
    )
    if not isinstance(run, dict):
        raise RuntimeError("GitHub returned malformed pending workflow run during recovery")
    attempt = base._validate_canonical_run(
        run,
        state.pending_run_id,
        state.pending_head,
        require_completed=False,
    )
    if attempt != state.pending_baseline_attempt:
        raise RuntimeError(
            "recovery refused: workflow attempt changed, so the pending mutation may have been issued"
        )

    latest = core.latest_required_check(repo, state.pending_head, token)
    if (
        latest is None
        or not core._positive_int(latest.get("id"))
        or latest["id"] != state.pending_check_id
    ):
        raise RuntimeError(
            "recovery refused: effective required-check identity changed after write-ahead state"
        )

    unresolved = previous._unresolved_same_head(repo, token, state.pending_head)
    if unresolved:
        scan_pr = unresolved[0]["number"]
    elif origin["state"] == "open":
        scan_pr = state.pending_pr
    else:
        scan_pr = 0
    previous._write_state(
        repo,
        token,
        previous._clear_pending(state, scan_pr=scan_pr),
    )
    print(
        "MONDE bootstrap recovery: cleared operator-confirmed unposted pending mutation "
        f"pr={state.pending_pr} run={state.pending_run_id} baseline={state.pending_baseline_attempt} "
        f"check={state.pending_check_id} head={state.pending_head} reason={reason}"
    )
    return 0


def install() -> None:
    previous.install()
    previous.previous._resume_pending = _resume_pending
    base.poll = previous.previous.poll
    core.poll = previous.previous.poll


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
        return _recover_confirmed_unposted(repo, token)
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
