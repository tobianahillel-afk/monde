from pathlib import Path
import json, subprocess, sys

ROOT=Path(sys.argv[1]); OUT=Path('/tmp/final-v10')
TARGET='b7f8eb1d82c22cf4eb545bb9cbbec141bb8dba60'
CHECK_KEYS=['status_machine_v10_narrow_imports','review_0027_provenance','test_0008_provenance_and_qualification','requirement_acceptance_preconditions','normative_identity_unchanged_since_cold_read','work_and_project_handover_consistency','work2_cross_branch_boundary','req0010_test0004_boundary','no_remaining_material_defect']

def y(path):
    raw=subprocess.check_output(['ruby','-ryaml','-rjson','-e','print JSON.generate(YAML.load_file(ARGV[0]))',str(path)])
    return json.loads(raw)
def cut(v,n):
    if v is None:return None
    s=str(v).replace('\n',' ')
    return s if len(s)<=n else s[:n]+'…'

f=json.loads((OUT/'facts.json').read_text()); opens=json.loads((OUT/'open_findings.json').read_text())
# Only facts needed for an independent closure decision; omit verbose progress and duplicated prose reasons.
rf=f['status_machine']['review_0027_authorization']; ta=f['status_machine']['test_0008_authorization']
rf={k:rf.get(k) for k in ['record_id','imported_status','artifact_commit_sha','source_review_id','source_submitted_at','reviewer_context_id','expected_outcome','one_shot','consumed_by_commit']}
ta={k:ta.get(k) for k in ['record_id','from_status','imported_status','execution_commit_sha','source_id','source_submitted_at','executor_context_id','expected_result','one_shot','consumed_by_commit']}
minimal={
 'target_sha':f['target_sha'],'deterministic_pass':f['deterministic_pass'],'live_pr3':f['live_pr3'],
 'work':f['work'],'status_machine':{'version':f['status_machine']['version'],'no_generic_planned_to_pass':f['status_machine']['no_generic_planned_to_pass'],'review27_auth':rf,'test8_auth':ta},
 'review27':f['review_0027'],'test8':f['test_0008'],'requirements':f['requirements'],'work2_boundary':f['work2_boundary'],'req0010_test0004':f['req0010_test0004']}
# Strip long evidence prose from TEST8 execution but keep source/result/binding and outcome facts.
minimal['test8']['execution']={k:minimal['test8']['execution'].get(k) for k in ['command_or_workflow','last_run_at','commit_sha','result']}

hist=[]
for p in sorted((ROOT/'registry/reviews').glob('REVIEW-*.yaml')):
    r=y(p); fs=[]
    for q in r.get('findings') or []:
        ev=q.get('evidence') or []
        fs.append({'id':q.get('id'),'severity':q.get('severity'),'category':q.get('category'),'description':cut(q.get('description'),420),'disposition':q.get('disposition'),'resolved_by':q.get('resolved_by'),'evidence':cut(ev[0],180) if ev else None})
    hist.append({'id':r.get('id'),'artifact':(r.get('artifact') or {}).get('commit_sha'),'outcome':r.get('outcome'),'findings':fs})

threads_doc=json.loads((OUT/'pr3_threads.json').read_text()); nodes=threads_doc.get('data',{}).get('repository',{}).get('pullRequest',{}).get('reviewThreads',{}).get('nodes',[])
threads=[]
for th in nodes:
    cs=(th.get('comments') or {}).get('nodes') or []; c=cs[0] if cs else {}
    if not th.get('isResolved'):
        threads.append({'id':th.get('id'),'path':c.get('path'),'outdated':c.get('outdated'),'body':cut(c.get('body'),220)})

sm=y(ROOT/'registry/status-machines.yaml'); tests=sm['registry_machines']['tests']; revs=sm['registry_machines']['reviews']; reqm=sm['registry_machines']['requirements']
contract={'test_transitions':tests['transitions'],'test_external_rule':tests['external_execution_import_rule'],'review_external_rule':revs['external_import_rule'],'review_approval_outcomes':revs['approval_capable_outcomes'],'requirement_acceptance':reqm['acceptance_preconditions']}
patch=subprocess.check_output(['git','-C',str(ROOT),'show','--format=','--patch','74dc253d849e3b6b6570fe55df415f5e9da65ab2','--','registry/requirements/REQ-0023.yaml','registry/requirements/REQ-0024.yaml','registry/requirements/REQ-0025.yaml'],text=True)
state=(ROOT/'PROJECT_STATE.md').read_text()
shape={'reviewed_commit':TARGET,'yaml_parse_success':True,'checks':{k:'PASS|FAIL' for k in CHECK_KEYS},'historical_findings':{'total':len(opens),'all_closable':'boolean','closable_ids':opens,'failures':[{'id':'finding id','reason':'string','evidence':'string'}]},'material_findings':[{'severity':'R1_CRITICAL|R2_MAJOR|R3_MODERATE|R4_MINOR','summary':'string','evidence':'string'}],'approval_outcome':'APPROVE|APPROVE_WITH_FOLLOWUP|CHANGES_REQUIRED|BLOCKED','rationale':'concise independent rationale'}
prompt=f'''FINAL fresh-context L2 closure review for MONDE WORK-0001. You did not author this state. Review EXACTLY {TARGET}; fail closed and ignore unsupported author assertions.

Nine checks must each be PASS: {', '.join(CHECK_KEYS)}.
- v10 REVIEW/TEST external imports must be record-specific, one-shot, exact-source/executor/revision-bound, consumed correctly, and must not create generic lifecycle bypass.
- REVIEW-0027 and TEST-0008 provenance must be truthful; TEST-0008 must contain no retroactive READY/RUNNING replay.
- REQ-0023/24/25 acceptance must satisfy the machine and preserve every REQUIREMENT_NORMATIVE_V1 identity field from the c12a5b55 cold read.
- WORK/PROJECT_STATE must remain truthful/non-terminal pending this review; WORK2 and REQ0010/TEST0004 boundaries must remain correct; no R1/R2/R3 defect may remain.

HISTORICAL FINDINGS: exact expected set is {json.dumps(opens)}. For every ID, inspect its originating finding below together with later review/correction evidence and current deterministic state. `closable_ids` must be exactly the subset you independently judge corrected/policy-validly closable. `all_closable=true` only if that subset equals the entire expected set. Any exception goes in failures. Do not close by author assertion alone.

Return ONLY valid JSON in this exact shape:
{json.dumps(shape,separators=(',',':'))}

CURRENT DETERMINISTIC FACTS:
{json.dumps(minimal,separators=(',',':'))}

CANONICAL CONTRACT SLICES:
{json.dumps(contract,separators=(',',':'))}

COMPLETE HISTORICAL REVIEW/FINDING CHAIN (all finding IDs retained):
{json.dumps(hist,separators=(',',':'))}

LIVE UNRESOLVED PR3 THREADS:
{json.dumps(threads,separators=(',',':'))}

ATOMIC ACCEPTANCE PATCH:
{patch}

CURRENT PROJECT_STATE:
{state}
'''
size=len(prompt.encode()); print(f'compact_v2_prompt_bytes={size} reviews={len(hist)} findings={sum(len(x["findings"]) for x in hist)} unresolved_threads={len(threads)}')
if size>=80000: raise SystemExit(f'v2 prompt too large: {size}')
(OUT/'prompt.txt').write_text(prompt)
