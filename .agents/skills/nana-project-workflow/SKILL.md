---
name: nana-project-workflow
description: Keep Nana work aligned with its product kernel and current execution state while minimizing context, review loops, and documentation. Use for every Nana planning, implementation, debugging, review, cleanup, release, handoff, Claude collaboration, UI, runtime, Tauri, migration, or architecture task in this repository.
---

# Nana project workflow

Keep every task on one product route, one active state, and proportional proof.
Never begin by scanning the complete repository, `docs/`, Obsidian export, or
external Vault.

## Bootstrap

1. Run `python scripts/nana_context.py check` from the repository root. Stop and
   resolve a reported authority/configuration error before changing product code.
2. Read `docs/PROJECT_KERNEL.md` completely.
3. Read `docs/ACTIVE_STATE.json` completely.
4. Choose exactly one route from `config/context-routes.json` and run
   `python scripts/nana_context.py bootstrap --route <route>`.
5. Read only the route files relevant to the concrete question. Expand scope
   only when a named missing fact cannot be resolved from them; state why.
6. Inspect `git status --short` before edits and preserve unrelated changes.

## Contract the task

Before implementation, state five items in working notes or commentary, not a
new repository document:

- user outcome;
- files or subsystem allowed to change;
- boundaries that must remain unchanged;
- acceptance evidence;
- review level.

Use `python scripts/nana_context.py review-level --paths <changed paths>` as the
default classifier. Read `references/review-and-retention.md` for review,
external-model collaboration, documentation, cleanup, or legacy retirement.

## Execute

1. Make the smallest coherent change that advances the selected user journey or
   removes a measured risk/friction.
2. Reuse adapters and mature tools; do not reproduce another platform inside
   Nana unless the kernel requires a differentiated canonical capability.
3. Keep Python as the only canonical business-data writer. Keep Rust inside the
   currently authorized shell/lifecycle boundary.
4. Add a regression test for every confirmed bug when practical. Do not add
   speculative tests for hypothetical implementations.
5. Run focused verification first. Run the full suite only for shared contracts,
   milestone gates, or changes whose impact is genuinely broad.
6. Do not create progress reports, scan diaries, review packets, or handoff files
   during ordinary work.

## Review

- R0: mechanical checks, no review document.
- R1: changed diff and adjacent contract, then at most one targeted re-review.
- R2: add independent security/data reasoning and fault injection for auth,
  path, external write, process, migration, schema, privacy, or security changes.
- R3: full matrix and real journey only at a milestone/release boundary.

Deduplicate findings by `path + contract + failure mode`. Persist only accepted
decisions, unresolved material risks, and regression tests. Escalate a P0/P1
that survives two cycles instead of continuing an unbounded AI review loop.

## Collaborate with another model

Generate the smallest route-specific pack. Strip absolute user paths and all
privacy-forbidden environment data. Ask the peer for an independent proposal or
review, exchange concrete objections, and record only the converged decision or
open disagreement. Do not preserve full prompts/responses or treat a peer model
as subordinate or authoritative.

Run `python scripts/nana_context.py privacy-scan --files <packet paths>` before
external disclosure. Treat any finding as a blocking failure; never print the
matched value while reporting it.

## Close out

1. Run the acceptance commands and `git diff --check`.
2. Run `python scripts/nana_context.py check` again.
3. Update `docs/ACTIVE_STATE.json` only if the current stage, gate, authority
   inputs, or next action changed. Never change `PROJECT_KERNEL.md` for routine
   implementation.
4. Put durable architecture changes in one ADR and confirmed bugs in tests.
5. Report outcome, evidence, remaining risk, and next gate. Do not claim more
   than the evidence proves.
