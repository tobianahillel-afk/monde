from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import trusted_source_attestor as source
import trusted_source_consumer as consumer
import trusted_source_collector as collector


class CompletedRunCollectorTests(unittest.TestCase):
    def setUp(self):
        manifest_path = Path(source.__file__).resolve().parent / "approved_sources.json"
        self.manifest = manifest_path.read_bytes()
        self.head = "a" * 40
        self.base = "b" * 40
        self.pr = {
            "number": 2, "state": "open", "draft": False,
            "head": {"sha": self.head}, "base": {"sha": self.base, "ref": "main"},
        }
        self.branch = {"commit": {"sha": self.base}}
        self.run = {
            "id": 9001, "run_attempt": 1, "head_sha": self.base,
            "head_branch": "main", "status": "completed", "conclusion": "success",
            "event": "pull_request_target", "path": consumer.WORKFLOW_PATH,
            "repository": {"full_name": collector.REPO},
            "created_at": "2026-10-09T11:00:00Z",
        }
        self.artifact = {
            "id": 9011, "name": "monde-trusted-proof-9001-1",
            "expired": False, "size_in_bytes": 500,
            "workflow_run": {"id": 9001},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "proof.json"
            with mock.patch.dict(os.environ, {
                "MONDE_ATTEST_PROOF_PATH": str(path),
                "GITHUB_RUN_ID": "9001",
                "GITHUB_RUN_ATTEMPT": "1",
            }):
                source._write_attestation_proof(
                    collector.REPO, self.head, self.base,
                    len(source.validate_manifest(json.loads(self.manifest))),
                )
            self.proof = path.read_bytes()

    def test_run_selection_refetches_exact_latest_across_two_events(self):
        old = {**self.run, "id": 9000, "created_at": "2026-10-09T10:00:00Z"}
        def fetch(_repo, route, _token):
            if "event=pull_request_target" in route:
                return {"total_count": 1, "workflow_runs": [old]}
            if "event=push" in route:
                return {"total_count": 1, "workflow_runs": [self.run]}
            if route == "actions/runs/9001":
                return self.run
            raise AssertionError(route)
        with mock.patch.object(source, "_get_json", side_effect=fetch):
            self.assertEqual(collector._collect_run(collector.REPO, "token")["id"], 9001)

    def test_run_selection_does_not_skip_newer_failed_run(self):
        failure = {**self.run, "id": 9002, "conclusion": "failure",
                   "created_at": "2026-10-09T12:00:00Z"}
        def fetch(_repo, route, _token):
            if "event=pull_request_target" in route:
                return {"total_count": 1, "workflow_runs": [failure]}
            if "event=push" in route:
                return {"total_count": 1, "workflow_runs": [self.run]}
            if route == "actions/runs/9002":
                return failure
            raise AssertionError(route)
        with mock.patch.object(source, "_get_json", side_effect=fetch):
            selected = collector._collect_run(collector.REPO, "token")
        self.assertEqual(selected["conclusion"], "failure")
        with self.assertRaises(source.AttestationError):
            consumer.verify_completed_proof(
                self.proof, selected, self.artifact, self.pr, self.branch, self.manifest,
            )

    def test_run_count_and_id_corruption_fails_closed(self):
        bad_cases = [
            {"total_count": 1, "workflow_runs": []},
            {"total_count": 0, "workflow_runs": [self.run]},
            {"total_count": "1", "workflow_runs": [self.run]},
            {"total_count": 1, "workflow_runs": ["bogus"]},
        ]
        for bad in bad_cases:
            with self.subTest(bad=bad):
                with mock.patch.object(source, "_get_json", return_value=bad):
                    with self.assertRaises(source.AttestationError):
                        collector._collect_run(collector.REPO, "t")

    def test_artifact_listing_is_complete_and_unique(self):
        with mock.patch.object(
            source, "_get_json", return_value={"total_count": 1, "artifacts": [self.artifact]}
        ):
            self.assertEqual(
                collector._unique_artifact(collector.REPO, "t", self.run),
                self.artifact,
            )
        for bad in (
            {"total_count": 101, "artifacts": [self.artifact]},
            {"total_count": 1, "artifacts": []},
            {"total_count": 2, "artifacts": [self.artifact, self.artifact]},
        ):
            with self.subTest(bad=bad), mock.patch.object(source, "_get_json", return_value=bad):
                with self.assertRaises(source.AttestationError):
                    collector._unique_artifact(collector.REPO, "t", self.run)

    @staticmethod
    def zip_bytes(files):
        raw = io.BytesIO()
        with zipfile.ZipFile(raw, "w") as zipped:
            for name, data in files:
                zipped.writestr(name, data)
        return raw.getvalue()

    def test_download_requires_single_exact_bounded_proof_file(self):
        zipdata = self.zip_bytes([(collector.PROOF_FILE, self.proof)])
        opener = mock.Mock()
        opener.open.return_value = io.BytesIO(zipdata)
        with mock.patch.object(collector.urllib.request, "build_opener", return_value=opener):
            self.assertEqual(
                collector._download_exact_proof(collector.REPO, "t", self.artifact),
                self.proof,
            )
        for bad in (
            b"not-zip",
            self.zip_bytes([("../proof.json", self.proof)]),
            self.zip_bytes([(collector.PROOF_FILE, self.proof), ("extra", b"1")]),
            self.zip_bytes([(collector.PROOF_FILE, b"x" * (consumer.MAX_PROOF_BYTES + 1))]),
            b"x" * (collector.MAX_ZIP_BYTES + 1),
        ):
            opener.open.return_value = io.BytesIO(bad)
            with mock.patch.object(collector.urllib.request, "build_opener", return_value=opener):
                with self.subTest(size=len(bad)), self.assertRaises(source.AttestationError):
                    collector._download_exact_proof(collector.REPO, "t", self.artifact)

    def test_redirect_never_forwards_token_to_untrusted_host(self):
        handler = collector._SafeArtifactRedirect()
        request = collector.urllib.request.Request(
            "https://api.github.com/repos/x/y/actions/artifacts/1/zip",
            headers={"Authorization": "Bearer secret"},
        )
        safe = handler.redirect_request(
            request, None, 302, "Found", {},
            "https://pipelines.actions.githubusercontent.com/signed",
        )
        self.assertIsNotNone(safe)
        self.assertFalse(safe.has_header("Authorization"))
        for location in (
            "http://pipelines.actions.githubusercontent.com/insecure",
            "https://evil.example.org/steal",
        ):
            with self.subTest(location=location), self.assertRaises(source.AttestationError):
                handler.redirect_request(request, None, 302, "Found", {}, location)

    def test_live_collector_rechecks_current_pr_and_main(self):
        calls = []
        def remote(_repo, route, _token):
            calls.append(route)
            if route == "pulls/2":
                return self.pr
            if route == "branches/main":
                return self.branch
            raise AssertionError(route)
        with (
            mock.patch.object(source, "_get_json", side_effect=remote),
            mock.patch.object(collector, "_collect_run", return_value=self.run),
            mock.patch.object(collector, "_unique_artifact", return_value=self.artifact),
            mock.patch.object(collector, "_download_exact_proof", return_value=self.proof),
        ):
            self.assertEqual(
                collector.check_current_main_owned_proof(collector.REPO, "t", self.manifest),
                (self.head, self.base),
            )
        self.assertEqual(calls, ["pulls/2", "branches/main", "pulls/2", "branches/main"])

    def test_live_collector_rejects_concurrent_main_advance(self):
        bases = iter([self.branch, {"commit": {"sha": "c" * 40}}])
        def remote(_repo, route, _token):
            if route == "pulls/2":
                return self.pr
            if route == "branches/main":
                return next(bases)
            raise AssertionError(route)
        with (
            mock.patch.object(source, "_get_json", side_effect=remote),
            mock.patch.object(collector, "_collect_run", return_value=self.run),
            mock.patch.object(collector, "_unique_artifact", return_value=self.artifact),
            mock.patch.object(collector, "_download_exact_proof", return_value=self.proof),
        ):
            with self.assertRaisesRegex(source.AttestationError, "drifted"):
                collector.check_current_main_owned_proof(collector.REPO, "t", self.manifest)


if __name__ == "__main__":
    unittest.main()
