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
            "/viewer", "/map-disagreements", "/disagreement.csv")
            and "view=disagreement-comparison" not in u]
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
            if parsed.path == "/viewer" and args.get("view") == "disagreement-comparison":
                continue  # This new link intentionally retains both temporal cutoffs.
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


    @staticmethod
    def focus_form(html):
        """Read the actual native GET controls instead of reconstructing URLs."""
        from html.parser import HTMLParser

        class Focus(HTMLParser):
            def __init__(self):
                super().__init__()
                self.active = False
                self.action = None
                self.inputs = {}

            def handle_starttag(self, tag, attrs):
                props = dict(attrs)
                if tag == "form" and props.get("id") == "disagreement-focus-form":
                    self.active = True
                    self.action = props.get("action")
                    self.method = props.get("method")
                elif self.active and tag == "input":
                    self.inputs[props["name"]] = props.get("value", "")

            def handle_endtag(self, tag):
                if tag == "form" and self.active:
                    self.active = False

        parsed = Focus()
        parsed.feed(html)
        return parsed

    def test_browser_refocus_source_and_entity_without_losing_original_reports(self):
        original = {**QUERY, "source": "survey-east", "entity": "site-a"}
        code, headers, raw = self.fetch("/disagreement-report", original)
        self.assertEqual(code, 200)
        self.assertIn("script-src 'none'", headers["Content-Security-Policy"])
        html = raw.decode("utf-8")
        form = self.focus_form(html)
        self.assertEqual(form.action, "/disagreement-report")
        self.assertEqual(form.method, "get")
        self.assertEqual(form.inputs["source"], "survey-east")
        self.assertEqual(form.inputs["entity"], "site-a")
        self.assertEqual(form.inputs["bbox"], QUERY["bbox"])
        self.assertEqual(form.inputs["at"], AT)
        self.assertEqual(form.inputs["known_at"], K1)
        self.assertIn('id="disagreement-source-suggestions"', html)
        self.assertIn('value="survey-west"', html)
        self.assertIn('id="disagreement-entity-suggestions"', html)
        # Both source/entity controls can be cleared. No source is silently inferred.
        reset = dict(form.inputs, source="", entity="")
        status, _, body = self.fetch(form.action, reset)
        self.assertEqual(status, 200)
        self.assertIn("<h2>site-a</h2>", body.decode("utf-8"))
        self.assertIn("<h2>site-b</h2>", body.decode("utf-8"))
        # Focusing the out-of-bounds source does not borrow a different source's Point.
        changed = dict(form.inputs, source="survey-west")
        status, _, body = self.fetch(form.action, changed)
        self.assertEqual(status, 200)
        self.assertIn("NO MATCHING SOURCE DISAGREEMENT", body.decode("utf-8"))

    def test_browser_refocus_preserves_temporal_axis_and_change_selection(self):
        for axis in ({"from_known_at": "2026-01-09T00:00:00Z"},
                     {"from_at": "2025-12-31T00:00:00Z"}):
            with self.subTest(axis=axis):
                params = {**QUERY, **axis, "source": "survey-east",
                          "entity": "site-a", "change_kind": "appeared"}
                status, _, raw = self.fetch("/disagreement-report", params)
                self.assertEqual(status, 200)
                form = self.focus_form(raw.decode("utf-8"))
                self.assertEqual(form.inputs["change_kind"], "appeared")
                self.assertEqual(form.inputs["known_at"], K1)
                self.assertEqual(form.inputs["at"], AT)
                for key, value in axis.items():
                    self.assertEqual(form.inputs[key], value)
                # Follow the actual GET form to refocus, then compare existing JSON.
                updated = dict(form.inputs, source="", entity="site-a")
                report = self.fetch(form.action, updated)
                self.assertEqual(report[0], 200)
                self.assertIn("Original source disagreements at two", report[2].decode())
                result = self.fetch("/disagreement-compare.json", updated)
                self.assertEqual(result[0], 200)
                self.assertEqual(json.loads(result[2])["selection"]["change_kind"],
                                 "appeared")

    def test_browser_focus_escapes_untrusted_entity_and_keeps_loopback_read_only(self):
        injected = '<img src=x onerror="alert(1)">'
        status, headers, body = self.fetch(
            "/disagreement-report", {**QUERY, "entity": injected})
        self.assertEqual(status, 200)
        html = body.decode("utf-8")
        self.assertNotIn(injected, html)
        self.assertIn("&lt;img src=x onerror=&quot;alert(1)&quot;&gt;", html)
        self.assertIn("script-src 'none'", headers["Content-Security-Policy"])
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        form = self.focus_form(html)
        self.assertEqual(form.inputs["entity"], injected)
        self.assertEqual(self.fetch(form.action, {**form.inputs, "entity": ""})[0], 200)



    @staticmethod
    def embedded_map(html):
        """Read the real offline viewer's data script without a browser dependency."""
        from html.parser import HTMLParser

        class Reader(HTMLParser):
            def __init__(self):
                super().__init__()
                self.inside = False
                self.parts = []

            def handle_starttag(self, tag, attrs):
                if tag == "script" and dict(attrs).get("id") == "monde-data":
                    self.inside = True

            def handle_endtag(self, tag):
                if tag == "script":
                    self.inside = False

            def handle_data(self, data):
                if self.inside:
                    self.parts.append(data)

        parser = Reader()
        parser.feed(html)
        return json.loads("".join(parser.parts))

    def test_both_original_disagreement_periods_open_on_one_map(self):
        from html import unescape
        from re import search
        from urllib.parse import parse_qs, urlsplit

        for axis in ({"from_known_at": "2026-01-09T00:00:00Z"},
                     {"from_at": "2026-01-01T01:00:00Z"}):
            with self.subTest(axis=axis):
                selected = {**QUERY, "source": "survey-east",
                            "entity": "site-a", **axis}
                status, _, report = self.fetch("/disagreement-report", selected)
                self.assertEqual(status, 200)
                link = search(
                    r'href="([^"]+)">Map both original evidence periods</a>',
                    report.decode("utf-8"))
                self.assertIsNotNone(link)
                opened = urlsplit(unescape(link.group(1)))
                self.assertEqual(opened.path, "/viewer")
                params = {name: values[0]
                          for name, values in parse_qs(opened.query).items()}
                self.assertEqual(params.pop("view"), "disagreement-comparison")
                self.assertEqual(params, selected)
                code, headers, body = self.fetch(
                    opened.path, {"view": "disagreement-comparison", **params})
                self.assertEqual(code, 200)
                self.assertIn(b"Two original source-report periods on one map", body)
                self.assertIn(b"NOT verified movement", body)
                self.assertIn("connect-src 'none'", headers["Content-Security-Policy"])
                self.assertNotIn("Access-Control-Allow-Origin", headers)
                mapped = self.embedded_map(body.decode("utf-8"))
                exported = json.loads(
                    self.fetch("/disagreement-compare.geojson", selected)[2])
                self.assertEqual(mapped["features"], exported["features"])
                self.assertEqual(mapped["monde_comparison"],
                                 exported["monde_comparison"])
                self.assertEqual({f["properties"]["source_id"]
                                  for f in mapped["features"]},
                                 {"survey-east", "survey-west"})
                self.assertEqual({f["properties"]["monde_inside_bbox"]
                                  for f in mapped["features"]}, {True, False})
                self.assertEqual(
                    mapped["monde_bbox_query"]["total_source_features"],
                    len(exported["features"]))

    def test_both_period_map_change_filter_and_empty_evidence(self):
        params = {**QUERY, "from_known_at": "2026-01-09T00:00:00Z",
                  "source": "survey-east", "entity": "site-a"}
        for kind in ("appeared", "disappeared", "modified"):
            with self.subTest(kind=kind):
                selected = {**params, "change_kind": kind}
                status, _, body = self.fetch(
                    "/viewer", {"view": "disagreement-comparison", **selected})
                self.assertEqual(status, 200)
                mapped = self.embedded_map(body.decode("utf-8"))
                exported = json.loads(
                    self.fetch("/disagreement-compare.geojson", selected)[2])
                self.assertEqual(mapped["features"], exported["features"])
                self.assertEqual(mapped["monde_bbox_query"]["status"],
                                 "MATCHES" if exported["features"] else "NO_MATCHES")
        status, _, body = self.fetch(
            "/viewer", {"view": "disagreement-comparison",
                        **params, "change_kind": "disappeared"})
        self.assertEqual(status, 200)
        self.assertEqual(self.embedded_map(body.decode())["features"], [])

    def test_both_period_map_rejects_invalid_or_ambiguous_input(self):
        valid = {**QUERY, "from_known_at": "2026-01-09T00:00:00Z"}
        for params in (QUERY,
                       {**valid, "from_at": "2026-01-01T00:00:00Z"},
                       {**valid, "change_kind": "invalid"},
                       {**valid, "source": "../../evil"},
                       {**valid, "extra": "unexpected"},
                       {**valid, "from_known_at": K1}):
            with self.subTest(params=params):
                status, _, body = self.fetch(
                    "/viewer", {"view": "disagreement-comparison", **params})
                self.assertEqual(status, 400)
                self.assertEqual(json.loads(body), {"error": "invalid_query"})




    def test_comparison_map_link_from_explore_does_not_switch_view(self):
        from html import unescape
        from re import search
        from urllib.parse import parse_qs, urlsplit

        selected = {**QUERY, "view": "disagreements", "source": "survey-east",
                    "from_known_at": "2026-01-09T00:00:00Z"}
        status, _, body = self.fetch("/disagreement-report", selected)
        self.assertEqual(status, 200)
        link = search(r'href="([^"]+)">Map both original evidence periods</a>',
                      body.decode())
        self.assertIsNotNone(link)
        url = urlsplit(unescape(link.group(1)))
        args = {key: values[0]
                for key, values in parse_qs(url.query).items()}
        self.assertEqual(args["view"], "disagreement-comparison")
        self.assertEqual(args["source"], selected["source"])
        self.assertEqual(self.fetch(url.path, args)[0], 200)





    def test_download_offline_two_period_comparison_map_preserves_original_evidence(self):
        from html import unescape
        from re import search
        from urllib.parse import parse_qs, urlsplit

        for axis in ({"from_known_at": "2026-01-09T00:00:00Z"},
                     {"from_at": "2026-01-01T01:00:00Z"}):
            with self.subTest(axis=axis):
                selected = {**QUERY, "source": "survey-east",
                            "entity": "site-a", **axis}
                report_status, _, report = self.fetch("/disagreement-report", selected)
                self.assertEqual(report_status, 200)
                link = search(r'href="([^"]+)">Download offline comparison map</a>',
                              report.decode("utf-8"))
                self.assertIsNotNone(link)
                link_url = urlsplit(unescape(link.group(1)))
                self.assertEqual(link_url.path, "/disagreement-compare.html")
                self.assertEqual({key: val[0] for key, val in
                                  parse_qs(link_url.query).items()}, selected)

                status, headers, offline = self.fetch(link_url.path, selected)
                self.assertEqual(status, 200)
                self.assertIn("attachment;", headers["Content-Disposition"])
                self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
                self.assertIn("connect-src 'none'", headers["Content-Security-Policy"])
                self.assertIn("img-src 'none'", headers["Content-Security-Policy"])
                self.assertNotIn("Access-Control-Allow-Origin", headers)
                self.assertNotIn(b"/inspect?view=", offline)
                self.assertIn(b"Two original source-report periods on one map", offline)
                self.assertIn(b"NOT verified movement", offline)

                offline_data = self.embedded_map(offline.decode("utf-8"))
                geojson = json.loads(self.fetch(
                    "/disagreement-compare.geojson", selected)[2])
                self.assertEqual(offline_data["features"], geojson["features"])
                self.assertEqual(offline_data["monde_comparison"],
                                 geojson["monde_comparison"])
                self.assertEqual({item["properties"]["source_id"]
                                  for item in offline_data["features"]},
                                 {"survey-east", "survey-west"})

    def test_offline_download_link_from_native_explorer_rejects_view_only_in_link(self):
        from html import unescape
        from re import search
        from urllib.parse import parse_qs, urlsplit

        selected = {**QUERY, "view": "disagreements", "source": "survey-east",
                    "from_known_at": "2026-01-09T00:00:00Z"}
        status, _, report = self.fetch("/disagreement-report", selected)
        self.assertEqual(status, 200)
        match = search(r'href="([^"]+)">Download offline comparison map</a>',
                       report.decode("utf-8"))
        self.assertIsNotNone(match)
        url = urlsplit(unescape(match.group(1)))
        args = {key: val[0] for key, val in parse_qs(url.query).items()}
        self.assertEqual(url.path, "/disagreement-compare.html")
        self.assertEqual(args, {k: v for k, v in selected.items() if k != "view"})
        self.assertEqual(self.fetch(url.path, args)[0], 200)

    def test_download_comparison_map_reuses_filters_empty_and_validation(self):
        selected = {**QUERY, "from_known_at": "2026-01-09T00:00:00Z",
                    "source": "survey-east", "entity": "site-a"}
        for kind in ("appeared", "disappeared", "modified"):
            params = {**selected, "change_kind": kind}
            status, _, body = self.fetch("/disagreement-compare.html", params)
            self.assertEqual(status, 200)
            mapped = self.embedded_map(body.decode())
            matching = json.loads(self.fetch("/disagreement-compare.geojson", params)[2])
            self.assertEqual(mapped["features"], matching["features"])
        for bad in (QUERY, {**selected, "from_at": "2026-01-01T00:00:00Z"},
                    {**selected, "source": "../unsafe"}, {**selected, "extra": "evil"},
                    {**selected, "change_kind": "other"},
                    {**selected, "from_known_at": selected["known_at"]}):
            with self.subTest(bad=bad):
                status, _, body = self.fetch("/disagreement-compare.html", bad)
                self.assertEqual(status, 400)
                self.assertEqual(json.loads(body), {"error": "invalid_query"})


    def test_comparison_period_selector_preserves_both_original_snapshots(self):
        """The server sends all evidence; only browser visibility changes."""
        for axis in ({"from_known_at": "2026-01-09T00:00:00Z"},
                     {"from_at": "2026-01-01T01:00:00Z"}):
            with self.subTest(axis=axis):
                selected = {**QUERY, "source": "survey-east",
                            "entity": "site-a", **axis}
                expected = json.loads(
                    self.fetch("/disagreement-compare.geojson", selected)[2])
                counts = {period: sum(
                    f["properties"]["monde_comparison_period"] == period
                    for f in expected["features"])
                    for period in ("earlier", "later")}
                # An empty earlier period is valid: absence of known source
                # reports at that cutoff must not be filled with later evidence.
                self.assertEqual(counts["earlier"] + counts["later"],
                                 len(expected["features"]))
                self.assertGreater(len(expected["features"]), 0)
                for route in ("/disagreement-compare.html", "/viewer"):
                    args = ({"view": "disagreement-comparison", **selected}
                            if route == "/viewer" else selected)
                    code, headers, raw = self.fetch(route, args)
                    self.assertEqual(code, 200)
                    html = raw.decode("utf-8")
                    self.assertIn('id="comparison-period-control"', html)
                    self.assertIn('value="earlier"', html)
                    self.assertIn('value="later"', html)
                    self.assertIn("The complete earlier/later evidence", html)
                    embedded = self.embedded_map(html)
                    self.assertEqual(embedded["features"], expected["features"])
                    self.assertEqual(embedded["monde_comparison"],
                                     expected["monde_comparison"])
                    self.assertIn("connect-src 'none'",
                                  headers["Content-Security-Policy"])
                self.assertEqual(self.path.read_bytes(), self.before)


    def test_complete_period_export_available_only_in_original_comparison_maps(self):
        for axis in ({"from_known_at": "2026-01-09T00:00:00Z"},
                     {"from_at": "2026-01-01T01:00:00Z"}):
            selected = {**QUERY, "source": "survey-east",
                        "entity": "site-a", **axis}
            status, _, raw = self.fetch("/disagreement-compare.html", selected)
            self.assertEqual(status, 200)
            html = raw.decode("utf-8")
            self.assertIn('id="export-comparison-complete"', html)
            self.assertIn("COMPLETE_EMBEDDED_SOURCE_SELECTION_NOT_DISPLAY_FILTERED",
                          html)
            self.assertIn('id="comparison-period-control" class="controls" hidden',
                          self.fetch("/viewer", {"view": "current", **QUERY})[2].decode())
            self.assertEqual(self.embedded_map(html)["features"],
                             json.loads(self.fetch("/disagreement-compare.geojson",
                                                   selected)[2])["features"])
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_complete_period_export_chromium_includes_offscreen_original_reports(self):
        """Real browser click reads generated Blob; no host/CDN or data writes."""
        import re
        import shutil
        import subprocess
        browser = next((x for name in ("google-chrome", "chromium", "chromium-browser")
                        if (x := shutil.which(name))), None)
        if browser is None:
            self.skipTest("Chromium absent; GitHub Actions covers browser export")
        selected = {**QUERY, "from_known_at": "2026-01-09T00:00:00Z",
                    "source": "survey-east", "entity": "site-a"}
        status, _, raw = self.fetch("/disagreement-compare.html", selected)
        self.assertEqual(status, 200)
        document = self.embedded_map(raw.decode("utf-8"))
        counts = {period: sum(
            f["properties"]["monde_comparison_period"] == period
            for f in document["features"])
            for period in ("earlier", "later")}
        probe = """<script>
// Capture the exact synchronous Blob constructor payload produced by the
// real browser UI and saveEvidence path; suppress the actual headless download.
const NativeBlob=window.Blob;
window.Blob=function(parts,options){
  const doc=JSON.parse(String(parts[0])),meta=doc.monde_complete_period_export;
  document.body.setAttribute("data-actual-period",meta.selected_period);
  document.body.setAttribute("data-actual-count",String(doc.features.length));
  document.body.setAttribute("data-actual-original",String(meta.original_feature_count));
  document.body.setAttribute("data-actual-basis",meta.scope);
  document.body.setAttribute("data-source-ids",
    Array.from(new Set(doc.features.map(f=>f.properties.source_id))).sort().join(","));
  return new NativeBlob(parts,options);
};
HTMLAnchorElement.prototype.click=function(){
  document.body.setAttribute("data-download-name",this.download);
};
const period=document.getElementById("comparison-period");
period.value="later";
period.dispatchEvent(new Event("change"));
document.getElementById("export-comparison-complete").click();
</script>"""
        file = Path(self.folder.name) / "comparison-export.html"
        file.write_text(raw.decode().replace("</body>", probe+"</body>"),
                        encoding="utf-8")
        rendered = subprocess.run([
            browser, "--headless", "--no-sandbox", "--disable-gpu",
            "--disable-dev-shm-usage", "--dump-dom", file.as_uri()], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=30, check=True).stdout.decode("utf-8")
        self.assertIn('data-monde-ready="true"', rendered)
        self.assertIn('data-actual-period="later"', rendered)
        self.assertIn('data-actual-count="'+str(counts["later"])+'"', rendered)
        self.assertIn('data-actual-original="'+str(len(document["features"]))+'"',
                      rendered)
        self.assertIn('data-actual-basis="COMPLETE_EMBEDDED_SOURCE_SELECTION_NOT_DISPLAY_FILTERED"',
                      rendered)
        self.assertIn('data-source-ids="survey-east,survey-west"', rendered)
        self.assertIn('data-download-name="monde-original-later-comparison.geojson"',
                      rendered)
        self.assertEqual(self.path.read_bytes(), self.before)


    def test_complete_period_csv_button_uses_existing_original_evidence(self):
        """The server embeds the same full, original source reports for CSV."""
        for axis in ({"from_known_at": "2026-01-09T00:00:00Z"},
                     {"from_at": "2026-01-01T01:00:00Z"}):
            with self.subTest(axis=axis):
                params = {**QUERY, "source": "survey-east", "entity": "site-a", **axis}
                status, _, body = self.fetch("/disagreement-compare.html", params)
                self.assertEqual(status, 200)
                html = body.decode("utf-8")
                self.assertIn('id="export-comparison-csv"', html)
                self.assertIn("COMPLETE_EMBEDDED_SOURCE_SELECTION_NOT_DISPLAY_FILTERED", html)
                embedded = self.embedded_map(html)
                original = json.loads(self.fetch("/disagreement-compare.geojson", params)[2])
                self.assertEqual(embedded["features"], original["features"])
                self.assertTrue(all(
                    f["properties"]["monde_comparison_period"] in ("earlier", "later")
                    for f in embedded["features"]))
                self.assertIn('id="comparison-period-control" class="controls" hidden',
                              self.fetch("/viewer", {"view": "current", **QUERY})[2].decode())
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_complete_period_csv_chromium_download_preserves_offscreen_originals(self):
        """Real offline Chromium Blob path checks export vs embedded evidence, not visual filters."""
        import re
        import shutil
        import subprocess
        browser = next((b for name in ("google-chrome", "chromium", "chromium-browser")
                        if (b := shutil.which(name))), None)
        if not browser:
            self.skipTest("Chromium unavailable; GitHub Actions runs browser integration")
        params = {**QUERY, "source": "survey-east", "entity": "site-a",
                  "from_known_at": "2026-01-09T00:00:00Z"}
        status, _, body = self.fetch("/disagreement-compare.html", params)
        self.assertEqual(status, 200)
        html = body.decode("utf-8")
        doc = self.embedded_map(html)
        counts = {p: sum(f["properties"]["monde_comparison_period"] == p
                         for f in doc["features"]) for p in ("earlier", "later")}
        probe = """<script>
const NativeBlob=window.Blob;
window.Blob=function(parts,options){
  const csv=String(parts[0]);
  document.body.setAttribute("data-csv-header",String(csv.includes("original_feature_id")));
  document.body.setAttribute("data-csv-inert",String(csv.includes("COMPLETE_EMBEDDED_SOURCE_SELECTION_NOT_DISPLAY_FILTERED")));
  document.body.setAttribute("data-csv-rows",String(csv.split(String.fromCharCode(13,10)).filter(Boolean).length-1));
  document.body.setAttribute("data-csv-source",String(csv.includes("survey-west")));
  document.body.setAttribute("data-csv-period",document.getElementById("comparison-period").value||"both");
  return new NativeBlob(parts,options);
};
HTMLAnchorElement.prototype.click=function(){
  document.body.setAttribute("data-csv-file",this.download);
};
for(const period of ["earlier","later",""]){
  const selection=document.getElementById("comparison-period");
  selection.value=period;
  selection.dispatchEvent(new Event("change"));
  document.getElementById("export-comparison-csv").click();
  const suffix=period||"both";
  document.body.setAttribute("data-"+suffix+"-csv-rows",document.body.getAttribute("data-csv-rows"));
  document.body.setAttribute("data-"+suffix+"-csv-file",document.body.getAttribute("data-csv-file"));
}
</script>"""
        output = Path(self.folder.name) / "complete-comparison-csv.html"
        output.write_text(html.replace("</body>", probe + "</body>"), encoding="utf-8")
        rendered = subprocess.run(
            [browser, "--headless", "--no-sandbox", "--disable-gpu",
             "--disable-dev-shm-usage", "--dump-dom", output.as_uri()],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
            check=True).stdout.decode("utf-8")
        self.assertIn('data-monde-ready="true"', rendered)
        for period in ("earlier", "later"):
            self.assertIn('data-'+period+'-csv-rows="'+str(counts[period])+'"',
                          rendered)
            self.assertIn('data-'+period+'-csv-file="monde-original-'+period+
                          '-comparison.csv"', rendered)
        self.assertIn('data-both-csv-rows="'+str(len(doc["features"]))+'"', rendered)
        self.assertIn('data-both-csv-file="monde-original-both-comparison.csv"',
                      rendered)
        self.assertIn('data-csv-header="true"', rendered)
        self.assertIn('data-csv-inert="true"', rendered)
        self.assertIn('data-csv-source="true"', rendered)
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_comparison_period_control_is_hidden_for_normal_source_maps(self):
        status, _, raw = self.fetch("/viewer",
                                    {"view": "current", **QUERY})
        self.assertEqual(status, 200)
        html = raw.decode()
        self.assertIn('id="comparison-period-control"', html)
        self.assertIn('id="comparison-period-control" class="controls" hidden', html)
        self.assertEqual(self.embedded_map(html).get("monde_comparison"), None)

    def test_period_selector_changes_rendered_svg_without_changing_saved_evidence(self):
        """Headless Chromium exercises the real offline JavaScript change event."""
        import re
        import shutil
        import subprocess
        browser = next((path for name in ("google-chrome", "chromium", "chromium-browser")
                        if (path := shutil.which(name))), None)
        if browser is None:
            self.skipTest("Chromium not installed; GitHub Actions tests browser path")
        selected = {**QUERY, "from_known_at": "2026-01-09T00:00:00Z",
                    "source": "survey-east", "entity": "site-a"}
        status, _, raw = self.fetch("/disagreement-compare.html", selected)
        self.assertEqual(status, 200)
        expected = self.embedded_map(raw.decode())
        counts = {period: sum(f["properties"]["monde_comparison_period"] == period
                              for f in expected["features"])
                  for period in ("earlier", "later")}
        probe = """<script>
const period=document.getElementById("comparison-period");
function count(mode) {
  period.value=mode;
  period.dispatchEvent(new Event("change"));
  return document.querySelectorAll("#points circle").length;
}
document.body.setAttribute("data-count-earlier",String(count("earlier")));
document.body.setAttribute("data-count-later",String(count("later")));
document.body.setAttribute("data-count-both",String(count("")));
</script>"""
        output = Path(self.folder.name) / "comparison.html"
        output.write_text(raw.decode().replace("</body>", probe + "</body>"),
                          encoding="utf-8")
        rendered = subprocess.run(
            [browser, "--headless", "--no-sandbox", "--disable-gpu",
             "--disable-dev-shm-usage", "--timeout=15000", "--dump-dom",
             output.as_uri()],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=30, check=True).stdout.decode("utf-8")
        self.assertIn('data-monde-ready="true"', rendered)
        for mode, value in (("earlier", counts["earlier"]),
                            ("later", counts["later"]),
                            ("both", len(expected["features"]))):
            match = re.search(r'data-count-' + mode + r'="(\d+)"', rendered)
            self.assertIsNotNone(match, "Browser did not run " + mode)
            self.assertEqual(int(match.group(1)), value)
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_offline_comparison_source_coverage_matches_complete_embedded_evidence(self):
        """Source/period matrix counts the full original snapshot, not the visible map."""
        import shutil
        import subprocess
        browser = next((p for name in ("google-chrome", "chromium", "chromium-browser")
                        if (p := shutil.which(name))), None)
        if not browser:
            self.skipTest("Chromium unavailable; GitHub Actions runs browser integration")
        params = {**QUERY, "source": "survey-east", "entity": "site-a",
                  "from_known_at": "2026-01-09T00:00:00Z"}
        status, _, body = self.fetch("/disagreement-compare.html", params)
        self.assertEqual(status, 200)
        html = body.decode("utf-8")
        embedded = self.embedded_map(html)
        actual = {}
        for f in embedded["features"]:
            source = f["properties"]["source_id"]
            period = f["properties"]["monde_comparison_period"]
            entry = actual.setdefault(source, {"earlier": 0, "later": 0})
            entry[period] += 1
        self.assertGreaterEqual(len(actual), 2)
        class_counts = {
            "both": sum(v["earlier"] + v["later"] for v in actual.values()
                        if v["earlier"] and v["later"]),
            "earlier-only": sum(v["earlier"] for v in actual.values()
                                if v["earlier"] and not v["later"]),
            "later-only": sum(v["later"] for v in actual.values()
                              if v["later"] and not v["earlier"]),
        }
        expected = "|".join(
            f"{name}:{actual[name]['earlier']}:{actual[name]['later']}"
            for name in sorted(actual))
        probe = """<script>
const body=document.body,coverage=document.getElementById("comparison-source-coverage");
body.dataset.coverageOpen=String(!coverage.hidden);
const records=Array.from(document.querySelectorAll("#comparison-source-rows tr"));
body.dataset.coverageCount=String(records.length);
body.dataset.coverageRows=records.map(row=>row.dataset.sourceId+":"+
  row.children[1].textContent+":"+row.children[2].textContent).join("|");
const sourceSelect=document.getElementById("sources");
const originalCount=document.getElementById("comparison-source-total").textContent;
records[0].querySelector("button").click();
body.dataset.sourceAfterClick=sourceSelect.value;
body.dataset.firstSource=records[0].dataset.sourceId;
const periodSelect=document.getElementById("comparison-period");
const earlierRow=records.find(row=>Number(row.children[1].textContent)>0);
if(earlierRow){
  earlierRow.children[1].querySelector("button").click();
  body.dataset.earlierJump=String(sourceSelect.value===earlierRow.dataset.sourceId &&
    periodSelect.value==="earlier");
}else{
  // This real temporal fixture can have no earlier evidence. Do not invent it.
  body.dataset.earlierJump=String(records.every(row=>
    Number(row.children[1].textContent)===0 &&
    row.children[1].querySelector("button")===null));
}
const laterRow=records.find(row=>Number(row.children[2].textContent)>0);
laterRow.children[2].querySelector("button").click();
body.dataset.laterJump=String(sourceSelect.value===laterRow.dataset.sourceId &&
  periodSelect.value==="later");
body.dataset.zeroCellsPlain=String(records.every(row=>
  [1,2].every(i=>Number(row.children[i].textContent)!==0 ||
    row.children[i].querySelector("button")===null)));
periodSelect.value="later";
periodSelect.dispatchEvent(new Event("change"));
body.dataset.coverageAfterFiltering=String(
  document.getElementById("comparison-source-total").textContent===originalCount);
const presence=document.getElementById("comparison-source-presence");
sourceSelect.value="";periodSelect.value="";
["both","earlier-only","later-only"].forEach(function(group){
  presence.value=group;presence.dispatchEvent(new Event("change"));
  body.dataset["coverageGroup"+group.replace("-","")]=
    document.getElementById("comparison-period-summary").textContent.split(" original")[0];
});
document.getElementById("comparison-all-sources").click();
body.dataset.sourceAfterReset=String(sourceSelect.value===""&&presence.value==="");
body.dataset.coverageGroupReset=document.getElementById("comparison-period-summary")
  .textContent.split(" original")[0];
</script>"""
        output = Path(self.folder.name) / "coverage-comparison-offline.html"
        output.write_text(html.replace("</body>", probe + "</body>"), encoding="utf-8")
        rendered = subprocess.run([
            browser, "--headless", "--no-sandbox", "--disable-gpu",
            "--disable-dev-shm-usage", "--dump-dom", output.as_uri()],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
            check=True).stdout.decode("utf-8")
        self.assertIn('data-monde-ready="true"', rendered)
        self.assertIn('data-coverage-open="true"', rendered)
        self.assertIn('data-coverage-count="' + str(len(actual)) + '"', rendered)
        self.assertIn('data-coverage-rows="' + expected + '"', rendered)
        self.assertIn('data-earlier-jump="true"', rendered)
        self.assertIn('data-later-jump="true"', rendered)
        self.assertIn('data-zero-cells-plain="true"', rendered)
        self.assertIn('data-coverage-after-filtering="true"', rendered)
        self.assertIn('data-source-after-reset="true"', rendered)
        for group, expected_count in class_counts.items():
            attr = "coverage-group" + group.replace("-", "")
            self.assertIn(f'data-{attr}="{expected_count}"', rendered)
        self.assertIn('data-coverage-group-reset="' +
                      str(len(embedded["features"])) + '"', rendered)
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_comparison_source_coverage_is_not_active_on_regular_maps(self):
        status, _, comparison = self.fetch("/disagreement-compare.html",
            {**QUERY, "from_known_at": "2026-01-09T00:00:00Z"})
        self.assertEqual(status, 200)
        self.assertIn(b'id="comparison-source-coverage" hidden', comparison)
        status, _, current = self.fetch("/viewer", {"view": "current", **QUERY})
        self.assertEqual(status, 200)
        self.assertIn(b'id="comparison-source-coverage" hidden', current)
        self.assertEqual(self.path.read_bytes(), self.before)


    def test_complete_source_coverage_csv_offline_matches_embedded_originals(self):
        """Export complete source counts, not display-filtered counts, in offline Chromium."""
        import shutil
        import subprocess
        browser = next((p for name in ("google-chrome", "chromium", "chromium-browser")
                        if (p := shutil.which(name))), None)
        if browser is None:
            self.skipTest("Chromium unavailable; GitHub Actions runs browser integration")
        params = {**QUERY, "source": "survey-east", "entity": "site-a",
                  "from_known_at": "2026-01-09T00:00:00Z"}
        status, _, body = self.fetch("/disagreement-compare.html", params)
        self.assertEqual(status, 200)
        original = body.decode("utf-8")
        embedded = self.embedded_map(original)
        counts = {}
        for feature in embedded["features"]:
            props = feature["properties"]
            row = counts.setdefault(props["source_id"], [0, 0])
            row[0 if props["monde_comparison_period"] == "earlier" else 1] += 1
        self.assertTrue(counts)
        probe = """<script>
const body=document.body, rows=document.querySelectorAll("#comparison-source-rows tr");
const NativeBlob=window.Blob;
window.Blob=function(parts,options){
  const csv=String(parts[0]);
  const lines=csv.replace(/^\\uFEFF/,"").trim().split("\\r\\n");
  body.dataset.coverageCsvRows=String(lines.length-1);
  body.dataset.coverageCsvHeader=String(lines[0].includes("selection_coverage"));
  body.dataset.coverageCsvScope=String(csv.includes("COMPLETE_EMBEDDED_SOURCE_SELECTION_NOT_DISPLAY_FILTERED"));
  body.dataset.coverageCsvCounts=lines.slice(1).map(line=>{
    const fields=line.split('","');
    return fields[1]+":"+fields[2]+":"+fields[3];
  }).join("|");
  return new NativeBlob(parts,options);
};
HTMLAnchorElement.prototype.click=function(){body.dataset.coverageCsvFilename=this.download;};
document.getElementById("sources").value=rows[0].dataset.sourceId;
document.getElementById("sources").dispatchEvent(new Event("change"));
document.getElementById("comparison-period").value="later";
document.getElementById("comparison-period").dispatchEvent(new Event("change"));
const presence=document.getElementById("comparison-source-presence");
presence.value="earlier-only";presence.dispatchEvent(new Event("change"));
document.getElementById("comparison-export-coverage-csv").click();
body.dataset.coverageCsvDisplayFilter=document.getElementById("comparison-period").value;
</script>"""
        output = Path(self.folder.name) / "source-coverage-export.html"
        output.write_text(original.replace("</body>", probe + "</body>"),
                          encoding="utf-8")
        rendered = subprocess.run([
            browser, "--headless", "--no-sandbox", "--disable-gpu",
            "--disable-dev-shm-usage", "--dump-dom", output.as_uri()],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=30, check=True).stdout.decode("utf-8")
        self.assertIn('data-monde-ready="true"', rendered)
        self.assertIn('data-coverage-csv-rows="' + str(len(counts)) + '"', rendered)
        self.assertIn('data-coverage-csv-header="true"', rendered)
        self.assertIn('data-coverage-csv-scope="true"', rendered)
        self.assertIn('data-coverage-csv-filename="monde-original-source-period-coverage.csv"', rendered)
        self.assertIn('data-coverage-csv-display-filter="later"', rendered)
        expected = "|".join(f"{source}:{values[0]}:{values[1]}"
                            for source, values in sorted(counts.items()))
        # Assert the CSV's actual per-source counts, not independently visible
        # DOM text or HTML escaping in attributes.
        self.assertIn('data-coverage-csv-counts="' + expected + '"', rendered)
        self.assertEqual(self.path.read_bytes(), self.before)



    def test_coverage_row_download_contains_exact_original_source_evidence(self):
        """Source-scoped two-period GeoJSON is independent of map display filters."""
        import shutil
        import subprocess
        browser = next((p for name in ("google-chrome", "chromium", "chromium-browser")
                        if (p := shutil.which(name))), None)
        if browser is None:
            self.skipTest("Chromium unavailable; GitHub Actions runs browser integration")
        params = {**QUERY, "source": "survey-east", "entity": "site-a",
                  "from_known_at": "2026-01-09T00:00:00Z"}
        status, _, body = self.fetch("/disagreement-compare.html", params)
        self.assertEqual(status, 200)
        html = body.decode("utf-8")
        document = self.embedded_map(html)
        sources = sorted({f["properties"]["source_id"] for f in document["features"]})
        self.assertTrue(sources)
        source = sources[0]
        expected = [f for f in document["features"]
                    if f["properties"]["source_id"] == source]
        earlier = sum(f["properties"]["monde_comparison_period"] == "earlier"
                      for f in expected)
        later = sum(f["properties"]["monde_comparison_period"] == "later"
                    for f in expected)
        probe = """<script>
const body=document.body,source=__SOURCE__,expected=__EXPECTED__;
const row=Array.from(document.querySelectorAll("#comparison-source-rows tr"))
  .find(x=>x.dataset.sourceId===source);
body.dataset.sourceDownloadButton=String(Boolean(row && row.children[5]
  .querySelector("button")));
const NativeBlob=window.Blob;
window.Blob=function(parts,options){
  if(options && options.type && options.type.startsWith("text/csv")){
    const csv=String(parts[0]),lines=csv.replace(/^\\uFEFF/,"").trimEnd().split("\\r\\n");
    const assertions=expected.map(f=>String(f.properties.assertion_id||
      f.properties.monde_original_feature_id));
    body.dataset.sourceCsvIntegrity=String(
      lines.length===expected.length+1 &&
      lines[0].includes("assertion_id") &&
      lines[0].includes("source_id") &&
      lines[0].includes("period") &&
      lines[0].includes("export_scope") &&
      lines.slice(1).every(line=>line.includes('"'+source.replace(/"/g,'""')+'"')) &&
      assertions.every(id=>csv.includes('"'+id.replace(/"/g,'""')+'"')) &&
      csv.includes("COMPLETE_EMBEDDED_SOURCE_SELECTION_NOT_DISPLAY_FILTERED"));
    return new NativeBlob(parts,options);
  }
  const output=JSON.parse(String(parts[0]));
  const meta=output.monde_source_period_export;
  body.dataset.sourceDownloadIntegrity=String(
    JSON.stringify(output.features)===JSON.stringify(expected) &&
    meta.source_id===source && meta.selected_period==="both" &&
    meta.earlier_original_report_count===__EARLIER__ &&
    meta.later_original_report_count===__LATER__ &&
    meta.original_feature_count>=expected.length &&
    meta.exported_feature_count===expected.length &&
    meta.scope==="COMPLETE_EMBEDDED_SOURCE_NOT_DISPLAY_FILTERED" &&
    output.monde_comparison.axis!==undefined);
  return new NativeBlob(parts,options);
};
HTMLAnchorElement.prototype.click=function(){
  if(this.download.endsWith(".csv"))body.dataset.sourceCsvFilename=this.download;
  else body.dataset.sourceDownloadFilename=this.download;
};
const selection=document.getElementById("sources");
selection.value=source;selection.dispatchEvent(new Event("change"));
const period=document.getElementById("comparison-period");
period.value="later";period.dispatchEvent(new Event("change"));
const search=document.getElementById("report-search");
search.value="no-visible-match";search.dispatchEvent(new Event("input"));
row.children[5].querySelector("button").click();
row.children[5].querySelectorAll("button")[1].click();
body.dataset.sourceDownloadPeriodUnchanged=String(period.value==="later");
</script>"""
        probe = (probe.replace("__SOURCE__", json.dumps(source))
                      .replace("__EXPECTED__", json.dumps(expected))
                      .replace("__EARLIER__", str(earlier))
                      .replace("__LATER__", str(later)))
        output = Path(self.folder.name) / "source-original-export.html"
        output.write_text(html.replace("</body>", probe + "</body>"),
                          encoding="utf-8")
        rendered = subprocess.run([
            browser, "--headless", "--no-sandbox", "--disable-gpu",
            "--disable-dev-shm-usage", "--dump-dom", output.as_uri()],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=30, check=True).stdout.decode("utf-8")
        self.assertIn('data-monde-ready="true"', rendered)
        self.assertIn('data-source-download-button="true"', rendered)
        self.assertIn('data-source-download-integrity="true"', rendered)
        self.assertIn('data-source-download-period-unchanged="true"', rendered)
        self.assertIn('data-source-csv-integrity="true"', rendered)
        self.assertIn('data-source-csv-filename="monde-original-source-both-periods.csv"', rendered)
        self.assertIn('data-source-download-filename="monde-original-source-both-periods.geojson"',
                      rendered)
        self.assertEqual(self.path.read_bytes(), self.before)



    def test_source_entity_comparison_shows_all_embedded_reports(self):
        """Real offline browser: inspect source/entity evidence despite display filters."""
        import shutil
        import subprocess
        browser = next((p for name in ("google-chrome", "chromium", "chromium-browser")
                        if (p := shutil.which(name))), None)
        if browser is None:
            self.skipTest("Chromium unavailable; GitHub Actions includes headless Chromium")
        status, _, response = self.fetch("/disagreement-compare.html", {
            **QUERY, "source": "survey-east", "entity": "site-a",
            "from_known_at": "2026-01-09T00:00:00Z"})
        self.assertEqual(status, 200)
        html = response.decode("utf-8")
        embedded = self.embedded_map(html)
        source = embedded["features"][0]["properties"]["source_id"]
        evidence = [f for f in embedded["features"] if f["properties"]["source_id"] == source]
        self.assertTrue(evidence)
        probe = """<script>
const root=document.body,src=__SOURCE__,expected=__EVIDENCE__;
const referenceComparison=__COMPARISON__;
const tr=Array.from(document.querySelectorAll("#comparison-source-rows tr"))
  .find(x=>x.dataset.sourceId===src);
const button=Array.from(tr.children[5].querySelectorAll("button"))
  .find(x=>x.textContent==="Compare entities");
const period=document.getElementById("comparison-period");
period.value="later";period.dispatchEvent(new Event("change"));
const search=document.getElementById("report-search");
search.value="no-such-visible-item";search.dispatchEvent(new Event("input"));
button.click();
const expansion=tr.nextElementSibling;
const actual=Array.from(expansion.querySelectorAll("p[data-period]"));
const entityNames=Array.from(expansion.querySelectorAll("li[data-entity]"))
  .map(x=>x.dataset.entity).sort();
const originalNames=Array.from(new Set(expected.map(x=>x.properties.entity))).sort();
root.dataset.sourceEntityComplete=String(
  button.getAttribute("aria-expanded")==="true" &&
  expansion.className==="comparison-source-entities" &&
  expansion.dataset.sourceId===src &&
  actual.length===expected.length &&
  JSON.stringify(entityNames)===JSON.stringify(originalNames) &&
  expected.every(f=>actual.some(p=>
    p.dataset.period===f.properties.monde_comparison_period &&
    p.textContent.includes(String(f.properties.assertion_id||
      f.properties.monde_original_feature_id)) &&
    p.textContent.includes(String(f.properties.evidence_id)) &&
    p.textContent.includes(f.geometry.coordinates.join(", ")))));
root.dataset.sourceEntityFiltersPreserved=String(
  period.value==="later" && search.value==="no-such-visible-item");
const chosenEntity=originalNames[0];
const row=Array.from(expansion.querySelectorAll("li[data-entity]"))
  .find(x=>x.dataset.entity===chosenEntity);
const expectedEntity=expected.filter(x=>x.properties.entity===chosenEntity);
const NativeBlob=window.Blob;
let geoOK=false,csvOK=false;
window.Blob=function(parts,options){
  if(options && options.type && options.type.startsWith("text/csv")){
    const csv=String(parts[0]);
    csvOK=csv.includes("COMPLETE_EMBEDDED_SOURCE_SELECTION_NOT_DISPLAY_FILTERED") &&
      csv.trimEnd().split("\\r\\n").length===expectedEntity.length+1 &&
      expectedEntity.every(f=>csv.includes('"'+String(f.properties.assertion_id||
        f.properties.monde_original_feature_id).replace(/"/g,'""')+'"'));
  }else if(options && options.type==="application/geo+json"){
    const output=JSON.parse(String(parts[0])),meta=output.monde_source_entity_export;
    geoOK=JSON.stringify(output.features)===JSON.stringify(expectedEntity) &&
      meta.scope==="COMPLETE_EMBEDDED_SOURCE_ENTITY_NOT_DISPLAY_FILTERED" &&
      meta.source_id===src && meta.entity===chosenEntity &&
      meta.selected_period==="both" &&
      meta.exported_feature_count===expectedEntity.length &&
      meta.earlier_original_report_count===expectedEntity.filter(f=>
        f.properties.monde_comparison_period==="earlier").length &&
      meta.later_original_report_count===expectedEntity.filter(f=>
        f.properties.monde_comparison_period==="later").length;
  }
  return new NativeBlob(parts,options);
};
HTMLAnchorElement.prototype.click=function(){
  if(this.download.endsWith(".csv"))root.dataset.entityCsvFilename=this.download;
  else root.dataset.entityGeoFilename=this.download;
};
// Only the three export/navigation actions, not report-level focus buttons.
const exports=row.querySelector("details > div").querySelectorAll("button");
root.dataset.entityExportButtons=String(exports.length===3);
exports[0].click();exports[1].click();
root.dataset.entityGeoComplete=String(geoOK);
root.dataset.entityCsvComplete=String(csvOK);
root.dataset.entityBothGeoFilename=root.dataset.entityGeoFilename;
root.dataset.entityBothCsvFilename=root.dataset.entityCsvFilename;
root.dataset.entityExportFiltersPreserved=String(
  period.value==="later" && search.value==="no-such-visible-item");
// Browser-level earlier/later evidence export must ignore presentation filters.
const entityPeriod=row.querySelector('select[aria-label^="Export original entity period for"]');
root.dataset.entityPeriodDefaultsBoth=String(entityPeriod?.value==="both");
const oldBlob=window.Blob;
for(const selected of ["earlier","later"]){
  let actualGeo=false,actualCsv=false;
  const chosen=expectedEntity.filter(f=>f.properties.monde_comparison_period===selected);
  entityPeriod.value=selected;
  window.Blob=function(parts,options){
    if(options.type==="application/geo+json"){
      const obj=JSON.parse(String(parts[0])),meta=obj.monde_source_entity_export;
      actualGeo=JSON.stringify(obj.features)===JSON.stringify(chosen) &&
        meta.scope==="COMPLETE_EMBEDDED_SOURCE_ENTITY_SELECTED_PERIOD_NOT_DISPLAY_FILTERED" &&
        meta.source_id===src && meta.entity===chosenEntity &&
        meta.selected_period===selected && meta.exported_feature_count===chosen.length &&
        meta.earlier_original_report_count===expectedEntity.filter(f=>
          f.properties.monde_comparison_period==="earlier").length &&
        meta.later_original_report_count===expectedEntity.filter(f=>
          f.properties.monde_comparison_period==="later").length;
    }else if(options.type.startsWith("text/csv")){
      const csv=String(parts[0]);
      actualCsv=csv.includes("source_id") &&
        csv.trimEnd().split(String.fromCharCode(13,10)).length===chosen.length+1 &&
        chosen.every(f=>csv.includes('"'+String(f.properties.assertion_id||
          f.properties.monde_original_feature_id).replace(/"/g,'""')+'"'));
    }
    return new NativeBlob(parts,options);
  };
  exports[0].click();exports[1].click();
  root.dataset["entity"+(selected==="earlier"?"Earlier":"Later")+"ExportComplete"]=
    String(actualGeo && actualCsv &&
      root.dataset.entityGeoFilename==="monde-original-source-entity-"+selected+"-period.geojson" &&
      root.dataset.entityCsvFilename==="monde-original-source-entity-"+selected+"-period.csv" &&
      period.value==="later" && search.value==="no-such-visible-item");
}
window.Blob=oldBlob;
// Navigate from comparison evidence to its source/entitity map without
// changing the complete underlying embedded original selection.
const show=Array.from(exports).find(x=>x.textContent==="Show both periods on map");
show?.click();
root.dataset.entityFocusMap=String(
  !!show && document.getElementById("sources").value===src &&
  document.getElementById("entities").value===chosenEntity &&
  period.value==="" && search.value==="" &&
  document.querySelectorAll("#points circle").length===expectedEntity.length &&
  document.getElementById("fit-reports").disabled===false);
// Navigate from a hidden original report to its exact period/point and
// verify the existing evidence inspector selects THAT assertion.
const one=expectedEntity[0];
const samePeriod=expectedEntity.filter(f=>
  f.properties.monde_comparison_period===one.properties.monde_comparison_period);
const originalEntry=Array.from(row.querySelectorAll("p[data-period]"))
  .find(p=>p.dataset.period===one.properties.monde_comparison_period &&
    p.textContent.includes(String(one.properties.assertion_id||
      one.properties.monde_original_feature_id)) &&
    p.textContent.includes(String(one.properties.evidence_id)));
const reportJump=Array.from(originalEntry?.querySelectorAll("button")||[])
  .find(b=>b.textContent==="Show this original report on map");
period.value=one.properties.monde_comparison_period==="earlier"?"later":"earlier";
search.value="no-such-visible-item";search.dispatchEvent(new Event("input"));
const originalDownload=Array.from(originalEntry?.querySelectorAll("button")||[])
  .find(b=>b.textContent==="Download this original report");
let exactDownloaded=false;
window.Blob=function(parts,options){
  if(options?.type==="application/geo+json"){
    const single=JSON.parse(String(parts[0]));
    const meta=single.monde_single_report_export;
    exactDownloaded=single.type==="FeatureCollection" &&
      JSON.stringify(single.features)===JSON.stringify([one]) &&
      JSON.stringify(single.monde_comparison)===JSON.stringify(referenceComparison) &&
      meta.scope==="EXACT_ORIGINAL_ASSERTION_NOT_DISPLAY_FILTERED" &&
      meta.source_id===src && meta.entity===chosenEntity &&
      meta.comparison_period===one.properties.monde_comparison_period &&
      meta.assertion_id===(one.properties.assertion_id||
        one.properties.monde_original_feature_id) &&
      meta.original_feature_id===one.id &&
      meta.evidence_id===one.properties.evidence_id &&
      meta.exported_feature_count===1;
  }
  return new NativeBlob(parts,options);
};
HTMLAnchorElement.prototype.click=function(){
  root.dataset.originalReportFilename=this.download;
};
originalDownload?.click();
root.dataset.originalReportExactExport=String(
  !!originalDownload && exactDownloaded &&
  root.dataset.originalReportFilename==="monde-original-report.geojson" &&
  period.value!==one.properties.monde_comparison_period &&
  search.value==="no-such-visible-item");
window.Blob=oldBlob;
reportJump?.click();
const exactMarker=Array.from(document.querySelectorAll("#points circle.selected"));
const selectedText=document.getElementById("details").textContent;
root.dataset.entityExactDiagnostic=[
  Boolean(originalEntry),Boolean(reportJump),
  document.getElementById("sources").value===src,
  document.getElementById("entities").value===chosenEntity,
  period.value===one.properties.monde_comparison_period,
  search.value==="",
  document.querySelectorAll("#points circle").length===samePeriod.length,
  exactMarker.length===1,
  selectedText.includes("Assertion: "+String(one.id)),
  selectedText.includes("Evidence: "+String(one.properties.evidence_id)),
  document.getElementById("focus-selected").disabled===false
].map(x=>x?"1":"0").join("");
root.dataset.entityExactReportMap=String(
  !!reportJump && document.getElementById("sources").value===src &&
  document.getElementById("entities").value===chosenEntity &&
  period.value===one.properties.monde_comparison_period &&
  search.value==="" &&
  document.querySelectorAll("#points circle").length===samePeriod.length &&
  exactMarker.length===1 &&
  selectedText.includes("Assertion: "+String(one.id)) &&
  selectedText.includes("Evidence: "+String(one.properties.evidence_id)) &&
  document.getElementById("focus-selected").disabled===false);
button.click();
root.dataset.sourceEntityClosed=String(
  button.getAttribute("aria-expanded")==="false" &&
  !tr.nextElementSibling?.classList.contains("comparison-source-entities"));
</script>"""
        probe = (probe.replace("__SOURCE__", json.dumps(source))
                      .replace("__EVIDENCE__", json.dumps(evidence))
                      .replace("__COMPARISON__", json.dumps(embedded.get("monde_comparison"))))
        target = Path(self.folder.name) / "source-entity-comparison.html"
        target.write_text(html.replace("</body>", probe + "</body>"), encoding="utf-8")
        result = subprocess.run([
            browser, "--headless", "--no-sandbox", "--disable-gpu",
            "--disable-dev-shm-usage", "--dump-dom", target.as_uri()],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
            check=True).stdout.decode("utf-8")
        self.assertIn('data-monde-ready="true"', result)
        self.assertIn('data-source-entity-complete="true"', result)
        self.assertIn('data-source-entity-filters-preserved="true"', result)
        self.assertIn('data-source-entity-closed="true"', result)
        self.assertIn('data-entity-export-buttons="true"', result)
        self.assertIn('data-entity-geo-complete="true"', result)
        self.assertIn('data-entity-csv-complete="true"', result)
        self.assertIn('data-entity-export-filters-preserved="true"', result)
        self.assertIn('data-entity-period-defaults-both="true"', result)
        self.assertIn('data-entity-focus-map="true"', result)
        self.assertIn('data-entity-exact-report-map="true"', result)
        self.assertIn('data-original-report-exact-export="true"', result)
        self.assertIn('data-original-report-filename="monde-original-report.geojson"', result)
        self.assertIn('data-entity-earlier-export-complete="true"', result)
        self.assertIn('data-entity-later-export-complete="true"', result)
        self.assertIn('data-entity-both-geo-filename="monde-original-source-entity-both-periods.geojson"', result)
        self.assertIn('data-entity-both-csv-filename="monde-original-source-entity-both-periods.csv"', result)
        self.assertEqual(self.path.read_bytes(), self.before)


    def test_source_entity_inventory_csv_matches_original_periods_despite_filters(self):
        """Actual Chromium export: every entity and original ID, independent of presentation."""
        import base64
        import re
        import shutil
        import subprocess
        browser = next((p for name in ("google-chrome", "chromium", "chromium-browser")
                        if (p := shutil.which(name))), None)
        if browser is None:
            self.skipTest("Chromium unavailable; GitHub Actions runs browser integration")
        status, _, response = self.fetch("/disagreement-compare.html", {
            **QUERY, "source": "survey-east", "entity": "site-a",
            "from_known_at": "2026-01-09T00:00:00Z"})
        self.assertEqual(status, 200)
        html = response.decode("utf-8")
        embedded = self.embedded_map(html)
        source = embedded["features"][0]["properties"]["source_id"]
        expected = [f for f in embedded["features"]
                    if f["properties"]["source_id"] == source]
        self.assertTrue(expected)
        probe = """<script>
const body=document.body,source=__SOURCE__;
const row=Array.from(document.querySelectorAll("#comparison-source-rows tr"))
  .find(x=>x.dataset.sourceId===source);
const period=document.getElementById("comparison-period");
period.value="later";period.dispatchEvent(new Event("change"));
const search=document.getElementById("report-search");
search.value="absent-original-report";search.dispatchEvent(new Event("input"));
const NativeBlob=window.Blob;
window.Blob=function(parts,options) {
  if(options?.type?.startsWith("text/csv"))
    body.dataset.inventoryCsvBase64=btoa(unescape(encodeURIComponent(String(parts[0]))));
  return new NativeBlob(parts,options);
};
HTMLAnchorElement.prototype.click=function(){
  body.dataset.inventoryFilename=this.download;
};
Array.from(row.children[5].querySelectorAll("button"))
  .find(x=>x.textContent==="Download entity inventory CSV").click();
body.dataset.inventoryFiltersPreserved=String(period.value==="later" &&
  search.value==="absent-original-report");
</script>""".replace("__SOURCE__", json.dumps(source))
        target = Path(self.folder.name) / "source-entity-inventory.html"
        target.write_text(html.replace("</body>", probe + "</body>"), encoding="utf-8")
        rendered = subprocess.run(
            [browser, "--headless", "--no-sandbox", "--disable-gpu",
             "--disable-dev-shm-usage", "--dump-dom", target.as_uri()],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
            check=True).stdout.decode("utf-8")
        self.assertIn('data-monde-ready="true"', rendered)
        self.assertIn('data-inventory-filename="monde-original-source-entity-inventory.csv"',
                      rendered)
        self.assertIn('data-inventory-filters-preserved="true"', rendered)
        matched = re.search(r'data-inventory-csv-base64="([A-Za-z0-9+/=]+)"', rendered)
        self.assertIsNotNone(matched, "Inventory export was not generated")
        payload = base64.b64decode(matched.group(1)).decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(payload)))
        keys = {(feature["properties"]["source_id"], feature["properties"]["entity"])
                for feature in expected}
        self.assertEqual({(row["source_id"], row["entity"]) for row in rows}, keys)
        for row in rows:
            reports = [f for f in expected if f["properties"]["entity"] == row["entity"]]
            self.assertEqual(row["source_id"], source)
            self.assertEqual(row["comparison_axis"], embedded["monde_comparison"]["axis"])
            for period_name in ("earlier", "later"):
                subset = [f for f in reports
                          if f["properties"]["monde_comparison_period"] == period_name]
                self.assertEqual(int(row[period_name + "_original_report_count"]), len(subset))
                self.assertEqual(json.loads(row[period_name + "_assertion_ids_json"]),
                                 [str(f["properties"].get("assertion_id") or
                                      f["properties"].get("monde_original_feature_id"))
                                  for f in subset])
                self.assertEqual(json.loads(row[period_name + "_evidence_ids_json"]),
                                 [str(f["properties"]["evidence_id"]) for f in subset])
            earlier = int(row["earlier_original_report_count"])
            later = int(row["later_original_report_count"])
            self.assertEqual(row["selection_coverage"],
                "BOTH_SELECTIONS" if earlier and later else
                "EARLIER_SELECTION_ONLY" if earlier else "LATER_SELECTION_ONLY")
            self.assertEqual(row["export_scope"],
                "COMPLETE_EMBEDDED_SOURCE_ENTITY_INVENTORY_NOT_DISPLAY_FILTERED")
        self.assertEqual(self.path.read_bytes(), self.before)


    def test_entity_first_source_coverage_csv_and_map_navigation(self):
        """Live HTTP/Chromium: entity/source/period inventory ignores display filters."""
        import base64
        import re
        import shutil
        import subprocess
        from collections import defaultdict

        browser = next((p for name in ("google-chrome", "chromium", "chromium-browser")
                        if (p := shutil.which(name))), None)
        if browser is None:
            self.skipTest("Chromium unavailable; GitHub Actions runs browser integration")
        status, _, body = self.fetch("/disagreement-compare.html", {
            **QUERY, "source": "survey-east", "entity": "site-a",
            "from_known_at": "2026-01-09T00:00:00Z"})
        self.assertEqual(status, 200)
        html = body.decode("utf-8")
        embedded = self.embedded_map(html)
        records = defaultdict(lambda: {"earlier": [], "later": []})
        for f in embedded["features"]:
            p = f["properties"]
            records[(p["entity"], p["source_id"])][p["monde_comparison_period"]].append(f)
        self.assertTrue(records, "Expected original source/entity evidence")
        expected_entities = sorted({entity for entity, _ in records})
        turnover = {}
        for entity in expected_entities:
            earlier_sources = {source for (candidate, source), periods in records.items()
                               if candidate == entity and periods["earlier"]}
            later_sources = {source for (candidate, source), periods in records.items()
                             if candidate == entity and periods["later"]}
            turnover[entity] = "changed" if earlier_sources != later_sources else "same"
        probe = """<script>
const root=document.body,records=__RECORDS__,entities=__ENTITIES__;
const turnover=__TURNOVER__;
const panel=document.getElementById("comparison-entity-coverage");
const rows=Array.from(document.querySelectorAll("#comparison-entity-rows tr"));
root.dataset.entityMatrixRendered=String(
  panel && !panel.hidden && rows.length===entities.length &&
  rows.every(r=>entities.includes(r.dataset.entity)));
root.dataset.turnoverClassification=String(rows.every(
  r=>r.dataset.sourceTurnover===turnover[r.dataset.entity]));
const turnoverFilter=document.getElementById("comparison-entity-turnover");
for(const mode of ["changed","same","all"]){
  turnoverFilter.value=mode;turnoverFilter.dispatchEvent(new Event("change"));
  root.dataset["turnover"+mode.charAt(0).toUpperCase()+mode.slice(1)]=
    String(rows.every(r=>r.hidden===(mode!=="all"&&turnover[r.dataset.entity]!==mode)));
}
const period=document.getElementById("comparison-period");
period.value="later";period.dispatchEvent(new Event("change"));
const search=document.getElementById("report-search");
search.value="not-a-visible-report";search.dispatchEvent(new Event("input"));
const NativeBlob=window.Blob;
window.Blob=function(parts,options){
  if(options && options.type.startsWith("text/csv"))
    root.dataset.entityMatrixCsv=btoa(unescape(encodeURIComponent(String(parts[0]))));
  return new NativeBlob(parts,options);
};
HTMLAnchorElement.prototype.click=function(){root.dataset.entityMatrixFilename=this.download;};
document.getElementById("comparison-export-entity-changes-csv").click();
root.dataset.turnoverCsv=root.dataset.entityMatrixCsv;
root.dataset.turnoverFilename=root.dataset.entityMatrixFilename;
document.getElementById("comparison-export-entity-coverage-csv").click();
root.dataset.entityMatrixFiltersPreserved=String(period.value==="later" &&
  search.value==="not-a-visible-report");
window.Blob=NativeBlob;
const target=rows.find(r=>r.dataset.entity===entities[0]);
const exportPeriod=document.getElementById("comparison-entity-export-period");
const exportEntity=target.querySelector('button[aria-label^="Download complete original evidence for entity"]');
root.dataset.entityGeojsonButton=String(!!exportEntity);
window.Blob=function(parts,options){
  if(options && options.type==="application/geo+json")
    root.dataset.entityGeojson=btoa(unescape(encodeURIComponent(String(parts[0]))));
  return new NativeBlob(parts,options);
};
HTMLAnchorElement.prototype.click=function(){root.dataset.entityGeojsonFilename=this.download;};
for(const selected of ["earlier","later","both"]){
  exportPeriod.value=selected;
  exportEntity.click();
  root.dataset["entityGeojson"+selected.charAt(0).toUpperCase()+selected.slice(1)]=
    root.dataset.entityGeojson;
}
root.dataset.entityGeojsonFiltersPreserved=String(period.value==="later" &&
  search.value==="not-a-visible-report" && exportPeriod.value==="both");
window.Blob=NativeBlob;
// Exact intersection exports remain complete even with conflicting display
// controls active. Capture each available earlier/later/both download.
const intersectionButtons=Array.from(target.querySelectorAll(
  "button[data-export-source-id][data-export-period]"));
const intersectionExports=[];
window.Blob=function(parts,options){
  if(options && options.type==="application/geo+json")
    root.dataset.intersectionPayload=String(parts[0]);
  return new NativeBlob(parts,options);
};
HTMLAnchorElement.prototype.click=function(){
  root.dataset.intersectionFilename=this.download;
};
for(const mode of ["earlier","later","both"]){
  const btn=intersectionButtons.find(b=>b.dataset.exportPeriod===mode);
  if(!btn)continue;
  btn.click();
  intersectionExports.push({
    source:btn.dataset.exportSourceId,period:mode,
    payload:root.dataset.intersectionPayload
  });
}
root.dataset.intersectionExports=btoa(unescape(encodeURIComponent(
  JSON.stringify(intersectionExports))));
root.dataset.intersectionFiltersPreserved=String(
  period.value==="later" && search.value==="not-a-visible-report");
window.Blob=NativeBlob;
// An entity/source/period intersection must navigate to *that* report set,
// not only to the source as a whole or whatever is currently visible.
const intersect=target.querySelector("td:nth-child(2) button") ||
  target.querySelector("td:nth-child(3) button") ||
  target.querySelector("td:nth-child(4) button");
const selectedSource=intersect && intersect.dataset.sourceId;
const selectedPeriod=intersect && intersect.dataset.period;
if(intersect)intersect.click();
root.dataset.entityMatrixSourceDrilldown=String(!!intersect &&
  document.getElementById("entities").value===entities[0] &&
  document.getElementById("sources").value===selectedSource &&
  document.getElementById("comparison-period").value===
    (selectedPeriod==="both"?"":selectedPeriod) &&
  document.getElementById("report-search").value==="" &&
  !document.getElementById("current-view-only").checked);
target.querySelector("button").click();
root.dataset.entityMatrixNavigation=String(
  document.getElementById("entities").value===entities[0] &&
  document.getElementById("sources").value==="" &&
  document.getElementById("comparison-period").value==="" &&
  document.getElementById("report-search").value==="");
</script>""".replace("__RECORDS__", json.dumps(len(records))).replace(
            "__ENTITIES__", json.dumps(expected_entities)).replace(
            "__TURNOVER__", json.dumps(turnover))
        target = Path(self.folder.name) / "entity-source-coverage.html"
        target.write_text(html.replace("</body>", probe + "</body>"), encoding="utf-8")
        rendered = subprocess.run([
            browser, "--headless", "--no-sandbox", "--disable-gpu",
            "--disable-dev-shm-usage", "--dump-dom", target.as_uri()],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
            check=True).stdout.decode("utf-8")
        for attr in ("entity-matrix-rendered", "entity-matrix-filters-preserved",
                     "entity-matrix-source-drilldown", "entity-matrix-navigation",
                     "turnover-classification", "turnover-changed", "turnover-same",
                     "turnover-all"):
            self.assertIn('data-' + attr + '="true"', rendered, attr)
        self.assertIn(
            'data-entity-matrix-filename="monde-original-entity-source-coverage.csv"',
            rendered)
        self.assertIn('data-entity-geojson-button="true"', rendered)
        self.assertIn('data-entity-geojson-filters-preserved="true"', rendered)
        self.assertIn(
            'data-entity-geojson-filename="monde-original-entity-period-reports.geojson"',
            rendered)
        for selected in ("earlier", "later", "both"):
            marker = "data-entity-geojson-" + selected
            result = re.search(marker + r'="([A-Za-z0-9+/=]+)"', rendered)
            self.assertIsNotNone(result, marker)
            doc = json.loads(base64.b64decode(result.group(1)).decode("utf-8"))
            selected_features = [f for f in embedded["features"]
                if f["properties"]["entity"] == expected_entities[0] and
                (selected == "both" or f["properties"]["monde_comparison_period"] == selected)]
            self.assertEqual(doc["features"], selected_features)
            self.assertEqual(doc["monde_comparison"], embedded["monde_comparison"])
            provenance = doc["monde_entity_period_export"]
            self.assertEqual(provenance["scope"],
                             "COMPLETE_EMBEDDED_ENTITY_NOT_DISPLAY_FILTERED")
            self.assertEqual(provenance["entity"], expected_entities[0])
            self.assertEqual(provenance["selected_period"], selected)
            self.assertEqual(provenance["original_feature_count"],
                             len(embedded["features"]))
            self.assertEqual(provenance["exported_feature_count"],
                             len(selected_features))
            self.assertEqual(provenance["earlier_original_report_count"],
                sum(f["properties"]["monde_comparison_period"] == "earlier"
                    for f in selected_features))
            self.assertEqual(provenance["later_original_report_count"],
                sum(f["properties"]["monde_comparison_period"] == "later"
                    for f in selected_features))
        self.assertIn('data-intersection-filters-preserved="true"', rendered)
        self.assertIn(
            'data-intersection-filename="monde-original-entity-source-period-reports.geojson"',
            rendered)
        exported_match = re.search(
            r'data-intersection-exports="([A-Za-z0-9+/=]+)"', rendered)
        self.assertIsNotNone(exported_match, "Intersection export missing")
        intersections = json.loads(base64.b64decode(
            exported_match.group(1)).decode("utf-8"))
        self.assertTrue(intersections, "No source/period download available")
        for item in intersections:
            doc = json.loads(item["payload"])
            expected = [f for f in embedded["features"]
                if f["properties"]["entity"] == expected_entities[0]
                and f["properties"]["source_id"] == item["source"]
                and (item["period"] == "both" or
                     f["properties"]["monde_comparison_period"] == item["period"])]
            self.assertTrue(expected, item)
            self.assertEqual(doc["features"], expected)
            self.assertEqual(doc["monde_comparison"], embedded["monde_comparison"])
            scope = doc["monde_entity_source_period_export"]
            self.assertEqual(scope["scope"],
                "COMPLETE_EMBEDDED_ENTITY_SOURCE_PERIOD_NOT_DISPLAY_FILTERED")
            self.assertEqual(scope["entity"], expected_entities[0])
            self.assertEqual(scope["source_id"], item["source"])
            self.assertEqual(scope["selected_period"], item["period"])
            self.assertEqual(scope["comparison_axis"], embedded["monde_comparison"]["axis"])
            self.assertEqual(scope["exported_feature_count"], len(expected))
            self.assertEqual(scope["original_feature_count"], len(embedded["features"]))
            self.assertEqual(scope["earlier_original_report_count"],
                sum(f["properties"]["monde_comparison_period"] == "earlier" for f in expected))
            self.assertEqual(scope["later_original_report_count"],
                sum(f["properties"]["monde_comparison_period"] == "later" for f in expected))
        self.assertIn('data-turnover-filename="monde-original-reporting-source-selection-changes.csv"',
                      rendered)
        changed_match = re.search(r'data-turnover-csv="([A-Za-z0-9+/=]+)"', rendered)
        self.assertIsNotNone(changed_match, "Reporting-source change CSV missing")
        changed_csv = base64.b64decode(changed_match.group(1)).decode("utf-8-sig")
        changed_rows = list(csv.DictReader(io.StringIO(changed_csv)))
        expected_changes = {
            (entity, source): "SOURCE_IN_EARLIER_SELECTION_ONLY" if periods["earlier"]
                else "SOURCE_IN_LATER_SELECTION_ONLY"
            for (entity, source), periods in records.items()
            if bool(periods["earlier"]) != bool(periods["later"])
        }
        self.assertEqual({(r["entity"], r["source_id"]): r["source_selection_change"]
                          for r in changed_rows}, expected_changes)
        for row in changed_rows:
            periods = records[(row["entity"], row["source_id"])]
            for period in ("earlier", "later"):
                self.assertEqual(int(row[period+"_original_report_count"]),
                                 len(periods[period]))
                self.assertEqual(json.loads(row[period+"_assertion_ids_json"]),
                    [str(f["properties"].get("assertion_id") or
                         f["properties"].get("monde_original_feature_id"))
                     for f in periods[period]])
            self.assertEqual(row["export_scope"],
                "EMBEDDED_SOURCE_SELECTION_CHANGE_NOT_VERIFIED_ABSENCE")
        match = re.search(r'data-entity-matrix-csv="([A-Za-z0-9+/=]+)"', rendered)
        self.assertIsNotNone(match, "Original source/entity CSV not generated")
        payload = base64.b64decode(match.group(1)).decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(payload)))
        self.assertEqual(len(rows), len(records))
        for row in rows:
            periods = records[(row["entity"], row["source_id"])]
            for period in ("earlier", "later"):
                original = periods[period]
                self.assertEqual(int(row[period + "_original_report_count"]),
                                 len(original))
                self.assertEqual(json.loads(row[period + "_assertion_ids_json"]),
                                 [str(f["properties"].get("assertion_id") or
                                      f["properties"].get("monde_original_feature_id"))
                                  for f in original])
                self.assertEqual(json.loads(row[period + "_evidence_ids_json"]),
                                 [str(f["properties"]["evidence_id"]) for f in original])
            self.assertEqual(row["comparison_axis"], embedded["monde_comparison"]["axis"])
            self.assertEqual(row["export_scope"],
                "COMPLETE_EMBEDDED_ENTITY_SOURCE_INVENTORY_NOT_DISPLAY_FILTERED")
        self.assertEqual(self.path.read_bytes(), self.before)


    def test_source_first_entity_coverage_drills_into_original_period_evidence(self):
        """Real HTTP + Chromium: source-first coverage is complete and navigable."""
        import base64
        import re
        import shutil
        import subprocess
        from collections import defaultdict

        browser = next((p for name in ("google-chrome", "chromium", "chromium-browser")
                        if (p := shutil.which(name))), None)
        if browser is None:
            self.skipTest("Chromium unavailable; GitHub Actions runs browser integration")
        status, _, body = self.fetch("/disagreement-compare.html", {
            **QUERY, "source": "survey-east", "entity": "site-a",
            "from_known_at": "2026-01-09T00:00:00Z"})
        self.assertEqual(status, 200)
        html = body.decode("utf-8")
        embedded = self.embedded_map(html)
        observations = defaultdict(lambda: defaultdict(lambda: {"earlier": [], "later": []}))
        for feature in embedded["features"]:
            props = feature["properties"]
            observations[props["source_id"]][props["entity"]][props["monde_comparison_period"]].append(feature)
        self.assertTrue(observations)
        expected = {}
        for source, by_entity in observations.items():
            earlier = {entity for entity, periods in by_entity.items() if periods["earlier"]}
            later = {entity for entity, periods in by_entity.items() if periods["later"]}
            changed = {
                entity: "earlier" if periods["earlier"] else "later"
                for entity, periods in by_entity.items()
                if bool(periods["earlier"]) != bool(periods["later"])
            }
            expected[source] = {
                "earlier": len(earlier), "later": len(later),
                "changed": changed, "reports": sum(
                    len(reports) for periods in by_entity.values()
                    for reports in periods.values())
            }
        expected_exports = {}
        for source, by_entity in observations.items():
            changed_entities = {
                entity for entity, periods in by_entity.items()
                if bool(periods["earlier"]) != bool(periods["later"])
            }
            expected_exports[source] = [
                feature for feature in embedded["features"]
                if feature["properties"]["source_id"] == source
                and feature["properties"]["entity"] in changed_entities
            ]
        script = ("""<script>
const expected=__EXPECTED__,expectedExports=__EXPECTED_EXPORTS__,body=document.body;
const panel=document.getElementById("comparison-source-entity-coverage");
const rows=Array.from(document.querySelectorAll("#comparison-source-entity-rows tr"));
body.dataset.sourceEntityReady=String(!!panel && !panel.hidden &&
  rows.length===Object.keys(expected).length && rows.every(function(row){
    const record=expected[row.dataset.sourceId];
    if(!record)return false;
    const cells=row.querySelectorAll("td");
    const changed=Array.from(row.querySelectorAll("button[data-changed-entity]"));
    return Number(cells[1].textContent)===record.earlier &&
      Number(cells[2].textContent)===record.later &&
      Number(cells[4].textContent)===record.reports &&
      Number(row.dataset.changedEntities)===Object.keys(record.changed).length &&
      changed.length===Object.keys(record.changed).length &&
      changed.every(b=>record.changed[b.dataset.changedEntity]===b.dataset.period);
  }));
const filter=document.getElementById("comparison-source-entity-turnover");
for(const mode of ["changed","same","all"]){
  filter.value=mode;filter.dispatchEvent(new Event("change"));
  body.dataset["sourceEntityFilter"+mode]=String(rows.every(function(row){
    const category=Object.keys(expected[row.dataset.sourceId].changed).length?"changed":"same";
    return row.hidden===(mode!=="all" && category!==mode);
  }));
}
const search=document.getElementById("report-search");
search.value="display-only-nothing";search.dispatchEvent(new Event("input"));
const period=document.getElementById("comparison-period");
period.value="later";period.dispatchEvent(new Event("change"));
const entityLink=document.querySelector("#comparison-source-entity-rows button[data-changed-entity]");
if(entityLink){
  const source=entityLink.closest("tr").dataset.sourceId;
  const entity=entityLink.dataset.changedEntity;
  const selected=entityLink.dataset.period;
  entityLink.click();
  body.dataset.sourceEntityDrilldown=String(
    document.getElementById("sources").value===source &&
    document.getElementById("entities").value===entity &&
    period.value===selected && search.value==="" &&
    !document.getElementById("current-view-only").checked);
}else{
  const row=rows[0],source=row.dataset.sourceId;
  row.querySelector("td button").click();
  body.dataset.sourceEntityDrilldown=String(
    document.getElementById("sources").value===source &&
    document.getElementById("entities").value==="" &&
    period.value==="");
}
// Exercise real saveEvidence Blob generation for *each* original source.
const NativeBlob=window.Blob;
let exportsMatch=true,downloads=0;
const changedResults=[];
window.Blob=function(parts,options){
  if(options&&options.type==="application/geo+json")
    changedResults.push(JSON.parse(String(parts[0])));
  return new NativeBlob(parts,options);
};
HTMLAnchorElement.prototype.click=function(){
  if(this.download.endsWith(".geojson"))
    body.dataset.changedSourceFilename=this.download;
};
search.value="not-on-map";search.dispatchEvent(new Event("input"));
period.value="later";period.dispatchEvent(new Event("change"));
rows.forEach(function(row){
  const source=row.dataset.sourceId;
  const button=row.querySelector("button[data-source-entity-change-export]");
  const expectedReports=expectedExports[source],hasChanges=expectedReports.length>0;
  if(!button||button.disabled===hasChanges){exportsMatch=false;return;}
  if(!hasChanges)return;
  const before=changedResults.length;
  button.click();
  if(changedResults.length!==before+1){exportsMatch=false;return;}
  const output=changedResults[before],meta=output.monde_source_entity_turnover_export;
  const earlierCount=expectedReports.filter(function(f){
    return f.properties.monde_comparison_period==="earlier";
  }).length;
  if(JSON.stringify(output.features)!==JSON.stringify(expectedReports)||
     !meta||meta.source_id!==source||
     meta.comparison_axis!==output.monde_comparison.axis||
     meta.changed_entity_count!==Object.keys(expected[source].changed).length||
     meta.exported_feature_count!==expectedReports.length||
     meta.earlier_original_report_count!==earlierCount||
     meta.later_original_report_count!==expectedReports.length-earlierCount||
     meta.original_feature_count!==__TOTAL_FEATURES__||
     meta.scope!=="COMPLETE_EMBEDDED_CHANGED_ENTITY_SELECTIONS_NOT_DISPLAY_FILTERED"||
     body.dataset.changedSourceFilename!=="monde-original-source-changing-entity-evidence.geojson"||
     search.value!=="not-on-map"||period.value!=="later")exportsMatch=false;
  downloads++;
});
window.Blob=NativeBlob;
body.dataset.changedSourceExport=String(exportsMatch&&
  downloads===Object.keys(expectedExports).filter(function(source){
    return expectedExports[source].length>0;
  }).length);
const marker={};
HTMLAnchorElement.prototype.click=function(){body.dataset.sourceEntityFilename=this.download;};
document.getElementById("comparison-source-entity-export").click();
body.dataset.sourceEntityCsvReused=String(
  body.dataset.sourceEntityFilename==="monde-original-reporting-source-selection-changes.csv");
</script>""".replace("__EXPECTED__", json.dumps(expected))
                     .replace("__EXPECTED_EXPORTS__", json.dumps(expected_exports))
                     .replace("__TOTAL_FEATURES__", str(len(embedded["features"]))))
        target = Path(self.folder.name) / "source-first-coverage.html"
        target.write_text(html.replace("</body>", script+"</body>"), encoding="utf-8")
        output = subprocess.run([
            browser, "--headless", "--no-sandbox", "--disable-gpu",
            "--disable-dev-shm-usage", "--dump-dom", target.as_uri()],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
            check=True).stdout.decode("utf-8")
        for attribute in ("source-entity-ready", "source-entity-drilldown",
                          "source-entity-filterchanged", "source-entity-filtersame",
                          "source-entity-filterall", "source-entity-csv-reused",
                          "changed-source-export"):
            self.assertIn('data-'+attribute+'="true"', output, attribute)
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_source_first_inventory_not_visible_on_noncomparison_map(self):
        response, _, body = self.fetch("/viewer", {**QUERY, "view": "current"})
        self.assertEqual(response, 200)
        self.assertIn(b'id="comparison-source-entity-coverage" hidden', body)


    def test_original_source_pair_same_period_overlap_and_exact_offline_export(self):
        """Real HTTP + offline Chromium: cross-examine two sources without losing evidence."""
        import shutil
        import subprocess
        from collections import defaultdict

        browser = next((p for name in ("google-chrome", "chromium", "chromium-browser")
                        if (p := shutil.which(name))), None)
        if browser is None:
            self.skipTest("Chromium unavailable; GitHub Actions runs browser integration")
        status, _, body = self.fetch("/disagreement-compare.html", {
            **QUERY, "source": "survey-east", "entity": "site-a",
            "from_known_at": "2026-01-09T00:00:00Z"})
        self.assertEqual(status, 200)
        html = body.decode("utf-8")
        embedded = self.embedded_map(html)
        observations = defaultdict(lambda: defaultdict(lambda: {"earlier": [], "later": []}))
        for feature in embedded["features"]:
            p = feature["properties"]
            observations[p["source_id"]][p["entity"]][p["monde_comparison_period"]].append(feature)
        sources = sorted(observations)
        self.assertGreaterEqual(len(sources), 2)
        pair = None
        overlap = {}
        for i, a_source in enumerate(sources):
            for b_source in sources[i+1:]:
                entities = {}
                for entity, a_periods in observations[a_source].items():
                    if entity not in observations[b_source]:
                        continue
                    b_periods = observations[b_source][entity]
                    earlier = bool(a_periods["earlier"] and b_periods["earlier"])
                    later = bool(a_periods["later"] and b_periods["later"])
                    if earlier or later:
                        entities[entity] = {
                            "earlier": earlier, "later": later,
                            "count": sum(len(x) for x in a_periods.values()) +
                                     sum(len(x) for x in b_periods.values())
                        }
                def reported_positions(reports):
                    return {tuple(feature["geometry"]["coordinates"])
                            for feature in reports}
                for entity, item in entities.items():
                    one = observations[a_source][entity]
                    two = observations[b_source][entity]
                    item["different_earlier"] = bool(
                        item["earlier"] and
                        reported_positions(one["earlier"]) !=
                        reported_positions(two["earlier"]))
                    item["different_later"] = bool(
                        item["later"] and
                        reported_positions(one["later"]) !=
                        reported_positions(two["later"]))
                if any(v["different_earlier"] or v["different_later"]
                       for v in entities.values()):
                    pair = (a_source, b_source)
                    overlap = entities
                    break
            if pair:
                break
        self.assertIsNotNone(pair, "fixture must include jointly reported original entity IDs")
        expected = [feature for feature in embedded["features"]
                    if feature["properties"]["source_id"] in pair
                    and feature["properties"]["entity"] in overlap]
        self.assertTrue(expected)
        different = {entity: item for entity, item in overlap.items()
                     if item["different_earlier"] or item["different_later"]}
        self.assertTrue(different, "fixture must include two sources reporting different positions")
        diff_reports = [feature for feature in expected
                        if feature["properties"]["entity"] in different]
        self.assertTrue(diff_reports)
        import math
        def approximate_km(p, q):
            lat1, lat2 = math.radians(p[1]), math.radians(q[1])
            delta_lat = lat2 - lat1
            delta_lon = math.radians(((q[0]-p[0]+540) % 360)-180)
            h = (math.sin(delta_lat/2)**2 +
                 math.cos(lat1)*math.cos(lat2)*math.sin(delta_lon/2)**2)
            return 6371.0088*2*math.asin(math.sqrt(min(1, max(0, h))))
        separations = {}
        for entity in overlap:
            first = observations[pair[0]][entity]
            second = observations[pair[1]][entity]
            separations[entity] = {}
            for period_name in ("earlier", "later"):
                one = {tuple(x["geometry"]["coordinates"]) for x in first[period_name]}
                two = {tuple(x["geometry"]["coordinates"]) for x in second[period_name]}
                all_distances = [approximate_km(a, b) for a in one for b in two]
                separations[entity][period_name] = (
                    {"nearest_km": round(min(all_distances), 3),
                     "farthest_km": round(max(all_distances), 3)}
                    if all_distances else None)
        script = ("""<script>
const expected=__EXPECTED__,sourcesPair=__SOURCES__,reports=__REPORTS__;
const separations=__SEPARATIONS__;
const root=document.body,panel=document.getElementById("comparison-source-pairs");
const a=document.getElementById("comparison-source-a"),b=document.getElementById("comparison-source-b");
const exportButton=document.getElementById("comparison-source-pair-export");
const diffButton=document.getElementById("comparison-source-pair-diff-export");
const csvButton=document.getElementById("comparison-source-pair-distance-csv");
a.value=sourcesPair[0];a.dispatchEvent(new Event("change"));
b.value=sourcesPair[1];b.dispatchEvent(new Event("change"));
const rows=Array.from(document.querySelectorAll("#comparison-source-pair-rows tr"));
root.dataset.pairRowsCorrect=String(panel&&!panel.hidden&&!exportButton.disabled&&
  rows.length===Object.keys(expected).length&&rows.every(function(row){
    const item=expected[row.dataset.pairEntity],cells=row.querySelectorAll("td");
    return !!item && row.dataset.sharedEarlier===String(item.earlier) &&
      row.dataset.sharedLater===String(item.later) &&
      row.dataset.differentEarlier===String(item.different_earlier) &&
      row.dataset.differentLater===String(item.different_later) &&
      Number(cells[5].textContent)===item.count&&
      ["earlier","later"].every(function(period){
        const measure=separations[row.dataset.pairEntity][period];
        const visible=period==="earlier"?cells[6]:cells[7];
        return measure?
          Math.abs(Number(row.dataset[period+"NearestKm"])-measure.nearest_km)<0.0015&&
          Math.abs(Number(row.dataset[period+"FarthestKm"])-measure.farthest_km)<0.0015&&
          visible.textContent.includes("–"):
          visible.textContent==="Not jointly reported"&&
          !Object.hasOwn(row.dataset,period+"NearestKm");
      });
  }));
// Presentation filtering must never truncate the original embedded evidence.
const search=document.getElementById("report-search");
search.value="not-in-evidence";search.dispatchEvent(new Event("input"));
const period=document.getElementById("comparison-period");
period.value="later";period.dispatchEvent(new Event("change"));
const nativeBlob=window.Blob;
let output=null,filename=null,csvOutput=null;
window.Blob=function(parts,options){
  if(options&&options.type==="application/geo+json")
    output=JSON.parse(String(parts[0]));
  if(options&&options.type==="text/csv;charset=utf-8")
    csvOutput=String(parts[0]);
  return new nativeBlob(parts,options);
};
HTMLAnchorElement.prototype.click=function(){filename=this.download;};
exportButton.click();
const meta=output&&output.monde_source_pair_coverage_export;
root.dataset.pairExportCorrect=String(!!meta&&
  JSON.stringify(output.features)===JSON.stringify(reports)&&
  meta.source_a===sourcesPair[0]&&meta.source_b===sourcesPair[1]&&
  meta.shared_entity_count===Object.keys(expected).length&&
  meta.original_feature_count===__TOTAL__&&
  meta.exported_feature_count===reports.length&&
  meta.earlier_original_report_count===reports.filter(function(f){
    return f.properties.monde_comparison_period==="earlier";
  }).length&&
  meta.later_original_report_count===reports.filter(function(f){
    return f.properties.monde_comparison_period==="later";
  }).length&&
  meta.scope==="COMPLETE_EMBEDDED_SAME_PERIOD_JOINT_ENTITY_COVERAGE"&&
  filename==="monde-original-source-pair-shared-evidence.geojson"&&
  search.value==="not-in-evidence"&&period.value==="later");
root.dataset.diffRowsCorrect=String(!diffButton.disabled&&
  rows.filter(function(row){
    return row.dataset.differentEarlier==="true"||row.dataset.differentLater==="true";
  }).length===Object.keys(__DIFFERENT__).length);
output=null;filename=null;diffButton.click();
const metaDiff=output&&output.monde_source_pair_position_difference_export;
root.dataset.diffExportCorrect=String(!!metaDiff&&
  JSON.stringify(output.features)===JSON.stringify(__DIFF_REPORTS__)&&
  metaDiff.scope==="COMPLETE_EMBEDDED_SOURCE_PAIR_REPORTED_POSITION_DIFFERENCES"&&
  metaDiff.source_a===sourcesPair[0]&&metaDiff.source_b===sourcesPair[1]&&
  metaDiff.differing_entity_count===Object.keys(__DIFFERENT__).length&&
  metaDiff.separation_method==="APPROXIMATE_WGS84_GREAT_CIRCLE_NEAREST_AND_FARTHEST_SOURCE_POINT_PAIRS_KM"&&
  metaDiff.source_reported_separations.length===Object.keys(__DIFFERENT__).length&&
  metaDiff.source_reported_separations.every(function(item){
    const reference=separations[item.entity];
    return reference&&["earlier","later"].every(function(period){
      const actual=item[period],value=reference[period];
      return !value?actual===null:
        !!actual&&Math.abs(actual.nearest_km-value.nearest_km)<0.0015&&
        Math.abs(actual.farthest_km-value.farthest_km)<0.0015;
    });
  })&&
  metaDiff.original_feature_count===__TOTAL__&&
  metaDiff.exported_feature_count===__DIFF_COUNT__&&
  metaDiff.earlier_original_report_count===__DIFF_REPORTS__.filter(function(f){
    return f.properties.monde_comparison_period==="earlier";
  }).length&&
  filename==="monde-original-source-pair-position-differences.geojson"&&
  search.value==="not-in-evidence"&&period.value==="later");
csvOutput=null;filename=null;csvButton.click();
const csvLines=csvOutput&&csvOutput.replace(/^\\uFEFF/,"").trimEnd().split("\\r\\n");
const csvRows=csvLines&&csvLines.slice(1),csvHeader=csvLines&&csvLines[0];
root.dataset.pairSeparationCsvCorrect=String(!!csvRows&&
  filename==="monde-original-source-pair-separations.csv"&&
  csvHeader.includes("nearest_separation_km,farthest_separation_km")&&
  csvRows.length===2*Object.keys(expected).length&&
  csvRows.every(function(line){
    return line.includes('"'+sourcesPair[0]+'"')&&
      line.includes('"'+sourcesPair[1]+'"')&&
      line.includes("ORIGINAL_SOURCE_REPORT_SEPARATION_NOT_VERIFIED_TRUTH_OR_MOTION");
  })&&Object.keys(expected).every(function(entity){
    return ["earlier","later"].every(function(p){
      const row=csvRows.find(function(line){return line.includes('"'+entity+'","'+p+'"');});
      if(!row)return false;
      const item=separations[entity][p];
      return item?
        row.includes('"'+item.nearest_km+'"')&&row.includes('"'+item.farthest_km+'"'):
        row.includes('"NOT_JOINTLY_REPORTED"')&&row.includes(',"","",');
    });
  })&&search.value==="not-in-evidence"&&period.value==="later");
// Analyst threshold workflow: independently calculate expected matches from
// the Python Haversine oracle, not from the UI's own filtering function.
const metricControl=document.getElementById("comparison-pair-distance-metric");
const periodControl=document.getElementById("comparison-pair-distance-period");
const thresholdControl=document.getElementById("comparison-pair-distance-min-km");
const thresholdExport=document.getElementById("comparison-pair-distance-export");
const nonZero=Object.values(separations).flatMap(function(x){
  return ["earlier","later"].map(function(p){return x[p]&&x[p].farthest_km;})
    .filter(function(v){return typeof v==="number"&&v>0;});
});
const threshold=Math.max.apply(null,nonZero);
const matching=Object.keys(separations).filter(function(entity){
  return ["earlier","later"].some(function(p){
    const d=separations[entity][p];return d!==null&&d.farthest_km>=threshold;
  });
});
metricControl.value="farthest";
periodControl.value="either";
thresholdControl.value=String(threshold);
thresholdControl.dispatchEvent(new Event("input"));
const thresholdRows=Array.from(document.querySelectorAll("#comparison-source-pair-rows tr"));
root.dataset.pairThresholdRowsCorrect=String(
  nonZero.length>0&&matching.length>0&&!thresholdExport.disabled&&
  thresholdRows.filter(function(row){return !row.hidden;}).length===matching.length&&
  thresholdRows.every(function(row){
    return row.hidden===!matching.includes(row.dataset.pairEntity);
  }));
output=null;filename=null;thresholdExport.click();
const thresholdReports=reports.filter(function(f){
  return matching.includes(f.properties.entity);
});
const thresholdMeta=output&&output.monde_source_pair_distance_threshold_export;
root.dataset.pairThresholdExportCorrect=String(!!thresholdMeta&&
  JSON.stringify(output.features)===JSON.stringify(thresholdReports)&&
  JSON.stringify(thresholdMeta.matched_entity_ids)===JSON.stringify(matching)&&
  thresholdMeta.matched_entity_count===matching.length&&
  thresholdMeta.minimum_separation_km===threshold&&
  thresholdMeta.metric==="farthest"&&thresholdMeta.selected_period==="either"&&
  thresholdMeta.source_a===sourcesPair[0]&&thresholdMeta.source_b===sourcesPair[1]&&
  thresholdMeta.original_feature_count===__TOTAL__&&
  thresholdMeta.exported_feature_count===thresholdReports.length&&
  thresholdMeta.scope==="COMPLETE_EMBEDDED_ORIGINAL_EVIDENCE_FOR_THRESHOLD_MATCHING_ENTITIES"&&
  filename==="monde-source-pair-threshold-matching-evidence.geojson"&&
  search.value==="not-in-evidence"&&period.value==="later");
periodControl.value="earlier";
periodControl.dispatchEvent(new Event("change"));
const earlierMatches=Object.keys(separations).filter(function(entity){
  const item=separations[entity].earlier;
  return item!==null&&item.farthest_km>=threshold;
});
root.dataset.pairThresholdPeriodCorrect=String(
  thresholdRows.filter(function(row){return !row.hidden;}).length===earlierMatches.length&&
  thresholdRows.every(function(row){
    return row.hidden===!earlierMatches.includes(row.dataset.pairEntity);
  }));
metricControl.value="nearest";
metricControl.dispatchEvent(new Event("change"));
const strictMatches=Object.keys(separations).filter(function(entity){
  const d=separations[entity].earlier;return d!==null&&d.nearest_km>=threshold;
});
root.dataset.pairThresholdMetricCorrect=String(
  thresholdRows.filter(function(row){return !row.hidden;}).length===strictMatches.length);
thresholdControl.value="-1";
thresholdControl.dispatchEvent(new Event("input"));
root.dataset.pairThresholdInvalidDenied=String(
  thresholdExport.disabled&&thresholdRows.every(function(row){return row.hidden;}));
thresholdControl.value="0";metricControl.value="farthest";periodControl.value="either";
thresholdControl.dispatchEvent(new Event("input"));
root.dataset.pairThresholdResetCorrect=String(
  thresholdRows.every(function(row){return !row.hidden;})&&!thresholdExport.disabled);
a.value=sourcesPair[0];b.value=sourcesPair[0];b.dispatchEvent(new Event("change"));
root.dataset.pairSameSourceDenied=String(exportButton.disabled&&diffButton.disabled&&csvButton.disabled&&thresholdExport.disabled&&
  document.querySelectorAll("#comparison-source-pair-rows tr").length===0);
</script>""".replace("__EXPECTED__", json.dumps(overlap))
                   .replace("__SEPARATIONS__", json.dumps(separations))
                   .replace("__SOURCES__", json.dumps(pair))
                   .replace("__REPORTS__", json.dumps(expected))
                   .replace("__TOTAL__", str(len(embedded["features"])))
                   .replace("__DIFFERENT__", json.dumps(different))
                   .replace("__DIFF_REPORTS__", json.dumps(diff_reports))
                   .replace("__DIFF_COUNT__", str(len(diff_reports))))
        target = Path(self.folder.name) / "source-pair-coverage.html"
        target.write_text(html.replace("</body>", script+"</body>"), encoding="utf-8")
        output = subprocess.run([
            browser, "--headless", "--no-sandbox", "--disable-gpu",
            "--disable-dev-shm-usage", "--dump-dom", target.as_uri()],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=35,
            check=True).stdout.decode("utf-8")
        for name in ("pair-rows-correct", "pair-export-correct",
                     "diff-rows-correct", "diff-export-correct",
                     "pair-separation-csv-correct",
                     "pair-threshold-rows-correct", "pair-threshold-export-correct",
                     "pair-threshold-period-correct", "pair-threshold-metric-correct",
                     "pair-threshold-invalid-denied", "pair-threshold-reset-correct",
                     "pair-same-source-denied"):
            self.assertIn('data-'+name+'="true"', output, name)
        response, _, ordinary = self.fetch("/viewer", {**QUERY, "view": "current"})
        self.assertEqual(response, 200)
        self.assertIn(b'id="comparison-source-pairs" hidden', ordinary)
        self.assertEqual(self.path.read_bytes(), self.before)


if __name__ == "__main__":
    unittest.main()
