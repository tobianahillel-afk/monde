"""Real persisted WorldMini + loopback HTTP source coverage behavior."""
import csv
import io
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from monde.local_api import create_server
from monde.source_pair_changes import source_directory
from tests.test_world_source_pair_changes import fixture_world, AT, BEFORE, AFTER
from tests.test_world_source_pair_world_changes import sample, EARLY, LATE, KNOWN


class SourceDirectoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = Path(self.tmp.name) / "world.json"
        self.world = fixture_world()
        self.world.save(self.saved)
        self.snapshot = self.saved.read_bytes()
        self.server = create_server(self.saved)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()
        self.assertEqual(self.saved.read_bytes(), self.snapshot)
        self.tmp.cleanup()

    def get(self, query=None, server=None):
        srv = server or self.server
        target = "/source-pair" + ("?" + urlencode(query) if query else "")
        connection = http.client.HTTPConnection(
            "127.0.0.1", srv.server_port, timeout=5)
        connection.request(
            "GET", target,
            headers={"Host": "127.0.0.1:" + str(srv.server_port)})
        reply = connection.getresponse()
        output = reply.status, dict(reply.getheaders()), reply.read()
        connection.close()
        return output

    def knowledge(self):
        return {"directory": "1", "axis": "knowledge", "at": AT,
                "from_known_at": BEFORE, "to_known_at": AFTER}

    def test_source_directory_json_matches_original_reports_and_links(self):
        query = self.knowledge()
        status, headers, raw = self.get({**query, "format": "json"})
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        doc = json.loads(raw)
        self.assertEqual(doc["schema"], "MONDE_SOURCE_COVERAGE_DIRECTORY_V1")
        self.assertEqual(doc, source_directory(
            self.world, "knowledge", ((AT, BEFORE), (AT, AFTER))))
        self.assertEqual(doc["total_sources"], 2)
        for source in doc["sources"]:
            self.assertTrue(source["example_assertion_ids"])
            self.assertEqual(source["later_entities"],
                             source["continuously_reported_entities"] +
                             source["newly_reported_entities"])
            self.assertEqual(source["earlier_entities"],
                             source["continuously_reported_entities"] +
                             source["no_longer_reported_entities"])
        status, _, html = self.get({**query, "format": "table"})
        self.assertEqual(status, 200)
        self.assertIn(b"Source comparisons", html)
        self.assertIn(b"discover=1", html)
        self.assertIn(b"source=survey-a", html)
        self.assertNotIn(b"<script", html)
        status, _, home = self.get()
        self.assertEqual(status, 200)
        self.assertEqual(home.count(b'name="directory"'), 2)

    def test_directory_csv_preserves_source_provenance_and_deep_link(self):
        q = self.knowledge()
        _, _, raw_json = self.get({**q, "format": "json"})
        original = json.loads(raw_json)["sources"]
        status, headers, raw_csv = self.get({**q, "format": "csv"})
        self.assertEqual(status, 200)
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        rows = list(csv.DictReader(io.StringIO(raw_csv.decode("utf-8"))))
        self.assertEqual([x["source_id"] for x in rows],
                         [x["source_id"] for x in original])
        for row, source in zip(rows, original):
            self.assertEqual(int(row["later_entities"]), source["later_entities"])
            self.assertEqual(json.loads(row["example_assertion_ids"]),
                             source["example_assertion_ids"])
        status, _, raw = self.get({"discover": "1", "axis": "knowledge",
                                   "at": AT, "from_known_at": BEFORE,
                                   "to_known_at": AFTER, "source": "survey-a",
                                   "format": "json"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)["source_focus"], "survey-a")

    def test_world_axis_parity_and_immutable_snapshot(self):
        world = sample(dateline=True)
        saved = Path(self.tmp.name) / "world-axis.json"
        world.save(saved)
        original = saved.read_bytes()
        server = create_server(saved)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            query = {"directory": "1", "axis": "world",
                     "from_at": EARLY, "to_at": LATE, "known_at": KNOWN}
            status, _, raw = self.get({**query, "format": "json"}, server)
            self.assertEqual(status, 200)
            doc = json.loads(raw)
            self.assertEqual(doc, source_directory(
                world, "world", ((EARLY, KNOWN), (LATE, KNOWN))))
            self.assertIn("not verified movement", doc["interpretation"])
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
            self.assertEqual(saved.read_bytes(), original)

    def test_reject_invalid_cutoffs_modes_and_unknown_keys(self):
        q = self.knowledge()
        for extra in ({"directory": "0"}, {"axis": "invalid"},
                      {"format": "yaml"}, {"discover": "1"},
                      {"source": "survey-a"}, {"top": "1"},
                      {"from_known_at": AFTER, "to_known_at": BEFORE},
                      {"from_known_at": "2026-01-01T00:00:00"}):
            with self.subTest(extra=extra):
                status, _, raw = self.get({
                    **q, **extra, "format": extra.get("format", "json")})
                self.assertEqual(status, 400)
                self.assertEqual(json.loads(raw), {"error": "invalid_query"})

    def test_no_reports_remain_unknown_not_source_agreement(self):
        q = {"directory": "1", "axis": "knowledge", "at": AT,
             "from_known_at": "2025-01-01T00:00:00Z",
             "to_known_at": "2025-01-02T00:00:00Z"}
        status, _, raw = self.get({**q, "format": "json"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)["sources"], [])
        status, _, html = self.get(q)
        self.assertEqual(status, 200)
        self.assertIn(b"NO ORIGINAL POINT SOURCE REPORTS", html)


if __name__ == "__main__":
    unittest.main()
