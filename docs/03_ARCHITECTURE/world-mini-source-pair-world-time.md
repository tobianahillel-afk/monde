# MONDE Mini — Original source-pair comparison over both temporal axes

The original `monde.source_pair_changes` CLI compares a source pair at a
**fixed world time** between two knowledge cutoffs (`--at`,
`--from-known-at`, `--to-known-at`), using `MONDE_SOURCE_PAIR_CHANGE_V1`.

## New: compare world-validity at fixed knowledge (WORK-0093)

```bash
PYTHONPATH=src python3 -m monde.source_pair_changes \
  --fixture saved-world.json --source-a survey-a --source-b survey-b \
  --from-at 2026-01-02T00:00:00Z --to-at 2026-01-05T00:00:00Z \
  --known-at 2026-01-07T00:00:00Z
```

The new `MONDE_SOURCE_PAIR_WORLD_CHANGE_V1` result retains each original
source/evidence/assertion ID and original GeoJSON geometry at both world
instants. It uses the **existing same source-pair distance calculation**.
Nearest/farthest kilometers and signed later-minus-earlier change are
approximate. If one source does not jointly report Points at either
instant, the corresponding separation and change are `null`, **never zero**.

Exactly one complete set of axis arguments is accepted. This is a
comparison of **source-reported validity**, not reliable ground truth,
physical movement, verified accuracy or speed. No stored-state writes,
new service, new dependencies or paid API are involved.


## Complete offline CSV (WORK-0094)

Use `--format csv` with **either** temporal comparison. For example:

```bash
PYTHONPATH=src python3 -m monde.source_pair_changes \
  --fixture saved-world.json --source-a survey-a --source-b survey-b \
  --from-at 2026-01-02T00:00:00Z --to-at 2026-01-05T00:00:00Z \
  --known-at 2026-01-07T00:00:00Z --format csv > source-pair.csv
```

The existing `--at/--from-known-at/--to-known-at` comparison also accepts
`--format csv`. Every entity in the comparison appears as an earlier and
later row, preserving the exact world and knowledge cutoffs. Each row carries
both original sources' full assertion IDs, evidence IDs and geographic
coordinates as JSON-array cells, along with counts, original-report status,
nearest/farthest approximate km and (on the later row only) the signed
difference when both periods are jointly reported.

`NOT_JOINTLY_REPORTED` has **blank numeric fields**, not invented zero
distances or implied movement. CSV escapes formula-leading entity/source
labels to avoid spreadsheet execution; it never modifies saved evidence.
Without `--format csv`, the existing JSON output and schemas are unchanged.
This is *reported source separation*, not verified location, source accuracy
or actual physical movement.

## Prioritize changes between original sources (WORK-0095)

To find the largest **changes in source-reported separation** rather than read every
entity, add `--top-nearest-changes N` (positive integer) to either comparison axis.

Example (knowledge changes at fixed world time):

```bash
PYTHONPATH=src python3 -m monde.source_pair_changes \
  --fixture saved-world.json --source-a survey-a --source-b survey-b \
  --at 2026-01-05T00:00:00Z \
  --from-known-at 2026-01-03T12:00:00Z \
  --to-known-at 2026-01-05T12:00:00Z \
  --top-nearest-changes 20 --format csv
```

The ordering is descending **absolute earlier-to-later nearest-distance change**
in approximate km (ties sorted by entity ID). Positive or negative changes
both count; this measures disagreement between *reported locations*, not
physical movement, truth, credibility or source accuracy. An entity not
jointly reported by both sources in **both** comparison periods is
**incomparable**, never assigned zero. The JSON `selection` block explains
the number eligible, omitted and returned. The existing CSV schema is
unchanged and preserves both periods' complete source assertion/evidence IDs
and original coordinates for every selected entity.

Without `--top-nearest-changes`, original JSON and CSV output are unchanged.
The operation reads the persisted WorldMini without modifying its bytes.

## Map temporal source-pair evidence as GeoJSON (WORK-0096)

Use `--format geojson` on either world-time or knowledge-time
comparison, optionally with `--top-nearest-changes N`:

~~~bash
PYTHONPATH=src python3 -m monde.source_pair_changes \
  --fixture saved-world.json --source-a survey-a --source-b survey-b \
  --from-at 2026-01-02T00:00:00Z --to-at 2026-01-05T00:00:00Z \
  --known-at 2026-01-07T00:00:00Z --format geojson > source-pair-periods.geojson
~~~

Each original Point is retained for each earlier/later period with original
coordinates, source/evidence identity and assertion lineage. The export feature
ID is unique across periods, while `monde_original_assertion_id` retains
the original assertion ID. `monde_source_pair` carries the period,
both temporal cutoffs, joint-report status, nullable separation and nullable
earlier-to-later change. `monde_comparison` describes the selected
sources, axis, original schema, cutoffs, epistemic disclaimer and any optional
top-N selection.

The output contains **only original source-reported Points**, never synthetic
connecting routes: reported-source differences do not establish physical
movement, accuracy or truth. Missing comparison values remain `null`,
never zero. Existing JSON/CSV and persisted WorldMini snapshots are unchanged.


## Source-pair convergence and divergence filter (WORK-0096)

The existing offline CLI accepts `--change-direction converging|diverging|unchanged|incomparable`
for **either temporal axis** and any output format (`json`, `csv`, `geojson`).
The comparison is the *later minus earlier nearest distance between the
two original reporting sources*: negative is `converging`, positive is
`diverging`, exactly zero is `unchanged`. An entity missing joint reports
in either period is `incomparable`, never a zero-distance assertion.

```bash
PYTHONPATH=src python3 -m monde.source_pair_changes \
  --fixture saved-world.json --source-a survey-a --source-b survey-b \
  --at 2026-01-05T00:00:00Z \
  --from-known-at 2026-01-03T12:00:00Z \
  --to-known-at 2026-01-05T12:00:00Z \
  --change-direction diverging --top-nearest-changes 20 --format geojson
```

Direction filtering precedes optional top-N ranking. The GeoJSON projection
retains original source/assertion/evidence identity and adds per-feature
classification and filter metadata; the stored WorldMini remains byte-identical.
This reports change in **source disagreement**, never verified physical movement.
Without the new option, existing JSON/CSV output and ranking are unchanged.


## Open a complete interactive offline evidence map (WORK-0096)

The existing local MONDE Mini SVG/map viewer can now display **both original
source-reporting periods** directly from a saved WorldMini comparison:

~~~bash
PYTHONPATH=src python3 -m monde.source_pair_changes \
  --fixture saved-world.json --source-a survey-a --source-b survey-b \
  --from-at 2026-01-02T00:00:00Z --to-at 2026-01-05T00:00:00Z \
  --known-at 2026-01-07T00:00:00Z \
  --change-direction diverging --format html > pair-evidence.html
~~~

Open \`pair-evidence.html\` in a browser **without a web server or Internet**.
The existing period/source/entity filters, point selection and evidence exports
remain available. The map embeds earlier and later **original Points separately**;
it never draws an inferred movement path, synthesizes a true position, or rewrites
evidence. Viewport fitting is based on the *selected* original Points and wraps
across the antimeridian. Empty selections show no points, not fabricated data.

The standalone HTML is generated by the already-existing \`monde.map_view.render_map\`
(with its CSP, escaped embedded JSON and self-contained land reference). Both
bitemporal comparison axes, source filters, and optional top-N apply *before*
rendering. JSON, CSV and GeoJSON formats remain unchanged when HTML is not requested.

## Browse original source-pair changes over local HTTP (WORK-0097)

Open `/source-pair` in the existing loopback-only read-only MONDE Mini
server. Two native GET forms allow choosing exact original source IDs and
either (1) a fixed world instant with two increasing knowledge cutoffs, or
(2) two increasing world-valid instants at one knowledge cutoff.

The result opens the **existing** self-contained HTML comparison map,
retaining both original reporting periods, source/assertion/evidence IDs,
nullable unknown states, and the original epistemic warnings. Specify
`format=json` or `format=geojson` for the same underlying comparison
as the offline CLI; `direction=converging|diverging|unchanged|incomparable`
optionally filters original source-separation changes without claiming
physical movement. Unknown parameters or invalid source IDs are rejected.

No new comparison engine, model, paid API, service, network permission, or
saved-state write is introduced. This is an unmerged stacked candidate,
not a new public web service or production deployment.

## Browser CSV export and top source-pair separation changes (WORK-0098)

In the local read-only MONDE Mini server, open `/source-pair`, select the
two original source IDs and choose either world-time or knowledge-time
cutoffs. The native form now offers **complete evidence CSV** alongside
the existing offline comparison map, JSON and GeoJSON.

The optional *Separation change* selector accepts `converging`,
`diverging`, `unchanged`, or `incomparable`. *Top absolute nearest
changes* accepts integers from 1 to 1000. Direction filtering happens
**before** top-N ranking, and the same canonical source-pair engine
calculates all output formats. Empty optional controls mean no filtering.

A direct read-only query can include `format=csv&top=20&direction=diverging`
along with the six required source/temporal parameters. The CSV is the
existing canonical `comparison_csv` output: every selected entity has
both original observation periods, source, assertion and evidence
identifiers, coordinates and nullable separation; no inferred source
agreement, ground truth or physical movement. CSV formula-escaping is
inherited from the same exporter. The response is a local file attachment,
with no caching, CORS, network request or saved-state write. Invalid or
oversized query controls return an error.

## Focus one entity in a source-pair comparison (WORK-0099)

The native read-only `/source-pair` browser forms now offer optional
**Entity ID**, e.g. `&entity=site-1`. The exact entity is selected from
the existing canonical world- or knowledge-time original-report comparison
*before* optional convergence/divergence selection and top-N ranking.
HTML map, JSON, GeoJSON and CSV preserve the earlier/later original
assertions, sources, evidence IDs, reported coordinates, nullable
separations and cutoffs. Missing entities produce an empty valid comparison
and never a fabricated location. Empty optional form input is ignored.
The existing loopback-only HTTP server and saved snapshots remain read-only.

## Accessible original source-pair evidence table (WORK-0100)

The existing loopback-only `/source-pair` native forms provide **Accessible source-pair evidence table** (`format=table`) on both knowledge-time and world-time axes. Each row displays one canonical entity's earlier/later original-source nearest and farthest separations, an explicitly nullable nearest-distance change, direction, and the unmodified source, assertion/evidence IDs and reported Point coordinates. Original report details include separate world-validity and knowledge cutoff values with read-only links to the existing source-history inspector. Entity dossiers link to both original temporal cutoffs. The header links back to the canonical map, JSON, GeoJSON and complete evidence CSV with the same source, entity, direction and top-N selections.

The HTML output is a server-rendered, accessible plain table without scripts or new endpoints, services or external dependencies. All original strings and query-derived href attributes are escaped; there is no new physical-ground-truth or motion inference. Empty sets have an explicit UNKNOWN notice. Existing `format=html|json|geojson|csv` behavior remains unchanged. Regression tests exercise both temporal axes, filtering, original evidence lineage, safe HTML and immutable persisted snapshots.

## Minimum material original-source separation change (WORK-0100)

The existing `/source-pair` native form accepts optional `min_change_km=2.5` for both world-validity and knowledge-time comparisons. Original entity, direction and minimum absolute nearest-separation change filters apply **before** top-N ranking. Only entities with comparable earlier **and** later source-reported separations qualify; missing comparisons remain UNKNOWN and are not treated as zero. The same selection is reflected in the HTML/map, accessible table, JSON, GeoJSON and CSV. No new route, distance algorithm, persistence mutation or hosted dependency.

## Original source-pair geographic focus (WORK-0101)

The existing read-only `GET /source-pair` browser forms accept an optional
`bbox=west,south,east,north` WGS84 longitude/latitude rectangle. Both
knowledge-time and world-validity comparisons support this. West greater
than east selects an antimeridian-wrapping rectangle.

An entity qualifies only when **either original selected source reports a
Point within the rectangle at the earlier or later cutoff**. Selection happens
before direction, minimum absolute change and top-N filtering. **All original
Point reports from both sources at both cutoffs remain in the selected row**,
including any reported coordinates outside the rectangle. Thus the filter
cannot manufacture apparent agreement or hide conflicting evidence in the
selected entity. It never infers physical movement, estimated position,
accuracy, source credibility or ground truth.

With `bbox`, JSON adds a `spatial_filter` object with the original numeric
bounds, selection basis and counts. GeoJSON includes the same metadata as
`monde_comparison.spatial_filter`, retaining every original feature's
source/assertion/evidence provenance. The accessible table displays the
geographic focus; current map, CSV and JSON routes remain the same.
Without `bbox`, output behavior and schemas are unchanged.

Blank optional bbox fields submitted by the browser mean no filter.
Malformed, nonfinite, out-of-WGS84 or inverted latitude values return 400.
This is entirely local, read-only, dependency-free, with unchanged saved
WorldMini bytes. Draft stacked on WORK-0100, not merged into `main`.

## Qualify a region by the original reporting source (WORK-0102)

Use `region_source=a` or `region_source=b` with an existing WGS84 `bbox`
to select entities where **that source's original Point** falls in the
region in either period. Without the selector (or `region_source=either`),
the previous either-source rule is unchanged. No region means the source
selector is invalid. The returned entities keep **both** sources' complete
original Points and provenance, including observations outside the focus.

The selection is applied before entity, direction, minimum-change and top-N
filters for both world-time and knowledge-time comparisons. JSON and GeoJSON
retain the qualifying original source ID; map, table and CSV use identical
selected evidence. All operations are offline/local read-only; there is no
consensus position, verified movement or additional dependency.


## Focus on both original reporters at the same cutoff (WORK-0103)

The read-only `/source-pair` form now supports `region_source=both`
alongside `either`, `a` and `b` when a WGS84 `bbox` is present.
An entity qualifies **only if both original sources independently report
a Point inside the region in the same earlier or later comparison period**.
Reports from A at the earlier cutoff and B only at the later cutoff
do not qualify merely because their union intersects the viewport.

Example:
`/source-pair?axis=knowledge&source_a=survey-a&source_b=survey-b&at=2026-01-05T00%3A00%3A00Z&from_known_at=2026-01-03T00%3A00%3A00Z&to_known_at=2026-01-06T00%3A00%3A00Z&bbox=29.5%2C-1%2C32.5%2C1&region_source=both&format=table`

Filtering still precedes entity/direction/min-change/top-N; every
selected entity retains the complete original source assertions from both
periods, including reported Points outside the region. The same selection
feeds the existing HTML map, accessible table, JSON, GeoJSON and CSV, on
both world-time and knowledge-time axes. This is **joint geographic reporting**,
not agreement, verified proximity or ground truth. No new endpoint, source
parser, dependency or persistence write is introduced.

## Choose the exact geographic comparison period (WORK-0103)

With WGS84 `bbox`, optional `region_period=earlier|later` qualifies
an entity only using the original reporter Points at that one comparison
cutoff. Default is both periods as before. With `region_source=both`,
both original sources must separately qualify at the selected same cutoff.
Complete earlier/later source evidence is kept in the unchanged HTML map,
accessible table, CSV, JSON and GeoJSON. Missing `bbox` or invalid period
returns HTTP 400. The response records `spatial_filter.qualifying_period`
only for an explicitly selected period.


### Require original reporting at both cutoffs (WORK-0103)

Choose `region_period=both` with an existing WGS84 `bbox` to retain an
entity only when the selected `region_source` criterion is satisfied **at
each of the earlier and later cutoffs independently**. For `region_source=both`,
each original reporting source must have its own in-region Point at *both*
cutoffs; an earlier-only source and later-only source cannot combine to qualify.
With `region_source=a|b|either`, that same reporter selection is evaluated
separately at both cutoffs (for `either`, the qualifying reporter may differ).

The default `region_period=either` retains its prior OR semantics, and
`earlier|later` remain available. JSON and GeoJSON include
`spatial_filter.qualifying_period="both"` when selected; the HTML map,
accessible table and CSV select the same original evidence without stripping
out-of-region reports, changing the World Model or inferring verified motion.

For explicit `region_period=both`, `spatial_filter.basis` uses
`*_IN_EACH_PERIOD`, and the accessible table says *both cutoffs* rather
than *either period*; legacy defaults retain their existing basis values.


## Persistent original-source separation at both cutoffs (WORK-0104)

The existing loopback-only `/source-pair` comparison form accepts optional
`min_persistent_km=100` for **either knowledge-time or world-time comparison**.
An entity qualifies only if both original sources jointly report Point positions
at *both* selected cutoffs and the minimum cross-source Point separation is at
least 100 km in each period. Multiple reports per source retain the existing
**nearest** pairwise measurement; no consensus or source credibility is inferred.
Missing joint reports are **UNKNOWN and excluded even at a zero threshold**.
Original A/B reports, assertion/evidence IDs and out-of-region positions remain
unchanged for selected entities. The filter precedes `top` ranking, composes
with region/source/period/direction filters and applies to all existing HTML,
accessible table, JSON, GeoJSON and CSV outputs. The JSON/GeoJSON
`persistent_separation_filter` records the threshold and qualifying count.
The underlying saved WorldMini is never rewritten. Omitting the option retains
the existing output contract.

## Discover original source pairs (WORK-0105)

The existing loopback-only `/source-pair` browser now includes native
**Discover source pairs** forms for knowledge time and world-validity time.
The read-only `discover=1` query returns an accessible ranking table
(`format=table`, default) or machine-readable
`MONDE_SOURCE_PAIR_DISCOVERY_V1` (`format=json`), without requiring
source IDs in advance. Clicking a source pair opens its already-existing
full original-evidence comparison at the same cutoffs.

Ranking uses the **largest nearest original Point separation** across
jointly reported entities at either selected cutoff; counts of jointly
reported entities at earlier and later cutoffs remain distinct. This
is not an accuracy score, consensus location, inferred movement or
continuous persistence claim. Missing joint reports remain UNKNOWN,
never zero. The WorldMini saved snapshot is unchanged.


## Discover increasing/decreasing source-pair differences (WORK-0106)

In the read-only `/source-pair?discover=1` browser, choose
`rank=increasing` or `rank=decreasing` instead of the default
`rank=separation`. Both world-valid-time and knowledge-time axes work.

A trend is calculated only for an **identical entity** jointly reported by
both original sources at **both** cutoffs. It uses the difference between
nearest cross-source reported distances (later minus earlier, approximate km).
The returned example includes both earlier and later original assertion IDs,
along with comparable/matching entity counts. Missing joint reports remain
UNKNOWN; they are not treated as zero or agreement.

The existing detailed source-pair comparison link opens the full original
evidence. The default discovery response remains unchanged. This is a
comparison of original claims, **not** verified location, movement or source
accuracy. No new dependency, hosted service or persistence write.

## Discover original reporter partners (WORK-0107)

An optional `source` in either read-only `/source-pair?discover=1` form
limits separation, increasing and decreasing rankings to pairs containing
that exact original reporter. It enumerates only that source's actual reporting
partners; missing joint Point observations are UNKNOWN, never agreement.
JSON adds `source_focus` only on explicit requests. HTML drilldown removes
the discovery-only filter before opening the existing full original evidence
comparison. Both temporal axes, ranking defaults and original assertion IDs
are preserved. No new route, dependency, store, truth inference or mutation.

### Ranked source-discovery CSV

The existing read-only `/source-pair?discover=1` interface supports `format=csv`
in addition to JSON and an accessible ranked table. Its download link retains the
comparison axis, both world/knowledge cutoffs, original reporter focus, ranking
and top-N selection. The UTF-8 CSV preserves each displayed pair's original
assertion IDs, example entity, reported separation, and both periods' joint
report counts. No matching original reports yield headers only rather than
invented agreement. Strings that could become spreadsheet formulas are escaped.
The response is limited by the existing server response size cap and leaves
persisted evidence unchanged. This is not a verified truth or trajectory.

## Map ranked source disagreement examples (WORK-0108)

The accessible `/source-pair?discover=1` ranking now links each ranked
original source pair directly to an **offline map of its example entity's
original reports**. The map reuses the existing `/source-pair`
`format=html&entity=...` comparison with the identical world-validity
and knowledge cutoffs. Discovery-only filters (`source`, `rank`, `top`,
`discover`) do not leak into map requests; the source pair itself remains
explicit. Every reported Point retains its original assertion identity.
The same ranked row also offers **Download original example GeoJSON** using
the already-supported source-pair `format=geojson&entity=...` export, so a
researcher can inspect the original Points in GIS software without losing
either reporter, original assertion IDs, or both temporal cutoffs. Discovery
filters do not leak into this link. The browser download filename is
`source-pair-example.geojson`; no new endpoint or export format is introduced.

The example is not a consensus position, an accuracy verdict or inferred
movement. Pairs without joint original evidence offer neither an example map
nor an example GeoJSON download. No new endpoint, store, third-party
dependency or network access is added.

### Map all ranked original example Points together (WORK-0108)

Use `format=html` with the existing read-only `/source-pair?discover=1`
query, or follow **Map all ranked original examples** from its ranking table,
to open one offline browser map of the original source Points included in
the existing bulk GeoJSON. Each marker retains rank, reporter pair, original
assertion, earlier/later period and the exact world/knowledge cutoffs. The
same offline map controls are reused, with no new endpoint, storage or paid
API. A map envelope is display-only, not a new geographic query, physical
movement estimate, reconciliation or verification of ground truth. Empty
rankings produce an empty map; the persisted snapshot is never changed.

### Minimum independently joint-reported entities (WORK-0108)

The read-only `/source-pair?discover=1` interface accepts optional
`min_joint=N` (1–10000), before top-N ranking. Separation counts **distinct
entities jointly reported by both original reporters at either temporal
cutoff**; increasing/decreasing trends instead require joint original reports
for the **same entity at both cutoffs**. This is evidence coverage, not source
credibility or ground truth. Default 1 preserves existing results. The same
filtered ranking flows to the accessible table, JSON, original GeoJSON,
CSV and offline map without adding a service, parser, store or paid API.

## Rank source pairs by jointly observed evidence coverage (WORK-0109)

Use `rank=coverage` in either existing `/source-pair?discover=1` form to
prioritize reporter pairs that jointly report original Points for the largest
number of **distinct entities at either cutoff**. Ties prefer the largest
reported nearest-source separation, then source IDs. `min_joint`, source
focus and `top` keep their existing semantics.

Evidence coverage is **not** source credibility, accuracy, verified physical
movement, or ground truth. Missing reports remain UNKNOWN, never inferred
agreement. Existing JSON, CSV, GeoJSON, offline-map and table outputs retain
original assertions and both temporal cutoffs. The default `separation`
ranking is unchanged. No new endpoint, storage, dependency or data mutation.

## Representative geographic divergence by median separation (WORK-0110)

The existing local, read-only `/source-pair?discover=1` supports
`rank=median` on **both** knowledge-time and world-time comparisons. It ranks
original reporter pairs by the median nearest separation of **distinct jointly
observed entities**, not the most extreme original Point. If an entity has
observations at both cutoffs, its greatest nearest separation contributes once:
two captures of the same entity do not count as two independent entities.

The ranked pair JSON exposes `median_nearest_km` (approximate km, rounded to
0.001). The native discovery form offers the option; the accessible table shows
a median column; CSV adds a median field only for this ranking, keeping the
default CSV schema unchanged. The original evidence GeoJSON retains original
Point geometry, source/assertion identity and provenance, with the ranking
median as metadata. Existing per-pair evidence/map drilldowns are reused.
`min_joint` still applies before top-N.

This identifies **representative source-reported separation**, never source
accuracy, physical truth, reliability or inferred movement. Missing joint
reports remain UNKNOWN; all queries reuse persisted WorldMini snapshots
without mutation or external services. PR is stacked on WORK-0109 (#139).


## Original Point source coverage directory (WORK-0111)

In the existing local source-pair browser, choose **Original Point reporter
coverage** for either world or knowledge time. The same bitemporal arguments
as source-pair discovery are used. Set `directory=1` and choose
`format=table` (default), `format=json` or `format=csv`.

Each original source has distinct entity counts and Point assertion counts
at the two cutoffs, along with newly reported, no-longer-reported and
continuously reported entity counts. JSON and CSV retain one original entity
and its actual original assertion IDs per reporter. Click a reporter
to open existing source-focused pair discovery at identical cutoffs.

Absence of a source report is not evidence of agreement. Reporting-count
changes are not proof of physical movement, source accuracy or reliability.
The existing saved WorldMini is read-only and no new service is introduced.


### Original reporter detail — evidence drill-down (WORK-0111)

From the source directory select a reporter. The same local read-only
/source-pair?directory=1 query accepts source=<original ID> with
format=table, json or csv. Every reported entity shows the original
assertion IDs before and after the selected world/knowledge cutoff,
labelled NEWLY_REPORTED, NO_LONGER_REPORTED or REPORTED_AT_BOTH.
Links open the existing source-specific history for that entity.
Reporting presence is not evidence of actual movement or truth.


### Filter original reporter transitions (WORK-0111 incremental)

In the source-specific coverage detail, use **All entities**, **Newly reported**,
**No longer reported** or **At both cutoffs**. These native read-only links
add an optional `change=new|gone|both` to the existing
`/source-pair?directory=1&source=...` query; it applies consistently to
table, JSON and CSV outputs. The unfiltered JSON contract is unchanged;
a filtered JSON response additionally reports `reporting_filter` and
`matched_entities` while retaining the original total source counts and
exact original assertion IDs. The parameter requires a source and rejects
unknown values. Both temporal axes remain explicit; missing reporting is
not evidence of a real disappearance, and saved observations are unchanged.


## Original source coverage GeoJSON (WORK-0112)

The source detail page can export original Point evidence from BOTH selected
world/knowledge cutoffs through the existing source-pair directory route with
format=geojson and an exact source ID. Optional change=new|gone|both selects
entities before their original Points are exported. Every Feature keeps original
assertion, evidence and source identity, unchanged coordinates, original reporting
status, period and time cutoffs. The envelope identifies source and comparison
scope. No location inference, accuracy assessment, physical movement, new
service, persisted-data mutation or paid API. Directory-level GeoJSON without
a source is rejected. Existing JSON, CSV and table behavior is unchanged.


### Original source coverage map (WORK-0112)

On a source-specific coverage detail page, **Map original source Points at both cutoffs** opens the existing local read-only map via `/source-pair?directory=1&axis=knowledge|world&source=...&format=map`. Both earlier and later original Point assertions are rendered, including per-report period, original assertion/evidence IDs and world/knowledge cutoffs. Optional `change=new|gone|both` filters the original reporting transitions. The viewport is a shortest-longitude-arc display envelope, not a new query, inferred physical movement or a consensus source position. The existing GeoJSON/CSV/JSON export contracts and saved WorldMini remain unchanged.

### Filter reporters by bitemporal entity coverage (WORK-0113)

The existing reporter directory has four native read-only views: **All reporters**,
**Any newly reported entities**, **Any no-longer-reported entities**, and
**Any continuously reported entities**. Optional `change=new|gone|both`
reuses the exact original source-reported entity counts at the selected
world/knowledge cutoffs. A reporter qualifies when at least one of its entities
belongs to that class; these categories may overlap. Filtered JSON includes
`reporting_filter` and `available_sources`; `total_sources` and the CSV
describe the filtered list. Reporter detail links retain the same transition
filter, whereas Find partners clears the directory-only filter for its
existing source-pair discovery route. No original observation is mutated,
and absence of a report is UNKNOWN, not verified disappearance or movement.


### Prioritize original reporter coverage changes (WORK-0113)

On the existing read-only original reporter directory, optional
`rank=new|gone|turnover` orders reporters by the number of **distinct
originally reported entities** newly covered, no longer covered, or in
either transition between the selected cutoffs. Ties resolve by source ID.
The native HTML ranking links, JSON `ranking` metadata and matching CSV
share the same order. The `change=new|gone|both` filter still applies
before ranking. The default order and schemas are unchanged when rank is
omitted. Rank is directory-only, never a source-detail or partner query.
Changes reflect reporting coverage, **not** physical loss, accuracy, events
or a verified truth claim; persisted evidence is never modified.


### Prioritize net original reporting coverage change (WORK-0114)

The existing original source directory supports optional `rank=net-gain` or
`rank=net-loss` on both knowledge-time and world-time comparisons. Each rank
uses the signed difference between **distinct source-reported Point entities**
at the later and earlier cutoffs, not the number of assertions or corrections.
Net gain equals newly reported minus no-longer-reported entities; net loss
reverses the sign. Mixed turnover cannot be mistaken for overall coverage
growth. Ties use the original source ID for stable ordering across HTML,
JSON and CSV, with the optional transition filter still applied *before* rank.

These ranks are view-only: no persisted change, inferred geographic movement,
source accuracy or reliability claim. The default directory schema and order,
per-source detail and source-partner discovery remain unchanged. Unknown ranks
and directory ranks on source-specific detail are rejected.


### Find original reporters by exact source ID prefix

The existing directory form accepts optional `source_prefix=survey-` for both
knowledge-time and world-time comparisons. The case-sensitive literal prefix
filters original reporter IDs *before* transition filtering and ranking;
the same selection appears in HTML, JSON and CSV. Prefixes are ASCII letters,
digits, `._:-`, up to 80 characters, not wildcards or patterns.
An empty optional form field leaves old unfiltered JSON unchanged.
Filtered JSON adds `source_prefix` and `available_sources`; no saved
WorldMini model changes. Source detail and pair-discovery links drop
inapplicable directory prefix/rank controls to remain navigable.

## Exact original-entity reporter lookup (WORK-0115)

The existing local source-coverage directory accepts optional `entity` for both
world and knowledge cutoffs. It selects original sources reporting a Point for
that exact entity at either cutoff. The example column preserves that entity's
original assertion IDs. Coverage and ranking statistics still count **all**
entities for each source, not just the focus entity. HTML, JSON and CSV select
the same sources, no data is changed, and detail/partner links omit the
unsupported filter. No additional route, dependency or API.


### Map original reporters of one exact entity (WORK-0115)

The local source directory can open `format=geojson` or `format=map` when
`entity` is explicitly selected. Only that entity's original Points from the
selected reporting sources at both cutoffs are shown, with original assertion,
evidence and source identifiers, unchanged WGS84 positions, period, world time
and knowledge cutoff. Optional source-prefix, ranking and reporting-transition
filters continue to select which reporters qualify. The map viewport is a
source-point display envelope, not verified movement or a consensus position.
Directory requests for a map without `source` or `entity` remain invalid.
No new endpoint, dependency, service, persisted-model mutation or paid API.

## WORK-0116 — Inspect one original reporter's entity map

From an exact-entity original coverage directory, the **Map this reporter for
the entity** link restricts an existing read-only two-cutoff source map to one
original source ID. Use `/source-pair?directory=1&entity=...&source=...&format=map`
with the existing world/knowledge cutoff parameters; `format=geojson` exports
the same exact original assertion/evidence/Point features. The unfiltered
entity reporter directory and per-source detail outputs remain unchanged;
combined source+entity parameters with other formats are rejected. Empty
matches return an empty feature collection, never an inferred location.
The existing saved WorldMini remains byte-identical.

## Compare two original reporters from one entity

The exact-entity original-reporter directory exposes a native, read-only form to select **two distinct original sources** and open the existing source-pair map with the same world/knowledge cutoffs. A source is offered only if it reported that exact entity at one of the selected cutoffs. The map keeps each original Point assertion, source, evidence and comparison period; it never asserts a consensus location, and no extra HTTP endpoint or persistent state is introduced.
