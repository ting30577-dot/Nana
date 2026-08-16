# Claude D3-06 design review packet (sanitized)

Date: 2026-08-08
Scope: D3-06 design only. No implementation, D3-07 Approval, export, or UI
mutation is authorized by this packet.

## Entry facts

- D3-05 is joint ACCEPT after F-01–F-19 scan/repair/final review.
- D2 owns admission, scheduler, locked executor, budget, Receipt, Artifact,
  Event/outbox, and runtime handoff semantics.
- D3-06 is exact T2 `python.unittest.locked`; D3-07 owns one-time Approval and
  T3 export.

## Codex proposal

See `docs/codex_d3_06_independent_design.md`. The core boundary is:

`typed StartRun/CancelRun -> server-owned exact fixture -> D2 PolicyGrant admission -> D2 scheduler -> D2 locked executor -> canonical Receipt/Artifact projection`

The browser cannot send test IDs, executable/shell input, grant decisions,
PolicyGrant/Approval material, or arbitrary effects. The service passes a
configured PolicyGrant reference to D2 admission and never queries PolicyGrant
or Approval to derive authorization.

The proposal now includes six pre-implementation gates:

- Gate-A binds exact server-owned args Artifact bytes/hash, frozen test ID,
  capability digest, and effect ceiling at execution time; replacement or
  TOCTOU fails closed.
- Gate-B preserves the D2 locked executor allowlist, effect subset, timeout,
  output, and termination-failure boundary; no generic runner or shell path.
- Gate-C makes Run/Action, Event/outbox, command-id replay, proposed/
  authorized/running states, and response-loss recovery durable and idempotent.
- Gate-D requires one D2-owned budget reservation lifecycle across success,
  failure, cancel, orphan, timeout, effect_unknown, crash, and replay.
- Gate-E makes cancellation termination-aware and exposes Receipt/Artifact only
  after owner-lane commit; cancelled/effect_unknown/orphaned stay distinct.
- Gate-F proves a non-blocking owner-lane bridge: owner-lane preflight/claim,
  worker-only frozen process execution with a thread-safe cancel signal and no
  SQLite writes, then owner-lane canonical completion; barrier/cancel/crash/
  shutdown tests must prove the bridge.

Start and Cancel share the Workspace owner lane. Intermediate proposed,
authorized, running, paused/cancel-requested, cancelled, failed,
budget-exceeded, orphaned, and effect_unknown states remain canonical facts;
crash/restart never synthesizes success or automatically reruns unknown work.

The bridge is required because the current D2 executor is synchronous and
touches SQLite before and after the process. Running it as one owner-lane call
would make CancelRun unable to reach a live process. The phased bridge must
preserve D2's existing preflight and completion semantics rather than create a
second executor.

## Review questions

1. Is the exact fixture/server-owned boundary sufficient to prevent arbitrary
   test or shell execution while still proving the T2 journey?
2. Is staged delegation to D2 admission, scheduler, and locked executor valid,
   including separate D2-owned transactions and durable intermediate states?
3. Are the start/cancel/crash/replay invariants complete, especially
   termination-in-progress, orphaned, effect_unknown, budget reservation, and
   Receipt/Artifact commit visibility?
4. What concrete counterexample or missing gate would VETO implementation?

Return explicit ACCEPT, VETO, or NOT YET CONSENSUS for each question. Claude
must not modify files or claim to have run tests.
