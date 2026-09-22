from __future__ import annotations

import os
from typing import Any

import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0049 as pending
import stale_green_bootstrap_authority_review0051_recovery as recovery
import stale_green_bootstrap_authority_review0055 as previous


RECOVERY_ACTION = recovery.RECOVERY_ACTION


def _pending_write_ack_process(*args: Any, **kwargs: Any):
    original_write = pending._write_state

    def guarded_write(repo: str, token: str, state: Any) -> None:
        is_pending = bool(getattr(state, "pending_pr", 0))
        if not is_pending:
            original_write(repo, token, state)
            return
        try:
            original_write(repo, token, state)
        except (pending.PendingMutationObservation, pending.PendingMutationUncertain):
            raise
        except Exception as exc:
            raise pending.PendingMutationUncertain(
                "write-ahead pending-state acknowledgement is ambiguous; "
                "automatic rerun and same-invocation idle overwrite are forbidden"
            ) from exc

    pending._write_state = guarded_write
    try:
        return previous._pending_lifetime_process(*args, **kwargs)
    finally:
        pending._write_state = original_write


def install() -> None:
    previous.install()
    pending._process_head_group = _pending_write_ack_process


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
