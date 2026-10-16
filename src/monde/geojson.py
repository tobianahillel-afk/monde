"""Import strictly source-attributed GeoJSON Point features into MONDE Mini.

This is an experimental *claim* adapter, not a geometry engine or truth oracle.
No network fetch, CRS reprojection, implied timestamp or source authority.
"""
import hashlib
import json
import math

from .world import _clone, _id, _time


def _point(geometry):
    if not isinstance(geometry, dict) or set(geometry) != {"type", "coordinates"}:
        raise ValueError("GeoJSON geometry must be a 2D Point")
    if geometry["type"] != "Point":
        raise ValueError("only 2D GeoJSON Point is supported")
    coordinates = geometry["coordinates"]
    if not isinstance(coordinates, list) or len(coordinates) != 2:
        raise ValueError("Point needs [longitude, latitude]")
    lon, lat = coordinates
    for value in coordinates:
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("coordinates must be finite JSON numbers")
    if not -180 <= lon <= 180 or not -90 <= lat <= 90:
        raise ValueError("longitude/latitude outside WGS84 ranges")
    return {"type": "Point", "coordinates": _clone(coordinates)}


def _stable_id(prefix, *parts):
    # Stable across repeated ingestion, never based on a changing row index.
    payload = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    return prefix + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def to_document(geojson, *, source_id, locator, captured_at, valid_from,
                source_event_at=None, valid_to=None):
    """Convert an explicit-source GeoJSON Point collection to schema-v1 reports.

    The caller must supply times and the original dataset locator. Properties
    and coordinates are source *claims*, not reconciled physical facts.
    No implicit correction of pre-existing source reports is invented.
    """
    _id(source_id)
    if not isinstance(locator, str) or not locator.strip():
        raise ValueError("explicit source locator required")
    captured = _time(captured_at)
    start = _time(valid_from)
    if source_event_at is not None and _time(source_event_at) > captured:
        raise ValueError("source event cannot follow capture")
    if valid_to is not None and _time(valid_to) <= start:
        raise ValueError("invalid validity interval")
    if not isinstance(geojson, dict) or set(geojson) != {"type", "features"} or \
            geojson["type"] != "FeatureCollection" or \
            not isinstance(geojson["features"], list):
        raise ValueError("expected GeoJSON FeatureCollection")
    evidence, assertions, seen = [], [], set()
    for feature in geojson["features"]:
        if not isinstance(feature, dict) or \
                set(feature) != {"type", "id", "properties", "geometry"} or \
                feature["type"] != "Feature":
            raise ValueError("each feature needs id, geometry and properties")
        raw_id = feature["id"]
        if type(raw_id) is int:
            raw_id = str(raw_id)
        entity_id = _id(raw_id)
        if entity_id in seen:
            raise ValueError("duplicate GeoJSON feature id")
        seen.add(entity_id)
        properties = feature["properties"]
        if not isinstance(properties, dict) or "geo_point" in properties:
            raise ValueError("properties must be an object without geo_point")
        value_by_attribute = {"geo_point": _point(feature["geometry"])}
        for key, value in properties.items():
            value_by_attribute[_id(key)] = _clone(value)
        evidence_id = _stable_id("geo-e-", source_id, locator, entity_id, captured_at)
        evidence.append({
            "id": evidence_id, "source_id": source_id, "locator": locator,
            "captured_at": captured_at, "source_event_at": source_event_at,
        })
        for attribute, value in value_by_attribute.items():
            assertions.append({
                "id": _stable_id("geo-a-", evidence_id, attribute),
                "entity": entity_id, "attribute": attribute,
                "value": value, "evidence_id": evidence_id,
                "kind": "CLAIM", "known_at": captured_at,
                "valid_from": valid_from, "valid_to": valid_to,
                "supersedes": None,
            })
    return {"schema_version": 1, "evidence": evidence, "assertions": assertions}
