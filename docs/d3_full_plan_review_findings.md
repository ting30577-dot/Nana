# D3 full-plan first review findings

## Continuation audit addendum — F12

- Severity: P0; re-opened during the D3 continuation audit.
- Evidence: the historical F6 repair narrowed D3-07 to a harness-created
  allow-root and excluded user-selected external directories, while the
  authoritative vertical-slice checklist requires a user-selected
  Workspace-outside test directory for the T3 fixture.
- Codex decision: VETO treating the harness-only interpretation as final. A
  constrained launcher/native-picker selection-id design is only a candidate;
  Claude has not independently reviewed it.
- Repair: keep F07-10 recorded, keep export disabled, and require explicit
  Codex + Claude reconciliation before capability registration or filesystem
  writes.

Review sequence: Claude completed the full decomposition scan before any plan
repair. This file consolidates every finding before batch resolution.

## Findings

### F1 — R1-R4 evidence omitted from the review packet

- Severity: blocker.
- Claude: D3-00 cannot be reviewed without the actual R1-R4 decisions.
- Codex: ACCEPT. The packet summarized accepted outcomes but did not include the
  specific transaction, sparse-ID, fixture-contract, and export-gate content.
- Repair: add exact R1-R4 frozen contracts to D3-00 and the final review packet.

### F2 — alleged D3-01/D3-02 child-process circular dependency

- Severity: clarification required; not a factual blocker in current code.
- Claude: “real child crash recovery” in D3-01 might require the D3-02 runtime
  process, creating a cycle.
- Codex: VETO the factual premise. The existing D3-01 test launches a real
  child process that holds only the OS Workspace lock, then kills it and proves
  reacquisition. It does not instantiate HTTP/runtime authority.
- Repair: name this `real lock-owner process crash`. Move full authenticated
  runtime-process crash/readiness behavior explicitly to D3-02.

### F3 — alleged reconcile dependency on D3-05 Event/outbox introduction

- Severity: plan evidence/reference defect.
- Claude: D3-01 reconciliation cannot close if Event/outbox arrives in D3-05.
- Codex: VETO the factual premise that Event/outbox arrives in D3-05. D1 already
  implements Artifact reconciliation and Event/outbox; D2 handoff freezes those
  facts. However, ACCEPT that D3-00 must freeze the reused contract and D3-01
  must test the real D1 reconciler integration rather than a callback only.
- Repair: freeze current schema/Event/outbox/reconcile contracts in D3-00;
  require D3-01 real reconciler ordering/failure integration; D3-05 references,
  not introduces, the contract.

### F4 — Event/SSE semantics lack one frozen owner

- Severity: high.
- Claude: Event semantics are scattered across D3-02/03/04 and can drift.
- Codex: ACCEPT.
- Repair: D3-00 owns the semantic contract; D3-03 owns service/reducer tests;
  D3-04 owns real-browser Last-Event-ID/auth/reconnect tests. Every stage review
  checks consistency with D3-00.

### F5 — D3-08 is too broad for one no-edit review

- Severity: high.
- Claude: create/edit/run/cancel/approve/export/Receipt combines three security
  boundaries.
- Codex: ACCEPT.
- Repair: split into D3-08A core mutation UI and D3-08B authorization-sensitive
  Approval/export/Receipt UI.

### F6 — D3-07 controlled-local versus external export is ambiguous

- Severity: blocker for export enablement.
- Claude: prose does not form a machine-checkable boundary or identify gate
  signers.
- Codex: ACCEPT.
- Repair: define a harness-created allow-root outside canonical Workspace;
  exact resolved target must remain below it; reject reparse/symlink/unknown
  atomic-replace support; no arbitrary user path, remote publish, or fallback.
  Codex and Claude must both ACCEPT a D3-07 decision record before enabling the
  capability.

### F7 — schema migration ownership is missing

- Severity: high.
- Claude: no stage owns schema version/migration work.
- Codex: ACCEPT.
- Repair: D3-00 freezes current schema v6 and a migration rule: the earliest
  stage requiring a canonical schema change owns migration, rollback, read
  ceiling, round-trip, and generated-contract evidence. No stage may silently
  defer its schema change.

### F8 — sparse Last-Event-ID negative test ownership is unclear

- Severity: medium.
- Claude: reconnect semantics need an explicit stage.
- Codex: ACCEPT.
- Repair: D3-03 tests sparse/non-dense IDs in snapshot/stream/reducer; D3-04
  tests the same semantics through authenticated browser fetch.

### F9 — D3-01 candidate evidence is incomplete under the new protocol

- Severity: blocker for D3-01 exit.
- Claude: current 6 focused tests are insufficient evidence for the final plan.
- Codex: ACCEPT. The candidate has not undergone its formal no-edit full scan,
  consolidated repair, final re-review, or Claude exit review. It also uses a
  reconciliation callback rather than the real D1 reconciler.
- Repair: keep D3-01 reopened after D3-00 closes.

## Batch-repair rule

All F1-F9 are now recorded. Plan edits may begin only after this consolidated
list; each repaired item must be checked again in the final full-plan review.

## Final re-review findings

Claude completed the post-repair full scan before the following edits.

### F10 — R1 first-use stage is ambiguous

- Severity: blocker for D3-00 closure.
- Claude: D3-06 admission might imply one-time Approval before D3-07 proves the
  atomic decide/authorize/consume transaction.
- Codex: ACCEPT the ambiguity. D3-06's frozen T2 locked-test uses the frozen
  PolicyGrant admission path and does not request or consume a one-time
  Approval. R1's new combined Approval decision/authorization transaction is
  first implemented and proved in D3-07 for T3 export.
- Repair: freeze this mapping in D3-00 and D3-06/D3-07 boundaries.

### F11 — schema v6 and Workspace lock persistence are unclear

- Severity: blocker for D3-00 closure.
- Claude: if D3-01 persists lock state, it might need an earlier migration.
- Codex: ACCEPT the need for explicit evidence; VETO persisted lock ownership.
  Workspace authority is the OS-held handle. A SQLite/file marker row cannot be
  authoritative because it becomes stale after process death. Schema v6 already
  contains Event/outbox/Artifact reconciliation facts reused by D3-01; D3-01
  adds no canonical table and needs no migration.
- Repair: freeze “no persisted lock authority” and the existing schema inputs
  in D3-00/D3-01.
