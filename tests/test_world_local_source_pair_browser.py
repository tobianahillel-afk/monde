"""Real HTTP source-pair comparisons using the original WorldMini functions."""
import csv
import http.client
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from monde.local_api import create_server
from monde.world import WorldMini
from monde.source_pair_changes import (
    compare_source_pair, compare_source_pair_world_time, comparison_geojson,
    filter_source_pair_direction, comparison_html, comparison_csv,
    top_nearest_source_pair_changes)
from tests.test_world_source_pair_changes import fixture_world, AT, BEFORE, AFTER
from tests.test_world_source_pair_world_changes import sample, EARLY, LATE, KNOWN


class LocalSourcePairBrowserTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "world.json"
        self.world = fixture_world()
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

    def fetch(self, args=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        target = "/source-pair" + ("?" + urlencode(args) if args is not None else "")
        conn.request("GET", target,
                     headers={"Host": "127.0.0.1:" + str(self.server.server_port)})
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return result

    def knowledge(self):
        return {"axis": "knowledge", "source_a": "survey-a", "source_b": "survey-b",
                "at": AT, "from_known_at": BEFORE, "to_known_at": AFTER}

    def test_browser_forms_use_real_sources_and_no_network_or_writes(self):
        status, headers, page = self.fetch()
        self.assertEqual(status, 200)
        self.assertIn(b'name="source_a"', page)
        self.assertIn(b'name="source_b"', page)
        self.assertIn(b'name="from_known_at"', page)
        self.assertIn(b'name="from_at"', page)
        self.assertIn(b'value="survey-a"', page)
        self.assertIn(b'value="survey-b"', page)
        self.assertNotIn(b"<script", page)
        self.assertIn("connect-src 'none'", headers["Content-Security-Policy"])
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_knowledge_json_and_geojson_match_existing_engine(self):
        expected = compare_source_pair(self.world, "survey-a", "survey-b",
                                       AT, BEFORE, AFTER)
        for fmt, obj in (("json", expected), ("geojson", comparison_geojson(expected))):
            with self.subTest(fmt=fmt):
                code, headers, raw = self.fetch({**self.knowledge(), "format": fmt})
                self.assertEqual(code, 200)
                self.assertEqual(headers["Cache-Control"], "no-store")
                self.assertEqual(json.loads(raw), obj)
        self.assertEqual(expected["entities"][0]["earlier_to_later_change_km"],
                         json.loads(self.fetch({**self.knowledge(), "format": "json"})[2])
                         ["entities"][0]["earlier_to_later_change_km"])

    def test_html_uses_existing_offline_source_comparison_map(self):
        code, headers, raw = self.fetch(self.knowledge())
        self.assertEqual(code, 200)
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertIn("connect-src 'none'", headers["Content-Security-Policy"])
        expected = comparison_html(compare_source_pair(
            self.world, "survey-a", "survey-b", AT, BEFORE, AFTER))
        self.assertEqual(raw.decode("utf-8"), expected)
        self.assertIn(b"survey-a", raw)
        self.assertIn(b"survey-b", raw)

    def test_direction_filter_preserves_original_metadata(self):
        expected = filter_source_pair_direction(compare_source_pair(
            self.world, "survey-a", "survey-b", AT, BEFORE, AFTER), "diverging")
        code, _, raw = self.fetch({**self.knowledge(), "format": "json",
                                   "direction": "diverging"})
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(raw), expected)

    def test_world_axis_uses_existing_world_validity_comparison(self):
        # Start a second real server for a different persisted world snapshot.
        state = Path(self.temp.name) / "world-times.json"
        world = sample()
        world.save(state)
        original = state.read_bytes()
        server = create_server(state)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            query = {"axis": "world", "source_a": "survey-a", "source_b": "survey-b",
                     "from_at": EARLY, "to_at": LATE, "known_at": KNOWN,
                     "format": "geojson"}
            conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            conn.request("GET", "/source-pair?" + urlencode(query),
                         headers={"Host": "127.0.0.1:" + str(server.server_port)})
            response = conn.getresponse()
            code, doc = response.status, json.loads(response.read())
            conn.close()
            self.assertEqual(code, 200)
            self.assertEqual(doc, comparison_geojson(compare_source_pair_world_time(
                world, "survey-a", "survey-b", EARLY, LATE, KNOWN)))
            self.assertEqual(doc["monde_comparison"]["comparison_axis"], "world")
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
            self.assertEqual(state.read_bytes(), original)

    def test_invalid_source_times_or_parameters_rejected(self):
        query = self.knowledge()
        for invalid in (
            {**query, "source_a": "survey-b"},
            {**query, "source_a": "../survey-a"},
            {**query, "axis": "future"},
            {**query, "unexpected": "yes"},
            {**query, "format": "xml"},
            {**query, "direction": "moving"},
            {**query, "to_known_at": BEFORE},
            {**query, "from_at": EARLY},
        ):
            with self.subTest(invalid=invalid):
                status, _, raw = self.fetch(invalid)
                self.assertEqual(status, 400)
                self.assertEqual(json.loads(raw), {"error": "invalid_query"})


    def test_csv_export_equals_canonical_engine_and_keeps_original_assertions(self):
        original = compare_source_pair(self.world, "survey-a", "survey-b",
                                       AT, BEFORE, AFTER)
        status, headers, body = self.fetch({**self.knowledge(), "format": "csv"})
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "text/csv; charset=utf-8")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Content-Disposition"],
                         'attachment; filename="original-source-pair-changes.csv"')
        self.assertEqual(body.decode("utf-8"), comparison_csv(original))
        rows = list(csv.DictReader(io.StringIO(body.decode("utf-8"))))
        self.assertEqual(len(rows), 2 * len(original["entities"]))
        self.assertTrue(all(row["source_a_assertion_ids"] is not None
                            and row["source_b_evidence_ids"] is not None for row in rows))

    def test_top_nearest_changes_applies_before_each_output_projection(self):
        original = compare_source_pair(self.world, "survey-a", "survey-b",
                                       AT, BEFORE, AFTER)
        ranked = top_nearest_source_pair_changes(original, 1)
        for fmt, expected in (
            ("json", ranked),
            ("geojson", comparison_geojson(ranked)),
        ):
            with self.subTest(fmt=fmt):
                code, _, body = self.fetch({**self.knowledge(), "format": fmt, "top": "1"})
                self.assertEqual(code, 200)
                self.assertEqual(json.loads(body), expected)
        code, _, body = self.fetch({**self.knowledge(), "format": "csv", "top": "1"})
        self.assertEqual(code, 200)
        self.assertEqual(body.decode(), comparison_csv(ranked))

    def test_combined_direction_then_ranking_matches_canonical_functions(self):
        original = compare_source_pair(self.world, "survey-a", "survey-b",
                                       AT, BEFORE, AFTER)
        for direction in ("converging", "diverging", "unchanged", "incomparable"):
            expected = top_nearest_source_pair_changes(
                filter_source_pair_direction(original, direction), 1)
            code, _, body = self.fetch({
                **self.knowledge(), "format": "json",
                "direction": direction, "top": "1"})
            self.assertEqual(code, 200)
            self.assertEqual(json.loads(body), expected)

    def test_native_forms_submit_all_controls_without_javascript(self):
        code, _, html = self.fetch()
        self.assertEqual(code, 200)
        self.assertIn(b'<select name="format">', html)
        self.assertIn(b'<select name="direction">', html)
        self.assertIn(b'name="top" min="1" max="1000"', html)
        self.assertIn(b'<option value="csv">', html)
        self.assertNotIn(b"<script", html)
        # Both native forms submit 9 parameters, including empty optionals.
        native = {**self.knowledge(), "format": "csv", "direction": "", "top": ""}
        status, _, raw = self.fetch(native)
        self.assertEqual(status, 200)
        self.assertEqual(raw.decode(), comparison_csv(compare_source_pair(
            self.world, "survey-a", "survey-b", AT, BEFORE, AFTER)))

    def test_invalid_ranking_and_extra_parameters_fail_without_state_writes(self):
        for value in ("0", "-1", "1001", "1.0", "nan", "2e2", "1 2", "01", "x"):
            with self.subTest(top=value):
                code, _, raw = self.fetch({**self.knowledge(), "top": value,
                                           "format": "csv"})
                self.assertEqual(code, 400)
                self.assertEqual(json.loads(raw), {"error": "invalid_query"})
        code, _, raw = self.fetch({**self.knowledge(), "format": "csv", "top": "1",
                                  "direction": "diverging", "extra": "1"})
        self.assertEqual(code, 400)


    def test_exact_entity_filter_retains_original_provenance_in_all_formats(self):
        original = compare_source_pair(self.world, "survey-a", "survey-b",
                                       AT, BEFORE, AFTER)
        focused = {**original, "entities": [
            row for row in original["entities"] if row["entity"] == "site-1"]}
        args = {**self.knowledge(), "entity": "site-1"}
        for fmt, expected in (("json", focused),
                              ("geojson", comparison_geojson(focused))):
            code, _, raw = self.fetch({**args, "format": fmt})
            self.assertEqual(code, 200)
            self.assertEqual(json.loads(raw), expected)
        code, _, raw = self.fetch({**args, "format": "csv"})
        self.assertEqual(code, 200)
        self.assertEqual(raw.decode("utf-8"), comparison_csv(focused))
        code, _, raw = self.fetch(args)
        self.assertEqual(code, 200)
        self.assertEqual(raw.decode("utf-8"), comparison_html(focused))
        self.assertIn("a-b2", json.dumps(focused))

    def test_unknown_entity_is_empty_valid_comparison_and_form_accepts_blank(self):
        original = compare_source_pair(self.world, "survey-a", "survey-b",
                                       AT, BEFORE, AFTER)
        expected = {**original, "entities": []}
        for fmt in ("json", "geojson", "csv"):
            status, _, raw = self.fetch({**self.knowledge(), "entity": "missing",
                                         "format": fmt})
            self.assertEqual(status, 200)
            if fmt == "json":
                self.assertEqual(json.loads(raw), expected)
            elif fmt == "geojson":
                self.assertEqual(json.loads(raw), comparison_geojson(expected))
            else:
                self.assertEqual(raw.decode(), comparison_csv(expected))
        status, _, raw = self.fetch({**self.knowledge(), "format": "json",
                                     "direction": "", "top": "", "entity": ""})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw), original)
        status, _, form = self.fetch()
        self.assertEqual(status, 200)
        self.assertEqual(form.count(b'name="entity"'), 2)

    def test_entity_scope_before_top_on_two_real_original_entities(self):
        # Construct the original evidence in knowledge order: WorldMini rejects
        # appending a fact with an earlier knowledge timestamp.
        world = WorldMini()
        early = "2026-01-02T00:00:00Z"
        late = "2026-01-04T00:00:00Z"
        originals = (
            ("survey-a", "main-a", "site-1", 0.0, early, None),
            ("survey-b", "main-b", "site-1", 2.0, early, None),
            ("survey-a", "extra-a", "site-extra", 10.0, early, None),
            ("survey-b", "extra-b", "site-extra", 10.5, early, None),
            ("survey-b", "main-b2", "site-1", 1.0, late, "a-main-b"),
        )
        for source, tag, entity, lon, known, parent in originals:
            world.add_evidence({"id": "e-" + tag, "source_id": source,
                                "locator": "fixture://" + tag,
                                "captured_at": known, "source_event_at": known})
            world.add_assertion({
                "id": "a-" + tag, "entity": entity, "attribute": "geo_point",
                "value": {"type": "Point", "coordinates": [lon, 0.]},
                "evidence_id": "e-" + tag, "kind": "CLAIM",
                "known_at": known, "valid_from": "2026-01-01T00:00:00Z",
                "valid_to": None, "supersedes": parent})
        file = Path(self.temp.name) / "multi.json"
        world.save(file)
        saved = file.read_bytes()
        server = create_server(file)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            original = compare_source_pair(world, "survey-a", "survey-b",
                                           AT, BEFORE, AFTER)
            self.assertEqual({row["entity"] for row in original["entities"]},
                             {"site-1", "site-extra"})
            focused = {**original, "entities": [
                row for row in original["entities"] if row["entity"] == "site-extra"]}
            expected = top_nearest_source_pair_changes(focused, 1)
            # site-1 has a larger change, hence filtering *after* top-1
            # would incorrectly produce an empty result for site-extra.
            ranked = top_nearest_source_pair_changes(original, 1)
            self.assertEqual([row["entity"] for row in ranked["entities"]],
                             ["site-1"])
            query = {**self.knowledge(), "entity": "site-extra",
                     "top": "1", "format": "json"}
            conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            conn.request("GET", "/source-pair?" + urlencode(query),
                         headers={"Host": "127.0.0.1:" + str(server.server_port)})
            response = conn.getresponse()
            code, actual = response.status, json.loads(response.read())
            conn.close()
            self.assertEqual(code, 200)
            self.assertEqual(actual, expected)
            self.assertEqual([row["entity"] for row in actual["entities"]],
                             ["site-extra"])
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
            self.assertEqual(file.read_bytes(), saved)

    def test_entity_filter_rejects_unsafe_ids_and_extraneous_fields(self):
        for entity in ("../site-1", "path/evil", "site-1\x00"):
            with self.subTest(entity=entity):
                code, _, body = self.fetch({**self.knowledge(), "entity": entity})
                self.assertEqual(code, 400)
                self.assertEqual(json.loads(body), {"error": "invalid_query"})
        code, _, body = self.fetch({**self.knowledge(), "entity": "site-1",
                                    "extra": "unexpected"})
        self.assertEqual(code, 400)


    def test_accessible_pair_table_shows_original_evidence_and_links(self):
        original = compare_source_pair(self.world, "survey-a", "survey-b",
                                       AT, BEFORE, AFTER)
        code, headers, page = self.fetch({**self.knowledge(), "format": "table"})
        body = page.decode("utf-8")
        self.assertEqual(code, 200)
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertIn("connect-src 'none'", headers["Content-Security-Policy"])
        self.assertNotIn("<script", body)
        self.assertIn('<table>', body)
        self.assertIn('<th scope="col">Earlier reported separation</th>', body)
        for item in original["entities"]:
            self.assertIn(item["entity"], body)
            for period in ("earlier", "later"):
                for source in ("source_a_original_reports", "source_b_original_reports"):
                    for report in item[period][source]:
                        self.assertIn(report["id"], body)
                        self.assertIn(report["properties"]["evidence_id"], body)
        self.assertIn("/inspect?view=source-history", body)
        self.assertIn("/inspect?view=entity", body)
        self.assertIn("format=csv", body)
        self.assertIn("format=geojson", body)

    def test_pair_table_retains_filters_and_world_time_cutoffs(self):
        from monde.source_pair_changes import source_pair_direction
        source = compare_source_pair_world_time(
            self.world, "survey-a", "survey-b", EARLY, LATE, KNOWN)
        # Ensure the table is derived from the same canonical records.
        query = {"axis": "world", "source_a": "survey-a",
                 "source_b": "survey-b", "from_at": EARLY, "to_at": LATE,
                 "known_at": KNOWN, "format": "table"}
        code, _, page = self.fetch(query)
        self.assertEqual(code, 200)
        html = page.decode("utf-8")
        for item in source["entities"]:
            self.assertIn(item["entity"], html)
            self.assertIn(source_pair_direction(item), html)
        self.assertIn("from_at=", html)
        self.assertIn("to_at=", html)
        self.assertIn("world " + EARLY, html)
        self.assertIn("world " + LATE, html)

    def test_pair_table_uses_existing_selection_and_handles_unknown(self):
        query = {**self.knowledge(), "entity": "site-1", "format": "table"}
        status, _, page = self.fetch(query)
        self.assertEqual(status, 200)
        self.assertIn(b"site-1", page)
        self.assertIn(b"entity=site-1", page)
        status, _, page = self.fetch({**query, "entity": "absent-entity"})
        self.assertEqual(status, 200)
        self.assertIn(b"NO MATCHING COMPARABLE SOURCE EVIDENCE", page)
        self.assertNotIn(b"<script", page)

    def test_pair_table_form_and_query_reject_invalid_format_and_inputs(self):
        status, _, html = self.fetch()
        self.assertEqual(status, 200)
        self.assertIn(b'<option value="table">', html)
        for params in ({**self.knowledge(), "format": "table", "source_a": "../bad"},
                       {**self.knowledge(), "format": "table", "unexpected": "x"},
                       {**self.knowledge(), "format": "TABLE"}):
            status, _, raw = self.fetch(params)
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(raw), {"error": "invalid_query"})

    def test_pair_table_escapes_untrusted_source_and_assertion_strings(self):
        from monde.local_api import _pair_table_html
        data = compare_source_pair(self.world, "survey-a", "survey-b",
                                   AT, BEFORE, AFTER)
        altered = json.loads(json.dumps(data))
        altered["source_a"] = '<img src=x onerror=alert(1)>'
        altered["entities"][0]["entity"] = 'evil"><script>alert(1)</script>'
        altered["entities"][0]["earlier"]["source_a_original_reports"][0]["id"] = \
            '<svg onload=alert(1)>'
        html = _pair_table_html(altered, self.knowledge())
        self.assertNotIn("<script>", html)
        self.assertNotIn("<svg", html)
        self.assertNotIn("<img", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&lt;svg", html)
        self.assertIn("&lt;img", html)


if __name__ == "__main__":
    unittest.main()
