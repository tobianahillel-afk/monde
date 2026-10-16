"""Real local KMZ original-source evidence in MONDE Mini maps."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from monde.kml_points import to_geojson
from monde.geojson import to_document
from monde.world import WorldMini

KML = ('<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
       '<Placemark id="survey"><name>Original survey</name>'
       '<MultiGeometry>'
       '<Point><coordinates>2.3522,48.8566</coordinates></Point>'
       '<LineString><coordinates>2.3522,48.8566 2.36,48.86</coordinates></LineString>'
       '</MultiGeometry></Placemark></Document></kml>')
AT = "2026-01-02T00:00:00Z"
CAPTURED = "2026-01-10T10:00:00Z"


class KMZTests(unittest.TestCase):
    def zip(self, directory, entries=None, name="survey.kmz"):
        target = Path(directory) / name
        if entries is None:
            entries = [("doc.kml", KML), ("images/notes.txt", "supporting asset")]
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            for filename, content in entries:
                archive.writestr(filename, content)
        return target

    def cmd(self, *args):
        return subprocess.run([sys.executable, "-m", "monde.map_view", *map(str, args)],
                              capture_output=True, text=True,
                              env={**os.environ, "PYTHONPATH": str(
                                  Path(__file__).resolve().parents[1] / "src")})

    def flags(self, source):
        return ("--kmz", source, "--source-id", "survey-source",
                "--source-locator", "dataset://survey.kmz",
                "--captured-at", CAPTURED, "--valid-from", "2026-01-01T00:00:00Z")

    def test_kmz_equals_plain_kml_and_preserves_bitemporal_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = self.zip(directory)
            plain = Path(directory) / "survey.kml"
            plain.write_text(KML, encoding="utf8")
            geo = to_geojson(archive, kmz=True)
            self.assertEqual(geo, to_geojson(plain))
            self.assertEqual(len(geo["features"]), 3)
            self.assertEqual(len({f["id"] for f in geo["features"]}), 3)
            doc = to_document(geo, source_id="survey-source",
                              locator="dataset://survey.kmz", captured_at=CAPTURED,
                              valid_from="2026-01-01T00:00:00Z")
            collection = WorldMini.from_document(doc).export_geojson_bbox(
                [-180, -90, 180, 90], AT, CAPTURED)
            self.assertEqual(len(collection["features"]), 3)
            self.assertEqual(len({f["properties"]["evidence_id"]
                                  for f in collection["features"]}), 3)

    def test_direct_kmz_cli_produces_offline_map_without_modifying_source(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = self.zip(directory)
            before = archive.read_bytes()
            output = Path(directory) / "map.html"
            result = self.cmd(*self.flags(archive), "--at", AT,
                              "--known-at", CAPTURED, "--output", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            page = output.read_text(encoding="utf8")
            for marker in ('"total_source_features":3', 'Original survey',
                           'survey-source', 'dataset://survey.kmz',
                           'KML_2_2_LINESTRING_POINT'):
                self.assertIn(marker, page)
            self.assertNotIn("https://tile.", page)
            self.assertEqual(archive.read_bytes(), before)
            fail = self.cmd(*self.flags(archive), "--at", AT, "--known-at",
                            CAPTURED, "--output", archive)
            self.assertNotEqual(fail.returncode, 0)
            self.assertEqual(archive.read_bytes(), before)

    def test_manifest_combines_kmz_with_competing_geojson_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            self.zip(directory)
            other = Path(directory) / "other.geojson"
            other.write_text(json.dumps({"type": "FeatureCollection", "features": [{
                "type": "Feature", "id": "survey", "properties": {},
                "geometry": {"type": "Point", "coordinates": [3, 49]}
            }]}), encoding="utf8")
            common = {"locator": "dataset://source", "captured_at": CAPTURED,
                      "valid_from": "2026-01-01T00:00:00Z"}
            manifest = Path(directory) / "manifest.json"
            manifest.write_text(json.dumps({"datasets": [
                {**common, "kmz": "survey.kmz", "source_id": "kmz-source"},
                {**common, "geojson": "other.geojson", "source_id": "geojson-source"}
            ]}), encoding="utf8")
            output = Path(directory) / "combined.html"
            run = self.cmd("--source-manifest", manifest, "--at", AT,
                           "--known-at", CAPTURED, "--output", output)
            self.assertEqual(run.returncode, 0, run.stderr)
            page = output.read_text(encoding="utf8")
            self.assertIn('"total_source_features":4', page)
            self.assertIn("kmz-source", page)
            self.assertIn("geojson-source", page)

    def test_invalid_archives_fail_atomically(self):
        invalid = [
            [("other.kml", KML)],
            [("doc.kml", KML), ("other.kml", KML)],
            [("../doc.kml", KML)],
            [("doc.kml", KML), ("../evil.txt", "X")],
            [("doc.kml", KML), ("doc.kml", KML)],
            [("doc.kml", KML.replace("2.3522,48.8566", "200,48.8566"))],
            [("doc.kml", "<!DOCTYPE kml [<!ENTITY a 'b'>]><kml/>")],
            [("doc.kml", KML.replace("</Document>",
                "<NetworkLink><name>remote</name></NetworkLink></Document>"))],
            [("doc.kml", "garbage XML")],
            [("doc.kml", " " * 10_000_001)]
        ]
        with tempfile.TemporaryDirectory() as directory:
            for index, entries in enumerate(invalid):
                with self.subTest(case=index):
                    archive = self.zip(directory, entries, str(index) + ".kmz")
                    target = Path(directory) / (str(index) + ".html")
                    with self.assertRaises(ValueError):
                        to_geojson(archive, kmz=True)
                    result = self.cmd(*self.flags(archive), "--at", AT,
                                      "--known-at", CAPTURED, "--output", target)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(target.exists())

    def test_malformed_zip_and_missing_provenance_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = self.zip(directory)
            archive.write_bytes(archive.read_bytes()[:40])
            with self.assertRaises(ValueError):
                to_geojson(archive, kmz=True)
            archive = self.zip(directory)
            r = self.cmd("--kmz", archive, "--at", AT,
                         "--known-at", CAPTURED, "--output",
                         Path(directory) / "not-created.html")
            self.assertNotEqual(r.returncode, 0)

    def test_manifest_mixed_source_type_is_rejected_without_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            self.zip(directory)
            manifest = Path(directory) / "manifest.json"
            manifest.write_text(json.dumps({"datasets": [{
                "source_id": "x", "locator": "dataset://x", "captured_at": CAPTURED,
                "valid_from": "2026-01-01T00:00:00Z",
                "kmz": "survey.kmz", "kml": "survey.kmz"}]}), encoding="utf8")
            output = Path(directory) / "preserve.html"
            output.write_text("PRESERVE", encoding="utf8")
            run = self.cmd("--source-manifest", manifest, "--at", AT,
                           "--known-at", CAPTURED, "--output", output)
            self.assertNotEqual(run.returncode, 0)
            self.assertEqual(output.read_text(encoding="utf8"), "PRESERVE")


if __name__ == "__main__":
    unittest.main()
