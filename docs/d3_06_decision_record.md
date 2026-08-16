# D3-06 decision record: locked test journey orchestration

Date: 2026-08-08
Status: implementation authorized; exit review pending.

## Joint decision

**Codex ACCEPT + Claude ACCEPT = D3-06 design ACCEPT.**

The implementation scope is the exact T2 `python.unittest.locked` journey
only. Browser commands are the closed typed StartRun/CancelRun union; all
fixture, capability, grant, budget, process, Receipt, Artifact, Event/outbox,
and projection authority remains server/D2-owned. D3-07 Approval, T3 export,
arbitrary shell/Python/network execution, and hostile-code sandbox claims are
excluded.

## Hard invariants authorized for implementation

1. Owner-lane subject authorization fails closed before Run/Action creation.
   Idempotency is actor/target/revision/fixture bound plus an opaque request
   nonce: same nonce replays, a new nonce intentionally reruns.
2. ActionHashMaterial covers the complete D2 authorization surface; fixture
   bytes come from the same immutable verified snapshot passed to the worker.
3. D2 admission, scheduler, and locked executor remain the sole authorities;
   D3 does not re-query PolicyGrant/Approval or invent authorization.
4. Claim/spawn/cancel/recovery compete on one Action-state CAS fence. The
   pre-spawn cancel path releases once; post-fence cancellation is
   termination-aware.
5. A single owner-lane recovery coordinator is the only terminal writer.
   `unknown_pending` deterministically becomes `orphaned` on confirmed
   residual/failure-to-confirm-death, otherwise `effect_unknown`; both are
   conservative consumed-budget settlements and remain distinct in audit and
   projection.
6. Terminal Action CAS, Receipt/Artifact/Event, unique Action-causation usage
   settlement, and `running_actions` decrement are one SQLite transaction.
   Watchdog only records timeout/cancel intent; worker has no DB handle.
7. Gate-G confirms process/job/descendant death and cleanup. Gate-H records
   tamper-evident gate decisions. Receipt exposes conservative billing basis.

## Required implementation evidence

- owner-lane/worker bridge with no off-lane SQLite writes;
- spawn fence and Start/Cancel/recovery races;
- exactly-once settlement and replay/response-loss/crash recovery;
- all D2 locked executor outcomes, Gate-G reaping, Gate-H audit, projection
  visibility, and strict ResourceWarning attribution;
- first scan, listed findings, batch repair, second scan, and updated D3-06
  evidence/manifest before Claude exit review.

## Current Codex-only exit amendment — 2026-08-11

The historical joint-design decision and absent Claude implementation verdict
above remain preserved as historical evidence. The product owner subsequently
removed Claude as a current prerequisite in
`docs/d3_codex_only_governance_decision_20260811.md`; this did not waive any
security invariant or automatically authorize a later stage.

Codex performed a fresh live-worktree independent re-audit, recorded F-33
through F-35, added direct durable-authorization and blob-promotion rollback /
restart evidence, and reran focused, strict and full regression suites. The
final evidence is in `docs/d3_06_codex_independent_exit_20260811.md`.

**Current D3-06 implementation decision: Codex-only ACCEPT.** The accepted
scope remains only the exact trusted fixture-only T2
`python.unittest.locked` path. No Approval, T3 export, external write,
arbitrary execution, network or hostile-sandbox claim follows from it.
