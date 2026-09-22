from __future__ import annotations

import time
from typing import Any

import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base


class RestartTargetScan(RuntimeError):
    pass


def _direct_target_for_pr(
    repo: str,
    token: str,
    pr: dict[str, Any],
    start_page: int = 1,
    expected_anchor: str = "-",
) -> tuple[tuple[dict[str, Any], dict[str, Any]] | None, int | None]:
    if base._remaining_request_budget() < base.MIN_TARGET_REQUEST_HEADROOM:
        raise base.DeferredForBudget(
            "insufficient request headroom for bounded target validation and mutation"
        )
    number = pr["number"]
    identity = core._pr_head_identity(pr)
    merge_sha = base._pr_merge_sha(pr)
    if merge_sha is None:
        raise RuntimeError(f"open PR #{number} lacks a current merge-ref SHA")

    page = start_page
    prior_anchor: str | None = None
    if page > 1:
        if base._SHA256.fullmatch(expected_anchor) is None:
            page = 1
        else:
            prior_checks, prior_has_more = base._candidate_gate_check_page(
                repo, identity[2], token, page - 1
            )
            actual_anchor = base._check_page_anchor(prior_checks, prior_has_more)
            if not prior_has_more or actual_anchor != expected_anchor:
                page = 1
            else:
                prior_anchor = actual_anchor

    page_anchor = "-"
    for _ in range(base.MAX_TARGET_PAGES_PER_INVOCATION):
        if base._remaining_request_budget() < base.MIN_TARGET_REQUEST_HEADROOM:
            raise base.DeferredForBudget(
                "insufficient request headroom before target check page"
            )
        checks, has_more = base._candidate_gate_check_page(
            repo, identity[2], token, page
        )
        page_anchor = base._check_page_anchor(checks, has_more)

        if prior_anchor is not None:
            if base._remaining_request_budget() < base.MIN_TARGET_REQUEST_HEADROOM:
                raise base.DeferredForBudget(
                    "insufficient request headroom while verifying target-page boundary"
                )
            verify_checks, verify_has_more = base._candidate_gate_check_page(
                repo, identity[2], token, page - 1
            )
            if (
                not verify_has_more
                or base._check_page_anchor(verify_checks, verify_has_more)
                != prior_anchor
            ):
                return None, base.ScanPage(1)

        for check in checks:
            if (
                base._remaining_request_budget()
                <= base.STATE_WRITE_REQUEST_RESERVE
                + base.POSTCONDITION_REQUEST_RESERVE
                + 5
            ):
                raise base.DeferredForBudget(
                    "request headroom reached while validating bounded check candidates"
                )
            run_id, job_id = base._validate_gate_check(check, identity[2])
            run = core.request_data(
                f"https://api.github.com/repos/{repo}/actions/runs/{run_id}", token
            )
            if not isinstance(run, dict):
                raise RuntimeError("GitHub returned malformed canonical MONDE Gate run")
            run_attempt = base._validate_canonical_run(
                run, run_id, identity[2], require_completed=True
            )
            if core._run_head_identity(run) != identity:
                continue
            if core._run_created_at(run) < core._pr_created_at(pr):
                continue
            if base._triggering_pr_authority(repo, run) != (number, merge_sha):
                continue
            job = core.request_data(
                f"https://api.github.com/repos/{repo}/actions/jobs/{job_id}", token
            )
            if not isinstance(job, dict):
                raise RuntimeError("GitHub returned malformed protected MONDE Gate job")
            base._validate_protected_job(
                job,
                job_id=job_id,
                run_id=run_id,
                run_attempt=run_attempt,
                head=identity[2],
            )
            return (run, check), None

        if not has_more:
            return None, None
        prior_anchor = page_anchor
        page += 1

    return None, base.ScanPage(page, page_anchor)


def _wait_for_terminal_invalidation(
    repo: str,
    head: str,
    token: str,
    run_id: int,
    previous_attempt: int,
    previous_check_id: int,
    original_pr: dict[str, Any] | None = None,
    strict_job_binding: bool = False,
) -> bool:
    expected_attempt = previous_attempt + 1
    terminal_run: dict[str, Any] | None = None
    protected_conclusion: str | None = None

    for poll_index in range(base.MAX_POSTCONDITION_POLLS):
        if terminal_run is None:
            run = core.request_data(
                f"https://api.github.com/repos/{repo}/actions/runs/{run_id}", token
            )
            if not isinstance(run, dict):
                raise RuntimeError("GitHub returned malformed rerun post-condition")
            attempt = base._validate_canonical_run(
                run, run_id, head, require_completed=False
            )
            if attempt > expected_attempt:
                raise base.DeferredObservation(
                    "rerun attempt advanced beyond the single mutation-bound attempt"
                )
            if attempt < expected_attempt or run.get("status") != "completed":
                if poll_index + 1 < base.MAX_POSTCONDITION_POLLS:
                    time.sleep(base.POSTCONDITION_POLL_SECONDS)
                continue
            protected_conclusion = core.required_merge_gate_conclusion(
                repo, run, token
            )
            terminal_run = run

        latest = core.latest_required_check(repo, head, token)
        if latest is not None and latest.get("id") != previous_check_id:
            latest_run_id, latest_job_id = base._validate_gate_check(latest, head)
            if latest_run_id == run_id and latest.get("status") == "completed":
                if latest.get("conclusion") != protected_conclusion:
                    raise RuntimeError(
                        "rerun protected job and effective required check disagree"
                    )
                if strict_job_binding:
                    job = core.request_data(
                        f"https://api.github.com/repos/{repo}/actions/jobs/{latest_job_id}",
                        token,
                    )
                    if not isinstance(job, dict):
                        raise RuntimeError(
                            "GitHub returned malformed rerun protected-job post-condition"
                        )
                    base._validate_protected_job(
                        job,
                        job_id=latest_job_id,
                        run_id=run_id,
                        run_attempt=expected_attempt,
                        head=head,
                    )
                    if job["conclusion"] != protected_conclusion:
                        raise RuntimeError(
                            "rerun protected job and effective required check disagree"
                        )
                if original_pr is not None and base._current_pr(
                    repo, token, original_pr
                ) is None:
                    raise base.DeferredObservation(
                        "pull request authority changed while observing rerun post-condition"
                    )
                return not base._latest_check_is_merge_acceptable(latest)

        if poll_index + 1 < base.MAX_POSTCONDITION_POLLS:
            time.sleep(base.POSTCONDITION_POLL_SECONDS)

    raise base.DeferredObservation(
        "rerun did not reach its single terminal required-check post-condition within the bounded observation window"
    )


def _mutation_baseline(
    repo: str,
    token: str,
    original: dict[str, Any],
    run_id: int,
) -> int | None:
    head = core._pr_head_identity(original)[2]
    payload = core.request_data(
        f"https://api.github.com/repos/{repo}/actions/runs/{run_id}", token
    )
    if not isinstance(payload, dict):
        raise RuntimeError("GitHub returned malformed mutation-bound workflow run")
    attempt = base._validate_canonical_run(
        payload, run_id, head, require_completed=False
    )
    if payload.get("status") != "completed":
        return None
    merge_sha = base._pr_merge_sha(original)
    if merge_sha is None or base._triggering_pr_authority(repo, payload) != (
        original["number"],
        merge_sha,
    ):
        raise RuntimeError("mutation-bound workflow run no longer matches current PR authority")
    return attempt


def _process_head_group(
    repo: str,
    token: str,
    group: list[dict[str, Any]],
    rerun_slots: int,
    scan_pr: int = 0,
    scan_page: int = 1,
    scan_anchor: str = "-",
) -> tuple[list[int], list[str], tuple[int, int] | None]:
    head = core._pr_head_identity(group[0])[2]
    current_check = core.latest_required_check(repo, head, token)
    if current_check is None:
        return [], [], None
    if current_check.get("status") != "completed":
        for original in base._ordered_group_for_scan(group, scan_pr):
            if core.unresolved_review_threads(repo, original["number"], token):
                return [], [], (original["number"], base.ScanPage(1))
        return [], [], None
    if not base._latest_check_is_merge_acceptable(current_check):
        return [], [], None

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
            target, next_page = _direct_target_for_pr(
                repo, token, original, start_page, scan_anchor
            )
        else:
            target, next_page = _direct_target_for_pr(
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
        latest = core.latest_required_check(repo, head, token)
        if not base._latest_check_is_merge_acceptable(latest):
            return posted, errors, None
        assert latest is not None
        mutation_fresh = base._current_pr(repo, token, original)
        if mutation_fresh is None:
            return posted, errors, (number, base.ScanPage(1))
        if (
            base._remaining_request_budget()
            < base.POSTCONDITION_REQUEST_RESERVE + base.STATE_WRITE_REQUEST_RESERVE
        ):
            raise base.DeferredForBudget(
                "insufficient request headroom for rerun post-condition"
            )

        run_id = int(run["id"])
        baseline_attempt = _mutation_baseline(repo, token, mutation_fresh, run_id)
        if baseline_attempt is None:
            return posted, errors, (number, base.ScanPage(1))

        final_pr = base._current_pr(repo, token, original)
        if final_pr is None:
            return posted, errors, (number, base.ScanPage(1))
        if not core.unresolved_review_threads(repo, number, token):
            continue

        core.rerun_workflow(repo, run_id, token)
        posted.append(run_id)
        try:
            invalidated = _wait_for_terminal_invalidation(
                repo,
                head,
                token,
                run_id,
                baseline_attempt,
                int(latest["id"]),
                original,
                True,
            )
        except base.DeferredObservation:
            return posted, errors, (number, base.ScanPage(1))

        if invalidated:
            return posted, errors, None
        if core.unresolved_review_threads(repo, number, token):
            return posted, errors, (number, base.ScanPage(1))
        current_check = core.latest_required_check(repo, head, token)
        if not base._latest_check_is_merge_acceptable(current_check):
            return posted, errors, None

    return posted, errors, None


def install() -> None:
    base._direct_target_for_pr = _direct_target_for_pr
    base._wait_for_terminal_invalidation = _wait_for_terminal_invalidation
    base._process_head_group = _process_head_group
    base.install()


def main() -> int:
    install()
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
