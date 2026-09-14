from pathlib import Path
import sys

root = Path(sys.argv[1])
p = root / 'registry/status-machines.yaml'
s = p.read_text(encoding='utf-8')
if not s.startswith('version: 10\ncanonical: true\n'):
    raise SystemExit('expected status-machines v10')
if 'record_id: REVIEW-0028' in s:
    raise SystemExit('REVIEW-0028 authorization already exists')
rule = '    external_import_rule: "For an externally completed review materialized after v7, a matching one-shot authorization must already exist in a parent commit before the REVIEW record first appears. The authorization binds record_id, resulting status, reviewed artifact SHA, source review identity/time, reviewer context and expected outcome. The imported REVIEW must declare that authorization. A later metadata-only binding must set consumed_by_commit to the actual first-materialization commit before the imported review may satisfy any work completion gate. An authorization with consumed_by_commit set cannot be reused."\n'
if s.count(rule) != 1:
    raise SystemExit('external review import rule anchor mismatch')
auth = '''      - record_id: REVIEW-0028
        imported_status: COMPLETE
        artifact_commit_sha: "b7f8eb1d82c22cf4eb545bb9cbbec141bb8dba60"
        source_review_id: "github-actions-run:34795556653:attempt:1"
        source_submitted_at: "2026-09-14T01:20:57.483306Z"
        reviewer_context_id: "github-actions:34795556653:1:final-v10-l2"
        expected_outcome: APPROVE
        one_shot: true
        consumed_by_commit: null
        source_kind: GITHUB_ACTIONS_COPILOT_CLI
        reason: "The final fresh-context GitHub Actions Copilot CLI L2 reviewed exact frozen candidate b7f8eb1d, passed all nine closure checks, found no material R1/R2/R3 defect, and independently judged the exact canonical set of 41 historical findings corrected or policy-validly closable. This one-shot authorization is committed before REVIEW-0028 first materialization so the completed external review can be imported truthfully without replaying OPEN/IN_PROGRESS."
'''
s = s.replace(rule, auth + rule, 1)
p.write_text(s, encoding='utf-8')
