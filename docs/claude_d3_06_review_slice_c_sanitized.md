# D3-06 slice C: mandatory execution gates (sanitized)

Review each gate with ACCEPT, VETO, or NOT YET CONSENSUS and identify any
missing gate.

- Gate-A: exact fixture bytes/hash, frozen test ID, capability digest, and
  effect ceiling are checked at execution time; the same immutable verified
  snapshot bytes are passed to the worker; replacement/TOCTOU fails closed.
- Gate-B: D2 locked executor remains sole authority for allowlist, effect
  subset, timeout/output limits, and termination failure; the worker is an
  extraction of D2's existing process-execution segment, with no generic
  runner or shell path.
- Gate-C: Run/Action/Event/outbox creation, command-id replay, intermediate
  states, and response-loss recovery are durable and idempotent without
  synthetic success.
- Gate-D: one D2 budget reservation lifecycle covers success/failure/cancel/
  orphan/timeout/effect_unknown/crash/replay with no double reservation.
  Pre-spawn cancel releases; timeout/effect_unknown/crash commit-settle the
  ledger exactly once and never refund uncertain effects.
- Gate-E: cancellation is termination-aware; Receipt/Artifact appear only
  after owner-lane commit; cancelled/effect_unknown/orphaned remain distinct.
- Gate-F: owner-lane preflight/claim -> worker-only frozen process with a
  thread-safe cancel signal and no SQLite writes -> owner-lane completion;
  watchdog owns timeout, passes no DB handle to the worker, and worker crash
  recovers to effect_unknown with one eventual commit settlement.
- Gate-G: termination confirms process death, escalates when required, and
  reaps descriptors/temp files/children; orphaned means confirmed residue.
- Gate-H: gate decisions/rejections emit tamper-evident audit Events with gate
  ID, fixture/capability digests, effect decision, actor, and causation.

The existing D2 executor is synchronous and touches SQLite before and after
the process, so calling the whole method on the sole owner lane would prevent
CancelRun from reaching a live process. The phased bridge must reuse D2 checks,
not create a second executor.

Review evidence includes the state proof: proposed -> authorized -> claimed ->
spawn_committed/running -> terminal, with claim/spawn/cancel/recovery
conditional writes on one Action state. Pre-fence cancel is cancelled plus one
release; post-fence results decide cancelled/effect_unknown/orphaned; crash
after fence is effect_unknown with one eventual commit settlement. Gate-G reads process/job
and descendant liveness after the termination ladder; inability to confirm
death is orphaned, and cleanup outcomes are audited.
