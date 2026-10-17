"""End-to-end local browser map: reuse the original source-evidence renderer."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from monde.local_api import create_server
from monde.map_view import render_map, disagreement_view
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

    def fetch(self, query, *, server=None, host=None, path="/viewer"):
        server = server or self.server
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        connection.request("GET", path + ("?" + urlencode(query) if query else ""), headers={
            "Host": host or "127.0.0.1:" + str(server.server_port)})
        reply = connection.getresponse()
        output = (reply.status, dict(reply.getheaders()), reply.read())
        connection.close()
        return output

    def test_explorer_submits_exact_real_viewer_queries(self):
        from html.parser import HTMLParser

        class FormReader(HTMLParser):
            def __init__(self):
                super().__init__()
                self.forms = []
                self.active = None

            def handle_starttag(self, tag, attrs):
                values = dict(attrs)
                if tag == "form":
                    self.active = {"action": values.get("action"),
                                   "method": values.get("method"), "inputs": []}
                    self.forms.append(self.active)
                elif tag == "input" and self.active is not None:
                    self.active["inputs"].append(values)

            def handle_endtag(self, tag):
                if tag == "form":
                    self.active = None

        code, headers, data = self.fetch({}, path="/explore")
        self.assertEqual(code, 200)
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertIn("form-action 'self'", headers["Content-Security-Policy"])
        self.assertIn("connect-src 'none'", headers["Content-Security-Policy"])
        self.assertNotIn(b"<script", data)
        forms = FormReader()
        forms.feed(data.decode("utf-8"))
        expected = {
            "current": {"view", "bbox", "at", "known_at", "source"},
            "disagreements": {"view", "bbox", "at", "known_at", "source"},
            "knowledge-changes": {"view", "bbox", "at", "from_known_at", "to_known_at", "source"},
            "world-changes": {"view", "bbox", "from_at", "to_at", "known_at", "source"},
            "nearest": {"view", "center", "limit", "at", "known_at"},
            "radius": {"view", "center", "radius_km", "at", "known_at"}
        }
        self.assertEqual(len(forms.forms), 6)
        params = {"bbox": "2.3,48.8,2.4,48.9", "at": AT, "known_at": K2,
                  "center": "2.3522,48.8566", "limit": "10", "radius_km": "5",
                  "from_known_at": K1, "to_known_at": K2,
                  "from_at": EARLIER, "to_at": AT, "source": "survey-1"}
        for form in forms.forms:
            self.assertEqual((form["action"], form["method"]), ("/viewer", "get"))
            fields = form["inputs"]
            names = [f["name"] for f in fields]
            self.assertEqual(len(names), len(set(names)))
            mode = next(f["value"] for f in fields if f["name"] == "view")
            self.assertIn(mode, expected)
            self.assertEqual(set(names), expected[mode])
            query = {name: params[name] for name in names if name != "view"}
            query["view"] = mode
            status, _, content = self.fetch(query)
            self.assertEqual(status, 200, mode)
            self.assertIn(b"MONDE Mini", content)

        code, _, response = self.fetch({"view": "current"}, path="/explore")
        self.assertEqual(code, 400)
        self.assertEqual(json.loads(response), {"error": "invalid_query"})

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
                self.assertEqual(response.decode("utf-8"), render_map(expected, inspector_links=True, navigation=query))
                self.assertIn(b"source-reported", response.lower())
                self.assertEqual(headers["Content-Length"], str(len(response)))
                self.assertEqual(headers["X-Frame-Options"], "DENY")
                self.assertEqual(headers["Cache-Control"], "no-store")
                self.assertIn("connect-src 'none'", headers["Content-Security-Policy"])
                self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_local_map_selection_can_open_original_evidence(self):
        variants = (
            dict(view="current", bbox="2.3,48.8,2.4,48.9", at=AT, known_at=K2),
            dict(view="knowledge-changes", bbox="2.3,48.8,2.4,48.9",
                 at=AT, from_known_at=K1, to_known_at=K2),
            dict(view="world-changes", bbox="2.3,48.8,2.4,48.9",
                 from_at=EARLIER, to_at=AT, known_at=K2),
            dict(view="nearest", center="2.3522,48.8566", limit="1",
                 at=AT, known_at=K2),
            dict(view="radius", center="2.3522,48.8566",
                 radius_km="5", at=AT, known_at=K2),
        )
        for query in variants:
            with self.subTest(view=query["view"]):
                status, headers, content = self.fetch(query)
                html = content.decode("utf-8")
                self.assertEqual(status, 200)
                self.assertIn("var inspectorEnabled = true;", html)
                self.assertIn('id="full-entity-inspection"', html)
                self.assertIn('id="full-source-history"', html)
                self.assertIn('view:"entity",entity:p.entity,at:worldAt,known_at:knownAt', html)
                self.assertIn('view:"source-history",source:p.source_id,entity:p.entity,known_at:knownAt', html)
                self.assertIn('p.monde_change === "NO_LONGER_CURRENT"', html)
                self.assertIn("connect-src 'none'", headers["Content-Security-Policy"])
        original = self.path.read_bytes()
        entity = "site-a"  # Known original source entity, though its corrected Point moved.
        code, _, body = self.fetch(dict(view="entity", entity=entity,
                                         at=AT, known_at=K2), path="/inspect")
        self.assertEqual(code, 200)
        self.assertIn(b"Original source assertions only", body)
        code, _, revisions = self.fetch(
            dict(view="source-history", source="survey-1", entity=entity, known_at=K2),
            path="/inspect")
        self.assertEqual(code, 200)
        self.assertIn(b"Original source assertions only", revisions)
        self.assertIn(b"correct-a", revisions)
        self.assertEqual(self.path.read_bytes(), original)

    def test_standalone_map_does_not_advertise_server_links(self):
        source = self.world.export_geojson_bbox(BBOX, AT, K2)
        html = render_map(source)
        self.assertIn("var inspectorEnabled = false;", html)
        self.assertIn('id="full-inspection-links" hidden', html)
        with self.assertRaises(ValueError):
            render_map(source, inspector_links="true")

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
            expected = disagreement_view(
                model, [2.3, 48.8, 2.4, 48.9], AT, K1)
            self.assertEqual(status, 200)
            self.assertEqual(body.decode("utf-8"), render_map(expected, inspector_links=True, navigation=query))
            # The map intentionally keeps both original source positions:
            # one inside the requested viewport and its opposing offscreen report.
            self.assertEqual(len(expected["features"]), 2)
            self.assertEqual(
                {feature["properties"]["monde_inside_bbox"]
                 for feature in expected["features"]}, {True, False})
            self.assertEqual(
                {feature["properties"]["source_id"]
                 for feature in expected["features"]},
                {"survey-east", "survey-west"})
            self.assertTrue(all(
                feature["properties"]["monde_conflicting_source_ids"] ==
                ["survey-east", "survey-west"]
                for feature in expected["features"]))
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
                render_map(disagreement_view(
                    model, [10.0, 10.0, 11.0, 11.0], AT, K1),
                    inspector_links=True, navigation=empty))
        finally:
            server.shutdown()
            worker.join(timeout=5)
            server.server_close()
        self.assertEqual(path.read_bytes(), original)

    def test_proximity_browser_matches_existing_geojson_and_map_renderer(self):
        center = [2.3522, 48.8566]
        queries = (
            (dict(view="nearest", center="2.3522,48.8566",
                  limit="1", at=AT, known_at=K1),
             self.world.export_geojson_nearest(center, 1, AT, K1)),
            (dict(view="radius", center="2.3522,48.8566",
                  radius_km="5", at=AT, known_at=K1),
             self.world.export_geojson_radius(center, 5.0, AT, K1)),
        )
        for query, expected in queries:
            with self.subTest(view=query["view"]):
                status, headers, body = self.fetch(query)
                self.assertEqual(status, 200)
                self.assertEqual(body.decode("utf-8"), render_map(expected, inspector_links=True, navigation=query))
                self.assertEqual(headers["Content-Length"], str(len(body)))
                self.assertEqual(headers["Cache-Control"], "no-store")
                self.assertEqual(headers["X-Frame-Options"], "DENY")
                self.assertIn("connect-src 'none'", headers["Content-Security-Policy"])
                self.assertNotIn("Access-Control-Allow-Origin", headers)
                model_route = "/nearest" if query["view"] == "nearest" else "/radius"
                raw_query = {k: v for k, v in query.items() if k != "view"}
                code, _, raw_body = self.fetch(raw_query, path=model_route)
                self.assertEqual(code, 200)
                self.assertEqual(json.loads(raw_body), expected)

    def test_browser_radius_preserves_off_radius_competing_sources(self):
        model = disputed()
        path = Path(self.tempdir.name) / "nearby-disputed.json"
        model.save(path)
        original = path.read_bytes()
        server = create_server(path)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            query = dict(view="radius", center="2.3522,48.8566",
                         radius_km="5", at=AT, known_at=K1)
            status, _, document = self.fetch(query, server=server)
            expected = model.export_geojson_radius([2.3522, 48.8566], 5.0, AT, K1)
            self.assertEqual(status, 200)
            self.assertEqual(document.decode("utf-8"), render_map(expected, inspector_links=True, navigation=query))
            features = expected["features"]
            self.assertEqual(len(features), 2)
            self.assertEqual({f["properties"]["source_id"] for f in features},
                             {"survey-east", "survey-west"})
            self.assertEqual({f["properties"]["monde_within_radius"] for f in features},
                             {True, False})
            self.assertTrue(all(f["properties"]["evidence_id"] for f in features))
            self.assertIn(b"survey-east", document)
            self.assertIn(b"survey-west", document)
            self.assertIn(b'"monde_proximity_display":"SELECTED_SOURCE_ENVELOPE_NOT_QUERY_BBOX"',
                          document)
            self.assertIn(b'"monde_within_radius":false', document)
            self.assertIn(b'"monde_within_radius":true', document)
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
        self.assertEqual(path.read_bytes(), original)

    def test_proximity_browser_rejects_unsafe_or_ambiguous_inputs(self):
        base = dict(view="nearest", center="2.3522,48.8566",
                    limit="10", at=AT, known_at=K1)
        bad = (
            dict(base, limit="0"),
            dict(base, limit="1001"),
            dict(base, center="200,48.8"),
            dict(base, center="nan,48.8"),
            dict(base, at="invalid"),
            dict(base, unknown="extra"),
            dict(base, radius_km="5"),
            dict(base, view="radius"),
            dict(base, view="radius", radius_km="-1", limit=None),
            dict(base, view="radius", radius_km="nan", limit=None),
        )
        for query in bad:
            with self.subTest(query=query):
                query = {key: value for key, value in query.items() if value is not None}
                status, _, body = self.fetch(query)
                self.assertEqual(status, 400)
                self.assertEqual(json.loads(body), {"error": "invalid_query"})
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        conn.request("GET", "/viewer?view=nearest&center=2.3522,48.8566"
                     "&center=0,0&limit=10&at=" + AT + "&known_at=" + K1,
                     headers={"Host": "127.0.0.1:" + str(self.server.server_port)})
        response = conn.getresponse()
        self.assertEqual(response.status, 400)
        response.read()
        conn.close()

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
