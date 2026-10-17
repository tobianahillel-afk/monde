"""Original-source lens for MONDE Mini read-only bbox maps."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from monde.local_api import create_server
from monde.map_view import render_map
from tests.test_world_geojson_disagreements import AT, K1, disputed

BOUNDS = [2.3, 48.8, 2.4, 48.9]
QUERY = {"bbox": "2.3,48.8,2.4,48.9", "at": AT, "known_at": K1}


class SourceLensHTTPTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "world.json"
        self.world = disputed()
        self.world.save(self.path)
        self.original = self.path.read_bytes()
        self.server = create_server(self.path)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()
        self.assertEqual(self.path.read_bytes(), self.original)
        self.dir.cleanup()

    def fetch(self, route, query):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        connection.request("GET", route + "?" + urlencode(query),
                           headers={"Host": "127.0.0.1:" + str(self.server.server_port)})
        result = connection.getresponse()
        data = (result.status, dict(result.getheaders()), result.read())
        connection.close()
        return data

    def test_original_source_selection_keeps_provenance_and_counts(self):
        code, headers, body = self.fetch("/map", {**QUERY, "source": "survey-east"})
        self.assertEqual(code, 200)
        data = json.loads(body)
        self.assertEqual(data["monde_source_filter"], "survey-east")
        self.assertEqual([x["properties"]["source_id"] for x in data["features"]],
                         ["survey-east"])
        self.assertEqual([x["properties"]["entity"] for x in data["features"]], ["site-a"])
        self.assertTrue(data["features"][0]["properties"]["evidence_id"])
        self.assertEqual(data["monde_bbox_query"]["total_matching_entities"], 1)
        self.assertEqual(data["monde_bbox_query"]["total_source_features"], 1)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_outside_source_is_not_mistaken_for_matching_source(self):
        code, _, data = self.fetch("/map", {**QUERY, "source": "survey-west"})
        self.assertEqual(code, 200)
        payload = json.loads(data)
        self.assertEqual(payload["features"], [])
        self.assertEqual(payload["monde_bbox_query"]["status"], "NO_MATCHES")
        self.assertEqual(payload["monde_bbox_query"]["total_matching_entities"], 0)

    def test_unspecified_source_is_byte_identical_to_world_export(self):
        code, _, raw = self.fetch("/map", QUERY)
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(raw), self.world.export_geojson_bbox(BOUNDS, AT, K1))
        self.assertEqual(self.fetch("/map", {**QUERY, "source": ""})[0], 200)

    def test_filtered_viewer_renders_real_source_and_preserves_time_navigation(self):
        query = {"view": "current", **QUERY, "source": "survey-east"}
        code, headers, body = self.fetch("/viewer", query)
        self.assertEqual(code, 200)
        output = json.loads(self.fetch("/map", {**QUERY, "source": "survey-east"})[2])
        self.assertEqual(body.decode("utf-8"),
                         render_map(output, inspector_links=True, navigation=query))
        self.assertIn(b'name="source" value="survey-east"', body)
        self.assertIn(b"survey-east", body)
        self.assertNotIn(b"survey-west", body)
        self.assertIn("connect-src 'none'", headers["Content-Security-Policy"])

    def test_invalid_source_cannot_change_query_semantics(self):
        for source in ("../survey-east", "bad<script>", "/abs", "a b", "z" * 100):
            with self.subTest(source=source):
                code, _, body = self.fetch("/map", {**QUERY, "source": source})
                self.assertEqual(code, 400)
                self.assertEqual(json.loads(body), {"error": "invalid_query"})
        for route, query in (
            ("/viewer", {"view": "disagreements", **QUERY, "source": "survey-east"}),
            ("/map", {**QUERY, "source": "survey-east", "extra": "x"}),
        ):
            code, _, body = self.fetch(route, query)
            self.assertEqual(code, 400)
            self.assertEqual(json.loads(body), {"error": "invalid_query"})


if __name__ == "__main__":
    unittest.main()
