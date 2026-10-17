# MONDE Mini — Original GeoPackage Web Mercator evidence (WORK-0039)

An original, **local read-only** GeoPackage layer may explicitly declare either
EPSG:4326 (longitude/latitude) or EPSG:3857 (projected Web Mercator metres).
A mixture of supported layers in the same GeoPackage is permitted through
the existing `--gpkg-all-layers` command. No dependencies, network requests,
database writes, inferred CRS or timestamps are introduced.

## Source coordinate semantics

- For **EPSG:4326**, the map uses the validated original source coordinates.
- For **EPSG:3857**, every 2D point is **mathematically converted** to WGS84
  lon/lat for the GeoJSON map. The derived map coordinates are **not**
  falsely described as original WGS84 source observations. The feature's
  evidence includes `gpkg_source_srs=EPSG:3857` as an explicit assertion.
  The original local SQLite/WKB and source locator remain unchanged.
- The strict input envelope is validated against the source geometry in its
  declared coordinate system. Original EPSG:3857 X/Y must lie inside the
  finite Web Mercator world; nonfinite/out-of-range coordinates are rejected.
- Every layer's GeoPackage table, geometry columns, spatial reference and
  individual WKB header must agree. Unsupported coordinate systems, 3D/M,
  malformed WKB and invalid layers are rejected; no silent skipping.

## One-command offline import

```sh
PYTHONPATH=src python3 -m monde.map_view \\
  --gpkg local-survey.gpkg --gpkg-all-layers \\
  --source-id local-survey \\
  --source-locator dataset://original/local-survey.gpkg \\
  --captured-at 2026-01-10T10:00:00Z \\
  --valid-from 2026-01-01T00:00:00Z \\
  --at 2026-01-02T00:00:00Z \\
  --known-at 2026-01-10T10:00:00Z \\
  --output map.html
```

Like all MONDE Mini geographic evidence, the result retains independent
source layer identity, explicit world and knowledge times, and conflicting
source assertions. Conversion is a display/coordinate transform, **not**
reconciliation or proof of physical location. No map HTML is written on
source validation failure.

For the complete offline map, layer visibility and source filtering,
see [the map reference](world-mini-offline-map.md).
