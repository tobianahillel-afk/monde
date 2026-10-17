"""End-to-end local browser map: reuse the original source-evidence renderer."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from monde.local_api import create_server
from monde.map_view import render_map
from tests.test_world_geojson_changes import model as change_model, correct, AT, K1, K2
from tests.test_world_geojson_disagreements import disputed

BBOX = [2.3, 48.8, 2.4, 48.9]
EARLIER = "2025-12-31T00:00:00Z"


class BrowserViewerTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "world.json"
        self.world = change_model()
        correct(self.world)
        self.world.save(str(self.path))
        self.original = self.path.read_bytes()
        self.server = create_server(self.path)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()
        self.assertEqual(self.path.read_bytes(), self.original)
        self.tempdir.cleanup()

    def fetch(self, query, *, server=None, host=None):
        server = server or self.server
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        connection.request("GET", "/viewer?" + urlencode(query), headers={
            "Host": host or "127.0.0.1:" + str(server.server_port)})
        reply = connection.getresponse()
        output = (reply.status, dict(reply.getheaders()), reply.read())
        connection.close()
        return output

    def test_all_three_browser_views_match_existing_model_and_renderer(self):
        cases = [
            (dict(view="current", bbox="2.3,48.8,2.4,48.9", at=AT, known_at=K2),
             self.world.export_geojson_bbox(BBOX, AT, K2)),
            (dict(view="knowledge-changes", bbox="2.3,48.8,2.4,48.9",
                  at=AT, from_known_at=K1, to_known_at=K2),
             self.world.export_geojson_bbox_knowledge_changes(BBOX, AT, K1, K2)),
            (dict(view="world-changes", bbox="2.3,48.8,2.4,48.9",
                  from_at=EARLIER, to_at=AT, known_at=K2),
             self.world.export_geojson_bbox_world_changes(BBOX, EARLIER, AT, K2)),
        ]
        for query, expected in cases:
            with self.subTest(mode=query["view"]):
                code, headers, response = self.fetch(query)
                self.assertEqual(code, 200)
                self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
                self.assertEqual(response.decode("utf-8"), render_map(expected))
                self.assertIn(b"source-reported", response.lower())
                self.assertEqual(headers["Content-Length"], str(len(response)))
                self.assertEqual(headers["X-Frame-Options"], "DENY")
                self.assertEqual(headers["Cache-Control"], "no-store")
                self.assertIn("connect-src 'none'", headers["Content-Security-Policy"])
                self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_browser_disagreements_preserves_offscreen_opposition(self):
        # Reuse real saved source claims and the existing offline renderer.
        model = disputed()
        path = Path(self.tempdir.name) / "disputed.json"
        model.save(path)
        original = path.read_bytes()
        server = create_server(path)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            query = dict(view="disagreements", bbox="2.3,48.8,2.4,48.9",
                         at=AT, known_at=K1)
            status, headers, body = self.fetch(query, server=server)
            expected = model.export_geojson_disagreements(
                AT, K1, [2.3, 48.8, 2.4, 48.9])
            self.assertEqual(status, 200)
            self.assertEqual(body.decode("utf-8"), render_map(expected))
            self.assertEqual(len(expected["features"]), 1)
            self.assertEqual(
                expected["features"][0]["properties"]["monde_conflicting_source_ids"],
                ["survey-east", "survey-west"])
            self.assertIn(b"Saved-state source disagreement view", body)
            self.assertIn(b"survey-east", body)
            self.assertIn(b"survey-west", body)
            self.assertIn("connect-src 'none'", headers["Content-Security-Policy"])
            self.assertNotIn("Access-Control-Allow-Origin", headers)

            # A viewport with no conflicting reports must not invent evidence.
            empty = dict(query, bbox="10,10,11,11")
            _, _, empty_body = self.fetch(empty, server=server)
            self.assertEqual(
                empty_body.decode("utf-8"),
                render_map(model.export_geojson_disagreements(
                    AT, K1, [10, 10, 11, 11])))
        finally:
            server.shutdown()
            worker.join(timeout=5)
            server.server_close()
        self.assertEqual(path.read_bytes(), original)

    def test_disallows_wrong_view_unknown_keys_and_invalid_time_or_bbox(self):
        valid = dict(view="current", bbox="2.3,48.8,2.4,48.9", at=AT, known_at=K2)
        invalid = [
            {**valid, "view": "unsupported"},
            {**valid, "view": "disagreements", "unexpected": "not-allowed"},
            {**valid, "view": "disagreements", "known_at": "not-a-time"},
            {**valid, "view": "disagreements", "bbox": "not-a-bbox"},
            {**valid, "view": ""},
            {**valid, "unexpected": "foo"},
            {**valid, "bbox": "200,1,210,2"},
            {**valid, "at": "bad"},
            {"view": "knowledge-changes", "bbox": valid["bbox"], "at": AT,
             "from_known_at": K2, "to_known_at": K1},
            {"view": "world-changes", "bbox": valid["bbox"], "from_at": AT,
             "to_at": EARLIER, "known_at": K2},
        ]
        for query in invalid:
            with self.subTest(query=query):
                code, _, result = self.fetch(query)
                self.assertEqual(code, 400)
                self.assertEqual(json.loads(result), {"error": "invalid_query"})
        code, _, result = self.fetch(valid, host="evil.example")
        self.assertEqual(code, 403)
        self.assertEqual(json.loads(result), {"error": "loopback_host_required"})

    def test_duplicate_parameter_cannot_change_viewer_mode(self):
        params = ("/viewer?view=current&view=knowledge-changes"
                  "&bbox=2.3,48.8,2.4,48.9&at=" + AT + "&known_at=" + K2)
        c = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        c.request("GET", params, headers={"Host": "127.0.0.1:" + str(self.server.server_port)})
        r = c.getresponse()
        self.assertEqual(r.status, 400)
        self.assertEqual(json.loads(r.read()), {"error": "invalid_query"})
        c.close()

    def test_response_limit_returns_bounded_json_error_not_partial_html(self):
        server = create_server(self.path, max_response_bytes=512)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            status, headers, body = self.fetch(
                dict(view="current", bbox="2.3,48.8,2.4,48.9", at=AT, known_at=K2),
                server=server)
            self.assertEqual(status, 413)
            self.assertIn("application/json", headers["Content-Type"])
            self.assertEqual(json.loads(body), {"error": "response_too_large"})
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
