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
