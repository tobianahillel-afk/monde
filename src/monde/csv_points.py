"""CSV source-reported Points adapted to the existing GeoJSON claim contract."""
import csv

MAX_ROWS = 50000


def to_geojson(path, *, id_column="id", lon_column="longitude",
               lat_column="latitude"):
    """Read WGS84 degrees as explicit source claims; never infer real locations."""
    cols = (id_column, lon_column, lat_column)
    if (any(not isinstance(x, str) or not x or x != x.strip() for x in cols)
            or len(set(cols)) != 3):
        raise ValueError("three distinct CSV column names are required")
    features, seen = [], set()
    with open(path, encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        headers = reader.fieldnames
        if (not headers or len(set(headers)) != len(headers) or
                any(not key or key != key.strip() for key in headers) or
                any(key not in headers for key in cols)):
            raise ValueError("CSV requires unique headers and explicit Point columns")
        for row in reader:
            if len(features) >= MAX_ROWS:
                raise ValueError("CSV row limit exceeded (50000)")
            if None in row or any(value is None for value in row.values()):
                raise ValueError("CSV row has inconsistent column count")
            ident = row[id_column]
            if not ident or ident != ident.strip() or ident in seen:
                raise ValueError("CSV source IDs must be present and unique")
            seen.add(ident)
            try:
                lon, lat = float(row[lon_column]), float(row[lat_column])
            except ValueError as exc:
                raise ValueError("CSV requires numeric WGS84 lon/lat") from exc
            properties = {key: value for key, value in row.items()
                          if key not in cols and value != ""}
            features.append({"type": "Feature", "id": ident, "properties": properties,
                             "geometry": {"type": "Point", "coordinates": [lon, lat]}})
    if not features:
        raise ValueError("CSV has no Point reports")
    return {"type": "FeatureCollection", "features": features}
