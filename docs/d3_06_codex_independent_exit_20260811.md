# D3-06 Codex independent implementation exit

Date: 2026-08-11  
Governance: `docs/d3_codex_only_governance_decision_20260811.md`  
Scope: exact trusted, frozen, fixture-only T2 `python.unittest.locked`

## Final no-edit re-review

Codex re-read the live runtime, storage, executor, Artifact and test surfaces
after the F-14 through F-32 repair batch. The review opened F-33 through F-35
in `docs/d3_06_codex_independent_reaudit_findings_20260811.md`; the repairs
added direct executable evidence without changing the frozen runtime design.

| Historical gap | Direct live-worktree evidence | Decision |
|---|---|---|
| F-A, implementation evidence | focused runtime, D1 Artifact, strict subset and full regression tests exercise the repaired transaction/restart paths | ACCEPT |
| F-B, server-fixed target/fixture and early rejection | `StartRunRequest` exposes no capability/backend/test selector; server injects `python.unittest.locked`; precheck rejects target/revision/policy before args Artifact provisioning | ACCEPT |
| F-C, durable admission is the sole execution authorization | a new test revokes the source PolicyGrant after admission and proves execution uses the durable `action_authorizations` record without Approval lookup | ACCEPT |
| F-D, promotion-before-commit crash | a new close/reopen test proves SQLite rollback, no phantom Receipt, no duplicate billing, conservative restart settlement and readable content-addressed failure Artifact | ACCEPT |
| F-E, `unknown_pending` mapping | the implementation represents it as running Action plus committed spawn fence; no fence converges to proven-zero-effect cancellation, while owner loss after fence converges to Action `effect_unknown`, Run `orphaned`, conservative billing and no retry | ACCEPT |

## Preserved boundary

- The capability is only `python.unittest.locked` over the immutable trusted
  fixture allowlist. It is not a hostile-code sandbox.
- The worker receives frozen process/test/root/limit inputs and a thread-safe
  cancel callback. It receives no SQLite connection or write authority.
- D2 admission, durable authorization, scheduler claim, budget reservation,
  executor, Receipt and owner-lane transaction remain canonical.
- Approval, T3 export, arbitrary shell/Python, network, external write and
  remote publish remain closed by this decision.

## Verification snapshot

| Verification | Result |
|---|---|
| `python -m compileall nana_sidecar tests scripts` | pass |
| D3-06 focused strict suite | 19 pass |
| D1 Artifact commit/failure/reconciliation plus D3-06 | 67 pass |
| prescribed D3/pre-gate strict suite | 125 pass, 2 platform skips |
| full Python regression | 388 pass, 2 platform skips |
| `npm.cmd run check` | pass |

The full Python suite still emits the already-attributed PySide6 GC shutdown
warning after successful completion. The strict D3 handle/process/write path
promotes `ResourceWarning` to an error and passes, so this is not attributed to
the D3 execution path.

## Decision

**D3-06 Codex-only implementation exit: ACCEPT.**

This closes D3-06 under the current governance decision. It authorizes only a
fresh D3-07 design/security entry review. It does not itself register T3,
authorize filesystem writes or flip any D3-07 implementation gate.
