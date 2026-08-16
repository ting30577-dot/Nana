# D3-06 independent design: locked test journey orchestration

Date: 2026-08-08
Status: Codex proposal only; no D3-06 implementation is authorized yet.

## Entry and scope

D3-05 is joint ACCEPT. D3-06 consumes its canonical Project/Inquiry/Plan and
the D2 runtime handoff. It adds only the exact T2 `python.unittest.locked`
journey. D3-07 Approval and T3 export remain excluded.

The browser sends typed `StartRun` or `CancelRun` commands through the sole
runtime POST authority. It never sends a test target, executable, shell, grant
decision, or authorization material. The server-owned dev fixture supplies one
frozen args Artifact (`test_id` from the built-in allowlist), capability
registry entry, and configured PolicyGrant reference. The D3 service passes
that reference and typed `ActionHashMaterial` into D2 admission; it never reads
PolicyGrant/Approval to derive authorization.

## Proposed command flow

1. **StartRun admission record:** on the Workspace owner lane, validate the
   authenticated actor's access to the target Project/Inquiry/Plan, the
   Project/Inquiry/Plan revision, and exact backend; snapshot the plan
   revision, budget, and fixture inputs; create one Run and one proposed Action
   with a stable command-log entry. Missing subject authorization fails closed
   before Run/Action creation, grant consumption, or budget reservation.
2. **D2 policy-grant admission:** call
   `CapabilityAdmissionService.authorize_with_policy_grant` with the exact
   action material and configured grant reference. D2 owns grant matching,
   consumption, authorization Event/outbox, and durable authorization material.
3. **D2 scheduler claim:** call `RunSchedulerService.claim_action`; it owns
   budget reservation, concurrency, `action.started`, and run/action race
   semantics.
4. **D2 locked executor:** call `LockedUnittestExecutorService.execute`; it
   owns frozen test-ID validation, process limits, cancellation polling,
   Receipt, Artifact, terminal action/run Event transitions, and
   `effect_unknown`/orphaned semantics.
5. **Projection:** read models consume the committed Events/outbox/Receipt;
   no handler returns success before the canonical transaction result exists.

The implementation may use separate D2-owned transactions between steps. Any
crash between them leaves a durable proposed/authorized/running state and is
reconciled as pending/orphaned; it must never synthesize success.

## Cancel and crash invariants

- Start and Cancel run on the same Workspace owner lane and use distinct stable
  command IDs; a race has one durable winner. Each idempotency key is
  server-bound to the authenticated actor, target identity, Project/Plan
  revision, fixture digest, and an opaque request nonce from the authenticated
  command envelope. Reusing one nonce is replay; a new nonce is an intentional,
  separately budgeted rerun.
- CancelRun targets only a server-issued Run ID. The owner lane reloads that
  Run, checks the authenticated actor's Project scope and causation relation,
  and rejects unknown or cross-scope targets before any cancel transition.
- Cancel before claim produces `cancelled`; Cancel after process start requests
  termination and follows D2's `cancelled`/`effect_unknown`/`orphaned` Receipt
  semantics. A termination failure is never presented as success.
- Claim and spawn have an owner-lane fence: the owner lane conditionally
  transitions the claimed Action to `starting`/`spawn_committed` only when
  `cancel_requested` is false. Cancel and that transition are competing
  compare-and-set writes. If cancel wins before `spawn_committed`, the worker
  is never spawned and D2 releases the reservation as `cancelled`; if the
  durable spawn fence wins, every later cancel is termination-aware and cannot
  be downgraded to pre-spawn cancellation. A crash after the fence but before
  worker completion reconciles conservatively to `orphaned` or
  `effect_unknown`, never to cancelled or a retry.
- A sidecar/launcher crash during execution is recovered from canonical
  `runs`, `actions`, Events, and Receipt state. Unknown effects remain
  `effect_unknown`; restart does not rerun automatically.
- Replay of StartRun/CancelRun returns the stored command result/error and
  cannot create a second Run, Action, budget reservation, process, or Receipt.
- Replay while a command is non-terminal returns the current durable state
  (`proposed`, `authorized`, `running`, `cancel_requested`, or `starting`)
  without blocking and without creating another resource.

The terminal vocabulary is explicit: `timed_out` is distinct from `failed`,
`effect_unknown`, and `orphaned`. A pre-spawn cancellation releases the start
reservation. A timed-out process and every `effect_unknown`/`orphaned` path
  perform one conservative **commit settlement** in the same owner-lane
  SQLite transaction as the terminal Action/Receipt/Event CAS. The settlement
  idempotency key is the Action causation ID and is protected by a unique
  ledger usage record; it records measured usage, decrements `running_actions`
  exactly once, and never refunds uncertain effects. Crash recovery performs
  the same CAS+settlement transaction when it classifies the Action; replay or
  retry sees the terminal/usage row and is a no-op. It may not leave a
  reservation permanently pending.
Any partial
Artifact is attached and projected only in the same owner-lane completion
transaction as the Receipt and terminal Event, and is labelled by the
canonical terminal state.

Admission's grant consumption and scheduler's budget reservation are separate
D2-owned transactions. A crash between them is reconciled by an owner-lane
recovery pass: an authorized-but-unclaimed Action receives exactly one terminal
`budget_exceeded`, `cancelled`, or `orphaned` fact and is never re-admitted or
reclaimed. The consumed grant is the durable admission fact, not an implicit
refund; refund semantics would require an explicit D2 release API and are out
of D3-06 scope.

The D2 `ActionHashMaterial` coverage is explicit and complete for the
authorization surface: capability ID/version/digest, canonical args and
args_hash, data class, provider, requested effect scope, network methods,
budget snapshot, risk tier, and reversibility. The server-owned fixture digest
is the args hash plus capability digest; the effect ceiling is
`requested_effects`. Actor/Project/Inquiry/Plan identity and exact revision
are bound by server-owned Run/Action relations and the idempotency envelope.
Scheduler claim, cancel, and recovery all CAS the same Action lifecycle state;
the first transition wins and later transitions are durable no-ops, guaranteeing
one terminal fact.

### State and assertion table

| durable state | owner-lane guard | next states | budget assertion |
|---|---|---|---|
| proposed | admission CAS | authorized / terminal denial | no reservation |
| authorized | claim/recovery CAS | claimed / budget_exceeded / cancelled / orphaned | at most one claim |
| claimed | spawn-fence CAS with `cancel_requested = false` | spawn_committed or cancelled | reserve exactly once; pre-fence cancel releases once |
| spawn_committed/running | cancel/timeout watchdog | cancel_requested or terminal result | no release on uncertainty |
| cancel_requested | worker result + termination check | cancelled, effect_unknown, orphaned | cancelled only after confirmed stop; unknown commit-settles once |
| running | worker completion transaction | succeeded, failed, timed_out, effect_unknown | terminal CAS + usage decrement are one transaction |
| any non-terminal | replay read | same durable state | no new resource |

Claim, spawn fence, cancel, and recovery all update the same Action state with
conditional writes; first writer wins and later writers are no-ops. The
reservation assertions are checked by the D2 ledger's before/after
`running_actions` values and causation ID. Gate-G reads the worker process/job
handle and descendant liveness after the termination ladder; inability to
confirm death is `orphaned`, never `cancelled`. Job/fd/temp cleanup outcomes
and the decision source are included in the canonical audit Event.

## Required owner-lane execution bridge

The current D2 locked executor is a synchronous service that both touches
SQLite and runs the frozen process. D3-06 must not call that whole method on
the sole SQLite owner lane, or CancelRun could not reach a running process.
Before implementation, the D2 executor boundary must expose a narrow phased
bridge without weakening its checks:

1. owner lane: preflight and `RunSchedulerService.claim_action`, returning an
   immutable validated execution plan and started Event IDs;
2. worker: run only the frozen locked runner with a thread-safe cancellation
   signal and no SQLite writes;
3. owner lane: reuse the executor's canonical completion/Receipt/Artifact/Event
   transaction with the worker result.

CancelRun sets the signal and records the scheduler cancel-requested state on
the owner lane. The worker result then determines cancelled versus
effect_unknown/orphaned; a signal is never treated as proof of safe
termination. A sidecar crash leaves the canonical running/paused state for
reconciliation and never auto-reruns it.

## Mandatory pre-implementation gates

- **Gate-A fixture identity:** the exact args Artifact bytes/hash, frozen test
  ID, capability digest, and effect ceiling are server-owned and checked at
  execution time; replacement/TOCTOU fails closed. The worker receives bytes
  from the same verified immutable read-only snapshot/handle whose hash was
  checked and never re-reads a mutable path.
- **Gate-B executor boundary:** D2 locked executor's allowlist, effect subset,
  timeout, output, and termination-failure semantics remain authoritative. The
  worker phase extracts D2's existing frozen process-execution segment; it is
  not a second executor, generic runner, or shell path.
- **Gate-C durable orchestration:** Run/Action creation, Events/outbox,
  command-id replay, intermediate proposed/authorized/running states, and
  response-loss recovery are idempotent without synthetic success.
- **Gate-D budget lifecycle:** every reservation is settled by the D2
  accounting path across success, failure, cancel, orphan, timeout,
  effect_unknown, crash, and replay; no double reservation is possible.
  Pre-spawn cancellation releases. Timeout, effect_unknown, and crash commit
  settle measured usage exactly once in the same terminal CAS transaction and
  never refund uncertain effects. The watchdog only requests timeout/cancel;
  owner-lane completion or recovery is the single settlement writer.

All terminal paths converge on one owner-lane recovery coordinator and its
`_settle_action_and_budget` transaction keyed by the Action causation ID. The
worker and watchdog are never terminal writers: the worker reports an
immutable result, the watchdog writes only timeout/cancel intent, and Gate-G
  supplies read-only liveness evidence. The coordinator first classifies a
  non-terminal `unknown_pending` Action deterministically: confirmed residual
  process/child/resource state, or inability to confirm death by the deadline,
  selects `orphaned`; confirmed death with effects still unverifiable selects
  `effect_unknown`. Both labels use the same consumed-budget settlement and
  differ only in audit/projection vocabulary. It then performs the conditional
  terminal Action update, unique
usage-settlement insert, Receipt/Artifact/Event writes, and
`running_actions` decrement in one transaction. Once classified, no later
path may upgrade it; duplicate triggers read the terminal/usage row and no-op.

The reservation-increment-but-no-terminal window is owned by that same
coordinator: recovery scans `claimed`, `spawn_committed`, `running`,
`cancel_requested`, `timeout_requested`, and `unknown_pending` states and
must either progress them or commit-settle them, so no concurrent command can
invent a second owner. D3-06 product policy deliberately charges uncertain
effects conservatively; the Receipt exposes
`billing_basis=conservative_uncertain_effect` and an audit Event, with no
automatic refund or hidden success.
- **Gate-E cancel/Receipt visibility:** cancellation is request/termination
  aware; Receipt and Artifact projections become visible only after committed
  owner-lane completion, with cancelled/effect_unknown/orphaned distinct.
- **Gate-F owner-lane non-blocking proof:** barrier, cancellation, crash, and
  shutdown tests prove the worker bridge never writes SQLite off-lane and
  CancelRun can reach a running worker. An owner-lane/independent watchdog
  owns timeout and can signal a blocked worker; the worker receives no SQLite
  connection or writable DB handle. Worker crash recovers to effect_unknown
  with reservation pending one commit settlement; orphaned is reserved for confirmed residual
  process/termination failure.
- **Gate-G termination and resource recovery:** cancel/timeout confirms
  process death, escalates when required, and reaps descriptors, temporary
  files, and child processes. `orphaned` means confirmed residual state.
- **Gate-H decision auditability:** every gate decision and rejection records a
  tamper-evident canonical Event with gate ID, fixture/capability digests,
  effect decision, actor, and causation; projections expose the audit trail.

## Required review/test matrix before implementation exit

- exact closed command union and server-owned actor/fixture inputs;
- no arbitrary test ID, shell, Python, network, or Approval path;
- admission is called exactly once per stable Action and its durable material
  binds to the Action hash;
- scheduler claim/cancel races, budget reservation rollback, and double-submit;
- executor success, assertion failure, timeout, cancellation, termination
  failure, output limit, runner error, and effect-scope violation;
- Receipt/Artifact visibility only after committed outbox Events;
- response loss and crash/restart recovery without synthetic success;
- projections for running, termination-in-progress, cancelled, failed,
  budget-exceeded, orphaned, and effect_unknown;
- strict `ResourceWarning` owner-lane shutdown and full D3 evidence sync.

## Decisions requested from Claude

1. ACCEPT/VETO the server-owned exact T2 fixture boundary and no browser
   authorization input.
2. ACCEPT/VETO the staged D2 delegation flow and the allowed intermediate
   durable states.
3. ACCEPT/VETO the start/cancel/crash invariants and projection vocabulary.
4. Identify any missing race, Receipt, Artifact, or security gate before code;
   Gate-G and Gate-H are mandatory, not optional follow-up work.

D3-06 implementation, OpenAPI expansion, and UI mutation work remain blocked
until Codex/Claude converge explicitly.
