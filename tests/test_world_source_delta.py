"""Portable append-only source-change reports, including real mixed-source files."""
import csv
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from monde.source_delta import source_delta, source_delta_geojson, source_delta_csv
from monde.world import WorldMini
from monde.csv_points import documents_from_manifest
from tests.test_world_map_source_manifest_layers import sample

ROOT = Path(__file__).resolve().parents[1]


def document(evidence_id, assertion_id, *, source="survey", known="2026-01-02T12:00:00Z",
             supersedes=None, value=1):
    return {"schema_version": 1,
            "evidence": [{
                "id": evidence_id, "source_id": source,
                "locator": "dataset://" + source,
                "captured_at": known, "source_event_at": "2026-01-01T00:00:00Z",
            }],
            "assertions": [{
                "id": assertion_id, "entity": "site-a", "attribute": "status",
                "value": value, "evidence_id": evidence_id, "kind": "CLAIM",
                "known_at": known, "valid_from": "2026-01-01T00:00:00Z",
                "valid_to": None, "supersedes": supersedes,
            }]}


class SnapshotDeltaTests(unittest.TestCase):
    def test_append_only_correction_preserves_original_source_and_time(self):
        before = WorldMini.from_document(document("e1", "a1"))
        after = WorldMini.from_document(before.export())
        after.append_document(document("e2", "a2", known="2026-01-03T12:00:00Z",
                                       supersedes="a1", value=2))
        report = source_delta(before, after)
        self.assertEqual(report["added"], {
            "evidence": 1, "assertions": 1, "corrections": 1})
        self.assertEqual(report["sources"][0]["affected_entities"], ["site-a"])
        self.assertEqual(report["sources"][0]["source_id"], "survey")
        self.assertEqual(report["new_reports"][0]["supersedes"], "a1")
        self.assertEqual(report["new_reports"][0]["known_at"], "2026-01-03T12:00:00Z")
        self.assertEqual(before.export()["assertions"][0]["value"], 1)

    def test_identical_snapshots_have_no_new_reports(self):
        before = WorldMini.from_document(document("e1", "a1"))
        result = source_delta(before, WorldMini.from_document(before.export()))
        self.assertEqual(result["added"]["evidence"], 0)
        self.assertEqual(result["added"]["assertions"], 0)
        self.assertEqual(result["sources"], [])
        self.assertEqual(result["new_reports"], [])

    def test_distinct_sources_remain_distinct_without_truth_reconciliation(self):
        before = WorldMini.from_document(document("e1", "a1"))
        after = WorldMini.from_document(before.export())
        after.append_document(document("e2", "a2", source="independent",
                                       known="2026-01-04T12:00:00Z", value=9))
        out = source_delta(before, after)
        self.assertEqual([x["source_id"] for x in out["sources"]], ["independent"])
        self.assertEqual(out["new_reports"][0]["kind"], "CLAIM")
        self.assertNotIn("estimated_truth", out)

    def test_rewritten_missing_or_reordered_history_is_rejected(self):
        original = document("e1", "a1")
        before = WorldMini.from_document(original)
        later = WorldMini.from_document(before.export())
        later.append_document(document("e2", "a2", source="other",
                                       known="2026-01-04T12:00:00Z"))
        tampered = later.export()
        tampered["assertions"][0]["value"] = "forged"
        with self.assertRaisesRegex(ValueError, "diverged"):
            source_delta(before, WorldMini.from_document(tampered))
        with self.assertRaisesRegex(ValueError, "diverged"):
            source_delta(later, before)
        reordered = later.export()
        reordered["evidence"].reverse()
        with self.assertRaisesRegex(ValueError, "diverged"):
            source_delta(before, WorldMini.from_document(reordered))


    def test_html_uses_existing_offline_renderer_without_fabricating_world_movement(self):
        from monde.source_delta import source_delta_html
        earlier = document("e1", "a1", value={"type": "Point",
                                             "coordinates": [2.3, 48.8]})
        earlier["assertions"][0]["attribute"] = "geo_point"
        before = WorldMini.from_document(earlier)
        after = WorldMini.from_document(before.export())
        correction = document("e2", "a2", known="2026-01-03T12:00:00Z",
                              supersedes="a1", value={"type": "Point",
                                                       "coordinates": [2.4, 48.9]})
        correction["assertions"][0]["attribute"] = "geo_point"
        after.append_document(correction)
        html = source_delta_html(before, after)
        self.assertIn("NEW SOURCE REPORTS ONLY", html)
        self.assertIn("id=\"monde-data\"", html)
        self.assertNotIn("https://tile.", html)
        self.assertNotIn("</script><script>alert", html)
        embedded = html.split('id="monde-data">', 1)[1].split("</script>", 1)[0]
        mapped = json.loads(embedded)
        self.assertEqual([f["id"] for f in mapped["features"]], ["a2"])
        self.assertEqual(mapped["features"][0]["properties"]["supersedes"], "a1")
        self.assertEqual(mapped["features"][0]["properties"]["source_id"], "survey")
        self.assertEqual(mapped["monde_source_delta"]["corrections_added"], 1)
        self.assertEqual(mapped["monde_bbox_query"]["total_source_features"], 1)
        self.assertEqual(before.export()["assertions"][0]["value"]["coordinates"],
                         [2.3, 48.8])

    def test_html_works_with_no_new_geo_points_but_preserves_delta_counts(self):
        from monde.source_delta import source_delta_html
        original = WorldMini.from_document(document("e1", "a1"))
        changed = WorldMini.from_document(original.export())
        changed.append_document(document("e2", "a2", value=2))
        html = source_delta_html(original, changed)
        embedded = html.split('id="monde-data">', 1)[1].split("</script>", 1)[0]
        data = json.loads(embedded)
        self.assertEqual(data["features"], [])
        self.assertEqual(data["monde_bbox_query"]["status"], "NO_MATCHES")
        self.assertEqual(data["monde_source_delta"]["assertions_added"], 1)

    def test_cli_html_from_saved_snapshots_is_read_only_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root)
            before, after = WorldMini(), WorldMini()
            point = document("e1", "a1", value={"type": "Point",
                                                "coordinates": [12.5, 41.9]})
            point["assertions"][0]["attribute"] = "geo_point"
            after.append_document(point)
            first, second, out = p/"before.json", p/"after.json", p/"changes.html"
            before.save(first)
            after.save(second)
            originals = first.read_bytes(), second.read_bytes()
            command = [sys.executable, "-m", "monde.source_delta",
                       "--before", str(first), "--after", str(second),
                       "--as-html", "--output", str(out)]
            env = {**os.environ, "PYTHONPATH": str(ROOT/"src")}
            done = subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn('id="monde-data"', out.read_text(encoding="utf-8"))
            self.assertEqual((first.read_bytes(), second.read_bytes()), originals)
            repeat = subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertEqual(repeat.returncode, 2)
            self.assertEqual((first.read_bytes(), second.read_bytes()), originals)
            self.assertEqual(out.read_text(encoding="utf-8").count('id="monde-data"'), 1)
            overwrite = subprocess.run(command[:-1] + [str(first)], env=env,
                                       capture_output=True, text=True)
            self.assertEqual(overwrite.returncode, 2)
            self.assertEqual((first.read_bytes(), second.read_bytes()), originals)

    def test_html_source_text_is_script_escaped_and_divergent_history_fails(self):
        from monde.source_delta import source_delta_html
        unsafe = document("e1", "a1", source="survey",
                          value={"type": "Point", "coordinates": [1, 2]})
        unsafe["evidence"][0]["locator"] = "</script><script>alert(1)</script>"
        unsafe["assertions"][0]["attribute"] = "geo_point"
        after = WorldMini.from_document(unsafe)
        html = source_delta_html(WorldMini(), after)
        self.assertNotIn("</script><script>alert(1)", html)
        self.assertIn("\\u003c", html)
        with self.assertRaisesRegex(ValueError, "diverged"):
            source_delta_html(after, WorldMini())

    def test_cli_reads_disk_snapshots_and_reports_failure_without_overwriting(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root)
            original = WorldMini.from_document(document("e1", "a1"))
            newer = WorldMini.from_document(original.export())
            newer.append_document(document("e2", "a2", known="2026-01-04T12:00:00Z"))
            before, after = p / "before.json", p / "after.json"
            original.save(before)
            newer.save(after)
            command = [sys.executable, "-m", "monde.source_delta",
                       "--before", str(before), "--after", str(after)]
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            result = subprocess.run(command, env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["added"]["assertions"], 1)
            input_bytes = before.read_bytes(), after.read_bytes()
            failed = subprocess.run([sys.executable, "-m", "monde.source_delta",
                                     "--before", str(after), "--after", str(before)],
                                    env=env, text=True, capture_output=True)
            self.assertEqual(failed.returncode, 2)
            self.assertIn("diverged", failed.stderr)
            self.assertEqual((before.read_bytes(), after.read_bytes()), input_bytes)

    def test_geojson_maps_only_new_source_point_reports_with_original_provenance(self):
        earlier = document("e1", "a1", value={"type": "Point", "coordinates": [2.3, 48.8]})
        earlier["assertions"][0]["attribute"] = "geo_point"
        before = WorldMini.from_document(earlier)
        after = WorldMini.from_document(before.export())
        corrected = document("e2", "a2", source="survey",
                             known="2026-01-03T12:00:00Z", supersedes="a1",
                             value={"type": "Point", "coordinates": [2.4, 48.9]})
        corrected["assertions"][0]["attribute"] = "geo_point"
        after.append_document(corrected)
        mapped = source_delta_geojson(before, after)
        self.assertEqual(mapped["type"], "FeatureCollection")
        self.assertEqual([f["id"] for f in mapped["features"]], ["a2"])
        point = mapped["features"][0]
        self.assertEqual(point["geometry"]["coordinates"], [2.4, 48.9])
        self.assertEqual(point["properties"]["source_id"], "survey")
        self.assertEqual(point["properties"]["evidence_id"], "e2")
        self.assertEqual(point["properties"]["source_locator"], "dataset://survey")
        self.assertEqual(point["properties"]["captured_at"], "2026-01-03T12:00:00Z")
        self.assertEqual(point["properties"]["source_event_at"], "2026-01-01T00:00:00Z")
        self.assertEqual(point["properties"]["supersedes"], "a1")
        self.assertEqual(point["properties"]["known_at"], "2026-01-03T12:00:00Z")
        self.assertEqual(point["properties"]["monde_status"], "NEW_SOURCE_REPORT_ONLY")
        self.assertEqual(mapped["monde_source_delta"]["corrections_added"], 1)
        self.assertEqual(before.export()["assertions"][0]["value"]["coordinates"],
                         [2.3, 48.8])

    def test_geojson_empty_for_non_spatial_reports_and_no_change(self):
        before = WorldMini.from_document(document("e1", "a1"))
        after = WorldMini.from_document(before.export())
        after.append_document(document("e2", "a2", known="2026-01-04T12:00:00Z"))
        report = source_delta_geojson(before, after)
        self.assertEqual(report["features"], [])
        self.assertEqual(report["monde_source_delta"]["assertions_added"], 1)
        self.assertEqual(report["monde_source_delta"]["status"], "NO_NEW_POINT_REPORTS")
        self.assertEqual(source_delta_geojson(after, after)["features"], [])

    def test_geojson_rejects_invalid_point_and_divergent_history(self):
        before = WorldMini()
        bad = document("e1", "a1",
                       value={"type": "Point", "coordinates": [190, 42]})
        bad["assertions"][0]["attribute"] = "geo_point"
        after = WorldMini.from_document(bad)
        with self.assertRaisesRegex(ValueError, "WGS84"):
            source_delta_geojson(before, after)
        with self.assertRaisesRegex(ValueError, "diverged"):
            source_delta_geojson(after, before)

    def test_cli_geojson_output_from_saved_states_without_file_mutation(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root)
            before = WorldMini()
            after = WorldMini()
            point = document("e1", "a1",
                             value={"type": "Point", "coordinates": [12.5, 41.9]})
            point["assertions"][0]["attribute"] = "geo_point"
            after.append_document(point)
            older, newer = p / "before.json", p / "after.json"
            before.save(older)
            after.save(newer)
            source_bytes = older.read_bytes(), newer.read_bytes()
            done = subprocess.run(
                [sys.executable, "-m", "monde.source_delta",
                 "--before", str(older), "--after", str(newer), "--as-geojson"],
                env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
                capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            geojson = json.loads(done.stdout)
            self.assertEqual(geojson["features"][0]["geometry"]["coordinates"],
                             [12.5, 41.9])
            self.assertEqual((older.read_bytes(), newer.read_bytes()), source_bytes)


    def test_csv_audits_original_and_corrected_values_without_inventing_truth(self):
        earlier = document("e1", "a1", value={"type": "Point", "coordinates": [2.3, 48.8]})
        earlier["assertions"][0]["attribute"] = "geo_point"
        before = WorldMini.from_document(earlier)
        after = WorldMini.from_document(before.export())
        corrected = document("e2", "a2", known="2026-01-03T12:00:00Z",
                             supersedes="a1",
                             value={"type": "Point", "coordinates": [2.4, 48.9]})
        corrected["assertions"][0]["attribute"] = "geo_point"
        corrected["evidence"][0]["locator"] = "=UNTRUSTED_EXTERNAL_FORMULA()"
        after.append_document(corrected)
        csv_body = source_delta_csv(before, after)
        rows = list(csv.DictReader(io.StringIO(csv_body)))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["world"], "OBSERVED")
        self.assertEqual(row["status"], "NEW_SOURCE_REPORT_ONLY")
        self.assertEqual(row["supersedes"], "a1")
        self.assertEqual(row["source_id"], "survey")
        self.assertEqual(json.loads(row["previous_value_json"]), earlier["assertions"][0]["value"])
        self.assertEqual(json.loads(row["reported_value_json"]), corrected["assertions"][0]["value"])
        self.assertEqual(json.loads(row["source_locator_json"]),
                         "=UNTRUSTED_EXTERNAL_FORMULA()")
        self.assertTrue(row["source_locator_json"].startswith('"'))
        self.assertEqual(row["known_at"], "2026-01-03T12:00:00Z")
        self.assertEqual(before.export()["assertions"][0]["value"],
                         {"type": "Point", "coordinates": [2.3, 48.8]})

    def test_csv_includes_nonspatial_reports_without_implying_reconciliation(self):
        before = WorldMini.from_document(document("e1", "a1", value="unchanged"))
        after = WorldMini.from_document(before.export())
        after.append_document(document("e2", "a2", known="2026-01-05T12:00:00Z",
                                       source="other", value={"claim": True}))
        rows = list(csv.DictReader(io.StringIO(source_delta_csv(before, after))))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["attribute"], "status")
        self.assertEqual(rows[0]["source_id"], "other")
        self.assertEqual(json.loads(rows[0]["reported_value_json"]), {"claim": True})
        self.assertEqual(rows[0]["previous_value_json"], "")
        header_only = source_delta_csv(after, WorldMini.from_document(after.export()))
        self.assertEqual(len(list(csv.reader(io.StringIO(header_only)))), 1)

    def test_cli_csv_produces_readonly_auditable_output_and_rejects_mixed_formats(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            old = WorldMini()
            new = WorldMini.from_document(document(
                "e1", "a1", value={"label": "reported"}))
            before_path, after_path = p / "before.json", p / "after.json"
            old.save(before_path)
            new.save(after_path)
            originals = (before_path.read_bytes(), after_path.read_bytes())
            args = [sys.executable, "-m", "monde.source_delta", "--before",
                    str(before_path), "--after", str(after_path)]
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            csv_result = subprocess.run([*args, "--as-csv"], env=env,
                                        capture_output=True, text=True)
            self.assertEqual(csv_result.returncode, 0, csv_result.stderr)
            rows = list(csv.DictReader(io.StringIO(csv_result.stdout)))
            self.assertEqual([row["assertion_id"] for row in rows], ["a1"])
            self.assertEqual(json.loads(rows[0]["reported_value_json"]),
                             {"label": "reported"})
            invalid = subprocess.run([*args, "--as-csv", "--as-geojson"], env=env,
                                     capture_output=True, text=True)
            self.assertNotEqual(invalid.returncode, 0)
            divergent = subprocess.run([
                sys.executable, "-m", "monde.source_delta", "--before",
                str(after_path), "--after", str(before_path), "--as-csv"
            ], env=env, capture_output=True, text=True)
            self.assertEqual(divergent.returncode, 2)
            self.assertFalse(divergent.stdout)
            self.assertEqual((before_path.read_bytes(), after_path.read_bytes()), originals)

    def test_real_geopackage_and_geojson_manifest_yield_per_source_delta(self):
        with tempfile.TemporaryDirectory() as root:
            manifest, _, _, _ = sample(root)
            paths, total = documents_from_manifest(manifest, output_path=Path(root) / "out.json")
            before = WorldMini()
            after = WorldMini()
            after.append_documents(paths)
            out = source_delta(before, after)
            self.assertEqual(out["added"]["evidence"], total)
            self.assertEqual(out["added"]["assertions"],
                             sum(len(doc["assertions"]) for doc in paths))
            self.assertEqual(out["added"]["corrections"], 0)
            self.assertEqual(len(out["sources"]), 4)
            self.assertEqual(sum(x["assertions_added"] for x in out["sources"]),
                             sum(len(doc["assertions"]) for doc in paths))
            self.assertEqual({x["source_id"] for x in out["sources"]},
                             {"survey:survey_points", "survey:survey_mixed",
                              "survey:survey_duplicate", "note"})


if __name__ == "__main__":
    unittest.main()
