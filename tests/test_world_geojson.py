"""Real GeoJSON Point source import and bitemporal integration tests."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from monde.geojson import to_document
from monde.world import WorldMini

ROOT = Path(__file__).resolve().parents[1]
POINTS = WorldMini.load_document(str(ROOT / "examples/monde-mini-points.geojson"))
BASE = ROOT / "examples/monde-mini.json"
CAPTURED = "2026-01-10T10:00:00Z"
VALID = "2026-01-01T00:00:00Z"
OPTIONS = {
    "source_id": "example-map",
    "locator": "fixture://example-map/places",
    "captured_at": CAPTURED,
    "source_event_at": "2026-01-09T12:00:00Z",
    "valid_from": VALID,
}
AT = "2026-01-02T00:00:00Z"


class GeoJsonImportTests(unittest.TestCase):
    def to_doc(self, data=None, **changes):
        return to_document(copy.deepcopy(POINTS if data is None else data),
                           **{**OPTIONS, **changes})

    def model(self):
        return WorldMini.from_document(WorldMini.load_document(str(BASE)))

    def test_import_creates_source_attributed_geo_points_and_properties(self):
        doc = self.to_doc()
        self.assertEqual(len(doc["evidence"]), 2)
        self.assertEqual(len(doc["assertions"]), 6)
        world = self.model()
        counts = world.append_document(doc)
        self.assertEqual(counts, {"added_evidence": 2, "added_assertions": 6})
        result = world.query("place-001", "geo_point", AT, CAPTURED)
        self.assertEqual(result["status"], "REPORTED")
        self.assertEqual(len(result["reports"]), 1)
        report = result["reports"][0]
        self.assertEqual(report["value"], {
            "type": "Point", "coordinates": [2.3522, 48.8566]})
        self.assertEqual(report["source_id"], "example-map")
        self.assertEqual(report["locator"], OPTIONS["locator"])
        self.assertEqual(report["captured_at"], CAPTURED)
        self.assertEqual(report["source_event_at"], OPTIONS["source_event_at"])
        self.assertEqual(world.query("place-002", "category", AT, CAPTURED)
                         ["reports"][0]["value"], "landmark")

    def test_knowledge_cutoff_does_not_reveal_future_geojson(self):
        world = self.model()
        world.append_document(self.to_doc())
        self.assertEqual(world.query("place-001", "geo_point", AT,
                         "2026-01-10T09:59:59Z")["status"], "UNKNOWN")
        self.assertEqual(world.query("place-001", "geo_point",
                         "2025-12-31T23:59:59Z", CAPTURED)["status"], "UNKNOWN")

    def test_stable_ids_make_identical_replay_idempotent_across_restarts(self):
        first = self.to_doc()
        self.assertEqual(first, self.to_doc())
        world = self.model()
        world.append_document(first)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "saved.json"
            world.save(path)
            reopened = WorldMini.read(path)
            before = reopened.export()
            self.assertEqual(reopened.append_document(self.to_doc()),
                             {"added_evidence": 0, "added_assertions": 0})
            self.assertEqual(reopened.export(), before)

    def test_incompatible_reuse_of_source_capture_and_feature_id_is_rejected(self):
        world = self.model()
        world.append_document(self.to_doc())
        tampered = copy.deepcopy(POINTS)
        tampered["features"][0]["geometry"]["coordinates"][0] = 3.0
        before = world.export()
        with self.assertRaisesRegex(ValueError, "collision"):
            world.append_document(self.to_doc(tampered))
        self.assertEqual(world.export(), before)

    def test_rejects_invalid_geojson_and_coordinates(self):
        invalid = []
        absent_id = copy.deepcopy(POINTS)
        del absent_id["features"][0]["id"]
        invalid.append(absent_id)
        duplicates = copy.deepcopy(POINTS)
        duplicates["features"][1]["id"] = "place-001"
        invalid.append(duplicates)
        polygon = copy.deepcopy(POINTS)
        polygon["features"][0]["geometry"] = {
            "type": "Polygon", "coordinates": []}
        invalid.append(polygon)
        bad_points = [[2.0], [181, 48], [2, -91], [True, 3],
                      ["2", 48], [float("nan"), 48], [2, 48, 1]]
        for point in bad_points:
            bad = copy.deepcopy(POINTS)
            bad["features"][0]["geometry"]["coordinates"] = point
            invalid.append(bad)
        for data in invalid:
            with self.subTest(data=data["features"][0].get("id")):
                with self.assertRaises(ValueError):
                    self.to_doc(data)

    def test_rejects_implicit_or_implausible_provenance(self):
        for change in (
            {"source_id": ""}, {"locator": ""},
            {"captured_at": "2026-01-10"},
            {"valid_from": "2026-01-01"},
            {"source_event_at": "2026-01-11T00:00:00Z"},
            {"valid_to": "2025-12-31T00:00:00Z"},
        ):
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    self.to_doc(**change)

    def test_does_not_infer_corrections_or_verified_physical_events(self):
        doc = self.to_doc()
        self.assertTrue(all(a["kind"] == "CLAIM" and
                            a["supersedes"] is None for a in doc["assertions"]))
        world = self.model()
        world.append_document(doc)
        self.assertEqual(len(world.query("place-001", "geo_point", AT, CAPTURED)
                             ["reports"]), 1)
        # A distinct source report is preserved rather than replacing another.
        world.append_document(self.to_doc(source_id="other-map"))
        reports = world.query("place-001", "geo_point", AT, CAPTURED)["reports"]
        self.assertEqual({r["source_id"] for r in reports},
                         {"example-map", "other-map"})

    def test_rejected_import_leaves_snapshot_identical(self):
        world = self.model()
        before = world.export()
        bad = copy.deepcopy(POINTS)
        bad["features"][1]["properties"]["geo_point"] = [0, 0]
        with self.assertRaisesRegex(ValueError, "geo_point"):
            world.append_document(self.to_doc(bad))
        self.assertEqual(world.export(), before)

    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "monde.world", *args],
                              env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
                              capture_output=True, text=True)

    def test_real_cli_save_reopen_query_and_invalid_output_safety(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "world.json"
            command = (
                "--fixture", str(BASE), "--ingest-geojson",
                str(ROOT / "examples/monde-mini-points.geojson"),
                "--source-id", OPTIONS["source_id"],
                "--source-locator", OPTIONS["locator"],
                "--captured-at", CAPTURED, "--valid-from", VALID,
                "--source-event-at", OPTIONS["source_event_at"],
                "--state-out", str(destination))
            saved = self.cli(*command)
            self.assertEqual(saved.returncode, 0, saved.stderr)
            self.assertEqual(json.loads(saved.stdout)["features"], 2)
            self.assertEqual(json.loads(saved.stdout)["added_assertions"], 6)
            query = self.cli("--fixture", str(destination), "--entity", "place-001",
                             "--attribute", "geo_point", "--at", AT,
                             "--known-at", CAPTURED)
            self.assertEqual(query.returncode, 0, query.stderr)
            self.assertEqual(json.loads(query.stdout)["reports"][0]["value"]
                             ["coordinates"], [2.3522, 48.8566])
            self.assertNotEqual(self.cli(*command).returncode, 0)  # no implicit overwrite
            before = destination.read_bytes()
            bad_file = Path(folder) / "invalid.geojson"
            bad = copy.deepcopy(POINTS)
            bad["features"][1]["geometry"] = None
            bad_file.write_text(json.dumps(bad), encoding="utf-8")
            invalid = list(command)
            invalid[3] = str(bad_file)
            invalid.append("--replace-state")
            attempt = self.cli(*invalid)
            self.assertNotEqual(attempt.returncode, 0)
            self.assertEqual(destination.read_bytes(), before)

    def test_geojson_metadata_cannot_be_used_with_query_or_document_import(self):
        args = ("--fixture", str(BASE), "--entity", "building-001",
                "--attribute", "floors", "--at", AT, "--known-at", CAPTURED,
                "--source-id", "unexpected")
        result = self.cli(*args)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("GeoJSON", result.stderr)

if __name__ == "__main__":
    unittest.main()
