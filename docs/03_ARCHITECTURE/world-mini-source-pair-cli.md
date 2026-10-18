# MONDE Mini — offline original source-pair change report

Using a saved `WorldMini` evidence document, compare two original reporting
sources at a **fixed world-valid time** and two ordered knowledge cutoffs:

```bash
PYTHONPATH=src python3 -m monde.source_pair_changes \
  --fixture saved-world.json --source-a survey-a --source-b survey-b \
  --at 2026-01-05T00:00:00Z \
  --from-known-at 2026-01-03T12:00:00Z \
  --to-known-at 2026-01-05T12:00:00Z
```

The JSON output contains original GeoJSON features, entity/source/assertion/
evidence identifiers, earlier/later nearest and farthest approximate WGS84
cross-source Point distances, and signed later-minus-earlier differences in km.

A missing jointly reported period yields `null` for its distance and for the
period-to-period change; it never means the separation was zero. Superseded
source claims disappear from the later selected view but remain in the earlier
view. This report is **not** a verification of source reliability, true position,
physical motion, speed or a reconstruction of any path.

All computation is local, read-only, and dependency-free beyond MONDE Mini.
The tool does not write or rewrite its saved input and adds no remote API.
Candidate implementation is stacked on WORK-0091 / PR #122 until integration.
