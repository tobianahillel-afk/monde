"""Map source disagreement transitions without choosing a true position."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.test_world_map_view import ROOT, VALID, KNOWN, with_points, extract
from tests.test_world_disagreement_changes import EARLY, LATER


def cli(*args):
    return subprocess.run([sys.executable, "-m", "monde.map_view", *map(str, args)],
                          cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
                          text=True, capture_output=True)


class OfflineDisagreementTransitionTests(unittest.TestCase):
    def test_appeared_preserves_complete_competing_sources_and_saved_state(self):
        with tempfile.TemporaryDirectory() as root:
            state, page = Path(root) / "state.json", Path(root) / "map.html"
            with_points().save(state)
            original = state.read_bytes()
            done = cli("--state", state, "--at", VALID, "--compare-known-at", EARLY,
                       "--known-at", KNOWN, "--disagreement-changes", "--output", page)
            self.assertEqual(done.returncode, 0, done.stderr)
            html = page.read_text(encoding="utf-8")
            _, geo = extract(html)
            view = geo["monde_disagreement_changes_view"]
            self.assertEqual(view["counts"]["APPEARED"], 1)
            self.assertEqual(view["basis"], "ORIGINAL_SOURCE_DISAGREEMENT_KNOWLEDGE_CHANGES_ONLY")
            self.assertTrue(geo["features"])
            self.assertEqual({f["properties"]["monde_disagreement_transition"]
                              for f in geo["features"]}, {"APPEARED"})
            self.assertEqual(view["changes"][0]["before_value_groups"], [])
            reports = [r for g in view["changes"][0]["after_value_groups"]
                       for r in g["reports"]]
            self.assertEqual({r["source_id"] for r in reports},
                             {"official-map", "contrary-map"})
            self.assertTrue(all(r["assertion_id"] and r["evidence_id"] for r in reports))
            self.assertIn('id="disagreement-change-panel"', html)
            self.assertIn('id="disagreement-change-list"', html)
            self.assertIn('id="export-disagreement-changes"', html)
            self.assertIn("MONDE_SOURCE_DISAGREEMENT_CHANGES_V1", html)
            self.assertIn("COMPLETE_ORIGINAL_SOURCE_GROUPS_NOT_VIEWPORT_FILTERED", html)
            self.assertIn('changes: changes.changes', html)
            self.assertIn('counts: changes.counts', html)
            self.assertIn('saveEvidence({', html)
            self.assertEqual(state.read_bytes(), original)

    def test_resolved_conflict_keeps_both_previous_values(self):
        world = with_points()
        previous = world.source_disagreements(VALID, KNOWN, "geo_point")
        entry = previous["disagreements"][0]
        reports = [r for group in entry["value_groups"] for r in group["reports"]]
        contrary = next(r for r in reports if r["source_id"] == "contrary-map")
        official = next(r for r in reports if r["source_id"] == "official-map")
        world.add_evidence({"id": "ev-correct-map", "source_id": "contrary-map",
                            "locator": "fixture://correct", "captured_at": LATER,
                            "source_event_at": None})
        world.add_assertion({"id": "claim-correct-map", "entity": entry["entity"],
                             "attribute": "geo_point", "kind": "CLAIM",
                             "value": official["value"], "evidence_id": "ev-correct-map",
                             "known_at": LATER, "valid_from": contrary["valid_from"],
                             "valid_to": contrary["valid_to"],
                             "supersedes": contrary["assertion_id"]})
        with tempfile.TemporaryDirectory() as root:
            state, page = Path(root) / "state.json", Path(root) / "map.html"
            world.save(state)
            original = state.read_bytes()
            done = cli("--state", state, "--at", VALID, "--compare-known-at", KNOWN,
                       "--known-at", LATER, "--disagreement-changes", "--output", page)
            self.assertEqual(done.returncode, 0, done.stderr)
            _, geo = extract(page.read_text(encoding="utf-8"))
            item = geo["monde_disagreement_changes_view"]["changes"][0]
            self.assertEqual(item["change"], "RESOLVED")
            self.assertEqual(len(item["before_value_groups"]), 2)
            self.assertEqual(item["after_value_groups"], [])
            self.assertTrue(all(f["properties"]["monde_disagreement_transition"] == "RESOLVED"
                                for f in geo["features"]))
            self.assertEqual(state.read_bytes(), original)

    def test_no_disagreement_change_requires_explicit_bbox(self):
        with tempfile.TemporaryDirectory() as root:
            state, page = Path(root) / "state.json", Path(root) / "map.html"
            with_points().save(state)
            args = ("--state", state, "--at", VALID, "--compare-known-at", KNOWN,
                    "--known-at", LATER, "--disagreement-changes", "--output", page)
            no = cli(*args)
            self.assertNotEqual(no.returncode, 0)
            self.assertIn("no changed cross-source Point disagreements", no.stderr)
            self.assertFalse(page.exists())
            yes = cli(*args, "--bbox", "1,45,6,51")
            self.assertEqual(yes.returncode, 0, yes.stderr)
            _, geo = extract(page.read_text(encoding="utf-8"))
            self.assertEqual(geo["features"], [])
            self.assertEqual(geo["monde_disagreement_changes_view"]["changes"], [])
            self.assertEqual(geo["monde_bbox_changes_query"]["status"], "NO_CHANGES")
            html = page.read_text(encoding="utf-8")
            self.assertIn('id="export-disagreement-changes"', html)
            self.assertIn('changes: changes.changes', html)
            self.assertEqual(geo["monde_disagreement_changes_view"]["counts"],
                             {"APPEARED": 0, "CHANGED": 0, "RESOLVED": 0})

    def test_invalid_combinations_and_nonoverwrite(self):
        with tempfile.TemporaryDirectory() as root:
            state, page = Path(root) / "state.json", Path(root) / "map.html"
            with_points().save(state)
            args = ("--state", state, "--at", VALID, "--compare-known-at", EARLY,
                    "--known-at", KNOWN, "--disagreement-changes", "--output", page)
            for extra in (("--only-disagreements",),
                          ("--compare-at", "2026-01-01T00:00:00Z")):
                rejected = cli(*args, *extra)
                self.assertNotEqual(rejected.returncode, 0)
                self.assertFalse(page.exists())
            correct = cli(*args)
            self.assertEqual(correct.returncode, 0, correct.stderr)
            prior = page.read_bytes()
            again = cli(*args)
            self.assertNotEqual(again.returncode, 0)
            self.assertEqual(page.read_bytes(), prior)

    def test_legacy_saved_disagreement_map_unchanged(self):
        with tempfile.TemporaryDirectory() as root:
            state, page = Path(root) / "state.json", Path(root) / "map.html"
            with_points().save(state)
            done = cli("--state", state, "--at", VALID, "--known-at", KNOWN,
                       "--only-disagreements", "--output", page)
            self.assertEqual(done.returncode, 0, done.stderr)
            _, doc = extract(page.read_text(encoding="utf-8"))
            self.assertIn("monde_disagreements_view", doc)
            self.assertNotIn("monde_disagreement_changes_view", doc)
