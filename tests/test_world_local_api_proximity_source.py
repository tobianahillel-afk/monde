"""Source-specific ranked proximity over real saved MONDE Mini evidence."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from monde.local_api import create_server
from monde.map_view import render_map
from tests.test_world_geojson_disagreements import AT, K1, add, disputed

CENTER = [2.35, 48.85]
PARAMS = {"center": "2.35,48.85", "at": AT, "known_at": K1}


class ProximitySourceHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.file = Path(self.temp.name) / "model.json"
        self.world = disputed()
        # The east source owns the globally nearest site-a. For west, site-c
        # is the closest; post-filtering a global top-one answer would be wrong.
        add(self.world, "survey-west", [2.36, 48.85], entity="site-c")
        self.world.save(self.file)
        self.original = self.file.read_bytes()
        self.server = create_server(self.file)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()
        self.assertEqual(self.file.read_bytes(), self.original)
        self.temp.cleanup()

    def fetch(self, route, query):
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=5)
        connection.request("GET", route + "?" + urlencode(query),
                           headers={"Host": "127.0.0.1:" + str(self.server.server_port)})
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def test_source_precedes_nearest_limit_and_changes_ranking(self):
        query = {**PARAMS, "limit": "1"}
        status, _, raw = self.fetch("/nearest", query)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw),
                         self.world.export_geojson_nearest(CENTER, 1, AT, K1))
        selected = {**query, "source": "survey-west"}
        status, _, raw = self.fetch("/nearest", selected)
        self.assertEqual(status, 200)
        payload = json.loads(raw)
        self.assertEqual(payload["monde_source_filter"], "survey-west")
        self.assertEqual(payload["monde_nearest_query"]["total_matching_entities"], 2)
        self.assertTrue(payload["monde_nearest_query"]["has_more"])
        self.assertEqual({f["properties"]["entity"] for f in payload["features"]},
                         {"site-c"})
        self.assertEqual({f["properties"]["source_id"] for f in payload["features"]},
                         {"survey-west"})
        self.assertEqual(payload["features"][0]["properties"]["monde_nearest_entity_rank"], 1)
        viewer = {"view": "nearest", **selected}
        code, headers, html = self.fetch("/viewer", viewer)
        self.assertEqual(code, 200)
        self.assertEqual(html.decode("utf-8"),
                         render_map(payload, inspector_links=True, navigation=viewer))
        self.assertIn(b'name="source" value="survey-west"', html)
        self.assertNotIn(b"survey-east", html)
        self.assertIn("connect-src 'none'", headers["Content-Security-Policy"])

    def test_radius_requires_selected_source_point_inside_radius(self):
        query = {**PARAMS, "radius_km": "1", "source": "survey-west"}
        status, _, raw = self.fetch("/radius", query)
        self.assertEqual(status, 200)
        payload = json.loads(raw)
        self.assertEqual(payload["monde_radius_query"]["total_matching_entities"], 1)
        self.assertEqual({f["properties"]["entity"] for f in payload["features"]},
                         {"site-c"})
        self.assertTrue(all(f["properties"]["monde_within_radius"]
                            for f in payload["features"]))
        self.assertEqual({f["properties"]["source_id"] for f in payload["features"]},
                         {"survey-west"})
        self.assertEqual(payload["monde_source_filter"], "survey-west")
        viewer = {"view": "radius", **query}
        code, _, html = self.fetch("/viewer", viewer)
        self.assertEqual(code, 200)
        self.assertEqual(html.decode("utf-8"),
                         render_map(payload, inspector_links=True, navigation=viewer))
        self.assertIn(b'name="source" value="survey-west"', html)
        # Other source's own inside Point may never qualify west's remote site-a.
        zero = {**PARAMS, "radius_km": "0.1", "source": "survey-west"}
        self.assertEqual(json.loads(self.fetch("/radius", zero)[2])
                         ["monde_radius_query"]["total_matching_entities"], 0)

    def test_empty_missing_source_and_cutoffs_preserve_base_semantics(self):
        for endpoint, args, getter in (
            ("/nearest", {**PARAMS, "limit": "2"}, lambda:
                self.world.export_geojson_nearest(CENTER, 2, AT, K1)),
            ("/radius", {**PARAMS, "radius_km": "1"}, lambda:
                self.world.export_geojson_radius(CENTER, 1, AT, K1)),
        ):
            for query in (args, {**args, "source": ""}):
                code, _, body = self.fetch(endpoint, query)
                self.assertEqual(code, 200)
                self.assertEqual(json.loads(body), getter())
            selected = {**args, "source": "survey-west",
                        "known_at": "2026-01-10T09:59:59Z"}
            code, _, body = self.fetch(endpoint, selected)
            self.assertEqual(code, 200)
            self.assertEqual(json.loads(body)["features"], [])

    def test_invalid_source_and_unknown_fields_are_rejected(self):
        for endpoint, args, mode in (
            ("/nearest", {**PARAMS, "limit": "1"}, "nearest"),
            ("/radius", {**PARAMS, "radius_km": "1"}, "radius"),
        ):
            for source in ("../evil", "<script>", "a b", "bad/x", "a" * 120):
                query = {**args, "source": source}
                for route, v in ((endpoint, query),
                                 ("/viewer", {"view": mode, **query})):
                    status, _, raw = self.fetch(route, v)
                    self.assertEqual(status, 400)
                    self.assertEqual(json.loads(raw), {"error": "invalid_query"})
            status, _, raw = self.fetch(endpoint, {**args, "unexpected": "x"})
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(raw), {"error": "invalid_query"})

    def test_explore_forms_offer_source_filter_for_both_proximity_views(self):
        code, headers, body = self.fetch("/explore", {})
        self.assertEqual(code, 200)
        html = body.decode("utf-8")
        for name in ("nearest", "radius"):
            form = html.split('value="' + name + '">', 1)[1].split('</form>', 1)[0]
            self.assertIn('name="source"', form)
            self.assertIn('list="saved-original-sources"', form)
        self.assertIn("survey-east", html)
        self.assertIn("survey-west", html)
        self.assertNotIn("<script", html)
        self.assertEqual(headers["Cache-Control"], "no-store")


if __name__ == "__main__":
    unittest.main()
