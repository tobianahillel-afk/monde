"""Real WorldMini persisted evidence and CLI tests for two source separations."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from monde.source_pair_changes import compare_source_pair, _distance
from monde.world import WorldMini

AT = "2026-01-05T00:00:00Z"
BEFORE = "2026-01-03T12:00:00Z"
AFTER = "2026-01-05T12:00:00Z"


def fixture_world():
    w = WorldMini()
    def report(source, name, known, value, supersedes=None, entity="site-1"):
        w.add_evidence({"id": "e-" + name, "source_id": source,
                        "locator": "fixture://" + name, "captured_at": known,
                        "source_event_at": known})
        w.add_assertion({"id": "a-" + name, "entity": entity,
                         "attribute": "geo_point", "value": value,
                         "evidence_id": "e-" + name, "kind": "CLAIM",
                         "known_at": known, "valid_from": "2026-01-01T00:00:00Z",
                         "valid_to": None, "supersedes": supersedes})
    report("survey-a", "a1", "2026-01-02T00:00:00Z", [0., 0.])
    report("survey-b", "b1", "2026-01-03T00:00:00Z", [2., 0.])
    report("survey-a", "orphan", "2026-01-03T01:00:00Z", [6., 0.],
           entity="site-only-one-source")
    report("survey-b", "b2", "2026-01-04T00:00:00Z", [1., 0.],
           supersedes="a-b1")
    return w


class SourcePairChangesTest(unittest.TestCase):
    def test_change_preserves_original_source_revisions_and_state(self):
        w = fixture_world()
        original = json.dumps(w.export(), sort_keys=True)
        result = compare_source_pair(w, "survey-a", "survey-b", AT, BEFORE, AFTER)
        self.assertEqual(result["schema"], "MONDE_SOURCE_PAIR_CHANGE_V1")
        self.assertEqual([r["entity"] for r in result["entities"]], ["site-1"])
        row = result["entities"][0]
        self.assertEqual(row["earlier"]["status"], "JOINTLY_REPORTED")
        self.assertEqual(row["later"]["status"], "JOINTLY_REPORTED")
        self.assertGreater(row["earlier"]["separation"]["nearest_km"], 200)
        self.assertLess(row["earlier_to_later_change_km"]["nearest_km"], -100)
        self.assertEqual([x["id"] for x in row["earlier"]["source_b_original_reports"]],
                         ["a-b1"])
        self.assertEqual([x["id"] for x in row["later"]["source_b_original_reports"]],
                         ["a-b2"])
        self.assertEqual(json.dumps(w.export(), sort_keys=True), original)

    def test_unreported_period_is_unknown_not_zero(self):
        result = compare_source_pair(fixture_world(), "survey-a", "survey-b",
                                     AT, "2026-01-02T12:00:00Z", AFTER)
        row = result["entities"][0]
        self.assertEqual(row["earlier"]["status"], "NOT_JOINTLY_REPORTED")
        self.assertIsNone(row["earlier"]["separation"])
        self.assertIsNone(row["earlier_to_later_change_km"])

    def test_antimeridian_uses_shorter_distance(self):
        self.assertLess(_distance([179.9, 0], [-179.9, 0]), 23)

    def test_reject_duplicate_sources_nonincreasing_and_naive_times(self):
        w = fixture_world()
        with self.assertRaises(ValueError):
            compare_source_pair(w, "survey-a", "survey-a", AT, BEFORE, AFTER)
        for start, end in ((AFTER, BEFORE), (AFTER, AFTER),
                           ("2026-01-03T12:00:00", AFTER)):
            with self.assertRaises(ValueError):
                compare_source_pair(w, "survey-a", "survey-b", AT, start, end)

    def test_persisted_world_real_cli_without_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "world.json"
            before = json.dumps(fixture_world().export()).encode()
            target.write_bytes(before)
            run = subprocess.run([
                sys.executable, "-m", "monde.source_pair_changes",
                "--fixture", str(target), "--source-a", "survey-a",
                "--source-b", "survey-b", "--at", AT,
                "--from-known-at", BEFORE, "--to-known-at", AFTER
            ], cwd=Path(__file__).resolve().parents[1],
               env={**os.environ, "PYTHONPATH": "src"}, capture_output=True,
               text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            doc = json.loads(run.stdout)
            self.assertEqual(doc["entities"][0]["later"]
                             ["source_b_original_reports"][0]["id"], "a-b2")
            self.assertEqual(target.read_bytes(), before)
