from __future__ import annotations

import copy
import io
import json
import zipfile
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import trusted_source_attestor as source
import trusted_source_consumer as consumer


class TrustedCompletedProofTests(unittest.TestCase):
    def setUp(self):
        self.manifest_bytes = (
            Path(source.__file__).resolve().parent / "approved_sources.json"
        ).read_bytes()
        self.count = len(source.validate_manifest(source.load_manifest(
            Path(source.__file__).resolve().parent / "approved_sources.json"
        )))
        self.head = "a" * 40
        self.base = "b" * 40
        self.run = {
            "id": 9001,
            "run_attempt": 1,
            "head_sha": self.base,
            "head_branch": "main",
            "status": "completed",
            "conclusion": "success",
            "event": "pull_request_target",
            "path": consumer.WORKFLOW_PATH,
            "repository": {"full_name": "tobianahillel-afk/monde"},
        }
        self.artifact = {
            "id": 9100,
            "name": "monde-trusted-proof-9001-1",
            "expired": False,
            "size_in_bytes": 400,
            "workflow_run": {"id": 9001},
        }
        self.pr = {
            "number": 2,
            "state": "open",
            "draft": False,
            "head": {"sha": self.head},
            "base": {"sha": self.base, "ref": "main"},
        }
        self.main = {"commit": {"sha": self.base}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "attestation.json"
            with mock.patch.dict(os.environ, {
                "MONDE_ATTEST_PROOF_PATH": str(path),
                "GITHUB_RUN_ID": "9001",
                "GITHUB_RUN_ATTEMPT": "1",
            }):
                source._write_attestation_proof(
                    "tobianahillel-afk/monde", self.head, self.base, self.count
                )
                self.proof_bytes = path.read_bytes()
                with self.assertRaisesRegex(source.AttestationError, "emission failed"):
                    source._write_attestation_proof(
                        "tobianahillel-afk/monde", self.head, self.base, self.count
                    )

    def verify(self, proof=None, run=None, artifact=None, pr=None, base=None,
               manifest_bytes=None):
        return consumer.verify_completed_proof(
            self.proof_bytes if proof is None else proof,
            self.run if run is None else run,
            self.artifact if artifact is None else artifact,
            self.pr if pr is None else pr,
            self.main if base is None else base,
            self.manifest_bytes if manifest_bytes is None else manifest_bytes,
        )

    def test_exact_artifact_archive_decoder_rejects_unsafe_zip_members(self):
        def archive(entries, compression=zipfile.ZIP_DEFLATED):
            output = io.BytesIO()
            with zipfile.ZipFile(output, "w", compression=compression) as bundle:
                for name, payload in entries:
                    bundle.writestr(name, payload)
            return output.getvalue()

        valid = archive([(consumer.PROOF_FILENAME, self.proof_bytes)])
        self.assertEqual(consumer.extract_exact_proof_archive(valid), self.proof_bytes)
        self.assertEqual(
            consumer.verify_completed_archive(
                valid, self.run, self.artifact, self.pr, self.main, self.manifest_bytes
            ),
            (self.head, self.base),
        )
        invalid = [
            b"", b"not a zip", b"x" * (consumer.MAX_ARCHIVE_BYTES + 1),
            archive([]),
            archive([("other.json", self.proof_bytes)]),
            archive([("../" + consumer.PROOF_FILENAME, self.proof_bytes)]),
            archive([(consumer.PROOF_FILENAME, self.proof_bytes), ("extra", b"x")]),
            archive([(consumer.PROOF_FILENAME, b"")]),
            archive([(consumer.PROOF_FILENAME, b"x" * (consumer.MAX_PROOF_BYTES + 1))]),
        ]
        symlink = zipfile.ZipInfo(consumer.PROOF_FILENAME)
        symlink.create_system = 3
        symlink.external_attr = 0o120777 << 16
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as bundle:
            bundle.writestr(symlink, self.proof_bytes)
        invalid.append(output.getvalue())

        stored = bytearray(archive(
            [(consumer.PROOF_FILENAME, self.proof_bytes)], zipfile.ZIP_STORED
        ))
        position = stored.find(self.proof_bytes)
        self.assertGreaterEqual(position, 0)
        stored[position] ^= 1  # CRC mismatch after tampering with stored ZIP bytes.
        invalid.append(bytes(stored))
        for bad in invalid:
            with self.subTest(length=len(bad)), self.assertRaises(source.AttestationError):
                consumer.extract_exact_proof_archive(bad)
        with self.assertRaises(source.AttestationError):
            consumer.extract_exact_proof_archive("not bytes")

    def test_exact_completed_main_run_and_artifact_pass(self):
        self.assertEqual(self.verify(), (self.head, self.base))
        alternate = copy.deepcopy(self.run)
        alternate["event"] = "push"
        alternate["path"] += "@refs/heads/main"
        self.assertEqual(self.verify(run=alternate), (self.head, self.base))

    def test_artifact_selection_is_exact_and_bounded(self):
        self.assertEqual(
            consumer.select_unique_artifact([{"id": 7, "name": "other"}, self.artifact], self.run),
            self.artifact,
        )
        for records in (
            None, [], [self.artifact, copy.deepcopy(self.artifact)],
            [{**self.artifact, "expired": True}],
            [{**self.artifact, "size_in_bytes": 9000}],
            [{**self.artifact, "workflow_run": {"id": 999}}],
            [{**self.artifact, "id": True}],
        ):
            with self.subTest(records=records), self.assertRaises(source.AttestationError):
                consumer.select_unique_artifact(records, self.run)

    def test_stale_main_and_pr_authority_never_pass(self):
        for key, changed in (
            ("head", {"sha": "c" * 40}),
            ("base", {"sha": "c" * 40, "ref": "main"}),
            ("draft", True),
            ("state", "closed"),
            ("number", True),
        ):
            pr = copy.deepcopy(self.pr)
            pr[key] = changed
            with self.subTest(key=key), self.assertRaises(source.AttestationError):
                self.verify(pr=pr)
        with self.assertRaisesRegex(source.AttestationError, "stale"):
            self.verify(base={"commit": {"sha": "c" * 40}})

    def test_failed_pending_wrong_base_and_untrusted_workflows_are_rejected(self):
        for key, bad in (
            ("status", "in_progress"),
            ("conclusion", "failure"),
            ("head_sha", "c" * 40),
            ("head_branch", "candidate"),
            ("path", ".github/workflows/untrusted.yml"),
            ("event", "pull_request"),
            ("id", 9002),
            ("run_attempt", 2),
            ("repository", {"full_name": "attacker/repo"}),
        ):
            run = copy.deepcopy(self.run)
            run[key] = bad
            with self.subTest(key=key), self.assertRaises(source.AttestationError):
                self.verify(run=run)

    def test_run_artifact_mismatch_rejected(self):
        for key, bad in (
            ("name", "monde-trusted-proof-1-1"),
            ("expired", True),
            ("size_in_bytes", 9000),
            ("workflow_run", {"id": 9002}),
        ):
            artifact = copy.deepcopy(self.artifact)
            artifact[key] = bad
            with self.subTest(key=key), self.assertRaises(source.AttestationError):
                self.verify(artifact=artifact)

    def test_proof_tampering_missing_extra_coercive_values_and_duplicate_json_fail(self):
        pristine = json.loads(self.proof_bytes)
        for key, bad in (
            ("candidate_sha", "c" * 40),
            ("base_sha", "c" * 40),
            ("run_id", True),
            ("run_attempt", 0),
            ("pr_number", True),
            ("approved_source_count", self.count - 1),
            ("manifest_sha256", "bad"),
            ("repository", "attacker/repo"),
        ):
            data = copy.deepcopy(pristine)
            data[key] = bad
            with self.subTest(key=key), self.assertRaises(source.AttestationError):
                self.verify(proof=json.dumps(data).encode())
        data = {**pristine, "unapproved": 1}
        with self.assertRaises(source.AttestationError):
            self.verify(proof=json.dumps(data).encode())
        duplicate = self.proof_bytes.rstrip()[:-1] + b',"run_id":9001}'
        with self.assertRaisesRegex(source.AttestationError, "malformed trusted proof"):
            self.verify(proof=duplicate)

    def test_manifest_identity_is_approved_and_exact(self):
        with self.assertRaises(source.AttestationError):
            self.verify(manifest_bytes=self.manifest_bytes + b" ")
        with self.assertRaises(source.AttestationError):
            self.verify(manifest_bytes=b"{}")

    def test_malformed_and_oversized_evidence_fail_closed(self):
        for proof in (b"not json", b"", b" " * (consumer.MAX_PROOF_BYTES + 1)):
            with self.subTest(proof=proof[:8]), self.assertRaises(source.AttestationError):
                self.verify(proof=proof)
        with self.assertRaises(source.AttestationError):
            self.verify(run=[])
        with self.assertRaises(source.AttestationError):
            self.verify(pr=[])

    def test_writer_rejects_non_numeric_run_and_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "proof.json"
            for run_id, attempt, count in (
                ("true", "1", self.count),
                ("123", "0", self.count),
                ("12", "1", True),
                ("12", "1", 0),
            ):
                with self.subTest(run_id=run_id, attempt=attempt, count=count):
                    with mock.patch.dict(os.environ, {
                        "MONDE_ATTEST_PROOF_PATH": str(path),
                        "GITHUB_RUN_ID": run_id,
                        "GITHUB_RUN_ATTEMPT": attempt,
                    }):
                        with self.assertRaisesRegex(source.AttestationError, "identity"):
                            source._write_attestation_proof(
                                "tobianahillel-afk/monde", self.head, self.base, count
                            )
                    self.assertFalse(path.exists())

    def test_workflow_uploads_only_after_main_owned_attestation(self):
        workflow = (
            Path(source.__file__).resolve().parents[1] / "workflows" /
            "monde-trusted-source.yml"
        ).read_text(encoding="utf-8")
        trusted = workflow.split("  trusted-attestation:", 1)[1]
        self.assertIn("MONDE_ATTEST_PROOF_PATH: ${{ runner.temp }}/monde-trusted-source-proof.json", trusted)
        self.assertIn("uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a", trusted)
        self.assertIn("if-no-files-found: error", trusted)
        self.assertLess(
            trusted.index("run: python3 .github/trusted/trusted_source_attestor.py"),
            trusted.index("Publish completed-run evidence"),
        )


if __name__ == "__main__":
    unittest.main()
