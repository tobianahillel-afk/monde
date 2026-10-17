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



if __name__ == "__main__":
    unittest.main()
