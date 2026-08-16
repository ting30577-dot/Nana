# Nana D3-00 final resolution packet (sanitized)

Purpose: resolve the three blockers retained by Claude's convergence review and
freeze the T3 export clarification. This packet contains no credentials,
environment values, literal authorization values, absolute user paths, machine
identity, private network information, or hardware identifiers.

## R1 — Approval decision and authorization consumption

Claude's counterexample is accepted. A two-transaction sequence that first
marks an Approval approved and later consumes it can crash in between. D3 will
not call the current public admission method after a separately committed
decision.

### Resolution

The typed decision application service delegates to a new D2 admission-owned
operation with one `BEGIN IMMEDIATE` transaction:

1. bind stable command ID/request hash and require idle connection;
2. load waiting Action, full ActionHashMaterial, registry entry, and requested
   Approval;
3. validate expected Approval state/revision and decision input;
4. for denial: update Approval to denied, append decided Event/outbox and stable
   command result in the same transaction; do not authorize Action;
5. for approval: update Approval to approved, append Approval-decided
   Event/outbox, run the existing approval authorization validation logic,
   update Action authorized, append action-authorized Event/outbox, write
   append-only action authorization material/event binding, record approval
   consumption, and write the stable command result;
6. commit once.

The validation/authorization logic remains owned by D2 admission. The D3 HTTP
layer does not copy or re-derive it. Implementation should refactor a private
transaction-scoped admission primitive rather than duplicate policy rules.

### Required tests

- `test_decide_approval_and_authorize_is_one_transaction`;
- `test_decide_approval_commit_failure_rolls_back_decision_authorization_events_outbox_consumption_and_command_result`;
- `test_decide_approval_response_loss_replays_without_second_consumption`;
- `test_same_command_id_changed_decision_conflicts`;
- `test_denial_never_creates_action_authorization_or_consumption`;
- `test_expired_or_changed_action_material_fails_closed_before_decision_commit`.

Decision: Codex **ACCEPT** this resolution. The old two-transaction design is
**VETO**.

## R2 — Event IDs and gap semantics

Claude's rollback-hole counterexample is accepted. Event IDs are stable and
strictly increasing among delivered committed Events; they are not a dense
sequence contract.

### Resolution

- Client reducer accepts any `event.id > last_applied_event_id`.
- `event.id <= last_applied_event_id` is an at-least-once duplicate and is
  ignored after schema validation.
- Integer non-contiguity (`next_id > last_id + 1`) is legal and never triggers
  a gap refresh by itself.
- Client does not claim it can infer a missing outbox row from ID arithmetic.
- Snapshot returns a high-water Event ID from the same SQLite read transaction;
  stream starts strictly after it.
- Refresh is triggered by explicit server replay-unavailable error, incompatible
  contract/schema, malformed frame, aggregate-version violation, Run-sequence
  violation, or transport failure policy—not by a missing integer.
- Outbox retain-only integrity remains a server invariant tested separately.

### Required tests

- replay IDs `10, 12, 19` without false gap;
- duplicate ID ignored without projection change;
- decreasing/out-of-order new Event fails closed;
- consistent snapshot/cursor race test;
- explicit replay-unavailable response forces snapshot refresh.

Decision: Codex **ACCEPT**. Dense-ID client logic is **VETO**.

## R3 — fixture/replay viewer contract ownership

Claude's two-contract counterexample is accepted.

### Resolution

There is exactly one public HTTP/OpenAPI contract authority: the new
authenticated runtime factory. The fixture/replay viewer is not a server, API,
or second generated client. It is a development/test data adapter that:

- imports the checked-in replay JSON at build/test time;
- validates it against shared generated domain/event types;
- feeds the same pure projection reducer used by the runtime client;
- performs no HTTP, auth, CORS, Workspace ownership, or mutation;
- is excluded from production navigation/build unless an explicit later ADR
  changes that boundary.

Thus `ready` and authentication gates apply to the real canonical runtime, not
to an offline reducer test. Both modes share types and reducer behavior, but
only one mode has an HTTP contract.

### Required tests

- fixture schema validates against shared event/projection types;
- fixture and equivalent authenticated runtime snapshot+Events produce equal
  projection;
- production bundle/navigation contains no fixture adapter entry;
- no second OpenAPI snapshot or generated HTTP client exists.

Decision: Codex **ACCEPT**. A second viewer HTTP/API contract is **VETO**.

## R4 — narrow T3 export

The frozen D3 E2E export target is a harness-created local test directory
outside the canonical Workspace, with exact resolved target included in the
Action hash and one-time Approval. It is a real external filesystem side effect
but a controlled test target, not a remote publish.

The capability writes a same-directory partial, flushes/syncs, and atomically
replaces the exact target where supported. If the process crashes or the final
effect cannot be verified, the Action/Receipt is `effect_unknown`; the UI never
synthesizes success. Idempotent replay checks exact content hash/target and does
not silently overwrite changed external content. Denial, expiry, Action change,
replay, canary, path boundary, partial write, and crash windows are separate
tests. This capability receives no hostile-code sandbox claim from D2.

Decision: Codex **ACCEPT with separate security gate**.

## Final labels requested from Claude

Please decide whether R1-R3 close the retained NOT CONSENSUS items and whether
R4 satisfies the export clarification. Then issue the final D3-00 decision
table. Any remaining material objection must remain NOT CONSENSUS.
