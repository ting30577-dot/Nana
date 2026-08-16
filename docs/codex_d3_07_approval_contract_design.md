# Codex independent design — D3-07 typed Approval contract

Date: 2026-08-09  
Status: design-only; implementation remains VETO until the joint 07-00 gate and
D3-06 Claude exit are ACCEPTed.

## Closed request union

The sole runtime may expose only these new typed command variants for the T3
fixture; no raw Action, PolicyGrant, filesystem path, shell, or provider input is
accepted:

```text
RequestApproval {
  type: "RequestApproval"
  command_id: UUID
  action_id: UUID
  expected_revision: integer  // current Action aggregate/Event version
}

DecideApproval {
  type: "DecideApproval"
  command_id: UUID
  approval_id: UUID
  decision: "approved" | "denied"
  expected_revision: integer  // current Approval aggregate/Event version
}
```

The `RequestApproval` shape above is the internal canonical Approval Command
after an exact Action exists. It is not authorization to expose `action_id` as
the D3 browser's export-preparation input. F07-23 separately evaluates a
narrowed journey request carrying Finding identity/version plus opaque target
selection; the owner would derive the Export Run/Action and only then construct
this canonical Command. See `docs/codex_d3_07_export_subject_audit.md`.

The server derives the ActionHash, capability digest, content hash, target
selection identity, actor/session, and expiry from canonical rows. The browser
cannot supply or override those subjects.

## Durable subject and atomicity

Approval authorization is validated against an in-memory actor/session-bound
selection, but the durable subject contains no opaque selection token or raw
machine identity. Its canonical commitment is:

```text
(action_id, action_hash, capability_id, capability_version, capability_digest,
 content_hash, selection_identity_digest, fixed_target_commitment, expires_at)
```

The opaque selection id, LocalSession binding, raw path, directory handle and
clear volume/file identity remain owner-runtime memory only. SQLite may persist
the irreversible non-locating digest/target commitment and the normal
Run/Action/Approval/Event bindings; restart never rebinds a new selection to
this subject.

For `decision="approved"`, `DecideApproval` commits the Approval decision,
durable Action authorization, one-time consumption marker, Approval and Action
Events, their outbox rows, and the stored `CommandResult` in one owner-lane
SQLite transaction through D2 admission primitives. There is no public
`ConsumeApproval` command; consumption is an internal step of this transaction.

For `decision="denied"`, the same command transaction commits only the denied
decision, `approval.decided` Event/outbox, and stable `CommandResult`. It neither
authorizes the Action nor writes an approval-consumption row.

The concurrency token is the existing append-only aggregate/Event version, not
a nonexistent Action/Approval table revision column. A changed ActionHash,
content, target selection, capability digest, actor, version, or expiry fails
closed.

## Replay and response loss

- Same `command_id` and byte-equivalent request returns the stored result without
  a second decision, authorization, or consumption.
- Same command id with changed request bytes returns a structured conflict.
- A response lost after commit is recovered by replaying the command id and
  validating the canonical subject, not by asking the browser to decide again.
- A consumed, denied, expired, or effect-unknown approval is never silently
  reactivated.

## Target scope caveat

`target_selection_id` is intentionally opaque. The product-owner-frozen D3
source is the Nana launcher/CLI; a post-dev native picker will preserve the same
backend contract. The browser never submits or receives an absolute path.
The product decision in `docs/d3_07_plan_aligned_decisions.md` freezes an
existing dedicated empty directory on a supported fixed local filesystem, with
root/system/Nana/Workspace/reparse/alias/UNC/network/cloud/collision/change
rejection, fixed filename and no overwrite. Claude must still review the
security properties recorded in
`docs/codex_f07_10_scope_reconciliation.md`.

## Explicit negative constraints

No PolicyGrant path, no browser-selected capability, no arbitrary filename, no
remote publish, no shell, no public `ConsumeApproval`, and no optimistic UI
success are part of this design.
