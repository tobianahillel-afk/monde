# MONDE Mini — GeoJSON map of current source Points within a radius

WORK-0015 reuses the existing bitemporal radius search to produce GeoJSON
FeatureCollection markers for a geographic map.

```sh
PYTHONPATH=src python3 -m monde.world --fixture saved.json \
  --export-geojson-radius '2.3522,48.8566' --radius-km 5 \
  --at 2026-01-02T00:00:00Z --known-at 2026-01-11T00:00:00Z
```

An entity qualifies if **one or more current source-reported Points** is
within the inclusive approximate spherical radius. All other current source
reports for each qualifying entity remain separate GeoJSON features, **even
if outside that radius**. This avoids treating one source's nearby position
as a verified location while silently dropping contradictory sources.

`properties.monde_within_radius` distinguishes qualifying positions from
outside-source counterparts. `monde_radius_entity_rank` sorts qualifying
entities by their closest source report; `monde_radius_entity_nearest_km`
records that approximate derived distance. Each feature retains its
assertion/evidence/source identity, locator, time-of-source-report/capture,
validity range, knowledge cutoff and original WGS84 2D coordinates.

`monde_distance_km` is populated only for qualifying points; `null` on
competing outside points means **not computed by this query**, not zero
distance. `monde_radius_query` includes center/radius, temporal cutoffs,
distance method and returned counts. No-match does not prove physical
absence. This is an experimental, unindexed, read-only in-memory operation
without external dependencies or inference of ground truth or movement.
