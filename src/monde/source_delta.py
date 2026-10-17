"""Compare two validated MONDE Mini snapshots without erasing source ancestry.

A delta describes newly *recorded source reports*, never a change to verified
physical reality. Append-only prefix checking rejects an unrelated or rewritten
history, even if its headline counts happen to agree.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path
import sys

from .world import WorldMini


def source_delta(before: WorldMini, after: WorldMini) -> dict:
    """Return the append-only evidence/claim delta between two durable states."""
    old, new = before.export(), after.export()
    for field in ("evidence", "assertions"):
        previous = old[field]
        current = new[field]
        if current[:len(previous)] != previous:
            raise ValueError("snapshot history diverged: " + field)

    evidence = new["evidence"][len(old["evidence"]):]
    assertions = new["assertions"][len(old["assertions"]):]
    evidence_by_id = {item["id"]: item for item in new["evidence"]}
    source_rows = {}
    details = []
    for item in evidence:
        row = source_rows.setdefault(item["source_id"], {
            "source_id": item["source_id"], "evidence_added": 0,
            "assertions_added": 0, "corrections_added": 0, "_entities": set(),
        })
        row["evidence_added"] += 1

    for item in assertions:
        original = evidence_by_id[item["evidence_id"]]
        source_id = original["source_id"]
        row = source_rows.setdefault(source_id, {
            "source_id": source_id, "evidence_added": 0,
            "assertions_added": 0, "corrections_added": 0, "_entities": set(),
        })
        row["assertions_added"] += 1
        row["_entities"].add(item["entity"])
        if item["supersedes"] is not None:
            row["corrections_added"] += 1
        details.append({
            "assertion_id": item["id"],
            "source_id": source_id,
            "evidence_id": item["evidence_id"],
            "entity": item["entity"],
            "attribute": item["attribute"],
            "kind": item["kind"],
            "known_at": item["known_at"],
            "valid_from": item["valid_from"],
            "valid_to": item["valid_to"],
            "supersedes": item["supersedes"],
        })
    sources = []
    for name in sorted(source_rows):
        row = source_rows[name]
        row["affected_entities"] = sorted(row.pop("_entities"))
        sources.append(row)
    return {
        "schema_version": 1,
        "world": "OBSERVED",
        "status": "SOURCE_REPORT_DELTA",
        "before": {
            "evidence": len(old["evidence"]),
            "assertions": len(old["assertions"]),
        },
        "after": {
            "evidence": len(new["evidence"]),
            "assertions": len(new["assertions"]),
        },
        "added": {
            "evidence": len(evidence),
            "assertions": len(assertions),
            "corrections": sum(item["supersedes"] is not None for item in assertions),
        },
        "sources": sources,
        "new_reports": details,
    }


def source_delta_geojson(before: WorldMini, after: WorldMini) -> dict:
    """Map *newly recorded* source Point reports; never infer actual movement.

    Uses the same append-only ancestry check as source_delta(). Each feature
    remains one un-reconciled assertion with its own evidence and temporal
    provenance, including superseded reports.
    """
    from .geojson import _point

    change = source_delta(before, after)
    snapshot = after.export()
    new_ids = {row["assertion_id"] for row in change["new_reports"]}
    additions = {item["id"]: item for item in snapshot["assertions"]
                 if item["id"] in new_ids}
    evidence = {item["id"]: item for item in snapshot["evidence"]}
    features = []
    for report in change["new_reports"]:
        if report["attribute"] != "geo_point":
            continue
        assertion = additions[report["assertion_id"]]
        capture = evidence[report["evidence_id"]]
        features.append({
            "type": "Feature",
            "id": report["assertion_id"],
            "geometry": _point(assertion["value"]),
            "properties": {
                **report,
                "source_locator": capture["locator"],
                "captured_at": capture["captured_at"],
                "source_event_at": capture["source_event_at"],
                "monde_world": "OBSERVED",
                "monde_status": "NEW_SOURCE_REPORT_ONLY",
            },
        })
    return {
        "type": "FeatureCollection",
        "features": features,
        "monde_source_delta": {
            "basis": "APPEND_ONLY_SOURCE_REPORTS",
            "point_reports_added": len(features),
            "evidence_added": change["added"]["evidence"],
            "assertions_added": change["added"]["assertions"],
            "corrections_added": change["added"]["corrections"],
            "status": "NEW_POINT_REPORTS" if features else "NO_NEW_POINT_REPORTS",
        },
    }




def source_delta_html(before: WorldMini, after: WorldMini) -> str:
    """Open the newly recorded source Points in the existing offline map.

    No world-time snapshot is inferred: reports span their original source
    validity and knowledge times, and old assertions remain in the files.
    """
    from .map_view import render_map

    result = source_delta_geojson(before, after)
    features = result["features"]
    for feature in features:
        props = feature["properties"]
        locator = props["source_locator"]
        props.update({
            "locator": locator if isinstance(locator, str) else json.dumps(
                locator, ensure_ascii=False, sort_keys=True, allow_nan=False),
            "monde_inside_bbox": True,
            "valid_at": "ALL_SOURCE_VALIDITY_INTERVALS",
            "knowledge_cutoff": "ALL_RECORDED_KNOWLEDGE",
        })
    result["monde_bbox_query"] = {
        "basis": "SOURCE_REPORTED_POINT_BBOX_ONLY",
        "bbox": [-180, -90, 180, 90],
        "valid_at": "ALL_SOURCE_VALIDITY_INTERVALS",
        "knowledge_cutoff": "ALL_RECORDED_KNOWLEDGE",
        "total_matching_entities": len({
            feature["properties"]["entity"] for feature in features}),
        "total_source_features": len(features),
        "status": "MATCHES" if features else "NO_MATCHES",
    }
    return render_map(result)


def source_delta_csv(before: WorldMini, after: WorldMini) -> str:
    """Export every new source report, including old/new correction values.

    JSON-encoded locator/value cells retain the original types and do not
    expose untrusted source strings as spreadsheet formulas. This is a change
    in the *recorded source evidence*, not a finding of physical-world truth.
    """
    report = source_delta(before, after)
    snapshot = after.export()
    assertions = {item["id"]: item for item in snapshot["assertions"]}
    evidence = {item["id"]: item for item in snapshot["evidence"]}
    output = io.StringIO(newline="")
    rows = csv.writer(output, lineterminator="\n")
    rows.writerow([
        "world", "status", "assertion_id", "entity", "attribute", "kind",
        "source_id", "evidence_id", "source_locator_json", "captured_at",
        "source_event_at", "known_at", "valid_from", "valid_to", "supersedes",
        "previous_value_json", "reported_value_json",
    ])

    def as_json(value):
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          allow_nan=False, separators=(",", ":"))

    for item in report["new_reports"]:
        assertion = assertions[item["assertion_id"]]
        capture = evidence[item["evidence_id"]]
        parent = assertions[item["supersedes"]] if item["supersedes"] else None
        rows.writerow([
            "OBSERVED", "NEW_SOURCE_REPORT_ONLY", item["assertion_id"],
            item["entity"], item["attribute"], item["kind"],
            item["source_id"], item["evidence_id"], as_json(capture["locator"]),
            capture["captured_at"], capture["source_event_at"] or "",
            item["known_at"], item["valid_from"], item["valid_to"] or "",
            item["supersedes"] or "",
            as_json(parent["value"]) if parent else "",
            as_json(assertion["value"]),
        ])
    return output.getvalue()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare saved MONDE Mini states: source reports added, not inferred truth")
    parser.add_argument("--before", required=True, help="earlier validated WorldMini JSON")
    parser.add_argument("--after", required=True, help="later append-only WorldMini JSON")
    formats = parser.add_mutually_exclusive_group()
    formats.add_argument("--as-geojson", action="store_true",
                         help="export only newly recorded source Point reports as GeoJSON")
    formats.add_argument("--as-csv", action="store_true",
                         help="export all new reports, corrections and old/new source values as CSV")
    formats.add_argument("--as-html", action="store_true",
                         help="show newly recorded source Points on the existing offline map")
    parser.add_argument("--output", help="new HTML path for --as-html (no overwrite)")
    args = parser.parse_args(argv)
    try:
        if args.as_html != bool(args.output):
            raise ValueError("--as-html requires --output; --output is HTML-only")
        if args.as_html and any(
                Path(args.output).resolve() ==
                __import__("pathlib").Path(source).resolve()
                for source in (args.before, args.after)):
            raise ValueError("output cannot overwrite input snapshot")
        before, after = WorldMini.read(args.before), WorldMini.read(args.after)
        if args.as_html:
            page = source_delta_html(before, after)
            with open(args.output, "x", encoding="utf-8") as target:
                target.write(page)
        elif args.as_csv:
            print(source_delta_csv(before, after), end="")
        else:
            report = (source_delta_geojson(before, after) if args.as_geojson
                      else source_delta(before, after))
            print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    except (OSError, ValueError, TypeError) as exc:
        print("MONDE Mini source delta: " + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
