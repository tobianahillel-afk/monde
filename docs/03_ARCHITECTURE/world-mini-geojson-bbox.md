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
