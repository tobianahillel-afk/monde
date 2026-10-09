"""Fail-closed, read-only verification of a completed trusted-source run.

This module is a proposed default-branch-owned consumer. It MUST NOT treat a
raw green commit status, a candidate-supplied proof, or an uncompleted workflow
as merge authority. A trusted caller must obtain all snapshots and the artifact
from GitHub independently and verify them again immediately before use.
"""
from __future__ import annotations

import hashlib
import io
import json
import stat
import zipfile
from typing import Any

import trusted_source_attestor as source


PROOF_KEYS = frozenset({
    "schema_version", "repository", "pr_number", "candidate_sha",
    "base_sha", "run_id", "run_attempt", "manifest_sha256",
    "approved_source_count",
})
PROOF_PREFIX = "monde-trusted-proof-"
WORKFLOW_PATH = ".github/workflows/monde-trusted-source.yml"
MAX_PROOF_BYTES = 8192
MAX_ARCHIVE_BYTES = 65536
PROOF_FILENAME = "monde-trusted-source-proof.json"


def _positive_int(value: Any) -> bool:
    return type(value) is int and value > 0


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise source.AttestationError(f"malformed trusted consumer {label}")
    return value


def extract_exact_proof_archive(archive: bytes) -> bytes:
    """Decode a bounded GitHub artifact ZIP without trusting archive paths."""
    if not isinstance(archive, bytes) or not archive or len(archive) > MAX_ARCHIVE_BYTES:
        raise source.AttestationError("invalid or oversized trusted artifact archive")
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            members = bundle.infolist()
            if len(members) != 1:
                raise source.AttestationError("trusted artifact must contain one proof file")
            entry = members[0]
            mode = (entry.external_attr >> 16) & 0xFFFF
            if (
                entry.filename != PROOF_FILENAME
                or entry.is_dir()
                or entry.flag_bits & 1
                or stat.S_IFMT(mode) not in (0, stat.S_IFREG)
                or entry.file_size < 1
                or entry.file_size > MAX_PROOF_BYTES
            ):
                raise source.AttestationError("unsafe trusted artifact member")
            with bundle.open(entry, "r") as handle:
                proof = handle.read(MAX_PROOF_BYTES + 1)
            if len(proof) != entry.file_size:
                raise source.AttestationError("trusted artifact member size mismatch")
            return proof
    except source.AttestationError:
        raise
    except (OSError, ValueError, RuntimeError, EOFError, zipfile.BadZipFile, NotImplementedError) as exc:
        raise source.AttestationError("cannot decode trusted artifact ZIP") from exc


def select_unique_artifact(artifacts: Any, run: Any) -> dict[str, Any]:
    """Select an immutable artifact from the independently fetched run's list."""
    checked_run = _object(run, "workflow run")
    run_id = checked_run.get("id")
    attempt = checked_run.get("run_attempt")
    if not _positive_int(run_id) or not _positive_int(attempt):
        raise source.AttestationError("invalid completed-run artifact identity")
    if not isinstance(artifacts, list):
        raise source.AttestationError("malformed completed-run artifacts")
    name = f"{PROOF_PREFIX}{run_id}-{attempt}"
    matches = [a for a in artifacts if isinstance(a, dict) and a.get("name") == name]
    if len(matches) != 1:
        raise source.AttestationError("missing or ambiguous completed-run proof artifact")
    a = matches[0]
    origin = _object(a.get("workflow_run"), "artifact run origin")
    if (
        not _positive_int(a.get("id"))
        or a.get("expired") is not False
        or not _positive_int(a.get("size_in_bytes"))
        or a["size_in_bytes"] > MAX_PROOF_BYTES
        or origin.get("id") != run_id
        or not _positive_int(origin.get("id"))
    ):
        raise source.AttestationError("invalid completed-run proof artifact")
    return a


def verify_completed_proof(
    proof_bytes: bytes, run: Any, artifact: Any,
    pull_request: Any, main_branch: Any, manifest_bytes: bytes,
) -> tuple[str, str]:
    """Verify exact candidate, base and successful main-owned run provenance.

    Only a read-only assertion, not a required GitHub merge check. Consumers
    still need independently enforced status-source rules and a base-freshness
    policy under WORK-0003.
    """
    if not isinstance(proof_bytes, bytes) or len(proof_bytes) > MAX_PROOF_BYTES:
        raise source.AttestationError("unbounded trusted proof payload")
    if not isinstance(manifest_bytes, bytes) or not manifest_bytes:
        raise source.AttestationError("missing approved default-branch manifest")
    try:
        proof = json.loads(
            proof_bytes.decode("utf-8"),
            object_pairs_hook=source._unique_json_object_pairs,
        )
        manifest = json.loads(
            manifest_bytes.decode("utf-8"),
            object_pairs_hook=source._unique_json_object_pairs,
        )
    except (ValueError, UnicodeDecodeError, source.AttestationError) as exc:
        raise source.AttestationError("malformed trusted proof JSON") from exc
    p = _object(proof, "proof")
    r = _object(run, "workflow run")
    a = _object(artifact, "artifact")
    pr = _object(pull_request, "pull request")
    base = _object(main_branch, "main branch")
    approved = source.validate_manifest(manifest)
    if set(p) != PROOF_KEYS:
        raise source.AttestationError("unexpected trusted proof fields")
    head = p.get("candidate_sha")
    base_sha = p.get("base_sha")
    if (
        type(p.get("schema_version")) is not int or p["schema_version"] != 1
        or p.get("repository") != "tobianahillel-afk/monde"
        or type(p.get("pr_number")) is not int or p["pr_number"] != 2
        or not source._sha(head) or not source._sha(base_sha)
        or not _positive_int(p.get("run_id"))
        or not _positive_int(p.get("run_attempt"))
        or type(p.get("approved_source_count")) is not int
        or p["approved_source_count"] != len(approved)
        or p.get("manifest_sha256") != hashlib.sha256(manifest_bytes).hexdigest()
    ):
        raise source.AttestationError("trusted proof content does not match approved source")
    if (
        not _positive_int(r.get("id")) or r["id"] != p["run_id"]
        or not _positive_int(r.get("run_attempt"))
        or r["run_attempt"] != p["run_attempt"]
        or r.get("head_sha") != base_sha
        or r.get("head_branch") != "main"
        or r.get("status") != "completed"
        or r.get("conclusion") != "success"
        or r.get("event") not in {"pull_request_target", "push"}
        or r.get("path") not in {WORKFLOW_PATH, WORKFLOW_PATH + "@main", WORKFLOW_PATH + "@refs/heads/main"}
        or _object(r.get("repository"), "run repository").get("full_name")
            != "tobianahillel-afk/monde"
    ):
        raise source.AttestationError("proof is not bound to a successful main-owned run")
    if (
        a.get("name") != f"{PROOF_PREFIX}{r['id']}-{r['run_attempt']}"
        or _object(a.get("workflow_run"), "artifact workflow").get("id") != r["id"]
        or not _positive_int(a.get("id"))
        or a.get("expired") is not False
        or not _positive_int(a.get("size_in_bytes"))
        or a["size_in_bytes"] > MAX_PROOF_BYTES
    ):
        raise source.AttestationError("proof does not belong to exact successful run")
    if (
        type(pr.get("number")) is not int or pr["number"] != 2
        or pr.get("state") != "open"
        or pr.get("draft") is not False
        or _object(pr.get("head"), "PR head").get("sha") != head
        or _object(pr.get("base"), "PR base").get("sha") != base_sha
        or pr["base"].get("ref") != "main"
        or _object(base.get("commit"), "main commit").get("sha") != base_sha
    ):
        raise source.AttestationError("trusted proof stale against current PR or main")
    return head, base_sha

def verify_completed_archive(
    archive_bytes: bytes, run: Any, artifact: Any,
    pull_request: Any, main_branch: Any, manifest_bytes: bytes,
) -> tuple[str, str]:
    """Decode the exact downloaded artifact before completed-run verification."""
    return verify_completed_proof(
        extract_exact_proof_archive(archive_bytes),
        run, artifact, pull_request, main_branch, manifest_bytes,
    )

