# Scope and review freshness

Status: Accepted  
Canonical: Yes

After a work item reaches READY, substantive changes to purpose, scope, acceptance-criterion meaning, requirements, assumptions, risks, assurance, dependencies, contracts, impact, required tests or rollback semantics require an explicit approved `scope_change` rationale.

A completed review is fresh only for the substantive content it examined. Later changes to implementation, workflows, schemas or semantic work-item content invalidate it. Administrative finalization—review/test records, progress/project-state synchronization, completion booleans and acceptance-criterion status changes that do not change criterion identity/meaning—does not invalidate an otherwise fresh review.

State-transition validation follows the actual ordered commit sequence of the pull request, not merely the base and head endpoints.
