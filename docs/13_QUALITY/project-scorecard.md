# MONDE Repository & Engineering Scorecard

Status: Accepted  
Canonical: Yes

## Purpose

MONDE should be assessable against an explicit engineering-quality standard rather than vague claims such as "well organized" or "production ready".

The target is **100/100** before MONDE claims a mature production-grade engineering process. Early phases are expected to score lower; gaps must be visible and tracked.

## Scoring

50 criteria × 2 points = 100 points.

For each criterion:

- `0` — absent / not demonstrated;
- `1` — partially defined or inconsistently enforced;
- `2` — defined, implemented/enforced where applicable and evidenced.

`N/A` is allowed only when the phase genuinely cannot exercise the criterion; N/A criteria are excluded from the maturity score but must include a rationale. Do not use N/A to hide debt.

## A. Repository orientation & resumability — 10 points

| # | Criterion | Target evidence | Bootstrap state |
|---|---|---|---|
| 1 | Product purpose immediately clear | `README.md` | 2 |
| 2 | Canonical start/read order | `docs/00_START_HERE.md` | 2 |
| 3 | AI contributor protocol | `AGENTS.md` | 2 |
| 4 | Current project state is explicit | `PROJECT_STATE.md` | 2 |
| 5 | New agent can resume without chat history | resume drill / work item | 1 |

## B. Planning, traceability & scope control — 12 points

| # | Criterion | Target evidence | Bootstrap state |
|---|---|---|---|
| 6 | Phase/lot/sublot/work hierarchy | development process | 2 |
| 7 | Machine-readable work items | registry template | 2 |
| 8 | Acceptance criteria tracked | work items | 2 |
| 9 | Tasks/runs decomposed before implementation | work items | 2 |
| 10 | Scope in/out explicit | work items/PR | 2 |
| 11 | Follow-up work separated from scope creep | process + work items | 2 |

## C. Dependencies, reuse & architecture — 12 points

| # | Criterion | Target evidence | Bootstrap state |
|---|---|---|---|
| 12 | Dependencies explicitly tracked | dependency registry | 1 |
| 13 | Reuse-first rule enforced | AGENTS/PR review | 1 |
| 14 | Duplicate component detection/review | repo search + review gate | 1 |
| 15 | Canonical architecture documentation structure | documentation architecture | 2 |
| 16 | Significant decisions captured as ADRs | ADR process + actual ADRs | 1 |
| 17 | Stable capability IDs/registry | capability template + populated registry | 1 |

## D. Documentation integrity — 10 points

| # | Criterion | Target evidence | Bootstrap state |
|---|---|---|---|
| 18 | Canonical vs draft docs distinguishable | status/front matter | 1 |
| 19 | Documentation precedence defined | START_HERE | 2 |
| 20 | Docs updated with behavior | DoD/PR gate | 1 |
| 21 | Broken/orphan references checked automatically | CI validator | 0 |
| 22 | Historical decisions preserved | Git + ADR supersession | 1 |

## E. Testing & correctness — 16 points

| # | Criterion | Target evidence | Bootstrap state |
|---|---|---|---|
| 23 | Unit-test strategy | testing strategy | 1 |
| 24 | Property/invariant testing | testing strategy | 1 |
| 25 | Contract/schema testing | testing strategy | 1 |
| 26 | Integration testing with real dependencies | testing strategy + CI | 1 |
| 27 | End-to-end testing | testing strategy + suites | 1 |
| 28 | Regression test requirement | bug workflow | 1 |
| 29 | 100% meaningful line/branch coverage gate | coverage tooling/CI | 1 |
| 30 | Golden-world semantic regression suite | MONDE Mini implementation | 0 |

## F. Real-world validation — 8 points

| # | Criterion | Target evidence | Bootstrap state |
|---|---|---|---|
| 31 | Browser behavior tested in real browser | E2E CI | 0 |
| 32 | APIs/connectors validated on real/sandbox endpoints where possible | live contract jobs | 0 |
| 33 | Databases/brokers/storage tested using supported real engines | integration CI | 0 |
| 34 | Representative real files/data formats used | fixture policy/datasets | 0 |

## G. Security engineering — 12 points

| # | Criterion | Target evidence | Bootstrap state |
|---|---|---|---|
| 35 | Secret-handling policy | development rules | 1 |
| 36 | Untrusted-input/trust-boundary policy | Constitution/dev rules | 2 |
| 37 | Authn/authz/tenant test policy | testing/dev rules | 1 |
| 38 | Dependency/secret/static scanning gates | CI | 0 |
| 39 | High-risk changes trigger adversarial review | AGENTS/process | 1 |
| 40 | Risky acquisition/document/browser isolation designed | development rules | 1 |

## H. Reliability, performance & observability — 12 points

| # | Criterion | Target evidence | Bootstrap state |
|---|---|---|---|
| 41 | Timeout/retry/idempotency rules | development rules | 1 |
| 42 | Resource budgets/performance tests | Constitution/testing | 1 |
| 43 | Load/soak/failure-injection strategy | testing strategy | 1 |
| 44 | Logs/metrics/traces requirements | development rules/DoD | 1 |
| 45 | Recovery/rollback requirement | work item/PR/DoD | 1 |
| 46 | No unbounded world-in-memory architecture | Constitution/dev rules | 2 |

## I. Data & epistemic quality — 8 points

| # | Criterion | Target evidence | Bootstrap state |
|---|---|---|---|
| 47 | Provenance/time/uncertainty invariants | Constitution | 2 |
| 48 | Observed/Estimated/Simulated separation | Constitution | 2 |
| 49 | Reversible identity/history semantics | Constitution | 2 |
| 50 | Epistemic invariants enforced by executable tests | invariant CI/MONDE Mini | 0 |

## Bootstrap score

Current provisional score from documented/evidenced bootstrap state:

- Orientation: 9/10
- Planning: 12/12
- Dependencies/architecture: 7/12
- Documentation: 5/10
- Testing: 7/16
- Real-world validation: 0/8
- Security: 6/12
- Reliability/performance/observability: 7/12
- Data/epistemics: 6/8

**Provisional total: 59/100**

This score is intentionally conservative: policy text receives only partial credit where automated enforcement or implementation does not yet exist.

## Rules for claiming 100/100

MONDE may claim 100/100 only when every applicable criterion has verifiable repository evidence. Documentation alone is not sufficient for criteria that require automation, implementation or real-system validation.

The scorecard itself must be reviewed at each major phase boundary; criteria may be made stricter as MONDE matures, but should not be weakened merely to improve the score.
