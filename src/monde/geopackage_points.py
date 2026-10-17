"""Bounded read-only GeoPackage EPSG:4326 Point/LineString/MultiLineString/Polygon/MultiPolygon adapter for original source evidence."""
import hashlib
import math
import os
import re
import sqlite3
import struct
from contextlib import closing
from urllib.parse import quote

MAX_BYTES = 100_000_000
MAX_POINTS = 50_000
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,62}\Z")


def _identifier(value):
    if not isinstance(value, str) or not _NAME.fullmatch(value):
        raise ValueError("GeoPackage layer/column requires a simple identifier")
    return '"' + value + '"'


def _point(blob):
    """Decode standard GeoPackage binary header and one 2D WKB Point."""
    if not isinstance(blob, bytes) or len(blob) < 29 or blob[:3] != b"GP\x00":
        raise ValueError("GeoPackage requires a nonempty Point geometry")
    flags = blob[3]
    envelope = (flags >> 1) & 7
    if flags & 0xF0 or envelope not in (0, 1):
        raise ValueError("unsupported GeoPackage flags or envelope")
    endian = "<" if flags & 1 else ">"
    if struct.unpack(endian + "i", blob[4:8])[0] != 4326:
        raise ValueError("GeoPackage geometry is not EPSG:4326")
    offset = 8 + (32 if envelope else 0)
    if len(blob) != offset + 21 or blob[offset] not in (0, 1):
        raise ValueError("GeoPackage requires exactly one 2D WKB Point")
    marker = "<" if blob[offset] == 1 else ">"
    geometry_type, lon, lat = struct.unpack(marker + "Idd", blob[offset + 1:])
    if (geometry_type != 1 or not math.isfinite(lon) or not math.isfinite(lat)
            or not -180 <= lon <= 180 or not -90 <= lat <= 90):
        raise ValueError("invalid WGS84 Point geometry")
    if envelope:
        a, b, c, d = struct.unpack(endian + "dddd", blob[8:40])
        if (not all(math.isfinite(v) for v in (a, b, c, d))
                or not a <= lon <= b or not c <= lat <= d):
            raise ValueError("GeoPackage envelope contradicts the Point")
    return [lon, lat]


def _line(blob):
    """Exactly one bounded, two-dimensional GeoPackage WKB LineString."""
    if not isinstance(blob, bytes) or len(blob) < 17 or blob[:3] != b"GP\x00":
        raise ValueError("GeoPackage requires a LineString geometry")
    flags = blob[3]
    envelope = (flags >> 1) & 7
    if flags & 0xF0 or envelope not in (0, 1):
        raise ValueError("unsupported GeoPackage flags or envelope")
    endian_header = "<" if flags & 1 else ">"
    if struct.unpack(endian_header + "i", blob[4:8])[0] != 4326:
        raise ValueError("GeoPackage geometry is not EPSG:4326")
    offset = 8 + (32 if envelope else 0)
    if len(blob) < offset + 9 or blob[offset] not in (0, 1):
        raise ValueError("GeoPackage requires 2D WKB LineString")
    endian = "<" if blob[offset] == 1 else ">"
    kind, count = struct.unpack_from(endian + "II", blob, offset + 1)
    if kind != 2 or not 2 <= count <= MAX_POINTS or len(blob) != offset + 9 + 16 * count:
        raise ValueError("invalid bounded 2D WKB LineString")
    points = []
    for index in range(count):
        lon, lat = struct.unpack_from(endian + "dd", blob, offset + 9 + 16 * index)
        if (not math.isfinite(lon) or not math.isfinite(lat)
                or not -180 <= lon <= 180 or not -90 <= lat <= 90):
            raise ValueError("LineString coordinate outside WGS84 bounds")
        points.append([lon, lat])
    if envelope:
        west, east, south, north = struct.unpack(endian_header + "dddd", blob[8:40])
        if (not all(math.isfinite(v) for v in (west, east, south, north))
                or any(not west <= lon <= east or not south <= lat <= north
                       for lon, lat in points)):
            raise ValueError("GeoPackage envelope contradicts LineString")
    return points



def _polygon(blob):
    """Read source-declared 2D Polygon rings; never infer filled geographic area."""
    if not isinstance(blob, bytes) or len(blob) < 17 or blob[:3] != b"GP\x00":
        raise ValueError("GeoPackage requires a Polygon geometry")
    flags = blob[3]
    envelope = (flags >> 1) & 7
    if flags & 0xF0 or envelope not in (0, 1):
        raise ValueError("unsupported GeoPackage Polygon flags")
    header_endian = "<" if flags & 1 else ">"
    if struct.unpack_from(header_endian + "i", blob, 4)[0] != 4326:
        raise ValueError("GeoPackage Polygon is not EPSG:4326")
    offset = 8 + (32 if envelope else 0)
    if len(blob) < offset + 9 or blob[offset] not in (0, 1):
        raise ValueError("GeoPackage requires 2D WKB Polygon")
    endian = "<" if blob[offset] == 1 else ">"
    kind, count = struct.unpack_from(endian + "II", blob, offset + 1)
    if kind != 3 or not 1 <= count <= 129:
        raise ValueError("Polygon needs one outer and at most 128 inner rings")
    pos = offset + 9
    rings = []
    total = 0
    for _ in range(count):
        if pos + 4 > len(blob):
            raise ValueError("truncated Polygon ring count")
        vertices = struct.unpack_from(endian + "I", blob, pos)[0]
        pos += 4
        if vertices < 4 or vertices > MAX_POINTS - total or pos + vertices * 16 > len(blob):
            raise ValueError("invalid bounded Polygon ring")
        ring = []
        for i in range(vertices):
            lon, lat = struct.unpack_from(endian + "dd", blob, pos + i * 16)
            if (not math.isfinite(lon) or not math.isfinite(lat)
                    or not -180 <= lon <= 180 or not -90 <= lat <= 90):
                raise ValueError("Polygon coordinate outside WGS84 bounds")
            ring.append([lon, lat])
        if ring[0] != ring[-1] or len({tuple(p) for p in ring[:-1]}) < 3:
            raise ValueError("Polygon ring must be closed with three distinct vertices")
        rings.append(ring)
        total += vertices
        pos += 16 * vertices
    if pos != len(blob):
        raise ValueError("unexpected trailing Polygon geometry bytes")
    if envelope:
        west, east, south, north = struct.unpack_from(header_endian + "dddd", blob, 8)
        if (not all(math.isfinite(v) for v in (west, east, south, north))
                or any(not west <= lon <= east or not south <= lat <= north
                       for ring in rings for lon, lat in ring)):
            raise ValueError("GeoPackage envelope contradicts Polygon rings")
    return rings




def _multiline(blob):
    """Decode original bounded 2D WKB MultiLineString members, never join paths."""
    if (not isinstance(blob, bytes) or len(blob) < 17 or len(blob) > MAX_BYTES
            or blob[:3] != b"GP\x00"):
        raise ValueError("GeoPackage requires one bounded MultiLineString")
    flags = blob[3]
    envelope = (flags >> 1) & 7
    if flags & 0xF0 or envelope not in (0, 1):
        raise ValueError("unsupported GeoPackage MultiLineString flags")
    header_endian = "<" if flags & 1 else ">"
    if struct.unpack_from(header_endian + "i", blob, 4)[0] != 4326:
        raise ValueError("GeoPackage MultiLineString is not EPSG:4326")
    offset = 8 + (32 if envelope else 0)
    if len(blob) < offset + 9 or blob[offset] not in (0, 1):
        raise ValueError("GeoPackage requires 2D WKB MultiLineString")
    endian = "<" if blob[offset] == 1 else ">"
    kind, count = struct.unpack_from(endian + "II", blob, offset + 1)
    if kind != 5 or not 1 <= count <= 128:
        raise ValueError("MultiLineString needs 1..128 original LineString components")
    pos = offset + 9
    lines = []
    total = 0
    for _ in range(count):
        if pos + 9 > len(blob) or blob[pos] not in (0, 1):
            raise ValueError("truncated MultiLineString member")
        member_endian = "<" if blob[pos] == 1 else ">"
        member_type, vertices = struct.unpack_from(member_endian + "II", blob, pos + 1)
        if (member_type != 2 or vertices < 2
                or vertices > MAX_POINTS - total
                or pos + 9 + 16 * vertices > len(blob)):
            raise ValueError("invalid bounded MultiLineString member")
        end = pos + 9 + 16 * vertices
        # Delegate coordinate and WKB validity to the existing LineString decoder.
        member = b"GP\x00\x01" + struct.pack("<i", 4326) + blob[pos:end]
        lines.append(_line(member))
        total += vertices
        pos = end
    if pos != len(blob):
        raise ValueError("unexpected trailing MultiLineString bytes")
    if envelope:
        west, east, south, north = struct.unpack_from(header_endian + "dddd", blob, 8)
        if (not all(math.isfinite(v) for v in (west, east, south, north))
                or any(not west <= lon <= east or not south <= lat <= north
                       for line in lines for lon, lat in line)):
            raise ValueError("GeoPackage envelope contradicts MultiLineString vertices")
    return lines


def _multipolygon(blob):
    """Preserve each original WKB MultiPolygon component and its independent rings."""
    if (not isinstance(blob, bytes) or len(blob) < 17 or len(blob) > MAX_BYTES
            or blob[:3] != b"GP\x00"):
        raise ValueError("GeoPackage requires one bounded MultiPolygon")
    flags = blob[3]
    envelope = (flags >> 1) & 7
    if flags & 0xF0 or envelope not in (0, 1):
        raise ValueError("unsupported GeoPackage MultiPolygon flags")
    header_endian = "<" if flags & 1 else ">"
    if struct.unpack_from(header_endian + "i", blob, 4)[0] != 4326:
        raise ValueError("GeoPackage MultiPolygon must be EPSG:4326")
    offset = 8 + (32 if envelope else 0)
    if len(blob) < offset + 9 or blob[offset] not in (0, 1):
        raise ValueError("GeoPackage requires 2D WKB MultiPolygon")
    endian = "<" if blob[offset] == 1 else ">"
    kind, count = struct.unpack_from(endian + "II", blob, offset + 1)
    if kind != 6 or not 1 <= count <= 128:
        raise ValueError("MultiPolygon needs 1..128 original Polygon components")
    pos = offset + 9
    polygons = []
    total = 0
    for _ in range(count):
        start = pos
        if pos + 9 > len(blob) or blob[pos] not in (0, 1):
            raise ValueError("truncated MultiPolygon member")
        member_endian = "<" if blob[pos] == 1 else ">"
        member_type, rings = struct.unpack_from(member_endian + "II", blob, pos + 1)
        if member_type != 3 or not 1 <= rings <= 129:
            raise ValueError("MultiPolygon member must be one 2D Polygon")
        pos += 9
        for _ in range(rings):
            if pos + 4 > len(blob):
                raise ValueError("truncated MultiPolygon ring")
            vertices = struct.unpack_from(member_endian + "I", blob, pos)[0]
            pos += 4
            if vertices < 4 or vertices > MAX_POINTS - total or pos + 16 * vertices > len(blob):
                raise ValueError("invalid bounded MultiPolygon ring")
            total += vertices
            pos += 16 * vertices
        # Reuse the already validated Polygon ring decoder rather than inventing
        # another ring-validation path. The outer GP header is checked separately.
        member = b"GP\x00\x01" + struct.pack("<i", 4326) + blob[start:pos]
        polygons.append(_polygon(member))
    if pos != len(blob):
        raise ValueError("trailing MultiPolygon WKB bytes")
    if envelope:
        west, east, south, north = struct.unpack_from(header_endian + "dddd", blob, 8)
        if (not all(math.isfinite(v) for v in (west, east, south, north))
                or any(not west <= lon <= east or not south <= lat <= north
                       for polygon in polygons for ring in polygon for lon, lat in ring)):
            raise ValueError("GeoPackage envelope contradicts MultiPolygon vertices")
    return polygons

def to_geojson(path, *, layer):
    """Read one local feature table, preserving original primary keys and attributes.

    Never infer capture/valid times or CRS, never write to the source database.
    """
    table = _identifier(layer)
    source = os.path.realpath(os.fspath(path))
    if not os.path.isfile(source) or os.path.getsize(source) > MAX_BYTES:
        raise ValueError("GeoPackage requires a local file at most 100 MB")
    uri = "file:" + quote(source, safe="/") + "?mode=ro&immutable=1"
    try:
        with closing(sqlite3.connect(uri, uri=True)) as db:
            db.execute("PRAGMA query_only=ON")
            db.execute("PRAGMA trusted_schema=OFF")
            if db.execute("PRAGMA application_id").fetchone()[0] != 0x47504B47:
                raise ValueError("not a standard GeoPackage")
            contents = db.execute("SELECT data_type, srs_id FROM gpkg_contents "
                                  "WHERE table_name=?", (layer,)).fetchall()
            columns_metadata = db.execute(
                "SELECT column_name, geometry_type_name, srs_id, z, m "
                "FROM gpkg_geometry_columns WHERE table_name=?", (layer,)).fetchall()
            reference = db.execute(
                "SELECT organization, organization_coordsys_id "
                "FROM gpkg_spatial_ref_sys WHERE srs_id=4326").fetchall()
            if (contents != [("features", 4326)] or len(columns_metadata) != 1
                    or reference != [("EPSG", 4326)]
                    or columns_metadata[0][1:] not in (
                        ("POINT", 4326, 0, 0), ("LINESTRING", 4326, 0, 0),
                         ("POLYGON", 4326, 0, 0), ("MULTIPOLYGON", 4326, 0, 0),
                         ("MULTILINESTRING", 4326, 0, 0))):
                raise ValueError("layer must declare a 2D EPSG:4326 Point, LineString, MultiLineString, Polygon or MultiPolygon table")
            kind = columns_metadata[0][1]
            geometry_field = columns_metadata[0][0]
            geom_sql = _identifier(geometry_field)
            if db.execute("SELECT type FROM sqlite_master WHERE name=?",
                          (layer,)).fetchone() != ("table",):
                raise ValueError("source layer must be a physical table")
            columns = db.execute("PRAGMA table_info(" + table + ")").fetchall()
            key = [col[1] for col in columns if col[5] == 1]
            if (len(key) != 1 or next((col[2].upper() for col in columns
                                      if col[1] == key[0]), "") != "INTEGER"
                    or geometry_field not in [col[1] for col in columns]):
                raise ValueError("GeoPackage requires a single integer primary key")
            attrs = [col[1] for col in columns
                     if col[1] not in (key[0], geometry_field)]
            if (len(attrs) > 16 or "geo_point" in attrs or "gpkg_trace" in attrs
                    or any(not _NAME.fullmatch(name) for name in attrs)):
                raise ValueError("unsupported source columns")
            selected = [_identifier(key[0]), geom_sql] + [_identifier(v) for v in attrs]
            statement = ("SELECT " + ", ".join(selected) + " FROM " + table +
                         " ORDER BY " + _identifier(key[0]) + " LIMIT ?")
            features = []
            for row in db.execute(statement, (MAX_POINTS + 1,)):
                if len(features) == MAX_POINTS:
                    raise ValueError("GeoPackage source Point count exceeds 50000")
                if type(row[0]) is not int or row[0] < 1:
                    raise ValueError("source feature id must be positive")
                properties = {}
                for name, value in zip(attrs, row[2:]):
                    if value is None:
                        continue
                    if type(value) is str:
                        if len(value) > 2000:
                            raise ValueError("GeoPackage source text exceeds 2000 characters")
                    elif type(value) in (int, float):
                        if isinstance(value, float) and not math.isfinite(value):
                            raise ValueError("nonfinite GeoPackage attribute")
                    else:
                        raise ValueError("unsupported source attribute type")
                    properties[name] = value
                if kind == "POINT":
                    features.append({"type": "Feature", "id": str(row[0]),
                                     "properties": properties, "geometry": {
                                         "type": "Point", "coordinates": _point(row[1])}})
                else:
                    polygons = (_multipolygon(row[1]) if kind == "MULTIPOLYGON"
                                else [[line] for line in _multiline(row[1])]
                                if kind == "MULTILINESTRING"
                                else [[_line(row[1])] if kind == "LINESTRING"
                                      else _polygon(row[1])])
                    if len(features) + sum(len(ring) for rings in polygons for ring in rings) > MAX_POINTS:
                        raise ValueError("GeoPackage source exceeds 50000 vertices")
                    original_name = properties.get("name")
                    label = (original_name if isinstance(original_name, str)
                             and 0 < len(original_name) <= 1000
                             else layer + " #" + str(row[0]))
                    is_polygon = kind in ("POLYGON", "MULTIPOLYGON")
                    for polygon_index, rings in enumerate(polygons):
                        trace_key = layer + ":" + str(row[0])
                        if kind in ("MULTIPOLYGON", "MULTILINESTRING"):
                            trace_key += ":" + str(polygon_index)
                        trace_id = hashlib.sha256(trace_key.encode("utf-8")).hexdigest()[:24]
                        for segment, ring in enumerate(rings):
                            for order, point in enumerate(ring):
                                trace = {
                                    "format": ("GPKG_1_3_MULTIPOLYGON_RING_POINT"
                                               if kind == "MULTIPOLYGON" else
                                               "GPKG_1_3_MULTILINESTRING_POINT"
                                               if kind == "MULTILINESTRING" else
                                               "GPKG_1_3_POLYGON_RING_POINT" if is_polygon
                                               else "GPKG_1_3_LINESTRING_POINT"),
                                    "kind": ("MultiPolygon" if kind == "MULTIPOLYGON" else
                                             "MultiLineString" if kind == "MULTILINESTRING" else
                                             "Polygon" if is_polygon else "LineString"),
                                    "name": label, "trace_id": trace_id,
                                    "segment": segment, "order": order,
                                    "layer": layer, "feature_id": str(row[0])}
                                if kind == "MULTIPOLYGON":
                                    trace["polygon_index"] = polygon_index
                                if kind == "MULTILINESTRING":
                                    trace["line_index"] = polygon_index
                                features.append({
                                    "type": "Feature",
                                    "id": ("gpkg-multipolygon-" if kind == "MULTIPOLYGON" else
                                           "gpkg-multiline-" if kind == "MULTILINESTRING"
                                           else "gpkg-polygon-" if is_polygon else "gpkg-line-")
                                          + layer + "-" + str(row[0]) + "-"
                                          + (str(polygon_index) + "-" if kind in ("MULTIPOLYGON", "MULTILINESTRING")
                                             else "")
                                          + (str(segment) + "-" if is_polygon else "")
                                          + str(order),
                                    "properties": {**properties, "gpkg_trace": trace},
                                    "geometry": {"type": "Point", "coordinates": point}})

    except sqlite3.DatabaseError as exc:
        raise ValueError("invalid or unreadable local GeoPackage") from exc
    if not features:
        raise ValueError("GeoPackage contains no supported original geometry reports")
    return {"type": "FeatureCollection", "features": features}
