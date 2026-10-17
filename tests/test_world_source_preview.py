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

    def test_preview_source_map_creates_offline_new_point_map_without_saving(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, raw = csv_source(root)
            state = root / "old.json"
            self.assertEqual(invoke("--ingest-source-manifest", manifest,
                                    "--state-out", state).returncode, 0)
            old_bytes = state.read_bytes()
            csv_source(root, capture=K2, rows=[("site-a", 2.4, 48.9, "updated")])
            raw_bytes = raw.read_bytes()
            map_path = root / "preview.html"
            result = invoke("--fixture", state, "--preview-source-manifest",
                            manifest, "--preview-source-map", map_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            self.assertEqual(summary["status"], "PREVIEW_NOT_SAVED")
            self.assertEqual(summary["preview_map_html"], str(map_path))
            self.assertEqual(summary["source_report_revisions"], 2)
            page = map_path.read_text(encoding="utf-8")
            self.assertIn("data-monde-ready", page)
            self.assertIn("site-a", page)
            self.assertIn("NEW_SOURCE_REPORT_ONLY", page)
            self.assertIn("survey", page)
            self.assertIn("dataset://survey/points", page)
            self.assertEqual(state.read_bytes(), old_bytes)
            self.assertEqual(raw.read_bytes(), raw_bytes)

    def test_preview_source_map_rejects_overwrite_and_invalid_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, raw = csv_source(root)
            state = root / "old.json"
            self.assertEqual(invoke("--ingest-source-manifest", manifest,
                                    "--state-out", state).returncode, 0)
            state_before = state.read_bytes()
            for out in (state, manifest, raw):
                original = Path(out).read_bytes()
                result = invoke("--fixture", state, "--preview-source-manifest",
                                manifest, "--preview-source-map", out)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(Path(out).read_bytes(), original)
            no_map = root / "never-created.html"
            csv_source(root, rows=[("site-a", 2.7, 49.2, "collision")])
            invalid = invoke("--fixture", state, "--preview-source-manifest",
                             manifest, "--preview-source-map", no_map)
            self.assertNotEqual(invalid.returncode, 0)
            self.assertFalse(no_map.exists())
            self.assertEqual(state.read_bytes(), state_before)

    def test_preview_source_map_requires_preview_mode_and_is_create_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, _ = csv_source(root)
            state = root / "old.json"
            self.assertEqual(invoke("--ingest-source-manifest", manifest,
                                    "--state-out", state).returncode, 0)
            map_path = root / "preview.html"
            wrong_mode = invoke("--fixture", state, "--all-attributes",
                                "--preview-source-map", map_path)
            self.assertNotEqual(wrong_mode.returncode, 0)
            self.assertFalse(map_path.exists())
            first = invoke("--fixture", state, "--preview-source-manifest",
                           manifest, "--preview-source-map", map_path)
            self.assertEqual(first.returncode, 0, first.stderr)
            original = map_path.read_bytes()
            duplicate = invoke("--fixture", state, "--preview-source-manifest",
                               manifest, "--preview-source-map", map_path)
            self.assertNotEqual(duplicate.returncode, 0)
            self.assertEqual(map_path.read_bytes(), original)

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


    def test_confirmed_preview_saves_only_the_inspected_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, raw = csv_source(root)
            old = root / "old.json"
            self.assertEqual(invoke("--ingest-source-manifest", manifest,
                                    "--state-out", old).returncode, 0)
            old_bytes = old.read_bytes()
            csv_source(root, capture=K2, rows=[("site-a", 3.2, 49.3, "updated")])
            original_source = raw.read_bytes()
            preview_run = invoke("--fixture", old, "--preview-source-manifest", manifest)
            self.assertEqual(preview_run.returncode, 0, preview_run.stderr)
            inspected = json.loads(preview_run.stdout)
            digest = inspected["preview_sha256"]
            self.assertRegex(digest, r"^[0-9a-f]{64}$")
            target = root / "reviewed.json"
            saved = invoke("--fixture", old, "--refresh-source-manifest", manifest,
                           "--expect-preview-sha256", digest,
                           "--state-out", target)
            self.assertEqual(saved.returncode, 0, saved.stderr)
            self.assertEqual(json.loads(saved.stdout)["preview_sha256"], digest)
            self.assertEqual(WorldMini.read(target).query("site-a", "label", AT, K2)
                             ["reports"][0]["value"], "updated")
            self.assertEqual(old.read_bytes(), old_bytes)
            self.assertEqual(raw.read_bytes(), original_source)

    def test_stale_preview_cannot_save_modified_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, _ = csv_source(root)
            old = root / "old.json"
            self.assertEqual(invoke("--ingest-source-manifest", manifest,
                                    "--state-out", old).returncode, 0)
            old_bytes = old.read_bytes()
            csv_source(root, capture=K2, rows=[("site-a", 2.5, 48.9, "inspected")])
            preview = json.loads(invoke("--fixture", old,
                "--preview-source-manifest", manifest).stdout)
            csv_source(root, capture="2026-01-04T12:00:00Z",
                       rows=[("site-a", 5.1, 50.2, "later")])
            target = root / "not-saved.json"
            denied = invoke("--fixture", old, "--refresh-source-manifest", manifest,
                            "--expect-preview-sha256", preview["preview_sha256"],
                            "--state-out", target)
            self.assertNotEqual(denied.returncode, 0)
            self.assertIn("preview no longer matches", denied.stderr)
            self.assertFalse(target.exists())
            self.assertEqual(old.read_bytes(), old_bytes)

    def test_baseline_drift_and_invalid_preview_digest_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, _ = csv_source(root)
            old = root / "old.json"
            self.assertEqual(invoke("--ingest-source-manifest", manifest,
                                    "--state-out", old).returncode, 0)
            csv_source(root, capture=K2, rows=[("site-a", 2.7, 49, "revised")])
            preview = json.loads(invoke("--fixture", old,
                "--preview-source-manifest", manifest).stdout)
            new_base = root / "second.json"
            self.assertEqual(invoke("--fixture", old, "--refresh-source-manifest",
                                    manifest, "--state-out", new_base).returncode, 0)
            target = root / "refused.json"
            mismatch = invoke("--fixture", new_base, "--refresh-source-manifest",
                              manifest, "--state-out", target,
                              "--expect-preview-sha256", preview["preview_sha256"])
            self.assertNotEqual(mismatch.returncode, 0)
            self.assertFalse(target.exists())
            for malformed in ("", "a" * 63, "A" * 64, "z" * 64):
                bad = invoke("--fixture", old, "--refresh-source-manifest", manifest,
                             "--state-out", target, "--expect-preview-sha256", malformed)
                self.assertNotEqual(bad.returncode, 0)
                self.assertFalse(target.exists())
            wrong_mode = invoke("--fixture", old, "--preview-source-manifest",
                                manifest, "--expect-preview-sha256", "a" * 64)
            self.assertNotEqual(wrong_mode.returncode, 0)


if __name__ == "__main__":
    unittest.main()
