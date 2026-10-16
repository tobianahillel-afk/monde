# MONDE Mini — CSV export of bitemporal source-reported Points (WORK-0020)

This experimental product capability exports the **current source reports** at
an explicit world-time and knowledge-time cutoff. It does **not** reconcile
competing sources or estimate true physical coordinates.

After importing [source CSV datasets](world-mini-csv-import.md) to a saved
WorldMini state, run:

    PYTHONPATH=src python3 -m monde.world \
      --fixture saved.json --export-csv \
      --at 2026-01-02T00:00:00Z --known-at 2026-01-11T10:00:00Z > reports.csv

Optionally add `--export-bbox '2.34,48.84,2.36,48.87'` to filter the
**source-reported** positions by WGS84 viewport. Every disagreeing source
position is a separate row; outside-viewport reports are excluded from that
filtered derivative, never deleted from the underlying WorldMini state.

The table includes entity, numeric longitude/latitude, assertion_id,
source_id, evidence_id, original locator, captured_at, source_event_at,
kind, known_at, valid_from, valid_to, query valid_at and knowledge_cutoff,
and `monde_status=SOURCE_REPORTED_ONLY`. Null event/end times are empty
cells (unknown), not invented values.

Untrusted text fields beginning with spreadsheet-formula characters are
escaped with an apostrophe.

The **offline source map** also offers **Export visible CSV** alongside its
filtered GeoJSON export. The download contains exactly the source assertions
currently shown after entity, source, capture-date, conflict, search, radius,
viewport, temporal-change and displayed-window filters. It adds
`monde_inside_bbox`, `monde_change`, and
`export_scope=FILTERED_VISIBLE_SOURCE_REPORTS_ONLY` to distinguish this
filtered derivative from the complete source snapshot. One row is generated
per original assertion, preserving independent and disagreeing sources;
no consensus location is calculated. Empty matching selections disable export.
UTF-8/BOM, quoted fields and apostrophe-escaping for untrusted formula-like
text enable offline spreadsheet inspection without a new server or dependency. This CSV is an **analysis/report export**; it is
not a replacement for the multi-source CSV ingest manifest or a ground truth
database. Only Python's standard library and existing WorldMini methods are used.
