"""Self-tests for the base-owned, non-executing source-attestation boundary."""
from __future__ import annotations

import importlib.util
import json
import io
import tempfile
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
        self.assertEqual(subject.verify_tree(manifest, candidate, base), 4)
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
        self.assertEqual(subject.verify_tree(manifest, candidate, base), 4)
        # WORK-0002 predates the base-owned trust files; their absence
        # must not invalidate its otherwise approved sources.
        preintegration = {"truncated": False, "tree": tree["tree"]}
        self.assertEqual(subject.verify_tree(manifest, preintegration, base), 4)
        duplicate = {"truncated": False, "tree": tree["tree"] + owned + [owned[0]]}
        with self.assertRaisesRegex(subject.AttestationError, "duplicate candidate trust-root"):
            subject.verify_tree(manifest, duplicate, base)
        extra = {"truncated": False, "tree": tree["tree"] + owned + [
            {"path": ".github/trusted/unapproved.py", "type": "blob",
             "mode": "100644", "sha": "a" * 40}
        ]}
        with self.assertRaisesRegex(subject.AttestationError, "unapproved default-branch trust-root"):
            subject.verify_tree(manifest, extra, base)
        drift = {"truncated": False, "tree": tree["tree"] + [{**x, "sha": "2" * 40} for x in owned]}
        with self.assertRaisesRegex(subject.AttestationError, "unapproved default-branch trust-root"):
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
        self.assertNotIn("head.sha", trusted.split("      - name: Validate and publish exact", 1)[0])

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
            mock.patch.object(subject, "_publish_status") as publisher,
        ):
            with self.assertRaisesRegex(subject.AttestationError, "current PR #2 authority"):
                subject.main()
            network.assert_called_once()
            self.assertEqual([x.args[3] for x in publisher.call_args_list], ["pending", "failure"])

    def test_trusted_manifest_rejects_duplicate_json_keys_at_every_depth(self):
        payloads = [
            '{"schema_version":1,"schema_version":1,"target_pr":2,"source_files":{}}',
            '{"schema_version":1,"target_pr":2,"source_files":{'
            '"requirements/governance-ci.txt":{"sha":"a","mode":"100644"},'
            '"requirements/governance-ci.txt":{"sha":"b","mode":"100644"}}}',
            '{"schema_version":1,"target_pr":2,"source_files":{'
            '"requirements/governance-ci.txt":{"sha":"a","sha":"b","mode":"100644"}}}',
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            for contents in payloads:
                with self.subTest(contents=contents):
                    path.write_text(contents, encoding="utf-8")
                    with self.assertRaisesRegex(
                        subject.AttestationError, "duplicate trusted-manifest JSON key"
                    ):
                        subject.load_manifest(path)

    def test_trusted_manifest_canonical_json_load_succeeds(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            manifest, _tree = fixture()
            path.write_text(json.dumps(manifest), encoding="utf-8")
            self.assertEqual(subject.load_manifest(path), manifest)

    def test_merge_result_requires_base_trust_roots_even_when_candidate_omits_them(self):
        manifest, candidate = fixture()
        owned = [
            {"path": ".github/trusted/trusted_source_attestor.py", "type": "blob",
             "mode": "100644", "sha": "1" * 40},
            {"path": ".github/trusted/approved_sources.json", "type": "blob",
             "mode": "100644", "sha": "2" * 40},
            {"path": ".github/workflows/monde-trusted-source.yml", "type": "blob",
             "mode": "100644", "sha": "3" * 40},
        ]
        base = {"truncated": False, "tree": owned}
        merged = {"truncated": False, "tree": candidate["tree"] + owned}
        self.assertEqual(subject.verify_tree(manifest, candidate, base), 4)
        self.assertEqual(
            subject.verify_tree(manifest, merged, base, require_base_owned=True), 4,
        )
        # Simulates a PR that has integrated main and then deleted trust roots.
        for missing in owned:
            pr_merge = {
                "truncated": False,
                "tree": [n for n in merged["tree"] if n["path"] != missing["path"]],
            }
            with self.subTest(path=missing["path"]), self.assertRaisesRegex(
                subject.AttestationError, "merged result removed"
            ):
                subject.verify_tree(manifest, pr_merge, base, require_base_owned=True)
        with self.assertRaisesRegex(subject.AttestationError, "merged result removed"):
            subject.verify_tree(manifest, candidate, base, require_base_owned=True)
        with self.assertRaisesRegex(subject.AttestationError, "unapproved default-branch trust-root"):
            subject.verify_tree(manifest, merged, require_base_owned=True)

    def test_exact_live_pr_snapshot_rejects_mismatched_authority(self):
        head, base = "a" * 40, "b" * 40
        pr = {
            "number": 2, "state": "open", "draft": False,
            "head": {"sha": head}, "base": {"sha": base, "ref": "main"},
            "mergeable": True, "merge_commit_sha": "c" * 40,
        }
        with mock.patch.object(subject, "_get_json", return_value=pr):
            self.assertEqual(
                subject._exact_pr_snapshot("o/r", "t", head, base), pr,
            )
        for bad in (
            {**pr, "number": True},
            {**pr, "head": {"sha": "f" * 40}},
            {**pr, "base": {"sha": base, "ref": "feature"}},
            {**pr, "draft": True},
            {**pr, "merge_commit_sha": None},
        ):
            with self.subTest(bad=bad), mock.patch.object(
                subject, "_get_json", return_value=bad
            ):
                with self.assertRaisesRegex(subject.AttestationError, "current PR #2 authority"):
                    subject._exact_pr_snapshot("o/r", "t", head, base)

    def test_merged_commit_must_bind_exact_base_and_candidate_parents(self):
        head, base, merge = "a" * 40, "b" * 40, "c" * 40
        manifest, candidate = fixture()
        roots = [
            {"path": ".github/trusted/trusted_source_attestor.py", "type": "blob",
             "mode": "100644", "sha": "1" * 40},
            {"path": ".github/trusted/approved_sources.json", "type": "blob",
             "mode": "100644", "sha": "2" * 40},
            {"path": ".github/workflows/monde-trusted-source.yml", "type": "blob",
             "mode": "100644", "sha": "3" * 40},
        ]
        base_tree = {"sha": "e" * 40, "truncated": False, "tree": roots}
        candidate_tree = {"sha": "d" * 40, **candidate}
        merged_tree = {
            "sha": "f" * 40,
            "truncated": False,
            "tree": candidate["tree"] + roots,
        }
        pr = {
            "number": 2, "state": "open", "draft": False,
            "head": {"sha": head}, "base": {"sha": base, "ref": "main"},
            "mergeable": True, "merge_commit_sha": merge,
        }
        documents = {
            "pulls/2": pr,
            "git/commits/" + head: {
                "sha": head, "tree": {"sha": candidate_tree["sha"]},
            },
            "git/trees/" + candidate_tree["sha"] + "?recursive=1": candidate_tree,
            "git/commits/" + base: {
                "sha": base, "tree": {"sha": base_tree["sha"]},
            },
            "git/trees/" + base_tree["sha"] + "?recursive=1": base_tree,
            "git/commits/" + merge: {
                "sha": merge, "parents": [{"sha": base}, {"sha": head}],
                "tree": {"sha": merged_tree["sha"]},
            },
            "git/trees/" + merged_tree["sha"] + "?recursive=1": merged_tree,
            "branches/main": {"commit": {"sha": base}},
        }
        def get(_repo, route, _token):
            return documents[route]
        with (
            mock.patch.object(subject, "load_manifest", return_value=manifest),
            mock.patch.object(subject, "_get_json", side_effect=get),
        ):
            self.assertEqual(subject._verify_approved_merge("o/r", "t", head, base), 4)
            documents["git/commits/" + merge]["parents"] = [
                {"sha": head}, {"sha": base},
            ]
            with self.assertRaisesRegex(subject.AttestationError, "merge is not bound"):
                subject._verify_approved_merge("o/r", "t", head, base)
            documents["git/commits/" + merge]["parents"] = [
                {"sha": base}, {"sha": head},
            ]
            documents["git/trees/" + merged_tree["sha"] + "?recursive=1"] = {
                **merged_tree,
                "tree": candidate["tree"],
            }
            with self.assertRaisesRegex(subject.AttestationError, "merged result removed"):
                subject._verify_approved_merge("o/r", "t", head, base)
            documents["git/trees/" + merged_tree["sha"] + "?recursive=1"] = merged_tree
            documents["branches/main"] = {"commit": {"sha": "0" * 40}}
            with self.assertRaisesRegex(subject.AttestationError, "default branch advanced"):
                subject._verify_approved_merge("o/r", "t", head, base)

    def test_exact_candidate_status_publisher_acknowledges_context(self):
        head = "a" * 40
        def response(request, timeout=0):
            self.assertEqual(timeout, 20)
            self.assertEqual(request.get_method(), "POST")
            self.assertTrue(request.full_url.endswith("/statuses/" + head))
            posted = json.loads(request.data)
            self.assertEqual(posted["context"], subject.STATUS_CONTEXT)
            return io.BytesIO(json.dumps({
                "state": posted["state"],
                "context": posted["context"],
                "sha": head,
            }).encode("utf-8"))
        with mock.patch.object(subject.urllib.request, "urlopen", side_effect=response):
            subject._publish_status("o/r", head, "t", "pending", "starting")
            subject._publish_status("o/r", head, "t", "success", "done")
            subject._publish_status("o/r", head, "t", "failure", "rejected")
        for state in ("", "error"):
            with self.assertRaisesRegex(subject.AttestationError, "invalid exact"):
                subject._publish_status("o/r", head, "t", state, "bad")
        with mock.patch.object(
            subject.urllib.request, "urlopen",
            return_value=io.BytesIO(b'{"state":"success","context":"wrong","sha":"' + head.encode() + b'"}'),
        ):
            with self.assertRaisesRegex(subject.AttestationError, "acknowledgement"):
                subject._publish_status("o/r", head, "t", "success", "bad")

    def test_status_publication_is_pending_then_terminal_on_exact_candidate_head(self):
        env = {
            "GITHUB_REPOSITORY": "tobianahillel-afk/monde",
            "MONDE_ATTEST_HEAD": "a" * 40,
            "MONDE_ATTEST_BASE": "b" * 40,
            "MONDE_ATTEST_BASE_REF": "main",
            "MONDE_ATTEST_PR": "2",
            "GITHUB_TOKEN": "test-only",
        }
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch.object(subject, "_verify_approved_merge", return_value=167),
            mock.patch.object(subject, "_publish_status") as status,
        ):
            self.assertEqual(subject.main(), 0)
        self.assertEqual([c.args[3] for c in status.call_args_list], ["pending", "success"])
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch.object(subject, "_verify_approved_merge",
                              side_effect=subject.AttestationError("bad tree")),
            mock.patch.object(subject, "_publish_status") as status,
        ):
            with self.assertRaisesRegex(subject.AttestationError, "bad tree"):
                subject.main()
        self.assertEqual([c.args[3] for c in status.call_args_list], ["pending", "failure"])

    def test_workflow_publishes_commit_status_with_trusted_job_permissions(self):
        workflow = (
            Path(__file__).resolve().parents[1] / "workflows" /
            "monde-trusted-source.yml"
        ).read_text(encoding="utf-8")
        trusted = workflow.split("  trusted-attestation:", 1)[1]
        self.assertIn("statuses: write", trusted)
        self.assertIn("contents: read", trusted)
        self.assertIn("MONDE_ATTEST_HEAD: ${{ github.event.pull_request.head.sha }}", trusted)
        self.assertNotIn("actions: write", trusted)
        self.assertNotIn("pull-requests: write", trusted)

    def test_commit_and_tree_are_never_executed(self):
        manifest, tree = fixture()
        self.assertEqual(subject.verify_tree(manifest, tree), 4)
        # All proof uses Git object identity. No subprocess, eval, import or
        # candidate-file evaluation is required by verify_tree.


if __name__ == "__main__":
    unittest.main()
