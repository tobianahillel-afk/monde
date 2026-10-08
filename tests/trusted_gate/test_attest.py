from __future__ import annotations

import copy
import io
import json
import os
from pathlib import Path
import runpy
import sys
import unittest
from unittest import mock

from tools.trusted_gate import attest as subject

A = "a" * 40
B = "b" * 40
C = "c" * 40
H = "d" * 40

MANDATORY = (
    ".github/workflows/governance.yml",
    ".github/workflows/_governance-core.yml",
    "requirements/governance-ci.txt",
    "tools/governance/validate_repo.py",
    "tools/governance/github_live_gate.py",
)
ROOT = (
    "tools/trusted_gate/attest.py",
    "registry/trust/approved-governance-v1.json",
    ".github/workflows/monde-trusted-attestation.yml",
)


def manifest():
    return {
        "version": 1, "origin_candidate_sha": H,
        "files": {name: {"sha": A, "mode": "100644"} for name in MANDATORY},
    }


def base_tree():
    return {path: (B, "100644") for path in ROOT}


def candidate_tree():
    return {
        **base_tree(),
        **{name: (A, "100644") for name in MANDATORY},
    }


def api_tree(index):
    return {
        "truncated": False,
        "tree": [
            {"path": name, "sha": sha, "mode": mode, "type": "blob"}
            for name, (sha, mode) in sorted(index.items())
        ],
    }


def snapshot():
    return {
        "number": 2, "state": "open",
        "head": {"sha": H, "repo": {"full_name": "o/r"}},
        "base": {"sha": C, "repo": {"full_name": "o/r"}},
    }


class TrustedAttestationTests(unittest.TestCase):
    def test_selects_source_and_config_but_excludes_default_root(self):
        for path in (
            "tools/governance/core.py",
            ".github/workflows/governance.yml",
            ".github/actions/custom/action.yml",
            "requirements/governance-ci.txt",
            "malicious/sitecustomize.py",
            "lib/payload.pth",
            "build/entry.sh",
            "pyproject.toml",
        ):
            self.assertTrue(subject.protected_path(path), path)
        for path in (
            "docs/README.md", "registry/reviews/REVIEW-0094.yaml",
            *ROOT, "tests/trusted_gate/test_attest.py",
        ):
            self.assertFalse(subject.protected_path(path), path)

    def test_manifest_rejects_missing_or_untrusted(self):
        self.assertEqual(len(subject.validate_manifest(manifest())), len(MANDATORY))
        cases = [
            None,
            {"version": True, "origin_candidate_sha": H, "files": manifest()["files"]},
            {**manifest(), "origin_candidate_sha": "invalid"},
            {**manifest(), "files": {}},
            {**manifest(), "files": {"arbitrary.md": {"sha": A, "mode": "100644"}}},
            {**manifest(), "files": {"new.py": {"sha": False, "mode": "100644"}}},
            {**manifest(), "files": {MANDATORY[0]: {"sha": A, "mode": "120000"}}},
        ]
        for case in cases:
            with self.subTest(case=str(case)[:70]):
                with self.assertRaises(subject.TrustFailure):
                    subject.validate_manifest(case)

    def test_exact_code_and_default_root_required(self):
        approved = subject.validate_manifest(manifest())
        subject.verify_trees(approved, base_tree(), candidate_tree())
        for changed in (
            {**candidate_tree(), MANDATORY[3]: (B, "100644")},
            {**candidate_tree(), "extra/sitecustomize.py": (B, "100644")},
            {key: value for key, value in candidate_tree().items() if key != MANDATORY[2]},
        ):
            with self.subTest(changed=sorted(changed)[:3]):
                with self.assertRaisesRegex(subject.TrustFailure, "executable source differs"):
                    subject.verify_trees(approved, base_tree(), changed)

        missing_root = {k: v for k, v in base_tree().items() if k != ROOT[0]}
        with self.assertRaisesRegex(subject.TrustFailure, "root is incomplete"):
            subject.verify_trees(approved, missing_root, candidate_tree())
        modified_root = {**candidate_tree(), ROOT[0]: (C, "100644")}
        with self.assertRaisesRegex(subject.TrustFailure, "modified.*trusted-root"):
            subject.verify_trees(approved, base_tree(), modified_root)

    def test_git_tree_shape_and_symlink_fail_closed(self):
        self.assertEqual(subject.index_tree(api_tree(candidate_tree())), candidate_tree())
        for payload in (
            None,
            {"truncated": True, "tree": []},
            {"truncated": False, "tree": "bad"},
            {"truncated": False, "tree": [{"path": "../bad.py", "type": "blob", "sha": A, "mode": "100644"}]},
            {"truncated": False, "tree": [{"path": "script.py", "type": "blob", "sha": A, "mode": "999999"}]},
            {"truncated": False, "tree": [{"path": "script.py", "type": "tree", "sha": A, "mode": "040000"}]},
            {"truncated": False, "tree": [
                {"path": "duplicate.py", "type": "blob", "sha": A, "mode": "100644"},
                {"path": "duplicate.py", "type": "blob", "sha": A, "mode": "100644"},
            ]},
        ):
            with self.subTest(payload=str(payload)[:60]):
                with self.assertRaises(subject.TrustFailure):
                    subject.index_tree(payload)

    def test_live_exact_revision_and_final_snapshot(self):
        approved = manifest()
        resources = [snapshot(), api_tree(base_tree()), api_tree(candidate_tree()), snapshot()]
        with mock.patch.object(subject, "fetch_json", side_effect=resources) as fetch:
            self.assertEqual(subject.attest("o/r", 2, H, C, approved, "token"), 5)
        self.assertEqual(fetch.call_count, 4)

        for altered in (
            {**snapshot(), "number": True},
            {**snapshot(), "state": "closed"},
            {**snapshot(), "head": {"sha": B, "repo": {"full_name": "o/r"}}},
            {**snapshot(), "head": {"sha": H, "repo": {"full_name": "fork/r"}}},
            {**snapshot(), "base": {"sha": B, "repo": {"full_name": "o/r"}}},
        ):
            with self.subTest(altered=altered), mock.patch.object(subject, "fetch_json", return_value=altered):
                with self.assertRaises(subject.TrustFailure):
                    subject.attest("o/r", 2, H, C, approved, "token")

        changed_after = {**snapshot(), "head": {"sha": B}}
        with mock.patch.object(
            subject, "fetch_json",
            side_effect=[snapshot(), api_tree(base_tree()), api_tree(candidate_tree()), changed_after],
        ):
            with self.assertRaisesRegex(subject.TrustFailure, "drifted"):
                subject.attest("o/r", 2, H, C, approved, "token")

    def test_invalid_selector_is_rejected_before_network(self):
        for repo,number,head in (("x",2,H),("o/r",True,H),("o/r",2,"bad")):
            with mock.patch.object(subject, "fetch_json") as fetch:
                with self.assertRaises(subject.TrustFailure):
                    subject.attest(repo, number, head, C, manifest(), "token")
                fetch.assert_not_called()


    def test_tree_malformed_nonblob_and_safe_unprotected_tree(self):
        with self.assertRaisesRegex(subject.TrustFailure, "node is malformed"):
            subject.index_tree({"truncated": False, "tree": [None]})
        value = {
            "truncated": False,
            "tree": [{"path": "docs", "type": "tree", "mode": "040000", "sha": A}],
        }
        self.assertEqual(subject.index_tree(value), {})

    def test_manifest_bad_shape_and_missing_mandatory(self):
        cases = [
            {"version": 1, "origin_candidate_sha": H, "files": {"go.py": "no"}},
            {"version": 1, "origin_candidate_sha": H, "files": {"go.py": {"sha": A}}},
            {"version": 1, "origin_candidate_sha": H, "files": {"go.py": {"sha": A, "mode": "100644"}}},
        ]
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises(subject.TrustFailure):
                    subject.validate_manifest(value)

    def test_rejects_executable_symlinks_explicitly(self):
        candidate = candidate_tree()
        candidate["extra/sitecustomize.py"] = (B, "120000")
        with self.assertRaisesRegex(subject.TrustFailure, "symlink"):
            subject.verify_trees(subject.validate_manifest(manifest()), base_tree(), candidate)

    def test_git_client_response_is_bounded_and_strictly_json(self):
        with self.assertRaisesRegex(subject.TrustFailure, "token is missing"):
            subject.fetch_json("https://api.github.com", "")

        def client(data):
            response = mock.MagicMock()
            response.__enter__.return_value.read.return_value = data
            return mock.patch.object(subject.request, "urlopen", return_value=response)

        with client(b'{"good": true}') as fetch:
            self.assertEqual(subject.fetch_json("https://api.github.com/x", "token"), {"good": True})
            self.assertEqual(fetch.call_args.kwargs["timeout"], 20)
        for payload, error in (
            (b"x", "malformed JSON"),
            (b"\xff", "malformed JSON"),
            (b"x" * 16_000_001, "exceeds bounded"),
        ):
            with self.subTest(error=error), client(payload):
                with self.assertRaisesRegex(subject.TrustFailure, error):
                    subject.fetch_json("https://api.github.com", "token")

    def test_snapshot_shape_missing_field_is_rejected(self):
        malformed = {"head": {}, "base": {}}
        with mock.patch.object(subject, "fetch_json", return_value=malformed):
            with self.assertRaisesRegex(subject.TrustFailure, "snapshot is malformed"):
                subject.attest("o/r", 2, H, C, manifest(), "token")

    def test_cli_success_error_and_module_entrypoint(self):
        env = {
            "GITHUB_REPOSITORY": "o/r",
            "MONDE_TRUST_PR_NUMBER": "2",
            "MONDE_TRUST_PR_HEAD": H,
            "MONDE_TRUST_PR_BASE": C,
            "GITHUB_TOKEN": "token",
        }
        with (
            mock.patch.object(sys, "argv", ["attest.py", "--manifest", "dummy.json"]),
            mock.patch.object(Path, "read_text", return_value=json.dumps(manifest())),
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch.object(subject, "attest", return_value=5) as call,
            mock.patch.object(sys, "stdout", new_callable=io.StringIO) as out,
        ):
            self.assertEqual(subject.main(), 0)
            self.assertIn("PASS: 5", out.getvalue())
        call.assert_called_once()

        with (
            mock.patch.object(sys, "argv", ["attest.py", "--manifest", "dummy.json"]),
            mock.patch.object(Path, "read_text", side_effect=OSError("broken")),
            mock.patch.object(sys, "stderr", new_callable=io.StringIO) as err,
        ):
            self.assertEqual(subject.main(), 1)
            self.assertIn("FAILED: broken", err.getvalue())

        with (
            mock.patch.object(sys, "argv", ["attest.py", "--manifest", "dummy.json"]),
            mock.patch.object(Path, "read_text", return_value=json.dumps(manifest())),
            mock.patch.dict(os.environ, {**env, "MONDE_TRUST_PR_NUMBER": "nope"}, clear=True),
            mock.patch.object(sys, "stderr", new_callable=io.StringIO),
        ):
            self.assertEqual(subject.main(), 1)

        with (
            mock.patch.object(sys, "argv", ["attest.py", "--manifest", "dummy.json"]),
            mock.patch.object(Path, "read_text", return_value="NOT JSON"),
            mock.patch.object(sys, "stderr", new_callable=io.StringIO),
        ):
            with self.assertRaises(SystemExit) as raised:
                runpy.run_module("tools.trusted_gate.attest", run_name="__main__")
        self.assertEqual(raised.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
