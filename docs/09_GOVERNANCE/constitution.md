# MONDE Constitution

Status: Accepted  
Canonical: Yes  
Authority: Highest repository-level product/engineering invariants unless explicitly superseded through a reviewed constitutional ADR.

## Purpose

The Constitution defines rules that implementation convenience must not silently violate.

## Epistemic invariants

1. **Nothing untrusted becomes truth directly.**
2. **Nothing inferred becomes observed.**
3. **Observation, Claim, Evidence and EstimatedState are distinct concepts.**
4. **Observed World, Estimated World and Simulated World remain distinct.**
5. **No important published assertion exists without provenance.**
6. **No fact without source.**
7. **No fact without time.**
8. **No state without validity semantics.**
9. **No inference without confidence/uncertainty.**
10. **No history overwritten.** Corrections and revisions create new states/versions.
11. **Original source/event timestamps are never replaced by ingestion timestamps.**
12. **Unknown is not zero.** Missingness semantics are explicit.
13. **Temporal and spatial precision are never fabricated.**
14. **Entity resolution is probabilistic where identity is not certain.**
15. **Entity merges are reversible assertions, not destructive rewrites.**

## Evidence and lineage invariants

16. Every derived important result must retain lineage: `source → extraction → claim/observation → entity/feature → model → result`.
17. Source independence must be modeled; copies of one origin are not independent corroboration.
18. Source captures are content-addressed or otherwise integrity-verifiable where feasible.
19. Revision/data-vintage semantics must be retained for mutable datasets.
20. MONDE outputs must not be re-ingested as independent external evidence without ancestry detection.

## Temporal invariants

21. MONDE must distinguish **World at T** from **What MONDE knew at T**.
22. Forecast evaluation must use the knowledge cutoff that existed when the forecast was made.
23. Relations and identities that change over time carry validity intervals/history.
24. `first_seen` is not silently treated as `published_time`.
25. Estimated times retain precision and uncertainty.

## Architecture invariants

26. One logical World Model; projections/serving stores must not create competing truths.
27. World Graph overlays may represent identity, evidence, time, geography, state, causality, forecasts and scenarios without duplicating canonical entities.
28. Critical state is recoverable from durable canonical stores/ledger/registries.
29. Nothing critical exists only in a disposable derived database/cache.
30. Serving/publishing must expose coherent world generations; partial updates must not appear as coherent truth.
31. At-least-once processing requires idempotency/deduplication.
32. Expensive recomputation must be impact-scoped rather than global by default.

## Engineering invariants

33. Existing primitives/components are reused before new equivalents are created.
34. Every implementation effort belongs to a tracked work item.
35. Every work item declares dependencies, reuse, contracts, tests and acceptance criteria.
36. Every meaningful change is reviewable and auditable through version control.
37. Critical behavior is reproducible from code/config/data-version declarations.
38. Nothing expensive runs without an explicit or inherited resource budget.
39. Observability is part of implementation, not an optional postscript.
40. Documentation and registries change with behavior; stale canonical docs are defects.

## Quality invariants

41. Passing compilation is not Definition of Done.
42. Project-owned executable code targets 100% meaningful line and branch coverage unless a reviewed exception exists.
43. Integration behavior must not be proven only by mocks when a safe real-system test is practical.
44. Regression coverage accompanies bug fixes.
45. Security-sensitive changes receive security review and adversarial validation appropriate to risk.
46. Performance-sensitive paths have resource/latency expectations and tests or benchmarks.
47. Tests must validate failure modes, not merely happy paths.

## Product invariants

48. Console and Globe are experiences over the same World Model and preserve shared context where applicable.
49. Important scores expose drivers, evidence, counter-evidence, uncertainty and model/version context.
50. MONDE must be able to say `UNKNOWN` and show what evidence could reduce uncertainty.
51. New capabilities should compose existing engines/primitives rather than become disconnected mini-products.
52. Exploration, forecasting, scenarios and decisions must be explainable back to world state and evidence.

## Change process

A proposal that intentionally violates or changes a constitutional invariant must:

1. open a dedicated ADR;
2. name the exact invariant(s) affected;
3. explain why the old invariant is insufficient;
4. document migration and compatibility impact;
5. include risk analysis and tests;
6. receive explicit review before merge;
7. update this document and all impacted registries in the same change set.

Silently working around an invariant is prohibited.
