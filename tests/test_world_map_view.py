"""WORK-0017: concrete offline evidence map output and CLI regressions."""
import copy
import json
import os
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from monde.geojson import to_document
from monde.map_view import render_map
from monde.world import WorldMini

ROOT = Path(__file__).resolve().parents[1]
VALID = "2026-01-02T00:00:00Z"
KNOWN = "2026-01-10T10:00:00Z"
BBOX = [2.34, 48.84, 2.36, 48.87]


class Extract(HTMLParser):
    def __init__(self):
        super().__init__()
        self.data_chunks = []
        self.scripts = []
        self.active = None
        self.ready_markers = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script":
            self.active = "data" if a.get("id") == "monde-data" else "code"

    def handle_endtag(self, tag):
        if tag == "script":
            self.active = None

    def handle_data(self, data):
        if self.active == "data":
            self.data_chunks.append(data)
        if self.active == "code":
            self.scripts.append(data)


def with_points():
    world = WorldMini.read(str(ROOT / "examples/monde-mini.json"))
    geo = WorldMini.load_document(str(ROOT / "examples/monde-mini-points.geojson"))
    world.append_document(to_document(
        geo, source_id="official-map", locator="fixture://official-map",
        captured_at=KNOWN, valid_from="2026-01-01T00:00:00Z"))
    alternative = copy.deepcopy(geo)
    alternative["features"] = alternative["features"][:1]
    alternative["features"][0]["geometry"]["coordinates"] = [5.0, 45.0]
    world.append_document(to_document(
        alternative, source_id="contrary-map", locator="fixture://contrary-map",
        captured_at=KNOWN, valid_from="2026-01-01T00:00:00Z"))
    return world


def extract(html):
    parser = Extract()
    parser.feed(html)
    return parser, json.loads("".join(parser.data_chunks))


class OfflineMapTest(unittest.TestCase):
    def test_all_competing_source_reports_retained_and_clickable(self):
        source = with_points().export_geojson_bbox(BBOX, VALID, KNOWN)
        html = render_map(source)
        parsed, embedded = extract(html)
        self.assertEqual(embedded, source)
        self.assertEqual(embedded["monde_bbox_query"]["total_matching_entities"], 1)
        self.assertEqual(len(embedded["features"]), 2)
        self.assertEqual(sorted(f["properties"]["monde_inside_bbox"]
                                for f in embedded["features"]), [False, True])
        self.assertIn('id="points"', html)
        self.assertIn('id="report-list"', html)
        self.assertIn("addEventListener", "".join(parsed.scripts))
        self.assertIn("aria-live", html)
        self.assertNotIn("<script src=", html)
        self.assertIn("connect-src 'none'", html)

    def test_no_matching_viewport_is_not_claimed_as_physical_absence(self):
        source = WorldMini.read(str(ROOT / "examples/monde-mini.json"))
        html = render_map(source.export_geojson_bbox(BBOX, VALID, KNOWN))
        _, data = extract(html)
        self.assertEqual(data["features"], [])
        self.assertEqual(data["monde_bbox_query"]["status"], "NO_MATCHES")
        self.assertIn("does not establish physical absence", html)

    def test_embed_untrusted_source_strings_cannot_escape_json_script(self):
        source = with_points().export_geojson_bbox(BBOX, VALID, KNOWN)
        injection = "</script><script>globalThis.pwned=true</script><img src=x onerror=alert(1)>"
        source["features"][0]["properties"]["locator"] = injection
        html = render_map(source)
        self.assertNotIn(injection, html)
        self.assertNotIn("</script><script>", html)
        p, embedded = extract(html)
        self.assertEqual(embedded["features"][0]["properties"]["locator"], injection)
        self.assertEqual(len(p.scripts), 1)

    def test_reject_invalid_point_and_missing_provenance(self):
        source = with_points().export_geojson_bbox(BBOX, VALID, KNOWN)
        for mutate in ("nan", "bool", "missing", "bad_type"):
            copy_source = copy.deepcopy(source)
            f = copy_source["features"][0]
            if mutate == "nan":
                f["geometry"]["coordinates"][0] = float("nan")
            elif mutate == "bool":
                f["geometry"]["coordinates"][0] = True
            elif mutate == "missing":
                del f["properties"]["evidence_id"]
            else:
                f["geometry"]["type"] = "LineString"
            with self.subTest(mutate=mutate):
                with self.assertRaises(ValueError):
                    render_map(copy_source)

    def test_saved_state_cli_writes_self_contained_html_and_preserves_state(self):
        w = with_points()
        original = w.export()
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "state.json"
            output = Path(td) / "map.html"
            w.save(str(target))
            cmd = [sys.executable, "-m", "monde.map_view",
                   "--state", str(target), "--bbox", "2.34,48.84,2.36,48.87",
                   "--at", VALID, "--known-at", KNOWN, "--output", str(output)]
            environment = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
            first = subprocess.run(cmd, capture_output=True, text=True,
                                   env=environment, cwd=ROOT)
            self.assertEqual(first.returncode, 0, first.stderr)
            html = output.read_text(encoding="utf-8")
            _, embedded = extract(html)
            self.assertEqual(len(embedded["features"]), 2)
            self.assertEqual(w.export(), original)
            self.assertEqual(WorldMini.read(str(target)).export(), original)
            again = subprocess.run(cmd, capture_output=True, text=True,
                                   env=environment, cwd=ROOT)
            self.assertNotEqual(again.returncode, 0, "must not overwrite map")
            self.assertEqual(output.read_text(encoding="utf-8"), html)

    def test_cli_invalid_bbox_fails_and_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "bad.html"
            cmd = [sys.executable, "-m", "monde.map_view",
                   "--state", str(ROOT / "examples/monde-mini.json"),
                   "--bbox", "0,100,10,0", "--at", VALID, "--known-at", KNOWN,
                   "--output", str(out)]
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  env=dict(os.environ, PYTHONPATH=str(ROOT / "src")))
            self.assertNotEqual(proc.returncode, 0)
            self.assertFalse(out.exists())

    def test_embedded_javascript_parses_under_node_when_available(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node unavailable; GitHub Actions browser smoke runs separately")
        html = render_map(with_points().export_geojson_bbox(BBOX, VALID, KNOWN))
        parsed, _ = extract(html)
        script = "\n".join(parsed.scripts)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "viewer.js"
            path.write_text(script, encoding="utf-8")
            out = subprocess.run([node, "--check", str(path)],
                                 capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stderr)


LATE = "2026-01-11T10:00:00Z"


def corrected_points():
    world = with_points()
    snapshot = world.export()
    sources = {e["id"]: e["source_id"] for e in snapshot["evidence"]}
    original = next(a for a in snapshot["assertions"]
                    if a["attribute"] == "geo_point"
                    and sources[a["evidence_id"]] == "official-map")
    world.add_evidence({
        "id": "map-knowledge-correction", "source_id": "official-map",
        "locator": "fixture://official-map/correction",
        "captured_at": LATE, "source_event_at": None,
    })
    world.add_assertion({
        **original, "id": "map-knowledge-updated", "known_at": LATE,
        "evidence_id": "map-knowledge-correction", "supersedes": original["id"],
        "value": {"type": "Point", "coordinates": [5.5, 44.5]},
    })
    return world, original["id"]


class OfflineKnowledgeChangeMapTest(unittest.TestCase):
    def test_evidence_and_locations_retained_across_cutoffs(self):
        world, prior_id = corrected_points()
        state = world.export()
        changes = world.export_geojson_bbox_knowledge_changes(BBOX, VALID, KNOWN, LATE)
        self.assertEqual(changes["monde_bbox_changes_query"]["status"], "CHANGES")
        html = render_map(changes)
        _, embedded = extract(html)
        self.assertEqual(embedded, changes)
        self.assertEqual({f["id"] for f in embedded["features"]},
                         {prior_id, "map-knowledge-updated"})
        self.assertEqual({f["properties"]["monde_change"] for f in embedded["features"]},
                         {"NEWLY_CURRENT", "NO_LONGER_CURRENT"})
        self.assertIn('id="change-filter"', html)
        self.assertIn("NOT verified physical movement", html)
        self.assertIn("p.monde_change", html)
        self.assertEqual(world.export(), state)

    def test_empty_comparison_retains_no_change_not_absence(self):
        world = with_points()
        changes = world.export_geojson_bbox_knowledge_changes(BBOX, VALID, KNOWN, LATE)
        html = render_map(changes)
        _, embedded = extract(html)
        self.assertEqual(embedded["features"], [])
        self.assertEqual(embedded["monde_bbox_changes_query"]["status"], "NO_CHANGES")
        self.assertIn("not verified", html)

    def test_comparison_rejects_invalid_change_basis(self):
        world, _ = corrected_points()
        changes = world.export_geojson_bbox_knowledge_changes(BBOX, VALID, KNOWN, LATE)
        for mutation in ("basis", "change", "cutoff"):
            bogus = copy.deepcopy(changes)
            if mutation == "basis":
                bogus["monde_bbox_changes_query"]["basis"] = "PHYSICAL_MOTION"
            elif mutation == "change":
                bogus["features"][0]["properties"]["monde_change"] = "MOVING"
            else:
                bogus["features"][0]["properties"]["from_known_at"] = "2000-01-01T00:00:00Z"
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                render_map(bogus)

    def test_saved_state_cli_comparison_and_no_overwrite(self):
        world, _ = corrected_points()
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state.json"
            target = Path(directory) / "changes.html"
            world.save(str(state))
            before = state.read_bytes()
            command = [sys.executable, "-m", "monde.map_view",
                       "--state", str(state), "--bbox", "2.34,48.84,2.36,48.87",
                       "--at", VALID, "--compare-known-at", KNOWN, "--known-at", LATE,
                       "--output", str(target)]
            env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
            result = subprocess.run(command, capture_output=True, text=True,
                                    env=env, cwd=ROOT)
            self.assertEqual(result.returncode, 0, result.stderr)
            _, embedded = extract(target.read_text(encoding="utf-8"))
            self.assertEqual(len(embedded["features"]), 2)
            self.assertEqual(state.read_bytes(), before)
            again = subprocess.run(command, capture_output=True, text=True,
                                   env=env, cwd=ROOT)
            self.assertNotEqual(again.returncode, 0)
            self.assertEqual(state.read_bytes(), before)

    def test_cli_rejects_reversed_knowledge_cutoffs(self):
        world, _ = corrected_points()
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state.json"
            target = Path(directory) / "bad.html"
            world.save(str(state))
            command = [sys.executable, "-m", "monde.map_view", "--state", str(state),
                       "--bbox", "2.34,48.84,2.36,48.87", "--at", VALID,
                       "--compare-known-at", LATE, "--known-at", KNOWN,
                       "--output", str(target)]
            result = subprocess.run(command, capture_output=True, text=True,
                                    env=dict(os.environ, PYTHONPATH=str(ROOT / "src")))
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()

class EvidenceSearchNavigationTest(unittest.TestCase):
    def test_search_and_focus_are_present_in_generated_offline_map(self):
        page = render_map(with_points().export_geojson_bbox(BBOX, VALID, KNOWN))
        self.assertIn('id="report-search"', page)
        self.assertIn('id="focus-selected"', page)
        self.assertIn('id="clear-search"', page)
        self.assertIn('search.addEventListener("input",render)', page)
        self.assertIn('centerOn(feature)', page)
        self.assertIn('p.evidence_id,p.locator', page)
        self.assertIn("toLocaleLowerCase()", page)
        self.assertIn("words.every(", page)
        self.assertNotIn("<script src=", page)
        self.assertIn("connect-src 'none'", page)

    def test_search_widgets_do_not_change_embedded_source_assertions(self):
        source = with_points().export_geojson_bbox(BBOX, VALID, KNOWN)
        before = copy.deepcopy(source)
        page = render_map(source)
        _, parsed = extract(page)
        self.assertEqual(source, before)
        self.assertEqual(parsed, before)
        self.assertIn('Source assertions only.', page)


class VisibleGeoJSONExportTest(unittest.TestCase):
    def test_export_action_retains_original_geojson_and_exposes_derivative_scope(self):
        original = with_points().export_geojson_bbox(BBOX, VALID, KNOWN)
        immutable = copy.deepcopy(original)
        html = render_map(original)
        self.assertEqual(extract(html)[1], immutable)
        self.assertEqual(original, immutable)
        self.assertIn('id="export-visible"', html)
        self.assertIn('"VISIBLE_SOURCE_REPORTS_ONLY"', html)
        self.assertIn('original_feature_count: features.length', html)
        self.assertIn('exported_feature_count: visibleFeatures.length', html)
        self.assertIn('monde-visible-source-evidence.geojson', html)
        self.assertIn('knowledge_change: knowledgeComparing ? changeFilter.value : ""', html)
        self.assertIn("exportButton.disabled = visibleFeatures.length === 0", html)
        self.assertIn("connect-src 'none'", html)

    def test_visible_export_exists_in_knowledge_change_map(self):
        world, _ = corrected_points()
        exported = world.export_geojson_bbox_knowledge_changes(
            BBOX, VALID, KNOWN, LATE)
        html = render_map(exported)
        self.assertIn('id="export-visible"', html)
        self.assertIn('knowledge_change: knowledgeComparing ? changeFilter.value : ""', html)
        self.assertIn('features: visibleFeatures.slice()', html)
        self.assertEqual(extract(html)[1], exported)


class OfflineWorldTimeComparisonTest(unittest.TestCase):
    def world_with_validity_changes(self):
        world = with_points()
        geo = WorldMini.load_document(str(ROOT / "examples/monde-mini-points.geojson"))
        earlier = copy.deepcopy(geo)
        earlier["features"] = earlier["features"][:1]
        world.append_document(to_document(
            earlier, source_id="historic-map", locator="fixture://historic",
            captured_at=KNOWN, valid_from="2025-12-01T00:00:00Z",
            valid_to="2026-01-01T00:00:00Z"))
        return world

    def test_world_time_deltas_keep_old_and_new_source_evidence(self):
        world = self.world_with_validity_changes()
        saved = world.export()
        delta = world.export_geojson_bbox_world_changes(
            BBOX, "2025-12-31T00:00:00Z", VALID, KNOWN)
        self.assertEqual({f["properties"]["monde_change"] for f in delta["features"]},
                         {"NEWLY_CURRENT", "NO_LONGER_CURRENT"})
        self.assertTrue(all(
            f["properties"]["monde_change_basis"] ==
            "REPORTED_VALIDITY_NOT_VERIFIED_MOTION" for f in delta["features"]))
        page = render_map(delta)
        self.assertEqual(extract(page)[1], delta)
        self.assertIn("Source-reported world-time validity changes", page)
        self.assertIn("world_time_change: worldComparing ? changeFilter.value", page)
        self.assertEqual(world.export(), saved)

    def test_invalid_world_time_basis_and_provenance_rejected(self):
        w = self.world_with_validity_changes()
        base = w.export_geojson_bbox_world_changes(
            BBOX, "2025-12-31T00:00:00Z", VALID, KNOWN)
        for case in ("basis", "cutoff", "change", "mixed"):
            data = copy.deepcopy(base)
            if case == "basis":
                data["monde_bbox_world_changes_query"]["basis"] = "TRUE_MOTION"
            elif case == "cutoff":
                data["features"][0]["properties"]["from_at"] = VALID
            elif case == "change":
                data["features"][0]["properties"]["monde_change"] = "MOVED"
            else:
                data["monde_bbox_changes_query"] = {}
            with self.subTest(case=case), self.assertRaises(ValueError):
                render_map(data)

    def test_world_time_cli_and_no_overwrite(self):
        world = self.world_with_validity_changes()
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state.json"
            output = Path(directory) / "world.html"
            world.save(str(state))
            original = state.read_bytes()
            cmd = [sys.executable, "-m", "monde.map_view",
                   "--state", str(state), "--bbox", "2.34,48.84,2.36,48.87",
                   "--compare-at", "2025-12-31T00:00:00Z", "--at", VALID,
                   "--known-at", KNOWN, "--output", str(output)]
            env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
            result = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=ROOT)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("monde_bbox_world_changes_query",
                          extract(output.read_text(encoding="utf-8"))[1])
            self.assertEqual(state.read_bytes(), original)
            self.assertNotEqual(subprocess.run(cmd, capture_output=True, env=env).returncode, 0)
            self.assertNotEqual(subprocess.run(
                cmd + ["--compare-known-at", KNOWN], capture_output=True, env=env).returncode, 0)
            self.assertEqual(state.read_bytes(), original)

    def test_reversed_world_times_do_not_create_output(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "invalid.html"
            cmd = [sys.executable, "-m", "monde.map_view",
                   "--state", str(ROOT / "examples/monde-mini.json"),
                   "--bbox", "2.34,48.84,2.36,48.87", "--compare-at", VALID,
                   "--at", "2025-12-31T00:00:00Z", "--known-at", KNOWN,
                   "--output", str(out)]
            self.assertNotEqual(subprocess.run(cmd, capture_output=True,
                 env=dict(os.environ, PYTHONPATH=str(ROOT / "src"))).returncode, 0)
            self.assertFalse(out.exists())


class OfflineEntityComparisonTest(unittest.TestCase):
    def test_entity_comparison_preserves_competing_evidence_without_truth_inference(self):
        source = with_points().export_geojson_bbox(BBOX, VALID, KNOWN)
        before = copy.deepcopy(source)
        page = render_map(source)
        _, embedded = extract(page)
        self.assertEqual(before, embedded)
        self.assertEqual(source, before)
        self.assertEqual(len(embedded["features"]), 2)
        self.assertIn('id="entities"', page)
        self.assertIn('id="disagreements-only"', page)
        self.assertIn('id="entity-comparison-list"', page)
        self.assertIn('id="entity-comparison-summary"', page)
        self.assertIn('different_source_positions_only: differentOnly.checked', page)
        self.assertIn('entity: entities.value', page)
        self.assertIn('not verified truth or movement', page)
        self.assertNotIn('<script src=', page)
        self.assertIn("connect-src 'none'", page)

    def test_comparison_available_in_both_temporal_change_modes(self):
        world, _ = corrected_points()
        inputs = (
            world.export_geojson_bbox_knowledge_changes(BBOX, VALID, KNOWN, LATE),
            world.export_geojson_bbox_world_changes(
                BBOX, "2025-12-31T00:00:00Z", VALID, LATE),
        )
        for source in inputs:
            with self.subTest(kind=list(source)):
                page = render_map(source)
                self.assertIn('id="entities"', page)
                self.assertIn('id="entity-comparison-list"', page)
                self.assertEqual(extract(page)[1], source)

class OfflineMapWindowTest(unittest.TestCase):
    def test_map_window_navigation_preserves_embedded_source_reports(self):
        original = with_points().export_geojson_bbox(BBOX, VALID, KNOWN)
        before = copy.deepcopy(original)
        page = render_map(original)
        self.assertEqual(extract(page)[1], before)
        self.assertEqual(original, before)
        self.assertIn('id="current-view-only"', page)
        self.assertIn('svg.addEventListener("pointerdown"', page)
        self.assertIn('svg.addEventListener("keydown"', page)
        self.assertIn('displayed_map_window_bbox_wgs84', page)
        self.assertIn('(ignoreDisplayedWindow || !currentViewOnly.checked || insideDisplayedWindow(f))', page)
        self.assertIn("connect-src 'none'", page)

    def test_map_window_available_in_both_temporal_comparison_modes(self):
        world, _ = corrected_points()
        cases = (
            world.export_geojson_bbox_knowledge_changes(BBOX, VALID, KNOWN, LATE),
            world.export_geojson_bbox_world_changes(
                BBOX, "2025-12-31T00:00:00Z", VALID, LATE),
        )
        for document in cases:
            with self.subTest(mode=list(document)):
                page = render_map(document)
                self.assertEqual(extract(page)[1], document)
                self.assertIn('id="current-view-only"', page)


class OfflineDisagreementLinksTest(unittest.TestCase):
    def test_links_toggle_and_original_source_provenance_unchanged(self):
        source = with_points().export_geojson_bbox(BBOX, VALID, KNOWN)
        before = copy.deepcopy(source)
        page = render_map(source)
        self.assertEqual(extract(page)[1], before)
        self.assertEqual(source, before)
        self.assertIn('id="disagreement-links"', page)
        self.assertIn('id="show-disagreement-links"', page)
        self.assertIn('showLinks.addEventListener("change",render)', page)
        self.assertIn('renderDisagreementLinks(visibleFeatures)', page)
        self.assertIn('not routes, movements', page)
        self.assertIn("connect-src 'none'", page)

    def test_links_are_supported_in_knowledge_and_world_comparisons(self):
        world, _ = corrected_points()
        for source in (world.export_geojson_bbox_knowledge_changes(
                BBOX, VALID, KNOWN, LATE),
                world.export_geojson_bbox_world_changes(
                BBOX, "2025-12-31T00:00:00Z", VALID, LATE)):
            with self.subTest(basis=list(source)):
                page = render_map(source)
                self.assertIn('id="disagreement-links"', page)
                self.assertEqual(extract(page)[1], source)

class OfflineCaptureDateFilterTest(unittest.TestCase):
    def test_capture_utc_range_preserves_original_bitemporal_source_evidence(self):
        source = with_points().export_geojson_bbox(BBOX, VALID, KNOWN)
        original = copy.deepcopy(source)
        html = render_map(source)
        self.assertEqual(extract(html)[1], original)
        self.assertEqual(source, original)
        self.assertIn('id="captured-from" type="date"', html)
        self.assertIn('id="captured-through" type="date"', html)
        self.assertIn('new Date(instant).toISOString().slice(0,10)', html)
        self.assertIn('captured_from_utc_day: capturedFrom.value', html)
        self.assertIn('captured_through_utc_day: capturedThrough.value', html)
        self.assertIn('Capture dates filter source evidence metadata', html)
        self.assertIn("connect-src 'none'", html)

    def test_capture_filter_is_available_in_both_temporal_change_modes(self):
        world, _ = corrected_points()
        for document in (
            world.export_geojson_bbox_knowledge_changes(BBOX, VALID, KNOWN, LATE),
            world.export_geojson_bbox_world_changes(
                BBOX, "2025-12-31T00:00:00Z", VALID, LATE),
        ):
            with self.subTest(mode=list(document)):
                html = render_map(document)
                self.assertEqual(extract(html)[1], document)
                self.assertIn('capturedThrough.addEventListener("change",render)', html)
                self.assertIn('capturedFrom.addEventListener("change",render)', html)

class OfflineFitReportsTest(unittest.TestCase):
    def test_fit_reuses_filters_without_changing_source_evidence(self):
        source = with_points().export_geojson_bbox(BBOX, VALID, KNOWN)
        before = copy.deepcopy(source)
        html = render_map(source)
        self.assertEqual(source, before)
        self.assertEqual(extract(html)[1], before)
        self.assertIn('id="fit-reports" type="button" disabled', html)
        self.assertIn('fitButton.addEventListener("click",fitReports)', html)
        self.assertIn('matchesFilters(f, true)', html)
        self.assertIn('fitButton.disabled = matchingReports().length === 0', html)
        self.assertIn("connect-src 'none'", html)

    def test_fit_available_on_both_temporal_comparisons(self):
        world, _ = corrected_points()
        for document in (
            world.export_geojson_bbox_knowledge_changes(BBOX, VALID, KNOWN, LATE),
            world.export_geojson_bbox_world_changes(
                BBOX, "2025-12-31T00:00:00Z", VALID, LATE),
        ):
            with self.subTest(mode=list(document)):
                html = render_map(document)
                self.assertEqual(extract(html)[1], document)
                self.assertIn('id="fit-reports"', html)


class OfflineEntityDossierExportTest(unittest.TestCase):
    def test_entity_dossier_export_retains_claims_filters_and_provenance(self):
        source = with_points().export_geojson_bbox(BBOX, VALID, KNOWN)
        original = copy.deepcopy(source)
        page = render_map(source)
        self.assertEqual(extract(page)[1], original)
        self.assertEqual(source, original)
        for expected in ('id="export-dossier" type="button" disabled',
                         'function createEntityDossier()',
                         'dossierButton.addEventListener("click"',
                         'reports: reports.slice()',
                         'filters: appliedFilters()',
                         'source_snapshot_report_count: features.length',
                         'entity_reports_in_source_snapshot: features.filter',
                         'a.properties.source_id !== b.properties.source_id',
                         'FILTERED_VISIBLE_SOURCE_REPORTS_ONLY',
                         'monde-entity-evidence-dossier.json',
                         "connect-src 'none'"):
            self.assertIn(expected, page)

    def test_dossier_available_in_both_time_comparison_modes(self):
        world, _ = corrected_points()
        docs = (world.export_geojson_bbox_knowledge_changes(BBOX, VALID, KNOWN, LATE),
                world.export_geojson_bbox_world_changes(
                    BBOX, "2025-12-31T00:00:00Z", VALID, LATE))
        for source in docs:
            with self.subTest(basis=list(source)):
                page = render_map(source)
                self.assertEqual(extract(page)[1], source)
                self.assertIn('id="export-dossier"', page)
                self.assertIn('KNOWLEDGE_CHANGE', page)
                self.assertIn('REPORTED_WORLD_TIME_CHANGE', page)
