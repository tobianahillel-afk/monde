from pathlib import Path
import json, subprocess, sys

ROOT = Path(sys.argv[1])
OUT = Path('/tmp/final-v10')
TARGET = 'b7f8eb1d82c22cf4eb545bb9cbbec141bb8dba60'
CHECK_KEYS = [
    'status_machine_v10_narrow_imports',
    'review_0027_provenance',
    'test_0008_provenance_and_qualification',
    'requirement_acceptance_preconditions',
    'normative_identity_unchanged_since_cold_read',
    'work_and_project_handover_consistency',
    'work2_cross_branch_boundary',
    'req0010_test0004_boundary',
    'no_remaining_material_defect',
]


def yaml_load(path: Path):
    raw = subprocess.check_output([
        'ruby', '-ryaml', '-rjson', '-e',
        'print JSON.generate(YAML.load_file(ARGV[0]))', str(path)
    ])
    return json.loads(raw)


def cut(value, n):
    if value is None:
        return None
    s = str(value).replace('\n', ' ')
    return s if len(s) <= n else s[:n] + '…'

facts = json.loads((OUT / 'facts.json').read_text())
open_ids = json.loads((OUT / 'open_findings.json').read_text())

# Keep all closure-critical deterministic facts, drop the large progress snapshot.
compact_facts = {k: v for k, v in facts.items() if k != 'progress_snapshot'}

# Compact every historical review while preserving every finding ID and enough
# source evidence to let the fresh reviewer reason independently about closure.
reviews = []
for p in sorted((ROOT / 'registry/reviews').glob('REVIEW-*.yaml')):
    r = yaml_load(p)
    item = {
        'id': r.get('id'),
        'status': r.get('status'),
        'outcome': r.get('outcome'),
        'artifact_commit': (r.get('artifact') or {}).get('commit_sha'),
        'reviewer_independence': (r.get('reviewer') or {}).get('independence_level'),
        'findings': [],
    }
    for f in r.get('findings') or []:
        ev = f.get('evidence') or []
        item['findings'].append({
            'id': f.get('id'),
            'severity': f.get('severity'),
            'category': f.get('category'),
            'description': cut(f.get('description'), 700),
            'disposition': f.get('disposition'),
            'resolved_by': f.get('resolved_by'),
            'evidence_sample': [cut(x, 320) for x in ev[:2]],
        })
    reviews.append(item)

threads_doc = json.loads((OUT / 'pr3_threads.json').read_text())
try:
    threads = threads_doc['data']['repository']['pullRequest']['reviewThreads']['nodes']
except Exception:
    threads = []
thread_summary = []
for th in threads:
    comments = (th.get('comments') or {}).get('nodes') or []
    c = comments[0] if comments else {}
    thread_summary.append({
        'id': th.get('id'),
        'resolved': th.get('isResolved'),
        'path': c.get('path'),
        'outdated': c.get('outdated'),
        'body': cut(c.get('body'), 450),
        'url': c.get('url'),
    })

# Selected current contract slices, independently parsed from the reviewed tree.
sm = yaml_load(ROOT / 'registry/status-machines.yaml')
selected_contract = {
    'tests': {
        'states': sm['registry_machines']['tests']['states'],
        'transitions': sm['registry_machines']['tests']['transitions'],
        'acceptance_cold_read_rule': sm['registry_machines']['tests']['acceptance_cold_read_rule'],
        'external_execution_import_rule': sm['registry_machines']['tests']['external_execution_import_rule'],
        'test0008_authorization': compact_facts['status_machine']['test_0008_authorization'],
    },
    'reviews': {
        'transitions': sm['registry_machines']['reviews']['transitions'],
        'approval_capable_outcomes': sm['registry_machines']['reviews']['approval_capable_outcomes'],
        'external_import_rule': sm['registry_machines']['reviews']['external_import_rule'],
        'review0027_authorization': compact_facts['status_machine']['review_0027_authorization'],
    },
    'requirements_acceptance_preconditions': sm['registry_machines']['requirements']['acceptance_preconditions'],
}

acceptance_patch = subprocess.check_output([
    'git', '-C', str(ROOT), 'show', '--format=', '--patch',
    '74dc253d849e3b6b6570fe55df415f5e9da65ab2', '--',
    'registry/requirements/REQ-0023.yaml',
    'registry/requirements/REQ-0024.yaml',
    'registry/requirements/REQ-0025.yaml'
], text=True)
changed_names = subprocess.check_output([
    'git', '-C', str(ROOT), 'diff', '--name-status',
    'c12a5b55c89168f20c028c2964da16de6f95ac56..' + TARGET
], text=True)
project_state = (ROOT / 'PROJECT_STATE.md').read_text(encoding='utf-8')

shape = {
    'reviewed_commit': TARGET,
    'yaml_parse_success': True,
    'checks': {k: 'PASS|FAIL' for k in CHECK_KEYS},
    'historical_findings': {
        'total': len(open_ids),
        'all_closable': 'boolean',
        'closable_ids': open_ids,
        'failures': [{'id': 'finding id', 'reason': 'string', 'evidence': 'string'}],
    },
    'material_findings': [
        {'severity': 'R1_CRITICAL|R2_MAJOR|R3_MODERATE|R4_MINOR', 'summary': 'string', 'evidence': 'string'}
    ],
    'approval_outcome': 'APPROVE|APPROVE_WITH_FOLLOWUP|CHANGES_REQUIRED|BLOCKED',
    'rationale': 'concise independent rationale',
}

prompt = f'''You are the FINAL fresh-context L2 closure reviewer for MONDE WORK-0001. You did not author this state. Review EXACTLY commit {TARGET}. Fail closed. Do not rely on author assertions when evidence disagrees.

The fresh job already independently parsed the repository and performed deterministic exact-SHA checks. You must reason over those facts plus the compact historical review evidence below. All 41 canonical open finding IDs are included; do not silently omit any.

REQUIRED DECISIONS:
1. status_machine_v10_narrow_imports: v10 external REVIEW/TEST imports are record-specific, one-shot, source/executor/revision-bound, correctly consumed, and create no generic lifecycle bypass.
2. review_0027_provenance: authorization/import/binding/consumption and reviewed SHA are coherent.
3. test_0008_provenance_and_qualification: source/executor/execution/import/history/cold-read evidence is coherent and no retroactive READY/RUNNING replay occurred.
4. requirement_acceptance_preconditions: REQ-0023/24/25 acceptance in 74dc253d satisfies the current machine.
5. normative_identity_unchanged_since_cold_read: every REQUIREMENT_NORMATIVE_V1 included field stayed identical to the c12a5b55 cold-read revision.
6. work_and_project_handover_consistency: WORK-0001 / PROJECT_STATE truthfully keep completion non-terminal pending this review.
7. work2_cross_branch_boundary: PR #3 mirror stays branch-safe and live PR #2 evidence remains behind explicit boundary.
8. req0010_test0004_boundary: current REQ-0010→TEST-0005 and TEST-0004 does not claim current REQ-0010 reverse coverage.
9. no_remaining_material_defect: no remaining R1/R2/R3 issue exists in the reviewed state.

HISTORICAL FINDINGS GATE:
- expected exact set = {json.dumps(open_ids)}
- For EACH ID, inspect its originating compact review finding and the later review/correction chain represented in the facts/reviews.
- `closable_ids` MUST contain exactly the IDs you independently judge corrected or otherwise policy-validly closable in the current tree.
- If any ID is not independently closable, omit it and explain it under `failures`.
- `all_closable` may be true only when the exact set is closable.
- Do not make an old finding disappear merely because a later document says it is fixed.

Return ONLY valid JSON matching this shape, with concrete values:
{json.dumps(shape, indent=2)}

=== DETERMINISTIC CURRENT FACTS ===
{json.dumps(compact_facts, indent=2)}

=== SELECTED CANONICAL CONTRACT ===
{json.dumps(selected_contract, indent=2)}

=== HISTORICAL REVIEW/FINDING CHAIN (COMPACT, COMPLETE IDS) ===
{json.dumps(reviews, indent=2)}

=== LIVE PR #3 THREAD SUMMARY ===
{json.dumps(thread_summary, indent=2)}

=== c12a5b55 → b7f8eb1d CHANGED PATHS ===
{changed_names}

=== ATOMIC REQUIREMENT ACCEPTANCE PATCH ===
{acceptance_patch}

=== CURRENT PROJECT_STATE ===
{project_state}
'''

size = len(prompt.encode('utf-8'))
if size > 90000:
    raise SystemExit(f'compact prompt still too large: {size} bytes')
(OUT / 'prompt.txt').write_text(prompt, encoding='utf-8')
print(f'compact_prompt_bytes={size}')
print(f'review_count={len(reviews)} finding_count={sum(len(r["findings"]) for r in reviews)} thread_count={len(thread_summary)}')
