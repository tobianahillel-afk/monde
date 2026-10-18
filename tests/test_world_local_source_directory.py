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


if __name__ == "__main__":
    unittest.main()
