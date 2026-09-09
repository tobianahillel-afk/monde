from __future__ import annotations

from pathlib import Path

import pytest

from tools.governance.path_safety import (
    PathFinding,
    contained,
    iter_strings_for_key,
    main,
    relative_display,
    validate,
    validate_markdown_paths,
    validate_yaml_paths,
)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_path_finding_and_containment_helpers(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    inside = root / "a.txt"
    inside.write_text("x")
    outside = tmp_path / "outside.txt"
    outside.write_text("x")

    finding = PathFinding("x", "PATH_SCOPE", "bad")
    assert finding.render() == "ERROR PATH_SCOPE x: bad"
    assert contained(root, inside)
    assert not contained(root, outside)
    assert relative_display(root, inside) == "a.txt"
    assert relative_display(root, outside) == str(outside)


def test_iter_strings_for_key_handles_nested_shapes() -> None:
    data = {
        "read_before": ["a.md", 42],
        "nested": [{"read_before": ["b.md"]}, {"read_before": "not-a-list"}],
        "scalar": 1,
    }
    assert list(iter_strings_for_key(data, "read_before")) == ["a.md", "b.md"]
    assert list(iter_strings_for_key(7, "read_before")) == []


def test_yaml_paths_accept_inside_and_reject_escape_absolute_and_symlink(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    write(root / "README.md", "ok")
    outside = tmp_path / "outside.md"
    outside.write_text("secret")
    (root / "escape").symlink_to(tmp_path, target_is_directory=True)

    write(root / "registry/work-items/WORK-0001.yaml", """
id: WORK-0001
status: IN_PROGRESS
read_before:
  - README.md
  - ../outside.md
  - /etc/hosts
  - escape/outside.md
""")
    write(root / "registry/work-items/_TEMPLATE.yaml", "read_before: [/etc/passwd]\n")

    findings = validate_yaml_paths(root)
    messages = [f.message for f in findings]
    assert len(findings) == 3
    assert any("../outside.md" in m for m in messages)
    assert any("/etc/hosts" in m for m in messages)
    assert any("escape/outside.md" in m for m in messages)


def test_yaml_paths_missing_registry_and_invalid_yaml_are_ignored_here(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    assert validate_yaml_paths(root) == []

    write(root / "registry/work-items/WORK-0001.yaml", "[invalid: yaml")
    assert validate_yaml_paths(root) == []


def test_yaml_read_error_is_deferred_to_main_validator(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "repo"
    path = root / "registry/work-items/WORK-0001.yaml"
    write(path, "id: WORK-0001\nstatus: IN_PROGRESS\n")
    original = Path.read_text

    def fake_read(self: Path, *args: object, **kwargs: object) -> str:
        if self == path:
            raise OSError("blocked")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    assert validate_yaml_paths(root) == []


def test_markdown_paths_accept_inside_external_and_anchor_but_reject_escape(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    write(root / "README.md", "root")
    write(root / "docs/good.md", "[root](../README.md) [web](https://example.com) [mail](mailto:a@b) [anchor](#x)\n")
    write(root / "docs/bad.md", "[escape](../../outside.md) [absolute](/etc/hosts)\n")
    write(tmp_path / "outside.md", "outside")
    write(root / ".git/ignored.md", "[escape](../../../outside.md)\n")

    findings = validate_markdown_paths(root)
    assert len(findings) == 2
    assert {f.rule for f in findings} == {"MARKDOWN_SCOPE"}


def test_markdown_read_error_is_deferred(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "repo"
    path = root / "bad.md"
    write(path, "x")
    original = Path.read_text

    def fake_read(self: Path, *args: object, **kwargs: object) -> str:
        if self == path:
            raise OSError("blocked")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    assert validate_markdown_paths(root) == []


def test_validate_combines_yaml_and_markdown_findings(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    write(root / "registry/work-items/WORK-0001.yaml", "id: WORK-0001\nstatus: IN_PROGRESS\nread_before: [../x]\n")
    write(root / "doc.md", "[x](../x)\n")
    assert {f.rule for f in validate(root)} == {"PATH_SCOPE", "MARKDOWN_SCOPE"}


def test_main_success_and_failure(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    clean = tmp_path / "clean"
    clean.mkdir()
    assert main([str(clean)]) == 0
    assert "0 error(s)" in capsys.readouterr().out

    bad = tmp_path / "bad"
    write(bad / "registry/work-items/WORK-0001.yaml", "id: WORK-0001\nstatus: IN_PROGRESS\nread_before: [../../escape]\n")
    assert main([str(bad)]) == 1
    captured = capsys.readouterr()
    assert "PATH_SCOPE" in captured.err
    assert "1 error(s)" in captured.out
