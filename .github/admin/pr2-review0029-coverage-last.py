from pathlib import Path

p = Path('tests/governance/test_review0029_branches.py')
s = p.read_text(encoding='utf-8')
s += r'''


def test_valid_initial_record_edge_when_guard_already_exists(tmp_path: Path) -> None:
    init_repo(tmp_path)
    guard = tmp_path / cg.GUARD_PATH
    guard.parent.mkdir(parents=True, exist_ok=True)
    guard.write_text('# guard already adopted\n', encoding='utf-8')
    base = commit(tmp_path, 'adopt guard')
    dump(tmp_path / 'registry/reviews/REVIEW-INITIAL.yaml', {'id': 'REVIEW-INITIAL', 'status': 'OPEN'})
    head = commit(tmp_path, 'introduce review in canonical initial state')
    findings = cg.validate(tmp_path, base, head)
    assert 'STATE_INITIAL' not in {f.rule for f in findings}
'''
p.write_text(s, encoding='utf-8')
