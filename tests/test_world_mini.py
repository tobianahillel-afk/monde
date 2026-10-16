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

    def test_timeline_source_reports_across_world_time_without_claiming_truth(self):
        self.model.add_evidence({
            "id": "e-survey", "source_id": "survey",
            "locator": "fixture://survey/2026-jan", "captured_at": "2026-01-09T00:00:00Z",
            "source_event_at": "2026-01-03T00:00:00Z",
        })
        self.model.add_assertion({
            "id": "a-height", "entity": "building-001", "attribute": "height",
            "value": 12, "evidence_id": "e-survey", "kind": "OBSERVATION",
            "known_at": "2026-01-09T00:00:00Z",
            "valid_from": "2026-01-03T00:00:00Z",
            "valid_to": "2026-01-06T00:00:00Z", "supersedes": None,
        })
        timeline = self.model.timeline(
            "building-001", "height", "2026-01-01T00:00:00Z",
            "2026-01-10T00:00:00Z", "2026-01-10T00:00:00Z")
        self.assertEqual(timeline["comparison"], "WORLD_TIME_REPORTS_ONLY")
        self.assertEqual([s["status"] for s in timeline["segments"]],
                         ["UNKNOWN", "REPORTED", "UNKNOWN"])
        self.assertEqual([(s["valid_from"], s["valid_to"]) for s in timeline["segments"]],
                         [("2026-01-01T00:00:00Z", "2026-01-03T00:00:00Z"),
                          ("2026-01-03T00:00:00Z", "2026-01-06T00:00:00Z"),
                          ("2026-01-06T00:00:00Z", "2026-01-10T00:00:00Z")])
        report = timeline["segments"][1]["reports"][0]
        self.assertEqual((report["value"], report["source_id"], report["evidence_id"]),
                         (12, "survey", "e-survey"))
        self.assertEqual(timeline["world"], "OBSERVED")
        self.assertEqual(self.model.timeline(
            "building-001", "height", "2026-01-01T00:00:00Z",
            "2026-01-10T00:00:00Z", "2026-01-08T00:00:00Z")["status"], "UNKNOWN")

    def test_timeline_preserves_conflicting_sources_and_corrected_knowledge(self):
        early = self.model.timeline(
            "building-001", "floors", "2026-01-01T00:00:00Z",
            "2026-02-01T00:00:00Z", "2026-01-05T00:00:00Z")
        late = self.model.timeline(
            "building-001", "floors", "2026-01-01T00:00:00Z",
            "2026-02-01T00:00:00Z", LATE)
        self.assertEqual(len(early["segments"]), 1)
        self.assertEqual([r["value"] for r in early["segments"][0]["reports"]], [5, 6])
        self.assertEqual([r["value"] for r in late["segments"][0]["reports"]], [6, 7])
        self.assertEqual(late["segments"][0]["reports"][1]["supersedes"], "a-city-initial")

    def test_timeline_knowledge_cutoff_does_not_leak_future_validity_boundaries(self):
        self.model.add_evidence({
            "id": "e-late-b", "source_id": "s", "locator": "fixture://later",
            "captured_at": "2026-01-20T00:00:00Z", "source_event_at": None,
        })
        self.model.add_assertion({
            "id": "a-late-height", "entity": "building-001", "attribute": "height",
            "value": 12, "evidence_id": "e-late-b", "kind": "CLAIM",
            "known_at": "2026-01-20T00:00:00Z",
            "valid_from": "2026-01-05T00:00:00Z",
            "valid_to": "2026-01-08T00:00:00Z", "supersedes": None,
        })
        unknown = self.model.timeline(
            "building-001", "height", "2026-01-01T00:00:00Z",
            "2026-01-12T00:00:00Z", LATE)
        self.assertEqual(unknown["status"], "UNKNOWN")
        self.assertEqual(len(unknown["segments"]), 1)
        later = self.model.timeline(
            "building-001", "height", "2026-01-01T00:00:00Z",
            "2026-01-12T00:00:00Z", "2026-01-21T00:00:00Z")
        self.assertEqual([s["status"] for s in later["segments"]],
                         ["UNKNOWN", "REPORTED", "UNKNOWN"])

    def test_timeline_offsets_half_open_boundaries_and_defensive_output(self):
        exported = self.model.export()
        res = self.model.timeline(
            "building-001", "floors", "2026-01-01T01:00:00+01:00",
            "2026-01-02T01:00:00+01:00", LATE)
        self.assertEqual(len(res["segments"]), 1)
        self.assertEqual(res["segments"][0]["valid_from"], "2026-01-01T00:00:00Z")
        self.assertEqual(res["segments"][0]["valid_to"], "2026-01-02T00:00:00Z")
        res["segments"][0]["reports"][0]["value"] = -1
        self.assertEqual(self.model.export(), exported)

    def test_timeline_rejects_backward_identical_and_timezone_naive_windows(self):
        for start, end in [
            ("2026-01-02T00:00:00Z", "2026-01-02T00:00:00Z"),
            ("2026-02-01T00:00:00Z", "2026-01-01T00:00:00Z"),
            ("2026-01-01T00:00:00", "2026-01-02T00:00:00Z"),
        ]:
            with self.assertRaises(ValueError):
                self.model.timeline("building-001", "floors", start, end, LATE)

    def test_timeline_cli_real_subprocess_and_invalid_combinations(self):
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        args = [sys.executable, "-m", "monde.world", "--fixture",
                str(ROOT / "examples/monde-mini.json"), "--entity", "building-001",
                "--attribute", "floors", "--timeline-from", "2026-01-01T00:00:00Z",
                "--timeline-to", "2026-01-03T00:00:00Z", "--known-at", LATE]
        result = subprocess.run(args, capture_output=True, text=True, env=env,
                                check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["comparison"], "WORLD_TIME_REPORTS_ONLY")
        self.assertEqual([r["value"] for r in output["segments"][0]["reports"]], [6, 7])
        for invalid in [args + ["--at", AT], args + ["--compare-known-at", AT],
                        args[:-2], args + ["--all-attributes"]]:
            rejected = subprocess.run(invalid, capture_output=True, text=True,
                                      env=env, check=False)
            self.assertNotEqual(rejected.returncode, 0)



    def test_search_cross_entity_matching_and_competing_reports(self):
        self.model.add_evidence({
            "id": "e-second", "source_id": "survey",
            "locator": "fixture://second", "captured_at": "2026-01-08T00:00:00Z",
            "source_event_at": None})
        self.model.add_assertion({
            "id": "a-second", "entity": "building-002", "attribute": "floors",
            "value": 7, "evidence_id": "e-second", "kind": "CLAIM",
            "known_at": "2026-01-08T00:00:00Z",
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_to": None, "supersedes": None})
        found = self.model.search_reports("floors", 7, AT, "2026-01-09T00:00:00Z")
        self.assertEqual(found["query"], "SOURCE_REPORT_MATCH_ONLY")
        self.assertEqual([m["entity"] for m in found["matches"]],
                         ["building-001", "building-002"])
        self.assertEqual([r["value"] for r in found["matches"][0]["other_reports"]], [6])
        self.assertEqual(found["matches"][0]["matched_reports"][0]["evidence_id"], "e-city-reg-2")
        self.assertEqual(self.model.search_reports(
            "floors", 7, AT, "2026-01-05T00:00:00Z")["status"], "NO_MATCHES")
        self.assertEqual(self.model.search_reports(
            "floors", 5, AT, "2026-01-05T00:00:00Z")["matches"][0]
            ["matched_reports"][0]["value"], 5)

    def test_search_no_match_means_no_report_not_physical_absence(self):
        found = self.model.search_reports("floors", 42, AT, LATE)
        self.assertEqual(found["status"], "NO_MATCHES")
        self.assertEqual(found["matches"], [])
        self.assertEqual(found["query"], "SOURCE_REPORT_MATCH_ONLY")

    def test_search_json_value_types_do_not_coerce_boolean_to_integer(self):
        self.model.add_evidence({
            "id": "e-exact", "source_id": "registry",
            "locator": "fixture://boolean", "captured_at": "2026-01-08T00:00:00Z",
            "source_event_at": None})
        for i, value in enumerate([False, 0, {"b": 2, "a": 1}]):
            self.model.add_assertion({
                "id": "a-exact-" + str(i), "entity": "building-00" + str(i+1),
                "attribute": "special", "value": value, "evidence_id": "e-exact",
                "kind": "CLAIM", "known_at": "2026-01-08T00:00:00Z",
                "valid_from": "2026-01-01T00:00:00Z",
                "valid_to": None, "supersedes": None})
        cut = "2026-01-09T00:00:00Z"
        self.assertEqual([m["entity"] for m in
                          self.model.search_reports("special", False, AT, cut)["matches"]],
                         ["building-001"])
        self.assertEqual([m["entity"] for m in
                          self.model.search_reports("special", 0, AT, cut)["matches"]],
                         ["building-002"])
        self.assertEqual([m["entity"] for m in
                          self.model.search_reports("special", {"a": 1, "b": 2},
                                                    AT, cut)["matches"]],
                         ["building-003"])

    def test_search_results_are_readonly_and_cutoffs_reject_naive_time(self):
        original = self.model.export()
        response = self.model.search_reports("floors", 7, AT, LATE)
        response["matches"][0]["matched_reports"][0]["value"] = 999
        self.assertEqual(self.model.export(), original)
        with self.assertRaises(ValueError):
            self.model.search_reports("floors", 7, AT, "2026-01-09")
        with self.assertRaises(ValueError):
            self.model.search_reports("bad attr", 7, AT, LATE)

    def test_cli_cross_entity_search_on_two_buildings(self):
        fixture = copy.deepcopy(DOC)
        fixture["evidence"].append({
            "id": "e-extra", "source_id": "survey", "locator": "fixture://extra",
            "captured_at": "2026-01-08T00:00:00Z", "source_event_at": None})
        fixture["assertions"].append({
            "id": "a-extra", "entity": "building-002", "attribute": "floors",
            "value": 7, "evidence_id": "e-extra", "kind": "CLAIM",
            "known_at": "2026-01-08T00:00:00Z",
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_to": None, "supersedes": None})
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "many.json"
            path.write_text(json.dumps(fixture), encoding="utf-8")
            args = [sys.executable, "-m", "monde.world", "--fixture", str(path),
                    "--search-attribute", "floors", "--equals-json", "7",
                    "--at", AT, "--known-at", "2026-01-09T00:00:00Z"]
            env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
            found = subprocess.run(args, capture_output=True, text=True, env=env)
            self.assertEqual(found.returncode, 0, found.stderr)
            result = json.loads(found.stdout)
            self.assertEqual([m["entity"] for m in result["matches"]],
                             ["building-001", "building-002"])
            self.assertEqual(result["matches"][0]["other_reports"][0]["value"], 6)
            for broken in [
                args + ["--entity", "building-001"],
                args[:args.index("--equals-json")+1] + ["NaN"] + args[args.index("--at"):],
                args[:args.index("--equals-json")+1] + ['{"a":1,"a":2}'] +
                    args[args.index("--at"):],
            ]:
                denied = subprocess.run(broken, capture_output=True, text=True, env=env)
                self.assertNotEqual(denied.returncode, 0)

    def test_search_flags_do_not_change_existing_entity_query_cli(self):
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        args = [sys.executable, "-m", "monde.world",
                "--fixture", str(ROOT / "examples/monde-mini.json"),
                "--entity", "building-001", "--attribute", "floors",
                "--at", AT, "--known-at", LATE]
        good = subprocess.run(args, capture_output=True, text=True, env=env)
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertEqual([r["value"] for r in json.loads(good.stdout)["reports"]], [6, 7])
        denied = subprocess.run(args + ["--equals-json", "7"],
                                capture_output=True, text=True, env=env)
        self.assertNotEqual(denied.returncode, 0)



    def test_world_time_compare_reports_validity_changes_not_physical_events(self):
        self.model.add_evidence({
            "id": "e-occupancy", "source_id": "survey",
            "locator": "fixture://survey/occupancy",
            "captured_at": "2026-01-08T00:00:00Z", "source_event_at": None,
        })
        for assertion_id, value, start, end in [
            ("a-occupied", "vacant", "2026-01-01T00:00:00Z", "2026-01-05T00:00:00Z"),
            ("a-occupied-later", "occupied", "2026-01-05T00:00:00Z", None),
        ]:
            self.model.add_assertion({
                "id": assertion_id, "entity": "building-001",
                "attribute": "occupancy", "value": value, "evidence_id": "e-occupancy",
                "kind": "CLAIM", "known_at": "2026-01-08T00:00:00Z",
                "valid_from": start, "valid_to": end, "supersedes": None,
            })
        result = self.model.compare_world_time(
            "building-001", AT, "2026-01-05T00:00:00Z",
            "2026-01-09T00:00:00Z")
        self.assertEqual(result["comparison"], "WORLD_TIME_REPORTS_ONLY")
        self.assertEqual(result["status"], "CHANGED")
        occupancy = result["changes"]["occupancy"]
        self.assertEqual(occupancy["before_status"], "REPORTED")
        self.assertEqual(occupancy["after_status"], "REPORTED")
        self.assertEqual([r["value"] for r in occupancy["no_longer_current"]], ["vacant"])
        self.assertEqual([r["value"] for r in occupancy["newly_current"]], ["occupied"])
        self.assertEqual(occupancy["newly_current"][0]["source_id"], "survey")
        self.assertEqual(occupancy["newly_current"][0]["evidence_id"], "e-occupancy")
        self.assertNotIn("floors", result["changes"])  # unchanged conflicting sources stay intact

    def test_world_time_compare_unknown_to_reported_at_fixed_knowledge(self):
        changed = self.model.compare_world_time(
            "building-001", "2025-12-31T00:00:00Z", AT, LATE)
        self.assertEqual(changed["status"], "CHANGED")
        floors = changed["changes"]["floors"]
        self.assertEqual(floors["before_status"], "UNKNOWN")
        self.assertEqual(floors["after_status"], "REPORTED")
        self.assertEqual([r["value"] for r in floors["newly_current"]], [6, 7])
        self.assertEqual(floors["no_longer_current"], [])

    def test_world_time_compare_known_at_prevents_future_knowledge_leak(self):
        earlier = self.model.compare_world_time(
            "building-001", "2025-12-31T00:00:00Z", AT,
            "2026-01-02T00:00:00Z")
        self.assertEqual(earlier["status"], "UNCHANGED")
        self.assertEqual(earlier["changes"], {})
        middle = self.model.compare_world_time(
            "building-001", "2025-12-31T00:00:00Z", AT,
            "2026-01-05T00:00:00Z")
        self.assertEqual([r["value"] for r in
                          middle["changes"]["floors"]["newly_current"]], [5, 6])

    def test_world_time_compare_rejects_invalid_and_non_increasing_instants(self):
        for earlier, later, known in [
            (AT, AT, LATE),
            ("2026-01-03T00:00:00Z", AT, LATE),
            ("2026-01-01T00:00:00", AT, LATE),
            (AT, "not-a-date", LATE),
            (AT, "2026-01-05T00:00:00Z", "2026-01-07"),
        ]:
            with self.assertRaises(ValueError):
                self.model.compare_world_time("building-001", earlier, later, known)
        with self.assertRaises(ValueError):
            self.model.compare_world_time("bad entity", AT, LATE, LATE)

    def test_world_time_compare_does_not_mutate_evidence_or_outputs(self):
        frozen = self.model.export()
        delta = self.model.compare_world_time(
            "building-001", "2025-12-31T00:00:00Z", AT, LATE)
        delta["changes"]["floors"]["newly_current"][0]["value"] = 999
        self.assertEqual(self.model.export(), frozen)
        self.assertEqual([r["value"] for r in self.model.query(
            "building-001", "floors", AT, LATE)["reports"]], [6, 7])

    def test_real_cli_world_time_compare_and_mode_rejections(self):
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        base = [sys.executable, "-m", "monde.world", "--fixture",
                str(ROOT / "examples/monde-mini.json"), "--entity", "building-001",
                "--all-attributes", "--at", AT, "--known-at", LATE,
                "--compare-at", "2025-12-31T00:00:00Z"]
        out = subprocess.run(base, capture_output=True, text=True, env=env)
        self.assertEqual(out.returncode, 0, out.stderr)
        result = json.loads(out.stdout)
        self.assertEqual(result["comparison"], "WORLD_TIME_REPORTS_ONLY")
        self.assertEqual([r["value"] for r in
                          result["changes"]["floors"]["newly_current"]], [6, 7])
        for bad in [
            base + ["--compare-known-at", "2026-01-05T00:00:00Z"],
            [arg for arg in base if arg != "--all-attributes"],
            base[:-1] + [AT],
            base + ["--timeline-from", AT, "--timeline-to", LATE],
            [*base[:base.index("--all-attributes")], "--attribute", "floors",
             *base[base.index("--all-attributes")+1:]],
        ]:
            run = subprocess.run(bad, capture_output=True, text=True, env=env)
            self.assertNotEqual(run.returncode, 0)

    def test_source_disagreements_temporal_evidence_and_revisions(self):
        found = self.model.source_disagreements(AT, LATE)
        self.assertEqual(found["comparison"], "DIFFERENT_SOURCE_REPORTS_ONLY")
        self.assertEqual(found["status"], "DISAGREEMENTS_FOUND")
        self.assertEqual([(d["entity"], d["attribute"]) for d in found["disagreements"]],
                         [("building-001", "floors")])
        groups = found["disagreements"][0]["value_groups"]
        self.assertEqual([g["value"] for g in groups], [6, 7])
        self.assertEqual({r["evidence_id"] for g in groups for r in g["reports"]},
                         {"e-news-1", "e-city-reg-2"})
        self.assertEqual(self.model.source_disagreements(
            AT, "2026-01-03T10:00:00Z")["status"], "NO_DISAGREEMENTS_FOUND")
        self.assertEqual(self.model.source_disagreements(
            AT, LATE, "nonexistent")["disagreements"], [])

    def test_source_disagreements_require_distinct_sources_and_values(self):
        only_one_source = copy.deepcopy(DOC)
        only_one_source["evidence"] = [DOC["evidence"][0], DOC["evidence"][2]]
        only_one_source["assertions"] = [copy.deepcopy(DOC["assertions"][0]),
                                         copy.deepcopy(DOC["assertions"][2])]
        only_one_source["assertions"][1]["supersedes"] = None
        self.assertEqual(WorldMini.from_document(only_one_source).source_disagreements(
            AT, LATE)["status"], "NO_DISAGREEMENTS_FOUND")
        agreement = copy.deepcopy(DOC)
        agreement["assertions"][2]["value"] = 6
        self.assertEqual(WorldMini.from_document(agreement).source_disagreements(
            AT, LATE)["disagreements"], [])

    def test_source_disagreements_across_entities_preserve_json_types(self):
        for source, label in [("survey", "a"), ("inspection", "b")]:
            self.model.add_evidence({
                "id": "ev-" + label, "source_id": source, "locator": "fixture://" + label,
                "captured_at": "2026-01-08T00:00:00Z", "source_event_at": None})
        for i, value in enumerate([False, 0]):
            self.model.add_assertion({
                "id": "val-" + str(i), "entity": "building-002",
                "attribute": "active", "value": value,
                "evidence_id": "ev-" + ("a" if i == 0 else "b"),
                "kind": "CLAIM", "known_at": "2026-01-08T00:00:00Z",
                "valid_from": "2026-01-01T00:00:00Z",
                "valid_to": None, "supersedes": None})
        found = self.model.source_disagreements(AT, "2026-01-09T00:00:00Z")
        self.assertEqual([(r["entity"], r["attribute"]) for r in found["disagreements"]],
                         [("building-001", "floors"), ("building-002", "active")])
        self.assertEqual({type(g["value"]) for g in
                          found["disagreements"][1]["value_groups"]}, {bool, int})
        frozen = self.model.export()
        found["disagreements"][0]["value_groups"][0]["reports"][0]["value"] = 999
        self.assertEqual(self.model.export(), frozen)

    def test_source_disagreements_real_cli_and_invalid_modes(self):
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        cmd = [sys.executable, "-m", "monde.world", "--fixture",
               str(ROOT / "examples/monde-mini.json"),
               "--source-disagreements", "--at", AT, "--known-at", LATE]
        out = subprocess.run(cmd, capture_output=True, text=True, env=env)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout)["status"], "DISAGREEMENTS_FOUND")
        for extra in [["--entity", "building-001"], ["--equals-json", "7"],
                      ["--compare-at", AT], ["--timeline-from", AT]]:
            rejected = subprocess.run(cmd + extra, capture_output=True, text=True, env=env)
            self.assertNotEqual(rejected.returncode, 0)
        with self.assertRaises(ValueError):
            self.model.source_disagreements(AT, "2026-01-07")
        with self.assertRaises(ValueError):
            self.model.source_disagreements(AT, LATE, "invalid attribute")


    def test_source_history_preserves_corrections_and_capture_lineage(self):
        result = self.model.source_history("city-registry", LATE)
        self.assertEqual(result["view"], "SOURCE_ASSERTION_HISTORY_ONLY")
        self.assertEqual(result["status"], "HISTORY_FOUND")
        reports = result["reports"]
        self.assertEqual([r["value"] for r in reports], [5, 7])
        self.assertEqual([r["current_at_cutoff"] for r in reports], [False, True])
        self.assertEqual(reports[0]["superseded_by"], "a-city-revision")
        self.assertEqual(reports[1]["supersedes"], "a-city-initial")
        self.assertEqual([r["evidence_id"] for r in reports],
                         ["e-city-reg-1", "e-city-reg-2"])
        self.assertEqual(reports[0]["source_event_at"], "2026-01-01T00:00:00Z")
        self.assertEqual(reports[1]["captured_at"], "2026-01-06T11:00:00Z")
        self.assertEqual(self.model.source_history("local-news", LATE)["reports"][0]["value"], 6)

    def test_source_history_cannot_see_future_correction(self):
        early = self.model.source_history("city-registry", "2026-01-05T00:00:00Z")
        self.assertEqual([r["assertion_id"] for r in early["reports"]], ["a-city-initial"])
        self.assertTrue(early["reports"][0]["current_at_cutoff"])
        self.assertIsNone(early["reports"][0]["superseded_by"])
        self.assertEqual(self.model.source_history(
            "city-registry", "2026-01-03T09:59:59Z")["status"], "NO_REPORTS")

    def test_source_history_filters_multiple_entities_and_properties(self):
        self.model.add_evidence({
            "id": "e-new-building", "source_id": "city-registry",
            "locator": "fixture://city-registry/second",
            "captured_at": "2026-01-08T00:00:00Z", "source_event_at": None,
        })
        self.model.add_assertion({
            "id": "a-new-building", "entity": "building-002",
            "attribute": "height", "value": 0,
            "evidence_id": "e-new-building", "kind": "OBSERVATION",
            "known_at": "2026-01-08T00:00:00Z",
            "valid_from": "2026-01-01T00:00:00Z", "valid_to": None,
            "supersedes": None,
        })
        result = self.model.source_history("city-registry", "2026-01-09T00:00:00Z")
        self.assertEqual([r["entity"] for r in result["reports"]],
                         ["building-001", "building-001", "building-002"])
        self.assertEqual(self.model.source_history(
            "city-registry", "2026-01-09T00:00:00Z",
            entity="building-002")["reports"][0]["value"], 0)
        self.assertEqual(self.model.source_history(
            "city-registry", "2026-01-09T00:00:00Z",
            attribute="height")["reports"][0]["entity"], "building-002")
        self.assertEqual(self.model.source_history(
            "city-registry", "2026-01-09T00:00:00Z",
            entity="building-001", attribute="height")["status"], "NO_REPORTS")

    def test_source_history_is_read_only_and_rejects_invalid_queries(self):
        old = self.model.export()
        history = self.model.source_history("city-registry", LATE)
        history["reports"][1]["value"] = "tampered"
        self.assertEqual(self.model.export(), old)
        self.assertEqual(self.model.source_history(
            "city-registry", LATE)["reports"][1]["value"], 7)
        for params in [
            ("not a source", LATE, None, None),
            ("city-registry", "2026-01-03", None, None),
            ("city-registry", LATE, "bad entity", None),
            ("city-registry", LATE, None, "bad attribute"),
        ]:
            with self.assertRaises(ValueError):
                self.model.source_history(*params)

    def test_source_history_cli_real_process_and_incompatible_modes(self):
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        base = [sys.executable, "-m", "monde.world", "--fixture",
                str(ROOT / "examples/monde-mini.json"), "--source-history",
                "city-registry", "--known-at", LATE]
        done = subprocess.run(base, capture_output=True, text=True, env=env)
        self.assertEqual(done.returncode, 0, done.stderr)
        reports = json.loads(done.stdout)["reports"]
        self.assertEqual([r["value"] for r in reports], [5, 7])
        filtered = subprocess.run(
            base + ["--entity", "building-001", "--source-attribute", "floors"],
            capture_output=True, text=True, env=env)
        self.assertEqual(filtered.returncode, 0, filtered.stderr)
        self.assertEqual(len(json.loads(filtered.stdout)["reports"]), 2)
        for args in [
            base + ["--at", AT],
            base + ["--compare-at", AT],
            base + ["--equals-json", "7"],
            base + ["--timeline-from", AT, "--timeline-to", LATE],
            [sys.executable, "-m", "monde.world", "--fixture",
             str(ROOT / "examples/monde-mini.json"),
             "--source-disagreements", "--at", AT, "--known-at", LATE,
             "--source-attribute", "floors"],
        ]:
            rejected = subprocess.run(args, capture_output=True, text=True, env=env)
            self.assertNotEqual(rejected.returncode, 0)


    def test_knowledge_timeline_unknown_arrivals_and_source_correction(self):
        history = self.model.knowledge_timeline(
            "building-001", "floors", AT,
            "2026-01-01T00:00:00Z", "2026-01-08T00:00:00Z")
        self.assertEqual(history["comparison"], "KNOWLEDGE_TIME_REPORTS_ONLY")
        segments = history["segments"]
        self.assertEqual(len(segments), 4)
        self.assertEqual([s["status"] for s in segments],
                         ["UNKNOWN", "REPORTED", "REPORTED", "REPORTED"])
        self.assertEqual([[r["value"] for r in s["reports"]] for s in segments],
                         [[], [5], [5, 6], [6, 7]])
        self.assertEqual([s["known_from"] for s in segments], [
            "2026-01-01T00:00:00Z", "2026-01-03T10:00:00Z",
            "2026-01-04T09:00:00Z", "2026-01-06T11:00:00Z"])
        self.assertEqual(segments[-1]["known_to"], "2026-01-08T00:00:00Z")
        self.assertEqual(segments[-1]["reports"][-1]["evidence_id"], "e-city-reg-2")
        self.assertEqual(segments[-1]["reports"][-1]["supersedes"], "a-city-initial")

    def test_knowledge_timeline_cutoff_never_leaks_future_correction(self):
        history = self.model.knowledge_timeline(
            "building-001", "floors", AT,
            "2026-01-03T00:00:00Z", "2026-01-05T00:00:00Z")
        self.assertEqual([[r["value"] for r in s["reports"]]
                          for s in history["segments"]], [[], [5], [5, 6]])
        self.assertTrue(all(r["assertion_id"] != "a-city-revision"
                            for s in history["segments"] for r in s["reports"]))
        boundary = self.model.knowledge_timeline(
            "building-001", "floors", AT,
            "2026-01-04T09:00:00Z", "2026-01-06T11:00:00Z")
        self.assertEqual(len(boundary["segments"]), 1)
        self.assertEqual([r["value"] for r in boundary["segments"][0]["reports"]],
                         [5, 6])

    def test_knowledge_timeline_unknown_and_out_of_validity_events(self):
        unknown = self.model.knowledge_timeline(
            "building-001", "height", AT,
            "2026-01-01T00:00:00Z", LATE)
        self.assertEqual(unknown["status"], "UNKNOWN")
        self.assertEqual(len(unknown["segments"]), 1)
        self.assertEqual(unknown["segments"][0]["reports"], [])
        outside = self.model.knowledge_timeline(
            "building-001", "floors", "2025-01-01T00:00:00Z",
            "2026-01-01T00:00:00Z", LATE)
        self.assertEqual(len(outside["segments"]), 1)
        self.assertEqual(outside["status"], "UNKNOWN")

    def test_knowledge_timeline_offsets_half_open_and_defensive_results(self):
        before = self.model.export()
        result = self.model.knowledge_timeline(
            "building-001", "floors", AT,
            "2026-01-01T01:00:00+01:00", "2026-01-08T01:00:00+01:00")
        self.assertEqual(result["segments"][0]["known_from"], "2026-01-01T00:00:00Z")
        result["segments"][-1]["reports"][-1]["value"] = "tampered"
        self.assertEqual(self.model.export(), before)
        self.assertEqual([r["value"] for r in self.query()["reports"]], [6, 7])

    def test_knowledge_timeline_rejects_invalid_bounds_and_identifiers(self):
        for start, end in [(LATE, AT), (AT, AT),
                           ("2026-01-01T00:00:00", LATE),
                           (AT, "2026-01-07")]:
            with self.assertRaises(ValueError):
                self.model.knowledge_timeline("building-001", "floors", AT, start, end)
        with self.assertRaises(ValueError):
            self.model.knowledge_timeline("bad entity", "floors", AT, AT, LATE)
        with self.assertRaises(ValueError):
            self.model.knowledge_timeline("building-001", "bad attribute", AT, AT, LATE)

    def test_knowledge_timeline_cli_real_process_and_exclusive_modes(self):
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        base = [sys.executable, "-m", "monde.world",
                "--fixture", str(ROOT / "examples/monde-mini.json"),
                "--entity", "building-001", "--attribute", "floors",
                "--at", AT, "--knowledge-timeline-from", "2026-01-01T00:00:00Z",
                "--known-at", LATE]
        done = subprocess.run(base, capture_output=True, text=True, env=env)
        self.assertEqual(done.returncode, 0, done.stderr)
        got = json.loads(done.stdout)
        self.assertEqual(got["comparison"], "KNOWLEDGE_TIME_REPORTS_ONLY")
        self.assertEqual([[x["value"] for x in s["reports"]]
                          for s in got["segments"]], [[], [5], [5, 6], [6, 7]])
        for extra in [["--compare-known-at", AT], ["--timeline-from", AT],
                      ["--source-history", "city-registry"], ["--all-attributes"],
                      ["--search-attribute", "floors"], ["--equals-json", "5"],
                      ["--source-disagreements"]]:
            bad = subprocess.run(base + extra, capture_output=True, text=True, env=env)
            self.assertNotEqual(bad.returncode, 0)


    def test_updates_source_arrivals_and_corrections(self):
        result = self.model.knowledge_updates("2026-01-03T10:00:00Z", LATE)
        self.assertEqual(result["comparison"], "NEW_SOURCE_REPORTS_ONLY")
        self.assertEqual([r["assertion_id"] for r in result["reports"]],
                         ["a-news", "a-city-revision"])
        self.assertEqual([r["value"] for r in result["reports"]], [6, 7])
        self.assertEqual(result["reports"][1]["supersedes"], "a-city-initial")
        self.assertEqual(result["reports"][1]["source_id"], "city-registry")
        self.assertTrue(all(r["evidence_id"] and r["locator"]
                            for r in result["reports"]))

    def test_updates_exclusive_start_inclusive_end_timezone(self):
        x = self.model.knowledge_updates("2026-01-03T10:00:00Z",
                                         "2026-01-04T09:00:00Z")
        self.assertEqual([r["assertion_id"] for r in x["reports"]], ["a-news"])
        y = self.model.knowledge_updates("2026-01-03T11:00:00+01:00",
                                         "2026-01-04T10:00:00+01:00")
        self.assertEqual(x["reports"], y["reports"])
        self.assertEqual(self.model.knowledge_updates(LATE, "2026-01-08T00:00:00Z")["status"],
                         "NO_NEW_REPORTS")

    def test_updates_filters_all_entities_and_exact_json_values(self):
        self.model.add_evidence({
            "id": "e-other", "source_id": "other", "locator": "fixture://other",
            "captured_at": "2026-01-08T00:00:00Z", "source_event_at": None})
        self.model.add_assertion({
            "id": "a-other", "entity": "building-002", "attribute": "floors",
            "value": 0, "evidence_id": "e-other", "kind": "OBSERVATION",
            "known_at": "2026-01-08T00:00:00Z",
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_to": None, "supersedes": None})
        all_updates = self.model.knowledge_updates("2026-01-06T11:00:00Z",
                                                    "2026-01-09T00:00:00Z")
        self.assertEqual([r["entity"] for r in all_updates["reports"]], ["building-002"])
        self.assertEqual(all_updates["reports"][0]["value"], 0)
        self.assertEqual(self.model.knowledge_updates("2026-01-06T11:00:00Z",
                         "2026-01-09T00:00:00Z", entity="building-001")["count"], 0)
        self.assertEqual(self.model.knowledge_updates(AT, "2026-01-09T00:00:00Z",
                         attribute="floors")["count"], 4)

    def test_updates_never_mutate_data_or_assert_truth(self):
        original = self.model.export()
        result = self.model.knowledge_updates(AT, LATE)
        self.assertEqual(result["world"], "OBSERVED")
        result["reports"][0]["value"] = "tampered"
        self.assertEqual(self.model.export(), original)
        self.assertEqual([r["value"] for r in self.query()["reports"]], [6, 7])

    def test_updates_reject_bad_cutoffs_or_entity(self):
        for start, end in [(AT, AT), (LATE, AT),
                           ("2026-01-01T00:00:00", LATE), (AT, "bad")]:
            with self.assertRaises(ValueError):
                self.model.knowledge_updates(start, end)
        with self.assertRaises(ValueError):
            self.model.knowledge_updates(AT, LATE, entity="invalid name")

    def test_world_knowledge_changes_aggregates_multiple_entities(self):
        self.model.add_assertion({
            "id": "a-building-002", "entity": "building-002",
            "attribute": "floors", "value": 3, "evidence_id": "e-city-reg-2",
            "kind": "CLAIM", "known_at": "2026-01-06T12:00:00Z",
            "valid_from": "2026-01-01T00:00:00Z", "valid_to": None,
            "supersedes": None,
        })
        result = self.model.world_knowledge_changes(
            AT, "2026-01-03T00:00:00Z", LATE)
        self.assertEqual(result["world"], "OBSERVED")
        self.assertEqual(result["comparison"],
                         "CROSS_ENTITY_KNOWLEDGE_REPORTS_ONLY")
        self.assertEqual([item["entity"] for item in result["entities"]],
                         ["building-001", "building-002"])
        self.assertEqual(result["entity_count"], 2)
        report = result["entities"][1]["changes"]["floors"]["newly_current"][0]
        self.assertEqual(report["value"], 3)
        self.assertEqual(report["evidence_id"], "e-city-reg-2")
        self.assertEqual(report["source_id"], "city-registry")
        early = self.model.world_knowledge_changes(
            AT, "2026-01-03T00:00:00Z", "2026-01-04T00:00:00Z")
        self.assertEqual([x["entity"] for x in early["entities"]],
                         ["building-001"])

    def test_world_knowledge_changes_corrections_unknown_and_immutability(self):
        before = self.model.export()
        result = self.model.world_knowledge_changes(
            AT, "2026-01-04T12:00:00Z", LATE)
        delta = result["entities"][0]["changes"]["floors"]
        self.assertEqual([x["value"] for x in delta["no_longer_current"]], [5])
        self.assertEqual([x["value"] for x in delta["newly_current"]], [7])
        self.assertEqual(delta["still_current_count"], 1)
        result["entities"][0]["changes"]["floors"]["newly_current"][0]["value"] = 999
        self.assertEqual(self.model.export(), before)
        unchanged = self.model.world_knowledge_changes(
            AT, LATE, "2026-01-08T00:00:00Z")
        self.assertEqual(unchanged["status"], "UNCHANGED")
        self.assertEqual(unchanged["entities"], [])
        for old, new in [(AT, AT), (LATE, AT),
                         ("2026-01-03T00:00:00", LATE)]:
            with self.assertRaises(ValueError):
                self.model.world_knowledge_changes(AT, old, new)

    def test_world_knowledge_changes_cli_end_to_end(self):
        cmd = [sys.executable, "-m", "monde.world", "--fixture",
               str(ROOT / "examples/monde-mini.json"),
               "--world-knowledge-changes", "--at", AT,
               "--compare-known-at", "2026-01-03T00:00:00Z",
               "--known-at", LATE]
        env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
        run = subprocess.run(cmd, cwd=ROOT, env=env, text=True,
                             capture_output=True, check=False)
        self.assertEqual(run.returncode, 0, run.stderr)
        data = json.loads(run.stdout)
        self.assertEqual(data["entity_count"], 1)
        self.assertEqual(data["entities"][0]["entity"], "building-001")
        self.assertTrue(data["entities"][0]["changes"]["floors"]["newly_current"])
        for extra in [["--entity", "building-001"],
                      ["--equals-json", "5"], ["--compare-at", AT],
                      ["--timeline-from", AT]]:
            bad = subprocess.run(cmd + extra, cwd=ROOT, env=env,
                                 text=True, capture_output=True, check=False)
            self.assertNotEqual(bad.returncode, 0)

    def test_updates_actual_cli_and_disallow_mode_mix(self):
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        argv = [sys.executable, "-m", "monde.world",
                "--fixture", str(ROOT / "examples/monde-mini.json"),
                "--knowledge-updates", "--updates-from",
                "2026-01-03T10:00:00Z", "--known-at", LATE]
        result = subprocess.run(argv, capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["count"], 2)
        for extra in [["--at", AT], ["--compare-at", AT],
                      ["--source-history", "city-registry"],
                      ["--timeline-from", AT], ["--equals-json", "5"],
                      ["--knowledge-timeline-from", AT]]:
            bad = subprocess.run(argv + extra, capture_output=True, text=True, env=env)
            self.assertNotEqual(bad.returncode, 0)
        missing = subprocess.run([sys.executable, "-m", "monde.world",
                                  "--fixture", str(ROOT / "examples/monde-mini.json"),
                                  "--knowledge-updates", "--known-at", LATE],
                                 capture_output=True, text=True, env=env)
        self.assertNotEqual(missing.returncode, 0)

if __name__ == "__main__":
    unittest.main()
