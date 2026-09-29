from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

import tools.governance.change_guard as cg

T11_PATH = "tools/governance/t11_closure.py"
INTEGRATION_PROVENANCE_PATH = "registry/integration-provenance.yaml"
WORKFLOW_PATH = ".github/workflows/governance.yml"
CORE_WORKFLOW_PATH = ".github/workflows/_governance-core.yml"
POLL_SCRIPT_PATH = "tools/governance/thread_state_poll.py"
POLL_CRON = "*/5 * * * *"
MAX_SECRET_BLOB_BYTES = 4 * 1024 * 1024
TERMINAL_IMPORT_STATUS = {"reviews": "COMPLETE", "tests": "PASS"}

EXPECTED_PROVENANCE_BOOTSTRAP_COMMITS = (
    "ac836f37dad997992f5824bfa7dcab805c851112",
    "637df199ca40556ed4177a6b09f39eac9b7b28a6",
    "42e4e93c0e25294b26d2a00d958660c9124697d1",
    "7c2a81d7b9fad7b26b218fc90340baf5e26535cc",
    "9ac613c28e3628947db341745f6cacd166015ac8",
)

REQUIRED_EVENT_TYPES = {
    "pull_request": {"opened", "synchronize", "reopened", "ready_for_review"},
    "pull_request_review": {"submitted", "edited", "dismissed"},
    "pull_request_review_comment": {"created", "edited", "deleted"},
}

CHECKOUT_ACTION = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
SETUP_PYTHON_ACTION = "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97"
DEPENDENCY_REVIEW_ACTION = "actions/dependency-review-action@a1d282b36b6f3519aa1f3fc636f609c47dddb294"
CODEQL_INIT_ACTION = "github/codeql-action/init@b96794f015dfd88f77b49b1c93e0fa7110f94c63"
CODEQL_ANALYZE_ACTION = "github/codeql-action/analyze@b96794f015dfd88f77b49b1c93e0fa7110f94c63"
PR_EVENT_IF = "startsWith(github.event_name, 'pull_request')"
CORE_PR_IF = "startsWith(inputs.event_name, 'pull_request')"
FINAL_GATE_IF = "always() && github.event_name != 'schedule'"
CODEQL_JOB_IF = "github.event_name != 'schedule'"
TRUSTED_RUNNER = "ubuntu-24.04"
WORKFLOW_PERMISSIONS = {"contents": "read"}
CORE_WORKFLOW_PERMISSIONS = {"contents": "read"}
DEPENDENCY_REVIEW_PERMISSIONS = {"contents": "read"}
CODEQL_PERMISSIONS = {
    "actions": "read",
    "contents": "read",
    "packages": "read",
    "security-events": "write",
}
FINAL_GATE_PERMISSIONS = {"contents": "read", "pull-requests": "read"}
POLL_PERMISSIONS = {
    "actions": "write",
    "contents": "read",
    "pull-requests": "read",
}
WORKFLOW_JOB_IDS = frozenset(
    {"governance-core", "dependency-review", "codeql", "final-gate", "review-thread-state-poll"}
)
CORE_WORKFLOW_JOB_IDS = frozenset({"candidate-tests", "validate"})
CORE_VALIDATE_NEEDS = frozenset({"candidate-tests"})
FINAL_GATE_NEEDS = frozenset({"governance-core", "dependency-review", "codeql"})

CORE_WORKFLOW_USES = "./.github/workflows/_governance-core.yml"
CORE_EVENT_EXPR = "${{ github.event_name }}"
CORE_BASE_EXPR = "${{ github.event.pull_request.base.sha || github.event.before || github.sha }}"
CORE_HEAD_EXPR = "${{ github.event.pull_request.head.sha || github.sha }}"
CORE_INPUT_BASE_EXPR = "${{ inputs.base_sha }}"
CORE_INPUT_HEAD_EXPR = "${{ inputs.head_sha }}"
CODEQL_HEAD_EXPR = "${{ github.event.pull_request.head.sha || github.sha }}"
FINAL_HEAD_EXPR = "${{ github.event.pull_request.head.sha }}"

DEPENDENCY_PROBE_RUN = """set -euo pipefail
code="$(curl --silent --show-error --output /tmp/monde-sbom.json --write-out '%{http_code}' \\
  --header 'Accept: application/vnd.github+json' \\
  --header "Authorization: Bearer ${GH_TOKEN}" \\
  --header 'X-GitHub-Api-Version: 2022-11-28' \\
  "https://api.github.com/repos/${GITHUB_REPOSITORY}/dependency-graph/sbom")"
case "$code" in
  200)
    echo 'supported=true' >> "$GITHUB_OUTPUT"
    ;;
  404)
    echo 'supported=false' >> "$GITHUB_OUTPUT"
    echo '::notice title=Dependency Graph unavailable::Dependency Review is defined but cannot become an effective hard gate until WORK-0003 enables GitHub Dependency Graph.'
    ;;
  *)
    echo "Unexpected Dependency Graph probe HTTP status: $code" >&2
    cat /tmp/monde-sbom.json >&2 || true
    exit 1
    ;;
esac
"""

CANDIDATE_PYTEST_COMMAND = (
    "python", "-m", "pytest", "--cov", "--cov-branch",
    "--cov-report=term-missing", "--cov-report=xml:coverage.xml", "--cov-fail-under=100",
)
CANDIDATE_MUTATION_COMMANDS = (
    ("python", "scripts/governance_mutation_smoke.py"),
    ("python", ".github/scripts/governance_l2_mutation_smoke.py"),
    ("python", ".github/scripts/governance_t10_mutation_smoke.py"),
    ("python", ".github/scripts/governance_t11_mutation_smoke.py"),
    ("python", ".github/scripts/governance_t13_mutation_smoke.py"),
)
CANDIDATE_MUTATION_SCRIPT_PATHS = frozenset(command[1] for command in CANDIDATE_MUTATION_COMMANDS)
CANDIDATE_SETUP_PYTHON_WITH = {
    "python-version": "3.13.15",
    "cache": "pip",
    "cache-dependency-path": "requirements/governance-ci.txt",
}
TRUSTED_VALIDATE_SETUP_PYTHON_WITH = {"python-version": "3.13.15"}

REQUIRED_CORE_COMMANDS = (
    ("CORE_TOOLCHAIN_WIRING", ("python", "-m", "pip", "install", "--require-hashes", "-r", "requirements/governance-ci.txt"), frozenset()),
    ("CORE_VALIDATE_REPO_WIRING", ("python", "-m", "tools.governance.validate_repo", ".", "--json-out", "governance-findings.json"), frozenset()),
    ("CORE_STRICT_CONTRACTS_WIRING", ("python", "-m", "tools.governance.strict_contracts", ".", "--json-out", "strict-findings.json"), frozenset()),
    ("CORE_PATH_SAFETY_WIRING", ("python", "-m", "tools.governance.path_safety", ".", "--json-out", "path-findings.json"), frozenset()),
    ("CORE_CHANGE_GUARD_WIRING", ("python", "-m", "tools.governance.change_guard", ".", "--base", CORE_INPUT_BASE_EXPR, "--head", CORE_INPUT_HEAD_EXPR, "--json-out", "change-findings.json"), frozenset({CORE_PR_IF})),
    ("CORE_L2_GATE_WIRING", ("PYTHONPATH=$PWD:$PWD/.github/scripts", "python", ".github/scripts/governance_l2_gate.py", ".", "--base", CORE_INPUT_BASE_EXPR, "--head", CORE_INPUT_HEAD_EXPR, "--json-out", "l2-hardening-findings.json"), frozenset({CORE_PR_IF})),
    ("CORE_REVIEW_CLOSURE_WIRING", ("python", "-m", "tools.governance.review_closure_gate", ".", "--base", CORE_INPUT_BASE_EXPR, "--head", CORE_INPUT_HEAD_EXPR, "--json-out", "review-closure-findings.json"), frozenset({CORE_PR_IF})),
    ("CORE_T7_WIRING", ("python", "-m", "tools.governance.t7_closure", ".", "--base", CORE_INPUT_BASE_EXPR, "--head", CORE_INPUT_HEAD_EXPR, "--json-out", "t7-closure-findings.json"), frozenset({CORE_PR_IF})),
    ("CORE_T8_WIRING", ("python", "-m", "tools.governance.t8_closure", ".", "--base", CORE_INPUT_BASE_EXPR, "--head", CORE_INPUT_HEAD_EXPR, "--json-out", "t8-closure-findings.json"), frozenset({CORE_PR_IF})),
    ("CORE_T9_WIRING", ("python", "-m", "tools.governance.t9_closure", ".", "--base", CORE_INPUT_BASE_EXPR, "--head", CORE_INPUT_HEAD_EXPR, "--json-out", "t9-closure-findings.json"), frozenset({CORE_PR_IF})),
    ("CORE_T10_WIRING", ("python", "-m", "tools.governance.t10_closure", ".", "--base", CORE_INPUT_BASE_EXPR, "--head", CORE_INPUT_HEAD_EXPR, "--json-out", "t10-closure-findings.json"), frozenset({CORE_PR_IF})),
    ("CORE_CONTEXT_MANIFEST_WIRING", ("python", "-m", "tools.governance.context_manifest", ".", "--base", CORE_INPUT_BASE_EXPR, "--head", CORE_INPUT_HEAD_EXPR, "--out", "context-manifest.json"), frozenset({CORE_PR_IF})),
)

CORE_REQUIRED_STEP_INDEXES = {
    "CORE_TOOLCHAIN_WIRING": 2,
    "CORE_VALIDATE_REPO_WIRING": 3,
    "CORE_STRICT_CONTRACTS_WIRING": 4,
    "CORE_PATH_SAFETY_WIRING": 5,
    "CORE_CHANGE_GUARD_WIRING": 6,
    "CORE_L2_GATE_WIRING": 7,
    "CORE_REVIEW_CLOSURE_WIRING": 8,
    "CORE_T7_WIRING": 9,
    "CORE_T8_WIRING": 10,
    "CORE_T9_WIRING": 11,
    "CORE_T10_WIRING": 12,
    "CORE_CONTEXT_MANIFEST_WIRING": 14,
}

FINAL_GATE_LANE_RESULTS_RUN = """set -euo pipefail
echo "governance-core=${{ needs.governance-core.result }}"
echo "dependency-review=${{ needs.dependency-review.result }}"
echo "codeql=${{ needs.codeql.result }}"
test '${{ needs.governance-core.result }}' = 'success'
test '${{ needs.codeql.result }}' = 'success'
case '${{ needs.dependency-review.result }}' in
  success|skipped) ;;
  *) exit 1 ;;
esac
"""


@dataclass(frozen=True)
class Finding:
    path: str
    rule: str
    message: str

    def render(self) -> str:
        return f"ERROR {self.rule} {self.path}: {self.message}"


def merge_inherits_provenance_blob(root: Path, sha: str) -> bool:
    parents = cg.commit_parents(root, sha)
    if len(parents) < 2:
        return False
    current_blob = cg.blob_sha_at(root, sha, INTEGRATION_PROVENANCE_PATH)
    if current_blob is None:
        return False
    return any(
        cg.blob_sha_at(root, parent, INTEGRATION_PROVENANCE_PATH) == current_blob
        for parent in parents
    )


def provenance_history_commits(root: Path, base: str, head: str) -> list[str]:
    merge_base = cg.git(root, "merge-base", base, head).strip()
    if not merge_base:
        raise RuntimeError("no merge base for integration-provenance bootstrap audit")
    commits = [
        line
        for line in cg.git(
            root,
            "rev-list",
            "--full-history",
            "--reverse",
            "--topo-order",
            f"{merge_base}..{head}",
            "--",
            INTEGRATION_PROVENANCE_PATH,
        ).splitlines()
        if line
    ]
    return [sha for sha in commits if not merge_inherits_provenance_blob(root, sha)]


def validate_provenance_bootstrap(root: Path, base: str, head: str) -> list[Finding]:
    if cg.file_exists_at(root, base, INTEGRATION_PROVENANCE_PATH):
        return []
    observed = tuple(provenance_history_commits(root, base, head))
    if observed == EXPECTED_PROVENANCE_BOOTSTRAP_COMMITS:
        return []
    return [
        Finding(
            INTEGRATION_PROVENANCE_PATH,
            "PROVENANCE_BOOTSTRAP_HISTORY",
            "pre-T10 integration-provenance bootstrap history must equal the independently reviewed immutable five-commit sequence; "
            f"expected={list(EXPECTED_PROVENANCE_BOOTSTRAP_COMMITS)}, observed={list(observed)}",
        )
    ]


def first_status_boundaries_full_history(root: Path, path: str, status: str, head: str) -> list[str]:
    commits = [
        line
        for line in cg.git(
            root,
            "rev-list",
            "--full-history",
            "--reverse",
            "--topo-order",
            head,
            "--",
            path,
        ).splitlines()
        if line
    ]
    boundaries: list[str] = []
    for sha in commits:
        current = cg.show_yaml(root, sha, path)
        if not current or current.get("status") != status:
            continue
        parents = cg.commit_parents(root, sha)
        if not parents or all((cg.show_yaml(root, parent, path) or {}).get("status") != status for parent in parents):
            boundaries.append(sha)
    return boundaries


def first_status_commit_full_history(root: Path, path: str, status: str, head: str) -> str | None:
    boundaries = first_status_boundaries_full_history(root, path, status, head)
    return boundaries[0] if boundaries else None


def _registry_paths(root: Path, head: str, directory: str) -> Iterable[str]:
    prefix = f"registry/{directory}"
    for path in cg.git(root, "ls-tree", "-r", "--name-only", head, prefix).splitlines():
        if path.endswith(".yaml") and not Path(path).name.startswith("_"):
            yield path


def _tree_sha(root: Path, sha: str) -> str | None:
    if not cg.commit_exists(root, sha):
        return None
    value = cg.git(root, "rev-parse", f"{sha}^{{tree}}").strip()
    return value if cg.FULL_COMMIT_SHA.fullmatch(value) else None


def squash_bridge_allows_first_status(
    root: Path,
    path: str,
    record: dict[str, Any],
    expected_import: str,
    current_first: str | None,
    head: str,
    directory: str,
) -> bool:
    provenance = cg.show_yaml(root, head, INTEGRATION_PROVENANCE_PATH) or {}
    for entry in provenance.get("squash_integrations", []) or []:
        if not isinstance(entry, dict):
            continue
        # T11 proves historical materialization, not evidence qualification. An exact
        # tree-equivalent squash may therefore recover the source-side first status for
        # any record present in that exact tree. T7/T9 separately keep eligible_*_ids
        # as the allowlist for whether a review/test may qualify as acceptance evidence.
        source_head = str(entry.get("source_head_sha") or "")
        integrated = str(entry.get("integrated_commit_sha") or "")
        expected_tree = str(entry.get("expected_tree_sha") or "")
        if not all(cg.FULL_COMMIT_SHA.fullmatch(value) for value in (expected_import, source_head, integrated, expected_tree)):
            continue
        if entry.get("historical_only") is not True or entry.get("future_reuse_forbidden") is not True:
            continue
        if current_first != integrated or not cg.is_ancestor(root, integrated, head):
            continue
        if first_status_commit_full_history(root, path, str(record.get("status") or ""), source_head) != expected_import:
            continue
        if not cg.is_ancestor(root, expected_import, source_head):
            continue
        if _tree_sha(root, source_head) != expected_tree or _tree_sha(root, integrated) != expected_tree:
            continue
        return True
    return False


def validate_ambiguous_import_materialization_history(root: Path, head: str) -> list[Finding]:
    out: list[Finding] = []
    for directory in ("reviews", "tests"):
        terminal_status = TERMINAL_IMPORT_STATUS[directory]
        for path in _registry_paths(root, head, directory):
            record = cg.show_yaml(root, head, path) or {}
            ext = record.get("external_import")
            raw_import = ext.get("import_commit") if isinstance(ext, dict) else None
            if record.get("status") != terminal_status or not isinstance(raw_import, str) or not cg.FULL_COMMIT_SHA.fullmatch(raw_import):
                continue
            boundaries = first_status_boundaries_full_history(root, path, terminal_status, head)
            if len(boundaries) > 1:
                out.append(
                    Finding(
                        path,
                        "IMPORT_FIRST_STATUS_AMBIGUOUS",
                        f"full merge history contains multiple independent first materializations of status {terminal_status!r}: {boundaries}",
                    )
                )
    return out


def validate_import_materialization_history(root: Path, head: str) -> list[Finding]:
    # Keep ambiguity rejection inside the import validator so callers cannot exercise
    # terminal import qualification while accidentally skipping the parallel-history
    # invariant. Unit tests that replace this whole validator remain isolated.
    out: list[Finding] = list(validate_ambiguous_import_materialization_history(root, head))
    for directory in ("reviews", "tests"):
        terminal_status = TERMINAL_IMPORT_STATUS[directory]
        for path in _registry_paths(root, head, directory):
            record = cg.show_yaml(root, head, path) or {}
            ext = record.get("external_import")
            if not isinstance(ext, dict) or record.get("status") != terminal_status:
                continue
            raw_import = ext.get("import_commit")
            if not raw_import:
                # Presence of external_import is itself an external-import claim.
                # Empty metadata is therefore unfinalized rather than equivalent to
                # absence; otherwise orphan COMPLETE/PASS records can bypass binding.
                out.append(
                    Finding(
                        path,
                        "IMPORT_TERMINAL_UNFINALIZED",
                        f"externally imported terminal {directory[:-1]} at status {terminal_status!r} must bind import_commit before it may remain at HEAD",
                    )
                )
                continue
            expected = str(raw_import)
            actual = first_status_commit_full_history(root, path, terminal_status, head)
            if actual == expected or squash_bridge_allows_first_status(root, path, record, expected, actual, head, directory):
                continue
            out.append(
                Finding(
                    path,
                    "IMPORT_FIRST_STATUS_FULL_HISTORY",
                    f"external import binds import_commit={expected!r}, but full merge history first materializes status {terminal_status!r} at {actual!r}",
                )
            )
    return out


def changed_blob_paths(root: Path, before: str, after: str) -> list[str]:
    return [
        line
        for line in cg.git(root, "diff", "--name-only", "--diff-filter=ACMR", before, after).splitlines()
        if line
    ]


def blob_size(root: Path, sha: str, path: str) -> int:
    raw = cg.git(root, "cat-file", "-s", f"{sha}:{path}").strip()
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"invalid blob size for {sha}:{path}: {raw!r}") from exc


def blob_bytes(root: Path, sha: str, path: str) -> bytes:
    proc = subprocess.run(
        ["git", "show", f"{sha}:{path}"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if proc.returncode:
        raise RuntimeError(proc.stderr.decode(errors="replace").strip() or f"cannot read blob {sha}:{path}")
    return proc.stdout


def validate_secret_history_blobs(root: Path, base: str, head: str) -> list[Finding]:
    out: list[Finding] = []
    _, edges = cg.pr_commit_edges(root, base, head, require_guard=False)
    for before, after in edges:
        for path in changed_blob_paths(root, before, after):
            size = blob_size(root, after, path)
            if size > MAX_SECRET_BLOB_BYTES:
                out.append(
                    Finding(
                        path,
                        "SECRET_HISTORY_UNSCANNED_BLOB",
                        f"changed blob at {after[:12]} is {size} bytes, above the {MAX_SECRET_BLOB_BYTES}-byte fail-closed secret-scan bound",
                    )
                )
                continue
            text = blob_bytes(root, after, path).decode("latin-1")
            if any(pattern.search(text) for pattern in cg.SECRET_PATTERNS):
                out.append(
                    Finding(
                        path,
                        "SECRET_HISTORY_BLOB",
                        f"high-confidence secret/private-key pattern exists in changed blob at {after[:12]}",
                    )
                )
    return out


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    except (OSError, yaml.YAMLError) as exc:
        raise RuntimeError(f"cannot parse {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"{path} must contain a YAML mapping")
    return data


def _event_types(on: dict[str, Any], event: str) -> set[str]:
    spec = on.get(event)
    if not isinstance(spec, dict):
        return set()
    values = spec.get("types")
    if not isinstance(values, list):
        return set()
    return {str(value) for value in values}


def _logical_run_commands(job: dict[str, Any]) -> list[list[str]]:
    steps = job.get("steps")
    if not isinstance(steps, list):
        return []
    commands: list[list[str]] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        run = step.get("run")
        if not isinstance(run, str):
            continue
        logical = ""
        for raw_line in run.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            continued = line.endswith("\\")
            piece = line[:-1].rstrip() if continued else line
            logical = f"{logical} {piece}".strip()
            if continued:
                continue
            try:
                commands.append(shlex.split(logical, posix=True))
            except ValueError:
                commands.append([])
            logical = ""
        if logical:
            try:
                commands.append(shlex.split(logical, posix=True))
            except ValueError:
                commands.append([])
    return commands


_FAILURE_MASKING_SHELL_FRAGMENTS = ("||", "&&", "&", ";", "|", ">", "<", "`", "$(")
_DANGEROUS_STEP_ENV_KEYS = {
    "PATH",
    "PYTHONPATH",
    "PYTHONHOME",
    "BASH_ENV",
    "ENV",
    "SHELLOPTS",
}


def _run_step_has_failure_masking_shell(run: str) -> bool:
    if any(fragment in run for fragment in _FAILURE_MASKING_SHELL_FRAGMENTS):
        return True
    for raw_line in run.splitlines():
        line = raw_line.strip()
        if line.startswith("set ") and (
            "+e" in line.split()
            or ("+o" in line.split() and "errexit" in line.split())
        ):
            return True
    return False


def _run_step_can_shadow_executable(run: str, executable: str) -> bool:
    name = re.escape(executable)
    function_keyword = re.compile(
        rf"^function\s+{name}(?:\s*\(\s*\))?(?=\s|$|\{{|\()"
    )
    paren_decl = re.compile(rf"^{name}\s*\(\s*\)(?=\s|$|\{{|\()")
    alias_decl = re.compile(rf"^alias\s+{name}\s*=")
    for raw_line in run.splitlines():
        line = raw_line.strip()
        if function_keyword.match(line) or paren_decl.match(line) or alias_decl.match(line):
            return True
        if line.startswith(("source ", ". ", "eval ")) and executable in run:
            return True
        if line.startswith("hash ") and executable in line:
            return True
    return False


def _exact_environment_safe(
    env: Any,
    required_env: dict[str, Any] | None = None,
) -> bool:
    if required_env is None:
        return env in (None, {})
    return isinstance(env, dict) and env == required_env


def _exact_permissions_safe(
    container: dict[str, Any],
    required_permissions: dict[str, Any] | None = None,
) -> bool:
    if required_permissions is None:
        return "permissions" not in container
    actual = container.get("permissions")
    return isinstance(actual, dict) and actual == required_permissions


def _container_execution_defaults_safe(container: dict[str, Any]) -> bool:
    if not _exact_environment_safe(container.get("env")):
        return False

    defaults = container.get("defaults")
    if defaults is not None:
        if not isinstance(defaults, dict):
            return False
        run_defaults = defaults.get("run")
        if run_defaults is not None:
            if not isinstance(run_defaults, dict):
                return False
            if "shell" in run_defaults or "working-directory" in run_defaults:
                return False
    return True


def _inherited_execution_controls_safe(
    workflow: dict[str, Any] | None,
    job: dict[str, Any],
) -> bool:
    if "container" in job:
        return False
    return _container_execution_defaults_safe(workflow or {}) and _container_execution_defaults_safe(job)


def _trusted_job_execution_substrate_safe(
    job: dict[str, Any],
    required_permissions: dict[str, Any] | None = None,
) -> bool:
    runner = job.get("runs-on")
    if runner is not None and runner != TRUSTED_RUNNER:
        return False
    if "services" in job:
        return False
    return _exact_permissions_safe(job, required_permissions)


def _execution_controls_safe(
    job: dict[str, Any],
    step: dict[str, Any],
    allowed_job_ifs: frozenset[str],
    allowed_step_ifs: frozenset[str],
    required_env: dict[str, Any] | None = None,
) -> bool:
    if job.get("continue-on-error") not in (None, False):
        return False
    job_if = job.get("if")
    if job_if is not None and (
        not isinstance(job_if, str) or job_if not in allowed_job_ifs
    ):
        return False

    if step.get("continue-on-error") not in (None, False):
        return False
    step_if = step.get("if")
    if step_if is not None and (
        not isinstance(step_if, str) or step_if not in allowed_step_ifs
    ):
        return False
    if "shell" in step or "working-directory" in step:
        return False
    if not _exact_environment_safe(step.get("env"), required_env):
        return False
    return True


def _steps_use_action(
    job: dict[str, Any],
    expected_use: str,
    *,
    workflow: dict[str, Any] | None = None,
    allowed_job_ifs: frozenset[str] = frozenset(),
    allowed_step_ifs: frozenset[str] = frozenset(),
    required_with: dict[str, Any] | None = None,
    required_env: dict[str, Any] | None = None,
    after_index: int | None = None,
) -> bool:
    if not _inherited_execution_controls_safe(workflow, job):
        return False
    steps = job.get("steps")
    if not isinstance(steps, list):
        return False
    expected_with = required_with or {}
    for index, step in enumerate(steps):
        if after_index is not None and index <= after_index:
            continue
        if not isinstance(step, dict) or step.get("uses") != expected_use:
            continue
        if not _execution_controls_safe(
            job,
            step,
            allowed_job_ifs,
            allowed_step_ifs,
            required_env,
        ):
            continue
        actual_with = step.get("with")
        normalized_with = {} if actual_with is None else actual_with
        if not isinstance(normalized_with, dict) or normalized_with != expected_with:
            continue
        return True
    return False


def _dependency_probe_index(workflow: dict[str, Any], job: dict[str, Any]) -> int | None:
    if not _inherited_execution_controls_safe(workflow, job):
        return None
    if job.get("continue-on-error") not in (None, False):
        return None
    steps = job.get("steps")
    if not isinstance(steps, list):
        return None
    for index, step in enumerate(steps):
        if not isinstance(step, dict) or step.get("id") != "depgraph":
            continue
        if step.get("continue-on-error") not in (None, False) or step.get("if") is not None:
            continue
        if step.get("shell") != "bash" or "working-directory" in step:
            continue
        if step.get("env") != {"GH_TOKEN": "${{ github.token }}"}:
            continue
        run = step.get("run")
        if not isinstance(run, str) or run != DEPENDENCY_PROBE_RUN:
            continue
        return index
    return None


def _dependency_probe_safe(workflow: dict[str, Any], job: dict[str, Any]) -> bool:
    return _dependency_probe_index(workflow, job) is not None


def _steps_execute_prefix(
    job: dict[str, Any],
    expected: tuple[str, ...],
    *,
    workflow: dict[str, Any] | None = None,
    allowed_job_ifs: frozenset[str] = frozenset(),
    allowed_step_ifs: frozenset[str] = frozenset(),
    required_env: dict[str, Any] | None = None,
) -> bool:
    if not _inherited_execution_controls_safe(workflow, job):
        return False
    steps = job.get("steps")
    if not isinstance(steps, list):
        return False
    for step in steps:
        if not isinstance(step, dict):
            continue
        if not _execution_controls_safe(
            job,
            step,
            allowed_job_ifs,
            allowed_step_ifs,
            required_env,
        ):
            continue
        run = step.get("run")
        if not isinstance(run, str) or _run_step_has_failure_masking_shell(run):
            continue
        executable = next((token for token in expected if "=" not in token), expected[0])
        if _run_step_can_shadow_executable(run, executable):
            continue
        commands = _logical_run_commands({"steps": [step]})
        if commands == [list(expected)]:
            return True
    return False


def _single_step_job(job: dict[str, Any], index: int) -> dict[str, Any]:
    steps = job.get("steps")
    narrowed = dict(job)
    if not isinstance(steps, list) or index < 0 or index >= len(steps):
        narrowed["steps"] = []
        return narrowed
    narrowed["steps"] = [steps[index]]
    return narrowed


def _trusted_prefix(checks: Iterable[bool]) -> bool:
    return all(checks)


def _action_at(
    job: dict[str, Any],
    index: int,
    expected_use: str,
    *,
    workflow: dict[str, Any] | None = None,
    allowed_job_ifs: frozenset[str] = frozenset(),
    allowed_step_ifs: frozenset[str] = frozenset(),
    required_with: dict[str, Any] | None = None,
    required_env: dict[str, Any] | None = None,
) -> bool:
    return _steps_use_action(
        _single_step_job(job, index),
        expected_use,
        workflow=workflow,
        allowed_job_ifs=allowed_job_ifs,
        allowed_step_ifs=allowed_step_ifs,
        required_with=required_with,
        required_env=required_env,
    )


def _command_at(
    job: dict[str, Any],
    index: int,
    expected: tuple[str, ...],
    *,
    workflow: dict[str, Any] | None = None,
    allowed_job_ifs: frozenset[str] = frozenset(),
    allowed_step_ifs: frozenset[str] = frozenset(),
    required_env: dict[str, Any] | None = None,
) -> bool:
    return _steps_execute_prefix(
        _single_step_job(job, index),
        expected,
        workflow=workflow,
        allowed_job_ifs=allowed_job_ifs,
        allowed_step_ifs=allowed_step_ifs,
        required_env=required_env,
    )


def _exact_run_at(
    job: dict[str, Any],
    index: int,
    expected_run: str,
    *,
    workflow: dict[str, Any] | None = None,
    allowed_job_ifs: frozenset[str] = frozenset(),
    required_shell: str | None = None,
    required_env: dict[str, Any] | None = None,
) -> bool:
    if not _inherited_execution_controls_safe(workflow, job):
        return False
    narrowed = _single_step_job(job, index)
    steps = narrowed.get("steps")
    if not isinstance(steps, list) or len(steps) != 1 or not isinstance(steps[0], dict):
        return False
    step = steps[0]
    if narrowed.get("continue-on-error") not in (None, False):
        return False
    job_if = narrowed.get("if")
    if job_if is not None and (
        not isinstance(job_if, str) or job_if not in allowed_job_ifs
    ):
        return False
    if step.get("continue-on-error") not in (None, False) or step.get("if") is not None:
        return False
    if "working-directory" in step:
        return False
    if required_shell is None:
        if "shell" in step:
            return False
    elif step.get("shell") != required_shell:
        return False
    if not _exact_environment_safe(step.get("env"), required_env):
        return False
    return step.get("run") == expected_run


def _poll_trusted_prefix(workflow: dict[str, Any], poll: dict[str, Any]) -> bool:
    if not _trusted_job_execution_substrate_safe(poll, POLL_PERMISSIONS):
        return False
    job_ifs = frozenset({"github.event_name == 'schedule'"})
    return _trusted_prefix(
        (
            _action_at(
                poll,
                0,
                CHECKOUT_ACTION,
                workflow=workflow,
                allowed_job_ifs=job_ifs,
                required_with={"persist-credentials": "false"},
            ),
            _action_at(
                poll,
                1,
                SETUP_PYTHON_ACTION,
                workflow=workflow,
                allowed_job_ifs=job_ifs,
                required_with={
                    "python-version": "3.13.15",
                    "cache": "pip",
                    "cache-dependency-path": "requirements/governance-ci.txt",
                },
            ),
            _command_at(
                poll,
                2,
                ("python", "-m", "pip", "install", "--require-hashes", "-r", "requirements/governance-ci.txt"),
                workflow=workflow,
                allowed_job_ifs=job_ifs,
            ),
            _command_at(
                poll,
                3,
                ("python", "-m", "tools.governance.thread_state_poll"),
                workflow=workflow,
                allowed_job_ifs=job_ifs,
                required_env={"GITHUB_TOKEN": "${{ github.token }}"},
            ),
        )
    )


def _exact_needs(job: dict[str, Any], required: frozenset[str]) -> bool:
    raw = job.get("needs")
    if isinstance(raw, str):
        items = [raw]
    elif isinstance(raw, list) and all(isinstance(item, str) for item in raw):
        items = raw
    else:
        return False
    return len(items) == len(required) and set(items) == set(required)


def _candidate_test_prefix(core: dict[str, Any], job: dict[str, Any]) -> bool:
    if not _trusted_job_execution_substrate_safe(job, None):
        return False
    checks: list[bool] = [
        _action_at(
            job,
            0,
            CHECKOUT_ACTION,
            workflow=core,
            required_with={"ref": CORE_INPUT_HEAD_EXPR, "fetch-depth": "0", "persist-credentials": "false"},
        ),
        _action_at(
            job,
            1,
            SETUP_PYTHON_ACTION,
            workflow=core,
            required_with=CANDIDATE_SETUP_PYTHON_WITH,
        ),
        _command_at(
            job,
            2,
            ("python", "-m", "pip", "install", "--require-hashes", "-r", "requirements/governance-ci.txt"),
            workflow=core,
        ),
        _command_at(job, 3, CANDIDATE_PYTEST_COMMAND, workflow=core),
    ]
    for offset, expected in enumerate(CANDIDATE_MUTATION_COMMANDS, start=4):
        checks.append(_command_at(job, offset, expected, workflow=core))
    return _trusted_prefix(checks)


def _job_contains_candidate_execution(job: dict[str, Any]) -> bool:
    for command in _logical_run_commands(job):
        if len(command) >= 3 and command[:3] == ["python", "-m", "pytest"]:
            return True
        if len(command) >= 2 and command[0] == "python" and command[1] in CANDIDATE_MUTATION_SCRIPT_PATHS:
            return True
    return False


def _core_trusted_prefix(core: dict[str, Any], validate: dict[str, Any]) -> bool:
    if not _trusted_job_execution_substrate_safe(validate, None):
        return False
    if _job_contains_candidate_execution(validate):
        return False
    checks: list[bool] = [
        _action_at(
            validate,
            0,
            CHECKOUT_ACTION,
            workflow=core,
            required_with={"ref": CORE_INPUT_HEAD_EXPR, "fetch-depth": "0", "persist-credentials": "false"},
        ),
        _action_at(
            validate,
            1,
            SETUP_PYTHON_ACTION,
            workflow=core,
            required_with=TRUSTED_VALIDATE_SETUP_PYTHON_WITH,
        ),
    ]
    for rule, expected, allowed_step_ifs in REQUIRED_CORE_COMMANDS:
        checks.append(
            _command_at(
                validate,
                CORE_REQUIRED_STEP_INDEXES[rule],
                expected,
                workflow=core,
                allowed_step_ifs=allowed_step_ifs,
            )
        )
    checks.append(
        _command_at(
            validate,
            13,
            ("python", "-m", "tools.governance.t11_closure", ".", "--base", CORE_INPUT_BASE_EXPR, "--head", CORE_INPUT_HEAD_EXPR, "--json-out", "t11-closure-findings.json"),
            workflow=core,
            allowed_step_ifs=frozenset({CORE_PR_IF}),
        )
    )
    return _trusted_prefix(checks)


def _dependency_review_trusted_prefix(
    workflow: dict[str, Any],
    job: dict[str, Any],
) -> bool:
    if not _trusted_job_execution_substrate_safe(job, DEPENDENCY_REVIEW_PERMISSIONS):
        return False
    job_ifs = frozenset({PR_EVENT_IF})
    return _trusted_prefix(
        (
            _dependency_probe_safe(workflow, _single_step_job(job, 0)),
            _action_at(
                job,
                1,
                DEPENDENCY_REVIEW_ACTION,
                workflow=workflow,
                allowed_job_ifs=job_ifs,
                allowed_step_ifs=frozenset({"steps.depgraph.outputs.supported == 'true'"}),
                required_with={"fail-on-severity": "moderate"},
            ),
        )
    )


def _codeql_trusted_prefix(workflow: dict[str, Any], job: dict[str, Any]) -> bool:
    if not _trusted_job_execution_substrate_safe(job, CODEQL_PERMISSIONS):
        return False
    job_ifs = frozenset({CODEQL_JOB_IF})
    return _trusted_prefix(
        (
            _action_at(
                job,
                0,
                CHECKOUT_ACTION,
                workflow=workflow,
                allowed_job_ifs=job_ifs,
                required_with={"ref": CODEQL_HEAD_EXPR, "persist-credentials": "false"},
            ),
            _action_at(
                job,
                1,
                CODEQL_INIT_ACTION,
                workflow=workflow,
                allowed_job_ifs=job_ifs,
                required_with={"languages": "python"},
            ),
            _action_at(
                job,
                2,
                CODEQL_ANALYZE_ACTION,
                workflow=workflow,
                allowed_job_ifs=job_ifs,
            ),
        )
    )


def _final_gate_trusted_prefix(workflow: dict[str, Any], job: dict[str, Any]) -> bool:
    if not _trusted_job_execution_substrate_safe(job, FINAL_GATE_PERMISSIONS):
        return False
    job_ifs = frozenset({FINAL_GATE_IF})
    pr_ifs = frozenset({PR_EVENT_IF})
    return _trusted_prefix(
        (
            _exact_run_at(
                job,
                0,
                FINAL_GATE_LANE_RESULTS_RUN,
                workflow=workflow,
                allowed_job_ifs=job_ifs,
                required_shell="bash",
            ),
            _command_at(
                job,
                1,
                ("test", "${{ needs.governance-core.result }}", "=", "success"),
                workflow=workflow,
                allowed_job_ifs=job_ifs,
            ),
            _command_at(
                job,
                2,
                ("test", "${{ needs.codeql.result }}", "=", "success"),
                workflow=workflow,
                allowed_job_ifs=job_ifs,
            ),
            _command_at(
                job,
                3,
                ("test", "${{ needs.dependency-review.result }}", "=", "success"),
                workflow=workflow,
                allowed_job_ifs=job_ifs,
                allowed_step_ifs=pr_ifs,
            ),
            _action_at(
                job,
                4,
                CHECKOUT_ACTION,
                workflow=workflow,
                allowed_job_ifs=job_ifs,
                allowed_step_ifs=pr_ifs,
                required_with={"ref": FINAL_HEAD_EXPR, "persist-credentials": "false"},
            ),
            _command_at(
                job,
                5,
                ("python", "-m", "tools.governance.github_live_gate", "--repo", "${{ github.repository }}", "--pr", "${{ github.event.pull_request.number }}", "--head", FINAL_HEAD_EXPR, "--root", ".", "--json-out", "github-live-gate.json"),
                workflow=workflow,
                allowed_job_ifs=job_ifs,
                allowed_step_ifs=pr_ifs,
                required_env={"GITHUB_TOKEN": "${{ github.token }}"},
            ),
        )
    )


def _steps_contain_run(job: dict[str, Any], needle: str) -> bool:
    """Legacy helper retained for compatibility; security-sensitive wiring checks do not use it."""
    steps = job.get("steps")
    if not isinstance(steps, list):
        return False
    return any(isinstance(step, dict) and isinstance(step.get("run"), str) and needle in step["run"] for step in steps)


def validate_workflow_structure(root: Path) -> list[Finding]:
    workflow = _load_yaml_mapping(root / WORKFLOW_PATH)
    core = _load_yaml_mapping(root / CORE_WORKFLOW_PATH)
    out: list[Finding] = []

    on = workflow.get("on")
    if not isinstance(on, dict):
        return [Finding(WORKFLOW_PATH, "WORKFLOW_TRIGGER_STRUCTURE", "top-level on mapping is missing or malformed")]
    for event, expected in REQUIRED_EVENT_TYPES.items():
        actual = _event_types(on, event)
        if not expected.issubset(actual):
            out.append(
                Finding(
                    WORKFLOW_PATH,
                    "WORKFLOW_TRIGGER_STRUCTURE",
                    f"effective {event} types must include {sorted(expected)}; observed={sorted(actual)}",
                )
            )

    schedules = on.get("schedule")
    has_poll_schedule = isinstance(schedules, list) and any(
        isinstance(item, dict) and str(item.get("cron") or "") == POLL_CRON for item in schedules
    )
    if not has_poll_schedule:
        out.append(Finding(WORKFLOW_PATH, "REVIEW_THREAD_POLL_SCHEDULE", f"effective schedule must include cron {POLL_CRON!r}"))

    if not _exact_permissions_safe(workflow, WORKFLOW_PERMISSIONS):
        out.append(
            Finding(
                WORKFLOW_PATH,
                "WORKFLOW_PERMISSIONS",
                f"workflow permissions must equal the exact least-privilege mapping {WORKFLOW_PERMISSIONS!r}",
            )
        )
    if not _exact_permissions_safe(core, CORE_WORKFLOW_PERMISSIONS):
        out.append(
            Finding(
                CORE_WORKFLOW_PATH,
                "CORE_WORKFLOW_PERMISSIONS",
                f"reusable governance-core permissions must equal the exact least-privilege mapping {CORE_WORKFLOW_PERMISSIONS!r}",
            )
        )

    jobs = workflow.get("jobs")
    jobs = jobs if isinstance(jobs, dict) else {}
    if set(jobs) != WORKFLOW_JOB_IDS:
        out.append(
            Finding(
                WORKFLOW_PATH,
                "WORKFLOW_JOB_SET",
                f"workflow jobs must equal the reviewed canonical set {sorted(WORKFLOW_JOB_IDS)}; observed={sorted(jobs)}",
            )
        )

    governance_core = jobs.get("governance-core")
    if not isinstance(governance_core, dict):
        out.append(Finding(WORKFLOW_PATH, "CORE_CALL_JOB", "governance-core reusable-workflow job is missing"))
    else:
        expected_inputs = {
            "event_name": CORE_EVENT_EXPR,
            "base_sha": CORE_BASE_EXPR,
            "head_sha": CORE_HEAD_EXPR,
        }
        if str(governance_core.get("if") or "") != CODEQL_JOB_IF:
            out.append(Finding(WORKFLOW_PATH, "CORE_CALL_SCOPE", "governance-core reusable workflow must run for every non-schedule event"))
        if governance_core.get("uses") != CORE_WORKFLOW_USES:
            out.append(Finding(WORKFLOW_PATH, "CORE_CALL_USES", "governance-core must call the trusted local reusable workflow"))
        actual_inputs = governance_core.get("with")
        if not isinstance(actual_inputs, dict) or actual_inputs != expected_inputs:
            out.append(Finding(WORKFLOW_PATH, "CORE_CALL_INPUTS", "governance-core must bind event/base/head inputs to the exact current GitHub event expressions"))
        if not _exact_permissions_safe(governance_core, None):
            out.append(Finding(WORKFLOW_PATH, "CORE_CALL_PERMISSIONS", "governance-core caller must inherit the exact workflow permission boundary without a job-level override"))

    poll = jobs.get("review-thread-state-poll")
    if not isinstance(poll, dict):
        out.append(Finding(WORKFLOW_PATH, "REVIEW_THREAD_POLL_JOB", "review-thread-state-poll job is missing"))
    else:
        if not _exact_permissions_safe(poll, POLL_PERMISSIONS):
            out.append(Finding(WORKFLOW_PATH, "REVIEW_THREAD_POLL_PERMISSIONS", f"poll job permissions must equal the exact mapping {POLL_PERMISSIONS!r}"))
        if str(poll.get("if") or "") != "github.event_name == 'schedule'":
            out.append(Finding(WORKFLOW_PATH, "REVIEW_THREAD_POLL_SCOPE", "poll job must run only for schedule events"))
        if not _steps_execute_prefix(
            poll,
            ("python", "-m", "tools.governance.thread_state_poll"),
            workflow=workflow,
            allowed_job_ifs=frozenset({"github.event_name == 'schedule'"}),
            required_env={"GITHUB_TOKEN": "${{ github.token }}"},
        ):
            out.append(Finding(WORKFLOW_PATH, "REVIEW_THREAD_POLL_WIRING", "poll job must execute the trusted review-thread state poller"))

    core_jobs = core.get("jobs")
    core_jobs = core_jobs if isinstance(core_jobs, dict) else {}
    if set(core_jobs) != CORE_WORKFLOW_JOB_IDS:
        out.append(
            Finding(
                CORE_WORKFLOW_PATH,
                "CORE_JOB_SET",
                f"reusable governance-core jobs must equal {sorted(CORE_WORKFLOW_JOB_IDS)}; observed={sorted(core_jobs)}",
            )
        )

    candidate_tests = core_jobs.get("candidate-tests")
    if not isinstance(candidate_tests, dict):
        out.append(Finding(CORE_WORKFLOW_PATH, "CORE_CANDIDATE_TEST_JOB", "candidate-tests isolation job is missing"))
    else:
        if "needs" in candidate_tests:
            out.append(Finding(CORE_WORKFLOW_PATH, "CORE_CANDIDATE_TEST_NEEDS", "candidate-tests must start on its own fresh runner without depending on another workflow job"))
        if not _exact_permissions_safe(candidate_tests, None):
            out.append(Finding(CORE_WORKFLOW_PATH, "CORE_CANDIDATE_TEST_PERMISSIONS", "candidate-tests must inherit the exact reusable-workflow permission boundary without a job-level override"))
        if not _candidate_test_prefix(core, candidate_tests):
            out.append(Finding(CORE_WORKFLOW_PATH, "CORE_PYTEST_WIRING", "PR-controlled pytest must run only in the isolated candidate-tests job with the exact checkout/setup/toolchain/test prefix"))

    validate = core_jobs.get("validate")
    validate = validate if isinstance(validate, dict) else {}
    if not _exact_needs(validate, CORE_VALIDATE_NEEDS):
        out.append(Finding(CORE_WORKFLOW_PATH, "CORE_VALIDATE_NEEDS", f"trusted validate job must depend exactly on {sorted(CORE_VALIDATE_NEEDS)}"))

    if not _exact_permissions_safe(validate, None):
        out.append(Finding(CORE_WORKFLOW_PATH, "CORE_VALIDATE_PERMISSIONS", "governance-core validate job must inherit the exact reusable-workflow permission boundary without a job-level override"))

    if not _steps_use_action(
        validate,
        CHECKOUT_ACTION,
        workflow=core,
        required_with={"ref": CORE_INPUT_HEAD_EXPR, "fetch-depth": "0", "persist-credentials": "false"},
    ):
        out.append(Finding(CORE_WORKFLOW_PATH, "CORE_CHECKOUT_ACTION", "governance core must checkout the exact requested head with the pinned checkout action"))
    if not _steps_use_action(
        validate,
        SETUP_PYTHON_ACTION,
        workflow=core,
        required_with=TRUSTED_VALIDATE_SETUP_PYTHON_WITH,
    ):
        out.append(Finding(CORE_WORKFLOW_PATH, "CORE_SETUP_PYTHON_ACTION", "trusted governance validation must use pinned Python without restoring candidate-influenced dependency caches"))

    for rule, expected, allowed_step_ifs in REQUIRED_CORE_COMMANDS:
        if not _steps_execute_prefix(
            validate,
            expected,
            workflow=core,
            allowed_step_ifs=allowed_step_ifs,
        ):
            out.append(
                Finding(
                    CORE_WORKFLOW_PATH,
                    rule,
                    f"governance core must execute required exact blocking command {list(expected)!r}",
                )
            )

    if not _steps_execute_prefix(
        validate,
        ("python", "-m", "tools.governance.t11_closure", ".", "--base", CORE_INPUT_BASE_EXPR, "--head", CORE_INPUT_HEAD_EXPR, "--json-out", "t11-closure-findings.json"),
        workflow=core,
        allowed_step_ifs=frozenset({CORE_PR_IF}),
    ):
        out.append(Finding(CORE_WORKFLOW_PATH, "T11_GATE_WIRING", "governance core must execute the T11 closure validator"))
    if isinstance(candidate_tests, dict) and not _steps_execute_prefix(
        candidate_tests,
        ("python", ".github/scripts/governance_t11_mutation_smoke.py"),
        workflow=core,
    ):
        out.append(Finding(CORE_WORKFLOW_PATH, "T11_MUTATION_WIRING", "isolated candidate-tests must execute the T11 mutation smoke"))
    if _job_contains_candidate_execution(validate):
        out.append(Finding(CORE_WORKFLOW_PATH, "CORE_VALIDATE_CANDIDATE_EXECUTION", "trusted validate job must not execute pytest or any candidate mutation smoke"))

    dependency_review = jobs.get("dependency-review")
    if not isinstance(dependency_review, dict):
        out.append(Finding(WORKFLOW_PATH, "DEPENDENCY_REVIEW_JOB", "dependency-review job is missing"))
    else:
        if not _exact_permissions_safe(dependency_review, DEPENDENCY_REVIEW_PERMISSIONS):
            out.append(Finding(WORKFLOW_PATH, "DEPENDENCY_REVIEW_PERMISSIONS", f"dependency-review permissions must equal the exact mapping {DEPENDENCY_REVIEW_PERMISSIONS!r}"))
        if str(dependency_review.get("if") or "") != PR_EVENT_IF:
            out.append(
                Finding(
                    WORKFLOW_PATH,
                    "DEPENDENCY_REVIEW_SCOPE",
                    "dependency-review job must run for every pull-request-family event",
                )
            )
        probe_index = _dependency_probe_index(workflow, dependency_review)
        if probe_index is None:
            out.append(
                Finding(
                    WORKFLOW_PATH,
                    "DEPENDENCY_REVIEW_PROBE",
                    "dependency-review capability condition must be produced by the exact fail-closed Dependency Graph probe",
                )
            )
        if not _steps_use_action(
            dependency_review,
            DEPENDENCY_REVIEW_ACTION,
            workflow=workflow,
            allowed_job_ifs=frozenset({PR_EVENT_IF}),
            allowed_step_ifs=frozenset({"steps.depgraph.outputs.supported == 'true'"}),
            required_with={"fail-on-severity": "moderate"},
            after_index=probe_index,
        ):
            out.append(
                Finding(
                    WORKFLOW_PATH,
                    "DEPENDENCY_REVIEW_ACTION",
                    "dependency-review job must execute the pinned Dependency Review action after the exact fail-closed capability producer under the expected supported-capability condition",
                )
            )

    codeql = jobs.get("codeql")
    if not isinstance(codeql, dict):
        out.append(Finding(WORKFLOW_PATH, "CODEQL_JOB", "codeql job is missing"))
    else:
        if not _exact_permissions_safe(codeql, CODEQL_PERMISSIONS):
            out.append(Finding(WORKFLOW_PATH, "CODEQL_PERMISSIONS", f"CodeQL permissions must equal the exact mapping {CODEQL_PERMISSIONS!r}"))
        if str(codeql.get("if") or "") != CODEQL_JOB_IF:
            out.append(Finding(WORKFLOW_PATH, "CODEQL_SCOPE", "codeql job must run for every non-schedule event"))
        codeql_job_ifs = frozenset({CODEQL_JOB_IF})
        if not _steps_use_action(
            codeql,
            CHECKOUT_ACTION,
            workflow=workflow,
            allowed_job_ifs=codeql_job_ifs,
            required_with={"ref": CODEQL_HEAD_EXPR, "persist-credentials": "false"},
        ):
            out.append(Finding(WORKFLOW_PATH, "CODEQL_CHECKOUT_ACTION", "codeql must checkout the exact event head with the pinned checkout action"))
        if not _steps_use_action(
            codeql,
            CODEQL_INIT_ACTION,
            workflow=workflow,
            allowed_job_ifs=codeql_job_ifs,
            required_with={"languages": "python"},
        ):
            out.append(Finding(WORKFLOW_PATH, "CODEQL_INIT_ACTION", "codeql job must execute the pinned CodeQL init action for Python"))
        if not _steps_use_action(
            codeql,
            CODEQL_ANALYZE_ACTION,
            workflow=workflow,
            allowed_job_ifs=codeql_job_ifs,
        ):
            out.append(Finding(WORKFLOW_PATH, "CODEQL_ANALYZE_ACTION", "codeql job must execute the pinned CodeQL analyze action"))

    final_gate = jobs.get("final-gate")
    if not isinstance(final_gate, dict):
        out.append(Finding(WORKFLOW_PATH, "FINAL_GATE_JOB", "final-gate job is missing"))
    else:
        if not _exact_permissions_safe(final_gate, FINAL_GATE_PERMISSIONS):
            out.append(Finding(WORKFLOW_PATH, "FINAL_GATE_PERMISSIONS", f"final-gate permissions must equal the exact mapping {FINAL_GATE_PERMISSIONS!r}"))
        if str(final_gate.get("if") or "") != FINAL_GATE_IF:
            out.append(Finding(WORKFLOW_PATH, "FINAL_GATE_SCOPE", "final-gate must run for every non-schedule event"))
        if not _exact_needs(final_gate, FINAL_GATE_NEEDS):
            needs = final_gate.get("needs")
            observed_needs = (
                [needs] if isinstance(needs, str)
                else needs if isinstance(needs, list)
                else []
            )
            out.append(
                Finding(
                    WORKFLOW_PATH,
                    "FINAL_GATE_NEEDS",
                    f"final-gate needs must equal {sorted(FINAL_GATE_NEEDS)}; observed={observed_needs}",
                )
            )
        final_job_ifs = frozenset({FINAL_GATE_IF})
        if not _steps_execute_prefix(
            final_gate,
            ("test", "${{ needs.governance-core.result }}", "=", "success"),
            workflow=workflow,
            allowed_job_ifs=final_job_ifs,
        ):
            out.append(Finding(WORKFLOW_PATH, "GOVERNANCE_CORE_REQUIRED", "final gate must explicitly require governance-core success"))
        if not _steps_execute_prefix(
            final_gate,
            ("test", "${{ needs.codeql.result }}", "=", "success"),
            workflow=workflow,
            allowed_job_ifs=final_job_ifs,
        ):
            out.append(Finding(WORKFLOW_PATH, "CODEQL_REQUIRED", "final gate must explicitly require codeql success"))
        if not _steps_execute_prefix(
            final_gate,
            ("test", "${{ needs.dependency-review.result }}", "=", "success"),
            workflow=workflow,
            allowed_job_ifs=final_job_ifs,
            allowed_step_ifs=frozenset({PR_EVENT_IF}),
        ):
            out.append(
                Finding(
                    WORKFLOW_PATH,
                    "DEPENDENCY_REVIEW_REQUIRED",
                    "pull-request-family final gate must explicitly require dependency-review success",
                )
            )
        if not _steps_use_action(
            final_gate,
            CHECKOUT_ACTION,
            workflow=workflow,
            allowed_job_ifs=final_job_ifs,
            allowed_step_ifs=frozenset({PR_EVENT_IF}),
            required_with={"ref": FINAL_HEAD_EXPR, "persist-credentials": "false"},
        ):
            out.append(Finding(WORKFLOW_PATH, "FINAL_GATE_CHECKOUT_ACTION", "final gate must checkout the exact current PR head with the pinned checkout action"))
        if not _steps_execute_prefix(
            final_gate,
            ("python", "-m", "tools.governance.github_live_gate", "--repo", "${{ github.repository }}", "--pr", "${{ github.event.pull_request.number }}", "--head", FINAL_HEAD_EXPR, "--root", ".", "--json-out", "github-live-gate.json"),
            workflow=workflow,
            allowed_job_ifs=final_job_ifs,
            allowed_step_ifs=frozenset({PR_EVENT_IF}),
            required_env={"GITHUB_TOKEN": "${{ github.token }}"},
        ):
            out.append(Finding(WORKFLOW_PATH, "FINAL_GATE_LIVE_WIRING", "final gate must execute the blocking live GitHub state validator"))

    if isinstance(poll, dict) and not _poll_trusted_prefix(workflow, poll):
        out.append(Finding(WORKFLOW_PATH, "REVIEW_THREAD_POLL_TRUSTED_PREFIX", "poll job sensitive command must be preceded only by the canonical checkout/setup/toolchain prefix"))
    if isinstance(validate, dict) and not _core_trusted_prefix(core, validate):
        out.append(Finding(CORE_WORKFLOW_PATH, "CORE_TRUSTED_PREFIX", "governance core sensitive commands must remain in the exact canonical trusted predecessor order"))
    if isinstance(dependency_review, dict) and not _dependency_review_trusted_prefix(workflow, dependency_review):
        out.append(Finding(WORKFLOW_PATH, "DEPENDENCY_REVIEW_TRUSTED_PREFIX", "Dependency Review consumer must have only the exact fail-closed producer as its predecessor"))
    if isinstance(codeql, dict) and not _codeql_trusted_prefix(workflow, codeql):
        out.append(Finding(WORKFLOW_PATH, "CODEQL_TRUSTED_PREFIX", "CodeQL actions must remain in the exact checkout/init/analyze trusted order"))
    if isinstance(final_gate, dict) and not _final_gate_trusted_prefix(workflow, final_gate):
        out.append(Finding(WORKFLOW_PATH, "FINAL_GATE_TRUSTED_PREFIX", "final-gate live validation must remain behind the exact canonical lane-check/checkout predecessor sequence"))
    return out


def run(root: Path, base: str, head: str) -> list[Finding]:
    root = root.resolve()
    out: list[Finding] = []
    out.extend(validate_provenance_bootstrap(root, base, head))
    out.extend(validate_import_materialization_history(root, head))
    out.extend(validate_secret_history_blobs(root, base, head))
    out.extend(validate_workflow_structure(root))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--json-out")
    args = parser.parse_args(argv)
    try:
        findings = run(Path(args.root), args.base, args.head)
    except RuntimeError as exc:
        print(f"ERROR T11_CLOSURE {exc}", file=sys.stderr)
        return 2
    for finding in findings:
        print(finding.render(), file=sys.stderr)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps([asdict(item) for item in findings], indent=2), encoding="utf-8")
    print(f"MONDE T11 closure gate: {len(findings)} error(s)")
    return 1 if findings else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
