"""Ingest bounded KML Points, LineStrings, and single-ring Polygon vertices.

Coordinates remain original source claims, not verified routes or areas.
"""
import os
import math
import hashlib
import json
import xml.etree.ElementTree as ET

MAX_KML_BYTES = 10_000_000
MAX_POINTS = 50_000
KML_NAMESPACE = "http://www.opengis.net/kml/2.2"


def _points(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("KML coordinates missing")
    tokens = text.split()
    if len(tokens) > MAX_POINTS:
        raise ValueError("KML point count limit exceeded")
    points = []
    for token in tokens:
        pair = token.split(",")
        if len(pair) != 2 or any(not part.strip() for part in pair):
            raise ValueError("KML coordinates must be 2D longitude,latitude")
        try:
            lon, lat = (float(part.strip()) for part in pair)
        except ValueError as exc:
            raise ValueError("non-numeric KML coordinates") from exc
        if not math.isfinite(lon) or not math.isfinite(lat) or not (
                -180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError("KML coordinates outside WGS84 bounds")
        points.append([lon, lat])
    return points


def _polygon_points(geometry, tag):
    """Accept only one closed, planar outer KML LinearRing; no holes inferred."""
    if geometry.attrib or len(geometry) != 1 or geometry[0].tag != tag("outerBoundaryIs"):
        raise ValueError("KML Polygon requires one outer boundary without holes")
    outer = geometry[0]
    if outer.attrib or len(outer) != 1 or outer[0].tag != tag("LinearRing"):
        raise ValueError("unsupported KML Polygon boundary")
    ring = outer[0]
    if ring.attrib or len(ring) != 1 or ring[0].tag != tag("coordinates"):
        raise ValueError("unsupported KML Polygon LinearRing")
    coords = ring[0]
    if coords.attrib or len(coords):
        raise ValueError("unsupported KML Polygon coordinates")
    points = _points(coords.text)
    if len(points) < 4 or points[0] != points[-1] or len({tuple(p) for p in points[:-1]}) < 3:
        raise ValueError("KML Polygon must have a closed ring of at least three vertices")
    return points


def to_geojson(path):
    """Convert bounded original KML geometry to source-ordered GeoJSON Point claims.

    A Placemark must carry a stable XML id. No ID, timestamp, or true location
    is inferred from name, row order, file name, or coordinates.
    """
    if os.path.getsize(path) > MAX_KML_BYTES:
        raise ValueError("KML exceeds 10 MB limit")
    with open(path, "rb") as source:
        raw = source.read(MAX_KML_BYTES + 1)
    if len(raw) > MAX_KML_BYTES:
        raise ValueError("KML exceeds 10 MB limit")
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("DTD and XML entities are forbidden in KML")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError("invalid local KML XML") from exc
    namespace = "{" + KML_NAMESPACE + "}"
    if root.tag not in ("kml", namespace + "kml"):
        raise ValueError("expected KML 2.2 root")
    if root.tag == "kml":
        namespace = ""
    tag = lambda name: namespace + name
    if any(node.tag in (tag("NetworkLink"), tag("NetworkLinkControl"))
           for node in root.iter()):
        raise ValueError("linked or remote KML content is unsupported")
    geometry_types = {tag(n) for n in (
        "Point", "LineString", "Polygon", "MultiGeometry", "Model", "Track",
        "MultiTrack", "LinearRing")}
    features, seen = [], set()
    for placemark in root.iter(tag("Placemark")):
        if len(features) >= MAX_POINTS:
            raise ValueError("KML Point count limit exceeded")
        ident = placemark.get("id")
        if not ident or ident in seen:
            raise ValueError("each KML Placemark requires a unique stable id")
        seen.add(ident)
        geometries = [node for node in placemark
                      if node.tag in geometry_types]
        if len(geometries) != 1 or geometries[0].tag not in (
                tag("Point"), tag("LineString"), tag("Polygon")):
            raise ValueError("only one supported KML geometry per Placemark")
        geometry = geometries[0]
        if geometry.tag == tag("Polygon"):
            points = _polygon_points(geometry, tag)
        else:
            if geometry.attrib or len(geometry) != 1 or (
                    geometry[0].tag != tag("coordinates")
                    or geometry[0].attrib or len(geometry[0])):
                raise ValueError("unsupported or ambiguous KML geometry")
            points = _points(geometry[0].text)
        if geometry.tag == tag("Point") and len(points) != 1:
            raise ValueError("KML Point must contain one coordinate")
        if geometry.tag == tag("LineString") and len(points) < 2:
            raise ValueError("KML LineString must have at least two samples")
        attrs = {}
        name = placemark.find(tag("name"))
        if name is not None and name.text is not None:
            if len(name.text) > 1000:
                raise ValueError("KML name is too long")
            attrs["name"] = name.text
        description = placemark.find(tag("description"))
        if description is not None and description.text is not None:
            if len(description.text) > 4000:
                raise ValueError("KML description is too long")
            attrs["description"] = description.text
        if placemark.find(tag("ExtendedData")) is not None:
            raise ValueError("KML ExtendedData is not yet supported; no silent loss")
        if len(features) + len(points) > MAX_POINTS:
            raise ValueError("KML source sample count limit exceeded")
        if geometry.tag == tag("Point"):
            features.append({"type": "Feature", "id": ident, "properties": attrs,
                             "geometry": {"type": "Point", "coordinates": points[0]}})
            continue
        trace_id = hashlib.sha256(ident.encode("utf-8")).hexdigest()[:24]
        repeats = {}
        for order, point in enumerate(points):
            digest = hashlib.sha256(json.dumps(
                [ident, point], separators=(",", ":")).encode("utf-8")
                ).hexdigest()[:32]
            base = ("kml-boundary-" if geometry.tag == tag("Polygon") else
                    "kml-line-") + digest
            repeats[base] = repeats.get(base, 0) + 1
            sample_id = base if repeats[base] == 1 else (
                base + "-repeat-" + str(repeats[base]))
            features.append({
                "type": "Feature", "id": sample_id,
                "properties": {**attrs, "kml_trace": {
                    "format": ("KML_2_2_POLYGON_RING_POINT" if geometry.tag == tag("Polygon")
                               else "KML_2_2_LINESTRING_POINT"),
                    "kind": ("Polygon" if geometry.tag == tag("Polygon")
                             else "LineString"), "name": attrs.get("name", ident),
                    "trace_id": trace_id, "segment": 0, "order": order,
                    **({"placemark_id": ident} if geometry.tag == tag("Polygon")
                       else {})}},
                "geometry": {"type": "Point", "coordinates": point}})
    if not features:
        raise ValueError("KML contains no supported Point, LineString or Polygon Placemark")
    return {"type": "FeatureCollection", "features": features}
