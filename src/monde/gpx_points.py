"""Bounded local GPX 1.1 Point claims, including source-ordered GPS traces.

GPX traces are preserved as a sequence of source-reported sample positions,
not as verified movement, a road, a physically continuous path, or a durable
identity for a real object. Source sample IDs retain repeated readings.
"""
import hashlib
import json
import math
import os
import xml.etree.ElementTree as ET

from .world import _id, _time

MAX_BYTES = 10_000_000
MAX_POINTS = 50_000
NAMESPACE = "{http://www.topografix.com/GPX/1/1}"


def _tag(name):
    return NAMESPACE + name


def _text(node, field, *, required=False):
    values = node.findall(_tag(field))
    if len(values) > 1:
        raise ValueError("duplicate GPX " + field)
    if not values:
        if required:
            raise ValueError("GPX requires " + field)
        return None
    child = values[0]
    if child.attrib or len(child):
        raise ValueError("nested or attributed GPX " + field)
    value = child.text or ""
    if not value or len(value) > 4000:
        raise ValueError("missing or oversized GPX " + field)
    return value


def _point(node, kind):
    if set(node.attrib) != {"lat", "lon"}:
        raise ValueError("GPX " + kind + " requires only lon/lat")
    try:
        lat, lon = float(node.get("lat")), float(node.get("lon"))
    except ValueError as exc:
        raise ValueError("non-numeric GPX coordinates") from exc
    if not math.isfinite(lat) or not math.isfinite(lon) or not (
            -90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("GPX coordinate is outside WGS84")
    fields = {"name": "name", "desc": "description", "cmt": "comment",
              "time": "waypoint_time", "ele": "elevation_m",
              "sym": "symbol", "type": "waypoint_type"}
    attrs = {}
    seen = set()
    for child in node:
        field = child.tag[len(NAMESPACE):] if child.tag.startswith(NAMESPACE) else ""
        if field not in fields or field in seen or child.attrib or len(child):
            raise ValueError("unsupported or ambiguous GPX " + kind + " field")
        seen.add(field)
        value = child.text or ""
        if len(value) > 4000:
            raise ValueError("GPX property too long")
        if field == "time" and value.strip():
            _time(value.strip())  # Timestamp from source, not physical validity.
        if field == "ele":
            try:
                elevation = float(value.strip())
            except ValueError as exc:
                raise ValueError("invalid GPX elevation") from exc
            if not math.isfinite(elevation):
                raise ValueError("non-finite GPX elevation")
            attrs["elevation_m"] = elevation  # Source-reported, not verified height.
        elif value:
            attrs[fields[field]] = value
    return [lon, lat], attrs


def _sample_id(kind, trace, coordinates, attrs):
    # This ID represents source sample content, NEVER a real-world entity.
    # A repeated identical sample receives an occurrence suffix below.
    stable = json.dumps([kind, trace, coordinates,
                         attrs.get("waypoint_time"), attrs.get("name")],
                        ensure_ascii=False, separators=(",", ":"))
    return "gpx-sample-" + hashlib.sha256(stable.encode("utf-8")).hexdigest()[:32]


def to_geojson(path):
    """Convert local GPX waypoints, routes and tracks to reported Point samples.

    Routes/tracks require unique source-provided names. Topology is carried in
    gpx_trace properties and visualized only between consecutive samples of
    the same source trace and segment; no implied observed physical motion.
    """
    if os.path.getsize(path) > MAX_BYTES:
        raise ValueError("GPX exceeds 10 MB limit")
    with open(path, "rb") as file:
        raw = file.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("GPX exceeds 10 MB limit")
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("GPX XML entity declarations and DTD are forbidden")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError("invalid GPX XML") from exc
    if root.tag != _tag("gpx") or root.get("version") != "1.1":
        raise ValueError("expected standard GPX 1.1")
    if any(child.tag not in {_tag("metadata"), _tag("wpt"),
                            _tag("rte"), _tag("trk")} for child in root):
        raise ValueError("unsupported GPX root element")
    features, seen, traces, occurrences = [], set(), set(), {}

    def append(ident, coords, properties):
        if len(features) >= MAX_POINTS:
            raise ValueError("GPX point limit exceeded")
        _id(ident)
        if ident in seen:
            raise ValueError("ambiguous duplicate GPX sample identity")
        seen.add(ident)
        features.append({"type": "Feature", "id": ident,
                         "properties": properties,
                         "geometry": {"type": "Point", "coordinates": coords}})

    for waypoint in root.findall(_tag("wpt")):
        coords, properties = _point(waypoint, "waypoint")
        ident = properties.get("name")
        if ident is None or ident != ident.strip():
            raise ValueError("GPX waypoint needs source-supplied stable name")
        append(ident, coords, properties)

    for kind in ("rte", "trk"):
        for trace in root.findall(_tag(kind)):
            if trace.attrib:
                raise ValueError("unsupported GPX trace attributes")
            name = _text(trace, "name", required=True)
            # Source-supplied name is a dataset-local trace label, not identity
            # of a verified physical route. No row-order-generated trace ID.
            if name != name.strip() or not name.strip():
                raise ValueError("ambiguous GPX trace name")
            if (kind, name) in traces:
                raise ValueError("duplicate GPX trace name")
            traces.add((kind, name))
            trace_id = hashlib.sha256(json.dumps(
                [kind, name], ensure_ascii=False).encode("utf-8")).hexdigest()[:24]
            if any(child.tag not in ({_tag("name"), _tag("desc"), _tag("rtept")}
                                     if kind == "rte" else
                                     {_tag("name"), _tag("desc"), _tag("trkseg")})
                   for child in trace):
                raise ValueError("unsupported GPX route/track content")
            description = _text(trace, "desc")
            if kind == "rte":
                segments = [list(trace.findall(_tag("rtept")))]
            else:
                segments = []
                for segment in trace.findall(_tag("trkseg")):
                    if segment.attrib or any(p.tag != _tag("trkpt") for p in segment):
                        raise ValueError("unsupported GPX track segment content")
                    segments.append(list(segment))
            if not segments or any(not segment for segment in segments):
                raise ValueError("empty GPX route/track segment")
            for segment_index, samples in enumerate(segments):
                for sample_index, sample in enumerate(samples):
                    coords, attrs = _point(sample, "trace point")
                    base = _sample_id(kind, name, coords, attrs)
                    # Stationary GPS samples may be bit-for-bit identical.
                    # Preserve them separately without shifting IDs of distinct
                    # samples or conflating their original segment/order.
                    occurrences[base] = occurrences.get(base, 0) + 1
                    ident = (base if occurrences[base] == 1 else
                             f"{base}-repeat-{occurrences[base]}")
                    attrs["gpx_trace"] = {
                        "format": "GPX_1_1_TRACE_POINT", "kind": kind,
                        "name": name, "trace_id": trace_id,
                        "segment": segment_index, "order": sample_index}
                    if description is not None:
                        attrs["trace_description"] = description
                    append(ident, coords, attrs)
    if not features:
        raise ValueError("GPX has no supported source Points")
    return {"type": "FeatureCollection", "features": features}
