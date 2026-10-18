"""Original-source lens for MONDE Mini read-only bbox maps."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from monde.local_api import create_server, _explorer_html
from monde.map_view import render_map
from tests.test_world_geojson_disagreements import AT, K1, disputed

BOUNDS = [2.3, 48.8, 2.4, 48.9]
QUERY = {"bbox": "2.3,48.8,2.4,48.9", "at": AT, "known_at": K1}


class SourceLensHTTPTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "world.json"
        self.world = disputed()
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
        self.dir.cleanup()

    def fetch(self, route, query):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        connection.request("GET", route + "?" + urlencode(query),
                           headers={"Host": "127.0.0.1:" + str(self.server.server_port)})
        result = connection.getresponse()
        data = (result.status, dict(result.getheaders()), result.read())
        connection.close()
        return data

    def test_explorer_suggests_original_sources_from_saved_points(self):
        code, headers, body = self.fetch("/explore", {})
        self.assertEqual(code, 200)
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertIn(b'list="saved-original-sources"', body)
        self.assertIn(b'<option value="survey-east"></option>', body)
        self.assertIn(b'<option value="survey-west"></option>', body)
        self.assertIn(b'original Point sources in this saved snapshot', body)
        self.assertNotIn(b"<script", body)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn("connect-src 'none'", headers["Content-Security-Policy"])
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        status, _, page = self.fetch("/viewer",
             {"view": "current", **QUERY, "source": "survey-east"})
        self.assertEqual(status, 200)
        self.assertIn(b'name="source" value="survey-east"', page)

    def test_suggested_source_ids_are_escaped_and_bounded(self):
        page = _explorer_html(('map"><script>alert(1)</script>', 'safe-source'))
        self.assertNotIn('<option value="map"><script>', page)
        self.assertIn('&lt;script&gt;', page)
        self.assertIn('value="safe-source"', page)
        capped = _explorer_html(tuple("source-%03d" % i for i in range(205)))
        self.assertIn('205 original Point sources', capped)
        self.assertIn('value="source-199"', capped)
        self.assertNotIn('value="source-200"', capped)

    def test_original_source_selection_keeps_provenance_and_counts(self):
        code, headers, body = self.fetch("/map", {**QUERY, "source": "survey-east"})
        self.assertEqual(code, 200)
        data = json.loads(body)
        self.assertEqual(data["monde_source_filter"], "survey-east")
        self.assertEqual([x["properties"]["source_id"] for x in data["features"]],
                         ["survey-east"])
        self.assertEqual([x["properties"]["entity"] for x in data["features"]], ["site-a"])
        self.assertTrue(data["features"][0]["properties"]["evidence_id"])
        self.assertEqual(data["monde_bbox_query"]["total_matching_entities"], 1)
        self.assertEqual(data["monde_bbox_query"]["total_source_features"], 1)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_outside_source_is_not_mistaken_for_matching_source(self):
        code, _, data = self.fetch("/map", {**QUERY, "source": "survey-west"})
        self.assertEqual(code, 200)
        payload = json.loads(data)
        self.assertEqual(payload["features"], [])
        self.assertEqual(payload["monde_bbox_query"]["status"], "NO_MATCHES")
        self.assertEqual(payload["monde_bbox_query"]["total_matching_entities"], 0)

    def test_unspecified_source_is_byte_identical_to_world_export(self):
        code, _, raw = self.fetch("/map", QUERY)
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(raw), self.world.export_geojson_bbox(BOUNDS, AT, K1))
        self.assertEqual(self.fetch("/map", {**QUERY, "source": ""})[0], 200)

    def test_filtered_viewer_renders_real_source_and_preserves_time_navigation(self):
        query = {"view": "current", **QUERY, "source": "survey-east"}
        code, headers, body = self.fetch("/viewer", query)
        self.assertEqual(code, 200)
        output = json.loads(self.fetch("/map", {**QUERY, "source": "survey-east"})[2])
        self.assertEqual(body.decode("utf-8"),
                         render_map(output, inspector_links=True, navigation=query))
        self.assertIn(b'name="source" value="survey-east"', body)
        self.assertIn(b"survey-east", body)
        self.assertNotIn(b"survey-west", body)
        self.assertIn("connect-src 'none'", headers["Content-Security-Policy"])

    def test_invalid_source_cannot_change_query_semantics(self):
        for source in ("../survey-east", "bad<script>", "/abs", "a b", "a\\b", "z" * 100):
            with self.subTest(source=source):
                code, _, body = self.fetch("/map", {**QUERY, "source": source})
                self.assertEqual(code, 400)
                self.assertEqual(json.loads(body), {"error": "invalid_query"})
        for route, query in (
            ("/viewer", {"view": "disagreements", **QUERY, "source": "survey-east"}),
            ("/map", {**QUERY, "source": "survey-east", "extra": "x"}),
        ):
            code, _, body = self.fetch(route, query)
            self.assertEqual(code, 400)
            self.assertEqual(json.loads(body), {"error": "invalid_query"})


class HistoricalSourceLensHTTPTests(unittest.TestCase):
    def setUp(self):
        from tests.test_world_geojson_changes import model, correct
        from monde.geojson import to_document
        self.world = model()
        correct(self.world)
        self.world.append_document(to_document(
            {"type": "FeatureCollection", "features": [
                {"type": "Feature", "id": "site-a",
                 "geometry": {"type": "Point", "coordinates": [2.35, 48.85]},
                 "properties": {}}]},
            source_id="survey-2", locator="fixture://survey-2",
            captured_at="2026-01-12T10:00:00Z",
            valid_from="2026-01-01T00:00:00Z"))
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "world.json"
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

    def fetch(self, route, query):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        conn.request("GET", route + "?" + urlencode(query),
                     headers={"Host": "127.0.0.1:" + str(self.server.server_port)})
        response = conn.getresponse()
        data = response.status, response.read()
        conn.close()
        return data

    def test_knowledge_change_source_keeps_both_old_and_new_positions(self):
        from tests.test_world_geojson_changes import K1, K2
        query = {"bbox": QUERY["bbox"], "at": AT,
                 "from_known_at": K1, "to_known_at": K2}
        code, raw = self.fetch("/map-knowledge-changes", {**query, "source": "survey-1"})
        self.assertEqual(code, 200)
        payload = json.loads(raw)
        self.assertEqual({f["properties"]["monde_change"] for f in payload["features"]},
                         {"NO_LONGER_CURRENT", "NEWLY_CURRENT"})
        self.assertEqual({f["properties"]["source_id"] for f in payload["features"]},
                         {"survey-1"})
        self.assertEqual(payload["monde_bbox_changes_query"]["total_changed_features"], 2)
        self.assertEqual(payload["monde_bbox_changes_query"]["total_matching_entities"], 1)
        self.assertTrue(all(f["properties"]["monde_change_basis"] ==
                            "KNOWLEDGE_NOT_PHYSICAL" for f in payload["features"]))
        code, raw = self.fetch("/map-knowledge-changes", {**query, "source": "survey-2"})
        self.assertEqual(code, 200)
        survey2 = json.loads(raw)["features"]
        self.assertEqual(len(survey2), 1)
        self.assertEqual(survey2[0]["properties"]["source_id"], "survey-2")
        self.assertEqual(survey2[0]["properties"]["monde_change"], "NEWLY_CURRENT")
        code, raw = self.fetch("/map-knowledge-changes", query)
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(raw),
                         self.world.export_geojson_bbox_knowledge_changes(
                             BOUNDS, AT, K1, K2))
        viewer = {"view": "knowledge-changes", **query, "source": "survey-1"}
        code, raw = self.fetch("/viewer", viewer)
        self.assertEqual(code, 200)
        self.assertEqual(raw.decode("utf-8"),
                         render_map(payload, inspector_links=True, navigation=viewer))
        self.assertIn(b'name="source" value="survey-1"', raw)

    def test_world_change_source_respects_world_validity_not_knowledge(self):
        from tests.test_world_geojson_changes import K2
        query = {"bbox": "3.2,49.0,3.3,49.2",
                 "from_at": "2025-12-31T00:00:00Z",
                 "to_at": AT, "known_at": K2}
        code, raw = self.fetch("/map-world-changes", {**query, "source": "survey-1"})
        self.assertEqual(code, 200)
        payload = json.loads(raw)
        self.assertEqual([f["properties"]["source_id"] for f in payload["features"]],
                         ["survey-1"])
        self.assertEqual(payload["features"][0]["properties"]["monde_change"],
                         "NEWLY_CURRENT")
        self.assertEqual(payload["features"][0]["properties"]["monde_change_basis"],
                         "REPORTED_VALIDITY_NOT_VERIFIED_MOTION")
        viewer = {"view": "world-changes", **query, "source": "survey-1"}
        code, raw = self.fetch("/viewer", viewer)
        self.assertEqual(code, 200)
        self.assertEqual(raw.decode("utf-8"),
                         render_map(payload, inspector_links=True, navigation=viewer))
        code, raw = self.fetch("/map-world-changes", query)
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(raw), self.world.export_geojson_bbox_world_changes(
                         [3.2, 49.0, 3.3, 49.2], query["from_at"], AT, K2))
        for route in ("/map-world-changes", "/viewer"):
            invalid = {**query, "source": "../survey-1"}
            if route == "/viewer":
                invalid["view"] = "world-changes"
            code, raw = self.fetch(route, invalid)
            self.assertEqual(code, 400)
            self.assertEqual(json.loads(raw), {"error": "invalid_query"})

    def test_explorer_shows_historical_source_inputs(self):
        html = _explorer_html(("survey-1",))
        for view in ("knowledge-changes", "world-changes"):
            form = html.split('value="' + view + '">', 1)[1].split('</form>', 1)[0]
            self.assertIn('name="source"', form)
            self.assertIn('list="saved-original-sources"', form)


if __name__ == "__main__":
    unittest.main()
