"""HTTP regression: readable original source disagreement reports."""
import http.client
import csv
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from monde.local_api import create_server
from tests.test_world_geojson_disagreements import AT, K1, disputed, add

QUERY = {"bbox": "2.3,48.8,2.4,48.9", "at": AT, "known_at": K1}


class DisagreementReportHTTPTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "snapshot.json"
        self.world = disputed()
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
        self.folder.cleanup()

    def fetch(self, route, args):
        client = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        client.request("GET", route + "?" + urlencode(args),
                       headers={"Host": "127.0.0.1:" + str(self.server.server_port)})
        response = client.getresponse()
        output = response.status, dict(response.getheaders()), response.read()
        client.close()
        return output

    def test_source_focus_retains_opposing_provenance_and_links(self):
        status, headers, body = self.fetch(
            "/disagreement-report", {**QUERY, "source": "survey-east"})
        self.assertEqual(status, 200)
        html = body.decode("utf-8")
        self.assertIn("site-a", html)
        self.assertNotIn("<h2>site-b</h2>", html)
        self.assertIn("survey-east", html)
        self.assertIn("survey-west", html)
        self.assertIn("assertion_id", html)
        self.assertIn("evidence_id", html)
        self.assertIn("/inspect?view=entity&amp;entity=site-a", html)
        self.assertIn("/viewer?view=disagreements", html)
        self.assertIn("/map-disagreements?", html)
        self.assertIn("outside", html)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertIn("script-src 'none'", headers["Content-Security-Policy"])
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_unfiltered_and_empty_source_do_not_invent_ground_truth(self):
        status, _, body = self.fetch("/disagreement-report", QUERY)
        self.assertEqual(status, 200)
        html = body.decode()
        self.assertIn("site-a", html)
        self.assertIn("site-b", html)
        self.assertIn("No consensus location", html)
        status, _, body = self.fetch(
            "/disagreement-report", {**QUERY, "source": "unseen-source"})
        self.assertEqual(status, 200)
        self.assertIn(b"NO MATCHING SOURCE DISAGREEMENT", body)
        self.assertNotIn(b"<section>", body)

    def test_explore_form_and_rejected_inputs(self):
        status, _, body = self.fetch("/explore", {})
        self.assertEqual(status, 200)
        self.assertIn(b'formaction="/disagreement-report"', body)
        status, _, _ = self.fetch(
            "/disagreement-report", {"view": "disagreements", **QUERY, "source": "survey-east"})
        self.assertEqual(status, 200)
        for request in (
            {"view": "wrong", **QUERY},
            {**QUERY, "source": "../other"},
            {**QUERY, "unexpected": "value"},
            {**QUERY, "at": "not-a-date"},
        ):
            status, _, body = self.fetch("/disagreement-report", request)
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(body), {"error": "invalid_query"})

    def test_bitemporal_map_links_preserve_original_source(self):
        status, _, body = self.fetch(
            "/disagreement-report", {**QUERY, "source": "survey-east"})
        self.assertEqual(status, 200)
        html = body.decode()
        self.assertIn("source=survey-east", html)
        self.assertIn("known_at=", html)
        self.assertIn("at=", html)
        self.assertIn("Original source disagreement evidence", html)


    def test_download_original_disagreement_csv_matches_visible_opposition(self):
        params = {**QUERY, "source": "survey-east"}
        code, headers, raw = self.fetch("/disagreement.csv", params)
        self.assertEqual(code, 200)
        self.assertEqual(headers["Content-Type"], "text/csv; charset=utf-8")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn("attachment;", headers["Content-Disposition"])
        rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
        self.assertEqual(len(rows), 2)
        self.assertEqual({r["entity"] for r in rows}, {"site-a"})
        self.assertEqual({r["source_id"] for r in rows},
                         {"survey-east", "survey-west"})
        self.assertEqual({r["inside_bbox"] for r in rows}, {"true", "false"})
        self.assertTrue(all(r["assertion_id"] and r["evidence_id"] for r in rows))
        self.assertTrue(all(r["world_at"] == AT and r["known_at"] == K1
                            for r in rows))
        self.assertEqual({float(r["longitude"]) for r in rows}, {2.35, 7.2})
        html = self.fetch("/disagreement-report", params)[2].decode("utf-8")
        self.assertIn("Download original evidence CSV", html)
        self.assertIn("/disagreement.csv?", html)
        self.assertIn("source=survey-east", html)

    def test_csv_empty_source_and_invalid_parameters(self):
        status, _, raw = self.fetch(
            "/disagreement.csv", {**QUERY, "source": "unseen-source"})
        self.assertEqual(status, 200)
        self.assertEqual(len(list(csv.DictReader(
            io.StringIO(raw.decode("utf-8"))))), 0)
        for bad in (
            {**QUERY, "source": "../survey-east"},
            {**QUERY, "unexpected": "value"},
            {**QUERY, "at": "not-a-date"},
            {**QUERY, "bbox": "0,0,0"},
        ):
            with self.subTest(bad=bad):
                status, _, raw = self.fetch("/disagreement.csv", bad)
                self.assertEqual(status, 400)
                self.assertEqual(json.loads(raw), {"error": "invalid_query"})

    def test_csv_escapes_spreadsheet_formula_like_entity_id(self):
        from monde.local_api import _disagreement_csv
        report = {"features": [
            {"properties": {
                "entity": "=2+2", "source_id": "legit-source",
                "assertion_id": "assertion-1", "evidence_id": "evidence-1",
                "monde_inside_bbox": True
            }, "geometry": {"coordinates": [-1.5, 42]}}
        ]}
        raw = _disagreement_csv(report, {"at": AT, "known_at": K1})
        rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
        self.assertEqual(rows[0]["entity"], "'=2+2")
        self.assertEqual(rows[0]["longitude"], "-1.5")
        self.assertIn("evidence-1", raw.decode("utf-8"))




    def test_source_focused_geojson_export_matches_full_original_report_and_csv(self):
        params = {**QUERY, "source": "survey-east"}
        status, headers, raw = self.fetch("/map-disagreements", params)
        self.assertEqual(status, 200)
        document = json.loads(raw)
        features = document["features"]
        self.assertEqual(document["monde_disagreement_source_focus"], "survey-east")
        self.assertEqual({f["properties"]["entity"] for f in features}, {"site-a"})
        self.assertEqual({f["properties"]["source_id"] for f in features},
                         {"survey-east", "survey-west"})
        self.assertEqual({tuple(f["geometry"]["coordinates"]) for f in features},
                         {(2.35, 48.85), (7.2, 47.5)})
        self.assertEqual({f["properties"]["monde_inside_bbox"] for f in features},
                         {True, False})
        self.assertTrue(all(f["properties"]["evidence_id"]
                            and f["properties"]["assertion_id"] for f in features))
        self.assertEqual(document["monde_bbox_query"]["total_matching_entities"], 1)
        self.assertEqual(document["monde_bbox_query"]["total_source_features"], 2)
        self.assertIn("no-store", headers["Cache-Control"])
        csv_status, _, csv_raw = self.fetch("/disagreement.csv", params)
        self.assertEqual(csv_status, 200)
        rows = list(csv.DictReader(io.StringIO(csv_raw.decode("utf-8"))))
        self.assertEqual(
            {(f["properties"]["source_id"], f["properties"]["assertion_id"])
             for f in features},
            {(row["source_id"], row["assertion_id"]) for row in rows})
        self.assertEqual({r["inside_bbox"] for r in rows}, {"true", "false"})
        report = self.fetch("/disagreement-report", params)[2].decode("utf-8")
        for feature in features:
            self.assertIn(feature["properties"]["evidence_id"], report)

    def test_source_focus_never_borrows_the_other_sources_bbox_qualification(self):
        status, _, raw = self.fetch(
            "/map-disagreements", {**QUERY, "source": "survey-west"})
        self.assertEqual(status, 200)
        data = json.loads(raw)
        self.assertEqual(data["features"], [])
        self.assertEqual(data["monde_bbox_query"]["total_matching_entities"], 0)
        self.assertEqual(data["monde_bbox_query"]["status"], "NO_MATCHES")
        status, _, raw = self.fetch("/map-disagreements", {
            **QUERY, "source": "unseen-source"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)["features"], [])
        status, _, raw = self.fetch(
            "/map-disagreements", {**QUERY, "source": "../survey-east"})
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(raw), {"error": "invalid_query"})

    def test_unfiltered_disagreement_geojson_remains_original_world_export(self):
        status, _, raw = self.fetch("/map-disagreements", QUERY)
        self.assertEqual(status, 200)
        expected = self.world.export_geojson_disagreements(
            AT, K1, [2.3, 48.8, 2.4, 48.9])
        self.assertEqual(json.loads(raw), expected)
        status, _, blank = self.fetch(
            "/map-disagreements", {**QUERY, "source": ""})
        self.assertEqual(status, 200)
        self.assertEqual(blank, raw)


    def test_entity_focus_original_provenance_parity(self):
        report = self.fetch("/disagreement-report", QUERY)[2].decode("utf-8")
        self.assertIn("Focus on this disagreement", report)
        self.assertIn("entity=site-a", report)
        params = {**QUERY, "entity": "site-a"}
        status, _, raw = self.fetch("/map-disagreements", params)
        self.assertEqual(status, 200)
        data = json.loads(raw)
        self.assertEqual(data["monde_disagreement_entity_focus"], "site-a")
        self.assertEqual({f["properties"]["source_id"] for f in data["features"]},
                         {"survey-east", "survey-west"})
        self.assertEqual({f["properties"]["monde_inside_bbox"] for f in data["features"]},
                         {True, False})
        self.assertEqual(data["monde_bbox_query"]["total_matching_entities"], 1)
        rows = list(csv.DictReader(io.StringIO(
            self.fetch("/disagreement.csv", params)[2].decode("utf-8"))))
        self.assertEqual({r["assertion_id"] for r in rows},
                         {f["properties"]["assertion_id"] for f in data["features"]})
        html = self.fetch("/disagreement-report", params)[2].decode()
        self.assertIn("Focused entity: site-a", html)
        self.assertIn("survey-west", html)
        self.assertNotIn("<h2>site-b</h2>", html)

    def test_entity_source_intersection_requires_own_source_qualification(self):
        for optional, expected in (
                ({"entity": "site-a", "source": "survey-east"},
                 {"survey-east", "survey-west"}),
                ({"entity": "site-a", "source": "survey-west"}, set()),
                ({"entity": "site-b", "source": "survey-east"}, set()),
                ({"entity": "unknown"}, set())):
            with self.subTest(optional=optional):
                params = {**QUERY, **optional}
                data = json.loads(self.fetch("/map-disagreements", params)[2])
                self.assertEqual({f["properties"]["source_id"]
                                  for f in data["features"]}, expected)
                self.assertEqual(self.fetch("/disagreement-report", params)[0], 200)
                self.assertEqual(self.fetch("/disagreement.csv", params)[0], 200)

    def test_entity_map_preserves_source_and_time_selection(self):
        params = {"view": "disagreements", **QUERY,
                  "source": "survey-east", "entity": "site-a"}
        status, _, raw = self.fetch("/viewer", params)
        self.assertEqual(status, 200)
        html = raw.decode()
        self.assertIn('name="entity" value="site-a"', html)
        self.assertIn('name="source" value="survey-east"', html)
        self.assertIn(b'formaction="/disagreement-report"',
                      self.fetch("/explore", {})[2])


    def test_focused_disagreement_time_form_preserves_case_and_cutoffs(self):
        from html.parser import HTMLParser

        class Form(HTMLParser):
            def __init__(self):
                super().__init__()
                self.active = False
                self.found = False
                self.inputs = {}

            def handle_starttag(self, tag, attrs):
                values = dict(attrs)
                if tag == "form" and values.get("action") == "/disagreement-report":
                    self.active = True
                    self.found = values.get("method") == "get"
                if tag == "input" and self.active:
                    self.inputs[values["name"]] = values.get("value", "")

            def handle_endtag(self, tag):
                if tag == "form":
                    self.active = False

        params = {**QUERY, "source": "survey-east", "entity": "site-a"}
        status, headers, raw = self.fetch("/disagreement-report", params)
        self.assertEqual(status, 200)
        parser = Form()
        parser.feed(raw.decode("utf-8"))
        self.assertTrue(parser.found)
        self.assertEqual(parser.inputs, params)
        updated = {**parser.inputs, "known_at": "2020-01-01T00:00:00Z"}
        status, _, changed = self.fetch("/disagreement-report", updated)
        self.assertEqual(status, 200)
        self.assertIn(b"Focused entity: site-a", changed)
        self.assertIn(b"Selected original source: survey-east", changed)
        self.assertIn(b"Knowledge cutoff: 2020-01-01T00:00:00Z", changed)
        status, _, unchanged = self.fetch("/disagreement-report", parser.inputs)
        self.assertEqual(status, 200)
        self.assertIn(b"survey-east", unchanged)
        self.assertIn(b"survey-west", unchanged)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn("script-src 'none'", headers["Content-Security-Policy"])

    def test_time_form_escapes_entity_and_rejects_invalid_time(self):
        entity = '<img src=x onerror=alert(1)>'
        status, _, raw = self.fetch("/disagreement-report", {**QUERY, "entity": entity})
        self.assertEqual(status, 200)
        html = raw.decode("utf-8")
        self.assertNotIn(entity, html)
        self.assertIn("&lt;img", html)
        self.assertIn("NO MATCHING SOURCE DISAGREEMENT", html)
        status, _, raw = self.fetch("/disagreement-report", {**QUERY, "at": "yesterday"})
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(raw), {"error": "invalid_query"})

    def test_unfiltered_contract_and_invalid_entity_inputs(self):
        for route in ("/map-disagreements", "/disagreement-report",
                      "/disagreement.csv", "/viewer"):
            params = {**QUERY, **({"view": "disagreements"}
                                   if route == "/viewer" else {})}
            with self.subTest(route=route):
                original = self.fetch(route, params)
                blank = self.fetch(route, {**params, "entity": ""})
                self.assertEqual(original[0], blank[0])
                self.assertEqual(original[2], blank[2])
                for bad in ("bad\nentity", "x" * 257):
                    status, _, body = self.fetch(route, {**params, "entity": bad})
                    self.assertEqual(status, 400)
                    self.assertEqual(json.loads(body), {"error": "invalid_query"})


    def test_compare_original_disagreement_at_two_knowledge_cutoffs(self):
        params = {**QUERY, "source": "survey-east", "entity": "site-a",
                  "from_known_at": "2026-01-09T00:00:00Z"}
        status, headers, raw = self.fetch("/disagreement-report", params)
        self.assertEqual(status, 200)
        html = raw.decode("utf-8")
        for expected in ("Original source disagreements at two knowledge cutoffs",
                         "APPEARED IN SELECTION",
                         "earlier: 0 original Points; later: 2 original Points",
                         "Earlier complete GeoJSON", "Earlier original CSV",
                         'name="from_known_at" value="2026-01-09T00:00:00Z"',
                         "survey-west", "NOT actual physical movement"):
            self.assertIn(expected, html)
        self.assertIn("script-src 'none'", headers["Content-Security-Policy"])

    def test_compare_unchanged_original_evidence_and_provenance(self):
        later = "2026-01-12T10:00:00Z"
        params = {**QUERY, "entity": "site-a",
                  "from_known_at": K1, "known_at": later}
        status, _, raw = self.fetch("/disagreement-report", params)
        self.assertEqual(status, 200)
        html = raw.decode("utf-8")
        self.assertIn("SAME REPORTED EVIDENCE", html)
        self.assertIn("earlier: 2 original Points; later: 2 original Points", html)
        selected = json.loads(self.fetch("/map-disagreements", {
            **QUERY, "entity": "site-a", "known_at": later})[2])
        for f in selected["features"]:
            self.assertIn(f["properties"]["assertion_id"], html)
            self.assertIn(f["properties"]["evidence_id"], html)

    def test_compare_rejects_invalid_order_and_does_not_change_json_contract(self):
        for earlier, later in ((K1, K1),
                               ("2026-01-13T00:00:00Z", K1),
                               ("invalid", K1),
                               ("2026-01-09T00:00:00", K1)):
            code, _, raw = self.fetch("/disagreement-report", {
                **QUERY, "from_known_at": earlier, "known_at": later})
            self.assertEqual(code, 400)
            self.assertEqual(json.loads(raw), {"error": "invalid_query"})
        code, _, _ = self.fetch("/map-disagreements", {
            **QUERY, "from_known_at": "2026-01-09T00:00:00Z"})
        self.assertEqual(code, 400)

    def test_compare_does_not_borrow_an_outside_source_point(self):
        params = {**QUERY, "source": "survey-west", "entity": "site-a",
                  "from_known_at": "2026-01-09T00:00:00Z"}
        status, _, raw = self.fetch("/disagreement-report", params)
        self.assertEqual(status, 200)
        self.assertIn("NO SOURCE DISAGREEMENT IN EITHER SELECTION", raw.decode())


    def test_comparison_links_resolve_to_existing_single_cutoff_routes(self):
        from html.parser import HTMLParser
        from urllib.parse import urlsplit, parse_qs

        class Anchors(HTMLParser):
            def __init__(self):
                super().__init__()
                self.links = []

            def handle_starttag(self, tag, attrs):
                if tag == "a":
                    self.links.append(dict(attrs).get("href", ""))

        params = {**QUERY, "source": "survey-east", "entity": "site-a",
                  "from_known_at": "2026-01-09T00:00:00Z"}
        status, _, raw = self.fetch("/disagreement-report", params)
        self.assertEqual(status, 200)
        parser = Anchors()
        parser.feed(raw.decode())
        target = [u for u in parser.links if urlsplit(u).path in (
            "/viewer", "/map-disagreements", "/disagreement.csv")]
        self.assertEqual(len(target), 6)
        for link in target:
            parsed = urlsplit(link)
            query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            self.assertNotIn("from_known_at", query)
            self.assertEqual(query["source"], "survey-east")
            self.assertEqual(query["entity"], "site-a")
            self.assertEqual(self.fetch(parsed.path, query)[0], 200)



    def test_world_time_comparison_preserves_original_source_evidence(self):
        params = {**QUERY, "source": "survey-east", "entity": "site-a",
                  "from_at": "2025-12-31T00:00:00Z"}
        status, headers, raw = self.fetch("/disagreement-report", params)
        self.assertEqual(status, 200)
        html = raw.decode("utf-8")
        for expected in ("Original source disagreements at two world times",
                         "Same knowledge cutoff: " + K1,
                         "APPEARED IN SELECTION", "earlier: 0 original Points",
                         "later: 2 original Points", "Earlier original CSV",
                         "Earlier complete GeoJSON", "survey-west",
                         'name="from_at" required', "NOT actual physical movement"):
            self.assertIn(expected, html)
        self.assertIn("script-src 'none'", headers["Content-Security-Policy"])

    def test_world_time_comparison_links_keep_one_cutoff_and_original_source(self):
        from html.parser import HTMLParser
        from urllib.parse import urlsplit, parse_qs

        class Links(HTMLParser):
            def __init__(self):
                super().__init__()
                self.urls = []

            def handle_starttag(self, tag, attrs):
                if tag == "a":
                    self.urls.append(dict(attrs).get("href", ""))

        earlier = "2026-01-01T12:00:00Z"
        params = {**QUERY, "source": "survey-east", "entity": "site-a",
                  "from_at": earlier}
        status, _, raw = self.fetch("/disagreement-report", params)
        self.assertEqual(status, 200)
        self.assertIn("SAME REPORTED EVIDENCE", raw.decode())
        p = Links()
        p.feed(raw.decode())
        cutoffs = []
        for url in p.urls:
            parsed = urlsplit(url)
            if parsed.path not in ("/viewer", "/map-disagreements", "/disagreement.csv"):
                continue
            args = {key: value[0] for key, value in parse_qs(parsed.query).items()}
            self.assertNotIn("from_at", args)
            self.assertEqual(args["known_at"], K1)
            self.assertEqual(args["source"], "survey-east")
            self.assertEqual(args["entity"], "site-a")
            self.assertEqual(self.fetch(parsed.path, args)[0], 200)
            cutoffs.append(args["at"])
        self.assertEqual(cutoffs.count(earlier), 3)
        self.assertEqual(cutoffs.count(AT), 3)

    def test_world_time_compare_rejects_invalid_axes_and_wrong_source(self):
        for cutoff in (AT, "2026-01-04T00:00:00Z", "invalid",
                       "2025-12-31T00:00:00"):
            code, _, raw = self.fetch("/disagreement-report",
                                      {**QUERY, "from_at": cutoff})
            self.assertEqual(code, 400)
            self.assertEqual(json.loads(raw), {"error": "invalid_query"})
        status, _, raw = self.fetch("/disagreement-report", {
            **QUERY, "from_at": "2025-12-31T00:00:00Z",
            "from_known_at": "2026-01-09T00:00:00Z"})
        self.assertEqual(status, 400)
        for route in ("/map-disagreements", "/disagreement.csv", "/viewer"):
            args = {**QUERY, "from_at": "2025-12-31T00:00:00Z"}
            if route == "/viewer":
                args["view"] = "disagreements"
            self.assertEqual(self.fetch(route, args)[0], 400)
        status, _, raw = self.fetch("/disagreement-report", {
            **QUERY, "source": "survey-west", "entity": "site-a",
            "from_at": "2025-12-31T00:00:00Z"})
        self.assertEqual(status, 200)
        self.assertIn("NO SOURCE DISAGREEMENT IN EITHER SELECTION", raw.decode())



    def test_comparison_json_world_time_preserves_all_original_provenance(self):
        params = {**QUERY, "source": "survey-east", "entity": "site-a",
                  "from_at": "2025-12-31T00:00:00Z"}
        status, headers, raw = self.fetch("/disagreement-compare.json", params)
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers["Content-Type"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        result = json.loads(raw)
        self.assertEqual(result["world"], "OBSERVED")
        self.assertEqual(result["axis"], "WORLD_TIME")
        self.assertEqual(result["selection"]["source"], "survey-east")
        self.assertEqual(result["earlier"]["at"], params["from_at"])
        self.assertEqual(result["later"]["at"], AT)
        self.assertEqual(result["earlier"]["known_at"], K1)
        self.assertEqual(result["later"]["known_at"], K1)
        self.assertEqual(result["changes"][0]["classification"], "APPEARED IN SELECTION")
        self.assertEqual(result["status"], "SELECTION_CHANGED")
        current = json.loads(self.fetch("/map-disagreements", {
            **QUERY, "source": "survey-east", "entity": "site-a"})[2])
        self.assertEqual(result["later"]["geojson"], current)
        for feature in result["later"]["geojson"]["features"]:
            for key in ("source_id", "assertion_id", "evidence_id"):
                self.assertTrue(feature["properties"][key])
        html = self.fetch("/disagreement-report", params)[2].decode("utf-8")
        self.assertIn("/disagreement-compare.json?", html)
        self.assertIn("Download complete original comparison JSON", html)

    def test_comparison_json_knowledge_time_remains_distinct_from_world_time(self):
        params = {**QUERY, "entity": "site-a",
                  "from_known_at": "2026-01-09T00:00:00Z"}
        status, _, raw = self.fetch("/disagreement-compare.json", params)
        self.assertEqual(status, 200)
        data = json.loads(raw)
        self.assertEqual(data["axis"], "KNOWLEDGE_TIME")
        self.assertEqual(data["earlier"]["at"], AT)
        self.assertEqual(data["later"]["at"], AT)
        self.assertEqual(data["earlier"]["known_at"], params["from_known_at"])
        self.assertEqual(data["later"]["known_at"], K1)
        self.assertEqual(data["changes"][0]["classification"], "APPEARED IN SELECTION")

    def test_comparison_json_no_selection_is_not_inferred_agreement(self):
        params = {**QUERY, "source": "unseen-source",
                  "from_at": "2025-12-31T00:00:00Z"}
        status, _, raw = self.fetch("/disagreement-compare.json", params)
        self.assertEqual(status, 200)
        data = json.loads(raw)
        self.assertEqual(data["changes"], [])
        self.assertEqual(data["status"], "NO_SELECTION_CHANGE")
        self.assertEqual(data["earlier"]["geojson"]["features"], [])
        self.assertEqual(data["later"]["geojson"]["features"], [])
        self.assertNotIn("consensus", json.dumps(data))

    def test_comparison_json_rejects_bad_cutoffs_axes_and_unknown_keys(self):
        for params in ({**QUERY},
                       {**QUERY, "from_at": AT},
                       {**QUERY, "from_at": "invalid"},
                       {**QUERY, "from_at": "2025-12-31T00:00:00"},
                       {**QUERY, "from_known_at": K1},
                       {**QUERY, "from_known_at": "2026-01-13T00:00:00Z"},
                       {**QUERY, "from_at": "2025-12-31T00:00:00Z",
                        "from_known_at": "2026-01-09T00:00:00Z"},
                       {**QUERY, "from_at": "2025-12-31T00:00:00Z", "bad": "1"}):
            status, _, raw = self.fetch("/disagreement-compare.json", params)
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(raw), {"error": "invalid_query"})

    def test_comparison_csv_knowledge_time_retains_full_opposing_evidence(self):
        params = {**QUERY, "source": "survey-east", "entity": "site-a",
                  "from_known_at": "2026-01-09T00:00:00Z"}
        status, headers, body = self.fetch("/disagreement-compare.csv", params)
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("original-disagreement-comparison.csv",
                      headers["Content-Disposition"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        rows = list(csv.DictReader(io.StringIO(body.decode("utf-8"))))
        comparison = json.loads(self.fetch("/disagreement-compare.json", params)[2])
        expected = {(f["properties"]["source_id"], f["properties"]["assertion_id"],
                     f["properties"]["evidence_id"],
                     tuple(f["geometry"]["coordinates"]))
                    for f in comparison["later"]["geojson"]["features"]}
        actual = {(r["source_id"], r["assertion_id"], r["evidence_id"],
                   (float(r["longitude"]), float(r["latitude"]))) for r in rows}
        self.assertEqual(actual, expected)
        self.assertEqual({r["source_id"] for r in rows},
                         {"survey-east", "survey-west"})
        self.assertEqual({r["inside_bbox"] for r in rows}, {"true", "false"})
        self.assertEqual({r["period"] for r in rows}, {"later"})
        self.assertEqual({r["classification"] for r in rows},
                         {"APPEARED IN SELECTION"})
        self.assertIn("/disagreement-compare.csv?",
                      self.fetch("/disagreement-report", params)[2].decode("utf-8"))

    def test_comparison_csv_world_time_and_two_original_periods(self):
        params = {**QUERY, "source": "survey-east", "entity": "site-a",
                  "from_at": "2026-01-01T01:00:00Z"}
        code, _, raw = self.fetch("/disagreement-compare.csv", params)
        self.assertEqual(code, 200)
        rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
        reference = json.loads(self.fetch("/disagreement-compare.json", params)[2])
        self.assertEqual(reference["axis"], "WORLD_TIME")
        self.assertEqual({r["period"] for r in rows}, {"earlier", "later"})
        self.assertEqual(len(rows), sum(len(reference[p]["geojson"]["features"])
                                       for p in ("earlier", "later")))
        self.assertEqual({r["classification"] for r in rows},
                         {"SAME REPORTED EVIDENCE"})
        for row in rows:
            part = reference[row["period"]]
            self.assertEqual((row["world_at"], row["known_at"]),
                             (part["at"], part["known_at"]))

    def test_comparison_csv_empty_and_invalid_requests(self):
        query = {**QUERY, "source": "source-not-seen",
                 "from_known_at": "2026-01-09T00:00:00Z"}
        code, _, body = self.fetch("/disagreement-compare.csv", query)
        self.assertEqual(code, 200)
        self.assertEqual(list(csv.DictReader(io.StringIO(body.decode("utf-8")))), [])
        for query in ({**QUERY}, {**QUERY, "from_at": AT},
                      {**QUERY, "from_at": "2025-12-31T00:00:00Z",
                       "from_known_at": "2026-01-09T00:00:00Z"},
                      {**QUERY, "from_known_at": "2026-01-09T00:00:00Z",
                       "unknown": "extra"}):
            status, _, body = self.fetch("/disagreement-compare.csv", query)
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(body), {"error": "invalid_query"})

    def test_comparison_csv_prevents_spreadsheet_formula_execution(self):
        from monde.local_api import _disagreement_comparison_csv
        feature = {"geometry": {"coordinates": [2.35, 48.85]},
                   "properties": {"entity": "=2+2", "source_id": "+BAD",
                                  "assertion_id": "-BAD", "evidence_id": "@BAD",
                                  "monde_inside_bbox": True}}
        comparison = {"axis": "KNOWLEDGE_TIME",
                      "changes": [{"entity": "=2+2", "classification": "REPORTED EVIDENCE CHANGED"}],
                      "earlier": {"at": AT, "known_at": K1, "geojson": {"features": []}},
                      "later": {"at": AT, "known_at": K1, "geojson": {"features": [feature]}}}
        rows = list(csv.DictReader(io.StringIO(
            _disagreement_comparison_csv(comparison).decode("utf-8"))))
        self.assertEqual(rows[0]["entity"], "'=2+2")
        self.assertEqual(rows[0]["source_id"], "'+BAD")
        self.assertEqual(rows[0]["assertion_id"], "'-BAD")
        self.assertEqual(rows[0]["evidence_id"], "'@BAD")


    def test_change_focus_hides_stable_evidence_and_retains_provenance(self):
        stable = {**QUERY, "source": "survey-east", "entity": "site-a",
                  "from_at": "2026-01-01T01:00:00Z"}
        original = json.loads(self.fetch("/disagreement-compare.json", stable)[2])
        self.assertEqual(original["changes"][0]["classification"],
                         "SAME REPORTED EVIDENCE")
        selected = {**stable, "changes_only": "1"}
        status, _, raw = self.fetch("/disagreement-compare.json", selected)
        self.assertEqual(status, 200)
        data = json.loads(raw)
        self.assertEqual(data["selection"]["changes_only"], "1")
        self.assertEqual(data["changes"], [])
        self.assertEqual(data["earlier"]["geojson"]["features"], [])
        self.assertEqual(data["later"]["geojson"]["features"], [])
        status, _, raw = self.fetch("/disagreement-compare.csv", selected)
        self.assertEqual(status, 200)
        self.assertEqual(list(csv.DictReader(io.StringIO(raw.decode()))), [])
        html = self.fetch("/disagreement-report", selected)[2].decode()
        self.assertIn("NO CHANGED ORIGINAL SOURCE DISAGREEMENT", html)
        self.assertIn("Show all original evidence", html)

    def test_change_focus_preserves_complete_opposing_reports(self):
        selected = {**QUERY, "source": "survey-east", "entity": "site-a",
                    "from_known_at": "2026-01-09T00:00:00Z", "changes_only": "1"}
        status, _, raw = self.fetch("/disagreement-compare.json", selected)
        self.assertEqual(status, 200)
        data = json.loads(raw)
        self.assertEqual(data["axis"], "KNOWLEDGE_TIME")
        self.assertEqual(data["changes"][0]["classification"],
                         "APPEARED IN SELECTION")
        features = data["later"]["geojson"]["features"]
        self.assertEqual({f["properties"]["source_id"] for f in features},
                         {"survey-east", "survey-west"})
        rows = list(csv.DictReader(io.StringIO(
            self.fetch("/disagreement-compare.csv", selected)[2].decode())))
        self.assertEqual({r["source_id"] for r in rows},
                         {"survey-east", "survey-west"})
        self.assertEqual(len(rows), len(features))
        html = self.fetch("/disagreement-report", selected)[2].decode()
        self.assertIn("Show changed evidence only", html)
        self.assertIn("changes_only=1", html)

    def test_change_focus_rejects_invalid_scope_and_unrelated_routes(self):
        for route in ("/disagreement-report", "/disagreement-compare.json",
                      "/disagreement-compare.csv"):
            for params in ({**QUERY, "changes_only": "1"},
                           {**QUERY, "from_known_at": "2026-01-09T00:00:00Z",
                            "changes_only": "yes"}):
                status, _, raw = self.fetch(route, params)
                self.assertEqual(status, 400)
                self.assertEqual(json.loads(raw), {"error": "invalid_query"})
        for route in ("/viewer", "/map-disagreements", "/disagreement.csv"):
            params = {**QUERY, "changes_only": "1"}
            if route == "/viewer":
                params["view"] = "disagreements"
            self.assertEqual(self.fetch(route, params)[0], 400)



    def test_change_kind_html_json_csv_real_http_selection_parity(self):
        params = {**QUERY, "source": "survey-east", "entity": "site-a",
                  "from_known_at": "2026-01-09T00:00:00Z"}
        for kind, classification in (("appeared", "APPEARED IN SELECTION"),
                                     ("disappeared", None),
                                     ("modified", None)):
            with self.subTest(kind=kind):
                selected = {**params, "change_kind": kind}
                status, _, raw = self.fetch("/disagreement-compare.json", selected)
                self.assertEqual(status, 200)
                comparison = json.loads(raw)
                self.assertEqual(comparison["selection"]["change_kind"], kind)
                self.assertEqual({r["classification"] for r in comparison["changes"]},
                                 {classification} if classification else set())
                reports = comparison["later"]["geojson"]["features"]
                self.assertEqual({r["properties"]["source_id"] for r in reports},
                                 {"survey-east", "survey-west"} if classification else set())
                csv_status, _, csv_raw = self.fetch("/disagreement-compare.csv", selected)
                self.assertEqual(csv_status, 200)
                rows = list(csv.DictReader(io.StringIO(csv_raw.decode())))
                self.assertEqual(len(rows), len(reports))
                self.assertEqual({r["classification"] for r in rows},
                                 {classification} if classification else set())
                html_status, _, html_raw = self.fetch("/disagreement-report", selected)
                self.assertEqual(html_status, 200)
                html = html_raw.decode()
                self.assertIn("Show newly appearing disagreements only", html)
                self.assertIn("Show disappearing disagreements only", html)
                self.assertIn("Show revised original evidence only", html)
                self.assertIn("change_kind=" + kind, html)
                if classification is None:
                    self.assertIn("NO ORIGINAL SOURCE DISAGREEMENT WITH SELECTED CHANGE TYPE", html)

    def test_change_kind_all_three_classes_at_both_bitemporal_axes(self):
        from unittest.mock import patch
        from monde.local_api import _disagreement_pair

        def point(entity, assertion, longitude):
            return {"type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [longitude, 48.85]},
                    "properties": {"entity": entity, "source_id": "survey-a",
                                   "assertion_id": assertion,
                                   "evidence_id": "e-" + assertion}}
        old = [point("disappeared", "old", 2.31), point("modified", "old-c", 2.32),
               point("stable", "same", 2.33)]
        new = [point("appeared", "new", 2.34), point("modified", "new-c", 2.35),
               point("stable", "same", 2.33)]
        old_doc = {"type": "FeatureCollection", "features": old}
        new_doc = {"type": "FeatureCollection", "features": new}
        for axis in ("from_at", "from_known_at"):
            for kind in ("appeared", "disappeared", "modified"):
                with self.subTest(axis=axis, kind=kind):
                    values = {**QUERY, axis: "2026-01-01T00:00:00Z",
                              "change_kind": kind}
                    with patch("monde.map_view.disagreement_view",
                               side_effect=[new_doc, old_doc]):
                        later, earlier = _disagreement_pair(self.world, values)
                    seen = {feature["properties"]["entity"] for feature
                            in later["features"] + earlier["features"]}
                    self.assertEqual(seen, {kind})

    def test_change_kind_rejects_unknown_values_and_unrelated_routes(self):
        base = {**QUERY, "from_known_at": "2026-01-09T00:00:00Z"}
        for route in ("/disagreement-report", "/disagreement-compare.json",
                      "/disagreement-compare.csv"):
            for params in ({**base, "change_kind": "other"},
                           {**QUERY, "change_kind": "appeared"},
                           {**base, "change_kind": ""}):
                with self.subTest(route=route, params=params):
                    status, _, raw = self.fetch(route, params)
                    self.assertEqual(status, 400)
                    self.assertEqual(json.loads(raw), {"error": "invalid_query"})
        for route in ("/viewer", "/map-disagreements", "/disagreement.csv"):
            params = {**QUERY, "change_kind": "appeared"}
            if route == "/viewer":
                params["view"] = "disagreements"
            self.assertEqual(self.fetch(route, params)[0], 400)


    def test_comparison_geojson_matches_original_reports_for_both_axes(self):
        for axis in ({"from_known_at": "2026-01-09T00:00:00Z"},
                     {"from_at": "2026-01-01T01:00:00Z"}):
            with self.subTest(axis=axis):
                params = {**QUERY, "source": "survey-east", "entity": "site-a", **axis}
                status, headers, body = self.fetch("/disagreement-compare.geojson", params)
                self.assertEqual(status, 200)
                self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
                self.assertEqual(headers["Cache-Control"], "no-store")
                data = json.loads(body)
                source = json.loads(self.fetch("/disagreement-compare.json", params)[2])
                self.assertEqual(data["type"], "FeatureCollection")
                self.assertEqual(data["world"], "OBSERVED")
                self.assertEqual(data["basis"], source["basis"])
                self.assertEqual(data["monde_comparison"]["axis"], source["axis"])
                self.assertEqual(data["monde_comparison"]["selection"], source["selection"])
                self.assertEqual(data["monde_comparison"]["status"], source["status"])
                references = []
                for period in ("earlier", "later"):
                    original = source[period]
                    self.assertEqual(data["monde_comparison"][period],
                                     {"at": original["at"], "known_at": original["known_at"]})
                    references.extend((period, feature)
                                      for feature in original["geojson"]["features"])
                self.assertEqual(len(data["features"]), len(references))
                self.assertEqual(len({f["id"] for f in data["features"]}),
                                 len(data["features"]))
                classifications = {r["entity"]: r["classification"]
                                   for r in source["changes"]}
                for feature, (period, original) in zip(data["features"], references):
                    props = feature["properties"]
                    self.assertEqual(feature["geometry"], original["geometry"])
                    for key, value in original["properties"].items():
                        self.assertEqual(props[key], value)
                    self.assertEqual(props["monde_original_feature_id"], original.get("id"))
                    self.assertEqual(props["monde_comparison_period"], period)
                    self.assertEqual(props["monde_disagreement_classification"],
                                     classifications[props["entity"]])
                    self.assertEqual(props["monde_world_at"], source[period]["at"])
                    self.assertEqual(props["monde_known_at"], source[period]["known_at"])
                html = self.fetch("/disagreement-report", params)[2].decode()
                self.assertIn("/disagreement-compare.geojson?", html)
                self.assertIn("Open original comparison GeoJSON", html)

    def test_comparison_geojson_filters_preserve_offscreen_opposing_sources(self):
        params = {**QUERY, "source": "survey-east", "entity": "site-a",
                  "from_known_at": "2026-01-09T00:00:00Z", "change_kind": "appeared"}
        code, _, raw = self.fetch("/disagreement-compare.geojson", params)
        self.assertEqual(code, 200)
        result = json.loads(raw)
        self.assertEqual(result["monde_comparison"]["selection"]["change_kind"], "appeared")
        self.assertEqual({f["properties"]["source_id"] for f in result["features"]},
                         {"survey-east", "survey-west"})
        self.assertEqual({f["properties"]["monde_inside_bbox"]
                          for f in result["features"]}, {True, False})
        self.assertEqual({f["properties"]["monde_disagreement_classification"]
                          for f in result["features"]}, {"APPEARED IN SELECTION"})
        empty = json.loads(self.fetch("/disagreement-compare.geojson",
                                      {**params, "change_kind": "disappeared"})[2])
        self.assertEqual(empty["features"], [])

    def test_comparison_geojson_invalid_queries_fail_closed(self):
        valid = {**QUERY, "from_known_at": "2026-01-09T00:00:00Z"}
        for query in (QUERY, {**valid, "from_at": "2026-01-01T00:00:00Z"},
                      {**valid, "change_kind": "unknown"},
                      {**valid, "extra": "x"},
                      {**valid, "from_known_at": K1}):
            with self.subTest(query=query):
                status, _, raw = self.fetch("/disagreement-compare.geojson", query)
                self.assertEqual(status, 400)
                self.assertEqual(json.loads(raw), {"error": "invalid_query"})

    def test_comparison_geojson_does_not_mutate_original_comparison(self):
        from copy import deepcopy
        from monde.local_api import _disagreement_comparison_geojson
        params = {**QUERY, "from_at": "2026-01-01T01:00:00Z"}
        source = json.loads(self.fetch("/disagreement-compare.json", params)[2])
        initial = deepcopy(source)
        output = _disagreement_comparison_geojson(source)
        self.assertEqual(source, initial)
        if output["features"]:
            output["features"][0]["properties"]["entity"] = "altered"
        self.assertEqual(source, initial)


if __name__ == "__main__":
    unittest.main()
