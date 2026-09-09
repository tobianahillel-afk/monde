# MONDE Reproducibility & Backtesting Protocol

Status: Accepted  
Canonical: Yes  
Last Updated: 2026-09-10

## Purpose

MONDE must be able to prove not only that a model or detector performs now, but what it would have produced using only information actually available at an earlier time. Backtesting, replay and reproducibility are therefore first-class engineering and scientific requirements.

## Reproducibility manifest

Any material experiment, model evaluation, benchmark, detector backtest or forecast evaluation should record enough information to reproduce it:

- experiment/run ID;
- code commit SHA;
- configuration version/hash;
- dataset IDs and exact data versions/vintages;
- source/evidence cutoff time;
- model IDs/versions/artifact hashes;
- feature definitions/versions;
- environment/runtime versions;
- random seeds where meaningful;
- query/filter/cohort definition;
- metric definitions;
- baseline/comparator;
- output artifact/evidence location;
- known nondeterminism;
- operator/agent and timestamp.

## Temporal leakage rule

Historical evaluation must use **What MONDE knew at T**, not a modern reconstruction accidentally containing future information.

Forbidden leakage examples:

- using a revised statistic published after forecast time;
- using an entity merge discovered years later without replaying the identity state known then;
- using a later news article to label an earlier signal in the model input;
- using future satellite imagery in a historical feature;
- train/test records derived from the same duplicated source origin;
- computing normalization parameters on the full future dataset.

## Backtest types

### Forecast backtest

Evaluate probabilistic/numeric forecasts on historical cutoffs.

Required where applicable:
- rolling/expanding time windows;
- calibration;
- Brier/log score for probabilistic events;
- MAE/RMSE/quantile loss for numeric forecasts;
- coverage of prediction intervals;
- performance by horizon/domain/region/regime;
- baseline comparison.

### Detector backtest

For anomaly, opportunity, weak-signal, fraud/risk or event detectors:
- event-level precision/recall;
- false-positive burden;
- lead time before confirmed event;
- performance by source coverage;
- confidence calibration;
- duplicate-origin controls;
- negative-control cohorts.

### Entity-resolution backtest

Use labeled or high-confidence historical identity cases:
- pair precision/recall/F1;
- false merge rate;
- false split rate;
- calibration of match probability;
- difficult same-name cases;
- temporal identity changes;
- rollback/split correctness.

For critical identity systems, false merges may be more costly than false splits; acceptance thresholds must reflect that asymmetry.

### Source-reliability backtest

Evaluate source claims against later-established outcomes while respecting domain and temporal context.

Reliability should be estimated by topic/source class, not treated as one universal score.

### Causal-model validation

Causal claims require stronger validation than predictive correlation. Depending on claim class use:
- holdout predictions;
- natural/quasi-experimental checks;
- placebo tests;
- negative controls;
- sensitivity to unobserved confounding;
- intervention consistency;
- alternative causal graph comparison.

MONDE must label causal evidence level explicitly.

### Retrieval/research backtest

Evaluate whether research/acquisition planning finds the relevant evidence:
- recall of known decisive evidence;
- precision/relevance;
- source diversity;
- first-signal recovery;
- cost/latency;
- missed-evidence analysis.

### End-to-end historical replay

For selected historical episodes, reconstruct the system state chronologically:

`source arrivals → captures → claims/observations → identity → belief updates → alerts/forecasts → later outcomes`

This is the strongest regression test for MONDE's epistemic behavior.

## Backtest dataset policy

Maintain:

- development/training datasets;
- validation datasets;
- frozen holdout datasets;
- temporal out-of-sample periods;
- stress/adversarial sets;
- MONDE Mini synthetic semantic world;
- curated historical event packs.

Do not repeatedly tune on the final holdout until it becomes a disguised training set.

## Historical Event Packs

Create versioned event packs for important domains, for example:
- company expansion;
- bankruptcy/distress;
- supply shortage;
- infrastructure outage;
- major policy change;
- disease/health supply event;
- market regime shift;
- physical construction completion;
- misinformation propagation.

Each pack contains:
- event timeline;
- source arrival timeline;
- ground-truth confidence/limitations;
- relevant entities/relations;
- known precursor signals;
- misleading signals;
- expected system behaviors.

Packs support repeatable detector/research/forecast comparison across versions.

## Baseline hierarchy

A new method must beat or justify itself against appropriate simpler baselines, such as:

- last value / seasonal naive;
- simple rule/threshold;
- BM25/search baseline;
- deterministic identifier match;
- linear/logistic model;
- current promoted model;
- human/research workflow baseline where measurable.

Complexity without measurable benefit is not an improvement.

## Statistical rigor

Where material:
- report sample size;
- confidence intervals/bootstrap uncertainty;
- multiple-comparison controls when searching many hypotheses;
- effect size, not only significance;
- subgroup performance;
- class imbalance;
- sensitivity to threshold choice.

## Performance backtesting

Backtests also cover engineering behavior:
- p50/p95/p99 latency;
- throughput;
- CPU/GPU time;
- peak RAM/VRAM;
- I/O/network;
- storage growth;
- cost per processed unit;
- degradation under larger worlds.

Track these metrics across versions to detect performance regressions.

## Security regression/backtesting

Security-sensitive components maintain replayable adversarial cases:
- malicious/untrusted input;
- prompt injection through acquired content;
- malformed documents/archives;
- authorization boundary cases;
- SSRF/path traversal classes where applicable;
- tenant/cache scope leakage;
- secret/log leakage.

Previously fixed security defects become permanent regression cases when practical.

## Shadow and canary modes

Before replacing important promoted behavior:

1. run new version in offline backtests;
2. run shadow mode against live inputs without affecting canonical output;
3. compare disagreement/error/resource metrics;
4. use limited canary rollout when applicable;
5. promote only after gates pass;
6. retain rollback path.

## Prediction Ledger integration

Every material forecast stores:
- creation time;
- knowledge cutoff;
- target/outcome definition;
- forecast distribution;
- model/feature/data versions;
- later realized outcome;
- scoring result.

Predictions are never rewritten after the fact. Corrections create new predictions linked to previous versions.

## Failure analysis

A failed forecast/model/detector should be classified, not merely scored:
- missing evidence;
- delayed source;
- bad identity resolution;
- extraction error;
- stale feature;
- model misspecification;
- regime change;
- causal mechanism missing;
- label/ground-truth problem;
- random/irreducible uncertainty.

These failure classes feed World Scientist and the research backlog.

## Promotion rule

No model/detector/forecast method becomes canonical/promoted based only on anecdotal examples. Promotion requires:
- defined target metrics;
- baseline comparison;
- leakage-safe evaluation;
- robustness/subgroup checks;
- resource budget;
- reproducibility manifest;
- review by required roles;
- rollback/previous promoted version retained.

## Scientific memory

Negative results, regressions and rejected approaches should be stored when they prevent repeated mistakes. MONDE's scientific process must remember not only what worked, but what was tried, under which assumptions, and why it failed.