"""Real HTTP source-pair comparisons using the original WorldMini functions."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from monde.local_api import create_server
from monde.source_pair_changes import (
    compare_source_pair, compare_source_pair_world_time, comparison_geojson,
    filter_source_pair_direction, comparison_html)
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


if __name__ == "__main__":
    unittest.main()
