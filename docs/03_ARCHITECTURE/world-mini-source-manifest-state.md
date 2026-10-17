# Persistent original-source WorldMini (WORK-0041)

Turn an original-source manifest containing local CSV, GeoJSON, GPX, KML,
KMZ and GeoPackage datasets into a durable bitemporal WorldMini evidence
state, without creating a map or introducing a new parser or dependency.

    PYTHONPATH=src python3 -m monde.world \
      --ingest-source-manifest sources.json --state-out world.json

A seed fixture is optional for this operation. To extend an existing state
pass --fixture previous.json and write a different --state-out next.json.

The existing temporal/spatial queries and offline map can open the output:

    PYTHONPATH=src python3 -m monde.world --fixture world.json \
      --export-geojson --at 2026-01-02T00:00:00Z \
      --known-at 2026-01-11T10:00:00Z

    PYTHONPATH=src python3 -m monde.map_view --state world.json \
      --at 2026-01-02T00:00:00Z \
      --known-at 2026-01-11T10:00:00Z --output map.html

The importer reuses the existing manifest reader and atomic WorldMini.save.
Bad late sources cause no partial snapshot, original source data is
unchanged, and prior output cannot be replaced unless the caller explicitly
supplies --replace-state. The legacy --ingest-csv-manifest flag still works.

Original coordinates and timestamps are source-reported evidence, not
reconciled geographic truth. No geocoding or physical-motion inference.
The original bounds of 16 datasets and 50,000 source reports remain.

## Query original source coverage at a knowledge cutoff

Read the persisted snapshot to inspect which independent source reports MONDE
had at a specific knowledge-time cutoff:

```sh
PYTHONPATH=src python3 -m monde.source_inventory --state world.json \
  --known-at 2026-01-11T10:00:00Z
```

Output lists each original source ID separately, including independent
GeoPackage layers, the original source locator(s), evidence count, recorded
assertion count, distinct entity count, attributes and timestamp ranges.
Reports captured after the cutoff and assertions learned later are excluded.
This **read-only** inventory does not modify the original datasets or
persistent snapshot and does not imply truth, confidence or physical movement.


## Preview a source capture without changing saved state (WORK-0044)

Inspect source-reported changes, including before/after values and the
original source locator, **before** deciding to save another world snapshot:

```sh
PYTHONPATH=src python3 -m monde.world \
  --fixture previous-world.json \
  --preview-source-manifest updated-sources.json
```

The result is a JSON report labeled `PREVIEW_NOT_SAVED`. No output state is
created or overwritten. Both earlier and incoming values are **source claims**,
not reconciled physical truth. Missing rows never imply that features were
deleted. Invalid, ambiguous, or stale captures reject without output state.
The analyst can then run the existing `--refresh-source-manifest`
command with a new `--state-out` after reviewing the evidence.
Changing the manifest between preview and refresh requires a new inspection.

## Preview new source Point reports on an offline map (WORK-0044)

Create a local map **before** accepting a later capture. The HTML contains only
newly recorded source-reported Points, with source identity, original locator,
valid/knowledge times and correction ancestry. It is **not** a map of verified
physical movement or deletions:

```sh
PYTHONPATH=src python3 -m monde.world \
  --fixture previous-world.json \
  --preview-source-manifest updated-sources.json \
  --preview-source-map capture-preview.html
```

The command still prints the ordinary `PREVIEW_NOT_SAVED` JSON summary;
`preview_map_html` identifies the created offline visualization. It does
not create or alter a WorldMini snapshot. The HTML output must be a **new path**
(existing output, the manifest, source files and the original snapshot cannot
be overwritten). An invalid capture produces no map. No network access is
needed to open the generated page.

## Confirm a source capture already inspected (WORK-0045)

The preview JSON includes `preview_sha256`, a SHA-256 digest of the
**complete original and resulting WorldMini evidence states**, including
their source/claim histories. Copy it into the refresh command:

```sh
PYTHONPATH=src python3 -m monde.world \
  --fixture before.json --preview-source-manifest captured.json
# Copy the preview_sha256 field from this JSON output:
PYTHONPATH=src python3 -m monde.world \
  --fixture before.json --refresh-source-manifest captured.json \
  --expect-preview-sha256 THE_64_CHARACTER_SHA256 --state-out accepted.json
```

If the parsed capture or original state changes before refresh, nothing is
saved. Original data and old snapshots are not overwritten. This is an
optional semantic consistency check, not an exact raw-file-byte checksum,
digital signature or assertion of physical truth. The existing unconfirmed
refresh command remains available and unchanged.


## Preview conflicting reports from different sources (WORK-0046)

The existing \`--preview-source-manifest\` response also lists
\`cross_source_disagreement_count\` and \`cross_source_disagreements\`.
Before accepting a capture, analysts can now see each **newly recorded**
value that differs from another source's report on the same entity and
attribute during an overlapping source-validity interval. Each item
preserves both assertion IDs, independent source IDs, the original values,
knowledge cutoff and the precise overlap interval. Later known corrections
of a source replace that source's earlier report when comparing; absence
of a row never means retraction.

This is a **warning about source-report disagreement**, not a confidence
estimate, verified ground truth, physical motion or a merge decision. The
existing preview digest and confirmed refresh command remain unchanged.
The preview still does not save or rewrite a world snapshot.


The optional `--preview-source-map preview.html` now includes the same
cross-source disagreement warnings as the JSON preview, with both original
source IDs, values, assertion IDs and overlapping validity interval. The
standalone HTML works offline; untrusted source strings appear as text, not
HTML, and the persisted world and raw source files are not modified.


## Explore saved contradictory source positions offline (WORK-0047)

After capturing a WorldMini state, inspect **only** entities for which distinct
sources currently report incompatible geographic Points at a chosen world-time
instant and knowledge cutoff:

```bash
python -m monde.map_view --state world.json \
  --at 2026-01-02T00:00:00Z --known-at 2026-01-10T10:00:00Z \
  --only-disagreements --output saved-source-disagreements.html
```

The generated self-contained HTML shows each competing original source Point
separately, retaining source IDs, evidence metadata and bitemporal labels.
Automatic bounds fit the disagreeing claims, including across the dateline.
An explicit `--bbox W,S,E,N` retains every contrary report for an entity
qualifying inside the viewport, even if a different source places it outside.
If there are no conflicting Points, auto-fit refuses to invent a location;
an explicit bbox can still show an empty map. The new mode cannot be combined
with `--compare-at` or `--compare-known-at`.

This is read-only source-report disagreement, **not** a verified position,
physical movement or inference of ground truth. Existing maps and state files
are unchanged; an existing HTML output file is never overwritten.


## Bitemporal source disagreement changes (WORK-0048)

Compare a fixed world-valid time between two knowledge cutoffs:

    PYTHONPATH=src python3 -m monde.world --fixture world.json \
      --source-disagreements --at 2026-01-02T00:00:00Z \
      --compare-known-at 2026-01-09T00:00:00Z \
      --known-at 2026-01-12T00:00:00Z

The read-only JSON classifies APPEARED, RESOLVED and CHANGED source/value
contradictions while retaining original before/after source reports and
evidence IDs. A new assertion ID with identical source value is not a new
conflict. RESOLVED means conflicting reports are no longer present at the
specified cutoff, **not** that a physical location is verified. Existing
single-cutoff --source-disagreements commands retain their behavior.
