# Claude D3-06 convergence packet (sanitized)

Date: 2026-08-08
Purpose: design convergence only; no implementation authorization.

## Fixed boundaries

- D2 is complete and frozen. Its canonical facts are Actions, Events,
  outbox_events, Receipts, Artifacts, Runs, and durable authorization
  material.
- D3-06 covers only the exact T2 `python.unittest.locked` dev journey.
  Approval/T3 export, arbitrary shell/Python/network execution, and hostile
  code sandbox claims are out of scope.
- Browser commands are a closed typed `StartRun`/`CancelRun` union. The
  browser supplies neither test IDs, executable or shell text, grant or
  approval decisions, authorization material, nor effect declarations.
- A server-owned fixture selects one frozen built-in test ID, exact args
  Artifact bytes/hash, capability-registry digest, configured PolicyGrant
  reference, and effect ceiling. The fixture identity is rechecked at the
  execution boundary; replacement or TOCTOU fails closed.
- D3 never re-queries PolicyGrant/Approval to derive authorization. It passes
  the configured reference and typed ActionHashMaterial to the D2 admission
  service, which owns matching, consumption, authorization Event/outbox, and
  durable authorization material.

## Proposed staged flow

1. Workspace owner lane validates Project/Inquiry/Plan revision, exact
   backend, and authenticated actor Project scope before creating anything;
   it snapshots plan/budget/fixture and idempotently creates one Run, one
   proposed Action, and a stable command-log entry. The idempotency key is
   server-bound to actor, target identity, exact revision, fixture digest, and
   an opaque request nonce: same nonce replays, a new nonce intentionally
   reruns.
   CancelRun targets only a server-issued Run ID and rechecks actor scope.
2. D2 admission authorizes that exact Action once.
3. D2 scheduler claims the Action and owns concurrency plus budget
   reservation.
4. D2 locked executor enforces its allowlist, effect subset, timeout/output
   limits, cancellation polling, termination-failure behavior, Receipt,
   Artifact, and terminal Events.
5. Projection reads only committed canonical facts; no synthetic success is
   returned before owner-lane completion commit.

Admission grant consumption and scheduler budget reservation are separate
D2-owned transactions. Recovery gives every authorized-but-unclaimed Action
exactly one terminal budget_exceeded/cancelled/orphaned fact and never
re-admits or reclaims it; the consumed grant is an intentional durable
admission fact, not an implicit refund. Refunds would require a separate D2
release API and are out of D3-06 scope.

ActionHashMaterial covers capability ID/version/digest, canonical args and
args_hash, data class, provider, requested effects, network methods, budget,
risk tier, and reversibility. Actor/target/revision are bound by server-owned
Run/Action relations and the command envelope. Scheduler claim, cancel, and
recovery CAS the same Action lifecycle state; first transition wins and later
transitions are durable no-ops.

Separate D2-owned transactions are allowed only with durable proposed,
authorized, running, paused/cancel-requested, cancelled, failed,
budget-exceeded, orphaned, and effect_unknown states plus idempotent
response-loss recovery.

## Required phased execution bridge

The existing D2 executor is synchronous and touches SQLite before and after
the process. Calling the whole method on the sole owner lane would prevent
CancelRun from reaching a live process. Therefore D3-06 must expose a narrow
phased bridge without a second executor:

1. owner lane performs D2 preflight and scheduler claim, returning an
   immutable validated execution plan and started-event identifiers;
2. worker runs only the frozen locked runner, with a thread-safe cancellation
   signal and no SQLite writes;
3. owner lane records the canonical completion/Receipt/Artifact/Event
   transaction using D2 logic.

CancelRun records the scheduler cancel request on the owner lane and signals
the worker. The result, not the signal alone, distinguishes cancelled from
effect_unknown/orphaned. A crash leaves canonical state for reconciliation;
restart never auto-reruns unknown work.

## Mandatory gates

- Gate-A: exact fixture identity, digest, capability digest, and effect ceiling
  are checked at execution time; the worker receives bytes from that same
  immutable verified snapshot, never a second mutable read.
- Gate-B: D2 locked executor remains the sole authority for allowlist, effect
  scope, limits, and termination failure; its existing process-execution
  segment is extracted for the worker, with no generic runner/shell path.
- Gate-C: durable Run/Action/Event/outbox states, command-id replay, and
  response-loss recovery are idempotent without synthetic success.
- Gate-D: one D2 budget reservation lifecycle covers success, failure, cancel,
  orphan, timeout, effect_unknown, crash, and replay, with no double reserve.
  Pre-spawn cancel releases; timeout/effect_unknown/crash commit-settle the
  ledger exactly once and never refund uncertain effects.
- Gate-E: cancellation is termination-aware; Receipt/Artifact become visible
  only after owner-lane commit, and cancelled/effect_unknown/orphaned remain
  distinct.
- Gate-F: barrier, cancellation, crash, and shutdown tests prove worker
  execution is nonblocking and performs no SQLite writes off-lane. An
  owner-lane/independent watchdog owns timeout, passes no DB handle to the
  worker, and worker crash recovers to effect_unknown with one eventual commit
  settlement.
- Gate-G: termination confirms process death, escalates when required, and
  reaps descriptors/temp files/children; orphaned means confirmed residue.
- Gate-H: gate decisions/rejections emit tamper-evident audit Events with gate
  ID, fixture/capability digests, effect decision, actor, and causation.

## Questions for independent review

1. ACCEPT/VETO the exact server-owned fixture boundary.
2. ACCEPT/VETO the staged D2 delegation and allowed durable states.
3. ACCEPT/VETO the start/cancel/crash/replay and projection invariants.
4. ACCEPT/VETO each Gate-A through Gate-H, naming any concrete counterexample.

Claude must not modify files or claim tests. Any unresolved objection remains
NOT YET CONSENSUS and blocks implementation.
