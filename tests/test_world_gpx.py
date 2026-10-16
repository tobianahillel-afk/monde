"""Actual original GPX -> evidence -> offline HTML, including mixed sources."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from monde.gpx_points import to_geojson
from monde.geojson import to_document
from monde.world import WorldMini

GPX = ('<?xml version="1.0"?><gpx xmlns="http://www.topografix.com/GPX/1/1" '
       'version="1.1" creator="survey">'
       '<wpt lat="48.8566" lon="2.3522"><name>site-alpha</name>'
       '<desc>Claim A</desc><time>2026-01-09T00:00:00Z</time></wpt>'
       '<wpt lat="40.7484" lon="-73.9857"><name>site-beta</name></wpt>'
       '</gpx>')
CAPTURED = "2026-01-10T10:00:00Z"
VALID = "2026-01-01T00:00:00Z"
AT = "2026-01-02T00:00:00Z"


class OriginalGPXTests(unittest.TestCase):
    def source(self, directory, text=GPX, name="original.gpx"):
        path = Path(directory) / name
        path.write_text(text, encoding="utf-8")
        return path

    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "monde.map_view",
                               *map(str, args)], capture_output=True, text=True,
                              env={**os.environ, "PYTHONPATH": str(
                                  Path(__file__).resolve().parents[1] / "src")})

    def flags(self, file):
        return ("--gpx", file, "--source-id", "original-gpx",
                "--source-locator", "dataset://survey/gpx",
                "--captured-at", CAPTURED, "--valid-from", VALID)

    def test_ids_time_coordinates_and_source_attribution(self):
        with tempfile.TemporaryDirectory() as directory:
            doc = to_geojson(self.source(directory))
            self.assertEqual([x["id"] for x in doc["features"]],
                             ["site-alpha", "site-beta"])
            self.assertEqual(doc["features"][0]["geometry"]["coordinates"],
                             [2.3522, 48.8566])
            self.assertEqual(doc["features"][0]["properties"]["waypoint_time"],
                             "2026-01-09T00:00:00Z")
            world = WorldMini.from_document(to_document(
                doc, source_id="original-gpx", locator="dataset://survey/gpx",
                captured_at=CAPTURED, valid_from=VALID))
            self.assertEqual(len(world.export_geojson_bbox(
                [-180, -90, 180, 90], AT, CAPTURED)["features"]), 2)

    def test_one_command_produces_real_offline_map(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self.source(directory)
            output = Path(directory) / "map.html"
            done = self.cli(*self.flags(source), "--at", AT,
                            "--known-at", CAPTURED, "--output", output)
            self.assertEqual(done.returncode, 0, done.stderr)
            page = output.read_text(encoding="utf-8")
            for word in ('"total_source_features":2', 'site-alpha',
                         'site-beta', 'original-gpx', 'dataset://survey/gpx'):
                self.assertIn(word, page)

    def test_gpx_geojson_manifest_preserves_source_disagreement(self):
        with tempfile.TemporaryDirectory() as directory:
            gpx = self.source(directory)
            geo = Path(directory) / "other.geojson"
            geo.write_text(json.dumps({"type": "FeatureCollection", "features": [{
                "type": "Feature", "id": "site-alpha", "properties": {},
                "geometry": {"type": "Point", "coordinates": [12.0, 45.0]}
            }]}), encoding="utf-8")
            common = {"locator": "dataset://claim", "captured_at": CAPTURED,
                      "valid_from": VALID}
            manifest = Path(directory) / "sources.json"
            manifest.write_text(json.dumps({"datasets": [
                {**common, "gpx": gpx.name, "source_id": "gpx-source"},
                {**common, "geojson": geo.name, "source_id": "geo-source"}
            ]}), encoding="utf-8")
            out = Path(directory) / "map.html"
            done = self.cli("--source-manifest", manifest, "--at", AT,
                            "--known-at", CAPTURED, "--output", out)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn('"total_source_features":3', out.read_text(encoding="utf-8"))

    def test_unsupported_inputs_rejected_without_output(self):
        with tempfile.TemporaryDirectory() as directory:
            for bad in [
                GPX.replace("<name>site-alpha</name>", ""),
                GPX.replace("<name>site-alpha</name>", "<name>site-beta</name>"),
                GPX.replace("<name>site-alpha</name>", "<name>has spaces</name>"),
                GPX.replace('lat="48.8566"', 'lat="inf"'),
                GPX.replace('lon="2.3522"', 'lon="181"'),
                GPX.replace('<desc>Claim A</desc>', '<ele>12</ele>'),
                GPX.replace('</gpx>', '<trk/><rte/></gpx>'),
                GPX.replace('<time>2026-01-09T00:00:00Z</time>',
                            '<time>invalid</time>'),
                '<!DOCTYPE gpx [<!ENTITY xx "data">]>' + GPX,
            ]:
                with self.subTest(bad=bad[:70]):
                    source = self.source(directory, bad)
                    with self.assertRaises(ValueError):
                        to_geojson(source)
                    output = Path(directory) / "invalid.html"
                    self.assertNotEqual(self.cli(*self.flags(source), "--at", AT,
                                                 "--known-at", CAPTURED, "--output",
                                                 output).returncode, 0)
                    self.assertFalse(output.exists())

    def test_existing_source_or_output_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self.source(directory)
            old = source.read_bytes()
            self.assertNotEqual(self.cli(*self.flags(source), "--at", AT,
                                         "--known-at", CAPTURED, "--output",
                                         source).returncode, 0)
            self.assertEqual(old, source.read_bytes())
            out = Path(directory) / "map.html"
            out.write_text("keep", encoding="utf-8")
            self.assertNotEqual(self.cli(*self.flags(source), "--at", AT,
                                         "--known-at", CAPTURED, "--output",
                                         out).returncode, 0)
            self.assertEqual(out.read_text(encoding="utf-8"), "keep")

    def test_second_invalid_source_aborts_manifest_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            good = self.source(directory)
            bad = self.source(directory, GPX.replace("<name>site-alpha</name>", ""),
                              name="bad.gpx")
            common = {"locator": "dataset://claim", "captured_at": CAPTURED,
                      "valid_from": VALID}
            manifest = Path(directory) / "sources.json"
            manifest.write_text(json.dumps({"datasets": [
                {**common, "gpx": good.name, "source_id": "good"},
                {**common, "gpx": bad.name, "source_id": "bad"}
            ]}), encoding="utf-8")
            out = Path(directory) / "not-created.html"
            self.assertNotEqual(self.cli("--source-manifest", manifest, "--at", AT,
                                         "--known-at", CAPTURED, "--output",
                                         out).returncode, 0)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
