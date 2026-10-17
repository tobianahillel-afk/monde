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

## Query original source coverage at a knowledge cutoff

Read the persisted snapshot to inspect which independent source reports MONDE
had at a specific knowledge-time cutoff:

```sh
PYTHONPATH=src python3 -m monde.source_inventory --state world.json \
  --known-at 2026-01-11T10:00:00Z
```

Output lists each original source ID separately, including independent
GeoPackage layers, the original source locator(s), evidence count, recorded
assertion count, distinct entity count, attributes and timestamp ranges.
Reports captured after the cutoff and assertions learned later are excluded.
This **read-only** inventory does not modify the original datasets or
persistent snapshot and does not imply truth, confidence or physical movement.


## Preview a source capture without changing saved state (WORK-0044)

Inspect source-reported changes, including before/after values and the
original source locator, **before** deciding to save another world snapshot:

```sh
PYTHONPATH=src python3 -m monde.world \
  --fixture previous-world.json \
  --preview-source-manifest updated-sources.json
```

The result is a JSON report labeled `PREVIEW_NOT_SAVED`. No output state is
created or overwritten. Both earlier and incoming values are **source claims**,
not reconciled physical truth. Missing rows never imply that features were
deleted. Invalid, ambiguous, or stale captures reject without output state.
The analyst can then run the existing `--refresh-source-manifest`
command with a new `--state-out` after reviewing the evidence.
Changing the manifest between preview and refresh requires a new inspection.

## Preview new source Point reports on an offline map (WORK-0044)

Create a local map **before** accepting a later capture. The HTML contains only
newly recorded source-reported Points, with source identity, original locator,
valid/knowledge times and correction ancestry. It is **not** a map of verified
physical movement or deletions:

```sh
PYTHONPATH=src python3 -m monde.world \
  --fixture previous-world.json \
  --preview-source-manifest updated-sources.json \
  --preview-source-map capture-preview.html
```

The command still prints the ordinary `PREVIEW_NOT_SAVED` JSON summary;
`preview_map_html` identifies the created offline visualization. It does
not create or alter a WorldMini snapshot. The HTML output must be a **new path**
(existing output, the manifest, source files and the original snapshot cannot
be overwritten). An invalid capture produces no map. No network access is
needed to open the generated page.
