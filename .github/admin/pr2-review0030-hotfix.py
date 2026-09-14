from pathlib import Path

p = Path('/tmp/pr2-review0030-fixes.py')
text = p.read_text(encoding='utf-8')
old = '''replace_once(
    "tests/governance/test_review0029_branches.py",
    \'\'\'    records = {\\n\'\'\',
    \'\'\'    monkeypatch.setattr(cg, "requirement_digest_matches", lambda *args: True)\\n    records = {\\n\'\'\',
)
'''
new = '''replace_once(
    "tests/governance/test_review0029_branches.py",
    \'\'\'    req = {"id": "REQ-1", "content_identity": {"scheme": "REQUIREMENT_NORMATIVE_V1", "digest": digest}, "verification": {"acceptance_evidence": ["junk", "REVIEW-1"], "acceptance_cold_read_test_ids": ["junk", "TEST-1"]}}\\n    records = {\\n\'\'\',
    \'\'\'    req = {"id": "REQ-1", "content_identity": {"scheme": "REQUIREMENT_NORMATIVE_V1", "digest": digest}, "verification": {"acceptance_evidence": ["junk", "REVIEW-1"], "acceptance_cold_read_test_ids": ["junk", "TEST-1"]}}\\n    monkeypatch.setattr(cg, "requirement_digest_matches", lambda *args: True)\\n    records = {\\n\'\'\',
)
'''
count = text.count(old)
assert count == 1, count
p.write_text(text.replace(old, new, 1), encoding='utf-8')
print('hotfixed REVIEW-0030 patch targeting')
