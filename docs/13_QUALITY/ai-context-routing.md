# AI Context Routing

Status: Accepted  
Canonical: Yes

MONDE agents must receive the smallest sufficient context, not the entire repository by default and not an arbitrary subset chosen from memory.

## Context manifest

For an active `WORK-*`, the context router produces three tiers:

- `MUST_READ`: README, AGENTS, START_HERE, PROJECT_STATE, active work item and its declared `read_before` dependencies.
- `SHOULD_READ`: directly affected documentation and changed implementation/configuration files.
- `ON_DEMAND`: schemas and wider dependencies that become necessary only when the task expands.

The manifest records base/head SHAs, active work IDs, assurance levels, changed files and an estimated context budget.

## Budget tiers

T0 is a minimal resume pack (target roughly <=5k tokens), T1 a normal implementation/review pack (roughly <=20k), and T2 a cross-domain expansion. Agents escalate context only when evidence says the narrower pack is insufficient.

## Live state

Repository context is not enough for merge decisions. Before review/merge, agents also inspect live GitHub state: exact HEAD, PR draft/open state, check conclusions, unresolved review threads and mergeability.

## Anti-omission rule

Context routing must be dependency-driven. If a modified contract has downstream users, those dependency records and tests enter the context even if they were outside the initial token budget. Token economy must never silently remove a critical dependency.

## Cold-start criterion

A fresh agent with no chat history must be able to resume by reading the generated context pack and live PR state. If it must reconstruct essential state from conversation history, the repository/context routing is incomplete.
