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

    @staticmethod
    def job_payload(run_id, conclusion="success", status="completed"):
        return {"total_count": 1, "jobs": [{
            "id": run_id + 10000,
            "run_id": run_id,
            "name": collector.TRUSTED_JOB_NAME,
            "status": status,
            "conclusion": conclusion if status == "completed" else None,
        }]}

    def test_run_selection_skips_newer_unrelated_pr_target(self):
        unrelated = {**self.run, "id": 9002, "event": "pull_request_target",
                     "created_at": "2026-10-09T12:00:00Z"}
        def fetch(_repo, route, _token):
            if "event=pull_request_target" in route:
                return {"total_count": 2, "workflow_runs": [unrelated, self.run]}
            if "event=push" in route:
                return {"total_count": 0, "workflow_runs": []}
            if route == "actions/runs/9002/jobs?per_page=100":
                return self.job_payload(9002, conclusion="skipped")
            if route == "actions/runs/9001/jobs?per_page=100":
                return self.job_payload(9001)
            if route == "actions/runs/9001":
                return self.run
            raise AssertionError(route)
        with mock.patch.object(source, "_get_json", side_effect=fetch) as query:
            self.assertEqual(collector._collect_run(collector.REPO, "t")["id"], 9001)
        self.assertNotIn(
            "actions/runs/9002", [call.args[1] for call in query.call_args_list]
        )

    def test_newer_failed_relevant_run_supersedes_older_success(self):
        failed = {**self.run, "id": 9003, "conclusion": "failure",
                  "created_at": "2026-10-09T13:00:00Z"}
        def fetch(_repo, route, _token):
            if "event=pull_request_target" in route:
                return {"total_count": 2, "workflow_runs": [failed, self.run]}
            if "event=push" in route:
                return {"total_count": 0, "workflow_runs": []}
            if route == "actions/runs/9003/jobs?per_page=100":
                return self.job_payload(9003, conclusion="failure")
            if route == "actions/runs/9003":
                return failed
            raise AssertionError(route)
        with mock.patch.object(source, "_get_json", side_effect=fetch):
            newest = collector._collect_run(collector.REPO, "t")
        self.assertEqual(newest["id"], 9003)
        with self.assertRaises(source.AttestationError):
            consumer.verify_completed_proof(
                self.proof, newest, self.artifact, self.pr, self.branch, self.manifest
            )

    def test_unknown_job_provenance_never_falls_back_to_old_green(self):
        for response in (
            {"total_count": 0, "jobs": []},
            {"total_count": 2, "jobs": self.job_payload(9002)["jobs"]},
            {"total_count": 1, "jobs": [{"id": 10002, "name": "other"}]},
            {"total_count": 1, "jobs": self.job_payload(9002)["jobs"] * 2},
        ):
            with self.subTest(response=response), mock.patch.object(
                source, "_get_json", return_value=response
            ):
                with self.assertRaises(source.AttestationError):
                    collector._attestation_job_relevant(collector.REPO, "t", {"id": 9002})

    def test_run_selection_refetches_exact_latest_across_two_events(self):
        old = {**self.run, "id": 9000, "created_at": "2026-10-09T10:00:00Z"}
        def fetch(_repo, route, _token):
            if "event=pull_request_target" in route:
                return {"total_count": 1, "workflow_runs": [old]}
            if "event=push" in route:
                return {"total_count": 1, "workflow_runs": [self.run]}
            if route == "actions/runs/9001/jobs?per_page=100":
                return self.job_payload(9001)
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
            if route == "actions/runs/9002/jobs?per_page=100":
                return self.job_payload(9002, conclusion="failure")
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

    def test_older_run_rerun_attempt_outranks_newer_original_run(self):
        older = {
            **self.run, "id": 8001, "run_attempt": 2,
            "created_at": "2026-10-09T09:00:00Z",
            "run_started_at": "2026-10-09T14:00:00Z",
            "status": "in_progress", "conclusion": None,
        }
        newer_original = {
            **self.run, "id": 9002,
            "created_at": "2026-10-09T12:00:00Z",
            "run_started_at": "2026-10-09T12:00:01Z",
        }
        def fetch(_repo, route, _token):
            if "event=pull_request_target" in route:
                return {"total_count": 2, "workflow_runs": [newer_original, older]}
            if "event=push" in route:
                return {"total_count": 0, "workflow_runs": []}
            if route == "actions/runs/8001/jobs?per_page=100":
                return self.job_payload(8001, status="in_progress")
            if route == "actions/runs/8001":
                return older
            raise AssertionError(route)
        with mock.patch.object(source, "_get_json", side_effect=fetch):
            selected = collector._collect_run(collector.REPO, "t")
        self.assertEqual(selected["id"], 8001)
        self.assertEqual(selected["run_attempt"], 2)

    def test_rerun_without_current_attempt_timestamp_is_ambiguous(self):
        older = {**self.run, "run_attempt": 2}
        with self.assertRaisesRegex(source.AttestationError, "rerun lacks"):
            collector._attempt_order(older)

    def test_paginated_unrelated_runs_do_not_hide_relevant_second_page(self):
        unrelated = [
            {
                **self.run,
                "id": 9200 + i,
                "created_at": "2026-10-09T13:00:00Z",
            } for i in range(100)
        ]
        def fetch(_repo, route, _token):
            if "event=pull_request_target" in route:
                return {
                    "total_count": 101,
                    "workflow_runs": [self.run] if "&page=2" in route else unrelated,
                }
            if "event=push" in route:
                return {"total_count": 0, "workflow_runs": []}
            if route.endswith("/jobs?per_page=100"):
                run_id = int(route.split("/")[2])
                return self.job_payload(
                    run_id, conclusion="success" if run_id == 9001 else "skipped"
                )
            if route == "actions/runs/9001":
                return self.run
            raise AssertionError(route)
        with mock.patch.object(source, "_get_json", side_effect=fetch) as req:
            self.assertEqual(collector._collect_run(collector.REPO, "t")["id"], 9001)
        self.assertTrue(any("&page=2" in x.args[1] for x in req.call_args_list))

    def test_truncated_or_drifting_run_pages_fail_closed(self):
        first_page = [{**self.run, "id": 10000+i} for i in range(100)]
        for second in (
            {"total_count": 101, "workflow_runs": []},
            {"total_count": 102, "workflow_runs": [{**self.run, "id": 20000}]},
            {"total_count": 101, "workflow_runs": [first_page[0]]},
        ):
            def fetch(_repo, route, _token):
                if "&page=2" in route:
                    return second
                return {"total_count": 101, "workflow_runs": first_page}
            with self.subTest(second=second), mock.patch.object(source, "_get_json", side_effect=fetch):
                with self.assertRaises(source.AttestationError):
                    collector._event_runs(collector.REPO, "t", "pull_request_target")

    def test_collector_rejects_new_relevant_run_after_artifact(self):
        later = {**self.run, "id": 9005, "created_at": "2026-10-09T15:00:00Z"}
        with (
            mock.patch.object(
                source, "_get_json",
                side_effect=[self.pr, self.branch, self.pr, self.branch],
            ),
            mock.patch.object(collector, "_collect_run", side_effect=[self.run, later]) as frontier,
            mock.patch.object(collector, "_unique_artifact", return_value=self.artifact),
            mock.patch.object(collector, "_download_exact_proof", return_value=self.proof),
        ):
            with self.assertRaisesRegex(source.AttestationError, "run frontier drifted"):
                collector.check_current_main_owned_proof(collector.REPO, "t", self.manifest)
        self.assertEqual(frontier.call_count, 2)

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
