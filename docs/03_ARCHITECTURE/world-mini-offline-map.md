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
