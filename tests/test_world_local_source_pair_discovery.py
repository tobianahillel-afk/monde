"""Source-pair discovery through real persisted WorldMini and loopback HTTP."""
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
from monde.source_pair_changes import discover_source_pairs, discovery_csv
from tests.test_world_source_pair_changes import fixture_world, AT, BEFORE, AFTER
from tests.test_world_source_pair_world_changes import sample, EARLY, LATE, KNOWN


class SourcePairDiscoveryHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.file = Path(self.tmp.name) / "world.json"
        self.world = fixture_world()
        self.world.save(self.file)
        self.original = self.file.read_bytes()
        self.server = create_server(self.file)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()
        self.assertEqual(self.file.read_bytes(), self.original)
        self.tmp.cleanup()

    def get(self, args=None, server=None):
        srv = server or self.server
        url = "/source-pair" + ("?" + urlencode(args) if args else "")
        conn = http.client.HTTPConnection("127.0.0.1", srv.server_port, timeout=5)
        conn.request("GET", url, headers={"Host": "127.0.0.1:" + str(srv.server_port)})
        response = conn.getresponse()
        data = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return data

    def knowledge(self):
        return {"discover": "1", "axis": "knowledge", "at": AT,
                "from_known_at": BEFORE, "to_known_at": AFTER}

    def test_discovery_ranks_original_pairs_and_links_to_existing_evidence(self):
        args = self.knowledge()
        code, headers, raw = self.get({**args, "format": "json"})
        self.assertEqual(code, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        doc = json.loads(raw)
        self.assertEqual(doc["schema"], "MONDE_SOURCE_PAIR_DISCOVERY_V1")
        self.assertEqual(doc["total_pairs"], 1)
        pair = doc["pairs"][0]
        self.assertEqual((pair["source_a"], pair["source_b"]),
                         ("survey-a", "survey-b"))
        self.assertEqual(pair["joint_entities"], 1)
        self.assertEqual(pair["joint_earlier_entities"], 1)
        self.assertEqual(pair["joint_later_entities"], 1)
        self.assertGreater(pair["max_nearest_km"], 200)
        self.assertEqual(pair["example_assertion_ids"], ["a-a1", "a-b1"])
        status, _, html = self.get({**args, "format": "table"})
        self.assertEqual(status, 200)
        self.assertIn(b"/source-pair?axis=knowledge", html)
        self.assertIn(b"source_a=survey-a", html)
        self.assertIn(b"source_b=survey-b", html)
        self.assertIn(b"Geographic differences between original reporters", html)
        self.assertNotIn(b"<script", html)
        status, _, page = self.get()
        self.assertEqual(status, 200)
        self.assertEqual(page.count(b'name="discover"'), 2)

    def test_discovery_requires_joint_reports_and_keeps_unknown_distinct(self):
        result = discover_source_pairs(self.world, "knowledge",
                                       ((AT, "2026-01-02T12:00:00Z"),
                                        (AT, AFTER)))
        self.assertEqual(result["pairs"][0]["joint_earlier_entities"], 0)
        self.assertEqual(result["pairs"][0]["joint_later_entities"], 1)
        self.assertEqual(result["pairs"][0]["example_period"], "later")
        # With no joint reports at either cutoff, do not invent a zero-distance pair.
        empty = discover_source_pairs(self.world, "knowledge",
                                      ((AT, "2026-01-02T00:00:00Z"),
                                       (AT, "2026-01-02T12:00:00Z")))
        self.assertEqual(empty["total_pairs"], 0)
        code, _, html = self.get({"discover": "1", "axis": "knowledge",
                                 "at": AT, "from_known_at": "2026-01-02T00:00:00Z",
                                 "to_known_at": "2026-01-02T12:00:00Z"})
        self.assertEqual(code, 200)
        self.assertIn(b"NO JOINT ORIGINAL SOURCE REPORTS", html)

    def test_world_validity_axis_matches_original_pair_evidence(self):
        w = sample(dateline=True)
        file = Path(self.tmp.name) / "world-validity.json"
        w.save(file)
        saved = file.read_bytes()
        server = create_server(file)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            args = {"discover": "1", "axis": "world", "from_at": EARLY,
                    "to_at": LATE, "known_at": KNOWN, "format": "json"}
            status, _, data = self.get(args, server)
            self.assertEqual(status, 200)
            result = json.loads(data)
            self.assertEqual(result, discover_source_pairs(
                w, "world", ((EARLY, KNOWN), (LATE, KNOWN))))
            self.assertEqual(result["cutoffs"]["earlier"]["world_at"], EARLY)
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
            self.assertEqual(file.read_bytes(), saved)

    def test_strict_query_rejection_and_limit(self):
        for extra in (
            {"discover": "0"}, {"axis": "unknown"}, {"top": "0"},
            {"top": "101"}, {"top": "1e2"}, {"top": "1.0"},
            {"format": "yaml"}, {"source_a": "survey-a"},
            {"from_known_at": AFTER, "to_known_at": BEFORE},
            {"from_known_at": "2026-01-01T00:00:00"},
        ):
            with self.subTest(extra=extra):
                code, _, raw = self.get({**self.knowledge(), **extra,
                                         "format": extra.get("format", "json")})
                self.assertEqual(code, 400)
                self.assertEqual(json.loads(raw), {"error": "invalid_query"})
        code, _, data = self.get({**self.knowledge(), "top": "1", "format": "json"})
        self.assertEqual(code, 200)
        self.assertEqual(len(json.loads(data)["pairs"]), 1)


    def test_decreasing_rank_preserves_both_original_report_revisions(self):
        args = {**self.knowledge(), "rank": "decreasing", "format": "json"}
        status, _, raw = self.get(args)
        self.assertEqual(status, 200)
        doc = json.loads(raw)
        self.assertEqual(doc["rank"], "decreasing")
        self.assertEqual(doc["total_pairs"], 1)
        pair = doc["pairs"][0]
        self.assertEqual(pair["comparable_entities"], 1)
        self.assertEqual(pair["matching_entities"], 1)
        self.assertLess(pair["rank_delta_km"], -100)
        self.assertEqual(pair["example_earlier_assertion_ids"],
                         ["a-a1", "a-b1"])
        self.assertEqual(pair["example_later_assertion_ids"],
                         ["a-a1", "a-b2"])
        status, _, html = self.get({**args, "format": "table"})
        self.assertEqual(status, 200)
        self.assertIn(b"Change km", html)
        self.assertIn(b"source_a=survey-a", html)
        self.assertIn(b"source_b=survey-b", html)
        self.assertNotIn(b"<script", html)

    def test_missing_joint_cutoff_does_not_create_a_false_trend(self):
        args = {**self.knowledge(), "from_known_at": "2026-01-02T12:00:00Z",
                "rank": "decreasing", "format": "json"}
        status, _, raw = self.get(args)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)["pairs"], [])
        default = discover_source_pairs(self.world, "knowledge",
            ((AT, "2026-01-02T12:00:00Z"), (AT, AFTER)))
        self.assertEqual(default["total_pairs"], 1)

    def test_increasing_pair_after_original_source_correction(self):
        from monde.world import WorldMini
        world = WorldMini()
        def add(source, suffix, longitude, known, supersedes=None):
            world.add_evidence({"id": "e-" + suffix, "source_id": source,
                                "locator": "fixture://" + suffix,
                                "captured_at": known, "source_event_at": known})
            world.add_assertion({"id": "a-" + suffix, "entity": "growth-site",
                                 "attribute": "geo_point",
                                 "value": {"type": "Point",
                                           "coordinates": [longitude, 0.]},
                                 "evidence_id": "e-" + suffix, "kind": "CLAIM",
                                 "known_at": known,
                                 "valid_from": "2026-01-01T00:00:00Z",
                                 "valid_to": None, "supersedes": supersedes})
        add("reporter-a", "new-a", 0., "2026-01-02T00:00:00Z")
        add("reporter-b", "new-b1", 0.2, "2026-01-03T00:00:00Z")
        add("reporter-b", "new-b2", 3., "2026-01-04T00:00:00Z",
            "a-new-b1")
        file = Path(self.tmp.name) / "growing.json"
        world.save(file)
        before = file.read_bytes()
        srv = create_server(file)
        worker = threading.Thread(target=srv.serve_forever, daemon=True)
        worker.start()
        try:
            args = {**self.knowledge(), "rank": "increasing", "format": "json"}
            status, _, body = self.get(args, srv)
            self.assertEqual(status, 200)
            pair = json.loads(body)["pairs"][0]
            self.assertGreater(pair["rank_delta_km"], 300)
            self.assertEqual(pair["example_entity"], "growth-site")
            self.assertEqual(pair["example_earlier_assertion_ids"],
                             ["a-new-a", "a-new-b1"])
            self.assertEqual(pair["example_later_assertion_ids"],
                             ["a-new-a", "a-new-b2"])
            status, _, body = self.get({**args, "rank": "decreasing"}, srv)
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["total_pairs"], 0)
        finally:
            srv.shutdown()
            worker.join(timeout=5)
            srv.server_close()
            self.assertEqual(file.read_bytes(), before)


    def test_focused_discovery_is_source_specific_and_links_original_evidence(self):
        args = {**self.knowledge(), "source": "survey-a", "format": "json"}
        status, _, body = self.get(args)
        self.assertEqual(status, 200)
        result = json.loads(body)
        self.assertEqual(result["source_focus"], "survey-a")
        self.assertEqual(result["total_pairs"], 1)
        self.assertEqual((result["pairs"][0]["source_a"],
                          result["pairs"][0]["source_b"]),
                         ("survey-a", "survey-b"))
        status, _, data = self.get({**args, "source": "unknown-source"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data)["pairs"], [])
        status, _, table = self.get({**args, "format": "table"})
        self.assertEqual(status, 200)
        self.assertIn(b"Original reporter focus: survey-a", table)
        self.assertIn(b"source_a=survey-a", table)
        self.assertIn(b"source_b=survey-b", table)
        self.assertNotIn(b"&amp;source=survey-a", table)
        status, _, homepage = self.get()
        self.assertEqual(status, 200)
        self.assertEqual(homepage.count(b'name="source" list="pair-ids"'), 2)
        self.assertEqual(self.file.read_bytes(), self.original)

    def test_source_focus_retains_trends_original_assertions_and_both_axes(self):
        args = {**self.knowledge(), "rank": "decreasing",
                "source": "survey-b", "format": "json"}
        status, _, raw = self.get(args)
        self.assertEqual(status, 200)
        pair = json.loads(raw)["pairs"][0]
        self.assertLess(pair["rank_delta_km"], 0)
        self.assertEqual(pair["example_earlier_assertion_ids"],
                         ["a-a1", "a-b1"])
        self.assertEqual(pair["example_later_assertion_ids"],
                         ["a-a1", "a-b2"])
        # An empty browser form input means no source focus (parse_qs
        # omits blank values), preserving default discovery behavior.
        status, _, raw = self.get({**args, "source": ""})
        self.assertEqual(status, 200)
        self.assertNotIn("source_focus", json.loads(raw))
        status, _, raw = self.get({**args, "source": "a\nb"})
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(raw), {"error": "invalid_query"})
        unreported = discover_source_pairs(
            sample(dateline=True), "world",
            ((EARLY, KNOWN), (LATE, KNOWN)), source="unknown-source")
        self.assertEqual(unreported["pairs"], [])
        self.assertEqual(unreported["source_focus"], "unknown-source")
        self.assertEqual(self.file.read_bytes(), self.original)

    def test_world_axis_trends_and_bad_rank_rejection(self):
        from tests.test_world_source_pair_world_changes import sample, EARLY, LATE, KNOWN
        cutoffs = ((EARLY, KNOWN), (LATE, KNOWN))
        self.assertEqual(discover_source_pairs(sample(), "world", cutoffs,
                         rank="decreasing")["total_pairs"], 1)
        self.assertEqual(discover_source_pairs(sample(), "world", cutoffs,
                         rank="increasing")["total_pairs"], 0)
        for bad in ("", "growth", "INCREASING", "other"):
            with self.subTest(bad=bad):
                status, _, raw = self.get({**self.knowledge(),
                                           "rank": bad, "format": "json"})
                self.assertEqual(status, 400)
                self.assertEqual(json.loads(raw), {"error": "invalid_query"})


    def test_ranked_csv_download_preserves_original_evidence_and_query(self):
        params = {**self.knowledge(), "source": "survey-a", "format": "csv"}
        status, headers, data = self.get(params)
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("attachment;", headers["Content-Disposition"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(int(headers["Content-Length"]), len(data))
        records = list(csv.DictReader(io.StringIO(data.decode("utf-8"))))
        self.assertEqual(len(records), 1)
        row = records[0]
        self.assertEqual((row["source_a"], row["source_b"]),
                         ("survey-a", "survey-b"))
        self.assertEqual(row["source_focus"], "survey-a")
        self.assertEqual(row["axis"], "knowledge")
        self.assertEqual(row["earlier_knowledge_at"], BEFORE)
        self.assertEqual(row["later_knowledge_at"], AFTER)
        self.assertEqual(json.loads(row["example_assertion_ids"]),
                         ["a-a1", "a-b1"])
        self.assertEqual(row["total_pairs"], "1")
        status, _, html = self.get({**params, "format": "table"})
        self.assertEqual(status, 200)
        self.assertIn(b"Download ranked source evidence CSV", html)
        self.assertIn(b"source=survey-a", html)
        self.assertIn(b"format=csv", html)
        status, _, homepage = self.get()
        self.assertEqual(status, 200)
        self.assertEqual(homepage.count(b"Download ranked evidence CSV"), 2)

    def test_ranked_csv_world_axis_and_unknown_are_not_fabricated(self):
        params = {"discover": "1", "axis": "world",
                  "from_at": EARLY, "to_at": LATE, "known_at": KNOWN,
                  "format": "csv"}
        world = sample(dateline=True)
        target = Path(self.tmp.name) / "world-rank.json"
        world.save(target)
        server = create_server(target)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            status, _, body = self.get(params, server)
            self.assertEqual(status, 200)
            rows = list(csv.DictReader(io.StringIO(body.decode("utf-8"))))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["axis"], "world")
            self.assertEqual(rows[0]["earlier_world_at"], EARLY)
            self.assertEqual(rows[0]["later_world_at"], LATE)
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
        status, _, body = self.get({**self.knowledge(),
                                   "source": "unknown-source", "format": "csv"})
        self.assertEqual(status, 200)
        self.assertEqual(len(list(csv.DictReader(io.StringIO(
            body.decode("utf-8"))))), 0)
        self.assertTrue(body.startswith(b"axis,"))
        self.assertEqual(self.file.read_bytes(), self.original)

    def test_csv_spreadsheet_formula_prefixes_are_neutralized(self):
        data = discover_source_pairs(
            self.world, "knowledge", ((AT, BEFORE), (AT, AFTER)))
        data["source_focus"] = "=HYPERLINK('https://example.invalid')"
        data["pairs"][0]["source_a"] = "+SUM(1,1)"
        data["pairs"][0]["source_b"] = "@cmd"
        data["pairs"][0]["example_entity"] = "-1+2"
        values = list(csv.DictReader(io.StringIO(discovery_csv(data))))
        for field in ("source_focus", "source_a", "source_b", "example_entity"):
            self.assertTrue(values[0][field].startswith("'"))
        self.assertEqual(values[0]["example_assertion_ids"], '["a-a1","a-b1"]')


if __name__ == "__main__":
    unittest.main()
