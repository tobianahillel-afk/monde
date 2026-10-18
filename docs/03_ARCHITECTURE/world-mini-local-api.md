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
  evidence/time-navigation forms. The same original-source lens now also
  applies to `/map-knowledge-changes`, `/map-world-changes` and their
  `/viewer` historical maps. Qualification requires a **changed report from
  that source** inside the bbox at either cutoff; both old/new source reports
  for qualifying entities remain, even if the other position is offscreen.
  Source-specific counts exclude unrelated sources. Time differences are
  source reports, never verified physical changes. Disagreements, nearest
  and radius remain explicitly unfiltered.
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

### Investigate contradictory source Points by original source (WORK-0065)

The local `/explore` disagreement map can now focus on a selected original
source ID. `/viewer?view=disagreements` and `/map-disagreements` accept an
optional `source` query parameter. An entity qualifies only when that source's
**own conflicting Point is inside the requested WGS84 viewport**. Every other
original contradictory report exported for the qualified entity remains visible
or discoverable, even when its point lies outside the viewport. This is **not**
a source-only subset or a consensus location; filtering must never conceal the
opposing evidence. The unfiltered JSON/map is unchanged. Native world-time and
knowledge-cutoff navigation retains the selected source. All operations are
read-only and use the existing offline source assertions without new dependencies.

### Original opposing-source evidence report (WORK-0066)

The local `/explore` Source disagreements form offers **Read opposing original evidence** to open `GET /disagreement-report?bbox=W,S,E,N&at=UTC&known_at=UTC[&source=ID]`. This script-free, loopback-only HTML groups original conflicting Point reports by entity, exposing source/assertion/evidence identities, original coordinates, entity dossiers and links to the map and GeoJSON. A selected source qualifies an entity with its own Point inside the viewport; original opposing reports outside the viewport remain visible. An empty report is not evidence of source agreement or absence. The existing strict GET parsing, CSP, response-size limit and unchanged saved snapshot apply.


### Direct original-disagreement CSV export (WORK-0067)

The read-only local HTML source-disagreement report now links to
GET /disagreement.csv?bbox=...&at=...&known_at=...&source=optional.
CSV preserves original entity, source_id, assertion_id, evidence_id,
WGS84 reported Point, source Point in/out-of-viewport indicator, and
both original world and knowledge cutoffs. Selected source qualifies
a conflict but never hides the opposing reports, even outside the bbox.
CSV data uses standard quoting and neutralizes spreadsheet formulas in
text identifiers. These are **original conflicting assertions**, not a
verified location, physical motion or reconciled consensus. Unfiltered
reports keep their existing behavior; no data writes or new dependencies.


### Complete source-focused GeoJSON evidence (WORK-0068)

When an analyst selects `source` in `/disagreement-report`, its **Open
read-only GeoJSON** link now returns exactly the same qualifying original
opposing Point reports as the HTML report and `/disagreement.csv`. A source's
own disputed Point must be inside the bbox; opposing source positions **outside
that viewport** remain in the GeoJSON with their assertion/evidence IDs and
`monde_inside_bbox` flags. This prevents a filtered map download from
silently dropping contradictory evidence. Only the optional `source` version
of `/map-disagreements` uses the existing full disagreement viewer selection.
Without `source` (or when it is blank), the legacy WorldMini JSON response
remains unchanged. No inferred location, new endpoint or persisted-state write.

## Focus one conflicting entity in original evidence (WORK-0069)

The existing read-only `/disagreement-report`, `/disagreement.csv`,
`/map-disagreements` and `/viewer?view=disagreements` accept an optional
`entity=<original-id>` selection. Analysts can follow a per-entity HTML report
link, preserving all opposing original source Points, even outside the viewport,
and retaining both temporal cutoffs. If a source filter is also present, that
source alone must qualify inside the viewport before the entity filter applies.
The native map time form retains the entity. Unfiltered routes are unchanged,
and an unknown entity is an empty evidence result, not evidence of agreement.

### Navigate focused original disagreements through time

The read-only `/disagreement-report` now provides a native GET form to change world-valid time or knowledge cutoff while retaining the selected bounding box, original source and entity. It reuses the existing evidence query and never infers physical truth or mutates saved assertions. Inputs are escaped and invalid cutoffs continue to fail validation.


### Compare one source disagreement across two knowledge cutoffs (WORK-0069)

The existing read-only `/disagreement-report` accepts an optional earlier
`from_known_at` strictly before `known_at`. A native GET form compares the
original evidence in the same bbox, fixed world time, source and entity at
both knowledge cutoffs. The UI distinguishes cases appearing/disappearing from
the **selected evidence view**, revised original report sets, and unchanged
reports. It includes complete earlier original source evidence, map, CSV and
GeoJSON links, retaining offscreen opposing source claims. No claimed physical
movement, consensus position, storage mutation or new dependency.


### Compare original disagreements across world-valid time

The existing read-only `/disagreement-report` accepts optional earlier `from_at` alongside later `at`, at a fixed `known_at`. Its native browser form shows earlier and later original source Point assertions for the same viewport, source and optional entity, with existing earlier map/GeoJSON/CSV links. The two comparison axes `from_at` and `from_known_at` are mutually exclusive. A selected source independently qualifies using its own in-bounds Point at each cutoff; conflicting offscreen evidence is retained. Labels describe changes in selected original evidence, **not** actual physical movement or ground truth. Single-cutoff exports and persisted state are unchanged.


### Download an original disagreement comparison (WORK-0071)

`GET /disagreement-compare.json?bbox=W,S,E,N&at=T2&known_at=K&from_at=T1`
compares source disagreements at two world times with fixed knowledge.
Alternatively, use `from_known_at=K1` and fixed `at=T` to compare knowledge.
Exactly one earlier cutoff is required. Optional `source` and `entity` filters
retain opposing original evidence and the selected viewport. The existing
read-only disagreement report exposes a **Download complete original comparison
JSON** link for either mode. The response includes the two original selected
GeoJSON documents, their independent time labels, and per-entity *selection*
changes (`APPEARED IN SELECTION`, `NO LONGER IN SELECTION`,
`REPORTED EVIDENCE CHANGED`, or `SAME REPORTED EVIDENCE`). Neither unchanged
selection nor an empty result proves agreement, actual location or movement.
The endpoint preserves original provenance and never changes saved state.

## Original disagreement comparison CSV (WORK-0072)

From a historical /disagreement-report, download a source-preserving table via
GET /disagreement-compare.csv alongside the existing complete comparison JSON.
It accepts precisely one earlier world-time `from_at` or knowledge-time
`from_known_at`, plus current bbox, `at`, `known_at` and optional source/entity.
Rows identify earlier/later selection, comparison axis, source's original
assertion/evidence IDs, WGS84 point, inside/outside viewport, both time cutoffs
and reported-evidence classification. All opposing offscreen sources remain.
These classifications describe changed source reports, not verified physical
movement, inferred agreement or consensus. Empty selections return a header-only
CSV. Text IDs are inert in spreadsheet software, responses are read-only and
bounded, and the saved WorldMini snapshot remains unchanged.


## Changed-only original disagreement comparison (WORK-0073)

For a two-cutoff `/disagreement-report`, `/disagreement-compare.json`, or
`/disagreement-compare.csv`, add `changes_only=1` to see only entities whose
*selected original source evidence* appeared, disappeared or changed between
cutoffs. The browser report provides links to toggle this focus. This is **not**
a determination that a real-world location changed or that other sources agree.
Classification is computed before filtering, and for every qualifying entity
all opposing original Points (including offscreen reports), source/assertion/
evidence identifiers, and bitemporal cutoffs remain available in JSON/CSV.
The filter requires exactly one earlier cutoff (`from_at` or `from_known_at`)
and does not change unfiltered map/export behavior. A result with no changed
entities means only that the selected evidence was unchanged, not that no
conflict exists or that a source statement is verified truth.


### Original disagreement change type (WORK-0074)

For a two-cutoff `/disagreement-report`, `/disagreement-compare.json` or
`/disagreement-compare.csv`, optional `change_kind=appeared|disappeared|modified`
focuses the existing original-source evidence comparison on one selected
classification. The HTML report links to each type and back to the complete
comparison. Classification happens before filtering; all opposing original
source Points, including offscreen evidence and IDs, are retained for matching
entities in both periods. Report-selection changes are not verified physical
movement or proof of absence. Other routes and invalid types reject the filter.

### Map-ready original bitemporal disagreement GeoJSON (WORK-0075)

The read-only comparison report links to /disagreement-compare.geojson,
using exactly one earlier knowledge or world-time cutoff. This combines both
sets of original source Points into a GeoJSON FeatureCollection for map tools.
Each report retains original geometry, evidence/assertion/source identifiers,
inside/outside-viewport flags, and separate original feature ID, period,
classification, world-valid time and knowledge cutoff. The export feature ID
is period-qualified, not a replacement assertion ID. Existing changes_only,
change_kind, source and entity filters apply consistently, retaining opposing
offscreen reports; empty results are valid empty FeatureCollections. These are
source reports, not confirmed movement or consensus. The endpoint reuses the
local host restrictions, response limits and immutable persisted snapshot.
This candidate depends on unmerged WORK-0074 / PR #105.

### Focus source or entity inside the evidence report (WORK-0076)

The existing read-only `/disagreement-report` page now includes an expandable
**Focus another original source or entity** native GET form. Analysts can type,
change or clear the source ID and entity ID without returning to `/explore`.
The form preserves the viewport, current world-valid time, knowledge cutoff,
one optional earlier world/knowledge cutoff and the existing change filters.
Suggestions come only from the reports already selected; other IDs can be typed.
As with the JSON/CSV/GeoJSON exports, a source qualifies using its *own*
in-viewport Point; opposing source Points remain in the selection, including
positions outside that viewport. Clearing a filter does not confirm an
inferred location or source truth. The saved WorldMini file stays unchanged,
and existing loopback/CSP/input validation still applies. This candidate
stacks on unmerged WORK-0075 / PR #106.


### Both original disagreement periods on one offline map (WORK-0077)

On a two-cutoff disagreement report, the new **Map both original evidence periods**
link opens the existing local /viewer with view=disagreement-comparison.
It preserves the selected source, entity, change_kind/changes_only filter,
viewport and both world/knowledge time cutoffs. This is the same evidence
selection as /disagreement-compare.geojson, embedded in the established
standalone browser map: period-qualified original feature IDs, original
source/assertion/evidence IDs, reported coordinates, inside/outside viewport
flags, classification and per-report world/knowledge cutoffs remain intact.

The map's viewport metadata is display framing only. Earlier evidence is
not reassigned to the later time. The browser visibly warns against inferred
physical movement, verified source truth or consensus. All output is
read-only, loopback-only and subject to the existing CSP and response limits.
The persisted WorldMini snapshot is unchanged. This draft feature is stacked
on unmerged WORK-0076 / PR #107, not yet deployed on main.


### Download standalone two-period source-evidence map (WORK-0078)

From a two-cutoff original disagreement report, Download offline comparison map
saves a self-contained HTML rendering of the same original source reports
provided by /disagreement-compare.geojson. The read-only loopback
/disagreement-compare.html endpoint accepts the same bbox, world and
knowledge cutoffs, optional source/entity focus and changed-evidence filters;
exactly one earlier world or knowledge cutoff is mandatory. It reuses the
existing offline map renderer, disabling server-dependent inspector links so
the saved map is usable without a MONDE server. Original source/assertion/
evidence IDs, per-period cutoffs, epistemic warnings and opposing offscreen
reports remain embedded. The response uses an attachment filename, CSP with
no network access and existing response-size limits. No snapshot changes.
Candidate is stacked on unmerged WORK-0077 / PR #108.

### Filter earlier and later original reports inside saved comparison maps (WORK-0079)

The existing two-period disagreement `/viewer?view=disagreement-comparison` and
standalone `/disagreement-compare.html` display an **Original evidence period**
selector: both periods (default), earlier only, or later only. The same original
Point assertions and time cutoffs remain embedded in the document. Changing the
selector affects displayed markers, side lists and filtered exports only;
server JSON/GeoJSON/CSV, source provenance and the saved World Model are never
modified. A hidden point is not missing evidence, a verified location or
proof of physical movement. Other map modes keep the control hidden.

### Export complete selected original comparison period (WORK-0080)

The offline two-period disagreement map has an **Export complete original period
GeoJSON** button next to the existing Both / Earlier / Later selector. The
result contains every original Point assertion in the **already embedded
source/entity/time comparison selection** for the selected period, including
opposing reports outside the displayed bbox and reports hidden by browser
search, visibility, map zoom and source controls. Both (the default) exports
both periods; valid empty earlier/later periods export an empty FeatureCollection
rather than inventing reports. The export keeps the original comparison
metadata, source/assertion/evidence IDs, original geometries and time cutoffs.
`monde_complete_period_export` records period and original/exported counts,
and distinguishes this complete embedded selection from the existing
**Export visible GeoJSON** button. It neither downloads the entire World
Model nor infers truth, location, movement or agreement. No network access,
server dependency, package, new route or state mutation is introduced.

### Complete offline comparison-period CSV (WORK-0081)

The existing self-contained original disagreement comparison map now provides
**Export complete original period CSV** alongside complete GeoJSON. Choose
**both**, **earlier** or **later**. The tabular export contains the original
embedded source-reported Point selection, including offscreen opposing evidence,
period, comparison axis, world and knowledge cutoffs, original feature,
assertion, source and evidence identifiers, and coordinates. Display-only
viewport, text and source filters do not remove rows. Text cells are CSV-quoted
and spreadsheet-formula escaped; only validated Point coordinates are numeric.
The CSV is a flattened analyst table; use the existing complete GeoJSON for
full nested original metadata. Empty selected periods export a header-only
CSV, not synthetic evidence. No external requests, new endpoint, model or
persistent data modifications.

### Original source coverage matrix in offline comparison maps (WORK-0082)

An offline two-period disagreement map includes an expandable **Original source
coverage by comparison period** table. Each source's Earlier/Later/Total count
comes from **all original source reports embedded in the selected comparison**,
not viewport, search, source or period display filters. Choosing a source
filters the visible map to that source; clicking a nonzero **Earlier** or **Later**
count selects that source and its original evidence period in one action.
A **Source reporting across selections** selector filters the offline map to
sources present in both selections, only the earlier selection, or only the
later selection. It classifies the entire embedded original report selection
before display filters. Choosing a source row clears this group selector;
**Show all original sources** clears both source and coverage-class filters.
No absent report can establish physical absence.
Zero counts are not links and do not imply physical absence.
**Show all original sources**
clears only the source display selection; neither operation mutates the
embedded evidence or persisted World Model. Empty or asymmetric period counts
do not prove a physical absence, agreement or movement. The table uses
text-only DOM assignment for original untrusted source identifiers, with no
external network requests, new API, new model or dependency. The complete source
coverage table can be exported as a standalone **CSV** containing the comparison
axis, every embedded original source ID, earlier/later/total Point-report counts,
and explicit `BOTH_SELECTIONS`, `EARLIER_SELECTION_ONLY`, or
`LATER_SELECTION_ONLY` labels. The CSV is independent of presentation filters,
escapes untrusted spreadsheet formulas and says nothing about ground-truth
source presence, actual movement, or physical absence.


### Export complete original evidence for one comparison source (WORK-0083)

Each original source coverage row in the standalone comparison map has a
**Download GeoJSON** and **Download CSV** controls. Both save the selected
source's complete original Point reports from both comparison periods, retaining individual
assertion/evidence IDs, original source locations, temporal and comparison
metadata. It operates on the complete embedded comparison rather than
the current viewport, source/period control, or search results.

The GeoJSON export includes the explicit metadata object
monde_source_period_export: original source ID, both earlier/later counts,
complete embedded count, exported count and the
COMPLETE_EMBEDDED_SOURCE_NOT_DISPLAY_FILTERED scope label. The CSV reuses the complete-period analyst columns and spreadsheet-safe
quoting. It includes the original source, assertion/evidence IDs, period,
coordinates, temporal provenance and export scope for exactly the same original
features as GeoJSON, even if no markers are currently visible. The flattened
CSV complements, rather than replaces, full nested GeoJSON. Filenames are
fixed, not derived from untrusted source text. No endpoint, dependency,
network call, inferred ground truth or saved-world mutation is added.
The change is an unmerged stacked candidate on WORK-0082.

### Original source reports by entity across two periods (WORK-0083)

The standalone comparison map's source-coverage table now offers **Compare
entities**. Expanding a source row groups that source's original Point reports
by entity and shows earlier/later report counts and individual source assertion
IDs, evidence IDs and reported coordinates. Groups derive from the entire
embedded comparison, not the map's viewport, source, search or period display
filters. They retain competing original reports individually, without consensus,
inferred disappearance or physical movement. Source and entity labels use
DOM text assignment rather than HTML. This read-only offline interaction makes
no network request and never changes the persisted WorldMini snapshot.

Each entity's expanded comparison includes **Download entity GeoJSON** and
**Download entity CSV**. These preserve both periods' full original assertions,
evidence IDs, source Point coordinates and bitemporal context even when map
display filters hide every marker. GeoJSON records the exact original source,
entity, per-period counts and the explicit scope
`COMPLETE_EMBEDDED_SOURCE_ENTITY_NOT_DISPLAY_FILTERED`.
CSV reuses existing spreadsheet-safe complete-evidence columns. Each entity has
an independent **Both / Earlier / Later** export selector. Earlier/Later exports
contain only that period's full original source reports and preserve assertion,
evidence, source and bitemporal identity, irrespective of visible map filters.
GeoJSON records the selected period, exported count, original period counts and
the scope `COMPLETE_EMBEDDED_SOURCE_ENTITY_SELECTED_PERIOD_NOT_DISPLAY_FILTERED`.
The default Both export retains the previous structure. No new route, dependency,
network call, inferred truth or saved-world mutation.

From each original source/entity comparison row, **Show both periods on map** now reuses the offline viewer to focus and fit the selected source's original entity Point reports. It clears conflicting presentation filters, not the embedded source evidence; no claimed physical movement, consensus position, new endpoint or data mutation.

The expanded source/entity comparison also provides **Show this original report on map**
for each original source Point assertion. The browser restores that report's actual
earlier/later comparison period, chooses its exact source/entity and original Point,
and opens the existing selected-evidence inspector. Conflicting display-only filters
are reset, while the other source assertions, both embedded original periods, the
evidence provenance and persisted snapshot remain unchanged. The focus is on a
source-reported coordinate, not a reconciled actual location or inferred movement.

An individual earlier/later assertion in the expanded comparison row also has **Download this original report**. The offline GeoJSON contains exactly that original Point feature, its full source/assertion/evidence/temporal metadata and original two-period comparison context. `monde_single_report_export` identifies the exact assertion and declares `EXACT_ORIGINAL_ASSERTION_NOT_DISPLAY_FILTERED`. Source, search, viewport and period **display** filters do not truncate the download. The fixed filename avoids deriving a path from untrusted source IDs. No new route, remote request, inferred truth or persisted state mutation.

The same source-coverage row also offers **Download entity inventory CSV**. It
exports one row per original source/entity in the complete embedded two-period
selection: per-period original report counts, coverage category, and JSON arrays
of exact original assertion and evidence IDs. The exported inventory is not
limited by the current search, map window, source dropdown or selected display
period. Labels are source-reported coverage only, **not** inferred agreement,
physical movement or missing-world evidence. CSV fields use the existing
spreadsheet-safe quoting, with a fixed download filename. This reuses the
interactive grouping above; no new World Model, endpoint or service.


### Entity-first original source coverage (WORK-0084)

For either axis of the read-only two-period disagreement-comparison map, expand
**Original entity coverage across sources and periods**. Each entity row lists
the original reporting sources in earlier, later and both selections, and the
total original Point reports. Click an entity to return to the existing map
of all its embedded source reports across both periods. The **Download complete
entity and source coverage CSV** action exports one row per entity/source pair,
including earlier/later report counts and complete original assertion/evidence
ID lists as JSON text. The CSV is spreadsheet-formula escaped and is derived
from all *embedded* original reports, not viewport/search/source/period display
filters. Zero reporting within the selection is **not** evidence of physical
absence or consensus. No new endpoint, external network, hosted API, model,
inferred movement, or saved-state mutation is introduced.

Each original entity row now has a **Download original reports** control and a
separate Both / Earlier / Later export-period selector. It preserves the exact
original Point feature objects, source, assertion, evidence, bitemporal metadata
and the parent comparison context for every embedded source of the selected
entity, regardless of map viewport, search, source or displayed period filters.
The `monde_entity_period_export` metadata records scope, selected entity,
period and original report counts. No consensus/movement inference, external
request, new endpoint or saved WorldMini mutation occurs.

**Entity × original source × comparison period navigation (WORK-0084):**
Each source name in an entity's Earlier, Later or Both coverage cell is now an
interactive, read-only link to exactly that entity/source/period selection on
the already embedded offline evidence map. It clears contradictory presentation
filters and fits the selected original reports. Empty intersections show no
link. The source and entity IDs are assigned through text nodes; no new
network route, source inference, or persisted model change is introduced.

## Entity/source/period evidence downloads (WORK-0084)

In the offline comparison map, the entity-first coverage table now provides a
**Download GeoJSON** action next to each source in the Earlier, Later or Both
column. It exports only that original entity/source/period intersection from
the complete embedded source reports, even if viewport, search and period
presentation filters hide the evidence. Original features, assertion/evidence
IDs and comparison cutoffs remain unchanged. The export includes explicit
entity, source, selected period, original/selected counts and an evidence-only
scope; it does not infer physical movement, truth or absence. The filename is
fixed, never derived from untrusted source or entity names. No additional
service, browser dependency or WorldMini persistence change is introduced.


### Original reporting-source selection changes (WORK-0085)

In a two-period offline disagreement comparison, the original entity coverage table now filters entities by whether their **set of reporting source IDs** is identical or different between the earlier and later selections. Each row shows counts of earlier-only and later-only source IDs. This is **selection coverage**, not evidence of physical change, source disappearance, verified absence or truth.

The **Download reporting-source selection changes CSV** action exports only entity/source intersections present in exactly one selected period, including all original assertion/evidence IDs and report counts. The export uses the **complete embedded comparison evidence**, never map viewport/search/period presentation filters. The pre-existing complete coverage CSV and GeoJSON exports remain unchanged. No additional endpoint, network call, state mutation or dependency.


### Source-first original entity coverage (WORK-0086)

The offline two-period disagreement map now includes **Original sources: entity
coverage between periods**. For every original source ID, it shows how many
distinct original entity IDs were reported in the earlier and later embedded
selections, identifies source/entity combinations reported in only one selected
period, and links directly to that original source/entity/period evidence on the
existing map. Analysts can filter sources with changed or identical reported
entity-ID sets; these are reporting selections, **not evidence of physical
absence, movement, completeness or truth**.

The source-first download control reuses the existing complete source/entity
selection-change CSV (with original assertion and evidence IDs), independent of
all presentation filters. The source-first table derives from the same embedded
original comparison features, not a second model, endpoint, hosted service or
persistent store. Saved snapshots and the unmodified offline map renderer
remain read-only.

### Source-first changed-entity evidence downloads (WORK-0087)

Each reporting-source row in the original two-period comparison now offers
**Download changed entity GeoJSON** when that source reports an entity in only
one of the two embedded selections. The download contains every original Point
report for those source/entity intersections (earlier and later as applicable),
including unchanged assertion/evidence identifiers and comparison metadata.
Its explicit source, comparison axis and original/selected counts come from
the complete embedded evidence, independent of map search, viewport, source,
or period presentation filters. Rows without selection changes disable the
button. This is a change in *which source reports appear in the selection*,
not proof of disappearance, movement, source completeness or truth. The export
uses the existing offline browser download mechanism; it does not mutate
saved WorldMini state or add a route, service, data model or dependency.


### Pairwise original reporting-source coverage (WORK-0088)

The existing self-contained two-period comparison map lets an analyst select **two distinct original reporting sources**, count their jointly reported entity IDs in the same earlier/later selection, inspect the entities through the original evidence explorer, and download the complete original GeoJSON from exactly those two sources for the shared entities. Counts and downloads use the original embedded evidence, independently of map display filters. A shared entity ID does **not** mean that sources agree, that a source is comprehensive, or that a location or movement is verified. The ordinary source map retains its previous behavior. No service, model, dependency or saved-state mutation is introduced.

### Compare original reported coordinates between two sources (WORK-0089)

For two selected source IDs in the offline two-period original evidence map,
the source-pair table now separately reports whether each source's **set of
original Point coordinates** differs at the earlier or later comparison cutoff.
Only entity IDs jointly reported in that period are compared; a period without
both sources is explicitly marked **Not jointly reported**, not "same".
Duplicate reports of one coordinate do not create false differences.
Identical coordinates do not prove independent agreement or ground truth, and
different coordinates do not identify the correct source or establish movement.

The new **Download original reports with different source coordinates** action
exports *all original Point features from both sources and both periods* for
entity IDs with a coordinate-set difference in at least one jointly reported
period. The source IDs, comparison axis, original assertion/evidence metadata
and original/selected report counts are retained, regardless of viewport,
search, source or period presentation controls. No consensus coordinates are
invented, no source report is rewritten, and the existing complete pair export
is unchanged. As in WORK-0088, this is a candidate on an unmerged stacked
branch, with no new endpoint, browser library, external service or persisted
WorldMini state change.


#### Approximate separations between two original reporting sources (WORK-0089)

For an entity jointly reported by the selected two sources at an earlier or later
comparison cutoff, the pair table now shows the **nearest and farthest
cross-source Point separations (km)** for that same period. These use the
existing antimeridian-aware great-circle approximation and de-duplicate
identical positions per source; they are not accuracy scores. A period without
reports from both sources is marked **Not jointly reported**, with no invented
zero distance. A nearest separation of zero can coexist with differing
coordinate sets when the sources share one position but report other positions.
The diverging-pair GeoJSON retains all original features and adds per-entity,
per-period nearest/farthest source-report separations computed from the **full
embedded evidence**, independent of map filters. No location is verified, no
movement or route is inferred, and no new endpoint, dependency, or stored-state
write is introduced.


The **Download complete pair separation CSV** action exports both earlier and later original source selections for every jointly reported entity, including source IDs, original report counts, assertion/evidence ID arrays, period-specific same/different/missing states, and nearest/farthest approximate source Point separations (km). Where reports are not jointly available, numeric distances are left blank rather than invented as zero. The source-pair export is based on complete immutable embedded evidence, regardless of visible map, search or period filters; spreadsheet-formula-like text uses the existing CSV quoting/escaping. Source separations do **not** establish verified positions, physical motion, accuracy or which source is correct.

### Filter original source-pair separation by threshold (WORK-0090)

In the self-contained two-period source-pair map, the analyst can choose **nearest or farthest** approximate separation between two sources' original reported Points, an earlier/later/either-period selection, and a minimum distance (0–20040 km). Only jointly reported periods qualify; a missing source measurement is never interpreted as zero. The table updates immediately and reports the count of matching entities. The **Download threshold-matching original evidence GeoJSON** action exports every embedded original report for both chosen sources and both periods belonging to matching entities, preserving all assertion/evidence IDs; this explicitly scoped export is distinct from the existing *complete*, display-filter-independent pair GeoJSON and CSV downloads. Empty, negative, non-finite and out-of-range input shows no matches and cannot export. The approximate distances are not verified source accuracy, location confidence, travel or ground truth. No new endpoint, external API, dependency or persistent-state mutation is introduced.

### Rank original source-pair coordinate divergence (WORK-0091)

The existing two-source comparison panel offers **original entity ID**, **largest separation first** and **smallest separation first** ordering. Ranking reuses the nearest/farthest distance metric and earlier/later/either period already selected by the analyst. For either-period ranking, the largest actual same-period measured separation is used; missing jointly reported measurements are unknown, never zero, and sort last. Equal distances are ordered by original entity ID for deterministic browsing. This presentation choice does not change the minimum threshold, original source assertions, or complete and threshold-matching GeoJSON/CSV exports. Separations are approximate original source-reported coordinate differences, not verified geography, motion, reliability or accuracy. No stored state, endpoint, paid API or dependency is added.


#### Inspect both original reporting sources on one offline map (WORK-0091)

The source-pair comparison table now links each jointly reported entity to its
**two original reporting sources on the map**, using the selected earlier/later/
either period. Other display filters are reset for this temporary focus, and
the map fits all original points reported by the two selected sources. A visible
**Show all original reports on map** control clears the focus; changing one of
the two selected sources also exits it. The underlying original assertions,
provenance and complete unfiltered GeoJSON/CSV exports are never modified.
These are source-reported coordinate claims, not verified truth, routes,
accuracy rankings or physical movements. No new API, dependency or persisted
state is introduced.
