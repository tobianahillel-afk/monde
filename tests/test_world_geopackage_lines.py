"""GeoPackage original LineString -> evidence claims -> MONDE Mini offline traces."""
import json
import os
from pathlib import Path
import sqlite3
import struct
import subprocess
import sys
import tempfile
import unittest

from monde.geopackage_points import _line, to_geojson
from monde.geojson import to_document
from monde.world import WorldMini
from tests.test_world_geopackage import build, CAP, AT


def line(points, *, srid=4326, envelope=False, big_endian=False):
    endian = ">" if big_endian else "<"
    flags = 0 if big_endian else 1
    if envelope:
        flags |= 2
    header = b"GP\x00" + bytes([flags]) + struct.pack(endian + "i", srid)
    if envelope:
        lons = [p[0] for p in points]
        lats = [p[1] for p in points]
        header += struct.pack(endian + "dddd", min(lons), max(lons), min(lats), max(lats))
    wkb = bytes([0 if big_endian else 1])
    wkb += struct.pack(endian + "II", 2, len(points))
    wkb += b"".join(struct.pack(endian + "dd", *point) for point in points)
    return header + wkb


def add_lines(path):
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE survey_lines (
                fid INTEGER PRIMARY KEY, geom BLOB NOT NULL, name TEXT);
            INSERT INTO gpkg_contents VALUES
                ('survey_lines','features','Source routes',4326);
            INSERT INTO gpkg_geometry_columns VALUES
                ('survey_lines','geom','LINESTRING',4326,0,0);
        """)
        db.executemany("INSERT INTO survey_lines VALUES (?, ?, ?)", [
            (12, line([(2.35, 48.85), (2.36, 48.86), (2.37, 48.87)]), "Survey path"),
            (13, line([(2.40, 48.80), (2.41, 48.81)], envelope=True), "Other path"),
        ])
    return path


class GeoPackageLineTests(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "monde.map_view", *map(str, args)],
                              capture_output=True, text=True, env={
                                  **os.environ, "PYTHONPATH": str(
                                      Path(__file__).resolve().parents[1] / "src")})

    def args(self, source):
        return ("--gpkg", source, "--gpkg-layer", "survey_lines",
                "--source-id", "gpkg-lines",
                "--source-locator", "dataset://survey-original.gpkg",
                "--captured-at", CAP, "--valid-from", "2026-01-01T00:00:00Z",
                "--at", AT, "--known-at", CAP)

    def test_real_sqlite_evidence_and_stable_feature_lineage(self):
        with tempfile.TemporaryDirectory() as d:
            original = add_lines(build(Path(d) / "survey.gpkg"))
            untouched = original.read_bytes()
            collection = to_geojson(original, layer="survey_lines")
            self.assertEqual(len(collection["features"]), 5)
            self.assertEqual([f["id"] for f in collection["features"][:3]],
                             ["gpkg-line-survey_lines-12-0",
                              "gpkg-line-survey_lines-12-1",
                              "gpkg-line-survey_lines-12-2"])
            first = collection["features"][0]
            self.assertEqual(first["properties"]["name"], "Survey path")
            self.assertEqual(first["properties"]["gpkg_trace"]["feature_id"], "12")
            self.assertEqual(first["properties"]["gpkg_trace"]["order"], 0)
            self.assertEqual(collection["features"][1]["geometry"]["coordinates"], [2.36, 48.86])
            self.assertNotEqual(
                collection["features"][0]["properties"]["gpkg_trace"]["trace_id"],
                collection["features"][3]["properties"]["gpkg_trace"]["trace_id"])
            world = WorldMini.from_document(to_document(
                collection, source_id="gpkg-lines",
                locator="dataset://survey-original.gpkg",
                captured_at=CAP, valid_from="2026-01-01T00:00:00Z"))
            export = world.export_geojson_bbox([-180, -90, 180, 90], AT, CAP)
            self.assertEqual(len(export["features"]), 5)
            self.assertEqual(export["features"][0]["properties"]["source_id"], "gpkg-lines")
            self.assertEqual(original.read_bytes(), untouched)

    def test_cli_renders_real_lines_without_remote_data(self):
        with tempfile.TemporaryDirectory() as d:
            original = add_lines(build(Path(d) / "survey.gpkg"))
            output = Path(d) / "map.html"
            done = self.cli(*self.args(original), "--output", output)
            self.assertEqual(done.returncode, 0, done.stderr)
            html = output.read_text(encoding="utf8")
            self.assertIn('"total_source_features":5', html)
            self.assertIn("GPKG_1_3_LINESTRING_POINT", html)
            self.assertIn("data-gpkg-trace", html)
            self.assertIn("GeoPackage source layer", html)
            self.assertNotIn("https://tile.", html)

    def test_mixed_source_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            original = add_lines(build(Path(d) / "survey.gpkg"))
            manifest = Path(d) / "manifest.json"
            manifest.write_text(json.dumps({"datasets": [
                {"source_id": "route", "locator": "dataset://route",
                 "captured_at": CAP, "valid_from": "2026-01-01T00:00:00Z",
                 "gpkg": original.name, "gpkg_layer": "survey_lines"},
                {"source_id": "points", "locator": "dataset://points",
                 "captured_at": CAP, "valid_from": "2026-01-01T00:00:00Z",
                 "gpkg": original.name, "gpkg_layer": "survey_points"}
            ]}), encoding="utf8")
            out = Path(d) / "mixed.html"
            done = self.cli("--source-manifest", manifest, "--at", AT,
                            "--known-at", CAP, "--output", out)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn('"total_source_features":7', out.read_text(encoding="utf8"))

    def test_invalid_wkb_rejected_atomically(self):
        with tempfile.TemporaryDirectory() as d:
            original = add_lines(build(Path(d) / "survey.gpkg"))
            cases = [
                b"bad", line([(2, 48), (3, 49)], srid=3857),
                line([(2, 48), (190, 49)]),
                line([(2, 48), (float("nan"), 49)]),
                line([(2, 48), (3, 49)]) + b"extra",
                line([(2, 48)]),
                line([(2, 48), (3, 49)])[:13],
            ]
            for i, damaged in enumerate(cases):
                with self.subTest(i=i):
                    with sqlite3.connect(original) as db:
                        db.execute("UPDATE survey_lines SET geom=? WHERE fid=12", (damaged,))
                    output = Path(d) / (str(i) + ".html")
                    done = self.cli(*self.args(original), "--output", output)
                    self.assertNotEqual(done.returncode, 0)
                    self.assertFalse(output.exists())

    def test_endianness_and_envelope_mismatch(self):
        self.assertEqual(_line(line([(2.35, 48.85), (2.4, 48.9)], big_endian=True)),
                         [[2.35, 48.85], [2.4, 48.9]])
        blob = bytearray(line([(2.35, 48.85), (2.4, 48.9)], envelope=True))
        struct.pack_into("<d", blob, 16, 2.36)
        with self.assertRaises(ValueError):
            _line(bytes(blob))

    def test_source_points_unaffected_and_unsupported_polygon_fails(self):
        with tempfile.TemporaryDirectory() as d:
            original = add_lines(build(Path(d) / "survey.gpkg"))
            self.assertEqual(len(to_geojson(original, layer="survey_points")["features"]), 2)
            with sqlite3.connect(original) as db:
                db.execute("UPDATE gpkg_geometry_columns "
                           "SET geometry_type_name='POLYGON' WHERE table_name='survey_lines'")
            with self.assertRaises(ValueError):
                to_geojson(original, layer="survey_lines")


if __name__ == "__main__":
    unittest.main()
