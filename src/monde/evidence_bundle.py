"""Validate a downloaded MONDE original-reporter evidence ZIP without extraction.

SHA-256 verifies consistency with the included manifest, NOT authenticity.
"""
import argparse
from collections import Counter
from hashlib import sha256
import io
import json
from pathlib import Path
from zipfile import BadZipFile, ZIP_STORED, ZipFile

SCHEMA = "MONDE_ORIGINAL_REPORTER_EVIDENCE_BUNDLE_V1"
FILES = frozenset((
    "index.html", "matrix.json", "matrix.csv", "original-points.geojson",
    "analytical-witnesses.geojson", "analytical-witnesses.csv"))
MAX_ARCHIVE = 64 * 1024 * 1024
MAX_MEMBER = 32 * 1024 * 1024


class BundleVerificationError(ValueError):
    """Archive failed integrity, content or provenance-role checks."""


def _json(data, name):
    try:
        result = json.loads(data.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise BundleVerificationError("invalid JSON: " + name) from exc
    if not isinstance(result, dict):
        raise BundleVerificationError("JSON object required: " + name)
    return result


def verify_bundle(data: bytes) -> dict:
    """Verify a downloaded bundle without extraction or network requests."""
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_ARCHIVE:
        raise BundleVerificationError("invalid archive bytes or size")
    try:
        with ZipFile(io.BytesIO(data)) as z:
            infos = z.infolist()
            names = [info.filename for info in infos]
            if (len(infos) != len(FILES) + 1 or len(names) != len(set(names))
                    or set(names) != FILES | {"manifest.json"}):
                raise BundleVerificationError("missing, duplicate or unexpected members")
            for info in infos:
                if (info.is_dir() or info.flag_bits & 1
                        or info.compress_type != ZIP_STORED
                        or info.file_size > MAX_MEMBER
                        or info.compress_size != info.file_size
                        or ((info.external_attr >> 16) & 0o170000) == 0o120000):
                    raise BundleVerificationError("unsupported ZIP member")
            manifest = _json(z.read("manifest.json"), "manifest.json")
            if manifest.get("schema") != SCHEMA:
                raise BundleVerificationError("unsupported bundle schema")
            records = manifest.get("files")
            if not isinstance(records, dict) or set(records) != FILES:
                raise BundleVerificationError("manifest file set mismatch")
            if (manifest.get("original_observations_only") != ["original-points.geojson"]
                    or manifest.get("analytical_not_original") != [
                        "analytical-witnesses.geojson", "analytical-witnesses.csv"]):
                raise BundleVerificationError("original/analytical roles mismatch")
            if manifest.get("axis") not in ("knowledge", "world") or not isinstance(
                    manifest.get("cutoffs"), dict):
                raise BundleVerificationError("invalid time metadata")
            if not all(isinstance(manifest.get(key), str) and manifest[key]
                       for key in ("source_a", "source_b")):
                raise BundleVerificationError("invalid source identity")
            if manifest["source_a"] == manifest["source_b"]:
                raise BundleVerificationError("duplicate source identities")
            for name in sorted(FILES):
                rec = records[name]
                if (not isinstance(rec, dict) or set(rec) != {"bytes", "sha256"}
                        or type(rec["bytes"]) is not int or rec["bytes"] < 0
                        or not isinstance(rec["sha256"], str)):
                    raise BundleVerificationError("invalid manifest entry: " + name)
                raw = z.read(name)
                if len(raw) != rec["bytes"] or sha256(raw).hexdigest() != rec["sha256"]:
                    raise BundleVerificationError("checksum mismatch: " + name)
            matrix = _json(z.read("matrix.json"), "matrix.json")
            for key in ("source_a", "source_b", "axis", "cutoffs"):
                if matrix.get(key) != manifest[key]:
                    raise BundleVerificationError("manifest/matrix mismatch: " + key)
            for name in ("original-points.geojson", "analytical-witnesses.geojson"):
                doc = _json(z.read(name), name)
                if doc.get("type") != "FeatureCollection" or not isinstance(
                        doc.get("features"), list):
                    raise BundleVerificationError("invalid geographic collection")
                for feature in doc["features"]:
                    if not isinstance(feature, dict) or not isinstance(
                            feature.get("properties"), dict):
                        raise BundleVerificationError("invalid geographic feature")
                    props = feature["properties"]
                    analytical = (props.get("monde_geometry_role")
                                  == "ANALYTICAL_REPORTER_GAP_WITNESS")
                    if name == "original-points.geojson" and analytical:
                        raise BundleVerificationError("analytical geometry labeled original")
                    if analytical and props.get("monde_original_observation") is not False:
                        raise BundleVerificationError("derived witness labeled observed")
            return {"valid": True, "schema": SCHEMA,
                    "source_a": manifest["source_a"], "source_b": manifest["source_b"],
                    "axis": manifest["axis"], "verified_files": len(FILES),
                    "authenticity": "NOT_ATTESTED"}
    except (BadZipFile, EOFError, RuntimeError, OverflowError) as exc:
        raise BundleVerificationError("invalid or corrupted ZIP") from exc


def compare_bundles(before: bytes, after: bytes, *, entity: str | None = None,
                    inspect_changed: bool = False) -> dict:
    """Compare two verified original-reporter exports, without asserting truth.

    Repeated source reports are counted separately. Different selections,
    bitemporal cutoffs or exported analytical witnesses are not interpreted as
    real-world events, movement or independent source authentication.
    """
    if entity is not None and (not isinstance(entity, str) or not entity
                               or len(entity) > 512 or
                               any(ord(ch) < 32 for ch in entity)):
        raise BundleVerificationError("invalid entity selector")
    if type(inspect_changed) is not bool or (inspect_changed and entity is not None):
        raise BundleVerificationError("inspect_changed cannot be combined with entity")
    left = verify_bundle(before)
    right = verify_bundle(after)
    for key in ("schema", "source_a", "source_b", "axis"):
        if left[key] != right[key]:
            raise BundleVerificationError("incompatible bundles: " + key)

    def contents(raw):
        with ZipFile(io.BytesIO(raw)) as archive:
            manifest = _json(archive.read("manifest.json"), "manifest.json")
            matrix = _json(archive.read("matrix.json"), "matrix.json")
            points = _json(archive.read("original-points.geojson"),
                           "original-points.geojson")
            rows = matrix.get("entities")
            if not isinstance(rows, list):
                raise BundleVerificationError("invalid matrix entities")
            by_id = {}
            for row in rows:
                if not isinstance(row, dict) or not isinstance(row.get("entity"), str):
                    raise BundleVerificationError("invalid matrix entity")
                identifier = row["entity"]
                if identifier in by_id:
                    raise BundleVerificationError("duplicate matrix entity")
                by_id[identifier] = json.dumps(
                    row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            original = Counter(json.dumps(
                feature, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                for feature in points["features"])
            selected = Counter(json.dumps(
                feature, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                for feature in points["features"]
                if entity is not None and feature["properties"].get("entity") == entity)
            grouped = {}
            if inspect_changed:
                for feature in points["features"]:
                    name = feature["properties"].get("entity")
                    if (not isinstance(name, str) or not name or len(name) > 512
                            or any(ord(char) < 32 for char in name)):
                        raise BundleVerificationError(
                            "original Point missing a valid entity for batch inspection")
                    serialized = json.dumps(
                        feature, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                    grouped.setdefault(name, Counter())[serialized] += 1
            return manifest, by_id, original, selected, grouped

    left_manifest, left_rows, left_points, left_selected, left_grouped = contents(before)
    right_manifest, right_rows, right_points, right_selected, right_grouped = contents(after)
    added = sorted(right_rows.keys() - left_rows.keys())
    removed = sorted(left_rows.keys() - right_rows.keys())
    common = left_rows.keys() & right_rows.keys()
    changed = sorted(i for i in common if left_rows[i] != right_rows[i])
    changed_files = sorted(
        name for name in FILES
        if left_manifest["files"][name]["sha256"]
        != right_manifest["files"][name]["sha256"])
    result = {
        "valid": True,
        "comparison": "MONDE_ORIGINAL_REPORTER_BUNDLE_COMPARISON_V1",
        "source_a": left["source_a"], "source_b": left["source_b"],
        "axis": left["axis"],
        "before_cutoffs": left_manifest["cutoffs"],
        "after_cutoffs": right_manifest["cutoffs"],
        "selection_or_cutoffs_differ": (
            left_manifest.get("selection") != right_manifest.get("selection")
            or left_manifest["cutoffs"] != right_manifest["cutoffs"]),
        "entities_added": added, "entities_removed": removed,
        "entities_changed": changed,
        "entities_unchanged_count": len(common) - len(changed),
        "original_points_added": sum((right_points - left_points).values()),
        "original_points_removed": sum((left_points - right_points).values()),
        "changed_files": changed_files,
        "authenticity": "NOT_ATTESTED",
        "interpretation": "EXPORTED_EVIDENCE_DIFFERENCE_NOT_WORLD_CHANGE",
    }
    def inspect_one(identifier, original_before, original_after):
        def changed_features(delta):
            return [{"feature": json.loads(raw), "count": count}
                    for raw, count in sorted(delta.items())]

        return {
            "entity": identifier,
            "before_matrix_row": (json.loads(left_rows[identifier])
                                  if identifier in left_rows else None),
            "after_matrix_row": (json.loads(right_rows[identifier])
                                 if identifier in right_rows else None),
            "original_points_before_count": sum(original_before.values()),
            "original_points_after_count": sum(original_after.values()),
            "original_points_unchanged_count": sum(
                (original_before & original_after).values()),
            "original_points_added": changed_features(
                original_after - original_before),
            "original_points_removed": changed_features(
                original_before - original_after),
        }

    if entity is not None:
        if (entity not in left_rows and entity not in right_rows
                and not left_selected and not right_selected):
            raise BundleVerificationError("entity absent from both verified exports")
        result["entity_inspection"] = inspect_one(
            entity, left_selected, right_selected)
    if inspect_changed:
        # Include changes exclusively in original source Points even where the
        # exported matrix row has not changed. Preserve repeated observations.
        candidates = set(added) | set(removed) | set(changed)
        for identifier in left_grouped.keys() | right_grouped.keys():
            if left_grouped.get(identifier, Counter()) != right_grouped.get(
                    identifier, Counter()):
                candidates.add(identifier)
        result["changed_entity_inspections"] = [
            inspect_one(identifier,
                        left_grouped.get(identifier, Counter()),
                        right_grouped.get(identifier, Counter()))
            for identifier in sorted(candidates)
        ]
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="Downloaded original reporter ZIP")
    parser.add_argument("--compare", type=Path, metavar="OTHER_ZIP",
                        help="Compare verified export with another original-reporter ZIP")
    selectors = parser.add_mutually_exclusive_group()
    selectors.add_argument("--entity", metavar="ENTITY_ID",
                           help="Inspect one entity's original reports in both verified exports")
    selectors.add_argument("--inspect-changed", action="store_true",
                           help="Inspect every changed matrix row or original Point report")
    args = parser.parse_args(argv)
    if args.compare is None and (args.entity is not None or args.inspect_changed):
        parser.error("--entity and --inspect-changed require --compare")
    try:
        if args.bundle.stat().st_size > MAX_ARCHIVE:
            raise BundleVerificationError("archive exceeds safe size")
        original = args.bundle.read_bytes()
        if args.compare is None:
            result = verify_bundle(original)
        else:
            if args.compare.stat().st_size > MAX_ARCHIVE:
                raise BundleVerificationError("comparison archive exceeds safe size")
            result = compare_bundles(original, args.compare.read_bytes(),
                                     entity=args.entity,
                                     inspect_changed=args.inspect_changed)
    except (OSError, BundleVerificationError) as exc:
        print(json.dumps({"valid": False, "reason": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
