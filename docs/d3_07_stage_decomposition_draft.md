# D3-07 stage decomposition (Codex draft; not yet jointly accepted)

This is a planning decomposition only. D3-07 implementation is blocked until
D3-06 has an explicit Claude implementation-exit decision. No export capability
is enabled by this document.

## 07-00 — entry/security decision gate

Freeze the R1/R4 questions before code: one-time Approval subject is the exact
Action id plus ActionHash; `DecideApproval(approved)` owns decision,
authorize/consume, Approval/Action Event/outbox and result in one owner-lane
SQLite transaction; `denied` cannot authorize or consume; unsupported or
unknown atomic replace has no fallback;
non-atomic fallback is forbidden; `effect_unknown` is never projected as
success; controlled local export is not remote publish. Record signers,
criteria, and explicit ACCEPT/VETO/尚未达成共识.

## 07-01 — typed Approval command and atomic admission

Add only the typed request/response needed for the dev export journey. Reuse D2
admission and transaction primitives; do not duplicate PolicyGrant/Approval
logic. Test action-hash binding, content mutation invalidation, expiry, denial,
replay, one-time consumption, actor binding, and response-loss replay.
F07-22 through F07-25 are product-frozen as the existing Relation graph plus
Export Run snapshot, no-new-canonical-Command application composition,
separate deterministic denied/expired Run convergence, and a public-only exact
deterministic draft-report Artifact. The contract is documented in
`docs/codex_d3_07_export_subject_audit.md`.

## 07-02 — exact T3 export capability contract

After the joint gate, register only the narrow T3 candidate
`export.draft_external` with digest, schema, one-time Approval mode,
`grantable=false`, provider mode, effect ceiling, output media type, size cap,
and fixed canary fixture. It is never the T4 `export.publish` capability or the
`PublishExport` Command. Arbitrary filename, shell, network, remote publish,
PolicyGrant authorization, and a harness root masquerading as user selection
remain forbidden. The Action hash includes the resolved target selection
identity and content hash.

## 07-03 — filesystem boundary and atomic write protocol

During D3 the user selects one existing dedicated empty Workspace-outside test
root on a supported fixed local filesystem through an interactive Nana
launcher/CLI prompt. The owner runtime validates it and issues a 60-minute/
LocalSession-bound one-attempt opaque id; browser requests contain no path.
Reject roots/profile/system/Nana/Workspace overlap, every reparse/identity alias,
UNC/network/mapped/cloud-sync targets, unsupported/unverifiable filesystems,
non-empty/colliding/changing targets and media/size violations. Use a fixed
filename and no overwrite. Selection-time checks are read-only. After atomic
Approval/consumption, commit a durable first-write fence before the real probe
or any external byte; the report proceeds only after the probe passes. Write
same-directory temp bytes, flush/sync, and use only the proven atomic operation.
Before-byte probe failure is empty-effect `failed`; proven-cleaned probe effects
are recorded as `failed`; unverifiable residue or post-fence crash is
`effect_unknown`; no fallback/retry/rebinding. F07-26 through F07-31 further
freeze raw path/handle/token/clear identity as memory-only, durable irreversible
commitments, handle-based Windows identity, explicit restart classification,
and reserve→SQLite commit→finalize compensation without claiming cross-resource
atomicity.

## 07-04 — matrix, crash, and projection evidence

Run the security matrix for path/reparse/size/media/canary/idempotency/replay,
atomic replace, crash points, changed target, secret leakage, and response loss.
Assert before/after artifacts, Receipt actual effects, budget settlement,
Approval consumption, Event/outbox, and conservative UI projection. Confirm no
remote publish and no D2 hostile-code claim.

## 07-05 — no-edit scan, repair, and joint exit

Codex scans every F# finding, lists all findings before edits, repairs them in a
single batch, reruns focused/D2/full/browser checks, performs a second no-edit
scan, updates the authoritative evidence index/manifest, and asks Claude for an
independent exit review. Any unresolved material issue keeps D3-07 disabled.

## Current decision

Codex draft decomposition: ACCEPT as a planning shape. Implementation and the
capability decision remain **尚未达成共识** until D3-06 joint exit and the
D3-07 07-00 security gate are both closed. The current Codex-only gate record
is `docs/d3_07_entry_gate_decision_record.md`; product rules are frozen by
`docs/d3_07_plan_aligned_decisions.md`, but neither record contains a capability
enable decision.
