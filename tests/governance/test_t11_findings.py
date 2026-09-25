from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import tools.governance.t11_closure as t11


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def _init_repo(root: Path) -> str:
    _git(root, "init")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "MONDE Test")
    (root / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "seed")
    return _git(root, "rev-parse", "HEAD")


def test_provenance_bootstrap_exact_and_base_existing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t11.cg, "file_exists_at", lambda *_: True)
    assert t11.validate_provenance_bootstrap(tmp_path, "base", "head") == []

    monkeypatch.setattr(t11.cg, "file_exists_at", lambda *_: False)
    monkeypatch.setattr(t11, "provenance_history_commits", lambda *_: list(t11.EXPECTED_PROVENANCE_BOOTSTRAP_COMMITS))
    assert t11.validate_provenance_bootstrap(tmp_path, "base", "head") == []

    monkeypatch.setattr(t11, "provenance_history_commits", lambda *_: ["unexpected"])
    findings = t11.validate_provenance_bootstrap(tmp_path, "base", "head")
    assert [item.rule for item in findings] == ["PROVENANCE_BOOTSTRAP_HISTORY"]


def test_provenance_history_requires_merge_base(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t11.cg, "git", lambda *_: "")
    with pytest.raises(RuntimeError, match="no merge base"):
        t11.provenance_history_commits(tmp_path, "base", "head")


def test_provenance_history_uses_full_history(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_git(_root: Path, *args: str) -> str:
        calls.append(args)
        if args[0] == "merge-base":
            return "mergebase\n"
        return "a\nb\n"

    monkeypatch.setattr(t11.cg, "git", fake_git)
    monkeypatch.setattr(t11.cg, "commit_parents", lambda *_: [])
    assert t11.provenance_history_commits(tmp_path, "base", "head") == ["a", "b"]
    assert "--full-history" in calls[1]


def test_merge_inherits_provenance_blob_shapes(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t11.cg, "commit_parents", lambda *_: ["p"])
    assert t11.merge_inherits_provenance_blob(tmp_path, "merge") is False

    monkeypatch.setattr(t11.cg, "commit_parents", lambda *_: ["p1", "p2"])
    monkeypatch.setattr(t11.cg, "blob_sha_at", lambda *_: None)
    assert t11.merge_inherits_provenance_blob(tmp_path, "merge") is False

    blobs = {"merge": "m", "p1": "a", "p2": "b"}
    monkeypatch.setattr(t11.cg, "blob_sha_at", lambda _r, sha, _p: blobs[sha])
    assert t11.merge_inherits_provenance_blob(tmp_path, "merge") is False

    blobs["p2"] = "m"
    assert t11.merge_inherits_provenance_blob(tmp_path, "merge") is True


def test_provenance_history_ignores_merge_that_inherits_parent_blob(tmp_path: Path) -> None:
    base = _init_repo(tmp_path)
    main_branch = _git(tmp_path, "branch", "--show-current")
    _git(tmp_path, "checkout", "-b", "source")
    path = tmp_path / t11.INTEGRATION_PROVENANCE_PATH
    path.parent.mkdir(parents=True)
    path.write_text("version: 1\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "source provenance")
    source = _git(tmp_path, "rev-parse", "HEAD")

    _git(tmp_path, "checkout", main_branch)
    _git(tmp_path, "merge", "--no-ff", "source", "-m", "inherit source provenance")
    merge = _git(tmp_path, "rev-parse", "HEAD")

    observed = t11.provenance_history_commits(tmp_path, base, merge)
    assert source in observed
    assert merge not in observed


def test_provenance_history_keeps_merge_with_new_conflict_blob(tmp_path: Path) -> None:
    base = _init_repo(tmp_path)
    main_branch = _git(tmp_path, "branch", "--show-current")
    path = tmp_path / t11.INTEGRATION_PROVENANCE_PATH

    _git(tmp_path, "checkout", "-b", "source")
    path.parent.mkdir(parents=True)
    path.write_text("version: source\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "source provenance")

    _git(tmp_path, "checkout", main_branch)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("version: main\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "main provenance")

    proc = subprocess.run(
        ["git", "merge", "--no-ff", "source", "-m", "conflicting provenance"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode != 0
    path.write_text("version: resolved\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "resolve provenance conflict")
    merge = _git(tmp_path, "rev-parse", "HEAD")

    assert merge in t11.provenance_history_commits(tmp_path, base, merge)


def test_first_status_commit_traverses_hidden_side_branch(tmp_path: Path) -> None:
    base = _init_repo(tmp_path)
    main_branch = _git(tmp_path, "branch", "--show-current")
    _git(tmp_path, "checkout", "-b", "side")
    path = tmp_path / "registry" / "reviews" / "REVIEW-X.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("id: REVIEW-X\nstatus: COMPLETE\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "side materialization")
    first = _git(tmp_path, "rev-parse", "HEAD")

    _git(tmp_path, "checkout", main_branch)
    _git(tmp_path, "merge", "-s", "ours", "side", "-m", "discard side tree")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("id: REVIEW-X\nstatus: COMPLETE\nexternal_import:\n  import_commit: later\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "later materialization")
    head = _git(tmp_path, "rev-parse", "HEAD")

    assert t11.first_status_commit_full_history(tmp_path, "registry/reviews/REVIEW-X.yaml", "COMPLETE", head) == first
    assert base != first


def test_first_status_commit_rejects_nonfirst_same_status(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t11.cg, "git", lambda *_: "a\n")
    monkeypatch.setattr(t11.cg, "show_yaml", lambda _r, sha, _p: {"status": "COMPLETE"} if sha in {"a", "p"} else None)
    monkeypatch.setattr(t11.cg, "commit_parents", lambda *_: ["p"])
    assert t11.first_status_commit_full_history(tmp_path, "x", "COMPLETE", "h") is None


def test_import_materialization_history_detects_mismatch(monkeypatch, tmp_path: Path) -> None:
    records = {
        "registry/reviews/REVIEW-1.yaml": {"status": "COMPLETE", "external_import": {"import_commit": "expected"}},
        "registry/reviews/REVIEW-2.yaml": {"status": "OPEN"},
        "registry/tests/TEST-1.yaml": {"status": "PASS", "external_import": {"import_commit": "same"}},
        "registry/tests/TEST-2.yaml": {"status": "PASS", "external_import": {}},
    }
    monkeypatch.setattr(
        t11,
        "_registry_paths",
        lambda _root, _head, directory: iter([path for path in records if f"registry/{directory}/" in path]),
    )
    monkeypatch.setattr(t11.cg, "show_yaml", lambda _root, _sha, path: records[path])
    monkeypatch.setattr(
        t11,
        "first_status_commit_full_history",
        lambda _root, path, _status, _head: "actual" if "REVIEW-1" in path else "same",
    )
    monkeypatch.setattr(t11, "squash_bridge_allows_first_status", lambda *_: False)
    findings = t11.validate_import_materialization_history(tmp_path, "head")
    assert [item.rule for item in findings] == [
        "IMPORT_FIRST_STATUS_FULL_HISTORY",
        "IMPORT_TERMINAL_UNFINALIZED",
    ]


def test_import_materialization_history_accepts_exact_or_squash(monkeypatch, tmp_path: Path) -> None:
    records = {
        "registry/reviews/A.yaml": {"status": "COMPLETE", "external_import": {"import_commit": "same"}},
        "registry/reviews/B.yaml": {"status": "COMPLETE", "external_import": {"import_commit": "source"}},
    }
    monkeypatch.setattr(t11, "_registry_paths", lambda _r, _h, directory: iter(records) if directory == "reviews" else iter([]))
    monkeypatch.setattr(t11.cg, "show_yaml", lambda _r, _h, path: records[path])
    monkeypatch.setattr(t11, "first_status_commit_full_history", lambda _r, path, _s, _h: "same" if path.endswith("A.yaml") else "integrated")
    monkeypatch.setattr(t11, "squash_bridge_allows_first_status", lambda _r, path, *_: path.endswith("B.yaml"))
    assert t11.validate_import_materialization_history(tmp_path, "head") == []


def test_registry_paths_filters_templates(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        t11.cg,
        "git",
        lambda *_: "registry/reviews/A.yaml\nregistry/reviews/_TEMPLATE.yaml\nregistry/reviews/readme.txt\n",
    )
    assert list(t11._registry_paths(tmp_path, "head", "reviews")) == ["registry/reviews/A.yaml"]


def test_tree_sha(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t11.cg, "commit_exists", lambda *_: False)
    assert t11._tree_sha(tmp_path, "x") is None
    monkeypatch.setattr(t11.cg, "commit_exists", lambda *_: True)
    monkeypatch.setattr(t11.cg, "git", lambda *_: "a" * 40 + "\n")
    assert t11._tree_sha(tmp_path, "x") == "a" * 40
    monkeypatch.setattr(t11.cg, "git", lambda *_: "bad\n")
    assert t11._tree_sha(tmp_path, "x") is None


def test_squash_bridge_proves_history_without_granting_evidence_eligibility(monkeypatch, tmp_path: Path) -> None:
    imp = "1" * 40
    source = "2" * 40
    integrated = "3" * 40
    tree = "4" * 40
    entry = {
        "eligible_review_ids": ["REVIEW-X"],
        "source_head_sha": source,
        "integrated_commit_sha": integrated,
        "expected_tree_sha": tree,
        "historical_only": True,
        "future_reuse_forbidden": True,
    }
    record = {"id": "REVIEW-X", "status": "COMPLETE"}
    monkeypatch.setattr(t11.cg, "show_yaml", lambda *_: {"squash_integrations": [entry]})
    monkeypatch.setattr(t11.cg, "is_ancestor", lambda *_: True)
    monkeypatch.setattr(t11, "first_status_commit_full_history", lambda *_: imp)
    monkeypatch.setattr(t11, "_tree_sha", lambda _r, sha: tree if sha in {source, integrated} else None)
    assert t11.squash_bridge_allows_first_status(tmp_path, "p", record, imp, integrated, "head", "reviews") is True

    # T11 only proves where the status was first materialized. Evidence qualification
    # remains a separate T7/T9 concern, so absence from eligible_review_ids must not
    # make the exact source-history bridge disappear here.
    assert t11.squash_bridge_allows_first_status(tmp_path, "p", {"id": "OTHER", "status": "COMPLETE"}, imp, integrated, "head", "reviews") is True
    bad = dict(entry, historical_only=False)
    monkeypatch.setattr(t11.cg, "show_yaml", lambda *_: {"squash_integrations": [bad]})
    assert t11.squash_bridge_allows_first_status(tmp_path, "p", record, imp, integrated, "head", "reviews") is False


def test_changed_blob_paths_and_blob_size(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t11.cg, "git", lambda *_: "a\n\nb\n")
    assert t11.changed_blob_paths(tmp_path, "a", "b") == ["a", "b"]
    monkeypatch.setattr(t11.cg, "git", lambda *_: "42\n")
    assert t11.blob_size(tmp_path, "sha", "p") == 42
    monkeypatch.setattr(t11.cg, "git", lambda *_: "not-a-size\n")
    with pytest.raises(RuntimeError, match="invalid blob size"):
        t11.blob_size(tmp_path, "sha", "p")


def test_blob_bytes_success_and_failure(monkeypatch, tmp_path: Path) -> None:
    class Proc:
        returncode = 0
        stdout = b"abc"
        stderr = b""

    monkeypatch.setattr(t11.subprocess, "run", lambda *a, **k: Proc())
    assert t11.blob_bytes(tmp_path, "sha", "p") == b"abc"

    class BadProc:
        returncode = 1
        stdout = b""
        stderr = b"bad blob"

    monkeypatch.setattr(t11.subprocess, "run", lambda *a, **k: BadProc())
    with pytest.raises(RuntimeError, match="bad blob"):
        t11.blob_bytes(tmp_path, "sha", "p")


def test_binary_classified_secret_blob_is_detected_even_after_deletion(tmp_path: Path) -> None:
    base = _init_repo(tmp_path)
    (tmp_path / ".gitattributes").write_text("*.dat binary\n", encoding="utf-8")
    token = ("ghp_" + "A" * 32).encode()
    (tmp_path / "leak.dat").write_bytes(b"\x00prefix\x00" + token + b"\x00suffix")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "binary leak")
    _git(tmp_path, "rm", "leak.dat")
    _git(tmp_path, "commit", "-m", "remove leak")
    head = _git(tmp_path, "rev-parse", "HEAD")

    findings = t11.validate_secret_history_blobs(tmp_path, base, head)
    assert any(item.rule == "SECRET_HISTORY_BLOB" and item.path == "leak.dat" for item in findings)


def test_secret_history_fails_closed_on_large_blob(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t11.cg, "pr_commit_edges", lambda *a, **k: ([], [("before", "after")]))
    monkeypatch.setattr(t11, "changed_blob_paths", lambda *_: ["huge.bin", "clean.txt"])
    monkeypatch.setattr(t11, "blob_size", lambda _r, _s, path: t11.MAX_SECRET_BLOB_BYTES + 1 if path == "huge.bin" else 4)
    monkeypatch.setattr(t11, "blob_bytes", lambda *_: b"safe")
    findings = t11.validate_secret_history_blobs(tmp_path, "base", "head")
    assert [item.rule for item in findings] == ["SECRET_HISTORY_UNSCANNED_BLOB"]


def _write_valid_workflows(root: Path) -> None:
    workflow = root / t11.WORKFLOW_PATH
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(
        """name: test
on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]
  pull_request_review:
    types: [submitted, edited, dismissed]
  pull_request_review_comment:
    types: [created, edited, deleted]
  schedule:
    - cron: '*/5 * * * *'
jobs:
  governance-core: {}
  review-thread-state-poll:
    if: github.event_name == 'schedule'
    permissions:
      actions: write
      pull-requests: read
      contents: read
    steps:
      - run: python -m tools.governance.thread_state_poll
  dependency-review:
    if: startsWith(github.event_name, 'pull_request')
    steps:
      - id: depgraph
        run: echo probe
      - if: steps.depgraph.outputs.supported == 'true'
        uses: actions/dependency-review-action@a1d282b36b6f3519aa1f3fc636f609c47dddb294
        with:
          fail-on-severity: moderate
  codeql:
    if: github.event_name != 'schedule'
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          ref: ${{ github.event.pull_request.head.sha || github.sha }}
          persist-credentials: false
      - uses: github/codeql-action/init@b96794f015dfd88f77b49b1c93e0fa7110f94c63
        with:
          languages: python
      - uses: github/codeql-action/analyze@b96794f015dfd88f77b49b1c93e0fa7110f94c63
  final-gate:
    if: always() && github.event_name != 'schedule'
    needs: [governance-core, dependency-review, codeql]
    steps:
      - run: test '${{ needs.governance-core.result }}' = 'success'
      - run: test '${{ needs.codeql.result }}' = 'success'
      - if: startsWith(github.event_name, 'pull_request')
        run: test '${{ needs.dependency-review.result }}' = 'success'
      - if: startsWith(github.event_name, 'pull_request')
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          ref: ${{ github.event.pull_request.head.sha }}
          persist-credentials: false
      - if: startsWith(github.event_name, 'pull_request')
        run: python -m tools.governance.github_live_gate --repo x --pr 1 --head h --root .
""",
        encoding="utf-8",
    )
    core = root / t11.CORE_WORKFLOW_PATH
    core.write_text(
        """on:
  workflow_call:
jobs:
  validate:
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          ref: ${{ inputs.head_sha }}
          persist-credentials: false
      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97
        with:
          python-version: '3.13.15'
          cache: pip
          cache-dependency-path: requirements/governance-ci.txt
      - run: python -m pip install --require-hashes -r requirements/governance-ci.txt
      - run: python -m pytest --cov --cov-branch
      - run: |
          python scripts/governance_mutation_smoke.py
          python .github/scripts/governance_l2_mutation_smoke.py
          python .github/scripts/governance_t10_mutation_smoke.py
          python .github/scripts/governance_t11_mutation_smoke.py
          python .github/scripts/governance_t13_mutation_smoke.py
      - run: |
          python -m tools.governance.validate_repo . --json-out a.json
          python -m tools.governance.strict_contracts . --json-out b.json
          python -m tools.governance.path_safety . --json-out c.json
      - if: startsWith(inputs.event_name, 'pull_request')
        run: python -m tools.governance.change_guard . --base x --head y
      - if: startsWith(inputs.event_name, 'pull_request')
        run: PYTHONPATH="$PWD:$PWD/.github/scripts" python .github/scripts/governance_l2_gate.py . --base x --head y
      - if: startsWith(inputs.event_name, 'pull_request')
        run: python -m tools.governance.review_closure_gate . --base x --head y
      - if: startsWith(inputs.event_name, 'pull_request')
        run: python -m tools.governance.t7_closure . --base x --head y
      - if: startsWith(inputs.event_name, 'pull_request')
        run: python -m tools.governance.t8_closure . --base x --head y
      - if: startsWith(inputs.event_name, 'pull_request')
        run: python -m tools.governance.t9_closure . --base x --head y
      - if: startsWith(inputs.event_name, 'pull_request')
        run: python -m tools.governance.t10_closure . --base x --head y
      - if: startsWith(inputs.event_name, 'pull_request')
        run: python -m tools.governance.t11_closure . --base x --head y
      - if: startsWith(inputs.event_name, 'pull_request')
        run: python -m tools.governance.context_manifest . --base x --head y
""",
        encoding="utf-8",
    )
def test_workflow_structure_parses_effective_yaml_not_comments(tmp_path: Path) -> None:
    _write_valid_workflows(tmp_path)
    assert t11.validate_workflow_structure(tmp_path) == []

    workflow = tmp_path / t11.WORKFLOW_PATH
    workflow.write_text(
        """# pull_request_review:
#   types: [submitted, edited, dismissed]
on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]
jobs: {}
""",
        encoding="utf-8",
    )
    findings = t11.validate_workflow_structure(tmp_path)
    rules = {item.rule for item in findings}
    assert "WORKFLOW_TRIGGER_STRUCTURE" in rules
    assert "REVIEW_THREAD_POLL_SCHEDULE" in rules
    assert "REVIEW_THREAD_POLL_JOB" in rules
    assert "T11_GATE_WIRING" not in rules


def test_workflow_structure_rejects_failure_masking_shell_suffixes(tmp_path: Path) -> None:
    _write_valid_workflows(tmp_path)

    workflow = tmp_path / t11.WORKFLOW_PATH
    text = workflow.read_text(encoding="utf-8")
    text = text.replace(
        "python -m tools.governance.thread_state_poll",
        "python -m tools.governance.thread_state_poll || true",
    )
    workflow.write_text(text, encoding="utf-8")
    rules = {item.rule for item in t11.validate_workflow_structure(tmp_path)}
    assert "REVIEW_THREAD_POLL_WIRING" in rules

    _write_valid_workflows(tmp_path)
    core = tmp_path / t11.CORE_WORKFLOW_PATH
    text = core.read_text(encoding="utf-8")
    text = text.replace(
        "python -m tools.governance.t11_closure . --base x --head y",
        "python -m tools.governance.t11_closure . --base x --head y ; exit 0",
    )
    core.write_text(text, encoding="utf-8")
    rules = {item.rule for item in t11.validate_workflow_structure(tmp_path)}
    assert "T11_GATE_WIRING" in rules

    _write_valid_workflows(tmp_path)
    core = tmp_path / t11.CORE_WORKFLOW_PATH
    text = core.read_text(encoding="utf-8")
    text = text.replace(
        "python .github/scripts/governance_t11_mutation_smoke.py",
        "python .github/scripts/governance_t11_mutation_smoke.py && true",
    )
    core.write_text(text, encoding="utf-8")
    rules = {item.rule for item in t11.validate_workflow_structure(tmp_path)}
    assert "T11_MUTATION_WIRING" in rules


def test_step_prefix_allows_safe_flags_and_rejects_failure_masking_shell() -> None:
    expected = ("python", "-m", "tools.governance.t11_closure", ".")
    safe = {
        "steps": [
            {
                "run": "python -m tools.governance.t11_closure . "
                "--base base --head head --json-out out.json"
            }
        ]
    }
    assert t11._steps_execute_prefix(safe, expected) is True
    assert t11._steps_execute_prefix({}, expected) is False
    assert t11._steps_execute_prefix({"steps": ["bad"]}, expected) is False

    for run in (
        "python -m tools.governance.t11_closure . || true",
        "python -m tools.governance.t11_closure . && true",
        "python -m tools.governance.t11_closure . ; exit 0",
        "python -m tools.governance.t11_closure . | cat",
        "python -m tools.governance.t11_closure . > /dev/null",
        "python -m tools.governance.t11_closure . < input",
        "python -m tools.governance.t11_closure . `echo x`",
        "python -m tools.governance.t11_closure . $(echo x)",
        "set +e\npython -m tools.governance.t11_closure .",
        "set +o errexit\npython -m tools.governance.t11_closure .",
    ):
        assert t11._steps_execute_prefix({"steps": [{"run": run}]}, expected) is False


def test_execution_container_defaults_cover_safe_and_malformed_shapes() -> None:
    assert t11._container_execution_defaults_safe({}) is True
    assert t11._container_execution_defaults_safe({"defaults": {}}) is True
    assert t11._container_execution_defaults_safe({"defaults": {"run": {}}}) is True
    assert t11._container_execution_defaults_safe({"env": "bad"}) is False
    assert t11._container_execution_defaults_safe({"defaults": "bad"}) is False
    assert t11._container_execution_defaults_safe({"defaults": {"run": "bad"}}) is False
    assert t11._container_execution_defaults_safe(
        {"defaults": {"run": {"shell": "bash"}}}
    ) is False
    assert t11._container_execution_defaults_safe(
        {"defaults": {"run": {"working-directory": "subdir"}}}
    ) is False


def test_workflow_structure_rejects_dependency_review_bypasses(tmp_path: Path) -> None:
    _write_valid_workflows(tmp_path)
    workflow = tmp_path / t11.WORKFLOW_PATH

    text = workflow.read_text(encoding="utf-8")
    workflow.write_text(
        text.replace(
            "  dependency-review:\n    if: startsWith(github.event_name, 'pull_request')\n",
            "  dependency-review:\n    if: false\n",
            1,
        ),
        encoding="utf-8",
    )
    assert "DEPENDENCY_REVIEW_SCOPE" in {
        item.rule for item in t11.validate_workflow_structure(tmp_path)
    }

    _write_valid_workflows(tmp_path)
    text = workflow.read_text(encoding="utf-8")
    workflow.write_text(
        text.replace(
            "    needs: [governance-core, dependency-review, codeql]\n",
            "    needs: [governance-core, codeql]\n",
            1,
        ),
        encoding="utf-8",
    )
    assert "FINAL_GATE_NEEDS" in {
        item.rule for item in t11.validate_workflow_structure(tmp_path)
    }

    _write_valid_workflows(tmp_path)
    text = workflow.read_text(encoding="utf-8")
    workflow.write_text(
        text.replace(
            "        run: test '${{ needs.dependency-review.result }}' = 'success'\n",
            "        run: true\n",
            1,
        ),
        encoding="utf-8",
    )
    assert "DEPENDENCY_REVIEW_REQUIRED" in {
        item.rule for item in t11.validate_workflow_structure(tmp_path)
    }

    _write_valid_workflows(tmp_path)
    text = workflow.read_text(encoding="utf-8")
    start = text.index("  dependency-review:\n")
    end = text.index("  codeql:\n", start)
    workflow.write_text(text[:start] + text[end:], encoding="utf-8")
    assert "DEPENDENCY_REVIEW_JOB" in {
        item.rule for item in t11.validate_workflow_structure(tmp_path)
    }


def test_review0084_structural_p1_regressions(tmp_path: Path) -> None:
    cases = [
        (
            t11.WORKFLOW_PATH,
            "      - run: python -m tools.governance.thread_state_poll\n",
            "      - run: |\n          python() {\n            true\n          }\n          python -m tools.governance.thread_state_poll\n",
            "REVIEW_THREAD_POLL_WIRING",
        ),
        (
            t11.WORKFLOW_PATH,
            "        uses: actions/dependency-review-action@a1d282b36b6f3519aa1f3fc636f609c47dddb294\n",
            "        run: true\n",
            "DEPENDENCY_REVIEW_ACTION",
        ),
        (
            t11.WORKFLOW_PATH,
            "        run: python -m tools.governance.github_live_gate --repo x --pr 1 --head h --root .\n",
            "        run: true\n",
            "FINAL_GATE_LIVE_WIRING",
        ),
        (
            t11.CORE_WORKFLOW_PATH,
            "        run: python -m tools.governance.context_manifest . --base x --head y\n",
            "        run: true\n",
            "CORE_CONTEXT_MANIFEST_WIRING",
        ),
        (
            t11.WORKFLOW_PATH,
            "      - uses: github/codeql-action/init@b96794f015dfd88f77b49b1c93e0fa7110f94c63\n",
            "      - run: true\n",
            "CODEQL_INIT_ACTION",
        ),
    ]
    for path, old, new, rule in cases:
        _write_valid_workflows(tmp_path)
        target = tmp_path / path
        text = target.read_text(encoding="utf-8")
        assert old in text
        target.write_text(text.replace(old, new, 1), encoding="utf-8")
        assert rule in {item.rule for item in t11.validate_workflow_structure(tmp_path)}


def test_action_and_shadow_helpers_fail_closed() -> None:
    expected = ("python", "-m", "tools.governance.thread_state_poll")
    for run in (
        "python() {\n  true\n}\npython -m tools.governance.thread_state_poll",
        "function python {\n  true\n}\npython -m tools.governance.thread_state_poll",
        "alias python=true\npython -m tools.governance.thread_state_poll",
        "source ./helpers.sh\npython -m tools.governance.thread_state_poll",
        ". ./helpers.sh\npython -m tools.governance.thread_state_poll",
        "eval setup_python\npython -m tools.governance.thread_state_poll",
        "hash -p /tmp/fake python\npython -m tools.governance.thread_state_poll",
    ):
        assert not t11._steps_execute_prefix({"steps": [{"run": run}]}, expected)

    safe_job = {
        "steps": [
            {
                "uses": t11.DEPENDENCY_REVIEW_ACTION,
                "if": "steps.depgraph.outputs.supported == 'true'",
                "with": {"fail-on-severity": "moderate"},
            }
        ]
    }
    assert t11._steps_use_action(
        safe_job,
        t11.DEPENDENCY_REVIEW_ACTION,
        allowed_step_ifs=frozenset({"steps.depgraph.outputs.supported == 'true'"}),
        required_with={"fail-on-severity": "moderate"},
    )
    assert not t11._steps_use_action({}, t11.DEPENDENCY_REVIEW_ACTION)
    assert not t11._steps_use_action(
        {"env": {"PATH": "/tmp"}, **safe_job},
        t11.DEPENDENCY_REVIEW_ACTION,
        allowed_step_ifs=frozenset({"steps.depgraph.outputs.supported == 'true'"}),
    )
    assert not t11._steps_use_action(
        {"steps": ["bad", {"uses": "wrong/action@" + "0" * 40}]},
        t11.DEPENDENCY_REVIEW_ACTION,
    )
    assert not t11._steps_use_action(
        {"steps": [{"uses": t11.DEPENDENCY_REVIEW_ACTION, "with": "bad"}]},
        t11.DEPENDENCY_REVIEW_ACTION,
        required_with={"fail-on-severity": "moderate"},
    )
    assert not t11._steps_use_action(
        {"steps": [{"uses": t11.DEPENDENCY_REVIEW_ACTION, "with": {"fail-on-severity": "low"}}]},
        t11.DEPENDENCY_REVIEW_ACTION,
        required_with={"fail-on-severity": "moderate"},
    )


def test_workflow_structure_rejects_bad_poll_and_core_wiring(tmp_path: Path) -> None:
    _write_valid_workflows(tmp_path)
    workflow = tmp_path / t11.WORKFLOW_PATH
    text = workflow.read_text(encoding="utf-8")
    text = text.replace("actions: write", "actions: read")
    text = text.replace("github.event_name == 'schedule'", "always()")
    text = text.replace("python -m tools.governance.thread_state_poll", "echo nope")
    text = text.replace("    - cron: '*/5 * * * *'\n", "")
    workflow.write_text(text, encoding="utf-8")
    core = tmp_path / t11.CORE_WORKFLOW_PATH
    core.write_text("on: {workflow_call: {}}\njobs: {validate: {steps: []}}\n", encoding="utf-8")
    rules = {item.rule for item in t11.validate_workflow_structure(tmp_path)}
    assert {
        "REVIEW_THREAD_POLL_SCHEDULE",
        "REVIEW_THREAD_POLL_PERMISSIONS",
        "REVIEW_THREAD_POLL_SCOPE",
        "REVIEW_THREAD_POLL_WIRING",
        "CORE_CHECKOUT_ACTION",
        "CORE_SETUP_PYTHON_ACTION",
        "CORE_PYTEST_WIRING",
        "T11_GATE_WIRING",
        "T11_MUTATION_WIRING",
    }.issubset(rules)


def test_workflow_structure_rejects_missing_on_and_parse_errors(tmp_path: Path) -> None:
    _write_valid_workflows(tmp_path)
    workflow = tmp_path / t11.WORKFLOW_PATH
    workflow.write_text("name: x\njobs: {}\n", encoding="utf-8")
    assert [item.rule for item in t11.validate_workflow_structure(tmp_path)] == ["WORKFLOW_TRIGGER_STRUCTURE"]

    workflow.write_text("- not\n- a mapping\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="must contain a YAML mapping"):
        t11.validate_workflow_structure(tmp_path)
    workflow.write_text("[broken", encoding="utf-8")
    with pytest.raises(RuntimeError, match="cannot parse"):
        t11.validate_workflow_structure(tmp_path)
    workflow.unlink()
    with pytest.raises(RuntimeError, match="cannot parse"):
        t11.validate_workflow_structure(tmp_path)


def test_event_and_step_helpers() -> None:
    assert t11._event_types({}, "x") == set()
    assert t11._event_types({"x": {"types": "bad"}}, "x") == set()
    assert t11._event_types({"x": {"types": ["a", "b"]}}, "x") == {"a", "b"}
    assert t11._steps_contain_run({}, "needle") is False
    assert t11._steps_contain_run({"steps": ["bad", {"run": "echo needle"}]}, "needle") is True


def test_run_and_main(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(t11, "validate_provenance_bootstrap", lambda *_: [t11.Finding("p", "A", "bad")])
    monkeypatch.setattr(t11, "validate_import_materialization_history", lambda *_: [])
    monkeypatch.setattr(t11, "validate_secret_history_blobs", lambda *_: [])
    monkeypatch.setattr(t11, "validate_workflow_structure", lambda *_: [])
    assert [item.rule for item in t11.run(tmp_path, "b", "h")] == ["A"]

    output = tmp_path / "out.json"
    assert t11.main([str(tmp_path), "--base", "b", "--head", "h", "--json-out", str(output)]) == 1
    assert output.exists()
    assert "ERROR A" in capsys.readouterr().err

    monkeypatch.setattr(t11, "validate_provenance_bootstrap", lambda *_: [])
    assert t11.main([str(tmp_path), "--base", "b", "--head", "h"]) == 0

    monkeypatch.setattr(t11, "run", lambda *_: (_ for _ in ()).throw(RuntimeError("boom")))
    assert t11.main([str(tmp_path), "--base", "b", "--head", "h"]) == 2
    assert "ERROR T11_CLOSURE boom" in capsys.readouterr().err
