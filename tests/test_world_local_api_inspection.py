"""Browser inspection of original source assertions and corrections."""
import copy
import http.client
from html.parser import HTMLParser
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from monde.local_api import _inspection_html, create_server
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
        self.assertEqual(len(forms.forms), 3)
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
