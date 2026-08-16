# D3-07 first scan findings (planning gate; no implementation edits)

Date: 2026-08-09. Scope: the D3-07 decomposition draft, D2 Approval/admission
primitives, current runtime command union, export-related contracts, and the
authoritative D3 boundaries. This is a pre-implementation scan; findings are
listed before any D3-07 code is enabled.

| ID | Severity | Finding | Evidence / consequence | Decision |
|---|---|---|---|---|
| F07-01 | P0 | The 07-00 entry gate is described but not yet a signed machine-checkable decision record. | Export must remain disabled until unsupported atomic replace, security-gate scope/signers, and `effect_unknown` operational handling have explicit ACCEPT/VETO outcomes. | VETO implementation until gate record exists. |
| F07-02 | P0 | No D3-07 typed Approval request/decision/consumption contract is exposed through the sole runtime. | Reusing raw D2 commands or UI local state would bypass one-time subject-hash binding and response-loss replay. | VETO until a closed typed union and replay binding are designed. |
| F07-03 | P0 | No registered exact-target T3 export capability exists. | Without registry digest, schema, provider/effect ceiling and canary, admission cannot prove the target or capability is frozen. | VETO. |
| F07-04 | P0 | No controlled allow-root/target resolver and positive atomic-replace probe exists. | Arbitrary external paths, reparse aliases, unsupported filesystems, or non-atomic fallback could create unverifiable writes. | VETO. |
| F07-05 | P1 | Approval/action/content hash and before/after Artifact contract is not yet connected to an export writer. | A successful write could not be reconciled to the approved bytes or Receipt actual effects. | Open. |
| F07-06 | P1 | Crash-point and changed-target matrix is only a planning item. | Partial write, flush/sync, replace, and response-loss outcomes need deterministic `effect_unknown` evidence. | Open. |
| F07-07 | P1 | D3-08B authorization-sensitive UI has not begun. | Approval pending/denied/expired/consumed and Receipt uncertainty must be rendered from canonical facts, not inferred front-end state. | Open; gated by 07 exit. |
| F07-08 | P1 | Authoritative evidence-index/manifest entries for D3-07 do not exist. | Green implementation tests alone would repeat the previous evidence-chain break. | Open. |
| F07-09 | P2 | No remote publish/export path is present, which is correct for this stage. | The boundary must remain explicit in code and tests so controlled local export cannot silently generalize. | ACCEPT as a negative constraint. |
| F07-10 | P0 | The current controlled allow-root draft may be narrower than the authoritative T3 fixture requirement. | The authoritative roadmap/vertical-slice text calls for a real approval writing a no-sensitive draft to a user-selected Workspace-outside test directory; the draft currently says harness-created root and rejects arbitrary user directories. | VETO until the scope is explicitly reconciled by Codex + Claude. |

## Scan conclusion

Codex first scan: F07-01 through F07-04 and F07-10 are hard blockers before any export
capability or mutation route is enabled. F07-05 through F07-08 must be resolved
in the implementation batch. F07-09 is an accepted scope boundary. Claude's
independent gate review is still required; no D3-07 implementation decision is
made by this scan.

Planning repair update: F07-01 now has both the Codex-only Markdown record
`docs/d3_07_entry_gate_decision_record.md` and the machine-readable record
`docs/evidence/v0.3.0-dev-d3-07-gate-decision.json`. It remains unresolved
because the required Claude joint signature is absent. The second planning scan
is recorded in `docs/evidence/v0.3.0-dev-d3-07-planning-gate.md`.

## Supplemental pre-gate runtime-surface scan

The later no-edit audit in `docs/d3_07_runtime_surface_audit.md` added F07-11
through F07-13: generic Approval/export schemas exist in the read-only contract
catalog, the mutation route must not expand before the joint gate, and the
handshake must keep external effects disabled. Existing exact route-inventory,
OpenAPI-authority, and handshake tests close the current negative-boundary
evidence; no route or runtime code was changed.

Product-decision update: F07-10's interpretation is now launcher/CLI user
selection with an opaque browser id; a harness root is test support only and
native picker remains post-dev. The later consistency scan resolves F07-16
through F07-19 as design decisions and adds F07-20: a positive write probe
cannot run before authorization. A subsequent authority recheck adds F07-21:
“dangerous target” has no enumerated canonical policy or selected-root
emptiness/collision rule. The export-subject audit then adds F07-22 through
F07-25 for the closed Relation mapping, typed request composition,
denial/expiry Run terminalization, and missing exact draft-report Artifact.
The selection-registry audit adds F07-26 through F07-31 for persistence/restart,
Windows handle identity, TTL/reuse, real CLI transport, restart classification,
and memory/SQLite coordination. The later product decision in
`docs/d3_07_plan_aligned_decisions.md` closes the product-choice portion of
F07-20 through F07-31, including a durable fence before all external effects,
fixed-local/empty target restrictions, public-only renderer inputs, irreversible
persisted commitments and a 60-minute one-session/one-attempt selection. These
updates do not change this first scan's historical findings or authorize runtime
implementation; Claude review, joint 07-00 ACCEPT and implementation evidence
remain absent.
