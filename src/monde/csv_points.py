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


MAX_MANIFEST_BYTES = 256_000
MAX_DATASETS = 16


def documents_from_manifest(path, *, output_path):
    """Convert source-specific local CSVs for one atomic WorldMini transaction."""
    import json
    import os
    from .geojson import to_document
    from .world import _object_no_duplicates

    manifest = os.path.realpath(os.fspath(path))
    output = os.path.realpath(os.fspath(output_path))
    if manifest == output:
        raise ValueError("output cannot overwrite CSV manifest")
    if os.path.getsize(manifest) > MAX_MANIFEST_BYTES:
        raise ValueError("CSV manifest exceeds size limit")
    with open(manifest, encoding="utf-8") as stream:
        payload = json.load(stream, object_pairs_hook=_object_no_duplicates,
                            parse_constant=lambda _: (_ for _ in ()).throw(
                                ValueError("invalid non-finite manifest value")))
    if not isinstance(payload, dict) or set(payload) != {"datasets"}:
        raise ValueError("CSV manifest requires datasets")
    datasets = payload["datasets"]
    if not isinstance(datasets, list) or not 1 <= len(datasets) <= MAX_DATASETS:
        raise ValueError("CSV manifest requires 1 to 16 datasets")
    required = {"csv", "source_id", "locator", "captured_at", "valid_from"}
    optional = {"valid_to", "source_event_at", "id_column", "lon_column", "lat_column"}
    documents, features = [], 0
    for entry in datasets:
        if (not isinstance(entry, dict) or not required <= set(entry)
                or set(entry) - required - optional):
            raise ValueError("CSV dataset has missing or unexpected fields")
        csv_path = entry["csv"]
        if not isinstance(csv_path, str) or not csv_path or csv_path != csv_path.strip():
            raise ValueError("CSV dataset path required")
        source_file = os.path.realpath(os.path.join(os.path.dirname(manifest), csv_path))
        if source_file == output:
            raise ValueError("output cannot overwrite CSV dataset")
        geojson = to_geojson(
            source_file, id_column=entry.get("id_column", "id"),
            lon_column=entry.get("lon_column", "longitude"),
            lat_column=entry.get("lat_column", "latitude"))
        features += len(geojson["features"])
        if features > MAX_ROWS:
            raise ValueError("CSV manifest total Point limit exceeded (50000)")
        documents.append(to_document(
            geojson, source_id=entry["source_id"], locator=entry["locator"],
            captured_at=entry["captured_at"], valid_from=entry["valid_from"],
            valid_to=entry.get("valid_to"),
            source_event_at=entry.get("source_event_at")))
    return documents, features
