"""WORK-0017: concrete offline evidence map output and CLI regressions."""
import copy
import json
import os
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from monde.geojson import to_document
from monde.map_view import render_map
from monde.world import WorldMini

ROOT = Path(__file__).resolve().parents[1]
VALID = "2026-01-02T00:00:00Z"
KNOWN = "2026-01-10T10:00:00Z"
BBOX = [2.34, 48.84, 2.36, 48.87]


class Extract(HTMLParser):
    def __init__(self):
        super().__init__()
        self.data_chunks = []
        self.scripts = []
        self.active = None
        self.ready_markers = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script":
            self.active = "data" if a.get("id") == "monde-data" else "code"

    def handle_endtag(self, tag):
        if tag == "script":
            self.active = None

    def handle_data(self, data):
        if self.active == "data":
            self.data_chunks.append(data)
        if self.active == "code":
            self.scripts.append(data)


def with_points():
    world = WorldMini.read(str(ROOT / "examples/monde-mini.json"))
    geo = WorldMini.load_document(str(ROOT / "examples/monde-mini-points.geojson"))
    world.append_document(to_document(
        geo, source_id="official-map", locator="fixture://official-map",
        captured_at=KNOWN, valid_from="2026-01-01T00:00:00Z"))
    alternative = copy.deepcopy(geo)
    alternative["features"] = alternative["features"][:1]
    alternative["features"][0]["geometry"]["coordinates"] = [5.0, 45.0]
    world.append_document(to_document(
        alternative, source_id="contrary-map", locator="fixture://contrary-map",
        captured_at=KNOWN, valid_from="2026-01-01T00:00:00Z"))
    return world


def extract(html):
    parser = Extract()
    parser.feed(html)
    return parser, json.loads("".join(parser.data_chunks))


class OfflineMapTest(unittest.TestCase):
    def test_all_competing_source_reports_retained_and_clickable(self):
        source = with_points().export_geojson_bbox(BBOX, VALID, KNOWN)
        html = render_map(source)
        parsed, embedded = extract(html)
        self.assertEqual(embedded, source)
        self.assertEqual(embedded["monde_bbox_query"]["total_matching_entities"], 1)
        self.assertEqual(len(embedded["features"]), 2)
        self.assertEqual(sorted(f["properties"]["monde_inside_bbox"]
                                for f in embedded["features"]), [False, True])
        self.assertIn('id="points"', html)
        self.assertIn('id="report-list"', html)
        self.assertIn("addEventListener", "".join(parsed.scripts))
        self.assertIn("aria-live", html)
        self.assertNotIn("<script src=", html)
        self.assertIn("connect-src 'none'", html)

    def test_no_matching_viewport_is_not_claimed_as_physical_absence(self):
        source = WorldMini.read(str(ROOT / "examples/monde-mini.json"))
        html = render_map(source.export_geojson_bbox(BBOX, VALID, KNOWN))
        _, data = extract(html)
        self.assertEqual(data["features"], [])
        self.assertEqual(data["monde_bbox_query"]["status"], "NO_MATCHES")
        self.assertIn("does not establish physical absence", html)

    def test_embed_untrusted_source_strings_cannot_escape_json_script(self):
        source = with_points().export_geojson_bbox(BBOX, VALID, KNOWN)
        injection = "</script><script>globalThis.pwned=true</script><img src=x onerror=alert(1)>"
        source["features"][0]["properties"]["locator"] = injection
        html = render_map(source)
        self.assertNotIn(injection, html)
        self.assertNotIn("</script><script>", html)
        p, embedded = extract(html)
        self.assertEqual(embedded["features"][0]["properties"]["locator"], injection)
        self.assertEqual(len(p.scripts), 1)

    def test_reject_invalid_point_and_missing_provenance(self):
        source = with_points().export_geojson_bbox(BBOX, VALID, KNOWN)
        for mutate in ("nan", "bool", "missing", "bad_type"):
            copy_source = copy.deepcopy(source)
            f = copy_source["features"][0]
            if mutate == "nan":
                f["geometry"]["coordinates"][0] = float("nan")
            elif mutate == "bool":
                f["geometry"]["coordinates"][0] = True
            elif mutate == "missing":
                del f["properties"]["evidence_id"]
            else:
                f["geometry"]["type"] = "LineString"
            with self.subTest(mutate=mutate):
                with self.assertRaises(ValueError):
                    render_map(copy_source)

    def test_saved_state_cli_writes_self_contained_html_and_preserves_state(self):
        w = with_points()
        original = w.export()
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "state.json"
            output = Path(td) / "map.html"
            w.save(str(target))
            cmd = [sys.executable, "-m", "monde.map_view",
                   "--state", str(target), "--bbox", "2.34,48.84,2.36,48.87",
                   "--at", VALID, "--known-at", KNOWN, "--output", str(output)]
            environment = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
            first = subprocess.run(cmd, capture_output=True, text=True,
                                   env=environment, cwd=ROOT)
            self.assertEqual(first.returncode, 0, first.stderr)
            html = output.read_text(encoding="utf-8")
            _, embedded = extract(html)
            self.assertEqual(len(embedded["features"]), 2)
            self.assertEqual(w.export(), original)
            self.assertEqual(WorldMini.read(str(target)).export(), original)
            again = subprocess.run(cmd, capture_output=True, text=True,
                                   env=environment, cwd=ROOT)
            self.assertNotEqual(again.returncode, 0, "must not overwrite map")
            self.assertEqual(output.read_text(encoding="utf-8"), html)

    def test_cli_invalid_bbox_fails_and_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "bad.html"
            cmd = [sys.executable, "-m", "monde.map_view",
                   "--state", str(ROOT / "examples/monde-mini.json"),
                   "--bbox", "0,100,10,0", "--at", VALID, "--known-at", KNOWN,
                   "--output", str(out)]
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  env=dict(os.environ, PYTHONPATH=str(ROOT / "src")))
            self.assertNotEqual(proc.returncode, 0)
            self.assertFalse(out.exists())

    def test_embedded_javascript_parses_under_node_when_available(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node unavailable; GitHub Actions browser smoke runs separately")
        html = render_map(with_points().export_geojson_bbox(BBOX, VALID, KNOWN))
        parsed, _ = extract(html)
        script = "\n".join(parsed.scripts)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "viewer.js"
            path.write_text(script, encoding="utf-8")
            out = subprocess.run([node, "--check", str(path)],
                                 capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stderr)


if __name__ == "__main__":
    unittest.main()
