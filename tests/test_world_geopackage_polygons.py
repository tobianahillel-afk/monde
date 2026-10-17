"""Original GeoPackage 2D Polygon rings -> sourced bitemporal offline map."""
import json
import os
from pathlib import Path
import sqlite3
import struct
import subprocess
import sys
import tempfile
import unittest

from monde.geopackage_points import _polygon, to_geojson
from monde.geojson import to_document
from monde.world import WorldMini
from tests.test_world_geopackage import AT, CAP, build


OUTER = [[2.35, 48.85], [2.37, 48.85], [2.37, 48.87], [2.35, 48.85]]
INNER = [[2.355, 48.855], [2.360, 48.855],
         [2.360, 48.860], [2.355, 48.855]]


def polygon(rings, *, srid=4326, envelope=False, big_endian=False):
    fmt = ">" if big_endian else "<"
    flags = 0 if big_endian else 1
    if envelope:
        flags |= 2
    gp = b"GP\x00" + bytes([flags]) + struct.pack(fmt + "i", srid)
    if envelope:
        coords = [p for ring in rings for p in ring]
        gp += struct.pack(fmt + "dddd",
                          min(p[0] for p in coords), max(p[0] for p in coords),
                          min(p[1] for p in coords), max(p[1] for p in coords))
    wkb = bytes([0 if big_endian else 1]) + struct.pack(fmt + "II", 3, len(rings))
    for ring in rings:
        wkb += struct.pack(fmt + "I", len(ring))
        wkb += b"".join(struct.pack(fmt + "dd", *p) for p in ring)
    return gp + wkb


def add_polygons(path):
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE survey_polygons (
                fid INTEGER PRIMARY KEY, geom BLOB NOT NULL, name TEXT);
            INSERT INTO gpkg_contents VALUES
                ('survey_polygons','features','Original claimed boundaries',4326);
            INSERT INTO gpkg_geometry_columns VALUES
                ('survey_polygons','geom','POLYGON',4326,0,0);
        """)
        db.execute("INSERT INTO survey_polygons VALUES (?, ?, ?)",
                   (21, polygon([OUTER, INNER], envelope=True), "Claimed block"))
        db.execute("INSERT INTO survey_polygons VALUES (?, ?, ?)",
                   (22, polygon([OUTER]), "Second source feature"))
    return path


class GeoPackagePolygonTests(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "monde.map_view",
                               *map(str, args)], capture_output=True, text=True,
                              env={**os.environ, "PYTHONPATH": str(
                                  Path(__file__).resolve().parents[1] / "src")})

    def args(self, file):
        return ("--gpkg", file, "--gpkg-layer", "survey_polygons",
                "--source-id", "original-boundaries",
                "--source-locator", "dataset://boundaries.gpkg",
                "--captured-at", CAP, "--valid-from", "2026-01-01T00:00:00Z",
                "--at", AT, "--known-at", CAP)

    def test_original_outer_inner_order_attributes_and_world_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            source = add_polygons(build(Path(d) / "original.gpkg"))
            unchanged = source.read_bytes()
            feature_set = to_geojson(source, layer="survey_polygons")
            self.assertEqual(len(feature_set["features"]), 12)
            first = feature_set["features"][0]
            self.assertEqual(first["id"], "gpkg-polygon-survey_polygons-21-0-0")
            self.assertEqual(feature_set["features"][4]["id"],
                             "gpkg-polygon-survey_polygons-21-1-0")
            self.assertEqual(first["properties"]["gpkg_trace"]["kind"], "Polygon")
            self.assertEqual(first["properties"]["gpkg_trace"]["name"], "Claimed block")
            self.assertEqual(first["properties"]["gpkg_trace"]["feature_id"], "21")
            self.assertEqual(feature_set["features"][4]["properties"]["gpkg_trace"]["segment"], 1)
            self.assertEqual(feature_set["features"][3]["geometry"]["coordinates"], OUTER[-1])
            self.assertEqual(feature_set["features"][7]["geometry"]["coordinates"], INNER[-1])
            world = WorldMini.from_document(to_document(
                feature_set, source_id="original-boundaries",
                locator="dataset://boundaries.gpkg", captured_at=CAP,
                valid_from="2026-01-01T00:00:00Z"))
            reports = world.export_geojson_bbox([-180, -90, 180, 90], AT, CAP)
            self.assertEqual(len(reports["features"]), 12)
            self.assertEqual(len({
                f["properties"]["monde_gpkg_trace"]["feature_id"]
                for f in reports["features"]}), 2)
            self.assertEqual(source.read_bytes(), unchanged)

    def test_cli_direct_original_polygon_offline_render(self):
        with tempfile.TemporaryDirectory() as d:
            path = add_polygons(build(Path(d) / "source.gpkg"))
            target = Path(d) / "map.html"
            result = self.cli(*self.args(path), "--output", target)
            self.assertEqual(result.returncode, 0, result.stderr)
            page = target.read_text(encoding="utf8")
            for marker in ['"total_source_features":12',
                           "GPKG_1_3_POLYGON_RING_POINT", "data-gpkg-boundary",
                           "Claimed block", "data-monde-gpkg-inner-segments"]:
                self.assertIn(marker, page)
            self.assertNotIn("https://tile.", page)

    def test_manifest_with_points_lines_and_polygon(self):
        with tempfile.TemporaryDirectory() as d:
            path = add_polygons(build(Path(d) / "source.gpkg"))
            manifest = Path(d) / "manifest.json"
            template = {"locator": "dataset://source", "captured_at": CAP,
                        "valid_from": "2026-01-01T00:00:00Z",
                        "gpkg": path.name}
            manifest.write_text(json.dumps({"datasets": [
                {**template, "source_id": "polygons", "gpkg_layer": "survey_polygons"},
                {**template, "source_id": "points", "gpkg_layer": "survey_points"}
            ]}), encoding="utf8")
            output = Path(d) / "combined.html"
            result = self.cli("--source-manifest", manifest, "--at", AT,
                              "--known-at", CAP, "--output", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"total_source_features":14', output.read_text(encoding="utf8"))

    def test_endianness_envelope_closure_and_ring_count(self):
        self.assertEqual(_polygon(polygon([OUTER, INNER], big_endian=True)),
                         [OUTER, INNER])
        self.assertEqual(_polygon(polygon([OUTER], envelope=True)), [OUTER])
        for blob in [b"bad", polygon([OUTER], srid=9999),
                     polygon([OUTER]) + b"extra", polygon([OUTER])[:-2],
                     polygon([]), polygon([OUTER[:-1]]),
                     polygon([OUTER, [[2, 48], [3, 49], [4, 49], [2, 48]]],
                             envelope=True)[:-1]]:
            with self.subTest(blob_size=len(blob)), self.assertRaises(ValueError):
                _polygon(blob)

    def test_bad_crs_envelope_nan_duplicate_rejected_without_output(self):
        with tempfile.TemporaryDirectory() as d:
            path = add_polygons(build(Path(d) / "source.gpkg"))
            malformed = [
                polygon([OUTER], srid=9999),
                polygon([OUTER[:-1]]),
                polygon([[[2.0, 48.0], [3.0, 48.0],
                          [3.0, float("nan")], [2.0, 48.0]]]),
                polygon([OUTER]) + b"\x00",
                polygon([OUTER])[:30],
            ]
            bad_envelope = bytearray(polygon([OUTER], envelope=True))
            struct.pack_into("<d", bad_envelope, 16, 2.36)
            malformed.append(bytes(bad_envelope))
            for index, blob in enumerate(malformed):
                with self.subTest(index=index):
                    with sqlite3.connect(path) as db:
                        db.execute("UPDATE survey_polygons SET geom=? WHERE fid=21",
                                   (blob,))
                    output = Path(d) / f"invalid-{index}.html"
                    run = self.cli(*self.args(path), "--output", output)
                    self.assertNotEqual(run.returncode, 0)
                    self.assertFalse(output.exists())

    def test_declared_polygon_cannot_hide_wrong_wkb_geometry(self):
        with tempfile.TemporaryDirectory() as d:
            path = add_polygons(build(Path(d) / "source.gpkg"))
            blob = bytearray(polygon([OUTER]))
            struct.pack_into("<I", blob, 9, 2)
            with sqlite3.connect(path) as db:
                db.execute("UPDATE survey_polygons SET geom=? WHERE fid=21", (bytes(blob),))
            with self.assertRaises(ValueError):
                to_geojson(path, layer="survey_polygons")


if __name__ == "__main__":
    unittest.main()
