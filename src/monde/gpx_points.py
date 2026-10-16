"""Offline GPX 1.1 Waypoints as explicit, source-reported WGS84 Point claims."""
import math
import os
import xml.etree.ElementTree as ET

from .world import _id, _time

MAX_BYTES = 10_000_000
MAX_POINTS = 50_000
NAMESPACE = "{http://www.topografix.com/GPX/1/1}"


def to_geojson(path):
    """Waypoint <name> must be a unique, caller-verified stable dataset ID."""
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
    if root.tag != NAMESPACE + "gpx" or root.get("version") != "1.1":
        raise ValueError("expected standard GPX 1.1")
    if any(child.tag not in (NAMESPACE + "metadata", NAMESPACE + "wpt")
           for child in root):
        raise ValueError("GPX tracks/routes and extensions are unsupported")
    allowed = {"name", "desc", "cmt", "time", "sym", "type"}
    props = {"desc": "description", "cmt": "comment",
             "time": "waypoint_time", "sym": "symbol", "type": "waypoint_type"}
    features, seen = [], set()
    for wpt in root.findall(NAMESPACE + "wpt"):
        if len(features) >= MAX_POINTS:
            raise ValueError("GPX point limit exceeded")
        if set(wpt.attrib) != {"lat", "lon"}:
            raise ValueError("GPX waypoint requires only lon/lat")
        try:
            lat, lon = float(wpt.get("lat")), float(wpt.get("lon"))
        except ValueError as exc:
            raise ValueError("non-numeric GPX coordinates") from exc
        if not math.isfinite(lat) or not math.isfinite(lon) or not (
                -90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("GPX coordinate is outside WGS84")
        attributes, observed = {}, set()
        for child in wpt:
            if not child.tag.startswith(NAMESPACE):
                raise ValueError("unsupported GPX waypoint namespace")
            field = child.tag[len(NAMESPACE):]
            if field not in allowed or field in observed or child.attrib or len(child):
                raise ValueError("unsupported or ambiguous GPX waypoint field")
            observed.add(field)
            value = child.text or ""
            if len(value) > 4000:
                raise ValueError("GPX property too long")
            if field == "time" and value.strip():
                _time(value.strip())  # Source-reported time, not inferred world-validity.
            if field in props and value:
                attributes[props[field]] = value
        name = wpt.find(NAMESPACE + "name")
        if name is None or not name.text or name.text != name.text.strip():
            raise ValueError("GPX waypoint needs source-supplied stable name")
        _id(name.text)
        if name.text in seen:
            raise ValueError("duplicate GPX waypoint name")
        seen.add(name.text)
        attributes["name"] = name.text
        features.append({"type": "Feature", "id": name.text,
                         "properties": attributes,
                         "geometry": {"type": "Point", "coordinates": [lon, lat]}})
    if not features:
        raise ValueError("GPX has no supported waypoints")
    return {"type": "FeatureCollection", "features": features}
