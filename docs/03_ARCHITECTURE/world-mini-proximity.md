# Source-reported proximity — MONDE Mini (experimental)

WORK-0010 builds on the [bbox query](world-mini-spatial-search.md) and the
[GeoJSON Point import](world-mini-geojson.md). Search for current source reports
within a specified approximate WGS84 **spherical great-circle** radius:

```sh
PYTHONPATH=src python3 -m monde.world --fixture saved-world.json \
  --search-geo-radius '2.3522,48.8566' --radius-km 3 \
  --at 2026-01-02T00:00:00Z --known-at 2026-01-11T00:00:00Z
```

Every matching entity retains evidence and source IDs, original locator,
captured/source timestamps, matching reports (with derived `distance_km`),
other current source locations, and both query time cutoffs. Results are
ordered by nearest **reported** distance; different sources may place one
entity at different coordinates. A source position is not a verified location,
and `NO_MATCHES` never means the entity or place is physically absent.

Distances use a spherical haversine with mean Earth radius 6371.0088 km;
they are approximate search measurements, **not** positional accuracy,
ellipsoidal survey results, inferred location, source uncertainty or a
confidence estimate. Radius is finite and nonnegative; zero permits exact
coordinate matches. Antimeridian/polar searches use shortest spherical arcs.
All operations are read-only, bitemporal and linear-time in this experimental
in-memory dataset; no network, new dependency, index or truth reconciliation.
