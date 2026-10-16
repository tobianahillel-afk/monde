# MONDE Mini — bitemporal source Point viewport (WORK-0016)

The viewport GeoJSON capability reuses the existing `search_geo_bbox` and
GeoJSON Point conversion. From a saved state, run:

```sh
PYTHONPATH=src python3 -m monde.world --fixture saved.json \
  --export-geojson-bbox '2,48,3,49' \
  --at 2026-01-02T00:00:00Z --known-at 2026-01-11T00:00:00Z
```

Coordinates are inclusive WGS84 west,south,east,north. West greater than
east crosses the antimeridian. An entity qualifies when **at least one
current source-reported Point** is inside the viewport. All other current
source Point reports for that entity remain as separate features, even
when outside the viewport. Per-feature `monde_inside_bbox` distinguishes
actual viewport matches from contrary source reports.

Each Feature preserves source/evidence IDs, original locator, capture/source
times, validity and knowledge cutoffs. `monde_bbox_query` states the
viewport, temporal cutoffs, matching entity count and feature count.
`NO_MATCHES` denotes absence of *qualifying known reports*, never physical
absence. This experimental, unindexed 2D source map offers no inferred
physical position, movement, precision or truth reconciliation.

## Bitemporal viewport knowledge changes

With a persisted state, inspect how source-reported Points change between knowledge
cutoffs, even when a source correction leaves the viewport:

~~~sh
PYTHONPATH=src python3 -m monde.world --fixture saved.json \
  --export-geojson-bbox-changes '2,48,3,49' \
  --at 2026-01-02T00:00:00Z \
  --compare-known-at 2026-01-10T00:00:00Z \
  --known-at 2026-01-11T00:00:00Z
~~~

An entity qualifies when a current source Point intersects the viewport at
**either** cutoff. The feed includes its entering or leaving source reports
even if a changed position is outside the viewport, retaining original
source/evidence IDs, timestamps and locators. Per-feature `monde_change` is
`NEWLY_CURRENT` or `NO_LONGER_CURRENT`; `monde_inside_bbox` refers to the
report geometry at that cutoff. These describe changed **knowledge**,
never verified physical movement. Unchanged reports are omitted; an empty
result does not imply a physically empty region. This experiment is unindexed.
