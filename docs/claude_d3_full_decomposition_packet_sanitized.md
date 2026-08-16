# Claude review packet — D3 full decomposition (sanitized)

This is a planning-only packet. It contains no usernames, absolute paths,
credentials, API keys, machine identifiers, or private runtime values.

## Current decisions

- D3-00 through D3-05: joint ACCEPT and recorded evidence.
- D3-06: local implementation evidence ACCEPT; Claude implementation-exit review unresolved because the configured gateway is unreachable.
- D3-07: fully decomposed but implementation VETO pending D3-06 joint exit and a joint 07-00 gate.
- F07-10: P0 scope conflict. Authority requires a user-selected Workspace-outside test directory for the T3 fixture; the current draft allows only a harness-created allow-root.

Codex's independent reconciliation proposes an opaque launcher/native-picker
selection id (not a browser path), server-side re-resolution, and ActionHash
binding. This is a candidate only; it is recorded in
`docs/codex_f07_10_scope_reconciliation.md`.

The typed Approval request/decision/consumption design is in
`docs/codex_d3_07_approval_contract_design.md`; it is also design-only.

## Proposed later stages

- D3-08A: typed core mutation UI, state-guarded start/cancel, projection reconciliation, negative-state/accessibility E2E.
- D3-08B: canonical Approval/Receipt/effect_unknown UI, typed one-time decision, export-target safety review, no optimistic success.
- D3-09: ten clean runs, crash/reconnect/cancel/export matrix, evidence-index/manifest synchronization, full scan, final joint review.

## Review questions

1. Is the stage order and boundary complete for a narrow D2-fact-consuming vertical slice?
2. Does F07-10 require changing the target resolver, or can “user-selected” be safely implemented as a constrained chooser rooted outside canonical Workspace?
3. Which invariants or failure cases are missing before implementation may be ACCEPTed?

Return independent evidence, risks, rebuttals, and an explicit ACCEPT, VETO, or
尚未达成共识 for each unresolved gate. Do not edit files.
