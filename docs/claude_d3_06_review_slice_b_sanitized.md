# D3-06 slice B: durable lifecycle and cancellation (sanitized)

Review only this slice; return ACCEPT, VETO, or NOT YET CONSENSUS.

- Separate D2-owned transactions may expose only durable proposed,
  authorized, running, paused/cancel-requested, cancelled, failed,
  budget-exceeded, orphaned, and effect_unknown states.
- Start/Cancel use stable command IDs and replay the stored command result or
  error without a second Run, Action, reservation, process, or Receipt.
- Cancel before claim yields cancelled. Cancel after process start requests
  termination; the process result, not the signal alone, distinguishes
  cancelled from effect_unknown/orphaned. Termination failure is never success.
- Claim and spawn are fenced by an owner-lane compare-and-set: the Action may
  enter `spawn_committed` only if cancel-requested is false. If cancellation
  wins first, no process is spawned and the reservation is released; after the
  fence, cancellation is termination-aware and cannot be treated as pre-spawn.
- Replay while non-terminal returns the current durable state without blocking
  or creating another resource.
- `timed_out` is a distinct terminal state. Pre-spawn cancellation releases
  its reservation; timeout and effect_unknown/orphaned conservatively commit
  measured usage. Any partial Artifact is projected only with the committed
  Receipt and terminal Event and carries the canonical unknown/timeout state.
- Receipt and Artifact projections become visible only after the owner-lane
  completion transaction commits its canonical Events/outbox.
- Crash/restart leaves canonical state for reconciliation and never
  automatically reruns unknown work or synthesizes success. Budget reservation
  is committed or released exactly once across success, failure, cancel,
  orphan, timeout, effect_unknown, crash, and replay.

Question: are replay, crash, cancel, Receipt/Artifact, and budget invariants
complete? Name a concrete counterexample if not.
