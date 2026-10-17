"""Real HTTP integration: original source Point maps across two clocks."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from monde.local_api import create_server
from tests.test_world_geojson_changes import model as change_model, correct, AT, K0, K1, K2
from tests.test_world_geojson_disagreements import disputed

BBOX = [2.3, 48.8, 2.4, 48.9]
EARLIER = "2025-12-31T00:00:00Z"


class LocalMapChangesHTTPTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.file = Path(self.dir.name) / "world.json"
        self.world = change_model()
        correct(self.world)
        self.world.save(str(self.file))
        self.original = self.file.read_bytes()
        self.server = create_server(self.file)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()
        self.assertEqual(self.file.read_bytes(), self.original)
        self.dir.cleanup()

    def fetch(self, route, args, server=None, host=None):
        s = server or self.server
        connection = http.client.HTTPConnection("127.0.0.1", s.server_port, timeout=5)
        connection.request("GET", route + "?" + urlencode(args), headers={
            "Host": host or "127.0.0.1:" + str(s.server_port)})
        reply = connection.getresponse()
        status, headers, body = reply.status, dict(reply.getheaders()), json.loads(reply.read())
        connection.close()
        return status, headers, body

    def test_newly_known_correction_keeps_old_and_new_source_geometry(self):
        q = dict(bbox="2.3,48.8,2.4,48.9", at=AT, from_known_at=K1, to_known_at=K2)
        status, headers, actual = self.fetch("/map-knowledge-changes", q)
        self.assertEqual(status, 200)
        self.assertEqual(actual, self.world.export_geojson_bbox_knowledge_changes(
            BBOX, AT, K1, K2))
        self.assertEqual(actual["type"], "FeatureCollection")
        kinds = {f["properties"]["monde_change"]: f for f in actual["features"]}
        self.assertIn("NO_LONGER_CURRENT", kinds)
        self.assertIn("NEWLY_CURRENT", kinds)
        self.assertTrue(kinds["NO_LONGER_CURRENT"]["properties"]["monde_inside_bbox"])
        self.assertFalse(kinds["NEWLY_CURRENT"]["properties"]["monde_inside_bbox"])
        self.assertTrue(all(f["properties"]["monde_change_basis"] ==
                            "KNOWLEDGE_NOT_PHYSICAL" and f["properties"]["evidence_id"]
                            for f in actual["features"]))
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_world_validity_transition_is_not_claimed_as_physical_motion(self):
        q = dict(bbox="2.3,48.8,2.4,48.9", from_at=EARLIER, to_at=AT, known_at=K1)
        status, _, got = self.fetch("/map-world-changes", q)
        self.assertEqual(status, 200)
        self.assertEqual(got, self.world.export_geojson_bbox_world_changes(
            BBOX, EARLIER, AT, K1))
        self.assertTrue(got["features"])
        self.assertTrue(all(f["properties"]["monde_change_basis"] ==
                            "REPORTED_VALIDITY_NOT_VERIFIED_MOTION"
                            for f in got["features"]))

    def test_spatial_disagreement_keeps_identity_of_offscreen_source(self):
        model = disputed()
        path = Path(self.dir.name) / "disputed.json"
        model.save(str(path))
        before = path.read_bytes()
        server = create_server(path)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            status, _, got = self.fetch("/map-disagreements",
                dict(bbox="2.3,48.8,2.4,48.9", at=AT, known_at=K1), server)
            self.assertEqual(status, 200)
            self.assertEqual(got, model.export_geojson_disagreements(AT, K1, BBOX))
            self.assertEqual(len(got["features"]), 1)
            props = got["features"][0]["properties"]
            self.assertEqual(props["monde_conflicting_source_ids"],
                             ["survey-east", "survey-west"])
            self.assertTrue(props["evidence_id"])
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
        self.assertEqual(path.read_bytes(), before)

    def test_invalid_times_bounds_and_authority_rejected(self):
        base = dict(bbox="2.3,48.8,2.4,48.9", at=AT,
                    from_known_at=K1, to_known_at=K2)
        cases = [
            ("/map-knowledge-changes", {**base, "bbox": "oops"}),
            ("/map-knowledge-changes", {**base, "to_known_at": K0}),
            ("/map-knowledge-changes", {**base, "unexpected": "anything"}),
            ("/map-world-changes", dict(bbox=base["bbox"], from_at=AT,
                                        to_at=EARLIER, known_at=K2)),
            ("/map-disagreements", dict(bbox="200,0,250,1", at=AT, known_at=K2)),
        ]
        for endpoint, parameters in cases:
            with self.subTest(endpoint=endpoint, parameters=parameters):
                status, _, result = self.fetch(endpoint, parameters)
                self.assertEqual((status, result), (400, {"error": "invalid_query"}))
        status, _, result = self.fetch("/map-knowledge-changes", base,
                                      host="untrusted.example")
        self.assertEqual(status, 403)
        self.assertEqual(result["error"], "loopback_host_required")

    def test_empty_viewport_exposes_no_imagined_features(self):
        q = dict(bbox="10,10,11,11", at=AT, from_known_at=K1, to_known_at=K2)
        status, _, result = self.fetch("/map-knowledge-changes", q)
        self.assertEqual(status, 200)
        self.assertEqual(result["features"], [])
        self.assertEqual(result["monde_bbox_changes_query"]["status"], "NO_CHANGES")
