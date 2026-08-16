# Nana D3 full-plan resolution packet (sanitized)

This packet contains the complete post-scan resolution of Claude's first
full-plan review. It contains no credentials, literal authorization values,
environment values, absolute user paths, machine identity, private network
information, or hardware identifiers.

## Review protocol followed

Claude completed the entire first scan before the plan was edited. Findings
F1-F9 were then consolidated. Repairs below were applied as one batch. This is
the requested final re-review; any new material finding reopens D3-00.

## Frozen R1-R4 decisions now included

- **R1:** Approval decision, Action authorization, authorization Event/outbox,
  durable authorization material, Approval consumption, and stable command
  result commit in one D2 admission-owned transaction. Two-transaction
  decide→consume is VETO.
- **R2:** delivered committed Event IDs are stable and strictly increasing but
  not dense. Integer holes are legal. Duplicate IDs are idempotent; decreasing
  new IDs fail closed. Snapshot high-water is read in the same SQLite read
  transaction.
- **R3:** one authenticated runtime HTTP/OpenAPI authority. Offline fixture is a
  build/test data adapter for the same generated types and pure reducer, never a
  second server/client/route/auth mode or production navigation entry.
- **R4:** export transaction/idempotency/effect_unknown skeleton is accepted;
  actual external write remains disabled until D3-07 jointly accepts atomic-
  replace behavior and a machine-checkable security gate.

## F1-F9 resolution

1. F1: R1-R4 are now explicit above and in D3-00 deliverables.
2. F2: D3-01's current real child is only an OS lock-owner process; it proves
   crash release without HTTP runtime. Full authenticated runtime-process
   crash/start/restart moved explicitly to D3-02. No cycle remains.
3. F3: D1 already supplies Artifact reconciliation and Event/outbox; D2 handoff
   freezes them. D3-00 now owns that input contract. D3-01 must integrate the
   real D1 reconciler before ready; D3-05 references rather than introduces it.
4. F4: D3-00 is the sole Event/replay semantic owner. D3-03 proves service and
   reducer behavior; D3-04 repeats it through authenticated browser fetch. Each
   stage review checks the D3-00 reference.
5. F5: old D3-08 split into D3-08A core create/edit/run/cancel/Artifact/Finding
   UI and D3-08B authorization-sensitive Approval/export/Receipt UI.
6. F6: D3-07 export is machine-bounded to a harness-created resolved allow-root
   outside canonical Workspace. Exact target must be a regular non-reparse
   child with frozen filename, media type, and size ceiling. Atomic-replace
   support is positively probed before authorization; unsupported means deny
   before write; after write starts, unverifiable crash means effect_unknown;
   non-atomic fallback is VETO. No arbitrary directory or remote publish.
   Enabling requires both Codex and Claude ACCEPT in D3-07 decision record.
7. F7: schema v6 is frozen input. The earliest stage needing a schema change
   owns migration, rollback, read ceiling, old→new round-trip, contract/registry
   stability, and generated-client evidence in that stage.
8. F8: D3-03 service/reducer and D3-04 real browser each own explicit sparse
   Last-Event-ID/duplicate/decreasing/reconnect tests. Integer continuity is
   never a gap oracle.
9. F9: D3-01 remains reopened. Its candidate callback and six tests are not
   exit evidence until formal no-edit scan, real D1 reconciler integration,
   batch repair, final re-review, strict/full tests, evidence closure, and
   Claude exit review.

## Final stage order

1. D3-00 design, R contracts, schema/event/review ownership.
2. D3-01 Workspace lock lifecycle plus real D1 reconciliation before ready and
   real lock-owner process crash recovery.
3. D3-02 sole authenticated runtime authority, readiness/default-deny/exact
   Origin/OpenAPI, plus real runtime-process crash/restart; no mutations.
4. D3-03 complete journey read models, consistent snapshot, Event service and
   pure reducer, offline adapter equivalence.
5. D3-04 read-only React Cockpit/Studio plus authenticated browser stream,
   reconnect, negative states, keyboard/DPI.
6. D3-05 typed idempotent provenance/Plan/Finding writers, with any required
   schema migration owned here; execution disabled.
7. D3-06 typed locked-test start/cancel using D2 admission→scheduler→executor/
   budget/Receipt, Artifact/Finding, failure/cancel/orphan/recovery.
8. D3-07 joint R4 gate, atomic Approval/authorization transaction, controlled
   export capability/security matrix.
9. D3-08A core mutation UI.
10. D3-08B Approval/export/Receipt UI.
11. D3-09 ten consecutive no-retry real-browser journeys, full evidence,
    authoritative sync, Codex final scan/repair/re-review, Claude exit.

## Scope remains fixed

No alpha.1 research, hostile-code sandbox, arbitrary shell/Python, arbitrary
external directory, remote publish, final Decision, Tauri, or production Local
Web bootstrap gate. Controlled local T3 export remains required for D3 exit but
cannot be enabled before D3-07 joint ACCEPT.

## Final review requested

Please re-scan every prior F1-F9 finding against this repaired plan, then scan
the complete dependency order once more for new omissions or cycles. For each
stage and the overall order return ACCEPT, VETO, or NOT CONSENSUS. If accepted,
state whether D3-00 may close and D3-01 formal review may begin. Do not claim
local test execution or repository edits.
