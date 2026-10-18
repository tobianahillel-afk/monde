"""Read-only bitemporal differences in original source-reported Point positions.

A distance between reports is not actual movement, accuracy or physical truth.
"""
import argparse
from datetime import datetime
import json
from math import asin, cos, radians, sin, sqrt

from .world import WorldMini


def _instant(value):
    if not isinstance(value, str):
        raise ValueError("timestamp must be a timezone-aware ISO-8601 string")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid timestamp") from exc
    if dt.utcoffset() is None:
        raise ValueError("timezone required")
    return dt


def _distance(a, b):
    lat1, lat2 = radians(a[1]), radians(b[1])
    dlat = lat2 - lat1
    dlon = radians(((b[0] - a[0] + 540) % 360) - 180)
    h = sin(dlat / 2)**2 + cos(lat1)*cos(lat2)*sin(dlon / 2)**2
    return 6371.0088 * 2 * asin(sqrt(min(1., max(0., h))))


def _measure(left, right):
    if not left or not right:
        return None
    aa = {tuple(x["geometry"]["coordinates"]) for x in left}
    bb = {tuple(x["geometry"]["coordinates"]) for x in right}
    values = [_distance(a, b) for a in aa for b in bb]
    return {"nearest_km": round(min(values), 3),
            "farthest_km": round(max(values), 3)}


def compare_source_pair(world, source_a, source_b, at, from_known_at, to_known_at):
    """Use the existing WorldMini bitemporal GeoJSON selector and original IDs."""
    if not all(isinstance(s, str) and s for s in (source_a, source_b)) \
            or source_a == source_b:
        raise ValueError("choose two distinct original sources")
    if _instant(from_known_at) >= _instant(to_known_at):
        raise ValueError("knowledge cutoffs must increase")
    _instant(at)
    snapshots = []
    for known_at in (from_known_at, to_known_at):
        by_entity = {}
        for feature in world.export_geojson(at, known_at)["features"]:
            p = feature["properties"]
            if p["source_id"] in (source_a, source_b):
                by_entity.setdefault(p["entity"], {}).setdefault(
                    p["source_id"], []).append(feature)
        snapshots.append(by_entity)
    rows = []
    for entity in sorted(set(snapshots[0]) | set(snapshots[1])):
        periods = []
        for snapshot in snapshots:
            entry = snapshot.get(entity, {})
            a = entry.get(source_a, [])
            b = entry.get(source_b, [])
            measured = _measure(a, b)
            periods.append({"status": "JOINTLY_REPORTED" if measured
                            else "NOT_JOINTLY_REPORTED",
                            "source_a_original_reports": a,
                            "source_b_original_reports": b,
                            "separation": measured})
        earlier, later = periods
        if earlier["separation"] is None and later["separation"] is None:
            continue
        delta = None
        if earlier["separation"] and later["separation"]:
            delta = {name: round(later["separation"][name] -
                                 earlier["separation"][name], 3)
                     for name in ("nearest_km", "farthest_km")}
        rows.append({"entity": entity, "earlier": earlier, "later": later,
                     "earlier_to_later_change_km": delta})
    return {"schema": "MONDE_SOURCE_PAIR_CHANGE_V1", "source_a": source_a,
            "source_b": source_b, "valid_at": at,
            "from_known_at": from_known_at, "to_known_at": to_known_at,
            "interpretation": "Original report separation only; not verified "
                              "location, motion, accuracy, or ground truth.",
            "entities": rows}


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Compare two original source Point reports across knowledge time")
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--source-a", required=True)
    parser.add_argument("--source-b", required=True)
    parser.add_argument("--at", required=True)
    parser.add_argument("--from-known-at", required=True)
    parser.add_argument("--to-known-at", required=True)
    args = parser.parse_args(argv)
    try:
        result = compare_source_pair(
            WorldMini.read(args.fixture), args.source_a, args.source_b,
            args.at, args.from_known_at, args.to_known_at)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
