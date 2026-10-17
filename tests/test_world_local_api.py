"""End-to-end loopback HTTP tests for the evidence-only MONDE Mini API."""
import copy
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from monde.local_api import create_server
from monde.world import WorldMini
from tests.test_world_mini import DOC, AT, LATE


class LocalAPIIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.state = Path(self.tempdir.name) / "world.json"
        WorldMini.from_document(copy.deepcopy(DOC)).save(self.state)
        self.original = self.state.read_bytes()
        self.server = create_server(self.state)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()
        self.assertEqual(self.state.read_bytes(), self.original)
        self.tempdir.cleanup()

    def request(self, path, *, method="GET", host=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        headers = {"Host": host or ("127.0.0.1:" + str(self.server.server_port))}
        conn.request(method, path, headers=headers)
        res = conn.getresponse()
        body = res.read()
        result = (res.status, dict(res.getheaders()), json.loads(body))
        conn.close()
        return result

    def path(self, endpoint, **args):
        return endpoint + ("?" + urlencode(args) if args else "")

    def test_health_is_explicitly_read_only(self):
        code, headers, result = self.request("/health")
        self.assertEqual(code, 200)
        self.assertEqual(result["mode"], "READ_ONLY")
        self.assertEqual(result["world"], "OBSERVED")
        self.assertIn("application/json", headers["Content-Type"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_reports_retain_conflicting_sources_at_two_knowledge_cutoffs(self):
        url = self.path("/reports", entity="building-001",
                        attribute="floors", at=AT, known_at=LATE)
        code, _, result = self.request(url)
        self.assertEqual(code, 200)
        self.assertEqual({r["source_id"] for r in result["reports"]},
                         {"local-news", "city-registry"})
        self.assertTrue(all(r["evidence_id"] and r["locator"]
                            for r in result["reports"]))
        _, _, older = self.request(self.path("/reports",
            entity="building-001", attribute="floors", at=AT,
            known_at="2026-01-03T09:59:59Z"))
        self.assertEqual(older["status"], "UNKNOWN")
        self.assertEqual(older["reports"], [])

    def test_entity_and_source_disagreements_use_same_world(self):
        code, _, entity = self.request(self.path("/entity",
            entity="building-001", at=AT, known_at=LATE))
        self.assertEqual(code, 200)
        self.assertEqual(entity["world"], "OBSERVED")
        self.assertEqual(len(entity["attributes"]["floors"]["reports"]), 2)
        code, _, dispute = self.request(self.path("/disagreements",
            at=AT, known_at=LATE, attribute="floors"))
        self.assertEqual(code, 200)
        item = next(x for x in dispute["disagreements"]
                    if x["entity"] == "building-001")
        self.assertEqual(len(item["value_groups"]), 2)

    def test_map_serves_original_point_evidence_without_inventing_position(self):
        code, _, result = self.request(self.path("/map", bbox="1,45,6,51",
                                                 at=AT, known_at=LATE))
        self.assertEqual(code, 200)
        self.assertEqual(result["type"], "FeatureCollection")
        self.assertEqual(result["monde_bbox_query"]["basis"],
                         "SOURCE_REPORTED_POINT_BBOX_ONLY")

    def test_mutation_methods_have_no_effect(self):
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            code, _, result = self.request("/reports", method=method)
            self.assertEqual(code, 405, method)
            self.assertEqual(result["error"], "read_only")

    def test_invalid_time_bbox_fields_and_path_return_json_errors(self):
        examples = [
            self.path("/reports", entity="building-001",
                      attribute="floors", at="2026-bogus", known_at=LATE),
            self.path("/reports", entity="building-001", attribute="floors",
                      at=AT, known_at=LATE) + "&entity=other",
            self.path("/reports", entity="building-001", attribute="floors",
                      at=AT, known_at=LATE) + "&token=secret",
            self.path("/map", bbox="0,0,500,90", at=AT, known_at=LATE),
            self.path("/map", bbox="inf,0,20,10", at=AT, known_at=LATE),
            self.path("/map", bbox="1,2,3", at=AT, known_at=LATE),
        ]
        for url in examples:
            with self.subTest(url=url):
                code, _, result = self.request(url)
                self.assertEqual(code, 400)
                self.assertEqual(result["error"], "invalid_query")
        code, _, result = self.request("/raw-state.json")
        self.assertEqual(code, 404)
        self.assertEqual(result["error"], "unknown_endpoint")

    def test_dns_rebinding_host_header_rejected(self):
        for host in ("evil.example", "evil.example:" + str(self.server.server_port),
                     "127.0.0.1:9999"):
            code, _, result = self.request("/health", host=host)
            self.assertEqual(code, 403, host)
            self.assertEqual(result["error"], "loopback_host_required")

    def test_original_state_remains_a_fixed_snapshot(self):
        before = self.request(self.path("/reports", entity="building-001",
            attribute="floors", at=AT, known_at=LATE))[2]
        self.state.write_text('{"corrupted":true}', encoding="utf-8")
        self.assertEqual(self.request(self.path("/reports",
            entity="building-001", attribute="floors", at=AT, known_at=LATE))[2], before)
        self.state.write_bytes(self.original)

    def test_large_result_is_bounded(self):
        small = create_server(self.state, max_response_bytes=256)
        thread = threading.Thread(target=small.serve_forever, daemon=True)
        thread.start()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", small.server_port, timeout=5)
            conn.request("GET", "/entity?" + urlencode({
                "entity": "building-001", "at": AT, "known_at": LATE}))
            result = conn.getresponse()
            self.assertEqual(result.status, 413)
            self.assertEqual(json.loads(result.read())["error"], "response_too_large")
            conn.close()
        finally:
            small.shutdown()
            thread.join(timeout=5)
            small.server_close()


if __name__ == "__main__":
    unittest.main()
