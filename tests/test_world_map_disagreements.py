"""Offline saved-state cross-source disagreement map: product regression tests."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from monde.map_view import automatic_source_bbox
from monde.world import WorldMini
from tests.test_world_map_view import BBOX, KNOWN, ROOT, VALID, extract, with_points


def run(*args):
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    return subprocess.run([sys.executable, "-m", "monde.map_view", *map(str, args)],
                          cwd=ROOT, env=env, text=True, capture_output=True)


class SavedDisagreementMapTests(unittest.TestCase):
    def test_only_conflicting_source_positions_are_mapped_with_provenance(self):
        world = with_points()
        with tempfile.TemporaryDirectory() as directory:
            state, page = Path(directory) / "saved.json", Path(directory) / "conflicts.html"
            world.save(str(state))
            original = state.read_bytes()
            result = run("--state", state, "--at", VALID, "--known-at", KNOWN,
                         "--bbox", ",".join(map(str, BBOX)),
                         "--only-disagreements", "--output", page)
            self.assertEqual(result.returncode, 0, result.stderr)
            _, geo = extract(page.read_text(encoding="utf-8"))
            features = geo["features"]
            self.assertEqual(len(features), 2)
            self.assertEqual(sorted(f["properties"]["monde_inside_bbox"]
                                    for f in features), [False, True])
            self.assertEqual({tuple(f["properties"]["monde_conflicting_source_ids"])
                              for f in features}, {("contrary-map", "official-map")})
            self.assertEqual(geo["monde_bbox_query"]["total_matching_entities"], 1)
            self.assertEqual(geo["monde_bbox_query"]["total_source_features"], 2)
            self.assertEqual(geo["monde_disagreements_view"]["basis"],
                             "CONTRADICTORY_SOURCE_POINT_REPORTS_ONLY")
            self.assertEqual(state.read_bytes(), original)

    def test_auto_fits_only_source_disagreement_points(self):
        with tempfile.TemporaryDirectory() as directory:
            world = with_points()
            state, page = Path(directory) / "saved.json", Path(directory) / "map.html"
            world.save(str(state))
            wanted = automatic_source_bbox(world, VALID, KNOWN,
                                           only_disagreements=True)
            result = run("--state", state, "--at", VALID, "--known-at", KNOWN,
                         "--only-disagreements", "--output", page)
            self.assertEqual(result.returncode, 0, result.stderr)
            _, data = extract(page.read_text(encoding="utf-8"))
            self.assertEqual(data["monde_bbox_query"]["bbox"], wanted)
            self.assertIn('id="saved-disagreements-note"', page.read_text())

    def test_empty_disagreements_require_bbox_or_report_no_matches(self):
        with tempfile.TemporaryDirectory() as directory:
            world = WorldMini.read(str(ROOT / "examples/monde-mini.json"))
            state, page = Path(directory) / "state.json", Path(directory) / "map.html"
            world.save(str(state))
            result = run("--state", state, "--at", VALID, "--known-at", KNOWN,
                         "--only-disagreements", "--output", page)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("no conflicting source-reported Points", result.stderr)
            self.assertFalse(page.exists())
            result = run("--state", state, "--at", VALID, "--known-at", KNOWN,
                         "--bbox", "1,45,6,51", "--only-disagreements",
                         "--output", page)
            self.assertEqual(result.returncode, 0, result.stderr)
            _, data = extract(page.read_text(encoding="utf-8"))
            self.assertEqual(data["features"], [])
            self.assertEqual(data["monde_bbox_query"]["status"], "NO_MATCHES")
            self.assertIn("does not establish physical absence", page.read_text())

    def test_mutually_exclusive_time_comparison_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            state, page = Path(directory) / "state.json", Path(directory) / "map.html"
            with_points().save(str(state))
            for mode, cutoff in [("--compare-at", "2026-01-01T00:00:00Z"),
                                 ("--compare-known-at", "2026-01-09T00:00:00Z")]:
                result = run("--state", state, "--at", VALID, "--known-at", KNOWN,
                             "--only-disagreements", mode, cutoff, "--output", page)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("cannot be combined", result.stderr)
                self.assertFalse(page.exists())

    def test_default_evidence_map_unchanged_and_output_create_only(self):
        with tempfile.TemporaryDirectory() as directory:
            state, page = Path(directory) / "state.json", Path(directory) / "map.html"
            with_points().save(str(state))
            args = ("--state", state, "--at", VALID, "--known-at", KNOWN,
                    "--bbox", ",".join(map(str, BBOX)), "--output", page)
            result = run(*args)
            self.assertEqual(result.returncode, 0, result.stderr)
            _, data = extract(page.read_text(encoding="utf-8"))
            self.assertNotIn("monde_disagreements_view", data)
            self.assertGreater(len(data["features"]), 2)
            prior = page.read_bytes()
            denied = run(*args)
            self.assertNotEqual(denied.returncode, 0)
            self.assertEqual(page.read_bytes(), prior)


if __name__ == "__main__":
    unittest.main()
