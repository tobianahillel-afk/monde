"""Mixed original sources -> persistent, reusable bitemporal WorldMini."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from monde.world import WorldMini
from tests.test_world_map_source_manifest_layers import sample
from tests.test_world_geopackage import AT, CAP

ROOT = Path(__file__).resolve().parents[1]


def cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "monde.world", *map(str, args)],
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True, text=True,
    )


class PersistentSourceManifestTests(unittest.TestCase):
    def test_real_geopackage_and_geojson_become_queryable_saved_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            manifest, database, note, _ = sample(d)
            old_db, old_note = database.read_bytes(), note.read_bytes()
            state = Path(d) / "world.json"
            run = cli("--ingest-source-manifest", manifest, "--state-out", state)
            self.assertEqual(run.returncode, 0, run.stderr)
            report = json.loads(run.stdout)
            self.assertEqual((report["features"], report["batches"], report["status"]),
                             (35, 4, "SAVED"))
            self.assertEqual((database.read_bytes(), note.read_bytes()),
                             (old_db, old_note))
            world = WorldMini.read(state)
            self.assertEqual(len(world.export()["evidence"]), 35)
            data = world.export_geojson_bbox([-180, -90, 180, 90], AT, CAP)
            self.assertEqual(len(data["features"]), 35)
            self.assertEqual({f["properties"]["source_id"] for f in data["features"]},
                             {"survey:survey_points", "survey:survey_mixed",
                              "survey:survey_duplicate", "note"})
            query = cli("--fixture", state, "--export-geojson",
                        "--at", AT, "--known-at", CAP)
            self.assertEqual(query.returncode, 0, query.stderr)

    def test_saved_state_feeds_existing_standalone_offline_map(self):
        with tempfile.TemporaryDirectory() as d:
            manifest, _, _, _ = sample(d)
            state, page = Path(d) / "world.json", Path(d) / "map.html"
            self.assertEqual(cli("--ingest-source-manifest", manifest,
                                 "--state-out", state).returncode, 0)
            run = subprocess.run(
                [sys.executable, "-m", "monde.map_view", "--state", str(state),
                 "--at", AT, "--known-at", CAP, "--output", str(page)],
                env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
                capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn('"total_source_features":35', page.read_text(encoding="utf-8"))

    def test_invalid_last_source_fails_without_partial_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            manifest, _, note, _ = sample(d)
            note.write_text("{broken", encoding="utf-8")
            output = Path(d) / "world.json"
            self.assertNotEqual(cli("--ingest-source-manifest", manifest,
                                    "--state-out", output).returncode, 0)
            self.assertFalse(output.exists())

    def test_no_accidental_overwrite_even_after_failed_explicit_replace(self):
        with tempfile.TemporaryDirectory() as d:
            manifest, _, note, _ = sample(d)
            output = Path(d) / "world.json"
            self.assertEqual(cli("--ingest-source-manifest", manifest,
                                 "--state-out", output).returncode, 0)
            before = output.read_bytes()
            self.assertNotEqual(cli("--ingest-source-manifest", manifest,
                                    "--state-out", output).returncode, 0)
            note.write_text("{broken", encoding="utf-8")
            self.assertNotEqual(cli("--ingest-source-manifest", manifest,
                                    "--state-out", output,
                                    "--replace-state").returncode, 0)
            self.assertEqual(output.read_bytes(), before)

    def test_legacy_manifest_with_fixture_and_missing_fixture_for_query(self):
        with tempfile.TemporaryDirectory() as d:
            manifest, _, _, _ = sample(d)
            fixture, output = Path(d) / "seed.json", Path(d) / "world.json"
            WorldMini().save(fixture)
            run = cli("--fixture", fixture, "--ingest-csv-manifest", manifest,
                      "--state-out", output)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(len(WorldMini.read(output).export_geojson_bbox(\n                [-180, -90, 180, 90], AT, CAP)["features"]), 35)
            missing = cli("--export-geojson", "--at", AT, "--known-at", CAP)
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("--fixture", missing.stderr)

    def test_original_source_and_manifest_are_not_output_targets(self):
        with tempfile.TemporaryDirectory() as d:
            manifest, _, note, _ = sample(d)
            original = manifest.read_bytes(), note.read_bytes()
            for target in (manifest, note):
                self.assertNotEqual(cli("--ingest-source-manifest", manifest,
                                        "--state-out", target,
                                        "--replace-state").returncode, 0)
            self.assertEqual((manifest.read_bytes(), note.read_bytes()), original)


if __name__ == "__main__":
    unittest.main()
