# D3-07 07-00 entry/security gate decision record

Date: 2026-08-09  
Scope: D3-07 controlled local T3 draft export only.  
Decision owner: Codex implementation owner; Claude joint signer pending.
Product decision source: `docs/d3_07_plan_aligned_decisions.md`.

## Independent Codex decision

| Gate | Decision | Rationale / required evidence |
|---|---|---|
| D3-06 joint implementation exit | VETO to D3-07 implementation | Claude's required independent exit review is unavailable; the sanitized packet has no joint verdict. |
| One-time Approval subject | ACCEPT as design invariant | Subject must bind the exact Action id and ActionHash; Action/content changes invalidate the Approval. Must be proven by the atomic writer tests. |
| Decide/authorize/consume atomicity | ACCEPT as frozen design | D3-00 R1 and the product-owner decision require `DecideApproval(approved)` to own decision, Action authorization, one-time consumption, Approval/Action Event/outbox and stable result in one transaction. No public `ConsumeApproval` exists. `denied` writes only decision/Event/outbox/result. Implementation evidence is still absent. |
| T3 capability grantability | ACCEPT as product design | Use the narrow unregistered T3 candidate `export.draft_external`, never T4 `export.publish`/`PublishExport`; one-time Approval only, no PolicyGrant path and no browser-selected capability. Registration and digest evidence remain gated. |
| Controlled allow-root | ACCEPT as product design | User selects the Workspace-outside test root through Nana launcher/CLI; runtime returns only an opaque id/redacted label to the browser. Harness roots remain test support. |
| Atomic replace support | ACCEPT as product design; implementation VETO | Selection checks are read-only. After atomic approval/consumption, a durable first-write fence commits before the real probe. No-byte failure is empty-effect `failed`; proven cleaned effects are recorded; unverifiable residue/crash is `effect_unknown`. No non-atomic fallback or retry. |
| Post-write uncertainty | ACCEPT as conservative invariant | Any crash or unverifiable effect after write begins is `effect_unknown`, never success or silent retry. |
| Remote publish | VETO | D3-07 is local controlled export only; no HTTP publish, cloud sync, or external service. |
| Authoritative T3 target scope | ACCEPT as product design | D3 uses a real user-selected Workspace-outside test directory supplied through the Nana launcher/CLI, never a harness root masquerading as selection. Runtime validation and joint security evidence remain required. |
| Export Run/Action ownership | ACCEPT as product design | Create a dedicated Export Run and exact Export Action linked by frozen snapshot and canonical Relations to the terminal algorithm Run, Finding and source Artifact. Never reopen or prolong the D3-06 Run. |
| User-selection mechanism | ACCEPT as product design | Launcher/CLI passes the selected directory to the owner runtime; after validation it issues a 60-minute/LocalSession-bound one-attempt opaque selection id and redacted label. Browser paths and pre-dev Tauri are forbidden. |
| Positive atomic-replace probe timing | ACCEPT as product design; joint evidence pending | F07-20 freezes read-only selection, atomic Approval/consumption, durable first-write fence, then real probe/report. Exact failed/effect-unknown classifications are mandatory. |
| Dangerous-target/collision policy | ACCEPT as product design; joint evidence pending | F07-21 requires an existing dedicated empty target on a supported fixed local filesystem; rejects roots/profile/system/Nana/Workspace overlap, every reparse/alias, UNC/network/mapped/cloud-sync, collision/change and unverifiable filesystems; fixed filename/no overwrite. |
| Export provenance graph | ACCEPT as product design; joint evidence pending | F07-22 uses existing producer and Artifact-lineage Relations plus a frozen snapshot; no direct Export Run→Finding/source-Run edge and no Registry extension. |
| Export request composition | ACCEPT as product design; joint evidence pending | F07-23 freezes the narrow Finding-version + opaque-selection application request with every security subject server-derived and no parallel canonical Command. |
| Denied/expired Export Run convergence | ACCEPT as product design; joint evidence pending | F07-24 freezes the minimal decision/expiry transaction followed by deterministic idempotent system `CancelRun` and startup reconciliation. |
| Exact draft-report Artifact | ACCEPT as product design; joint evidence pending | F07-25 freezes public-only canonical inputs and exact UTF-8/NFC/LF `text/markdown` bytes, ≤4096 bytes, renderer digest/DRAFT marker and 50-canary zero-match evidence before Approval. |
| Opaque-selection persistence | ACCEPT as product design; joint evidence pending | F07-26 keeps raw path/handle/clear identity/token in memory; only irreversible non-locating commitments, expiry and subject/binding facts may be durable. Restart invalidates selection; no rebinding. |
| Windows directory identity | ACCEPT as product design; joint evidence pending | F07-27 requires retained handle/final identity/local volume-file identity, component reparse/alias rejection, identity-based Workspace overlap and pre-write recheck; clear identity never leaves process memory. |
| Selection TTL/reuse | ACCEPT as product design; joint evidence pending | F07-28 freezes a 60-minute maximum bounded by LocalSession, clamped Approval expiry and one selection per Export Run/Action/attempt. |
| Real CLI selection source | ACCEPT as product design; joint evidence pending | F07-29 freezes an interactive pre-serve prompt with no path command-line argument; `test_harness` is distinct and no pre-dev Tauri is introduced. |
| Selection-loss restart states | ACCEPT as product design; joint evidence pending | F07-30 requires a committed first-write fence before every probe/byte; no-fence authorized states fail with empty effects, fenced states become `effect_unknown`, with no rebind/retry. |
| Memory/SQLite coordination | ACCEPT as product design; joint evidence pending | F07-31 freezes deterministic reserve→SQLite commit→finalize, exact-match rollback release and restart convergence, explicitly not a cross-resource atomic transaction. |

## Current joint status

This record is not a joint ACCEPT. Claude must independently review the
sanitized gate packet and either ACCEPT, VETO, or mark unresolved. Until then,
the capability remains unregistered, the runtime route remains absent, and no
filesystem write is authorized.

## Current local continuation status — 2026-08-10

The product owner temporarily paused Claude transport repair and instructed
Codex to continue the local, pre-gate work. The Codex implementation-readiness
matrix and boundary audit are complete, but this pause is not a joint review and
does not change any gate flag. No Approval/T3 writer, mutation route,
capability registration, or external byte path may be added while the machine
record remains unresolved. See
`docs/d3_07_implementation_readiness_matrix.md` and
`docs/evidence/v0.3.0-dev-d3-07-readiness-audit-20260810.md`.

## Entry criteria before implementation

1. D3-06 Claude implementation-exit review reaches ACCEPT.
2. Claude/Codex both sign the D3-07 07-00 gate.
3. The exact T3 capability contract is jointly frozen and its executable test
   plan is accepted; registration and implementation tests occur only after
   entry authorization.
4. Claude independently reviews the product-frozen F07-20/F07-21 fence/probe,
   failure-classification and strict fixed-local target policy.
5. Claude independently reviews the product-frozen F07-22 through F07-25
   provenance, application composition, denial/expiry convergence and
   public-only exact renderer.
6. Claude independently reviews the product-frozen F07-26 through F07-31
   storage/restart, Windows identity, 60-minute one-use lifetime, CLI ownership,
   durable fence and memory/SQLite coordination.
7. Codex and Claude jointly ACCEPT those frozen rules without weakening them.
8. The user-selection/allow-root/atomic-write protocol is
   specified in a sanitized implementation packet.

Capability registration, real filesystem-write evidence and implementation
tests are D3-07 implementation/exit requirements, not circular prerequisites to
the 07-00 implementation-entry decision.

## Current Codex-only implementation exit — 2026-08-11

The preceding joint-review prerequisites are retained as historical gate
evidence and are not current authority. The product owner explicitly withdrew
Claude as a prerequisite in
`docs/d3_codex_only_governance_decision_20260811.md`; the missing Claude result
has not been relabelled.

Codex completed the fresh entry review, implementation, consolidated repair,
strict/full verification and no-edit scan. F07-32 through F07-41 are closed in
`docs/d3_07_implementation_scan_findings_20260811.md`; the exit decision is
`docs/d3_07_codex_implementation_exit_20260811.md`.

**Current D3-07 status: Codex-only ACCEPT.** The exact
`export.draft_external` capability is registered and its fixed-local writer is
authorized only within this stage contract. D3-08A is the next stage.
