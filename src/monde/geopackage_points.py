"""Bounded read-only GeoPackage 2D source geometries (EPSG:4326 / EPSG:3857)."""
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


# Explicit, bounded Web Mercator interpretation. Every derived Point is tagged
# with its original source CRS; the original SQLite/WKB is never modified.
_WEB_RADIUS = 6378137.0
_WEB_LIMIT = math.pi * _WEB_RADIUS


def _source_srs(blob, endian):
    srs = struct.unpack_from(endian + "i", blob, 4)[0]
    if srs not in (4326, 3857):
        raise ValueError("only 2D EPSG:4326 or EPSG:3857 is supported")
    return srs


def _lonlat(x, y, srs):
    if not math.isfinite(x) or not math.isfinite(y):
        raise ValueError("nonfinite original GeoPackage coordinate")
    if srs == 4326:
        if not -180 <= x <= 180 or not -90 <= y <= 90:
            raise ValueError("original WGS84 coordinate outside bounds")
        return [x, y]
    if srs != 3857 or abs(x) > _WEB_LIMIT or abs(y) > _WEB_LIMIT:
        raise ValueError("original EPSG:3857 coordinate outside Web Mercator bounds")
    return [math.degrees(x / _WEB_RADIUS),
            math.degrees(math.atan(math.sinh(y / _WEB_RADIUS)))]


def _check_envelope(blob, endian, points, srs):
    west, east, south, north = struct.unpack_from(endian + "dddd", blob, 8)
    if not all(math.isfinite(v) for v in (west, east, south, north)):
        raise ValueError("nonfinite GeoPackage source envelope")
    if west > east or south > north:
        raise ValueError("reversed GeoPackage source envelope")
    bottom = _lonlat(west, south, srs)
    upper = _lonlat(east, north, srs)
    tolerance = 1e-9 if srs == 3857 else 0.0
    if any(not bottom[0] - tolerance <= point[0] <= upper[0] + tolerance
           or not bottom[1] - tolerance <= point[1] <= upper[1] + tolerance
           for point in points):
        raise ValueError("GeoPackage source envelope contradicts geometry")


def _point(blob):
    """Decode standard GeoPackage binary header and one 2D WKB Point."""
    if not isinstance(blob, bytes) or len(blob) < 29 or blob[:3] != b"GP\x00":
        raise ValueError("GeoPackage requires a nonempty Point geometry")
    flags = blob[3]
    envelope = (flags >> 1) & 7
    if flags & 0xF0 or envelope not in (0, 1):
        raise ValueError("unsupported GeoPackage flags or envelope")
    endian = "<" if flags & 1 else ">"
    srs = _source_srs(blob, endian)
    offset = 8 + (32 if envelope else 0)
    if len(blob) != offset + 21 or blob[offset] not in (0, 1):
        raise ValueError("GeoPackage requires exactly one 2D WKB Point")
    marker = "<" if blob[offset] == 1 else ">"
    geometry_type, lon, lat = struct.unpack(marker + "Idd", blob[offset + 1:])
    if geometry_type != 1:
        raise ValueError("invalid 2D WKB Point geometry")
    point = _lonlat(lon, lat, srs)
    if envelope:
        _check_envelope(blob, endian, [point], srs)
    return point



def _multipoint(blob):
    """Read original 2D WKB MultiPoint members; never infer a path."""
    if (not isinstance(blob, bytes) or len(blob) < 17 or len(blob) > MAX_BYTES
            or blob[:3] != b"GP\x00"):
        raise ValueError("invalid bounded GeoPackage MultiPoint")
    flags = blob[3]
    envelope = (flags >> 1) & 7
    if flags & 0xF0 or envelope not in (0, 1):
        raise ValueError("unsupported MultiPoint flags")
    header_endian = "<" if flags & 1 else ">"
    srs = _source_srs(blob, header_endian)
    offset = 8 + 32 * bool(envelope)
    if len(blob) < offset + 9 or blob[offset] not in (0, 1):
        raise ValueError("MultiPoint WKB header missing")
    endian = "<" if blob[offset] == 1 else ">"
    kind, count = struct.unpack_from(endian + "II", blob, offset + 1)
    if kind != 4 or not 1 <= count <= MAX_POINTS or len(blob) != offset + 9 + 21 * count:
        raise ValueError("invalid bounded MultiPoint members")
    points = []
    for index in range(count):
        start = offset + 9 + index * 21
        member = b"GP\x00\x01" + struct.pack("<i", srs) + blob[start:start + 21]
        points.append(_point(member))
    if envelope:
        _check_envelope(blob, header_endian, points, srs)
    return points


def _line(blob):
    """Exactly one bounded, two-dimensional GeoPackage WKB LineString."""
    if not isinstance(blob, bytes) or len(blob) < 17 or blob[:3] != b"GP\x00":
        raise ValueError("GeoPackage requires a LineString geometry")
    flags = blob[3]
    envelope = (flags >> 1) & 7
    if flags & 0xF0 or envelope not in (0, 1):
        raise ValueError("unsupported GeoPackage flags or envelope")
    endian_header = "<" if flags & 1 else ">"
    srs = _source_srs(blob, endian_header)
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
        points.append(_lonlat(lon, lat, srs))
    if envelope:
        _check_envelope(blob, endian_header, points, srs)
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
    srs = _source_srs(blob, header_endian)
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
            ring.append(_lonlat(lon, lat, srs))
        if ring[0] != ring[-1] or len({tuple(p) for p in ring[:-1]}) < 3:
            raise ValueError("Polygon ring must be closed with three distinct vertices")
        rings.append(ring)
        total += vertices
        pos += 16 * vertices
    if pos != len(blob):
        raise ValueError("unexpected trailing Polygon geometry bytes")
    if envelope:
        _check_envelope(blob, header_endian, [point for ring in rings for point in ring], srs)
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
    srs = _source_srs(blob, header_endian)
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
        member = b"GP\x00\x01" + struct.pack("<i", srs) + blob[pos:end]
        lines.append(_line(member))
        total += vertices
        pos = end
    if pos != len(blob):
        raise ValueError("unexpected trailing MultiLineString bytes")
    if envelope:
        _check_envelope(blob, header_endian, [point for line in lines for point in line], srs)
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
    srs = _source_srs(blob, header_endian)
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
        member = b"GP\x00\x01" + struct.pack("<i", srs) + blob[start:pos]
        polygons.append(_polygon(member))
    if pos != len(blob):
        raise ValueError("trailing MultiPolygon WKB bytes")
    if envelope:
        _check_envelope(blob, header_endian, [point for polygon in polygons for ring in polygon for point in ring], srs)
    return polygons


def _declared_geometry_kind(blob):
    """Dispatch a 2D GEOMETRY row to an existing strict GeoPackage decoder."""
    if (not isinstance(blob, bytes) or len(blob) < 13
            or len(blob) > MAX_BYTES or blob[:3] != b"GP\x00"):
        raise ValueError("invalid GeoPackage GEOMETRY row")
    flags = blob[3]
    envelope = (flags >> 1) & 7
    if flags & 0xF0 or envelope not in (0, 1):
        raise ValueError("unsupported GeoPackage GEOMETRY flags")
    endian = "<" if flags & 1 else ">"
    _source_srs(blob, endian)
    offset = 8 + (32 if envelope else 0)
    if len(blob) < offset + 5 or blob[offset] not in (0, 1):
        raise ValueError("missing 2D WKB subtype")
    wkb_endian = "<" if blob[offset] == 1 else ">"
    geometry_type = struct.unpack_from(wkb_endian + "I", blob, offset + 1)[0]
    types = {1: "POINT", 2: "LINESTRING", 3: "POLYGON",
             4: "MULTIPOINT", 5: "MULTILINESTRING", 6: "MULTIPOLYGON"}
    if geometry_type not in types:
        raise ValueError("unsupported 2D GeoPackage GEOMETRY subtype")
    return types[geometry_type]



MAX_LAYERS = 16


def list_layers(path):
    """Discover all original GeoPackage feature tables, never hidden layers."""
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
            layers = [row[0] for row in db.execute(
                "SELECT table_name FROM gpkg_contents "
                "WHERE data_type='features' ORDER BY table_name LIMIT ?",
                (MAX_LAYERS + 1,))]
    except sqlite3.DatabaseError as exc:
        raise ValueError("invalid or unreadable local GeoPackage") from exc
    if not 1 <= len(layers) <= MAX_LAYERS:
        raise ValueError("GeoPackage requires 1 to 16 feature layers")
    for name in layers:
        _identifier(name)
    return layers


def documents_for_layers(path, *, source_id, locator, captured_at,
                         valid_from, valid_to=None, source_event_at=None):
    """Source-scoped, atomic multi-layer WorldMini documents from one local file.

    Reuse the existing strict per-layer GeoPackage reader. Each layer retains
    its own source identity; equal row IDs in different layers stay distinct.
    """
    from .geojson import to_document
    documents, count = [], 0
    for layer in list_layers(path):
        geo = to_geojson(path, layer=layer)
        count += len(geo["features"])
        if count > MAX_POINTS:
            raise ValueError("GeoPackage all-layers observation limit exceeded")
        for feature in geo["features"]:
            props = feature["properties"]
            if "gpkg_source_layer" in props or "gpkg_source_fid" in props:
                raise ValueError("GeoPackage attribute collides with layer provenance")
            original = str(feature["id"])
            # Multipart vertex IDs are generated by the existing strict
            # reader; preserve the actual SQLite row FID independently.
            original_fid = (props["gpkg_trace"]["feature_id"]
                            if "gpkg_trace" in props else original)
            feature["id"] = "gpkg-layer-" + hashlib.sha256(
                (layer + "\x00" + original).encode("utf-8")).hexdigest()[:32]
            props["gpkg_source_layer"] = layer
            props["gpkg_source_fid"] = original_fid
        documents.append(to_document(
            geo, source_id=source_id + ":" + layer,
            locator=locator + "#gpkg-layer=" + layer,
            captured_at=captured_at, valid_from=valid_from,
            valid_to=valid_to, source_event_at=source_event_at))
    return documents

def to_geojson(path, *, layer):
    """Read one local feature table, preserving original primary keys and attributes.

    Never infer capture/valid times. EPSG:3857 -> WGS84 is an explicitly
    labelled derived map coordinate, not a rewrite of original source WKB.
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
            source_srs = contents[0][1] if len(contents) == 1 else None
            reference = db.execute(
                "SELECT organization, organization_coordsys_id "
                "FROM gpkg_spatial_ref_sys WHERE srs_id=?", (source_srs,)).fetchall()
            if (source_srs not in (4326, 3857) or
                    contents != [("features", source_srs)] or len(columns_metadata) != 1
                    or reference != [("EPSG", source_srs)]
                    or columns_metadata[0][1:] not in tuple(
                        (kind, source_srs, 0, 0) for kind in (
                            "POINT", "LINESTRING", "POLYGON", "MULTIPOLYGON",
                            "MULTILINESTRING", "MULTIPOINT", "GEOMETRY"))):
                raise ValueError("layer must declare supported 2D EPSG:4326 or EPSG:3857 geometry")
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
                    or "gpkg_source_srs" in attrs
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
                if not isinstance(row[1], bytes) or len(row[1]) < 8 or row[1][:3] != b"GP\x00":
                    raise ValueError("GeoPackage row has invalid geometry header")
                header_endian = "<" if row[1][3] & 1 else ">"
                if _source_srs(row[1], header_endian) != source_srs:
                    raise ValueError("GeoPackage row SRID disagrees with declared layer")
                if source_srs == 3857:
                    properties["gpkg_source_srs"] = "EPSG:3857"
                row_kind = (_declared_geometry_kind(row[1])
                            if kind == "GEOMETRY" else kind)
                if row_kind == "POINT":
                    features.append({"type": "Feature", "id": str(row[0]),
                                     "properties": properties, "geometry": {
                                         "type": "Point", "coordinates": _point(row[1])}})
                elif row_kind == "MULTIPOINT":
                    points = _multipoint(row[1])
                    if len(features) + len(points) > MAX_POINTS:
                        raise ValueError("GeoPackage source exceeds 50000 original Points")
                    original_name = properties.get("name")
                    label = (original_name if isinstance(original_name, str)
                             and 0 < len(original_name) <= 1000
                             else layer + " #" + str(row[0]))
                    group = hashlib.sha256((layer + ":" + str(row[0])).encode(
                        "utf-8")).hexdigest()[:24]
                    for index, point in enumerate(points):
                        features.append({
                            "type": "Feature",
                            "id": "gpkg-multipoint-" + layer + "-" + str(row[0])
                                  + "-" + str(index),
                            "properties": {**properties, "gpkg_trace": {
                                "format": "GPKG_1_3_MULTIPOINT_POINT",
                                "kind": "MultiPoint", "name": label,
                                "trace_id": group, "segment": 0, "order": index,
                                "layer": layer, "feature_id": str(row[0])}},
                            "geometry": {"type": "Point", "coordinates": point}})
                else:
                    polygons = (_multipolygon(row[1]) if row_kind == "MULTIPOLYGON"
                                else [[line] for line in _multiline(row[1])]
                                if row_kind == "MULTILINESTRING"
                                else [[_line(row[1])] if row_kind == "LINESTRING"
                                      else _polygon(row[1])])
                    if len(features) + sum(len(ring) for rings in polygons for ring in rings) > MAX_POINTS:
                        raise ValueError("GeoPackage source exceeds 50000 vertices")
                    original_name = properties.get("name")
                    label = (original_name if isinstance(original_name, str)
                             and 0 < len(original_name) <= 1000
                             else layer + " #" + str(row[0]))
                    is_polygon = row_kind in ("POLYGON", "MULTIPOLYGON")
                    for polygon_index, rings in enumerate(polygons):
                        trace_key = layer + ":" + str(row[0])
                        if row_kind in ("MULTIPOLYGON", "MULTILINESTRING"):
                            trace_key += ":" + str(polygon_index)
                        trace_id = hashlib.sha256(trace_key.encode("utf-8")).hexdigest()[:24]
                        for segment, ring in enumerate(rings):
                            for order, point in enumerate(ring):
                                trace = {
                                    "format": ("GPKG_1_3_MULTIPOLYGON_RING_POINT"
                                               if row_kind == "MULTIPOLYGON" else
                                               "GPKG_1_3_MULTILINESTRING_POINT"
                                               if row_kind == "MULTILINESTRING" else
                                               "GPKG_1_3_POLYGON_RING_POINT" if is_polygon
                                               else "GPKG_1_3_LINESTRING_POINT"),
                                    "kind": ("MultiPolygon" if row_kind == "MULTIPOLYGON" else
                                             "MultiLineString" if row_kind == "MULTILINESTRING" else
                                             "Polygon" if is_polygon else "LineString"),
                                    "name": label, "trace_id": trace_id,
                                    "segment": segment, "order": order,
                                    "layer": layer, "feature_id": str(row[0])}
                                if row_kind == "MULTIPOLYGON":
                                    trace["polygon_index"] = polygon_index
                                if row_kind == "MULTILINESTRING":
                                    trace["line_index"] = polygon_index
                                features.append({
                                    "type": "Feature",
                                    "id": ("gpkg-multipolygon-" if row_kind == "MULTIPOLYGON" else
                                           "gpkg-multiline-" if row_kind == "MULTILINESTRING"
                                           else "gpkg-polygon-" if is_polygon else "gpkg-line-")
                                          + layer + "-" + str(row[0]) + "-"
                                          + (str(polygon_index) + "-" if row_kind in ("MULTIPOLYGON", "MULTILINESTRING")
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
