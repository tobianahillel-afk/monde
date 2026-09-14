#!/usr/bin/env bash
set -euo pipefail

TARGET_HEAD="40550a5d3e3e3f75f467c6e6cd29d3fe729a25e5"
REVIEW_ID="REVIEW-0029"
SOURCE_REVIEW_ID="PRR_kwDOUUI5ts8AAAABNbhVFw"
SOURCE_SUBMITTED_AT="2026-09-14T09:48:59Z"
CONTEXT_ID="fresh-context-pr2-40550a5d"
THREADS="PRRT_kwDOUUI5ts6iD2t4;PRRT_kwDOUUI5ts6iD2t-;PRRT_kwDOUUI5ts6iD2uH;PRRT_kwDOUUI5ts6iD2uL;PRRT_kwDOUUI5ts6iD2uQ;PRRT_kwDOUUI5ts6iD2ub"

# Fail closed if PR #2 moved after the external review.
test "$(git rev-parse HEAD)" = "$TARGET_HEAD"
git fetch origin feat/work-0002-governance-ci
test "$(git rev-parse origin/feat/work-0002-governance-ci)" = "$TARGET_HEAD"

git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'

# 1) Preauthorize the already-completed external review in a parent commit.
python - <<'PY'
from pathlib import Path
p = Path('registry/status-machines.yaml')
s = p.read_text()
assert 'record_id: REVIEW-0029' not in s
marker = '    external_import_rule: "For an externally completed review materialized after v7, a matching one-shot authorization must already exist in a parent commit before the REVIEW record first appears.'
assert s.count(marker) == 1
block = '''      - record_id: REVIEW-0029
        imported_status: COMPLETE
        artifact_commit_sha: "40550a5d3e3e3f75f467c6e6cd29d3fe729a25e5"
        source_review_id: "PRR_kwDOUUI5ts8AAAABNbhVFw"
        source_submitted_at: "2026-09-14T09:48:59Z"
        reviewer_context_id: "fresh-context-pr2-40550a5d"
        expected_outcome: CHANGES_REQUIRED
        one_shot: true
        consumed_by_commit: null
        finding_origin: "PRRT_kwDOUUI5ts6iD2t4;PRRT_kwDOUUI5ts6iD2t-;PRRT_kwDOUUI5ts6iD2uH;PRRT_kwDOUUI5ts6iD2uL;PRRT_kwDOUUI5ts6iD2uQ;PRRT_kwDOUUI5ts6iD2ub"
        reason: "The fresh-context GitHub Codex review of exact PR #2 candidate 40550a5d completed externally before REVIEW-0029 materialization and produced six material findings. This one-shot authorization is committed first so the negative review can be imported truthfully as COMPLETE without replaying OPEN/IN_PROGRESS after the fact."
'''
s = s.replace('    external_import_rule:', block + '    external_import_rule:', 1)
p.write_text(s)
PY
git add registry/status-machines.yaml
git diff --cached --check
git commit -m 'chore(review): authorize REVIEW-0029 import'
AUTH_SHA="$(git rev-parse HEAD)"

# 2) Materialize the completed negative external review with all six findings OPEN.
cat > registry/reviews/REVIEW-0029.yaml <<EOF
id: REVIEW-0029
status: COMPLETE
artifact:
  type: PULL_REQUEST
  id_or_path: "PR-2"
  commit_sha: "$TARGET_HEAD"
reviewer:
  actor: "GitHub Codex fresh-context reviewer"
  context_id: "$CONTEXT_ID"
  independence_level: L2
roles:
  - ARCHITECTURE_REUSE
  - VERIFICATION_VALIDATION
  - SECURITY
  - PERFORMANCE_SRE
  - DOCUMENTATION_TRACEABILITY
  - RED_TEAM_SKEPTIC

external_import:
  mode: PREAUTHORIZED_EXTERNAL_COMPLETION
  authorization_commit: "$AUTH_SHA"
  source_review_id: "$SOURCE_REVIEW_ID"
  source_submitted_at: "$SOURCE_SUBMITTED_AT"
  import_commit: null

scope:
  work_items: [WORK-0002]
  requirements: []
  capabilities: []
  contracts:
    - "v10 lifecycle and import/acceptance semantics"
    - "revision-bound PASS test evidence"
    - "immutable review revision binding and freshness"
    - "blocking-finding acceptance authority"
    - "required-test semantic freshness"
    - "graph-aware PR merge-base endpoint semantics"
  risks:
    - "Lifecycle adjacency alone can bypass initial-state, acceptance-precondition or one-shot-import rules."
    - "A PASS test definition can be trusted without concrete revision-bound execution evidence."
    - "Mutable/non-object review commit references can bypass freshness."
    - "Blocking findings can be self-accepted without matrix-authorized durable authority evidence."
    - "Required TEST contracts can be weakened after review without staling review evidence."
    - "Base-tip endpoint diffs can replay base-side changes as PR-local changes when main advances."

findings:
  - id: F-1
    severity: R2_MAJOR
    category: VERIFICATION_VALIDATION
    description: "The graph-aware change guard reads only adjacency transitions from the v10 lifecycle contract and does not enforce initial-state rules, requirement acceptance preconditions, or exact one-shot import exceptions for newly introduced/transitioned records. A PR could therefore create a TEST directly as PASS, a REVIEW directly as COMPLETE, or accept a requirement without its required digest-bound review/cold-read evidence."
    evidence:
      - "GitHub Codex review $SOURCE_REVIEW_ID on exact head $TARGET_HEAD"
      - "Inline thread PRRT_kwDOUUI5ts6iD2t4"
      - "tools/governance/change_guard.py canonical_transitions / per-edge validation"
      - "registry/status-machines.yaml v10 lifecycle and acceptance/import rules"
    disposition: OPEN
    resolved_by: null

  - id: F-2
    severity: R2_MAJOR
    category: VERIFICATION_VALIDATION
    description: "The TEST schema still permits status PASS using only a definition plus prose execution-evidence policy, without a concrete result/evidence artifact or exact tested commit SHA. DONE validation subsequently trusts PASS status, so an unexecuted definition can satisfy a mandatory test gate."
    evidence:
      - "GitHub Codex review $SOURCE_REVIEW_ID on exact head $TARGET_HEAD"
      - "Inline thread PRRT_kwDOUUI5ts6iD2t-"
      - "schemas/registry/tests.schema.json execution-definition alternative"
      - "TEST-0002 / TEST-0003 exercise the weak historical shape"
    disposition: OPEN
    resolved_by: null

  - id: F-3
    severity: R2_MAJOR
    category: VERIFICATION_VALIDATION
    description: "A COMPLETE review artifact.commit_sha accepts any non-empty string; values such as HEAD or short/mutable references can pass schema/strict validation and yield empty freshness diffs. Reviewed revisions must be full immutable commit object IDs whose existence/ancestry is verified."
    evidence:
      - "GitHub Codex review $SOURCE_REVIEW_ID on exact head $TARGET_HEAD"
      - "Inline thread PRRT_kwDOUUI5ts6iD2uH"
      - "schemas/registry/reviews.schema.json COMPLETE artifact.commit_sha constraint"
      - "review freshness logic in tools/governance/change_guard.py"
    disposition: OPEN
    resolved_by: null

  - id: F-4
    severity: R2_MAJOR
    category: SECURITY
    description: "DONE validation treats a blocking R1/R2 finding with disposition ACCEPTED like RESOLVED without resolving registry/acceptance-authority.yaml, validating the required acceptance fields/matrix rule, or proving durable authority evidence. An author could self-declare acceptance of a blocking finding and satisfy completion."
    evidence:
      - "GitHub Codex review $SOURCE_REVIEW_ID on exact head $TARGET_HEAD"
      - "Inline thread PRRT_kwDOUUI5ts6iD2uL"
      - "tools/governance/strict_contracts.py blocking-finding completion logic"
      - "registry/acceptance-authority.yaml finding_acceptance/evidence_contract"
    disposition: OPEN
    resolved_by: null

  - id: F-5
    severity: R2_MAJOR
    category: VERIFICATION_VALIDATION
    description: "Every registry/tests change is treated as administrative before semantic dependency/reference checks. After an approving review, a later endpoint commit can weaken a required TEST's protected contracts, cases, command or evidence policy without staling the review. Only execution/result metadata may be administrative; the verification contract itself must remain freshness-relevant."
    evidence:
      - "GitHub Codex review $SOURCE_REVIEW_ID on exact head $TARGET_HEAD"
      - "Inline thread PRRT_kwDOUUI5ts6iD2uQ"
      - "tools/governance/change_guard.py administrative-path classification"
      - "WORK required_tests references"
    disposition: OPEN
    resolved_by: null

  - id: F-6
    severity: R3_MODERATE
    category: VERIFICATION_VALIDATION
    description: "Endpoint changed files are computed from base-tip..head-tip rather than the PR merge-base contribution. When main advances without being merged into the branch, base-only changes can appear as PR deletions/meta-governance changes. Endpoint files should use merge-base/three-dot semantics while per-commit validation retains true-parent edges."
    evidence:
      - "GitHub Codex review $SOURCE_REVIEW_ID on exact head $TARGET_HEAD"
      - "Inline thread PRRT_kwDOUUI5ts6iD2ub"
      - "tools/governance/change_guard.py endpoint_files"
      - "Git merge-base / three-dot endpoint semantics"
    disposition: OPEN
    resolved_by: null

checks:
  assumptions_challenged:
    - "Passing adjacency validation is equivalent to satisfying the complete canonical lifecycle contract."
    - "A declared PASS status can stand in for revision-bound execution evidence."
    - "Any non-empty review SHA is immutable and freshness-safe."
    - "ACCEPTED blocking findings are automatically authority-valid."
    - "All TEST registry mutations are administrative."
    - "base-tip..head-tip is equivalent to PR merge-base endpoint scope."
  omitted_categories_considered:
    - "A3 assurance-derived independence floors"
    - "review SHA freshness"
    - "PASS TEST evidence"
    - "NOT_APPLICABLE justifications"
    - "non-WORK registry context routing"
    - "transition-stable PROJECT_STATE"
    - "v10 graph-aware parent-edge semantics"
    - "security/supply-chain/live GitHub trust boundaries"
  duplicate_or_reuse_search:
    - "The six earlier c50c330 findings were rechecked but not assumed exhaustive."
    - "These six findings are fresh gaps found on the exact integrated v10 candidate."
  failure_modes_considered:
    - "direct terminal-state introduction"
    - "acceptance without preconditions"
    - "unexecuted PASS evidence"
    - "mutable review revision reference"
    - "unauthorized blocking-finding acceptance"
    - "post-review weakening of required test semantics"
    - "base-side history replay into PR endpoint scope"
  evidence_requested:
    - "Regression tests for all six findings"
    - "Full line/branch coverage and mutation smoke"
    - "Repository/strict/path/change validators green on the corrected exact SHA"
    - "Fresh independent L2 after correction"

outcome: CHANGES_REQUIRED
completed_at: "$SOURCE_SUBMITTED_AT"

history:
  created_at: "2026-09-14"
  updated_at: "2026-09-14"
EOF

git add registry/reviews/REVIEW-0029.yaml
git diff --cached --check
git commit -m 'chore(review): record REVIEW-0029 findings'
IMPORT_SHA="$(git rev-parse HEAD)"

# 3) Bind the imported review to its actual first-materialization commit.
python - <<PY
from pathlib import Path
p = Path('registry/reviews/REVIEW-0029.yaml')
s = p.read_text()
assert '  import_commit: null' in s
p.write_text(s.replace('  import_commit: null', '  import_commit: "${IMPORT_SHA}"', 1))
PY
git add registry/reviews/REVIEW-0029.yaml
git diff --cached --check
git commit -m 'chore(review): bind REVIEW-0029 import'

# 4) Consume the one-shot authorization using the first-materialization commit.
python - <<PY
from pathlib import Path
p = Path('registry/status-machines.yaml')
s = p.read_text()
needle = '''      - record_id: REVIEW-0029
        imported_status: COMPLETE
        artifact_commit_sha: "$TARGET_HEAD"
        source_review_id: "$SOURCE_REVIEW_ID"
        source_submitted_at: "$SOURCE_SUBMITTED_AT"
        reviewer_context_id: "$CONTEXT_ID"
        expected_outcome: CHANGES_REQUIRED
        one_shot: true
        consumed_by_commit: null'''
replace = needle.replace('consumed_by_commit: null', 'consumed_by_commit: "${IMPORT_SHA}"')
assert s.count(needle) == 1
p.write_text(s.replace(needle, replace, 1))
PY
git add registry/status-machines.yaml
git diff --cached --check
git commit -m 'chore(review): consume REVIEW-0029 authorization'

# Validate the durable negative-review materialization before publication.
python -m pip install --require-hashes -r requirements/governance-ci.txt
python -m tools.governance.validate_repo .
python -m tools.governance.strict_contracts .
python -m tools.governance.path_safety .

git push origin HEAD:feat/work-0002-governance-ci
printf 'AUTH_SHA=%s\nIMPORT_SHA=%s\nFINAL_HEAD=%s\n' "$AUTH_SHA" "$IMPORT_SHA" "$(git rev-parse HEAD)"
