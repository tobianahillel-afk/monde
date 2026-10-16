"""Bounded read-only GeoPackage EPSG:4326 Point adapter for original source evidence."""
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
                    or columns_metadata[0][1:] != ("POINT", 4326, 0, 0)):
                raise ValueError("layer must declare a 2D EPSG:4326 Point feature table")
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
            if (len(attrs) > 16 or "geo_point" in attrs
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
                features.append({"type": "Feature", "id": str(row[0]),
                                 "properties": properties, "geometry": {
                                     "type": "Point", "coordinates": _point(row[1])}})
    except sqlite3.DatabaseError as exc:
        raise ValueError("invalid or unreadable local GeoPackage") from exc
    if not features:
        raise ValueError("GeoPackage contains no original Point reports")
    return {"type": "FeatureCollection", "features": features}
