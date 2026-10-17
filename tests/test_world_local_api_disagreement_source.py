"""Read-only original-source focus with intact opposing disagreement evidence."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from monde.local_api import create_server, _explorer_html
from monde.map_view import disagreement_view, render_map
from tests.test_world_geojson_disagreements import AT, K1, disputed

EAST = [2.3, 48.8, 2.4, 48.9]
EAST_Q = {"bbox": "2.3,48.8,2.4,48.9", "at": AT, "known_at": K1}
WEST_Q = {"bbox": "7.1,47.4,7.3,47.6", "at": AT, "known_at": K1}


class DisagreementSourceHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name) / "world.json"
        self.world = disputed()
        self.world.save(self.state)
        self.original = self.state.read_bytes()
        self.server = create_server(self.state)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()
        self.assertEqual(self.state.read_bytes(), self.original)
        self.tmp.cleanup()

    def fetch(self, endpoint, query):
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=5)
        connection.request(
            "GET", endpoint + "?" + urlencode(query),
            headers={"Host": "127.0.0.1:" + str(self.server.server_port)})
        response = connection.getresponse()
        data = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return data

    def test_selected_source_qualifies_own_point_and_keeps_opposing_evidence(self):
        status, headers, raw = self.fetch(
            "/map-disagreements", {**EAST_Q, "source": "survey-east"})
        self.assertEqual(status, 200)
        data = json.loads(raw)
        self.assertEqual(data["monde_source_focus"], "survey-east")
        self.assertEqual({f["properties"]["source_id"] for f in data["features"]},
                         {"survey-east", "survey-west"})
        self.assertEqual({tuple(f["geometry"]["coordinates"])
                          for f in data["features"]}, {(2.35, 48.85), (7.2, 47.5)})
        for f in data["features"]:
            self.assertEqual(f["properties"]["entity"], "site-a")
            self.assertEqual(f["properties"]["monde_conflicting_source_ids"],
                             ["survey-east", "survey-west"])
            self.assertEqual(f["properties"]["monde_disagreement_basis"],
                             "DISTINCT_SOURCE_REPORTS_NOT_PHYSICAL_TRUTH")
            self.assertEqual(f["id"], f["properties"]["assertion_id"])
            self.assertTrue(f["properties"]["evidence_id"])
        self.assertEqual(data["monde_bbox_query"]["total_matching_entities"], 1)
        self.assertEqual(data["monde_bbox_query"]["total_source_features"], 2)
        self.assertEqual(
            data["monde_disagreements_view"]["conflicting_entities_in_view"], 1)
        self.assertEqual(data["monde_bbox_query"]["status"], "MATCHES")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_offscreen_selected_source_does_not_borrow_other_sources_location(self):
        status, _, raw = self.fetch(
            "/map-disagreements", {**EAST_Q, "source": "survey-west"})
        self.assertEqual(status, 200)
        data = json.loads(raw)
        self.assertEqual(data["features"], [])
        self.assertEqual(data["monde_bbox_query"]["total_matching_entities"], 0)
        self.assertEqual(data["monde_bbox_query"]["status"], "NO_MATCHES")
        self.assertEqual(data["monde_disagreements_view"]["conflicting_entities_in_view"], 0)
        status, _, raw = self.fetch(
            "/map-disagreements", {**WEST_Q, "source": "survey-west"})
        self.assertEqual(status, 200)
        self.assertEqual({f["properties"]["source_id"] for f in json.loads(raw)["features"]},
                         {"survey-east", "survey-west"})

    def test_non_disputed_source_point_never_masquerades_as_a_disagreement(self):
        query = {"bbox": "1.1,45.0,1.3,45.2", "at": AT,
                 "known_at": K1, "source": "survey-east"}
        code, _, data = self.fetch("/map-disagreements", query)
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(data)["features"], [])
        code, _, data = self.fetch(
            "/map-disagreements", {**EAST_Q, "source": "unknown-source"})
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(data)["features"], [])

    def test_legacy_json_is_unchanged_and_blank_source_is_unfiltered(self):
        code, _, data = self.fetch("/map-disagreements", EAST_Q)
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(data),
                         self.world.export_geojson_disagreements(AT, K1, EAST))
        code, _, blank = self.fetch(
            "/map-disagreements", {**EAST_Q, "source": ""})
        self.assertEqual(code, 200)
        self.assertEqual(blank, data)

    def test_actual_viewer_and_native_navigation_preserve_original_source_focus(self):
        query = {"view": "disagreements", **EAST_Q, "source": "survey-east"}
        code, headers, body = self.fetch("/viewer", query)
        self.assertEqual(code, 200)
        _, _, raw = self.fetch(
            "/map-disagreements", {**EAST_Q, "source": "survey-east"})
        document = json.loads(raw)
        self.assertEqual(body.decode("utf-8"),
                         render_map(document, inspector_links=True, navigation=query))
        self.assertIn(b'name="source" value="survey-east"', body)
        self.assertIn(b"survey-west", body)
        self.assertIn("connect-src 'none'", headers["Content-Security-Policy"])
        self.assertIn("form-action 'self'", headers["Content-Security-Policy"])
        html = _explorer_html(("survey-east", "survey-west"))
        disagreements = html.split('value="disagreements">', 1)[1].split("</form>", 1)[0]
        self.assertIn('name="source"', disagreements)
        self.assertIn('list="saved-original-sources"', disagreements)

    def test_invalid_focus_is_rejected_and_time_cutoff_is_respected(self):
        for route, extra in (
            ("/map-disagreements", {}),
            ("/viewer", {"view": "disagreements"}),
        ):
            for source in ("../survey-east", "<script>", "survey east", "z" * 100):
                code, _, raw = self.fetch(route, {**EAST_Q, **extra, "source": source})
                self.assertEqual(code, 400)
                self.assertEqual(json.loads(raw), {"error": "invalid_query"})
            code, _, raw = self.fetch(
                route, {**EAST_Q, **extra, "source": "survey-east", "extra": "x"})
            self.assertEqual(code, 400)
            self.assertEqual(json.loads(raw), {"error": "invalid_query"})
        earlier = {**EAST_Q, "known_at": "2026-01-09T00:00:00Z",
                   "source": "survey-east"}
        code, _, raw = self.fetch("/map-disagreements", earlier)
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(raw)["features"], [])


if __name__ == "__main__":
    unittest.main()
