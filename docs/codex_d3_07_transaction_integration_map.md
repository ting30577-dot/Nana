# Codex D3-07 transaction and runtime integration map

Date: 2026-08-09  
Status: design-only; no Approval route, Export capability, schema migration or
Workspace-outside writer is authorized by this record.

## Authority constraints carried into the map

1. Authority 05 defines optimistic concurrency through append-only
   `Event.aggregate_version`, requires domain changes, Event/outbox and stable
   `CommandResult` to share the SQLite transaction, and says an unapproved
   Action cannot produce effects.
2. The product-owner-frozen D3-07 rule makes `DecideApproval(approved)` the
   owner of the decision, Action authorization and one-time consumption.
   `denied` owns only the denied decision, one Approval Event/outbox and its
   stable result.
3. Authority 05 still contains the canonical `AuthorizeAction` type. It is not
   a `ConsumeApproval` command and is not deleted by this design. The D3 browser
   journey will not expose it as a separate approval-completion call.
4. No canonical or journey `ConsumeApproval` variant exists in the current
   contracts, generated OpenAPI or TypeScript output. D3-07 must keep it absent.

## Current implementation facts

- `nana_sidecar/contracts/commands.py` already uses canonical literals
  `approved` and `denied`. `RequestApproval`, `DecideApproval` and
  `AuthorizeAction` are contract types, but the sole D3 mutation route accepts
  only the narrower journey union.
- `approvals` and `actions` have no `revision` column. Their concurrency/history
  sequence is `MAX(events.aggregate_version)` for the matching aggregate.
- `CapabilityAdmissionService.authorize_with_approval` currently starts its own
  transaction and requires an Approval that is already `approved`. It then
  authorizes the Action and inserts `approval_consumptions`; it does not decide
  the Approval or write a command-log result. Calling it after a separately
  committed `DecideApproval` would therefore violate the frozen atomicity.
- Existing durable authorization is already strong enough for the approved
  branch: `action_authorizations.authorization_event_id` and
  `approval_consumptions.event_id` can both reference the same
  `action.authorized` Event. Unique keys enforce one authorization and one
  consumption per Action/Approval.
- The current journey `StartRun` implementation is a closed D3-06 fixture. It
  accepts only `python.unittest.locked`, creates both the algorithm Run and its
  T2 Action, and starts the Run in `running`. It cannot be called as-is to
  create the independent Export Run and then followed by a second generic
  `ProposeAction` without producing the wrong Action.
- Stored-result validation currently assumes most journey aggregates stay at
  version 1. Approval decisions and Action authorization necessarily advance
  existing aggregates, so D3-07 needs explicit version-aware validators rather
  than reusing that assumption.

## Approved-branch transaction topology

The following is the exact candidate write set after the remaining product and
joint gates accept it. All numbered steps occur under the existing
`BEGIN IMMEDIATE` command transaction; any failure rolls every step back.

1. Perform command-id/request-hash replay preflight. A stored result is returned
   only after its complete domain/Event/outbox binding is revalidated.
2. Load the Approval and calculate its current version from its Event stream.
   Require `command.expected_revision` to equal that value, decision
   `requested`, unexpired subject and exact actor/session authority.
3. Load the subject Action, its current Event version, canonical args bytes,
   ActionHash material and registry contract. Require `waiting_approval`, exact
   subject id/hash, no authorization row and no consumption row.
4. Update only the Approval decision fields to `approved` and the canonical
   deciding actor/time.
5. Append `approval.decided` at Approval aggregate version `current + 1` and
   insert its outbox row.
6. Invoke an **in-transaction private admission primitive** that rechecks the
   Action/Approval/material, updates the Action to `authorized`, appends
   `action.authorized` at Action aggregate version `current + 1`, inserts its
   outbox row, and inserts immutable `action_authorizations`.
7. Insert `approval_consumptions`, referencing that same
   `action.authorized` Event. This is the only consumption step and has no
   public Command/request variant.
8. Store one accepted `CommandResult` whose ordered Event ids are
   `[approval.decided, action.authorized]` and whose affected revisions contain
   the exact resulting Approval and Action aggregate/Event versions.
9. Commit. Export execution and every Workspace-outside byte start only after
   this commit is known or recovered by idempotent replay.

The Action update must use its exact prior state and immutable ActionHash
binding in its guarded predicate. The Event unique constraint remains the final
concurrent-version guard; no invented table `revision` field is permitted.

## Denied-branch transaction topology

The denied branch shares only the replay, Approval-version, subject-hash,
actor/session and expiry validation above. Its complete write set is:

1. update the Approval decision to `denied` with deciding actor/time;
2. append one `approval.decided` Event at Approval version `current + 1`;
3. insert that Event's outbox row;
4. store one accepted `CommandResult` containing only the Approval revision and
   Event id;
5. commit.

It does **not** update the Action, append an Action Event, insert
`action_authorizations`, insert `approval_consumptions`, claim a scheduler
Action, write a Receipt or touch the selected directory. A separately
correlated deterministic system `CancelRun` performs later Export Run
convergence and is not part of `DecideApproval(denied)`.

## Required code seams after the gate opens

| Responsibility | Existing seam | Required D3-07 shape |
|---|---|---|
| idempotency/transaction/result | `storage/command_transactions.py` | Reuse `execute_transactional`; add Approval-specific stored-result and rejection validation. |
| Action/Approval material validation | `storage/admission.py` | Extract a private in-transaction Approval admission primitive; keep top-level policy-grant admission behavior unchanged. |
| typed journey dispatch | `contracts/journey.py`, `storage/journey_commands.py` | Add only the accepted narrow application request; never accept capability, path, ActionHash or authorization inputs from the browser. |
| Approval projection | `read_models.py` and generated web contracts | Project requested/approved/denied/expired from canonical rows and Events; UI success follows committed SSE facts. |
| independent Export subject | new owner service behind journey dispatch | Derive deterministic Run/Action/Artifact/Relation/Approval ids and commit the accepted F07-23 composite without invoking the D3-06 locked `StartRun` handler. |
| external execution | later exact T3 executor | Require the durable approved authorization and consumed Approval before claim; never infer authority from UI/session memory alone. |

The proposed F07-23 application request is an orchestration boundary, not a new
canonical Command name. It may reuse internal domain primitives for the
existing `StartRun`/`ProposeAction`/`CommitArtifact`/`RequestApproval` semantics,
but must have one outer idempotency record and one deterministic composite
result. It must not nest multiple `BEGIN IMMEDIATE` command services or use the
specialized D3-06 `StartRun` handler. This topology is accepted as product
design by `docs/d3_07_plan_aligned_decisions.md`; independent/joint security
review and implementation evidence remain pending.

## Mandatory fault and replay evidence

At minimum, implementation tests must inject failure after each mutable step in
both decision branches, at outbox insertion and final commit, then reopen the
database and replay the same command. They must also cover two real SQLite
connections racing the same Approval version; stale Approval/Event version;
changed ActionHash/args/capability/selection; expired, denied or already consumed
Approval; command-id content conflict; lost response after commit; tampered
stored result/Event/outbox; and proof that denied produces zero authorization,
consumption, Receipt and external effects.

## Gate effect

This map removes implementation guesswork but grants no permission. F07-20
through F07-31 are product-frozen; the D3-06 Claude exit, independent review of
those rules and joint D3-07 entry gate remain unresolved. The authoritative
machine flags remain false.
