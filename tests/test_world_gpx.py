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

TRACE_GPX = ('<?xml version="1.0"?>'
    '<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1" creator="survey">'
    '<rte><name>survey-route</name><desc>Only source-reported samples</desc>'
    '<rtept lat="48.850" lon="2.350"><name>point-a</name></rtept>'
    '<rtept lat="48.860" lon="2.360"><name>point-b</name></rtept>'
    '<rtept lat="48.865" lon="2.365"><name>point-c</name></rtept></rte>'
    '<trk><name>survey-track</name><trkseg>'
    '<trkpt lat="40.70" lon="-73.99"><time>2026-01-01T09:00:00Z</time></trkpt>'
    '<trkpt lat="40.71" lon="-73.98"><time>2026-01-01T09:01:00Z</time></trkpt>'
    '</trkseg><trkseg>'
    '<trkpt lat="40.72" lon="-73.97"><time>2026-01-01T10:00:00Z</time></trkpt>'
    '<trkpt lat="40.73" lon="-73.96"><time>2026-01-01T10:01:00Z</time></trkpt>'
    '</trkseg></trk></gpx>')

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
                GPX.replace('<desc>Claim A</desc>', '<ele>NaN</ele>'),
                GPX.replace('<desc>Claim A</desc>', '<ele>1e309</ele>'),
                GPX.replace('<desc>Claim A</desc>', '<ele>oops</ele>'),
                GPX.replace('<desc>Claim A</desc>', '<ele></ele>'),
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



    def test_source_clock_retains_exact_evidence_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self.source(directory, TRACE_GPX)
            original = to_geojson(source)
            world = WorldMini.from_document(to_document(original,
                source_id="clock", locator="dataset://clock",
                captured_at=CAPTURED, valid_from=VALID))
            features = world.export_geojson_bbox([-180, -90, 180, 90],
                                                 AT, CAPTURED)["features"]
            original_props = {f["id"]: f["properties"] for f in original["features"]}
            timed = [f for f in features if "monde_gpx_sample_time" in f["properties"]]
            self.assertEqual(len(timed), 4)
            for f in timed:
                p = f["properties"]
                self.assertEqual(p["monde_gpx_sample_time"],
                                 original_props[p["entity"]]["waypoint_time"])
                self.assertEqual(p["source_id"], "clock")
                self.assertIn("monde_gpx_trace", p)

    def test_source_clock_profile_present_in_offline_html(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self.source(directory, TRACE_GPX)
            output = Path(directory) / "trace-clock.html"
            done = self.cli(*self.flags(source), "--at", AT,
                            "--known-at", CAPTURED, "--output", output)
            self.assertEqual(done.returncode, 0, done.stderr)
            page = output.read_text(encoding="utf-8")
            self.assertIn("monde_gpx_sample_time", page)
            self.assertIn("source_timestamp_pairs", page)
            self.assertIn("reversed_source_timestamp_pair_count", page)
            self.assertIn("do not prove elapsed physical travel", page)

    def test_trace_segment_profile_control_is_emitted_for_real_gpx(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self.source(directory, TRACE_GPX)
            output = Path(directory) / "source-traces.html"
            done = self.cli(*self.flags(source), "--at", AT,
                            "--known-at", CAPTURED, "--output", output)
            self.assertEqual(done.returncode, 0, done.stderr)
            html = output.read_text(encoding="utf-8")
            self.assertIn('id="export-trace-profile"', html)
            self.assertIn("MONDE_MINI_GPX_SOURCE_SEGMENT_PROFILE_V1", html)
            self.assertIn("adjacent_pair_count", html)
            self.assertIn("original_reports:samples", html)

    def test_original_route_and_track_points_are_stable_source_samples(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self.source(directory, TRACE_GPX)
            doc = to_geojson(source)
            self.assertEqual(len(doc["features"]), 7)
            trace = [f for f in doc["features"]
                     if "gpx_trace" in f["properties"]]
            self.assertEqual(len(trace), 7)
            self.assertEqual([f["properties"]["gpx_trace"]["segment"] for f in trace],
                             [0, 0, 0, 0, 0, 1, 1])
            self.assertEqual([f["properties"]["gpx_trace"]["order"] for f in trace],
                             [0, 1, 2, 0, 1, 0, 1])
            self.assertEqual([f["id"] for f in trace],
                             [f["id"] for f in to_geojson(source)["features"]])
            self.assertEqual(len({f["id"] for f in trace}), 7)
            self.assertEqual(trace[3]["properties"]["waypoint_time"],
                             "2026-01-01T09:00:00Z")

    def test_bitemporal_source_trace_metadata_is_not_cross_source_merged(self):
        with tempfile.TemporaryDirectory() as directory:
            samples = to_geojson(self.source(directory, TRACE_GPX))
            world = WorldMini.from_document(to_document(
                samples, source_id="survey-original", locator="dataset://survey/trace",
                captured_at=CAPTURED, valid_from=VALID))
            mapped = world.export_geojson_bbox(
                [-180, -90, 180, 90], AT, CAPTURED)
            self.assertEqual(len(mapped["features"]), 7)
            for feature in mapped["features"]:
                self.assertEqual(feature["properties"]["source_id"], "survey-original")
                self.assertEqual(feature["properties"]["monde_gpx_trace"]["format"],
                                 "GPX_1_1_TRACE_POINT")
                self.assertEqual(feature["properties"]["monde_status"],
                                 "SOURCE_REPORTED_ONLY")
            early = world.export_geojson_bbox(
                [-180, -90, 180, 90], AT, "2026-01-09T00:00:00Z")
            self.assertEqual(early["features"], [])

    def test_one_command_original_traces_generate_offline_connected_map(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self.source(directory, TRACE_GPX)
            output = Path(directory) / "trace.html"
            run = self.cli(*self.flags(source), "--at", AT,
                           "--known-at", CAPTURED, "--output", output)
            self.assertEqual(run.returncode, 0, run.stderr)
            page = output.read_text(encoding="utf-8")
            for value in ('"total_source_features":7', 'survey-route',
                          'survey-track', 'dataset://survey/gpx',
                          'data-monde-gpx-segments', 'id="source-traces"'):
                self.assertIn(value, page)
            self.assertNotIn("https://", page)

    def test_invalid_and_ambiguous_traces_do_not_create_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            for bad in [
                TRACE_GPX.replace("<name>survey-route</name>", ""),
                TRACE_GPX.replace("<name>survey-route</name>",
                                  "<name>survey-route</name><name>survey-route</name>"),
                TRACE_GPX.replace("</rte>", "<rtept lat='48.850' lon='2.350'>"
                    "<name>point-a</name><name>duplicated-name</name>"
                    "</rtept></rte>"),
                TRACE_GPX.replace("<trkseg>", "<trkseg><extensions/>", 1),
                TRACE_GPX.replace("</trk>", "<extensions/></trk>"),
                TRACE_GPX.replace('lon="2.350"', 'lon="181"'),
                TRACE_GPX.replace("<rtept lat=", "<rtept ele='50' lat=", 1),
                TRACE_GPX.replace("</rte>", "</rte><rte><name>survey-route</name>"
                    "<rtept lat='50' lon='2'/></rte>")
            ]:
                with self.subTest(original=bad[-90:]):
                    source = self.source(directory, bad)
                    with self.assertRaises(ValueError):
                        to_geojson(source)
                    output = Path(directory) / "refuse.html"
                    run = self.cli(*self.flags(source), "--at", AT,
                                   "--known-at", CAPTURED, "--output", output)
                    self.assertNotEqual(run.returncode, 0)
                    self.assertFalse(output.exists())

    def test_source_trace_layers_never_invent_missing_segments(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self.source(directory, TRACE_GPX)
            doc = to_geojson(source)
            self.assertEqual(doc["features"][3]["properties"]["gpx_trace"]["order"], 0)
            self.assertEqual(doc["features"][5]["properties"]["gpx_trace"]["segment"], 1)
            self.assertNotEqual(doc["features"][3]["properties"]["gpx_trace"]["trace_id"],
                                doc["features"][0]["properties"]["gpx_trace"]["trace_id"])

    def test_gpxtype_rejects_remote_links_and_entities(self):
        with tempfile.TemporaryDirectory() as directory:
            for text in [TRACE_GPX.replace("</gpx>", "<extensions/></gpx>"),
                         '<!DOCTYPE gpx [<!ENTITY name SYSTEM "file:///etc/passwd">]>' + TRACE_GPX,
                         TRACE_GPX.replace("</gpx>", "<trk><name>x</name>"
                             "<trkseg/></trk></gpx>")]:
                with self.subTest(text=text[:65]):
                    with self.assertRaises(ValueError):
                        to_geojson(self.source(directory, text))


    def test_identical_stationary_readings_preserve_source_sample_order(self):
        with tempfile.TemporaryDirectory() as directory:
            original = TRACE_GPX.replace(
                '<trkpt lat="40.71" lon="-73.98">',
                '<trkpt lat="40.70" lon="-73.99"><time>'
                '2026-01-01T09:00:00Z</time></trkpt>'
                '<trkpt lat="40.71" lon="-73.98">', 1)
            source = self.source(directory, original)
            doc = to_geojson(source)
            self.assertEqual(len(doc["features"]), 8)
            track = [f for f in doc["features"]
                     if f["properties"].get("gpx_trace", {}).get("name") ==
                     "survey-track"]
            self.assertEqual(len(track), 5)
            self.assertNotEqual(track[0]["id"], track[1]["id"])
            self.assertEqual(track[1]["id"], track[0]["id"] + "-repeat-2")
            self.assertEqual(track[0]["geometry"], track[1]["geometry"])
            self.assertEqual([p["properties"]["gpx_trace"]["order"]
                              for p in track], [0, 1, 2, 0, 1])
            self.assertEqual([p["id"] for p in doc["features"]],
                             [p["id"] for p in to_geojson(source)["features"]])
            world = WorldMini.from_document(to_document(
                doc, source_id="stationary-gpx", locator="dataset://stationary",
                captured_at=CAPTURED, valid_from=VALID))
            self.assertEqual(len(world.export_geojson_bbox(
                [-180, -90, 180, 90], AT, CAPTURED)["features"]), 8)
            html = Path(directory) / "map.html"
            run = self.cli(*self.flags(source), "--at", AT,
                           "--known-at", CAPTURED, "--output", html)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn('"total_source_features":8',
                          html.read_text(encoding="utf-8"))

    def test_gpx_elevation_is_evidence_only_not_derived_altitude(self):
        with tempfile.TemporaryDirectory() as directory:
            source_text = TRACE_GPX.replace(
                '<trkpt lat="40.70" lon="-73.99">',
                '<trkpt lat="40.70" lon="-73.99"><ele>123.75</ele>', 1)
            source_text = source_text.replace(
                '<rtept lat="48.850" lon="2.350">',
                '<rtept lat="48.850" lon="2.350"><ele>-5.5</ele>', 1)
            source_text = source_text.replace(
                '<rtept lat="48.865" lon="2.365">',
                '<rtept lat="48.865" lon="2.365"><ele>0</ele>', 1)
            source = self.source(directory, source_text)
            features = to_geojson(source)["features"]
            self.assertEqual(features[0]["properties"]["elevation_m"], -5.5)
            self.assertEqual(features[2]["properties"]["elevation_m"], 0.0)
            self.assertEqual(features[3]["properties"]["elevation_m"], 123.75)
            self.assertEqual(features[3]["geometry"]["coordinates"],
                             [-73.99, 40.70])
            world = WorldMini.from_document(to_document(
                {"type": "FeatureCollection", "features": features},
                source_id="elev-gpx", locator="dataset://elev",
                captured_at=CAPTURED, valid_from=VALID))
            report = world.query(features[3]["id"], "elevation_m", AT, CAPTURED)
            self.assertEqual(report["status"], "REPORTED")
            self.assertEqual(report["reports"][0]["value"], 123.75)
            self.assertEqual(report["reports"][0]["source_id"], "elev-gpx")
            mapped = world.export_geojson_bbox([-180, -90, 180, 90], AT, CAPTURED)
            by_entity = {f["properties"]["entity"]: f for f in mapped["features"]}
            for original in (features[0], features[2], features[3]):
                linked = by_entity[original["id"]]
                source_elevation = world.query(original["id"], "elevation_m",
                                              AT, CAPTURED)["reports"][0]
                self.assertEqual(
                    linked["properties"]["monde_gpx_sample_elevation_m"],
                    original["properties"]["elevation_m"])
                self.assertEqual(linked["properties"]["source_id"], "elev-gpx")
                self.assertEqual(linked["properties"]["evidence_id"],
                                 source_elevation["evidence_id"])
            self.assertNotIn("monde_gpx_sample_elevation_m",
                             by_entity[features[1]["id"]]["properties"])

    def test_repeated_samples_across_track_segments_are_not_collapsed(self):
        sample = '<trkpt lat="40.70" lon="-73.99"/>'
        original = ('<?xml version="1.0"?><gpx '
                    'xmlns="http://www.topografix.com/GPX/1/1" version="1.1" '
                    'creator="survey"><trk><name>same-site</name><trkseg>'
                    + sample + sample + '</trkseg><trkseg>' + sample +
                    '</trkseg></trk></gpx>')
        with tempfile.TemporaryDirectory() as directory:
            doc = to_geojson(self.source(directory, original))
            self.assertEqual(len(doc["features"]), 3)
            self.assertEqual(len({f["id"] for f in doc["features"]}), 3)
            self.assertEqual([f["properties"]["gpx_trace"]["segment"]
                              for f in doc["features"]], [0, 0, 1])
            self.assertEqual([f["id"].split("-repeat-")[0]
                              for f in doc["features"]],
                             [doc["features"][0]["id"]] * 3)


    def test_trace_filter_is_available_in_original_offline_page(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self.source(directory, TRACE_GPX)
            output = Path(directory) / "trace-inspector.html"
            run = self.cli(*self.flags(source), "--at", AT,
                           "--known-at", CAPTURED, "--output", output)
            self.assertEqual(run.returncode, 0, run.stderr)
            page = output.read_text(encoding="utf-8")
            self.assertIn('id="trace-filter"', page)
            self.assertIn('id="trace-filter-summary"', page)
            self.assertIn("original source trace segments", page)
            self.assertIn("gpx_source_trace: traceFilter.value", page)

    def test_gpx_source_clock_day_controls_and_export_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "source-days.html"
            done = self.cli(*self.flags(self.source(directory, TRACE_GPX)),
                            "--at", AT, "--known-at", CAPTURED, "--output", output)
            self.assertEqual(done.returncode, 0, done.stderr)
            page = output.read_text(encoding="utf-8")
            for token in ('id="gpx-clock-from"', 'id="gpx-clock-through"',
                          'id="clear-gpx-clock"', "originalGpxSourceDay",
                          "gpx_source_sample_from_utc_day",
                          "gpx_source_sample_time_basis"):
                self.assertIn(token, page)

    def test_source_elevation_profile_is_offline_and_source_only(self):
        with tempfile.TemporaryDirectory() as directory:
            elevated = TRACE_GPX.replace(
                '<rtept lat="48.850" lon="2.350">',
                '<rtept lat="48.850" lon="2.350"><ele>-5.5</ele>', 1)
            elevated = elevated.replace(
                '<rtept lat="48.860" lon="2.360">',
                '<rtept lat="48.860" lon="2.360"><ele>0</ele>', 1)
            elevated = elevated.replace(
                '<rtept lat="48.865" lon="2.365">',
                '<rtept lat="48.865" lon="2.365"><ele>3.25</ele>', 1)
            target = Path(directory) / "elevation.html"
            run = self.cli(*self.flags(self.source(directory, elevated)),
                           "--at", AT, "--known-at", CAPTURED, "--output", target)
            self.assertEqual(run.returncode, 0, run.stderr)
            page = target.read_text(encoding="utf-8")
            self.assertIn("monde_gpx_sample_elevation_m", page)
            self.assertIn("source_elevation_pairs", page)
            self.assertIn("do not prove terrain altitude", page)

if __name__ == "__main__":
    unittest.main()
