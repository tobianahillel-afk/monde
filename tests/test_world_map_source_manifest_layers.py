"""Original multi-layer GeoPackage plus other sources on one offline map."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from monde.csv_points import documents_from_manifest
from monde.world import WorldMini
from tests.test_world_geopackage_all_layers import make_source
from tests.test_world_geopackage import AT, CAP

START = "2026-01-01T00:00:00Z"


def sample(folder):
    root = Path(folder)
    database = make_source(root / "survey.gpkg")
    note = root / "notes.geojson"
    note.write_text(json.dumps({
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature", "id": "local-note",
            "geometry": {"type": "Point", "coordinates": [4.3, 50.1]},
            "properties": {"note": "independent report"}
        }]
    }), encoding="utf-8")
    manifest = root / "sources.json"
    data = {"datasets": [
        {"gpkg": database.name, "gpkg_all_layers": True,
         "source_id": "survey", "locator": "dataset://original/survey.gpkg",
         "captured_at": CAP, "valid_from": START},
        {"geojson": note.name, "source_id": "note",
         "locator": "dataset://original/notes.geojson",
         "captured_at": CAP, "valid_from": START}
    ]}
    manifest.write_text(json.dumps(data), encoding="utf-8")
    return manifest, database, note, data


def run_map(*args):
    return subprocess.run(
        [sys.executable, "-m", "monde.map_view", *map(str, args)],
        capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH":
             str(Path(__file__).resolve().parents[1] / "src")}
    )


class WholeGeoPackageManifestTests(unittest.TestCase):
    def test_mixed_sources_render_one_offline_map_without_source_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            manifest, database, note, _ = sample(d)
            before_db, before_note = database.read_bytes(), note.read_bytes()
            output = Path(d) / "combined.html"
            result = run_map("--source-manifest", manifest, "--at", AT,
                             "--known-at", CAP, "--output", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            html = output.read_text(encoding="utf-8")
            self.assertIn('"total_source_features":35', html)
            for expected in ("survey:survey_points", "survey:survey_mixed",
                             "survey:survey_duplicate", "note",
                             "dataset://original/notes.geojson",
                             "monde_gpkg_source_fid", "monde_gpkg_source_layer"):
                self.assertIn(expected, html)
            self.assertNotIn("https://tile.", html)
            self.assertEqual(database.read_bytes(), before_db)
            self.assertEqual(note.read_bytes(), before_note)

    def test_multipart_identity_and_source_evidence_survive_combination(self):
        with tempfile.TemporaryDirectory() as d:
            manifest, _, _, _ = sample(d)
            documents, features = documents_from_manifest(
                manifest, output_path=Path(d) / "map.html")
            self.assertEqual(len(documents), 4)
            self.assertEqual(features, 35)
            world = WorldMini()
            world.append_documents(documents)
            collection = world.export_geojson_bbox([-180, -90, 180, 90], AT, CAP)
            self.assertEqual(len(collection["features"]), 35)
            ids = [f["properties"]["entity"] for f in collection["features"]]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertEqual({f["properties"]["source_id"] for f in collection["features"]},
                             {"survey:survey_points", "survey:survey_mixed",
                              "survey:survey_duplicate", "note"})
            same_fid = [f for f in collection["features"]
                        if f["properties"].get("monde_gpkg_source_fid") == "1"]
            self.assertEqual(len(same_fid), 2)

    def test_invalid_geopackage_layer_fails_atomically(self):
        with tempfile.TemporaryDirectory() as d:
            manifest, database, _, _ = sample(d)
            with sqlite3.connect(database) as conn:
                conn.execute("UPDATE gpkg_geometry_columns SET z=1 "
                             "WHERE table_name='survey_mixed'")
            out = Path(d) / "bad.html"
            result = run_map("--source-manifest", manifest, "--at", AT,
                             "--known-at", CAP, "--output", out)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(out.exists())

    def test_invalid_last_source_fails_atomically(self):
        with tempfile.TemporaryDirectory() as d:
            manifest, _, note, _ = sample(d)
            note.write_text("{broken", encoding="utf-8")
            out = Path(d) / "bad.html"
            result = run_map("--source-manifest", manifest, "--at", AT,
                             "--known-at", CAP, "--output", out)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(out.exists())

    def test_ambiguous_gp_layer_flags_and_foreign_flags_fail(self):
        with tempfile.TemporaryDirectory() as d:
            manifest, _, _, initial = sample(d)
            for mutation in ({"gpkg_layer": "survey_points"},
                             {"gpkg_all_layers": False},
                             {"gpkg_all_layers": "true"},
                             {"gpkg_all_layers": 1},
                             {"gpkg_all_layers": None},
                             {"gpkg_layer": ""}):
                with self.subTest(mutation=mutation):
                    data = json.loads(json.dumps(initial))
                    data["datasets"][0].update(mutation)
                    manifest.write_text(json.dumps(data), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        documents_from_manifest(manifest, output_path=Path(d) / "map.html")
            data = json.loads(json.dumps(initial))
            data["datasets"][1]["gpkg_all_layers"] = True
            manifest.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                documents_from_manifest(manifest, output_path=Path(d) / "map.html")

    def test_existing_explicit_layer_manifest_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            manifest, _, _, data = sample(d)
            data["datasets"][0].pop("gpkg_all_layers")
            data["datasets"][0]["gpkg_layer"] = "survey_points"
            manifest.write_text(json.dumps(data), encoding="utf-8")
            docs, count = documents_from_manifest(
                manifest, output_path=Path(d) / "map.html")
            self.assertEqual(len(docs), 2)
            self.assertGreater(count, 1)
            self.assertLess(count, 35)


if __name__ == "__main__":
    unittest.main()
