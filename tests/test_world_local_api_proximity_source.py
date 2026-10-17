"""Source-scoped MONDE Mini proximity: source-first ranking and live local HTTP."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from monde.geojson import to_document
from monde.local_api import create_server
from monde.map_view import render_map
from monde.world import WorldMini

AT = "2026-01-02T00:00:00Z"
KNOWN = "2026-01-10T10:00:00Z"
CENTER = [2.35, 48.85]
NEAR = {"center": "2.35,48.85", "limit": "1", "at": AT, "known_at": KNOWN}
RAD = {"center": "2.35,48.85", "radius_km": "5", "at": AT, "known_at": KNOWN}


def add(world, entity, source, point):
    world.append_document(to_document(
        {"type": "FeatureCollection", "features": [
            {"type": "Feature", "id": entity, "properties": {},
             "geometry": {"type": "Point", "coordinates": point}}]},
        source_id=source, locator="fixture://" + source + "/" + entity,
        captured_at=KNOWN, valid_from="2026-01-01T00:00:00Z"))


class SourceScopedProximityHTTP(unittest.TestCase):
    def setUp(self):
        self.world = WorldMini()
        add(self.world, "place-a", "west", [2.35, 48.85])
        add(self.world, "place-a", "east", [5.0, 45.0])
        add(self.world, "place-b", "east", [2.36, 48.85])
        add(self.world, "place-b", "west", [6.0, 47.0])
        self.temp = tempfile.TemporaryDirectory()
        self.state = Path(self.temp.name) / "world.json"
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
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        conn.request("GET", route + "?" + urlencode(query),
                     headers={"Host": "127.0.0.1:" + str(self.server.server_port)})
        response = conn.getresponse()
        answer = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return answer

    def test_nearest_source_ranks_before_limit(self):
        all_results = json.loads(self.fetch("/nearest", NEAR)[2])
        self.assertEqual(all_results["features"][0]["properties"]["entity"], "place-a")
        code, headers, data = self.fetch("/nearest", {**NEAR, "source": "east"})
        self.assertEqual(code, 200)
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        selected = json.loads(data)
        self.assertEqual(selected["monde_source_filter"], "east")
        self.assertEqual({f["properties"]["entity"] for f in selected["features"]},
                         {"place-b"})
        self.assertEqual({f["properties"]["source_id"] for f in selected["features"]},
                         {"east"})
        self.assertEqual(selected["monde_nearest_query"]["total_matching_entities"], 2)
        self.assertTrue(selected["monde_nearest_query"]["has_more"])
        self.assertEqual(selected, self.world.export_geojson_nearest(
            CENTER, 1, AT, KNOWN, source_id="east"))

    def test_radius_only_selected_source_qualifies(self):
        selected = json.loads(self.fetch("/radius", {**RAD, "source": "east"})[2])
        self.assertEqual({f["properties"]["entity"] for f in selected["features"]},
                         {"place-b"})
        self.assertEqual(selected["monde_radius_query"]["total_matching_entities"], 1)
        self.assertEqual(selected["features"][0]["properties"]["source_id"], "east")
        self.assertTrue(selected["features"][0]["properties"]["monde_within_radius"])
        self.assertEqual(json.loads(self.fetch("/radius", RAD)[2]),
                         self.world.export_geojson_radius(CENTER, 5, AT, KNOWN))

    def test_browser_map_matches_json_and_preserves_source(self):
        for view, route, query in (("nearest", "/nearest", NEAR),
                                   ("radius", "/radius", RAD)):
            values = {"view": view, **query, "source": "east"}
            code, headers, body = self.fetch("/viewer", values)
            self.assertEqual(code, 200)
            data = json.loads(self.fetch(route, {**query, "source": "east"})[2])
            self.assertEqual(body.decode("utf-8"),
                             render_map(data, inspector_links=True, navigation=values))
            self.assertIn(b'name="source" value="east"', body)
            self.assertIn("connect-src 'none'", headers["Content-Security-Policy"])
        _, _, home = self.fetch("/explore", {})
        for view in ("nearest", "radius"):
            form = home.split(('value="' + view + '">').encode(), 1)[1].split(b'</form>', 1)[0]
            self.assertIn(b'name="source"', form)

    def test_unknown_and_bad_source_are_not_silently_reconciled(self):
        for route, query in (("/nearest", NEAR), ("/radius", RAD),
                             ("/viewer", {"view": "nearest", **NEAR}),
                             ("/viewer", {"view": "radius", **RAD})):
            with self.subTest(route=route):
                code, _, body = self.fetch(route, {**query, "source": "../east"})
                self.assertEqual(code, 400)
                self.assertEqual(json.loads(body), {"error": "invalid_query"})
                code, _, body = self.fetch(route, {**query, "source": "unknown"})
                self.assertEqual(code, 200)
                if route != "/viewer":
                    self.assertEqual(json.loads(body)["features"], [])
                self.assertEqual(self.fetch(route, {**query, "source": "east",
                                                    "extra": "x"})[0], 400)

    def test_original_calls_and_saved_model_remain_unchanged(self):
        baseline = self.world.export()
        for fn, args in ((self.world.search_geo_nearest, (CENTER, 1, AT, KNOWN)),
                         (self.world.search_geo_radius, (CENTER, 5, AT, KNOWN))):
            for source in ("../east", "/west", "a b", "bad<script>", "z"*100):
                with self.assertRaises(ValueError):
                    fn(*args, source_id=source)
        self.assertEqual(baseline, self.world.export())
        self.assertEqual(json.loads(self.fetch("/nearest", NEAR)[2]),
                         self.world.export_geojson_nearest(CENTER, 1, AT, KNOWN))
        self.assertEqual(json.loads(self.fetch("/radius", RAD)[2]),
                         self.world.export_geojson_radius(CENTER, 5, AT, KNOWN))


if __name__ == "__main__":
    unittest.main()
