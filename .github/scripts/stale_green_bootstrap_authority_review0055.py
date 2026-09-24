from __future__ import annotations

import os
from typing import Any

import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0049 as pending
import stale_green_bootstrap_authority_review0051_recovery as recovery
import stale_green_bootstrap_authority_review0054 as previous


_ORIGINAL_PROCESS = pending._process_head_group
RECOVERY_ACTION = recovery.RECOVERY_ACTION


def _pending_lifetime_process(*args: Any, **kwargs: Any):
    original_write = pending._write_state
    pending_active = False

    def tracked_write(repo: str, token: str, state: Any) -> None:
        nonlocal pending_active
        original_write(repo, token, state)
        pending_active = bool(getattr(state, "pending_pr", 0))

    pending._write_state = tracked_write
    try:
        return _ORIGINAL_PROCESS(*args, **kwargs)
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
    pending._process_head_group = _pending_lifetime_process


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
