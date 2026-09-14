#!/usr/bin/env bash
set -euo pipefail

TARGET_HEAD="cbc2dfc065e73b9086d13a483b8b693ddc2fa6cc"
BASE_SHA="29086643387ff46ab6636dd2fa3014efccc10165"
BRANCH="feat/work-0002-governance-ci"

# Exact-head guard: this importer is valid only for the reviewed candidate.
test "$(git rev-parse HEAD)" = "$TARGET_HEAD"
git fetch origin "$BRANCH" main
test "$(git rev-parse origin/$BRANCH)" = "$TARGET_HEAD"

python -m pip install --require-hashes -r requirements/governance-ci.txt

git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'

# 1) Preauthorize the externally completed negative review in a parent commit.
python - <<'PY'
from pathlib import Path
p = Path('registry/status-machines.yaml')
s = p.read_text()
anchor = '    external_import_rule: For an externally completed review materialized after v7, a matching one-shot authorization must\n'
assert s.count(anchor) == 1, s.count(anchor)
block = '''    - record_id: REVIEW-0030
      imported_status: COMPLETE
      artifact_commit_sha: cbc2dfc065e73b9086d13a483b8b693ddc2fa6cc
      source_review_id: PRR_kwDOUUI5ts8AAAABNccy5Q
      source_submitted_at: '2026-09-14T11:45:39Z'
      reviewer_context_id: fresh-context-pr2-cbc2dfc
      expected_outcome: CHANGES_REQUIRED
      one_shot: true
      consumed_by_commit: null
      finding_origin: PRRT_kwDOUUI5ts6iF6p2;PRRT_kwDOUUI5ts6iF6qN;PRRT_kwDOUUI5ts6iF6qU;PRRT_kwDOUUI5ts6iF6qY;PRRT_kwDOUUI5ts6iF6qf;PRRT_kwDOUUI5ts6iF6qm
      reason: 'The fresh-context GitHub Codex review of exact PR #2 candidate cbc2dfc completed externally before REVIEW-0030 materialization and produced six new material P1 findings. This one-shot authorization is committed first so the negative review can be imported truthfully as COMPLETE without replaying OPEN/IN_PROGRESS after the fact.'
'''
p.write_text(s.replace(anchor, block + anchor))
PY

git add registry/status-machines.yaml
git diff --cached --check
git commit -m 'chore(governance): authorize REVIEW-0030 import'
AUTH_SHA="$(git rev-parse HEAD)"

# 2) Materialize the externally completed negative review exactly once.
cat > registry/reviews/REVIEW-0030.yaml <<EOF
id: REVIEW-0030
status: COMPLETE
artifact:
  type: PULL_REQUEST
  id_or_path: "PR-2"
  commit_sha: "cbc2dfc065e73b9086d13a483b8b693ddc2fa6cc"
reviewer:
  actor: "GitHub Codex fresh-context reviewer"
  context_id: "fresh-context-pr2-cbc2dfc"
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
  source_review_id: "PRR_kwDOUUI5ts8AAAABNccy5Q"
  source_submitted_at: "2026-09-14T11:45:39Z"
  import_commit: null

scope:
  work_items: [WORK-0002]
  requirements: []
  capabilities: []
  contracts:
    - "risk acceptance transition preconditions"
    - "REQUIREMENT_NORMATIVE_V1 digest recomputation"
    - "repository-owner authority evidence binding"
    - "one-shot review import binding and consumption"
    - "PASS TEST execution revision existence and ancestry"
    - "review completion eligibility for COMPLETE versus CLOSED"
  risks:
    - "Risk records can transition to ACCEPTED without the canonical authority/precondition contract."
    - "Requirement acceptance evidence can repeat an invented digest instead of binding canonical normative content."
    - "A contributor can present an unrelated GitHub repository URL as repository-owner authority proof."
    - "An imported COMPLETE review can be consumed as completion evidence before its one-shot authorization is bound/consumed."
    - "A PASS test can cite a syntactically valid but nonexistent execution revision."
    - "A CLOSED review can be repurposed as approval evidence."

findings:
  - id: F-1
    severity: R2_MAJOR
    category: VERIFICATION_VALIDATION
    description: "Transitions into RISK ACCEPTED validate adjacency but do not enforce the v10 risk acceptance preconditions: accepted flag, actor, matrix-authorized role, typed durable evidence, matrix version/rule, rationale, timestamp, and review condition."
    evidence:
      - "GitHub Codex review PRR_kwDOUUI5ts8AAAABNccy5Q on exact head cbc2dfc065e73b9086d13a483b8b693ddc2fa6cc"
      - "Inline thread PRRT_kwDOUUI5ts6iF6p2"
      - "tools/governance/change_guard.py risk edge validation"
      - "registry/status-machines.yaml risks.acceptance_preconditions"
    disposition: OPEN
    resolved_by: null

  - id: F-2
    severity: R2_MAJOR
    category: VERIFICATION_VALIDATION
    description: "Requirement PROPOSED-to-ACCEPTED validation checks digest syntax and matching evidence but does not recompute REQUIREMENT_NORMATIVE_V1 from the canonical normative projection using the configured RFC 8785/JCS byte serialization."
    evidence:
      - "GitHub Codex review PRR_kwDOUUI5ts8AAAABNccy5Q on exact head cbc2dfc065e73b9086d13a483b8b693ddc2fa6cc"
      - "Inline thread PRRT_kwDOUUI5ts6iF6qN"
      - "tools/governance/change_guard.py requirement_acceptance_satisfied"
      - "registry/content-identity.yaml REQUIREMENT_NORMATIVE_V1"
    disposition: OPEN
    resolved_by: null

  - id: F-3
    severity: R2_MAJOR
    category: SECURITY
    description: "GITHUB_REPOSITORY_OWNER_PERMISSION authority validation accepts an arbitrary GitHub repository-shaped URL whose owner path matches accepted_by; it is not bound to the governed MONDE repository or a durable permission artifact establishing the actor's role."
    evidence:
      - "GitHub Codex review PRR_kwDOUUI5ts8AAAABNccy5Q on exact head cbc2dfc065e73b9086d13a483b8b693ddc2fa6cc"
      - "Inline thread PRRT_kwDOUUI5ts6iF6qU"
      - "tools/governance/strict_contracts.py authority evidence validation"
      - "registry/acceptance-authority.yaml evidence_contract"
    disposition: OPEN
    resolved_by: null

  - id: F-4
    severity: R2_MAJOR
    category: VERIFICATION_VALIDATION
    description: "A preauthorized external COMPLETE review can be materialized while its authorization is unconsumed, but completion validation does not require the later import_commit binding and consumed_by_commit state before that review becomes eligible evidence."
    evidence:
      - "GitHub Codex review PRR_kwDOUUI5ts8AAAABNccy5Q on exact head cbc2dfc065e73b9086d13a483b8b693ddc2fa6cc"
      - "Inline thread PRRT_kwDOUUI5ts6iF6qY"
      - "tools/governance/change_guard.py historical_import_allowed"
      - "registry/status-machines.yaml reviews.external_import_rule"
    disposition: OPEN
    resolved_by: null

  - id: F-5
    severity: R2_MAJOR
    category: VERIFICATION_VALIDATION
    description: "PASS TEST execution.commit_sha is shape-checked but not verified to exist as a Git commit in relevant ancestry, so a fabricated 40-hex revision can satisfy required test evidence."
    evidence:
      - "GitHub Codex review PRR_kwDOUUI5ts8AAAABNccy5Q on exact head cbc2dfc065e73b9086d13a483b8b693ddc2fa6cc"
      - "Inline thread PRRT_kwDOUUI5ts6iF6qf"
      - "tools/governance/strict_contracts.py PASS TEST evidence validation"
    disposition: OPEN
    resolved_by: null

  - id: F-6
    severity: R2_MAJOR
    category: VERIFICATION_VALIDATION
    description: "DONE review validation accepts CLOSED reviews with an approving outcome and lets them contribute roles/independence even though the canonical review lifecycle says CLOSED never satisfies a work-item completion gate."
    evidence:
      - "GitHub Codex review PRR_kwDOUUI5ts8AAAABNccy5Q on exact head cbc2dfc065e73b9086d13a483b8b693ddc2fa6cc"
      - "Inline thread PRRT_kwDOUUI5ts6iF6qm"
      - "tools/governance/validate_repo.py completed review validation"
      - "registry/status-machines.yaml reviews.closed_rule"
    disposition: OPEN
    resolved_by: null

checks:
  assumptions_challenged:
    - "Lifecycle adjacency is sufficient for risk acceptance."
    - "A repeated syntactically valid requirement digest proves normative identity."
    - "A repository-shaped GitHub URL proves repository-owner authority."
    - "Preauthorization alone makes an imported review eligible completion evidence."
    - "A 40-hex TEST execution SHA necessarily names a real tested revision."
    - "CLOSED reviews remain approval-capable."
  omitted_categories_considered:
    - "risk acceptance authority"
    - "normative digest recomputation"
    - "durable repository-owner evidence"
    - "external review import finalization"
    - "test revision existence/ancestry"
    - "review lifecycle completion eligibility"
  duplicate_or_reuse_search:
    - "All twelve prior open threads were rechecked but not assumed exhaustive."
    - "These six findings are fresh gaps found on the exact REVIEW-0029-corrected candidate."
  failure_modes_considered:
    - "unauthorized risk acceptance"
    - "invented normative digest"
    - "cross-repository owner-proof spoofing"
    - "half-finished one-shot review import used as approval"
    - "fabricated tested revision"
    - "abandoned CLOSED review reused as approval"
  evidence_requested:
    - "Regression tests for all six findings"
    - "Full line/branch coverage and mutation smoke"
    - "Repository/strict/path/change validators green on the corrected exact SHA"
    - "Fresh independent L2 after correction"

outcome: CHANGES_REQUIRED
completed_at: "2026-09-14T11:45:39Z"

history:
  created_at: "2026-09-14"
  updated_at: "2026-09-14"
EOF

git add registry/reviews/REVIEW-0030.yaml
git diff --cached --check
git commit -m 'chore(governance): import REVIEW-0030 negative L2'
IMPORT_SHA="$(git rev-parse HEAD)"

# 3) Bind the imported REVIEW record to the actual materialization commit.
python - "$IMPORT_SHA" <<'PY'
from pathlib import Path
import sys
sha = sys.argv[1]
p = Path('registry/reviews/REVIEW-0030.yaml')
s = p.read_text()
needle = '  import_commit: null\n'
assert s.count(needle) == 1, s.count(needle)
p.write_text(s.replace(needle, f'  import_commit: "{sha}"\n', 1))
PY

git add registry/reviews/REVIEW-0030.yaml
git diff --cached --check
git commit -m 'chore(governance): bind REVIEW-0030 import commit'
BIND_SHA="$(git rev-parse HEAD)"

# 4) Consume exactly the REVIEW-0030 one-shot authorization using the import commit.
python - "$IMPORT_SHA" <<'PY'
from pathlib import Path
import sys
sha = sys.argv[1]
p = Path('registry/status-machines.yaml')
s = p.read_text()
start = s.index('    - record_id: REVIEW-0030\n')
end = s.index('    external_import_rule:', start)
block = s[start:end]
needle = '      consumed_by_commit: null\n'
assert block.count(needle) == 1, block.count(needle)
block = block.replace(needle, f'      consumed_by_commit: {sha}\n', 1)
p.write_text(s[:start] + block + s[end:])
PY

git add registry/status-machines.yaml
git diff --cached --check
git commit -m 'chore(governance): consume REVIEW-0030 authorization'
FINAL_SHA="$(git rev-parse HEAD)"

# Administrative import must itself satisfy repository governance.
python -m tools.governance.validate_repo .
python -m tools.governance.strict_contracts .
python -m tools.governance.path_safety .
python -m tools.governance.change_guard . --base "$BASE_SHA" --head "$FINAL_SHA"

git push origin HEAD:"$BRANCH"
printf 'AUTH_SHA=%s\nIMPORT_SHA=%s\nBIND_SHA=%s\nFINAL_SHA=%s\n' "$AUTH_SHA" "$IMPORT_SHA" "$BIND_SHA" "$FINAL_SHA"
