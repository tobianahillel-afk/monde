"""Read-only collection of trusted-source evidence from GitHub's own APIs.

Not a GitHub-required merge gate by itself. This module must execute from the
approved default-branch source tree with a read-only token; caller must not
substitute candidate-owned code, API responses or artifact bytes.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import trusted_source_attestor as source
import trusted_source_consumer as consumer


REPO = "tobianahillel-afk/monde"
MAX_ZIP_BYTES = consumer.MAX_ARCHIVE_BYTES
PROOF_FILE = consumer.PROOF_FILENAME
MAX_RUNS = 100
TRUSTED_JOB_NAME = "MONDE / Trusted Source"


def _attestation_job_relevant(repo: str, token: str, run: dict[str, Any]) -> bool:
    """Only a non-skipped, base-owned attestation job represents PR #2/push.

    Unrelated pull_request_target workflow invocations exist for other PRs,
    but their exact job is SKIPPED by the default-branch-owned workflow guard.
    Never use mere run existence or mutable display_title as PR provenance.
    """
    run_id = run.get("id")
    if not consumer._positive_int(run_id):
        raise source.AttestationError("invalid trusted run identity")
    response = source._get_json(repo, f"actions/runs/{run_id}/jobs?per_page=100", token)
    jobs = response.get("jobs")
    total = response.get("total_count")
    if (
        type(total) is not int or total < 0 or total > 100
        or not isinstance(jobs, list) or len(jobs) != total
        or any(not isinstance(j, dict) for j in jobs)
    ):
        raise source.AttestationError("incomplete trusted attestation job provenance")
    matches = [j for j in jobs if j.get("name") == TRUSTED_JOB_NAME]
    if len(matches) != 1:
        # A queued run whose job graph is not visible cannot authorize an old
        # success: deny transiently, rather than guess a PR association.
        raise source.AttestationError("missing or ambiguous trusted attestation job")
    job = matches[0]
    if not consumer._positive_int(job.get("id")) or job.get("run_id") != run_id:
        raise source.AttestationError("malformed trusted attestation job identity")
    status = job.get("status")
    conclusion = job.get("conclusion")
    if status == "completed" and conclusion == "skipped":
        return False
    if (
        status not in {"queued", "in_progress", "completed", "waiting"}
        or (status == "completed" and conclusion not in {
            "success", "failure", "cancelled", "timed_out", "action_required",
            "neutral", "stale"
        })
        or (status != "completed" and conclusion is not None)
    ):
        raise source.AttestationError("ambiguous trusted attestation job state")
    return True


def _collect_run(repo: str, token: str) -> dict[str, Any]:
    if repo != REPO or not token:
        raise source.AttestationError("invalid trusted-source evidence collection identity")
    # Each endpoint returns GitHub-ordered most-recent first. Conservative:
    # only the newest relevant source run may authorize the current PR; an
    # older success cannot bypass a newer failed or pending re-attestation.
    runs: list[dict[str, Any]] = []
    for event in ("pull_request_target", "push"):
        response = source._get_json(
            repo,
            "actions/workflows/monde-trusted-source.yml/runs"
            f"?branch=main&event={event}&per_page={MAX_RUNS}",
            token,
        )
        candidates = response.get("workflow_runs")
        if not isinstance(candidates, list) or any(not isinstance(x, dict) for x in candidates):
            raise source.AttestationError("malformed trusted workflow-run listing")
        if type(response.get("total_count")) is not int or response["total_count"] < len(candidates):
            raise source.AttestationError("malformed trusted workflow-run count")
        runs.extend(candidates)
    if not runs:
        raise source.AttestationError("no default-branch trusted-source workflow run")
    if any(not consumer._positive_int(r.get("id")) or not isinstance(r.get("created_at"), str)
           for r in runs):
        raise source.AttestationError("malformed trusted workflow-run ordering")
    runs.sort(key=lambda r: (r["created_at"], r["id"]), reverse=True)
    seen: set[int] = set()
    for candidate in runs:
        run_id = candidate["id"]
        if run_id in seen:
            raise source.AttestationError("duplicate trusted source run identity")
        seen.add(run_id)
        if not _attestation_job_relevant(repo, token, candidate):
            # Other PRs targeting main schedule the same workflow, but the
            # only security-sensitive job is skipped by the exact PR #2 guard.
            continue
        # Re-fetch by ID rather than trusting only the list projection.
        run = source._get_json(repo, f"actions/runs/{run_id}", token)
        if (
            run.get("id") != run_id
            or run.get("created_at") != candidate["created_at"]
            or run.get("run_attempt") != candidate.get("run_attempt")
            or run.get("event") != candidate.get("event")
        ):
            raise source.AttestationError("trusted source run identity changed")
        return run
    raise source.AttestationError("no relevant PR #2 or main-push attestation run")


def _unique_artifact(repo: str, token: str, run: dict[str, Any]) -> dict[str, Any]:
    if not consumer._positive_int(run.get("id")):
        raise source.AttestationError("malformed trusted run for artifact discovery")
    response = source._get_json(
        repo, f"actions/runs/{run['id']}/artifacts?per_page=100", token,
    )
    items = response.get("artifacts")
    total = response.get("total_count")
    if (
        type(total) is not int or total < 0 or total > 100
        or not isinstance(items, list) or len(items) != total
    ):
        raise source.AttestationError("incomplete trusted proof artifact listing")
    return consumer.select_unique_artifact(items, run)


class _SafeArtifactRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        host = parsed.hostname or ""
        if (
            parsed.scheme != "https"
            or not (host.endswith(".githubusercontent.com")
                    or host.endswith(".blob.core.windows.net"))
        ):
            raise source.AttestationError("unapproved GitHub artifact redirect")
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None:
            redirected.remove_header("Authorization")
        return redirected


def _download_exact_proof(repo: str, token: str, artifact: dict[str, Any]) -> bytes:
    artifact_id = artifact.get("id")
    if repo != REPO or not token or not consumer._positive_int(artifact_id):
        raise source.AttestationError("malformed trusted artifact download identity")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/actions/artifacts/{artifact_id}/zip",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        opener = urllib.request.build_opener(_SafeArtifactRedirect())
        with opener.open(request, timeout=20) as response:
            archive = response.read(MAX_ZIP_BYTES + 1)
    except (OSError, urllib.error.HTTPError) as exc:
        raise source.AttestationError("trusted proof artifact download failed") from exc
    if len(archive) > MAX_ZIP_BYTES:
        raise source.AttestationError("trusted proof artifact exceeds ZIP bound")
    return consumer.extract_exact_proof_archive(archive)


def check_current_main_owned_proof(repo: str, token: str, manifest_bytes: bytes) -> tuple[str, str]:
    if repo != REPO or not token:
        raise source.AttestationError("invalid trusted consumer invocation")
    original_pr = source._get_json(repo, "pulls/2", token)
    original_base = source._get_json(repo, "branches/main", token)
    run = _collect_run(repo, token)
    artifact = _unique_artifact(repo, token, run)
    proof = _download_exact_proof(repo, token, artifact)
    # Re-fetch mutable PR and main once all remote work completes. The caller
    # must additionally enforce branch up-to-date/required-check rules because
    # another actor can always push AFTER this final read.
    final_pr = source._get_json(repo, "pulls/2", token)
    final_base = source._get_json(repo, "branches/main", token)
    if (
        original_pr != final_pr or original_base != final_base
    ):
        raise source.AttestationError("PR or default branch drifted during proof collection")
    return consumer.verify_completed_proof(
        proof, run, artifact, final_pr, final_base, manifest_bytes,
    )


def main() -> int:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    manifest = source.Path(__file__).resolve().parent / "approved_sources.json"
    head, base = check_current_main_owned_proof(repo, token, manifest.read_bytes())
    print(f"MONDE read-only trusted proof verified: head={head}, base={base}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (source.AttestationError, OSError, ValueError) as exc:
        print(f"MONDE trusted proof denied: {exc}", file=source.sys.stderr)
        raise SystemExit(1)
