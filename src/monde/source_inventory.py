"""Read-only knowledge-time source inventory for a persisted MONDE Mini world."""
from __future__ import annotations

import argparse
import json
import sys

from .world import WorldMini, _time


def source_inventory(world: WorldMini, known_at: str) -> dict:
    """Count captured evidence and learned assertions, without inferring truth."""
    cutoff = _time(known_at)
    state = world.export()
    rows = {}
    evidence = {}

    for item in state["evidence"]:
        instant = _time(item["captured_at"])
        if instant > cutoff:
            continue
        evidence[item["id"]] = item
        row = rows.setdefault(item["source_id"], {
            "source_id": item["source_id"], "locators": set(),
            "evidence_count": 0, "assertion_count": 0, "entity_count": 0,
            "attribute_counts": {}, "first_captured_at": None,
            "last_captured_at": None, "first_known_at": None,
            "last_known_at": None, "_entities": set(),
        })
        row["locators"].add(item["locator"])
        row["evidence_count"] += 1
        stamp = instant.isoformat()
        row["first_captured_at"] = min(stamp, row["first_captured_at"] or stamp)
        row["last_captured_at"] = max(stamp, row["last_captured_at"] or stamp)

    for assertion in state["assertions"]:
        original = evidence.get(assertion["evidence_id"])
        if original is None:
            continue
        instant = _time(assertion["known_at"])
        if instant > cutoff:
            continue
        row = rows[original["source_id"]]
        row["assertion_count"] += 1
        row["_entities"].add(assertion["entity"])
        name = assertion["attribute"]
        row["attribute_counts"][name] = row["attribute_counts"].get(name, 0) + 1
        stamp = instant.isoformat()
        row["first_known_at"] = min(stamp, row["first_known_at"] or stamp)
        row["last_known_at"] = max(stamp, row["last_known_at"] or stamp)

    sources = []
    for name in sorted(rows):
        row = rows[name]
        row["entity_count"] = len(row.pop("_entities"))
        row["locators"] = sorted(row["locators"])
        row["attribute_counts"] = dict(sorted(row["attribute_counts"].items()))
        sources.append(row)
    return {
        "world": "OBSERVED", "status": "SOURCE_REPORTS_ONLY",
        "knowledge_cutoff": known_at,
        "totals": {"sources": len(sources),
                   "evidence": sum(r["evidence_count"] for r in sources),
                   "assertions": sum(r["assertion_count"] for r in sources)},
        "sources": sources,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect saved MONDE Mini source coverage at knowledge time")
    parser.add_argument("--state", required=True, help="saved WorldMini JSON")
    parser.add_argument("--known-at", required=True, help="inclusive timezone-aware cutoff")
    args = parser.parse_args(argv)
    try:
        world = WorldMini.read(args.state)
        print(json.dumps(source_inventory(world, args.known_at),
                         ensure_ascii=False, sort_keys=True))
    except (OSError, ValueError, TypeError) as exc:
        print("MONDE Mini source inventory: " + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
