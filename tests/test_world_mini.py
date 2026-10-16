"""MONDE Mini bitemporal and provenance regression suite (real Python)."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from monde.world import WorldMini

ROOT = Path(__file__).resolve().parents[1]
DOC = json.loads((ROOT / "examples/monde-mini.json").read_text(encoding="utf-8"))
AT = "2026-01-02T00:00:00Z"
LATE = "2026-01-07T00:00:00Z"


class WorldMiniTest(unittest.TestCase):
    def setUp(self):
        self.model = WorldMini.from_document(copy.deepcopy(DOC))

    def query(self, known=LATE, at=AT):
        return self.model.query("building-001", "floors", at, known)

    def test_conflicting_sources_preserved_with_provenance(self):
        reports = self.query()["reports"]
        self.assertEqual([r["value"] for r in reports], [6, 7])
        self.assertEqual({r["source_id"] for r in reports},
                         {"local-news", "city-registry"})
        self.assertTrue(all(r["locator"] and r["evidence_id"] for r in reports))

    def test_as_known_at_differs_from_as_valid_at(self):
        self.assertEqual(self.query("2026-01-03T09:59:59Z")["status"], "UNKNOWN")
        self.assertEqual([r["value"] for r in
                          self.query("2026-01-03T10:00:00Z")["reports"]], [5])
        self.assertEqual([r["value"] for r in
                          self.query("2026-01-05T00:00:00Z")["reports"]], [5, 6])
        self.assertEqual([r["value"] for r in self.query()["reports"]], [6, 7])

    def test_corrections_do_not_overwrite_history(self):
        self.assertEqual(len(self.model.export()["assertions"]), 3)
        self.assertEqual(self.query()["reports"][-1]["supersedes"], "a-city-initial")
        self.assertEqual([r["value"] for r in
                          self.query("2026-01-05T00:00:00Z")["reports"]], [5, 6])

    def test_unknown_not_equal_zero(self):
        x = self.model.query("building-001", "basements", AT, LATE)
        self.assertEqual(x["status"], "UNKNOWN")
        self.assertEqual(x["reports"], [])

    def test_validity_half_open(self):
        entry = {
            "id": "e-short", "source_id": "src", "locator": "fixture://short",
            "captured_at": "2026-01-08T00:00:00Z", "source_event_at": None
        }
        self.model.add_evidence(entry)
        self.model.add_assertion({
            "id": "a-short", "entity": "building-001", "attribute": "height",
            "value": 5, "evidence_id": "e-short", "kind": "OBSERVATION",
            "known_at": "2026-01-08T00:00:00Z",
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_to": "2026-02-01T00:00:00Z", "supersedes": None
        })
        self.assertEqual(len(self.model.query("building-001", "height",
                          "2026-01-31T23:59:59Z", "2026-01-09T00:00:00Z")["reports"]), 1)
        self.assertEqual(self.model.query("building-001", "height",
                         "2026-02-01T00:00:00Z", "2026-01-09T00:00:00Z")["status"], "UNKNOWN")

    def test_duplicate_idempotent_or_collision(self):
        first = copy.deepcopy(DOC["assertions"][0])
        self.model.add_assertion(first)
        self.assertEqual(len(self.model.export()["assertions"]), 3)
        with self.assertRaisesRegex(ValueError, "collision"):
            self.model.add_assertion({**first, "value": 99})
        evidence = copy.deepcopy(DOC["evidence"][0])
        self.model.add_evidence(evidence)
        with self.assertRaisesRegex(ValueError, "collision"):
            self.model.add_evidence({**evidence, "locator": "tampered"})

    def test_missing_evidence_and_disguised_inference_rejected(self):
        for change in ({"evidence_id": "missing"}, {"kind": "ESTIMATED"},
                       {"kind": "SIMULATED"}):
            with self.assertRaises(ValueError):
                self.model.add_assertion({**DOC["assertions"][0],
                                          "id": "a-new", **change})

    def test_cross_source_correction_refused(self):
        invalid = {**DOC["assertions"][-1], "id": "bad-revision",
                   "evidence_id": "e-news-1", "supersedes": "a-city-revision",
                   "known_at": "2026-01-08T00:00:00Z"}
        with self.assertRaises(ValueError):
            self.model.add_assertion(invalid)

    def test_backdated_knowledge_refused(self):
        with self.assertRaisesRegex(ValueError, "backdate"):
            self.model.add_assertion({**DOC["assertions"][0],
                                      "id": "a-backdated",
                                      "known_at": "2026-01-03T11:00:00Z"})

    def test_invalid_interval_refused(self):
        for end in ("2026-01-01T00:00:00Z", "2025-12-31T00:00:00Z"):
            with self.assertRaises(ValueError):
                self.model.add_assertion({**DOC["assertions"][0],
                                          "id": "a-inverted",
                                          "known_at": "2026-01-08T00:00:00Z",
                                          "valid_to": end})

    def test_knowledge_before_capture_refused(self):
        with self.assertRaises(ValueError):
            self.model.add_assertion({**DOC["assertions"][0],
                                      "id": "a-early",
                                      "known_at": "2026-01-02T00:00:00Z"})

    def test_timezone_missing_refused_but_offsets_compared(self):
        with self.assertRaises(ValueError):
            self.query("2026-01-07T00:00:00")
        self.assertEqual([r["value"] for r in
                          self.query("2026-01-07T01:00:00+01:00")["reports"]], [6, 7])

    def test_snapshots_cannot_mutate_world(self):
        q = self.query()
        q["reports"][0]["value"] = "changed"
        self.model.export()["assertions"][0]["value"] = "changed"
        self.assertEqual([r["value"] for r in self.query()["reports"]], [6, 7])

    def test_reopen_export_reproduces_same_answers(self):
        reopened = WorldMini.from_document(self.model.export())
        self.assertEqual(reopened.export(), self.model.export())
        self.assertEqual(reopened.query("building-001", "floors", AT, LATE), self.query())

    def test_duplicate_json_keys_and_nonfinite_input_rejected(self):
        for raw in ('{"schema_version":1,"schema_version":1,"evidence":[],"assertions":[]}',
                    '{"schema_version":1,"evidence":[],"assertions":[NaN]}'):
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                             delete=False) as tmp:
                tmp.write(raw)
                path = tmp.name
            try:
                with self.assertRaises(ValueError):
                    WorldMini.read(path)
            finally:
                os.unlink(path)


    def test_entity_snapshot_preserves_all_source_reports_without_picking_truth(self):
        snapshot = self.model.entity_snapshot("building-001", AT, LATE)
        self.assertEqual(snapshot["world"], "OBSERVED")
        self.assertEqual(snapshot["status"], "REPORTED")
        self.assertEqual(list(snapshot["attributes"]), ["floors"])
        reports = snapshot["attributes"]["floors"]["reports"]
        self.assertEqual([r["value"] for r in reports], [6, 7])
        self.assertEqual({r["evidence_id"] for r in reports},
                         {"e-news-1", "e-city-reg-2"})

    def test_snapshot_is_bitemporal_and_never_fabricates_unknown_attributes(self):
        before = self.model.entity_snapshot("building-001", AT,
                                             "2026-01-05T00:00:00Z")
        self.assertEqual([r["value"] for r in
                          before["attributes"]["floors"]["reports"]], [5, 6])
        unknown = self.model.entity_snapshot("building-001", AT,
                                              "2026-01-02T00:00:00Z")
        self.assertEqual(unknown["status"], "UNKNOWN")
        self.assertEqual(unknown["attributes"], {})
        self.assertNotIn("basements", self.model.entity_snapshot(
            "building-001", AT, LATE)["attributes"])

    def test_snapshot_aggregates_multiple_properties_without_losing_zero(self):
        self.model.add_evidence({"id": "e-b-basement", "source_id": "survey",
                                 "locator": "fixture://survey/basements",
                                 "captured_at": "2026-01-08T00:00:00Z",
                                 "source_event_at": None})
        self.model.add_assertion({"id": "a-b-basement", "entity": "building-001",
                                  "attribute": "basements", "value": 0,
                                  "evidence_id": "e-b-basement", "kind": "OBSERVATION",
                                  "known_at": "2026-01-08T00:00:00Z",
                                  "valid_from": "2026-01-01T00:00:00Z",
                                  "valid_to": None, "supersedes": None})
        current = self.model.entity_snapshot("building-001", AT,
                                              "2026-01-09T00:00:00Z")
        self.assertEqual(list(current["attributes"]), ["basements", "floors"])
        self.assertEqual(current["attributes"]["basements"]["reports"][0]["value"], 0)
        old = self.model.entity_snapshot("building-001", AT, LATE)
        self.assertNotIn("basements", old["attributes"])
        current["attributes"]["floors"]["reports"][0]["value"] = -999
        self.assertEqual([r["value"] for r in
                          self.model.query("building-001", "floors", AT,
                                           "2026-01-09T00:00:00Z")["reports"]],
                         [6, 7])

    def test_entity_snapshot_rejects_invalid_identity_and_temporal_cutoffs(self):
        for entity, at, known in [("bad entity", AT, LATE),
                                   ("building-001", "unparseable", LATE),
                                   ("building-001", AT, "2026-01-07")]:
            with self.assertRaises(ValueError):
                self.model.entity_snapshot(entity, at, known)

    def test_real_cli_all_attributes_and_mutually_exclusive_flags(self):
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        args = [sys.executable, "-m", "monde.world", "--fixture",
                str(ROOT / "examples/monde-mini.json"), "--entity", "building-001",
                "--all-attributes", "--at", AT, "--known-at", LATE]
        result = subprocess.run(args, capture_output=True, text=True, check=False, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([x["value"] for x in
                          json.loads(result.stdout)["attributes"]["floors"]["reports"]], [6, 7])
        unsupported = subprocess.run(args + ["--attribute", "floors"],
                                     capture_output=True, text=True, check=False, env=env)
        self.assertNotEqual(unsupported.returncode, 0)

    def test_real_cli_on_repo_fixture(self):
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        args = [sys.executable, "-m", "monde.world", "--fixture",
                str(ROOT / "examples/monde-mini.json"), "--entity", "building-001",
                "--attribute", "floors", "--at", AT, "--known-at", LATE]
        run = subprocess.run(args, capture_output=True, text=True, check=False, env=env)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual([r["value"] for r in json.loads(run.stdout)["reports"]], [6, 7])
        args[args.index(AT)] = "invalid"
        fail = subprocess.run(args, capture_output=True, text=True, check=False, env=env)
        self.assertEqual(fail.returncode, 2)


    def test_knowledge_delta_source_correction_and_stable_other_source(self):
        delta = self.model.compare_knowledge(
            "building-001", AT, "2026-01-05T00:00:00Z", LATE)
        self.assertEqual(delta["comparison"], "KNOWLEDGE_ONLY")
        self.assertEqual(delta["status"], "CHANGED")
        floors = delta["changes"]["floors"]
        self.assertEqual([r["value"] for r in floors["newly_current"]], [7])
        self.assertEqual([r["value"] for r in floors["no_longer_current"]], [5])
        self.assertEqual(floors["still_current_count"], 1)
        self.assertEqual(floors["newly_current"][0]["supersedes"], "a-city-initial")
        self.assertEqual(floors["newly_current"][0]["source_id"], "city-registry")
        self.assertEqual(floors["no_longer_current"][0]["evidence_id"], "e-city-reg-1")
        self.assertEqual(len(self.model.export()["assertions"]), 3)

    def test_knowledge_delta_new_reports_from_unknown(self):
        delta = self.model.compare_knowledge(
            "building-001", AT, "2026-01-03T09:59:59Z", "2026-01-05T00:00:00Z")
        floors = delta["changes"]["floors"]
        self.assertEqual(floors["before_status"], "UNKNOWN")
        self.assertEqual(floors["after_status"], "REPORTED")
        self.assertEqual([r["value"] for r in floors["newly_current"]], [5, 6])
        self.assertEqual(floors["no_longer_current"], [])

    def test_knowledge_delta_unchanged_cutoffs_and_missing_entity(self):
        for entity in ("building-001", "missing-001"):
            delta = self.model.compare_knowledge(
                entity, AT, LATE, "2026-01-08T00:00:00Z")
            self.assertEqual(delta["status"], "UNCHANGED")
            self.assertEqual(delta["changes"], {})

    def test_knowledge_delta_rejects_invalid_range(self):
        for before, after in [
            (LATE, LATE), (LATE, "2026-01-05T00:00:00Z"),
            ("2026-01-05T00:00:00", LATE)
        ]:
            with self.assertRaises(ValueError):
                self.model.compare_knowledge("building-001", AT, before, after)

    def test_knowledge_delta_is_bitemporal_immutable(self):
        exported = self.model.export()
        delta = self.model.compare_knowledge(
            "building-001", "2025-12-31T00:00:00Z",
            "2026-01-05T00:00:00Z", LATE)
        self.assertEqual(delta["status"], "UNCHANGED")
        diff = self.model.compare_knowledge("building-001", AT,
                                            "2026-01-05T00:00:00Z", LATE)
        diff["changes"]["floors"]["newly_current"][0]["value"] = -999
        self.assertEqual(self.model.export(), exported)
        self.assertEqual(self.query()["reports"][-1]["value"], 7)

    def test_real_cli_knowledge_comparison(self):
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        args = [sys.executable, "-m", "monde.world", "--fixture",
                str(ROOT / "examples/monde-mini.json"), "--entity", "building-001",
                "--all-attributes", "--at", AT, "--known-at", LATE,
                "--compare-known-at", "2026-01-05T00:00:00Z"]
        result = subprocess.run(args, capture_output=True, text=True, env=env,
                                check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        diff = json.loads(result.stdout)
        self.assertEqual(diff["comparison"], "KNOWLEDGE_ONLY")
        self.assertEqual([r["value"] for r in
                          diff["changes"]["floors"]["newly_current"]], [7])
        invalid = subprocess.run(args + ["--attribute", "floors"],
                                 capture_output=True, text=True, env=env,
                                 check=False)
        self.assertNotEqual(invalid.returncode, 0)


if __name__ == "__main__":
    unittest.main()
