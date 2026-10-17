# MONDE Mini — Complete GeoPackage in a mixed-source offline map (WORK-0040)

The existing source manifest can now combine **all feature layers** from an
original local GeoPackage with independent CSV, GeoJSON, KML, KMZ and GPX
datasets in a single offline map. No network requests, dependencies or new
parsers are introduced.

Example `sources.json` beside the local files:

    {
      "datasets": [
        {
          "gpkg": "survey.gpkg", "gpkg_all_layers": true,
          "source_id": "survey",
          "locator": "dataset://original/survey.gpkg",
          "captured_at": "2026-01-10T10:00:00Z",
          "valid_from": "2026-01-01T00:00:00Z"
        },
        {
          "geojson": "notes.geojson", "source_id": "field",
          "locator": "dataset://original/notes.geojson",
          "captured_at": "2026-01-10T10:00:00Z",
          "valid_from": "2026-01-01T00:00:00Z"
        }
      ]
    }

Run:

    PYTHONPATH=src python3 -m monde.map_view \
      --source-manifest sources.json \
      --at 2026-01-02T00:00:00Z --known-at 2026-01-10T10:00:00Z \
      --output combined.html

Every original layer retains its own source ID (`survey:layer_name`), original
SQLite FID reference and bitemporal evidence. EPSG:3857 map coordinates stay
labelled as derived; sources are never merged into a ground-truth location.

For a GeoPackage entry, choose exactly one of `gpkg_layer` (existing single
layer) or `gpkg_all_layers: true` (all layers). The flag is rejected on other
formats; false, string booleans or conflicting selections are rejected.
The existing limits of 16 datasets, 16 layers per GeoPackage and 50,000
features per manifest remain in force. Invalid input leaves no partial HTML.
