"""Real GeoPackage MultiPolygon members -> MONDE Mini original-source evidence."""
import json
import os
from pathlib import Path
import sqlite3
import struct
import subprocess
import sys
import tempfile
import unittest

from monde.geopackage_points import _multipolygon, to_geojson
from monde.geojson import to_document
from monde.world import WorldMini
from tests.test_world_geopackage import build, AT, CAP
from tests.test_world_geopackage_polygons import OUTER, INNER, polygon

OUTER2 = [[3.0, 49.0], [3.03, 49.0], [3.03, 49.03], [3.0, 49.0]]
POLYGONS = [[OUTER, INNER], [OUTER2]]


def multipolygon(members, *, envelope=False, big_endian=False, srid=4326):
    endian = ">" if big_endian else "<"
    flags = (0 if big_endian else 1) | (2 if envelope else 0)
    header = b"GP\x00" + bytes([flags]) + struct.pack(endian + "i", srid)
    if envelope:
        coords = [p for member in members for ring in member for p in ring]
        header += struct.pack(endian + "dddd", min(p[0] for p in coords),
                              max(p[0] for p in coords), min(p[1] for p in coords),
                              max(p[1] for p in coords))
    wkb = bytes([0 if big_endian else 1]) + struct.pack(endian + "II", 6, len(members))
    for index, member in enumerate(members):
        # Different endian children are valid WKB and must retain their vertices.
        wkb += polygon(member, big_endian=bool(index % 2)) [8:]
    return header + wkb


def add_multipolygons(path):
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE survey_multi (fid INTEGER PRIMARY KEY, geom BLOB NOT NULL, name TEXT);
            INSERT INTO gpkg_contents VALUES
                ('survey_multi','features','Original multipart evidence',4326);
            INSERT INTO gpkg_geometry_columns VALUES
                ('survey_multi','geom','MULTIPOLYGON',4326,0,0);
        """)
        db.execute("INSERT INTO survey_multi VALUES (?, ?, ?)",
                   (41, multipolygon(POLYGONS, envelope=True), "Multipart claim"))
    return path


class GeoPackageMultiPolygonTests(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "monde.map_view",
                               *map(str, args)], text=True, capture_output=True,
                              env={**os.environ, "PYTHONPATH": str(
                                  Path(__file__).resolve().parents[1] / "src")})

    def args(self, source):
        return ("--gpkg", source, "--gpkg-layer", "survey_multi",
                "--source-id", "original-multi",
                "--source-locator", "dataset://multi.gpkg",
                "--captured-at", CAP, "--valid-from", "2026-01-01T00:00:00Z",
                "--at", AT, "--known-at", CAP)

    def test_decoder_keeps_component_ring_order_and_mixed_endian(self):
        self.assertEqual(_multipolygon(multipolygon(POLYGONS, envelope=True)), POLYGONS)
        self.assertEqual(_multipolygon(multipolygon(POLYGONS, big_endian=True)), POLYGONS)

    def test_source_provenance_and_bitemporal_export_do_not_merge_members(self):
        with tempfile.TemporaryDirectory() as d:
            path = add_multipolygons(build(Path(d) / "source.gpkg"))
            original = path.read_bytes()
            collection = to_geojson(path, layer="survey_multi")
            self.assertEqual(len(collection["features"]), 12)
            samples = collection["features"]
            self.assertEqual(samples[0]["id"], "gpkg-multipolygon-survey_multi-41-0-0-0")
            self.assertEqual(samples[8]["id"], "gpkg-multipolygon-survey_multi-41-1-0-0")
            self.assertEqual(samples[0]["properties"]["gpkg_trace"]["polygon_index"], 0)
            self.assertEqual(samples[8]["properties"]["gpkg_trace"]["polygon_index"], 1)
            self.assertEqual(samples[4]["properties"]["gpkg_trace"]["segment"], 1)
            self.assertNotEqual(samples[0]["properties"]["gpkg_trace"]["trace_id"],
                                samples[8]["properties"]["gpkg_trace"]["trace_id"])
            world = WorldMini.from_document(to_document(
                collection, source_id="original-multi", locator="dataset://multi.gpkg",
                captured_at=CAP, valid_from="2026-01-01T00:00:00Z"))
            exported = world.export_geojson_bbox([-180, -90, 180, 90], AT, CAP)
            self.assertEqual(len(exported["features"]), 12)
            self.assertEqual({f["properties"]["source_id"] for f in exported["features"]},
                             {"original-multi"})
            self.assertEqual({f["properties"]["monde_gpkg_trace"]["polygon_index"]
                              for f in exported["features"]}, {0, 1})
            self.assertEqual(path.read_bytes(), original)

    def test_direct_cli_and_mixed_manifest_render_original_members(self):
        with tempfile.TemporaryDirectory() as d:
            path = add_multipolygons(build(Path(d) / "source.gpkg"))
            direct = Path(d) / "multi.html"
            result = self.cli(*self.args(path), "--output", direct)
            self.assertEqual(result.returncode, 0, result.stderr)
            html = direct.read_text(encoding="utf8")
            for marker in ("GPKG_1_3_MULTIPOLYGON_RING_POINT",
                           "data-gpkg-boundary", "Multipart claim",
                           "data-monde-gpkg-inner-segments"):
                self.assertIn(marker, html)
            manifest = Path(d) / "sources.json"
            manifest.write_text(json.dumps({"datasets": [
                {"gpkg": path.name, "gpkg_layer": "survey_multi",
                 "source_id": "original-multi", "locator": "dataset://multi.gpkg",
                 "captured_at": CAP, "valid_from": "2026-01-01T00:00:00Z"},
                {"gpkg": path.name, "gpkg_layer": "survey_points",
                 "source_id": "original-point", "locator": "dataset://point.gpkg",
                 "captured_at": CAP, "valid_from": "2026-01-01T00:00:00Z"}]}),
                encoding="utf8")
            combined = Path(d) / "combined.html"
            result = self.cli("--source-manifest", manifest, "--at", AT,
                              "--known-at", CAP, "--output", combined)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"total_source_features":14', combined.read_text(encoding="utf8"))

    def test_corrupt_nested_wkb_and_inconsistent_metadata_fail_atomically(self):
        with tempfile.TemporaryDirectory() as d:
            path = add_multipolygons(build(Path(d) / "source.gpkg"))
            valid = multipolygon(POLYGONS)
            invalid = [
                b"bad", valid + b"extra", valid[:-2],
                multipolygon(POLYGONS, srid=3857), multipolygon([]),
                multipolygon([[OUTER[:-1]]]), multipolygon([[OUTER, INNER], []]),
            ]
            bad_type = bytearray(valid)
            struct.pack_into("<I", bad_type, 17, 2)
            invalid.append(bytes(bad_type))
            huge_count = bytearray(valid)
            struct.pack_into("<I", huge_count, 13, 9999)
            invalid.append(bytes(huge_count))
            bad_envelope = bytearray(multipolygon(POLYGONS, envelope=True))
            struct.pack_into("<d", bad_envelope, 16, 2.36)
            invalid.append(bytes(bad_envelope))
            for i, blob in enumerate(invalid):
                with self.subTest(index=i):
                    with sqlite3.connect(path) as db:
                        db.execute("UPDATE survey_multi SET geom=? WHERE fid=41", (blob,))
                    output = Path(d) / ("invalid-" + str(i) + ".html")
                    result = self.cli(*self.args(path), "--output", output)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(output.exists())

    def test_layer_claim_must_match_actual_wkb(self):
        with tempfile.TemporaryDirectory() as d:
            path = add_multipolygons(build(Path(d) / "source.gpkg"))
            with sqlite3.connect(path) as db:
                db.execute("UPDATE survey_multi SET geom=? WHERE fid=41",
                           (polygon([OUTER]),))
            with self.assertRaises(ValueError):
                to_geojson(path, layer="survey_multi")


if __name__ == "__main__":
    unittest.main()
