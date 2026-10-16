# MONDE Mini — source-attributed CSV Point ingestion (WORK-0019)

This product increment turns a local UTF-8 CSV dataset into the existing
evidence-grounded World Model and the offline HTML evidence map, without a
new database, remote service or additional package.

Example source CSV (longitude,latitude are WGS84 degrees):

    id,longitude,latitude,label
    place-001,2.3522,48.8566,Paris
    place-002,-73.9857,40.7484,New York

Import with explicit source and temporal provenance:

    PYTHONPATH=src python3 -m monde.world \
      --fixture examples/monde-mini.json --ingest-csv points.csv \
      --source-id open-csv --source-locator dataset://original/points.csv \
      --captured-at 2026-01-10T10:00:00Z --valid-from 2026-01-01T00:00:00Z \
      --state-out saved.json

For columns uid,lon,lat use the CSV ID/lon/lat column flags.
Then view in the existing offline map:

    PYTHONPATH=src python3 -m monde.map_view --state saved.json \
      --bbox '2.34,48.84,2.36,48.87' --at 2026-01-02T00:00:00Z \
      --known-at 2026-01-10T10:00:00Z --output evidence.html

All nonempty extra property cells stay original source strings, not inferred
numeric types. Empty cells are unknown rather than zero. Identifiers are explicit
and unique per batch. Validation reuses the original strict GeoJSON claim adapter.
A failed import does not mutate the existing saved state, and no output overwrites
its input by default. This prototype accepts up to 50,000 CSV rows per batch.

Reported coordinates are not verified positions. A corrected source must supply
new evidence and explicit supersession using MONDE's existing update behavior;
it must never overwrite an old reported position as independent physical truth.
