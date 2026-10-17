# MONDE Mini — Local read-only HTTP API (WORK-0050)

This optional adapter **reuses** the same saved MONDE Mini World Model and
query functions used by the CLI and offline map. It does not reconcile source
claims into physical truth, infer locations, ingest evidence, or update state.

With an existing MONDE Mini saved snapshot, run:

```bash
PYTHONPATH=src python3 -m monde.local_api --state world.json --port 8765
```

The process binds only to **127.0.0.1**, with exact loopback Host validation.
It is intended for one machine's tools and prototypes, not deployment to a
network, cloud instance, iframe or untrusted local browser. No authentication,
CORS access or public HTTPS endpoint is provided. The server loads one snapshot
at startup; to see new source captures, stop and restart it with a new snapshot.

Endpoints (GET, all JSON):

- `/health` — read-only status.
- `/reports?entity=building-001&attribute=floors&at=2026-01-02T00%3A00%3A00Z&known_at=2026-01-07T00%3A00%3A00Z`
  — original source assertions, with provenance and bitemporal cutoff.
- `/entity?entity=building-001&at=...&known_at=...` — all currently
  reported attributes, preserving contradictory reports and explicit UNKNOWN.
- `/disagreements?at=...&known_at=...&attribute=floors` — distinct
  cross-source values; `attribute` is optional.
- `/map?bbox=1,45,6,51&at=...&known_at=...` — WorldMini's existing
  source-report GeoJSON, including conflicting coordinates.
- `/tile?z=5&x=16&y=11&at=...&known_at=...` — GeoJSON for a WGS84
  viewport derived from a standard XYZ Web Mercator tile, including the original
  source Point assertions and tile metadata; this is not a raster tile service.
- `/nearest?center=2.3522,48.8566&limit=10&at=...&known_at=...` —
  nearest **source-reported** Point entities, ranked by approximate spherical
  distance, not inferred ground-truth positions (maximum 1000 entities).
- `/radius?center=2.3522,48.8566&radius_km=5&at=...&known_at=...` —
  source Points within a radius, keeping conflicting out-of-radius reports of
  matched entities. Distance is not a measure of positional accuracy.

Queries always require explicit valid world time `at` and knowledge time
`known_at` except `/health`. Duplicate/missing/unknown parameters, malformed
bounds/times and non-loopback Host headers are rejected. POST/PUT/PATCH/DELETE
return HTTP 405 and cannot change source state. Output is bounded by default
to 2 MB; larger responses fail with HTTP 413 rather than truncating evidence.
The API deliberately exposes only WorldMini's existing observed/source-reported
methods, not inferred ground truth. It does **not** expose the full saved state,
browse the filesystem, enable CORS or call an external service.

This is an **unmerged candidate** dependent on WORK-0049 and its stacked chain;
CI proves the tested branch, not delivery on `main`.
