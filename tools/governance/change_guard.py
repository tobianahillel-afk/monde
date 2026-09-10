from __future__ import annotations
import argparse,json,subprocess,sys
from dataclasses import asdict,dataclass
from pathlib import Path
from typing import Any
import yaml

TRANSITIONS={
"work-items":{"NOT_STARTED":{"PROPOSED","PLANNED"},"PROPOSED":{"PLANNED","CANCELLED"},"PLANNED":{"READY","IN_PROGRESS","BLOCKED","CANCELLED"},"READY":{"IN_PROGRESS","BLOCKED"},"IN_PROGRESS":{"PARTIAL","BLOCKED","IN_REVIEW","DONE"},"PARTIAL":{"IN_PROGRESS","BLOCKED","IN_REVIEW"},"BLOCKED":{"IN_PROGRESS","CANCELLED"},"IN_REVIEW":{"IN_PROGRESS","DONE","BLOCKED"},"DONE":{"DEPRECATED"},"DEPRECATED":set(),"CANCELLED":set(),"NOT_APPLICABLE":set()},
"reviews":{"OPEN":{"IN_PROGRESS","CLOSED"},"IN_PROGRESS":{"COMPLETE","CLOSED"},"COMPLETE":{"CLOSED"},"CLOSED":set()},
"tests":{"NOT_STARTED":{"PLANNED","READY"},"PLANNED":{"READY","BLOCKED"},"READY":{"PASS","FAIL","BLOCKED"},"PASS":{"FAIL","DEPRECATED"},"FAIL":{"READY","BLOCKED","DEPRECATED"},"BLOCKED":{"READY","DEPRECATED"},"DEPRECATED":set()},
}
META_PATH_PREFIXES=(".github/","tools/governance/","schemas/registry/","scripts/governance_")
ADMIN_PATH_PREFIXES=("registry/reviews/","registry/tests/","registry/progress/","PROJECT_STATE.md")
SEMANTIC_WORK_KEYS={"purpose","scope","acceptance_criteria","requirements","assumptions","risks","assurance","depends_on","reuses","contracts","impact_analysis","required_tests","scientific_validation","risk","rollback"}
@dataclass(frozen=True)
class ChangeFinding:
    path:str;rule:str;message:str
    def render(self):return f"ERROR {self.rule} {self.path}: {self.message}"
def git(root:Path,*args:str)->str:
    p=subprocess.run(["git",*args],cwd=root,text=True,capture_output=True,check=False)
    if p.returncode:raise RuntimeError(p.stderr.strip() or "git command failed")
    return p.stdout
def changed_files(root:Path,base:str,head:str)->list[str]:return [x for x in git(root,"diff","--name-only",f"{base}..{head}").splitlines() if x]
def show_yaml(root:Path,sha:str,path:str)->dict[str,Any]|None:
    try:text=git(root,"show",f"{sha}:{path}")
    except RuntimeError:return None
    try:data=yaml.safe_load(text)
    except yaml.YAMLError:return None
    return data if isinstance(data,dict) else None
def registry_kind(path:str)->str|None:
    parts=Path(path).parts
    return parts[1] if len(parts)>=3 and parts[0]=="registry" and path.endswith(".yaml") and not Path(path).name.startswith("_") else None
def semantic_projection(data:dict[str,Any]|None)->dict[str,Any]:
    if not data:return {}
    return {k:data.get(k) for k in sorted(SEMANTIC_WORK_KEYS) if k in data}
def validate(root:Path,base:str,head:str)->list[ChangeFinding]:
    out=[];files=changed_files(root,base,head)
    for path in files:
        kind=registry_kind(path)
        if not kind:continue
        old=show_yaml(root,base,path);new=show_yaml(root,head,path)
        if old and not new:out.append(ChangeFinding(path,"RECORD_DELETE","published registry records must be superseded/deprecated, not deleted"));continue
        if not old or not new:continue
        if old.get("id")!=new.get("id"):out.append(ChangeFinding(path,"ID_IMMUTABLE","registry id changed across base→head"))
        before=old.get("status")
        if kind=="work-items" and before in {"READY","IN_PROGRESS","PARTIAL","BLOCKED","IN_REVIEW"}:
            if semantic_projection(old)!=semantic_projection(new):
                scope_change=new.get("scope_change") or {}
                if scope_change.get("approved") is not True or not scope_change.get("rationale"):
                    out.append(ChangeFinding(path,"SCOPE_DRIFT","semantic scope/AC/contracts changed after READY without approved scope_change rationale"))
    # Validate state transitions and late scope drift against the actual commit sequence.
    commits=[base]+[x for x in git(root,"rev-list","--reverse",f"{base}..{head}").splitlines() if x]
    for path in files:
        kind=registry_kind(path); allowed=TRANSITIONS.get(kind or "")
        if not allowed:continue
        previous=show_yaml(root,commits[0],path)
        for sha in commits[1:]:
            current=show_yaml(root,sha,path)
            if previous and current:
                before,after=previous.get("status"),current.get("status")
                if before!=after and after not in allowed.get(str(before),set()):
                    out.append(ChangeFinding(path,"STATE_TRANSITION",f"invalid {kind} transition {before} -> {after} at {sha[:12]}"))
                if kind=="work-items" and before in {"READY","IN_PROGRESS","PARTIAL","BLOCKED","IN_REVIEW"} and semantic_projection(previous)!=semantic_projection(current):
                    scope_change=current.get("scope_change") or {}
                    if scope_change.get("approved") is not True or not scope_change.get("rationale"):
                        out.append(ChangeFinding(path,"SCOPE_DRIFT",f"semantic scope/AC/contracts changed at {sha[:12]} without approved scope_change rationale"))
            previous=current if current is not None else previous
    if any(path.startswith(META_PATH_PREFIXES) for path in files):
        works=[show_yaml(root,head,p) for p in files if p.startswith("registry/work-items/") and p.endswith(".yaml")]
        if not any(w and (w.get("assurance") or {}).get("level") in {"A3","A4"} for w in works):out.append(ChangeFinding(".github/tools/governance","META_GOVERNANCE","meta-governance change requires an affected A3/A4 work item in the change"))
    # A completed review remains fresh only when subsequent changes are administrative/semantic-neutral.
    work_paths=[x for x in git(root,"ls-tree","-r","--name-only",head,"registry/work-items").splitlines() if x.endswith(".yaml") and not Path(x).name.startswith("_")]
    for path in work_paths:
        work=show_yaml(root,head,path) or {};plan=work.get("review_plan") or {}
        for rid in plan.get("completed_reviews",[]) or []:
            review_path=f"registry/reviews/{rid}.yaml";review=show_yaml(root,head,review_path)
            if not review or review.get("status") not in {"COMPLETE","CLOSED"}:continue
            reviewed=str((review.get("artifact") or {}).get("commit_sha") or "")
            if not reviewed or reviewed==head:continue
            try:later=changed_files(root,reviewed,head)
            except RuntimeError:out.append(ChangeFinding(review_path,"REVIEW_FRESHNESS","review commit is not available in history"));continue
            substantive=[]
            for fp in later:
                if fp.startswith(ADMIN_PATH_PREFIXES):continue
                if fp==path:
                    oldw=show_yaml(root,reviewed,path);neww=show_yaml(root,head,path)
                    if semantic_projection(oldw)==semantic_projection(neww):continue
                substantive.append(fp)
            if substantive:out.append(ChangeFinding(review_path,"REVIEW_FRESHNESS",f"review {rid} predates substantive changes: {', '.join(substantive[:8])}"))
    return out
def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser();p.add_argument("root",nargs="?",default=".");p.add_argument("--base",required=True);p.add_argument("--head",required=True);p.add_argument("--json-out");a=p.parse_args(argv)
    try:f=validate(Path(a.root).resolve(),a.base,a.head)
    except RuntimeError as exc:print(f"ERROR CHANGE_GUARD {exc}",file=sys.stderr);return 2
    for x in f:print(x.render(),file=sys.stderr)
    if a.json_out:Path(a.json_out).write_text(json.dumps([asdict(x) for x in f],indent=2),encoding="utf-8")
    print(f"MONDE change guard: {len(f)} error(s)");return 1 if f else 0
if __name__=="__main__":raise SystemExit(main()) # pragma: no cover
