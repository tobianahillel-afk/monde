"""Two original-source Points compared without inventing a consensus."""
import http.client
from html.parser import HTMLParser
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from monde.local_api import create_server
from monde.map_view import render_map
from tests.test_world_geojson_disagreements import AT, K1, disputed

QUERY = {"bbox": "2.3,48.8,2.4,48.9", "at": AT, "known_at": K1,
         "source_a": "survey-east", "source_b": "survey-west"}


class SourceComparisonHTTPTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.file = Path(self.folder.name) / "saved.json"
        self.model = disputed()
        self.model.save(self.file)
        self.original = self.file.read_bytes()
        self.server = create_server(self.file)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.worker.join(timeout=5)
        self.server.server_close()
        self.assertEqual(self.file.read_bytes(), self.original)
        self.folder.cleanup()

    def fetch(self, route, params):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        conn.request("GET", route + "?" + urlencode(params),
                     headers={"Host": "127.0.0.1:" + str(self.server.server_port)})
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return result

    def test_selected_pair_keeps_original_offscreen_contradiction(self):
        status, headers, raw = self.fetch("/map-compare-sources", QUERY)
        self.assertEqual(status, 200)
        data = json.loads(raw)
        self.assertEqual(data["monde_source_comparison"]["matching_entities"], 1)
        self.assertEqual(data["monde_source_comparison"]["comparison_basis"],
                         "ORIGINAL_SOURCE_POINTS_NOT_GROUND_TRUTH")
        self.assertEqual(data["monde_bbox_query"]["total_matching_entities"], 1)
        self.assertEqual(data["monde_bbox_query"]["total_source_features"], 2)
        self.assertEqual({f["properties"]["source_id"] for f in data["features"]},
                         {"survey-east", "survey-west"})
        self.assertEqual({f["properties"]["entity"] for f in data["features"]}, {"site-a"})
        inside = [f for f in data["features"]
                  if f["properties"]["monde_inside_bbox"]]
        outside = [f for f in data["features"]
                   if not f["properties"]["monde_inside_bbox"]]
        self.assertEqual([f["properties"]["source_id"] for f in inside], ["survey-east"])
        self.assertEqual([f["properties"]["source_id"] for f in outside], ["survey-west"])
        self.assertEqual(outside[0]["geometry"]["coordinates"], [7.2, 47.5])
        self.assertTrue(all(f["properties"]["evidence_id"] and
                            f["properties"]["assertion_id"] for f in data["features"]))
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_comparison_browser_preserves_both_sources_and_world_time(self):
        q = {"view": "compare-sources", **QUERY}
        status, headers, body = self.fetch("/viewer", q)
        self.assertEqual(status, 200)
        geo = json.loads(self.fetch("/map-compare-sources", QUERY)[2])
        self.assertEqual(body.decode("utf-8"),
                         render_map(geo, inspector_links=True, navigation=q))
        self.assertIn(b'name="source_a" value="survey-east"', body)
        self.assertIn(b'name="source_b" value="survey-west"', body)
        self.assertIn("connect-src 'none'", headers["Content-Security-Policy"])

    def test_no_false_pair_from_only_one_source_or_nonselected_inside(self):
        # site-b has only an east report: never counts as cross-source evidence.
        records = json.loads(self.fetch("/map-compare-sources", QUERY)[2])
        self.assertNotIn("site-b", {f["properties"]["entity"] for f in records["features"]})
        # Both sources are reported outside the small viewport.
        other = {**QUERY, "bbox": "0,0,1,1"}
        result = json.loads(self.fetch("/map-compare-sources", other)[2])
        self.assertEqual(result["features"], [])
        self.assertEqual(result["monde_bbox_query"]["status"], "NO_MATCHES")
        self.assertEqual(result["monde_source_comparison"]["matching_entities"], 0)
        unknown = {**QUERY, "source_b": "unknown"}
        self.assertEqual(json.loads(self.fetch("/map-compare-sources", unknown)[2])
                         ["features"], [])

    def test_invalid_or_equal_source_ids_rejected(self):
        for field, bad in (("source_a", "../bad"), ("source_b", "<script>"),
                           ("source_a", "a" * 100), ("source_b", "survey-east")):
            q = {**QUERY, field: bad}
            for route, params in (("/map-compare-sources", q),
                                  ("/viewer", {"view": "compare-sources", **q})):
                status, _, raw = self.fetch(route, params)
                self.assertEqual(status, 400)
                self.assertEqual(json.loads(raw), {"error": "invalid_query"})
        status, _, raw = self.fetch("/map-compare-sources", {**QUERY, "extra": "x"})
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(raw), {"error": "invalid_query"})

    def test_explorer_has_native_two_source_form_and_suggestions(self):
        status, headers, html = self.fetch("/explore", {})
        self.assertEqual(status, 200)
        self.assertIn("form-action 'self'", headers["Content-Security-Policy"])
        html = html.decode("utf-8")
        self.assertEqual(html.count('<input type="hidden" name="view" value="compare-sources">'), 1)
        form = html.split('value="compare-sources">', 1)[1].split('</form>', 1)[0]
        self.assertIn('name="source_a" list="saved-original-sources" required', form)
        self.assertIn('name="source_b" list="saved-original-sources" required', form)
        self.assertIn('value="survey-east"', html)
        self.assertIn('value="survey-west"', html)
        self.assertNotIn("<script", html)


    def test_only_different_reports_reuses_pair_and_preserves_originals(self):
        params = {**QUERY, "different_only": "1"}
        status, headers, raw = self.fetch("/map-compare-sources", params)
        self.assertEqual(status, 200)
        data = json.loads(raw)
        self.assertEqual(data["monde_source_comparison"]["scope"],
                         "DIFFERENT_REPORTED_POINT_SETS")
        self.assertEqual(data["monde_source_comparison"]["matching_entities"], 1)
        self.assertEqual({f["properties"]["source_id"] for f in data["features"]},
                         {"survey-east", "survey-west"})
        self.assertEqual(len(data["features"]), 2)
        self.assertEqual(data["monde_bbox_query"]["total_source_features"], 2)
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        view = {"view": "compare-sources", **params}
        code, response_headers, page = self.fetch("/viewer", view)
        self.assertEqual(code, 200)
        self.assertEqual(page.decode(), render_map(data, inspector_links=True, navigation=view))
        self.assertIn(b'name="different_only" value="1" checked', page)
        self.assertIn("connect-src 'none'", response_headers["Content-Security-Policy"])
        _, _, home = self.fetch("/explore", {})
        self.assertIn(b'name="different_only" value="1"', home)

    def test_rejects_invalid_difference_filter_without_changing_default(self):
        original = json.loads(self.fetch("/map-compare-sources", QUERY)[2])
        self.assertNotIn("scope", original["monde_source_comparison"])
        for flag in ("0", "true", "yes", "../1", ""):
            with self.subTest(flag=flag):
                params = {**QUERY, "different_only": flag}
                for route, query in (("/map-compare-sources", params),
                                     ("/viewer", {"view": "compare-sources", **params})):
                    status, _, raw = self.fetch(route, query)
                    self.assertEqual(status, 400)
                    self.assertEqual(json.loads(raw), {"error": "invalid_query"})
        self.assertEqual(json.loads(self.fetch("/map-compare-sources", QUERY)[2]), original)

    def test_equal_source_coordinates_are_not_reported_as_conflicts(self):
        from monde.world import WorldMini
        from monde.local_api import _compare_source_bbox
        from tests.test_world_geojson_disagreements import add

        model = WorldMini()
        add(model, "survey-east", [2.35, 48.85], entity="same")
        add(model, "survey-west", [2.35, 48.85], entity="same")
        add(model, "survey-east", [2.36, 48.85], entity="different")
        add(model, "survey-west", [4.0, 45.0], entity="different")
        original = model.export()
        selection = model.export_geojson_bbox([2.3, 48.8, 2.4, 48.9], AT, K1)
        unfiltered = _compare_source_bbox(selection, "survey-east", "survey-west")
        filtered = _compare_source_bbox(selection, "survey-east", "survey-west", True)
        self.assertEqual(unfiltered["monde_source_comparison"]["matching_entities"], 2)
        self.assertEqual(filtered["monde_source_comparison"]["matching_entities"], 1)
        self.assertEqual({f["properties"]["entity"] for f in filtered["features"]},
                         {"different"})
        self.assertEqual(len(filtered["features"]), 2)
        self.assertEqual({f["properties"]["source_id"] for f in filtered["features"]},
                         {"survey-east", "survey-west"})
        self.assertEqual(model.export(), original)


if __name__ == "__main__":
    unittest.main()
