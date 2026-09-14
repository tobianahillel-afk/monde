#!/usr/bin/env bash
set -euo pipefail

PR2_HEAD="ba9f467fa73a1e1151fb6df13955f1a88e5d8a1f"
MAIN_HEAD="29086643387ff46ab6636dd2fa3014efccc10165"
PATCH_SOURCE="30f2c390741f58a1dc7af67915ce6e99c404b3ec"

# Fail closed if either reviewed input moved.
test "$(git rev-parse HEAD)" = "$PR2_HEAD"
git fetch origin main review/test-0008-github-models
test "$(git rev-parse origin/main)" = "$MAIN_HEAD"
git cat-file -e "${PATCH_SOURCE}^{commit}"

# Reuse the graph-aware patch body that already reached 87/87 tests and 100% coverage.
git show "${PATCH_SOURCE}:.github/workflows/admin-pr2-change-guard-v10.yml" > /tmp/pr2-change-guard-source.yml
python - <<'PY'
from pathlib import Path
src = Path('/tmp/pr2-change-guard-source.yml').read_text().splitlines()
start = next(i for i, line in enumerate(src) if line.strip() == '- name: Patch graph-aware v10 change guard and regressions')
stop = next(i for i, line in enumerate(src[start + 1:], start + 1) if line.strip() == '- name: Set up Python')
block = src[start:stop]
run_i = next(i for i, line in enumerate(block) if line.strip() == 'run: |')
script = '\n'.join((line[10:] if line.startswith('          ') else line) for line in block[run_i + 1:]) + '\n'
Path('/tmp/reapply-pr2-change-guard.sh').write_text(script)
PY
bash /tmp/reapply-pr2-change-guard.sh

# Align the mutation harness with the new endpoint-scoped review freshness predicate.
python - <<'PY'
from pathlib import Path
p = Path('scripts/governance_mutation_smoke.py')
s = p.read_text()
old = """        'if change_relevant_to_work(root, path, work, reviewed, head, file_path)',
        'if True',
"""
new = """        'if file_path in endpoint_set\\n                and change_relevant_to_work(root, path, work, reviewed, head, file_path)',
        'if change_relevant_to_work(root, path, work, reviewed, head, file_path)',
"""
assert s.count(old) == 1
p.write_text(s.replace(old, new, 1))
PY

git diff --check

# Full proof before any PR2 mutation.
python -m pip install --require-hashes -r requirements/governance-ci.txt
python -m pytest --cov=tools.governance --cov-branch --cov-report=term-missing --cov-fail-under=100
python scripts/governance_mutation_smoke.py
python -m tools.governance.validate_repo .
python -m tools.governance.strict_contracts .
python -m tools.governance.path_safety .
python -m tools.governance.change_guard . --base "$MAIN_HEAD" --head "$PR2_HEAD"

# Publish only the already-proved tree.
git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
git add tools/governance/change_guard.py tests/governance/test_change_guard.py scripts/governance_mutation_smoke.py
git diff --cached --check
git commit -m 'fix(governance): make change guard v10 merge-aware'
git push origin HEAD:feat/work-0002-governance-ci
echo "CORRECTED_HEAD=$(git rev-parse HEAD)"
