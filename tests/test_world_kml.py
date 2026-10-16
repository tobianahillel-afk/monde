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
                            '<Polygon><coordinates>2,48 3,49</coordinates></Polygon>'),
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


    def test_original_polygon_outer_ring_retains_closed_vertex_evidence(self):
        poly = ('<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
                '<Placemark id="block"><name>Source-declared boundary</name>'
                '<Polygon><outerBoundaryIs><LinearRing><coordinates>'
                '2.35,48.85 2.36,48.85 2.36,48.86 2.35,48.85'
                '</coordinates></LinearRing></outerBoundaryIs></Polygon>'
                '</Placemark></Document></kml>')
        with tempfile.TemporaryDirectory() as directory:
            path = self.fixture(directory, poly)
            geo = to_geojson(path)
            self.assertEqual(geo, to_geojson(path))
            features = geo["features"]
            self.assertEqual(len(features), 4)
            self.assertEqual(len({f["id"] for f in features}), 4)
            self.assertEqual(features[-1]["geometry"]["coordinates"],
                             features[0]["geometry"]["coordinates"])
            self.assertTrue(features[-1]["id"].endswith("-repeat-2"))
            self.assertEqual([f["properties"]["kml_trace"]["order"]
                              for f in features], [0, 1, 2, 3])
            self.assertTrue(all(f["properties"]["kml_trace"]["kind"] == "Polygon"
                                for f in features))
            doc = to_document(geo, source_id="claimed-block",
                              locator="dataset://unverified-boundary.kml",
                              captured_at=CAPTURED,
                              valid_from="2026-01-01T00:00:00Z")
            observed = WorldMini.from_document(doc).export_geojson_bbox(
                [-180, -90, 180, 90], AT, CAPTURED)["features"]
            self.assertEqual(len(observed), 4)
            self.assertEqual(len({f["properties"]["evidence_id"] for f in observed}), 4)
            self.assertTrue(all(f["properties"]["source_id"] == "claimed-block"
                                and f["properties"]["monde_kml_trace"]["kind"] == "Polygon"
                                and f["properties"]["monde_status"] == "SOURCE_REPORTED_ONLY"
                                for f in observed))

    def test_source_polygon_to_offline_map_without_network_or_saved_state(self):
        source = ('<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
                  '<Placemark id="claimed-area"><name>Reported border only</name>'
                  '<Polygon><outerBoundaryIs><LinearRing><coordinates>'
                  '2.35,48.85 2.36,48.85 2.36,48.86 2.35,48.85'
                  '</coordinates></LinearRing></outerBoundaryIs></Polygon>'
                  '</Placemark></Document></kml>')
        with tempfile.TemporaryDirectory() as directory:
            path = self.fixture(directory, source)
            output = Path(directory) / "boundary.html"
            result = self.cli(*self.flags(path), "--at", AT,
                              "--known-at", CAPTURED, "--output", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            page = output.read_text(encoding="utf-8")
            for expected in ('"total_source_features":4',
                             'KML_2_2_POLYGON_RING_POINT',
                             'data-monde-kml-boundary-segments',
                             'data-kml-boundary', 'claimed-area',
                             'Reported border only'):
                self.assertIn(expected, page)
            self.assertNotIn('https://tile.', page)

    def test_polygon_rejects_holes_open_rings_three_dimensions_and_multiple_shapes(self):
        open_boundary = (
            '<Polygon><outerBoundaryIs><LinearRing><coordinates>'
            '2.35,48.85 2.36,48.85 2.36,48.86 2.35,48.85'
            '</coordinates></LinearRing></outerBoundaryIs></Polygon>')
        samples = [
            open_boundary.replace('2.35,48.85</coordinates>',
                                  '2.36,48.87</coordinates>'),
            open_boundary.replace('2.36,48.86', '2.36,48.86,12'),
            open_boundary.replace('2.36,48.86', '2.35,48.85'),
            open_boundary.replace('</Polygon>', '<innerBoundaryIs/>'
                                  '</Polygon>'),
            open_boundary.replace('</Polygon>', '<altitudeMode>absolute'
                                  '</altitudeMode></Polygon>'),
            open_boundary.replace('outerBoundaryIs', 'innerBoundaryIs'),
            open_boundary.replace('<LinearRing>', '<LinearRing id="x">'),
            open_boundary + open_boundary,
        ]
        with tempfile.TemporaryDirectory() as directory:
            for i, geometry in enumerate(samples):
                xml = ('<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
                       '<Placemark id="boundary">' + geometry +
                       '</Placemark></Document></kml>')
                path = self.fixture(directory, xml, str(i) + ".kml")
                with self.subTest(index=i):
                    with self.assertRaises(ValueError):
                        to_geojson(path)
                    target = Path(directory) / ("unexpected-%d.html" % i)
                    outcome = self.cli(*self.flags(path), "--at", AT,
                                       "--known-at", CAPTURED, "--output", target)
                    self.assertNotEqual(outcome.returncode, 0)
                    self.assertFalse(target.exists())

    def test_polygon_and_line_use_separate_source_ids_with_no_inferred_fill(self):
        polygon = ('<Polygon><outerBoundaryIs><LinearRing><coordinates>'
                   '2.35,48.85 2.36,48.85 2.36,48.86 2.35,48.85'
                   '</coordinates></LinearRing></outerBoundaryIs></Polygon>')
        line = ('<LineString><coordinates>2.35,48.85 2.36,48.85'
                '</coordinates></LineString>')
        xml = ('<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
               '<Placemark id="area">' + polygon + '</Placemark>'
               '<Placemark id="line">' + line + '</Placemark>'
               '</Document></kml>')
        with tempfile.TemporaryDirectory() as directory:
            result = to_geojson(self.fixture(directory, xml))
            self.assertEqual(len(result["features"]), 6)
            ids = [f["id"] for f in result["features"]]
            self.assertEqual(len(set(ids)), 6)
            self.assertEqual(sum("kml-boundary-" in x for x in ids), 4)
            self.assertEqual(sum("kml-line-" in x for x in ids), 2)

    def test_polygon_inner_rings_keep_order_role_ids_and_bitemporal_evidence(self):
        outer = "2.35,48.85 2.37,48.85 2.37,48.87 2.35,48.85"
        inner = "2.355,48.855 2.365,48.855 2.365,48.865 2.355,48.855"
        xml = ('<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
               '<Placemark id="reported-zone"><name>Unverified area with hole</name>'
               '<Polygon><outerBoundaryIs><LinearRing><coordinates>' + outer +
               '</coordinates></LinearRing></outerBoundaryIs>'
               '<innerBoundaryIs><LinearRing><coordinates>' + inner +
               '</coordinates></LinearRing></innerBoundaryIs></Polygon>'
               '</Placemark></Document></kml>')
        with tempfile.TemporaryDirectory() as directory:
            source = self.fixture(directory, xml)
            features = to_geojson(source)["features"]
            self.assertEqual(features, to_geojson(source)["features"])
            self.assertEqual(len(features), 8)
            self.assertEqual(len({f["id"] for f in features}), 8)
            traces = [f["properties"]["kml_trace"] for f in features]
            self.assertEqual([t["segment"] for t in traces], [0]*4 + [1]*4)
            self.assertEqual([t["order"] for t in traces], list(range(4))*2)
            self.assertEqual(len({t["trace_id"] for t in traces}), 1)
            self.assertEqual([f["geometry"]["coordinates"] for f in features[4:]],
                             [[2.355,48.855],[2.365,48.855],
                              [2.365,48.865],[2.355,48.855]])
            doc = to_document({"type":"FeatureCollection","features":features},
                              source_id="reported-zone-source",
                              locator="dataset://original-zone.kml",
                              captured_at=CAPTURED,
                              valid_from="2026-01-01T00:00:00Z")
            visible = WorldMini.from_document(doc).export_geojson_bbox(
                [-180,-90,180,90],AT,CAPTURED)["features"]
            self.assertEqual(len(visible), 8)
            self.assertEqual({x["properties"]["monde_kml_trace"]["segment"]
                              for x in visible}, {0,1})
            self.assertEqual(len({x["properties"]["evidence_id"] for x in visible}),8)
            self.assertTrue(all(x["properties"]["source_id"]=="reported-zone-source"
                                and x["properties"]["monde_status"]=="SOURCE_REPORTED_ONLY"
                                for x in visible))
            output=Path(directory)/"zone.html"
            run=self.cli(*self.flags(source),"--at",AT,"--known-at",CAPTURED,
                         "--output",output)
            self.assertEqual(run.returncode,0,run.stderr)
            html=output.read_text(encoding="utf-8")
            for marker in ('data-kml-inner-ring','data-monde-kml-inner-segments',
                           'Source-declared ring:',"Unverified area with hole"):
                self.assertIn(marker,html)
            self.assertNotIn("https://tile.",html)

    def test_polygon_multiple_inner_rings_do_not_join_other_ring_evidence(self):
        outer="2.35,48.85 2.39,48.85 2.39,48.89 2.35,48.85"
        hole1="2.353,48.853 2.355,48.853 2.355,48.855 2.353,48.853"
        hole2="2.373,48.873 2.375,48.873 2.375,48.875 2.373,48.873"
        rings=('<outerBoundaryIs><LinearRing><coordinates>'+outer+
               '</coordinates></LinearRing></outerBoundaryIs>'+
               '<innerBoundaryIs><LinearRing><coordinates>'+hole1+
               '</coordinates></LinearRing></innerBoundaryIs>'+
               '<innerBoundaryIs><LinearRing><coordinates>'+hole2+
               '</coordinates></LinearRing></innerBoundaryIs>')
        xml=('<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
             '<Placemark id="zone"><Polygon>'+rings+
             '</Polygon></Placemark></Document></kml>')
        with tempfile.TemporaryDirectory() as directory:
            features=to_geojson(self.fixture(directory,xml))["features"]
            self.assertEqual(len(features),12)
            self.assertEqual([f["properties"]["kml_trace"]["segment"]
                              for f in features],[0]*4+[1]*4+[2]*4)
            self.assertEqual([f["properties"]["kml_trace"]["order"]
                              for f in features],list(range(4))*3)
            self.assertEqual(len({f["id"] for f in features}),12)

    def test_polygon_inner_ring_invalidity_rejects_entire_source_atomically(self):
        outer=('<outerBoundaryIs><LinearRing><coordinates>'
               '2.35,48.85 2.39,48.85 2.39,48.89 2.35,48.85'
               '</coordinates></LinearRing></outerBoundaryIs>')
        inner=('<innerBoundaryIs><LinearRing><coordinates>'
               '2.36,48.86 2.37,48.86 2.37,48.87 2.36,48.86'
               '</coordinates></LinearRing></innerBoundaryIs>')
        invalids=[
            inner.replace('2.36,48.86</coordinates>','2.38,48.86</coordinates>'),
            inner.replace('2.37,48.87','2.37,48.87,9'),
            inner.replace('2.37,48.87','2.36,48.86'),
            '<innerBoundaryIs/>',
            inner.replace('innerBoundaryIs','outerBoundaryIs'),
            inner*129,
            inner.replace('<LinearRing>','<LinearRing id="wrong">')
        ]
        with tempfile.TemporaryDirectory() as directory:
            for i,bad in enumerate(invalids):
                xml=('<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
                     '<Placemark id="zone"><Polygon>'+outer+bad+
                     '</Polygon></Placemark></Document></kml>')
                path=self.fixture(directory,xml,str(i)+".kml")
                with self.subTest(index=i):
                    with self.assertRaises(ValueError):
                        to_geojson(path)
                    out=Path(directory)/("bad-"+str(i)+".html")
                    result=self.cli(*self.flags(path),"--at",AT,"--known-at",
                                    CAPTURED,"--output",out)
                    self.assertNotEqual(result.returncode,0)
                    self.assertFalse(out.exists())


    def test_multigeometry_mixed_source_components_to_world_and_offline_map(self):
        multi = ('<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
                 '<Placemark id="compound"><name>Source compound</name>'
                 '<MultiGeometry>'
                 '<Point><coordinates>2.35,48.85</coordinates></Point>'
                 '<LineString><coordinates>2.35,48.85 2.36,48.86 '
                 '2.37,48.87</coordinates></LineString>'
                 '<Polygon><outerBoundaryIs><LinearRing><coordinates>'
                 '2.35,48.85 2.37,48.85 2.37,48.87 2.35,48.85'
                 '</coordinates></LinearRing></outerBoundaryIs>'
                 '<innerBoundaryIs><LinearRing><coordinates>'
                 '2.353,48.853 2.356,48.853 2.356,48.856 2.353,48.853'
                 '</coordinates></LinearRing></innerBoundaryIs>'
                 '</Polygon></MultiGeometry></Placemark></Document></kml>')
        with tempfile.TemporaryDirectory() as directory:
            source = self.fixture(directory, multi)
            geo = to_geojson(source)
            self.assertEqual(geo, to_geojson(source))
            features = geo["features"]
            self.assertEqual(len(features), 12)
            self.assertEqual(len({f["id"] for f in features}), 12)
            self.assertTrue(features[0]["id"].startswith("kml-point-"))
            self.assertNotIn("kml_trace", features[0]["properties"])
            traces = [f["properties"]["kml_trace"] for f in features[1:]]
            self.assertEqual([t["kind"] for t in traces],
                             ["LineString"]*3 + ["Polygon"]*8)
            self.assertEqual(len({t["trace_id"] for t in traces[:3]}), 1)
            self.assertEqual(len({t["trace_id"] for t in traces[3:]}), 1)
            self.assertNotEqual(traces[0]["trace_id"], traces[3]["trace_id"])
            self.assertEqual([t["segment"] for t in traces[3:]], [0]*4 + [1]*4)
            doc = to_document(geo, source_id="compound-source",
                              locator="dataset://compound.kml",
                              captured_at=CAPTURED,
                              valid_from="2026-01-01T00:00:00Z")
            visible = WorldMini.from_document(doc).export_geojson_bbox(
                [-180, -90, 180, 90], AT, CAPTURED)["features"]
            self.assertEqual(len(visible), 12)
            self.assertEqual(len({f["properties"]["evidence_id"]
                                  for f in visible}), 12)
            self.assertTrue(all(f["properties"]["source_id"] == "compound-source"
                                and f["properties"]["monde_status"] ==
                                "SOURCE_REPORTED_ONLY" for f in visible))
            out = Path(directory) / "compound.html"
            completed = self.cli(*self.flags(source), "--at", AT,
                                 "--known-at", CAPTURED, "--output", out)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            html = out.read_text(encoding="utf-8")
            self.assertIn('KML_2_2_POLYGON_RING_POINT', html)
            self.assertIn('KML_2_2_LINESTRING_POINT', html)
            self.assertIn('Source compound', html)
            self.assertNotIn("https://tile.", html)

    def test_multigeometry_identical_components_have_distinct_source_traces(self):
        same = "<LineString><coordinates>2.35,48.85 2.36,48.86</coordinates></LineString>"
        content = ('<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
                   '<Placemark id="repeated"><MultiGeometry>' + same + same +
                   '</MultiGeometry></Placemark></Document></kml>')
        with tempfile.TemporaryDirectory() as directory:
            features = to_geojson(self.fixture(directory, content))["features"]
        self.assertEqual(len(features), 4)
        self.assertEqual(len({f["id"] for f in features}), 4)
        ids = [f["properties"]["kml_trace"]["trace_id"] for f in features]
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(ids[2], ids[3])
        self.assertNotEqual(ids[0], ids[2])
        self.assertEqual([f["properties"]["kml_trace"]["order"]
                          for f in features], [0, 1, 0, 1])

    def test_multigeometry_fail_closed_for_unsupported_or_ambiguous_components(self):
        point = "<Point><coordinates>2.35,48.85</coordinates></Point>"
        line = "<LineString><coordinates>2.35,48.85 2.36,48.86</coordinates></LineString>"
        invalid = [
            '<MultiGeometry/>',
            '<MultiGeometry>' + point * 33 + '</MultiGeometry>',
            '<MultiGeometry>' + point +
            '<MultiGeometry>' + line + '</MultiGeometry></MultiGeometry>',
            '<MultiGeometry>' + point + '<Model/></MultiGeometry>',
            '<MultiGeometry id="surprise">' + point + '</MultiGeometry>',
            '<MultiGeometry>' + point.replace('2.35,48.85', '200,48.85') +
            '</MultiGeometry>',
            '<MultiGeometry>' + line.replace('2.36,48.86', '2.36,48.86,10') +
            '</MultiGeometry>',
            '<MultiGeometry>' + point + '</MultiGeometry>' + point,
        ]
        with tempfile.TemporaryDirectory() as directory:
            for i, geometry in enumerate(invalid):
                source = self.fixture(
                    directory, '<kml xmlns="http://www.opengis.net/kml/2.2">'
                    '<Document><Placemark id="invalid">' + geometry +
                    '</Placemark></Document></kml>', str(i) + ".kml")
                output = Path(directory) / ("invalid-%d.html" % i)
                with self.subTest(case=i):
                    with self.assertRaises(ValueError):
                        to_geojson(source)
                    completed = self.cli(*self.flags(source), "--at", AT,
                                         "--known-at", CAPTURED, "--output", output)
                    self.assertNotEqual(completed.returncode, 0)
                    self.assertFalse(output.exists())

    def test_multigeometry_source_ids_do_not_change_legacy_geometry_contracts(self):
        sample = '<LineString><coordinates>2.35,48.85 2.36,48.86</coordinates></LineString>'
        root = ('<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
                '<Placemark id="legacy">' + sample + '</Placemark></Document></kml>')
        wrapped = ('<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
                   '<Placemark id="legacy"><MultiGeometry>' + sample +
                   '</MultiGeometry></Placemark></Document></kml>')
        with tempfile.TemporaryDirectory() as directory:
            legacy = to_geojson(self.fixture(directory, root, "legacy.kml"))
            compound = to_geojson(self.fixture(directory, wrapped, "wrapped.kml"))
        self.assertEqual(len(legacy["features"]), 2)
        self.assertEqual(len(compound["features"]), 2)
        self.assertEqual(len({f["id"] for f in compound["features"]}), 2)
        self.assertNotEqual(legacy["features"][0]["id"], compound["features"][0]["id"])
        self.assertEqual([f["geometry"]["coordinates"] for f in legacy["features"]],
                         [f["geometry"]["coordinates"] for f in compound["features"]])

if __name__ == "__main__":
    unittest.main()
