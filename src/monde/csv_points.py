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
    from .world import WorldMini, _object_no_duplicates

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
    required = {"source_id", "locator", "captured_at", "valid_from"}
    optional = {"csv", "geojson", "kml", "kmz", "gpx", "gpkg", "gpkg_layer", "valid_to", "source_event_at",
                "id_column", "lon_column", "lat_column"}
    documents, features = [], 0
    for entry in datasets:
        if (not isinstance(entry, dict) or not required <= set(entry)
                or set(entry) - required - optional):
            raise ValueError("CSV dataset has missing or unexpected fields")
        formats = [name for name in ("csv", "geojson", "kml", "kmz", "gpx", "gpkg") if name in entry]
        if len(formats) != 1:
            raise ValueError("each dataset requires exactly one csv, geojson, kml, kmz, gpx or gpkg input")
        kind = formats[0]
        if (kind != "gpkg" and "gpkg_layer" in entry) or (
                kind == "gpkg" and (not isinstance(entry.get("gpkg_layer"), str)
                                    or not entry["gpkg_layer"])):
            raise ValueError("gpkg_layer is required only for gpkg datasets")
        if kind != "csv" and {"id_column", "lon_column", "lat_column"} & entry.keys():
            raise ValueError("CSV column options are invalid for GeoJSON/KML/GPX")
        source_path = entry[kind]
        if (not isinstance(source_path, str) or not source_path
                or source_path != source_path.strip()):
            raise ValueError("dataset path required")
        source_file = os.path.realpath(os.path.join(os.path.dirname(manifest), source_path))
        if source_file == output:
            raise ValueError("output cannot overwrite source dataset")
        if kind == "csv":
            geojson = to_geojson(
                source_file, id_column=entry.get("id_column", "id"),
                lon_column=entry.get("lon_column", "longitude"),
                lat_column=entry.get("lat_column", "latitude"))
        elif kind in ("kml", "kmz"):
            from .kml_points import to_geojson as kml_to_geojson
            geojson = kml_to_geojson(source_file, kmz=(kind == "kmz"))
        elif kind == "gpkg":
            from .geopackage_points import to_geojson as gpkg_to_geojson
            geojson = gpkg_to_geojson(source_file, layer=entry["gpkg_layer"])
        elif kind == "gpx":
            from .gpx_points import to_geojson as gpx_to_geojson
            geojson = gpx_to_geojson(source_file)
        else:
            geojson = WorldMini.load_document(source_file)
        features += len(geojson["features"])
        if features > MAX_ROWS:
            raise ValueError("source manifest total Point limit exceeded (50000)")
        documents.append(to_document(
            geojson, source_id=entry["source_id"], locator=entry["locator"],
            captured_at=entry["captured_at"], valid_from=entry["valid_from"],
            valid_to=entry.get("valid_to"),
            source_event_at=entry.get("source_event_at")))
    return documents, features


def to_source_csv(collection):
    """Export one source assertion per row; never reconcile geographic positions."""
    import io

    fields = ("entity", "longitude", "latitude", "assertion_id", "source_id",
              "evidence_id", "locator", "captured_at", "source_event_at",
              "kind", "known_at", "valid_from", "valid_to", "valid_at",
              "knowledge_cutoff", "monde_status")
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(fields)
    for feature in collection["features"]:
        props = feature["properties"]
        lon, lat = feature["geometry"]["coordinates"]

        def text(name):
            value = props.get(name)
            if value is None:
                return ""
            value = str(value)
            # Original locators may be untrusted; prevent spreadsheet formulas.
            return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value

        writer.writerow([text("entity"), lon, lat, text("assertion_id"),
                         text("source_id"), text("evidence_id"), text("locator"),
                         text("captured_at"), text("source_event_at"), text("kind"),
                         text("known_at"), text("valid_from"), text("valid_to"),
                         text("valid_at"), text("knowledge_cutoff"),
                         text("monde_status")])
    return stream.getvalue()
