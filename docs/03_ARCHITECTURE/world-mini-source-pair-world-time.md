# MONDE Mini — Original source-pair comparison over both temporal axes

The original `monde.source_pair_changes` CLI compares a source pair at a
**fixed world time** between two knowledge cutoffs (`--at`,
`--from-known-at`, `--to-known-at`), using `MONDE_SOURCE_PAIR_CHANGE_V1`.

## New: compare world-validity at fixed knowledge (WORK-0093)

```bash
PYTHONPATH=src python3 -m monde.source_pair_changes \
  --fixture saved-world.json --source-a survey-a --source-b survey-b \
  --from-at 2026-01-02T00:00:00Z --to-at 2026-01-05T00:00:00Z \
  --known-at 2026-01-07T00:00:00Z
```

The new `MONDE_SOURCE_PAIR_WORLD_CHANGE_V1` result retains each original
source/evidence/assertion ID and original GeoJSON geometry at both world
instants. It uses the **existing same source-pair distance calculation**.
Nearest/farthest kilometers and signed later-minus-earlier change are
approximate. If one source does not jointly report Points at either
instant, the corresponding separation and change are `null`, **never zero**.

Exactly one complete set of axis arguments is accepted. This is a
comparison of **source-reported validity**, not reliable ground truth,
physical movement, verified accuracy or speed. No stored-state writes,
new service, new dependencies or paid API are involved.


## Complete offline CSV (WORK-0094)

Use `--format csv` with **either** temporal comparison. For example:

```bash
PYTHONPATH=src python3 -m monde.source_pair_changes \
  --fixture saved-world.json --source-a survey-a --source-b survey-b \
  --from-at 2026-01-02T00:00:00Z --to-at 2026-01-05T00:00:00Z \
  --known-at 2026-01-07T00:00:00Z --format csv > source-pair.csv
```

The existing `--at/--from-known-at/--to-known-at` comparison also accepts
`--format csv`. Every entity in the comparison appears as an earlier and
later row, preserving the exact world and knowledge cutoffs. Each row carries
both original sources' full assertion IDs, evidence IDs and geographic
coordinates as JSON-array cells, along with counts, original-report status,
nearest/farthest approximate km and (on the later row only) the signed
difference when both periods are jointly reported.

`NOT_JOINTLY_REPORTED` has **blank numeric fields**, not invented zero
distances or implied movement. CSV escapes formula-leading entity/source
labels to avoid spreadsheet execution; it never modifies saved evidence.
Without `--format csv`, the existing JSON output and schemas are unchanged.
This is *reported source separation*, not verified location, source accuracy
or actual physical movement.

## Prioritize changes between original sources (WORK-0095)

To find the largest **changes in source-reported separation** rather than read every
entity, add `--top-nearest-changes N` (positive integer) to either comparison axis.

Example (knowledge changes at fixed world time):

```bash
PYTHONPATH=src python3 -m monde.source_pair_changes \
  --fixture saved-world.json --source-a survey-a --source-b survey-b \
  --at 2026-01-05T00:00:00Z \
  --from-known-at 2026-01-03T12:00:00Z \
  --to-known-at 2026-01-05T12:00:00Z \
  --top-nearest-changes 20 --format csv
```

The ordering is descending **absolute earlier-to-later nearest-distance change**
in approximate km (ties sorted by entity ID). Positive or negative changes
both count; this measures disagreement between *reported locations*, not
physical movement, truth, credibility or source accuracy. An entity not
jointly reported by both sources in **both** comparison periods is
**incomparable**, never assigned zero. The JSON `selection` block explains
the number eligible, omitted and returned. The existing CSV schema is
unchanged and preserves both periods' complete source assertion/evidence IDs
and original coordinates for every selected entity.

Without `--top-nearest-changes`, original JSON and CSV output are unchanged.
The operation reads the persisted WorldMini without modifying its bytes.
