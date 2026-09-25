import subprocess,yaml,json
from tools.governance import context_manifest as c

def run(root,*a):return subprocess.run(['git',*a],cwd=root,text=True,capture_output=True,check=True).stdout.strip()
def test_build_and_cli(tmp_path):
    run(tmp_path,'init');run(tmp_path,'config','user.email','x@y');run(tmp_path,'config','user.name','x')
    for f in ['README.md','AGENTS.md','PROJECT_STATE.md']:(tmp_path/f).write_text('x')
    (tmp_path/'docs').mkdir();(tmp_path/'docs/00_START_HERE.md').write_text('x');(tmp_path/'registry/work-items').mkdir(parents=True)
    d={'id':'WORK-1','status':'IN_PROGRESS','read_before':['README.md'],'affected_docs':['AGENTS.md'],'affected_schemas':['schema.json'],'assurance':{'level':'A3'}};(tmp_path/'registry/work-items/WORK-1.yaml').write_text(yaml.safe_dump(d));run(tmp_path,'add','.');run(tmp_path,'commit','-m','b');base=run(tmp_path,'rev-parse','HEAD');(tmp_path/'schema.json').write_text('{}');run(tmp_path,'add','.');run(tmp_path,'commit','-m','h');head=run(tmp_path,'rev-parse','HEAD')
    m=c.build(tmp_path,base,head);assert 'WORK-1' in m['active_work'];assert m['context']['budget_tier'] in {'T0','T1','T2'}
    out=tmp_path/'o.json';assert c.main([str(tmp_path),'--base',base,'--head',head,'--out',str(out)])==0;assert json.loads(out.read_text())['head_sha']==head
def test_git_error(tmp_path):assert c.main([str(tmp_path),'--base','x','--head','y','--out',str(tmp_path/'o')])==2
def test_load_bad_and_tiers(tmp_path):
    p=tmp_path/'bad.yaml';p.write_text('x: [');assert c.load(p)=={};p.write_text('- x');assert c.load(p)=={}
