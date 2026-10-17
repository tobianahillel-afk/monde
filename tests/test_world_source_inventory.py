"""Behavioral tests of persisted source evidence inventories."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from monde.source_inventory import source_inventory
from monde.world import WorldMini
from tests.test_world_map_source_manifest_layers import sample
from tests.test_world_geopackage import CAP

ROOT = Path(__file__).resolve().parents[1]


def cli(module, *args):
    return subprocess.run(
        [sys.executable, "-m", module, *map(str, args)],
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True, text=True)


class SourceInventoryTests(unittest.TestCase):
    def test_mixed_geopackage_layers_are_separate_sources_after_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, database, note, _ = sample(tmp)
            state = Path(tmp) / "world.json"
            originals = database.read_bytes(), note.read_bytes()
            result = cli("monde.world", "--ingest-source-manifest", manifest,
                         "--state-out", state)
            self.assertEqual(result.returncode, 0, result.stderr)
            saved = state.read_bytes()
            query = cli("monde.source_inventory", "--state", state,
                        "--known-at", CAP)
            self.assertEqual(query.returncode, 0, query.stderr)
            report = json.loads(query.stdout)
            self.assertEqual(report["status"], "SOURCE_REPORTS_ONLY")
            self.assertEqual(report["world"], "OBSERVED")
            self.assertEqual(report["totals"]["sources"], 4)
            self.assertEqual(report["totals"]["evidence"], 35)
            self.assertGreaterEqual(report["totals"]["assertions"], 35)
            self.assertEqual({r["source_id"] for r in report["sources"]},
                             {"survey:survey_points", "survey:survey_mixed",
                              "survey:survey_duplicate", "note"})
            for row in report["sources"]:
                self.assertEqual(len(row["locators"]), 1)
                self.assertGreater(row["assertion_count"], 0)
            self.assertEqual(state.read_bytes(), saved)
            self.assertEqual((database.read_bytes(), note.read_bytes()), originals)

    def test_future_evidence_is_absent_from_early_knowledge_cutoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, _, _, _ = sample(tmp)
            state = Path(tmp) / "world.json"
            self.assertEqual(cli("monde.world", "--ingest-source-manifest", manifest,
                                 "--state-out", state).returncode, 0)
            inventory = source_inventory(WorldMini.read(state),
                                         "2026-01-01T00:00:00Z")
            self.assertEqual(inventory["sources"], [])
            self.assertEqual(inventory["totals"],
                             {"sources": 0, "evidence": 0, "assertions": 0})

    def test_future_assertion_not_counted_before_knowledge(self):
        model = WorldMini()
        model.add_evidence({"id": "ev1", "source_id": "source1",
                            "locator": "dataset://test",
                            "captured_at": "2026-01-01T00:00:00Z",
                            "source_event_at": None})
        model.add_assertion({"id": "as1", "entity": "site1",
                             "attribute": "condition", "value": "reported",
                             "evidence_id": "ev1", "kind": "CLAIM",
                             "known_at": "2026-01-03T00:00:00Z",
                             "valid_from": "2026-01-01T00:00:00Z",
                             "valid_to": None, "supersedes": None})
        early = source_inventory(model, "2026-01-02T00:00:00Z")
        self.assertEqual(early["totals"]["assertions"], 0)
        self.assertEqual(early["sources"][0]["entity_count"], 0)
        later = source_inventory(model, "2026-01-04T00:00:00Z")
        self.assertEqual(later["sources"][0]["attribute_counts"], {"condition": 1})
        self.assertEqual(later["sources"][0]["entity_count"], 1)

    def test_errors_do_not_create_or_mutate_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            absent = Path(tmp) / "absent.json"
            command = cli("monde.source_inventory", "--state", absent,
                          "--known-at", "2026-01-01T00:00:00Z")
            self.assertNotEqual(command.returncode, 0)
            self.assertFalse(absent.exists())
            with self.assertRaises(ValueError):
                source_inventory(WorldMini(), "not-an-iso-timestamp")


if __name__ == "__main__":
    unittest.main()
