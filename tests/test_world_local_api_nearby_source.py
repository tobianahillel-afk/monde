"""Real loopback HTTP regression for original-source proximity selection."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from monde.local_api import create_server
from monde.map_view import render_map
from tests.test_world_geojson_disagreements import disputed, AT, K1

CENTER = [7.2, 47.5]
ARGS = {"center": "7.2,47.5", "at": AT, "known_at": K1}


class SourceProximityHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state = Path(self.temp.name) / "state.json"
        self.world = disputed()
        self.world.save(self.state)
        self.original = self.state.read_bytes()
        self.server = create_server(self.state)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()
        self.assertEqual(self.state.read_bytes(), self.original)
        self.temp.cleanup()

    def fetch(self, route, query):
        con = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        con.request("GET", route + "?" + urlencode(query),
                    headers={"Host": "127.0.0.1:" + str(self.server.server_port)})
        resp = con.getresponse()
        result = (resp.status, dict(resp.getheaders()), resp.read())
        con.close()
        return result

    def test_source_selection_precedes_nearest_limit(self):
        base = {**ARGS, "limit": "1"}
        original = json.loads(self.fetch("/nearest", base)[2])
        self.assertEqual(original["features"][0]["properties"]["source_id"], "survey-west")
        code, headers, raw = self.fetch("/nearest", {**base, "source": "survey-east"})
        self.assertEqual(code, 200)
        document = json.loads(raw)
        self.assertEqual(document["monde_source_filter"], "survey-east")
        self.assertEqual(document["monde_nearest_query"]["total_matching_entities"], 2)
        self.assertTrue(document["monde_nearest_query"]["has_more"])
        self.assertEqual(len({f["properties"]["entity"] for f in document["features"]}), 1)
        self.assertEqual({f["properties"]["source_id"] for f in document["features"]},
                         {"survey-east"})
        self.assertTrue(all(f["properties"]["evidence_id"] for f in document["features"]))
        self.assertEqual(document, self.world.export_geojson_nearest(CENTER, 1, AT, K1,
                                                                     source="survey-east"))
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_radius_qualifies_only_selected_source(self):
        base = {**ARGS, "radius_km": "2"}
        west = json.loads(self.fetch("/radius", {**base, "source": "survey-west"})[2])
        self.assertEqual(west["monde_source_filter"], "survey-west")
        self.assertEqual(west["monde_radius_query"]["total_matching_entities"], 1)
        self.assertEqual({f["properties"]["source_id"] for f in west["features"]},
                         {"survey-west"})
        self.assertTrue(all(f["properties"]["monde_within_radius"] for f in west["features"]))
        east = json.loads(self.fetch("/radius", {**base, "source": "survey-east"})[2])
        self.assertEqual(east["features"], [])
        self.assertEqual(east["monde_radius_query"]["status"], "NO_MATCHES")
        self.assertEqual(json.loads(self.fetch("/radius", {**base, "source": "unknown"})[2])["features"], [])

    def test_browser_matches_json_and_keeps_source_in_navigation(self):
        for mode, query in (
            ("nearest", {**ARGS, "limit": "1", "source": "survey-east"}),
            ("radius", {**ARGS, "radius_km": "2", "source": "survey-west"}),
        ):
            with self.subTest(mode=mode):
                code, headers, content = self.fetch("/viewer", {"view": mode, **query})
                self.assertEqual(code, 200)
                payload = json.loads(self.fetch("/" + mode, query)[2])
                self.assertEqual(content.decode("utf-8"),
                                 render_map(payload, inspector_links=True,
                                            navigation={"view": mode, **query}))
                self.assertIn(b'name="source" value="survey-', content)
                self.assertIn("connect-src 'none'", headers["Content-Security-Policy"])
                self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_unfiltered_contract_and_invalid_source(self):
        self.assertEqual(json.loads(self.fetch("/nearest", {**ARGS, "limit": "1"})[2]),
                         self.world.export_geojson_nearest(CENTER, 1, AT, K1))
        self.assertEqual(json.loads(self.fetch("/radius", {**ARGS, "radius_km": "2"})[2]),
                         self.world.export_geojson_radius(CENTER, 2., AT, K1))
        for route, params in (
            ("/nearest", {**ARGS, "limit": "1", "source": "../other"}),
            ("/radius", {**ARGS, "radius_km": "2", "source": "<script>"}),
            ("/viewer", {"view": "nearest", **ARGS, "limit": "1", "source": "bad id"}),
            ("/nearest", {**ARGS, "limit": "1", "source": "survey-east", "bad": "x"}),
        ):
            with self.subTest(route=route):
                code, _, body = self.fetch(route, params)
                self.assertEqual(code, 400)
                self.assertEqual(json.loads(body), {"error": "invalid_query"})


if __name__ == "__main__":
    unittest.main()
