"""Self-tests for the base-owned, non-executing source-attestation boundary."""
from __future__ import annotations

import importlib.util
import os
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

    def test_recursive_git_tree_directory_entries_are_structural_only(self):
        manifest, tree = fixture()
        directories = [
            {"path": ".github", "type": "tree", "mode": "040000", "sha": "1" * 40},
            {"path": ".github/workflows", "type": "tree", "mode": "040000", "sha": "2" * 40},
            {"path": ".github/trusted", "type": "tree", "mode": "040000", "sha": "3" * 40},
            {"path": "requirements", "type": "tree", "mode": "040000", "sha": "4" * 40},
            {"path": "tools", "type": "tree", "mode": "040000", "sha": "5" * 40},
            {"path": "tools/governance", "type": "tree", "mode": "040000", "sha": "6" * 40},
        ]
        owned = [
            {"path": ".github/trusted/trusted_source_attestor.py", "type": "blob", "mode": "100644", "sha": "7" * 40},
            {"path": ".github/trusted/approved_sources.json", "type": "blob", "mode": "100644", "sha": "8" * 40},
            {"path": ".github/workflows/monde-trusted-source.yml", "type": "blob", "mode": "100644", "sha": "9" * 40},
        ]
        base = {"truncated": False, "tree": directories + owned}
        candidate = {"truncated": False, "tree": directories + tree["tree"] + owned}
        self.assertEqual(subject.verify_tree(manifest, candidate, base), 7)
        self.assertEqual(subject.verify_tree(manifest, {"truncated": False, "tree": directories + tree["tree"]}), 4)

    def test_directory_exemption_does_not_permit_unsafe_source_entries(self):
        manifest, tree = fixture()
        for node in (
            {"path": "tools/governance", "type": "blob", "mode": "040000", "sha": "1" * 40},
            {"path": "tools/governance/untrusted", "type": "tree", "mode": "100644", "sha": "2" * 40},
            {"path": "docs/unsafe-link", "type": "blob", "mode": "120000", "sha": "3" * 40},
            {"path": "docs/submodule", "type": "commit", "mode": "160000", "sha": "4" * 40},
        ):
            with self.subTest(node=node), self.assertRaises(subject.AttestationError):
                subject.verify_tree(manifest, {"truncated": False, "tree": tree["tree"] + [node]})

        owned = [
            {"path": ".github/trusted/trusted_source_attestor.py", "type": "blob", "mode": "100644", "sha": "7" * 40},
            {"path": ".github/trusted/approved_sources.json", "type": "blob", "mode": "100644", "sha": "8" * 40},
            {"path": ".github/workflows/monde-trusted-source.yml", "type": "blob", "mode": "100644", "sha": "9" * 40},
        ]
        bad_base = {"truncated": False, "tree": owned + [
            {"path": ".github/trusted/unapproved", "type": "blob", "mode": "040000", "sha": "a" * 40},
        ]}
        with self.assertRaises(subject.AttestationError):
            subject.verify_tree(manifest, {"truncated": False, "tree": tree["tree"] + owned}, bad_base)

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

    def test_base_owned_trust_root_must_match_approved_main(self):
        manifest, tree = fixture()
        owned = [
            {"path": ".github/trusted/trusted_source_attestor.py", "type": "blob", "mode": "100644", "sha": "e" * 40},
            {"path": ".github/trusted/approved_sources.json", "type": "blob", "mode": "100644", "sha": "f" * 40},
            {"path": ".github/workflows/monde-trusted-source.yml", "type": "blob", "mode": "100644", "sha": "1" * 40},
        ]
        base = {"truncated": False, "tree": owned}
        candidate = {"truncated": False, "tree": tree["tree"] + owned}
        self.assertEqual(subject.verify_tree(manifest, candidate, base), 7)
        drift = {"truncated": False, "tree": tree["tree"] + [{**x, "sha": "2" * 40} for x in owned]}
        with self.assertRaisesRegex(subject.AttestationError, "unapproved governance"):
            subject.verify_tree(manifest, drift, base)
        with self.assertRaisesRegex(subject.AttestationError, "missing default-branch"):
            subject.verify_tree(manifest, candidate, {"truncated": False, "tree": owned[:1]})
        with self.assertRaisesRegex(subject.AttestationError, "trust-root tree is incomplete"):
            subject.verify_tree(manifest, candidate, {"truncated": True, "tree": owned})

    def test_scope_guards_unexpected_executable_sources(self):
        self.assertTrue(subject.in_scope("sitecustomize.py", "100644"))
        self.assertTrue(subject.in_scope("unknown", "100755"))
        self.assertTrue(subject.in_scope("requirements/override.txt", "100644"))
        self.assertTrue(subject.in_scope(".github/workflows/extra.yml", "100644"))
        self.assertFalse(subject.in_scope("docs/readme.md", "100644"))
        self.assertTrue(subject.in_scope(".github/actions/local/action.yml", "100644"))
        self.assertTrue(subject.in_scope(".github/CODEOWNERS", "100644"))
        self.assertTrue(subject.in_scope(".github/dependabot.yml", "100644"))
        self.assertTrue(subject.in_scope("scripts/gate_helper.sh", "100644"))
        self.assertTrue(subject.in_scope("tools/governance/validator.bin", "100644"))
        self.assertTrue(subject.in_scope("tests/governance/test_fixture.json", "100644"))
        self.assertTrue(subject.in_scope("native_extension.dll", "100644"))
        self.assertTrue(subject.in_scope("plugin.zip", "100644"))
        self.assertTrue(subject.in_scope("Makefile", "100644"))
        self.assertTrue(subject.in_scope(".gitmodules", "100644"))
        self.assertTrue(subject.in_scope(".gitattributes", "100644"))
        self.assertTrue(subject.in_scope(".lfsconfig", "100644"))
        self.assertTrue(subject.in_scope("docs/unsafe-link", "120000"))
        self.assertTrue(subject.in_scope("docs/unapproved-submodule", "160000"))

    def test_candidate_cannot_add_unapproved_local_actions_or_scripts(self):
        manifest, tree = fixture()
        for path in (
            ".github/actions/local/action.yml",
            ".github/CODEOWNERS",
            "scripts/injected_wrapper.sh",
            "tools/governance/module.wasm",
            "plugin.zip",
            "Makefile",
        ):
            node = {"path": path, "type": "blob", "mode": "100644", "sha": "e" * 40}
            with self.subTest(path=path), self.assertRaisesRegex(
                subject.AttestationError, "unapproved governance source change"
            ):
                subject.verify_tree(
                    manifest, {"truncated": False, "tree": tree["tree"] + [node]}
                )

    def test_unapproved_gitlinks_symlinks_and_checkout_config_fail_anywhere(self):
        manifest, tree = fixture()
        attacks = [
            {"path": "docs/unsafe-link", "type": "blob", "mode": "120000", "sha": "e" * 40},
            {"path": "docs/unapproved-submodule", "type": "commit", "mode": "160000", "sha": "e" * 40},
            {"path": ".gitmodules", "type": "blob", "mode": "100644", "sha": "e" * 40},
            {"path": ".gitattributes", "type": "blob", "mode": "100644", "sha": "e" * 40},
            {"path": ".lfsconfig", "type": "blob", "mode": "100644", "sha": "e" * 40},
        ]
        for injected in attacks:
            with self.subTest(path=injected["path"]), self.assertRaises(subject.AttestationError):
                subject.verify_tree(
                    manifest,
                    {"truncated": False, "tree": tree["tree"] + [injected]},
                )

    def test_manifest_cannot_claim_base_owned_sources_or_noncanonical_paths(self):
        manifest, _ = fixture()
        for path in (
            ".github/trusted/new_trust_helper.py",
            ".github/workflows/monde-trusted-source.yml",
            "tools//governance/validate.py",
            "tools/./governance/validate.py",
            "tools/../governance/validate.py",
            "tools\\governance\\validate.py",
        ):
            altered = dict(manifest)
            altered["source_files"] = {
                **manifest["source_files"],
                path: {"sha": "e" * 40, "mode": "100644"},
            }
            with self.subTest(path=path), self.assertRaises(subject.AttestationError):
                subject.validate_manifest(altered)

    def test_trusted_workflow_checkout_is_bound_to_event_base_commit(self):
        workflow = (
            Path(__file__).resolve().parents[1] / "workflows" /
            "monde-trusted-source.yml"
        ).read_text(encoding="utf-8")
        trusted = workflow.split("  trusted-attestation:", 1)[1]
        self.assertIn("ref: ${{ github.event.pull_request.base.sha }}", trusted)
        self.assertIn("github.event.pull_request.base.ref == 'main'", trusted)
        self.assertIn("MONDE_ATTEST_BASE_REF: ${{ github.event.pull_request.base.ref }}", trusted)
        self.assertNotIn("github.event.repository.default_branch", trusted)
        self.assertIn("persist-credentials: false", trusted)
        self.assertNotIn("head.sha", trusted.split("      - name: Verify exact candidate", 1)[0])

    def test_runtime_rejects_non_default_base_before_network_request(self):
        common = {
            "GITHUB_REPOSITORY": "tobianahillel-afk/monde",
            "MONDE_ATTEST_HEAD": "a" * 40,
            "MONDE_ATTEST_BASE": "b" * 40,
            "MONDE_ATTEST_PR": "2",
            "GITHUB_TOKEN": "not-a-real-token",
        }
        for ref in ("", "feature", "Main", "refs/heads/main"):
            with (
                self.subTest(ref=ref),
                mock.patch.dict(os.environ, {**common, "MONDE_ATTEST_BASE_REF": ref}, clear=True),
                mock.patch.object(subject, "_get_json") as network,
            ):
                with self.assertRaisesRegex(subject.AttestationError, "invalid trusted-source invocation identity"):
                    subject.main()
                network.assert_not_called()

        with (
            mock.patch.dict(os.environ, {**common, "MONDE_ATTEST_BASE_REF": "main"}, clear=True),
            mock.patch.object(subject, "_get_json", return_value={}) as network,
        ):
            with self.assertRaisesRegex(subject.AttestationError, "candidate commit identity mismatch"):
                subject.main()
            network.assert_called_once()

    def test_commit_and_tree_are_never_executed(self):
        manifest, tree = fixture()
        self.assertEqual(subject.verify_tree(manifest, tree), 4)
        # All proof uses Git object identity. No subprocess, eval, import or
        # candidate-file evaluation is required by verify_tree.


if __name__ == "__main__":
    unittest.main()
