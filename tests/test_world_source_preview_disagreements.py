"""Source provenance and temporal overlap in preview-only disagreement warnings."""
import json
from pathlib import Path
import tempfile
import unittest

from monde.source_refresh import preview_documents, refresh_documents
from monde.world import WorldMini
from tests.test_world_source_refresh import K1, K2, csv_source, invoke


def report(source, evidence, assertion, value, known, *, start="2026-01-01T00:00:00Z",
           end=None, supersedes=None):
    return {"schema_version": 1, "evidence": [{
        "id": evidence, "source_id": source, "locator": "dataset://" + source,
        "captured_at": known, "source_event_at": start,
    }], "assertions": [{
        "id": assertion, "entity": "site-a", "attribute": "status",
        "value": value, "evidence_id": evidence, "kind": "CLAIM",
        "known_at": known, "valid_from": start, "valid_to": end,
        "supersedes": supersedes,
    }]}


class CrossSourcePreviewTests(unittest.TestCase):
    def test_distinct_sources_and_overlapping_validity_warn_without_saving(self):
        original = WorldMini.from_document(report("survey", "e1", "a1", "open", K1))
        prior = original.export()
        preview = preview_documents(original, [
            report("another", "e2", "a2", "closed", K2,
                   start="2026-01-02T00:00:00Z")])
        self.assertEqual(preview["cross_source_disagreement_count"], 1)
        conflict, = preview["cross_source_disagreements"]
        self.assertEqual(conflict["status"], "CONFLICTING_SOURCE_REPORTS_ONLY")
        self.assertEqual((conflict["new_source_id"], conflict["other_source_id"]),
                         ("another", "survey"))
        self.assertEqual((conflict["new_reported_value"], conflict["other_reported_value"]),
                         ("closed", "open"))
        self.assertEqual(conflict["overlap_valid_from"], "2026-01-02T00:00:00+00:00")
        self.assertIsNone(conflict["overlap_valid_to"])
        self.assertEqual(original.export(), prior)
        self.assertNotIn("estimated_state", preview)

    def test_equal_values_same_source_and_disjoint_validity_do_not_warn(self):
        before = WorldMini.from_document(report("survey", "e1", "a1", "open", K1,
                                                 end="2026-01-03T00:00:00Z"))
        for candidate in [
            report("another", "e2", "a2", "open", K2),
            report("another", "e3", "a3", "closed", K2,
                   start="2026-01-03T00:00:00Z"),
        ]:
            self.assertEqual(preview_documents(before, [candidate])[
                "cross_source_disagreements"], [])
        same_source = report("survey", "e4", "a4", "closed", K2,
                             start="2026-01-03T00:00:00Z")
        self.assertEqual(preview_documents(before, [same_source])[
            "cross_source_disagreement_count"], 0)

    def test_superseded_old_report_not_reported_as_current_disagreement(self):
        before = WorldMini.from_document(report("survey", "e1", "a1", "old", K1))
        before.append_document(report("survey", "e2", "a2", "revised",
                                      "2026-01-02T18:00:00Z", supersedes="a1"))
        same = preview_documents(before, [
            report("another", "e3", "a3", "revised", K2)])
        self.assertEqual(same["cross_source_disagreements"], [])
        different = preview_documents(before, [
            report("another", "e4", "a4", "conflicting", K2)])
        self.assertEqual(different["cross_source_disagreement_count"], 1)
        self.assertEqual(different["cross_source_disagreements"][0][
            "other_assertion_id"], "a2")

    def test_same_capture_pair_counted_once_and_replay_has_no_new_warning(self):
        empty = WorldMini()
        first = report("source_a", "ea", "aa", "north", K1)
        second = report("source_b", "eb", "ab", "south", K2)
        preview = preview_documents(empty, [first, second])
        self.assertEqual(preview["cross_source_disagreement_count"], 1)
        after, _ = refresh_documents(empty, [first, second])
        self.assertEqual(preview_documents(after, [first, second])[
            "cross_source_disagreement_count"], 0)

    def test_real_original_csv_cli_reports_conflicts_without_touching_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, raw = csv_source(root)
            previous = root / "before.json"
            built = invoke("--ingest-source-manifest", manifest, "--state-out", previous)
            self.assertEqual(built.returncode, 0, built.stderr)
            unchanged_state = previous.read_bytes()
            csv_source(root, source="another", locator="dataset://another/points",
                       capture=K2, rows=[("site-a", 3.0, 49.0, "disputed")])
            original_csv = raw.read_bytes()
            checked = invoke("--fixture", previous, "--preview-source-manifest", manifest)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            data = json.loads(checked.stdout)
            self.assertEqual(data["status"], "PREVIEW_NOT_SAVED")
            self.assertGreaterEqual(data["cross_source_disagreement_count"], 2)
            self.assertEqual({x["attribute"] for x in data[
                "cross_source_disagreements"]}, {"geo_point", "label"})
            self.assertEqual(previous.read_bytes(), unchanged_state)
            self.assertEqual(raw.read_bytes(), original_csv)
            self.assertEqual(sorted(p.name for p in root.iterdir()),
                             ["before.json", "manifest.json", "observations.csv"])

    def test_preview_offline_map_displays_conflicting_original_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, original_csv = csv_source(root)
            snapshot = root / "before.json"
            initial = invoke("--ingest-source-manifest", manifest,
                             "--state-out", snapshot)
            self.assertEqual(initial.returncode, 0, initial.stderr)
            old_snapshot, old_csv = snapshot.read_bytes(), original_csv.read_bytes()
            csv_source(root, source="different", locator="dataset://different/points",
                       capture=K2, rows=[("site-a", 3.0, 49.0, "conflicted")])
            new_csv = original_csv.read_bytes()
            page = root / "preview.html"
            outcome = invoke("--fixture", snapshot, "--preview-source-manifest",
                             manifest, "--preview-source-map", page)
            self.assertEqual(outcome.returncode, 0, outcome.stderr)
            payload = json.loads(outcome.stdout)
            self.assertGreaterEqual(payload["cross_source_disagreement_count"], 2)
            html = page.read_text(encoding="utf-8")
            self.assertIn('id="preview-source-conflicts"', html)
            self.assertIn('"monde_preview_disagreements"', html)
            self.assertIn('"CONFLICTING_SOURCE_REPORTS_ONLY"', html)
            self.assertIn('conflicted', html)
            self.assertEqual(payload["status"], "PREVIEW_NOT_SAVED")
            self.assertEqual(snapshot.read_bytes(), old_snapshot)
            self.assertEqual(original_csv.read_bytes(), new_csv)

    def test_preview_map_escapes_untrusted_source_values_and_keeps_preview_only(self):
        from monde.source_delta import source_delta_html
        previous = WorldMini.from_document(report("source_a", "e1", "a1", "open", K1))
        next_world, _ = refresh_documents(previous, [
            report("source_b", "e2", "a2", "</script><img src=x>", K2)])
        warnings = preview_documents(previous, [
            report("source_b", "e2", "a2", "</script><img src=x>", K2)])
        html = source_delta_html(previous, next_world,
                                 disagreements=warnings["cross_source_disagreements"])
        self.assertIn('"monde_preview_disagreements"', html)
        self.assertNotIn("</script><img src=x>", html)
        self.assertIn("\\u003c/script\\u003e", html)
        self.assertIn("data-monde-ready", html)


if __name__ == "__main__":
    unittest.main()
