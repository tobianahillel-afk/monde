"""Original KML Point ingestion and full offline-map user paths."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from monde.kml_points import to_geojson
from monde.geojson import to_document
from monde.world import WorldMini

CAPTURED = "2026-01-10T10:00:00Z"
AT = "2026-01-02T00:00:00Z"
KML = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<kml xmlns=\"http://www.opengis.net/kml/2.2\"><Document>\n<Placemark id=\"place-a\"><name>Alpha</name><Point><coordinates>2.3522,48.8566</coordinates></Point></Placemark>\n<Placemark id=\"place-b\"><name>Beta</name><Point><coordinates>-73.9857,40.7484</coordinates></Point></Placemark>\n</Document></kml>\n"


class KMLSourceTests(unittest.TestCase):
    def fixture(self, folder, content=KML, name="original.kml"):
        path = Path(folder) / name
        path.write_text(content, encoding="utf-8")
        return path

    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "monde.map_view",
                               *map(str, args)], text=True, capture_output=True,
                              env={**os.environ, "PYTHONPATH": str(
                                  Path(__file__).resolve().parents[1] / "src")})

    def flags(self, source):
        return ("--kml", source, "--source-id", "original-kml",
                "--source-locator", "dataset://original.kml",
                "--captured-at", CAPTURED, "--valid-from", "2026-01-01T00:00:00Z")

    def test_evidence_preserves_original_kml_ids_and_coordinates(self):
        with tempfile.TemporaryDirectory() as directory:
            geo = to_geojson(self.fixture(directory))
            self.assertEqual([f["id"] for f in geo["features"]], ["place-a", "place-b"])
            self.assertEqual(geo["features"][0]["geometry"]["coordinates"], [2.3522, 48.8566])
            doc = to_document(geo, source_id="original-kml", locator="dataset://kml",
                              captured_at=CAPTURED, valid_from="2026-01-01T00:00:00Z")
            self.assertEqual(len(doc["evidence"]), 2)
            self.assertEqual(len(WorldMini.from_document(doc).export_geojson_bbox(
                [-180, -90, 180, 90], AT, CAPTURED)["features"]), 2)

    def test_one_command_outputs_standalone_map_without_saved_state(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self.fixture(directory)
            out = Path(directory) / "map.html"
            done = self.cli(*self.flags(source), "--at", AT, "--known-at",
                            CAPTURED, "--output", out)
            self.assertEqual(done.returncode, 0, done.stderr)
            rendered = out.read_text(encoding="utf-8")
            for key in ('"total_source_features":2', 'original-kml',
                        'place-a', 'place-b', 'dataset://original.kml',
                        'id="export-visible-csv"'):
                self.assertIn(key, rendered)

    def test_multi_source_kml_and_geojson_keep_competing_claims(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self.fixture(directory)
            geo = Path(directory) / "other.geojson"
            geo.write_text(json.dumps({"type":"FeatureCollection","features":[{
                "type":"Feature","id":"place-a","properties":{},
                "geometry":{"type":"Point","coordinates":[6.1,44.3]}
            }]}), encoding="utf-8")
            manifest = Path(directory) / "sources.json"
            common = {"locator": "dataset://survey", "captured_at": CAPTURED,
                      "valid_from": "2026-01-01T00:00:00Z"}
            manifest.write_text(json.dumps({"datasets":[
                {**common,"kml":source.name,"source_id":"source-kml"},
                {**common,"geojson":geo.name,"source_id":"source-geojson"}
            ]}), encoding="utf-8")
            out=Path(directory)/"combined.html"
            result=self.cli("--source-manifest",manifest,"--at",AT,"--known-at",
                            CAPTURED,"--output",out)
            self.assertEqual(result.returncode,0,result.stderr)
            page=out.read_text(encoding="utf-8")
            for key in ('"total_source_features":3','source-kml','source-geojson'):
                self.assertIn(key,page)

    def test_rejects_unknown_geometry_missing_ids_altitude_remote_dtd(self):
        with tempfile.TemporaryDirectory() as directory:
            source=self.fixture(directory)
            invalid=[
                KML.replace('id="place-a"',''),
                KML.replace('id="place-b"','id="place-a"'),
                KML.replace('2.3522,48.8566','2.3522,48.8566,35'),
                KML.replace('2.3522,48.8566','181,48.8566'),
                KML.replace('<Point><coordinates>2.3522,48.8566</coordinates></Point>',
                            '<LineString><coordinates>2,48 3,49</coordinates></LineString>'),
                KML.replace('</Document>','<NetworkLink><name>remote</name></NetworkLink></Document>'),
                KML.replace('<name>Alpha</name>','<ExtendedData/><name>Alpha</name>'),
                '<!DOCTYPE kml [<!ENTITY xx "boom">]><kml/>'
            ]
            for value in invalid:
                with self.subTest(value=value[:50]):
                    source.write_text(value,encoding="utf-8")
                    with self.assertRaises(ValueError):
                        to_geojson(source)
                    output=Path(directory)/"never.html"
                    self.assertNotEqual(self.cli(*self.flags(source),"--at",AT,
                                                 "--known-at",CAPTURED,"--output",
                                                 output).returncode,0)
                    self.assertFalse(output.exists())

    def test_missing_provenance_and_existing_input_or_output_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            source=self.fixture(directory)
            original=source.read_bytes()
            self.assertNotEqual(self.cli("--kml",source,"--at",AT,
                                         "--known-at",CAPTURED,"--output",
                                         Path(directory)/"missing.html").returncode,0)
            self.assertNotEqual(self.cli(*self.flags(source),"--at",AT,
                                         "--known-at",CAPTURED,"--output",source).returncode,0)
            self.assertEqual(source.read_bytes(),original)
            existing=Path(directory)/"existing.html"
            existing.write_text("KEEP",encoding="utf-8")
            self.assertNotEqual(self.cli(*self.flags(source),"--at",AT,
                                         "--known-at",CAPTURED,"--output",existing).returncode,0)
            self.assertEqual(existing.read_text(encoding="utf-8"),"KEEP")

    def test_invalid_second_source_is_atomic_and_formats_are_exclusive(self):
        with tempfile.TemporaryDirectory() as directory:
            good=self.fixture(directory)
            bad=self.fixture(directory,KML.replace('id="place-b"','id="place-a"'),
                             "bad.kml")
            manifest=Path(directory)/"sources.json"
            common={"locator":"dataset://source","captured_at":CAPTURED,
                    "valid_from":"2026-01-01T00:00:00Z"}
            for entries in [
                [{**common,"kml":good.name,"source_id":"A"},
                 {**common,"kml":bad.name,"source_id":"B"}],
                [{**common,"kml":good.name,"geojson":good.name,"source_id":"A"}],
                [{**common,"kml":good.name,"id_column":"name","source_id":"A"}]]:
                manifest.write_text(json.dumps({"datasets":entries}),encoding="utf-8")
                out=Path(directory)/"never.html"
                r=self.cli("--source-manifest",manifest,"--at",AT,
                           "--known-at",CAPTURED,"--output",out)
                self.assertNotEqual(r.returncode,0)
                self.assertFalse(out.exists())


    def test_original_linestring_retains_distinct_same_source_sample_evidence(self):
        line = ('<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
                '<Placemark id="line-a"><name>Original survey line</name>'
                '<LineString><coordinates>2.35,48.85 2.36,48.86 '
                '2.36,48.86 2.37,48.87</coordinates></LineString>'
                '</Placemark></Document></kml>')
        with tempfile.TemporaryDirectory() as directory:
            file = self.fixture(directory, line)
            first = to_geojson(file)
            self.assertEqual(first, to_geojson(file))
            self.assertEqual(len(first["features"]), 4)
            ids = [v["id"] for v in first["features"]]
            self.assertEqual(len(set(ids)), 4)
            self.assertTrue(ids[2].endswith("-repeat-2"))
            self.assertEqual([v["properties"]["kml_trace"]["order"]
                              for v in first["features"]], [0, 1, 2, 3])
            document = to_document(first, source_id="kml-survey",
                                   locator="dataset://survey.kml",
                                   captured_at=CAPTURED,
                                   valid_from="2026-01-01T00:00:00Z")
            features = WorldMini.from_document(document).export_geojson_bbox(
                [-180, -90, 180, 90], AT, CAPTURED)["features"]
            self.assertEqual(len(features), 4)
            for feature in features:
                self.assertEqual(feature["properties"]["source_id"], "kml-survey")
                self.assertEqual(feature["properties"]["monde_kml_trace"]["trace_id"],
                                 first["features"][0]["properties"]["kml_trace"]["trace_id"])
                self.assertEqual(feature["properties"]["monde_status"],
                                 "SOURCE_REPORTED_ONLY")
            self.assertEqual(len({f["properties"]["evidence_id"] for f in features}), 4)

    def test_linestring_source_to_offline_map_without_intermediate_state(self):
        line = ('<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
                '<Placemark id="segment"><name>Unverified path</name>'
                '<LineString><coordinates>2.35,48.85 2.36,48.86 '
                '2.37,48.87</coordinates></LineString></Placemark>'
                '</Document></kml>')
        with tempfile.TemporaryDirectory() as directory:
            source = self.fixture(directory, line)
            out = Path(directory) / "line.html"
            result = self.cli(*self.flags(source), "--at", AT,
                              "--known-at", CAPTURED, "--output", out)
            self.assertEqual(result.returncode, 0, result.stderr)
            html = out.read_text(encoding="utf-8")
            self.assertIn("data-monde-kml-segments", html)
            self.assertIn("KML_2_2_LINESTRING_POINT", html)
            self.assertIn("ORIGINAL_KML_SAMPLES_NOT_VERIFIED_MOTION", html)
            self.assertIn("Unverified path", html)
            self.assertEqual(source.read_text(encoding="utf-8"), line)

    def test_linestring_rejects_ambiguous_or_unsupported_geometry_atomically(self):
        original = ('<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
                    '<Placemark id="original-line"><LineString><coordinates>'
                    '2.35,48.85 2.36,48.86</coordinates></LineString>'
                    '</Placemark></Document></kml>')
        errors = [
            original.replace('2.36,48.86', '2.36,48.86,100'),
            original.replace('2.36,48.86', 'inf,48.86'),
            original.replace('2.36,48.86', '200,48.86'),
            original.replace('2.36,48.86', '2.35,48.85'),
            original.replace('2.35,48.85 2.36,48.86', '2.35,48.85'),
            original.replace('<LineString>', '<LineString><tessellate>1</tessellate>'),
            original.replace('id="original-line"', 'id=""'),
            original.replace('</Document>', '<Placemark id="original-line">'
                             '<Point><coordinates>2.3,48.8</coordinates></Point>'
                             '</Placemark></Document>'),
        ]
        # Repeated locations are valid original samples, not invalid geometry.
        errors.pop(3)
        with tempfile.TemporaryDirectory() as directory:
            file = self.fixture(directory, original)
            out = Path(directory) / "result.html"
            for invalid in errors:
                file.write_text(invalid, encoding="utf-8")
                with self.subTest(text=invalid[:55]):
                    with self.assertRaises(ValueError):
                        to_geojson(file)
                    run = self.cli(*self.flags(file), "--at", AT,
                                   "--known-at", CAPTURED, "--output", out)
                    self.assertNotEqual(run.returncode, 0)
                    self.assertFalse(out.exists())

    def test_linestring_and_original_point_placemarks_remain_separate(self):
        mixed = ('<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
                 '<Placemark id="place"><Point><coordinates>2.35,48.85'
                 '</coordinates></Point></Placemark>'
                 '<Placemark id="line"><LineString><coordinates>'
                 '2.35,48.85 2.36,48.86</coordinates></LineString>'
                 '</Placemark></Document></kml>')
        with tempfile.TemporaryDirectory() as directory:
            feature_set = to_geojson(self.fixture(directory, mixed))["features"]
            self.assertEqual(len(feature_set), 3)
            point = next(f for f in feature_set if f["id"] == "place")
            self.assertNotIn("kml_trace", point["properties"])
            self.assertEqual(len([f for f in feature_set
                                  if "kml_trace" in f["properties"]]), 2)

if __name__ == "__main__":
    unittest.main()
