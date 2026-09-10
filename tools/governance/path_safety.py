from __future__ import annotations
import argparse, json, re, shlex, sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable
import yaml

PATH_KEYS=("read_before","affected_docs","affected_schemas","affected_paths")
MARKDOWN_LINK=re.compile(r"\[[^\]]+\]\(([^)]+)\)")
EXTERNAL_PREFIXES=("http://","https://","mailto:","#")
@dataclass(frozen=True)
class PathFinding:
    path:str; rule:str; message:str
    def render(self)->str:return f"ERROR {self.rule} {self.path}: {self.message}"

def relative_display(root:Path,path:Path)->str:
    try:return str(path.resolve().relative_to(root.resolve()))
    except ValueError:return str(path)
def contained(root:Path,candidate:Path)->bool:
    try:candidate.resolve().relative_to(root.resolve());return True
    except ValueError:return False
def iter_strings_for_key(value:Any,key:str)->Iterable[str]:
    if isinstance(value,dict):
        for k,v in value.items():
            if k==key and isinstance(v,list):
                yield from (x for x in v if isinstance(x,str))
            yield from iter_strings_for_key(v,key)
    elif isinstance(value,list):
        for item in value:yield from iter_strings_for_key(item,key)
def markdown_destination(raw:str)->str:
    raw=raw.strip()
    if raw.startswith("<"):
        end=raw.find(">")
        return raw[1:end] if end>0 else raw
    try:parts=shlex.split(raw,posix=True)
    except ValueError:return raw
    return parts[0] if parts else ""
def validate_yaml_paths(root:Path)->list[PathFinding]:
    out=[]; registry=root/"registry"
    if not registry.exists():return out
    for path in sorted(registry.rglob("*.yaml")):
        if path.name.startswith("_"):continue
        try:data=yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError,yaml.YAMLError):continue
        for key in PATH_KEYS:
            for raw in iter_strings_for_key(data,key):
                declared=Path(raw); candidate=declared if declared.is_absolute() else root/declared
                if not contained(root,candidate):out.append(PathFinding(relative_display(root,path),"PATH_SCOPE",f"{key} path escapes repository root: {raw}"))
    return out
def validate_markdown_paths(root:Path)->list[PathFinding]:
    out=[]
    for path in sorted(root.rglob("*.md")):
        if ".git" in path.parts:continue
        try:text=path.read_text(encoding="utf-8")
        except OSError:continue
        for target in MARKDOWN_LINK.findall(text):
            clean=markdown_destination(target).split("#",1)[0].strip()
            if not clean or clean.startswith(EXTERNAL_PREFIXES):continue
            declared=Path(clean); candidate=declared if declared.is_absolute() else path.parent/declared
            if not contained(root,candidate):out.append(PathFinding(relative_display(root,path),"MARKDOWN_SCOPE",f"relative link escapes repository root: {target}"))
    return out
def validate(root:Path)->list[PathFinding]:return validate_yaml_paths(root.resolve())+validate_markdown_paths(root.resolve())
def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser();p.add_argument("root",nargs="?",default=".");p.add_argument("--json-out");a=p.parse_args(argv)
    findings=validate(Path(a.root))
    for f in findings:print(f.render(),file=sys.stderr)
    if a.json_out:Path(a.json_out).write_text(json.dumps([asdict(x) for x in findings],indent=2),encoding="utf-8")
    print(f"MONDE path-safety validation: {len(findings)} error(s)")
    return 1 if findings else 0
if __name__=="__main__":raise SystemExit(main()) # pragma: no cover
