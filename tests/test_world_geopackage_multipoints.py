"""Real GeoPackage MultiPoint observations -> bitemporal offline evidence map."""
import json
import os
from pathlib import Path
import sqlite3
import struct
import subprocess
import sys
import tempfile
import unittest

from monde.geopackage_points import _multipoint, to_geojson
from monde.geojson import to_document
from monde.world import WorldMini
from tests.test_world_geopackage import build, point, AT, CAP

POINTS = [[2.35, 48.85], [2.36, 48.86], [3.0, 49.0]]


def multipoint(points, envelope=False, big_endian=False, srid=4326):
    fmt = ">" if big_endian else "<"
    flags = (0 if big_endian else 1) | (2 if envelope else 0)
    header = b"GP\x00" + bytes([flags]) + struct.pack(fmt + "i", srid)
    if envelope:
        header += struct.pack(fmt + "dddd",
                              min(p[0] for p in points), max(p[0] for p in points),
                              min(p[1] for p in points), max(p[1] for p in points))
    wkb = bytes([0 if big_endian else 1]) + struct.pack(fmt + "II", 4, len(points))
    for i, (lon, lat) in enumerate(points):
        wkb += point(lon, lat, little=bool(i % 2))[8:]
    return header + wkb


def source_db(path):
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE source_multi (fid INTEGER PRIMARY KEY, geom BLOB NOT NULL, name TEXT);
            INSERT INTO gpkg_contents VALUES
              ('source_multi','features','Original multipart points',4326);
            INSERT INTO gpkg_geometry_columns VALUES
              ('source_multi','geom','MULTIPOINT',4326,0,0);
        """)
        db.execute("INSERT INTO source_multi VALUES (?,?,?)",
                   (41, multipoint(POINTS, envelope=True), "Three samples"))
    return path


class MultiPointTests(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "monde.map_view", *map(str, args)],
                              text=True, capture_output=True, env={**os.environ,
                              "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")})

    def params(self, path):
        return ("--gpkg", path, "--gpkg-layer", "source_multi",
                "--source-id", "observations", "--source-locator", "dataset://multi.gpkg",
                "--captured-at", CAP, "--valid-from", "2026-01-01T00:00:00Z",
                "--at", AT, "--known-at", CAP)

    def test_wkb_mixed_endianness_and_envelope(self):
        self.assertEqual(_multipoint(multipoint(POINTS, envelope=True)), POINTS)
        self.assertEqual(_multipoint(multipoint(POINTS, big_endian=True)), POINTS)

    def test_sqlite_provenance_and_world_model_export(self):
        with tempfile.TemporaryDirectory() as d:
            path = source_db(build(Path(d) / "source.gpkg"))
            before = path.read_bytes()
            feats = to_geojson(path, layer="source_multi")["features"]
            self.assertEqual(len(feats), 3)
            self.assertEqual([f["id"] for f in feats],
                             ["gpkg-multipoint-source_multi-41-" + str(i) for i in range(3)])
            self.assertEqual([f["properties"]["gpkg_trace"]["order"] for f in feats],
                             [0, 1, 2])
            world = WorldMini.from_document(to_document(
                {"type":"FeatureCollection", "features":feats}, source_id="observations",
                locator="dataset://multi.gpkg", captured_at=CAP,
                valid_from="2026-01-01T00:00:00Z"))
            output = world.export_geojson_bbox([-180, -90, 180, 90], AT, CAP)
            self.assertEqual(len(output["features"]), 3)
            self.assertEqual({f["properties"]["monde_gpkg_trace"]["kind"]
                              for f in output["features"]}, {"MultiPoint"})
            self.assertEqual(path.read_bytes(), before)

    def test_cli_and_mixed_sources_do_not_invent_paths(self):
        with tempfile.TemporaryDirectory() as d:
            path = source_db(build(Path(d) / "source.gpkg"))
            html = Path(d) / "out.html"
            result = self.cli(*self.params(path), "--output", html)
            self.assertEqual(result.returncode, 0, result.stderr)
            content = html.read_text(encoding="utf8")
            self.assertIn('"total_source_features":3', content)
            self.assertIn("Source-declared MultiPoint member", content)
            self.assertIn('first.kind==="MultiPoint")continue', content)
            manifest = Path(d) / "sources.json"
            manifest.write_text(json.dumps({"datasets":[{
                "gpkg":path.name, "gpkg_layer":"source_multi", "source_id":"multi",
                "locator":"dataset://multi.gpkg", "captured_at":CAP,
                "valid_from":"2026-01-01T00:00:00Z"},{
                "gpkg":path.name, "gpkg_layer":"survey_points", "source_id":"points",
                "locator":"dataset://points.gpkg", "captured_at":CAP,
                "valid_from":"2026-01-01T00:00:00Z"}]}), encoding="utf8")
            output = Path(d) / "mixed.html"
            result = self.cli("--source-manifest",manifest,"--at",AT,
                              "--known-at",CAP,"--output",output)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"total_source_features":5',output.read_text(encoding="utf8"))

    def test_corrupt_wkb_rejected_without_html(self):
        with tempfile.TemporaryDirectory() as d:
            path = source_db(build(Path(d) / "source.gpkg"))
            valid = multipoint(POINTS)
            corrupt = [valid[:-1], valid+b"x", b"bad",
                       multipoint(POINTS,srid=9999), multipoint([]),
                       multipoint([[200,48]])]
            wrong = bytearray(valid)
            struct.pack_into("<I",wrong,17,2)
            corrupt.append(bytes(wrong))
            envelope = bytearray(multipoint(POINTS,envelope=True))
            struct.pack_into("<d",envelope,16,2.355)
            corrupt.append(bytes(envelope))
            for i, blob in enumerate(corrupt):
                with self.subTest(i=i):
                    with sqlite3.connect(path) as db:
                        db.execute("UPDATE source_multi SET geom=? WHERE fid=41",(blob,))
                    output=Path(d)/("invalid-%d.html"%i)
                    done=self.cli(*self.params(path),"--output",output)
                    self.assertNotEqual(done.returncode,0)
                    self.assertFalse(output.exists())

    def test_metadata_must_match_source_wkb(self):
        with tempfile.TemporaryDirectory() as d:
            path=source_db(build(Path(d)/"source.gpkg"))
            with sqlite3.connect(path) as db:
                db.execute("UPDATE source_multi SET geom=? WHERE fid=41",
                           (point(2.35,48.85),))
            with self.assertRaises(ValueError):
                to_geojson(path,layer="source_multi")
