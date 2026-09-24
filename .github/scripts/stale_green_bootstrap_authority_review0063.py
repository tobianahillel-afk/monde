from __future__ import annotations

import os
from typing import Any

import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0051_recovery as recovery
import stale_green_bootstrap_authority_review0061 as chronology
import stale_green_bootstrap_authority_review0062 as previous


RECOVERY_ACTION = recovery.RECOVERY_ACTION
_ORIGINAL_VALIDATE_CHRONOLOGY = chronology._validate_attempt_job_chronology


def _validate_full_run_job_containment(
    run: dict[str, Any],
    job: dict[str, Any],
) -> None:
    _ORIGINAL_VALIDATE_CHRONOLOGY(run, job)
    run_updated = core._updated_at(run.get("updated_at"))
    job_started = core._timestamp(
        job.get("started_at"),
        "protected MONDE Gate job started_at",
    )
    if job_started > run_updated:
        raise RuntimeError(
            "GitHub returned protected MONDE Gate job starting after current workflow run update"
        )
    if job.get("status") == "completed":
        job_completed = core._timestamp(
            job.get("completed_at"),
            "protected MONDE Gate job completed_at",
        )
        if job_completed > run_updated:
            raise RuntimeError(
                "GitHub returned protected MONDE Gate job completing after current workflow run update"
            )


def install() -> None:
    previous.install()
    chronology._validate_attempt_job_chronology = _validate_full_run_job_containment


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
