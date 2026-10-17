"""HTTP regression: readable original source disagreement reports."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from monde.local_api import create_server
from tests.test_world_geojson_disagreements import AT, K1, disputed, add

QUERY = {"bbox": "2.3,48.8,2.4,48.9", "at": AT, "known_at": K1}


class DisagreementReportHTTPTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "snapshot.json"
        self.world = disputed()
        add(self.world, "survey-north", [2.34, 48.84], entity="site-b")
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
        self.folder.cleanup()

    def fetch(self, route, args):
        client = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        client.request("GET", route + "?" + urlencode(args),
                       headers={"Host": "127.0.0.1:" + str(self.server.server_port)})
        response = client.getresponse()
        output = response.status, dict(response.getheaders()), response.read()
        client.close()
        return output

    def test_source_focus_retains_opposing_provenance_and_links(self):
        status, headers, body = self.fetch(
            "/disagreement-report", {**QUERY, "source": "survey-east"})
        self.assertEqual(status, 200)
        html = body.decode("utf-8")
        self.assertIn("site-a", html)
        self.assertNotIn("<h2>site-b</h2>", html)
        self.assertIn("survey-east", html)
        self.assertIn("survey-west", html)
        self.assertIn("assertion_id", html)
        self.assertIn("evidence_id", html)
        self.assertIn("/inspect?view=entity&amp;entity=site-a", html)
        self.assertIn("/viewer?view=disagreements", html)
        self.assertIn("/map-disagreements?", html)
        self.assertIn("outside", html)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertIn("script-src 'none'", headers["Content-Security-Policy"])
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_unfiltered_and_empty_source_do_not_invent_ground_truth(self):
        status, _, body = self.fetch("/disagreement-report", QUERY)
        self.assertEqual(status, 200)
        html = body.decode()
        self.assertIn("site-a", html)
        self.assertIn("site-b", html)
        self.assertIn("No consensus location", html)
        status, _, body = self.fetch(
            "/disagreement-report", {**QUERY, "source": "unseen-source"})
        self.assertEqual(status, 200)
        self.assertIn(b"NO MATCHING SOURCE DISAGREEMENT", body)
        self.assertNotIn(b"<section>", body)

    def test_explore_form_and_rejected_inputs(self):
        status, _, body = self.fetch("/explore", {})
        self.assertEqual(status, 200)
        self.assertIn(b'formaction="/disagreement-report"', body)
        status, _, _ = self.fetch(
            "/disagreement-report", {"view": "disagreements", **QUERY, "source": "survey-east"})
        self.assertEqual(status, 200)
        for request in (
            {"view": "wrong", **QUERY},
            {**QUERY, "source": "../other"},
            {**QUERY, "unexpected": "value"},
            {**QUERY, "at": "not-a-date"},
        ):
            status, _, body = self.fetch("/disagreement-report", request)
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(body), {"error": "invalid_query"})

    def test_bitemporal_map_links_preserve_original_source(self):
        status, _, body = self.fetch(
            "/disagreement-report", {**QUERY, "source": "survey-east"})
        self.assertEqual(status, 200)
        html = body.decode()
        self.assertIn("source=survey-east", html)
        self.assertIn("known_at=", html)
        self.assertIn("at=", html)
        self.assertIn("Original source disagreement evidence", html)


if __name__ == "__main__":
    unittest.main()
