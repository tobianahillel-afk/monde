"""Import locally supplied KML 2.2 Point reports, retaining explicit source IDs.

KML location is a *source claim*, never a verified place or MONDE consensus.
Only local, bounded Point Placemarks with stable IDs are supported.
"""
import os
import math
import xml.etree.ElementTree as ET

MAX_KML_BYTES = 10_000_000
MAX_POINTS = 50_000
KML_NAMESPACE = "http://www.opengis.net/kml/2.2"


def to_geojson(path):
    """Convert an original KML document to existing GeoJSON Point claims.

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
        if len(geometries) != 1 or geometries[0].tag != tag("Point"):
            raise ValueError("only one 2D Point per KML Placemark is supported")
        geometry = geometries[0]
        coordinates = geometry.findall(tag("coordinates"))
        if len(coordinates) != 1 or not coordinates[0].text:
            raise ValueError("KML Point requires longitude,latitude")
        raw_point = coordinates[0].text.strip().split(",")
        if len(raw_point) != 2 or any(not part.strip() for part in raw_point):
            raise ValueError("KML Point must be 2D lon,lat without altitude")
        try:
            lon, lat = (float(v.strip()) for v in raw_point)
        except ValueError as exc:
            raise ValueError("KML Point requires numeric WGS84 coordinates") from exc
        if not math.isfinite(lon) or not math.isfinite(lat) or not (
                -180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError("KML Point is outside finite WGS84 bounds")
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
        features.append({"type": "Feature", "id": ident, "properties": attrs,
                         "geometry": {"type": "Point", "coordinates": [lon, lat]}})
    if not features:
        raise ValueError("KML contains no supported Point Placemark")
    return {"type": "FeatureCollection", "features": features}
