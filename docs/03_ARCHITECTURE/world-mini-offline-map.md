# MONDE Mini — offline interactive evidence map (WORK-0017)

**Experimental user-visible slice, not the MONDE production Globe.**

Generate a single HTML file from a saved MONDE Mini state:

```sh
PYTHONPATH=src python3 -m monde.map_view \
  --state saved.json \
  --bbox '2.34,48.84,2.36,48.87' \
  --at 2026-01-02T00:00:00Z \
  --known-at 2026-01-10T10:00:00Z \
  --output evidence-map.html
```

Open `evidence-map.html` in a browser. The self-contained page requires no server,
API key, JavaScript library, remote tiles, external images or internet access.

Use **Zoom +/-** and **Whole world** for a schematic longitude/latitude
world grid, filter the source list, and select any point or report to inspect
its assertion ID, source ID, original locator, evidence ID, capture time and
temporal cutoffs. Filled markers are within the requested bbox; hollow
markers are alternative positions reported by other sources for matching
entities, **even when outside the selected viewport**.

The projection is deliberately schematic, not a detailed coastline basemap.
The source-reported coordinates do not establish the entity's true physical
position. An empty result means there are no *matching known source reports*,
not that a place is physically empty. Different source claims are not merged.

Input is read-only; output must be a new path to prevent accidental overwrite.
Large exports are refused explicitly (5,000 features or 3 MB of embedded
JSON), not silently truncated. Source metadata is encoded as safe JSON in a
nonexecutable script element, and displayed using DOM text nodes. The page
has an offline-denying Content Security Policy.

Existing WORK-0016 viewport GeoJSON and its world/knowledge time semantics
are reused without modifying the World Model or adding another database.
