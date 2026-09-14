from pathlib import Path

p = Path("scripts/governance_mutation_smoke.py")
s = p.read_text(encoding="utf-8")

replacements = [
    (
        '''    "required-test-pass": (\n        "tools/governance/strict_contracts.py",\n        'if test is None or test.get("status") != "PASS":',\n        'if False:',\n    ),\n''',
        '''    "required-test-pass": (\n        "tools/governance/strict_contracts.py",\n        'if test is None or not pass_test_has_execution(test):',\n        'if False:',\n    ),\n''',
        "required-test-pass mutation target",
    ),
    (
        '''    "canonical-review-severity": (\n        "tools/governance/strict_contracts.py",\n        'if rank <= BLOCKING_REVIEW_RANK and finding.get("disposition") not in {"RESOLVED", "ACCEPTED"}:',\n        'if False:',\n    ),\n''',
        '''    "canonical-review-severity": (\n        "tools/governance/strict_contracts.py",\n        'if rank <= BLOCKING_REVIEW_RANK:',\n        'if False:',\n    ),\n''',
        "canonical-review-severity mutation target",
    ),
    (
        '''    "review-complete-sha": (\n        "tools/governance/strict_contracts.py",\n        'if review.get("status") == "COMPLETE" and not reviewed_sha:',\n        'if False:',\n    ),\n''',
        '''    "review-complete-sha": (\n        "tools/governance/strict_contracts.py",\n        'if review.get("status") == "COMPLETE" and not FULL_COMMIT_SHA.fullmatch(reviewed_sha):',\n        'if False:',\n    ),\n''',
        "review-complete-sha mutation target",
    ),
    (
        '''    "test-pass-protected-contract-schema": (\n        "schemas/registry/tests.schema.json",\n        '\"contracts\": {\"type\": \"array\", \"minItems\": 1, \"items\": {\"type\": \"string\", \"minLength\": 1}}',\n        '\"contracts\": {\"type\": \"array\", \"items\": {\"type\": \"string\", \"minLength\": 1}}',\n    ),\n''',
        '''    "test-pass-execution-sha-schema": (\n        "schemas/registry/tests.schema.json",\n        '\"pattern\": \"^[0-9a-f]{40}$\"',\n        '\"type\": \"string\"',\n    ),\n''',
        "test-pass execution SHA schema mutation target",
    ),
]

for old, new, label in replacements:
    count = s.count(old)
    assert count == 1, f"{label}: expected 1 occurrence, got {count}"
    s = s.replace(old, new, 1)

p.write_text(s, encoding="utf-8")
