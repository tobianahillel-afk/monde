# MONDE Mini — Bitemporal GeoJSON map export (experimental)

WORK-0011 exposes source-reported Points already held in MONDE Mini as a
standards-compatible GeoJSON `FeatureCollection`, ready to be consumed by a
map or future MONDE Globe. It never chooses a single ground-truth location.

```sh
PYTHONPATH=src python3 -m monde.world --fixture saved-world.json \
  --export-geojson --at 2026-01-02T00:00:00Z \
  --known-at 2026-01-11T00:00:00Z > map.geojson
```

Optional viewport, including antimeridian-crossing bounds:

```sh
PYTHONPATH=src python3 -m monde.world --fixture saved-world.json \
  --export-geojson --export-bbox '2,48,3,49' \
  --at 2026-01-02T00:00:00Z --known-at 2026-01-11T00:00:00Z
```

Every *currently visible* source Point assertion becomes its **own**
GeoJSON Feature, identified by its assertion ID. Properties retain entity,
source, evidence, original locator, capture/source/knowledge and validity
timestamps, and the requested T/K cutoffs. Conflicting source coordinates
become separate Features, not a fabricated consensus. A corrected assertion
only disappears once its replacement is known at K. Bbox limits *reports*,
never excludes the existence of other reports about an entity.

Reuses the existing bitemporal `query`, Point validator and bbox scan. It
adds no external dependencies, geocoding, inferred confidence or new storage.
This remains a linear, in-memory experimental map-data interface. Missing
Features are not proof that an entity or physical location is absent.
