"""End-to-end CSV manifest -> evidence WorldMini -> standalone offline map."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
AT = "2026-01-02T00:00:00Z"
KNOWN = "2026-01-11T10:00:00Z"


class DirectCsvMapTests(unittest.TestCase):
    def run_map(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "monde.map_view", *map(str, args)],
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            capture_output=True, text=True,
        )

    @staticmethod
    def fixtures(folder):
        folder = Path(folder)
        (folder / "one.csv").write_text(
            "id,longitude,latitude,label\nshared,2.35,48.85,first\n",
            encoding="utf-8",
        )
        (folder / "two.csv").write_text(
            "id,longitude,latitude,label\nshared,2.40,48.86,second\n",
            encoding="utf-8",
        )
        manifest = folder / "sources.json"
        manifest.write_text(json.dumps({"datasets": [
            {"csv": "one.csv", "source_id": "survey-a",
             "locator": "dataset://one", "captured_at": "2026-01-10T10:00:00Z",
             "valid_from": "2026-01-01T00:00:00Z"},
            {"csv": "two.csv", "source_id": "survey-b",
             "locator": "dataset://two", "captured_at": KNOWN,
             "valid_from": "2026-01-01T00:00:00Z"}
        ]}), encoding="utf-8")
        return manifest

    def test_direct_sources_keep_both_conflicting_claims_and_do_not_save_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self.fixtures(tmp)
            target = Path(tmp) / "evidence.html"
            run = self.run_map("--csv-manifest", manifest,
                "--bbox", "2.34,48.84,2.41,48.87",
                "--at", AT, "--known-at", KNOWN, "--output", target)
            self.assertEqual(run.returncode, 0, run.stderr)
            html = target.read_text(encoding="utf-8")
            for expected in ("survey-a", "survey-b", "dataset://one",
                             "dataset://two", "SOURCE_REPORTED", "shared",
                             'id="export-visible-csv"'):
                self.assertIn(expected, html)
            self.assertIn('data-monde-ready', html)
            self.assertFalse((Path(tmp) / "state.json").exists())
            self.assertEqual(len(list(Path(tmp).glob("*.html"))), 1)

    def test_valid_at_and_knowledge_cutoff_do_not_invent_late_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self.fixtures(tmp)
            target = Path(tmp) / "early.html"
            run = self.run_map("--csv-manifest", manifest,
                "--bbox", "2.34,48.84,2.41,48.87",
                "--at", AT, "--known-at", "2026-01-10T10:00:00Z",
                "--output", target)
            self.assertEqual(run.returncode, 0, run.stderr)
            html = target.read_text(encoding="utf-8")
            self.assertIn("survey-a", html)
            self.assertNotIn("survey-b", html)

    def test_comparison_reuses_existing_bitemporal_map(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self.fixtures(tmp)
            target = Path(tmp) / "changes.html"
            run = self.run_map("--csv-manifest", manifest,
                "--bbox", "2.34,48.84,2.41,48.87",
                "--at", AT,
                "--compare-known-at", "2026-01-10T10:00:00Z",
                "--known-at", KNOWN, "--output", target)
            self.assertEqual(run.returncode, 0, run.stderr)
            html = target.read_text(encoding="utf-8")
            self.assertIn("NEWLY_CURRENT", html)
            self.assertIn("survey-b", html)

    def test_invalid_late_csv_aborts_without_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self.fixtures(tmp)
            (Path(tmp) / "two.csv").write_text(
                "id,longitude,latitude\nshared,not-a-number,48.86\n",
                encoding="utf-8",
            )
            output = Path(tmp) / "never.html"
            run = self.run_map("--csv-manifest", manifest, "--bbox",
                "-180,-90,180,90", "--at", AT, "--known-at", KNOWN,
                "--output", output)
            self.assertNotEqual(run.returncode, 0)
            self.assertFalse(output.exists())

    def test_no_overwrite_of_manifest_sources_or_existing_map(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self.fixtures(tmp)
            common = ("--csv-manifest", manifest, "--bbox", "-180,-90,180,90",
                      "--at", AT, "--known-at", KNOWN)
            original = manifest.read_bytes()
            result = self.run_map(*common, "--output", manifest)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(manifest.read_bytes(), original)
            csvfile = Path(tmp) / "one.csv"
            original_csv = csvfile.read_bytes()
            self.assertNotEqual(
                self.run_map(*common, "--output", csvfile).returncode, 0)
            self.assertEqual(csvfile.read_bytes(), original_csv)
            output = Path(tmp) / "existing.html"
            output.write_text("PRESERVE", encoding="utf-8")
            self.assertNotEqual(
                self.run_map(*common, "--output", output).returncode, 0)
            self.assertEqual(output.read_text(), "PRESERVE")

    def test_mutually_exclusive_source_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self.fixtures(tmp)
            output = Path(tmp) / "never.html"
            base = ("--bbox", "-180,-90,180,90", "--at", AT,
                    "--known-at", KNOWN, "--output", output)
            self.assertNotEqual(self.run_map(*base).returncode, 0)
            self.assertNotEqual(
                self.run_map("--state", "any.json", "--csv-manifest",
                             manifest, *base).returncode, 0)
            self.assertFalse(output.exists())


    def test_default_auto_bbox_fits_csv_claims_without_manual_coordinates(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self.fixtures(tmp)
            output = Path(tmp) / "automatic.html"
            result = self.run_map("--csv-manifest", manifest, "--at", AT,
                                  "--known-at", KNOWN, "--output", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            html = output.read_text(encoding="utf-8")
            self.assertIn("survey-a", html)
            self.assertIn("survey-b", html)
            self.assertIn('"total_source_features":2', html)
            self.assertIn('"bbox":[', html)

    def test_auto_bbox_uses_short_dateline_arc_and_keeps_both_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self.fixtures(tmp)
            (Path(tmp) / "one.csv").write_text(
                "id,longitude,latitude,label\nshared,179.8,5,first\n",
                encoding="utf-8")
            (Path(tmp) / "two.csv").write_text(
                "id,longitude,latitude,label\nshared,-179.8,5,second\n",
                encoding="utf-8")
            output = Path(tmp) / "dateline.html"
            result = self.run_map("--csv-manifest", manifest, "--at", AT,
                                  "--known-at", KNOWN, "--output", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            import re
            bounds = json.loads("[" + re.search(
                r'"bbox":\[([^\]]+)\]', output.read_text(encoding="utf-8")
            ).group(1) + "]")
            self.assertGreater(bounds[0], bounds[2])  # wrapped W > E
            self.assertGreater(bounds[0], 170)
            self.assertLess(bounds[2], -170)
            self.assertTrue(-90 <= bounds[1] <= 5 <= bounds[3] <= 90)

    def test_auto_bbox_comparison_includes_source_only_present_at_early_cutoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self.fixtures(tmp)
            output = Path(tmp) / "comparison.html"
            result = self.run_map("--csv-manifest", manifest, "--at", AT,
                "--compare-known-at", "2026-01-10T10:00:00Z",
                "--known-at", KNOWN, "--output", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            html = output.read_text(encoding="utf-8")
            self.assertIn("survey-b", html)
            self.assertIn("NEWLY_CURRENT", html)

    def test_auto_bbox_empty_history_fails_cleanly_but_explicit_bbox_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self.fixtures(tmp)
            missing = Path(tmp) / "missing.html"
            args = ("--csv-manifest", manifest, "--at", AT,
                    "--known-at", "2026-01-01T00:00:00Z", "--output", missing)
            result = self.run_map(*args)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("no known source Points", result.stderr)
            self.assertFalse(missing.exists())
            explicit = Path(tmp) / "empty.html"
            result = self.run_map("--csv-manifest", manifest, "--at", AT,
                "--known-at", "2026-01-01T00:00:00Z", "--bbox",
                "-180,-90,180,90", "--output", explicit)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"total_source_features":0',
                          explicit.read_text(encoding="utf-8"))

    def test_auto_bbox_world_time_comparison_uses_both_world_cutoffs(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self.fixtures(tmp)
            early = "2025-12-31T00:00:00Z"
            output = Path(tmp) / "world-time.html"
            result = self.run_map("--csv-manifest", manifest,
                "--compare-at", early, "--at", AT,
                "--known-at", KNOWN, "--output", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("NEWLY_CURRENT", output.read_text(encoding="utf-8"))

    def test_auto_bbox_nonfinite_or_invalid_csv_still_refuses_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self.fixtures(tmp)
            (Path(tmp) / "two.csv").write_text(
                "id,longitude,latitude,label\nshared,NaN,48.86,second\n",
                encoding="utf-8")
            output = Path(tmp) / "invalid.html"
            result = self.run_map("--csv-manifest", manifest, "--at", AT,
                                  "--known-at", KNOWN, "--output", output)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
