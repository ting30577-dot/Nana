# ADR-004: Separate commands, actions, events, grants, approvals, and receipts

- Status: accepted
- Date: 2026-07-29
- Milestone: v0.3.0-dev

## Decision

- Command expresses a requested canonical state change and carries an
  idempotency key, actor, and expected revision.
- Action is one concrete capability invocation with a frozen action hash.
- Event is append-only evidence of committed state.
- PolicyGrant pre-authorizes a constrained class of actions.
- Approval binds one subject hash.
- ActionReceipt records the actual effect and authorization source.

These records are not interchangeable. Content changes invalidate approval.
Final Decision, publish, and delete cannot use a PolicyGrant.

## D0 implementation

Strict Python models and generated TypeScript types encode the separation.
The SQLite schema has distinct tables and append-order uniqueness constraints.
The three D1 Artifact lifecycle events have a discriminated
`ArtifactLifecycleEvent` union with strict staged/committed/reconciled payloads;
the database rejects empty or mismatched lifecycle payloads.
