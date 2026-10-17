"""Read-only disagreement focus retains *opposing* source evidence."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from monde.local_api import create_server
from monde.map_view import render_map
from tests.test_world_geojson_disagreements import AT, K1, disputed, add

BOUNDS = "2.3,48.8,2.4,48.9"
QUERY = {"bbox": BOUNDS, "at": AT, "known_at": K1}


class DisagreementFocusHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "snapshot.json"
        self.world = disputed()
        # A second conflicting entity qualified by another *own* source.
        add(self.world, "survey-north", [2.34, 48.84], entity="site-b")
        self.world.save(self.path)
        self.before = self.path.read_bytes()
        self.server = create_server(self.path)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()
        self.assertEqual(self.path.read_bytes(), self.before)
        self.tmp.cleanup()

    def fetch(self, route, query):
        c = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        c.request("GET", route + "?" + urlencode(query),
                  headers={"Host": "127.0.0.1:" + str(self.server.server_port)})
        response = c.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        c.close()
        return result

    def test_selected_source_qualifies_only_its_own_visible_conflicts(self):
        code, headers, body = self.fetch("/map-disagreements",
                                         {**QUERY, "source": "survey-east"})
        self.assertEqual(code, 200)
        data = json.loads(body)
        self.assertEqual(data["monde_disagreement_source_focus"], "survey-east")
        self.assertEqual({f["properties"]["entity"] for f in data["features"]},
                         {"site-a"})
        self.assertEqual({f["properties"]["source_id"] for f in data["features"]},
                         {"survey-east"})
        props = data["features"][0]["properties"]
        self.assertEqual(props["monde_conflicting_source_ids"],
                         ["survey-east", "survey-west"])
        self.assertTrue(props["evidence_id"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_opposing_visible_and_offscreen_original_sources_survive_viewer(self):
        code, _, body = self.fetch("/viewer",
            {"view": "disagreements", **QUERY, "source": "survey-east"})
        self.assertEqual(code, 200)
        from monde.map_view import disagreement_view
        from monde.local_api import _focus_disagreement_source
        expected = _focus_disagreement_source(
            disagreement_view(self.world, [2.3, 48.8, 2.4, 48.9], AT, K1),
            "survey-east")
        self.assertEqual(body.decode("utf-8"), render_map(expected,
            inspector_links=True,
            navigation={"view": "disagreements", **QUERY, "source": "survey-east"}))
        self.assertEqual({f["properties"]["source_id"]
                          for f in expected["features"]},
                         {"survey-east", "survey-west"})
        self.assertEqual(expected["monde_bbox_query"]["total_matching_entities"], 1)
        self.assertEqual(expected["monde_disagreements_view"]
                         ["conflicting_entities_in_view"], 1)
        self.assertIn(b'name="source" value="survey-east"', body)
        self.assertNotIn(b"survey-north", body)

    def test_selected_source_offscreen_cannot_borrow_opposing_source_viewport(self):
        for source in ("survey-west", "not-known"):
            status, _, body = self.fetch("/map-disagreements",
                                         {**QUERY, "source": source})
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["features"], [])
            status, _, body = self.fetch("/viewer",
                   {"view": "disagreements", **QUERY, "source": source})
            self.assertEqual(status, 200)
        status, _, body = self.fetch("/map-disagreements",
                                    {**QUERY, "source": "survey-north"})
        self.assertEqual(status, 200)
        props = [f["properties"] for f in json.loads(body)["features"]]
        self.assertEqual([(p["entity"], p["source_id"]) for p in props],
                         [("site-b", "survey-north")])
        self.assertEqual(props[0]["monde_conflicting_source_ids"],
                         ["survey-east", "survey-north"])

    def test_unfiltered_json_unchanged_and_source_form_available(self):
        status, _, body = self.fetch("/map-disagreements", QUERY)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body),
                         self.world.export_geojson_disagreements(
                             AT, K1, [2.3, 48.8, 2.4, 48.9]))
        status, headers, body = self.fetch("/explore", {})
        self.assertEqual(status, 200)
        form = body.split(b'value="disagreements">', 1)[1].split(b"</form>", 1)[0]
        self.assertIn(b'name="source"', form)
        self.assertIn(b'list="saved-original-sources"', form)
        self.assertIn("connect-src 'none'", headers["Content-Security-Policy"])

    def test_invalid_source_rejected_not_silently_ignored(self):
        for route, query in (
            ("/map-disagreements", {**QUERY, "source": "../survey-east"}),
            ("/viewer", {"view": "disagreements", **QUERY, "source": "bad<script>"}),
            ("/map-disagreements", {**QUERY, "source": "survey-east", "extra": "x"}),
            ("/viewer", {"view": "disagreements", **QUERY, "source": "a b"}),
        ):
            status, _, body = self.fetch(route, query)
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(body), {"error": "invalid_query"})


if __name__ == "__main__":
    unittest.main()
