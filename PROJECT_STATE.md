# MONDE — Project State

Status: Accepted  
Canonical operational state: Yes

> Fast resume point. Durable intent lives in Git. Live PR/check/thread truth is volatile and must be re-queried before review or merge decisions.

## Current phase / lot

- **PHASE-0 — Specification and repository governance** is `IN_PROGRESS`.
- **LOT-0 — AI-first repository operating system** is `IN_PROGRESS`.
- **SUBLOT-0.1 / WORK-0001** is `DONE / A3` and was squash-merged to `main` as `29086643387ff46ab6636dd2fa3014efccc10165`.
- **SUBLOT-0.2 / WORK-0002** is the active `IN_REVIEW / A3` work on PR #2 / `feat/work-0002-governance-ci`.
- WORK-0003 and WORK-0004 remain planned downstream work.

## Exact WORK-0002 resume checkpoint

The current PR #2 branch checkpoint before this handover synchronization is
`0d4569b47e7e57f9141b95558bc4ae2c55124051`.

That commit is the final metadata-only consumption step for REVIEW-0030. REVIEW-0030 itself reviewed exact substantive candidate
`cbc2dfc065e73b9086d13a483b8b693ddc2fa6cc`, completed externally with `CHANGES_REQUIRED`, and was truthfully handled through the
v10 one-shot import protocol:

1. authorization commit `1c7693b4a6ee7b003947599b0bf5ffefd444bcbd`;
2. review materialization/import commit `630604416bdccd3b07f57c011152e7fe14e0f2b4`;
3. metadata binding commit `788ade473e8c8c58604c019db7f0072322eb4074`;
4. authorization-consumption commit `0d4569b47e7e57f9141b95558bc4ae2c55124051`.

The import sequence is historical evidence only. It does not mean WORK-0002 is corrected or approved.

## Current independent-review closure set

PR #2 has **18 unresolved material review threads/findings**. None may be author-resolved.

The first six open findings require:

1. A3/A4 assurance to impose minimum review independence (`A3 ≥ L2`, `A4 ≥ L3`).
2. COMPLETE review evidence to bind an exact `artifact.commit_sha`.
3. PASS TEST records to carry substantive protected-contract/case/execution evidence.
4. Every `NOT_APPLICABLE` progress dimension to carry a non-empty justification.
5. Context routing to seed dependency closure from changed non-WORK registry records.
6. Handover state to remain current and transition-stable.

REVIEW-0029 added six further findings requiring:

1. lifecycle validation to enforce canonical initial-state materialization while allowing only exact, record/commit-bound historical or preauthorized imports;
2. requirement `PROPOSED → ACCEPTED` transitions to enforce content-bound independent-review and cold-read preconditions;
3. every current `PASS` TEST used as completion evidence to carry concrete revision-bound execution evidence;
4. blocking finding `ACCEPTED` disposition to resolve the exact authority matrix role/rule/evidence contract;
5. COMPLETE review artifact evidence to use a full immutable existing commit object ID valid for ancestry/freshness checks;
6. freshness/change-control to keep required TEST contract changes substantive and use PR merge-base semantics for endpoint scope.

REVIEW-0030 added six new `R2_MAJOR` findings against `cbc2dfc065e73b9086d13a483b8b693ddc2fa6cc`:

1. `RISK → ACCEPTED` validates adjacency but not the full canonical acceptance preconditions and authority resolution.
2. Requirement acceptance repeats a syntactically valid digest but does not recompute `REQUIREMENT_NORMATIVE_V1` from canonical RFC 8785/JCS bytes.
3. `GITHUB_REPOSITORY_OWNER_PERMISSION` can be spoofed with an unrelated GitHub repository URL rather than proving authority over `tobianahillel-afk/monde`.
4. A preauthorized imported COMPLETE review can become completion evidence before `external_import.import_commit` and authorization consumption are finalized.
5. A PASS TEST may cite a fabricated 40-hex `execution.commit_sha` because existence/relevant ancestry is not checked.
6. A `CLOSED` review with an approving outcome can incorrectly contribute completion roles/independence despite the canonical lifecycle forbidding it.

## Additional resume-audit defect

While reconstructing the exact corrective context, the resume audit found that `registry/work-items/WORK-0004.yaml` currently contains duplicate
top-level `progress_justifications` keys. The current loader uses ordinary PyYAML mapping behavior, so duplicate keys can silently overwrite earlier
canonical state.

WORK-0002 therefore also owns a narrow parser-hardening correction: canonical machine-readable YAML must fail closed on duplicate mapping keys, with
a regression test, and the existing WORK-0004 duplicate must be repaired. This is governance hardening, not MONDE product scope expansion.

## Corrective contract decisions

- **Risk owning work:** the canonical matrix requires an `owning-work assurance` value. If a risk acceptance cannot resolve exactly one owning WORK
  and its assurance level from canonical scope, acceptance fails closed. No first-item or implicit-max heuristic is allowed.
- **Repository owner evidence:** the existing TEST-0007 precedent is authoritative for implementation. `GITHUB_REPOSITORY_OWNER_PERMISSION` must
  be bound to the governed repository `tobianahillel-afk/monde` and establish that the named accepting actor is that repository owner/administrator;
  an arbitrary repository-shaped URL is insufficient.
- **Requirement digest:** acceptance must recompute the configured `REQUIREMENT_NORMATIVE_V1` projection and hash exact RFC 8785/JCS UTF-8 bytes.
- **PASS TEST revision:** the SHA must be a real Git commit reachable in the relevant governed history, except only exact canonical historical/import
  exceptions already recorded in `registry/status-machines.yaml`.
- **Imported review completion:** external COMPLETE review evidence is not completion-eligible until import binding and one-shot authorization
  consumption are both finalized.

## Current WORK-0002 gate

Required sequence from this handover state:

1. Correct REVIEW-0030/F-1..F-6 plus the duplicate-key YAML parser defect using the smallest responsible validators/contracts.
2. Add dedicated regression tests and mutation targets for every corrected property.
3. Keep all 18 existing review threads unresolved during author-side correction.
4. Run the full deterministic A3 proof on the exact corrective SHA: pytest with 100% line+branch coverage, mutation smoke, repository validator,
   strict contracts, path safety, change guard, context manifest, CodeQL and Dependency Review.
5. Obtain a complete pull-request MONDE Gate on the exact non-bot transition-stable candidate. A workflow with no jobs is never proof.
6. Obtain a **fresh-context L2** on that exact final candidate. The reviewer must inspect all 18 open findings and the new parser-hardening change.
7. Only an approval-capable independent result with no new blocking finding may justify durable review evidence and thread/finding closure.
8. Synchronize WORK-0002 completion only after those independent gates pass, then run the final exact-head merge candidate gate.
9. Continue with WORK-0003, then WORK-0004.

## WORK-0001 provenance boundary

WORK-0001 final closure remains canonical on `main`: REVIEW-0028 independently verified its substantive final-v10 candidate; all historical
WORK-0001 findings/threads were independently closed before squash merge. PR #2 consumes that merged contract and must not recreate or rewrite it.

## Repository visibility

MONDE intentionally remains **public**. Never commit credentials, tokens, secrets, private/personal datasets or user-identifying runtime data.
Sensitive runtime material remains outside Git. WORK-0003 owns repository/ruleset/required-check/security-setting hardening while preserving public
visibility.

## Product/UI/UX owner gate

Product specification and product identity remain owner-gated decisions. Agents must not silently canonize product experience, UI/UX, visual
identity, brand, color system, interface density, interaction language, emotional/psychovisual tone or other strong design choices. Major
product-function decisions require explicit owner co-design rather than irreversible invention.

## Resume sequence

1. `README.md`
2. `AGENTS.md`
3. `docs/00_START_HERE.md`
4. this file
5. `registry/work-items/WORK-0002.yaml`
6. `registry/progress/matrix.yaml`
7. `registry/status-machines.yaml`
8. `registry/acceptance-authority.yaml`
9. `registry/content-identity.yaml`
10. `registry/reviews/REVIEW-0029.yaml`
11. `registry/reviews/REVIEW-0030.yaml`
12. `registry/tests/TEST-0002.yaml`, `TEST-0003.yaml`, and `TEST-0007.yaml`
13. live PR #2 HEAD, checks, reviews and all review threads
14. `tools/governance/` and `tests/governance/`

No prior chat history is required.
