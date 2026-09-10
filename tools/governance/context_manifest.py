from __future__ import annotations
import argparse,json,subprocess
from pathlib import Path
from typing import Any
import yaml

def git(root:Path,*args:str)->str:
    p=subprocess.run(["git",*args],cwd=root,text=True,capture_output=True,check=False)
    if p.returncode:raise RuntimeError(p.stderr.strip() or "git failed")
    return p.stdout
def changed(root:Path,base:str,head:str)->list[str]:return [x for x in git(root,"diff","--name-only",f"{base}..{head}").splitlines() if x]
def load(path:Path)->dict[str,Any]:
    try:data=yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError,yaml.YAMLError):return {}
    return data if isinstance(data,dict) else {}
def active_work(root:Path)->list[Path]:
    out=[]
    for p in sorted((root/"registry/work-items").glob("WORK-*.yaml")):
        if load(p).get("status") in {"READY","IN_PROGRESS","PARTIAL","BLOCKED","IN_REVIEW"}:out.append(p)
    return out
def build(root:Path,base:str,head:str)->dict[str,Any]:
    files=changed(root,base,head);works=active_work(root);must=["README.md","AGENTS.md","docs/00_START_HERE.md","PROJECT_STATE.md"]
    should=[];ondemand=[];levels=[]
    for p in works:
        d=load(p);must.append(str(p.relative_to(root)));must.extend(d.get("read_before",[]) or []);should.extend(d.get("affected_docs",[]) or []);ondemand.extend(d.get("affected_schemas",[]) or []);levels.append((d.get("assurance") or {}).get("level"))
    for fp in files:
        if fp.endswith((".py",".yml",".yaml",".json")):should.append(fp)
    def uniq(v):return list(dict.fromkeys(x for x in v if isinstance(x,str)))
    must=uniq(must);should=[x for x in uniq(should) if x not in must];ondemand=[x for x in uniq(ondemand) if x not in must and x not in should]
    est=sum((root/x).stat().st_size for x in must if (root/x).exists())//4
    return {"base_sha":base,"head_sha":head,"active_work":[p.stem for p in works],"assurance_levels":levels,"changed_files":files,"context":{"must_read":must,"should_read":should,"on_demand":ondemand,"estimated_must_read_tokens":est,"budget_tier":"T0" if est<=5000 else "T1" if est<=20000 else "T2"}}
def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser();p.add_argument("root",nargs="?",default=".");p.add_argument("--base",required=True);p.add_argument("--head",required=True);p.add_argument("--out",required=True);a=p.parse_args(argv)
    try:d=build(Path(a.root).resolve(),a.base,a.head)
    except RuntimeError as exc:print(f"ERROR CONTEXT {exc}");return 2
    Path(a.out).write_text(json.dumps(d,indent=2),encoding="utf-8");print(f"MONDE context manifest: {len(d['context']['must_read'])} MUST_READ files");return 0
if __name__=="__main__":raise SystemExit(main()) # pragma: no cover
