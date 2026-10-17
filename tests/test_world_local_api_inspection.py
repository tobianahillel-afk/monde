"""Browser inspection of original source assertions and corrections."""
import copy
import http.client
from html.parser import HTMLParser
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import urlencode, urlsplit, parse_qs

from monde.local_api import _inspection_html, create_server
from tests.test_world_geojson_changes import model as change_model, correct, AT as GEO_AT, VALID as GEO_VALID, K2 as GEO_K2
from monde.world import WorldMini
from tests.test_world_mini import DOC, AT, LATE


class EvidenceInspectorTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "world.json"
        self.world = WorldMini.from_document(copy.deepcopy(DOC))
        self.world.save(self.path)
        self.original = self.path.read_bytes()
        self.server = create_server(self.path)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.worker.join(timeout=5)
        self.server.server_close()
        self.assertEqual(self.path.read_bytes(), self.original)
        self.dir.cleanup()

    def fetch(self, endpoint="/inspect", params=None, *, host=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        target = endpoint + ("?" + urlencode(params) if params is not None else "")
        connection.request("GET", target, headers={
            "Host": host if host is not None else "127.0.0.1:" + str(self.server.server_port)
        })
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def test_explore_links_inspector_and_native_forms(self):
        status, _, explore = self.fetch("/explore")
        self.assertEqual(status, 200)
        self.assertIn(b'href="/inspect"', explore)
        code, headers, document = self.fetch()
        self.assertEqual(code, 200)
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertIn("script-src 'none'", headers["Content-Security-Policy"])
        self.assertNotIn(b"<script", document)
        class Forms(HTMLParser):
            def __init__(self):
                super().__init__()
                self.forms = []
            def handle_starttag(self, tag, attributes):
                if tag == "form":
                    self.forms.append(dict(attributes))
        forms = Forms()
        forms.feed(document.decode("utf-8"))
        self.assertEqual(len(forms.forms), 5)
        self.assertTrue(all(f.get("action") == "/inspect" and f.get("method") == "get"
                            for f in forms.forms))

    def test_html_matches_original_model_reports_not_estimates(self):
        cases = (
            ("entity", dict(entity="building-001", at=AT, known_at=LATE),
             self.world.entity_snapshot("building-001", AT, LATE)),
            ("reports", dict(entity="building-001", attribute="floors", at=AT,
                             known_at=LATE),
             self.world.query("building-001", "floors", AT, LATE)),
            ("source-history", dict(source="city-registry", known_at=LATE),
             self.world.source_history("city-registry", LATE)),
        )
        for view, values, expected in cases:
            with self.subTest(view=view):
                status, headers, body = self.fetch(params={"view": view, **values})
                self.assertEqual(status, 200)
                self.assertEqual(headers["Cache-Control"], "no-store")
                self.assertEqual(headers["X-Frame-Options"], "DENY")
                self.assertIn("script-src 'none'", headers["Content-Security-Policy"])
                self.assertIn("connect-src 'none'", headers["Content-Security-Policy"])
                self.assertNotIn("Access-Control-Allow-Origin", headers)
                self.assertEqual(headers["Content-Length"], str(len(body)))
                content = body.decode("utf-8")
                self.assertIn("Original source assertions only", content)
                self.assertIn("View complete original JSON response", content)
                self.assertNotIn("<script", content)
                from html import escape
                if view == "entity":
                    reports = [r for value in expected["attributes"].values()
                               for r in value["reports"]]
                else:
                    reports = expected["reports"]
                for report in reports:
                    # Report JSON is present in full, with the same values and provenance.
                    self.assertIn(escape(json.dumps(report, ensure_ascii=False,
                        sort_keys=True, indent=2, allow_nan=False)), content)
                self.assertEqual(self.path.read_bytes(), self.original)

    def test_unknown_is_not_false_and_source_history_accepts_filters(self):
        status, _, body = self.fetch(params={"view": "reports", "entity": "building-001",
            "attribute": "nonexistent", "at": AT, "known_at": LATE})
        self.assertEqual(status, 200)
        self.assertIn(b"UNKNOWN", body)
        self.assertIn(b"no matching source report", body)
        status, _, body = self.fetch(params={"view": "source-history",
            "source": "city-registry", "known_at": LATE,
            "entity": "building-001", "attribute": "floors"})
        self.assertEqual(status, 200)
        expected = self.world.source_history("city-registry", LATE,
                                             "building-001", "floors")
        for report in expected["reports"]:
            self.assertIn(report["assertion_id"].encode(), body)

    def test_untrusted_source_fields_cannot_inject_markup_or_script(self):
        malicious = "<script>alert('x')</script><img src=x onerror=alert(1)>"
        payload = {"world": "OBSERVED", "status": "REPORTED",
                   "reports": [{"source_id": malicious, "assertion_id": malicious,
                                "value": malicious, "locator": malicious}]}
        html = _inspection_html(payload, "reports", {"view": "reports",
            "entity": "building-001", "attribute": "floors", "at": AT,
            "known_at": LATE})
        self.assertNotIn("<script", html)
        self.assertNotIn("<img", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&lt;img", html)

    def test_evidence_inspector_returns_to_the_actual_source_point_on_map(self):
        """Follow a real dossier link through the loopback server, not a mock URL."""
        model = change_model()
        correct(model)
        state = Path(self.dir.name) / "geographic.json"
        model.save(state)
        original = state.read_bytes()
        server = create_server(state)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()

        def retrieve(target):
            conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            try:
                conn.request("GET", target, headers={
                    "Host": "127.0.0.1:" + str(server.server_port)})
                response = conn.getresponse()
                return response.status, response.read().decode("utf-8")
            finally:
                conn.close()

        class MapLinks(HTMLParser):
            def __init__(self):
                super().__init__()
                self.links = []
            def handle_starttag(self, tag, attributes):
                if tag == "a":
                    href = dict(attributes).get("href", "")
                    if href.startswith("/viewer?"):
                        self.links.append(href)

        try:
            for view, query in (
                ("entity", dict(entity="site-a", at=GEO_AT, known_at=GEO_K2)),
                ("reports", dict(entity="site-a", attribute="geo_point",
                                 at=GEO_AT, known_at=GEO_K2)),
                ("source-history", dict(source="survey-1", entity="site-a",
                                        attribute="geo_point", known_at=GEO_K2)),
            ):
                with self.subTest(view=view):
                    target = "/inspect?" + urlencode({"view": view, **query})
                    status, body = retrieve(target)
                    self.assertEqual(status, 200)
                    anchors = MapLinks()
                    anchors.feed(body)
                    self.assertTrue(anchors.links, "Missing source-map navigation")
                    for href in anchors.links:
                        parts = urlsplit(href)
                        values = {k: v[0] for k, v in parse_qs(parts.query).items()}
                        self.assertEqual(parts.path, "/viewer")
                        self.assertEqual(values["view"], "radius")
                        self.assertEqual(values["known_at"], GEO_K2)
                        self.assertEqual(values["radius_km"], "1")
                        self.assertEqual(len(values["center"].split(",")), 2)
                        self.assertEqual(values["at"], GEO_VALID if view == "source-history" else GEO_AT)
                        code, map_html = retrieve(href)
                        self.assertEqual(code, 200)
                        self.assertIn("MONDE Mini", map_html)
                        self.assertIn("Original source", map_html)
            # Links do not change saved source evidence.
            self.assertEqual(state.read_bytes(), original)
        finally:
            server.shutdown()
            worker.join(timeout=5)
            server.server_close()

    def test_only_valid_current_geopoints_get_map_links(self):
        point = {"type": "Point", "coordinates": [2.35, 48.85]}
        original = {
            "attribute": "geo_point", "source_id": "survey-1",
            "assertion_id": "point-1", "value": point, "valid_from": GEO_AT,
            "current_at_cutoff": True,
        }
        params = {"view": "source-history", "source": "survey-1",
                  "known_at": GEO_K2}
        def show(*reports):
            return _inspection_html({"world": "OBSERVED", "status": "HISTORY_FOUND",
                                     "reports": list(reports)}, "source-history", params)
        current = show(original)
        self.assertEqual(current.count('href="/viewer?'), 1)
        retired = show({**original, "current_at_cutoff": False})
        self.assertNotIn('href="/viewer?', retired)
        other = show({**original, "attribute": "name"})
        self.assertNotIn('href="/viewer?', other)
        malicious = show({**original, "value": {
            "type": "Point", "coordinates": ['<img src=x onerror=1>', 48.85]}})
        self.assertNotIn('href="/viewer?', malicious)
        self.assertIn("&lt;img", malicious)
        no_point = _inspection_html({"world": "OBSERVED", "status": "UNKNOWN",
                                    "attributes": {}}, "entity",
                                    {"view": "entity", "entity": "site-a",
                                     "at": GEO_AT, "known_at": GEO_K2})
        self.assertIn("UNKNOWN", no_point)
        self.assertNotIn('href="/viewer?', no_point)

    def test_rejects_wrong_modes_parameters_origins_and_mutations(self):
        requests = (
            {"view": "entity", "entity": "building-001", "known_at": LATE},
            {"view": "entity", "entity": "building-001", "at": AT,
             "known_at": LATE, "surprise": "x"},
            {"view": "reports", "entity": "building-001", "attribute": "floors",
             "at": "not-a-date", "known_at": LATE},
            {"view": "source-history", "source": "city-registry",
             "known_at": LATE, "bogus": "x"},
            {"view": "ACTIVE_4"},
        )
        for query in requests:
            with self.subTest(query=query):
                code, _, result = self.fetch(params=query)
                self.assertEqual((code, json.loads(result)), (400, {"error": "invalid_query"}))
        code, _, result = self.fetch("/inspect?view=entity&view=entity&entity=building-001&at=" +
                                      AT + "&known_at=" + LATE)
        self.assertEqual((code, json.loads(result)), (400, {"error": "invalid_query"}))
        code, _, body = self.fetch(host="attacker.example")
        self.assertEqual((code, json.loads(body)), (403, {"error": "loopback_host_required"}))
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_browser_knowledge_comparison_has_original_provenance_and_json_parity(self):
        before = "2026-01-05T00:00:00Z"
        params = {"view": "compare-knowledge", "entity": "building-001",
                  "at": AT, "from_known_at": before, "to_known_at": LATE}
        code, headers, body = self.fetch(params=params)
        self.assertEqual(code, 200)
        self.assertIn("script-src 'none'", headers["Content-Security-Policy"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["Content-Length"], str(len(body)))
        html = body.decode("utf-8")
        expected = self.world.compare_knowledge("building-001", AT, before, LATE)
        self.assertEqual(expected["status"], "CHANGED")
        self.assertIn("Newly current", html)
        self.assertIn("No longer current", html)
        self.assertIn("Knowledge changes are not verified physical", html)
        self.assertIn("/compare-knowledge?", html)
        from html import escape
        for change in expected["changes"].values():
            for report in change["newly_current"] + change["no_longer_current"]:
                self.assertIn(escape(json.dumps(report, ensure_ascii=False,
                    sort_keys=True, indent=2, allow_nan=False)), html)
        raw_params = {k: v for k, v in params.items() if k != "view"}
        status, _, original = self.fetch("/compare-knowledge", raw_params)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(original), expected)
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_browser_knowledge_comparison_unchanged_and_invalid_inputs(self):
        params = {"view": "compare-knowledge", "entity": "building-001",
                  "at": AT, "from_known_at": LATE,
                  "to_known_at": "2026-01-08T00:00:00Z"}
        status, _, body = self.fetch(params=params)
        self.assertEqual(status, 200)
        self.assertIn(b"UNCHANGED", body)
        self.assertNotIn(b"UNKNOWN \xe2\x80\x94 no matching", body)
        for changed in ({"to_known_at": LATE},
                        {"to_known_at": "2026-01-04T00:00:00Z"},
                        {"at": "invalid"},
                        {"unexpected": "overwrite"}):
            code, _, body = self.fetch(params={**params, **changed})
            self.assertEqual((code, json.loads(body)),
                             (400, {"error": "invalid_query"}))
        code, _, body = self.fetch("/inspect?view=compare-knowledge&" +
                                    urlencode(params))
        self.assertEqual((code, json.loads(body)),
                         (400, {"error": "invalid_query"}))
        code, _, body = self.fetch(params={**params,
            "entity": "<img src=x onerror=alert(1)>"})
        self.assertEqual((code, json.loads(body)),
                         (400, {"error": "invalid_query"}))

    def test_browser_knowledge_correction_links_old_and_new_points_to_correct_cutoffs(self):
        from tests.test_world_geojson_changes import K1 as GEO_K1
        geographic = change_model()
        original_report = correct(geographic)
        state = Path(self.dir.name) / "geographic-compare.json"
        geographic.save(state)
        saved = state.read_bytes()
        server = create_server(state)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        def read(target):
            conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            try:
                conn.request("GET", target, headers={
                    "Host": "127.0.0.1:" + str(server.server_port)})
                response = conn.getresponse()
                return response.status, response.read().decode("utf-8")
            finally:
                conn.close()
        class MapLinks(HTMLParser):
            def __init__(self):
                super().__init__()
                self.links = []
            def handle_starttag(self, tag, attributes):
                if tag == "a":
                    href = dict(attributes).get("href", "")
                    if href.startswith("/viewer?"):
                        self.links.append(href)
        try:
            params = {"view": "compare-knowledge", "entity": "site-a",
                      "at": GEO_AT, "from_known_at": GEO_K1, "to_known_at": GEO_K2}
            code, body = read("/inspect?" + urlencode(params))
            self.assertEqual(code, 200)
            self.assertIn(original_report["assertion_id"], body)
            self.assertIn("correct-a", body)
            parser = MapLinks()
            parser.feed(body)
            self.assertEqual(len(parser.links), 3)
            located = {}
            comparison = None
            for link in parser.links:
                parsed = urlsplit(link)
                args = {k: v[0] for k, v in parse_qs(parsed.query).items()}
                self.assertEqual(parsed.path, "/viewer")
                if args["view"] == "knowledge-changes":
                    comparison = args
                    self.assertEqual(args["at"], GEO_AT)
                    self.assertEqual(args["from_known_at"], GEO_K1)
                    self.assertEqual(args["to_known_at"], GEO_K2)
                else:
                    self.assertEqual(args["view"], "radius")
                    self.assertEqual(args["at"], GEO_AT)
                    located[args["known_at"]] = args["center"]
                map_code, map_html = read(link)
                self.assertEqual(map_code, 200)
                self.assertIn("MONDE Mini", map_html)
            self.assertIsNotNone(comparison)
            code, raw = read("/map-knowledge-changes?" + urlencode({
                key: value for key, value in comparison.items() if key != "view"}))
            self.assertEqual(code, 200)
            self.assertEqual({f["properties"]["monde_change"]
                              for f in json.loads(raw)["features"]},
                             {"NO_LONGER_CURRENT", "NEWLY_CURRENT"})
            self.assertEqual(located, {
                GEO_K1: "2.35,48.85", GEO_K2: "3.25,49.1"})
            self.assertEqual(state.read_bytes(), saved)
        finally:
            server.shutdown()
            worker.join(timeout=5)
            server.server_close()

    def test_browser_world_comparison_uses_existing_world_model_and_json(self):
        params = {"view": "compare-world", "entity": "building-001",
                  "from_at": "2025-12-31T00:00:00Z", "to_at": AT, "known_at": LATE}
        code, headers, content = self.fetch(params=params)
        self.assertEqual(code, 200)
        self.assertIn("script-src 'none'", headers["Content-Security-Policy"])
        self.assertIn("no-store", headers["Cache-Control"])
        html = content.decode("utf-8")
        expected = self.world.compare_world_time("building-001",
            params["from_at"], params["to_at"], LATE)
        self.assertEqual(expected["status"], "CHANGED")
        self.assertEqual(expected["comparison"], "WORLD_TIME_REPORTS_ONLY")
        self.assertIn("Reported at later world time", html)
        self.assertIn("source assertions", html)
        from html import escape
        for delta in expected["changes"].values():
            for report in delta["newly_current"] + delta["no_longer_current"]:
                self.assertIn(escape(json.dumps(report, ensure_ascii=False,
                    sort_keys=True, indent=2, allow_nan=False)), html)
        raw = {k: v for k, v in params.items() if k != "view"}
        status, _, body = self.fetch("/compare-world", raw)
        self.assertEqual((status, json.loads(body)), (200, expected))
        stable = {**params, "from_at": AT, "to_at": "2026-01-03T00:00:00Z"}
        status, _, body = self.fetch(params=stable)
        self.assertEqual(status, 200)
        self.assertIn(b"UNCHANGED", body)
        for broken in ({"to_at": params["from_at"]},
                       {"from_at": params["to_at"]},
                       {"known_at": "not-a-date"},
                       {"unexpected": "oops"}):
            status, _, body = self.fetch(params={**params, **broken})
            self.assertEqual((status, json.loads(body)),
                             (400, {"error": "invalid_query"}))
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_browser_world_comparison_map_links_keep_original_world_cutoffs(self):
        from tests.test_world_geojson_changes import K1 as GEO_K1
        world = change_model()
        world.append_document({
            "schema_version": 1,
            "evidence": [
                {"id": "e-old-location", "source_id": "historical-survey",
                 "locator": "fixture://old-location", "captured_at": GEO_K1,
                 "source_event_at": None},
                {"id": "e-new-location", "source_id": "updated-survey",
                 "locator": "fixture://new-location", "captured_at": GEO_K1,
                 "source_event_at": None}],
            "assertions": [
                {"id": "a-old-location", "entity": "site-a", "attribute": "geo_point",
                 "value": {"type": "Point", "coordinates": [2.0, 48.0]},
                 "evidence_id": "e-old-location", "kind": "CLAIM",
                 "known_at": GEO_K1, "valid_from": GEO_VALID,
                 "valid_to": "2026-01-03T00:00:00Z", "supersedes": None},
                {"id": "a-new-location", "entity": "site-a", "attribute": "geo_point",
                 "value": {"type": "Point", "coordinates": [3.0, 49.0]},
                 "evidence_id": "e-new-location", "kind": "CLAIM",
                 "known_at": GEO_K1, "valid_from": "2026-01-03T00:00:00Z",
                 "valid_to": None, "supersedes": None}]
        })
        state = Path(self.dir.name) / "world-times.json"
        world.save(state)
        before = state.read_bytes()
        server = create_server(state)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            query = {"view": "compare-world", "entity": "site-a",
                     "from_at": GEO_AT, "to_at": "2026-01-04T00:00:00Z",
                     "known_at": GEO_K1}
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            try:
                connection.request("GET", "/inspect?" + urlencode(query),
                    headers={"Host": "127.0.0.1:" + str(server.server_port)})
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                document = response.read().decode("utf-8")
            finally:
                connection.close()
            class Links(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.urls = []
                def handle_starttag(self, tag, attrs):
                    if tag == "a":
                        href = dict(attrs).get("href", "")
                        if href.startswith("/viewer?"):
                            self.urls.append(href)
            parser = Links()
            parser.feed(document)
            self.assertIn("a-old-location", document)
            self.assertIn("a-new-location", document)
            self.assertEqual(len(parser.urls), 3)
            links = {}
            comparison = None
            for url in parser.urls:
                args = {k: values[0] for k, values in
                        parse_qs(urlsplit(url).query).items()}
                self.assertEqual(args["known_at"], GEO_K1)
                if args["view"] == "world-changes":
                    comparison = args
                    self.assertEqual(args["from_at"], GEO_AT)
                    self.assertEqual(args["to_at"], "2026-01-04T00:00:00Z")
                else:
                    self.assertEqual(args["view"], "radius")
                    links[args["at"]] = args["center"]
            self.assertIsNotNone(comparison)
            connection = http.client.HTTPConnection(
                "127.0.0.1", server.server_port, timeout=5)
            try:
                connection.request("GET", "/map-world-changes?" + urlencode({
                    key: value for key, value in comparison.items()
                    if key != "view"}), headers={
                    "Host": "127.0.0.1:" + str(server.server_port)})
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                collection = json.loads(response.read())
                self.assertEqual({f["properties"]["monde_change"]
                    for f in collection["features"]},
                    {"NO_LONGER_CURRENT", "NEWLY_CURRENT"})
            finally:
                connection.close()
            self.assertEqual(links, {GEO_AT: "2.0,48.0",
                "2026-01-04T00:00:00Z": "3.0,49.0"})
            self.assertEqual(state.read_bytes(), before)
        finally:
            server.shutdown()
            worker.join(timeout=5)
            server.server_close()


    def test_bitemporal_map_link_does_not_invent_original_geography(self):
        from monde.local_api import _comparison_map_link
        params = {"at": GEO_AT, "from_known_at": "2026-01-01T00:00:00Z",
                  "to_known_at": "2026-01-04T00:00:00Z"}
        no_points = {"changes": {"floors": {
            "newly_current": [{"value": 4}], "no_longer_current": []}}}
        self.assertIsNone(_comparison_map_link(no_points, "compare-knowledge", params))
        def point(lon, lat):
            return {"value": {"type": "Point", "coordinates": [lon, lat]}}
        changes = {"changes": {"geo_point": {
            "newly_current": [point(179.9, 48)],
            "no_longer_current": [point(-179.9, 48)]}}}
        self.assertIsNone(_comparison_map_link(changes, "compare-knowledge", params))
        changes["changes"]["geo_point"]["no_longer_current"] = [point(179.8, 48)]
        url = _comparison_map_link(changes, "compare-knowledge", params)
        self.assertTrue(url.startswith("/viewer?"))
        args = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
        self.assertEqual(args["view"], "knowledge-changes")
        self.assertEqual(args["to_known_at"], params["to_known_at"])
        west, south, east, north = map(float, args["bbox"].split(","))
        self.assertLessEqual(west, 179.8)
        self.assertGreaterEqual(east, 179.9)
        self.assertLessEqual(south, 48)
        self.assertGreaterEqual(north, 48)
