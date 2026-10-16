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

## Batch import: multiple original CSV datasets

Pass a UTF-8 JSON manifest to `--ingest-csv-manifest sources.json` with `--fixture examples/monde-mini.json --state-out combined.json`. The manifest has exactly one `datasets` array containing 1–16 entries. Every entry declares `csv`, `source_id`, `locator`, `captured_at`, `valid_from`; optionally `valid_to`, `source_event_at`, `id_column`, `lon_column`, `lat_column`. Paths are relative to the manifest.

Example:

    {"datasets":[
      {"csv":"city-a.csv","source_id":"city-a","locator":"dataset://a",
       "captured_at":"2026-01-10T10:00:00Z","valid_from":"2026-01-01T00:00:00Z"},
      {"csv":"city-b.csv","source_id":"city-b","locator":"dataset://b",
       "captured_at":"2026-01-11T10:00:00Z","valid_from":"2026-01-01T00:00:00Z",
       "id_column":"uid","lon_column":"lon","lat_column":"lat"}
    ]}

The existing source-to-GeoJSON adapter and atomic `append_documents` commit preserve each source report independently. An invalid later source rejects the entire batch without writing the output state. The manifest permits at most 50,000 Points across all datasets; it never geocodes, reconciles physical positions or infers event times.

## Direct CSV-to-offline-map workflow (WORK-0021)

For local source datasets, a separate persisted JSON state is **not required**
to generate an interactive, standalone evidence map. Reuse the same CSV manifest
(with explicit source, capture time and valid-world time) used for batch import:

    PYTHONPATH=src python3 -m monde.map_view \\
      --csv-manifest sources.json \\
      --bbox '2.3,48.8,2.5,48.9' \\
      --at '2026-01-02T00:00:00Z' \\
      --known-at '2026-01-11T10:00:00Z' \\
      --output evidence.html

Open `evidence.html` locally; no server, account, external tile provider or
internet connection is needed. The page retains **source assertions and their
individual evidence identities** (including contradictory positions), not a
reconciled/verified location. The viewport and knowledge cutoff are explicit.
Existing `--compare-known-at` and `--compare-at` modes also work with this
input. For persistent updates and historical snapshots, keep using the separate
`--ingest-csv-manifest ... --state-out ...` command followed by `--state`.
The input choice is exclusive (`--state` **or** `--csv-manifest`). Invalid
input produces no HTML file; existing destination files and source CSV/manifest
files cannot be overwritten. Limits remain 16 datasets / 50,000 Points, with
standalone-map limits of 5,000 included source reports and 3 MB embedded JSON.


### Automatic geographic framing (T3)

You can now omit `--bbox` (or use `--bbox auto`) for both saved states and
CSV manifests. MONDE chooses a viewport from the source-reported Points
visible at the requested world and knowledge timestamps, with a small padding.
For example:

```sh
PYTHONPATH=src python3 -m monde.map_view \
  --csv-manifest sources.json \
  --at 2026-01-02T00:00:00Z \
  --known-at 2026-01-11T10:00:00Z \
  --output evidence-map.html
```

When comparing world or knowledge time, automatic framing uses the reports
visible at **both** cutoffs. It takes the shortest longitude arc across the
antimeridian, rather than mistakenly showing almost the entire globe for
reports at +179.8° and -179.8°. The viewport is a convenience for displaying
source claims, **not** a reconciled location, confidence estimate or evidence
that other places are empty.

If there are no known source Points at the chosen cutoffs, automatic framing
fails explicitly without creating HTML; supply a manual `--bbox W,S,E,N`
if you deliberately want an empty map. Explicit `--bbox` behavior is unchanged.
