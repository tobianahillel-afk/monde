"""World-valid-time source-pair distance changes using real saved WorldMini."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from monde.source_pair_changes import compare_source_pair_world_time, compare_source_pair
from monde.world import WorldMini

EARLY = "2026-01-02T00:00:00Z"
LATE = "2026-01-05T00:00:00Z"
KNOWN = "2026-01-07T00:00:00Z"


def sample(*, old=True, dateline=False):
    world = WorldMini()
    def add(source, name, point, start, end=None, entity="site-1"):
        world.add_evidence({"id": "e-" + name, "source_id": source,
                            "locator": "fixture://" + name,
                            "captured_at": "2026-01-01T00:00:00Z",
                            "source_event_at": "2026-01-01T00:00:00Z"})
        world.add_assertion({"id": "a-" + name, "entity": entity,
                             "attribute": "geo_point",
                             "value": {"type": "Point", "coordinates": point},
                             "evidence_id": "e-" + name, "kind": "CLAIM",
                             "known_at": "2026-01-01T00:00:00Z",
                             "valid_from": start, "valid_to": end,
                             "supersedes": None})
    start, transition = "2026-01-01T00:00:00Z", "2026-01-04T00:00:00Z"
    a, b, c = (-179.9, 179.9, -179.8) if dateline else (0., 2., 1.)
    add("survey-a", "a", [a, 0.], start)
    if old:
        add("survey-b", "b-old", [b, 0.], start, transition)
    add("survey-b", "b-new", [c, 0.], transition)
    add("survey-a", "solo", [10., 0.], start, entity="site-unpaired")
    return world


class SourcePairWorldTimeTest(unittest.TestCase):
    def test_original_reports_and_real_world_validity_change(self):
        world = sample()
        immutable = json.dumps(world.export(), sort_keys=True)
        result = compare_source_pair_world_time(
            world, "survey-a", "survey-b", EARLY, LATE, KNOWN)
        self.assertEqual(result["schema"], "MONDE_SOURCE_PAIR_WORLD_CHANGE_V1")
        self.assertEqual([r["entity"] for r in result["entities"]], ["site-1"])
        row = result["entities"][0]
        self.assertEqual(row["earlier"]["status"], "JOINTLY_REPORTED")
        self.assertEqual([r["id"] for r in row["earlier"]["source_b_original_reports"]],
                         ["a-b-old"])
        self.assertEqual([r["id"] for r in row["later"]["source_b_original_reports"]],
                         ["a-b-new"])
        self.assertEqual(row["later"]["source_b_original_reports"][0]
                         ["properties"]["evidence_id"], "e-b-new")
        self.assertGreater(row["earlier"]["separation"]["nearest_km"], 200)
        self.assertLess(row["earlier_to_later_change_km"]["nearest_km"], -100)
        self.assertIn("not verified motion", result["interpretation"])
        self.assertEqual(json.dumps(world.export(), sort_keys=True), immutable)

    def test_unreported_period_is_unknown_not_zero(self):
        result = compare_source_pair_world_time(
            sample(old=False), "survey-a", "survey-b", EARLY, LATE, KNOWN)
        row = result["entities"][0]
        self.assertEqual(row["earlier"]["status"], "NOT_JOINTLY_REPORTED")
        self.assertIsNone(row["earlier"]["separation"])
        self.assertIsNone(row["earlier_to_later_change_km"])
        self.assertEqual(row["later"]["status"], "JOINTLY_REPORTED")

    def test_antimeridian_shortest_arc(self):
        row = compare_source_pair_world_time(
            sample(dateline=True), "survey-a", "survey-b",
            EARLY, LATE, KNOWN)["entities"][0]
        self.assertLess(row["earlier"]["separation"]["nearest_km"], 25)
        self.assertLess(row["later"]["separation"]["nearest_km"], 20)

    def test_reject_invalid_times_and_sources(self):
        for a, b, earlier, later, known in (
                ("survey-a", "survey-a", EARLY, LATE, KNOWN),
                ("survey-a", "survey-b", LATE, EARLY, KNOWN),
                ("survey-a", "survey-b", LATE, LATE, KNOWN),
                ("survey-a", "survey-b", EARLY, LATE, "2026-01-07T00:00:00"),
                ("survey-a", "survey-b", "invalid", LATE, KNOWN)):
            with self.subTest(a=a, earlier=earlier, later=later, known=known):
                with self.assertRaises(ValueError):
                    compare_source_pair_world_time(sample(), a, b, earlier, later, known)

    def test_real_cli_and_persisted_bytes_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "world.json"
            sample().save(path)
            before = path.read_bytes()
            args = [sys.executable, "-m", "monde.source_pair_changes",
                    "--fixture", str(path), "--source-a", "survey-a",
                    "--source-b", "survey-b", "--from-at", EARLY,
                    "--to-at", LATE, "--known-at", KNOWN]
            common = {"cwd": Path(__file__).resolve().parents[1],
                      "env": {**os.environ, "PYTHONPATH": "src"},
                      "capture_output": True, "text": True}
            run = subprocess.run(args, **common)
            self.assertEqual(run.returncode, 0, run.stderr)
            doc = json.loads(run.stdout)
            self.assertEqual(doc["schema"], "MONDE_SOURCE_PAIR_WORLD_CHANGE_V1")
            self.assertEqual(doc["entities"][0]["later"]
                             ["source_b_original_reports"][0]["id"], "a-b-new")
            for extra in (["--at", EARLY], ["--from-at", LATE],
                          ["--from-known-at", EARLY]):
                failure = subprocess.run(args + extra, **common)
                self.assertNotEqual(failure.returncode, 0, extra)
            self.assertEqual(path.read_bytes(), before)

    def test_existing_knowledge_time_contract_preserved(self):
        from tests.test_world_source_pair_changes import fixture_world, AT, BEFORE, AFTER
        result = compare_source_pair(fixture_world(), "survey-a", "survey-b",
                                     AT, BEFORE, AFTER)
        self.assertEqual(result["schema"], "MONDE_SOURCE_PAIR_CHANGE_V1")
        self.assertIn("from_known_at", result)
        self.assertNotIn("from_at", result)
        self.assertEqual(result["entities"][0]["earlier"]
                         ["source_b_original_reports"][0]["id"], "a-b1")


if __name__ == "__main__":
    unittest.main()
