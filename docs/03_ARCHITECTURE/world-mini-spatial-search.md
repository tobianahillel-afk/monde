# Source-reported spatial search — MONDE Mini (experimental)

After importing GeoJSON Point evidence through WORK-0008, MONDE Mini can find
entities that at least one source claims are inside a WGS84 bounding box.
The result is not verified physical truth.

Example, after saving a snapshot:

    PYTHONPATH=src python3 -m monde.world --fixture saved-world.json \
      --search-geo-bbox '2.3,48.8,2.4,48.9' \
      --at 2026-01-02T00:00:00Z --known-at 2026-01-11T00:00:00Z

The box is WEST,SOUTH,EAST,NORTH in WGS84 degrees. Boundaries are inclusive.
When WEST is greater than EAST, the rectangle crosses the antimeridian.
The world-time and knowledge-time cutoffs have the same semantics as the
existing MONDE Mini bitemporal queries.

A matching entity retains its full evidence-linked source reports in
matched_reports, and other current source positions in other_reports.
Different sources can disagree. NO_MATCHES does not prove physical absence,
nor does it imply that missing data is false.

Malformed Point records and invalid bounding boxes fail explicitly. This
is a linear scan appropriate only for the experimental in-memory dataset;
no GIS index, new library, network fetch or geocoding is introduced.
