#!/usr/bin/env bash
set -euo pipefail

TARGET_HEAD="0d4569b47e7e57f9141b95558bc4ae2c55124051"
BASE_SHA="29086643387ff46ab6636dd2fa3014efccc10165"
BRANCH="feat/work-0002-governance-ci"
ADMIN_BRANCH="review/test-0008-github-models"

# This corrective runner is valid only for the exact REVIEW-0030-imported head.
test "$(git rev-parse HEAD)" = "$TARGET_HEAD"
git fetch origin "$BRANCH" "$ADMIN_BRANCH" main
test "$(git rev-parse origin/$BRANCH)" = "$TARGET_HEAD"

python -m pip install --require-hashes -r requirements/governance-ci.txt

git show "origin/$ADMIN_BRANCH:.github/admin/pr2-review0030-fixes.py" > /tmp/pr2-review0030-fixes.py
git show "origin/$ADMIN_BRANCH:.github/admin/pr2-review0030-hotfix.py" > /tmp/pr2-review0030-hotfix.py
python /tmp/pr2-review0030-hotfix.py
python /tmp/pr2-review0030-fixes.py

git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
git add \
  tools/governance/change_guard.py \
  tools/governance/strict_contracts.py \
  tools/governance/validate_repo.py \
  registry/acceptance-authority.yaml \
  registry/reviews/REVIEW-0001.yaml \
  registry/work-items/WORK-0002.yaml \
  tests/governance/test_review0029_branches.py \
  tests/governance/test_review0030_findings.py \
  scripts/governance_mutation_smoke.py

git diff --cached --check
git commit -m 'fix(governance): close REVIEW-0030 contract gaps'
CANDIDATE="$(git rev-parse HEAD)"

# Full deterministic proof before publication.
python -m pytest -q --cov=tools.governance --cov-branch --cov-report=term-missing --cov-fail-under=100
python scripts/governance_mutation_smoke.py
python -m tools.governance.validate_repo .
python -m tools.governance.strict_contracts .
python -m tools.governance.path_safety .
python -m tools.governance.change_guard . --base "$BASE_SHA" --head "$CANDIDATE"

git push origin HEAD:"$BRANCH"
printf 'CANDIDATE=%s\n' "$CANDIDATE"
