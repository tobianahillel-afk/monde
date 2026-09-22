from __future__ import annotations
import subprocess,yaml
from pathlib import Path
from tools.governance import change_guard as c

def run(root,*a):return subprocess.run(['git',*a],cwd=root,text=True,capture_output=True,check=True).stdout.strip()
def write(root,path,data):
    p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(yaml.safe_dump(data) if isinstance(data,dict) else data,encoding='utf-8')
def commit(root,msg):run(root,'add','.');run(root,'commit','-m',msg);return run(root,'rev-parse','HEAD')
def repo(tmp_path,include_guard=True):
    run(tmp_path,'init');run(tmp_path,'config','user.email','x@y');run(tmp_path,'config','user.name','x')
    w={'id':'WORK-1','status':'IN_PROGRESS','purpose':'p','scope':{'in':['a'],'out':[]},'acceptance_criteria':[{'id':'AC','description':'x','status':'NOT_STARTED'}],'assurance':{'level':'A3'},'review_plan':{'completed_reviews':[]}}
    write(tmp_path,'registry/work-items/WORK-1.yaml',w);write(tmp_path,'x.txt','a')
    write(tmp_path,'registry/status-machines.yaml',{'registry_machines':{
        'work_items':{'initial':'PROPOSED','transitions':{'IN_PROGRESS':['IN_REVIEW','PARTIAL','BLOCKED','CANCELLED'],'IN_REVIEW':['IN_PROGRESS','PARTIAL','BLOCKED','DONE'],'DONE':['DEPRECATED'],'CANCELLED':[]}},
        'reviews':{'initial':'OPEN','transitions':{'OPEN':['IN_PROGRESS','CLOSED'],'IN_PROGRESS':['COMPLETE','CLOSED'],'COMPLETE':[],'CLOSED':[]}},
        'requirements':{'initial':'PROPOSED','transitions':{'PROPOSED':['ACCEPTED','CANCELLED'],'ACCEPTED':['SUPERSEDED','DEPRECATED']}},
        'tests':{'initial':'PLANNED','transitions':{'PLANNED':['READY','BLOCKED','CANCELLED'],'READY':['RUNNING','BLOCKED','CANCELLED'],'RUNNING':['PASS','FAIL','BLOCKED'],'PASS':['READY','SUPERSEDED'],'FAIL':['READY','BLOCKED','SUPERSEDED'],'BLOCKED':['READY','CANCELLED','SUPERSEDED'],'CANCELLED':[],'SUPERSEDED':[]}},
    }})
    if include_guard:write(tmp_path,c.GUARD_PATH,'guard')
    return commit(tmp_path,'base')
def test_scope_transition_delete_meta(tmp_path):
    base=repo(tmp_path);w=yaml.safe_load((tmp_path/'registry/work-items/WORK-1.yaml').read_text());w['status']='IN_REVIEW';write(tmp_path,'registry/work-items/WORK-1.yaml',w);base=commit(tmp_path,'review state');w['scope']['in']=['b'];w['status']='DONE';write(tmp_path,'registry/work-items/WORK-1.yaml',w);write(tmp_path,'.github/workflows/x.yml','x');head=commit(tmp_path,'change')
    rules={x.rule for x in c.validate(tmp_path,base,head)};assert 'SCOPE_DRIFT' in rules and 'STATE_TRANSITION' not in rules
    base=head;(tmp_path/'registry/work-items/WORK-1.yaml').unlink();head=commit(tmp_path,'delete');assert 'RECORD_DELETE' in {x.rule for x in c.validate(tmp_path,base,head)}
def test_id_bad_transition_and_meta_without_a3(tmp_path):
    base=repo(tmp_path);w=yaml.safe_load((tmp_path/'registry/work-items/WORK-1.yaml').read_text());w['id']='WORK-2';w['status']='DONE';w['assurance']['level']='A1';w['scope_change']={'approved':True,'rationale':'x'};write(tmp_path,'registry/work-items/WORK-1.yaml',w);write(tmp_path,'tools/governance/x.py','x');head=commit(tmp_path,'bad');rules={x.rule for x in c.validate(tmp_path,base,head)};assert {'ID_IMMUTABLE','STATE_TRANSITION','META_GOVERNANCE'}<=rules
def test_review_freshness_and_admin_neutral(tmp_path):
    base=repo(tmp_path);w=yaml.safe_load((tmp_path/'registry/work-items/WORK-1.yaml').read_text());w['status']='IN_REVIEW';write(tmp_path,'registry/work-items/WORK-1.yaml',w);reviewed=commit(tmp_path,'reviewed')
    rev={'id':'REVIEW-1','status':'COMPLETE','artifact':{'commit_sha':reviewed}};write(tmp_path,'registry/reviews/REVIEW-1.yaml',rev);w['review_plan']['completed_reviews']=['REVIEW-1'];write(tmp_path,'registry/work-items/WORK-1.yaml',w);head=commit(tmp_path,'admin');assert not [x for x in c.validate(tmp_path,reviewed,head) if x.rule=='REVIEW_FRESHNESS']
    base=head;write(tmp_path,'x.txt','behavior');head=commit(tmp_path,'behavior');assert 'REVIEW_FRESHNESS' in {x.rule for x in c.validate(tmp_path,base,head)}
def test_acceptance_status_is_admin_but_meaning_is_semantic():
    a={'acceptance_criteria':[{'id':'AC','description':'same','status':'IN_REVIEW'}]};b={'acceptance_criteria':[{'id':'AC','description':'same','status':'DONE'}]};d={'acceptance_criteria':[{'id':'AC','description':'changed','status':'DONE'}]}
    assert c.semantic_projection(a)==c.semantic_projection(b);assert c.semantic_projection(a)!=c.semantic_projection(d)
    assert c.acceptance_contract('x')=='x';assert c.acceptance_contract(['x'])==['x']
def test_bootstrap_guard_is_nonretroactive(tmp_path):
    base=repo(tmp_path,False);w=yaml.safe_load((tmp_path/'registry/work-items/WORK-1.yaml').read_text());w['scope']['in']=['legacy'];write(tmp_path,'registry/work-items/WORK-1.yaml',w);commit(tmp_path,'legacy change before guard')
    w['scope_change']={'approved':True,'rationale':'bootstrap migration'};write(tmp_path,'registry/work-items/WORK-1.yaml',w);write(tmp_path,c.GUARD_PATH,'introduced');head=commit(tmp_path,'introduce guard')
    assert 'SCOPE_DRIFT' not in {x.rule for x in c.validate(tmp_path,base,head)}
def test_no_guard_sequence_uses_endpoint_only(tmp_path):
    base=repo(tmp_path,False);w=yaml.safe_load((tmp_path/'registry/work-items/WORK-1.yaml').read_text());w['status']='IN_REVIEW';write(tmp_path,'registry/work-items/WORK-1.yaml',w);head=commit(tmp_path,'state before adoption');assert 'STATE_TRANSITION' not in {x.rule for x in c.validate(tmp_path,base,head)}
def test_cli_git_error(tmp_path,capsys):
    assert c.main([str(tmp_path),'--base','a','--head','b'])==2;assert 'CHANGE_GUARD' in capsys.readouterr().err
def test_change_helpers_and_cli_success(tmp_path,capsys):
    base=repo(tmp_path); assert c.ChangeFinding('p','r','m').render().startswith('ERROR r')
    assert c.registry_kind('README.md') is None;assert c.registry_kind('registry/work-items/_TEMPLATE.yaml') is None;assert c.semantic_projection(None)=={}
    assert c.file_exists_at(tmp_path,base,c.GUARD_PATH);assert not c.file_exists_at(tmp_path,base,'missing')
    write(tmp_path,'registry/reviews/REVIEW-1.yaml','x: [');head=commit(tmp_path,'bad yaml');assert c.show_yaml(tmp_path,head,'registry/reviews/REVIEW-1.yaml') is None;assert c.show_yaml(tmp_path,head,'missing.yaml') is None
    out=tmp_path/'out.json';assert c.main([str(tmp_path),'--base',base,'--head',head,'--json-out',str(out)]) in {0,1};assert out.exists();assert 'MONDE change guard' in capsys.readouterr().out
def test_review_missing_history_and_neutral_work(tmp_path):
    base=repo(tmp_path);w=yaml.safe_load((tmp_path/'registry/work-items/WORK-1.yaml').read_text());w['status']='IN_REVIEW';w['review_plan']['completed_reviews']=['REVIEW-1'];w['scope_change']={'approved':True,'rationale':'state'};write(tmp_path,'registry/work-items/WORK-1.yaml',w);write(tmp_path,'registry/reviews/REVIEW-1.yaml',{'id':'REVIEW-1','status':'COMPLETE','artifact':{'commit_sha':'deadbeef'}});head=commit(tmp_path,'review');assert 'REVIEW_FRESHNESS' in {x.rule for x in c.validate(tmp_path,base,head)}
def test_nonwork_transition_and_review_freshness_variants(tmp_path):
    base=repo(tmp_path)
    write(tmp_path,'registry/reviews/REVIEW-2.yaml',{'id':'REVIEW-2','status':'OPEN','artifact':{'commit_sha':''}});b2=commit(tmp_path,'review base')
    write(tmp_path,'registry/reviews/REVIEW-2.yaml',{'id':'REVIEW-2','status':'IN_PROGRESS','artifact':{'commit_sha':''}});h2=commit(tmp_path,'review move');assert not c.validate(tmp_path,b2,h2)
    w=yaml.safe_load((tmp_path/'registry/work-items/WORK-1.yaml').read_text());w['review_plan']['completed_reviews']=['REVIEW-2'];write(tmp_path,'registry/work-items/WORK-1.yaml',w);h3=commit(tmp_path,'ref incomplete');assert not [x for x in c.validate(tmp_path,h2,h3) if x.rule=='REVIEW_FRESHNESS']
    write(tmp_path,'registry/reviews/REVIEW-2.yaml',{'id':'REVIEW-2','status':'COMPLETE','artifact':{'commit_sha':''}});h4=commit(tmp_path,'complete no sha');assert 'REVIEW_FRESHNESS' in {x.rule for x in c.validate(tmp_path,h3,h4)}
    w=yaml.safe_load((tmp_path/'registry/work-items/WORK-1.yaml').read_text());w['review_plan']['completed_reviews']=[];write(tmp_path,'registry/work-items/WORK-1.yaml',w);reviewed=commit(tmp_path,'review point')
    write(tmp_path,'registry/reviews/REVIEW-3.yaml',{'id':'REVIEW-3','status':'COMPLETE','artifact':{'commit_sha':reviewed}});w['review_plan']['completed_reviews']=['REVIEW-3'];w['scope']['in']=['changed'];w['scope_change']={'approved':True,'rationale':'approved'};write(tmp_path,'registry/work-items/WORK-1.yaml',w);head=commit(tmp_path,'semantic after review');assert 'REVIEW_FRESHNESS' in {x.rule for x in c.validate(tmp_path,reviewed,head)}
def test_sequence_scope_drift_after_progress(tmp_path):
    base=repo(tmp_path);w=yaml.safe_load((tmp_path/'registry/work-items/WORK-1.yaml').read_text());w['status']='IN_REVIEW';write(tmp_path,'registry/work-items/WORK-1.yaml',w);commit(tmp_path,'progress')
    w['scope']['in']=['late'];write(tmp_path,'registry/work-items/WORK-1.yaml',w);head=commit(tmp_path,'late drift');assert 'SCOPE_DRIFT' in {x.rule for x in c.validate(tmp_path,base,head)}


def test_merge_of_current_base_does_not_replay_base_transition(tmp_path):
    old_base=repo(tmp_path)
    write(tmp_path,'registry/tests/TEST-1.yaml',{'id':'TEST-1','status':'PASS'})
    old_base=commit(tmp_path,'old test pass')
    run(tmp_path,'branch','feature',old_base);run(tmp_path,'branch','mainline',old_base)
    run(tmp_path,'checkout','feature');write(tmp_path,'feature.txt','feature');commit(tmp_path,'feature change')
    run(tmp_path,'checkout','mainline');write(tmp_path,'registry/tests/TEST-1.yaml',{'id':'TEST-1','status':'SUPERSEDED'});main=commit(tmp_path,'canonical supersede')
    run(tmp_path,'checkout','feature');run(tmp_path,'merge','--no-ff','mainline','-m','integrate current main');head=run(tmp_path,'rev-parse','HEAD')
    findings=c.validate(tmp_path,main,head)
    assert not [f for f in findings if f.rule=='STATE_TRANSITION' and f.path=='registry/tests/TEST-1.yaml']
    exclusive = set(c.pr_commit_edges(tmp_path, main, head, require_guard=False)[0])
    assert not c.inherited_merge_record_allowed(tmp_path, main, main, head, 'missing.yaml', {'id': 'TEST-X'}, exclusive)
    assert not c.inherited_merge_record_allowed(tmp_path, main, main, head, 'registry/tests/TEST-1.yaml', {}, exclusive)


def test_moved_base_does_not_replay_record_inherited_by_historical_merge(tmp_path):
    common = repo(tmp_path)
    run(tmp_path, 'branch', 'feature', common); run(tmp_path, 'branch', 'mainline', common)
    run(tmp_path, 'checkout', 'mainline')
    write(tmp_path, 'registry/reviews/REVIEW-9.yaml', {'id': 'REVIEW-9', 'status': 'OPEN', 'artifact': {'commit_sha': ''}})
    commit(tmp_path, 'review open')
    write(tmp_path, 'registry/reviews/REVIEW-9.yaml', {'id': 'REVIEW-9', 'status': 'IN_PROGRESS', 'artifact': {'commit_sha': ''}})
    commit(tmp_path, 'review progress')
    write(tmp_path, 'registry/reviews/REVIEW-9.yaml', {'id': 'REVIEW-9', 'status': 'COMPLETE', 'artifact': {'commit_sha': ''}})
    old_main = commit(tmp_path, 'review complete')
    run(tmp_path, 'checkout', 'feature'); write(tmp_path, 'feature.txt', 'feature'); commit(tmp_path, 'feature work')
    run(tmp_path, 'merge', '--no-ff', 'mainline', '-m', 'historical main integration')
    historical_merge = run(tmp_path, 'rev-parse', 'HEAD')
    run(tmp_path, 'checkout', 'mainline'); write(tmp_path, 'later.txt', 'later'); moved_base = commit(tmp_path, 'main moves')
    run(tmp_path, 'checkout', 'feature'); run(tmp_path, 'merge', '--no-ff', 'mainline', '-m', 'integrate moved main')
    head = run(tmp_path, 'rev-parse', 'HEAD')
    findings = c.validate(tmp_path, moved_base, head)
    assert not [f for f in findings if f.rule == 'STATE_INITIAL' and f.path == 'registry/reviews/REVIEW-9.yaml']
    assert c.is_ancestor(tmp_path, old_main, moved_base)
    assert c.comparison_parent(tmp_path, moved_base, historical_merge) == old_main


def test_current_base_merge_reuses_guarded_source_history_without_rematerializing(tmp_path):
    common = repo(tmp_path)
    run(tmp_path, 'branch', 'feature', common); run(tmp_path, 'branch', 'mainline', common)
    run(tmp_path, 'checkout', 'feature')
    write(tmp_path, 'registry/reviews/REVIEW-9.yaml', {'id': 'REVIEW-9', 'status': 'OPEN', 'artifact': {'commit_sha': ''}})
    commit(tmp_path, 'branch review open')
    write(tmp_path, 'registry/reviews/REVIEW-9.yaml', {'id': 'REVIEW-9', 'status': 'IN_PROGRESS', 'artifact': {'commit_sha': ''}})
    commit(tmp_path, 'branch review progress')
    write(tmp_path, 'registry/reviews/REVIEW-9.yaml', {'id': 'REVIEW-9', 'status': 'COMPLETE', 'artifact': {'commit_sha': ''}})
    source = commit(tmp_path, 'branch review complete')
    run(tmp_path, 'checkout', 'mainline'); write(tmp_path, 'main.txt', 'main'); base = commit(tmp_path, 'main advances')
    run(tmp_path, 'checkout', 'feature'); run(tmp_path, 'merge', '--no-ff', 'mainline', '-m', 'integrate current main')
    head = run(tmp_path, 'rev-parse', 'HEAD')
    findings = c.validate(tmp_path, base, head)
    assert not [f for f in findings if f.rule == 'STATE_INITIAL' and f.path == 'registry/reviews/REVIEW-9.yaml']
    assert source in c.pr_commit_edges(tmp_path, base, head, require_guard=False)[0]
    assert not c.inherited_merge_record_allowed(
        tmp_path,
        base,
        base,
        head,
        'registry/reviews/REVIEW-9.yaml',
        {'id': 'REVIEW-9'},
        set(),
    )


def test_current_base_merge_does_not_hide_ungoverned_source_introduction(tmp_path):
    common = repo(tmp_path, False)
    run(tmp_path, 'branch', 'feature', common); run(tmp_path, 'branch', 'mainline', common)
    run(tmp_path, 'checkout', 'feature')
    write(tmp_path, 'registry/reviews/REVIEW-9.yaml', {'id': 'REVIEW-9', 'status': 'COMPLETE', 'artifact': {'commit_sha': ''}})
    commit(tmp_path, 'ungoverned terminal review')
    run(tmp_path, 'checkout', 'mainline')
    write(tmp_path, c.GUARD_PATH, 'guard')
    base = commit(tmp_path, 'main adopts guard')
    run(tmp_path, 'checkout', 'feature'); run(tmp_path, 'merge', '--no-ff', 'mainline', '-m', 'integrate guarded main')
    head = run(tmp_path, 'rev-parse', 'HEAD')
    findings = c.validate(tmp_path, base, head)
    assert [f for f in findings if f.rule == 'STATE_INITIAL' and f.path == 'registry/reviews/REVIEW-9.yaml']


def test_merge_conflict_resolution_still_validates_real_status_change(tmp_path):
    common = repo(tmp_path)
    write(tmp_path, 'registry/reviews/REVIEW-9.yaml', {'id': 'REVIEW-9', 'status': 'OPEN', 'artifact': {'commit_sha': ''}})
    common = commit(tmp_path, 'review open')
    run(tmp_path, 'branch', 'feature', common); run(tmp_path, 'branch', 'mainline', common)
    run(tmp_path, 'checkout', 'feature')
    write(tmp_path, 'registry/reviews/REVIEW-9.yaml', {'id': 'REVIEW-9', 'status': 'IN_PROGRESS', 'artifact': {'commit_sha': ''}})
    commit(tmp_path, 'feature progresses review')
    run(tmp_path, 'checkout', 'mainline')
    write(tmp_path, 'registry/reviews/REVIEW-9.yaml', {'id': 'REVIEW-9', 'status': 'CLOSED', 'artifact': {'commit_sha': ''}})
    base = commit(tmp_path, 'main closes review')
    run(tmp_path, 'checkout', 'feature')
    proc = subprocess.run(['git','merge','--no-ff','mainline','-m','conflicting merge'], cwd=tmp_path, text=True, capture_output=True)
    assert proc.returncode != 0
    write(tmp_path, 'registry/reviews/REVIEW-9.yaml', {'id': 'REVIEW-9', 'status': 'COMPLETE', 'artifact': {'commit_sha': ''}})
    head = commit(tmp_path, 'resolve conflict to invalid complete')
    findings = c.validate(tmp_path, base, head)
    assert [f for f in findings if f.rule == 'STATE_TRANSITION' and f.path == 'registry/reviews/REVIEW-9.yaml']


def test_done_unmodified_work_review_is_not_reopened_by_downstream_change(tmp_path):
    base=repo(tmp_path);w=yaml.safe_load((tmp_path/'registry/work-items/WORK-1.yaml').read_text());w['status']='IN_REVIEW';write(tmp_path,'registry/work-items/WORK-1.yaml',w);reviewed=commit(tmp_path,'reviewed')
    write(tmp_path,'registry/reviews/REVIEW-1.yaml',{'id':'REVIEW-1','status':'COMPLETE','artifact':{'commit_sha':reviewed}});w['review_plan']['completed_reviews']=['REVIEW-1'];w['status']='DONE';write(tmp_path,'registry/work-items/WORK-1.yaml',w);base=commit(tmp_path,'done on base')
    write(tmp_path,'x.txt','future downstream behavior');head=commit(tmp_path,'later work')
    assert not [f for f in c.validate(tmp_path,base,head) if f.rule=='REVIEW_FRESHNESS']


def test_canonical_transition_table_is_enforced(tmp_path):
    base=repo(tmp_path);write(tmp_path,'registry/tests/TEST-1.yaml',{'id':'TEST-1','status':'PASS'});base=commit(tmp_path,'pass')
    write(tmp_path,'registry/tests/TEST-1.yaml',{'id':'TEST-1','status':'SUPERSEDED'});head=commit(tmp_path,'supersede')
    assert 'STATE_TRANSITION' not in {f.rule for f in c.validate(tmp_path,base,head)}
    machine=yaml.safe_load((tmp_path/'registry/status-machines.yaml').read_text());machine['registry_machines']['tests']['transitions']['PASS']=[];write(tmp_path,'registry/status-machines.yaml',machine);bad=commit(tmp_path,'remove edge')
    write(tmp_path,'registry/tests/TEST-1.yaml',{'id':'TEST-1','status':'READY'});bad2=commit(tmp_path,'invalid after terminal')
    assert 'STATE_TRANSITION' in {f.rule for f in c.validate(tmp_path,bad,bad2)}


def test_review_freshness_ignores_changes_inherited_before_pr_base(tmp_path):
    reviewed=repo(tmp_path)
    w=yaml.safe_load((tmp_path/'registry/work-items/WORK-1.yaml').read_text())
    w['status']='IN_REVIEW'
    w['affected_paths']=['x.txt']
    w['scope_change']={'approved':True,'rationale':'declare reviewed scope'}
    write(tmp_path,'registry/work-items/WORK-1.yaml',w)
    reviewed=commit(tmp_path,'reviewed scoped work')
    write(tmp_path,'registry/reviews/REVIEW-1.yaml',{'id':'REVIEW-1','status':'COMPLETE','artifact':{'commit_sha':reviewed}})
    w['review_plan']['completed_reviews']=['REVIEW-1']
    write(tmp_path,'registry/work-items/WORK-1.yaml',w)
    write(tmp_path,'x.txt','base inherited behavior')
    base=commit(tmp_path,'base inherits post-review change')
    write(tmp_path,'unrelated.txt','pr-only endpoint')
    head=commit(tmp_path,'unrelated pr change')
    assert not [f for f in c.validate(tmp_path,base,head) if f.rule=='REVIEW_FRESHNESS']



def test_new_terminal_records_fail_initial_state(tmp_path):
    base = repo(tmp_path)
    write(tmp_path, 'registry/tests/TEST-9.yaml', {'id': 'TEST-9', 'status': 'PASS'})
    write(tmp_path, 'registry/reviews/REVIEW-9.yaml', {'id': 'REVIEW-9', 'status': 'COMPLETE', 'artifact': {'commit_sha': base}, 'outcome': 'APPROVE'})
    write(tmp_path, 'registry/requirements/REQ-9.yaml', {'id': 'REQ-9', 'status': 'ACCEPTED'})
    head = commit(tmp_path, 'bad terminal introductions')
    assert len([f for f in c.validate(tmp_path, base, head) if f.rule == 'STATE_INITIAL']) == 3


def test_requirement_acceptance_requires_bound_review_and_cold_read(tmp_path):
    base = repo(tmp_path)
    req = {'id': 'REQ-1', 'status': 'PROPOSED', 'content_identity': {'scheme': 'REQUIREMENT_NORMATIVE_V1', 'digest': 'sha256:' + 'a' * 64}, 'verification': {'acceptance_evidence': [], 'acceptance_cold_read_test_ids': []}}
    write(tmp_path, 'registry/requirements/REQ-1.yaml', req)
    base = commit(tmp_path, 'proposed requirement')
    req['status'] = 'ACCEPTED'
    write(tmp_path, 'registry/requirements/REQ-1.yaml', req)
    head = commit(tmp_path, 'accept without proof')
    assert 'ACCEPTANCE_PRECONDITION' in {f.rule for f in c.validate(tmp_path, base, head)}


def test_review_ref_must_be_full_existing_ancestor(tmp_path):
    base = repo(tmp_path)
    w = yaml.safe_load((tmp_path / 'registry/work-items/WORK-1.yaml').read_text())
    w['status'] = 'IN_REVIEW'; w['review_plan']['completed_reviews'] = ['REVIEW-1']
    write(tmp_path, 'registry/work-items/WORK-1.yaml', w)
    write(tmp_path, 'registry/reviews/REVIEW-1.yaml', {'id': 'REVIEW-1', 'status': 'COMPLETE', 'artifact': {'commit_sha': 'HEAD'}})
    head = commit(tmp_path, 'mutable review ref')
    assert 'REVIEW_FRESHNESS' in {f.rule for f in c.validate(tmp_path, base, head)}


def test_required_test_contract_change_stales_review_but_execution_metadata_does_not(tmp_path):
    base = repo(tmp_path)
    w = yaml.safe_load((tmp_path / 'registry/work-items/WORK-1.yaml').read_text())
    w['status'] = 'IN_REVIEW'; w['required_tests'] = {'unit': ['TEST-1']}
    write(tmp_path, 'registry/work-items/WORK-1.yaml', w)
    test = {'id': 'TEST-1', 'status': 'PASS', 'name': 't', 'type': 'UNIT', 'protects': {'contracts': ['c']}, 'cases': {'happy': ['x']}, 'execution_definition': {'command': 'pytest'}, 'execution_evidence_policy': {'source_of_truth': 'CI', 'rule': 'sha'}, 'execution': {'command_or_workflow': 'pytest', 'commit_sha': '0' * 40, 'result': 'PASS', 'evidence': ['x']}}
    write(tmp_path, 'registry/tests/TEST-1.yaml', test)
    reviewed = commit(tmp_path, 'reviewed test contract')
    write(tmp_path, 'registry/reviews/REVIEW-1.yaml', {'id': 'REVIEW-1', 'status': 'COMPLETE', 'artifact': {'commit_sha': reviewed}})
    w['review_plan']['completed_reviews'] = ['REVIEW-1']; write(tmp_path, 'registry/work-items/WORK-1.yaml', w)
    admin = commit(tmp_path, 'attach review')
    test['execution']['evidence'] = ['new run']; write(tmp_path, 'registry/tests/TEST-1.yaml', test)
    meta = commit(tmp_path, 'execution metadata')
    assert 'REVIEW_FRESHNESS' not in {f.rule for f in c.validate(tmp_path, admin, meta)}
    base = meta; test['cases'] = {'happy': ['weakened']}; write(tmp_path, 'registry/tests/TEST-1.yaml', test)
    head = commit(tmp_path, 'test semantic drift')
    assert 'REVIEW_FRESHNESS' in {f.rule for f in c.validate(tmp_path, base, head)}


def test_endpoint_changes_use_merge_base_not_moved_base_tip(tmp_path):
    common = repo(tmp_path)
    run(tmp_path, 'branch', 'feature', common); run(tmp_path, 'branch', 'mainline', common)
    run(tmp_path, 'checkout', 'feature'); write(tmp_path, 'feature.txt', 'feature'); head = commit(tmp_path, 'feature')
    run(tmp_path, 'checkout', 'mainline'); write(tmp_path, 'registry/reviews/BASE-ONLY.yaml', {'id': 'REVIEW-99', 'status': 'OPEN'}); base = commit(tmp_path, 'base only')
    run(tmp_path, 'checkout', 'feature')
    assert 'registry/reviews/BASE-ONLY.yaml' not in c.endpoint_changed_files(tmp_path, base, head)
