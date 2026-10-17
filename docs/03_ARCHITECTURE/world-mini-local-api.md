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
- `/map-disagreements?bbox=2.3,48.8,2.4,48.9&at=T&known_at=K` —
  original source Point disagreements within a viewport. Disagreement is
  calculated across *all* sources before clipping, so an offscreen opposing
  report still identifies an on-screen conflict. No consensus position.
- `/map-knowledge-changes?bbox=2.3,48.8,2.4,48.9&at=T&from_known_at=K1&to_known_at=K2` —
  entering/leaving source Point assertions at fixed world time. Entities are
  selected if they intersect the viewport at either knowledge cutoff; changed
  positions outside the viewport are retained with evidence and IDs.
  Learning a new report does not prove physical movement.
- `/map-world-changes?bbox=2.3,48.8,2.4,48.9&from_at=T1&to_at=T2&known_at=K` —
  observed source *reports* whose validity changes at fixed knowledge cutoff.
  These are not verified physical movements.
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
- `/timeline?entity=building-001&attribute=floors&from_at=T1&to_at=T2&known_at=K`
  — source-reported intervals and explicit UNKNOWN gaps, at fixed knowledge K.
- `/compare-knowledge?entity=building-001&at=T&from_known_at=K1&to_known_at=K2`
  — reports newly known or corrected at unchanged world time T.
- `/compare-world?entity=building-001&from_at=T1&to_at=T2&known_at=K`
  — changes in source-reported validity, not proof of physical-world events.
- `/source-history?source=city-registry&known_at=K&entity=building-001&attribute=floors`
  — that source's original and superseded assertions with evidence lineage.
  `entity` and `attribute` are optional filters.
- `/disagreement-changes?at=T&from_known_at=K1&to_known_at=K2&attribute=floors`
  — how cross-source contradictions evolved as additional reports were learned.
  `attribute` is optional.

- `/knowledge-updates?from_known_at=K1&to_known_at=K2&entity=building-001&attribute=floors`
  — evidence-linked source reports learned during (K1, K2], including corrections.
  `entity` and `attribute` are optional. This is a historical change feed,
  **not an exactly-once replication cursor**.
- `/knowledge-timeline?entity=building-001&attribute=floors&at=T&from_known_at=K1&to_known_at=K2`
  — UNKNOWN and REPORTED intervals for one world-time as knowledge evolved.
- `/world-knowledge-changes?at=T&from_known_at=K1&to_known_at=K2`
  — entity-wide source-report changes at unchanged world-time T; no inference
  that physical objects changed.

These investigation routes reuse existing `WorldMini` methods: no new
temporal engine, mutable state, model prediction or inferred consensus.
For temporal comparisons and the knowledge-change feed, `K1 < K2` or `T1 < T2` is required, and query
timestamps must be explicit timezone-aware ISO-8601 values.

Queries require the exact temporal parameters for each endpoint, except
`/health`. An entity history can require only `known_at`; other queries distinguish
world-time and knowledge-time fields explicitly. Duplicate/missing/unknown parameters, malformed
bounds/times and non-loopback Host headers are rejected. POST/PUT/PATCH/DELETE
return HTTP 405 and cannot change source state. Output is bounded by default
to 2 MB; larger responses fail with HTTP 413 rather than truncating evidence.
The API deliberately exposes only WorldMini's existing observed/source-reported
methods, not inferred ground truth. It does **not** expose the full saved state,
browse the filesystem, enable CORS or call an external service.

This is an **unmerged candidate** dependent on WORK-0049 and its stacked chain;
CI proves the tested branch, not delivery on `main`.


### Open the map directly in a local browser (WORK-0052)

The same already-existing standalone map renderer can now be served by the
read-only loopback API. In a browser on the machine running MONDE Mini, visit:

- `/viewer?view=current&bbox=2.3,48.8,2.4,48.9&at=T&known_at=K` — original source-reported Points in the viewport.
- `/viewer?view=disagreements&bbox=2.3,48.8,2.4,48.9&at=T&known_at=K` — original source Point reports that disagree across distinct sources. The disagreement is determined before viewport clipping, so offscreen opposing evidence remains identified and no consensus position is fabricated.
- `/viewer?view=knowledge-changes&bbox=2.3,48.8,2.4,48.9&at=T&from_known_at=K1&to_known_at=K2` — learn/correction changes at fixed world time, **not physical motion**.
- `/viewer?view=world-changes&bbox=2.3,48.8,2.4,48.9&from_at=T1&to_at=T2&known_at=K` — validity changes at fixed knowledge, **not verified events or movement**.

Replace T/K placeholders with URL-encoded UTC timestamps. This produces a
self-contained HTML map with source/evidence IDs and the existing timeline,
zoom, pan and evidence-inspection controls. No JavaScript API fetches, online
tiles, cross-origin scripts, browser persistence, public listener or data
mutations are introduced. It is designed for **trusted local users only**;
it is not an authenticated shared web service. All inputs follow the same
strict duplicate/unknown-parameter, spatial and temporal validation as the
corresponding GeoJSON endpoints. Responses are bounded by the server's
configured limit, marked `no-store`, and deny framing.


### Guided local map explorer (WORK-0052)

Open **http://127.0.0.1:8765/explore** after starting the local API.
Four native HTML GET forms open existing original source observations,
source disagreements, knowledge-time changes and world-time changes.
They submit only each viewer's accepted parameters. The bbox is an editable
WGS84 example, not a user location; all timestamps must be explicit and
timezone-aware ISO-8601. This entry page has no JavaScript, online tiles,
external scripts or writes. It is bounded, read-only, frame-denied and
loopback-only, with CSP form-action limited to self. Unknown query parameters
to /explore receive HTTP 400.
