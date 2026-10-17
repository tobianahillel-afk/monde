"""Bitemporal changes in source-reported disagreements; never ground truth."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.test_world_map_view import ROOT, VALID, KNOWN, with_points

EARLY = "2026-01-09T00:00:00Z"
LATER = "2026-01-12T00:00:00Z"


class DisagreementChangesTest(unittest.TestCase):
    def test_emergence_preserves_both_original_sources(self):
        world = with_points()
        original = world.export()
        result = world.source_disagreement_changes(VALID, EARLY, KNOWN)
        self.assertEqual(result["counts"], {"APPEARED": 1, "RESOLVED": 0, "CHANGED": 0})
        entry = result["changes"][0]
        self.assertEqual(entry["before_value_groups"], [])
        self.assertEqual({r["source_id"] for g in entry["after_value_groups"]
                          for r in g["reports"]},
                         {"official-map", "contrary-map"})
        self.assertTrue(all(r["assertion_id"] and r["evidence_id"]
                            for g in entry["after_value_groups"] for r in g["reports"]))
        self.assertEqual(world.export(), original)

    def test_later_same_data_reports_no_disagreement_change(self):
        self.assertEqual(with_points().source_disagreement_changes(
            VALID, KNOWN, LATER)["status"], "UNCHANGED")

    def test_source_correction_resolves_conflict_without_truth_claim(self):
        world = with_points()
        groups = world.source_disagreements(VALID, KNOWN, "geo_point")["disagreements"][0]
        reports = [r for g in groups["value_groups"] for r in g["reports"]]
        contrary = next(r for r in reports if r["source_id"] == "contrary-map")
        official = next(r for r in reports if r["source_id"] == "official-map")
        world.add_evidence({"id": "ev-correction", "source_id": "contrary-map",
                            "locator": "fixture://correction", "captured_at": LATER,
                            "source_event_at": None})
        world.add_assertion({
            "id": "claim-correction", "entity": groups["entity"],
            "attribute": groups["attribute"], "kind": "CLAIM",
            "value": official["value"], "evidence_id": "ev-correction",
            "known_at": LATER, "valid_from": contrary["valid_from"],
            "valid_to": contrary["valid_to"], "supersedes": contrary["assertion_id"]})
        result = world.source_disagreement_changes(VALID, KNOWN, LATER)
        self.assertEqual(result["counts"]["RESOLVED"], 1)
        self.assertEqual(result["changes"][0]["after_value_groups"], [])

    def test_invalid_cutoff_order_rejected(self):
        world = with_points()
        for first, last in [(KNOWN, KNOWN), (LATER, KNOWN), ("invalid", KNOWN)]:
            with self.subTest(first=first, last=last):
                with self.assertRaises(ValueError):
                    world.source_disagreement_changes(VALID, first, last)

    def test_persisted_cli_preserves_snapshot_and_original_mode(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "world.json"
            with_points().save(path)
            original = path.read_bytes()
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            args = [sys.executable, "-m", "monde.world", "--fixture", str(path),
                    "--source-disagreements", "--at", VALID, "--known-at", KNOWN]
            changed = subprocess.run(args + ["--compare-known-at", EARLY],
                                     cwd=ROOT, env=env, text=True, capture_output=True)
            self.assertEqual(changed.returncode, 0, changed.stderr)
            self.assertEqual(json.loads(changed.stdout)["counts"]["APPEARED"], 1)
            ordinary = subprocess.run(args, cwd=ROOT, env=env, text=True, capture_output=True)
            self.assertEqual(ordinary.returncode, 0, ordinary.stderr)
            self.assertEqual(json.loads(ordinary.stdout)["comparison"],
                             "DIFFERENT_SOURCE_REPORTS_ONLY")
            self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
