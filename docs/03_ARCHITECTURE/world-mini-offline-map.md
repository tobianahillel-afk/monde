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
type, source time and finite source-reported elevation (`ele`, metres) are
preserved as properties; elevation is not a verified 3D position. Source
capture/validity and knowledge time come from explicit CLI or manifest flags.

Example (with an original GPX containing waypoint names):

    PYTHONPATH=src python3 -m monde.map_view --gpx original.gpx \
      --source-id original-gpx --source-locator dataset://gps/original.gpx \
      --captured-at 2026-01-10T10:00:00Z --valid-from 2026-01-01T00:00:00Z \
      --at 2026-01-02T00:00:00Z --known-at 2026-01-10T10:00:00Z \
      --output source-map.html

The existing source-manifest format accepts a gpx input field alongside CSV,
GeoJSON and KML, preserving original per-source evidence across mixed datasets.
Input files and existing output files are never overwritten. Routes, tracks,
non-finite elevation, waypoint extensions and unsupported fields are explicitly rejected.
File-level GPX metadata is not mapped into claims; provide source identity and
original locator separately. No network calls or external map services are used.


## GPX 1.1 source-reported routes and tracks (experimental WORK-0025)

The original `--gpx` and mixed-source manifest paths now accept local GPX 1.1
routes (`rte/rtept`) and tracks (`trk/trkseg/trkpt`) alongside waypoints.
Each trace requires a unique source-provided `name`, all geometry must be
finite 2D WGS84, and points are retained as individual source-assertion
records with evidence, capture, valid-world and known-at timestamps. Source
sample order and track segment numbers are retained as `gpx_trace` claims.
A track/route sample ID is deterministic from source-reported coordinates,
trace label and optional time/name: it is **not** a persistent physical entity
identity. Repeated identical GPS readings (including stationary samples) are
retained with stable occurrence-suffixed IDs; original segment and sample
order are never collapsed. Optional finite GPX `ele` is retained as a separate
source-reported altitude property, not verified vertical position. The offline map
draws cyan dashed edges only between **consecutive currently visible** points
of the same source, trace and segment. It never connects missing samples,
separate segments, or across the antimeridian, and does not establish verified
travel or an observed road. Its browser still makes **no network requests**.

For example:

```sh
PYTHONPATH=src python3 -m monde.map_view \\
  --gpx original-route.gpx --source-id source-survey-1 \\
  --source-locator dataset://survey/route.gpx \\
  --captured-at 2026-01-10T10:00:00Z \\
  --valid-from 2026-01-01T00:00:00Z \\
  --at 2026-01-02T00:00:00Z \\
  --known-at 2026-01-10T10:00:00Z \\
  --output trace-evidence.html
```

Unsupported extensions, invalid/non-finite altitude, DTD/entities, remote
geometry and ambiguous source identities fail closed. The source label and sample grouping come from
the original GPX, not from inferred geographic truth.


### Explore one original GPX source trace segment

When a GPX route or track appears, the GPX source trace / segment selector offers one option per original source, trace and segment. Selecting it filters the displayed reports and the existing GeoJSON/CSV export to source-attributed samples, with original and currently visible sample counts. The All traces button restores all source claims. Segments never imply observed physical travel, nor are points missing from a filtered view connected into a fabricated path.


## GPX source segment profile (WORK-0025)

Select a **GPX source trace / segment** in the standalone map and click **Export source segment profile**. The downloadable JSON retains each currently visible original Point report and its source/evidence identifiers, the unchanged bitemporal map query, filters, original segment identity and original sample count. It counts only originally consecutive sample pairs that both survive all active filters. The summed approximate great-circle **coordinate separations** in kilometers are not the surveyed route length, physical distance traveled, verified motion, inferred speed, or complete geometry. Missing or hidden samples are never bridged; clearing the selection disables the export. Everything works offline without additional dependencies.

## Original GPX sample UTC-day filter (WORK-0025)

In the offline source evidence map, GPX source sample from / through (UTC day) uses the original GPX route/track sample timestamps, independently of captured_at, world validity or knowledge time. The inclusive filter only retains timestamped original source trace samples while active; untimed readings, standalone waypoints and unrelated formats are excluded. Report lists, visible map links, source trace profiles and GeoJSON exports share the filter. The exported derivative records both bounds and the original source-clock basis, preserving source/evidence/assertion IDs. Filtered sample-order gaps are never connected. These timestamps do not establish verified travel, speed or physical events.


## Inspect one original GPX sample at a time (WORK-0025)

After selecting an original route or track segment, **Next source sample** and
**Previous source sample** inspect currently matching Point assertions in their
original GPX order, centering each reported coordinate and exposing its source,
assertion and evidence IDs. Navigation stops at visible segment bounds and
respects the existing filters. Hidden samples are skipped rather than interpolated;
no path, verified movement or physical location is inferred. The original offline
source snapshot and GeoJSON/CSV export semantics remain unchanged.


## WORK-0026 — Original local KML LineString samples

A KML 2.2 source file with uniquely identified 2D Point and LineString
Placemarks is accepted through the existing --kml one-command offline
source-evidence map. Each LineString coordinate becomes a distinct
evidence-linked source-reported Point. Its kml_trace assertion records the
original Placemark source identity, trace identifier and sample order; repeated
identical original samples remain separate rather than silently deduplicated.

The offline map draws dotted connections only between adjacent samples
from the same source, LineString and segment, subject to visible filters.
It does not connect across missing samples or the antimeridian. Click a Point
to inspect its original source LineString and sample order. Connections
are source-reported geometry, not a verified journey, transport route or
physical trajectory. No server, basemap downloads or external API is used.
Unsupported geometries, altitude coordinates, network-linked KML, ambiguous
IDs and malformed XML fail before creating the output file.

## Source-reported KML Polygon boundaries (WORK-0027)

A local KML 2.2 `Polygon` with one explicit closed `outerBoundaryIs / LinearRing`
(no inner rings or 3D coordinates) can be inspected with the same `--kml` /
`--source-manifest` workflows as KML Points and LineStrings. The converter
retains every original vertex, including the repeated closing coordinate, as a
distinct source-evidence Point with stable ID and original ring order. The map
draws amber dashed adjacent source-reported ring edges only when both endpoints
remain visible under filters and the segment does not cross the antimeridian.
It never fills, reconstructs, repairs or validates an enclosed area. Source
geometry is **not** proof of a legal boundary, territorial ownership, land use,
traversability, presence or measured surface. Self-intersecting rings remain
source claims; missing closure, holes, altitude and unsupported geometry fail
without partial output.

## KML Polygon outer and inner rings (WORK-0028)

A source Polygon with one closed outer `LinearRing` and up to 128 closed
`innerBoundaryIs` LinearRings is ingested as separate *original point evidence*
per ring. `monde_kml_trace.segment=0` marks the outer boundary and positive
segments mark each explicitly supplied inner boundary, in original KML order.
The original repeated closing vertex is retained as its own sample/evidence.
The offline SVG evidence map draws only consecutive samples **within the same
ring**: amber dashed edges for outer rings and rose dashed edges for inner
rings. Filtering that hides a vertex cannot create replacement or connecting
edges. No area fill, inside/outside judgment, legal boundary claim, geometric
repair, or polygon validity inference is performed. Unsupported geometry,
three-dimensional samples and malformed rings fail atomically.

## Source-declared KML MultiGeometry (WORK-0029)

A KML 2.2 Placemark can contain one bounded \`MultiGeometry\` with up to 32
direct \`Point\`, \`LineString\` and \`Polygon\` children. Run the same offline
\`--kml\` command already used above: the original local file is converted
into independently evidenced source Point samples and displayed on the same map.
No extra conversion tool, dependency, network request or map engine is needed.

Every component receives distinct deterministic source sample IDs and retains
its original `kml_placemark_id` and `kml_component_index` as source-attributed
WorldMini assertions; LineString and Polygon traces use distinct per-component
trace IDs, so neither two shapes
nor adjacent rings are joined by a fabricated edge. Existing single geometry
Placemarks retain their current IDs and semantics. Malformed, nested, remote,
3D or over-budget input is rejected before producing output.

**Important:** MultiGeometry is an original *source grouping*, not a proven
real-world area, motion, topology, object identity or asserted containment.
The map stays schematic, offline and bitemporal; every location remains a
source report with its evidence and original time metadata.

## Import a local KMZ source archive (WORK-0030)

A local **KMZ** can now be used directly with the existing MONDE Mini map:

```sh
PYTHONPATH=src python3 -m monde.map_view \
  --kmz original-survey.kmz \
  --source-id survey-kmz \
  --source-locator dataset://original-survey.kmz \
  --captured-at 2026-01-10T10:00:00Z \
  --valid-from 2026-01-01T00:00:00Z \
  --at 2026-01-02T00:00:00Z \
  --known-at 2026-01-10T10:00:00Z \
  --output evidence-map.html
```

The KMZ must contain one **root `doc.kml`**, whose supported Points,
LineStrings, Polygons and MultiGeometry are processed by the **same** KML
parser as ordinary `--kml`. Original per-source IDs, vertex ordering, ring
boundaries and bitemporal provenance are retained. An additional dataset
in a `--source-manifest` may use `"kmz": "original-survey.kmz"`
with the same explicit provenance fields as KML.

There is **no extraction** or network access. Accompanying local assets are
never opened; a second KML document is rejected rather than silently ignored.
Archives are bounded (25 MB compressed, 40 MB declared inflated content,
64 members, 10 MB maximum `doc.kml`), and malformed archives, encrypted
members, unsafe entry names, remote KML links and ambiguous documents fail
before any output is created. This imports **source claims**, not verified
geographic reality or a reconstructed globe.


## Import an original GeoPackage Point source (WORK-0031)

MONDE Mini can read a local SQLite **GeoPackage (.gpkg)** directly, without
GeoJSON conversion, a GIS server, extra libraries or network services.
Specify exactly which original 2D WGS84 Point feature table to inspect.

    PYTHONPATH=src python3 -m monde.map_view \
      --gpkg original-survey.gpkg \
      --gpkg-layer survey_points \
      --source-id original-survey \
      --source-locator dataset://original-survey.gpkg \
      --captured-at 2026-01-10T10:00:00Z \
      --valid-from 2026-01-01T00:00:00Z \
      --at 2026-01-02T00:00:00Z \
      --known-at 2026-01-10T10:00:00Z \
      --output evidence-map.html

In a multi-source \`--source-manifest\` dataset, use
\`"gpkg": "original-survey.gpkg", "gpkg_layer": "survey_points"\` with
the normal explicit \`source_id\`, \`locator\`, \`captured_at\` and
\`valid_from\` fields. Mixed original CSV, GeoJSON, GPX, KML and KMZ datasets
continue to use the same atomic WorldMini evidence model.

The layer must be a physical GeoPackage feature table with one INTEGER primary
key, an explicitly declared 2D Point geometry, and matching EPSG:4326 table,
spatial-reference and binary geometry metadata. Source point IDs, scalar
attributes and coordinates are preserved as **source reports**, not validated
physical truth. Timestamps are mandatory inputs, never inferred from files.
Unsupported CRS, non-Point geometries, invalid or contradictory WKB, ambiguous
layer/column identifiers and malformed SQLite sources are rejected.

Read-only import is bounded to 100 MB per database and 50,000 source Points;
the original source remains untouched, and existing output files cannot be
overwritten. No reprojection, remote attachment, spatial inference or feature
reconciliation is performed.


## Inspect original GeoPackage LineString traces (WORK-0032)

The existing `--gpkg FILE --gpkg-layer TABLE` CLI and `gpkg` manifest entries
also accept one original GeoPackage **2D EPSG:4326 LineString** feature table.
No conversion, reprojection, network access or GIS dependency is required.
For example, substitute `--gpkg-layer survey_lines` into the GeoPackage
command above. Original row primary keys, per-line vertex order, scalar
attributes and explicit source/capture/validity times are retained. The
offline map draws only consecutive vertices from the **same original line**,
labels the result as source evidence rather than verified movement and
never joins separate feature IDs. Antimeridian-crossing segments are omitted
instead of inventing a route across the map.

WKB count, endianness, SRID, optional envelope, finite WGS84 ranges, and
exact binary length are validated; lines require at least two 2D vertices.
The existing read-only 100 MB database and 50,000 source-sample limits apply.
Malformed or unsupported geometries fail before writing any output. Original
GeoPackage Point imports remain unchanged. Polygons, 3D/Z/M, complex
geometries and external resources remain unsupported.

## Import original GeoPackage Polygon rings (WORK-0033)

The existing `--gpkg FILE --gpkg-layer TABLE` and `--source-manifest`
also support physical feature tables declared **2D WGS84 POLYGON**. No
conversion or additional dependency is necessary. Original integer feature
keys, names, coordinate order and separate **outer / inner rings** are preserved
as individually attributed source-report samples in the World Model.

The map joins **only consecutive vertices in the same original ring**,
distinguishes inner from outer boundaries visually and exposes the source
layer, feature ID, ring index, sample order and evidence timestamps. An
original closed ring stays closed; it does not imply a verified filled area,
land ownership or true physical geometry. Missing samples and
antimeridian-crossing segments are never invented.

Binary GeoPackage and 2D WKB geometry must agree on type and EPSG:4326;
optional envelopes are verified against all original vertices. At most 128
inner rings and 50,000 total source samples are accepted within the existing
100 MB read-only database limit. Invalid, truncated, nonclosed,
out-of-range or contradictory rings abort before any HTML output is created.
Point and LineString imports are unchanged. 3D/Z/M, MultiPolygon, reprojection
and remote datasets remain outside this narrow increment.


## Original GeoPackage MultiPolygon components (WORK-0034)

Physical 2D EPSG:4326 **MULTIPOLYGON** feature tables can be opened directly with
`--gpkg FILE --gpkg-layer TABLE` or a local `gpkg` manifest entry. Each
source-declared Polygon member retains its **original component index**, ring
index (outer or hole), complete vertex order, source feature ID, source
attributes, capture time and world-valid-time provenance. Each member has its
own trace identity; separate components and rings are never joined on the map.
The map shows outline evidence only, not an inferred filled boundary or
verified physical geography.

The original binary is parsed read-only. Unsupported CRS, Z/M WKB,
mismatched MultiPolygon/Polygon declarations, malformed member counts,
incomplete rings and envelope contradictions fail atomically. The decoder
accepts at most 128 Polygon components and 50,000 total source vertices.
It adds no remote API, tile service or dependency and preserves the previous
Point, LineString and Polygon formats.

## Original GeoPackage MultiLineString routes (WORK-0035)

A local read-only **2D EPSG:4326 `MULTILINESTRING`** layer now opens in the
same offline MONDE Mini command and source manifest as GeoPackage Points,
LineStrings, Polygons and MultiPolygons. Each original LineString member retains
a separate `line_index`, `trace_id`, feature ID and vertex sequence, so two
unconnected source routes are never silently joined into one path.

This is *source-reported geometry*, not verified motion, routing, land coverage
or a reconstructed real-world trajectory. MultiLineString supports mixed
endianness WKB children and optional bounded envelopes; unsupported SRIDs,
3D geometries, malformed members and incorrect metadata fail before an output
map is written. The original SQLite file remains unmodified.


## Original GeoPackage MultiPoint member observations (WORK-0036)

Local EPSG:4326 2D `MULTIPOINT` feature tables are now supported. Every
member retains a stable index, feature ID, source attributes and explicit
capture/valid times. These source-reported markers are never connected into
invented trajectories. Nested mixed-endian WKB, envelope and metadata checks
fail atomically before HTML output; local SQLite is opened read-only.


## Original mixed GeoPackage GEOMETRY layers (WORK-0037)

A local 2D EPSG:4326 feature table declared GEOMETRY may contain original
Point, LineString, Polygon, MultiPoint, MultiLineString and MultiPolygon
features **in the same layer**. MONDE Mini dispatches each WKB row to
the already validated subtype reader; no intermediary file conversion or new
library is required.

The existing CLI options --gpkg, --gpkg-layer, --source-id,
--source-locator, --captured-at, --valid-from, --at, --known-at and --output
work unchanged. Likewise for source-manifest gpkg / gpkg_layer datasets.
Original row IDs, geometry component/ring indices, attributes and source
time/provenance are preserved through the offline WorldMini map.
Multipart members remain independent; no routes or boundaries are inferred.

The import is strictly 2D WGS84. Unsupported subtypes, including
GeometryCollection and Z/M geometries, malformed WKB, conflicting envelopes
or SRIDs, non-finite coordinates and unsafe source metadata are rejected
without producing partial HTML.


## One-command original GeoPackage multi-layer source map (WORK-0038)

Use `--gpkg-all-layers` instead of `--gpkg-layer` with the existing
`--gpkg`, explicit source/time flags and `--output`. MONDE reads up to
16 original GeoPackage feature tables (sorted by name), reuses the bounded
2D EPSG:4326 decoders and produces **one offline map** without a manifest.
Each layer gets its own source identity (`source-id:layer`) and locator
fragment, preserving equal row/FID values from different layers as distinct
evidence. Original layer and feature identities remain in
`gpkg_source_layer` and `gpkg_source_fid` properties.
Unsupported/malformed source layers, unsafe attributes, excessive counts
or conflicting metadata reject the **whole** export before writing HTML.
No data are downloaded, reprojected, reconciled or silently omitted.
Existing single-layer and explicit multi-dataset manifest modes are unchanged.

Original layer/FID pairs are also visible as `monde_gpkg_source_layer` and
`monde_gpkg_source_fid` in the offline map's source-evidence features.
