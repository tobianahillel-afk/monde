"""Source-directory behavior through the actual read-only loopback HTTP server."""
from html import unescape
import http.client
import json
from pathlib import Path
import re
import tempfile
import threading
import unittest
from urllib.parse import parse_qs, urlencode, urlsplit

from monde.local_api import create_server, _source_catalog_html
from tests.test_world_geojson_disagreements import AT, K1, disputed


class SourceDirectoryHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "world.json"
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
        self.temp.cleanup()

    def fetch(self, route, params=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        conn.request("GET", route + ("?" + urlencode(params) if params is not None else ""),
                     headers={"Host": "127.0.0.1:" + str(self.server.server_port)})
        res = conn.getresponse()
        output = res.status, dict(res.getheaders()), res.read()
        conn.close()
        return output

    def test_discover_sources_from_explorer_without_script_or_writes(self):
        status, _, home = self.fetch("/explore")
        self.assertEqual(status, 200)
        self.assertIn(b'href="/sources"', home)
        status, headers, page = self.fetch("/sources")
        self.assertEqual(status, 200)
        self.assertIn(b'name="at"', page)
        self.assertIn(b'name="known_at"', page)
        self.assertIn(b'name="prefix"', page)
        self.assertNotIn(b'<script', page)
        self.assertIn("script-src 'none'", headers["Content-Security-Policy"])
        self.assertIn("connect-src 'none'", headers["Content-Security-Policy"])
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_current_original_source_counts_and_links(self):
        status, _, page = self.fetch("/sources", {"at": AT, "known_at": K1, "prefix": ""})
        self.assertEqual(status, 200)
        text = page.decode("utf-8")
        self.assertIn("<td>survey-east</td><td>1</td><td>1</td>", text)
        self.assertIn("<td>survey-west</td><td>1</td><td>1</td>", text)
        self.assertIn("not physical truth or reliability", text)
        links = [unescape(value) for value in re.findall(r'href="([^"]+)"', text)]
        url = next(u for u in links if u.startswith("/viewer?") and "source=survey-east" in u)
        result = urlsplit(url)
        params = {k: v[0] for k, v in parse_qs(result.query).items()}
        self.assertEqual(params["at"], AT)
        self.assertEqual(params["known_at"], K1)
        self.assertEqual(params["source"], "survey-east")
        self.assertEqual(self.fetch(result.path, params)[0], 200)
        self.assertTrue(any("/inspect?" in u and "source=survey-east" in u for u in links))

    def test_prefix_and_cursor_filter_source_directory_not_evidence(self):
        params = {"at": AT, "known_at": K1}
        status, _, page = self.fetch("/sources", {**params, "prefix": "survey-e"})
        self.assertEqual(status, 200)
        self.assertIn(b"<td>survey-east</td>", page)
        self.assertNotIn(b"<td>survey-west</td>", page)
        status, _, page = self.fetch("/sources", {**params, "after": "survey-east"})
        self.assertEqual(status, 200)
        self.assertIn(b"<td>survey-west</td>", page)
        self.assertNotIn(b"<td>survey-east</td>", page)
        status, _, page = self.fetch("/sources", params)
        self.assertEqual(status, 200)
        self.assertIn(b"survey-east", page)
        self.assertIn(b"survey-west", page)

    def test_invalid_query_cannot_access_unexpected_routes_or_mutate(self):
        for params in (
            {"at": AT},
            {"at": AT, "known_at": "garbage"},
            {"at": AT, "known_at": K1, "other": "yes"},
            {"at": AT, "known_at": K1, "prefix": "../x"},
            {"at": AT, "known_at": K1, "after": "<script>"},
        ):
            with self.subTest(params=params):
                status, _, body = self.fetch("/sources", params)
                self.assertEqual(status, 400)
                self.assertEqual(json.loads(body), {"error": "invalid_query"})

    def test_source_ids_are_escaped_and_directory_is_paginated(self):
        source_ids = tuple("source-%03d" % i for i in range(105))
        html = _source_catalog_html(self.world, source_ids, {"at": AT, "known_at": K1})
        self.assertIn("<td>source-099</td>", html)
        self.assertNotIn("<td>source-100</td>", html)
        self.assertIn("Next 100 sources", html)
        html = _source_catalog_html(self.world, ('a"><script>alert(1)</script>',),
                                    {"at": AT, "known_at": K1})
        self.assertNotIn('a"><script>', html)
        self.assertIn("&lt;script&gt;", html)

    def test_sources_without_current_points_remain_discoverable_as_history(self):
        old = {"at": AT, "known_at": "2025-01-01T00:00:00Z"}
        status, _, page = self.fetch("/sources", old)
        self.assertEqual(status, 200)
        self.assertIn(b"<td>survey-east</td><td>0</td><td>0</td>", page)
        self.assertIn(b"History", page)
        self.assertNotIn(b">Map</a>", page)


if __name__ == "__main__":
    unittest.main()
