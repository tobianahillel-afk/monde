"""Real persisted WorldMini + loopback HTTP source coverage behavior."""
import csv
import io
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from html import unescape
import re
from urllib.parse import urlencode, urlsplit, parse_qs

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
                      {"top": "1"},
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

    def test_source_details_original_assertions_and_existing_history_links(self):
        q = {**self.knowledge(), "source": "survey-b"}
        status, _, raw = self.get({**q, "format": "json"})
        self.assertEqual(status, 200)
        doc = json.loads(raw)
        self.assertEqual(doc["schema"], "MONDE_SOURCE_COVERAGE_DETAIL_V1")
        self.assertEqual(doc["source_id"], "survey-b")
        self.assertEqual(doc["earlier_entities"], 1)
        self.assertEqual(doc["later_entities"], 1)
        self.assertEqual(doc["entities"][0]["entity"], "site-1")
        self.assertEqual(doc["entities"][0]["status"], "REPORTED_AT_BOTH")
        self.assertEqual(doc["entities"][0]["earlier_assertion_ids"], ["a-b1"])
        self.assertEqual(doc["entities"][0]["later_assertion_ids"], ["a-b2"])
        status, _, html = self.get(q)
        self.assertEqual(status, 200)
        self.assertIn(b"source-history", html)
        self.assertIn(b"source=survey-b", html)
        self.assertIn(b"a-b1", html)
        self.assertIn(b"a-b2", html)
        status, _, directory = self.get({**self.knowledge(), "format": "table"})
        self.assertEqual(status, 200)
        self.assertIn(b"Find partners", directory)
        self.assertIn(b"source=survey-b", directory)

    def test_source_detail_csv_original_ids_and_missing_source(self):
        q = {**self.knowledge(), "source": "survey-a"}
        status, headers, raw = self.get({**q, "format": "csv"})
        self.assertEqual(status, 200)
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
        self.assertEqual([r["entity"] for r in rows],
                         ["site-1", "site-only-one-source"])
        self.assertEqual(json.loads(rows[0]["earlier_assertion_ids"]), ["a-a1"])
        self.assertEqual(json.loads(rows[1]["later_assertion_ids"]), ["a-orphan"])
        status, _, raw = self.get({**self.knowledge(), "source": "not-present",
                                   "format": "json"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)["entities"], [])

    def test_source_detail_bad_input_and_world_axis(self):
        for bad in ("\ninvalid", "x" * 201):
            status, _, raw = self.get({**self.knowledge(), "source": bad,
                                       "format": "json"})
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(raw), {"error": "invalid_query"})
        status, _, raw = self.get({**self.knowledge(), "source": "survey-a",
                                   "top": "2", "format": "json"})
        self.assertEqual(status, 400)
        status, _, raw = self.get({**self.knowledge(), "source": "survey-a",
                                   "format": "html"})
        self.assertEqual(status, 400)
        world = sample(dateline=True)
        path = Path(self.tmp.name) / "world-detail.json"
        world.save(path)
        before = path.read_bytes()
        server = create_server(path)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            q = {"directory": "1", "source": "not-present", "axis": "world",
                 "from_at": EARLY, "to_at": LATE, "known_at": KNOWN,
                 "format": "json"}
            status, _, raw = self.get(q, server)
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(raw)["axis"], "world")
        finally:
            server.shutdown()
            worker.join(timeout=5)
            server.server_close()
            self.assertEqual(path.read_bytes(), before)




    def test_filter_reporting_transitions_preserves_original_ids(self):
        query = self.knowledge()
        q = {**query, "source": "survey-a"}
        status, _, raw = self.get({**q, "change": "both", "format": "json"})
        self.assertEqual(status, 200)
        both = json.loads(raw)
        self.assertEqual(both["reporting_filter"], "both")
        self.assertEqual(both["matched_entities"], 2)
        self.assertEqual([r["entity"] for r in both["entities"]],
                         ["site-1", "site-only-one-source"])
        self.assertEqual(both["entities"][0]["earlier_assertion_ids"], ["a-a1"])
        status, _, raw = self.get({**q, "change": "new", "format": "csv"})
        self.assertEqual(status, 200)
        self.assertEqual(list(csv.DictReader(io.StringIO(raw.decode("utf-8")))), [])
        status, _, html = self.get({**q, "change": "new", "format": "table"})
        self.assertEqual(status, 200)
        self.assertIn(b"Newly reported", html)
        self.assertIn(b"0 matching original entities", html)
        self.assertIn(b"change=gone", html)
        self.assertIn(b"aria-current", html)
        self.assertNotIn(b"<script", html)
        status, _, raw = self.get({**q, "format": "json"})
        self.assertNotIn("reporting_filter", json.loads(raw))

    def test_new_reporting_filter_real_knowledge_cutoffs_and_csv_parity(self):
        query = {**self.knowledge(),
                 "from_known_at": "2026-01-02T12:00:00Z", "source": "survey-a"}
        status, _, raw = self.get({**query, "change": "new", "format": "json"})
        self.assertEqual(status, 200)
        doc = json.loads(raw)
        self.assertEqual(doc["matched_entities"], 1)
        self.assertEqual([r["entity"] for r in doc["entities"]],
                         ["site-only-one-source"])
        self.assertEqual(doc["entities"][0]["later_assertion_ids"], ["a-orphan"])
        status, _, raw = self.get({**query, "change": "new", "format": "csv"})
        self.assertEqual(status, 200)
        rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
        self.assertEqual([r["entity"] for r in rows], ["site-only-one-source"])
        self.assertEqual(json.loads(rows[0]["later_assertion_ids"]), ["a-orphan"])
        status, _, raw = self.get({**query, "change": "both", "format": "json"})
        self.assertEqual(json.loads(raw)["matched_entities"], 1)

    def test_reporting_filter_rejects_unknown_values_and_discovery_misuse(self):
        for query in ({**self.knowledge(), "source": "survey-a", "change": "OTHER"},
                      {**self.knowledge(), "source": "survey-a", "change": ""},
                      {**self.knowledge(), "source": "survey-a",
                       "change": "new", "discover": "1"}):
            with self.subTest(query=query):
                status, _, raw = self.get({**query, "format": "json"})
                self.assertEqual(status, 400)
                self.assertEqual(json.loads(raw), {"error": "invalid_query"})

    def test_reporting_filter_world_axis_and_no_snapshot_writes(self):
        world = sample(dateline=True)
        path = Path(self.tmp.name) / "world-filter.json"
        world.save(path)
        original = path.read_bytes()
        server = create_server(path)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            query = {"directory": "1", "axis": "world", "source": "not-present",
                     "from_at": EARLY, "to_at": LATE, "known_at": KNOWN,
                     "change": "gone", "format": "json"}
            status, _, raw = self.get(query, server)
            self.assertEqual(status, 200)
            doc = json.loads(raw)
            self.assertEqual(doc["matched_entities"], 0)
            self.assertEqual(doc["reporting_filter"], "gone")
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
            self.assertEqual(path.read_bytes(), original)



    def test_source_geojson_preserves_original_points(self):
        q = {**self.knowledge(), "source": "survey-a"}
        status, _, raw = self.get({**q, "format": "geojson"})
        self.assertEqual(status, 200)
        doc = json.loads(raw)
        self.assertEqual(doc["type"], "FeatureCollection")
        self.assertEqual(doc["monde_source_coverage"]["source_id"], "survey-a")
        self.assertEqual(doc["monde_source_coverage"]["axis"], "knowledge")
        original = {}
        for period, known in (("earlier", BEFORE), ("later", AFTER)):
            for feature in self.world.export_geojson(AT, known)["features"]:
                if feature["properties"]["source_id"] == "survey-a":
                    original[period, feature["id"]] = feature
        self.assertEqual(len(doc["features"]), len(original))
        for feature in doc["features"]:
            p = feature["properties"]
            key = p["monde_comparison_period"], p["monde_original_assertion_id"]
            self.assertIn(key, original)
            self.assertEqual(feature["geometry"], original[key]["geometry"])
            self.assertEqual(p["evidence_id"],
                             original[key]["properties"]["evidence_id"])
            self.assertEqual(p["monde_world_at"], AT)
        _, _, page = self.get(q)
        self.assertIn(b"Download original Point GeoJSON for both cutoffs", page)

    def test_source_geojson_transition_filter_and_strict_scope(self):
        q = {**self.knowledge(), "source": "survey-a",
             "from_known_at": "2026-01-02T12:00:00Z",
             "change": "new", "format": "geojson"}
        status, _, raw = self.get(q)
        self.assertEqual(status, 200)
        doc = json.loads(raw)
        self.assertEqual(doc["monde_source_coverage"]["reporting_filter"], "new")
        self.assertEqual(doc["monde_source_coverage"]["matched_entities"], 1)
        self.assertTrue(doc["features"])
        self.assertEqual({f["properties"]["entity"] for f in doc["features"]},
                         {"site-only-one-source"})
        self.assertEqual({f["properties"]["monde_comparison_period"]
                          for f in doc["features"]}, {"later"})
        status, _, raw = self.get({**q, "source": "unknown-source"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)["features"], [])
        for bad in ({**self.knowledge(), "format": "geojson"},
                    {**q, "change": "invalid"},
                    {**q, "source": ""}):
            status, _, _ = self.get(bad)
            self.assertEqual(status, 400)

    def test_source_geojson_world_time_and_immutable_model(self):
        world = sample(dateline=True)
        saved = Path(self.tmp.name) / "source-world.json"
        world.save(saved)
        original = saved.read_bytes()
        server = create_server(saved)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            q = {"directory": "1", "axis": "world", "from_at": EARLY,
                 "to_at": LATE, "known_at": KNOWN}
            status, _, raw = self.get({**q, "format": "json"}, server)
            self.assertEqual(status, 200)
            sources = json.loads(raw)["sources"]
            self.assertTrue(sources)
            status, _, raw = self.get({**q, "source": sources[0]["source_id"],
                                       "format": "geojson"}, server)
            self.assertEqual(status, 200)
            doc = json.loads(raw)
            self.assertEqual(doc["monde_source_coverage"]["axis"], "world")
            self.assertEqual(doc["monde_source_coverage"]["cutoffs"]["earlier"]
                             ["world_at"], EARLY)
            self.assertEqual(doc["monde_source_coverage"]["cutoffs"]["later"]
                             ["world_at"], LATE)
            for feature in doc["features"]:
                self.assertEqual(feature["properties"]["source_id"],
                                 sources[0]["source_id"])
                self.assertEqual(feature["properties"]["monde_known_at"], KNOWN)
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
            self.assertEqual(saved.read_bytes(), original)

    def test_coverage_map_renders_original_points_and_reports_without_mutation(self):
        from monde.source_pair_changes import (
            source_directory_detail, source_directory_geojson, source_directory_map)
        query = {**self.knowledge(), "source": "survey-a"}
        status, headers, page = self.get({**query, "format": "map"})
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn(b"Both comparison periods show original source-reported", page)
        self.assertIn(b"monde_original_assertion_id", page)
        self.assertIn(b"monde_comparison_period", page)
        self.assertIn(b"monde_inside_bbox", page)
        # Both HTML inspector links and detail labels must use the selected
        # original Point's own cutoffs, never the synthetic display envelope.
        self.assertIn(b"sourceCoveragePeriod ? p.monde_world_at", page)
        self.assertIn(b"sourceCoveragePeriod ? p.monde_known_at", page)
        self.assertIn(b"Original reporting period: ", page)
        detail = source_directory_detail(
            self.world, "knowledge", ((AT, BEFORE), (AT, AFTER)), "survey-a")
        original = source_directory_geojson(self.world, detail)
        mapped = source_directory_map(self.world, detail)
        self.assertEqual([f["geometry"] for f in mapped["features"]],
                         [f["geometry"] for f in original["features"]])
        self.assertEqual([f["properties"]["monde_original_assertion_id"]
                          for f in mapped["features"]],
                         [f["properties"]["monde_original_assertion_id"]
                          for f in original["features"]])
        self.assertTrue(all(f["properties"]["monde_inside_bbox"]
                            for f in mapped["features"]))
        self.assertEqual(mapped["monde_bbox_query"]["total_source_features"],
                         len(mapped["features"]))
        status, _, detail_page = self.get(query)
        self.assertEqual(status, 200)
        self.assertIn(b"Map original source Points at both cutoffs", detail_page)
        empty_status, _, empty = self.get({
            **query, "source": "nonexistent-source", "format": "map"})
        self.assertEqual(empty_status, 200)
        self.assertIn(b"NO_MATCHES", empty)
        for bad in ({**self.knowledge(), "format": "map"},
                    {**query, "format": "map", "change": "unrecognized"}):
            self.assertEqual(self.get(bad)[0], 400)

    def test_coverage_map_world_time_and_strict_original_source_scope(self):
        from monde.source_pair_changes import (
            source_directory_detail, source_directory_map)
        world = sample(dateline=True)
        path = Path(self.tmp.name) / "world-axis.json"
        world.save(path)
        initial = path.read_bytes()
        server = create_server(path)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            query = {"directory": "1", "axis": "world",
                     "from_at": EARLY, "to_at": LATE, "known_at": KNOWN}
            source = source_directory(world, "world",
                                      ((EARLY, KNOWN), (LATE, KNOWN))
                                      )["sources"][0]["source_id"]
            status, _, body = self.get(
                {**query, "source": source, "format": "map"}, server)
            self.assertEqual(status, 200)
            self.assertIn(b"monde_source_coverage", body)
            self.assertIn(b"monde_world_at", body)
            detail = source_directory_detail(
                world, "world", ((EARLY, KNOWN), (LATE, KNOWN)), source)
            mapped = source_directory_map(world, detail)
            self.assertEqual(mapped["monde_source_coverage"]["axis"], "world")
            self.assertEqual(
                mapped["monde_source_coverage"]["display_basis"],
                "BOTH_ORIGINAL_REPORTING_PERIODS_NOT_VERIFIED_MOVEMENT")
            self.assertEqual(
                {f["properties"]["source_id"] for f in mapped["features"]},
                {source} if mapped["features"] else set())
            self.assertEqual(
                mapped["monde_bbox_query"]["total_source_features"],
                len(mapped["features"]))
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
            self.assertEqual(path.read_bytes(), initial)


    def test_reporter_directory_transition_filters_reuse_original_counts(self):
        query = self.knowledge()
        _, _, payload = self.get({**query, "format": "json"})
        original = json.loads(payload)
        categories = {"new": "newly_reported_entities",
                      "gone": "no_longer_reported_entities",
                      "both": "continuously_reported_entities"}
        for mode, count in categories.items():
            with self.subTest(mode=mode):
                expected = [item for item in original["sources"] if item[count] > 0]
                status, _, payload = self.get({**query, "change": mode, "format": "json"})
                self.assertEqual(status, 200)
                result = json.loads(payload)
                self.assertEqual(result["reporting_filter"], mode)
                self.assertEqual(result["available_sources"], original["total_sources"])
                self.assertEqual(result["total_sources"], len(expected))
                self.assertEqual(result["sources"], expected)
                self.assertEqual(result, source_directory(
                    self.world, "knowledge", ((AT, BEFORE), (AT, AFTER)), mode))
                status, _, payload = self.get({**query, "change": mode, "format": "csv"})
                self.assertEqual(status, 200)
                rows = list(csv.DictReader(io.StringIO(payload.decode("utf-8"))))
                self.assertEqual([row["source_id"] for row in rows],
                                 [row["source_id"] for row in expected])
                status, _, html = self.get({**query, "change": mode})
                self.assertEqual(status, 200)
                self.assertIn(b"Original reporter transition filters", html)
                self.assertIn(b'Download matching coverage CSV', html)
                self.assertIn(b'aria-current="page"', html)
                if expected:
                    self.assertIn(b"change=" + mode.encode("ascii"), html)
                    self.assertIn(b"Find partners", html)

    def test_reporter_transition_filters_strict_and_world_time_read_only(self):
        query = self.knowledge()
        for invalid in ("unknown", "all", "", "NEW"):
            status, _, payload = self.get({**query, "change": invalid, "format": "json"})
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(payload), {"error": "invalid_query"})
        empty = {**query, "from_known_at": "2025-01-01T00:00:00Z",
                 "to_known_at": "2025-01-02T00:00:00Z", "change": "new"}
        status, _, payload = self.get({**empty, "format": "json"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(payload)["sources"], [])
        status, _, page = self.get(empty)
        self.assertEqual(status, 200)
        self.assertIn(b"NO MATCHING ORIGINAL SOURCE REPORTING TRANSITIONS", page)
        world = sample(dateline=True)
        saved = Path(self.tmp.name) / "world-filtered.json"
        world.save(saved)
        initial = saved.read_bytes()
        server = create_server(saved)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            base = {"directory": "1", "axis": "world",
                    "from_at": EARLY, "to_at": LATE, "known_at": KNOWN}
            status, _, payload = self.get({**base, "format": "json"}, server)
            self.assertEqual(status, 200)
            original = json.loads(payload)["sources"]
            status, _, payload = self.get(
                {**base, "change": "gone", "format": "json"}, server)
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(payload)["sources"], [
                row for row in original if row["no_longer_reported_entities"] > 0])
        finally:
            server.shutdown()
            worker.join(timeout=5)
            server.server_close()
            self.assertEqual(saved.read_bytes(), initial)


    def test_optional_rank_form_does_not_submit_an_empty_rejected_rank(self):
        status, _, html = self.get()
        self.assertEqual(status, 200)
        self.assertEqual(html.count(b'type="radio" name="rank"'), 2 * 5)
        # The existing source-pair discovery forms still have two ranking menus.
        self.assertEqual(html.count(b'<select name="rank">'), 2)
        self.assertNotIn(b'name="rank" value=""', html)

    def test_rank_original_reporter_transitions_http_json_csv_html(self):
        query = self.knowledge()
        _, _, raw = self.get({**query, "format": "json"})
        original = json.loads(raw)
        scores = {"new": lambda row: row["newly_reported_entities"],
                  "gone": lambda row: row["no_longer_reported_entities"],
                  "turnover": lambda row: (row["newly_reported_entities"] +
                                           row["no_longer_reported_entities"])}
        for mode, key in scores.items():
            with self.subTest(rank=mode):
                status, _, raw = self.get({**query, "rank": mode, "format": "json"})
                self.assertEqual(status, 200)
                result = json.loads(raw)
                self.assertEqual(result["ranking"], mode)
                expected = sorted(original["sources"],
                                  key=lambda row: (-key(row), row["source_id"]))
                self.assertEqual(result["sources"], expected)
                self.assertEqual(result["total_sources"], len(expected))
                status, _, raw = self.get({**query, "rank": mode, "format": "csv"})
                self.assertEqual(status, 200)
                rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
                self.assertEqual([r["source_id"] for r in rows],
                                 [r["source_id"] for r in expected])
                status, _, html = self.get({**query, "rank": mode})
                self.assertEqual(status, 200)
                self.assertIn(b'Original reporter coverage ranking', html)
                self.assertIn(b'aria-current="page"', html)
                self.assertIn(b"rank=" + mode.encode("ascii"), html)
                # Existing reporter detail remains directly navigable.
                if expected:
                    self.assertIn(b"source=" + expected[0]["source_id"].encode(), html)
                self.assertNotIn(b"source=" + expected[0]["source_id"].encode() +
                                 b"&format=table&rank=", html)

    def test_rank_filters_world_time_and_invalid_inputs(self):
        # A ranking is a directory-level read-only view, never a per-source
        # reinterpretation of original evidence.
        for invalid in ("", "NEW", "all", "source", "delta", "turnover%00"):
            status, _, payload = self.get({
                **self.knowledge(), "rank": invalid, "format": "json"})
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(payload), {"error": "invalid_query"})
        status, _, payload = self.get({
            **self.knowledge(), "source": "survey-a",
            "rank": "new", "format": "json"})
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(payload), {"error": "invalid_query"})
        world = sample(dateline=True)
        saved = Path(self.tmp.name) / "rank-world.json"
        world.save(saved)
        initial = saved.read_bytes()
        server = create_server(saved)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            query = {"directory": "1", "axis": "world",
                     "from_at": EARLY, "to_at": LATE, "known_at": KNOWN,
                     "change": "gone", "rank": "turnover"}
            status, _, payload = self.get({**query, "format": "json"}, server)
            self.assertEqual(status, 200)
            ranked = json.loads(payload)
            self.assertEqual(ranked["ranking"], "turnover")
            self.assertEqual(ranked["reporting_filter"], "gone")
            self.assertTrue(all(row["no_longer_reported_entities"] > 0
                                for row in ranked["sources"]))
            expected = sorted(ranked["sources"], key=lambda row: (
                -(row["newly_reported_entities"] +
                  row["no_longer_reported_entities"]), row["source_id"]))
            self.assertEqual(ranked["sources"], expected)
            status, _, raw = self.get({**query, "format": "csv"}, server)
            self.assertEqual(status, 200)
            rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
            self.assertEqual([row["source_id"] for row in rows],
                             [row["source_id"] for row in expected])
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
            self.assertEqual(saved.read_bytes(), initial)


    def test_net_gain_loss_ranking_uses_distinct_entities_not_assertion_volume(self):
        """A mixed-gain-and-loss reporter must not outrank a larger net gain."""
        early = "2025-04-01T00:00:00Z"
        late = "2025-04-02T00:00:00Z"
        fixed = "2025-04-03T00:00:00Z"

        class SourcePointWorld:
            def export_geojson(self, at, known_at):
                before = {
                    "mixed": {"one", "two", "three"},
                    "growing": {"one"},
                    "shrinking": {"a", "b", "c", "d"},
                }
                after = {
                    "mixed": {"one", "four", "five", "six"},
                    "growing": {"one", "two", "three"},
                    "shrinking": {"a", "b"},
                }
                selected = before if known_at == early else after
                return {"features": [
                    {"id": f"{source}-{entity}", "properties": {
                        "source_id": source, "entity": entity}}
                    for source, entities in selected.items()
                    for entity in sorted(entities)
                ]}

        world = SourcePointWorld()
        cutoffs = ((fixed, early), (fixed, late))
        default = source_directory(world, "knowledge", cutoffs)
        gain = source_directory(world, "knowledge", cutoffs, rank="net-gain")
        loss = source_directory(world, "knowledge", cutoffs, rank="net-loss")
        self.assertEqual([row["source_id"] for row in gain["sources"]],
                         ["growing", "mixed", "shrinking"])
        self.assertEqual([row["source_id"] for row in loss["sources"]],
                         ["shrinking", "mixed", "growing"])
        self.assertNotIn("ranking", default)
        self.assertEqual(gain["ranking"], "net-gain")
        self.assertEqual(loss["ranking"], "net-loss")
        for row in gain["sources"]:
            self.assertEqual(row["later_entities"] - row["earlier_entities"],
                             row["newly_reported_entities"] -
                             row["no_longer_reported_entities"])

    def test_net_coverage_http_html_json_csv_and_world_axis(self):
        for axis, world, query in (
            ("knowledge", self.world, self.knowledge()),
            ("world", sample(dateline=True), {
                "directory": "1", "axis": "world", "from_at": EARLY,
                "to_at": LATE, "known_at": KNOWN}),
        ):
            if axis == "world":
                saved = Path(self.tmp.name) / "world-net.json"
                world.save(saved)
                immutable = saved.read_bytes()
                server = create_server(saved)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
            else:
                server = self.server
            try:
                for mode, key in (
                    ("net-gain", lambda x: x["later_entities"] -
                                              x["earlier_entities"]),
                    ("net-loss", lambda x: x["earlier_entities"] -
                                              x["later_entities"]),
                ):
                    with self.subTest(axis=axis, ranking=mode):
                        status, _, data = self.get(
                            {**query, "rank": mode, "format": "json"}, server)
                        self.assertEqual(status, 200)
                        document = json.loads(data)
                        self.assertEqual(document["ranking"], mode)
                        expected = sorted(document["sources"],
                                          key=lambda row: (-key(row), row["source_id"]))
                        self.assertEqual(document["sources"], expected)
                        status, _, csv_body = self.get(
                            {**query, "rank": mode, "format": "csv"}, server)
                        self.assertEqual(status, 200)
                        csv_rows = list(csv.DictReader(io.StringIO(
                            csv_body.decode("utf-8"))))
                        self.assertEqual([r["source_id"] for r in csv_rows],
                                         [r["source_id"] for r in expected])
                        status, _, html = self.get({**query, "rank": mode}, server)
                        self.assertEqual(status, 200)
                        self.assertIn(b"Original reporter coverage ranking", html)
                        self.assertIn(b"rank=" + mode.encode(), html)
                        self.assertIn(b'aria-current="page"', html)
                status, _, default = self.get({**query, "format": "json"}, server)
                self.assertEqual(status, 200)
                self.assertNotIn("ranking", json.loads(default))
            finally:
                if axis == "world":
                    server.shutdown()
                    thread.join(timeout=5)
                    server.server_close()
                    self.assertEqual(saved.read_bytes(), immutable)

    def test_net_coverage_invalid_modes_do_not_change_detail_scope(self):
        query = self.knowledge()
        for invalid in ("net", "NET-GAIN", "net-loss%00", "net-gain ", "0"):
            status, _, data = self.get({**query, "rank": invalid,
                                         "format": "json"})
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(data), {"error": "invalid_query"})
        for mode in ("net-gain", "net-loss"):
            status, _, data = self.get({**query, "source": "survey-a",
                                         "rank": mode, "format": "json"})
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(data), {"error": "invalid_query"})


    def test_source_prefix_search_real_http_json_csv_and_navigation(self):
        query = self.knowledge()
        status, _, original_raw = self.get({**query, "format": "json"})
        self.assertEqual(status, 200)
        original = json.loads(original_raw)
        options = {**query, "source_prefix": "survey-a"}
        status, _, raw = self.get({**options, "format": "json"})
        self.assertEqual(status, 200)
        selected = json.loads(raw)
        self.assertEqual(selected["source_prefix"], "survey-a")
        self.assertEqual(selected["available_sources"], original["total_sources"])
        self.assertEqual(selected["sources"], [item for item in original["sources"]
                          if item["source_id"].startswith("survey-a")])
        for variation in (options, {**options, "rank": "net-gain"},
                          {**options, "rank": "turnover", "change": "both"}):
            status, _, raw = self.get({**variation, "format": "json"})
            self.assertEqual(status, 200)
            filtered = json.loads(raw)
            status, _, csv_body = self.get({**variation, "format": "csv"})
            self.assertEqual(status, 200)
            rows = list(csv.DictReader(io.StringIO(csv_body.decode("utf-8"))))
            self.assertEqual([row["source_id"] for row in rows],
                             [item["source_id"] for item in filtered["sources"]])
        status, _, html_bytes = self.get(options)
        self.assertEqual(status, 200)
        html = html_bytes.decode("utf-8")
        self.assertIn("source_prefix=survey-a", html)
        self.assertIn("matching of", html)
        # Both per-source and partner deep links should remain usable after
        # navigating from a directory with prefix/rank filters applied.
        from html import unescape
        import re
        for params in (options, {**options, "rank": "net-loss"}):
            status, _, html_bytes = self.get(params)
            self.assertEqual(status, 200)
            html = html_bytes.decode("utf-8")
            links = re.findall(r'href="([^"]+)"[^>]*>Find partners</a>', html)
            self.assertTrue(links)
            for link in links:
                url = unescape(link)
                self.assertIn("discover=1", url)
                self.assertNotIn("source_prefix=", url)
                self.assertNotIn("rank=", url)
                connection = http.client.HTTPConnection(
                    "127.0.0.1", self.server.server_port, timeout=5)
                connection.request("GET", url, headers={
                    "Host": "127.0.0.1:" + str(self.server.server_port)})
                reply = connection.getresponse()
                self.assertEqual(reply.status, 200)
                reply.read()
                connection.close()
        status, _, blank_raw = self.get({**query, "source_prefix": "",
                                           "format": "json"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(blank_raw), original)
        status, _, missing = self.get({**query, "source_prefix": "absent",
                                       "format": "json"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(missing)["sources"], [])
        status, _, missing_html = self.get({**query, "source_prefix": "absent"})
        self.assertEqual(status, 200)
        self.assertIn(b"NO MATCHING ORIGINAL SOURCE REPORTING TRANSITIONS",
                      missing_html)

    def test_source_prefix_strict_validation_and_detail_scope(self):
        query = self.knowledge()
        for invalid in ("*", "../", "space name", "survey%00",
                        "a" * 81, "\u00e9"):
            status, _, body = self.get({**query, "source_prefix": invalid,
                                        "format": "json"})
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(body), {"error": "invalid_query"})
        status, _, body = self.get({**query, "source": "survey-a",
                                    "source_prefix": "survey", "format": "json"})
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body), {"error": "invalid_query"})
        with self.assertRaises(ValueError):
            source_directory(self.world, "knowledge", ((AT, BEFORE), (AT, AFTER)),
                             source_prefix="../../")

    def test_source_prefix_world_axis_retains_persisted_model(self):
        world = sample(dateline=True)
        saved = Path(self.tmp.name) / "source-prefix-world.json"
        world.save(saved)
        before = saved.read_bytes()
        server = create_server(saved)
        runner = threading.Thread(target=server.serve_forever, daemon=True)
        runner.start()
        try:
            query = {"directory": "1", "axis": "world",
                     "from_at": EARLY, "to_at": LATE, "known_at": KNOWN}
            status, _, raw = self.get({**query, "format": "json"}, server)
            self.assertEqual(status, 200)
            original = json.loads(raw)["sources"]
            self.assertTrue(original)
            prefix = original[0]["source_id"][:3]
            status, _, raw = self.get({**query, "source_prefix": prefix,
                                       "format": "json"}, server)
            self.assertEqual(status, 200)
            filtered = json.loads(raw)["sources"]
            self.assertEqual(filtered, [row for row in original
                                       if row["source_id"].startswith(prefix)])
            status, _, raw = self.get({**query, "source_prefix": prefix,
                                       "format": "csv"}, server)
            self.assertEqual(status, 200)
            csv_rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
            self.assertEqual([row["source_id"] for row in csv_rows],
                             [row["source_id"] for row in filtered])
        finally:
            server.shutdown()
            runner.join(timeout=5)
            server.server_close()
            self.assertEqual(saved.read_bytes(), before)



    def test_exact_entity_reporter_directory_live_http(self):
        q = self.knowledge()
        status, _, raw = self.get({**q, "format": "json"})
        self.assertEqual(status, 200)
        original = json.loads(raw)
        entity = original["sources"][0]["example_entity"]
        reporters = {feature["properties"]["source_id"]
                     for t in (BEFORE, AFTER)
                     for feature in self.world.export_geojson(AT, t)["features"]
                     if feature["properties"]["entity"] == entity}
        filtered = {**q, "entity": entity}
        status, _, raw = self.get({**filtered, "format": "json"})
        self.assertEqual(status, 200)
        result = json.loads(raw)
        self.assertEqual(result["entity_focus"], entity)
        self.assertEqual(result["available_sources"], original["total_sources"])
        self.assertEqual({row["source_id"] for row in result["sources"]}, reporters)
        for row in result["sources"]:
            full = next(item for item in original["sources"]
                        if item["source_id"] == row["source_id"])
            self.assertEqual(row["example_entity"], entity)
            self.assertEqual(row["earlier_entities"], full["earlier_entities"])
            self.assertEqual(row["later_entities"], full["later_entities"])
            self.assertTrue(row["example_assertion_ids"])
        status, _, body = self.get({**filtered, "format": "csv"})
        self.assertEqual(status, 200)
        rows = list(csv.DictReader(io.StringIO(body.decode("utf-8"))))
        self.assertEqual([row["source_id"] for row in rows],
                         [row["source_id"] for row in result["sources"]])
        status, _, html = self.get(filtered)
        self.assertEqual(status, 200)
        self.assertIn(b"Exact original entity:", html)
        from html import unescape
        import re
        partners = re.findall(rb'href="([^"]+)"[^>]*>Find partners</a>', html)
        self.assertTrue(partners)
        for url in partners:
            self.assertNotIn("entity=", unescape(url.decode()))
        status, _, missing = self.get({**filtered, "entity": "unseen-entity",
                                       "format": "json"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(missing)["sources"], [])

    def test_exact_entity_reporter_validation_and_world_axis(self):
        q = self.knowledge()
        for bad in ("\x00", "\n", "x" * 201):
            status, _, raw = self.get({**q, "entity": bad, "format": "json"})
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(raw), {"error": "invalid_query"})
        status, _, _ = self.get({**q, "source": "survey-a",
                                 "entity": "anything", "format": "json"})
        self.assertEqual(status, 400)
        world = sample(dateline=True)
        saved = Path(self.tmp.name) / "world-entity.json"
        world.save(saved)
        before = saved.read_bytes()
        server = create_server(saved)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            q2 = {"directory": "1", "axis": "world", "from_at": EARLY,
                  "to_at": LATE, "known_at": KNOWN}
            status, _, raw = self.get({**q2, "format": "json"}, server)
            self.assertEqual(status, 200)
            sample_row = json.loads(raw)["sources"][0]
            status, _, raw = self.get({**q2, "entity": sample_row["example_entity"],
                                       "format": "json"}, server)
            self.assertEqual(status, 200)
            self.assertIn(sample_row["source_id"],
                          {x["source_id"] for x in json.loads(raw)["sources"]})
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
            self.assertEqual(saved.read_bytes(), before)


    def test_exact_entity_reporters_map_and_geojson_live_http(self):
        query = self.knowledge()
        status, _, raw = self.get({**query, "format": "json"})
        self.assertEqual(status, 200)
        entity = json.loads(raw)["sources"][0]["example_entity"]
        focused = {**query, "entity": entity}
        status, _, raw = self.get({**focused, "format": "json"})
        self.assertEqual(status, 200)
        directory = json.loads(raw)
        reporters = {row["source_id"] for row in directory["sources"]}
        status, _, raw = self.get({**focused, "format": "geojson"})
        self.assertEqual(status, 200)
        geo = json.loads(raw)
        self.assertEqual(geo["type"], "FeatureCollection")
        self.assertEqual(geo["monde_source_coverage"]["entity_focus"], entity)
        self.assertEqual(geo["monde_source_coverage"]["selected_sources"],
                         len(reporters))
        original = {
            (period, f["id"]): f
            for period, instant in (("earlier", BEFORE), ("later", AFTER))
            for f in self.world.export_geojson(AT, instant)["features"]
        }
        self.assertTrue(geo["features"])
        self.assertEqual({f["properties"]["source_id"] for f in geo["features"]},
                         reporters)
        for feature in geo["features"]:
            p = feature["properties"]
            period, assertion = p["monde_comparison_period"], p["monde_original_assertion_id"]
            original_point = original[(period, assertion)]
            self.assertEqual(p["entity"], entity)
            self.assertEqual(feature["geometry"], original_point["geometry"])
            self.assertEqual(p["source_id"], original_point["properties"]["source_id"])
            self.assertEqual(p["monde_known_at"], BEFORE if period == "earlier" else AFTER)
            self.assertEqual(p["monde_world_at"], AT)
        status, _, html = self.get(focused)
        self.assertEqual(status, 200)
        self.assertIn(b"Map all original reporters of this entity", html)
        self.assertIn(b"Download original reporter Points GeoJSON", html)
        status, _, map_html = self.get({**focused, "format": "map"})
        self.assertEqual(status, 200)
        self.assertIn(b"<!doctype html>", map_html.lower())
        status, _, missing = self.get({**query, "entity": "no-such-report-xyz",
                                      "format": "geojson"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(missing)["features"], [])
        for fmt in ("geojson", "map"):
            status, _, body = self.get({**query, "format": fmt})
            self.assertEqual(status, 400)

    def test_original_reporter_map_world_axis_preserves_saved_world(self):
        world = sample(dateline=True)
        saved = Path(self.tmp.name) / "entity-reporters-map.json"
        world.save(saved)
        before = saved.read_bytes()
        server = create_server(saved)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            q = {"directory": "1", "axis": "world",
                 "from_at": EARLY, "to_at": LATE, "known_at": KNOWN}
            status, _, raw = self.get({**q, "format": "json"}, server)
            self.assertEqual(status, 200)
            entity = json.loads(raw)["sources"][0]["example_entity"]
            status, _, raw = self.get({**q, "entity": entity,
                                       "format": "geojson"}, server)
            self.assertEqual(status, 200)
            features = json.loads(raw)["features"]
            self.assertTrue(features)
            for feature in features:
                p = feature["properties"]
                self.assertEqual(p["entity"], entity)
                self.assertEqual(p["monde_world_at"],
                                 EARLY if p["monde_comparison_period"] == "earlier" else LATE)
                self.assertEqual(p["monde_known_at"], KNOWN)
            status, _, html = self.get({**q, "entity": entity, "format": "map"},
                                       server)
            self.assertEqual(status, 200)
            self.assertIn(b"<!doctype html>", html.lower())
            status, _, raw = self.get({**q, "source": "survey-a",
                                      "entity": entity, "format": "geojson"}, server)
            self.assertEqual(status, 200)
            self.assertTrue(all(
                feature["properties"]["source_id"] == "survey-a" and
                feature["properties"]["entity"] == entity
                for feature in json.loads(raw)["features"]))
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
            self.assertEqual(saved.read_bytes(), before)


    def test_exact_entity_single_original_reporter_map_http(self):
        from html import unescape
        import re
        query = self.knowledge()
        status, _, raw = self.get({**query, "format": "json"})
        self.assertEqual(status, 200)
        row = json.loads(raw)["sources"][0]
        focused = {**query, "entity": row["example_entity"]}
        status, _, html = self.get(focused)
        self.assertEqual(status, 200)
        links = re.findall(
            rb'href="([^"]+)"[^>]*>Map this reporter for the entity</a>',
            html)
        self.assertTrue(links)
        from urllib.parse import parse_qs, urlsplit
        source_query = parse_qs(urlsplit(unescape(links[0].decode())).query)
        self.assertEqual(source_query["format"], ["map"])
        self.assertEqual(source_query["entity"], [row["example_entity"]])
        single = {**focused, "source": source_query["source"][0]}
        status, _, raw = self.get({**single, "format": "geojson"})
        self.assertEqual(status, 200)
        document = json.loads(raw)
        self.assertEqual(document["monde_source_coverage"]["source_focus"],
                         single["source"])
        self.assertEqual(document["monde_source_coverage"]["selected_sources"], 1)
        status, _, raw = self.get({**focused, "format": "geojson"})
        self.assertEqual(status, 200)
        all_reports = json.loads(raw)
        expected = [feature for feature in all_reports["features"]
                    if feature["properties"]["source_id"] == single["source"]]
        self.assertEqual(document["features"], expected)
        self.assertTrue(document["features"])
        status, _, page = self.get({**single, "format": "map"})
        self.assertEqual(status, 200)
        self.assertIn(b"<!doctype html>", page.lower())
        self.assertIn(single["source"].encode(), page)

    def test_original_reporter_intersection_invalid_and_empty(self):
        query = self.knowledge()
        status, _, raw = self.get({**query, "format": "json"})
        entity = json.loads(raw)["sources"][0]["example_entity"]
        for output in ("json", "csv", "table"):
            status, _, raw = self.get({**query, "entity": entity,
                                       "source": "survey-a", "format": output})
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(raw)["error"], "invalid_query")
        for source in ("x" * 201, "survey-a\ninvalid"):
            status, _, raw = self.get({**query, "entity": entity,
                                       "source": source, "format": "geojson"})
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(raw)["error"], "invalid_query")
        status, _, raw = self.get({**query, "entity": entity,
                                   "source": "nonexistent-reporter",
                                   "format": "geojson"})
        self.assertEqual(status, 200)
        empty = json.loads(raw)
        self.assertEqual(empty["features"], [])
        self.assertEqual(empty["monde_source_coverage"]["selected_sources"], 0)
        self.assertEqual(empty["monde_source_coverage"]["source_focus"],
                         "nonexistent-reporter")

    def test_original_reporter_single_source_world_axis_no_mutation(self):
        world = sample(dateline=True)
        saved = Path(self.tmp.name) / "entity-original-reporter.json"
        world.save(saved)
        before = saved.read_bytes()
        server = create_server(saved)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            query = {"directory": "1", "axis": "world",
                     "from_at": EARLY, "to_at": LATE, "known_at": KNOWN}
            status, _, raw = self.get({**query, "format": "json"}, server)
            self.assertEqual(status, 200)
            row = json.loads(raw)["sources"][0]
            selected = {**query, "entity": row["example_entity"],
                        "source": row["source_id"]}
            status, _, raw = self.get({**selected, "format": "geojson"}, server)
            self.assertEqual(status, 200)
            features = json.loads(raw)["features"]
            self.assertTrue(features)
            for feature in features:
                props = feature["properties"]
                self.assertEqual(props["source_id"], row["source_id"])
                self.assertEqual(props["entity"], row["example_entity"])
                self.assertEqual(props["monde_known_at"], KNOWN)
                self.assertEqual(props["monde_world_at"],
                                 EARLY if props["monde_comparison_period"] == "earlier"
                                 else LATE)
            status, _, page = self.get({**selected, "format": "map"}, server)
            self.assertEqual(status, 200)
            self.assertIn(b"<!doctype html>", page.lower())
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
            self.assertEqual(saved.read_bytes(), before)

    def test_exact_entity_compare_two_original_reporters_navigation(self):
        """One native GET form opens the existing source-pair evidence map."""
        from html.parser import HTMLParser

        class FormReader(HTMLParser):
            def __init__(self):
                super().__init__()
                self.forms = []
                self.current = None

            def handle_starttag(self, tag, attrs):
                data = dict(attrs)
                if tag == "form" and data.get("action") == "/source-pair":
                    self.current = {"fields": {}, "selects": {}}
                    self.forms.append(self.current)
                elif self.current is not None and tag == "input":
                    if data.get("name"):
                        self.current["fields"][data["name"]] = data.get("value", "")
                elif self.current is not None and tag == "select":
                    self.selected_name = data.get("name")
                    if self.selected_name in ("source_a", "source_b", "format"):
                        self.current["selects"][self.selected_name] = []
                elif self.current is not None and tag == "option":
                    if hasattr(self, "selected_name") and self.selected_name in (
                            "source_a", "source_b", "format"):
                        self.current["selects"][self.selected_name].append(data)

            def handle_endtag(self, tag):
                if tag == "form":
                    self.current = None
                elif tag == "select":
                    self.selected_name = None

        query = self.knowledge()
        focused = {**query, "entity": "site-1"}
        status, _, raw = self.get(focused)
        self.assertEqual(status, 200)
        reader = FormReader()
        reader.feed(raw.decode("utf-8"))
        candidates = [f for f in reader.forms
                      if set(f["selects"]) == {"source_a", "source_b", "format"}]
        self.assertEqual(len(candidates), 1)
        frm = candidates[0]
        self.assertEqual(frm["fields"]["entity"], "site-1")
        self.assertEqual({x["value"] for x in frm["selects"]["format"]},
                         {"html", "table", "json", "csv", "geojson"})
        self.assertEqual([x["value"] for x in frm["selects"]["format"]
                          if "selected" in x], ["html"])
        for key in ("axis", "at", "from_known_at", "to_known_at"):
            self.assertEqual(frm["fields"][key], query[key])
        self.assertEqual(set(x["value"] for x in frm["selects"]["source_a"]),
                         {"survey-a", "survey-b"})
        self.assertEqual(set(x["value"] for x in frm["selects"]["source_b"]),
                         {"survey-a", "survey-b"})
        first = next(x["value"] for x in frm["selects"]["source_a"]
                     if "selected" in x)
        second = next(x["value"] for x in frm["selects"]["source_b"]
                      if "selected" in x)
        self.assertNotEqual(first, second)
        compare = {**frm["fields"], "source_a": first, "source_b": second,
                   "format": "html"}
        status, _, page = self.get(compare)
        self.assertEqual(status, 200)
        self.assertIn(b"<!doctype html>", page.lower())
        status, _, raw = self.get({**compare, "format": "json"})
        self.assertEqual(status, 200)
        doc = json.loads(raw)
        self.assertEqual([x["entity"] for x in doc["entities"]], ["site-1"])
        self.assertEqual({doc["source_a"], doc["source_b"]},
                         {"survey-a", "survey-b"})
        status, _, raw = self.get({**compare, "format": "geojson"})
        self.assertEqual(status, 200)
        features = json.loads(raw)["features"]
        self.assertTrue(features)
        self.assertEqual({x["properties"]["source_id"] for x in features},
                         {"survey-a", "survey-b"})
        self.assertEqual({x["properties"]["entity"] for x in features}, {"site-1"})


    def test_entity_original_reporters_export_all_formats_from_same_form(self):
        """Native GET selections preserve exact source IDs and both cutoffs."""
        selected = {k: v for k, v in self.knowledge().items()
                    if k != "directory"}
        selected.update(entity="site-1", source_a="survey-a", source_b="survey-b")
        status, _, raw = self.get({**selected, "format": "json"})
        self.assertEqual(status, 200)
        doc = json.loads(raw)
        self.assertEqual(doc["source_a"], "survey-a")
        self.assertEqual(doc["source_b"], "survey-b")
        self.assertEqual([e["entity"] for e in doc["entities"]], ["site-1"])
        for period in ("earlier", "later"):
            for record in doc["entities"][0][period]["source_a_original_reports"] + (
                    doc["entities"][0][period]["source_b_original_reports"]):
                self.assertIn(record["properties"]["source_id"], ("survey-a", "survey-b"))
                self.assertTrue(record["id"])
                self.assertTrue(record["properties"]["evidence_id"])
        for fmt in ("table", "html"):
            status, _, body = self.get({**selected, "format": fmt})
            self.assertEqual(status, 200)
            self.assertIn(b"<!doctype html>", body.lower())
            self.assertIn(b"survey-a", body)
            self.assertIn(b"survey-b", body)
        status, headers, body = self.get({**selected, "format": "csv"})
        self.assertEqual(status, 200)
        self.assertIn("text/csv", headers["Content-Type"])
        rows = list(csv.DictReader(io.StringIO(body.decode("utf-8"))))
        self.assertEqual({row["entity"] for row in rows}, {"site-1"})
        self.assertEqual({row["source_a"] for row in rows}, {"survey-a"})
        self.assertEqual({row["source_b"] for row in rows}, {"survey-b"})
        self.assertEqual({row["period"] for row in rows}, {"earlier", "later"})
        status, _, body = self.get({**selected, "format": "geojson"})
        self.assertEqual(status, 200)
        geo = json.loads(body)
        self.assertEqual(geo["monde_comparison"]["source_a"], "survey-a")
        self.assertEqual(geo["monde_comparison"]["source_b"], "survey-b")
        self.assertEqual({f["properties"]["entity"] for f in geo["features"]}, {"site-1"})
        self.assertEqual({f["properties"]["source_id"] for f in geo["features"]},
                         {"survey-a", "survey-b"})
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_source_comparison_export_rejects_invalid_and_duplicate_reporters(self):
        base = {k: v for k, v in self.knowledge().items()
                if k != "directory"}
        base.update(entity="site-1", source_a="survey-a", source_b="survey-b")
        for extra in ({"source_b": "survey-a"},
                      {"format": "xml"},
                      {"source_a": "../bad"},
                      {"unknown": "secret"}):
            status, _, body = self.get({**base, **extra})
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(body)["error"], "invalid_query")
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_entity_reporter_compare_form_absent_with_one_source_or_no_match(self):
        for entity in ("site-only-one-source", "does-not-exist"):
            status, _, page = self.get({**self.knowledge(), "entity": entity})
            self.assertEqual(status, 200)
            self.assertNotIn(b'Compare source positions on one map', page)
        status, _, raw = self.get({**self.knowledge(), "entity": "site-1",
                                   "source": "survey-a", "format": "map"})
        self.assertEqual(status, 200)
        self.assertNotIn(b'Compare source positions on one map', raw)

    def test_compare_two_reporters_world_axis_uses_original_world_cutoffs(self):
        world = sample(dateline=True)
        saved = Path(self.tmp.name) / "world-two-reporters.json"
        world.save(saved)
        before = saved.read_bytes()
        server = create_server(saved)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            q = {"directory": "1", "axis": "world",
                 "from_at": EARLY, "to_at": LATE, "known_at": KNOWN}
            status, _, raw = self.get({**q, "format": "json"}, server)
            self.assertEqual(status, 200)
            source_rows = json.loads(raw)["sources"]
            entity = source_rows[0]["example_entity"]
            status, _, page = self.get({**q, "entity": entity}, server)
            self.assertEqual(status, 200)
            if len([x for x in source_rows if x["example_entity"] == entity]) >= 2:
                self.assertIn(b'Compare source positions on one map', page)
            else:
                self.assertNotIn(b'Compare source positions on one map', page)
            if b'Compare source positions on one map' in page:
                self.assertIn(b'name="from_at"', page)
                self.assertIn(b'name="to_at"', page)
                self.assertIn(b'name="known_at"', page)
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
            self.assertEqual(saved.read_bytes(), before)


    def test_all_original_reporters_assertion_csv_real_http(self):
        """CSV has each untouched original Point, not summary counts or inferred truth."""
        query = {**self.knowledge(), "entity": "site-1"}
        status, _, raw = self.get({**query, "format": "geojson"})
        self.assertEqual(status, 200)
        geojson = json.loads(raw)
        expected = [
            (p["properties"]["monde_comparison_period"],
             p["properties"]["source_id"],
             str(p["properties"]["monde_original_assertion_id"]),
             p["properties"]["evidence_id"],
             p["properties"]["monde_world_at"],
             p["properties"]["monde_known_at"],
             str(p["geometry"]["coordinates"][0]),
             str(p["geometry"]["coordinates"][1]))
            for p in geojson["features"]
        ]
        self.assertTrue(expected)
        status, headers, raw = self.get({**query, "format": "assertions-csv"})
        self.assertEqual(status, 200)
        self.assertIn("text/csv", headers["Content-Type"])
        self.assertIn("original-entity-reporter-assertions.csv",
                      headers["Content-Disposition"])
        rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
        self.assertEqual(len(rows), len(expected))
        actual = [(row["period"], row["source_id"], row["assertion_id"],
                   row["evidence_id"], row["world_at"], row["known_at"],
                   row["longitude"], row["latitude"]) for row in rows]
        self.assertEqual(actual, expected)
        self.assertEqual({row["entity"] for row in rows}, {"site-1"})
        status, _, page = self.get(query)
        self.assertEqual(status, 200)
        self.assertIn(b"Download all original reporter assertions CSV", page)
        self.assertIn(b"format=assertions-csv", page)
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_assertion_csv_world_axis_and_empty_entity(self):
        world = sample(dateline=True)
        saved = Path(self.tmp.name) / "source-assertions-world.json"
        world.save(saved)
        before = saved.read_bytes()
        server = create_server(saved)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            q = {"directory": "1", "axis": "world", "from_at": EARLY,
                 "to_at": LATE, "known_at": KNOWN}
            status, _, raw = self.get({**q, "format": "json"}, server)
            self.assertEqual(status, 200)
            entity = json.loads(raw)["sources"][0]["example_entity"]
            status, _, original = self.get({**q, "entity": entity,
                                            "format": "geojson"}, server)
            self.assertEqual(status, 200)
            status, _, raw = self.get({**q, "entity": entity,
                                      "format": "assertions-csv"}, server)
            self.assertEqual(status, 200)
            rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
            self.assertEqual(len(rows), len(json.loads(original)["features"]))
            self.assertEqual({row["known_at"] for row in rows}, {KNOWN})
            self.assertTrue({row["world_at"] for row in rows}.issubset({EARLY, LATE}))
            status, _, raw = self.get({**q, "entity": "absent-original-entity",
                                      "format": "assertions-csv"}, server)
            self.assertEqual(status, 200)
            self.assertEqual(list(csv.DictReader(io.StringIO(raw.decode("utf-8")))), [])
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
        self.assertEqual(saved.read_bytes(), before)

    def test_assertion_csv_rejects_unscoped_source_and_bad_formats(self):
        query = self.knowledge()
        for extra in (
                {"format": "assertions-csv"},
                {"format": "assertions-csv", "source": "survey-a"},
                {"format": "assertions-csv", "source": "survey-a", "entity": "site-1"},
                {"format": "assertions-csv", "entity": "site-1", "rank": "nonsense"},
                {"format": "assertions-csv", "entity": "site-1", "extra": "x"}):
            with self.subTest(extra=extra):
                status, _, raw = self.get({**query, **extra})
                self.assertEqual(status, 400)
                self.assertEqual(json.loads(raw)["error"], "invalid_query")
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_assertion_csv_escapes_spreadsheet_formula_identifiers(self):
        from monde.source_pair_changes import source_directory_entity_assertions_csv
        class Minimal:
            def export_geojson(self, at, known):
                return {"features": [{
                    "id": "=assertion", "geometry": {"type": "Point", "coordinates": [1, 2]},
                    "properties": {"entity": "=entity", "source_id": "@reporter",
                                   "evidence_id": "+evidence"}
                }]}
        directory = {
            "schema": "MONDE_SOURCE_COVERAGE_DIRECTORY_V1",
            "entity_focus": "=entity", "axis": "knowledge",
            "sources": [{"source_id": "@reporter",
                         "example_assertion_ids": ["=assertion"]}],
            "cutoffs": {
                "earlier": {"world_at": AT, "knowledge_at": BEFORE},
                "later": {"world_at": AT, "knowledge_at": AFTER},
            },
            "interpretation": "original"
        }
        output = source_directory_entity_assertions_csv(Minimal(), directory)
        rows = list(csv.DictReader(io.StringIO(output)))
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertEqual(row["entity"], "'=entity")
            self.assertEqual(row["source_id"], "'@reporter")
            self.assertEqual(row["assertion_id"], "'=assertion")
            self.assertEqual(row["evidence_id"], "'+evidence")


    def test_original_report_presence_csv_matches_both_geojson_cutoffs(self):
        query = {**self.knowledge(), "entity": "site-1"}
        status, _, data = self.get({**query, "format": "geojson"})
        self.assertEqual(status, 200)
        expected = {}
        for feature in json.loads(data)["features"]:
            p = feature["properties"]
            key = (p["source_id"], str(p["monde_original_assertion_id"]),
                   p["evidence_id"], *feature["geometry"]["coordinates"])
            expected.setdefault(key, set()).add(p["monde_comparison_period"])
        self.assertTrue(expected)
        status, headers, data = self.get({**query, "format": "presence-csv"})
        self.assertEqual(status, 200)
        self.assertIn("text/csv", headers["Content-Type"])
        self.assertIn("original-entity-report-presence.csv", headers["Content-Disposition"])
        rows = list(csv.DictReader(io.StringIO(data.decode("utf-8"))))
        self.assertEqual(len(rows), len(expected))
        for row in rows:
            key = (row["source_id"], row["assertion_id"], row["evidence_id"],
                   float(row["longitude"]), float(row["latitude"]))
            seen = expected[key]
            self.assertEqual(row["earlier_visible"], str(int("earlier" in seen)))
            self.assertEqual(row["later_visible"], str(int("later" in seen)))
            self.assertEqual(row["visibility_transition"], (
                "BOTH_CUTOFFS" if len(seen) == 2 else
                "EARLIER_ONLY" if "earlier" in seen else "LATER_ONLY"))
            self.assertEqual(row["earlier_world_at"], AT)
            self.assertEqual(row["later_world_at"], AT)
            self.assertEqual(row["earlier_known_at"], BEFORE)
            self.assertEqual(row["later_known_at"], AFTER)
        status, _, page = self.get(query)
        self.assertEqual(status, 200)
        self.assertIn(b"Download original report presence changes CSV", page)
        self.assertIn(b"format=presence-csv", page)

    def test_original_report_presence_csv_world_axis_and_empty(self):
        world = sample(dateline=True)
        saved = Path(self.tmp.name) / "presence-world.json"
        world.save(saved)
        old = saved.read_bytes()
        server = create_server(saved)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            query = {"directory": "1", "axis": "world", "from_at": EARLY,
                     "to_at": LATE, "known_at": KNOWN}
            status, _, doc = self.get({**query, "format": "json"}, server)
            self.assertEqual(status, 200)
            entity = json.loads(doc)["sources"][0]["example_entity"]
            status, _, body = self.get({**query, "entity": entity,
                                        "format": "presence-csv"}, server)
            self.assertEqual(status, 200)
            rows = list(csv.DictReader(io.StringIO(body.decode("utf-8"))))
            self.assertTrue(rows)
            for row in rows:
                self.assertEqual(row["earlier_world_at"], EARLY)
                self.assertEqual(row["later_world_at"], LATE)
                self.assertEqual(row["earlier_known_at"], KNOWN)
                self.assertEqual(row["later_known_at"], KNOWN)
            status, _, body = self.get({**query, "entity": "missing-entity",
                                        "format": "presence-csv"}, server)
            self.assertEqual(status, 200)
            self.assertFalse(list(csv.DictReader(io.StringIO(body.decode("utf-8")))))
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
        self.assertEqual(saved.read_bytes(), old)

    def test_original_report_presence_csv_scope_and_spreadsheet_safety(self):
        for extra in ({"format": "presence-csv"},
                      {"entity": "site-1", "source": "survey-a", "format": "assertions-csv"},
                      {"entity": "site-1", "format": "presence-csv", "extra": "x"}):
            status, _, data = self.get({**self.knowledge(), **extra})
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(data)["error"], "invalid_query")
        from monde.source_pair_changes import source_directory_entity_presence_csv
        class Minimal:
            def export_geojson(self, at, known):
                return {"features": [{"id": "=report",
                    "geometry": {"type": "Point", "coordinates": [1, 2]},
                    "properties": {"entity": "=entity", "source_id": "@source",
                                   "evidence_id": "+evidence"}}]}
        directory = {"schema": "MONDE_SOURCE_COVERAGE_DIRECTORY_V1",
                     "entity_focus": "=entity", "axis": "knowledge",
                     "sources": [{"source_id": "@source",
                                  "example_assertion_ids": ["=report"]}],
                     "cutoffs": {"earlier": {"world_at": AT, "knowledge_at": BEFORE},
                                "later": {"world_at": AT, "knowledge_at": AFTER}},
                     "interpretation": "original"}
        data = source_directory_entity_presence_csv(Minimal(), directory)
        rows = list(csv.DictReader(io.StringIO(data)))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["visibility_transition"], "BOTH_CUTOFFS")
        self.assertEqual([rows[0][k] for k in
                          ("entity", "source_id", "assertion_id", "evidence_id")],
                         ["'=entity", "'@source", "'=report", "'+evidence"])



    def test_original_report_presence_map_matches_csv_and_geojson(self):
        """Map filter and original CSV use the same report identity."""
        query = {**self.knowledge(), "entity": "site-1"}
        status, _, raw = self.get({**query, "format": "presence-csv"})
        self.assertEqual(status, 200)
        rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
        self.assertTrue(rows)
        expected = {(row["source_id"], row["assertion_id"], row["evidence_id"],
                     float(row["longitude"]), float(row["latitude"])):
                    row["visibility_transition"] for row in rows}
        total = 0
        for mode, transition in (("earlier", "EARLIER_ONLY"),
                                 ("later", "LATER_ONLY"),
                                 ("both", "BOTH_CUTOFFS")):
            status, _, raw = self.get({**query, "presence": mode, "format": "geojson"})
            self.assertEqual(status, 200)
            doc = json.loads(raw)
            self.assertEqual(doc["monde_source_coverage"]["presence_filter"], mode)
            for feature in doc["features"]:
                p = feature["properties"]
                key = (p["source_id"], str(p["monde_original_assertion_id"]),
                       p["evidence_id"], *feature["geometry"]["coordinates"])
                self.assertEqual(expected[key], transition)
                self.assertEqual(p["monde_visibility_transition"], transition)
                self.assertIn(p["monde_comparison_period"], ("earlier", "later"))
            total += len(doc["features"])
            status, _, html = self.get({**query, "presence": mode, "format": "map"})
            self.assertEqual(status, 200)
            self.assertIn(b"<!doctype html>", html.lower())
        status, _, raw = self.get({**query, "format": "geojson"})
        self.assertEqual(status, 200)
        original = json.loads(raw)["features"]
        self.assertEqual(total, len(original))
        self.assertTrue(all("monde_visibility_transition" not in
                            feature["properties"] for feature in original))
        status, _, html = self.get(query)
        self.assertEqual(status, 200)
        for token in (b"presence=earlier", b"presence=later",
                      b"presence=both", b"Earlier cutoff only",
                      b"Later cutoff only", b"Both cutoffs"):
            self.assertIn(token, html)

    def test_original_report_presence_map_rejects_unscoped_query(self):
        query = self.knowledge()
        invalid = (
            {"presence": "later", "format": "geojson"},
            {"source": "survey-a", "presence": "later", "format": "map"},
            {"entity": "site-1", "presence": "unknown", "format": "map"},
            {"entity": "site-1", "presence": "later", "format": "json"},
            {"entity": "site-1", "presence": "both", "format": "table"},
        )
        for args in invalid:
            status, _, raw = self.get({**query, **args})
            self.assertEqual(status, 400, args)
            self.assertEqual(json.loads(raw)["error"], "invalid_query")

    def test_original_report_presence_map_world_axis_read_only(self):
        world = sample(dateline=True)
        saved = Path(self.tmp.name) / "presence-map-world.json"
        world.save(saved)
        old = saved.read_bytes()
        server = create_server(saved)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            query = {"directory": "1", "axis": "world", "from_at": EARLY,
                     "to_at": LATE, "known_at": KNOWN}
            status, _, raw = self.get({**query, "format": "json"}, server)
            self.assertEqual(status, 200)
            entity = json.loads(raw)["sources"][0]["example_entity"]
            for mode in ("earlier", "later", "both"):
                status, _, raw = self.get({**query, "entity": entity,
                    "presence": mode, "format": "geojson"}, server)
                self.assertEqual(status, 200)
                doc = json.loads(raw)
                self.assertEqual(doc["monde_source_coverage"]["axis"], "world")
                self.assertEqual(doc["monde_source_coverage"]["presence_filter"], mode)
                for feature in doc["features"]:
                    p = feature["properties"]
                    self.assertIn(p["monde_world_at"], (EARLY, LATE))
                    self.assertEqual(p["monde_known_at"], KNOWN)
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
        self.assertEqual(saved.read_bytes(), old)

    def test_report_presence_is_per_original_point_not_inferred_movement(self):
        from monde.source_pair_changes import source_directory_entity_geojson
        class Minimal:
            def export_geojson(self, at, known):
                earlier = known == BEFORE
                ids = [("stay", 1), ("old", 2)] if earlier else [
                    ("stay", 1), ("new", 3)]
                return {"features": [{
                    "id": item,
                    "geometry": {"type": "Point", "coordinates": [lon, 10]},
                    "properties": {"entity": "e1", "source_id": "survey-1",
                                   "evidence_id": "evidence-" + item}
                } for item, lon in ids]}
        directory = {
            "schema": "MONDE_SOURCE_COVERAGE_DIRECTORY_V1",
            "entity_focus": "e1", "axis": "knowledge",
            "sources": [{"source_id": "survey-1",
                         "example_assertion_ids": ["stay", "old", "new"]}],
            "cutoffs": {"earlier": {"world_at": AT, "knowledge_at": BEFORE},
                        "later": {"world_at": AT, "knowledge_at": AFTER}},
            "interpretation": "original only",
        }
        expected = {"earlier": {"old"}, "later": {"new"}, "both": {"stay"}}
        for mode, reports in expected.items():
            out = source_directory_entity_geojson(Minimal(), directory, mode)
            self.assertEqual({f["properties"]["monde_original_assertion_id"]
                              for f in out["features"]}, reports)
            self.assertEqual(len(out["features"]), 2 if mode == "both" else 1)


    def test_original_reporter_presence_summary_links_match_csv(self):
        import re
        from html import unescape
        from urllib.parse import parse_qs, urlsplit
        from monde.source_pair_changes import source_directory_entity_presence_summary

        query = {**self.knowledge(), "entity": "site-1"}
        status, _, raw = self.get({**query, "format": "json"})
        self.assertEqual(status, 200)
        rows = source_directory_entity_presence_summary(self.world, json.loads(raw))
        self.assertTrue(rows)
        status, _, csv_raw = self.get({**query, "format": "presence-csv"})
        self.assertEqual(status, 200)
        expected = {}
        for line in csv.DictReader(io.StringIO(csv_raw.decode("utf-8"))):
            by_source = expected.setdefault(line["source_id"],
                {"earlier_only": 0, "later_only": 0, "both_cutoffs": 0})
            field = {"EARLIER_ONLY": "earlier_only",
                     "LATER_ONLY": "later_only",
                     "BOTH_CUTOFFS": "both_cutoffs"}[line["visibility_transition"]]
            by_source[field] += 1
        for row in rows:
            self.assertEqual({k: row[k] for k in expected[row["source_id"]]},
                             expected[row["source_id"]])
        status, _, html_raw = self.get(query)
        self.assertEqual(status, 200)
        html = html_raw.decode("utf-8")
        self.assertIn("Original Point report presence by reporter", html)
        links = [unescape(v) for v in re.findall(r'href="([^"]+)"', html)]
        scoped = [s for s in links
                  if "presence=" in s and "source=" in s and "format=map" in s]
        self.assertEqual(len(scoped), sum(sum(row[k] > 0 for k in
            ("earlier_only", "later_only", "both_cutoffs")) for row in rows))
        for link in scoped:
            params = {k: v[0] for k, v in parse_qs(urlsplit(link).query).items()}
            self.assertEqual(urlsplit(link).path, "/source-pair")
            self.assertEqual(params["entity"], "site-1")
            status, _, map_html = self.get(params)
            self.assertEqual(status, 200)
            self.assertIn(b"<!doctype html>", map_html.lower())
            status, _, data = self.get({**params, "format": "geojson"})
            self.assertEqual(status, 200)
            features = json.loads(data)["features"]
            self.assertTrue(features)
            for feature in features:
                self.assertEqual(feature["properties"]["source_id"], params["source"])
                self.assertEqual(feature["properties"]["monde_visibility_transition"],
                    {"earlier": "EARLIER_ONLY", "later": "LATER_ONLY",
                     "both": "BOTH_CUTOFFS"}[params["presence"]])

    def test_original_reporter_presence_summary_world_axis_and_no_evidence(self):
        from monde.source_pair_changes import source_directory_entity_presence_summary
        world = sample(dateline=True)
        saved = Path(self.tmp.name) / "reporter-world.json"
        world.save(saved)
        initial = saved.read_bytes()
        server = create_server(saved)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            query = {"directory": "1", "axis": "world",
                     "from_at": EARLY, "to_at": LATE, "known_at": KNOWN}
            status, _, raw = self.get({**query, "format": "json"}, server)
            self.assertEqual(status, 200)
            entity = json.loads(raw)["sources"][0]["example_entity"]
            selected = {**query, "entity": entity}
            status, _, raw = self.get({**selected, "format": "json"}, server)
            self.assertEqual(status, 200)
            summary = source_directory_entity_presence_summary(world, json.loads(raw))
            self.assertTrue(summary)
            status, _, page = self.get(selected, server)
            self.assertEqual(status, 200)
            self.assertIn(b"Original Point report presence by reporter", page)
            self.assertIn(b"from_at=", page)
            self.assertIn(b"to_at=", page)
            status, _, empty = self.get({**query, "entity": "missing-entity"}, server)
            self.assertEqual(status, 200)
            self.assertIn(b"Original Point report presence by reporter", empty)
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
        self.assertEqual(saved.read_bytes(), initial)


    def test_presence_category_csv_per_reporter_matches_original_geojson(self):
        """Real HTTP download matches current map by source and report identity."""
        import re
        from html import unescape
        from urllib.parse import parse_qs, urlsplit
        base = {**self.knowledge(), "entity": "site-1"}
        status, _, raw = self.get({**base, "format": "presence-csv"})
        self.assertEqual(status, 200)
        all_rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
        status, _, page = self.get(base)
        self.assertEqual(status, 200)
        links = [unescape(v) for v in re.findall(
            r'href="([^"]+)"', page.decode("utf-8"))]
        csv_links = [v for v in links if "source=" in v and "presence=" in v
                     and "format=presence-csv" in v]
        self.assertTrue(csv_links)
        for link in csv_links:
            params = {k: v[0] for k, v in
                      parse_qs(urlsplit(link).query).items()}
            status, headers, raw = self.get(params)
            self.assertEqual(status, 200)
            self.assertIn("text/csv", headers["Content-Type"])
            selected = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
            wanted = {"earlier": "EARLIER_ONLY", "later": "LATER_ONLY",
                      "both": "BOTH_CUTOFFS"}[params["presence"]]
            self.assertEqual(selected, [r for r in all_rows
                if r["source_id"] == params["source"]
                and r["visibility_transition"] == wanted])
            self.assertTrue(selected)
            status, _, raw = self.get({**params, "format": "geojson"})
            self.assertEqual(status, 200)
            got = {(r["source_id"], r["assertion_id"], r["evidence_id"],
                    float(r["longitude"]), float(r["latitude"]))
                   for r in selected}
            expected = set()
            for f in json.loads(raw)["features"]:
                p = f["properties"]
                expected.add((p["source_id"],
                    str(p["monde_original_assertion_id"]), p["evidence_id"],
                    *f["geometry"]["coordinates"]))
            self.assertEqual(got, expected)

    def test_presence_category_csv_world_axis_read_only_and_validation(self):
        world = sample(dateline=True)
        saved = Path(self.tmp.name) / "presence-category-world.json"
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
            entity = json.loads(raw)["sources"][0]["example_entity"]
            base = {**query, "entity": entity}
            status, _, raw = self.get({**base, "format": "presence-csv"}, server)
            self.assertEqual(status, 200)
            all_rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
            self.assertTrue(all_rows)
            for presence, label in (("earlier", "EARLIER_ONLY"),
                                    ("later", "LATER_ONLY"),
                                    ("both", "BOTH_CUTOFFS")):
                status, _, raw = self.get({**base, "presence": presence,
                    "format": "presence-csv"}, server)
                self.assertEqual(status, 200)
                rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
                self.assertEqual(rows, [r for r in all_rows
                                       if r["visibility_transition"] == label])
            status, _, raw = self.get({**base, "presence": "earlier",
                "source": "missing", "format": "presence-csv"}, server)
            self.assertEqual(status, 200)
            self.assertEqual(list(csv.DictReader(
                io.StringIO(raw.decode("utf-8")))), [])
            for bad in ({"presence": "wrong"}, {"presence": "both", "format": "table"},
                        {"source": "survey-a", "format": "assertions-csv"},
                        {"entity": "", "presence": "both"}):
                status, _, raw = self.get({**base, "format": "presence-csv",
                                           **bad}, server)
                self.assertEqual(status, 400, bad)
                self.assertEqual(json.loads(raw)["error"], "invalid_query")
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
        self.assertEqual(saved.read_bytes(), original)



    def test_presence_html_exact_source_and_period_csv_parity(self):
        import re
        from html import escape as html_escape, unescape
        from urllib.parse import parse_qs, urlsplit
        base = {**self.knowledge(), "entity": "site-1"}
        status, _, raw = self.get(base)
        self.assertEqual(status, 200)
        links = [unescape(link) for link in re.findall(r'href="([^"]+)"', raw.decode())]
        selected = [url for url in links if "format=presence-table" in url
                    and "source=" in url and "presence=" in url]
        self.assertTrue(selected)
        for url in selected:
            params = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
            status, _, raw = self.get({**params, "format": "presence-csv"})
            self.assertEqual(status, 200)
            expected = list(csv.DictReader(io.StringIO(raw.decode())))
            self.assertTrue(expected)
            status, headers, raw = self.get(params)
            self.assertEqual(status, 200)
            self.assertIn("text/html", headers["Content-Type"])
            page = raw.decode()
            self.assertEqual(page.count("<tr>") - 1, len(expected))
            self.assertIn("Map the same original reports", page)
            for row in expected:
                self.assertIn("<td>" + html_escape(row["assertion_id"]) + "</td>", page)
                self.assertIn("<td>" + row["visibility_transition"] + "</td>", page)

    def test_presence_html_strict_entity_scope_and_empty_evidence(self):
        base = self.knowledge()
        for query in ({"format": "presence-table"},
                      {"source": "survey-a", "format": "presence-table"},
                      {"entity": "site-1", "presence": "invalid",
                       "format": "presence-table"},
                      {"entity": "site-1", "format": "presence-table", "extra": "x"}):
            status, _, raw = self.get({**base, **query})
            self.assertEqual(status, 400, query)
            self.assertEqual(json.loads(raw)["error"], "invalid_query")
        status, _, raw = self.get({**base, "entity": "missing",
                                   "format": "presence-table"})
        self.assertEqual(status, 200)
        self.assertIn(b"0 original report identities", raw)

    def test_presence_html_world_axis_and_unchanged_persisted_evidence(self):
        world = sample(dateline=True)
        path = Path(self.tmp.name) / "world-browser-evidence.json"
        world.save(path)
        initial = path.read_bytes()
        server = create_server(path)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            query = {"directory": "1", "axis": "world",
                     "from_at": EARLY, "to_at": LATE, "known_at": KNOWN}
            status, _, raw = self.get({**query, "format": "json"}, server)
            self.assertEqual(status, 200)
            entity = json.loads(raw)["sources"][0]["example_entity"]
            chosen = {**query, "entity": entity}
            status, _, html = self.get({**chosen, "format": "presence-table"}, server)
            self.assertEqual(status, 200)
            self.assertIn(b"axis: world time", html)
            status, _, raw = self.get({**chosen, "format": "presence-csv"}, server)
            self.assertEqual(status, 200)
            expected = list(csv.DictReader(io.StringIO(raw.decode())))
            self.assertEqual(html.decode().count("<tr>") - 1, len(expected))
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
        self.assertEqual(path.read_bytes(), initial)


    def test_presence_table_links_exact_report_history_and_original_cutoff_map(self):
        from html import unescape
        from urllib.parse import parse_qs, urlsplit
        import re

        query = {**self.knowledge(), "entity": "site-1"}
        status, _, raw = self.get({**query, "format": "presence-csv"})
        self.assertEqual(status, 200)
        csv_rows = list(csv.DictReader(io.StringIO(raw.decode())))
        self.assertTrue(csv_rows)
        status, _, raw = self.get({**query, "format": "presence-table"})
        self.assertEqual(status, 200)
        page = raw.decode()
        self.assertIn("Trace original evidence", page)
        self.assertEqual(page.count("Inspect original source history"), len(csv_rows))
        urls = [unescape(s) for s in re.findall(r'href="([^"]+)"', page)]
        history = [url for url in urls if url.startswith("/inspect?")]
        maps = [url for url in urls if url.startswith("/viewer?")]
        self.assertEqual(len(history), len(csv_rows))
        self.assertEqual(len(maps), sum(
            int(r["earlier_visible"]) + int(r["later_visible"])
            for r in csv_rows))
        # Follow actual browser links against the persisted loopback server,
        # not just the URL strings emitted by the HTML renderer.
        for link in history[:1] + maps[:1]:
            conn = http.client.HTTPConnection(
                "127.0.0.1", self.server.server_port, timeout=5)
            try:
                conn.request("GET", link, headers={
                    "Host": "127.0.0.1:" + str(self.server.server_port)})
                result = conn.getresponse()
                body = result.read()
                self.assertEqual(result.status, 200, link)
                self.assertIn("text/html", result.getheader("Content-Type"))
                self.assertIn(b"Original", body)
            finally:
                conn.close()
        for url in history:
            params = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
            self.assertEqual(params["view"], "source-history")
            self.assertEqual(params["entity"], "site-1")
            self.assertEqual(params["attribute"], "geo_point")
            self.assertEqual(params["known_at"], AFTER)
            # History links are a separate read-only route; source identity
            # is carried as originally recorded, never as an inferred location.
            self.assertIn(params["source"], {"survey-a", "survey-b"})
        for row in csv_rows:
            expected = []
            for period in ("earlier", "later"):
                if row[period + "_visible"] != "1":
                    continue
                expected.append((
                    row["longitude"] + "," + row["latitude"],
                    row[period + "_world_at"], row[period + "_known_at"]))
            actual = []
            for url in maps:
                p = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
                if p["center"] == row["longitude"] + "," + row["latitude"]:
                    actual.append((p["center"], p["at"], p["known_at"]))
            for target in expected:
                self.assertIn(target, actual)



    def test_original_presence_json_matches_original_csv_and_browser_links(self):
        """Persisted world, real HTTP JSON/CSV identity parity and browser GET."""
        from urllib.parse import urlsplit, parse_qs
        from html import unescape
        import re
        query = {**self.knowledge(), "entity": "site-1"}
        status, headers, payload = self.get({**query, "format": "presence-json"})
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers["Content-Type"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        document = json.loads(payload)
        self.assertEqual(document["schema"], "MONDE_ORIGINAL_POINT_PRESENCE_V1")
        self.assertEqual(document["entity"], "site-1")
        self.assertEqual(document["axis"], "knowledge")
        self.assertIn("not verified movement", document["interpretation"])
        self.assertEqual(document["report_count"], len(document["reports"]))
        self.assertTrue(document["reports"])
        _, _, raw_csv = self.get({**query, "format": "presence-csv"})
        csv_rows = list(csv.DictReader(io.StringIO(raw_csv.decode("utf-8"))))
        self.assertEqual(len(csv_rows), len(document["reports"]))
        for original, csv_row in zip(document["reports"], csv_rows):
            for key in ("entity", "source_id", "assertion_id", "evidence_id",
                        "visibility_transition"):
                self.assertEqual(str(original[key]), csv_row[key])
            self.assertEqual(str(original["longitude"]), csv_row["longitude"])
            self.assertEqual(str(original["latitude"]), csv_row["latitude"])
            self.assertEqual(int(original["earlier_visible"]),
                             int(csv_row["earlier_visible"]))
            self.assertEqual(int(original["later_visible"]),
                             int(csv_row["later_visible"]))
        _, _, rendered = self.get({**query, "format": "table"})
        self.assertIn(b"Download original report presence JSON", rendered)
        hrefs = [unescape(x) for x in re.findall(
            r'href="([^"]+)"', rendered.decode("utf-8"))]
        target = next(x for x in hrefs if "format=presence-json" in x)
        params = {k: vals[0] for k, vals in
                  parse_qs(urlsplit(target).query).items()}
        self.assertEqual(json.loads(self.get(params)[2]), document)

    def test_original_presence_json_source_category_and_scope(self):
        q = {**self.knowledge(), "entity": "site-1"}
        entire = json.loads(self.get({**q, "format": "presence-json"})[2])
        for source in ("survey-a", "survey-b"):
            for selection, category in (
                    ("earlier", "EARLIER_ONLY"),
                    ("later", "LATER_ONLY"),
                    ("both", "BOTH_CUTOFFS")):
                params = {**q, "source": source, "presence": selection,
                          "format": "presence-json"}
                status, _, body = self.get(params)
                self.assertEqual(status, 200)
                result = json.loads(body)
                self.assertEqual(result["source_focus"], source)
                self.assertEqual(result["presence_filter"], selection)
                wanted = [r for r in entire["reports"]
                          if r["source_id"] == source and
                          r["visibility_transition"] == category]
                self.assertEqual(result["reports"], wanted)
                self.assertEqual(result["report_count"], len(wanted))
        for bad in (
                {"format": "presence-json"},
                {"source": "survey-a", "format": "presence-json"},
                {"entity": "site-1", "presence": "unknown",
                 "format": "presence-json"},
                {"entity": "site-1", "format": "presence-json",
                 "unrecognized": "x"}):
            status, _, body = self.get({**self.knowledge(), **bad})
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(body)["error"], "invalid_query")

    def test_original_presence_json_world_axis_and_unchanged_saved_world(self):
        q = {"directory": "1", "axis": "world", "from_at": EARLY,
             "to_at": LATE, "known_at": KNOWN, "entity": "missing",
             "format": "presence-json"}
        status, _, body = self.get(q)
        self.assertEqual(status, 200)
        doc = json.loads(body)
        self.assertEqual(doc["axis"], "world")
        self.assertEqual(doc["report_count"], 0)
        self.assertEqual(doc["reports"], [])
        self.assertEqual(doc["cutoffs"]["earlier"]["world_at"], EARLY)
        self.assertEqual(doc["cutoffs"]["later"]["world_at"], LATE)
        self.assertEqual(doc["cutoffs"]["earlier"]["knowledge_at"], KNOWN)
        self.assertEqual(self.saved.read_bytes(), self.snapshot)


    def test_presence_geojson_unique_original_points_and_json_identity_parity(self):
        """Real persisted HTTP: one original report even when seen at both cutoffs."""
        query = {**self.knowledge(), "entity": "site-1"}
        status, headers, payload = self.get({**query, "format": "presence-geojson"})
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers["Content-Type"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        doc = json.loads(payload)
        self.assertEqual(doc["type"], "FeatureCollection")
        self.assertEqual(doc["monde_source_coverage"]["schema"],
                         "MONDE_ORIGINAL_POINT_PRESENCE_GEOJSON_V1")
        report_doc = json.loads(self.get({**query, "format": "presence-json"})[2])
        self.assertEqual(len(doc["features"]), report_doc["report_count"])
        by_identity = {
            (r["source_id"], r["assertion_id"], r["evidence_id"],
             r["longitude"], r["latitude"]): r for r in report_doc["reports"]
        }
        self.assertTrue(by_identity)
        identities = set()
        for item in doc["features"]:
            p = item["properties"]
            coords = item["geometry"]["coordinates"]
            key = (p["source_id"], p["monde_original_assertion_id"],
                   p["evidence_id"], coords[0], coords[1])
            self.assertNotIn(key, identities)
            identities.add(key)
            original = by_identity[key]
            self.assertEqual(json.loads(item["id"]), list(key))
            self.assertEqual(p["earlier_visible"], original["earlier_visible"])
            self.assertEqual(p["later_visible"], original["later_visible"])
            self.assertEqual(p["monde_visibility_transition"],
                             original["visibility_transition"])
            self.assertNotIn("monde_comparison_period", p)
        self.assertEqual(identities, set(by_identity))
        self.assertTrue(any(r["earlier_visible"] and r["later_visible"]
                            for r in report_doc["reports"]))
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_presence_geojson_filters_world_axis_and_browser_download(self):
        """Source/category filters, navigation, and world-time are read-only."""
        from html import unescape
        from urllib.parse import parse_qs, urlsplit
        import re
        query = {**self.knowledge(), "entity": "site-1"}
        full = json.loads(self.get({**query, "format": "presence-geojson"})[2])
        for reporter in ("survey-a", "survey-b"):
            for selection, category in (("earlier", "EARLIER_ONLY"),
                                        ("later", "LATER_ONLY"),
                                        ("both", "BOTH_CUTOFFS")):
                subset = {**query, "source": reporter, "presence": selection,
                          "format": "presence-geojson"}
                status, _, payload = self.get(subset)
                self.assertEqual(status, 200)
                obj = json.loads(payload)
                self.assertEqual(obj["monde_source_coverage"]["source_focus"], reporter)
                self.assertEqual(obj["monde_source_coverage"]["presence_filter"], selection)
                self.assertEqual(
                    [f["id"] for f in obj["features"]],
                    [f["id"] for f in full["features"]
                     if f["properties"]["source_id"] == reporter and
                     f["properties"]["monde_visibility_transition"] == category])
        page = self.get({**query, "format": "table"})[2].decode("utf-8")
        self.assertIn("Download unique original report presence GeoJSON", page)
        links = [unescape(v) for v in re.findall(r'href="([^"]+)"', page)]
        href = next(v for v in links if "format=presence-geojson" in v)
        params = {k: v[0] for k, v in parse_qs(urlsplit(href).query).items()}
        self.assertEqual(json.loads(self.get(params)[2]), full)
        table = self.get({**query, "format": "presence-table"})[2]
        self.assertIn(b"Download unique matching GeoJSON", table)
        world = {"directory": "1", "axis": "world", "from_at": EARLY,
                 "to_at": LATE, "known_at": KNOWN, "entity": "missing",
                 "format": "presence-geojson"}
        self.assertEqual(json.loads(self.get(world)[2])["features"], [])
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_presence_geojson_rejects_unscoped_or_invalid_queries(self):
        for query in (
            {**self.knowledge(), "format": "presence-geojson"},
            {**self.knowledge(), "source": "survey-a", "format": "presence-geojson"},
            {**self.knowledge(), "entity": "site-1", "presence": "unknown",
             "format": "presence-geojson"},
            {**self.knowledge(), "entity": "site-1", "extra": "x",
             "format": "presence-geojson"},
        ):
            status, _, payload = self.get(query)
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(payload)["error"], "invalid_query")

    def test_unique_presence_map_reuses_exact_original_points(self):
        from monde.source_pair_changes import source_directory_entity_presence_map
        query = {**self.knowledge(), "entity": "site-1"}
        directory = json.loads(self.get({**query, "format": "json"})[2])
        geojson = json.loads(self.get({**query, "format": "presence-geojson"})[2])
        mapped = source_directory_entity_presence_map(self.world, directory)
        self.assertEqual([f["id"] for f in mapped["features"]],
                         [f["id"] for f in geojson["features"]])
        self.assertEqual(mapped["monde_bbox_query"]["total_source_features"],
                         len(geojson["features"]))
        self.assertTrue(mapped["features"])
        self.assertTrue(all(f["properties"]["monde_inside_bbox"]
                            for f in mapped["features"]))
        self.assertEqual(
            {f["properties"]["monde_visibility_transition"]
             for f in mapped["features"]},
            {f["properties"]["monde_visibility_transition"]
             for f in geojson["features"]})
        self.assertEqual(len({f["id"] for f in mapped["features"]}),
                         len(mapped["features"]))
        self.assertIn("NOT_VERIFIED_MOVEMENT",
                      mapped["monde_source_coverage"]["display_basis"])

    def test_unique_presence_map_live_http_filters_links_and_unchanged_snapshot(self):
        from html import unescape
        from urllib.parse import parse_qs, urlsplit
        import re
        query = {**self.knowledge(), "entity": "site-1"}
        code, headers, body = self.get({**query, "format": "presence-map"})
        self.assertEqual(code, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn(b"MONDE_ORIGINAL_POINT_PRESENCE_GEOJSON_V1", body)
        self.assertIn(b"monde_visibility_transition", body)
        page = self.get({**query, "format": "table"})[2].decode("utf-8")
        self.assertIn("Map unique original reports by temporal presence", page)
        links = [unescape(v) for v in re.findall(r'href="([^"]+)"', page)]
        link = next(v for v in links if "format=presence-map" in v)
        params = {k: v[0] for k, v in parse_qs(urlsplit(link).query).items()}
        self.assertEqual(self.get(params)[0], 200)
        self.assertIn(b"Map unique matching Points",
                      self.get({**query, "format": "presence-table"})[2])
        for category in ("earlier", "later", "both"):
            params = {**query, "format": "presence-map", "source": "survey-a",
                      "presence": category}
            self.assertEqual(self.get(params)[0], 200)
        for bad in ({**query, "format": "presence-map", "presence": "invalid"},
                    {**self.knowledge(), "format": "presence-map"},
                    {**query, "format": "presence-map", "unknown": "x"}):
            self.assertEqual(self.get(bad)[0], 400)
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_unique_presence_map_empty_world_cutoffs(self):
        from monde.source_pair_changes import source_directory_entity_presence_map
        query = {"directory": "1", "axis": "world", "from_at": EARLY,
                 "to_at": LATE, "known_at": KNOWN, "entity": "missing"}
        directory = json.loads(self.get({**query, "format": "json"})[2])
        mapped = source_directory_entity_presence_map(self.world, directory)
        self.assertEqual(mapped["features"], [])
        self.assertEqual(mapped["monde_bbox_query"]["status"], "NO_MATCHES")
        self.assertEqual(self.get({**query, "format": "presence-map"})[0], 200)
        self.assertEqual(self.saved.read_bytes(), self.snapshot)



    def test_exact_original_point_from_presence_table_is_one_evidence_identity(self):
        """HTTP table links resolve exactly one original Point, never a centroid."""
        from html import unescape
        from urllib.parse import parse_qs, urlsplit
        import re
        from monde.source_pair_changes import (
            source_directory_entity_presence_map,
            source_directory_entity_presence_records,
        )
        query = {**self.knowledge(), "entity": "site-1"}
        directory = json.loads(self.get({**query, "format": "json"})[2])
        originals = source_directory_entity_presence_records(self.world, directory)
        self.assertTrue(originals)
        table = self.get({**query, "format": "presence-table"})[2].decode("utf-8")
        links = [unescape(v) for v in re.findall(r'href="([^"]+)"', table)
                 if "assertion=" in v and "format=presence-map" in v]
        self.assertEqual(len(links), len(originals))
        for link in links:
            params = {k: v[0] for k, v in parse_qs(urlsplit(link).query).items()}
            self.assertEqual(urlsplit(link).path, "/source-pair")
            status, headers, body = self.get(params)
            self.assertEqual(status, 200)
            self.assertIn("text/html", headers["Content-Type"])
            self.assertIn(b"MONDE_ORIGINAL_POINT_PRESENCE_GEOJSON_V1", body)
            focus = {
                "source_id": params["source"], "assertion_id": params["assertion"],
                "evidence_id": params["evidence"],
                "longitude": float(params["longitude"]),
                "latitude": float(params["latitude"]),
            }
            geojson = source_directory_entity_presence_map(
                self.world,
                {**directory, "sources": [s for s in directory["sources"]
                    if s["source_id"] == params["source"]],
                 "source_focus": params["source"]}, focus=focus)
            self.assertEqual(len(geojson["features"]), 1)
            self.assertEqual(geojson["features"][0]["properties"]
                             ["monde_original_assertion_id"], params["assertion"])
            self.assertEqual(geojson["monde_bbox_query"]["total_source_features"], 1)
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_exact_original_point_rejects_partial_unsafe_or_unscoped_requests(self):
        query = {**self.knowledge(), "entity": "site-1",
                 "source": "survey-a", "format": "presence-map"}
        for bad in (
            {**query, "assertion": "a"},
            {**query, "assertion": "a", "evidence": "e", "longitude": "0"},
            {**query, "assertion": "a", "evidence": "e",
             "longitude": "nan", "latitude": "0"},
            {**query, "assertion": "a", "evidence": "e",
             "longitude": "181", "latitude": "0"},
            {**query, "assertion": "a", "evidence": "e",
             "longitude": "0", "latitude": "-91"},
            {**query, "assertion": "a", "evidence": "e",
             "longitude": "0", "latitude": "0", "format": "presence-json"},
            {**{k: v for k, v in query.items() if k != "entity"},
             "assertion": "a", "evidence": "e", "longitude": "0",
             "latitude": "0"},
        ):
            self.assertEqual(self.get(bad)[0], 400)
        self.assertEqual(self.saved.read_bytes(), self.snapshot)


    def test_presence_kml_matches_unique_source_points_over_persisted_http(self):
        from xml.etree import ElementTree as ET
        ns = {"k": "http://www.opengis.net/kml/2.2"}
        params = {**self.knowledge(), "entity": "site-1"}
        status, headers, body = self.get({**params, "format": "presence-kml"})
        self.assertEqual(status, 200)
        self.assertIn("application/vnd.google-earth.kml+xml", headers["Content-Type"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn(".kml", headers["Content-Disposition"])
        root = ET.fromstring(body)
        metadata = {f.attrib["name"]: f.findtext("k:value", namespaces=ns)
                    for f in root.findall("k:Document/k:ExtendedData/k:Data", ns)}
        self.assertEqual(metadata["schema"], "MONDE_ORIGINAL_POINT_PRESENCE_KML_V1")
        self.assertEqual(metadata["earlier_world_at"], AT)
        self.assertEqual(metadata["earlier_knowledge_at"], BEFORE)
        self.assertEqual(metadata["later_knowledge_at"], AFTER)
        original = json.loads(self.get({**params, "format": "presence-geojson"})[2])
        marks = root.findall("k:Document/k:Placemark", ns)
        self.assertEqual(int(metadata["report_count"]), len(original["features"]))
        self.assertEqual(len(marks), len(original["features"]))
        seen = set()
        for mark, feature in zip(marks, original["features"]):
            props = {d.attrib["name"]: d.findtext("k:value", namespaces=ns)
                     for d in mark.findall("k:ExtendedData/k:Data", ns)}
            source = feature["properties"]
            longitude, latitude = feature["geometry"]["coordinates"]
            coords = mark.findtext("k:Point/k:coordinates", namespaces=ns)
            self.assertEqual([float(x) for x in coords.split(",")],
                             [longitude, latitude, 0.])
            identity = (props["source_id"], props["assertion_id"],
                        props["evidence_id"], longitude, latitude)
            self.assertNotIn(identity, seen)
            seen.add(identity)
            self.assertEqual(props["assertion_id"], source["monde_original_assertion_id"])
            self.assertEqual(props["evidence_id"], source["evidence_id"])
            self.assertEqual(props["visibility_transition"],
                             source["monde_visibility_transition"])
            for period in ("earlier", "later"):
                self.assertEqual(props[period + "_visible"],
                                 str(source[period + "_visible"]).lower())
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_presence_kml_filters_links_empty_world_and_strict_scope(self):
        from xml.etree import ElementTree as ET
        from html import unescape
        from urllib.parse import parse_qs, urlsplit
        import re
        ns = {"k": "http://www.opengis.net/kml/2.2"}
        params = {**self.knowledge(), "entity": "site-1"}
        all_points = json.loads(self.get({**params, "format": "presence-geojson"})[2])
        for source in ("survey-a", "survey-b"):
            for selection, category in (("earlier", "EARLIER_ONLY"),
                                        ("later", "LATER_ONLY"),
                                        ("both", "BOTH_CUTOFFS")):
                q = {**params, "source": source, "presence": selection,
                     "format": "presence-kml"}
                status, _, body = self.get(q)
                self.assertEqual(status, 200)
                actual = ET.fromstring(body).findall("k:Document/k:Placemark", ns)
                wanted = [f for f in all_points["features"]
                          if f["properties"]["source_id"] == source and
                          f["properties"]["monde_visibility_transition"] == category]
                self.assertEqual(len(actual), len(wanted))
        html = self.get({**params, "format": "table"})[2].decode("utf-8")
        self.assertIn("Download original Point presence KML", html)
        link = next(unescape(l) for l in re.findall(r'href="([^"]+)"', html)
                    if "format=presence-kml" in l)
        target = {k: v[0] for k, v in parse_qs(urlsplit(link).query).items()}
        self.assertEqual(self.get(target)[2],
                         self.get({**params, "format": "presence-kml"})[2])
        self.assertIn(b"Download matching KML",
                      self.get({**params, "format": "presence-table"})[2])
        empty = {"directory": "1", "axis": "world", "from_at": EARLY,
                 "to_at": LATE, "known_at": KNOWN, "entity": "missing",
                 "format": "presence-kml"}
        self.assertEqual(ET.fromstring(self.get(empty)[2]).findall(
            "k:Document/k:Placemark", ns), [])
        good = {**params, "format": "presence-kml"}
        for bad in ({**self.knowledge(), "format": "presence-kml"},
                    {**good, "presence": "unknown"},
                    {**good, "unexpected": "value"},
                    {**good, "source": "survey-a", "assertion": "unscoped"},
                    {**{k: v for k, v in good.items() if k != "entity"},
                     "source": "survey-a"}):
            status, _, body = self.get(bad)
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(body)["error"], "invalid_query")
        self.assertEqual(self.saved.read_bytes(), self.snapshot)


    def test_portable_kmz_contains_original_kml_and_complete_geojson(self):
        """Persisted WorldMini, actual loopback HTTP and lossless GIS package."""
        from zipfile import ZipFile
        from xml.etree import ElementTree as ET
        query = {**self.knowledge(), "entity": "site-1"}
        status, headers, blob = self.get({**query, "format": "presence-kmz"})
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/vnd.google-earth.kmz")
        self.assertIn(".kmz", headers["Content-Disposition"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        with ZipFile(io.BytesIO(blob)) as package:
            self.assertEqual(package.namelist(), ["doc.kml", "original-presence.geojson"])
            self.assertIsNone(package.testzip())
            kml = package.read("doc.kml")
            geojson = json.loads(package.read("original-presence.geojson"))
        self.assertEqual(kml, self.get({**query, "format": "presence-kml"})[2])
        self.assertEqual(geojson, json.loads(
            self.get({**query, "format": "presence-geojson"})[2]))
        ns = "{http://www.opengis.net/kml/2.2}"
        self.assertEqual(len(ET.fromstring(kml).findall(
            ns + "Document/" + ns + "Placemark")), len(geojson["features"]))
        self.assertEqual(blob, self.get({**query, "format": "presence-kmz"})[2])
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_portable_kmz_source_presence_scope_links_and_rejection(self):
        from zipfile import ZipFile
        query = {**self.knowledge(), "entity": "site-1"}
        self.assertIn(b"Download portable original Point KMZ",
                      self.get({**query, "format": "table"})[2])
        self.assertIn(b"Download matching KMZ",
                      self.get({**query, "format": "presence-table"})[2])
        for source in ("survey-a", "survey-b"):
            for presence in ("earlier", "later", "both"):
                scoped = {**query, "source": source, "presence": presence}
                status, _, blob = self.get({**scoped, "format": "presence-kmz"})
                self.assertEqual(status, 200)
                with ZipFile(io.BytesIO(blob)) as package:
                    selected = json.loads(package.read("original-presence.geojson"))
                expected = json.loads(
                    self.get({**scoped, "format": "presence-geojson"})[2])
                self.assertEqual(selected, expected)
        empty = {**query, "entity": "unknown-entity"}
        with ZipFile(io.BytesIO(self.get({**empty, "format": "presence-kmz"})[2])) as package:
            self.assertEqual(json.loads(
                package.read("original-presence.geojson"))["features"], [])
        for bad in ({**self.knowledge(), "format": "presence-kmz"},
                    {**query, "format": "presence-kmz", "presence": "invalid"},
                    {**query, "format": "presence-kmz", "unexpected": "value"},
                    {**query, "format": "presence-kmz", "source": "survey-a",
                     "assertion": "incomplete"}):
            status, _, raw = self.get(bad)
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(raw)["error"], "invalid_query")
        self.assertEqual(self.saved.read_bytes(), self.snapshot)


    def test_original_source_presence_gpx_waypoints_match_complete_geojson(self):
        """Real loopback HTTP: standard GPX waypoints with lossless MONDE evidence."""
        from xml.etree import ElementTree as ET
        params = {**self.knowledge(), "entity": "site-1"}
        status, headers, body = self.get({**params, "format": "presence-gpx"})
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/gpx+xml; charset=utf-8")
        self.assertIn(".gpx", headers["Content-Disposition"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        ns = "{http://www.topografix.com/GPX/1/1}"
        ext = "{urn:monde:original-source-evidence:1}"
        root = ET.fromstring(body)
        self.assertEqual(root.tag, ns + "gpx")
        self.assertEqual(root.attrib["version"], "1.1")
        original = json.loads(self.get({**params, "format": "presence-geojson"})[2])
        coverage = root.find(ns + "metadata/" + ns + "extensions/" + ext + "coverage")
        self.assertEqual(json.loads(coverage.text), original["monde_source_coverage"])
        points = root.findall(ns + "wpt")
        self.assertEqual(len(points), len(original["features"]))
        for feature, waypoint in zip(original["features"], points):
            lon, lat = feature["geometry"]["coordinates"]
            self.assertEqual((float(waypoint.attrib["lon"]), float(waypoint.attrib["lat"])),
                             (lon, lat))
            extension = waypoint.find(ns + "extensions")
            self.assertEqual(json.loads(extension.find(ext + "original_properties").text),
                             feature["properties"])
            self.assertEqual(extension.find(ext + "original_feature_id").text, feature["id"])
            self.assertIsNone(waypoint.find(ns + "trk"))
            self.assertIsNone(waypoint.find(ns + "rte"))
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_original_source_presence_gpx_filters_navigation_and_bad_queries(self):
        from xml.etree import ElementTree as ET
        params = {**self.knowledge(), "entity": "site-1"}
        self.assertIn(b"Download original Point waypoints GPX",
                      self.get({**params, "format": "table"})[2])
        self.assertIn(b"Download matching GPX waypoints",
                      self.get({**params, "format": "presence-table"})[2])
        ns = "{http://www.topografix.com/GPX/1/1}"
        ext = "{urn:monde:original-source-evidence:1}"
        for source in ("survey-a", "survey-b"):
            for presence in ("earlier", "later", "both"):
                scoped = {**params, "source": source, "presence": presence}
                status, _, body = self.get({**scoped, "format": "presence-gpx"})
                self.assertEqual(status, 200)
                root = ET.fromstring(body)
                expected = json.loads(
                    self.get({**scoped, "format": "presence-geojson"})[2])
                self.assertEqual(len(root.findall(ns + "wpt")), len(expected["features"]))
                self.assertEqual(
                    json.loads(root.find(ns + "metadata/" + ns + "extensions/" +
                                         ext + "coverage").text),
                    expected["monde_source_coverage"])
        empty = {**params, "entity": "unknown-entity", "format": "presence-gpx"}
        self.assertEqual(ET.fromstring(self.get(empty)[2]).findall(ns + "wpt"), [])
        for invalid in ({**self.knowledge(), "format": "presence-gpx"},
                        {**params, "format": "presence-gpx", "presence": "future"},
                        {**params, "format": "presence-gpx", "unexpected": "anything"},
                        {**params, "format": "presence-gpx", "source": "survey-a",
                         "assertion": "partial"}):
            status, _, payload = self.get(invalid)
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(payload)["error"], "invalid_query")
        self.assertEqual(self.saved.read_bytes(), self.snapshot)



    def test_original_presence_gpkg_opens_in_sqlite_with_exact_original_points(self):
        """Roundtrip actual loopback HTTP and OGC GeoPackage/WKB semantics."""
        import sqlite3
        import struct
        from tempfile import NamedTemporaryFile
        from pathlib import Path
        query = {**self.knowledge(), "entity": "site-1"}
        status, headers, blob = self.get({**query, "format": "presence-gpkg"})
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/geopackage+sqlite3")
        self.assertIn(".gpkg", headers["Content-Disposition"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertTrue(blob.startswith(b"SQLite format 3\x00"))
        original = json.loads(self.get({**query, "format": "presence-geojson"})[2])
        with NamedTemporaryFile(suffix=".gpkg") as file:
            Path(file.name).write_bytes(blob)
            db = sqlite3.connect(file.name)
            try:
                self.assertEqual(db.execute("PRAGMA application_id").fetchone()[0],
                                 0x47504B47)
                self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 10300)
                self.assertEqual(db.execute(
                    "SELECT table_name,data_type,srs_id FROM gpkg_contents"
                ).fetchone(), ("original_points", "features", 4326))
                self.assertEqual(db.execute(
                    "SELECT geometry_type_name,srs_id,z,m FROM gpkg_geometry_columns"
                ).fetchone(), ("POINT", 4326, 0, 0))
                coverage = json.loads(db.execute(
                    "SELECT coverage_json FROM monde_coverage WHERE id=1"
                ).fetchone()[0])
                self.assertEqual(coverage, original["monde_source_coverage"])
                rows = db.execute(
                    "SELECT feature_id,source_id,assertion_id,evidence_id,"
                    "earlier_visible,later_visible,visibility_transition,"
                    "original_properties_json,geom FROM original_points ORDER BY fid"
                ).fetchall()
                self.assertEqual(len(rows), len(original["features"]))
                for row, feature in zip(rows, original["features"]):
                    p = feature["properties"]
                    self.assertEqual(row[:4], (
                        feature["id"], p["source_id"],
                        p["monde_original_assertion_id"], p["evidence_id"]))
                    self.assertEqual(row[4:7], (
                        int(p["earlier_visible"]), int(p["later_visible"]),
                        p["monde_visibility_transition"]))
                    self.assertEqual(json.loads(row[7]), p)
                    geom = row[8]
                    self.assertEqual(geom[:2], b"GP")
                    self.assertEqual(struct.unpack("<BBI", geom[2:8]), (0, 1, 4326))
                    self.assertEqual(struct.unpack("<BI", geom[8:13]), (1, 1))
                    self.assertEqual(list(struct.unpack("<dd", geom[13:29])),
                                     feature["geometry"]["coordinates"])
            finally:
                db.close()
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_original_presence_gpkg_filter_empty_invalid_and_navigation(self):
        import sqlite3
        from pathlib import Path
        from tempfile import NamedTemporaryFile
        params = {**self.knowledge(), "entity": "site-1"}
        self.assertIn(b"Download original Point evidence GeoPackage",
                      self.get({**params, "format": "table"})[2])
        self.assertIn(b"Download matching GeoPackage",
                      self.get({**params, "format": "presence-table"})[2])
        for source in ("survey-a", "survey-b"):
            for selected in ("earlier", "later", "both"):
                query = {**params, "source": source, "presence": selected}
                actual = self.get({**query, "format": "presence-gpkg"})
                expected = json.loads(
                    self.get({**query, "format": "presence-geojson"})[2])
                self.assertEqual(actual[0], 200)
                with NamedTemporaryFile(suffix=".gpkg") as file:
                    Path(file.name).write_bytes(actual[2])
                    with sqlite3.connect(file.name) as db:
                        self.assertEqual(
                            db.execute("SELECT count(*) FROM original_points").fetchone()[0],
                            len(expected["features"]))
                        self.assertEqual(json.loads(db.execute(
                            "SELECT coverage_json FROM monde_coverage").fetchone()[0]),
                            expected["monde_source_coverage"])
        empty = self.get({**params, "entity": "missing",
                          "format": "presence-gpkg"})
        self.assertEqual(empty[0], 200)
        with NamedTemporaryFile(suffix=".gpkg") as file:
            Path(file.name).write_bytes(empty[2])
            with sqlite3.connect(file.name) as db:
                self.assertEqual(db.execute(
                    "SELECT count(*) FROM original_points").fetchone()[0], 0)
        for query in ({**self.knowledge(), "format": "presence-gpkg"},
                      {**params, "format": "presence-gpkg", "presence": "bad"},
                      {**params, "format": "presence-gpkg", "unknown": "bad"},
                      {**params, "format": "presence-gpkg", "source": "survey-a",
                       "assertion": "partial"}):
            self.assertEqual(self.get(query)[0], 400)
        self.assertEqual(self.saved.read_bytes(), self.snapshot)



    def test_global_presence_geopackage_exports_all_entities_across_cutoffs(self):
        """One offline GIS layer, with exact original identities across entities."""
        import sqlite3
        import struct
        from tempfile import NamedTemporaryFile
        query = self.knowledge()
        status, headers, blob = self.get({
            **query, "format": "presence-all-gpkg"})
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/geopackage+sqlite3")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertTrue(blob.startswith(b"SQLite format 3\x00"))
        earlier = self.world.export_geojson(AT, BEFORE)["features"]
        later = self.world.export_geojson(AT, AFTER)["features"]
        original_identities = {
            (f["properties"]["entity"], f["properties"]["source_id"], f["id"],
             f["properties"]["evidence_id"], *f["geometry"]["coordinates"])
            for f in earlier + later
        }
        with NamedTemporaryFile(suffix=".gpkg") as f:
            Path(f.name).write_bytes(blob)
            with sqlite3.connect(f.name) as db:
                rows = db.execute(
                    "SELECT entity,source_id,assertion_id,evidence_id,geom,"
                    "earlier_visible,later_visible,original_properties_json "
                    "FROM original_points ORDER BY fid").fetchall()
                found = set()
                for entity, source, assertion, evidence, geom, before, after, props in rows:
                    self.assertEqual(geom[:2], b"GP")
                    longitude, latitude = struct.unpack("<dd", geom[13:29])
                    found.add((entity, source, assertion, evidence, longitude, latitude))
                    data = json.loads(props)
                    self.assertEqual((entity, source, assertion, evidence),
                                     (data["entity"], data["source_id"],
                                      data["monde_original_assertion_id"],
                                      data["evidence_id"]))
                    self.assertEqual((before, after),
                                     (int(data["earlier_visible"]), int(data["later_visible"])))
                self.assertEqual(found, original_identities)
                self.assertEqual(len(rows), len(original_identities))
                coverage = json.loads(db.execute(
                    "SELECT coverage_json FROM monde_coverage").fetchone()[0])
                self.assertEqual(coverage["schema"],
                                 "MONDE_ORIGINAL_POINT_PRESENCE_GPKG_ALL_V1")
                self.assertEqual(coverage["original_report_count"], len(rows))
                self.assertEqual(coverage["distinct_entities"],
                                 len({item[0] for item in original_identities}))
        self.assertIn(b"Download all selected original Points GeoPackage",
                      self.get({**query, "format": "table"})[2])
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_global_geopackage_source_presence_filters_and_empty_matches(self):
        import sqlite3
        from tempfile import NamedTemporaryFile
        params = self.knowledge()
        for source in ("survey-a", "survey-b", "no-such-source"):
            for presence in ("earlier", "later", "both"):
                query = {**params, "source_prefix": source,
                         "presence": presence, "format": "presence-all-gpkg"}
                status, _, blob = self.get(query)
                self.assertEqual(status, 200)
                with NamedTemporaryFile(suffix=".gpkg") as f:
                    Path(f.name).write_bytes(blob)
                    with sqlite3.connect(f.name) as db:
                        rows = db.execute(
                            "SELECT source_id,earlier_visible,later_visible "
                            "FROM original_points").fetchall()
                        for reporter, earlier, later in rows:
                            self.assertTrue(reporter.startswith(source))
                            self.assertEqual(
                                ("both" if earlier and later else
                                 "earlier" if earlier else "later"), presence)
                        coverage = json.loads(db.execute(
                            "SELECT coverage_json FROM monde_coverage").fetchone()[0])
                        self.assertEqual(coverage["original_report_count"], len(rows))
        for bad in (
            {**params, "format": "presence-all-gpkg", "entity": "site-1"},
            {**params, "format": "presence-all-gpkg", "source": "survey-a"},
            {**params, "format": "presence-all-gpkg", "presence": "unknown"},
            {**params, "format": "presence-all-gpkg", "unexpected": "x"},
        ):
            self.assertEqual(self.get(bad)[0], 400)
        self.assertEqual(self.saved.read_bytes(), self.snapshot)


    def test_presence_geopackage_has_queryable_offline_spatial_index(self):
        """RTree covers exactly the original feature FIDs, including empty files."""
        import sqlite3
        from tempfile import NamedTemporaryFile

        for query in (
            {**self.knowledge(), "entity": "site-1",
             "format": "presence-gpkg"},
            {**self.knowledge(), "format": "presence-all-gpkg"},
            {**self.knowledge(), "entity": "nonexistent",
             "format": "presence-gpkg"},
        ):
            status, _, blob = self.get(query)
            self.assertEqual(status, 200)
            with NamedTemporaryFile(suffix=".gpkg") as file:
                Path(file.name).write_bytes(blob)
                with sqlite3.connect(file.name) as db:
                    self.assertEqual(
                        db.execute("SELECT extension_name, scope FROM gpkg_extensions "
                                   "WHERE table_name='original_points' "
                                   "AND column_name='geom'").fetchall(),
                        [("gpkg_rtree_index", "read-write")])
                    points = db.execute(
                        "SELECT fid,geom FROM original_points ORDER BY fid").fetchall()
                    indexed = db.execute(
                        "SELECT id,minx,maxx,miny,maxy "
                        "FROM rtree_original_points_geom ORDER BY id").fetchall()
                    self.assertEqual([row[0] for row in indexed],
                                     [row[0] for row in points])
                    self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0],
                                     "ok")
                    import struct
                    for (fid, geom), (index_id, west, east, south, north) in zip(
                            points, indexed):
                        lon, lat = struct.unpack("<dd", geom[13:29])
                        self.assertEqual(fid, index_id)
                        self.assertLessEqual(west, lon)
                        self.assertGreaterEqual(east, lon)
                        self.assertLessEqual(south, lat)
                        self.assertGreaterEqual(north, lat)
                        hits = db.execute(
                            "SELECT id FROM rtree_original_points_geom "
                            "WHERE minx<=? AND maxx>=? AND miny<=? AND maxy>=?",
                            (lon + 0.001, lon - 0.001,
                             lat + 0.001, lat - 0.001)).fetchall()
                        self.assertIn((fid,), hits)


    def test_global_geopackage_bbox_matches_original_source_geometry(self):
        """Download only originally reported Points; preserve SQLite provenance."""
        import sqlite3
        import struct
        from tempfile import NamedTemporaryFile
        params = self.knowledge()
        page = self.get({**params, "format": "table"})[2]
        self.assertIn(b"Download area GeoPackage", page)
        self.assertIn(b'name="bbox"', page)
        self.assertIn(b'name="format" value="presence-all-gpkg"', page)
        status, _, whole = self.get({**params, "format": "presence-all-gpkg"})
        self.assertEqual(status, 200)
        with NamedTemporaryFile(suffix=".gpkg") as f:
            Path(f.name).write_bytes(whole)
            with sqlite3.connect(f.name) as db:
                original = [(row[0], *struct.unpack("<dd", row[1][13:29]))
                            for row in db.execute(
                                "SELECT feature_id,geom FROM original_points")]
        self.assertTrue(original)
        lon, lat = original[0][1:]
        bounds = [max(-180.0, lon-.005), max(-90.0, lat-.005),
                  min(180.0, lon+.005), min(90.0, lat+.005)]
        expected = {fid for fid, x, y in original if
                    bounds[0] <= x <= bounds[2] and bounds[1] <= y <= bounds[3]}
        status, headers, blob = self.get({**params,
            "format": "presence-all-gpkg", "bbox": ",".join(map(str, bounds))})
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/geopackage+sqlite3")
        with NamedTemporaryFile(suffix=".gpkg") as f:
            Path(f.name).write_bytes(blob)
            with sqlite3.connect(f.name) as db:
                self.assertEqual({row[0] for row in db.execute(
                    "SELECT feature_id FROM original_points")}, expected)
                coverage = json.loads(db.execute(
                    "SELECT coverage_json FROM monde_coverage").fetchone()[0])
                self.assertEqual(coverage["bbox_filter"], bounds)
                self.assertEqual(coverage["original_report_count"], len(expected))
                self.assertEqual(db.execute(
                    "SELECT count(*) FROM rtree_original_points_geom").fetchone()[0],
                    len(expected))
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_global_geopackage_bbox_antimeridian_empty_and_invalid(self):
        """Wrapped query covers both longitude shores; malformed regions fail closed."""
        import sqlite3
        import struct
        from tempfile import NamedTemporaryFile
        world = sample(dateline=True)
        saved = Path(self.tmp.name) / "dateline-region.json"
        world.save(saved)
        initial = saved.read_bytes()
        other = create_server(saved)
        thread = threading.Thread(target=other.serve_forever, daemon=True)
        thread.start()
        try:
            params = {"directory": "1", "axis": "world", "from_at": EARLY,
                      "to_at": LATE, "known_at": KNOWN,
                      "format": "presence-all-gpkg", "bbox": "179,-1,-179,1"}
            status, _, blob = self.get(params, server=other)
            self.assertEqual(status, 200)
            with NamedTemporaryFile(suffix=".gpkg") as f:
                Path(f.name).write_bytes(blob)
                with sqlite3.connect(f.name) as db:
                    positions = [struct.unpack("<dd", row[0][13:29])
                                 for row in db.execute("SELECT geom FROM original_points")]
                    self.assertTrue(any(x < -179 for x, y in positions))
                    self.assertTrue(any(x > 179 for x, y in positions))
                    self.assertTrue(all(x >= 179 or x <= -179 for x, y in positions))
                    self.assertEqual(db.execute(
                        "SELECT count(*) FROM rtree_original_points_geom").fetchone()[0],
                        len(positions))
            status, _, blob = self.get({**params, "bbox": "40,40,41,41"}, server=other)
            self.assertEqual(status, 200)
            with NamedTemporaryFile(suffix=".gpkg") as f:
                Path(f.name).write_bytes(blob)
                with sqlite3.connect(f.name) as db:
                    self.assertEqual(db.execute(
                        "SELECT count(*) FROM original_points").fetchone()[0], 0)
                    self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            for bad in ("0,0,0,1", "1,5,2,4", "nan,0,1,1",
                        "-181,0,1,1", "180,0,-180,1", "0,0,1,91",
                        "0,0,1", "a,b,c,d"):
                self.assertEqual(self.get({**params, "bbox": bad},
                                          server=other)[0], 400)
            self.assertEqual(self.get({**params, "format": "json"},
                                      server=other)[0], 400)
            self.assertEqual(self.get({**params, "entity": "site-1"},
                                      server=other)[0], 400)
        finally:
            other.shutdown()
            thread.join(timeout=5)
            other.server_close()
        self.assertEqual(saved.read_bytes(), initial)


    def test_global_geojson_matches_same_source_evidence_as_geopackage(self):
        import sqlite3
        from tempfile import NamedTemporaryFile
        query = self.knowledge()
        status, headers, raw = self.get({**query, "format": "presence-all-geojson"})
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers["Content-Type"])
        result = json.loads(raw)
        self.assertEqual(result["monde_source_coverage"]["schema"],
                         "MONDE_ORIGINAL_POINT_PRESENCE_GEOJSON_ALL_V1")
        self.assertEqual(result["monde_source_coverage"]["original_report_count"],
                         len(result["features"]))
        self.assertEqual(len({f["id"] for f in result["features"]}),
                         len(result["features"]))
        _, _, raw_gpkg = self.get({**query, "format": "presence-all-gpkg"})
        with NamedTemporaryFile(suffix=".gpkg") as file:
            Path(file.name).write_bytes(raw_gpkg)
            with sqlite3.connect(file.name) as db:
                self.assertEqual(
                    {fid: json.loads(props) for fid, props in db.execute(
                        "SELECT feature_id,original_properties_json FROM original_points")},
                    {f["id"]: f["properties"] for f in result["features"]})
        html = self.get({**query, "format": "table"})[2]
        self.assertIn(b"Download all selected original Points GeoJSON", html)
        self.assertIn(b"Download area GeoJSON", html)
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_global_geojson_preserves_source_presence_filters_and_rejects_scope(self):
        query = self.knowledge()
        for presence, expected in (("earlier", "EARLIER_ONLY"),
                                   ("later", "LATER_ONLY"), ("both", "BOTH_CUTOFFS")):
            status, _, raw = self.get({**query, "format": "presence-all-geojson",
                                       "source_prefix": "survey-a", "presence": presence})
            self.assertEqual(status, 200)
            result = json.loads(raw)
            self.assertTrue(all(f["properties"]["source_id"].startswith("survey-a") and
                                f["properties"]["monde_visibility_transition"] == expected
                                for f in result["features"]))
        for bad in ({"entity": "site-1"}, {"source": "survey-a"},
                    {"presence": "invalid"}, {"bbox": "0,0,0,1"},
                    {"bbox": "nan,0,1,1"}, {"unknown": "x"}):
            self.assertEqual(self.get({**query, "format": "presence-all-geojson",
                                       **bad})[0], 400)
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_global_geojson_wrapped_bbox_matches_geopackage_point_identities(self):
        import sqlite3
        from tempfile import NamedTemporaryFile
        world = sample(dateline=True)
        saved = Path(self.tmp.name) / "dateline-geojson.json"
        world.save(saved)
        initial = saved.read_bytes()
        server = create_server(saved)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for bbox in ("179,-1,-179,1", "40,40,41,41"):
                params = {"directory": "1", "axis": "world", "from_at": EARLY,
                          "to_at": LATE, "known_at": KNOWN, "bbox": bbox}
                status, _, raw = self.get({**params, "format": "presence-all-geojson"},
                                          server)
                self.assertEqual(status, 200)
                result = json.loads(raw)
                self.assertEqual(result["monde_source_coverage"]["bbox_filter"],
                                 [float(x) for x in bbox.split(",")])
                status, _, gpkg = self.get({**params, "format": "presence-all-gpkg"},
                                            server)
                self.assertEqual(status, 200)
                with NamedTemporaryFile(suffix=".gpkg") as file:
                    Path(file.name).write_bytes(gpkg)
                    with sqlite3.connect(file.name) as db:
                        self.assertEqual(
                            {row[0] for row in db.execute(
                                "SELECT feature_id FROM original_points")},
                            {feature["id"] for feature in result["features"]})
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
        self.assertEqual(saved.read_bytes(), initial)


    def test_global_csv_has_exact_original_geojson_feature_identities_and_metadata(self):
        import csv
        import io
        query = self.knowledge()
        status, headers, payload = self.get({**query, "format": "presence-all-csv"})
        self.assertEqual(status, 200)
        self.assertIn("text/csv", headers["Content-Type"])
        self.assertIn("attachment", headers["Content-Disposition"])
        rows = list(csv.DictReader(io.StringIO(payload.decode("utf-8"))))
        original = json.loads(self.get({**query, "format": "presence-all-geojson"})[2])
        self.assertEqual(len(rows), len(original["features"]))
        self.assertEqual([r["feature_id"] for r in rows],
                         [f["id"] for f in original["features"]])
        for row, feature in zip(rows, original["features"]):
            props = feature["properties"]
            self.assertEqual(json.loads(row["original_properties_json"]), props)
            self.assertEqual(row["source_id"], props["source_id"])
            self.assertEqual(row["assertion_id"], props["monde_original_assertion_id"])
            self.assertEqual(row["evidence_id"], props["evidence_id"])
            self.assertEqual([float(row["longitude"]), float(row["latitude"])],
                             feature["geometry"]["coordinates"])
            self.assertEqual(int(row["earlier_visible"]), int(props["earlier_visible"]))
            self.assertEqual(int(row["later_visible"]), int(props["later_visible"]))
            self.assertEqual(row["visibility_transition"],
                             props["monde_visibility_transition"])
            for side in ("earlier", "later"):
                cutoff = original["monde_source_coverage"]["cutoffs"][side]
                self.assertEqual(row[side+"_world_at"], cutoff["world_at"])
                self.assertEqual(row[side+"_known_at"], cutoff["knowledge_at"])
        page = self.get({**query, "format": "table"})[2]
        self.assertIn(b"Download all selected original Points CSV", page)
        self.assertIn(b"Download area CSV", page)
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_global_csv_reuses_source_and_presence_filters_and_validates_scope(self):
        import csv
        import io
        for presence in ("earlier", "later", "both"):
            query = {**self.knowledge(), "format": "presence-all-csv",
                     "source_prefix": "survey-a", "presence": presence}
            status, _, raw = self.get(query)
            self.assertEqual(status, 200)
            rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
            geo = json.loads(self.get({**query, "format": "presence-all-geojson"})[2])
            self.assertEqual([row["feature_id"] for row in rows],
                             [f["id"] for f in geo["features"]])
        for invalid in ({"entity": "site-1"}, {"source": "survey-a"},
                        {"presence": "unknown"}, {"bbox": "0,0,0,1"},
                        {"bbox": "nan,0,1,1"}, {"unexpected": "x"}):
            self.assertEqual(self.get({**self.knowledge(),
                                      "format": "presence-all-csv", **invalid})[0], 400)
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_global_csv_wrapped_bbox_and_empty_region_preserve_saved_world(self):
        import csv
        import io
        world = sample(dateline=True)
        saved = Path(self.tmp.name) / "dateline-csv-global.json"
        world.save(saved)
        baseline = saved.read_bytes()
        server = create_server(saved)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for bbox in ("179,-1,-179,1", "40,40,41,41"):
                query = {"directory": "1", "axis": "world", "from_at": EARLY,
                         "to_at": LATE, "known_at": KNOWN, "bbox": bbox}
                status, _, raw = self.get({**query, "format": "presence-all-csv"},
                                          server)
                self.assertEqual(status, 200)
                rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
                geo = json.loads(self.get({**query,
                    "format": "presence-all-geojson"}, server)[2])
                self.assertEqual([r["feature_id"] for r in rows],
                                 [f["id"] for f in geo["features"]])
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
        self.assertEqual(saved.read_bytes(), baseline)


    def test_global_presence_map_reuses_exact_original_point_geojson(self):
        """Live HTTP map uses the global original evidence selector, no inferred movement."""
        from monde.source_pair_changes import source_directory_all_presence_map
        query = self.knowledge()
        base = {**query, "format": "presence-all-geojson"}
        original = json.loads(self.get(base)[2])
        status, headers, rendered = self.get({**query, "format": "presence-all-map"})
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn(b"Original source", rendered)
        self.assertIn(b"Both comparison periods", rendered)
        self.assertIn(b"not verified movement", rendered)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn("connect-src 'none'", headers["Content-Security-Policy"])
        directory = json.loads(self.get({**query, "format": "json"})[2])
        layer = source_directory_all_presence_map(self.world, directory)
        self.assertEqual([f["id"] for f in layer["features"]],
                         [f["id"] for f in original["features"]])
        self.assertEqual([f["geometry"] for f in layer["features"]],
                         [f["geometry"] for f in original["features"]])
        self.assertEqual(layer["monde_bbox_query"]["total_source_features"],
                         len(original["features"]))
        self.assertTrue(all(f["properties"]["monde_inside_bbox"]
                            for f in layer["features"]))
        self.assertIn(b"Map all selected original Points", self.get(
            {**query, "format": "table"})[2])
        self.assertIn(b"Open area evidence map", self.get(
            {**query, "format": "table"})[2])
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_global_presence_map_respects_reporter_and_temporal_filters(self):
        from monde.source_pair_changes import source_directory_all_presence_map
        for presence in ("earlier", "later", "both"):
            query = {**self.knowledge(), "source_prefix": "survey-a",
                     "presence": presence}
            self.assertEqual(self.get({**query, "format": "presence-all-map"})[0], 200)
            directory = json.loads(self.get({
                **{k: value for k, value in query.items() if k != "presence"},
                "format": "json"})[2])
            layer = source_directory_all_presence_map(self.world, directory, presence)
            geo = json.loads(self.get({**query, "format": "presence-all-geojson"})[2])
            self.assertEqual([f["id"] for f in layer["features"]],
                             [f["id"] for f in geo["features"]])
            self.assertEqual(layer["monde_source_coverage"]["presence_filter"], presence)
        for bad in ({"entity": "site-1"}, {"source": "survey-a"},
                    {"presence": "invalid"}, {"bbox": "nan,-1,2,1"},
                    {"bbox": "0,0,0,1"}, {"unexpected": "evil"}):
            self.assertEqual(self.get({
                **self.knowledge(), "format": "presence-all-map", **bad})[0], 400)
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_global_presence_map_wrapped_bbox_and_empty_area_are_read_only(self):
        from monde.source_pair_changes import source_directory_all_presence_map
        world = sample(dateline=True)
        saved = Path(self.tmp.name) / "dateline-presence-map.json"
        world.save(saved)
        initial = saved.read_bytes()
        server = create_server(saved)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for bbox in ("179,-1,-179,1", "40,40,41,41"):
                query = {"directory": "1", "axis": "world", "from_at": EARLY,
                         "to_at": LATE, "known_at": KNOWN, "bbox": bbox}
                status, _, rendered = self.get({**query, "format": "presence-all-map"}, server)
                self.assertEqual(status, 200)
                self.assertIn(b"Both comparison periods", rendered)
                source = json.loads(self.get({**query, "format": "presence-all-geojson"},
                                             server)[2])
                directory = json.loads(self.get({
                    **{k: value for k, value in query.items() if k != "bbox"},
                    "format": "json"}, server)[2])
                box = [float(x) for x in bbox.split(",")]
                layer = source_directory_all_presence_map(world, directory, bbox=box)
                self.assertEqual(layer["monde_bbox_query"]["bbox"], box)
                self.assertEqual([f["id"] for f in layer["features"]],
                                 [f["id"] for f in source["features"]])
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
        self.assertEqual(saved.read_bytes(), initial)


    def test_global_exact_reporter_drilldown_consistent_across_map_geojson_csv_gpkg(self):
        import sqlite3
        from tempfile import NamedTemporaryFile
        query = {**self.knowledge(), "source_exact": "survey-a"}
        status, _, geo_raw = self.get({**query, "format": "presence-all-geojson"})
        self.assertEqual(status, 200)
        doc = json.loads(geo_raw)
        original_ids = [row["id"] for row in doc["features"]]
        self.assertTrue(original_ids)
        self.assertEqual(doc["monde_source_coverage"]["exact_source_filter"], "survey-a")
        self.assertEqual(doc["monde_source_coverage"]["selected_sources"], 1)
        self.assertTrue(all(row["properties"]["source_id"] == "survey-a"
                            for row in doc["features"]))
        status, headers, html = self.get({**query, "format": "presence-all-map"})
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn(b"Original source", html)
        status, _, csv_raw = self.get({**query, "format": "presence-all-csv"})
        self.assertEqual(status, 200)
        rows = list(csv.DictReader(io.StringIO(csv_raw.decode("utf-8"))))
        self.assertEqual([row["feature_id"] for row in rows], original_ids)
        status, _, gpkg_raw = self.get({**query, "format": "presence-all-gpkg"})
        self.assertEqual(status, 200)
        with NamedTemporaryFile(suffix=".gpkg") as target:
            Path(target.name).write_bytes(gpkg_raw)
            with sqlite3.connect(target.name) as db:
                ids = [row[0] for row in db.execute(
                    "SELECT feature_id FROM original_points ORDER BY feature_id")]
        self.assertEqual(ids, sorted(original_ids))
        directory_html = self.get({**self.knowledge(), "format": "table"})[2]
        self.assertIn(b"Map this reporter across all entities", directory_html)
        self.assertIn(b"source_exact=survey-a", directory_html)
        prefix_html = self.get({**self.knowledge(), "format": "table",
                                "source_prefix": "survey"})[2]
        self.assertIn(b"source_exact=survey-a", prefix_html)
        self.assertNotIn(b"source_prefix=survey&amp;format=presence-all-map", prefix_html)
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_global_exact_reporter_unknown_and_invalid_scope_fail_closed(self):
        for fmt in ("presence-all-map", "presence-all-geojson",
                    "presence-all-csv", "presence-all-gpkg"):
            query = {**self.knowledge(), "format": fmt,
                     "source_exact": "no-such-source"}
            status, _, raw = self.get(query)
            self.assertEqual(status, 200)
            if fmt == "presence-all-geojson":
                self.assertEqual(json.loads(raw)["features"], [])
            elif fmt == "presence-all-csv":
                self.assertEqual(len(list(csv.DictReader(
                    io.StringIO(raw.decode("utf-8"))))), 0)
        for bad in (
            {"source_exact": ""}, {"source_exact": "\x7f"},
            {"source_exact": "survey-a", "source_prefix": "survey"},
            {"source_exact": "survey-a", "entity": "site-1"},
            {"source_exact": "survey-a", "source": "survey-a"},
            {"source_exact": "survey-a", "format": "table"},
        ):
            payload = {**self.knowledge(), "format": "presence-all-geojson", **bad}
            self.assertEqual(self.get(payload)[0], 400)
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_global_exact_reporter_wrapped_area_preserves_source_identity(self):
        world = sample(dateline=True)
        saved = Path(self.tmp.name) / "dateline-exact-source.json"
        world.save(saved)
        unchanged = saved.read_bytes()
        server = create_server(saved)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            baseline = { "directory": "1", "axis": "world",
                        "from_at": EARLY, "to_at": LATE, "known_at": KNOWN,
                        "bbox": "179,-1,-179,1" }
            geo = json.loads(self.get({
                **baseline, "format": "presence-all-geojson"}, server)[2])
            available = sorted({f["properties"]["source_id"] for f in geo["features"]})
            self.assertTrue(available)
            for reporter in available:
                query = {**baseline, "source_exact": reporter}
                scoped = json.loads(self.get({**query,
                    "format": "presence-all-geojson"}, server)[2])
                self.assertEqual([f["id"] for f in scoped["features"]],
                    [f["id"] for f in geo["features"]
                     if f["properties"]["source_id"] == reporter])
                self.assertEqual(self.get({
                    **query, "format": "presence-all-map"}, server)[0], 200)
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
        self.assertEqual(saved.read_bytes(), unchanged)


    def test_global_two_reporters_share_original_point_identities_in_four_formats(self):
        import sqlite3
        from tempfile import NamedTemporaryFile
        query = {**self.knowledge(), "compare_a": "survey-a",
                 "compare_b": "survey-b"}
        original = json.loads(self.get({
            **self.knowledge(), "format": "presence-all-geojson"})[2])
        status, _, body = self.get({**query, "format": "presence-all-geojson"})
        self.assertEqual(status, 200)
        compared = json.loads(body)
        self.assertEqual(compared["monde_source_coverage"]["compared_source_ids"],
                         ["survey-a", "survey-b"])
        expected = [feature for feature in original["features"]
                    if feature["properties"]["source_id"] in ("survey-a", "survey-b")]
        self.assertEqual(compared["features"], expected)
        self.assertTrue(expected)
        for fmt in ("presence-all-map", "presence-all-csv", "presence-all-gpkg"):
            status, headers, body = self.get({**query, "format": fmt})
            self.assertEqual(status, 200)
            if fmt == "presence-all-map":
                self.assertIn(b"Original source", body)
                self.assertIn("connect-src 'none'", headers["Content-Security-Policy"])
            elif fmt == "presence-all-csv":
                rows = list(csv.DictReader(io.StringIO(body.decode("utf-8"))))
                self.assertEqual([row["feature_id"] for row in rows],
                                 [row["id"] for row in expected])
            else:
                with NamedTemporaryFile(suffix=".gpkg") as target:
                    Path(target.name).write_bytes(body)
                    with sqlite3.connect(target.name) as db:
                        ids = [row[0] for row in db.execute(
                            "SELECT feature_id FROM original_points ORDER BY feature_id")]
                self.assertEqual(ids, sorted(row["id"] for row in expected))
        table = self.get({**self.knowledge(), "format": "table"})[2]
        self.assertIn(b'Compare two original reporters across all entities', table)
        self.assertIn(b'name="compare_a"', table)
        self.assertIn(b'name="compare_b"', table)
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_global_two_reporters_scope_rejections_and_missing_source(self):
        base = {**self.knowledge(), "format": "presence-all-geojson"}
        for bad in (
                {"compare_a": "survey-a"},
                {"compare_a": "survey-a", "compare_b": "survey-a"},
                {"compare_a": "survey-a", "compare_b": ""},
                {"compare_a": "survey-a", "compare_b": "\x7f"},
                {"compare_a": "survey-a", "compare_b": "survey-b",
                 "source_exact": "survey-a"},
                {"compare_a": "survey-a", "compare_b": "survey-b",
                 "source_prefix": "survey"},
                {"compare_a": "survey-a", "compare_b": "survey-b",
                 "entity": "site-1"},
                {"compare_a": "survey-a", "compare_b": "survey-b",
                 "format": "json"},
        ):
            self.assertEqual(self.get({**base, **bad})[0], 400, bad)
        out = json.loads(self.get({
            **base, "compare_a": "survey-a", "compare_b": "unknown-source"})[2])
        self.assertEqual({f["properties"]["source_id"] for f in out["features"]},
                         {"survey-a"})
        self.assertEqual(out["monde_source_coverage"]["selected_sources"], 1)
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_global_two_reporters_keep_presence_and_area_cutoffs(self):
        from monde.source_pair_changes import source_directory_all_presence_geojson
        directory = json.loads(self.get({**self.knowledge(), "format": "json"})[2])
        for presence in ("earlier", "later", "both"):
            query = {**self.knowledge(), "compare_a": "survey-a",
                     "compare_b": "survey-b", "presence": presence,
                     "bbox": "-180,-90,180,90"}
            status, _, raw = self.get({**query, "format": "presence-all-geojson"})
            self.assertEqual(status, 200)
            expected = source_directory_all_presence_geojson(
                self.world, directory, presence, [-180, -90, 180, 90],
                source_compare=("survey-a", "survey-b"))
            self.assertEqual(json.loads(raw), expected)
        self.assertEqual(self.saved.read_bytes(), self.snapshot)


    def test_two_reporter_matrix_json_preserves_gis_original_evidence(self):
        q = {**self.knowledge(), "compare_a": "survey-a",
             "compare_b": "survey-b"}
        status, headers, raw = self.get({**q, "format": "presence-all-compare-json"})
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        matrix = json.loads(raw)
        self.assertEqual(matrix["schema"], "MONDE_ORIGINAL_POINT_REPORTER_MATRIX_V1")
        self.assertEqual((matrix["source_a"], matrix["source_b"]),
                         ("survey-a", "survey-b"))
        status, _, raw_geo = self.get({**q, "format": "presence-all-geojson"})
        self.assertEqual(status, 200)
        features = json.loads(raw_geo)["features"]
        self.assertEqual(matrix["total_original_reports"], len(features))
        self.assertEqual(matrix["total_entities"], len({
            f["properties"]["entity"] for f in features}))
        self.assertTrue(matrix["entities"])
        for item in matrix["entities"]:
            for period in ("earlier", "later"):
                current = [f for f in features if
                           f["properties"]["entity"] == item["entity"] and
                           f["properties"][period + "_visible"]]
                a = [f for f in current if f["properties"]["source_id"] == "survey-a"]
                b = [f for f in current if f["properties"]["source_id"] == "survey-b"]
                expected = ("BOTH_REPORTED" if a and b else
                            "ONLY_SOURCE_A" if a else
                            "ONLY_SOURCE_B" if b else "NOT_REPORTED")
                self.assertEqual(item[period]["status"], expected)
                for key, originals in (("source_a", a), ("source_b", b)):
                    self.assertEqual(item[period][key]["count"], len(originals))
                    self.assertEqual(item[period][key]["assertion_ids"],
                                     [f["properties"]["monde_original_assertion_id"]
                                      for f in originals])
                    self.assertEqual(item[period][key]["evidence_ids"],
                                     [f["properties"]["evidence_id"]
                                      for f in originals])
                    self.assertEqual(item[period][key]["coordinates"],
                                     [f["geometry"]["coordinates"]
                                      for f in originals])
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_two_reporter_matrix_browser_and_strict_query(self):
        q = {**self.knowledge(), "compare_a": "survey-a",
             "compare_b": "survey-b"}
        status, _, html = self.get({**q, "format": "presence-all-compare-table"})
        self.assertEqual(status, 200)
        self.assertIn(b"Original reporter Point matrix", html)
        self.assertIn(b"Open original evidence map", html)
        self.assertIn(b"presence-all-compare-json", html)
        status, _, index = self.get(self.knowledge())
        self.assertEqual(status, 200)
        self.assertIn(b"Original reporting table", index)
        self.assertIn(b"Original reporting JSON", index)
        for invalid in ({"compare_b": "survey-a"}, {"compare_a": ""},
                        {"source_exact": "survey-a"},
                        {"source_prefix": "sur"}, {"entity": "site-1"}):
            for fmt in ("presence-all-compare-json", "presence-all-compare-table"):
                status, _, raw = self.get({**q, **invalid, "format": fmt})
                self.assertEqual(status, 400)
                self.assertEqual(json.loads(raw), {"error": "invalid_query"})
        for fmt in ("presence-all-compare-json", "presence-all-compare-table"):
            self.assertEqual(self.get({**self.knowledge(), "format": fmt})[0], 400)
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_two_reporter_matrix_respects_spatial_and_visibility_filters(self):
        from monde.source_pair_changes import source_directory_global_pair_matrix
        directory = json.loads(self.get({**self.knowledge(), "format": "json"})[2])
        for period in ("earlier", "later", "both"):
            query = {**self.knowledge(), "compare_a": "survey-a",
                     "compare_b": "survey-b", "presence": period,
                     "bbox": "-180,-90,180,90"}
            status, _, raw = self.get({**query, "format": "presence-all-compare-json"})
            self.assertEqual(status, 200)
            expected = source_directory_global_pair_matrix(
                self.world, directory, period, [-180, -90, 180, 90],
                ("survey-a", "survey-b"))
            self.assertEqual(json.loads(raw), expected)
        status, _, raw = self.get({
            **self.knowledge(), "compare_a": "unknown-a", "compare_b": "unknown-b",
            "format": "presence-all-compare-json"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)["entities"], [])
        self.assertEqual(self.saved.read_bytes(), self.snapshot)


    def test_two_reporter_matrix_csv_matches_json_and_filtered_evidence(self):
        for presence in (None, "earlier", "later", "both"):
            query = {**self.knowledge(), "compare_a": "survey-a",
                     "compare_b": "survey-b", "bbox": "-180,-90,180,90"}
            if presence:
                query["presence"] = presence
            status, _, raw = self.get({**query, "format": "presence-all-compare-json"})
            self.assertEqual(status, 200)
            matrix = json.loads(raw)
            status, headers, raw = self.get({
                **query, "format": "presence-all-compare-csv"})
            self.assertEqual(status, 200)
            self.assertEqual(headers["Content-Type"], "text/csv; charset=utf-8")
            self.assertIn("monde-original-reporter-matrix.csv",
                          headers["Content-Disposition"])
            self.assertEqual(headers["Cache-Control"], "no-store")
            rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
            self.assertEqual(len(rows), 2 * matrix["total_entities"])
            for row in rows:
                item = next(x for x in matrix["entities"] if
                            x["entity"] == row["entity"])
                period = row["period"]
                self.assertEqual(row["reporting_status"], item[period]["status"])
                self.assertEqual((row["source_a"], row["source_b"]),
                                 (matrix["source_a"], matrix["source_b"]))
                for reporter in ("source_a", "source_b"):
                    original = item[period][reporter]
                    self.assertEqual(int(row[reporter + "_count"]),
                                     original["count"])
                    for field in ("assertion_ids", "evidence_ids", "coordinates"):
                        self.assertEqual(
                            json.loads(row[reporter + "_" + field + "_json"]),
                            original[field])
                cutoff = matrix["cutoffs"][period]
                self.assertEqual((row["world_at"], row["knowledge_at"]),
                                 (cutoff["world_at"], cutoff["knowledge_at"]))
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_two_reporter_matrix_csv_navigation_and_rejections(self):
        base = {**self.knowledge(), "compare_a": "survey-a",
                "compare_b": "survey-b"}
        status, _, page = self.get({
            **base, "format": "presence-all-compare-table"})
        self.assertEqual(status, 200)
        self.assertIn(b"Download reporter matrix CSV", page)
        self.assertIn(b"presence-all-compare-csv", page)
        status, _, index = self.get(self.knowledge())
        self.assertEqual(status, 200)
        self.assertIn(b"Original reporting matrix CSV", index)
        for extra in ({"compare_b": "survey-a"}, {"compare_a": ""},
                      {"source_exact": "survey-a"}, {"entity": "site-1"},
                      {"source_prefix": "sur"}):
            status, _, raw = self.get({
                **base, **extra, "format": "presence-all-compare-csv"})
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(raw), {"error": "invalid_query"})
        self.assertEqual(self.get({
            **self.knowledge(), "format": "presence-all-compare-csv"})[0], 400)
        status, _, empty = self.get({
            **self.knowledge(), "compare_a": "missing-a",
            "compare_b": "missing-b", "format": "presence-all-compare-csv"})
        self.assertEqual(status, 200)
        self.assertEqual(list(csv.DictReader(
            io.StringIO(empty.decode("utf-8")))), [])
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_two_reporter_matrix_csv_escapes_spreadsheet_formulas(self):
        from monde.source_pair_changes import source_directory_global_pair_matrix_csv
        original = lambda count, ids: {
            "count": count, "assertion_ids": ids, "evidence_ids": ["@e"] if ids else [],
            "coordinates": [[1.0, 2.0]] if ids else []}
        matrix = {
            "schema": "MONDE_ORIGINAL_POINT_REPORTER_MATRIX_V1",
            "source_a": "=reporter", "source_b": "@reporter",
            "cutoffs": {"earlier": {"world_at": AT, "knowledge_at": BEFORE},
                        "later": {"world_at": AT, "knowledge_at": AFTER}},
            "entities": [{
                "entity": "+entity",
                "earlier": {"status": "ONLY_SOURCE_A",
                            "source_a": original(1, ["=assertion"]),
                            "source_b": original(0, [])},
                "later": {"status": "ONLY_SOURCE_B",
                          "source_a": original(0, []),
                          "source_b": original(1, ["-assertion"])}}]}
        rows = list(csv.DictReader(io.StringIO(
            source_directory_global_pair_matrix_csv(matrix))))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["entity"], "'+entity")
        self.assertEqual(rows[0]["source_a"], "'=reporter")
        self.assertEqual(rows[0]["source_b"], "'@reporter")
        self.assertEqual(json.loads(rows[0]["source_a_assertion_ids_json"]),
                         ["=assertion"])
        self.assertEqual(json.loads(rows[1]["source_b_assertion_ids_json"]),
                         ["-assertion"])
        with self.assertRaises(ValueError):
            source_directory_global_pair_matrix_csv({"schema": "UNEXPECTED"})



    def test_two_reporter_matrix_drills_into_existing_source_maps(self):
        query = {**self.knowledge(), "compare_a": "survey-a",
                 "compare_b": "survey-b", "bbox": "-180,-90,180,90"}
        status, _, raw = self.get({**query, "format": "presence-all-compare-json"})
        self.assertEqual(status, 200)
        rows = json.loads(raw)["entities"]
        self.assertTrue(rows)
        status, _, page = self.get({**query, "format": "presence-all-compare-table"})
        self.assertEqual(status, 200)
        self.assertIn(b"outside any global bbox filter", page)
        self.assertNotIn(b'value="presence-all-compare-table",', page)
        anchors = re.findall(r'<a href="([^"]+)">([^<]+)</a>', page.decode("utf-8"))
        links = [(label, {key: values[0] for key, values in
                 parse_qs(urlsplit(unescape(href)).query).items()})
                 for href, label in anchors]
        first = rows[0]
        entity = first["entity"]
        dossier = next(q for label, q in links if label == "Entity evidence"
                       and q.get("entity") == entity)
        self.assertEqual(dossier["format"], "presence-table")
        for key in self.knowledge():
            self.assertEqual(dossier[key], self.knowledge()[key])
        self.assertNotIn("bbox", dossier)
        self.assertNotIn("compare_a", dossier)
        self.assertNotIn("compare_b", dossier)
        status, _, original = self.get(dossier)
        self.assertEqual(status, 200)
        self.assertIn(b"<!doctype html>", original.lower())
        for side, label, source in (
                ("source_a", "Source A map", "survey-a"),
                ("source_b", "Source B map", "survey-b")):
            present = any(first[period][side]["count"]
                          for period in ("earlier", "later"))
            found = [q for text, q in links
                     if text == label and q.get("entity") == entity]
            self.assertEqual(bool(found), bool(present))
            if found:
                selected = found[0]
                self.assertEqual((selected["format"], selected["source"]),
                                 ("presence-map", source))
                self.assertNotIn("bbox", selected)
                for key in self.knowledge():
                    self.assertEqual(selected[key], self.knowledge()[key])
                status, _, map_html = self.get(selected)
                self.assertEqual(status, 200)
                self.assertIn(b"<!doctype html>", map_html.lower())
        self.assertEqual(self.saved.read_bytes(), self.snapshot)


    def test_reporter_matrix_transitions_keep_http_json_csv_and_html_in_sync(self):
        """Real saved WorldMini on the loopback server; no inferred truth."""
        base = {**self.knowledge(), "compare_a": "survey-a",
                "compare_b": "survey-b", "bbox": "-180,-90,180,90"}
        status, _, raw = self.get({**base, "format": "presence-all-compare-json"})
        self.assertEqual(status, 200)
        original = json.loads(raw)
        self.assertEqual(original["total_entities"], len(original["entities"]))
        self.assertEqual(original["total_entities_unfiltered"], len(original["entities"]))
        self.assertEqual(sum(original["transition_counts"].values()),
                         original["total_entities"])
        classification = {
            "reporters-changed": "REPORTERS_CHANGED",
            "evidence-changed": "ORIGINAL_EVIDENCE_CHANGED",
            "unchanged": "UNCHANGED",
        }
        all_entities = {row["entity"]: row for row in original["entities"]}
        for selected, category in classification.items():
            query = {**base, "transition": selected}
            status, _, raw = self.get({**query, "format": "presence-all-compare-json"})
            self.assertEqual(status, 200)
            current = json.loads(raw)
            self.assertEqual(current["transition_filter"], selected)
            self.assertEqual(current["transition_counts"], original["transition_counts"])
            self.assertEqual(current["total_entities_unfiltered"], len(all_entities))
            self.assertEqual(current["total_entities"],
                             original["transition_counts"][category])
            self.assertEqual([row["entity"] for row in current["entities"]],
                             [row["entity"] for row in original["entities"]
                              if row["reporting_transition"] == category])
            for row in current["entities"]:
                self.assertEqual(row["earlier"], all_entities[row["entity"]]["earlier"])
                self.assertEqual(row["later"], all_entities[row["entity"]]["later"])
            status, headers, raw_csv = self.get({
                **query, "format": "presence-all-compare-csv"})
            self.assertEqual(status, 200)
            self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
            rows = list(csv.DictReader(io.StringIO(raw_csv.decode("utf-8"))))
            self.assertEqual(len(rows), 2 * current["total_entities"])
            self.assertEqual({r["reporting_transition"] for r in rows},
                             {category} if rows else set())
            status, _, html = self.get({
                **query, "format": "presence-all-compare-table"})
            self.assertEqual(status, 200)
            self.assertIn(b"Original evidence transition filters", html)
            self.assertIn(b"Matching entities:", html)
            self.assertIn(b"presence-all-compare-csv", html)
            self.assertIn(b"transition=", html)
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_reporter_matrix_transition_classifier_distinguishes_reporters_and_revisions(self):
        """A changed original assertion is not the same as a changed reporter."""
        from copy import deepcopy
        from monde.source_pair_changes import filter_reporter_matrix_transitions
        report = lambda ids: {
            "count": len(ids), "assertion_ids": ids, "evidence_ids": ids,
            "coordinates": [[2.0, 48.0] for _ in ids]}
        before = {"status": "BOTH_REPORTED",
                  "source_a": report(["a"]), "source_b": report(["b"])}
        unchanged = {"entity": "no-change", "earlier": deepcopy(before),
                     "later": deepcopy(before)}
        amended = {"entity": "new-assertion", "earlier": deepcopy(before),
                   "later": deepcopy(before)}
        amended["later"]["source_b"] = report(["b2"])
        reporter = {"entity": "reporter-gone", "earlier": deepcopy(before),
                    "later": deepcopy(before)}
        reporter["later"]["source_b"] = report([])
        reporter["later"]["status"] = "ONLY_SOURCE_A"
        rows = [unchanged, amended, reporter]
        base = {"schema": "MONDE_ORIGINAL_POINT_REPORTER_MATRIX_V1",
                "entities": rows, "total_entities": len(rows),
                "per_period": {}}
        expected = {
            "unchanged": ("UNCHANGED", "no-change"),
            "evidence-changed": ("ORIGINAL_EVIDENCE_CHANGED", "new-assertion"),
            "reporters-changed": ("REPORTERS_CHANGED", "reporter-gone"),
        }
        for query, (category, entity) in expected.items():
            filtered = filter_reporter_matrix_transitions(base, query)
            self.assertEqual([r["entity"] for r in filtered["entities"]], [entity])
            self.assertEqual(filtered["entities"][0]["reporting_transition"], category)
            self.assertEqual(filtered["total_entities_unfiltered"], 3)
        self.assertEqual(base["entities"], rows)
        with self.assertRaises(ValueError):
            filter_reporter_matrix_transitions(base, "invented")

    def test_reporter_matrix_transition_rejects_unknown_and_unrelated_query(self):
        base = {**self.knowledge(), "compare_a": "survey-a",
                "compare_b": "survey-b"}
        for bad in (
                {**base, "format": "presence-all-compare-json",
                 "transition": "unknown"},
                {**base, "format": "presence-all-compare-json",
                 "transition": ""},
                {**base, "format": "presence-all-geojson",
                 "transition": "unchanged"},
                {**base, "format": "presence-all-csv",
                 "transition": "reporters-changed"},
                {**self.knowledge(), "format": "json",
                 "transition": "unchanged"},
                {**self.knowledge(), "format": "presence-all-compare-table",
                 "transition": "unchanged"},
        ):
            with self.subTest(bad=bad):
                status, _, body = self.get(bad)
                self.assertEqual(status, 400)
                self.assertEqual(json.loads(body), {"error": "invalid_query"})
        self.assertEqual(self.saved.read_bytes(), self.snapshot)


    def test_reporter_matrix_transition_map_reuses_exact_original_point_evidence(self):
        """Persisted loopback HTTP: matrix -> GeoJSON -> offline map, both axes."""
        for cutoffs in (
                self.knowledge(),
                {"directory": "1", "axis": "world", "from_at": EARLY,
                 "to_at": LATE, "known_at": KNOWN}):
            base = {**cutoffs, "compare_a": "survey-a",
                    "compare_b": "survey-b", "bbox": "-180,-90,180,90"}
            status, _, original_raw = self.get({
                **base, "format": "presence-all-geojson"})
            self.assertEqual(status, 200)
            original = json.loads(original_raw)["features"]
            for selection in (None, "reporters-changed",
                              "evidence-changed", "unchanged"):
                query = dict(base)
                if selection is not None:
                    query["transition"] = selection
                status, _, matrix_raw = self.get({
                    **query, "format": "presence-all-compare-json"})
                self.assertEqual(status, 200)
                matrix = json.loads(matrix_raw)
                categories = {row["entity"]: row["reporting_transition"]
                              for row in matrix["entities"]}
                expected = [feature for feature in original
                            if feature["properties"]["entity"] in categories]
                status, _, raw = self.get({
                    **query, "format": "presence-all-compare-geojson"})
                self.assertEqual(status, 200)
                actual = json.loads(raw)
                self.assertEqual([f["id"] for f in actual["features"]],
                                 [f["id"] for f in expected])
                for found, prior in zip(actual["features"], expected):
                    props = dict(found["properties"])
                    self.assertEqual(
                        props.pop("monde_reporting_transition"),
                        categories[props["entity"]])
                    gap = next(row["reporter_gap_trend"]
                               for row in matrix["entities"]
                               if row["entity"] == props["entity"])
                    self.assertEqual(props.pop("monde_reporter_gap_trend"), gap)
                    marked = props.pop("monde_nearest_original_pair_periods", [])
                    self.assertTrue(set(marked) <= {"earlier", "later"})
                    row = next(r for r in matrix["entities"]
                               if r["entity"] == props["entity"])
                    expected_periods = []
                    for period in ("earlier", "later"):
                        pair = row[period]["nearest_original_pair"]
                        if pair is None or not props[period + "_visible"]:
                            continue
                        side = ("source_a" if props["source_id"] ==
                                matrix["source_a"] else "source_b")
                        original_pair = pair[side]
                        if (original_pair["assertion_id"] ==
                                props["monde_original_assertion_id"]
                                and original_pair["evidence_id"] ==
                                props["evidence_id"]
                                and original_pair["coordinates"] ==
                                found["geometry"]["coordinates"]):
                            expected_periods.append(period)
                    self.assertEqual(marked, expected_periods)
                    self.assertEqual(props, prior["properties"])
                    self.assertEqual(found["geometry"], prior["geometry"])
                coverage = actual["monde_source_coverage"]
                self.assertEqual(coverage["original_report_count"], len(expected))
                self.assertEqual(coverage["distinct_entities"], len(categories))
                self.assertEqual(coverage["reporter_matrix"]["matching_entities"],
                                 matrix["total_entities"])
                status, _, html = self.get({
                    **query, "format": "presence-all-compare-map"})
                self.assertEqual(status, 200)
                self.assertIn(b"<!doctype html>", html.lower())
            self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_reporter_transition_map_strict_scope_and_empty_originals(self):
        base = {**self.knowledge(), "compare_a": "missing-a",
                "compare_b": "missing-b"}
        status, _, raw = self.get({
            **base, "transition": "reporters-changed",
            "format": "presence-all-compare-geojson"})
        self.assertEqual(status, 200)
        doc = json.loads(raw)
        self.assertEqual(doc["features"], [])
        self.assertEqual(doc["monde_source_coverage"]
                         ["reporter_matrix"]["matching_entities"], 0)
        for invalid in ({"compare_b": "missing-a"}, {"transition": "no-such"},
                        {"source_prefix": "missing"}, {"source_exact": "missing-a"},
                        {"entity": "site-1"}):
            for fmt in ("presence-all-compare-map",
                        "presence-all-compare-geojson"):
                status, _, raw = self.get({**base, **invalid, "format": fmt})
                self.assertEqual(status, 400)
                self.assertEqual(json.loads(raw), {"error": "invalid_query"})
        for fmt in ("presence-all-compare-map", "presence-all-compare-geojson"):
            self.assertEqual(self.get({**self.knowledge(), "format": fmt})[0], 400)
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_reporter_matrix_entity_focus_opens_two_original_sources_on_map(self):
        """Matrix row -> one-entity map, preserving both reporters and cutoffs."""
        base = {**self.knowledge(), "compare_a": "survey-a",
                "compare_b": "survey-b", "bbox": "-180,-90,180,90"}
        status, _, raw = self.get({**base, "format": "presence-all-compare-json"})
        self.assertEqual(status, 200)
        matrix = json.loads(raw)
        self.assertGreater(matrix["total_entities"], 0)
        entity = matrix["entities"][0]["entity"]
        status, _, html = self.get({**base, "format": "presence-all-compare-table"})
        self.assertEqual(status, 200)
        anchors = re.findall(r'<a href="([^"]+)">Compare both reporters on map</a>',
                             html.decode("utf-8"))
        self.assertEqual(len(anchors), matrix["total_entities"])
        link = next({k: values[0] for k, values in
                     parse_qs(urlsplit(unescape(a)).query).items()}
                    for a in anchors
                    if parse_qs(urlsplit(unescape(a)).query)["focus_entity"][0] == entity)
        self.assertEqual(link["format"], "presence-all-compare-map")
        self.assertEqual((link["compare_a"], link["compare_b"]),
                         ("survey-a", "survey-b"))
        self.assertEqual(link["bbox"], base["bbox"])
        for k in self.knowledge():
            self.assertEqual(link[k], self.knowledge()[k])
        status, _, map_html = self.get(link)
        self.assertEqual(status, 200)
        self.assertIn(b"<!doctype html>", map_html.lower())

        _, _, total_raw = self.get({
            **base, "format": "presence-all-compare-geojson"})
        total = json.loads(total_raw)
        _, _, focused_raw = self.get({
            **link, "format": "presence-all-compare-geojson"})
        focused = json.loads(focused_raw)
        expected = [f for f in total["features"]
                    if f["properties"]["entity"] == entity]
        self.assertEqual(focused["features"], expected)
        self.assertEqual(focused["monde_source_coverage"]
                         ["reporter_matrix"]["focus_entity"], entity)
        self.assertEqual(focused["monde_source_coverage"]
                         ["reporter_matrix"]["matching_entities"], 1)
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_reporter_matrix_focus_respects_transition_and_world_cutoffs(self):
        for cutoffs in (self.knowledge(),
                        {"directory": "1", "axis": "world",
                         "from_at": EARLY, "to_at": LATE, "known_at": KNOWN}):
            base = {**cutoffs, "compare_a": "survey-a",
                    "compare_b": "survey-b", "bbox": "-180,-90,180,90"}
            for transition in (None, "reporters-changed", "evidence-changed",
                               "unchanged"):
                query = {**base, **({"transition": transition} if transition else {})}
                _, _, raw = self.get({**query, "format": "presence-all-compare-json"})
                matrix = json.loads(raw)
                entity = (matrix["entities"][0]["entity"]
                          if matrix["entities"] else "nonexistent-report")
                _, _, raw = self.get({**query, "focus_entity": entity,
                                       "format": "presence-all-compare-geojson"})
                focus = json.loads(raw)
                selected = [r for r in matrix["entities"] if r["entity"] == entity]
                self.assertEqual(focus["monde_source_coverage"]
                                 ["reporter_matrix"]["matching_entities"], len(selected))
                self.assertEqual({f["properties"]["entity"] for f in focus["features"]},
                                 {entity} if selected else set())
                self.assertEqual(self.get({**query, "focus_entity": entity,
                                           "format": "presence-all-compare-map"})[0], 200)
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_reporter_matrix_focus_rejects_ambiguous_or_unsafe_scope(self):
        base = {**self.knowledge(), "compare_a": "survey-a",
                "compare_b": "survey-b"}
        for params in (
                {"focus_entity": ""},
                {"focus_entity": "site-1\nbad"},
                {"focus_entity": "site-1", "format": "presence-all-compare-json"},
                {"focus_entity": "site-1", "format": "presence-all-compare-csv"},
                {"focus_entity": "site-1", "compare_b": "survey-a"},
                {"focus_entity": "site-1", "source": "survey-a"},
                {"focus_entity": "site-1", "entity": "site-1"},
        ):
            candidate = {**base, "format": "presence-all-compare-geojson", **params}
            status, _, raw = self.get(candidate)
            self.assertEqual(status, 400, candidate)
            self.assertEqual(json.loads(raw), {"error": "invalid_query"})
        status, _, raw = self.get({**self.knowledge(), "focus_entity": "site-1",
                                   "format": "presence-all-compare-geojson"})
        self.assertEqual(status, 400)
        self.assertEqual(self.saved.read_bytes(), self.snapshot)


    def test_reporter_matrix_original_point_separation_matches_http_csv_and_html(self):
        """Quantify original source-to-source Point gaps; never infer consensus."""
        from monde.source_pair_changes import _distance
        for times in (self.knowledge(),
                      {"directory": "1", "axis": "world",
                       "from_at": EARLY, "to_at": LATE, "known_at": KNOWN}):
            params = {**times, "compare_a": "survey-a", "compare_b": "survey-b"}
            status, _, raw = self.get({**params, "format": "presence-all-compare-json"})
            self.assertEqual(status, 200)
            matrix = json.loads(raw)
            status, _, raw = self.get({**params, "format": "presence-all-compare-csv"})
            self.assertEqual(status, 200)
            csv_rows = {(r["entity"], r["period"]): r for r in
                        csv.DictReader(io.StringIO(raw.decode("utf-8")))}
            self.assertEqual(len(csv_rows), 2 * matrix["total_entities"])
            joint = 0
            for entity in matrix["entities"]:
                for period in ("earlier", "later"):
                    selected = entity[period]
                    a_points = selected["source_a"]["coordinates"]
                    b_points = selected["source_b"]["coordinates"]
                    measured = selected["separation_km"]
                    flat = csv_rows[(entity["entity"], period)]
                    if not a_points or not b_points:
                        self.assertIsNone(measured)
                        self.assertEqual(flat["nearest_reporter_separation_km"], "")
                        self.assertEqual(flat["farthest_reporter_separation_km"], "")
                    else:
                        joint += 1
                        gaps = [_distance(a, b) for a in a_points for b in b_points]
                        self.assertEqual(measured, {
                            "nearest_km": round(min(gaps), 3),
                            "farthest_km": round(max(gaps), 3)})
                        self.assertEqual(float(flat["nearest_reporter_separation_km"]),
                                         measured["nearest_km"])
                        self.assertEqual(float(flat["farthest_reporter_separation_km"]),
                                         measured["farthest_km"])
                before, after = (entity[period]["separation_km"]
                                 for period in ("earlier", "later"))
                expected = ({kind: round(after[kind] - before[kind], 3)
                             for kind in ("nearest_km", "farthest_km")}
                            if before is not None and after is not None else None)
                self.assertEqual(entity["separation_change_km"], expected)
            self.assertGreater(joint, 0)
            status, _, html = self.get({**params, "format": "presence-all-compare-table"})
            self.assertEqual(status, 200)
            self.assertIn(b"Reporter separation (min-max km)", html)
        self.assertEqual(self.saved.read_bytes(), self.snapshot)


    def test_original_reporter_gap_trend_filter_json_csv_map_and_html(self):
        """One actual saved WorldMini drives the same spatial/time evidence in all outputs."""
        for times in (self.knowledge(),
                      {"directory": "1", "axis": "world", "from_at": EARLY,
                       "to_at": LATE, "known_at": KNOWN}):
            base = {**times, "compare_a": "survey-a", "compare_b": "survey-b",
                    "bbox": "-180,-90,180,90"}
            status, _, raw = self.get({**base, "format": "presence-all-compare-json"})
            self.assertEqual(status, 200)
            complete = json.loads(raw)
            classifications = {"widening": "WIDENING", "narrowing": "NARROWING",
                               "steady": "STEADY", "unknown": "UNKNOWN"}
            self.assertEqual(sum(complete["gap_trend_counts"].values()),
                             complete["total_entities"])
            for item in complete["entities"]:
                delta = item["separation_change_km"]
                value = None if delta is None else delta["nearest_km"]
                expected = ("UNKNOWN" if value is None else "WIDENING" if value > 0
                            else "NARROWING" if value < 0 else "STEADY")
                self.assertEqual(item["reporter_gap_trend"], expected)
            for choice, label in classifications.items():
                query = {**base, "gap_trend": choice}
                _, _, raw = self.get({**query, "format": "presence-all-compare-json"})
                filtered = json.loads(raw)
                self.assertEqual(filtered["gap_trend_filter"], choice)
                self.assertEqual(filtered["gap_trend_counts"], complete["gap_trend_counts"])
                self.assertEqual([r["entity"] for r in filtered["entities"]],
                                 [r["entity"] for r in complete["entities"]
                                  if r["reporter_gap_trend"] == label])
                _, _, csv_body = self.get({**query, "format": "presence-all-compare-csv"})
                rows = list(csv.DictReader(io.StringIO(csv_body.decode("utf-8"))))
                self.assertEqual(len(rows), 2 * filtered["total_entities"])
                self.assertTrue(all(row["reporter_gap_trend"] == label for row in rows))
                _, _, raw = self.get({**query, "format": "presence-all-compare-geojson"})
                geojson = json.loads(raw)
                self.assertEqual(
                    geojson["monde_source_coverage"]["reporter_matrix"]["gap_trend_filter"],
                    choice)
                self.assertTrue(all(
                    x["properties"]["monde_reporter_gap_trend"] == label
                    for x in geojson["features"]))
                self.assertEqual(self.get({**query,
                    "format": "presence-all-compare-map"})[0], 200)
            _, _, html = self.get({**base, "format": "presence-all-compare-table"})
            self.assertIn(b"Original source separation trends", html)
            self.assertIn(b"gap_trend=widening", html)
            self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_original_reporter_gap_trend_rejects_unsafe_and_unrelated_queries(self):
        base = {**self.knowledge(), "compare_a": "survey-a", "compare_b": "survey-b"}
        for query in ({"gap_trend": "wrong"}, {"gap_trend": ""},
                      {"gap_trend": "WIDENING"}, {"gap_trend": "widening%0A"}):
            status, _, raw = self.get({**base, "format": "presence-all-compare-json",
                                       **query})
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(raw), {"error": "invalid_query"})
        for fmt in ("presence-all-geojson", "presence-all-map", "json"):
            status, _, raw = self.get({**base, "format": fmt,
                                       "gap_trend": "unknown"})
            self.assertEqual(status, 400)
        self.assertEqual(self.saved.read_bytes(), self.snapshot)


    def test_original_reporter_gap_priority_http_csv_map_and_snapshot(self):
        base = {**self.knowledge(), "compare_a": "survey-a",
                "compare_b": "survey-b"}
        status, _, raw = self.get({**base, "format": "presence-all-compare-json"})
        self.assertEqual(status, 200)
        original = json.loads(raw)
        query = {**base, "min_gap_km": "0", "gap_order": "largest"}
        status, _, raw = self.get({**query, "format": "presence-all-compare-json"})
        self.assertEqual(status, 200)
        picked = json.loads(raw)
        def max_gap(row):
            values = [row[period]["separation_km"]["nearest_km"]
                      for period in ("earlier", "later")
                      if row[period]["separation_km"] is not None]
            return max(values) if values else None
        expected = [r for r in original["entities"] if max_gap(r) is not None]
        expected.sort(key=lambda r: (-max_gap(r), r["entity"]))
        self.assertEqual([r["entity"] for r in picked["entities"]],
                         [r["entity"] for r in expected])
        self.assertEqual(picked["gap_selection"]["minimum_nearest_km"], 0.0)
        self.assertEqual(picked["gap_selection"]["order"], "largest")
        self.assertEqual(picked["total_original_reports"],
                         original["total_original_reports"])
        self.assertEqual(picked["total_entities"], len(expected))
        status, _, raw = self.get({**query, "format": "presence-all-compare-csv"})
        self.assertEqual(status, 200)
        rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
        self.assertEqual([r["entity"] for r in rows[::2]],
                         [r["entity"] for r in expected])
        status, _, html = self.get({**query, "format": "presence-all-compare-table"})
        self.assertEqual(status, 200)
        self.assertIn(b"Prioritize original reporter Point separation", html)
        self.assertIn(b'name="min_gap_km"', html)
        self.assertIn(b'name="gap_order"', html)
        status, _, raw = self.get({**query, "format": "presence-all-compare-geojson"})
        self.assertEqual(status, 200)
        self.assertEqual({f["properties"]["entity"] for f in json.loads(raw)["features"]},
                         {row["entity"] for row in expected})
        self.assertEqual(self.get({**query, "format": "presence-all-compare-map"})[0], 200)
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_original_reporter_gap_priority_rejects_invalid_scope_both_axes(self):
        periods = (self.knowledge(),
                   {"directory": "1", "axis": "world",
                    "from_at": EARLY, "to_at": LATE, "known_at": KNOWN})
        for time in periods:
            q = {**time, "compare_a": "survey-a", "compare_b": "survey-b"}
            for fmt in ("presence-all-compare-json", "presence-all-compare-geojson"):
                status, _, raw = self.get({**q, "format": fmt, "min_gap_km": "20015"})
                self.assertEqual(status, 200)
                output = json.loads(raw)
                self.assertEqual(output["features"] if fmt.endswith("geojson")
                                 else output["entities"], [])
            for invalid in ("", "-1", "nan", "inf", "1e6", "20.1234", "20016", "01"):
                status, _, raw = self.get({**q, "format": "presence-all-compare-json",
                                           "min_gap_km": invalid})
                self.assertEqual(status, 400, invalid)
                self.assertEqual(json.loads(raw), {"error": "invalid_query"})
            for changes in ({"gap_order": "random"},
                            {"format": "presence-all-map", "min_gap_km": "2"},
                            {"format": "presence-all-geojson", "gap_order": "largest"}):
                status, _, raw = self.get({**q, "format": "presence-all-compare-json",
                                           **changes})
                self.assertEqual(status, 400, changes)
                self.assertEqual(json.loads(raw), {"error": "invalid_query"})
        self.assertEqual(self.saved.read_bytes(), self.snapshot)


    def test_persistent_reporter_gap_real_http_parity(self):
        """Verify original source Points at both cutoffs, never inferred position."""
        for cutoff in (self.knowledge(),
                       {"directory": "1", "axis": "world",
                        "from_at": EARLY, "to_at": LATE, "known_at": KNOWN}):
            base = {**cutoff, "compare_a": "survey-a", "compare_b": "survey-b"}
            status, _, raw = self.get({**base, "format": "presence-all-compare-json"})
            self.assertEqual(status, 200)
            original = json.loads(raw)
            def gap(row):
                values = [row[p]["separation_km"]["nearest_km"]
                          for p in ("earlier", "later")
                          if row[p]["separation_km"] is not None]
                return min(values) if len(values) == 2 else None
            expected = [r for r in original["entities"] if gap(r) is not None]
            expected.sort(key=lambda r: (-gap(r), r["entity"]))
            query = {**base, "min_gap_km": "0", "gap_window": "both",
                     "gap_order": "largest"}
            status, _, raw = self.get({**query, "format": "presence-all-compare-json"})
            self.assertEqual(status, 200)
            matrix = json.loads(raw)
            self.assertEqual([r["entity"] for r in matrix["entities"]],
                             [r["entity"] for r in expected])
            self.assertEqual(matrix["gap_selection"]["window"], "both")
            self.assertIn("both cutoffs", matrix["gap_selection"]["interpretation"])
            _, _, raw = self.get({**query, "format": "presence-all-compare-csv"})
            csv_rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
            self.assertEqual([r["entity"] for r in csv_rows[::2]],
                             [r["entity"] for r in expected])
            _, _, raw = self.get({**query, "format": "presence-all-compare-geojson"})
            geojson = json.loads(raw)
            self.assertEqual({f["properties"]["entity"] for f in geojson["features"]},
                             {r["entity"] for r in expected})
            self.assertEqual(geojson["monde_source_coverage"]["reporter_matrix"]
                             ["gap_selection"]["window"], "both")
            status, _, html = self.get({**query, "format": "presence-all-compare-table"})
            self.assertEqual(status, 200)
            self.assertIn(b'name="gap_window"', html)
            self.assertIn(b'Both cutoffs (persistent)', html)
            self.assertIn(b'value="both" selected', html)
            self.assertEqual(self.get({**query, "format": "presence-all-compare-map"})[0], 200)
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_persistent_gap_input_guard_and_previous_either_semantics(self):
        base = {**self.knowledge(), "compare_a": "survey-a",
                "compare_b": "survey-b", "format": "presence-all-compare-json"}
        _, _, raw = self.get({**base, "min_gap_km": "0"})
        previous = json.loads(raw)
        _, _, raw = self.get({**base, "min_gap_km": "0", "gap_window": "either"})
        self.assertEqual(previous["entities"], json.loads(raw)["entities"])
        for invalid in ({"gap_window": "both"},
                        {"gap_window": "", "min_gap_km": "0"},
                        {"gap_window": "BOTH", "min_gap_km": "0"},
                        {"gap_window": "before", "min_gap_km": "0"},
                        {"gap_window": "both", "min_gap_km": "nan"},
                        {"gap_window": "both", "min_gap_km": "0",
                         "format": "presence-all-map"}):
            status, _, raw = self.get({**base, **invalid})
            self.assertEqual(status, 400, invalid)
            self.assertEqual(json.loads(raw), {"error": "invalid_query"})
        self.assertEqual(self.saved.read_bytes(), self.snapshot)


    def test_nearest_original_report_pair_is_provenance_traceable_across_outputs(self):
        """Inspect which exact original assertions determine the numeric gap."""
        from monde.source_pair_changes import _distance
        for times in (self.knowledge(),
                      {"directory": "1", "axis": "world",
                       "from_at": EARLY, "to_at": LATE, "known_at": KNOWN}):
            base = {**times, "compare_a": "survey-a", "compare_b": "survey-b",
                    "bbox": "-180,-90,180,90"}
            status, _, raw = self.get({**base, "format": "presence-all-compare-json"})
            self.assertEqual(status, 200)
            matrix = json.loads(raw)
            _, _, csv_raw = self.get({**base, "format": "presence-all-compare-csv"})
            csv_rows = {(row["entity"], row["period"]): row for row in
                        csv.DictReader(io.StringIO(csv_raw.decode("utf-8")))}
            _, _, geo_raw = self.get({**base, "format": "presence-all-compare-geojson"})
            features = json.loads(geo_raw)["features"]
            witnesses = 0
            for entity in matrix["entities"]:
                for period in ("earlier", "later"):
                    current = entity[period]
                    pair = current["nearest_original_pair"]
                    flat = csv_rows[(entity["entity"], period)]
                    for side in ("source_a", "source_b"):
                        column = "nearest_" + side + "_original_json"
                        self.assertEqual(json.loads(flat[column]) if flat[column] else None,
                                         pair[side] if pair else None)
                    if pair is None:
                        self.assertIsNone(current["separation_km"])
                        continue
                    witnesses += 1
                    gap = _distance(pair["source_a"]["coordinates"],
                                    pair["source_b"]["coordinates"])
                    self.assertEqual(round(gap, 3), pair["distance_km"])
                    self.assertEqual(pair["distance_km"],
                                     current["separation_km"]["nearest_km"])
                    for side, source in (("source_a", "survey-a"),
                                         ("source_b", "survey-b")):
                        original = pair[side]
                        matching = [f for f in features
                                    if f["properties"]["entity"] == entity["entity"]
                                    and f["properties"]["source_id"] == source
                                    and f["properties"]["monde_original_assertion_id"] ==
                                        original["assertion_id"]
                                    and f["properties"]["evidence_id"] ==
                                        original["evidence_id"]
                                    and f["geometry"]["coordinates"] ==
                                        original["coordinates"]]
                        self.assertTrue(matching)
                        self.assertTrue(any(period in f["properties"].get(
                            "monde_nearest_original_pair_periods", [])
                            for f in matching))
            self.assertGreater(witnesses, 0)
            status, _, html = self.get({**base, "format": "presence-all-compare-table"})
            self.assertEqual(status, 200)
            self.assertIn(b"Nearest original report pair", html)
            self.assertEqual(self.get({**base, "format": "presence-all-compare-map"})[0],
                             200)
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_nearest_original_pair_ties_are_deterministic_and_unknown_is_null(self):
        from monde.source_pair_changes import _measure_with_original_pair
        def feature(assertion, evidence, coordinate):
            return {"geometry": {"coordinates": coordinate},
                    "properties": {"monde_original_assertion_id": assertion,
                                   "evidence_id": evidence}}
        left = [feature("a2", "e2", [1, 0]), feature("a1", "e1", [1, 0])]
        right = [feature("b1", "f1", [1, 0])]
        first = _measure_with_original_pair(left, right)
        self.assertEqual(first[0], {"nearest_km": 0.0, "farthest_km": 0.0})
        self.assertEqual(first[1]["source_a"]["assertion_id"], "a1")
        self.assertEqual(first, _measure_with_original_pair(list(reversed(left)), right))
        self.assertEqual(_measure_with_original_pair([], right), (None, None))
        self.assertEqual(_measure_with_original_pair(left, []), (None, None))


    def test_reporter_gap_change_priority_real_http_and_original_evidence(self):
        """Rank the magnitude of the CHANGE in reporters, never their accuracy."""
        for cutoffs in (self.knowledge(),
                        {"directory": "1", "axis": "world",
                         "from_at": EARLY, "to_at": LATE, "known_at": KNOWN}):
            base = {**cutoffs, "compare_a": "survey-a", "compare_b": "survey-b",
                    "bbox": "-180,-90,180,90"}
            status, _, raw = self.get({**base, "format": "presence-all-compare-json"})
            self.assertEqual(status, 200)
            original = json.loads(raw)
            def magnitude(row):
                delta = row["separation_change_km"]
                return None if delta is None else abs(delta["nearest_km"])
            expected = sorted(original["entities"], key=lambda r: (
                magnitude(r) is None, -(magnitude(r) or 0), r["entity"]))
            query = {**base, "gap_order": "largest-change"}
            status, _, raw = self.get({**query,
                                       "format": "presence-all-compare-json"})
            self.assertEqual(status, 200)
            matrix = json.loads(raw)
            self.assertEqual([r["entity"] for r in matrix["entities"]],
                             [r["entity"] for r in expected])
            self.assertEqual(matrix["gap_selection"]["order"], "largest-change")
            self.assertEqual(matrix["total_entities"], original["total_entities"])
            self.assertEqual(matrix["total_original_reports"],
                             original["total_original_reports"])
            for actual, before in zip(matrix["entities"], expected):
                self.assertEqual(actual, before)

            status, _, csv_body = self.get({**query,
                    "format": "presence-all-compare-csv"})
            self.assertEqual(status, 200)
            rows = list(csv.DictReader(io.StringIO(csv_body.decode("utf-8"))))
            self.assertEqual([r["entity"] for r in rows[::2]],
                             [r["entity"] for r in expected])
            status, _, html = self.get({**query,
                    "format": "presence-all-compare-table"})
            self.assertEqual(status, 200)
            self.assertIn(b'value="largest-change" selected', html)
            self.assertIn(b'Largest change in original-report gap first', html)
            status, _, geo_raw = self.get({**query,
                    "format": "presence-all-compare-geojson"})
            self.assertEqual(status, 200)
            geojson = json.loads(geo_raw)
            self.assertEqual(geojson["monde_source_coverage"]
                             ["reporter_matrix"]["gap_selection"]["order"],
                             "largest-change")
            self.assertEqual({f["properties"]["entity"]
                              for f in geojson["features"]},
                             {row["entity"] for row in expected})
            self.assertEqual(self.get({**query,
                    "format": "presence-all-compare-map"})[0], 200)
            self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_reporter_gap_change_priority_ignores_unpaired_unknown_not_zero(self):
        base = {**self.knowledge(), "compare_a": "survey-a",
                "compare_b": "survey-b"}
        _, _, raw = self.get({**base, "format": "presence-all-compare-json"})
        original = json.loads(raw)
        ranked = json.loads(self.get({**base, "gap_order": "largest-change",
                         "format": "presence-all-compare-json"})[2])
        known = [r for r in ranked["entities"]
                 if r["separation_change_km"] is not None]
        missing = [r for r in ranked["entities"]
                   if r["separation_change_km"] is None]
        self.assertEqual(ranked["entities"], known + missing)
        self.assertEqual(len(ranked["entities"]), len(original["entities"]))
        self.assertEqual([r["entity"] for r in known],
                         [r["entity"] for r in sorted(known, key=lambda r: (
                            -abs(r["separation_change_km"]["nearest_km"]),
                            r["entity"]))])
        for invalid in ("largest-change-now", "LARGEST-CHANGE", "", "random"):
            status, _, raw = self.get({**base, "gap_order": invalid,
                                 "format": "presence-all-compare-json"})
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(raw), {"error": "invalid_query"})
        for unrelated in ("presence-all-map", "presence-all-geojson", "json"):
            status, _, raw = self.get({**base, "gap_order": "largest-change",
                                      "format": unrelated})
            self.assertEqual(status, 400)
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_gap_change_priority_preserves_existing_persistent_threshold(self):
        base = {**self.knowledge(), "compare_a": "survey-a",
                "compare_b": "survey-b", "min_gap_km": "0",
                "gap_window": "both"}
        original = json.loads(self.get({**base,
            "format": "presence-all-compare-json"})[2])
        change = json.loads(self.get({**base, "gap_order": "largest-change",
            "format": "presence-all-compare-json"})[2])
        self.assertEqual({r["entity"] for r in original["entities"]},
                         {r["entity"] for r in change["entities"]})
        self.assertEqual(change["gap_selection"]["window"], "both")
        self.assertTrue(all(r["separation_change_km"] is not None
                            for r in change["entities"]))
        self.assertEqual(self.saved.read_bytes(), self.snapshot)


    def test_original_reporter_minimum_change_filter_http_across_formats(self):
        """Only comparable original observations pass a magnitude threshold."""
        for base in (self.knowledge(),
                     {"directory": "1", "axis": "world",
                      "from_at": EARLY, "to_at": LATE, "known_at": KNOWN}):
            query = {**base, "compare_a": "survey-a",
                     "compare_b": "survey-b"}
            fmt = "presence-all-compare-json"
            status, _, raw = self.get({**query, "format": fmt})
            self.assertEqual(status, 200)
            original = json.loads(raw)
            comparable = [row for row in original["entities"]
                          if row["separation_change_km"] is not None]
            # 0 is an explicit filter: unknown pairs must not become zero gaps.
            filtered_query = {**query, "min_gap_change_km": "0",
                              "gap_order": "largest-change"}
            status, _, raw = self.get({**filtered_query, "format": fmt})
            self.assertEqual(status, 200)
            result = json.loads(raw)
            self.assertEqual({r["entity"] for r in result["entities"]},
                             {r["entity"] for r in comparable})
            self.assertEqual(result["gap_selection"]["minimum_abs_change_km"], 0)
            self.assertEqual(result["total_entities"], len(comparable))
            if comparable:
                magnitudes = [abs(r["separation_change_km"]["nearest_km"])
                              for r in comparable]
                # A positive threshold must exclude all smaller original gaps.
                threshold = "1.000"
                status, _, raw = self.get({
                    **filtered_query, "min_gap_change_km": threshold,
                    "format": fmt})
                self.assertEqual(status, 200)
                selected = json.loads(raw)
                expected = {r["entity"] for r in comparable
                            if abs(r["separation_change_km"]["nearest_km"]) >= 1}
                self.assertEqual({r["entity"] for r in selected["entities"]},
                                 expected)
                self.assertTrue(all(v >= 0 for v in magnitudes))
            status, _, csv_body = self.get({
                **filtered_query, "format": "presence-all-compare-csv"})
            self.assertEqual(status, 200)
            rows = list(csv.DictReader(io.StringIO(csv_body.decode("utf-8"))))
            self.assertEqual({r["entity"] for r in rows}, 
                             {r["entity"] for r in comparable})
            status, _, geo_raw = self.get({
                **filtered_query, "format": "presence-all-compare-geojson"})
            self.assertEqual(status, 200)
            geo = json.loads(geo_raw)
            self.assertEqual({f["properties"]["entity"] for f in geo["features"]},
                             {r["entity"] for r in comparable})
            self.assertEqual(geo["monde_source_coverage"]
                             ["reporter_matrix"]["gap_selection"]
                             ["minimum_abs_change_km"], 0)
            status, _, html = self.get({
                **filtered_query, "format": "presence-all-compare-table"})
            self.assertEqual(status, 200)
            self.assertIn(b'name="min_gap_change_km"', html)
            self.assertIn(b'Minimum absolute change between cutoffs', html)
            self.assertEqual(self.get({
                **filtered_query, "format": "presence-all-compare-map"})[0], 200)
            # Browser empty field preserves the original unfiltered result.
            _, _, empty_raw = self.get({**query, "min_gap_change_km": "",
                                         "format": fmt})
            self.assertEqual(json.loads(empty_raw), original)
            self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_original_reporter_minimum_change_filter_rejects_bad_scope(self):
        query = {**self.knowledge(), "compare_a": "survey-a",
                 "compare_b": "survey-b"}
        for invalid in ("-1", "NaN", "inf", "1e2", "1.0001", "20016",
                        " 1", "01", "1,0", "false"):
            status, _, body = self.get({
                **query, "format": "presence-all-compare-json",
                "min_gap_change_km": invalid})
            self.assertEqual(status, 400, invalid)
            self.assertEqual(json.loads(body), {"error": "invalid_query"})
        for unrelated in ("presence-all-map", "presence-all-geojson", "json"):
            status, _, body = self.get({
                **query, "format": unrelated, "min_gap_change_km": "1"})
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(body), {"error": "invalid_query"})
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_original_reporter_minimum_change_combines_existing_filters(self):
        base = {**self.knowledge(), "compare_a": "survey-a",
                "compare_b": "survey-b", "min_gap_km": "0",
                "gap_window": "both", "gap_order": "largest-change"}
        _, _, raw = self.get({**base, "format": "presence-all-compare-json"})
        prior = json.loads(raw)
        status, _, raw = self.get({**base, "min_gap_change_km": "0",
                                  "format": "presence-all-compare-json"})
        self.assertEqual(status, 200)
        current = json.loads(raw)
        self.assertEqual(prior["entities"], current["entities"])
        self.assertEqual(current["gap_selection"]["window"], "both")
        self.assertEqual(current["gap_selection"]["minimum_abs_change_km"], 0)
        self.assertEqual(self.saved.read_bytes(), self.snapshot)


    def test_original_reporter_crossing_threshold_both_axes_and_exports(self):
        """Threshold crossings derive only from original comparable source Points."""
        for base in (self.knowledge(),
                     {"directory": "1", "axis": "world",
                      "from_at": EARLY, "to_at": LATE, "known_at": KNOWN}):
            query = {**base, "compare_a": "survey-a", "compare_b": "survey-b"}
            unfiltered = json.loads(self.get({
                **query, "format": "presence-all-compare-json"})[2])
            comparable = [r for r in unfiltered["entities"]
                          if r["earlier"]["separation_km"] is not None
                          and r["later"]["separation_km"] is not None]
            thresholds = ["0", "1", "20015"] + [
                str(round(r["earlier"]["separation_km"]["nearest_km"], 3))
                for r in comparable]
            for threshold in thresholds:
                number = float(threshold)
                options = {**query, "gap_crossing_km": threshold,
                           "gap_order": "largest-change"}
                status, _, payload = self.get({
                    **options, "format": "presence-all-compare-json"})
                self.assertEqual(status, 200)
                filtered = json.loads(payload)
                expected = {}
                for r in comparable:
                    before = r["earlier"]["separation_km"]["nearest_km"]
                    after = r["later"]["separation_km"]["nearest_km"]
                    if before <= number < after:
                        expected[r["entity"]] = "CROSSED_ABOVE"
                    elif after <= number < before:
                        expected[r["entity"]] = "CROSSED_BELOW"
                self.assertEqual({
                    r["entity"]: r["reporter_gap_crossing"]
                    for r in filtered["entities"]}, expected)
                self.assertEqual(filtered["gap_selection"]["crossing_threshold_km"],
                                 number)
                csv_output = self.get({
                    **options, "format": "presence-all-compare-csv"})[2]
                rows = list(csv.DictReader(io.StringIO(csv_output.decode("utf-8"))))
                self.assertEqual({r["entity"] for r in rows}, set(expected))
                status, _, raw = self.get({
                    **options, "format": "presence-all-compare-geojson"})
                self.assertEqual(status, 200)
                geo = json.loads(raw)
                self.assertEqual({f["properties"]["entity"] for f in geo["features"]},
                                 set(expected))
                for f in geo["features"]:
                    self.assertEqual(f["properties"]["monde_reporter_gap_crossing"],
                                     expected[f["properties"]["entity"]])
                status, _, html = self.get({
                    **options, "format": "presence-all-compare-table"})
                self.assertEqual(status, 200)
                self.assertIn(b'name="gap_crossing_km"', html)
                self.assertEqual(self.get({
                    **options, "format": "presence-all-compare-map"})[0], 200)
            _, _, raw = self.get({**query, "gap_crossing_km": "",
                                  "format": "presence-all-compare-json"})
            self.assertEqual(json.loads(raw), unfiltered)
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

    def test_reporter_crossing_rejects_unsafe_or_unrelated_queries(self):
        query = {**self.knowledge(), "compare_a": "survey-a",
                 "compare_b": "survey-b"}
        for invalid in ("-1", "NaN", "inf", "1e2", "1.0001", "20016",
                        " 1", "01", "1,0", "false", "+0"):
            status, _, payload = self.get({
                **query, "format": "presence-all-compare-json",
                "gap_crossing_km": invalid})
            self.assertEqual(status, 400, invalid)
            self.assertEqual(json.loads(payload), {"error": "invalid_query"})
        for fmt in ("presence-all-map", "presence-all-geojson", "json"):
            status, _, payload = self.get({
                **query, "format": fmt, "gap_crossing_km": "1"})
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(payload), {"error": "invalid_query"})
        self.assertEqual(self.saved.read_bytes(), self.snapshot)

if __name__ == "__main__":
    unittest.main()
