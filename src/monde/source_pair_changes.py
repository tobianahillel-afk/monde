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



def source_directory(world, axis, cutoffs, change=None, rank=None, source_prefix=None,
                     entity=None):
    """Per-original-source Point coverage and optional evidence-based ranking."""
    if change not in (None, "new", "gone", "both"):
        raise ValueError("invalid source reporting transition")
    if rank not in (None, "new", "gone", "turnover", "net-gain", "net-loss"):
        raise ValueError("invalid original source coverage ranking")
    if source_prefix is not None:
        if (not isinstance(source_prefix, str) or not source_prefix or
                len(source_prefix) > 80 or not source_prefix.isascii() or
                not all(c.isalnum() or c in "._:-" for c in source_prefix)):
            raise ValueError("invalid source directory prefix")
    if entity is not None and (not isinstance(entity, str) or
            not 0 < len(entity) <= 200 or any(ord(c) < 32 or ord(c) == 127
                                               for c in entity)):
        raise ValueError("invalid original entity filter")
    if axis not in ("knowledge", "world") or len(cutoffs) != 2:
        raise ValueError("invalid source directory axis")
    for at, known_at in cutoffs:
        _instant(at)
        _instant(known_at)
    (first_at, first_known), (last_at, last_known) = cutoffs
    if axis == "knowledge":
        if first_at != last_at or _instant(first_known) >= _instant(last_known):
            raise ValueError("invalid source directory knowledge cutoffs")
    elif first_known != last_known or _instant(first_at) >= _instant(last_at):
        raise ValueError("invalid source directory world cutoffs")

    periods = {}
    for label, (at, known_at) in zip(("earlier", "later"), cutoffs):
        sources = {}
        for feature in world.export_geojson(at, known_at)["features"]:
            properties = feature["properties"]
            sources.setdefault(properties["source_id"], {}).setdefault(
                properties["entity"], set()).add(feature["id"])
        periods[label] = sources

    result = []
    for source in sorted(set(periods["earlier"]) | set(periods["later"])):
        earlier = periods["earlier"].get(source, {})
        later = periods["later"].get(source, {})
        a, b = set(earlier), set(later)
        example = entity if entity is not None and entity in (a | b) else min(a | b)
        result.append({
            "source_id": source,
            "earlier_entities": len(a),
            "later_entities": len(b),
            "earlier_assertions": sum(map(len, earlier.values())),
            "later_assertions": sum(map(len, later.values())),
            "continuously_reported_entities": len(a & b),
            "newly_reported_entities": len(b - a),
            "no_longer_reported_entities": len(a - b),
            "example_entity": example,
            "example_assertion_ids": sorted(
                earlier.get(example, set()) | later.get(example, set())),
        })
    result.sort(key=lambda row: (-max(row["earlier_entities"],
                                     row["later_entities"]), row["source_id"]))
    available_sources = len(result)
    if entity is not None:
        result = [row for row in result if row["example_entity"] == entity]
    if source_prefix is not None:
        result = [row for row in result if row["source_id"].startswith(source_prefix)]
    if change is not None:
        field = {"new": "newly_reported_entities",
                 "gone": "no_longer_reported_entities",
                 "both": "continuously_reported_entities"}[change]
        result = [row for row in result if row[field] > 0]
    if rank is not None:
        # Count original entities, not observations/assertions or inferred events.
        # Secondary source ID ensures stable ranking across requests and exports.
        count = {
            "new": lambda row: row["newly_reported_entities"],
            "gone": lambda row: row["no_longer_reported_entities"],
            "turnover": lambda row: (row["newly_reported_entities"] +
                                     row["no_longer_reported_entities"]),
            "net-gain": lambda row: (row["later_entities"] -
                                      row["earlier_entities"]),
            "net-loss": lambda row: (row["earlier_entities"] -
                                      row["later_entities"]),
        }[rank]
        result.sort(key=lambda row: (-count(row), row["source_id"]))
    document = {
        "schema": "MONDE_SOURCE_COVERAGE_DIRECTORY_V1",
        "axis": axis,
        "cutoffs": {
            name: {"world_at": at, "knowledge_at": known_at}
            for name, (at, known_at) in zip(("earlier", "later"), cutoffs)
        },
        "interpretation": (
            "Original source-reported Point coverage only. Changes in reported "
            "entities are not verified movement, accuracy, or actual events."
        ),
        "total_sources": len(result),
        "sources": result,
    }
    if change is not None:
        document["reporting_filter"] = change
    if source_prefix is not None:
        document["source_prefix"] = source_prefix
    if entity is not None:
        document["entity_focus"] = entity
        document["interpretation"] += (
            " Selected sources reported this exact original entity at either"
            " cutoff; coverage counts still include all source entities.")
    if change is not None or source_prefix is not None or entity is not None:
        document["available_sources"] = available_sources
    if rank is not None:
        document["ranking"] = rank
    return document



def source_directory_detail(world, axis, cutoffs, source, change=None):
    """Show original assertion IDs, optionally limited by reporting transition."""
    filters = {"new": "NEWLY_REPORTED", "gone": "NO_LONGER_REPORTED",
               "both": "REPORTED_AT_BOTH"}
    if change is not None and change not in filters:
        raise ValueError("invalid original reporting transition")
    if not isinstance(source, str) or not 0 < len(source) <= 200 or any(
            ord(ch) < 32 or ord(ch) == 127 for ch in source):
        raise ValueError("invalid original reporter")
    directory = source_directory(world, axis, cutoffs)
    before, after = {}, {}
    for found, (at, known_at) in zip((before, after), cutoffs):
        for feature in world.export_geojson(at, known_at)["features"]:
            props = feature["properties"]
            if props["source_id"] == source:
                found.setdefault(props["entity"], set()).add(feature["id"])
    rows = []
    for entity in sorted(before.keys() | after.keys()):
        earlier = sorted(before.get(entity, set()))
        later = sorted(after.get(entity, set()))
        rows.append({
            "entity": entity,
            "status": ("REPORTED_AT_BOTH" if earlier and later else
                       "NEWLY_REPORTED" if later else "NO_LONGER_REPORTED"),
            "earlier_assertion_ids": earlier,
            "later_assertion_ids": later,
        })
    if change is not None:
        rows = [row for row in rows if row["status"] == filters[change]]
    result = {
        "schema": "MONDE_SOURCE_COVERAGE_DETAIL_V1",
        "axis": axis, "cutoffs": directory["cutoffs"],
        "source_id": source, "interpretation": directory["interpretation"],
        "earlier_entities": len(before), "later_entities": len(after),
        "entities": rows,
    }
    if change is not None:
        result["reporting_filter"] = change
        result["matched_entities"] = len(rows)
    return result



def source_directory_geojson(world, detail):
    """Export original source Points at two cutoffs, never inferred truth."""
    if detail.get("schema") != "MONDE_SOURCE_COVERAGE_DETAIL_V1":
        raise ValueError("unsupported source coverage detail")
    allowed = {row["entity"]: row for row in detail["entities"]}
    features = []
    for period in ("earlier", "later"):
        cutoff = detail["cutoffs"][period]
        at, known_at = cutoff["world_at"], cutoff["knowledge_at"]
        ids = {entity: set(row[period + "_assertion_ids"])
               for entity, row in allowed.items()}
        for original in world.export_geojson(at, known_at)["features"]:
            props = original["properties"]
            if (props["source_id"] != detail["source_id"] or
                    original["id"] not in ids.get(props["entity"], ())):
                continue
            metadata = dict(props)
            metadata.update(
                monde_original_assertion_id=original["id"],
                monde_comparison_period=period,
                monde_world_at=at,
                monde_known_at=known_at,
                monde_reported_coverage_status=allowed[props["entity"]]["status"])
            features.append({
                "type": "Feature", "id": period + ":" + str(original["id"]),
                "geometry": original["geometry"], "properties": metadata,
            })
    coverage = {
        "schema": "MONDE_SOURCE_COVERAGE_GEOJSON_V1",
        "source_id": detail["source_id"], "axis": detail["axis"],
        "cutoffs": detail["cutoffs"], "interpretation": detail["interpretation"],
        "original_feature_count": len(features),
        "matched_entities": len(allowed),
    }
    if "reporting_filter" in detail:
        coverage["reporting_filter"] = detail["reporting_filter"]
    return {"type": "FeatureCollection", "features": features,
            "monde_source_coverage": coverage}


def source_directory_map(world, detail):
    """Display both original reporting periods without inferring physical motion."""
    geojson = source_directory_geojson(world, detail)
    features = geojson["features"]
    for feature in features:
        feature["properties"]["monde_inside_bbox"] = True
    earlier = detail["cutoffs"]["earlier"]
    geojson["monde_bbox_query"] = {
        "basis": "SOURCE_REPORTED_POINT_BBOX_ONLY",
        "bbox": _source_display_bbox(features),
        "valid_at": earlier["world_at"],
        "knowledge_cutoff": earlier["knowledge_at"],
        "total_matching_entities": len({
            feature["properties"]["entity"] for feature in features}),
        "total_source_features": len(features),
        "status": "MATCHES" if features else "NO_MATCHES",
    }
    geojson["monde_source_coverage"]["display_basis"] = (
        "BOTH_ORIGINAL_REPORTING_PERIODS_NOT_VERIFIED_MOVEMENT")
    return geojson


def source_directory_entity_geojson(world, directory, presence=None):
    """Preserve original Point reports, optionally select temporal visibility."""
    if (directory.get("schema") != "MONDE_SOURCE_COVERAGE_DIRECTORY_V1" or
            "entity_focus" not in directory):
        raise ValueError("original entity reporter directory required")
    selected = {row["source_id"]: set(row["example_assertion_ids"])
                for row in directory["sources"]}
    entity = directory["entity_focus"]
    features = []
    for period in ("earlier", "later"):
        cutoff = directory["cutoffs"][period]
        at, known_at = cutoff["world_at"], cutoff["knowledge_at"]
        for original in world.export_geojson(at, known_at)["features"]:
            props = original["properties"]
            if (props["entity"] != entity or
                    original["id"] not in selected.get(props["source_id"], ())):
                continue
            metadata = dict(props)
            metadata.update(monde_original_assertion_id=original["id"],
                            monde_comparison_period=period,
                            monde_world_at=at, monde_known_at=known_at)
            features.append({
                "type": "Feature", "id": period + ":" + str(original["id"]),
                "geometry": original["geometry"], "properties": metadata,
            })
    if presence is not None:
        if presence not in ("earlier", "later", "both"):
            raise ValueError("invalid original report presence filter")
        # Identity combines original reporter, assertion, evidence and Point.
        # Never infer movement or a consensus position from a source update.
        periods = {}
        for feature in features:
            p = feature["properties"]
            identity = (p["source_id"], p["monde_original_assertion_id"],
                        p["evidence_id"], tuple(feature["geometry"]["coordinates"]))
            periods.setdefault(identity, set()).add(p["monde_comparison_period"])
        selected = []
        for feature in features:
            p = feature["properties"]
            identity = (p["source_id"], p["monde_original_assertion_id"],
                        p["evidence_id"], tuple(feature["geometry"]["coordinates"]))
            periods_seen = periods[identity]
            classification = ("both" if len(periods_seen) == 2 else
                              "earlier" if "earlier" in periods_seen else "later")
            if classification == presence:
                p["monde_visibility_transition"] = {
                    "earlier": "EARLIER_ONLY",
                    "later": "LATER_ONLY",
                    "both": "BOTH_CUTOFFS",
                }[classification]
                selected.append(feature)
        features = selected
    return {
        "type": "FeatureCollection", "features": features,
        "monde_source_coverage": {
            "schema": "MONDE_ENTITY_REPORTERS_GEOJSON_V1",
            "entity_focus": entity, "axis": directory["axis"],
            "cutoffs": directory["cutoffs"],
            "selected_sources": len(selected),
            **({"source_focus": directory["source_focus"]}
               if "source_focus" in directory else {}),
            "original_feature_count": len(features),
            **({"presence_filter": presence} if presence is not None else {}),
            "interpretation": directory["interpretation"],
        },
    }



def source_directory_entity_assertions_csv(world, directory):
    """One original Point per row, across all selected entity reporters/cutoffs.

    Reuses the already-proven entity GeoJSON selection. CSV is for inspection,
    not for establishing consensus or transforming stored source assertions.
    """
    geojson = source_directory_entity_geojson(world, directory)

    def safe(value):
        value = str(value)
        # Quoting CSV cells is insufficient against spreadsheet formulas.
        return "'" + value if value.startswith(("=", "+", "-", "@", "\t", "\r", "\n")) else value

    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(("entity", "source_id", "period", "world_at", "known_at",
                     "assertion_id", "evidence_id", "longitude", "latitude"))
    for feature in geojson["features"]:
        props = feature["properties"]
        longitude, latitude = feature["geometry"]["coordinates"]
        writer.writerow((safe(props["entity"]), safe(props["source_id"]),
                         props["monde_comparison_period"], props["monde_world_at"],
                         props["monde_known_at"],
                         safe(props["monde_original_assertion_id"]),
                         safe(props["evidence_id"]), longitude, latitude))
    return output.getvalue()



def source_directory_entity_presence_summary(world, directory):
    """Distinct original report identities per reporter at both cutoffs."""
    features = source_directory_entity_geojson(world, directory)["features"]
    seen = {}
    for feature in features:
        p = feature["properties"]
        identity = (p["source_id"], p["monde_original_assertion_id"],
                    p["evidence_id"], tuple(feature["geometry"]["coordinates"]))
        seen.setdefault(identity, set()).add(p["monde_comparison_period"])
    rows = {item["source_id"]: {"source_id": item["source_id"],
            "earlier_only": 0, "later_only": 0, "both_cutoffs": 0}
            for item in directory["sources"]}
    for identity, periods in seen.items():
        category = ("both_cutoffs" if len(periods) == 2 else
                    "earlier_only" if "earlier" in periods else "later_only")
        rows[identity[0]][category] += 1
    return [rows[source] for source in sorted(rows)]


def source_directory_entity_presence_records(world, directory, presence=None):
    """Return unmodified original Point identities with temporal visibility."""
    if presence is not None and presence not in ("earlier", "later", "both"):
        raise ValueError("invalid original report presence filter")
    features = source_directory_entity_geojson(world, directory)["features"]
    reports = {}
    for feature in features:
        p = feature["properties"]
        lon, lat = feature["geometry"]["coordinates"]
        identity = (p["source_id"], p["monde_original_assertion_id"],
                    p["evidence_id"], lon, lat)
        reports.setdefault(identity, set()).add(p["monde_comparison_period"])
    rows = []
    for identity in sorted(reports, key=lambda row: tuple(map(str, row))):
        source, assertion, evidence, lon, lat = identity
        before, after = ("earlier" in reports[identity], "later" in reports[identity])
        transition = ("BOTH_CUTOFFS" if before and after else
                      "EARLIER_ONLY" if before else "LATER_ONLY")
        if presence is not None and transition != {
                "earlier": "EARLIER_ONLY", "later": "LATER_ONLY",
                "both": "BOTH_CUTOFFS"}[presence]:
            continue
        rows.append({"entity": directory["entity_focus"],
                     "source_id": source, "assertion_id": assertion,
                     "evidence_id": evidence, "longitude": lon, "latitude": lat,
                     "earlier_visible": before, "later_visible": after,
                     "visibility_transition": transition})
    return rows


def source_directory_entity_presence_json(world, directory, presence=None):
    """Machine-readable original source Point presence, not inferred truth."""
    rows = source_directory_entity_presence_records(world, directory, presence)
    return {"schema": "MONDE_ORIGINAL_POINT_PRESENCE_V1",
            "entity": directory["entity_focus"],
            "axis": directory["axis"],
            "cutoffs": directory["cutoffs"],
            **({"source_focus": directory["source_focus"]}
               if "source_focus" in directory else {}),
            **({"presence_filter": presence} if presence is not None else {}),
            "report_count": len(rows),
            "reports": rows,
            "interpretation": "Original source-report visibility, not verified movement or truth"}


def source_directory_entity_presence_csv(world, directory, presence=None):
    """Spreadsheet-safe original presence CSV, from the shared report identities."""
    reports = source_directory_entity_presence_records(world, directory, presence)

    def safe(value):
        value = str(value)
        return "'" + value if value.startswith(("=", "+", "-", "@", "\t", "\r", "\n")) else value

    early = directory["cutoffs"]["earlier"]
    late = directory["cutoffs"]["later"]
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(("entity", "source_id", "assertion_id", "evidence_id",
                     "longitude", "latitude", "earlier_visible", "later_visible",
                     "visibility_transition", "earlier_world_at", "earlier_known_at",
                     "later_world_at", "later_known_at"))
    for r in reports:
        writer.writerow((safe(r["entity"]), safe(r["source_id"]),
                         safe(r["assertion_id"]), safe(r["evidence_id"]),
                         r["longitude"], r["latitude"],
                         int(r["earlier_visible"]), int(r["later_visible"]),
                         r["visibility_transition"], early["world_at"],
                         early["knowledge_at"], late["world_at"], late["knowledge_at"]))
    return output.getvalue()


def source_directory_entity_map(world, directory, presence=None):
    """Reuse the original Point map for selected temporal visibility."""
    geojson = source_directory_entity_geojson(world, directory, presence)
    features = geojson["features"]
    for feature in features:
        feature["properties"]["monde_inside_bbox"] = True
    earlier = directory["cutoffs"]["earlier"]
    geojson["monde_bbox_query"] = {
        "basis": "SOURCE_REPORTED_POINT_BBOX_ONLY",
        "bbox": _source_display_bbox(features),
        "valid_at": earlier["world_at"],
        "knowledge_cutoff": earlier["knowledge_at"],
        "total_matching_entities": 1 if features else 0,
        "total_source_features": len(features),
        "status": "MATCHES" if features else "NO_MATCHES",
    }
    geojson["monde_source_coverage"]["display_basis"] = (
        "ORIGINAL_REPORTS_AT_BOTH_CUTOFFS_NOT_CONSENSUS_LOCATION")
    return geojson


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


def _source_display_bbox(features):
    """Smallest source Point longitude arc for a display viewport only."""
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

    return bounds


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

    bounds = _source_display_bbox(features)

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
