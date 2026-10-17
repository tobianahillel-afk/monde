"""Compare two validated MONDE Mini snapshots without erasing source ancestry.

A delta describes newly *recorded source reports*, never a change to verified
physical reality. Append-only prefix checking rejects an unrelated or rewritten
history, even if its headline counts happen to agree.
"""
from __future__ import annotations

import argparse
import json
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare saved MONDE Mini states: source reports added, not inferred truth")
    parser.add_argument("--before", required=True, help="earlier validated WorldMini JSON")
    parser.add_argument("--after", required=True, help="later append-only WorldMini JSON")
    args = parser.parse_args(argv)
    try:
        report = source_delta(WorldMini.read(args.before), WorldMini.read(args.after))
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    except (OSError, ValueError, TypeError) as exc:
        print("MONDE Mini source delta: " + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
