"""Real mixed-geometry GeoPackage -> WorldMini evidence -> offline map."""
import json
import os
from pathlib import Path
import sqlite3
import struct
import subprocess
import sys
import tempfile
import unittest

from monde.geopackage_points import to_geojson
from monde.geojson import to_document
from monde.world import WorldMini
from tests.test_world_geopackage import AT, CAP, build, point
from tests.test_world_geopackage_lines import line
from tests.test_world_geopackage_polygons import polygon, OUTER, INNER
from tests.test_world_geopackage_multipoints import multipoint, POINTS
from tests.test_world_geopackage_multilines import multiline, LINES
from tests.test_world_geopackage_multipolygons import multipolygon, POLYGONS


def mixed_db(path):
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE survey_mixed (
                fid INTEGER PRIMARY KEY, geom BLOB NOT NULL, name TEXT);
            INSERT INTO gpkg_contents VALUES
                ('survey_mixed','features','Mixed original geometry',4326);
            INSERT INTO gpkg_geometry_columns VALUES
                ('survey_mixed','geom','GEOMETRY',4326,0,0);
        """)
        db.executemany("INSERT INTO survey_mixed VALUES (?,?,?)", [
            (11, point(2.35, 48.85, envelope=True), "Site"),
            (12, line([[2.35, 48.85], [2.36, 48.86]]), "Route"),
            (13, polygon([OUTER, INNER], envelope=True), "Boundary"),
            (14, multipoint(POINTS, envelope=True), "Observations"),
            (15, multiline(LINES, envelope=True), "Independent traces"),
            (16, multipolygon(POLYGONS, envelope=True), "Multipart areas"),
        ])
    return path


class MixedGeoPackageTests(unittest.TestCase):
    def args(self, path):
        return ("--gpkg", path, "--gpkg-layer", "survey_mixed",
                "--source-id", "original-mixed",
                "--source-locator", "dataset://original/mixed.gpkg",
                "--captured-at", CAP, "--valid-from", "2026-01-01T00:00:00Z",
                "--at", AT, "--known-at", CAP)

    def cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "monde.map_view", *map(str, args)],
            text=True, capture_output=True,
            env={**os.environ,
                 "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")})

    def test_all_six_wkb_kinds_keep_source_row_and_component_identity(self):
        with tempfile.TemporaryDirectory() as d:
            path = mixed_db(build(Path(d) / "observations.gpkg"))
            original = path.read_bytes()
            features = to_geojson(path, layer="survey_mixed")["features"]
            self.assertEqual(len(features), 31)
            self.assertEqual(features[0]["id"], "11")
            self.assertEqual(features[1]["id"], "gpkg-line-survey_mixed-12-0")
            self.assertEqual(features[3]["id"], "gpkg-polygon-survey_mixed-13-0-0")
            self.assertEqual(features[11]["id"], "gpkg-multipoint-survey_mixed-14-0")
            self.assertEqual(features[14]["id"], "gpkg-multiline-survey_mixed-15-0-0")
            self.assertEqual(features[19]["id"], "gpkg-multipolygon-survey_mixed-16-0-0-0")
            self.assertEqual({f["properties"]["name"] for f in features},
                             {"Site", "Route", "Boundary", "Observations",
                              "Independent traces", "Multipart areas"})
            self.assertEqual(path.read_bytes(), original)

    def test_world_model_preserves_bitemporal_evidence_and_member_separation(self):
        with tempfile.TemporaryDirectory() as d:
            path = mixed_db(build(Path(d) / "source.gpkg"))
            doc = to_document(to_geojson(path, layer="survey_mixed"),
                              source_id="survey", locator="dataset://survey/mixed.gpkg",
                              captured_at=CAP, valid_from="2026-01-01T00:00:00Z")
            world = WorldMini.from_document(doc)
            exported = world.export_geojson_bbox([-180, -90, 180, 90], AT, CAP)
            self.assertEqual(len(exported["features"]), 31)
            self.assertEqual({x["properties"]["source_id"] for x in exported["features"]},
                             {"survey"})
            self.assertEqual({x["properties"]["monde_gpkg_trace"]["kind"]
                              for x in exported["features"]
                              if "monde_gpkg_trace" in x["properties"]},
                             {"LineString", "Polygon", "MultiPoint",
                              "MultiLineString", "MultiPolygon"})
            self.assertEqual(sum(x["properties"].get("monde_gpkg_trace", {}).get("kind")
                                 == "MultiPoint" for x in exported["features"]), 3)

    def test_cli_and_manifest_render_real_offline_map_without_network(self):
        with tempfile.TemporaryDirectory() as d:
            path = mixed_db(build(Path(d) / "survey.gpkg"))
            html = Path(d) / "direct.html"
            done = self.cli(*self.args(path), "--output", html)
            self.assertEqual(done.returncode, 0, done.stderr)
            page = html.read_text(encoding="utf-8")
            self.assertIn('"total_source_features":31', page)
            self.assertIn("GPKG_1_3_MULTIPOLYGON_RING_POINT", page)
            self.assertIn("GPKG_1_3_MULTIPOINT_POINT", page)
            self.assertIn("GPKG_1_3_LINESTRING_POINT", page)
            self.assertNotIn("https://tile.", page)
            manifest = Path(d) / "manifest.json"
            manifest.write_text(json.dumps({"datasets": [{
                "gpkg": path.name, "gpkg_layer": "survey_mixed",
                "source_id": "survey", "locator": "dataset://survey/mixed.gpkg",
                "captured_at": CAP, "valid_from": "2026-01-01T00:00:00Z"
            }]}), encoding="utf-8")
            exported = Path(d) / "manifest.html"
            run = self.cli("--source-manifest", manifest,
                           "--at", AT, "--known-at", CAP, "--output", exported)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn('"total_source_features":31',
                          exported.read_text(encoding="utf-8"))

    def test_bad_wkb_crs_and_geometry_subtypes_fail_without_partial_output(self):
        with tempfile.TemporaryDirectory() as d:
            path = mixed_db(build(Path(d) / "source.gpkg"))
            valid = point(2.35, 48.85)
            bad_type = valid[:9] + struct.pack("<I", 7) + valid[13:]
            bad_3d = valid[:9] + struct.pack("<I", 1001) + valid[13:]
            malformed = [b"bad", valid[:-1], valid + b"trailing",
                         point(2.35, 48.85, srid=9999), bad_type, bad_3d,
                         point(181, 48.85), point(float("nan"), 48.85)]
            for i, blob in enumerate(malformed):
                with self.subTest(case=i):
                    with sqlite3.connect(path) as db:
                        db.execute("UPDATE survey_mixed SET geom=? WHERE fid=11",
                                   (blob,))
                    with self.assertRaises(ValueError):
                        to_geojson(path, layer="survey_mixed")
                    output = Path(d) / ("rejected-%d.html" % i)
                    result = self.cli(*self.args(path), "--output", output)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(output.exists())

    def test_mismatched_metadata_dimensions_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = mixed_db(build(Path(d) / "source.gpkg"))
            with sqlite3.connect(path) as db:
                db.execute("UPDATE gpkg_geometry_columns SET z=1 "
                           "WHERE table_name='survey_mixed'")
            with self.assertRaises(ValueError):
                to_geojson(path, layer="survey_mixed")


if __name__ == "__main__":
    unittest.main()
