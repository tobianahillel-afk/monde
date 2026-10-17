# Persistent original-source WorldMini (WORK-0041)

Turn an original-source manifest containing local CSV, GeoJSON, GPX, KML,
KMZ and GeoPackage datasets into a durable bitemporal WorldMini evidence
state, without creating a map or introducing a new parser or dependency.

    PYTHONPATH=src python3 -m monde.world \
      --ingest-source-manifest sources.json --state-out world.json

A seed fixture is optional for this operation. To extend an existing state
pass --fixture previous.json and write a different --state-out next.json.

The existing temporal/spatial queries and offline map can open the output:

    PYTHONPATH=src python3 -m monde.world --fixture world.json \
      --export-geojson --at 2026-01-02T00:00:00Z \
      --known-at 2026-01-11T10:00:00Z

    PYTHONPATH=src python3 -m monde.map_view --state world.json \
      --at 2026-01-02T00:00:00Z \
      --known-at 2026-01-11T10:00:00Z --output map.html

The importer reuses the existing manifest reader and atomic WorldMini.save.
Bad late sources cause no partial snapshot, original source data is
unchanged, and prior output cannot be replaced unless the caller explicitly
supplies --replace-state. The legacy --ingest-csv-manifest flag still works.

Original coordinates and timestamps are source-reported evidence, not
reconciled geographic truth. No geocoding or physical-motion inference.
The original bounds of 16 datasets and 50,000 source reports remain.
