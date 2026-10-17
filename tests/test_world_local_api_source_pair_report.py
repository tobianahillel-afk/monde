"""Real browser-ready, read-only original pair evidence report tests."""
import http.client
import json
from html.parser import HTMLParser
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import parse_qs, urlencode, urlsplit

from monde.local_api import create_server
from tests.test_world_geojson_disagreements import AT, K1, disputed

QUERY = {"bbox": "2.3,48.8,2.4,48.9", "at": AT, "known_at": K1,
         "source_a": "survey-east", "source_b": "survey-west"}


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.hrefs.extend(value for name, value in attrs if name == "href")


class SourcePairReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "world.json"
        self.world = disputed()
        self.world.save(self.path)
        self.before = self.path.read_bytes()
        self.server = create_server(self.path)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.worker.join(timeout=5)
        self.server.server_close()
        self.assertEqual(self.before, self.path.read_bytes())
        self.tmp.cleanup()

    def fetch(self, route, query):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        conn.request("GET", route + "?" + urlencode(query),
                     headers={"Host": "127.0.0.1:" + str(self.server.server_port)})
        response = conn.getresponse()
        answer = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return answer

    def test_full_pair_includes_both_originals_and_offscreen_report(self):
        query = {"view": "compare-sources", **QUERY}
        code, headers, html = self.fetch("/source-pair-report", query)
        self.assertEqual(code, 200)
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn("script-src 'none'", headers["Content-Security-Policy"])
        self.assertIn("connect-src 'none'", headers["Content-Security-Policy"])
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        page = html.decode()
        self.assertIn("survey-east", page)
        self.assertIn("survey-west", page)
        self.assertIn("[2.35, 48.85]", page)
        self.assertIn("[7.2, 47.5]", page)
        self.assertIn("Outside selection", page)
        self.assertIn("Matching entities: 1; original Point reports: 2", page)
        self.assertNotIn("site-b</td>", page)
        self.assertNotIn("<script", page)
        evidence = json.loads(self.fetch("/map-compare-sources", QUERY)[2])
        for feature in evidence["features"]:
            self.assertIn(feature["properties"]["assertion_id"], page)
            self.assertIn(feature["properties"]["evidence_id"], page)

    def test_report_links_back_to_map_and_original_dossier(self):
        params = {"view": "compare-sources", **QUERY, "different_only": "1"}
        code, _, body = self.fetch("/source-pair-report", params)
        self.assertEqual(code, 200)
        page = body.decode()
        self.assertIn("Only entities with different complete reported Point sets.", page)
        parser = Links()
        parser.feed(page)
        self.assertEqual(len([x for x in parser.hrefs if x.startswith("/inspect?")]), 2)
        links = [urlsplit(link) for link in parser.hrefs]
        comparison = next(x for x in links if x.path == "/viewer")
        self.assertEqual(parse_qs(comparison.query)["different_only"], ["1"])
        self.assertEqual(parse_qs(comparison.query)["source_b"], ["survey-west"])
        for item in links:
            if item.path == "/inspect":
                args = {key: value[0] for key, value in parse_qs(item.query).items()}
                self.assertEqual(args["view"], "entity")
                self.assertEqual(args["entity"], "site-a")
                self.assertEqual(args["at"], AT)
                self.assertEqual(args["known_at"], K1)
                self.assertEqual(self.fetch(item.path, args)[0], 200)
        code, _, home = self.fetch("/explore", {})
        self.assertEqual(code, 200)
        self.assertIn(b'formaction="/source-pair-report"', home)

    def test_empty_pair_does_not_report_unknown_as_a_difference(self):
        params = {"view": "compare-sources", **QUERY, "source_b": "unknown"}
        code, _, body = self.fetch("/source-pair-report", params)
        self.assertEqual(code, 200)
        self.assertIn(b"Matching entities: 0; original Point reports: 0", body)
        self.assertNotIn(b"<td>site-a</td>", body)
        self.assertEqual(self.fetch("/source-pair-report", {
            **params, "different_only": "1"})[0], 200)

    def test_invalid_and_unexpected_parameters_are_rejected(self):
        good = {"view": "compare-sources", **QUERY}
        for params in (
            {**good, "source_a": "../bad"},
            {**good, "source_b": "survey-east"},
            {**good, "different_only": "0"},
            {**good, "different_only": ""},
            {**good, "view": "current"},
            {**good, "unexpected": "x"},
        ):
            code, _, raw = self.fetch("/source-pair-report", params)
            self.assertEqual(code, 400)
            self.assertEqual(json.loads(raw), {"error": "invalid_query"})
        self.assertEqual(self.fetch("/source-pair-report", {})[0], 400)
