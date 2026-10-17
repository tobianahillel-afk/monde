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
- `/map?bbox=2.3,48.8,2.4,48.9&at=T&known_at=K&source=survey-1` — optional
  **single-original-source** evidence lens. The source's own Point must
  intersect the viewport to select an entity; the same source's other
  positions for that entity remain visible as contrary reports. The response
  preserves each assertion and its provenance, contains `monde_source_filter`,
  and updates its displayed result counts. It does **not** imply that another
  source agreed or that a position is verified physical truth. The same
  optional filter is available in `/viewer?view=current&...` and its native
  evidence/time-navigation forms; other views remain explicitly unfiltered.
  The local `/explore` form suggests source IDs that have at least one original
  `geo_point` assertion in the saved snapshot. Up to 200 alphabetical IDs
  appear as native browser suggestions; manually entering any valid source ID
  still works. Suggestions do not assert that a source has an active Point at
  the chosen world-time/knowledge-time cutoff. No browser script or network
  dependency is added.
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

### Nearby source-reported observations in the local browser (WORK-0053)

Open `http://127.0.0.1:8765/explore` to use the two new **proximity
map** forms alongside the four existing evidence views. They do not
geolocate the current user: enter the search center explicitly.

- `/viewer?view=nearest&center=2.3522,48.8566&limit=10&at=T&known_at=K`
  shows the nearest source-reported Point entities (1–1000). All current
  competing source Point locations of selected entities remain distinct;
  distance is calculated from reported coordinates, not an estimated
  true position or measurement accuracy.
- `/viewer?view=radius&center=2.3522,48.8566&radius_km=5&at=T&known_at=K`
  maps entities with at least one source-reported Point inside the radius.
  **Other current source reports of those entities remain on the map even
  when their coordinates are outside the radius**, preserving disagreements.

Both modes reuse the existing `WorldMini.export_geojson_nearest` and
`WorldMini.export_geojson_radius` selectors **unchanged**. The existing
`monde.map_view.render_map` now also accepts their source-evidence documents:
it derives a **display-only envelope** from the original selected coordinates
to reuse the standalone offline map. This display envelope is NOT the search
radius, the ranking criterion, a new source claim, or a physical position
estimate. Original `monde_nearest_query` / `monde_radius_query` metadata
and every original competing source position remain included; the radius view
distinguishes inside/outside reports using `monde_within_radius`.
The existing loopback-only HTTP server enforces exact params, world and
knowledge cutoffs, response limits, no-store, no-network CSP, no writes,
and saved-state immutability. There is no online basemap, new proximity
algorithm, geolocation permission or external API.

### Inspect original entity reports and source history in a local browser (WORK-0054)

Open `http://127.0.0.1:8765/inspect` or follow **Inspect original entity
reports and source histories** from `/explore`. Three native GET forms expose
only the existing `WorldMini.entity_snapshot`, `WorldMini.query`, and
`WorldMini.source_history` functions:

- `/inspect?view=entity&entity=building-001&at=T&known_at=K` — every
  source-reported attribute, including original conflicting source claims.
- `/inspect?view=reports&entity=building-001&attribute=floors&at=T&known_at=K`
  — source evidence and provenance for one attribute at explicit world/knowledge time.
- `/inspect?view=source-history&source=city-registry&known_at=K` — source
  assertions and their corrections up to K; optional `entity`/`attribute`
  parameters may narrow the history.

The browser renders each full original report in an expandable, HTML-escaped
evidence record (including evidence and assertion IDs, source locator,
original event/capture time, validity and knowledge cutoffs). It never
merges contradictory reports or infers truth. An empty result is explicitly
**UNKNOWN**, not zero, false or proof of absence. Links to the unchanged
original JSON endpoints make the complete machine-readable evidence available.
The inspection HTML has **no browser scripts or external requests**, and
inherits loopback-only hosting, strict argument validation, size limits,
no-store, frame denial, and no saved-state mutation. This remains an
**unmerged stacked candidate**; the GitHub Actions tests cover its branch.

### Map selection to full original evidence (WORK-0055)

A selected original source Point in the local /viewer now exposes links to the
complete entity dossier and original source revision history on the same
loopback server. The selected entity/source and explicit time cutoffs are
encoded by URLSearchParams, never used as raw HTML. A NO_LONGER_CURRENT
comparison uses the earlier valid/knowledge cutoff to inspect retired source
reports; newly current evidence uses the later cutoff. The map shows a filtered
subset; the complete dossier can contain other reports. This is not inferred
truth, a physical-world change or proof of absence. The standalone/offline CLI
keeps the links inactive. No remote API or mutable endpoint was added. This
is still an unmerged stacked proposal after WORK-0054.

### Return to the original source Point from a dossier (WORK-0055)

A loopback `/inspect` entity dossier, single-attribute report or source-history
record now links each **original `geo_point` source assertion** back to the
existing local `/viewer?view=radius` map, centered on the *reported* coordinate
(1 km display search). This is navigation among already-saved source claims, not
geocoding, inferred entity position or verification of ground truth. Entity and
attribute views preserve the chosen world/knowledge cutoff; source history uses
the surviving assertion's original validity start and requested knowledge cutoff.
Superseded history assertions deliberately have no map link because the current
report map would otherwise show a different assertion instead. Other competing
current source positions of a matching entity remain visible, including those
outside the radius. Invalid/non-Point values get no link. URLs are query-encoded,
HTML-escaped, and stay same-origin; the inspector remains script-free and every
endpoint remains read-only. End-to-end tests follow the link through the loopback
server and check that the saved World Model is byte-for-byte unchanged.


### Comparing knowledge of one entity in the browser (WORK-0056)

The read-only local /inspect browser form now supports view=compare-knowledge
with entity, at, from_known_at, and to_known_at. It directly calls the
existing WorldMini.compare_knowledge entity query; the matching JSON response
is already available at /compare-knowledge with the same non-view parameters.

The same physical-world time (at) is used on both sides. The earlier and
later knowledge cutoffs select the original reports marked "No longer current"
and "Newly current". Their full unmodified report dictionaries, source IDs,
evidence IDs, locators, and timestamps are HTML-escaped and displayed. A
difference in knowledge is NOT proof of an observed physical-world change.
When no report changed the page says UNCHANGED rather than UNKNOWN or absent.

For original geo_point corrections, links to the existing local map viewer
retain the correct historical state: retired source-reported Points use
from_known_at, and newly current Points use to_known_at. No geolocation is
inferred or corrected by the UI; the offline map, saved snapshot, loopback
restriction, no-network Content Security Policy, and strict GET interface
remain intact.


### Comparing source-reported world-time validity in the browser (WORK-0056)

The same read-only `/inspect` browser now offers `view=compare-world`
with an entity, two world-time instants (`from_at`, `to_at`) and one fixed
knowledge cutoff (`known_at`). This reuses `WorldMini.compare_world_time`
directly; the unmodified JSON is available at `/compare-world`.

Where `compare-knowledge` holds world time fixed and varies what was known,
`compare-world` holds knowledge fixed and varies **source-reported validity**.
The original assertions and provenance are displayed as reported at the
earlier and later instants. Differences **do not prove physical change**.
Source-reported Points link to their actual earlier/later world-time map states,
with the same knowledge cutoff. Unchanged results are labeled UNCHANGED rather
than inferred absence. No additional data model, service, writable route,
remote call or external dependency was introduced.

### One-click temporal change map

From either entity comparison in `/inspect`, open a **combined source-reported
Point change map** with a single link. The link reuses the existing read-only
`/viewer` knowledge-change or world-change map, preserving the exact temporal
cutoffs and selecting a viewport around both earlier and later source-reported
positions. This is an area query: nearby evidence may also appear. It does
**not** infer verified physical motion. A map link is not shown when no original
source Point changes, or when positions cross the antimeridian and a naive
viewport would misleadingly cover almost the globe. Original per-source
position links remain available. No additional service, dependency or write.

### Dateline-crossing source comparison maps (WORK-0056)

The one-click temporal comparison map uses the shortest circular longitude
arc for original source-reported Points. Across ±180°, a wrapped WGS84 bbox
(west > east) reuses the existing WorldMini and map viewer, avoiding a false
near-global rectangle. Widely dispersed reports spanning more than 180°
still have no misleading combined map link. Original reports, cutoffs,
provenance and saved state remain unchanged. A real local HTTP test follows
the wrapped viewer link and verifies both original Point change reports.


### Change world validity and knowledge time on the open map (WORK-0057)

Local /viewer maps include an expandable **Explore another world / knowledge
time** form. Editing the UTC world-validity and knowledge cutoff opens the
same map or proximity query at those times, preserving its geographic viewport,
center, mode and distance or limit. Current maps can switch to cross-source
disagreements without returning to /explore.

Knowledge/world comparison maps preserve their earlier/later temporal cutoffs.
This is a native read-only GET /viewer over existing WorldMini queries:
no new model, inferred physical movement, external service, upload or saved-state
change. Standalone offline CLI maps intentionally show no server-dependent form.

### Source-specific proximity maps (WORK-0058)

The existing local `/nearest`, `/radius` JSON and matching `/viewer` routes now
accept an optional original `source` ID. Selection takes place **before**
nearest ranking and radius qualification: another source cannot take a
nearest-result slot or qualify an entity for the selected source. The map
retains only the selected source's original assertions; this is not consensus
geography. Native world-time/knowledge-time forms preserve the source choice.
Without `source` the API payloads remain unchanged. Queries remain read-only,
strictly validated, local and independent of external APIs.
