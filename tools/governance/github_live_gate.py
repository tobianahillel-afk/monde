from __future__ import annotations
import argparse,json,os,sys,urllib.error,urllib.request
from dataclasses import asdict,dataclass
from pathlib import Path
from typing import Any
@dataclass(frozen=True)
class LiveFinding:
    rule:str;message:str
    def render(self):
        return f"ERROR {self.rule}: {self.message}"
def request_json(url:str,token:str,method:str="GET",body:dict[str,Any]|None=None)->dict[str,Any]:
    data=json.dumps(body).encode() if body is not None else None
    req=urllib.request.Request(url,data=data,method=method,headers={"Accept":"application/vnd.github+json","Authorization":f"Bearer {token}","X-GitHub-Api-Version":"2022-11-28","Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=20) as r:
        parsed=json.loads(r.read().decode())
    if not isinstance(parsed,dict):raise RuntimeError("GitHub returned non-object JSON")
    return parsed
def fetch_threads(repo:str,pr:int,token:str)->list[dict[str,Any]]:
    owner,name=repo.split("/",1);query='''query($owner:String!,$name:String!,$number:Int!,$cursor:String){repository(owner:$owner,name:$name){pullRequest(number:$number){reviewThreads(first:100,after:$cursor){nodes{id isResolved} pageInfo{hasNextPage endCursor}}}}}'''
    cursor=None;nodes=[]
    while True:
        payload={"query":query,"variables":{"owner":owner,"name":name,"number":pr,"cursor":cursor}}
        res=request_json("https://api.github.com/graphql",token,"POST",payload)
        if res.get("errors"):raise RuntimeError(f"GraphQL errors: {res['errors']}")
        try:page=res["data"]["repository"]["pullRequest"]["reviewThreads"]
        except (KeyError,TypeError) as exc:raise RuntimeError("malformed reviewThreads response") from exc
        nodes.extend(page.get("nodes") or [])
        info=page.get("pageInfo") or {}
        if not info.get("hasNextPage"):break
        cursor=info.get("endCursor")
        if not cursor:raise RuntimeError("pagination says next page but endCursor is missing")
    return nodes
def validate(repo:str,pr:int,head:str,token:str)->tuple[list[LiveFinding],str]:
    info=request_json(f"https://api.github.com/repos/{repo}/pulls/{pr}",token);find=[]
    actual=((info.get("head") or {}).get("sha"))
    if actual!=head:find.append(LiveFinding("HEAD_MISMATCH",f"expected {head}, GitHub reports {actual}"))
    if info.get("draft") is True:return find,"DEFERRED_DRAFT"
    if info.get("state")!="open":find.append(LiveFinding("PR_STATE",f"PR is {info.get('state')!r}, expected open"))
    if info.get("mergeable") is not True:find.append(LiveFinding("MERGEABLE",f"GitHub mergeable={info.get('mergeable')!r}; fail closed"))
    threads=fetch_threads(repo,pr,token);unresolved=[t.get("id") for t in threads if not t.get("isResolved")]
    if unresolved:find.append(LiveFinding("UNRESOLVED_THREADS",f"{len(unresolved)} unresolved review thread(s)"))
    return find,"READY_CHECKED"
def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser();p.add_argument("--repo",required=True);p.add_argument("--pr",required=True,type=int);p.add_argument("--head",required=True);p.add_argument("--json-out");a=p.parse_args(argv);token=os.environ.get("GITHUB_TOKEN","")
    if not token:print("ERROR LIVE_GATE: GITHUB_TOKEN is required",file=sys.stderr);return 2
    try:find,status=validate(a.repo,a.pr,a.head,token)
    except (RuntimeError,urllib.error.URLError,json.JSONDecodeError) as exc:print(f"ERROR LIVE_GATE: {exc}",file=sys.stderr);return 2
    for x in find:print(x.render(),file=sys.stderr)
    payload={"status":status,"findings":[asdict(x) for x in find],"repo":a.repo,"pr":a.pr,"head":a.head}
    if a.json_out:Path(a.json_out).write_text(json.dumps(payload,indent=2),encoding="utf-8")
    print(f"MONDE GitHub live gate: {status}, {len(find)} error(s)");return 1 if find else 0
if __name__=="__main__":raise SystemExit(main()) # pragma: no cover
