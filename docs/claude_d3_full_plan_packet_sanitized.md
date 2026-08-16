# Nana D3 full decomposition review packet (sanitized)

This packet asks Claude to review the complete D3 phase division before further
implementation. It contains no credentials, environment values, absolute user
paths, machine identity, private network information, or hardware identifiers.

## Already accepted global decisions

- Workspace lock precedes writable SQLite; reconciliation precedes ready;
  SQLite/WAL closes before lock release; second instance fails closed.
- Frozen D0 app is not physically mounted into runtime.
- One new authenticated runtime factory is the only HTTP/OpenAPI authority.
- Canonical query/SSE/mutation before reconciliation-ready is VETO.
- D3/UI authorization re-derivation and D2 execution bypass are VETO.
- Browser uses authenticated fetch + ReadableStream; Event IDs are stable,
  strictly increasing but not dense.
- Offline replay is a shared reducer data adapter, not a second HTTP contract.
- Approval decision/authorization consumption is owned by one D2 admission
  transaction.
- External T3 export remains disabled until atomic-replace fallback and the
  separate security gate are explicitly accepted.

## Mandatory per-stage review sequence

Entry check → candidate implementation → complete no-edit scan → consolidated
F-number findings → batch red-test/repair → complete final re-review → focused
and full evidence closure → Claude exit review. Passing implementation tests is
not stage completion.

## Proposed complete stages

1. **D3-00 design/decomposition:** freeze journey, architecture, review protocol,
   R1/R2/R3 decisions, and R4 gate.
2. **D3-01 Workspace lifecycle:** OS lock, lock-before-write, reconcile-before-
   ready, second instance, close-before-unlock, startup/close failure, real
   child crash recovery.
3. **D3-02 runtime authority/readiness:** Workspace-owned authenticated factory,
   startup states, exact public routes, default-deny, exact Origin preflight,
   not-ready gate, runtime OpenAPI/client regeneration, no mutation.
4. **D3-03 read models/snapshot/reducer:** full journey projections, same-read-
   transaction high water, sparse-ID reducer, replay adapter, fixture/runtime
   projection equivalence, no second client.
5. **D3-04 read-only React/SSE:** industrial/editorial Cockpit+Studio,
   causality rail, authenticated browser stream, reconnect/refresh, negative
   states, keyboard/DPI, fixture excluded from production.
6. **D3-05 canonical journey writers:** typed idempotent fixture/provenance,
   Plan, Finding commands with revisions, Event/outbox/result in one transaction,
   no raw Action/policy input.
7. **D3-06 locked test orchestration:** typed start/cancel, exact frozen test,
   D2 admission→scheduler→executor/budget/Receipt, Artifact/Finding, all negative
   terminal states and crash recovery.
8. **D3-07 Approval/T3 export:** first close R4 decision; then D2-owned atomic
   Approval/authorization transaction, exact controlled target, supported
   atomic replace only, uncertainty→effect_unknown, separate security matrix.
9. **D3-08 integrated mutation UI:** create/edit/run/cancel/approve/export/
   Receipt interactions reconciled through canonical Events, keyboard and DPI,
   no unknown-effect shortcuts.
10. **D3-09 final gate:** ten consecutive no-retry real-browser journeys,
    negative/reload/crash/second-instance/accessibility matrix, full tests,
    manifest, authoritative sync, Codex full scan/repair/re-review, Claude exit.

## Scope boundaries

No alpha.1 research work, generic hostile-code sandbox, arbitrary shell/Python,
remote publish, final Decision, Tauri, or Local Web production bootstrap gate is
included. D3 must still finish controlled local T3 draft export because it is
part of the dev journey.

## Current state

D3-01 has candidate code and 6 focused strict-warning tests, but it is reopened
for the newly mandated full scan/list-all/findings/batch-repair/final-review
protocol. No D3 mutation route or external export is enabled.

## Review request

Please review the entire decomposition independently. Check for missing
dependencies, circular ordering, scope leakage, insufficient exit evidence, or
stages that are too broad to review correctly. For each stage and the overall
order, return ACCEPT, VETO, or NOT CONSENSUS with counterexamples. Suggest
specific changes before implementation continues. Do not claim local test
execution or repository edits.
