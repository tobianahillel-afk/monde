#!/usr/bin/env bash
set -euo pipefail
TARGET_HEAD="4eb23ffcae5eab9bb6ead05104258893df96c93a"
BASE_SHA="29086643387ff46ab6636dd2fa3014efccc10165"
ADMIN_BRANCH="review/test-0008-github-models"

test "$(git rev-parse HEAD)" = "$TARGET_HEAD"
git fetch origin feat/work-0002-governance-ci "$ADMIN_BRANCH" main
test "$(git rev-parse origin/feat/work-0002-governance-ci)" = "$TARGET_HEAD"

python -m pip install --require-hashes -r requirements/governance-ci.txt

git show "origin/$ADMIN_BRANCH:.github/admin/pr2-review0029-fixes.py" > /tmp/pr2-review0029-fixes.py
git show "origin/$ADMIN_BRANCH:.github/admin/pr2-review0029-test-fixes.py" > /tmp/pr2-review0029-test-fixes.py
python /tmp/pr2-review0029-fixes.py
python /tmp/pr2-review0029-test-fixes.py

git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
git add tools/governance/change_guard.py tools/governance/strict_contracts.py schemas/registry/tests.schema.json schemas/registry/reviews.schema.json registry/tests/TEST-0002.yaml registry/tests/TEST-0003.yaml registry/status-machines.yaml tests/governance/test_change_guard.py tests/governance/test_final_l2_findings.py tests/governance/test_current_gap_regressions.py tests/governance/test_strict_contracts.py tests/governance/test_review0029_branches.py scripts/governance_mutation_smoke.py registry/work-items/WORK-0002.yaml
git diff --cached --check
git commit -m 'fix(governance): close REVIEW-0029 contract gaps'
CANDIDATE="$(git rev-parse HEAD)"

python -m pytest -q --cov=tools.governance --cov-branch --cov-report=term-missing --cov-fail-under=100
python scripts/governance_mutation_smoke.py
python -m tools.governance.validate_repo .
python -m tools.governance.strict_contracts .
python -m tools.governance.path_safety .
python -m tools.governance.change_guard . --base "$BASE_SHA" --head "$CANDIDATE"

git push origin HEAD:feat/work-0002-governance-ci
printf 'CANDIDATE=%s\n' "$CANDIDATE"
