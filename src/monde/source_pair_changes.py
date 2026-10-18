"""Read-only bitemporal differences in original source-reported Point positions.

A distance between reports is not actual movement, accuracy or physical truth.
"""
import argparse
import csv
from datetime import datetime
import io
import json
from math import asin, cos, isfinite, radians, sin, sqrt

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




def comparison_geojson(document):
    """Project original source Points at two time cutoffs, never inferred motion."""
    if document["schema"] == "MONDE_SOURCE_PAIR_CHANGE_V1":
        axis = "knowledge"
        times = {"earlier": (document["valid_at"], document["from_known_at"]),
                 "later": (document["valid_at"], document["to_known_at"])}
    elif document["schema"] == "MONDE_SOURCE_PAIR_WORLD_CHANGE_V1":
        axis = "world"
        times = {"earlier": (document["from_at"], document["known_at"]),
                 "later": (document["to_at"], document["known_at"])}
    else:
        raise ValueError("unsupported source-pair comparison schema")

    features = []
    for entity in document["entities"]:
        for period in ("earlier", "later"):
            row = entity[period]
            at, known_at = times[period]
            for key in ("source_a_original_reports", "source_b_original_reports"):
                for original in row[key]:
                    properties = dict(original["properties"])
                    properties["monde_original_assertion_id"] = original["id"]
                    properties["monde_source_pair"] = {
                        "period": period, "world_at": at,
                        "knowledge_at": known_at, "status": row["status"],
                        "separation": row["separation"],
                        "earlier_to_later_change_km":
                            entity["earlier_to_later_change_km"],
                        "direction": source_pair_direction(entity),
                    }
                    features.append({
                        "type": "Feature", "id": f"{period}:{len(features)}",
                        "geometry": original["geometry"], "properties": properties,
                    })
    result = {
        "type": "FeatureCollection", "features": features,
        "monde_comparison": {
            "schema": "MONDE_SOURCE_PAIR_GEOJSON_V1",
            "comparison_schema": document["schema"], "comparison_axis": axis,
            "source_a": document["source_a"], "source_b": document["source_b"],
            "cutoffs": {
                period: {"world_at": at, "knowledge_at": known_at}
                for period, (at, known_at) in times.items()},
            "interpretation": document["interpretation"],
            "selection": document.get("selection"),
            "direction_filter": document.get("direction_filter"),
        },
    }
    if "spatial_filter" in document:
        result["monde_comparison"]["spatial_filter"] = document["spatial_filter"]
    return result


def source_pair_direction(row):
    """Classify only the nearest reported cross-source separation change."""
    change = row["earlier_to_later_change_km"]
    if change is None:
        return "incomparable"
    delta = change["nearest_km"]
    return "diverging" if delta > 0 else "converging" if delta < 0 else "unchanged"


def filter_source_pair_direction(document, direction):
    """Filter selected original records, without altering the input document."""
    if direction not in ("converging", "diverging", "unchanged", "incomparable"):
        raise ValueError("invalid reported source-pair direction")
    matched = [row for row in document["entities"]
               if source_pair_direction(row) == direction]
    return {**document, "entities": matched,
            "direction_filter": {"direction": direction,
                                 "total_entities": len(document["entities"]),
                                 "selected_entities": len(matched)}}


def top_nearest_source_pair_changes(document, limit):
    """Select material changes in original source separations, with provenance.

    Missing joint reports are incomparable, never equivalent to zero change.
    The original document and retained entity records are not modified.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise ValueError("top nearest changes must be a positive integer")
    eligible = []
    for row in document["entities"]:
        change = row["earlier_to_later_change_km"]
        if change is None:
            continue
        nearest = change["nearest_km"]
        if not isinstance(nearest, (int, float)) or not isfinite(nearest):
            raise ValueError("invalid source separation change")
        eligible.append(row)
    ranked = sorted(eligible, key=lambda row: (
        -abs(row["earlier_to_later_change_km"]["nearest_km"]), row["entity"]))
    return {**document, "entities": ranked[:limit], "selection": {
        "method": "absolute_nearest_reported_separation_change_km",
        "requested_top": limit, "eligible_entities": len(eligible),
        "total_entities": len(document["entities"]),
        "omitted_not_jointly_reported": len(document["entities"]) - len(eligible),
        "selected_entities": min(limit, len(eligible))}}



def comparison_html(document):
    """Render original pair reports in the existing offline MONDE map viewer.

    Every original report remains separate. This is a *display* envelope, not
    a new spatial query, reconstructed route, position estimate or truth claim.
    """
    from .map_view import render_map

    geojson = comparison_geojson(document)
    features = geojson["features"]
    cutoffs = geojson["monde_comparison"]["cutoffs"]
    for feature in features:
        props = feature["properties"]
        pair = props["monde_source_pair"]
        props["monde_comparison_period"] = pair["period"]
        props["monde_world_at"] = pair["world_at"]
        props["monde_known_at"] = pair["knowledge_at"]
        props["monde_original_feature_id"] = props["monde_original_assertion_id"]
        props["monde_inside_bbox"] = True

    if features:
        coords = [f["geometry"]["coordinates"] for f in features]
        # Smallest WGS84 circular longitude interval, including antimeridian.
        angles = sorted({(p[0] + 180.0) % 360.0 for p in coords})
        if len(angles) == 1:
            start = end = angles[0]
        else:
            gap = max(range(len(angles)), key=lambda i:
                      (angles[(i + 1) % len(angles)] - angles[i]) % 360.0)
            start, end = angles[(gap + 1) % len(angles)], angles[gap]
            if end < start:
                end += 360.0
        span = end - start
        padding = max(.005, span * .05)
        if span + 2 * padding >= 360.0:
            west, east = -180., 180.
        else:
            west = ((start - padding) % 360.0) - 180.0
            east = ((end + padding) % 360.0) - 180.0
        south, north = min(p[1] for p in coords), max(p[1] for p in coords)
        lat_padding = max(.005, (north - south) * .05)
        bounds = [west, max(-90., south - lat_padding),
                  east, min(90., north + lat_padding)]
    else:
        bounds = [-180., -90., 180., 90.]

    geojson["monde_comparison"]["axis"] = geojson["monde_comparison"]["comparison_axis"]
    geojson["monde_bbox_query"] = {
        "basis": "SOURCE_REPORTED_POINT_BBOX_ONLY",
        "bbox": bounds,
        "valid_at": cutoffs["earlier"]["world_at"],
        "knowledge_cutoff": cutoffs["earlier"]["knowledge_at"],
        "total_matching_entities": len({
            f["properties"]["entity"] for f in features}),
        "total_source_features": len(features),
        "status": "MATCHES" if features else "NO_MATCHES",
    }
    return render_map(geojson)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Compare two original source Point reports across knowledge time")
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--format", choices=("json", "csv", "geojson", "html"), default="json")
    parser.add_argument("--top-nearest-changes", type=int, metavar="N",
                        help="top N absolute changes in original-source nearest separation")
    parser.add_argument("--change-direction",
                        choices=("converging", "diverging", "unchanged", "incomparable"),
                        help="filter by change in original cross-source separation")
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
    if args.change_direction is not None:
        result = filter_source_pair_direction(result, args.change_direction)
    if args.top_nearest_changes is not None:
        try:
            result = top_nearest_source_pair_changes(result, args.top_nearest_changes)
        except ValueError as error:
            parser.error(str(error))
    if args.format == "csv":
        print(comparison_csv(result), end="")
    elif args.format == "geojson":
        print(json.dumps(comparison_geojson(result), ensure_ascii=False, sort_keys=True))
    elif args.format == "html":
        print(comparison_html(result))
    else:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
