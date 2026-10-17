"""Real captured-source refresh: stable provenance, historical replay and CLI."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from monde.csv_points import documents_from_manifest
from monde.source_delta import source_delta, source_delta_geojson
from monde.source_refresh import refresh_documents
from monde.world import WorldMini

ROOT = Path(__file__).resolve().parents[1]
AT = "2026-01-01T12:00:00Z"
K1 = "2026-01-02T12:00:00Z"
K2 = "2026-01-03T12:00:00Z"


def csv_source(directory, *, capture=K1, rows=None, source="survey",
               locator="dataset://survey/points"):
    directory = Path(directory)
    path = directory / "observations.csv"
    rows = rows or [("site-a", 2.3, 48.8, "first")]
    path.write_text("id,longitude,latitude,label\n" +
                    "".join(f"{ident},{lon},{lat},{label}\n"
                            for ident, lon, lat, label in rows), encoding="utf-8")
    manifest = directory / "manifest.json"
    manifest.write_text(json.dumps({"datasets": [{
        "csv": path.name, "source_id": source, "locator": locator,
        "captured_at": capture, "valid_from": "2026-01-01T00:00:00Z",
        "source_event_at": "2026-01-01T00:00:00Z",
    }]}), encoding="utf-8")
    return manifest, path


def invoke(*args):
    return subprocess.run([sys.executable, "-m", "monde.world", *map(str, args)],
                          env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
                          capture_output=True, text=True)


class SourceRefreshTests(unittest.TestCase):
    def test_real_csv_capture_updates_stored_source_and_supports_bitemporal_query(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root)
            manifest, raw = csv_source(directory)
            first = directory / "snapshot-1.json"
            self.assertEqual(invoke("--ingest-source-manifest", manifest,
                                    "--state-out", first).returncode, 0)
            before_raw = first.read_bytes()
            csv_source(directory, capture=K2, rows=[("site-a", 2.4, 48.9, "updated")])
            second = directory / "snapshot-2.json"
            refreshed = invoke("--fixture", first, "--refresh-source-manifest",
                               manifest, "--state-out", second)
            self.assertEqual(refreshed.returncode, 0, refreshed.stderr)
            payload = json.loads(refreshed.stdout)
            self.assertEqual(payload["operation"], "REFRESH_SOURCE_MANIFEST")
            self.assertEqual(payload["source_report_revisions"], 2)
            self.assertEqual(payload["added_assertions"], 2)
            self.assertEqual(first.read_bytes(), before_raw)
            world = WorldMini.read(second)
            earlier = world.query("site-a", "geo_point", AT, K1)
            later = world.query("site-a", "geo_point", AT, K2)
            self.assertEqual(earlier["reports"][0]["value"]["coordinates"], [2.3, 48.8])
            self.assertEqual(later["reports"][0]["value"]["coordinates"], [2.4, 48.9])
            self.assertEqual(later["reports"][0]["supersedes"],
                             earlier["reports"][0]["assertion_id"])
            delta = source_delta(WorldMini.read(first), world)
            self.assertEqual(delta["added"]["corrections"], 2)
            features = source_delta_geojson(WorldMini.read(first), world)
            self.assertEqual(features["features"][0]["properties"]["source_id"], "survey")
            self.assertEqual(features["features"][0]["properties"]["captured_at"], K2)
            self.assertEqual(raw.read_text(encoding="utf-8").count("site-a"), 1)

    def test_replaying_same_capture_is_idempotent_and_preserves_history(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest, _ = csv_source(directory)
            batches, _ = documents_from_manifest(manifest, output_path=Path(directory)/"x.json")
            initial = WorldMini()
            updated, first = refresh_documents(initial, batches)
            self.assertEqual(first["added_assertions"], 2)
            again, result = refresh_documents(updated, batches)
            self.assertEqual(result["added_assertions"], 0)
            self.assertEqual(result["added_evidence"], 0)
            self.assertEqual(result["replayed_assertions"], 2)
            self.assertEqual(again.export(), updated.export())

    def test_missing_second_capture_row_does_not_infer_deletion(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest, _ = csv_source(directory, rows=[
                ("site-a", 2, 48, "active"), ("site-b", 3, 49, "active")])
            first_batches, _ = documents_from_manifest(
                manifest, output_path=Path(directory)/"one.json")
            first, _ = refresh_documents(WorldMini(), first_batches)
            csv_source(directory, capture=K2, rows=[("site-a", 2.5, 48, "new")])
            batches, _ = documents_from_manifest(
                manifest, output_path=Path(directory)/"two.json")
            newer, report = refresh_documents(first, batches)
            self.assertEqual(report["source_report_revisions"], 2)
            self.assertEqual(newer.query("site-b", "label", AT, K2)["reports"][0]["value"],
                             "active")
            self.assertEqual(len(newer.export()["assertions"]), 6)
            self.assertEqual(len(first.export()["assertions"]), 4)

    def test_same_source_different_original_locator_is_an_independent_report(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest, _ = csv_source(directory)
            one, _ = documents_from_manifest(manifest, output_path=Path(directory)/"a.json")
            initial, _ = refresh_documents(WorldMini(), one)
            csv_source(directory, capture=K2, locator="dataset://other-instrument",
                       rows=[("site-a", 3, 49, "independent")])
            two, _ = documents_from_manifest(manifest, output_path=Path(directory)/"b.json")
            updated, status = refresh_documents(initial, two)
            self.assertEqual(status["source_report_revisions"], 0)
            current = updated.query("site-a", "geo_point", AT, K2)["reports"]
            self.assertEqual(len(current), 2)
            self.assertEqual({x["locator"] for x in current},
                             {"dataset://survey/points", "dataset://other-instrument"})

    def test_same_capture_conflict_rejected_without_mutating_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest, _ = csv_source(directory)
            first, _ = documents_from_manifest(manifest, output_path=Path(directory)/"a.json")
            initial, _ = refresh_documents(WorldMini(), first)
            original = initial.export()
            csv_source(directory, rows=[("site-a", 3, 49, "contradiction")])
            clash, _ = documents_from_manifest(manifest, output_path=Path(directory)/"b.json")
            with self.assertRaisesRegex(ValueError, "collision"):
                refresh_documents(initial, clash)
            self.assertEqual(initial.export(), original)

    def test_later_capture_cannot_revise_to_earlier_known_time(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest, _ = csv_source(directory, capture=K2)
            first, _ = documents_from_manifest(manifest, output_path=Path(directory)/"a.json")
            original, _ = refresh_documents(WorldMini(), first)
            csv_source(directory, capture=K1, rows=[("site-a", 4, 50, "past")])
            older, _ = documents_from_manifest(manifest, output_path=Path(directory)/"b.json")
            with self.assertRaisesRegex(ValueError, "advance knowledge time"):
                refresh_documents(original, older)

    def test_cli_rejects_snapshot_overwrite_and_malformed_second_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            manifest, raw = csv_source(directory)
            original, second = base/"old.json", base/"new.json"
            self.assertEqual(invoke("--ingest-source-manifest", manifest,
                                    "--state-out", original).returncode, 0)
            old = original.read_bytes()
            self.assertNotEqual(invoke("--fixture", original, "--refresh-source-manifest",
                                       manifest, "--state-out", original,
                                       "--replace-state").returncode, 0)
            self.assertEqual(old, original.read_bytes())
            raw.write_text("id,longitude,latitude,label\nsite-a,not-a-number,1,bad\n",
                           encoding="utf-8")
            failed = invoke("--fixture", original, "--refresh-source-manifest",
                            manifest, "--state-out", second)
            self.assertNotEqual(failed.returncode, 0)
            self.assertFalse(second.exists())
            self.assertEqual(old, original.read_bytes())

    def test_repeat_cli_refresh_returns_no_changes_not_a_second_correction(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            manifest, _ = csv_source(directory)
            one, two, three = (base/n for n in ("a.json", "b.json", "c.json"))
            self.assertEqual(invoke("--ingest-source-manifest", manifest,
                                    "--state-out", one).returncode, 0)
            csv_source(directory, capture=K2, rows=[("site-a", 6, 44, "new")])
            self.assertEqual(invoke("--fixture", one, "--refresh-source-manifest",
                                    manifest, "--state-out", two).returncode, 0)
            result = invoke("--fixture", two, "--refresh-source-manifest",
                            manifest, "--state-out", three)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["added_assertions"], 0)
            self.assertEqual(WorldMini.read(three).export(), WorldMini.read(two).export())


    def test_real_mixed_geopackage_and_geojson_revisions_preserve_original_files(self):
        from tests.test_world_map_source_manifest_layers import sample
        from tests.test_world_geopackage import CAP as SOURCE_CAPTURE
        with tempfile.TemporaryDirectory() as directory:
            manifest, database, note, payload = sample(directory)
            original_database = database.read_bytes()
            before_batches, count = documents_from_manifest(
                manifest, output_path=Path(directory)/"before.json")
            self.assertEqual(count, 35)
            before, first = refresh_documents(WorldMini(), before_batches)
            self.assertGreater(first["added_assertions"], 35)
            original = before.export()
            newer_capture = "2026-02-01T10:00:00Z"
            for dataset in payload["datasets"]:
                dataset["captured_at"] = newer_capture
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            source_note = json.loads(note.read_text(encoding="utf-8"))
            source_note["features"][0]["geometry"]["coordinates"] = [5.1, 50.2]
            note.write_text(json.dumps(source_note), encoding="utf-8")
            after_batches, count = documents_from_manifest(
                manifest, output_path=Path(directory)/"after.json")
            after, change = refresh_documents(before, after_batches)
            self.assertEqual(count, 35)
            self.assertEqual(change["source_report_revisions"],
                             len(original["assertions"]))
            delta = source_delta(before, after)
            self.assertEqual(delta["added"]["corrections"],
                             len(original["assertions"]))
            self.assertEqual(before.export(), original)
            self.assertEqual(database.read_bytes(), original_database)
            older = after.query("local-note", "geo_point", AT, SOURCE_CAPTURE)
            current = after.query("local-note", "geo_point", AT, newer_capture)
            self.assertEqual(older["reports"][0]["value"]["coordinates"], [4.3, 50.1])
            self.assertEqual(current["reports"][0]["value"]["coordinates"], [5.1, 50.2])
            self.assertEqual(current["reports"][0]["source_id"], "note")



if __name__ == "__main__":
    unittest.main()
