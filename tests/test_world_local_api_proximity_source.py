"""Source-aware proximity must qualify and rank original Points before limiting."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from monde.local_api import create_server
from tests.test_world_geojson_disagreements import AT, K1, add, disputed


class SourceProximityHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name) / "state.json"
        self.world = disputed()
        add(self.world, "survey-east", [2.3522, 48.8566], entity="site-c")
        # A second, out-of-radius original Point from the selected same source.
        add(self.world, "survey-east", [6, 48], entity="site-a")
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
        self.tmp.cleanup()

    def fetch(self, path, params):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        conn.request("GET", path + "?" + urlencode(params),
                     headers={"Host": "127.0.0.1:" + str(self.server.server_port)})
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return result

    def test_source_selection_precedes_nearest_rank_and_limit(self):
        args = {"center": "2.3522,48.8566", "limit": "1",
                "at": AT, "known_at": K1}
        status, _, data = self.fetch("/nearest", args)
        self.assertEqual(status, 200)
        unfiltered = json.loads(data)
        self.assertEqual({f["properties"]["entity"] for f in unfiltered["features"]},
                         {"site-c"})
        status, _, data = self.fetch("/nearest", {**args, "source": "survey-west"})
        self.assertEqual(status, 200)
        selected = json.loads(data)
        self.assertEqual({f["properties"]["entity"] for f in selected["features"]},
                         {"site-a"})
        self.assertEqual({f["properties"]["source_id"] for f in selected["features"]},
                         {"survey-west"})
        self.assertEqual(selected["monde_nearest_query"]["total_matching_entities"], 1)
        self.assertFalse(selected["monde_nearest_query"]["has_more"])
        self.assertEqual(selected["monde_source_filter"], "survey-west")
        self.assertEqual(json.loads(self.fetch("/nearest", {**args, "source": ""})[2]),
                         self.world.export_geojson_nearest([2.3522, 48.8566], 1, AT, K1))

    def test_radius_keeps_other_positions_of_selected_source_only(self):
        args = {"center": "2.3522,48.8566", "radius_km": "1",
                "at": AT, "known_at": K1}
        selected = json.loads(self.fetch("/radius", {**args, "source": "survey-east"})[2])
        self.assertEqual(selected["monde_radius_query"]["total_matching_entities"], 2)
        self.assertEqual({f["properties"]["source_id"] for f in selected["features"]},
                         {"survey-east"})
        site_a = [f for f in selected["features"]
                  if f["properties"]["entity"] == "site-a"]
        self.assertEqual({f["properties"]["monde_within_radius"] for f in site_a},
                         {True, False})
        self.assertTrue(all(f["properties"]["evidence_id"] for f in site_a))
        west = json.loads(self.fetch("/radius", {**args, "source": "survey-west"})[2])
        self.assertEqual(west["features"], [])
        self.assertEqual(west["monde_radius_query"]["status"], "NO_MATCHES")

    def test_browser_paths_and_original_source_controls(self):
        status, headers, body = self.fetch("/explore", {})
        self.assertEqual(status, 200)
        self.assertGreaterEqual(body.count(b'name="source"'), 4)
        self.assertIn("connect-src 'none'", headers["Content-Security-Policy"])
        nearest = {"view": "nearest", "center": "2.3522,48.8566",
                   "limit": "1", "at": AT, "known_at": K1, "source": "survey-west"}
        status, headers, body = self.fetch("/viewer", nearest)
        self.assertEqual(status, 200)
        self.assertIn(b'name="source" value="survey-west"', body)
        self.assertIn(b"survey-west", body)
        self.assertIn("connect-src 'none'", headers["Content-Security-Policy"])
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        radius = {"view": "radius", "center": nearest["center"], "radius_km": "1",
                  "at": AT, "known_at": K1, "source": "survey-east"}
        self.assertEqual(self.fetch("/viewer", radius)[0], 200)

    def test_invalid_source_and_strict_http_parameters(self):
        args = {"center": "2.3522,48.8566", "limit": "1", "at": AT,
                "known_at": K1}
        for source in ("../x", "<script>", "a b", "/abs", "x" * 97):
            with self.subTest(source=source):
                status, _, raw = self.fetch("/nearest", {**args, "source": source})
                self.assertEqual(status, 400)
                self.assertEqual(json.loads(raw), {"error": "invalid_query"})
        self.assertEqual(self.fetch("/nearest", {**args, "source": "survey-east",
                                                "unexpected": "x"})[0], 400)
        self.assertEqual(self.fetch("/radius", {
            "center": args["center"], "radius_km": "1",
            "at": AT, "known_at": K1, "source": "bad/id"})[0], 400)
        with self.assertRaises(ValueError):
            self.world.search_geo_radius([2.3522, 48.8566], 1, AT, K1,
                                         source_id="bad/id")
