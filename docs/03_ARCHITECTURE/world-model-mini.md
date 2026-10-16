# MONDE Mini — executable bitemporal World Model discovery slice

Status: EXPERIMENTAL — proposed WORK-0006 / LOT-2. Not the Accepted World Ledger.

MONDE previously had no executable product World Model on main. This coherent
spike adds a standalone evidence-to-historical-query capability using the Python
standard library. It is not a final schema or a production persistence layer.

## User journey

1. Record an external source evidence reference: immutable evidence ID, source ID,
   locator, original source event time and separate capture time.
2. Append a source-reported observation or claim with a validity interval, a
   knowledge timestamp, a subject, property and immutable evidence reference.
3. Query valid-at time T and knowledge-cutoff K independently.
4. Receive all non-superseded source reports with their original provenance,
   including contradictory sources. The answer is REPORTED, never verified truth.
5. Append a same-source correction of a previous claim without rewriting the
   old historical knowledge snapshot.

Both source event time and capture time remain unchanged. No estimated or
simulated statement can be ingested as an observed claim. UNKNOWN differs from
zero or false. Historical validity uses [valid_from, valid_to), with optional
open end. Revisions with changed interval scope are deliberately unsupported.

## Run without any paid API or local dependency

From repository root, use Python 3:

    PYTHONPATH=src python3 -m monde.world \
      --fixture examples/monde-mini.json \
      --entity building-001 --attribute floors \
      --at 2026-01-02T00:00:00Z \
      --known-at 2026-01-07T00:00:00Z

The synthetic building produces two contradictory source reports: 6 and 7
floors. A knowledge cutoff before the city correction returns 5 and 6. An
unknown property returns status UNKNOWN and zero reports.

For a source-attributed snapshot of **all known building attributes** at the
same valid-time and knowledge cutoff, omit `--attribute` and use
`--all-attributes` instead:

    PYTHONPATH=src python3 -m monde.world \\
      --fixture examples/monde-mini.json \\
      --entity building-001 --all-attributes \\
      --at 2026-01-02T00:00:00Z --known-at 2026-01-07T00:00:00Z

The snapshot contains one key per reported attribute, with all distinct source
reports preserved; no reconciled value is selected. Absent/unobserved properties
are omitted rather than represented as zero. A real observed zero remains zero.

    PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_world_mini.py' -v

A separate GitHub Actions PR CI runs these real Python and CLI tests.

## Compare what sources reported at two knowledge cutoffs

At a fixed world-time T, MONDE Mini can now show which source-reported
assertions became current and which earlier reports ceased to be current
because of corrections. It never treats a knowledge update as a physical
change in the world.

    PYTHONPATH=src python3 -m monde.world \
      --fixture examples/monde-mini.json \
      --entity building-001 --all-attributes \
      --at 2026-01-02T00:00:00Z \
      --compare-known-at 2026-01-05T00:00:00Z \
      --known-at 2026-01-07T00:00:00Z

The output has comparison KNOWLEDGE_ONLY and retains complete provenance
for newly current and no-longer-current source reports, including their
original event/capture timestamps. On the synthetic building, the city
registry corrects 5 floors to 7; the independent news claim of 6 remains
current. The previous claim is still in the append-only export.

Both knowledge cutoffs are exact, timezone-aware timestamps, with the
earlier cutoff strictly before the later cutoff. The feature is an
experimental knowledge-history query, not a truth or causal-change engine.

## Scope and limitations

- Pure in-memory reference model, explicit JSON import/export only; not durable.
- No reconciliation/consensus, no estimated or simulated world, no forecast,
  no source-independence weighting and no asserted confidence score.
- No spatial operations, entity merge, fuzzy or uncertain dates, mutable
  database, authorization or concurrency/multi-writer contract.
- Required normative LOT-2 schemas and reviews have not been approved.
- Treat the fixture as invented synthetic examples, never real-world facts.
- Real source ingestion requires a separate reviewed privacy/security contract.

Rollback: close or revert this one isolated PR; it makes no changes to main,
database, credentials or existing accepted contracts.

## Inspect reported world-time history at fixed knowledge

Use `WorldMini.timeline(entity, attribute, from_at, to_at, known_at)` to
see the half-open periods in which a source report was current, **at one
fixed knowledge cutoff**. UNKNOWN gaps are explicit, and competing source
reports appear side-by-side without an estimated or simulated state. The
`WORLD_TIME_REPORTS_ONLY` marker means changes in a source's validity
assertions, **not verified physical changes**. Original evidence, event and
capture timestamps remain in each report. Input bounds require timezone-aware
ISO-8601 values and an increasing interval.

```sh
PYTHONPATH=src python3 -m monde.world \
  --fixture examples/monde-mini.json \
  --entity building-001 --attribute floors \
  --timeline-from 2026-01-01T00:00:00Z \
  --timeline-to 2026-02-01T00:00:00Z \
  --known-at 2026-01-07T00:00:00Z
```

This is an experimental LOT-2 reporting primitive: in-memory data and strict
source-reported validity only. It neither detects real-world events nor resolves
contradictions. The existing one-instant and knowledge-delta CLI modes remain
unchanged.


## Search across source reports without erasing disagreements

WorldMini.search_reports(attribute, value, at, known_at) finds entities for
which some source reported an exact JSON value at world-time T and knowledge
cutoff K. Results retain matched_reports plus other_reports, each with original
source and evidence lineage. It never asserts a reconciled real-world truth.
NO_MATCHES describes missing matching reports, not physical absence. JSON
booleans and numbers are distinct; objects compare by canonical JSON keys.

    PYTHONPATH=src python3 -m monde.world \
      --fixture examples/monde-mini.json \
      --search-attribute floors --equals-json 7 \
      --at 2026-01-02T00:00:00Z \
      --known-at 2026-01-07T00:00:00Z

The bundled fixture returns building-001 with a corrected seven-floor city
report and retains the competing six-floor local-news report. A subprocess
regression covers two buildings. Existing snapshot, timeline and knowledge
comparison modes stay separate. This is an in-memory discovery scan without
external services, source ranking or production data ingestion.


## Compare source-reported validity across world times

The new `WorldMini.compare_world_time(entity, from_at, to_at, known_at)`
compares **two valid-world instants using one fixed knowledge cutoff**.
It is the complement of `compare_knowledge`: the latter compares what
was known at K1 vs K2 at a single T. The output marker
`WORLD_TIME_REPORTS_ONLY` prevents a source's reported validity change
from being mistaken for a confirmed physical event. Newly active,
no-longer-active and still-current reports retain provenance; UNKNOWN is not
zero, and unchanged contradictory reports do not disappear.

```sh
PYTHONPATH=src python3 -m monde.world \
  --fixture examples/monde-mini.json \
  --entity building-001 --all-attributes \
  --compare-at 2025-12-31T00:00:00Z \
  --at 2026-01-02T00:00:00Z \
  --known-at 2026-01-07T00:00:00Z
```

The synthetic fixture transitions from no source report to competing floor
reports 6 and 7. This means **source-reported coverage at different T**, not
verified construction or demolition. Times must be offset-aware and ordered
strictly; the knowledge cutoff is held constant, and no real data ingestion
or persistent World Ledger is implied.

## Find cross-source disagreements without selecting a winner (T8)

WorldMini.source_disagreements(at, known_at, attribute=None) scans for distinct
source IDs reporting different JSON values on the same property and entity at
a world-time instant T and knowledge cutoff K. Each value group retains the
original evidence lineage and all reports. Multiple conflicting reports from
only one source ID are not treated as cross-source disagreement. Source IDs
do not establish statistical independence.

Command:

    PYTHONPATH=src python3 -m monde.world --fixture examples/monde-mini.json \
      --source-disagreements --at 2026-01-02T00:00:00Z \
      --known-at 2026-01-07T00:00:00Z

The synthetic fixture yields conflicting claims of six and seven floors with
both evidence IDs. This is source-report comparison, not physical-world truth,
causal inference, confidence calibration or source reputation. Empty results
do not prove agreement or missingness; cutoff limits are explicit.

## Source-oriented correction history (T9)

Use `WorldMini.source_history(source_id, known_at, entity=None, attribute=None)`
to inspect **all assertions a specific source had supplied by knowledge cutoff K**,
including assertions later corrected by that same source. Each report retains
its original source, evidence locator, event/capture time, validity interval,
knowledge time, and `supersedes` / `superseded_by` lineage. A correction is
marked `current_at_cutoff` only after its own knowledge time; this field
does **not** mean that the statement is valid now or that the world state is
true. There is no world-time `--at` filter: reported validity remains explicit
per report. Empty results mean **NO_REPORTS**, not physical absence.

```sh
PYTHONPATH=src python3 -m monde.world \\
  --fixture examples/monde-mini.json \\
  --source-history city-registry \\
  --known-at 2026-01-07T00:00:00Z
```

Optional `--entity building-001` and `--source-attribute floors` narrow the
source audit. The example reports the city's original 5-floor claim and its
7-floor correction, linked to their original captured evidence. At an earlier
knowledge cutoff, the correction remains invisible and the 5-floor statement
is still marked current *as a source assertion*. No source consensus,
reputation scoring, inferred events or new dependency is introduced.


## Track how sources became known (T10: knowledge-time timeline)

`WorldMini.knowledge_timeline(entity, attribute, at, from_known_at, to_known_at)`
holds **world-time T fixed** and divides an increasing **knowledge-time window**
into half-open intervals. Each segment contains the source reports available at
that cutoff, or explicit `UNKNOWN` before the first report. Source corrections
replace only that source's earlier assertion once known; conflicting sources
remain visible with evidence IDs, capture times, source locators and correction
lineage. This is a history of what MONDE *knew was reported*, not a history of
verified changes in the world.

```sh
PYTHONPATH=src python3 -m monde.world --fixture examples/monde-mini.json \
  --entity building-001 --attribute floors \
  --at 2026-01-02T00:00:00Z \
  --knowledge-timeline-from 2026-01-01T00:00:00Z \
  --known-at 2026-01-08T00:00:00Z
```

For the synthetic fixture the sequence is `UNKNOWN`, the city report of
5 floors, two competing reports (5 and 6), then city-corrected 7 alongside
the independent news report 6. The exclusive upper bound prevents a future
correction leaking into earlier segments. No real data ingestion, reconciliation,
source-quality weighting or event inference is introduced.


## Cross-entity knowledge arrivals (T11)

WorldMini.knowledge_updates(from_known_at, to_known_at, entity=None, attribute=None) lists newly known source assertions in the interval (K1, K2], including corrections. It preserves evidence, source ID/locator, original event/capture time, claimed validity, and supersedes lineage. It never labels report arrival as a physical-world change.

Run: PYTHONPATH=src python3 -m monde.world --fixture examples/monde-mini.json --knowledge-updates --updates-from 2026-01-03T10:00:00Z --known-at 2026-01-07T00:00:00Z

NO_NEW_REPORTS means no newly recorded assertions in that slice of the imported fixture, not no real-world changes. This audit is in-memory, not a lossless durable replication cursor; a later event carrying an already-polled timestamp may require overlap/re-reading.

## World-wide knowledge changes at fixed world time (T12)

Use the existing per-entity bitemporal report comparison across all entities.
Results preserve competing sources, original evidence and correction lineage.
A newly known report is never treated as a verified physical event.

```sh
PYTHONPATH=src python3 -m monde.world --fixture examples/monde-mini.json \
  --world-knowledge-changes --at 2026-01-02T00:00:00Z \
  --compare-known-at 2026-01-03T00:00:00Z --known-at 2026-01-07T00:00:00Z
```

Changed entities and attributes only; UNKNOWN is not zero, and this does not
implement persistent ingestion, a true event detector, or a reconciled belief.
