"""Read-only bitemporal differences in original source-reported Point positions.

A distance between reports is not actual movement, accuracy or physical truth.
"""
import argparse
import csv
from datetime import datetime
import io
import json
from statistics import median
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




def discover_source_pairs(world, axis, cutoffs, top=25, rank="separation", source=None,
                          min_joint_entities=1):
    """Rank original source pairs by geographic separation or temporal change.

    A trend requires the same entity to be jointly reported by both original
    sources at *both* cutoffs. Missing evidence is UNKNOWN, not zero.
    """
    from itertools import combinations

    if axis not in ("knowledge", "world") or len(cutoffs) != 2:
        raise ValueError("invalid source-pair discovery axis")
    if type(top) is not int or not 1 <= top <= 100:
        raise ValueError("invalid source-pair discovery limit")
    if rank not in ("separation", "coverage", "median", "increasing", "decreasing"):
        raise ValueError("invalid source-pair discovery ranking")
    if source is not None and (not isinstance(source, str) or not source):
        raise ValueError("invalid original source focus")
    if type(min_joint_entities) is not int or not 1 <= min_joint_entities <= 10000:
        raise ValueError("invalid minimum joint entities")
    for at, known_at in cutoffs:
        _instant(at)
        _instant(known_at)
    (at1, known1), (at2, known2) = cutoffs
    if axis == "knowledge":
        if at1 != at2 or _instant(known1) >= _instant(known2):
            raise ValueError("invalid discovery knowledge cutoffs")
    elif known1 != known2 or _instant(at1) >= _instant(at2):
        raise ValueError("invalid discovery world cutoffs")

    pairs = {}
    for period, (at, known_at) in zip(("earlier", "later"), cutoffs):
        by_entity = {}
        for feature in world.export_geojson(at, known_at)["features"]:
            prop = feature["properties"]
            by_entity.setdefault(prop["entity"], {}).setdefault(
                prop["source_id"], []).append(feature)
        for entity, reporters in by_entity.items():
            if source is None:
                relevant_pairs = combinations(sorted(reporters), 2)
            elif source in reporters:
                relevant_pairs = ((min(source, other), max(source, other))
                                  for other in sorted(reporters) if other != source)
            else:
                continue
            for sa, sb in relevant_pairs:
                measured = _measure(reporters[sa], reporters[sb])
                if measured is None:
                    continue
                item = pairs.setdefault((sa, sb), {
                    "source_a": sa, "source_b": sb,
                    "joint_earlier_entities": 0, "joint_later_entities": 0,
                    "max_nearest_km": 0.0, "example_entity": None,
                    "example_period": None, "example_assertion_ids": [],
                    "_entities": set(),
                    **({"_median_entity_km": {}} if rank == "median" else {}),
                })
                if rank in ("increasing", "decreasing"):
                    item.setdefault("_cutoff_evidence", {}).setdefault(
                        entity, {})[period] = {
                        "nearest_km": measured["nearest_km"],
                        "assertion_ids": sorted(
                            feature["id"] for source in (sa, sb)
                            for feature in reporters[source]),
                    }
                item["_entities"].add(entity)
                item["joint_" + period + "_entities"] += 1
                distance = measured["nearest_km"]
                if rank == "median":
                    values = item["_median_entity_km"]
                    values[entity] = max(distance, values.get(entity, 0.0))
                if item["example_entity"] is None or distance > item["max_nearest_km"]:
                    item["max_nearest_km"] = distance
                    item["example_entity"] = entity
                    item["example_period"] = period
                    item["example_assertion_ids"] = sorted(
                        feature["id"] for source in (sa, sb)
                        for feature in reporters[source])

    ranked = []
    for item in pairs.values():
        item["joint_entities"] = len(item.pop("_entities"))
        if rank == "median":
            # Count each entity once even when observed at both cutoffs.
            item["median_nearest_km"] = round(
                median(item.pop("_median_entity_km").values()), 3)
        if rank in ("increasing", "decreasing"):
            samples = item.pop("_cutoff_evidence", {})
            comparable = []
            for entity, periods in samples.items():
                if set(periods) != {"earlier", "later"}:
                    continue
                delta = round(periods["later"]["nearest_km"] -
                              periods["earlier"]["nearest_km"], 3)
                comparable.append((delta, entity, periods))
            matches = ([entry for entry in comparable if entry[0] > 0]
                       if rank == "increasing" else
                       [entry for entry in comparable if entry[0] < 0])
            if not matches:
                continue
            delta, entity, periods = sorted(
                matches, key=lambda entry: (-abs(entry[0]), entry[1]))[0]
            item.update(rank_delta_km=delta,
                        comparable_entities=len(comparable),
                        matching_entities=len(matches),
                        example_entity=entity,
                        example_period="both",
                        example_earlier_assertion_ids=periods["earlier"]["assertion_ids"],
                        example_later_assertion_ids=periods["later"]["assertion_ids"],
                        example_assertion_ids=sorted(set(
                            periods["earlier"]["assertion_ids"] +
                            periods["later"]["assertion_ids"])))
        evidence_count = (item["joint_entities"] if rank in ("separation", "coverage", "median")
                          else item["comparable_entities"])
        if evidence_count < min_joint_entities:
            continue
        ranked.append(item)
    if rank == "separation":
        ranked.sort(key=lambda item: (
            -item["max_nearest_km"], -item["joint_entities"],
            item["source_a"], item["source_b"]))
    elif rank == "coverage":
        ranked.sort(key=lambda item: (
            -item["joint_entities"], -item["max_nearest_km"],
            item["source_a"], item["source_b"]))
    elif rank == "median":
        ranked.sort(key=lambda item: (
            -item["median_nearest_km"], -item["joint_entities"],
            item["source_a"], item["source_b"]))
    else:
        ranked.sort(key=lambda item: (
            -abs(item["rank_delta_km"]), -item["matching_entities"],
            item["source_a"], item["source_b"]))
    result = {
        "schema": "MONDE_SOURCE_PAIR_DISCOVERY_V1",
        "axis": axis, "cutoffs": {
            period: {"world_at": at, "knowledge_at": known_at}
            for period, (at, known_at) in zip(("earlier", "later"), cutoffs)
        },
        "interpretation": ("Original source-reported Point differences only; "
                           "not verified accuracy, agreement, movement, or truth. "
                           "Missing joint reports are UNKNOWN, not zero."),
        "total_pairs": len(ranked), "top": top, "pairs": ranked[:top],
    }
    if source is not None:
        result["source_focus"] = source
    if min_joint_entities != 1:
        result["min_joint_entities"] = min_joint_entities
    if rank != "separation":
        result["rank"] = rank
        if rank == "coverage":
            result["interpretation"] += (
                " Coverage counts distinct entities jointly reported by both"
                " sources at either cutoff; it measures original observation"
                " overlap, not verified source reliability.")
        elif rank == "median":
            result["interpretation"] += (
                " Median nearest separation uses one largest observed distance"
                " per jointly reported entity across the two cutoffs; it is"
                " robust to a single extreme outlier, not ground truth.")
        else:
            result["interpretation"] += (
                " Trends compare the same entity at both cutoffs, retaining"
                " original assertion IDs; unpaired observations are UNKNOWN.")
    return result


def discovery_geojson(world, document):
    """Original Point evidence for all ranked source-pair examples, never inferred coordinates."""
    if document["schema"] != "MONDE_SOURCE_PAIR_DISCOVERY_V1":
        raise ValueError("unsupported source-pair discovery schema")
    by_period = {}
    for period in ("earlier", "later"):
        cutoff = document["cutoffs"][period]
        index = {}
        for original in world.export_geojson(
                cutoff["world_at"], cutoff["knowledge_at"])["features"]:
            props = original["properties"]
            index.setdefault((props["entity"], props["source_id"]), []).append(original)
        by_period[period] = index
    features = []
    for rank, pair in enumerate(document["pairs"], 1):
        for period in ("earlier", "later"):
            cutoff = document["cutoffs"][period]
            for source in (pair["source_a"], pair["source_b"]):
                for original in by_period[period].get((pair["example_entity"], source), []):
                    properties = dict(original["properties"])
                    properties["monde_original_assertion_id"] = original["id"]
                    properties["monde_discovery"] = {
                        "rank": rank, "source_a": pair["source_a"],
                        "source_b": pair["source_b"],
                        "example_entity": pair["example_entity"],
                        "period": period, "world_at": cutoff["world_at"],
                        "knowledge_at": cutoff["knowledge_at"],
                        "max_nearest_km": pair["max_nearest_km"],
                        "rank_delta_km": pair.get("rank_delta_km"),
                    }
                    if "median_nearest_km" in pair:
                        properties["monde_discovery"]["median_nearest_km"] = (
                            pair["median_nearest_km"])
                    features.append({
                        "type": "Feature",
                        "id": f"{rank}:{period}:{original['id']}",
                        "geometry": original["geometry"], "properties": properties,
                    })
    output = {
        "type": "FeatureCollection", "features": features,
        "monde_discovery": {
            "schema": "MONDE_SOURCE_PAIR_DISCOVERY_GEOJSON_V1",
            "axis": document["axis"], "cutoffs": document["cutoffs"],
            "rank": document.get("rank", "separation"),
            "source_focus": document.get("source_focus"),
            "total_pairs": document["total_pairs"],
            "exported_pairs": len(document["pairs"]),
            "interpretation": document["interpretation"],
        },
    }
    if "min_joint_entities" in document:
        output["monde_discovery"]["min_joint_entities"] = document["min_joint_entities"]
    return output


def discovery_csv(document):
    """Export ranked original reporter evidence at both temporal cutoffs."""
    if document["schema"] != "MONDE_SOURCE_PAIR_DISCOVERY_V1":
        raise ValueError("unsupported source-pair discovery schema")

    def safe(value):
        text = str(value)
        return "'" + text if text.startswith(("=", "+", "-", "@", "\t", "\r", "\n")) else text

    def ids(item, key):
        return json.dumps(item.get(key, []), ensure_ascii=False,
                          separators=(",", ":"))

    early = document["cutoffs"]["earlier"]
    late = document["cutoffs"]["later"]
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    median_fields = (("median_nearest_km",)
                     if document.get("rank") == "median" else ())
    writer.writerow((
        "axis", "earlier_world_at", "earlier_knowledge_at",
        "later_world_at", "later_knowledge_at", "ranking",
        "source_focus", "total_pairs", "source_a", "source_b",
        "max_nearest_km", "rank_delta_km", "joint_entities",
        "joint_earlier_entities", "joint_later_entities",
        "comparable_entities", "matching_entities",
        "example_entity", "example_period",
        "example_assertion_ids", "example_earlier_assertion_ids",
        "example_later_assertion_ids") + median_fields)
    for item in document["pairs"]:
        writer.writerow((
            document["axis"], early["world_at"], early["knowledge_at"],
            late["world_at"], late["knowledge_at"],
            document.get("rank", "separation"),
            safe(document.get("source_focus", "")), document["total_pairs"],
            safe(item["source_a"]), safe(item["source_b"]),
            item["max_nearest_km"], item.get("rank_delta_km", ""),
            item["joint_entities"], item["joint_earlier_entities"],
            item["joint_later_entities"], item.get("comparable_entities", ""),
            item.get("matching_entities", ""), safe(item["example_entity"]),
            item["example_period"], ids(item, "example_assertion_ids"),
            ids(item, "example_earlier_assertion_ids"),
            ids(item, "example_later_assertion_ids")) +
            ((item["median_nearest_km"],) if median_fields else ()))
    return output.getvalue()


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
    if "persistent_separation_filter" in document:
        result["monde_comparison"]["persistent_separation_filter"] = (
            document["persistent_separation_filter"])
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



def discovery_html(world, document):
    """Render all ranked source-pair examples in the existing offline viewer."""
    geojson = discovery_geojson(world, document)
    geojson["monde_comparison"] = {
        "schema": "MONDE_SOURCE_PAIR_DISCOVERY_MAP_V1",
        "comparison_axis": document["axis"],
        "cutoffs": document["cutoffs"],
        "interpretation": document["interpretation"],
    }
    for feature in geojson["features"]:
        info = feature["properties"]["monde_discovery"]
        feature["properties"]["monde_source_pair"] = {
            "period": info["period"],
            "world_at": info["world_at"],
            "knowledge_at": info["knowledge_at"],
        }
    return _source_pair_map(geojson)


def comparison_html(document):
    """Render one original source pair via the shared offline map viewer."""
    return _source_pair_map(comparison_geojson(document))


def _source_pair_map(geojson):
    """Only derive a map display envelope; never infer source truth."""
    from .map_view import render_map

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
