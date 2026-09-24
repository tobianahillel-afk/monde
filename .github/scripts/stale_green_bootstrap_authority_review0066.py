from __future__ import annotations

import os
from typing import Any

import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0049 as pending
import stale_green_bootstrap_authority_review0051_recovery as recovery
import stale_green_bootstrap_authority_review0055 as lifetime
import stale_green_bootstrap_authority_review0065 as previous


RECOVERY_ACTION = recovery.RECOVERY_ACTION


def _require_expected_gate(
    repo: str,
    head: str,
    token: str,
    expected_check_id: int,
    phase: str,
) -> dict[str, Any]:
    latest = core.latest_required_check(repo, head, token)
    if not base._latest_check_is_merge_acceptable(latest):
        raise RuntimeError(
            f"global MONDE Gate authority is not merge-acceptable during {phase}"
        )
    assert latest is not None
    if latest.get("id") != expected_check_id:
        raise RuntimeError(
            f"global MONDE Gate authority changed during {phase}"
        )
    return latest


def _coherent_mutation_snapshot_process(
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
        return lifetime._pending_lifetime_process(
            repo,
            token,
            group,
            rerun_slots,
            state,
            scan_pr,
            scan_page,
            scan_anchor,
        )

    head = core._pr_head_identity(group[0])[2]
    original_write = pending._write_state

    def guarded_write(
        write_repo: str,
        write_token: str,
        next_state: Any,
    ) -> None:
        is_pending = bool(getattr(next_state, "pending_pr", 0))
        if not is_pending:
            original_write(write_repo, write_token, next_state)
            return

        expected_check_id = getattr(next_state, "pending_check_id", 0)
        if not core._positive_int(expected_check_id):
            raise RuntimeError(
                "pending mutation lacks exact prior required-check identity"
            )

        _require_expected_gate(
            write_repo,
            head,
            write_token,
            expected_check_id,
            "mutation snapshot G1",
        )

        current_pr = pending._current_pending_pr(
            write_repo,
            write_token,
            next_state,
        )
        if current_pr is None:
            raise RuntimeError(
                "pending pull-request authority closed during mutation snapshot"
            )
        if not core.unresolved_review_threads(
            write_repo,
            next_state.pending_pr,
            write_token,
        ):
            raise RuntimeError(
                "review-thread authority resolved during mutation snapshot"
            )

        _require_expected_gate(
            write_repo,
            head,
            write_token,
            expected_check_id,
            "mutation snapshot G2",
        )

        if base._remaining_request_budget() < pending.MUTATION_REQUEST_RESERVE:
            raise base.DeferredForBudget(
                "insufficient request headroom after coherent mutation snapshot"
            )

        try:
            original_write(write_repo, write_token, next_state)
        except (pending.PendingMutationObservation, pending.PendingMutationUncertain):
            raise
        except Exception as exc:
            raise pending.PendingMutationUncertain(
                "write-ahead pending-state acknowledgement is ambiguous; "
                "automatic rerun and same-invocation idle overwrite are forbidden"
            ) from exc

    pending._write_state = guarded_write
    try:
        return lifetime._pending_lifetime_process(
            repo,
            token,
            group,
            rerun_slots,
            state,
            scan_pr,
            scan_page,
            scan_anchor,
        )
    finally:
        pending._write_state = original_write


def install() -> None:
    previous.install()
    pending._process_head_group = _coherent_mutation_snapshot_process


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
