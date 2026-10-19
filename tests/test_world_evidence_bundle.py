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

    def test_selection_change_is_visible_even_if_entities_are_unchanged(self):
        earlier = fixture()
        later = fixture()
        manifest = json.loads(later["manifest.json"])
        manifest["selection"] = {"gap_crossing_km": "1"}
        later["manifest.json"] = json.dumps(manifest).encode()
        result = compare_bundles(pack(earlier), pack(later))
        self.assertTrue(result["selection_or_cutoffs_differ"])
        self.assertEqual(result["entities_changed"], [])
        self.assertEqual(result["changed_files"], [])

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


class TestOfflineEntityInspection(unittest.TestCase):
    """Compare verifiable exact source reports for one entity, not inferred movement."""

    @staticmethod
    def _archive(rows, features):
        docs = fixture()
        matrix = json.loads(docs["matrix.json"])
        matrix["entities"] = rows
        matrix["total_entities"] = len(rows)
        docs["matrix.json"] = json.dumps(matrix, sort_keys=True).encode()
        docs["original-points.geojson"] = json.dumps({
            "type": "FeatureCollection", "features": features
        }, sort_keys=True).encode()
        manifest = json.loads(docs["manifest.json"])
        for name in ("matrix.json", "original-points.geojson"):
            payload = docs[name]
            manifest["files"][name] = {
                "bytes": len(payload), "sha256": sha256(payload).hexdigest()
            }
        docs["manifest.json"] = json.dumps(manifest, sort_keys=True).encode()
        return pack(docs)

    @staticmethod
    def _report(entity, source, assertion):
        return {"type": "Feature", "geometry": {
            "type": "Point", "coordinates": [2.3, 48.2]
        }, "properties": {"entity": entity, "source_id": source,
                          "assertion_id": assertion, "evidence_id": "doc-" + assertion,
                          "monde_original_observation": True}}

    def test_original_assertion_counts_and_matrix_deltas_for_one_entity(self):
        old = self._report("A", "survey-a", "original-1")
        new = self._report("A", "survey-b", "original-2")
        unrelated = self._report("B", "survey-a", "unrelated")
        before = self._archive([{"entity": "A", "reporting_transition": "UNKNOWN"}],
                               [old, old, unrelated])
        after = self._archive([{"entity": "A", "reporting_transition": "CHANGED"}],
                              [old, new, unrelated])
        result = compare_bundles(before, after, entity="A")
        detail = result["entity_inspection"]
        self.assertEqual(detail["before_matrix_row"]["reporting_transition"], "UNKNOWN")
        self.assertEqual(detail["after_matrix_row"]["reporting_transition"], "CHANGED")
        self.assertEqual(detail["original_points_before_count"], 2)
        self.assertEqual(detail["original_points_after_count"], 2)
        self.assertEqual(detail["original_points_unchanged_count"], 1)
        self.assertEqual(detail["original_points_removed"][0]["count"], 1)
        self.assertEqual(detail["original_points_removed"][0]["feature"]["properties"]
                         ["assertion_id"], "original-1")
        self.assertEqual(detail["original_points_added"][0]["feature"]["properties"]
                         ["assertion_id"], "original-2")
        self.assertEqual(result["original_points_added"], 1)
        self.assertEqual(result["original_points_removed"], 1)
        self.assertEqual(result["authenticity"], "NOT_ATTESTED")
        self.assertEqual(result["interpretation"],
                         "EXPORTED_EVIDENCE_DIFFERENCE_NOT_WORLD_CHANGE")

    def test_selected_entity_can_disappear_and_unrelated_originals_are_not_leaked(self):
        p = self._report("A", "survey-a", "gone")
        b = self._report("B", "survey-b", "stay")
        before = self._archive([{"entity": "A", "earlier": {"status": "PRESENT"}}],
                               [p, b])
        after = self._archive([], [b])
        detail = compare_bundles(before, after, entity="A")["entity_inspection"]
        self.assertEqual(detail["before_matrix_row"]["entity"], "A")
        self.assertIsNone(detail["after_matrix_row"])
        self.assertEqual(detail["original_points_removed"][0]["feature"]
                         ["properties"]["entity"], "A")
        self.assertEqual(detail["original_points_added"], [])
        self.assertNotIn('"unrelated"', json.dumps(detail))

    def test_absent_and_invalid_selectors_do_not_invent_evidence(self):
        zipped = self._archive([], [])
        for bad in ("", "A\nB", "A" * 513):
            with self.subTest(selector=repr(bad)):
                with self.assertRaisesRegex(BundleVerificationError,
                                            "invalid entity selector"):
                    compare_bundles(zipped, zipped, entity=bad)
        with self.assertRaisesRegex(BundleVerificationError, "absent"):
            compare_bundles(zipped, zipped, entity="missing")

    def test_actual_offline_cli_reports_entity_provenance_and_preserves_archives(self):
        source = self._report("A", "survey-a", "a-1")
        before = self._archive([], [])
        after = self._archive([{"entity": "A", "later": {"status": "OBSERVED"}}],
                              [source])
        with tempfile.TemporaryDirectory() as folder:
            old = Path(folder) / "before.zip"
            new = Path(folder) / "after.zip"
            old.write_bytes(before)
            new.write_bytes(after)
            cmd = [sys.executable, "-m", "monde.evidence_bundle",
                   str(old), "--compare", str(new), "--entity", "A"]
            outcome = subprocess.run(cmd, text=True, capture_output=True,
                                     check=False)
            self.assertEqual(outcome.returncode, 0, outcome.stderr)
            body = json.loads(outcome.stdout)
            self.assertEqual(body["entity_inspection"]["original_points_added"]
                             [0]["feature"]["properties"]["evidence_id"], "doc-a-1")
            self.assertEqual(body["authenticity"], "NOT_ATTESTED")
            self.assertEqual(old.read_bytes(), before)
            self.assertEqual(new.read_bytes(), after)
            no_compare = subprocess.run(
                [sys.executable, "-m", "monde.evidence_bundle", str(old),
                 "--entity", "A"], text=True, capture_output=True, check=False)
            self.assertEqual(no_compare.returncode, 2)
            self.assertIn("--entity requires --compare", no_compare.stderr)

    def test_batch_inspection_detects_matrix_and_original_only_changes(self):
        point_a = self._report("A", "survey-a", "original-1")
        point_a_new = self._report("A", "survey-b", "original-2")
        point_c = self._report("C", "survey-a", "source-only-before")
        point_c_new = self._report("C", "survey-a", "source-only-after")
        unchanged = self._report("D", "survey-b", "unchanged")
        before = self._archive(
            [{"entity": "A", "status": "before"}, {"entity": "B", "status": "removed"}],
            [point_a, point_a, point_c, unchanged])
        after = self._archive(
            [{"entity": "A", "status": "after"}, {"entity": "E", "status": "added"}],
            [point_a, point_a_new, point_c_new, unchanged])
        result = compare_bundles(before, after, inspect_changed=True)
        found = {row["entity"]: row for row in result["changed_entity_inspections"]}
        self.assertEqual(sorted(found), ["A", "B", "C", "E"])
        self.assertEqual(found["A"]["original_points_removed"][0]["count"], 1)
        self.assertEqual(found["A"]["original_points_added"][0]["feature"]
                         ["properties"]["assertion_id"], "original-2")
        self.assertEqual(found["A"]["original_points_unchanged_count"], 1)
        self.assertIsNone(found["B"]["after_matrix_row"])
        self.assertIsNone(found["E"]["before_matrix_row"])
        self.assertIsNone(found["C"]["before_matrix_row"])
        self.assertEqual(found["C"]["original_points_added"][0]["feature"]
                         ["properties"]["assertion_id"], "source-only-after")
        self.assertNotIn('"unchanged"', json.dumps(found))
        self.assertEqual(result["authenticity"], "NOT_ATTESTED")
        self.assertEqual(result["interpretation"],
                         "EXPORTED_EVIDENCE_DIFFERENCE_NOT_WORLD_CHANGE")

    def test_batch_inspection_of_identical_verified_archives_is_empty(self):
        data = self._archive([], [])
        result = compare_bundles(data, data, inspect_changed=True)
        self.assertEqual(result["changed_entity_inspections"], [])
        self.assertNotIn("entity_inspection", result)

    def test_batch_inspection_rejects_unattributable_original_point(self):
        report = self._report("A", "survey-a", "missing-entity")
        report["properties"].pop("entity")
        packed = self._archive([], [report])
        with self.assertRaisesRegex(BundleVerificationError, "valid entity"):
            compare_bundles(packed, packed, inspect_changed=True)

    def test_batch_inspection_cli_json_and_immutable_archives(self):
        previous = self._archive([], [])
        latest = self._archive([{"entity": "A", "status": "added"}],
                               [self._report("A", "survey-a", "new-assertion")])
        with tempfile.TemporaryDirectory() as folder:
            before = Path(folder) / "before.zip"
            after = Path(folder) / "after.zip"
            before.write_bytes(previous)
            after.write_bytes(latest)
            cmd = [sys.executable, "-m", "monde.evidence_bundle",
                   str(before), "--compare", str(after), "--inspect-changed"]
            run = subprocess.run(cmd, text=True, capture_output=True, check=False)
            self.assertEqual(run.returncode, 0, run.stderr)
            body = json.loads(run.stdout)
            self.assertEqual([r["entity"] for r in body["changed_entity_inspections"]],
                             ["A"])
            self.assertEqual(body["changed_entity_inspections"][0]
                             ["original_points_added"][0]["feature"]
                             ["properties"]["evidence_id"], "doc-new-assertion")
            self.assertEqual(before.read_bytes(), previous)
            self.assertEqual(after.read_bytes(), latest)
            for tail in (["--inspect-changed"],
                         ["--compare", str(after), "--entity", "A",
                          "--inspect-changed"]):
                invalid = subprocess.run(
                    [sys.executable, "-m", "monde.evidence_bundle", str(before), *tail],
                    text=True, capture_output=True, check=False)
                self.assertEqual(invalid.returncode, 2)


if __name__ == "__main__":
    unittest.main()
