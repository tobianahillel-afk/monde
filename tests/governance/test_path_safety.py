from pathlib import Path
import yaml
from tools.governance import path_safety as p

def test_helpers_and_markdown(tmp_path):
    root=tmp_path; (root/'registry/x').mkdir(parents=True); (root/'docs').mkdir(); (root/'inside').write_text('x')
    assert p.contained(root,root/'inside'); assert not p.contained(root,root.parent/'outside')
    assert p.relative_display(root,root/'inside')=='inside'; assert str(root.parent/'outside')==p.relative_display(root,root.parent/'outside')
    assert p.markdown_destination('guide.md "Guide"')=='guide.md'; assert p.markdown_destination('<a b.md>')=='a b.md'; assert p.markdown_destination('"unterminated')=='"unterminated'
    data={'x':{'read_before':['inside',3]},'list':[{'affected_docs':['inside']}]}; assert list(p.iter_strings_for_key(data,'read_before'))==['inside']
    (root/'registry/x/a.yaml').write_text(yaml.safe_dump({'id':'X','read_before':['../escape']})); (root/'registry/x/_TEMPLATE.yaml').write_text('x: [')
    (root/'docs/a.md').write_text('[ok](../inside "title")\n[out](../../escape)\n[web](https://x)')
    ys=p.validate_yaml_paths(root); ms=p.validate_markdown_paths(root)
    assert ys and ys[0].rule=='PATH_SCOPE'; assert ms and ms[0].rule=='MARKDOWN_SCOPE'
def test_validate_missing_and_main(tmp_path,capsys):
    assert p.validate(tmp_path)==[]
    out=tmp_path/'out.json'; assert p.main([str(tmp_path),'--json-out',str(out)])==0; assert out.exists(); assert '0 error' in capsys.readouterr().out
def test_path_error_branches(tmp_path,monkeypatch):
    assert p.PathFinding('p','r','m').render().startswith('ERROR r')
    (tmp_path/'registry/x').mkdir(parents=True);bad=tmp_path/'registry/x/bad.yaml';bad.write_text('x: [');assert p.validate_yaml_paths(tmp_path)==[]
    docs=tmp_path/'docs';docs.mkdir();md=docs/'x.md';md.write_text('x')
    orig=Path.read_text
    def boom(self,*a,**k):
        if self==md:raise OSError('x')
        return orig(self,*a,**k)
    monkeypatch.setattr(Path,'read_text',boom);assert p.validate_markdown_paths(tmp_path)==[]
    assert p.main([str(tmp_path)])==0
def test_git_markdown_is_skipped(tmp_path):
    d=tmp_path/'.git';d.mkdir();(d/'x.md').write_text('[x](../../outside)');assert p.validate_markdown_paths(tmp_path)==[]
