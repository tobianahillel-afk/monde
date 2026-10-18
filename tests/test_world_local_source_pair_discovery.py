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
        detail_url = table.rsplit(b'<a href="', 1)[1].split(b'"', 1)[0]
        self.assertNotIn(b"&amp;source=survey-a", detail_url)
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



    def test_ranked_discovery_opens_example_original_point_map(self):
        """Ranking -> focused original-report offline map, without changing data."""
        from html import unescape
        import re
        from urllib.parse import parse_qs, urlsplit

        for axis in ("knowledge", "world"):
            if axis == "knowledge":
                args = self.knowledge()
                server = self.server
            else:
                other = sample(dateline=True)
                other_file = Path(self.tmp.name) / "world-map-drilldown.json"
                other.save(other_file)
                server = create_server(other_file)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                args = {"discover": "1", "axis": "world", "from_at": EARLY,
                        "to_at": LATE, "known_at": KNOWN}
            try:
                status, _, html = self.get({**args, "format": "table"}, server)
                self.assertEqual(status, 200)
                # Follow this row's drilldown, not the separate bulk map link.
                maps = [unescape(value) for value in re.findall(
                    r'href="([^"]+)"[^>]*>Map original example evidence</a>',
                    html.decode("utf-8"))
                    if parse_qs(urlsplit(unescape(value)).query).get("format")
                    == ["html"]]
                self.assertTrue(maps, "ranked pair must open an actual evidence map")
                query = parse_qs(urlsplit(maps[0]).query)
                self.assertEqual(query["axis"], [axis])
                self.assertEqual(query["entity"], [
                    json.loads(self.get({**args, "format": "json"}, server)[2])
                    ["pairs"][0]["example_entity"]])
                self.assertNotIn("source", query)
                self.assertNotIn("discover", query)
                self.assertNotIn("rank", query)
                self.assertNotIn("top", query)
                for key in ("at", "from_known_at", "to_known_at") if axis == "knowledge" else (
                        "from_at", "to_at", "known_at"):
                    self.assertEqual(query[key], [args[key]])
                status, headers, map_html = self.get(
                    {k: value[0] for k, value in query.items()}, server)
                self.assertEqual(status, 200)
                self.assertTrue(headers["Content-Type"].startswith("text/html"))
                self.assertIn(b"monde_source_pair", map_html)
                self.assertIn(b"monde_original_assertion_id", map_html)
            finally:
                if axis == "world":
                    server.shutdown()
                    thread.join(timeout=5)
                    server.server_close()

    def test_ranked_discovery_exports_original_example_geojson(self):
        """Ranked evidence -> real GeoJSON; never lose source/temporal provenance."""
        from html import unescape
        from urllib.parse import parse_qs, urlsplit
        import re

        for axis in ("knowledge", "world"):
            if axis == "knowledge":
                server = self.server
                args = {**self.knowledge(), "source": "survey-a",
                        "rank": "separation", "top": "1"}
            else:
                file = Path(self.tmp.name) / "ranked-world-geojson.json"
                world = sample(dateline=True)
                world.save(file)
                original = file.read_bytes()
                server = create_server(file)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                args = {"discover": "1", "axis": "world",
                        "from_at": EARLY, "to_at": LATE,
                        "known_at": KNOWN, "top": "1"}
            try:
                status, _, html = self.get({**args, "format": "table"}, server)
                self.assertEqual(status, 200)
                text = html.decode("utf-8")
                self.assertIn("Download original example GeoJSON", text)
                hrefs = [unescape(h) for h in re.findall(
                    r'<a download="source-pair-example.geojson" href="([^"]+)"',
                    text)]
                self.assertEqual(len(hrefs), 1)
                query = parse_qs(urlsplit(hrefs[0]).query)
                self.assertEqual(query["format"], ["geojson"])
                self.assertEqual(query["axis"], [axis])
                for excluded in ("discover", "rank", "top", "source"):
                    self.assertNotIn(excluded, query)
                for cutoff in (("at", "from_known_at", "to_known_at")
                               if axis == "knowledge" else
                               ("from_at", "to_at", "known_at")):
                    self.assertEqual(query[cutoff], [args[cutoff]])
                ranked = json.loads(self.get({**args, "format": "json"}, server)[2])
                example = ranked["pairs"][0]
                self.assertEqual(query["entity"], [example["example_entity"]])
                status, _, raw = self.get(
                    {key: values[0] for key, values in query.items()}, server)
                self.assertEqual(status, 200)
                exported = json.loads(raw)
                self.assertEqual(exported["type"], "FeatureCollection")
                self.assertEqual(exported["monde_comparison"]["comparison_axis"], axis)
                self.assertEqual(exported["monde_comparison"]["cutoffs"], ranked["cutoffs"])
                self.assertEqual({feature["properties"]["source_id"]
                                  for feature in exported["features"]},
                                 {example["source_a"], example["source_b"]})
                self.assertEqual({feature["properties"]["entity"]
                                  for feature in exported["features"]},
                                 {example["example_entity"]})
                original_ids = {
                    f["properties"]["monde_original_assertion_id"]
                    for f in exported["features"]
                }
                self.assertTrue(set(example["example_assertion_ids"])
                                .issubset(original_ids))
                self.assertTrue(all(
                    f["properties"]["monde_source_pair"]["period"] in
                    ("earlier", "later") for f in exported["features"]))
            finally:
                if axis == "world":
                    server.shutdown()
                    thread.join(timeout=5)
                    server.server_close()
                    self.assertEqual(file.read_bytes(), original)

    def test_ranked_geojson_empty_results_have_no_download_link(self):
        args = {"discover": "1", "axis": "knowledge", "at": AT,
                "from_known_at": "2026-01-02T00:00:00Z",
                "to_known_at": "2026-01-02T12:00:00Z"}
        status, _, html = self.get(args)
        self.assertEqual(status, 200)
        self.assertNotIn(b"Download original example GeoJSON", html)

    def test_ranked_discovery_without_joint_reports_has_no_example_map(self):
        args = {"discover": "1", "axis": "knowledge", "at": AT,
                "from_known_at": "2026-01-02T00:00:00Z",
                "to_known_at": "2026-01-02T12:00:00Z"}
        status, _, html = self.get(args)
        self.assertEqual(status, 200)
        self.assertNotIn(b"Map original example evidence", html)
        self.assertIn(b"NO JOINT ORIGINAL SOURCE REPORTS", html)



    def test_discovery_bulk_geojson_original_evidence_and_browser_link(self):
        from monde.source_pair_changes import discovery_geojson
        args = {**self.knowledge(), "rank": "decreasing", "top": "1"}
        code, headers, raw = self.get({**args, "format": "geojson"})
        self.assertEqual(code, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        doc = json.loads(raw)
        self.assertEqual(doc["type"], "FeatureCollection")
        self.assertEqual(doc["monde_discovery"]["exported_pairs"], 1)
        self.assertEqual(doc["monde_discovery"]["rank"], "decreasing")
        ids = {(feature["properties"]["monde_discovery"]["period"],
                feature["properties"]["monde_original_assertion_id"])
               for feature in doc["features"]}
        self.assertEqual(ids, {("earlier", "a-a1"), ("earlier", "a-b1"),
                               ("later", "a-a1"), ("later", "a-b2")})
        self.assertEqual(len({f["id"] for f in doc["features"]}), 4)
        self.assertTrue(all(f["geometry"]["type"] == "Point"
                            for f in doc["features"]))
        self.assertTrue(all(f["properties"]["source_id"] in ("survey-a", "survey-b")
                            for f in doc["features"]))
        ranked = json.loads(self.get({**args, "format": "json"})[2])
        self.assertEqual(doc, discovery_geojson(self.world, ranked))
        code, _, html = self.get({**args, "format": "table"})
        self.assertEqual(code, 200)
        self.assertIn(b"Download all ranked original examples GeoJSON", html)
        self.assertIn(b'ranked-original-source-pairs.geojson', html)
        self.assertEqual(self.file.read_bytes(), self.original)

    def test_discovery_bulk_geojson_both_axes_and_source_focus(self):
        world = sample(dateline=True)
        file = Path(self.tmp.name) / "bulk-world.json"
        world.save(file)
        before = file.read_bytes()
        server = create_server(file)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            args = {"discover": "1", "axis": "world", "from_at": EARLY,
                    "to_at": LATE, "known_at": KNOWN, "format": "geojson"}
            code, _, raw = self.get(args, server)
            self.assertEqual(code, 200)
            all_pairs = json.loads(raw)
            self.assertEqual(all_pairs["monde_discovery"]["axis"], "world")
            original_ids = {f["id"] for cutoff in (EARLY, LATE)
                            for f in world.export_geojson(cutoff, KNOWN)["features"]}
            self.assertTrue(all_pairs["features"])
            self.assertTrue(all(
                f["properties"]["monde_original_assertion_id"] in original_ids
                for f in all_pairs["features"]))
            source = all_pairs["features"][0]["properties"]["source_id"]
            code, _, raw = self.get({**args, "source": source}, server)
            self.assertEqual(code, 200)
            focused = json.loads(raw)
            self.assertEqual(focused["monde_discovery"]["source_focus"], source)
            self.assertTrue(all(source in (
                f["properties"]["monde_discovery"]["source_a"],
                f["properties"]["monde_discovery"]["source_b"])
                for f in focused["features"]))
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
            self.assertEqual(file.read_bytes(), before)

    def test_discovery_bulk_geojson_empty_and_invalid_params(self):
        args = {**self.knowledge(), "from_known_at": "2026-01-02T00:00:00Z",
                "to_known_at": "2026-01-02T12:00:00Z", "format": "geojson"}
        code, _, raw = self.get(args)
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(raw)["features"], [])
        for invalid in ({"top": "101"}, {"rank": "invalid"},
                        {"source": "../bad"}, {"unexpected": "x"}):
            code, _, raw = self.get({**self.knowledge(), "format": "geojson", **invalid})
            self.assertEqual(code, 400)
            self.assertEqual(json.loads(raw), {"error": "invalid_query"})
        self.assertEqual(self.file.read_bytes(), self.original)

    def test_ranked_all_examples_open_one_offline_map(self):
        args = {**self.knowledge(), "rank": "decreasing", "top": "1"}
        code, headers, page = self.get({**args, "format": "html"})
        self.assertEqual(code, 200)
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertEqual(headers["Cache-Control"], "no-store")
        for text in (b"monde_discovery", b"monde_comparison_period",
                     b"monde_original_assertion_id", b"survey-a", b"survey-b",
                     b"decreasing", b"data.monde_comparison"):
            self.assertIn(text, page)
        code, _, table = self.get({**args, "format": "table"})
        self.assertEqual(code, 200)
        self.assertIn(b"Map all ranked original examples", table)
        self.assertIn(b"format=html", table)

    def test_ranked_all_examples_world_axis_and_cutoffs(self):
        w = sample(dateline=True)
        file = Path(self.tmp.name) / "ranked-all-world.json"
        w.save(file)
        before = file.read_bytes()
        srv = create_server(file)
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        try:
            args = {"discover": "1", "axis": "world", "from_at": EARLY,
                    "to_at": LATE, "known_at": KNOWN, "format": "html"}
            code, headers, page = self.get(args, srv)
            self.assertEqual(code, 200)
            for text in (b"monde_discovery", b"world",
                         EARLY.encode(), LATE.encode()):
                self.assertIn(text, page)
            self.assertEqual(headers["Cache-Control"], "no-store")
        finally:
            srv.shutdown()
            thread.join(timeout=5)
            srv.server_close()
            self.assertEqual(file.read_bytes(), before)

    def test_ranked_all_examples_empty_and_invalid(self):
        args = {**self.knowledge(), "from_known_at": "2026-01-02T00:00:00Z",
                "to_known_at": "2026-01-02T12:00:00Z", "format": "html"}
        code, _, page = self.get(args)
        self.assertEqual(code, 200)
        self.assertIn(b"NO_MATCHES", page)
        for invalid in ({"top": "101"}, {"rank": "none"},
                        {"source": "../bad"}, {"unexpected": "x"}):
            code, _, body = self.get({**self.knowledge(), "format": "html", **invalid})
            self.assertEqual(code, 400)
            self.assertEqual(json.loads(body), {"error": "invalid_query"})
        self.assertEqual(self.file.read_bytes(), self.original)


    def test_minimum_joint_entities_filters_before_top_and_preserves_default(self):
        query = {**self.knowledge(), "format": "json"}
        status, _, raw = self.get(query)
        self.assertEqual(status, 200)
        baseline = json.loads(raw)
        self.assertEqual(baseline["total_pairs"], 1)
        self.assertNotIn("min_joint_entities", baseline)
        status, _, raw = self.get({**query, "min_joint": "1"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw), baseline)
        for rank in ("separation", "decreasing"):
            case = {**query, "min_joint": "2", "top": "1", "rank": rank}
            status, _, raw = self.get(case)
            self.assertEqual(status, 200)
            result = json.loads(raw)
            self.assertEqual(result["pairs"], [])
            self.assertEqual(result["total_pairs"], 0)
            self.assertEqual(result["min_joint_entities"], 2)
            status, _, page = self.get({**case, "format": "table"})
            self.assertEqual(status, 200)
            self.assertIn(b"Minimum independently joint-reported entities: 2", page)
            status, _, data = self.get({**case, "format": "geojson"})
            self.assertEqual(status, 200)
            geo = json.loads(data)
            self.assertEqual(geo["features"], [])
            self.assertEqual(geo["monde_discovery"]["min_joint_entities"], 2)
        self.assertEqual(self.file.read_bytes(), self.original)

    def test_minimum_joint_entities_strict_input_world_axis_and_map(self):
        from monde.source_pair_changes import discover_source_pairs
        for bad in (0, -1, True, 10001, "2"):
            with self.assertRaises(ValueError):
                discover_source_pairs(self.world, "knowledge",
                    ((AT, BEFORE), (AT, AFTER)), min_joint_entities=bad)
        for bad in ("", "0", "-1", "2.0", "1e2", "10001", " 2", "0002"):
            code, _, body = self.get({**self.knowledge(), "min_joint": bad})
            self.assertEqual(code, 400)
            self.assertEqual(json.loads(body), {"error": "invalid_query"})
        status, _, page = self.get()
        self.assertEqual(status, 200)
        self.assertEqual(page.count(b'name="min_joint"'), 2)
        world = sample(dateline=True)
        file = Path(self.tmp.name) / "joint-world.json"
        world.save(file)
        before = file.read_bytes()
        srv = create_server(file)
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        try:
            q = {"discover": "1", "axis": "world", "from_at": EARLY,
                 "to_at": LATE, "known_at": KNOWN, "min_joint": "100"}
            code, _, raw = self.get({**q, "format": "json"}, srv)
            self.assertEqual(code, 200)
            self.assertEqual(json.loads(raw)["pairs"], [])
            code, _, html = self.get({**q, "format": "html"}, srv)
            self.assertEqual(code, 200)
            self.assertIn(b"NO_MATCHES", html)
            code, _, csv_body = self.get({**q, "format": "csv"}, srv)
            self.assertEqual(code, 200)
            self.assertEqual(list(csv.DictReader(io.StringIO(csv_body.decode()))), [])
        finally:
            srv.shutdown()
            thread.join(timeout=5)
            srv.server_close()
            self.assertEqual(file.read_bytes(), before)


    def test_minimum_joint_entities_selects_supported_pair_before_top_ranking(self):
        # A far-away one-entity disagreement must not conceal a pair
        # independently reported for two distinct entities.
        from monde.world import WorldMini
        world = WorldMini()
        def add(source, label, entity, longitude, known, supersedes=None):
            world.add_evidence({"id": "e-joint-" + label, "source_id": source,
                                "locator": "fixture://joint-" + label,
                                "captured_at": known, "source_event_at": known})
            world.add_assertion({"id": "a-joint-" + label, "entity": entity,
                                 "attribute": "geo_point",
                                 "value": {"type": "Point",
                                           "coordinates": [longitude, 0.0]},
                                 "evidence_id": "e-joint-" + label,
                                 "kind": "CLAIM", "known_at": known,
                                 "valid_from": "2026-01-01T00:00:00Z",
                                 "valid_to": None, "supersedes": supersedes})
        add("survey-a", "a-site1", "site-1", 0., "2026-01-02T01:00:00Z")
        add("survey-b", "b-site1", "site-1", 2., "2026-01-02T02:00:00Z")
        add("survey-a", "a-site2", "site-2", 0., "2026-01-02T03:00:00Z")
        add("survey-b", "b-site2", "site-2", 1., "2026-01-02T04:00:00Z")
        add("survey-c", "c-site1", "site-1", 100., "2026-01-02T05:00:00Z")
        add("survey-b", "b-site1-revised", "site-1", 1.,
            "2026-01-04T00:00:00Z", supersedes="a-joint-b-site1")
        target = Path(self.tmp.name) / "multi-source-ranking.json"
        world.save(target)
        saved = target.read_bytes()
        server = create_server(target)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            q = {**self.knowledge(), "top": "1", "format": "json"}
            code, _, body = self.get(q, server)
            self.assertEqual(code, 200)
            first = json.loads(body)["pairs"][0]
            self.assertIn("survey-c", (first["source_a"], first["source_b"]))
            code, _, body = self.get({**q, "min_joint": "2"}, server)
            self.assertEqual(code, 200)
            selected = json.loads(body)
            self.assertEqual(selected["total_pairs"], 1)
            pair = selected["pairs"][0]
            self.assertEqual((pair["source_a"], pair["source_b"]),
                             ("survey-a", "survey-b"))
            self.assertEqual(pair["joint_entities"], 2)
            code, _, body = self.get({**q, "min_joint": "2",
                                      "rank": "decreasing"}, server)
            self.assertEqual(code, 200)
            trend = json.loads(body)["pairs"][0]
            self.assertEqual(trend["comparable_entities"], 2)
            self.assertEqual(trend["matching_entities"], 1)
            code, _, body = self.get({**q, "min_joint": "3"}, server)
            self.assertEqual(code, 200)
            self.assertEqual(json.loads(body)["pairs"], [])
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
            self.assertEqual(target.read_bytes(), saved)


    def test_rank_coverage_prioritizes_broad_joint_evidence_through_http(self):
        from monde.world import WorldMini
        world = WorldMini()
        def add(source, entity, longitude, key):
            known = "2026-01-02T01:00:00Z"
            world.add_evidence({"id": "e-cover-" + key, "source_id": source,
                                "locator": "fixture://cover-" + key,
                                "captured_at": known, "source_event_at": known})
            world.add_assertion({"id": "a-cover-" + key, "entity": entity,
                                 "attribute": "geo_point",
                                 "value": {"type": "Point", "coordinates": [longitude, 0.]},
                                 "evidence_id": "e-cover-" + key,
                                 "kind": "CLAIM", "known_at": known,
                                 "valid_from": "2026-01-01T00:00:00Z",
                                 "valid_to": None, "supersedes": None})
        for entity, tag in (("site-1", "1"), ("site-2", "2")):
            add("survey-a", entity, 0., "a" + tag)
            add("survey-b", entity, 1., "b" + tag)
        add("survey-c", "site-1", 100., "c1")
        file = Path(self.tmp.name) / "coverage.json"
        world.save(file)
        saved = file.read_bytes()
        server = create_server(file)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            q = {**self.knowledge(), "format": "json", "top": "1"}
            status, _, raw = self.get(q, server)
            self.assertEqual(status, 200)
            first = json.loads(raw)
            self.assertNotIn("rank", first)
            self.assertIn("survey-c", (first["pairs"][0]["source_a"],
                                       first["pairs"][0]["source_b"]))
            status, _, raw = self.get({**q, "rank": "coverage"}, server)
            self.assertEqual(status, 200)
            result = json.loads(raw)
            self.assertEqual(result["rank"], "coverage")
            self.assertEqual(result["total_pairs"], 3)
            self.assertEqual((result["pairs"][0]["source_a"],
                              result["pairs"][0]["source_b"]),
                             ("survey-a", "survey-b"))
            self.assertEqual(result["pairs"][0]["joint_entities"], 2)
            self.assertTrue(result["pairs"][0]["example_assertion_ids"])
            self.assertNotIn("rank_delta_km", result["pairs"][0])
            for fmt in ("table", "csv", "geojson", "html"):
                status, _, raw = self.get({**q, "rank": "coverage",
                                           "format": fmt}, server)
                self.assertEqual(status, 200, fmt)
                if fmt == "csv":
                    rows = list(csv.DictReader(io.StringIO(raw.decode())))
                    self.assertEqual(rows[0]["joint_entities"], "2")
                elif fmt == "geojson":
                    feature = json.loads(raw)
                    self.assertEqual(feature["monde_discovery"]["rank"], "coverage")
                    self.assertEqual({f["properties"]["source_id"]
                                      for f in feature["features"]},
                                     {"survey-a", "survey-b"})
                elif fmt == "table":
                    self.assertIn(b"source_a=survey-a", raw)
                    self.assertIn(b"source_b=survey-b", raw)
                else:
                    self.assertIn(b"MONDE", raw)
            status, _, raw = self.get(server=server)
            self.assertEqual(status, 200)
            self.assertEqual(raw.count(b'value="coverage"'), 2)
            for wrong in ("Coverage", "coverages", "", "=coverage"):
                status, _, _ = self.get({**q, "rank": wrong}, server)
                self.assertEqual(status, 400, wrong)
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
            self.assertEqual(file.read_bytes(), saved)

    def test_coverage_rank_preserves_world_and_knowledge_cutoffs(self):
        result = discover_source_pairs(self.world, "knowledge",
                                       ((AT, BEFORE), (AT, AFTER)),
                                       rank="coverage")
        self.assertEqual(result["rank"], "coverage")
        self.assertNotIn("rank_delta_km", result["pairs"][0])
        later = discover_source_pairs(
            self.world, "knowledge",
            ((AT, "2026-01-02T12:00:00Z"), (AT, AFTER)), rank="coverage")
        self.assertEqual(later["pairs"][0]["joint_earlier_entities"], 0)
        self.assertEqual(later["pairs"][0]["joint_later_entities"], 1)
        q = {"discover": "1", "axis": "world",
             "from_at": EARLY, "to_at": LATE, "known_at": KNOWN,
             "format": "json", "rank": "coverage"}
        status, _, raw = self.get(q)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)["rank"], "coverage")
        self.assertEqual(json.loads(raw)["axis"], "world")

if __name__ == "__main__":
    unittest.main()

