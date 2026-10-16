"""Real one-command GeoJSON source -> standalone offline evidence map."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

AT = "2026-01-02T00:00:00Z"
KNOWN = "2026-01-10T10:00:00Z"


class DirectGeoJSONMapTests(unittest.TestCase):
    def run_map(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "monde.map_view", *map(str, args)],
            capture_output=True, text=True, env={
                **os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")
            },
        )

    def fixture(self, root):
        path = Path(root) / "original.geojson"
        path.write_text(json.dumps({
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "id": "shared", "geometry": {
                    "type": "Point", "coordinates": [2.3522, 48.8566]
                }, "properties": {"name": "source report"}},
                {"type": "Feature", "id": "other", "geometry": {
                    "type": "Point", "coordinates": [-73.9857, 40.7484]
                }, "properties": {"name": "another report"}},
            ],
        }), encoding="utf-8")
        return path

    def flags(self, path):
        return ("--geojson", path, "--source-id", "survey-original",
                "--source-locator", "dataset://original.geojson",
                "--captured-at", KNOWN, "--valid-from", "2026-01-01T00:00:00Z")

    def test_direct_geojson_renders_both_original_reports_without_state(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.fixture(folder)
            output = Path(folder) / "map.html"
            result = self.run_map(*self.flags(path), "--at", AT,
                                  "--known-at", KNOWN, "--output", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            page = output.read_text(encoding="utf-8")
            for token in ('"total_source_features":2', "survey-original",
                          "dataset://original.geojson", "shared", "other",
                          "SOURCE_REPORTED", 'id="export-visible-csv"'):
                self.assertIn(token, page)
            self.assertFalse((Path(folder) / "state.json").exists())

    def test_world_time_change_and_early_knowledge_cutoff(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.fixture(folder)
            output = Path(folder) / "changes.html"
            result = self.run_map(*self.flags(path),
                                  "--compare-at", "2025-12-31T00:00:00Z",
                                  "--at", AT, "--known-at", KNOWN,
                                  "--output", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("NEWLY_CURRENT", output.read_text(encoding="utf-8"))
            empty = Path(folder) / "empty.html"
            result = self.run_map(*self.flags(path),
                                  "--bbox=-180,-90,180,90", "--at", AT,
                                  "--known-at", "2026-01-01T00:00:00Z",
                                  "--output", empty)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"total_source_features":0',
                          empty.read_text(encoding="utf-8"))

    def test_invalid_geometry_and_duplicate_json_fields_fail_without_output(self):
        with tempfile.TemporaryDirectory() as folder:
            source = self.fixture(folder)
            output = Path(folder) / "never.html"
            invalid = json.loads(source.read_text(encoding="utf-8"))
            invalid["features"][0]["geometry"] = {
                "type": "LineString", "coordinates": [[2.35, 48.85], [2.36, 48.86]]
            }
            source.write_text(json.dumps(invalid), encoding="utf-8")
            result = self.run_map(*self.flags(source), "--at", AT,
                                  "--known-at", KNOWN, "--output", output)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())
            source.write_text('{"type":"FeatureCollection","type":"FeatureCollection","features":[]}',
                              encoding="utf-8")
            result = self.run_map(*self.flags(source), "--at", AT,
                                  "--known-at", KNOWN, "--output", output)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())

    def test_provenance_is_required_and_not_accepted_on_other_input_modes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.fixture(folder)
            output = Path(folder) / "never.html"
            base = ("--at", AT, "--known-at", KNOWN, "--output", output)
            self.assertNotEqual(self.run_map("--geojson", path, *base).returncode, 0)
            self.assertNotEqual(self.run_map("--geojson", path,
                "--captured-at", KNOWN, *base).returncode, 0)
            self.assertNotEqual(self.run_map("--state", "does-not-matter.json",
                "--source-id", "forbidden", *base).returncode, 0)
            self.assertNotEqual(self.run_map("--geojson", path,
                "--csv-manifest", "conflict.json", *base).returncode, 0)
            self.assertFalse(output.exists())

    def test_existing_output_and_source_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            source = self.fixture(folder)
            old = source.read_bytes()
            flags = self.flags(source)
            rest = ("--at", AT, "--known-at", KNOWN)
            self.assertNotEqual(self.run_map(*flags, *rest,
                "--output", source).returncode, 0)
            self.assertEqual(source.read_bytes(), old)
            output = Path(folder) / "prior.html"
            output.write_text("PRESERVE", encoding="utf-8")
            self.assertNotEqual(self.run_map(*flags, *rest,
                "--output", output).returncode, 0)
            self.assertEqual(output.read_text(encoding="utf-8"), "PRESERVE")

    def test_auto_bbox_wraps_antimeridian_without_reconciling_points(self):
        with tempfile.TemporaryDirectory() as folder:
            source = self.fixture(folder)
            collection = json.loads(source.read_text(encoding="utf-8"))
            collection["features"][0]["geometry"]["coordinates"] = [179.8, 5.0]
            collection["features"][1]["geometry"]["coordinates"] = [-179.8, 5.0]
            source.write_text(json.dumps(collection), encoding="utf-8")
            output = Path(folder) / "wrapped.html"
            result = self.run_map(*self.flags(source), "--at", AT,
                                  "--known-at", KNOWN, "--output", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            page = output.read_text(encoding="utf-8")
            bounds = json.loads("[" + re.search(
                r'"bbox":\[([^\]]+)\]', page).group(1) + "]")
            self.assertGreater(bounds[0], bounds[2])
            self.assertIn('"total_source_features":2', page)

    def test_untrusted_locator_is_encoded_as_data_not_html_markup(self):
        with tempfile.TemporaryDirectory() as folder:
            source = self.fixture(folder)
            output = Path(folder) / "safe.html"
            flags = list(self.flags(source))
            flags[flags.index("--source-locator") + 1] = "dataset://</script><script>evil()</script>"
            result = self.run_map(*flags, "--at", AT,
                                  "--known-at", KNOWN, "--output", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            page = output.read_text(encoding="utf-8")
            self.assertNotIn("</script><script>evil()", page)
            self.assertIn("\\u003c/script\\u003e", page)



    def sources(self, root, mixed=False):
        folder = Path(root)
        def point(lon, lat):
            return {"type": "FeatureCollection", "features": [{
                "type": "Feature", "id": "shared", "properties": {},
                "geometry": {"type": "Point", "coordinates": [lon, lat]}}]}
        (folder / "a.geojson").write_text(
            json.dumps(point(2.35, 48.86)), encoding="utf-8")
        if mixed:
            (folder / "b.csv").write_text(
                "id,longitude,latitude\nshared,5.4,45.6\n", encoding="utf-8")
        else:
            (folder / "b.geojson").write_text(
                json.dumps(point(5.4, 45.6)), encoding="utf-8")
        entries = [
            {"geojson": "a.geojson", "source_id": "original-a",
             "locator": "dataset://a", "captured_at": KNOWN,
             "valid_from": "2026-01-01T00:00:00Z"},
            {("csv" if mixed else "geojson"): ("b.csv" if mixed else "b.geojson"),
             "source_id": "original-b", "locator": "dataset://b",
             "captured_at": KNOWN, "valid_from": "2026-01-01T00:00:00Z"}]
        manifest = folder / "sources.json"
        manifest.write_text(json.dumps({"datasets": entries}), encoding="utf-8")
        return manifest

    def test_multi_geojson_manifest_renders_competing_sources_without_state(self):
        with tempfile.TemporaryDirectory() as root:
            manifest = self.sources(root)
            output = Path(root) / "map.html"
            result = self.run_map("--source-manifest", manifest,
                                  "--at", AT, "--known-at", KNOWN, "--output", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            page = output.read_text(encoding="utf-8")
            for term in ('"total_source_features":2', "original-a",
                         "original-b", "dataset://a", "dataset://b", "shared"):
                self.assertIn(term, page)
            self.assertFalse((Path(root) / "state.json").exists())

    def test_mixed_csv_and_geojson_sources_share_one_map(self):
        with tempfile.TemporaryDirectory() as root:
            manifest = self.sources(root, mixed=True)
            output = Path(root) / "mixed.html"
            result = self.run_map("--source-manifest", manifest,
                                  "--at", AT, "--known-at", KNOWN, "--output", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            page = output.read_text(encoding="utf-8")
            self.assertIn('"total_source_features":2', page)
            self.assertIn("original-a", page)
            self.assertIn("original-b", page)

    def test_invalid_second_geojson_does_not_produce_partial_output(self):
        with tempfile.TemporaryDirectory() as root:
            manifest = self.sources(root)
            (Path(root) / "b.geojson").write_text(
                '{"type":"FeatureCollection","features":[{"type":"Feature",'
                '"id":"shared","geometry":{"type":"LineString",'
                '"coordinates":[[1,2],[3,4]]},"properties":{}}]}',
                encoding="utf-8")
            output = Path(root) / "absent.html"
            result = self.run_map("--source-manifest", manifest,
                                  "--at", AT, "--known-at", KNOWN, "--output", output)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())

    def test_manifests_preserve_inputs_and_reject_ambiguous_format(self):
        with tempfile.TemporaryDirectory() as root:
            manifest = self.sources(root)
            before = manifest.read_bytes()
            input_file = Path(root) / "a.geojson"
            input_before = input_file.read_bytes()
            flags = ("--source-manifest", manifest, "--at", AT, "--known-at", KNOWN)
            self.assertNotEqual(self.run_map(*flags, "--output", manifest).returncode, 0)
            self.assertNotEqual(self.run_map(*flags, "--output", input_file).returncode, 0)
            self.assertEqual(manifest.read_bytes(), before)
            self.assertEqual(input_file.read_bytes(), input_before)
            data = json.loads(before)
            data["datasets"][1]["csv"] = "b.csv"
            manifest.write_text(json.dumps(data), encoding="utf-8")
            output = Path(root) / "no.html"
            self.assertNotEqual(self.run_map(*flags, "--output", output).returncode, 0)
            self.assertFalse(output.exists())

    def test_each_geojson_source_requires_explicit_provenance(self):
        with tempfile.TemporaryDirectory() as root:
            manifest = self.sources(root)
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["datasets"][1].pop("locator")
            manifest.write_text(json.dumps(data), encoding="utf-8")
            output = Path(root) / "no.html"
            result = self.run_map("--source-manifest", manifest,
                                  "--at", AT, "--known-at", KNOWN, "--output", output)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())

    def test_offline_land_reference_is_bundled_and_separate_from_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            source = self.fixture(folder)
            output = Path(folder) / "land.html"
            result = self.run_map(*self.flags(source), "--at", AT,
                                  "--known-at", KNOWN, "--output", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            page = output.read_text(encoding="utf-8")
            self.assertIn('var landReference = {"kind":"NATURAL_EARTH_110M_LAND_CONTEXT_V1"', page)
            self.assertIn('"kind":"NATURAL_EARTH_110M_LAND_CONTEXT_V1"', page)
            self.assertIn('id="land"', page)
            self.assertIn('"total_source_features":2', page)
            self.assertNotIn("__MONDE_EMBEDDED_REFERENCE_LAND__", page)
            self.assertNotIn('https://tile.', page)


if __name__ == "__main__":
    unittest.main()
