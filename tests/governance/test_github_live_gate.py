import json
from tools.governance import github_live_gate as g
class Resp:
    def __init__(self,d):self.d=d
    def __enter__(self):return self
    def __exit__(self,*a):pass
    def read(self):return json.dumps(self.d).encode()
def test_request(monkeypatch):
    monkeypatch.setattr(g.urllib.request,'urlopen',lambda req,timeout:Resp({'x':1}));assert g.request_json('https://x.test','t')=={'x':1}
    monkeypatch.setattr(g.urllib.request,'urlopen',lambda req,timeout:Resp([1]))
    try:g.request_json('https://x.test','t')
    except RuntimeError:pass
    else:assert False
def test_validate_draft_ready_threads(monkeypatch):
    def req(url,token,method='GET',body=None):
        if 'pulls/' in url:return {'head':{'sha':'h'},'draft':True,'state':'open','mergeable':True}
        return {}
    monkeypatch.setattr(g,'request_json',req);f,s=g.validate('o/r',1,'h','t');assert not f and s=='DEFERRED_DRAFT'
    def req2(url,token,method='GET',body=None):
        if 'pulls/' in url:return {'head':{'sha':'other'},'draft':False,'state':'closed','mergeable':None}
        return {'data': {'repository': {'pullRequest': {'reviewThreads': {'nodes': [{'id':'1','isResolved':False}], 'pageInfo': {'hasNextPage':False,'endCursor':None}}}}}}
    monkeypatch.setattr(g,'request_json',req2);f,s=g.validate('o/r',1,'h','t');rules={x.rule for x in f};assert {'HEAD_MISMATCH','PR_STATE','MERGEABLE','UNRESOLVED_THREADS'}<=rules and s=='READY_CHECKED'
def test_thread_pagination_errors(monkeypatch):
    pages=iter([{'data': {'repository': {'pullRequest': {'reviewThreads': {'nodes': [], 'pageInfo': {'hasNextPage': True, 'endCursor': 'c'}}}}}}, {'data': {'repository': {'pullRequest': {'reviewThreads': {'nodes': [{'id':'x','isResolved':True}], 'pageInfo': {'hasNextPage': False}}}}}}]);monkeypatch.setattr(g,'request_json',lambda *a,**k:next(pages));assert len(g.fetch_threads('o/r',1,'t'))==1
    monkeypatch.setattr(g,'request_json',lambda *a,**k:{'errors':['x']})
    try:g.fetch_threads('o/r',1,'t')
    except RuntimeError:pass
    else:assert False
    monkeypatch.setattr(g,'request_json',lambda *a,**k:{'data':{}})
    try:g.fetch_threads('o/r',1,'t')
    except RuntimeError:pass
    else:assert False
    monkeypatch.setattr(g,'request_json',lambda *a,**k:{'data': {'repository': {'pullRequest': {'reviewThreads': {'nodes': [], 'pageInfo': {'hasNextPage': True}}}}}})
    try:g.fetch_threads('o/r',1,'t')
    except RuntimeError:pass
    else:assert False
def test_main(monkeypatch,tmp_path):
    monkeypatch.delenv('GITHUB_TOKEN',raising=False);assert g.main(['--repo','o/r','--pr','1','--head','h'])==2
    monkeypatch.setenv('GITHUB_TOKEN','t');monkeypatch.setattr(g,'validate',lambda *a: ([], 'READY_CHECKED'));out=tmp_path/'o.json';assert g.main(['--repo','o/r','--pr','1','--head','h','--json-out',str(out)])==0
    monkeypatch.setattr(g,'validate',lambda *a: (_ for _ in ()).throw(RuntimeError('x')));assert g.main(['--repo','o/r','--pr','1','--head','h'])==2
def test_live_finding_render():assert g.LiveFinding('R','m').render()=='ERROR R: m'
