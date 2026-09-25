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

REQUIRED_CORE_COMMANDS = (
    ("CORE_TOOLCHAIN_WIRING", ("python", "-m", "pip", "install", "--require-hashes", "-r", "requirements/governance-ci.txt"), frozenset()),
    ("CORE_PYTEST_WIRING", ("python", "-m", "pytest"), frozenset()),
    ("CORE_BASE_MUTATION_WIRING", ("python", "scripts/governance_mutation_smoke.py"), frozenset()),
    ("CORE_L2_MUTATION_WIRING", ("python", ".github/scripts/governance_l2_mutation_smoke.py"), frozenset()),
    ("CORE_T10_MUTATION_WIRING", ("python", ".github/scripts/governance_t10_mutation_smoke.py"), frozenset()),
    ("CORE_T13_MUTATION_WIRING", ("python", ".github/scripts/governance_t13_mutation_smoke.py"), frozenset()),
    ("CORE_VALIDATE_REPO_WIRING", ("python", "-m", "tools.governance.validate_repo", "."), frozenset()),
    ("CORE_STRICT_CONTRACTS_WIRING", ("python", "-m", "tools.governance.strict_contracts", "."), frozenset()),
    ("CORE_PATH_SAFETY_WIRING", ("python", "-m", "tools.governance.path_safety", "."), frozenset()),
    ("CORE_CHANGE_GUARD_WIRING", ("python", "-m", "tools.governance.change_guard", "."), frozenset({CORE_PR_IF})),
    ("CORE_L2_GATE_WIRING", ("PYTHONPATH=$PWD:$PWD/.github/scripts", "python", ".github/scripts/governance_l2_gate.py", "."), frozenset({CORE_PR_IF})),
    ("CORE_REVIEW_CLOSURE_WIRING", ("python", "-m", "tools.governance.review_closure_gate", "."), frozenset({CORE_PR_IF})),
    ("CORE_T7_WIRING", ("python", "-m", "tools.governance.t7_closure", "."), frozenset({CORE_PR_IF})),
    ("CORE_T8_WIRING", ("python", "-m", "tools.governance.t8_closure", "."), frozenset({CORE_PR_IF})),
    ("CORE_T9_WIRING", ("python", "-m", "tools.governance.t9_closure", "."), frozenset({CORE_PR_IF})),
    ("CORE_T10_WIRING", ("python", "-m", "tools.governance.t10_closure", "."), frozenset({CORE_PR_IF})),
    ("CORE_CONTEXT_MANIFEST_WIRING", ("python", "-m", "tools.governance.context_manifest", "."), frozenset({CORE_PR_IF})),
)


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
    function_decl = re.compile(
        rf"^(?:function\s+)?{name}\s*(?:\(\s*\))?\s*\{{"
    )
    alias_decl = re.compile(rf"^alias\s+{name}\s*=")
    for raw_line in run.splitlines():
        line = raw_line.strip()
        if function_decl.match(line) or alias_decl.match(line):
            return True
        if line.startswith(("source ", ". ", "eval ")) and executable in run:
            return True
        if line.startswith("hash ") and executable in line:
            return True
    return False


def _container_execution_defaults_safe(container: dict[str, Any]) -> bool:
    env = container.get("env")
    if env is not None:
        if not isinstance(env, dict):
            return False
        if any(str(key).upper() in _DANGEROUS_STEP_ENV_KEYS for key in env):
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
    return _container_execution_defaults_safe(workflow or {}) and _container_execution_defaults_safe(job)


def _execution_controls_safe(
    job: dict[str, Any],
    step: dict[str, Any],
    allowed_job_ifs: frozenset[str],
    allowed_step_ifs: frozenset[str],
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
    env = step.get("env")
    if env is not None:
        if not isinstance(env, dict):
            return False
        if any(str(key).upper() in _DANGEROUS_STEP_ENV_KEYS for key in env):
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
) -> bool:
    if not _inherited_execution_controls_safe(workflow, job):
        return False
    steps = job.get("steps")
    if not isinstance(steps, list):
        return False
    expected_with = required_with or {}
    for step in steps:
        if not isinstance(step, dict) or step.get("uses") != expected_use:
            continue
        if not _execution_controls_safe(job, step, allowed_job_ifs, allowed_step_ifs):
            continue
        actual_with = step.get("with")
        if expected_with:
            if not isinstance(actual_with, dict):
                continue
            if any(actual_with.get(key) != value for key, value in expected_with.items()):
                continue
        return True
    return False


def _steps_execute_prefix(
    job: dict[str, Any],
    expected: tuple[str, ...],
    *,
    workflow: dict[str, Any] | None = None,
    allowed_job_ifs: frozenset[str] = frozenset(),
    allowed_step_ifs: frozenset[str] = frozenset(),
) -> bool:
    if not _inherited_execution_controls_safe(workflow, job):
        return False
    steps = job.get("steps")
    if not isinstance(steps, list):
        return False
    for step in steps:
        if not isinstance(step, dict):
            continue
        if not _execution_controls_safe(job, step, allowed_job_ifs, allowed_step_ifs):
            continue
        run = step.get("run")
        if not isinstance(run, str) or _run_step_has_failure_masking_shell(run):
            continue
        executable = next((token for token in expected if "=" not in token), expected[0])
        if _run_step_can_shadow_executable(run, executable):
            continue
        commands = _logical_run_commands({"steps": [step]})
        if any(tuple(command[: len(expected)]) == expected for command in commands):
            return True
    return False


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

    jobs = workflow.get("jobs")
    jobs = jobs if isinstance(jobs, dict) else {}
    poll = jobs.get("review-thread-state-poll")
    if not isinstance(poll, dict):
        out.append(Finding(WORKFLOW_PATH, "REVIEW_THREAD_POLL_JOB", "review-thread-state-poll job is missing"))
    else:
        permissions = poll.get("permissions")
        permissions = permissions if isinstance(permissions, dict) else {}
        if permissions.get("actions") != "write" or permissions.get("pull-requests") != "read" or permissions.get("contents") != "read":
            out.append(Finding(WORKFLOW_PATH, "REVIEW_THREAD_POLL_PERMISSIONS", "poll job requires actions:write plus pull-requests:read and contents:read"))
        if str(poll.get("if") or "") != "github.event_name == 'schedule'":
            out.append(Finding(WORKFLOW_PATH, "REVIEW_THREAD_POLL_SCOPE", "poll job must run only for schedule events"))
        if not _steps_execute_prefix(
            poll,
            ("python", "-m", "tools.governance.thread_state_poll"),
            workflow=workflow,
            allowed_job_ifs=frozenset({"github.event_name == 'schedule'"}),
        ):
            out.append(Finding(WORKFLOW_PATH, "REVIEW_THREAD_POLL_WIRING", "poll job must execute the trusted review-thread state poller"))

    core_jobs = core.get("jobs")
    core_jobs = core_jobs if isinstance(core_jobs, dict) else {}
    validate = core_jobs.get("validate")
    validate = validate if isinstance(validate, dict) else {}

    if not _steps_use_action(
        validate,
        CHECKOUT_ACTION,
        workflow=core,
        required_with={"persist-credentials": False},
    ):
        out.append(Finding(CORE_WORKFLOW_PATH, "CORE_CHECKOUT_ACTION", "governance core must checkout the exact requested head with the pinned checkout action"))
    if not _steps_use_action(
        validate,
        SETUP_PYTHON_ACTION,
        workflow=core,
        required_with={
            "python-version": "3.13.15",
            "cache": "pip",
            "cache-dependency-path": "requirements/governance-ci.txt",
        },
    ):
        out.append(Finding(CORE_WORKFLOW_PATH, "CORE_SETUP_PYTHON_ACTION", "governance core must use the pinned Python setup action and expected toolchain inputs"))

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
                    f"governance core must execute required blocking command prefix {list(expected)!r}",
                )
            )

    if not _steps_execute_prefix(
        validate,
        ("python", "-m", "tools.governance.t11_closure", "."),
        workflow=core,
        allowed_step_ifs=frozenset({CORE_PR_IF}),
    ):
        out.append(Finding(CORE_WORKFLOW_PATH, "T11_GATE_WIRING", "governance core must execute the T11 closure validator"))
    if not _steps_execute_prefix(
        validate,
        ("python", ".github/scripts/governance_t11_mutation_smoke.py"),
        workflow=core,
    ):
        out.append(Finding(CORE_WORKFLOW_PATH, "T11_MUTATION_WIRING", "governance core must execute the T11 mutation smoke"))

    dependency_review = jobs.get("dependency-review")
    if not isinstance(dependency_review, dict):
        out.append(Finding(WORKFLOW_PATH, "DEPENDENCY_REVIEW_JOB", "dependency-review job is missing"))
    else:
        if str(dependency_review.get("if") or "") != PR_EVENT_IF:
            out.append(
                Finding(
                    WORKFLOW_PATH,
                    "DEPENDENCY_REVIEW_SCOPE",
                    "dependency-review job must run for every pull-request-family event",
                )
            )
        if not _steps_use_action(
            dependency_review,
            DEPENDENCY_REVIEW_ACTION,
            workflow=workflow,
            allowed_job_ifs=frozenset({PR_EVENT_IF}),
            allowed_step_ifs=frozenset({"steps.depgraph.outputs.supported == 'true'"}),
            required_with={"fail-on-severity": "moderate"},
        ):
            out.append(
                Finding(
                    WORKFLOW_PATH,
                    "DEPENDENCY_REVIEW_ACTION",
                    "dependency-review job must execute the pinned Dependency Review action under the expected supported-capability condition",
                )
            )

    codeql = jobs.get("codeql")
    if not isinstance(codeql, dict):
        out.append(Finding(WORKFLOW_PATH, "CODEQL_JOB", "codeql job is missing"))
    else:
        if str(codeql.get("if") or "") != CODEQL_JOB_IF:
            out.append(Finding(WORKFLOW_PATH, "CODEQL_SCOPE", "codeql job must run for every non-schedule event"))
        codeql_job_ifs = frozenset({CODEQL_JOB_IF})
        if not _steps_use_action(
            codeql,
            CHECKOUT_ACTION,
            workflow=workflow,
            allowed_job_ifs=codeql_job_ifs,
            required_with={"persist-credentials": False},
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
        if str(final_gate.get("if") or "") != FINAL_GATE_IF:
            out.append(Finding(WORKFLOW_PATH, "FINAL_GATE_SCOPE", "final-gate must run for every non-schedule event"))
        needs = final_gate.get("needs")
        observed_needs = {str(item) for item in needs} if isinstance(needs, list) else set()
        required_needs = {"governance-core", "dependency-review", "codeql"}
        if not required_needs.issubset(observed_needs):
            out.append(
                Finding(
                    WORKFLOW_PATH,
                    "FINAL_GATE_NEEDS",
                    f"final-gate must depend on {sorted(required_needs)}; observed={sorted(observed_needs)}",
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
            required_with={"persist-credentials": False},
        ):
            out.append(Finding(WORKFLOW_PATH, "FINAL_GATE_CHECKOUT_ACTION", "final gate must checkout the exact current PR head with the pinned checkout action"))
        if not _steps_execute_prefix(
            final_gate,
            ("python", "-m", "tools.governance.github_live_gate"),
            workflow=workflow,
            allowed_job_ifs=final_job_ifs,
            allowed_step_ifs=frozenset({PR_EVENT_IF}),
        ):
            out.append(Finding(WORKFLOW_PATH, "FINAL_GATE_LIVE_WIRING", "final gate must execute the blocking live GitHub state validator"))
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
