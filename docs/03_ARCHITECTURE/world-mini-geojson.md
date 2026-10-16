# GeoJSON Point ingestion — MONDE Mini (experimental)

This is an executable **local source-document import**, not a Web/OSM API
connector, production geospatial index, geocoder, or verified world-state
reconciliation. Coordinates and properties are **source reports only**.

The importer accepts strictly GeoJSON `FeatureCollection` with 2D WGS84
`Point` features, an explicit unique `id`, and a JSON `properties` object.
The source identity, original locator, capture time and reported valid-time
are mandatory CLI metadata. MONDE **does not fabricate timestamps** from the
file, assume geodetic precision, or interpret a source claim as physical truth.

```sh
PYTHONPATH=src python3 -m monde.world \
  --fixture examples/monde-mini.json \
  --ingest-geojson examples/monde-mini-points.geojson \
  --source-id example-map --source-locator fixture://example-map/places \
  --captured-at 2026-01-10T10:00:00Z --valid-from 2026-01-01T00:00:00Z \
  --state-out /tmp/monde-points.json

PYTHONPATH=src python3 -m monde.world \
  --fixture /tmp/monde-points.json \
  --entity place-001 --attribute geo_point \
  --at 2026-01-02T00:00:00Z --known-at 2026-01-11T00:00:00Z
```

Coordinates are stored as source-attributed `geo_point` claims. Other
properties are ordinary reported attributes, with the same bitemporal query
behavior and independent source evidence as the rest of MONDE Mini.
One evidence record is created per feature and assertions share that evidence
record. Stable identifiers allow repeat imports of **identical** source files
to be idempotent; a conflicting reuse of an ID fails before publication.

Invalid coordinates, unsupported geometry, duplicate feature IDs, missing
provenance, and schema deviations are rejected. Existing snapshot output is
untouched on invalid import. Overwrite still requires `--replace-state` and
is only safe with the documented **single-writer** assumption.

No polygons, projection conversion, entity resolution, automatic correction,
bulk real-world download, network request or real-source license assessment
is added. Real feeds require a separate privacy/license review and appropriate
source permission; the included Point fixture is synthetic.
