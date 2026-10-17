"""Preview original source captures before accepting a durable world refresh."""
import json
from pathlib import Path
import tempfile
import unittest

from monde.csv_points import documents_from_manifest
from monde.source_refresh import preview_documents, refresh_documents
from monde.world import WorldMini
from tests.test_world_source_refresh import AT, K1, K2, csv_source, invoke


class SourcePreviewTests(unittest.TestCase):
    def test_cli_preview_before_save_returns_previous_and_reported_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, raw = csv_source(root)
            initial = root / "initial.json"
            self.assertEqual(invoke("--ingest-source-manifest", manifest,
                                    "--state-out", initial).returncode, 0)
            original = initial.read_bytes()
            csv_source(root, capture=K2, rows=[("site-a", 2.4, 48.9, "updated")])
            csv_before = raw.read_bytes()
            result = invoke("--fixture", initial, "--preview-source-manifest", manifest)
            self.assertEqual(result.returncode, 0, result.stderr)
            preview = json.loads(result.stdout)
            self.assertEqual(preview["status"], "PREVIEW_NOT_SAVED")
            self.assertEqual(preview["features"], 1)
            self.assertEqual(preview["source_report_revisions"], 2)
            self.assertEqual(preview["added_assertions"], 2)
            points = [row for row in preview["new_reports"]
                      if row["attribute"] == "geo_point"]
            self.assertEqual(len(points), 1)
            self.assertEqual(points[0]["previous_reported_value"]["coordinates"],
                             [2.3, 48.8])
            self.assertEqual(points[0]["reported_value"]["coordinates"], [2.4, 48.9])
            self.assertEqual(points[0]["source_id"], "survey")
            self.assertEqual(points[0]["source_locator"], "dataset://survey/points")
            self.assertEqual(points[0]["known_at"], K2)
            self.assertEqual(points[0]["status"], "SOURCE_REPORT_REVISION")
            self.assertEqual(initial.read_bytes(), original)
            self.assertEqual(raw.read_bytes(), csv_before)
            self.assertEqual(sorted(p.name for p in root.iterdir()),
                             ["initial.json", "manifest.json", "observations.csv"])
            saved = root / "new.json"
            self.assertEqual(invoke("--fixture", initial, "--refresh-source-manifest",
                                    manifest, "--state-out", saved).returncode, 0)
            self.assertEqual(WorldMini.read(saved).query("site-a", "label", AT, K2)
                             ["reports"][0]["value"], "updated")

    def test_identical_capture_previews_no_new_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest, _ = csv_source(directory)
            docs, _ = documents_from_manifest(
                manifest, output_path=Path(directory) / "output.json")
            world, _ = refresh_documents(WorldMini(), docs)
            initial = world.export()
            result = preview_documents(world, docs)
            self.assertEqual(result["status"], "PREVIEW_NOT_SAVED")
            self.assertEqual(result["new_reports"], [])
            self.assertEqual(result["added_assertions"], 0)
            self.assertEqual(result["added_evidence"], 0)
            self.assertEqual(result["replayed_assertions"], 2)
            self.assertEqual(world.export(), initial)

    def test_invalid_same_capture_rejects_without_state_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, raw = csv_source(root)
            old = root / "world.json"
            self.assertEqual(invoke("--ingest-source-manifest", manifest,
                                    "--state-out", old).returncode, 0)
            prior = old.read_bytes()
            csv_source(root, rows=[("site-a", 3, 48.9, "contradiction")])
            result = invoke("--fixture", old, "--preview-source-manifest", manifest)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("collision", result.stderr.lower())
            self.assertEqual(result.stdout, "")
            self.assertEqual(old.read_bytes(), prior)

    def test_preview_refuses_output_or_replace_options(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, _ = csv_source(root)
            state = root / "world.json"
            self.assertEqual(invoke("--ingest-source-manifest", manifest,
                                    "--state-out", state).returncode, 0)
            for extra in [("--state-out", root / "must-not-exist.json"),
                          ("--replace-state",)]:
                result = invoke("--fixture", state, "--preview-source-manifest",
                                manifest, *extra)
                self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root / "must-not-exist.json").exists())

    def test_preview_is_not_retraction_or_physical_truth(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest, _ = csv_source(directory, rows=[
                ("site-a", 2, 48, "old"), ("site-b", 3, 49, "still reported")])
            before, _ = documents_from_manifest(
                manifest, output_path=Path(directory) / "not-written.json")
            world, _ = refresh_documents(WorldMini(), before)
            csv_source(directory, capture=K2, rows=[
                ("site-a", 2.5, 48, "new")])
            newer, _ = documents_from_manifest(
                manifest, output_path=Path(directory) / "not-written.json")
            preview = preview_documents(world, newer)
            self.assertEqual({row["entity"] for row in preview["new_reports"]},
                             {"site-a"})
            self.assertEqual(world.query("site-b", "label", AT, K2)
                             ["reports"][0]["value"], "still reported")


if __name__ == "__main__":
    unittest.main()
