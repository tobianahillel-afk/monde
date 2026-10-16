# MONDE Mini — nearest bitemporal Points rendered as GeoJSON

WORK-0014 exports the existing nearest-source-Point query as GeoJSON, ready for a map view.

Run from a saved state:

    PYTHONPATH=src python3 -m monde.world --fixture saved.json \
      --export-geojson-nearest '2.3522,48.8566' --nearest-limit 10 \
      --at 2026-01-02T00:00:00Z --known-at 2026-01-11T00:00:00Z

The result is a FeatureCollection with the extra GeoJSON foreign member
monde_nearest_query recording center, limit, time cutoffs, distance method,
total matching entities and whether more exist. Ranking uses the nearest
CURRENT SOURCE REPORT per entity, never reconciled ground truth. Every
current conflicting source Point for each selected entity remains a separate
Feature, so the feature count can exceed the entity limit.

Each marker retains assertion ID, evidence ID, source ID, locator, source and
capture timestamps, world validity and knowledge cutoff. Distances are
derived spherical haversine approximations, not positional accuracy or a
claim of verified physical location. A no-match result is not proof of
absence in the physical world. Experimental read-only in-memory scan,
without GIS dependencies, remote services, or geospatial indexing.
