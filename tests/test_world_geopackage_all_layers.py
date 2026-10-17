"""One-command all-layer GeoPackage -> bitemporal WorldMini offline evidence."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from monde.geopackage_points import list_layers, documents_for_layers
from monde.world import WorldMini
from tests.test_world_geopackage import AT, CAP, build, point
from tests.test_world_geopackage_mixed import mixed_db


def make_source(path):
    mixed_db(build(path))
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE survey_duplicate (
                fid INTEGER PRIMARY KEY, geom BLOB NOT NULL, name TEXT);
            INSERT INTO gpkg_contents VALUES
                ('survey_duplicate','features','Other source layer',4326);
            INSERT INTO gpkg_geometry_columns VALUES
                ('survey_duplicate','geom','POINT',4326,0,0);
        """)
        db.execute("INSERT INTO survey_duplicate VALUES (1,?,?)",
                   (point(4.3, 50.1), "Same FID, different source"))
    return path


class AllGeoPackageLayersTests(unittest.TestCase):
    def direct(self, path):
        return ("--gpkg", path, "--gpkg-all-layers",
                "--source-id", "original-survey",
                "--source-locator", "dataset://survey/source.gpkg",
                "--captured-at", CAP, "--valid-from", "2026-01-01T00:00:00Z",
                "--at", AT, "--known-at", CAP)

    def cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "monde.map_view", *map(str, args)],
            text=True, capture_output=True,
            env={**os.environ,
                 "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")})

    def test_layers_are_sorted_and_source_ids_do_not_conflate_equal_fids(self):
        with tempfile.TemporaryDirectory() as d:
            source = make_source(Path(d) / "real.gpkg")
            before = source.read_bytes()
            self.assertEqual(list_layers(source),
                             ["survey_duplicate", "survey_mixed", "survey_points"])
            docs = documents_for_layers(
                source, source_id="survey", locator="dataset://original",
                captured_at=CAP, valid_from="2026-01-01T00:00:00Z")
            self.assertEqual(len(docs), 3)
            world = WorldMini()
            world.append_documents(docs)
            geo = world.export_geojson_bbox([-180, -90, 180, 90], AT, CAP)
            self.assertEqual(len(geo["features"]), 34)
            # Multipart members still carry their original SQLite row FIDs.
            mixed = [f for f in geo["features"] if
                     f["properties"].get("monde_gpkg_source_layer") == "survey_mixed"]
            self.assertEqual({f["properties"]["monde_gpkg_source_fid"]
                              for f in mixed}, {"11", "12", "13", "14", "15", "16"})
            ids = [f["properties"]["entity"] for f in geo["features"]]
            self.assertEqual(len(ids), len(set(ids)))
            distinct = [f for f in geo["features"]
                        if f["properties"].get("monde_gpkg_source_fid") == "1"]
            self.assertEqual(len(distinct), 2)
            self.assertEqual({f["properties"]["monde_gpkg_source_layer"] for f in distinct},
                             {"survey_duplicate", "survey_points"})
            self.assertEqual({f["properties"]["source_id"] for f in distinct},
                             {"survey:survey_duplicate", "survey:survey_points"})
            self.assertEqual(source.read_bytes(), before)

    def test_real_cli_one_command_produces_single_offline_map(self):
        with tempfile.TemporaryDirectory() as d:
            source = make_source(Path(d) / "survey.gpkg")
            out = Path(d) / "map.html"
            result = self.cli(*self.direct(source), "--output", out)
            self.assertEqual(result.returncode, 0, result.stderr)
            page = out.read_text(encoding="utf-8")
            self.assertIn('"total_source_features":34', page)
            self.assertIn("survey:survey_mixed", page)
            self.assertIn("survey:survey_points", page)
            self.assertIn("survey:survey_duplicate", page)
            self.assertIn("GPKG_1_3_MULTIPOLYGON_RING_POINT", page)
            self.assertIn("monde_gpkg_source_layer", page)
            self.assertNotIn("https://tile.", page)

    def test_invalid_layer_blocks_entire_output_atomically(self):
        with tempfile.TemporaryDirectory() as d:
            source = make_source(Path(d) / "survey.gpkg")
            with sqlite3.connect(source) as db:
                db.execute("UPDATE gpkg_geometry_columns SET z=1 "
                           "WHERE table_name='survey_mixed'")
            result = self.cli(*self.direct(source), "--output", Path(d) / "bad.html")
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((Path(d) / "bad.html").exists())

    def test_layer_flags_are_unambiguous(self):
        with tempfile.TemporaryDirectory() as d:
            path = make_source(Path(d) / "survey.gpkg")
            args = self.direct(path)
            for flags in [("--gpkg-layer", "survey_points"), ("--state", "other")]:
                output = Path(d) / ("bad-" + str(len(flags)) + ".html")
                result = self.cli(*args, *flags, "--output", output)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output.exists())
            output = Path(d) / "missing-layer.html"
            simple = [x for x in args if x != "--gpkg-all-layers"]
            result = self.cli(*simple, "--output", output)
            self.assertNotEqual(result.returncode, 0)

    def test_feature_layer_limit_is_bounded_not_silently_truncated(self):
        with tempfile.TemporaryDirectory() as d:
            source = make_source(Path(d) / "survey.gpkg")
            with sqlite3.connect(source) as db:
                for i in range(16):
                    db.execute("INSERT INTO gpkg_contents VALUES (?,?,?,?)",
                               ("extra_%02d" % i, "features", "Layer", 4326))
            with self.assertRaises(ValueError):
                list_layers(source)

    def test_provenance_field_collision_rejected_before_html(self):
        with tempfile.TemporaryDirectory() as d:
            source = make_source(Path(d) / "survey.gpkg")
            with sqlite3.connect(source) as db:
                db.execute("ALTER TABLE survey_duplicate ADD COLUMN gpkg_source_fid TEXT")
                db.execute("UPDATE survey_duplicate SET gpkg_source_fid='source-defined'")
            output = Path(d) / "bad.html"
            result = self.cli(*self.direct(source), "--output", output)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
