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
