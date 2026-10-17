"""Read-only source-involved disagreement maps retain opposing original evidence."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from monde.local_api import create_server, _explorer_html
from monde.map_view import render_map
from tests.test_world_geojson_disagreements import AT, K1, K2, disputed

BBOX = "2.3,48.8,2.4,48.9"
WINDOW = [2.3, 48.8, 2.4, 48.9]
QUERY = {"bbox": BBOX, "at": AT, "known_at": K1}


class SourceDisagreementHTTPTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.file = Path(self.directory.name) / "world.json"
        self.world = disputed()
        self.world.save(self.file)
        self.saved = self.file.read_bytes()
        self.server = create_server(self.file)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()
        self.assertEqual(self.file.read_bytes(), self.saved)
        self.directory.cleanup()

    def get(self, endpoint, query):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        conn.request("GET", endpoint + "?" + urlencode(query),
                     headers={"Host": "127.0.0.1:" + str(self.server.server_port)})
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return result

    def test_qualifying_source_keeps_both_original_positions_and_ids(self):
        status, headers, raw = self.get(
            "/map-disagreements", {**QUERY, "source": "survey-east"})
        self.assertEqual(status, 200)
        result = json.loads(raw)
        features = result["features"]
        self.assertEqual({f["properties"]["source_id"] for f in features},
                         {"survey-east", "survey-west"})
        self.assertEqual({tuple(f["geometry"]["coordinates"]) for f in features},
                         {(2.35, 48.85), (7.2, 47.5)})
        self.assertTrue(all(f["properties"]["entity"] == "site-a" for f in features))
        self.assertTrue(all(f["properties"]["evidence_id"] for f in features))
        self.assertTrue(all(f["properties"]["monde_conflicting_source_ids"] ==
                            ["survey-east", "survey-west"] for f in features))
        self.assertEqual(sum(f["properties"]["monde_inside_bbox"] for f in features), 1)
        self.assertEqual(result["monde_source_filter"], "survey-east")
        self.assertEqual(result["monde_source_filter_basis"],
                         "SOURCE_INVOLVED_IN_CONFLICT_KEEP_OPPOSITION")
        self.assertEqual(result["monde_bbox_query"]["total_matching_entities"], 1)
        self.assertEqual(result["monde_bbox_query"]["total_source_features"], 2)
        self.assertEqual(result["monde_disagreements_view"]["conflicting_entities_in_view"], 1)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_other_source_offscreen_cannot_qualify_disagreement(self):
        code, _, data = self.get("/map-disagreements",
                                  {**QUERY, "source": "survey-west"})
        self.assertEqual(code, 200)
        result = json.loads(data)
        self.assertEqual(result["features"], [])
        self.assertEqual(result["monde_bbox_query"]["status"], "NO_MATCHES")
        self.assertEqual(result["monde_disagreements_view"]["conflicting_entities_in_view"], 0)

    def test_unfiltered_contract_and_blank_source_remain_unchanged(self):
        code, _, data = self.get("/map-disagreements", QUERY)
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(data),
                         self.world.export_geojson_disagreements(AT, K1, WINDOW))
        code, _, blank = self.get("/map-disagreements", {**QUERY, "source": ""})
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(blank), json.loads(data))

    def test_viewer_matches_existing_renderer_and_preserves_source_navigation(self):
        query = {"view": "disagreements", **QUERY, "source": "survey-east"}
        code, headers, html = self.get("/viewer", query)
        self.assertEqual(code, 200)
        from monde.map_view import disagreement_view
        from monde.local_api import _filter_disagreements_by_source
        expected = _filter_disagreements_by_source(
            disagreement_view(self.world, WINDOW, AT, K1), "survey-east")
        self.assertEqual(html.decode("utf-8"),
                         render_map(expected, inspector_links=True, navigation=query))
        self.assertIn(b'name="source" value="survey-east"', html)
        self.assertIn(b"survey-west", html)
        self.assertIn("connect-src 'none'", headers["Content-Security-Policy"])
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_explorer_includes_optional_source_for_disagreements(self):
        html = _explorer_html(("survey-east", "survey-west"))
        form = html.split('value="disagreements">', 1)[1].split("</form>", 1)[0]
        self.assertIn('name="source"', form)
        self.assertIn('list="saved-original-sources"', form)
        self.assertIn("keep opposing evidence", form)

    def test_rejects_bad_source_and_duplicate_fields_without_altering_state(self):
        for source in ("../survey-east", "<script>", "white space", "s" * 110):
            for route in ("/map-disagreements", "/viewer"):
                args = {**QUERY, "source": source}
                if route == "/viewer":
                    args["view"] = "disagreements"
                code, _, raw = self.get(route, args)
                self.assertEqual(code, 400)
                self.assertEqual(json.loads(raw), {"error": "invalid_query"})
        code, _, raw = self.get("/map-disagreements",
                                {**QUERY, "source": "survey-east", "surprise": "yes"})
        self.assertEqual(code, 400)
        self.assertEqual(json.loads(raw), {"error": "invalid_query"})

    def test_no_conflict_at_earlier_knowledge_cutoff(self):
        code, _, body = self.get("/map-disagreements", {
            **QUERY, "known_at": "2025-12-31T00:00:00Z", "source": "survey-east"})
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)["features"], [])


if __name__ == "__main__":
    unittest.main()
