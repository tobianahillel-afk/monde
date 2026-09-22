from __future__ import annotations

import os
from typing import Any

import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0048 as observation
import stale_green_bootstrap_authority_review0049 as pending
import stale_green_bootstrap_authority_review0051_recovery as previous


_ORIGINAL_WAIT = observation._wait_for_terminal_invalidation
RECOVERY_ACTION = previous.RECOVERY_ACTION


def _pending_preserving_wait(*args: Any, **kwargs: Any) -> bool:
    try:
        return _ORIGINAL_WAIT(*args, **kwargs)
    except base.DeferredObservation:
        raise
    except pending.PendingMutationUncertain:
        raise
    except RuntimeError as exc:
        raise pending.PendingMutationUncertain(
            "rerun post-condition observation failed after mutation; durable pending state retained"
        ) from exc


def install() -> None:
    previous.install()
    observation._wait_for_terminal_invalidation = _pending_preserving_wait


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
        return previous._inspect_confirmed_unposted(repo, token)
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
