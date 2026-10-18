"""Real loopback HTTP evidence-region comparisons, including antimeridian."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from monde.local_api import create_server
from monde.source_pair_changes import (
    compare_source_pair, compare_source_pair_world_time, comparison_geojson,
    comparison_csv, top_nearest_source_pair_changes,
)
from tests.test_world_source_pair_changes import fixture_world, AT, BEFORE, AFTER
from tests.test_world_source_pair_world_changes import sample, EARLY, LATE, KNOWN


class GeographicSourcePairTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "world.json"
        self.world = fixture_world()
        for source, suffix, longitude in (
                ("survey-a", "far-a", 30.0), ("survey-b", "far-b", 32.0)):
            self.world.add_evidence({
                "id": "e-" + suffix, "source_id": source,
                "locator": "fixture://" + suffix, "captured_at": AFTER,
                "source_event_at": AFTER,
            })
            self.world.add_assertion({
                "id": "a-" + suffix, "entity": "site-far", "attribute": "geo_point",
                "value": {"type": "Point", "coordinates": [longitude, 0.0]},
                "evidence_id": "e-" + suffix, "kind": "CLAIM",
                "known_at": AFTER, "valid_from": "2026-01-01T00:00:00Z",
                "valid_to": None, "supersedes": None,
            })
        self.world.save(self.path)
        self.before = self.path.read_bytes()
        self.server = create_server(self.path)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()
        self.assertEqual(self.path.read_bytes(), self.before)
        self.tmp.cleanup()

    def fetch(self, query=None, server=None):
        instance = server or self.server
        target = "/source-pair" + ("?" + urlencode(query) if query else "")
        conn = http.client.HTTPConnection("127.0.0.1", instance.server_port, timeout=5)
        conn.request("GET", target,
                     headers={"Host": "127.0.0.1:" + str(instance.server_port)})
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return result

    def query(self):
        return {"axis": "knowledge", "source_a": "survey-a", "source_b": "survey-b",
                "at": AT, "from_known_at": BEFORE, "to_known_at": AFTER}

    def test_region_filters_before_top_preserving_complete_original_reports(self):
        original = compare_source_pair(self.world, "survey-a", "survey-b", AT, BEFORE, AFTER)
        selected = [row for row in original["entities"] if row["entity"] == "site-1"]
        self.assertEqual({row["entity"] for row in original["entities"]},
                         {"site-1", "site-far"})
        focused = {**original, "entities": selected, "spatial_filter": {
            "bbox": [-0.1, -1.0, 0.1, 1.0],
            "basis": "ANY_ORIGINAL_SOURCE_POINT_IN_EITHER_PERIOD",
            "total_entities": 2, "matching_entities": 1,
        }}
        expected = top_nearest_source_pair_changes(focused, 1)
        for fmt in ("json", "geojson", "csv", "table", "html"):
            with self.subTest(fmt=fmt):
                code, headers, raw = self.fetch({
                    **self.query(), "bbox": "-0.1,-1,0.1,1", "top": "1", "format": fmt})
                self.assertEqual(code, 200)
                self.assertEqual(headers["Cache-Control"], "no-store")
                if fmt == "json":
                    self.assertEqual(json.loads(raw), expected)
                elif fmt == "geojson":
                    geo = json.loads(raw)
                    self.assertEqual(geo, comparison_geojson(expected))
                    assertions = {f["properties"]["monde_original_assertion_id"]
                                  for f in geo["features"]}
                    self.assertIn("a-b1", assertions)
                    self.assertIn("a-b2", assertions)
                elif fmt == "csv":
                    self.assertEqual(raw.decode(), comparison_csv(expected))
                else:
                    self.assertIn(b"site-1", raw)
                    self.assertNotIn(b"site-far", raw)
                    if fmt == "table":
                        self.assertIn(b"Geographic focus", raw)

    def test_world_axis_antimeridian_keeps_all_original_reports(self):
        w = sample(dateline=True)
        file = Path(self.tmp.name) / "wrapped.json"
        w.save(file)
        baseline = file.read_bytes()
        server = create_server(file)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            query = {"axis": "world", "source_a": "survey-a",
                     "source_b": "survey-b", "from_at": EARLY, "to_at": LATE,
                     "known_at": KNOWN, "bbox": "179.8,-1,-179.8,1", "format": "json"}
            code, _, raw = self.fetch(query, server)
            self.assertEqual(code, 200)
            doc = json.loads(raw)
            canonical = compare_source_pair_world_time(
                w, "survey-a", "survey-b", EARLY, LATE, KNOWN)
            self.assertEqual(doc["entities"], canonical["entities"])
            self.assertEqual(doc["spatial_filter"]["bbox"], [179.8, -1.0, -179.8, 1.0])
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
            self.assertEqual(file.read_bytes(), baseline)

    def test_empty_region_means_unknown_not_source_agreement(self):
        for fmt in ("json", "geojson", "table"):
            code, _, raw = self.fetch({
                **self.query(), "bbox": "100,20,120,40", "format": fmt})
            self.assertEqual(code, 200)
            if fmt == "json":
                self.assertEqual(json.loads(raw)["entities"], [])
            elif fmt == "geojson":
                geo = json.loads(raw)
                self.assertEqual(geo["features"], [])
                self.assertEqual(geo["monde_comparison"]["spatial_filter"]
                                 ["matching_entities"], 0)
            else:
                self.assertIn(b"NO MATCHING COMPARABLE SOURCE EVIDENCE", raw)

    def test_invalid_spatial_bounds_rejected_at_real_http_boundary(self):
        for bbox in ("0,0,2", "x,0,2,4", "-181,0,2,4", "0,-91,2,4",
                     "0,10,2,9", "0,0,181,10", "nan,0,1,1", "0,0,inf,1",
                     "0,0,0,91", "0,0,2,2<script>"):
            with self.subTest(bbox=bbox):
                code, _, data = self.fetch({
                    **self.query(), "bbox": bbox, "format": "json"})
                self.assertEqual(code, 400)
                self.assertEqual(json.loads(data), {"error": "invalid_query"})

    def test_blank_bbox_is_no_filter_and_native_forms_expose_region(self):
        default = self.fetch({**self.query(), "format": "json"})
        blank = self.fetch({**self.query(), "bbox": "", "format": "json"})
        self.assertEqual(default, blank)
        code, headers, form = self.fetch()
        self.assertEqual(code, 200)
        self.assertEqual(form.count(b'name="bbox"'), 2)
        self.assertNotIn(b"<script", form)
        self.assertIn("connect-src 'none'", headers["Content-Security-Policy"])


    def test_choose_original_reporter_for_region_without_losing_other_source(self):
        base = {**self.query(), "bbox": "29.5,-1,30.5,1", "format": "json"}
        default = json.loads(self.fetch(base)[2])
        explicit = json.loads(self.fetch({**base, "region_source": "either"})[2])
        self.assertEqual(default, explicit)
        a = json.loads(self.fetch({**base, "region_source": "a"})[2])
        self.assertEqual([row["entity"] for row in a["entities"]], ["site-far"])
        self.assertEqual(a["spatial_filter"]["qualifying_source_id"], "survey-a")
        reports = a["entities"][0]["later"]
        sources = {f["properties"]["source_id"] for key in (
            "source_a_original_reports", "source_b_original_reports")
            for f in reports[key]}
        self.assertEqual(sources, {"survey-a", "survey-b"})
        b = json.loads(self.fetch({**base, "region_source": "b"})[2])
        self.assertEqual(b["entities"], [])
        b_region = {**base, "bbox": "31.5,-1,32.5,1", "region_source": "b"}
        self.assertEqual([r["entity"] for r in json.loads(self.fetch(b_region)[2])["entities"]],
                         ["site-far"])

    def test_reporter_selection_matches_json_geojson_csv_table_and_map(self):
        params = {**self.query(), "bbox": "29.5,-1,30.5,1",
                  "region_source": "a", "top": "1"}
        doc = json.loads(self.fetch({**params, "format": "json"})[2])
        self.assertEqual(json.loads(self.fetch({**params, "format": "geojson"})[2]),
                         comparison_geojson(doc))
        self.assertEqual(self.fetch({**params, "format": "csv"})[2].decode(),
                         comparison_csv(doc))
        for mode in ("table", "html"):
            code, _, page = self.fetch({**params, "format": mode})
            self.assertEqual(code, 200)
            self.assertIn(b"site-far", page)
            self.assertNotIn(b"site-1", page)
        self.assertIn(b"survey-a", self.fetch({**params, "format": "table"})[2])

    def test_reporter_selection_rejects_invalid_values_and_requires_region(self):
        for extra in ({"region_source": "a"},
                      {"bbox": "29,-1,33,1", "region_source": "both"},
                      {"bbox": "29,-1,33,1", "region_source": "A"},
                      {"bbox": "29,-1,33,1", "region_source": "unknown"}):
            with self.subTest(extra=extra):
                code, _, data = self.fetch({**self.query(), **extra, "format": "json"})
                self.assertEqual(code, 400)
                self.assertEqual(json.loads(data), {"error": "invalid_query"})

    def test_region_reporter_form_and_world_axis(self):
        code, _, page = self.fetch()
        self.assertEqual(code, 200)
        self.assertEqual(page.count(b'name="region_source"'), 2)
        w = sample(dateline=True)
        path = Path(self.tmp.name) / "region-world.json"
        w.save(path)
        before = path.read_bytes()
        server = create_server(path)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            query = {"axis": "world", "source_a": "survey-a",
                     "source_b": "survey-b", "from_at": EARLY, "to_at": LATE,
                     "known_at": KNOWN, "bbox": "179.8,-1,-179.8,1",
                     "region_source": "a", "format": "json"}
            status, _, data = self.fetch(query, server)
            self.assertEqual(status, 200)
            doc = json.loads(data)
            self.assertEqual(doc["spatial_filter"]["qualifying_source_id"], "survey-a")
            self.assertEqual(doc["entities"], compare_source_pair_world_time(
                w, "survey-a", "survey-b", EARLY, LATE, KNOWN)["entities"])
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
