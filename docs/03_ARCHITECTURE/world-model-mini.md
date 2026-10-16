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
