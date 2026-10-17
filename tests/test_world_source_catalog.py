"""Browse original sources at explicit world time T and knowledge cutoff K."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from monde.local_api import create_server, _source_catalog_html
from monde.world import WorldMini
from tests.test_world_geojson_disagreements import AT, K1, K2, disputed, add

OLD = "2026-01-09T00:00:00Z"
PAST_WORLD = "2025-12-01T00:00:00Z"


class SourceCatalogTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "saved.json"
        self.world = disputed()
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
        self.dir.cleanup()

    def fetch(self, route, params):
        conn = http.client.HTTPConnection("127.0.0.1",
                                          self.server.server_port, timeout=5)
        conn.request("GET", route + "?" + urlencode(params),
                     headers={"Host": "127.0.0.1:" + str(self.server.server_port)})
        reply = conn.getresponse()
        out = (reply.status, dict(reply.getheaders()), reply.read())
        conn.close()
        return out

    def test_catalog_counts_original_reports_without_reconciling_sources(self):
        self.assertEqual(self.world.source_catalog(AT, K1), {
            "world": "OBSERVED", "view": "SOURCE_CATALOG_ONLY",
            "valid_at": AT, "knowledge_cutoff": K1,
            "status": "SOURCES_FOUND",
            "sources": [
                {"source_id": "survey-east", "known_assertion_count": 2,
                 "current_point_report_count": 2,
                 "current_point_entity_count": 2},
                {"source_id": "survey-west", "known_assertion_count": 1,
                 "current_point_report_count": 1,
                 "current_point_entity_count": 1}]})

    def test_sources_unknown_at_earlier_cutoff_and_invalid_at_earlier_world_time(self):
        old = self.world.source_catalog(AT, OLD)
        self.assertEqual(old["status"], "NO_SOURCES")
        self.assertEqual(old["sources"], [])
        earlier = self.world.source_catalog(PAST_WORLD, K1)
        self.assertEqual([x["current_point_report_count"] for x in earlier["sources"]],
                         [0, 0])
        self.assertEqual([x["known_assertion_count"] for x in earlier["sources"]],
                         [2, 1])

    def test_current_point_count_excludes_superseded_revision(self):
        world = disputed()
        original = next(a for a in world.export()["assertions"]
                        if a["entity"] == "site-a"
                        and any(ev["id"] == a["evidence_id"]
                                and ev["source_id"] == "survey-east"
                                for ev in world.export()["evidence"]))
        world.add_evidence({"id": "evidence-revision", "source_id": "survey-east",
                            "locator": "fixture://revision", "captured_at": K2,
                            "source_event_at": None})
        world.add_assertion({**original, "id": "assertion-revision",
                             "evidence_id": "evidence-revision",
                             "known_at": K2, "supersedes": original["id"]})
        before = world.export()
        earlier = world.source_catalog(AT, K1)
        later = world.source_catalog(AT, K2)
        self.assertEqual(earlier["sources"][0]["known_assertion_count"], 2)
        self.assertEqual(later["sources"][0]["known_assertion_count"], 3)
        self.assertEqual(later["sources"][0]["current_point_report_count"], 2)
        self.assertEqual(world.export(), before)

    def test_real_local_json_and_browser_deep_links(self):
        query = {"at": AT, "known_at": K1}
        status, headers, raw = self.fetch("/sources", query)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw), self.world.source_catalog(AT, K1))
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        status, headers, html = self.fetch("/sources-browser", query)
        self.assertEqual(status, 200)
        self.assertIn(b"survey-east", html)
        self.assertIn(b"survey-west", html)
        self.assertIn(b"/inspect?view=source-history&amp;source=survey-east", html)
        self.assertIn(b"known_at=2026-01-10T10%3A00%3A00Z", html)
        self.assertIn("script-src 'none'", headers["Content-Security-Policy"])
        self.assertNotIn(b"<script", html)
        status, _, explore = self.fetch("/explore", {})
        self.assertEqual(status, 200)
        self.assertIn(b'action="/sources-browser"', explore)

    def test_browser_escapes_ids_and_rejects_bad_times_and_unknown_params(self):
        document = {"valid_at": AT, "knowledge_cutoff": K1,
                    "sources": [{"source_id": 's"><script>alert(1)</script>',
                                 "known_assertion_count": 1,
                                 "current_point_report_count": 1,
                                 "current_point_entity_count": 1}]}
        html = _source_catalog_html(document)
        self.assertNotIn('s"><script>', html)
        self.assertIn("&lt;script&gt;", html)
        for route, params in (
            ("/sources", {"at": "bad", "known_at": K1}),
            ("/sources-browser", {"at": AT, "known_at": "bad"}),
            ("/sources", {"at": AT, "known_at": K1, "extra": "x"}),
            ("/sources-browser", {"at": AT, "known_at": K1, "extra": "x"})):
            status, _, body = self.fetch(route, params)
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(body), {"error": "invalid_query"})


if __name__ == "__main__":
    unittest.main()
