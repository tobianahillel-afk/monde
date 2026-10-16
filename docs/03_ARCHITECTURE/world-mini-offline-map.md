# MONDE Mini — offline interactive evidence map (WORK-0017)

**Experimental user-visible slice, not the MONDE production Globe.**

Generate a single HTML file from a saved MONDE Mini state:

```sh
PYTHONPATH=src python3 -m monde.map_view \
  --state saved.json \
  --bbox '2.34,48.84,2.36,48.87' \
  --at 2026-01-02T00:00:00Z \
  --known-at 2026-01-10T10:00:00Z \
  --output evidence-map.html
```

Open `evidence-map.html` in a browser. The self-contained page requires no server,
API key, JavaScript library, remote tiles, external images or internet access.

Use **Export visible GeoJSON** to save the currently displayed source reports (after search, source, viewport and change filters) into a portable GeoJSON FeatureCollection, without network requests. The download preserves source assertion IDs, evidence, competing positions and the original time/viewport query. The `monde_visible_export` field records the applied filters and explicitly marks the result as a **filtered derivative**, not complete source coverage or reconciled physical truth. The original saved MONDE state remains unchanged. The button is disabled when there are no visible reports.

Use **Find evidence** to search locally by entity, assertion ID, source ID,
evidence ID or original locator (case-insensitive, multiple words); combine the
search with the source, change and inside-viewport filters. Select a report to
center the schematic map on its source-reported coordinates, or use **Center
selected report** to return to it after zooming. All queries run entirely
inside the saved HTML: no network requests and no new data or truth claims.

Use **Zoom +/-** and **Whole world** for a schematic longitude/latitude
world grid, filter the source list, and select any point or report to inspect
its assertion ID, source ID, original locator, evidence ID, capture time and
temporal cutoffs. Filled markers are within the requested bbox; hollow
markers are alternative positions reported by other sources for matching
entities, **even when outside the selected viewport**.

The projection is deliberately schematic, not a detailed coastline basemap.
The source-reported coordinates do not establish the entity's true physical
position. An empty result means there are no *matching known source reports*,
not that a place is physically empty. Different source claims are not merged.

Input is read-only; output must be a new path to prevent accidental overwrite.
Large exports are refused explicitly (5,000 features or 3 MB of embedded
JSON), not silently truncated. Source metadata is encoded as safe JSON in a
nonexecutable script element, and displayed using DOM text nodes. The page
has an offline-denying Content Security Policy.

Existing WORK-0016 viewport GeoJSON and its world/knowledge time semantics
are reused without modifying the World Model or adding another database.

## Offline knowledge-change map

The same HTML explorer can display **changes in reported knowledge** between
two cutoffs (not verified physical movement):

```sh
PYTHONPATH=src python3 -m monde.map_view \
  --state saved.json --bbox '2.34,48.84,2.36,48.87' \
  --at 2026-01-02T00:00:00Z \
  --compare-known-at 2026-01-10T10:00:00Z \
  --known-at 2026-01-11T10:00:00Z \
  --output knowledge-changes.html
```

The map retains both source claims when a reported location is corrected, even
if the newer position leaves the viewport. Filter by source and by
`NEWLY_CURRENT` / `NO_LONGER_CURRENT`, select a report to inspect its
original evidence and its knowledge window, and use the same offline zoom.
Unchanged source reports are omitted from this *change-only* view; an empty
result cannot establish physical absence. No new dependency or API.

## Offline source-reported world-time changes

Compare source-reported Point validity between two world instants at a
fixed knowledge cutoff. This is different from comparing what MONDE learned;
source validity changes are not proof of physical movement.

Example command: `PYTHONPATH=src python3 -m monde.map_view --state saved.json --bbox '2.34,48.84,2.36,48.87' --compare-at 2025-12-31T00:00:00Z --at 2026-01-02T00:00:00Z --known-at 2026-01-10T10:00:00Z --output world-changes.html`.

The viewer reuses `WorldMini.export_geojson_bbox_world_changes` and retains
`NEWLY_CURRENT` / `NO_LONGER_CURRENT` original source evidence, coordinates,
and both world instants. Search, filter and export visible source reports
offline. `--compare-at` and `--compare-known-at` cannot be used together.
Existing state is immutable; output is never overwritten.

## Compare reports about the same entity (T7)

Use the **Entity** selector to isolate a named entity, or **Different-source position
claims only** to find entities for which separate sources report differing
coordinates. **Compare reported positions** lists every still-visible source
assertion with its original evidence and coordinates; click a report to inspect
its lineage and center on that *reported* point. Source, text, viewport and
world/knowledge-change filters compose with entity comparison.

The display does **not** identify a correct coordinate, rank sources by
trustworthiness, imply that a location moved, or upgrade a source claim into
observed physical truth. Filtered GeoJSON exports include entity and
position-disagreement filter metadata, while preserving original assertions
and the complete original time query.

## Navigate and export the displayed map window (T9)

Use drag-to-pan or keyboard arrow keys (while the SVG map has focus).
**Inside displayed map window only** filters rendered original source reports,
evidence comparisons, disagreement links and the GeoJSON download to the
currently shown schematic WGS84 window. Zoom, center and reset recompute it.
The original requested bbox remains **unchanged**, as do assertion IDs,
source IDs, evidence and temporal lineage. The exported derivative records
`displayed_map_window_only` and `displayed_map_window_bbox_wgs84` under
`monde_visible_export.filters`; the bbox is null if disabled. The window
describes a schematic display, not an observed or verified physical location,
movement or absence. No network, tile service or dependency is introduced.

## Visual links between source-reported positions

Enable **Show source-position disagreement links** to compare different-source
coordinate claims about the same entity directly on the schematic map. Dashed
links are derived from currently visible reports, so existing entity, source,
search, viewport and temporal-change filters apply. Connections use the shortest
antimeridian wrap and do not describe a route, physical movement, verified
location, confidence score or uncertainty distance. Links are screen-only; a
filtered GeoJSON download retains the original source evidence unchanged.

## Filter source reports by evidence capture date (T10)

The offline evidence explorer includes **Captured from (UTC day)** and
**Captured through (UTC day)** controls. They select original source reports
whose `captured_at` timestamp falls on inclusive UTC calendar days, and
compose with existing source, entity, text, requested/displayed viewport and
world/knowledge-change filters.

Capture time is **source-evidence metadata**, not the world-validity time,
knowledge-time cutoff, a trusted observation time, or the physical event time.
An empty date selection imposes no date constraint; unknown or invalid capture
timestamps cannot pass an active date filter. Timezone offsets in valid capture
times are normalized to UTC, irrespective of browser locale.

The filtered GeoJSON includes `captured_from_utc_day` and
`captured_through_utc_day` in derivative filter metadata and preserves the
original bitemporal query, source assertion IDs, evidence, and coordinates.
Filtering never mutates the saved World Model or implies physical absence.

## Fit matching reports (T11)

Use **Fit matching reports** to frame the source-reported coordinates that match
current entity, source, evidence search, capture UTC day, disagreement, requested
bbox and temporal-change filters. Only the *displayed map window* filter is
ignored while calculating the framing, to recover matching reports outside the
current pan/zoom window. If that filter remains enabled, the visible list and
GeoJSON export are recomputed after moving the map.

The map is still a schematic WGS84 projection, not a true-location estimate.
Locations near opposite sides of the international dateline may require a
nearly global view rather than an invented geographic route. The button is
disabled for zero matching reports. All source assertions, IDs, provenance,
original temporal query and saved state remain unchanged.

## Offline entity evidence dossier (T12)

After selecting a report or choosing an Entity, **Export entity evidence dossier**
downloads a standalone JSON file containing that entity's currently filtered
source-reported Points, original assertions, evidence identifiers, source
locators, capture timestamps, original time-query cutoffs and filter provenance.
It reports how many source claims were present before filtering, how many were
included, and whether different sources reported different coordinates.

The dossier is a **filtered derivative, not a complete history or location
consensus**. Omitted reports prove no physical absence, and reported changes
do not prove movement. Works offline for normal, knowledge-change and
world-time-change maps, with no added API, server or package.

## Source-reported proximity exploration (T13)

In the standalone map, select any original source report, choose **Use selected
report as center**, and enter a nonnegative radius in kilometers (0 to 20040).
The explorer filters the *embedded source Points* by approximate great-circle
distance from that report's **source-claimed coordinate**. Longitude wraps at
the antimeridian. A later selection does not silently move the radius center;
use the center button again to change it or **Clear radius** to restore all
other filters. An invalid radius returns no reports until corrected.

This is an evidence-navigation operation, **not a radius around a verified
physical location**, geocoding, a route, a confidence score or proof of absence.
It composes with source, entity, capture-day, disagreement, map-window and
world/knowledge time-change filters and with **Fit matching reports**.
Visible GeoJSON and entity dossier downloads retain the original source
assertions, evidence IDs and query and add the chosen center's assertion,
source and evidence IDs, original coordinates, radius kilometers and an
explicit approximate-distance derivation under `filters`. It neither changes
the saved snapshot nor requests an external map or API.

## Compare two original reported Points (T14)

Select any original source report, click **Use selected as A**, select another
report, and click **Use selected as B**. The offline map shows an approximate
shortest great-circle distance between the two **source-claimed WGS84 Point
coordinates** (Earth mean-radius approximation, not a measured survey).
An endpoint stays bound to its original assertion and provenance if a filter
subsequently hides that report; use **Clear comparison** to start over.

**Export evidence + separation** downloads JSON with both intact original
GeoJSON features (assertion, source ID, evidence, capture and temporal context),
the original bitemporal map query, the approximate distance in kilometers and
explicit same-entity/same-assertion indicators. Works with regular and both
temporal-change maps. No remote map, geocoding, inference engine or new package.
A result is **not** a route, verified movement, true entity location,
location consensus or a confidence estimate. A zero distance means the two
reported coordinates coincide, not that either is physically correct.


## Cross-entity source-position disagreement inventory (WORK-0018)

The offline evidence explorer provides a **Cross-entity source disagreements**
navigator and **Export disagreement inventory**. It groups the original
source-reported Points by entity under the current filters (including the
displayed map window, capture-day bounds, source, search, temporal-change,
proximity and viewport filters), **except the currently selected entity**. Each
entry gives counts of source reports, distinct source IDs and distinct reported
coordinate pairs, and can be selected to inspect its original claims on the map.
It intentionally does not rank sources, infer a true location, or infer motion.

A conflict exists only when at least two distinct source IDs and at least two
distinct reported coordinate pairs are present **within the filtered subset**.
The report is empty and the export button disabled if there is no such group;
absence of reported conflict is not evidence of physical agreement or absence.
Longitudes +180 and -180 represent the same meridian for this classification.

The downloaded `monde-source-conflict-inventory.json` preserves the original
bitemporal source query, every included original GeoJSON Feature, assertion IDs,
source IDs, evidence IDs, and the filters used. Its scope explicitly excludes
the selected-entity filter so the inventory can compare multiple entities.
No network calls, external map libraries or saved-state mutation are required.


## Direct GeoJSON-to-offline-map workflow (WORK-0022)

You can also generate the same standalone offline evidence map from an original
GeoJSON `FeatureCollection` of WGS84 `Point` features, without first saving a
MONDE state file. Each feature needs its own `id`, `geometry` and `properties`.
The source identity and both time dimensions must be supplied explicitly:

```sh
PYTHONPATH=src python3 -m monde.map_view \
  --geojson examples/monde-mini-points.geojson \
  --source-id original-survey \
  --source-locator dataset://original-survey/points.geojson \
  --captured-at 2026-01-10T10:00:00Z \
  --valid-from 2026-01-01T00:00:00Z \
  --at 2026-01-02T00:00:00Z \
  --known-at 2026-01-10T10:00:00Z \
  --output source-map.html
```

`--valid-to` and `--source-event-at` are optional only when the original
source does not provide those facts; they are never inferred. The map uses the
same automatic source-point bounding box, bitemporal comparison options,
source/evidence identifiers and offline browser view as saved states and CSV
manifests. `--state`, `--csv-manifest` and `--geojson` are mutually exclusive.
GeoJSON claims are **not verified physical positions**, and distinct source
reports must never be collapsed into one location. Input files and pre-existing
output files are not overwritten. Repeated corrections require the separate
append-only state workflow with explicit evidence/supersession.

## Multiple original GeoJSON and mixed source datasets (WORK-0022)

Create an offline evidence map directly from multiple original GeoJSON FeatureCollections of source-reported 2D Points. The same manifest can combine original CSV files and GeoJSON files; each retains separate source attribution and valid/knowledge timestamps. No intermediate persisted WorldMini state is needed.

Save a local sources.json manifest (file paths are relative to the manifest):

```json
{"datasets":[
  {"geojson":"survey-a.geojson","source_id":"survey-a","locator":"dataset://a","captured_at":"2026-01-10T10:00:00Z","valid_from":"2026-01-01T00:00:00Z"},
  {"geojson":"survey-b.geojson","source_id":"survey-b","locator":"dataset://b","captured_at":"2026-01-10T10:00:00Z","valid_from":"2026-01-01T00:00:00Z"}
]}
```

Then run:

```sh
PYTHONPATH=src python3 -m monde.map_view --source-manifest sources.json --at 2026-01-02T00:00:00Z --known-at 2026-01-10T10:00:00Z --output evidence.html
```

Each dataset requires exactly one csv or geojson input plus source_id, locator, captured_at and valid_from, with optional valid_to and source_event_at. CSV-specific column overrides do not apply to GeoJSON. The existing --csv-manifest CLI name remains an alias for compatibility. The original source claims remain contradictory where they disagree: this feature does not reconcile physical positions or infer a true location, observation time or event time.

All inputs are read-only; one invalid dataset aborts before output, and existing outputs or source files are not overwritten. Existing source-count limits, auto geographic bounds, bitemporal filters, derivative exports, and offline/no-network rendering are reused.

## Offline reference geography (WORK-0022/T5)

The standalone source-evidence HTML now embeds **Natural Earth 1:110m land
polygons** as a muted SVG base layer. The reference coastlines help an analyst
recognize continents without opening an online map, installing a mapping SDK,
requesting tiles, or requiring any API. Points, source disagreement links,
source evidence, selection, exports and bitemporal queries retain their own
separate foreground layer and original provenance.

**Source:** [Natural Earth public-domain 1:110m land](https://github.com/nvkelso/natural-earth-vector);
GeoJSON conversion: [martynafford/natural-earth-geojson](https://github.com/martynafford/natural-earth-geojson/blob/0b9a6ceb0a7032713abd9460ac1e995a9c60cd1e/110m/physical/ne_110m_land.json),
pinned upstream revision `0b9a6ceb0a7032713abd9460ac1e995a9c60cd1e`.
The simplified land shapes are **cartographic context**, neither physical
entity observations nor MONDE evidence. Their coarse scale is unsuitable
for precise local boundaries or disputes. No source data is transmitted
externally; the renderer only reads the versioned local asset.


## UTC source-capture timeline (WORK-0022/T6)

The offline evidence map shows a clickable histogram-like list of capture days from original source-report metadata (UTC). Its counts apply the current search, source, entity, viewport, distance, disagreement, and comparison filters, **excluding the capture-date range itself** so alternative days remain discoverable. Up to the 24 most recent days are shown; the total number of matching distinct days is reported. Clicking a day sets both inclusive capture-day bounds, and **All capture days** clears them. The visible map, list, and existing GeoJSON/CSV exports remain aligned with the selected bounds; no original source report, ID, timestamp, or temporal query is modified. A capture date is neither a world-state timestamp nor proof that a physical event occurred.

## Original KML Point evidence (WORK-0023)

Local **KML 2.2 Point Placemarks** can now be mapped offline using the same
WorldMini evidence engine as original GeoJSON and CSV. Each Placemark must carry
a distinct, stable XML `id` attribute. Original `name` and `description` are
retained as source-reported properties; no identity, capture time, world-validity
date, reconciled location or source authority is inferred.

```sh
PYTHONPATH=src python3 -m monde.map_view \
  --kml survey.kml --source-id survey-kml \
  --source-locator dataset://survey/original-kml \
  --captured-at 2026-01-10T10:00:00Z \
  --valid-from 2026-01-01T00:00:00Z \
  --at 2026-01-02T00:00:00Z \
  --known-at 2026-01-10T10:00:00Z \
  --output original-kml-map.html
```

The existing `--source-manifest` accepts a dataset with `"kml":"survey.kml"`
in place of `"geojson"` or `"csv"`; all three formats may be combined. Each
dataset still requires its own explicit `source_id`, `locator`, `captured_at`,
and `valid_from`. Conflicting reported Point positions remain independent
source assertions. Inputs are read-only and a failed source does not create a
partial HTML output.

Only original 2D WGS84 Point coordinates are supported; altitude,
LineString/Polygon/MultiGeometry, network links, ExtendedData, XML DTD/entities,
absent or duplicated stable IDs and invalid coordinates are rejected rather
than silently interpreted or discarded. 10 MB per KML and 50,000 Point cap.
The output is source *evidence*, never independently verified physical truth.

## GPX waypoint import (WORK-0024)

Original local GPX 1.1 waypoints are accepted as source-reported 2D WGS84 Points.
Each waypoint name must be unique, identifier-safe and verified stable by the
source owner: GPX does not guarantee identity stability. Neither position nor
timestamp is promoted to physical truth. Waypoint description, comment, symbol,
type and source time are preserved as properties; source capture/validity and
knowledge time always come from the explicit CLI or manifest flags.

Example (with an original GPX containing waypoint names):

    PYTHONPATH=src python3 -m monde.map_view --gpx original.gpx \
      --source-id original-gpx --source-locator dataset://gps/original.gpx \
      --captured-at 2026-01-10T10:00:00Z --valid-from 2026-01-01T00:00:00Z \
      --at 2026-01-02T00:00:00Z --known-at 2026-01-10T10:00:00Z \
      --output source-map.html

The existing source-manifest format accepts a gpx input field alongside CSV,
GeoJSON and KML, preserving original per-source evidence across mixed datasets.
Input files and existing output files are never overwritten. Routes, tracks,
elevation, waypoint extensions and unsupported fields are explicitly rejected.
File-level GPX metadata is not mapped into claims; provide source identity and
original locator separately. No network calls or external map services are used.
