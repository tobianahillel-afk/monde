from pathlib import Path
import sys

ROOT = Path(sys.argv[1])
MODE = sys.argv[2]
REVIEW_IMPORT_SHA = "f78d5575a94b49d90abb166003cf4520bf167d3a"
AUTHORIZATION_SHA = "4b15dc41c2489239d932827880f612d7ef55bbfa"
TARGET_SHA = "c12a5b55c89168f20c028c2964da16de6f95ac56"
SOURCE_ID = "github-actions-run:34793888383:attempt:1"
SOURCE_TIME = "2026-09-14T00:49:49.870683Z"
CONTEXT_ID = "github-actions:34793888383:1:test-0008-v2"
RUN_URL = "https://github.com/tobianahillel-afk/monde/actions/runs/34793888383"
JOB_ID = "103823151339"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, got {count}")
    return text.replace(old, new, 1)


def block(text: str, start_marker: str, end_marker: str) -> tuple[int, int, str]:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return start, end, text[start:end]


status_path = ROOT / "registry/status-machines.yaml"
test_path = ROOT / "registry/tests/TEST-0008.yaml"

if MODE == "consume-review":
    s = status_path.read_text(encoding="utf-8")
    a, b, chunk = block(s, "      - record_id: REVIEW-0027\n", "    external_import_rule:")
    chunk = replace_once(chunk, "        consumed_by_commit: null\n", f'        consumed_by_commit: "{REVIEW_IMPORT_SHA}"\n', "REVIEW-0027 consumption")
    s = s[:a] + chunk + s[b:]
    status_path.write_text(s, encoding="utf-8")

elif MODE == "import-test":
    t = test_path.read_text(encoding="utf-8")
    t = replace_once(t, "status: PLANNED\n", "status: PASS\n", "TEST-0008 status")
    t = replace_once(t, "  qualifies: false\n", "  qualifies: true\n", "qualifies")
    t = replace_once(t, "    kind: null\n    source_id: null\n    submitted_at: null\n", f'    kind: GITHUB_ACTIONS_COPILOT_CLI\n    source_id: "{SOURCE_ID}"\n    submitted_at: "{SOURCE_TIME}"\n', "source")
    t = replace_once(t, "    actor: null\n    context_id: null\n    independence_level: null\n    fresh_context: false\n    authoring_context_separated: false\n", f'    actor: "github-copilot-cli@1.0.83"\n    context_id: "{CONTEXT_ID}"\n    independence_level: L2\n    fresh_context: true\n    authoring_context_separated: true\n', "executor")
    if t.count("      status_at_read: null\n") != 3:
        raise SystemExit("expected three null requirement read statuses")
    t = t.replace("      status_at_read: null\n", "      status_at_read: PROPOSED\n")
    for key in [
        "understood_without_author_reasoning",
        "atomic_and_testable",
        "dependencies_and_conflicts_checked",
        "omissions_and_failure_modes_checked",
        "evidence_plan_sufficient",
    ]:
        t = replace_once(t, f"    {key}: null\n", f"    {key}: PASS\n", key)
    t = replace_once(t, "  all_required_outcomes_pass: false\n", "  all_required_outcomes_pass: true\n", "all outcomes")
    t = replace_once(
        t,
        "  completed_at: null\n\nexecution:\n",
        f'''  completed_at: "{SOURCE_TIME}"\n\nexternal_import:\n  authorization_source: "registry/status-machines.yaml@{AUTHORIZATION_SHA}#registry_machines.tests.external_execution_import_authorizations.TEST-0008"\n  import_commit: null\n\nexecution:\n''',
        "external import insertion",
    )
    t = replace_once(t, "  command_or_workflow: null\n", '  command_or_workflow: "GitHub Actions / TEST-0008 fresh-context L2 v2"\n', "workflow")
    t = replace_once(t, "  last_run_at: null\n", f'  last_run_at: "{SOURCE_TIME}"\n', "last run")
    t = replace_once(t, "  commit_sha: null\n", f'  commit_sha: "{TARGET_SHA}"\n', "execution sha")
    t = replace_once(t, "  result: null\n", "  result: PASS\n", "execution result")
    t = replace_once(
        t,
        "  evidence: []\n",
        f'''  evidence:\n    - "Workflow run {RUN_URL}"\n    - "Workflow job {JOB_ID} completed success and checked out exact target {TARGET_SHA}"\n    - "Independent deterministic YAML parse confirmed WORK-0001 IN_REVIEW / A3 / RUN-3 IN_REVIEW with completion gates false"\n    - "Independent RFC 8785/JCS recomputation matched REQ-0023/REQ-0024/REQ-0025 declared digests while all three were PROPOSED"\n    - "Fresh Copilot L2 returned PASS for all five required cold-read outcomes for each of the three requirements (15/15)"\n    - "Fresh Copilot L2 verified REVIEW-0026/F-1, F-2 and F-3 as PASS, found no material R1/R2/R3 finding and returned APPROVE_WITH_FOLLOWUP"\n    - "REVIEW-0027 durably imports the same source/context and exact requirement revisions"\n''',
        "evidence",
    )
    t = replace_once(
        t,
        "  executions: []\n",
        f'''  executions:\n    - commit_sha: "{TARGET_SHA}"\n      recorded_result: PASS\n      recorded_in_commit: null\n      validity: VALID\n      invalidated_by: null\n      reason: "Fresh-context GitHub Actions Copilot CLI L2 independently parsed the exact target, recomputed all three normative digests, recorded 15/15 required cold-read outcomes PASS, verified REVIEW-0026/F-1/F-2/F-3, and found no material R1/R2/R3 defect."\n''',
        "history execution",
    )
    test_path.write_text(t, encoding="utf-8")

elif MODE == "bind-test":
    if len(sys.argv) != 4:
        raise SystemExit("bind-test requires TEST import commit SHA")
    import_sha = sys.argv[3]
    if len(import_sha) != 40:
        raise SystemExit("invalid import SHA")
    t = test_path.read_text(encoding="utf-8")
    t = replace_once(t, "  import_commit: null\n", f'  import_commit: "{import_sha}"\n', "TEST external import binding")
    t = replace_once(t, "      recorded_in_commit: null\n", f'      recorded_in_commit: "{import_sha}"\n', "TEST execution binding")
    test_path.write_text(t, encoding="utf-8")

    s = status_path.read_text(encoding="utf-8")
    a, b, chunk = block(s, "      - record_id: TEST-0008\n", "    external_execution_import_rule:")
    chunk = replace_once(chunk, "        consumed_by_commit: null\n", f'        consumed_by_commit: "{import_sha}"\n', "TEST-0008 authorization consumption")
    s = s[:a] + chunk + s[b:]
    status_path.write_text(s, encoding="utf-8")

else:
    raise SystemExit(f"unknown mode: {MODE}")
