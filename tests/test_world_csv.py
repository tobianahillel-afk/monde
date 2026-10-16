"""CSV-to-WorldMini source provenance and offline-map end-to-end tests."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from monde.csv_points import to_geojson
from monde.geojson import to_document
from monde.world import WorldMini

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/monde-mini.json"
CAPTURE = "2026-01-10T10:00:00Z"
VALID = "2026-01-01T00:00:00Z"
AT = "2026-01-02T00:00:00Z"
SOURCE = dict(source_id="csv-open-data", locator="fixture://csv/points",
              captured_at=CAPTURE, valid_from=VALID)


class CsvPointTests(unittest.TestCase):
    def make_csv(self, folder, rows, headers="id,longitude,latitude,label\n"):
        path = Path(folder) / "sample.csv"
        path.write_text(headers + rows, encoding="utf-8")
        return path

    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "monde.world", *args],
                              env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
                              capture_output=True, text=True)

    def test_world_claims_source_time_unknown_and_missing_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_csv(tmp, "place-001,2.3522,48.8566,Paris\n"
                                      "place-002,-73.9857,40.7484,\n")
            data = to_geojson(path)
            self.assertEqual(data["features"][1]["properties"], {})
            doc = to_document(data, **SOURCE)
            self.assertTrue(all(x["kind"] == "CLAIM" for x in doc["assertions"]))
            world = WorldMini.read(FIXTURE)
            self.assertEqual(world.append_document(doc)["added_evidence"], 2)
            r = world.query("place-001", "geo_point", AT, CAPTURE)
            self.assertEqual(r["status"], "REPORTED")
            self.assertEqual(r["reports"][0]["source_id"], "csv-open-data")
            self.assertEqual(r["reports"][0]["value"]["coordinates"],
                             [2.3522, 48.8566])
            self.assertEqual(world.query("place-002", "label", AT, CAPTURE)["status"],
                             "UNKNOWN")
            self.assertEqual(world.query("place-001", "geo_point", AT,
                             "2026-01-10T09:59:59Z")["status"], "UNKNOWN")

    def test_stable_reimport_and_distinct_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_csv(tmp, "place-001,2.3522,48.8566,Paris\n")
            doc = to_document(to_geojson(path), **SOURCE)
            world = WorldMini.read(FIXTURE)
            world.append_document(doc)
            self.assertEqual(world.append_document(copy.deepcopy(doc)),
                             {"added_evidence": 0, "added_assertions": 0})
            second = to_document(to_geojson(path), **{**SOURCE, "source_id": "source-2"})
            world.append_document(second)
            r = world.query("place-001", "geo_point", AT, CAPTURE)
            self.assertEqual({x["source_id"] for x in r["reports"]},
                             {"csv-open-data", "source-2"})

    def test_column_mapping_bom_quotes_and_string_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.csv"
            path.write_text("\ufeffuid,lon,lat,description\n"
                            '00021,180,90,"Comma, quote"\n', encoding="utf-8")
            feature = to_geojson(path, id_column="uid", lon_column="lon",
                                 lat_column="lat")["features"][0]
            self.assertEqual(feature["id"], "00021")
            self.assertEqual(feature["properties"]["description"], "Comma, quote")
            self.assertEqual(feature["geometry"]["coordinates"], [180, 90])

    def test_bad_csv_rejected_before_world_mutation(self):
        cases = [
            ("id,longitude,latitude\n", "p1,2,3\np1,4,5\n"),
            ("id,longitude,latitude\n", "p1,181,3\n"),
            ("id,longitude,latitude\n", "p1,NaN,3\n"),
            ("id,longitude,latitude\n", "p1,invalid,3\n"),
            ("id,longitude,latitude\n", "p1,2,3,extra\n"),
            ("id,longitude,latitude\n", "p1,2\n"),
            ("id,longitude,longitude\n", "p1,2,3\n"),
            ("id,longitude,latitude\n", ""),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            for header, rows in cases:
                with self.subTest(header=header, rows=rows):
                    path = self.make_csv(tmp, rows, headers=header)
                    with self.assertRaises(ValueError):
                        to_document(to_geojson(path), **SOURCE)
            path = self.make_csv(tmp, "p1,2,3\n", headers="id,longitude,latitude\n")
            with self.assertRaises(ValueError):
                to_geojson(path, lon_column="id")
            with self.assertRaises(ValueError):
                to_geojson(path, lon_column="missing")

    def test_real_cli_csv_to_saved_world_to_offline_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self.make_csv(tmp, "place-001,2.3522,48.8566,Paris\n")
            out = Path(tmp) / "world.json"
            args = ("--fixture", str(FIXTURE), "--ingest-csv", str(source),
                    "--source-id", "csv-open-data", "--source-locator",
                    "fixture://csv/points", "--captured-at", CAPTURE,
                    "--valid-from", VALID, "--state-out", str(out))
            proc = self.cli(*args)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["operation"], "IMPORT_CSV_POINTS")
            query = self.cli("--fixture", str(out), "--entity", "place-001",
                             "--attribute", "geo_point", "--at", AT,
                             "--known-at", CAPTURE)
            self.assertEqual(query.returncode, 0, query.stderr)
            self.assertEqual(json.loads(query.stdout)["reports"][0]["value"]
                             ["coordinates"], [2.3522, 48.8566])
            html = Path(tmp) / "map.html"
            rendered = subprocess.run(
                [sys.executable, "-m", "monde.map_view", "--state", str(out),
                 "--bbox", "2.34,48.84,2.36,48.87", "--at", AT,
                 "--known-at", CAPTURE, "--output", str(html)],
                env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
                capture_output=True, text=True)
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            content = html.read_text(encoding="utf-8")
            self.assertIn("csv-open-data", content)
            self.assertIn("place-001", content)
            self.assertNotEqual(self.cli(*args).returncode, 0)

    def test_invalid_import_never_overwrites_snapshot_or_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self.make_csv(tmp, "ok,2,3,yes\nbad,181,3,no\n")
            out = Path(tmp) / "world.json"
            out.write_text("unchanged\n", encoding="utf-8")
            args = ("--fixture", str(FIXTURE), "--ingest-csv", str(source),
                    "--source-id", "csv", "--source-locator", "fixture://csv",
                    "--captured-at", CAPTURE, "--valid-from", VALID,
                    "--state-out", str(out), "--replace-state")
            result = self.cli(*args)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(out.read_text(encoding="utf-8"), "unchanged\n")
            result = self.cli(*args[:-3], "--state-out", str(source), "--replace-state")
            self.assertNotEqual(result.returncode, 0)

    def test_metadata_and_column_options_never_apply_to_queries(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self.make_csv(tmp, "p1,2,3,p\n")
            args = ["--fixture", str(FIXTURE), "--ingest-csv", str(source),
                    "--source-id", "csv", "--source-locator", "fixture://csv",
                    "--captured-at", CAPTURE, "--valid-from", VALID,
                    "--state-out", str(Path(tmp) / "out.json")]
            args.remove("--captured-at")
            args.remove(CAPTURE)
            self.assertNotEqual(self.cli(*args).returncode, 0)
            self.assertNotEqual(self.cli("--fixture", str(FIXTURE),
                "--entity", "place-001", "--attribute", "geo_point",
                "--at", AT, "--known-at", CAPTURE,
                "--csv-id-column", "id").returncode, 0)
