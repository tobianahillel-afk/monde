"""Real HTTP tests: source catalog, links and unmodified persisted model."""
import http.client
import json
from html.parser import HTMLParser
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import urlencode, urlsplit, parse_qs

from monde.local_api import create_server
from tests.test_world_geojson_disagreements import AT, K1, disputed

QUERY = {"bbox": "2.3,48.8,2.4,48.9", "at": AT, "known_at": K1}

class SourceCatalogHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "world.json"
        disputed().save(self.path)
        self.original = self.path.read_bytes()
        self.server = create_server(self.path)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()
        self.assertEqual(self.path.read_bytes(), self.original)
        self.tmp.cleanup()

    def get(self, route, params=None):
        con = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        con.request("GET", route + ("?" + urlencode(params) if params else ""),
                    headers={"Host": "127.0.0.1:" + str(self.server.server_port)})
        res = con.getresponse()
        value = res.status, dict(res.getheaders()), res.read()
        con.close()
        return value

    def test_source_catalog_counts_only_source_points_inside_bbox(self):
        code, headers, data = self.get("/map-sources", QUERY)
        self.assertEqual(code, 200)
        catalog = json.loads(data)
        self.assertEqual(catalog["monde_source_catalog"]["scope"],
                         "original_points_inside_bbox")
        self.assertEqual(catalog["sources"], [
            {"source_id": "survey-east", "point_reports": 1, "matching_entities": 1}])
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_html_source_links_resolve_to_existing_filtered_map(self):
        code, headers, body = self.get("/source-catalog", {"view": "current", **QUERY})
        self.assertEqual(code, 200)
        self.assertIn("script-src 'none'", headers["Content-Security-Policy"])
        self.assertIn(b"survey-east", body)
        self.assertNotIn(b"survey-west", body)
        class Links(HTMLParser):
            def __init__(self):
                super().__init__()
                self.items = []
            def handle_starttag(self, tag, attrs):
                if tag == "a":
                    self.items.append(dict(attrs)["href"])
        parsed = Links()
        parsed.feed(body.decode("utf-8"))
        links = [x for x in parsed.items if x.startswith("/viewer?")]
        self.assertEqual(len(links), 1)
        path = urlsplit(links[0])
        params = {key: values[0] for key, values in parse_qs(path.query).items()}
        self.assertEqual(params, {"view": "current", **QUERY, "source": "survey-east"})
        code, _, html = self.get(path.path, params)
        self.assertEqual(code, 200)
        self.assertIn(b"survey-east", html)
        self.assertNotIn(b"survey-west", html)

    def test_explore_has_single_catalog_button_in_current_map_form(self):
        code, _, body = self.get("/explore")
        self.assertEqual(code, 200)
        self.assertEqual(body.count(b'formaction="/source-catalog"'), 1)
        self.assertEqual(body.count(b'<form '), 6)

    def test_strict_query_and_empty_area(self):
        for route, params in [
            ("/map-sources", {**QUERY, "unknown": "1"}),
            ("/map-sources", {**QUERY, "bbox": "bad"}),
            ("/map-sources", {**QUERY, "at": "invalid"}),
            ("/source-catalog", {"view": "disagreements", **QUERY}),
        ]:
            with self.subTest(route=route, params=params):
                code, _, data = self.get(route, params)
                self.assertEqual(code, 400)
                self.assertEqual(json.loads(data), {"error": "invalid_query"})
        code, _, raw = self.get("/map-sources", {**QUERY, "bbox": "80,70,81,71"})
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(raw)["sources"], [])


if __name__ == "__main__":
    unittest.main()
