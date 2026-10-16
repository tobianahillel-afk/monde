"""Real WorldMini CLI to spreadsheet CSV integration tests."""
import csv
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = "2026-01-10T10:00:00Z"
LATER = "2026-01-11T10:00:00Z"
AT = "2026-01-02T00:00:00Z"
START = "2026-01-01T00:00:00Z"


class SourceCsvExportTests(unittest.TestCase):
    def command(self, *arguments):
        return subprocess.run(
            [sys.executable, "-m", "monde.world", *arguments],
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            capture_output=True, text=True)

    def test_multi_source_import_export_preserves_bitemporal_disagreement(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "a.csv").write_text(
                "id,longitude,latitude\nshared,2.35,48.85\n", encoding="utf-8")
            (root / "b.csv").write_text(
                "id,longitude,latitude\nshared,2.40,48.86\n", encoding="utf-8")
            manifest = root / "sources.json"
            manifest.write_text(json.dumps({"datasets": [
                {"csv": "a.csv", "source_id": "survey-a", "locator": "dataset://a",
                 "captured_at": CAPTURE, "valid_from": START},
                {"csv": "b.csv", "source_id": "survey-b", "locator": "dataset://b",
                 "captured_at": LATER, "valid_from": START}]}), encoding="utf-8")
            stored = root / "state.json"
            ingested = self.command("--fixture", str(ROOT / "examples/monde-mini.json"),
                "--ingest-csv-manifest", str(manifest), "--state-out", str(stored))
            self.assertEqual(ingested.returncode, 0, ingested.stderr)
            args = ("--fixture", str(stored), "--export-csv", "--at", AT, "--known-at")
            early = self.command(*args, CAPTURE)
            self.assertEqual(early.returncode, 0, early.stderr)
            early_rows = list(csv.DictReader(io.StringIO(early.stdout)))
            self.assertEqual([row["source_id"] for row in early_rows], ["survey-a"])
            later = self.command(*args, LATER)
            self.assertEqual(later.returncode, 0, later.stderr)
            rows = list(csv.DictReader(io.StringIO(later.stdout)))
            self.assertEqual(len(rows), 2)
            self.assertEqual({r["source_id"] for r in rows}, {"survey-a", "survey-b"})
            self.assertEqual({r["longitude"] for r in rows}, {"2.35", "2.4"})
            self.assertEqual(len({r["evidence_id"] for r in rows}), 2)
            self.assertEqual({r["monde_status"] for r in rows},
                             {"SOURCE_REPORTED_ONLY"})
            self.assertEqual({r["valid_at"] for r in rows}, {AT})
            self.assertEqual({r["kind"] for r in rows}, {"CLAIM"})
            bbox = self.command("--fixture", str(stored), "--export-csv",
                "--export-bbox", "2.34,48.84,2.36,48.86",
                "--at", AT, "--known-at", LATER)
            self.assertEqual(bbox.returncode, 0, bbox.stderr)
            self.assertEqual(len(list(csv.DictReader(io.StringIO(bbox.stdout)))), 1)
            geojson = self.command("--fixture", str(stored), "--export-geojson",
                "--at", AT, "--known-at", LATER)
            self.assertEqual(len(json.loads(geojson.stdout)["features"]), 2)

    def test_untrusted_locator_cannot_be_spreadsheet_formula(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            csv_path = root / "one.csv"
            csv_path.write_text("id,longitude,latitude\np1,2.35,48.85\n", encoding="utf-8")
            stored = root / "state.json"
            loaded = self.command("--fixture", str(ROOT / "examples/monde-mini.json"),
                "--ingest-csv", str(csv_path), "--source-id", "survey",
                "--source-locator", '  =HYPERLINK("target")',
                "--captured-at", CAPTURE, "--valid-from", START,
                "--state-out", str(stored))
            self.assertEqual(loaded.returncode, 0, loaded.stderr)
            output = self.command("--fixture", str(stored),
                "--export-csv", "--at", AT, "--known-at", CAPTURE)
            self.assertEqual(output.returncode, 0, output.stderr)
            row = next(csv.DictReader(io.StringIO(output.stdout)))
            self.assertTrue(row["locator"].startswith("'  =HYPERLINK"))
            self.assertEqual(row["latitude"], "48.85")

    def test_absent_reports_have_header_and_no_fabricated_rows(self):
        result = self.command("--fixture", str(ROOT / "examples/monde-mini.json"),
            "--export-csv", "--at", AT, "--known-at", "2020-01-01T00:00:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(list(csv.DictReader(io.StringIO(result.stdout)))), 0)
        self.assertIn("evidence_id", result.stdout.splitlines()[0])

    def test_invalid_or_mixed_query_flags_fail(self):
        original = ("--fixture", str(ROOT / "examples/monde-mini.json"),
                    "--export-csv")
        options = [
            (*original, "--at", AT),
            (*original, "--known-at", CAPTURE),
            (*original, "--at", AT, "--known-at", CAPTURE, "--entity", "p1"),
            (*original, "--at", AT, "--known-at", CAPTURE,
             "--export-bbox", "broken"),
            (*original, "--at", AT, "--known-at", CAPTURE,
             "--compare-at", START),
        ]
        for params in options:
            with self.subTest(flags=params):
                self.assertNotEqual(self.command(*params).returncode, 0)
