# MONDE Mini — GeoJSON source-knowledge changes (experimental)

WORK-0012 exports **which source-reported Points became current or ceased to be current** between knowledge cutoffs K1 and K2, for the *same* valid-world-time T. These are **changes in what MONDE knew**, not verified physical moves, new buildings or world events.

```sh
PYTHONPATH=src python3 -m monde.world --fixture saved-world.json \
  --export-geojson-changes --at 2026-01-02T00:00:00Z \
  --compare-known-at 2026-01-10T00:00:00Z \
  --known-at 2026-01-12T00:00:00Z > source-changes.geojson
```

Optional `--export-bbox '2.3,48.8,3.3,49.2'` restricts each snapshot to reported coordinates in the viewport, including antimeridian-crossing boxes. Each GeoJSON Feature preserves source ID, original evidence ID, locator, valid/known/capture times and reported geometry. `properties.monde_change` is `NEWLY_CURRENT` or `NO_LONGER_CURRENT`; `properties.monde_change_basis` is always `KNOWLEDGE_NOT_PHYSICAL`. Unchanged source assertions are omitted. An updated source location may emit both old and new positions; other sources are unaffected.

The implementation reuses `WorldMini.export_geojson` twice and compares stable assertion IDs. No new service, database, external API, inference or map index. Empty FeatureCollections do not prove physical absence.
