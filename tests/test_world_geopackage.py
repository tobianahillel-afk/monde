"""Real SQLite GeoPackage -> source evidence -> MONDE Mini offline map."""
import json
import os
from pathlib import Path
import sqlite3
import struct
import subprocess
import sys
import tempfile
import unittest

from monde.geopackage_points import _point, to_geojson
from monde.geojson import to_document
from monde.world import WorldMini

AT = "2026-01-02T00:00:00Z"
CAP = "2026-01-10T10:00:00Z"


def point(lon, lat, *, srid=4326, envelope=False, little=True):
    flags = 1 | (2 if envelope else 0)
    header = b"GP\x00" + bytes([flags]) + struct.pack("<i", srid)
    if envelope:
        header += struct.pack("<dddd", lon, lon, lat, lat)
    fmt = "<" if little else ">"
    return header + bytes([1 if little else 0]) + struct.pack(fmt + "Idd", 1, lon, lat)


def build(path):
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA application_id=1196444487")
        db.executescript("""
        CREATE TABLE gpkg_spatial_ref_sys (
          srs_name TEXT, srs_id INTEGER PRIMARY KEY,
          organization TEXT, organization_coordsys_id INTEGER,
          definition TEXT, description TEXT);
        CREATE TABLE gpkg_contents (
          table_name TEXT PRIMARY KEY, data_type TEXT, identifier TEXT, srs_id INTEGER);
        CREATE TABLE gpkg_geometry_columns (
          table_name TEXT, column_name TEXT, geometry_type_name TEXT,
          srs_id INTEGER, z INTEGER, m INTEGER);
        CREATE TABLE survey_points (
          fid INTEGER PRIMARY KEY, geom BLOB NOT NULL, name TEXT);
        """)
        db.execute("INSERT INTO gpkg_spatial_ref_sys VALUES "
                   "('WGS 84',4326,'EPSG',4326,'EPSG definition','fixture')")
        db.execute("INSERT INTO gpkg_contents VALUES "
                   "('survey_points','features','Survey points',4326)")
        db.execute("INSERT INTO gpkg_geometry_columns VALUES "
                   "('survey_points','geom','POINT',4326,0,0)")
        db.executemany("INSERT INTO survey_points VALUES (?, ?, ?)", [
            (1, point(2.3522, 48.8566), "Survey A"),
            (2, point(2.36, 48.86, envelope=True), "Survey B")])
    return path


class GeoPackageTests(unittest.TestCase):
    def cmd(self, *args):
        return subprocess.run([sys.executable, "-m", "monde.map_view", *map(str, args)],
                              capture_output=True, text=True,
                              env={**os.environ, "PYTHONPATH": str(
                                  Path(__file__).resolve().parents[1] / "src")})

    def direct(self, source):
        return ("--gpkg", source, "--gpkg-layer", "survey_points",
                "--source-id", "gpkg-survey", "--source-locator", "dataset://survey.gpkg",
                "--captured-at", CAP, "--valid-from", "2026-01-01T00:00:00Z",
                "--at", AT, "--known-at", CAP)

    def test_original_sqlite_source_reaches_temporal_model(self):
        with tempfile.TemporaryDirectory() as d:
            source = build(Path(d) / "source.gpkg")
            original = source.read_bytes()
            geo = to_geojson(source, layer="survey_points")
            self.assertEqual([f["id"] for f in geo["features"]], ["1", "2"])
            self.assertEqual(geo["features"][1]["geometry"]["coordinates"], [2.36, 48.86])
            self.assertEqual(geo["features"][0]["properties"]["name"], "Survey A")
            world = WorldMini.from_document(to_document(
                geo, source_id="gpkg-survey", locator="dataset://survey.gpkg",
                captured_at=CAP, valid_from="2026-01-01T00:00:00Z"))
            export = world.export_geojson_bbox([-180, -90, 180, 90], AT, CAP)
            self.assertEqual(len(export["features"]), 2)
            self.assertEqual(len({x["properties"]["evidence_id"]
                                  for x in export["features"]}), 2)
            self.assertEqual(world.entity_snapshot("1", AT, CAP)["attributes"]
                             ["name"]["reports"][0]["value"], "Survey A")
            self.assertEqual(source.read_bytes(), original)

    def test_direct_cli_creates_actual_offline_map(self):
        with tempfile.TemporaryDirectory() as d:
            source = build(Path(d) / "source.gpkg")
            output = Path(d) / "map.html"
            run = self.cmd(*self.direct(source), "--output", output)
            self.assertEqual(run.returncode, 0, run.stderr)
            html = output.read_text(encoding="utf8")
            for marker in ('"total_source_features":2', "gpkg-survey", "dataset://survey.gpkg"):
                self.assertIn(marker, html)
            self.assertNotIn("https://tile.", html)
            self.assertEqual(source.read_bytes()[:16], b"SQLite format 3\x00")

    def test_source_manifest_combines_real_gpkg_and_geojson(self):
        with tempfile.TemporaryDirectory() as d:
            build(Path(d) / "source.gpkg")
            other = Path(d) / "other.geojson"
            other.write_text(json.dumps({
                "type": "FeatureCollection", "features": [{
                    "type": "Feature", "id": "other-report", "properties": {},
                    "geometry": {"type": "Point", "coordinates": [3, 49]}}]
            }), encoding="utf8")
            common = {"locator": "dataset://original", "captured_at": CAP,
                      "valid_from": "2026-01-01T00:00:00Z"}
            manifest = Path(d) / "sources.json"
            manifest.write_text(json.dumps({"datasets": [
                {**common, "gpkg": "source.gpkg", "gpkg_layer": "survey_points",
                 "source_id": "gpkg-source"},
                {**common, "geojson": "other.geojson", "source_id": "other-source"}
            ]}), encoding="utf8")
            output = Path(d) / "combined.html"
            run = self.cmd("--source-manifest", manifest, "--at", AT,
                           "--known-at", CAP, "--output", output)
            self.assertEqual(run.returncode, 0, run.stderr)
            page = output.read_text(encoding="utf8")
            self.assertIn('"total_source_features":3', page)
            self.assertIn("gpkg-source", page)
            self.assertIn("other-source", page)

    def test_unsafe_layer_and_inconsistent_crs_fail(self):
        with tempfile.TemporaryDirectory() as d:
            source = build(Path(d) / "source.gpkg")
            for name in ["survey_points;DROP TABLE survey_points", "unknown", "", "../survey"]:
                with self.subTest(layer=name), self.assertRaises(ValueError):
                    to_geojson(source, layer=name)
            with sqlite3.connect(source) as db:
                db.execute("UPDATE gpkg_contents SET srs_id=3857")
            with self.assertRaises(ValueError):
                to_geojson(source, layer="survey_points")

    def test_bad_geometry_fails_without_partial_output(self):
        with tempfile.TemporaryDirectory() as d:
            source = build(Path(d) / "source.gpkg")
            for index, malformed in enumerate([
                b"bad", point(2, 49, srid=3857),
                point(200, 49), point(float("nan"), 49),
                point(2, 49) + b"extra"
            ]):
                with self.subTest(case=index):
                    with sqlite3.connect(source) as db:
                        db.execute("UPDATE survey_points SET geom=? WHERE fid=1",
                                   (malformed,))
                    with self.assertRaises(ValueError):
                        to_geojson(source, layer="survey_points")
                    output = Path(d) / (str(index) + ".html")
                    run = self.cmd(*self.direct(source), "--output", output)
                    self.assertNotEqual(run.returncode, 0)
                    self.assertFalse(output.exists())

    def test_invalid_source_does_not_overwrite_existing_output(self):
        with tempfile.TemporaryDirectory() as d:
            source = build(Path(d) / "source.gpkg")
            output = Path(d) / "existing.html"
            output.write_text("PRESERVED", encoding="utf8")
            run = self.cmd(*self.direct(source), "--output", output)
            self.assertNotEqual(run.returncode, 0)
            self.assertEqual(output.read_text(encoding="utf8"), "PRESERVED")
            manifest = Path(d) / "sources.json"
            manifest.write_text(json.dumps({"datasets": [{
                "source_id": "s", "locator": "dataset://s", "captured_at": CAP,
                "valid_from": "2026-01-01T00:00:00Z", "gpkg": "source.gpkg"
            }]}), encoding="utf8")
            absent = Path(d) / "absent.html"
            fail = self.cmd("--source-manifest", manifest, "--at", AT,
                            "--known-at", CAP, "--output", absent)
            self.assertNotEqual(fail.returncode, 0)
            self.assertFalse(absent.exists())

    def test_wkb_big_endian_and_header_rejections(self):
        self.assertEqual(_point(point(2.35, 48.85, little=False)), [2.35, 48.85])
        for malformed in [
            b"", b"GP\x00\x11" + point(2, 49)[4:],
            b"GP\x00\x09" + point(2, 49)[4:],
            point(2, 49)[:8] + b"\x01" + struct.pack("<Idd", 2, 2, 49)
        ]:
            with self.subTest(blob=malformed[:8]), self.assertRaises(ValueError):
                _point(malformed)


if __name__ == "__main__":
    unittest.main()
