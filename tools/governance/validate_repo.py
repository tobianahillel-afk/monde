from __future__ import annotations
import argparse,json,re,sys
from dataclasses import asdict,dataclass
from datetime import date
from pathlib import Path
from typing import Any,Iterable
import yaml
from jsonschema import Draft202012Validator
from .path_safety import markdown_destination

GLOBAL_STATUSES={"NOT_STARTED","PROPOSED","PLANNED","READY","IN_PROGRESS","PARTIAL","BLOCKED","IN_REVIEW","DONE","DEPRECATED","CANCELLED","NOT_APPLICABLE"}
STATUS_BY_KIND={
"work-items":GLOBAL_STATUSES,"capabilities":GLOBAL_STATUSES,
"requirements":GLOBAL_STATUSES|{"ACCEPTED","SUPERSEDED"},
"assumptions":{"OPEN","VALIDATED","REFUTED","EXPIRED","SUPERSEDED","CLOSED"},
"risks":{"OPEN","ACCEPTED","MITIGATED","MATERIALIZED","CLOSED"},
"reviews":{"OPEN","IN_PROGRESS","COMPLETE","CLOSED"},
"tests":{"NOT_STARTED","PLANNED","READY","PASS","FAIL","BLOCKED","DEPRECATED"},
"experiments":{"NOT_STARTED","PLANNED","READY","IN_PROGRESS","PASS","FAIL","BLOCKED","COMPLETE","DEPRECATED"}}
PREFIX_BY_KIND={"work-items":"WORK-","capabilities":"CAP-","requirements":"REQ-","assumptions":"ASM-","risks":"RISK-","reviews":"REVIEW-","tests":"TEST-","experiments":"EXP-"}
ID_PATTERN=re.compile(r"\b(WORK|CAP|REQ|ASM|RISK|REVIEW|TEST|EXP)-\d+\b")
MARKDOWN_LINK=re.compile(r"\[[^\]]+\]\(([^)]+)\)")
PLACEHOLDER=re.compile(r"\b(TODO|TBD|FIXME)\b",re.I)
PINNED_ACTION=re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*@[0-9a-f]{40}$")
PINNED_DOCKER=re.compile(r"^docker://[^@\s]+@sha256:[0-9a-f]{64}$")
SECRET_PATTERNS=(re.compile(r"AKIA[0-9A-Z]{16}"),re.compile(r"ghp_[A-Za-z0-9]{30,}"),re.compile(r"github_pat_[A-Za-z0-9_]{50,}"),re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"))
DONE_PROGRESS_ALLOWED={"DONE","NOT_APPLICABLE"}
@dataclass(frozen=True)
class Issue:
    path:str;rule:str;message:str;severity:str="ERROR"
    def render(self)->str:return f"{self.severity} {self.rule} {self.path}: {self.message}"
@dataclass
class Record:
    kind:str;path:Path;data:dict[str,Any]
    @property
    def id(self)->str:return str(self.data.get("id", ""))
class Validator:
    def __init__(self,root:Path,today:date|None=None):self.root=root.resolve();self.today=today or date.today();self.issues=[];self.records=[];self.by_id={}
    def add(self,path:Path|str,rule:str,message:str,severity:str="ERROR"):
        p=str(path)
        if isinstance(path,Path):
            try:p=str(path.resolve().relative_to(self.root))
            except ValueError:p=str(path)
        self.issues.append(Issue(p,rule,message,severity))
    def load_yaml(self,path:Path)->Any|None:
        try:return yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError,yaml.YAMLError) as exc:self.add(path,"YAML_PARSE",str(exc));return None
    def discover_records(self):
        base=self.root/"registry"
        for kind,prefix in PREFIX_BY_KIND.items():
            d=base/kind
            if not d.exists():continue
            for path in sorted(d.glob("*.yaml")):
                if path.name.startswith("_"):continue
                data=self.load_yaml(path)
                if data is None:continue
                if not isinstance(data,dict):self.add(path,"RECORD_SHAPE","registry record must be a YAML mapping");continue
                r=Record(kind,path,data);self.records.append(r)
                if not r.id:self.add(path,"ID_REQUIRED","registry record is missing id")
                elif not r.id.startswith(prefix):self.add(path,"ID_PREFIX",f"id {r.id!r} must start with {prefix}")
                elif r.id in self.by_id:self.add(path,"ID_UNIQUE",f"duplicate id {r.id}")
                else:self.by_id[r.id]=r
    def validate_schemas(self):
        for r in self.records:
            path=self.root/"schemas/registry"/f"{r.kind}.schema.json"
            if not path.exists():self.add(r.path,"SCHEMA_MISSING",f"missing schema {path.relative_to(self.root)}");continue
            try:schema=json.loads(path.read_text(encoding="utf-8"))
            except (OSError,json.JSONDecodeError) as exc:self.add(path,"SCHEMA_PARSE",str(exc));continue
            for error in Draft202012Validator(schema).iter_errors(r.data):self.add(r.path,"SCHEMA",error.message)
    def validate_statuses(self):
        for r in self.records:
            if r.data.get("status") not in STATUS_BY_KIND[r.kind]:self.add(r.path,"STATUS",f"invalid status {r.data.get('status')!r} for {r.kind}")
    def iter_strings(self,v:Any)->Iterable[str]:
        if isinstance(v,str):yield v
        elif isinstance(v,dict):
            for x in v.values():yield from self.iter_strings(x)
        elif isinstance(v,list):
            for x in v:yield from self.iter_strings(x)
    def validate_references(self):
        for r in self.records:
            for text in self.iter_strings(r.data):
                for m in ID_PATTERN.finditer(text):
                    ref=m.group(0)
                    if ref!=r.id and ref not in self.by_id:self.add(r.path,"REFERENCE",f"unknown registry reference {ref}")
    def validate_paths(self):
        for r in self.records:
            for key in ("read_before","affected_docs","affected_schemas"):
                vals=r.data.get(key,[]) or []
                if not isinstance(vals,list):self.add(r.path,"PATH_LIST",f"{key} must be a list");continue
                for val in vals:
                    if not isinstance(val,str):self.add(r.path,"PATH_TYPE",f"{key} contains non-string path {val!r}")
                    elif not (self.root/val).exists():self.add(r.path,"PATH_EXISTS",f"{key} path does not exist: {val}")
    def validate_work_tasks(self,r:Record):
        plan=r.data.get("implementation_plan",{}) or {};tasks=plan.get("tasks",[]) or [];runs=plan.get("planned_runs",[]) or []
        ids={t.get("id") for t in tasks if isinstance(t,dict) and t.get("id")}
        for t in tasks:
            if not isinstance(t,dict):self.add(r.path,"TASK_SHAPE","task must be a mapping");continue
            for dep in t.get("depends_on",[]) or []:
                if dep not in ids:self.add(r.path,"TASK_DEP",f"task {t.get('id')} depends on unknown task {dep}")
        for run in runs:
            if not isinstance(run,dict):self.add(r.path,"RUN_SHAPE","planned run must be a mapping");continue
            for tid in run.get("tasks",[]) or []:
                if tid not in ids:self.add(r.path,"RUN_TASK",f"run {run.get('id')} references unknown task {tid}")
    def validate_review_evidence(self,r:Record):
        plan=r.data.get("review_plan",{}) or {};required=set(plan.get("required_hats",[]) or []);target=str(plan.get("independence_level", ""));completed=plan.get("completed_reviews",[]) or []
        if required and not completed:self.add(r.path,"DONE_REVIEW","DONE work item requires completed review evidence");return
        covered=set();independence_ok=not target.startswith("L2")
        for rid in completed:
            rr=self.by_id.get(rid)
            if not rr or rr.kind!="reviews":self.add(r.path,"DONE_REVIEW",f"review evidence {rid} is missing");continue
            d=rr.data
            if d.get("status") not in {"COMPLETE","CLOSED"}:self.add(r.path,"DONE_REVIEW",f"review {rid} is not complete")
            if d.get("outcome") not in {"APPROVED","APPROVED_WITH_NONBLOCKING_FOLLOWUPS","PASS"}:self.add(r.path,"DONE_REVIEW",f"review {rid} outcome does not approve completion")
            covered.update(d.get("roles",[]) or [])
            level=str((d.get("reviewer") or {}).get("independence_level", ""))
            if level in {"L2","L3"}:independence_ok=True
            for f in d.get("findings",[]) or []:
                if isinstance(f,dict) and f.get("severity") in {"R0_CRITICAL","R1_BLOCKER","R2_MAJOR"} and f.get("disposition") not in {"RESOLVED","ACCEPTED"}:self.add(r.path,"DONE_REVIEW",f"review {rid} retains blocking finding {f.get('id')}")
        if not required.issubset(covered):self.add(r.path,"DONE_REVIEW",f"completed reviews miss required hats {sorted(required-covered)}")
        if not independence_ok:self.add(r.path,"DONE_REVIEW",f"no completed review satisfies independence {target}")
    def validate_done_work(self,r:Record):
        crit=r.data.get("acceptance_criteria",[]) or []
        if not crit:self.add(r.path,"DONE_AC","DONE work item must have acceptance criteria")
        for c in crit:
            if not isinstance(c,dict) or c.get("status")!="DONE":self.add(r.path,"DONE_AC",f"incomplete acceptance criterion {c!r}")
        comp=r.data.get("completion",{}) or {}
        for k in ("definition_of_ready_checked","definition_of_done_checked","traceability_checked","review_complete","docs_updated","registries_updated","project_state_updated"):
            if comp.get(k) is not True:self.add(r.path,"DONE_COMPLETION",f"DONE work item requires completion.{k}=true")
        self.validate_review_evidence(r)
    def validate_work_graph(self):
        works={k:v for k,v in self.by_id.items() if v.kind=="work-items"};edges={}
        for wid,r in works.items():
            deps=r.data.get("depends_on",[]) or [];edges[wid]=[]
            if not isinstance(deps,list):self.add(r.path,"WORK_DEPS","depends_on must be a list");continue
            for dep in deps:
                if dep not in works:self.add(r.path,"WORK_DEP_EXISTS",f"unknown work dependency {dep}")
                else:edges[wid].append(dep)
            self.validate_work_tasks(r)
            if r.data.get("status")=="DONE":self.validate_done_work(r)
        state={}
        def visit(n,stack):
            if state.get(n)==1:self.add(works[n].path,"WORK_CYCLE",f"dependency cycle detected: {' -> '.join(stack+[n])}");return
            if state.get(n)==2:return
            state[n]=1
            for d in edges.get(n,[]):visit(d,stack+[n])
            state[n]=2
        for n in edges:visit(n,[])
    def check_due(self,r:Record,raw:Any,rule:str):
        if raw in (None,""):return
        try:d=date.fromisoformat(str(raw))
        except ValueError:self.add(r.path,rule,f"invalid ISO date {raw!r}");return
        if d<self.today:self.add(r.path,rule,f"review/validation date {d} is overdue")
    def validate_due_dates(self):
        for r in self.records:
            if r.kind=="assumptions" and r.data.get("status")=="OPEN":self.check_due(r,(r.data.get("validation") or {}).get("target_date"),"ASSUMPTION_DUE")
            if r.kind=="risks" and r.data.get("status")=="OPEN":self.check_due(r,r.data.get("review_by"),"RISK_DUE")
    def validate_markdown(self):
        for p in sorted(self.root.rglob("*.md")):
            if ".git" in p.parts:continue
            try:text=p.read_text(encoding="utf-8")
            except OSError as exc:self.add(p,"MARKDOWN_READ",str(exc));continue
            if "Canonical: Yes" in text and "Status: Accepted" in text and PLACEHOLDER.search(text):self.add(p,"CANONICAL_PLACEHOLDER","Accepted canonical document contains TODO/TBD/FIXME")
            for raw in MARKDOWN_LINK.findall(text):
                clean=markdown_destination(raw).split("#",1)[0].strip()
                if not clean or clean.startswith(("http://","https://","mailto:","#")):continue
                if not (p.parent/clean).resolve().exists():self.add(p,"MARKDOWN_LINK",f"broken relative link: {raw}")
    def validate_progress(self):
        p=self.root/"registry/progress/matrix.yaml"
        if not p.exists():self.add(p,"PROGRESS_REQUIRED","progress matrix is missing");return
        data=self.load_yaml(p)
        if not isinstance(data,dict):return
        vocab=set(data.get("status_vocabulary",[]) or [])
        if vocab!=GLOBAL_STATUSES:self.add(p,"STATUS_VOCAB","progress status_vocabulary must equal canonical set")
        found={}
        for phase in (data.get("phases") or {}).values():
            for lot in (phase.get("lots") or {}).values():
                for sub in (lot.get("sublots") or {}).values():
                    for wid,state in (sub.get("work_items") or {}).items():found[wid]=state
        works={r.id:r for r in self.records if r.kind=="work-items"}
        for wid,r in works.items():
            if wid not in found:self.add(p,"PROGRESS_WORK",f"work item {wid} is missing from progress matrix")
        for wid,state in found.items():
            r=works.get(wid)
            if not r:self.add(p,"PROGRESS_WORK",f"progress matrix references unknown work item {wid}");continue
            status=state.get("status") if isinstance(state,dict) else None
            if status!=r.data.get("status"):self.add(p,"PROGRESS_STATUS",f"{wid} matrix status {status!r} != work item status {r.data.get('status')!r}")
            if r.data.get("status")=="DONE" and isinstance(state,dict):
                for key,val in state.items():
                    if key=="status":continue
                    if isinstance(val,str) and val in GLOBAL_STATUSES and val not in DONE_PROGRESS_ALLOWED:self.add(p,"PROGRESS_DONE_DIMENSION",f"{wid}.{key}={val} is incomplete for DONE")
    def validate_project_state(self):
        p=self.root/"PROJECT_STATE.md"
        if not p.exists():self.add(p,"PROJECT_STATE_REQUIRED","PROJECT_STATE.md is missing");return
        try:text=p.read_text(encoding="utf-8")
        except OSError as exc:self.add(p,"PROJECT_STATE_READ",str(exc));return
        section=self.extract_section(text,"Active work");ids=set(re.findall(r"\bWORK-\d+\b",section))
        if not ids:self.add(p,"ACTIVE_WORK","Active work section must reference at least one WORK id")
        for wid in ids:
            r=self.by_id.get(wid)
            if not r:self.add(p,"ACTIVE_WORK",f"unknown active work item {wid}")
            elif r.data.get("status") in {"DONE","DEPRECATED","CANCELLED"}:self.add(p,"ACTIVE_WORK",f"active work item {wid} has terminal status")
    @staticmethod
    def extract_section(text:str,heading:str)->str:
        m=re.search(rf"^##\s+{re.escape(heading)}\s*$",text,re.M|re.I)
        if not m:return ""
        nxt=re.search(r"^##\s+",text[m.end():],re.M);return text[m.end():m.end()+nxt.start()] if nxt else text[m.end():]
    def validate_action_pins(self):
        for p in sorted((self.root/".github/workflows").glob("*.yml")) if (self.root/".github/workflows").exists() else []:
            try:data=yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            except (OSError,yaml.YAMLError):continue
            def walk(v):
                if isinstance(v,dict):
                    for k,x in v.items():
                        if k=="uses" and isinstance(x,str):
                            if x.startswith("./"):pass
                            elif x.startswith("docker://"):
                                if not PINNED_DOCKER.fullmatch(x):self.add(p,"ACTION_PIN",f"docker action must use sha256 digest: {x}")
                            elif not PINNED_ACTION.fullmatch(x):self.add(p,"ACTION_PIN",f"action must use full commit SHA: {x}")
                        walk(x)
                elif isinstance(v,list):
                    for x in v:walk(x)
            walk(data)
    def validate_secrets(self):
        skip={".git"}
        for p in self.root.rglob("*"):
            if not p.is_file() or any(x in p.parts for x in skip) or p.suffix.lower() in {".png",".jpg",".jpeg",".zip",".pdf"}:continue
            try:text=p.read_text(encoding="utf-8")
            except (OSError,UnicodeDecodeError):continue
            for pat in SECRET_PATTERNS:
                if pat.search(text):self.add(p,"SECRET_PATTERN","high-confidence secret/private-key pattern detected");break
    def run(self):
        self.discover_records();self.validate_schemas();self.validate_statuses();self.validate_references();self.validate_paths();self.validate_work_graph();self.validate_due_dates();self.validate_markdown();self.validate_progress();self.validate_project_state();self.validate_action_pins();self.validate_secrets();return self.issues

def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser();p.add_argument("root",nargs="?",default=".");p.add_argument("--today");p.add_argument("--json-out");a=p.parse_args(argv)
    try:today=date.fromisoformat(a.today) if a.today else None
    except ValueError:print("ERROR CLI --today must be ISO YYYY-MM-DD",file=sys.stderr);return 2
    v=Validator(Path(a.root),today);issues=v.run()
    for i in issues:print(i.render(),file=sys.stderr if i.severity=="ERROR" else sys.stdout)
    if a.json_out:Path(a.json_out).write_text(json.dumps([asdict(x) for x in issues],indent=2),encoding="utf-8")
    errors=sum(i.severity=="ERROR" for i in issues);print(f"MONDE governance validation: {errors} error(s), {len(issues)-errors} warning(s), {len(v.records)} record(s)");return 1 if errors else 0
if __name__=="__main__":raise SystemExit(main()) # pragma: no cover
