from pathlib import Path

p = Path("scripts/governance_mutation_smoke.py")
s = p.read_text(encoding="utf-8")
old = '''    "required-test-pass": (\n        "tools/governance/strict_contracts.py",\n        'if test is None or test.get("status") != "PASS":',\n        'if False:',\n    ),\n'''
new = '''    "required-test-pass": (\n        "tools/governance/strict_contracts.py",\n        'if test is None or not pass_test_has_execution(test):',\n        'if False:',\n    ),\n'''
count = s.count(old)
assert count == 1, f"required-test-pass mutation target: expected 1 occurrence, got {count}"
p.write_text(s.replace(old, new, 1), encoding="utf-8")
