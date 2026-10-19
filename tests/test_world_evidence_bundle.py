"""Evidence-bundle offline verifier tests: real ZIP content and CLI execution."""
import io
import json
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

from monde.evidence_bundle import BundleVerificationError, SCHEMA, compare_bundles, verify_bundle


def fixture():
    matrix = {"source_a": "survey-a", "source_b": "survey-b",
              "axis": "knowledge", "cutoffs": {"at": "2026-01-05T00:00:00Z"},
              "total_entities": 0, "entities": []}
    def encode(obj):
        return (json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n").encode()
    docs = {
        "matrix.json": encode(matrix),
        "matrix.csv": b"entity,source_a,source_b\n",
        "index.html": b'<!doctype html><title>Original evidence</title>',
        "original-points.geojson": encode({"type": "FeatureCollection", "features": []}),
        "analytical-witnesses.geojson": encode({"type": "FeatureCollection", "features": []}),
        "analytical-witnesses.csv": b"source_a,source_b\n",
    }
    manifest = {
        "schema": SCHEMA, "source_a": matrix["source_a"], "source_b": matrix["source_b"],
        "axis": matrix["axis"], "cutoffs": matrix["cutoffs"],
        "original_observations_only": ["original-points.geojson"],
        "analytical_not_original": [
            "analytical-witnesses.geojson", "analytical-witnesses.csv"],
        "files": {n: {"bytes": len(raw), "sha256": sha256(raw).hexdigest()}
                  for n, raw in docs.items()},
    }
    docs["manifest.json"] = encode(manifest)
    return docs


def pack(docs, compression=ZIP_STORED):
    buf = io.BytesIO()
    with ZipFile(buf, "w", compression=compression) as z:
        for name, blob in sorted(docs.items()):
            z.writestr(name, blob)
    return buf.getvalue()


class TestOfflineEvidenceBundle(unittest.TestCase):
    def test_real_stored_zip_is_verified_without_authenticity_claim(self):
        result = verify_bundle(pack(fixture()))
        self.assertTrue(result["valid"])
        self.assertEqual(result["verified_files"], 6)
        self.assertEqual(result["source_a"], "survey-a")
        self.assertEqual(result["authenticity"], "NOT_ATTESTED")

    def test_changed_evidence_rejected(self):
        docs = fixture()
        docs["matrix.csv"] += b"unmanifested mutation\n"
        with self.assertRaisesRegex(BundleVerificationError, "checksum mismatch"):
            verify_bundle(pack(docs))

    def test_missing_added_and_traversal_members_rejected(self):
        docs = fixture()
        for altered in [
            {k: v for k, v in docs.items() if k != "matrix.json"},
            {**docs, "extraneous.exe": b"x"},
            {**docs, "../outside": b"x"},
        ]:
            with self.subTest(files=sorted(altered)):
                with self.assertRaises(BundleVerificationError):
                    verify_bundle(pack(altered))

    def test_duplicate_member_rejected(self):
        docs = fixture()
        buf = io.BytesIO()
        with ZipFile(buf, "w") as z:
            for name, data in docs.items():
                z.writestr(name, data)
            # Avoid accidental overwrite: ZIP format explicitly permits duplicates.
            z.writestr("matrix.csv", b"duplicate")
        with self.assertRaisesRegex(BundleVerificationError, "duplicate"):
            verify_bundle(buf.getvalue())

    def test_compressed_and_unreadable_zip_rejected(self):
        with self.assertRaisesRegex(BundleVerificationError, "unsupported"):
            verify_bundle(pack(fixture(), ZIP_DEFLATED))
        with self.assertRaises(BundleVerificationError):
            verify_bundle(b"not an archive")

    def test_manifest_cannot_reclassify_analytical_output_as_original(self):
        docs = fixture()
        manifest = json.loads(docs["manifest.json"])
        manifest["original_observations_only"] = ["analytical-witnesses.geojson"]
        docs["manifest.json"] = json.dumps(manifest).encode()
        with self.assertRaisesRegex(BundleVerificationError, "roles mismatch"):
            verify_bundle(pack(docs))

    def test_metadata_mismatch_detected_with_valid_updated_sha256(self):
        docs = fixture()
        matrix = json.loads(docs["matrix.json"])
        matrix["source_a"] = "different-origin"
        docs["matrix.json"] = json.dumps(matrix).encode()
        manifest = json.loads(docs["manifest.json"])
        manifest["files"]["matrix.json"] = {
            "bytes": len(docs["matrix.json"]),
            "sha256": sha256(docs["matrix.json"]).hexdigest(),
        }
        docs["manifest.json"] = json.dumps(manifest).encode()
        with self.assertRaisesRegex(BundleVerificationError, "manifest/matrix mismatch"):
            verify_bundle(pack(docs))

    def test_derived_feature_cannot_pose_as_original_point(self):
        docs = fixture()
        payload = {"type": "FeatureCollection", "features": [{
            "type": "Feature", "geometry": {"type": "Point", "coordinates": [2, 48]},
            "properties": {
                "monde_geometry_role": "ANALYTICAL_REPORTER_GAP_WITNESS",
                "monde_original_observation": False,
            }}]}
        docs["original-points.geojson"] = json.dumps(payload).encode()
        manifest = json.loads(docs["manifest.json"])
        manifest["files"]["original-points.geojson"] = {
            "bytes": len(docs["original-points.geojson"]),
            "sha256": sha256(docs["original-points.geojson"]).hexdigest(),
        }
        docs["manifest.json"] = json.dumps(manifest).encode()
        with self.assertRaisesRegex(BundleVerificationError, "labeled original"):
            verify_bundle(pack(docs))

    def test_cli_uses_exit_codes_and_does_not_modify_zip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.zip"
            before = pack(fixture())
            path.write_bytes(before)
            ok = subprocess.run(
                [sys.executable, "-m", "monde.evidence_bundle", str(path)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(ok.returncode, 0, ok.stderr)
            self.assertTrue(json.loads(ok.stdout)["valid"])
            self.assertEqual(path.read_bytes(), before)
            path.write_bytes(b"invalid archive")
            bad = subprocess.run(
                [sys.executable, "-m", "monde.evidence_bundle", str(path)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(bad.returncode, 1)
            self.assertFalse(json.loads(bad.stdout)["valid"])


class TestOfflineBundleComparison(unittest.TestCase):
    def test_identical_exports_have_no_report_or_feature_changes(self):
        zipped = pack(fixture())
        compared = compare_bundles(zipped, zipped)
        self.assertTrue(compared["valid"])
        self.assertEqual(compared["entities_added"], [])
        self.assertEqual(compared["entities_changed"], [])
        self.assertEqual(compared["original_points_added"], 0)
        self.assertEqual(compared["original_points_removed"], 0)
        self.assertEqual(compared["changed_files"], [])
        self.assertEqual(compared["authenticity"], "NOT_ATTESTED")

    def test_original_evidence_addition_distinct_from_derived_witness(self):
        old = fixture()
        latest = fixture()
        matrix = json.loads(latest["matrix.json"])
        matrix["entities"].append({"entity": "A", "earlier": {"status": "UNKNOWN"}})
        matrix["total_entities"] = 1
        feature = {"type": "Feature", "geometry": {"type": "Point",
                   "coordinates": [2.0, 48.0]},
                   "properties": {"entity": "A", "source_id": "survey-a",
                                  "assertion_id": "report-1",
                                  "evidence_id": "doc-1",
                                  "monde_original_observation": True}}
        points = {"type": "FeatureCollection", "features": [feature]}
        latest["matrix.json"] = json.dumps(matrix).encode()
        latest["original-points.geojson"] = json.dumps(points).encode()
        manifest = json.loads(latest["manifest.json"])
        for name in ("matrix.json", "original-points.geojson"):
            raw = latest[name]
            manifest["files"][name] = {"bytes": len(raw),
                                        "sha256": sha256(raw).hexdigest()}
        latest["manifest.json"] = json.dumps(manifest).encode()
        outcome = compare_bundles(pack(old), pack(latest))
        self.assertEqual(outcome["entities_added"], ["A"])
        self.assertEqual(outcome["original_points_added"], 1)
        self.assertEqual(outcome["original_points_removed"], 0)
        self.assertEqual(outcome["changed_files"],
                         ["matrix.json", "original-points.geojson"])
        self.assertEqual(outcome["interpretation"],
                         "EXPORTED_EVIDENCE_DIFFERENCE_NOT_WORLD_CHANGE")

    def test_cutoff_change_reported_without_interpreting_world_change(self):
        original = fixture()
        other = fixture()
        manifest = json.loads(other["manifest.json"])
        matrix = json.loads(other["matrix.json"])
        matrix["cutoffs"]["at"] = "2026-02-05T00:00:00Z"
        manifest["cutoffs"] = matrix["cutoffs"]
        other["matrix.json"] = json.dumps(matrix).encode()
        manifest["files"]["matrix.json"] = {
            "bytes": len(other["matrix.json"]),
            "sha256": sha256(other["matrix.json"]).hexdigest()}
        other["manifest.json"] = json.dumps(manifest).encode()
        result = compare_bundles(pack(original), pack(other))
        self.assertTrue(result["selection_or_cutoffs_differ"])
        self.assertEqual(result["entities_changed"], [])

    def test_mismatched_sources_and_broken_hash_never_compare(self):
        before = fixture()
        unrelated = fixture()
        m = json.loads(unrelated["manifest.json"])
        x = json.loads(unrelated["matrix.json"])
        m["source_b"] = x["source_b"] = "other-reporter"
        unrelated["matrix.json"] = json.dumps(x).encode()
        m["files"]["matrix.json"] = {
            "bytes": len(unrelated["matrix.json"]),
            "sha256": sha256(unrelated["matrix.json"]).hexdigest()}
        unrelated["manifest.json"] = json.dumps(m).encode()
        with self.assertRaisesRegex(BundleVerificationError, "incompatible"):
            compare_bundles(pack(before), pack(unrelated))
        broken = fixture()
        broken["index.html"] = b"changed but not rehashed"
        with self.assertRaisesRegex(BundleVerificationError, "checksum mismatch"):
            compare_bundles(pack(before), pack(broken))

    def test_compare_cli_reports_json_and_preserves_both_archives(self):
        with tempfile.TemporaryDirectory() as folder:
            original, other = (Path(folder) / name for name in ("a.zip", "b.zip"))
            data = pack(fixture())
            original.write_bytes(data)
            other.write_bytes(data)
            result = subprocess.run(
                [sys.executable, "-m", "monde.evidence_bundle",
                 str(original), "--compare", str(other)],
                capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)["valid"])
            self.assertEqual(original.read_bytes(), data)
            self.assertEqual(other.read_bytes(), data)


if __name__ == "__main__":
    unittest.main()
