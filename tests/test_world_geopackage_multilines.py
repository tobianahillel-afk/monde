"""Real GeoPackage MultiLineString members -> bitemporal evidence -> offline map."""
import json
import os
from pathlib import Path
import sqlite3
import struct
import subprocess
import sys
import tempfile
import unittest

from monde.geopackage_points import _multiline, to_geojson
from monde.geojson import to_document
from monde.world import WorldMini
from tests.test_world_geopackage import build, AT, CAP
from tests.test_world_geopackage_lines import line

LINES = [
    [[2.35, 48.85], [2.36, 48.86], [2.37, 48.87]],
    [[3.0, 49.0], [3.04, 49.04]],
]


def multiline(members, *, envelope=False, big_endian=False, srid=4326):
    endian = ">" if big_endian else "<"
    flags = (0 if big_endian else 1) | (2 if envelope else 0)
    header = b"GP\x00" + bytes([flags]) + struct.pack(endian + "i", srid)
    if envelope:
        pts = [p for member in members for p in member]
        header += struct.pack(endian + "dddd", min(p[0] for p in pts),
                              max(p[0] for p in pts), min(p[1] for p in pts),
                              max(p[1] for p in pts))
    wkb = bytes([0 if big_endian else 1]) + struct.pack(endian + "II", 5, len(members))
    for index, member in enumerate(members):
        wkb += line(member, big_endian=bool(index % 2)) [8:]
    return header + wkb


def add_multilines(source):
    with sqlite3.connect(source) as db:
        db.executescript("""
            CREATE TABLE survey_multilines (fid INTEGER PRIMARY KEY, geom BLOB NOT NULL, name TEXT);
            INSERT INTO gpkg_contents VALUES
                ('survey_multilines','features','Original multipart routes',4326);
            INSERT INTO gpkg_geometry_columns VALUES
                ('survey_multilines','geom','MULTILINESTRING',4326,0,0);
        """)
        db.execute("INSERT INTO survey_multilines VALUES (?, ?, ?)",
                   (41, multiline(LINES, envelope=True), "Two independent paths"))
    return source


class GeoPackageMultiLineTests(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "monde.map_view",
                               *map(str, args)], capture_output=True, text=True,
                              env={**os.environ, "PYTHONPATH": str(
                                  Path(__file__).resolve().parents[1] / "src")})

    def args(self, source):
        return ("--gpkg", source, "--gpkg-layer", "survey_multilines",
                "--source-id", "original-multiline",
                "--source-locator", "dataset://multi-lines.gpkg",
                "--captured-at", CAP, "--valid-from", "2026-01-01T00:00:00Z",
                "--at", AT, "--known-at", CAP)

    def test_decoder_preserves_components_and_nested_endianness(self):
        self.assertEqual(_multiline(multiline(LINES, envelope=True)), LINES)
        self.assertEqual(_multiline(multiline(LINES, big_endian=True)), LINES)

    def test_real_sqlite_provenance_and_export_have_independent_routes(self):
        with tempfile.TemporaryDirectory() as d:
            source = add_multilines(build(Path(d) / "source.gpkg"))
            original = source.read_bytes()
            features = to_geojson(source, layer="survey_multilines")["features"]
            self.assertEqual(len(features), 5)
            self.assertEqual(features[0]["id"], "gpkg-multiline-survey_multilines-41-0-0")
            self.assertEqual(features[3]["id"], "gpkg-multiline-survey_multilines-41-1-0")
            traces = [f["properties"]["gpkg_trace"] for f in features]
            self.assertEqual([t["line_index"] for t in traces], [0, 0, 0, 1, 1])
            self.assertEqual([t["order"] for t in traces], [0, 1, 2, 0, 1])
            self.assertNotEqual(traces[0]["trace_id"], traces[3]["trace_id"])
            world = WorldMini.from_document(to_document(
                {"type": "FeatureCollection", "features": features},
                source_id="original-multiline", locator="dataset://multi-lines.gpkg",
                captured_at=CAP, valid_from="2026-01-01T00:00:00Z"))
            exported = world.export_geojson_bbox([-180, -90, 180, 90], AT, CAP)
            self.assertEqual(len(exported["features"]), 5)
            self.assertEqual({f["properties"]["source_id"] for f in exported["features"]},
                             {"original-multiline"})
            self.assertEqual({f["properties"]["monde_gpkg_trace"]["line_index"]
                              for f in exported["features"]}, {0, 1})
            self.assertEqual(source.read_bytes(), original)

    def test_direct_cli_and_mixed_manifest_preserve_source_components(self):
        with tempfile.TemporaryDirectory() as d:
            source = add_multilines(build(Path(d) / "source.gpkg"))
            output = Path(d) / "multi.html"
            result = self.cli(*self.args(source), "--output", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            html = output.read_text(encoding="utf8")
            for token in ("GPKG_1_3_MULTILINESTRING_POINT",
                          "data-gpkg-trace", "Source-declared MultiLineString component",
                          '"total_source_features":5'):
                self.assertIn(token, html)
            manifest = Path(d) / "sources.json"
            manifest.write_text(json.dumps({"datasets": [
                {"gpkg": source.name, "gpkg_layer": "survey_multilines",
                 "source_id": "original-multiline", "locator": "dataset://multi-lines.gpkg",
                 "captured_at": CAP, "valid_from": "2026-01-01T00:00:00Z"},
                {"gpkg": source.name, "gpkg_layer": "survey_points",
                 "source_id": "original-point", "locator": "dataset://points.gpkg",
                 "captured_at": CAP, "valid_from": "2026-01-01T00:00:00Z"}
            ]}), encoding="utf8")
            combined = Path(d) / "combined.html"
            result = self.cli("--source-manifest", manifest, "--at", AT,
                              "--known-at", CAP, "--output", combined)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"total_source_features":7', combined.read_text(encoding="utf8"))

    def test_malformed_nested_wkb_is_atomic(self):
        with tempfile.TemporaryDirectory() as d:
            source = add_multilines(build(Path(d) / "source.gpkg"))
            valid = multiline(LINES)
            invalid = [b"bad", valid[:-1], valid + b"extra",
                       multiline(LINES, srid=9999), multiline([]),
                       multiline([[[2, 48]]])]
            wrong_type = bytearray(valid)
            struct.pack_into("<I", wrong_type, 17, 1)
            invalid.append(bytes(wrong_type))
            absurd_count = bytearray(valid)
            struct.pack_into("<I", absurd_count, 13, 9999)
            invalid.append(bytes(absurd_count))
            wrong_envelope = bytearray(multiline(LINES, envelope=True))
            struct.pack_into("<d", wrong_envelope, 16, 2.355)
            invalid.append(bytes(wrong_envelope))
            for i, damaged in enumerate(invalid):
                with self.subTest(index=i):
                    with sqlite3.connect(source) as db:
                        db.execute("UPDATE survey_multilines SET geom=? WHERE fid=41",
                                   (damaged,))
                    output = Path(d) / ("bad-" + str(i) + ".html")
                    done = self.cli(*self.args(source), "--output", output)
                    self.assertNotEqual(done.returncode, 0)
                    self.assertFalse(output.exists())

    def test_metadata_must_match_original_wkb_kind(self):
        with tempfile.TemporaryDirectory() as d:
            source = add_multilines(build(Path(d) / "source.gpkg"))
            with sqlite3.connect(source) as db:
                db.execute("UPDATE survey_multilines SET geom=? WHERE fid=41",
                           (line([(2.35, 48.85), (2.37, 48.86)]),))
            with self.assertRaises(ValueError):
                to_geojson(source, layer="survey_multilines")


if __name__ == "__main__":
    unittest.main()
