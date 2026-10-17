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
from tests.test_world_spatial import model as spatial_model, CAPTURED as SPATIAL_K


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

    def request(self, path, *, method="GET", host=None, port=None):
        port = self.server.server_port if port is None else port
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        headers = {"Host": host or ("127.0.0.1:" + str(port))}
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

    def test_spatial_navigation_over_real_local_http(self):
        """One persisted spatial model serves tiles and provenance-preserving proximity."""
        spatial = spatial_model()
        spatial_path = Path(self.tempdir.name) / "spatial.json"
        spatial.save(spatial_path)
        original = spatial_path.read_bytes()
        server = create_server(spatial_path)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            cases = [
                ("/tile", {"z": 5, "x": 16, "y": 11, "at": AT,
                           "known_at": SPATIAL_K},
                 spatial.export_geojson_tile(5, 16, 11, AT, SPATIAL_K)),
                ("/nearest", {"center": "2.3522,48.8566", "limit": 1,
                              "at": AT, "known_at": SPATIAL_K},
                 spatial.export_geojson_nearest([2.3522, 48.8566], 1, AT, SPATIAL_K)),
                ("/radius", {"center": "2.3522,48.8566", "radius_km": 10,
                             "at": AT, "known_at": SPATIAL_K},
                 spatial.export_geojson_radius([2.3522, 48.8566], 10, AT, SPATIAL_K)),
            ]
            for endpoint, args, expected in cases:
                with self.subTest(endpoint=endpoint):
                    code, _, result = self.request(self.path(endpoint, **args),
                                                    port=server.server_port)
                    self.assertEqual(code, 200)
                    self.assertEqual(result, expected)
                    self.assertEqual(result["type"], "FeatureCollection")
                    self.assertTrue(result["features"])
                    self.assertTrue(all(f["properties"]["source_id"] == "example-map"
                                        and f["properties"]["evidence_id"]
                                        for f in result["features"]))
            _, _, too_early = self.request(self.path(
                "/nearest", center="2.3522,48.8566", limit=1, at=AT,
                known_at="2026-01-10T09:59:59Z"), port=server.server_port)
            self.assertEqual(too_early["features"], [])
        finally:
            server.shutdown()
            worker.join(timeout=5)
            server.server_close()
        self.assertEqual(spatial_path.read_bytes(), original)

    def test_new_spatial_endpoints_reject_bad_inputs(self):
        for endpoint, params in [
            ("/tile", {"z": -1, "x": 0, "y": 0}),
            ("/tile", {"z": 23, "x": 0, "y": 0}),
            ("/tile", {"z": 4, "x": 16, "y": 0}),
            ("/tile", {"z": "bad", "x": 0, "y": 0}),
            ("/nearest", {"center": "2.3", "limit": 1}),
            ("/nearest", {"center": "200,48", "limit": 1}),
            ("/nearest", {"center": "2,48", "limit": 0}),
            ("/radius", {"center": "2,48", "radius_km": -1}),
            ("/radius", {"center": "nan,48", "radius_km": 10}),
            ("/radius", {"center": "2,48", "radius_km": "inf"}),
        ]:
            with self.subTest(endpoint=endpoint, params=params):
                code, _, result = self.request(self.path(
                    endpoint, **params, at=AT, known_at=LATE))
                self.assertEqual(code, 400)
                self.assertEqual(result["error"], "invalid_query")

    def test_temporal_investigation_over_real_http(self):
        """Existing WorldMini history and two clocks are exposed without recomputation."""
        model = WorldMini.from_document(copy.deepcopy(DOC))
        start = "2025-12-31T00:00:00Z"
        older = "2026-01-03T09:59:59Z"
        cases = [
            ("/timeline",
             {"entity": "building-001", "attribute": "floors", "from_at": start,
              "to_at": AT, "known_at": LATE},
             model.timeline("building-001", "floors", start, AT, LATE)),
            ("/compare-knowledge",
             {"entity": "building-001", "at": AT,
              "from_known_at": older, "to_known_at": LATE},
             model.compare_knowledge("building-001", AT, older, LATE)),
            ("/compare-world",
             {"entity": "building-001", "from_at": start, "to_at": AT,
              "known_at": LATE},
             model.compare_world_time("building-001", start, AT, LATE)),
            ("/source-history", {"source": "city-registry", "known_at": LATE,
                                 "entity": "building-001", "attribute": "floors"},
             model.source_history("city-registry", LATE, "building-001", "floors")),
            ("/disagreement-changes",
             {"at": AT, "from_known_at": older, "to_known_at": LATE,
              "attribute": "floors"},
             model.source_disagreement_changes(AT, older, LATE, "floors")),
        ]
        for endpoint, args, expected in cases:
            with self.subTest(endpoint=endpoint):
                code, headers, result = self.request(self.path(endpoint, **args))
                self.assertEqual(code, 200)
                self.assertEqual(result, expected)
                self.assertEqual(result["world"], "OBSERVED")
                self.assertEqual(headers["Cache-Control"], "no-store")
                self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_source_corrections_keep_original_provenance_via_http(self):
        url = self.path("/source-history", source="city-registry",
                        known_at=LATE, entity="building-001", attribute="floors")
        code, _, result = self.request(url)
        self.assertEqual(code, 200)
        self.assertEqual(result["view"], "SOURCE_ASSERTION_HISTORY_ONLY")
        self.assertTrue(result["reports"])
        for report in result["reports"]:
            self.assertEqual(report["source_id"], "city-registry")
            self.assertTrue(report["evidence_id"])
            self.assertTrue(report["locator"])
            self.assertIn("source_event_at", report)
            self.assertIn("captured_at", report)
        code, _, missing = self.request(self.path(
            "/source-history", source="city-registry",
            known_at="2025-01-01T00:00:00Z", entity="building-001"))
        self.assertEqual(code, 200)
        self.assertEqual(missing["status"], "NO_REPORTS")

    def test_knowledge_change_feed_over_real_http(self):
        """Existing WorldMini methods are exposed with unchanged provenance and clocks."""
        model = WorldMini.from_document(copy.deepcopy(DOC))
        older = "2026-01-03T09:59:59Z"
        cases = [
            ("/knowledge-updates",
             {"from_known_at": older, "to_known_at": LATE,
              "entity": "building-001", "attribute": "floors"},
             model.knowledge_updates(older, LATE, "building-001", "floors")),
            ("/knowledge-timeline",
             {"entity": "building-001", "attribute": "floors", "at": AT,
              "from_known_at": older, "to_known_at": LATE},
             model.knowledge_timeline("building-001", "floors", AT, older, LATE)),
            ("/world-knowledge-changes",
             {"at": AT, "from_known_at": older, "to_known_at": LATE},
             model.world_knowledge_changes(AT, older, LATE)),
        ]
        for route, params, expected in cases:
            with self.subTest(route=route):
                status, headers, result = self.request(self.path(route, **params))
                self.assertEqual(status, 200)
                self.assertEqual(result, expected)
                self.assertEqual(result["world"], "OBSERVED")
                self.assertEqual(headers["Cache-Control"], "no-store")
                self.assertNotIn("Access-Control-Allow-Origin", headers)
        self.assertTrue(cases[0][2]["reports"])
        self.assertTrue(all(entry["source_id"] and entry["evidence_id"]
                            and entry["locator"] for entry in cases[0][2]["reports"]))
        self.assertTrue(cases[1][2]["segments"])
        self.assertTrue(cases[2][2]["entities"])

    def test_knowledge_change_feed_rejects_invalid_ranges_and_filters(self):
        older = "2026-01-03T09:59:59Z"
        examples = [
            ("/knowledge-updates", {"from_known_at": LATE, "to_known_at": older}),
            ("/knowledge-updates", {"from_known_at": older, "to_known_at": older}),
            ("/knowledge-updates", {"from_known_at": older, "to_known_at": LATE,
                                    "entity": "bad entity"}),
            ("/knowledge-updates", {"from_known_at": older, "to_known_at": LATE,
                                    "unknown": "value"}),
            ("/knowledge-timeline", {"entity": "building-001", "attribute": "floors",
                                     "at": AT, "from_known_at": LATE,
                                     "to_known_at": older}),
            ("/knowledge-timeline", {"entity": "building-001", "attribute": "floors",
                                     "at": AT, "from_known_at": older}),
            ("/world-knowledge-changes", {"at": AT, "from_known_at": LATE,
                                          "to_known_at": older}),
            ("/world-knowledge-changes", {"at": AT, "from_known_at": older,
                                          "to_known_at": "not-a-time"}),
            ("/world-knowledge-changes", {"from_known_at": older, "to_known_at": LATE}),
        ]
        for route, params in examples:
            with self.subTest(route=route, params=params):
                code, _, result = self.request(self.path(route, **params))
                self.assertEqual(code, 400)
                self.assertEqual(result["error"], "invalid_query")
        valid = self.path("/knowledge-updates", from_known_at=older, to_known_at=LATE)
        code, _, result = self.request(valid + "&to_known_at=" + LATE)
        self.assertEqual(code, 400)
        self.assertEqual(result["error"], "invalid_query")

    def test_temporal_endpoints_reject_ambiguous_or_invalid_ranges(self):
        cases = [
            ("/timeline", {"entity": "building-001", "attribute": "floors",
                           "from_at": AT, "to_at": AT, "known_at": LATE}),
            ("/compare-knowledge", {"entity": "building-001", "at": AT,
                                     "from_known_at": LATE, "to_known_at": LATE}),
            ("/compare-world", {"entity": "building-001", "from_at": AT,
                                 "to_at": "garbage", "known_at": LATE}),
            ("/disagreement-changes", {"at": AT, "from_known_at": LATE,
                                       "to_known_at": "2025-01-01T00:00:00Z"}),
            ("/source-history", {"source": "city-registry", "known_at": "bad"}),
            ("/source-history", {"source": "city-registry", "known_at": LATE,
                                "not_a_filter": "unexpected"}),
            ("/timeline", {"entity": "building-001", "attribute": "floors",
                           "from_at": AT, "to_at": LATE}),  # missing known_at
        ]
        for endpoint, args in cases:
            with self.subTest(endpoint=endpoint, args=args):
                status, _, data = self.request(self.path(endpoint, **args))
                self.assertEqual(status, 400)
                self.assertEqual(data["error"], "invalid_query")

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
