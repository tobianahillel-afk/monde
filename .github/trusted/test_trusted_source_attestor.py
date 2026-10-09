"""Self-tests for the base-owned, non-executing source-attestation boundary."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest import mock

spec = importlib.util.spec_from_file_location(
    "trusted_source_attestor",
    Path(__file__).resolve().parent / "trusted_source_attestor.py",
)
assert spec and spec.loader
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)

def fixture():
    expected = {
        "requirements/governance-ci.txt": {"sha": "a" * 40, "mode": "100644"},
        "tools/governance/validate_repo.py": {"sha": "b" * 40, "mode": "100644"},
        ".github/workflows/governance.yml": {"sha": "c" * 40, "mode": "100644"},
        ".github/workflows/_governance-core.yml": {"sha": "d" * 40, "mode": "100644"},
    }
    manifest = {"schema_version": 1, "target_pr": 2, "source_files": expected}
    tree = {
        "truncated": False,
        "tree": [
            {"path": path, "type": "blob", **data}
            for path, data in expected.items()
        ],
    }
    return manifest, tree


class TrustedSourceTests(unittest.TestCase):
    def test_exact_approved_tree_passes(self):
        manifest, tree = fixture()
        self.assertEqual(subject.verify_tree(manifest, tree), 4)

    def test_missing_extra_and_modified_executable_fail(self):
        manifest, tree = fixture()
        for nodes in (
            tree["tree"][:-1],
            tree["tree"] + [{"path": "sitecustomize.py", "type": "blob", "mode": "100644", "sha": "e" * 40}],
            [{**n, "sha": "f" * 40} if n["path"] == "requirements/governance-ci.txt" else n for n in tree["tree"]],
        ):
            with self.subTest(nodes=nodes), self.assertRaisesRegex(subject.AttestationError, "unapproved governance"):
                subject.verify_tree(manifest, {"truncated": False, "tree": nodes})

    def test_symlink_and_executable_modes_fail(self):
        manifest, tree = fixture()
        for mode in ("120000", "160000", "100755"):
            changed = [{**n, "mode": mode} if n["path"] == "tools/governance/validate_repo.py" else n for n in tree["tree"]]
            with self.subTest(mode=mode), self.assertRaises(subject.AttestationError):
                subject.verify_tree(manifest, {"truncated": False, "tree": changed})

    def test_missing_invalid_or_duplicated_nodes_fail(self):
        manifest, tree = fixture()
        for value in (
            {"truncated": True, "tree": tree["tree"]},
            {"truncated": False, "tree": None},
            {"truncated": False, "tree": tree["tree"] + [tree["tree"][0]]},
            {"truncated": False, "tree": [None]},
        ):
            with self.subTest(value=value), self.assertRaises(subject.AttestationError):
                subject.verify_tree(manifest, value)

    def test_bad_manifest_and_identity_are_rejected(self):
        manifest, tree = fixture()
        for key, value in (
            ("target_pr", True),
            ("target_pr", 3),
            ("schema_version", 2),
            ("source_files", {}),
        ):
            candidate = dict(manifest)
            candidate[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(subject.AttestationError):
                subject.verify_tree(candidate, tree)
        bad = dict(manifest)
        bad["source_files"] = dict(manifest["source_files"])
        bad["source_files"]["sitecustomize.py"] = {"sha": "bad", "mode": "100644"}
        with self.assertRaises(subject.AttestationError):
            subject.validate_manifest(bad)

    def test_scope_guards_unexpected_executable_sources(self):
        self.assertTrue(subject.in_scope("sitecustomize.py", "100644"))
        self.assertTrue(subject.in_scope("unknown", "100755"))
        self.assertTrue(subject.in_scope("requirements/override.txt", "100644"))
        self.assertTrue(subject.in_scope(".github/workflows/extra.yml", "100644"))
        self.assertFalse(subject.in_scope("docs/readme.md", "100644"))

    def test_commit_and_tree_are_never_executed(self):
        manifest, tree = fixture()
        self.assertEqual(subject.verify_tree(manifest, tree), 4)
        # All proof uses Git object identity. No subprocess, eval, import or
        # candidate-file evaluation is required by verify_tree.


if __name__ == "__main__":
    unittest.main()
