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
    if include_guard:write(tmp_path,c.GUARD_PATH,'guard')
    return commit(tmp_path,'base')
def test_scope_transition_delete_meta(tmp_path):
    base=repo(tmp_path);w=yaml.safe_load((tmp_path/'registry/work-items/WORK-1.yaml').read_text());w['scope']['in']=['b'];w['status']='DONE';write(tmp_path,'registry/work-items/WORK-1.yaml',w);write(tmp_path,'.github/workflows/x.yml','x');head=commit(tmp_path,'change')
    rules={x.rule for x in c.validate(tmp_path,base,head)};assert 'SCOPE_DRIFT' in rules and 'STATE_TRANSITION' not in rules
    base=head;(tmp_path/'registry/work-items/WORK-1.yaml').unlink();head=commit(tmp_path,'delete');assert 'RECORD_DELETE' in {x.rule for x in c.validate(tmp_path,base,head)}
def test_id_bad_transition_and_meta_without_a3(tmp_path):
    base=repo(tmp_path);w=yaml.safe_load((tmp_path/'registry/work-items/WORK-1.yaml').read_text());w['id']='WORK-2';w['status']='CANCELLED';w['assurance']['level']='A1';w['scope_change']={'approved':True,'rationale':'x'};write(tmp_path,'registry/work-items/WORK-1.yaml',w);write(tmp_path,'tools/governance/x.py','x');head=commit(tmp_path,'bad');rules={x.rule for x in c.validate(tmp_path,base,head)};assert {'ID_IMMUTABLE','STATE_TRANSITION','META_GOVERNANCE'}<=rules
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
    write(tmp_path,'registry/reviews/REVIEW-2.yaml',{'id':'REVIEW-2','status':'COMPLETE','artifact':{'commit_sha':''}});h4=commit(tmp_path,'complete no sha');assert not [x for x in c.validate(tmp_path,h3,h4) if x.rule=='REVIEW_FRESHNESS']
    w=yaml.safe_load((tmp_path/'registry/work-items/WORK-1.yaml').read_text());w['review_plan']['completed_reviews']=[];write(tmp_path,'registry/work-items/WORK-1.yaml',w);reviewed=commit(tmp_path,'review point')
    write(tmp_path,'registry/reviews/REVIEW-3.yaml',{'id':'REVIEW-3','status':'COMPLETE','artifact':{'commit_sha':reviewed}});w['review_plan']['completed_reviews']=['REVIEW-3'];w['scope']['in']=['changed'];w['scope_change']={'approved':True,'rationale':'approved'};write(tmp_path,'registry/work-items/WORK-1.yaml',w);head=commit(tmp_path,'semantic after review');assert 'REVIEW_FRESHNESS' in {x.rule for x in c.validate(tmp_path,reviewed,head)}
def test_sequence_scope_drift_after_progress(tmp_path):
    base=repo(tmp_path);w=yaml.safe_load((tmp_path/'registry/work-items/WORK-1.yaml').read_text());w['status']='IN_REVIEW';write(tmp_path,'registry/work-items/WORK-1.yaml',w);commit(tmp_path,'progress')
    w['scope']['in']=['late'];write(tmp_path,'registry/work-items/WORK-1.yaml',w);head=commit(tmp_path,'late drift');assert 'SCOPE_DRIFT' in {x.rule for x in c.validate(tmp_path,base,head)}
