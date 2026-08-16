# D3-06 Codex independent re-audit findings

Date: 2026-08-11  
Governance: Codex-only under
`docs/d3_codex_only_governance_decision_20260811.md`  
Scope: exact trusted fixture-only T2 `python.unittest.locked` bridge

## No-edit scan method

After the governance record was created, the D3-06 runtime implementation was
held unchanged while Codex re-read the live request contract, owner-lane bridge,
D1 Artifact protocol, D2 admission/scheduler/budget/executor seams, startup
reconciliation, read models and all 17 focused D3-06 tests. Historical Claude
gaps F-A through F-E were treated as open questions rather than verdicts.

## Directly closed historical gaps

- **F-A:** the implementation is directly inspectable in the live worktree.
  `JourneyCommandService._complete_locked_context` delegates one terminal write
  set to `LockedUnittestExecutorService._record_completion`; its single
  transaction publishes the staged result Artifact, attaches producer and
  Relation facts, writes Receipt and budget settlement, appends Gate-A..H and
  Action events, and terminalizes the Run. Existing rollback/restart tests
  exercise the boundary rather than relying only on a narrative count.
- **F-B:** `StartRunRequest` contains only project/inquiry/plan identities,
  plan/expected revision and random seed. `to_canonical_command` injects the
  exact server-owned `python.unittest.locked` capability. Strict Pydantic input
  rejects browser backend/capability material with 422 before a Run is created;
  stale/illegal target revision is rejected before args Artifact provisioning.
- **F-E:** `unknown_pending` is intentionally not a public schema state. It is
  the recovery classification `Action.state=running` plus a durable
  `action.output{phase=spawn_committed}` fence. No fence proves the worker could
  not start and converges to a zero-effect cancelled Receipt; a fence plus
  owner loss cannot re-prove liveness/effects and converges to Action
  `effect_unknown`, Run `orphaned`, conservative billing and no retry. Confirmed
  live timeout remains `timed_out`; verified pre-spawn cancellation remains
  `cancelled`; termination failure is Action `effect_unknown` plus Run
  `orphaned`. No branch upgrades uncertainty to success or refunds it.

## Consolidated findings before repair

| ID | Severity | Finding | Evidence / consequence | Decision |
|---|---|---|---|---|
| F-33 | P2 evidence gap | F-C is true in code but lacks a focused mutation proof. | Executor preflight joins `action_authorizations` and never joins `policy_grants` or `approvals`; however no D3-06 test revokes the source Grant after admission and proves the already-authorized Action still executes from its durable authorization snapshot. | Repair with a focused test; no runtime change expected. |
| F-34 | P1 evidence gap | F-D lacks a D3-specific close/reopen crash proof at the exact result-blob promotion/SQLite rollback window. | The existing rollback test promotes the blob and rolls the terminal transaction back, but reconciles in the same process. D1 separately proves orphan-final recovery. The D3 claim also needs one combined close/reopen case proving one final Receipt, one usage settlement, one output relation and no phantom pre-crash Receipt. | Repair with a close/reopen fault-injection test and real `ArtifactReader`; no runtime change expected unless the test exposes a defect. |
| F-35 | P3 evidence clarity | The final D3-06 record does not explicitly map `unknown_pending` to its durable representation and terminal outcomes. | Reviewers can confuse a design-only name with a missing database enum or infer that all uncertainty maps identically. | Repair the independent exit evidence with the explicit mapping above. |

## Batch-repair boundary

The repair may modify only D3-06 focused tests and D3-06 Codex-only evidence
records unless a red test proves a runtime defect. It must not add Approval,
T3 capability, mutation-route expansion, external path selection, shell,
network or Workspace-outside writes.

Current local decision: **VETO pending F-33 through F-35 evidence repair**.
