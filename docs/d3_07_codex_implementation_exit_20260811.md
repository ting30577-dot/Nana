# D3-07 Codex-only implementation exit

Date: 2026-08-11  
Governance: `docs/d3_codex_only_governance_decision_20260811.md`

## Implemented boundary

D3-07 implements one exact T3 capability, `export.draft_external`. A launcher
user selects an existing dedicated empty fixed-local NTFS directory before the
runtime serves. The browser receives only a 60-minute, LocalSession/user-bound,
one-attempt opaque selection id and redacted label.

`RequestApproval` derives the Export Run, Action, capability, frozen renderer,
public draft Artifact, source graph, effects, budget and ActionHash from
canonical facts. `DecideApproval(approved)` performs decision, D2 durable
authorization, one-time consumption, Approval/Action events and outbox, and the
stable result in one owner-lane SQLite transaction. No public consume operation
exists. Denied and expired decisions never authorize, consume, receipt or write.

Execution loads only the durable admission record. It validates all frozen
Artifacts and identities before committing an append-only first-write fence,
then performs a positive probe and fixed-name no-overwrite write. Verified
success, proven cleanup failure and unverifiable effect are represented as
`succeeded`, `failed` and `effect_unknown`; restart never rebinds or retries an
old Action.

## Direct verification

| Verification | Result |
|---|---|
| `python -m compileall nana_sidecar tests scripts` | pass |
| D3-07 focused strict suite | 23 pass at final repair checkpoint |
| D2/D3 strict `ResourceWarning` suite | 202 pass, 2 platform skips |
| full Python regression | 410 pass, 2 platform skips |
| `npm.cmd run check` | pass |
| Vitest + projection self-test | 58 pass + self-test pass |
| production build | pass |
| existing read-only browser E2E | 17 pass, 0 retries/failures |

The full Python process prints the previously attributed PySide6 GC shutdown
warning after a successful exit. The 202-test D2/D3 handle/process/write suite
promotes `ResourceWarning` to an error and passes.

## Security review disposition

F07-32 through F07-41 are recorded and closed in
`docs/d3_07_implementation_scan_findings_20260811.md`. In particular, the
Windows rename behavior was tested rather than inferred: retained identity plus
pre/post-effect revalidation is the authority, and any mismatch after the fence
is never reported as success.

## Decision

**D3-07 Codex-only implementation exit: ACCEPT.**

This authorizes the next ordered stage, D3-08A. It does not authorize T4
publish, remote/cloud export, arbitrary filesystem targets, arbitrary process
execution, network access or hostile-code sandbox claims.
