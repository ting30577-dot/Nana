# D3-05 convergence packet after first Claude review (sanitized)

Date: 2026-08-08
State: implementation remains prohibited

## Privacy statement

Only relative module names, schema excerpts expressed as facts, authoritative
document names, and design decisions are included. There is no credential,
environment value, user/machine identity, private address, hardware identifier,
or username-bearing absolute path.

## First review result

Claude returned **NOT YET CONSENSUS**. Codex accepts that verdict as the current
joint state. This packet addresses P0-1, P0-2, P1-1 through P1-5, and P2-1
through P2-4. It requests a second design decision; it does not report an
implementation.

## Source evidence omitted from the first packet

1. `nana_sidecar/storage/schema.py` defines
   `command_log.command_id TEXT PRIMARY KEY`.
2. The same schema defines unique Event aggregate version and Run sequence
   constraints. `relations.id` is a primary key but active semantic-edge
   uniqueness is currently a service/registry invariant rather than a partial
   unique index.
3. `nana_sidecar/storage/command_transactions.py` enters `BEGIN IMMEDIATE`
   before its second command-log check and all domain/Event/outbox/result
   writes. SQLite therefore serializes competing service writers before their
   read-after-BEGIN duplicate/cardinality checks.
4. `nana_sidecar/storage/workspace_lock.py` acquires the OS Workspace lock before
   opening/migrating SQLite, completes reconciliation before ready, closes
   SQLite before releasing the lock, and retains ownership if close cannot be
   proven.
5. sqlite3 currently uses its default thread-affinity check. The proposed owner
   lane intentionally preserves that default.
6. Schema-v6 legal values include Resource `available`, Locator `valid`, and
   Evidence `valid`. Event payloads are typed as a JSON object but the closed
   Event type registry already contains `resource.registered`,
   `locator.created`, and `evidence.attached`.
7. There is no existing D0/D1 user `CreateWorkspace` Command. The current
   `WorkspaceRuntime.start` initializes/migrates/reconciles storage but does not
   create a canonical Workspace row. The first packet's prerequisite therefore
   was a genuine gap.
8. The authoritative `11_首个纵向切片执行清单.md` requires, before the locked
   test, defining one Hypothesis. Its dev scope also requires a traceable Finding
   draft and defers full counterexample/benchmark/final Decision work.
9. The frozen Relation Registry already defines
   `hypothesis_tested_by_run` with same-Inquiry validation. D3-06 is the first
   owner of Run creation.

## P0-1 resolution: structural single writer; schema v6 retained conditionally

Codex ACCEPTs Claude's requirement for a hard invariant and VETOs treating v7
as already necessary.

The design now requires:

- one `ThreadPoolExecutor(max_workers=1)` owned by runtime control;
- `WorkspaceRuntime.start`, internal Workspace bootstrap, every command
  transaction, and `WorkspaceRuntime.close` all execute on that lane;
- the sqlite connection retains default `check_same_thread=True`;
- the event-loop thread and any other worker cannot access that connection;
- runtime `draining` rejects new writes with 503, waits for the one admitted
  command, closes SQLite on the owner lane, then shuts down the executor only
  after a successful close/lock release;
- a lane scheduling/worker failure moves runtime to fail-closed and never opens
  a second writer;
- the existing OS lock continues to deny a second Nana runtime process;
- active Evidence/Relation duplicate and cardinality queries occur after
  `BEGIN IMMEDIATE`, so a second compliant connection cannot race past them;
- the database primary key remains the final command-ID uniqueness barrier.

Required tests assert owner thread identity at start/write/close, deliberate
cross-thread access raising sqlite3's affinity error, second-runtime denial,
same/different command races, and strict ResourceWarning-as-error shutdown.

This is stronger than relying on the executor by convention: the connection
itself rejects an off-lane call. Schema v6 is ACCEPT only if all these gates
pass. Any failure before D3-05 exit changes the decision to schema-v7 migration
owned and evidenced in D3-05; no fallback weakens the invariant.

## P0-2 resolution: typed internal Workspace bootstrap

Add internal `WorkspaceBootstrapSpec` and `WorkspaceBootstrapService`. They are
not browser routes and do not alter the frozen D0 user Command union.

Before ready, on the writer lane, the service starts one transaction and:

- if no Workspace exists, inserts the one typed configured Workspace plus
  `workspace.created` Event and outbox row;
- if exactly one row exists and every immutable/bootstrap field matches,
  returns an idempotent no-op;
- if multiple rows or any identity/configuration mismatch exists, rolls back and
  fails startup closed.

The spec carries only a stable UUID, portable logical data root, data-safe
policy, status, revision 1, and created time. No host path enters an Event or
error.

The frozen fixture composition passes the typed spec to runtime startup. The
fixture loader has no SQL handle and uses only the curated command service from
CreateProject onward. Tests use the same bootstrap service, not direct domain
inserts, and trace SQL to prove the loader itself never writes domain/Event/
outbox/command tables outside those services.

This is a storage-lifecycle bootstrap fact, not a user mutation. It therefore
does not need or expose a new browser Command, but it has the same transaction,
Event/outbox, crash rollback, exact-match idempotency, and fail-closed evidence
standards.

## P1 resolutions

### P1-1 Evidence duplicate semantics — ACCEPT and repaired

Two different command IDs with the same Inquiry, Locator, direction, and
excerpt hash are a deterministic replayable duplicate rejection. Different
directions remain distinct assertions because they map to distinct Claim
Relation types. The duplicate query is inside `BEGIN IMMEDIATE`.

### P1-2 cross-scope validation — ACCEPT and made explicit

Every composed writer loads and compares explicit scope:

- Resource Project must equal Inquiry Project before Evidence creation;
- Evidence and Claim must share Inquiry and derived Project;
- all DraftFinding Evidence IDs and terminal Run must share Inquiry and Project;
- the frozen descriptor must be registered into its request Project;
- no registry call substitutes for these explicit service checks.

### P1-3 expected-revision rule — ACCEPT and repaired

The uniform rule is: bind the revisioned input whose current content or
validity the command directly consumes. Other endpoints are checked live in the
same transaction.

- AttachEvidence now binds Locator revision, not Inquiry revision.
- Public Evidence-to-Claim CreateRelation binds Claim revision.
- Automatic `resource_contains_evidence` is a consequence of consuming that
  Locator, so it shares the Locator token.
- CreateLocator binds Resource; Plan revision binds Plan; Project/Inquiry child
  facts bind their revisioned container when there is no more specific
  revisioned input.

The token does not claim to be a collection revision, and creates do not
increment their container.

### P1-4 owner-thread close — ACCEPT

Owner-thread SQLite close plus OS-lock ordering is part of the strict D3
ResourceWarning-as-error gate. Runtime shutdown cannot release the lock or
executor early.

### P1-5 Hypothesis — Codex VETOs deferral, with authoritative handoff

Hypothesis is not added as an optional feature. It is a required pure research
fact in the authoritative first vertical slice. D3-05 owns its typed creation
and adds it to canonical bootstrap/reducer data so it is not invisible. D3-06,
the first Run owner, is explicitly assigned the existing
`hypothesis_tested_by_run` Relation. Until D3-06, execution is disabled and the
proposed Hypothesis accurately represents work awaiting a test.

Deferring it would leave no named later stage to satisfy the authoritative
pre-Run checklist and would force D3-06 to mix a missing research writer into
execution orchestration.

## P2 resolutions

- Rejection witnesses use UUIDs, logical descriptor IDs, hashes, states, and
  revisions only; never resolved roots, absolute paths, OS errors with paths,
  or tracebacks.
- A meta-test inventories every runtime mutation route and fails on any method
  or path beyond the one curated POST. Unknown union discriminators and an
  injected full-Command variant fail.
- Draining and lane failures return data-safe 503/500 and never partially
  commit; injected before/after-commit failures retain D1 replay semantics.
- Existing creation Events retain verification evidence without adding an
  Event type: Resource status/raw hash/descriptor/algorithm; Locator
  status/span/Resource hash/quote hash/algorithm; Evidence status/Locator/
  excerpt hash/verification basis. Payloads contain portable facts only.

## Revised item decisions requested

Please decide each item explicitly:

1. Structural owner lane + schema v6 conditional no-migration: ACCEPT, VETO, or
   NOT YET CONSENSUS.
2. Internal typed Workspace bootstrap: ACCEPT, VETO, or NOT YET CONSENSUS.
3. Revised expected-revision rule: ACCEPT, VETO, or NOT YET CONSENSUS.
4. Hypothesis D3-05 creation/projection with D3-06 Run relation handoff: ACCEPT,
   VETO, or NOT YET CONSENSUS.
5. Existing creation Event types with explicit verification payloads: ACCEPT,
   VETO, or NOT YET CONSENSUS.
6. Evidence duplicate and explicit cross-scope rules: ACCEPT, VETO, or NOT YET
   CONSENSUS.

Also state whether the earlier conditional ACCEPTs for the closed-union POST,
server actor, shutdown order, body limit, and route default-deny are now fully
resolved at design level.

Finally return one overall D3-05 design verdict. Only overall ACCEPT authorizes
D3-05 implementation. D3-06 and all later stages remain excluded.
