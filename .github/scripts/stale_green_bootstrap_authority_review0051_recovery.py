from __future__ import annotations

import os

import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0050 as v5
import stale_green_bootstrap_authority_review0050_recovery as previous


RECOVERY_ACTION = "inspect-unposted-pending"
RECOVERY_CONFIRMATION = previous.RECOVERY_CONFIRMATION


def _inspect_confirmed_unposted(repo: str, token: str) -> int:
    state = v5._read_state(repo, token)
    reason = previous._validate_recovery_request(state)

    run = core.request_data(
        f"https://api.github.com/repos/{repo}/actions/runs/{state.pending_run_id}", token
    )
    if not isinstance(run, dict):
        raise RuntimeError("GitHub returned malformed pending workflow run during recovery inspection")
    attempt = base._validate_canonical_run(
        run,
        state.pending_run_id,
        state.pending_head,
        require_completed=False,
    )
    if attempt != state.pending_baseline_attempt:
        raise RuntimeError(
            "recovery inspection refused: workflow attempt changed, so mutation attribution is ambiguous"
        )

    latest = core.latest_required_check(repo, state.pending_head, token)
    if (
        latest is None
        or not core._positive_int(latest.get("id"))
        or latest["id"] != state.pending_check_id
    ):
        raise RuntimeError(
            "recovery inspection refused: effective required-check identity changed after write-ahead state"
        )

    print(
        "MONDE bootstrap recovery inspection: durable pending mutation preserved; "
        f"pr={state.pending_pr} head={state.pending_head} run={state.pending_run_id} "
        f"baseline={state.pending_baseline_attempt} check={state.pending_check_id}. "
        "If independent operator evidence establishes that the original POST never occurred, "
        f"manually rerun canonical run {state.pending_run_id}; do not clear issue #7. "
        f"reason={reason}"
    )
    return 0


def install() -> None:
    previous.install()


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
        return _inspect_confirmed_unposted(repo, token)
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
