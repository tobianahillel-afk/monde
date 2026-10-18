"""Read-only bitemporal differences in original source-reported Point positions.

A distance between reports is not actual movement, accuracy or physical truth.
"""
import argparse
import csv
from datetime import datetime
import io
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


def _source_pair_rows(world, source_a, source_b, cutoffs):
    """Compare original source Points at two explicitly chosen bitemporal cuts."""
    snapshots = []
    for at, known_at in cutoffs:
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
            left = entry.get(source_a, [])
            right = entry.get(source_b, [])
            measured = _measure(left, right)
            periods.append({"status": "JOINTLY_REPORTED" if measured
                            else "NOT_JOINTLY_REPORTED",
                            "source_a_original_reports": left,
                            "source_b_original_reports": right,
                            "separation": measured})
        earlier, later = periods
        if earlier["separation"] is None and later["separation"] is None:
            continue
        delta = None
        if earlier["separation"] is not None and later["separation"] is not None:
            delta = {name: round(later["separation"][name] -
                                 earlier["separation"][name], 3)
                     for name in ("nearest_km", "farthest_km")}
        rows.append({"entity": entity, "earlier": earlier, "later": later,
                     "earlier_to_later_change_km": delta})
    return rows


def _validate_sources(source_a, source_b):
    if not all(isinstance(s, str) and s for s in (source_a, source_b)) \
            or source_a == source_b:
        raise ValueError("choose two distinct original sources")


def compare_source_pair(world, source_a, source_b, at, from_known_at, to_known_at):
    """Compare evolving *knowledge* at a fixed world-valid time."""
    _validate_sources(source_a, source_b)
    if _instant(from_known_at) >= _instant(to_known_at):
        raise ValueError("knowledge cutoffs must increase")
    _instant(at)
    return {"schema": "MONDE_SOURCE_PAIR_CHANGE_V1", "source_a": source_a,
            "source_b": source_b, "valid_at": at,
            "from_known_at": from_known_at, "to_known_at": to_known_at,
            "interpretation": "Original report separation only; not verified "
                              "location, motion, accuracy, or ground truth.",
            "entities": _source_pair_rows(world, source_a, source_b,
                                          ((at, from_known_at),
                                           (at, to_known_at)))}


def compare_source_pair_world_time(world, source_a, source_b,
                                   from_at, to_at, known_at):
    """Compare reported *world validity* at one fixed knowledge cutoff.

    A separation delta is about source assertions, never actual movement.
    """
    _validate_sources(source_a, source_b)
    if _instant(from_at) >= _instant(to_at):
        raise ValueError("world times must increase")
    _instant(known_at)
    return {"schema": "MONDE_SOURCE_PAIR_WORLD_CHANGE_V1",
            "source_a": source_a, "source_b": source_b,
            "from_at": from_at, "to_at": to_at, "known_at": known_at,
            "interpretation": "Differences in source-reported world validity "
                              "only; not verified motion, location, accuracy, "
                              "or ground truth.",
            "entities": _source_pair_rows(world, source_a, source_b,
                                          ((from_at, known_at),
                                           (to_at, known_at)))}



def comparison_csv(document):
    """CSV representation of original source evidence for either time axis."""
    if document["schema"] == "MONDE_SOURCE_PAIR_CHANGE_V1":
        axis = "knowledge"
        cutoffs = {"earlier": (document["valid_at"], document["from_known_at"]),
                   "later": (document["valid_at"], document["to_known_at"])}
    elif document["schema"] == "MONDE_SOURCE_PAIR_WORLD_CHANGE_V1":
        axis = "world"
        cutoffs = {"earlier": (document["from_at"], document["known_at"]),
                   "later": (document["to_at"], document["known_at"])}
    else:
        raise ValueError("unsupported source-pair comparison schema")

    def safe(value):
        # CSV escaping is not sufficient against spreadsheet formula injection.
        return "'" + value if value.startswith(("=", "+", "-", "@", "\t", "\r", "\n")) else value

    def originals(features, field):
        values = ([f["geometry"]["coordinates"] for f in features]
                  if field == "coordinates" else
                  [f["id"] for f in features] if field == "assertion_id" else
                  [f["properties"][field] for f in features])
        return json.dumps(values, ensure_ascii=False, separators=(",", ":"))

    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("comparison_axis", "world_at", "knowledge_at", "entity",
                     "period", "source_a", "source_b", "status", "nearest_km",
                     "farthest_km", "change_nearest_km", "change_farthest_km",
                     "source_a_count", "source_b_count", "source_a_assertion_ids",
                     "source_b_assertion_ids", "source_a_evidence_ids",
                     "source_b_evidence_ids", "source_a_coordinates",
                     "source_b_coordinates"))
    for item in document["entities"]:
        for period in ("earlier", "later"):
            at, known_at = cutoffs[period]
            data = item[period]
            a = data["source_a_original_reports"]
            b = data["source_b_original_reports"]
            sep = data["separation"]
            delta = item["earlier_to_later_change_km"] if period == "later" else None
            writer.writerow((
                axis, at, known_at, safe(item["entity"]), period,
                safe(document["source_a"]), safe(document["source_b"]), data["status"],
                sep["nearest_km"] if sep is not None else "",
                sep["farthest_km"] if sep is not None else "",
                delta["nearest_km"] if delta is not None else "",
                delta["farthest_km"] if delta is not None else "",
                len(a), len(b), originals(a, "assertion_id"),
                originals(b, "assertion_id"), originals(a, "evidence_id"),
                originals(b, "evidence_id"), originals(a, "coordinates"),
                originals(b, "coordinates")))
    return output.getvalue()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Compare two original source Point reports across knowledge time")
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    parser.add_argument("--source-a", required=True)
    parser.add_argument("--source-b", required=True)
    parser.add_argument("--at", help="fixed world time for knowledge comparison")
    parser.add_argument("--from-known-at")
    parser.add_argument("--to-known-at")
    parser.add_argument("--from-at", help="earlier world time (world comparison)")
    parser.add_argument("--to-at", help="later world time (world comparison)")
    parser.add_argument("--known-at", help="fixed knowledge cutoff (world comparison)")
    args = parser.parse_args(argv)
    knowledge_args = (args.at, args.from_known_at, args.to_known_at)
    world_args = (args.from_at, args.to_at, args.known_at)
    if any(value is not None for value in world_args):
        if any(value is not None for value in knowledge_args) or \
                not all(value is not None for value in world_args):
            parser.error("choose exactly one complete comparison axis")
        compare = compare_source_pair_world_time
        cutoffs = world_args
    else:
        if not all(value is not None for value in knowledge_args):
            parser.error("provide complete --at/--from-known-at/--to-known-at")
        compare = compare_source_pair
        cutoffs = knowledge_args
    try:
        result = compare(WorldMini.read(args.fixture),
                         args.source_a, args.source_b, *cutoffs)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    if args.format == "csv":
        print(comparison_csv(result), end="")
    else:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
