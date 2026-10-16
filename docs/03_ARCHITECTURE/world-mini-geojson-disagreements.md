# MONDE Mini — GeoJSON of conflicting source-reported Point locations

WORK-0013 adds a bitemporal map-ready `FeatureCollection` of **source disagreement**, not reconciled or verified physical locations. Every current conflicting report remains a separate Point feature with its original source, evidence ID, locator, world validity and knowledge timestamp.

```sh
PYTHONPATH=src python3 -m monde.world --fixture saved-world.json \
  --export-geojson-disagreements --at 2026-01-02T00:00:00Z \
  --known-at 2026-01-12T00:00:00Z > disagreements.geojson
```

`--export-bbox WEST,SOUTH,EAST,NORTH` restricts the rendered Points. **Disagreements are detected against all current reports before clipping.** A visible Point can thus list competing source IDs whose positions lie outside the viewport. Each feature includes `monde_disagreement_basis=DISTINCT_SOURCE_REPORTS_NOT_PHYSICAL_TRUTH` and `monde_conflicting_source_ids`. Two independent sources reporting the exact same coordinates do not constitute a disagreement. An empty result is not proof of real-world agreement or absence.

The method reuses `WorldMini.source_disagreements` and `WorldMini.export_geojson`; no new storage, GIS engine, model, external API or paid service.
