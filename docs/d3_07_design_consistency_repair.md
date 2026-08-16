# D3-07 design-consistency scan and repair

Date: 2026-08-09  
Scope: no-edit scan followed by documentation-only repair; runtime remains
disabled.

## Findings before repair

| ID | Severity | Finding | Consequence | Decision |
|---|---|---|---|---|
| F07-14 | P1 | The older Codex independent proposal used `RequestExport`, `DecideExportApproval`, and `ExecuteApprovedExport`, while the newer typed contract uses `RequestApproval`, `DecideApproval`, and `ConsumeApproval`. | Reviewers could treat two different command unions as the proposed interface. | VETO ambiguity; normalize names. |
| F07-15 | P0 | The older proposal described harness-only allow-root as if final, while F07-10 keeps the authoritative user-selected target unresolved. | A stale proposal could silently narrow the T3 acceptance criterion. | VETO final harness-only scope. |

## Batch documentation repair

- Updated `docs/codex_d3_07_independent_design.md` to use the typed Approval
  command names and to describe `ConsumeApproval` as the candidate D2-owned
  operation.
- Marked the harness-created allow-root as a deterministic candidate, not a
  final T3 scope.
- Kept arbitrary browser paths, shell, network, and remote publish forbidden.

## Second no-edit scan

The proposal now matches `docs/codex_d3_07_approval_contract_design.md` and the
F07-10 reconciliation document. No runtime or OpenAPI route changed. F07-14 is
resolved as documentation consistency; F07-15 remains unresolved until Claude
and Codex jointly accept the target interpretation.

## Third no-edit scan — prior consistency claim withdrawn

The preceding second-scan sentence is retained as historical evidence, but its
claim that the two proposals match is withdrawn. A line-by-line comparison with
the authoritative command catalog and the implemented D2 admission boundary
found additional pre-implementation conflicts:

| ID | Severity | Finding | Evidence / consequence | Current decision |
|---|---|---|---|---|
| F07-16 | P0 | Transaction ownership is contradictory. | `codex_d3_07_approval_contract_design.md` exposed `ConsumeApproval` but also said `DecideApproval` itself commits decision, authorization, consumption, Event/outbox and result. `codex_d3_07_independent_design.md` instead separated decision from a later consume operation. D2 `authorize_with_approval` only consumes an already-approved Approval and requires an idle connection. | **Resolved as design repair.** D3-00 R1 already jointly VETOed two-transaction decide→consume. Product owner reconfirmed that `DecideApproval(approved)` owns decision + authorization + one-time consumption atomically; there is no public `ConsumeApproval`. `denied` writes decision/Event/outbox/result only. Implementation remains gated. |
| F07-17 | P0 | The proposed `RequestApproval` assumes an existing export Action, but no accepted journey command creates the T3 export Run/Action. | D3-06 creates only the locked T2 Action and settles its Run terminal. D2 admission requires an Action attached to a Run, and the scheduler only claims Actions whose Run is `running`. Appending an export Action after that Run is terminal therefore cannot execute through the accepted scheduler. | **Resolved as product design.** Create an independent Export Run and exact Export Action after the algorithm Run/Finding/Artifact are terminal; bind them through frozen snapshot and canonical Relations. Never reopen or prolong the D3-06 Run. Implementation remains gated. |
| F07-18 | P1 | The draft concurrency and decision tokens do not match a frozen canonical schema. | The draft named `expected_action_revision` and `expected_approval_revision`, while the tables have no revision columns; only Event aggregate versions exist. It also used `approve/deny`, whereas the canonical generic command uses `approved/denied`. | **Resolved as contract design.** Use inherited `expected_revision` as the current aggregate/Event version and canonical `approved/denied` literals. Implementation remains gated. |
| F07-19 | P0 | The owner of user directory selection was not implementation-compatible. | The earlier candidate depended on a native picker even though Tauri is post-dev; browser absolute paths and harness-as-user-selection are both invalid. | **Resolved as product design.** D3 launcher/CLI accepts the user-selected Workspace-outside test directory; the later F07-28 decision fixes the opaque id at 60 minutes/LocalSession/one attempt. Browser receives only id/redacted label; native picker remains post-dev. Implementation remains gated. |
| F07-20 | P0 | A positive atomic-replace probe before Approval would itself be an unauthorized T3 write. | Real proof requires creating/renaming a file in the Workspace-outside directory, while D3-00 requires proof that no external file appears before authorization and authority classifies Workspace-outside writes as T3. | **Resolved as product design.** Selection performs read-only checks; after atomic approval/consumption the owner commits a durable first-write fence before the real probe. No-byte failure is `failed` with empty effects; proven cleaned probe effects are recorded as `failed`; unverifiable residue/crash is `effect_unknown`. No fallback or retry. Joint evidence remains gated. |
| F07-21 | P0 | “Dangerous target” had no canonical executable policy. | An under-specified list could under-protect user data or silently broaden the fixture. | **Resolved as product design.** D3 requires an existing, dedicated, empty directory on a supported fixed local filesystem and rejects roots/profile/system/Nana/Workspace overlap, every reparse/alias, UNC/network/mapped/cloud-sync targets, non-empty/colliding/changed targets and unverifiable filesystems. Fixed filename, no overwrite. Joint evidence remains gated. |
| F07-22 | P0 | The closed Relation Registry has no direct Export Run→Finding/source-Run edge. | Reusing `run_retry_of_run` or writing an unknown relation would falsify provenance and violate authority 05. | **Resolved as product design.** Use only `run_produces_finding`, `run_produces_artifact` and `artifact_derived_from_artifact`; freeze Finding/Run/Artifact ids, versions and hashes in the Export Run snapshot. No Registry extension. |
| F07-23 | P0 | No accepted typed composition creates the Export Run, exact Action and Approval subject. | Browser `StartRun` is T2-only; raw Action/capability/hash input is forbidden; D3-00 G forbids silently inventing a parallel canonical Command. | **Resolved as product design.** A narrow journey/application `RequestApproval(command_id,finding_id,expected_revision,target_selection_id)` composes existing canonical semantics; the server derives every Run/Artifact/Action/capability/hash/effect field. |
| F07-24 | P0 | A denied/expired Approval would leave the independent Export Run non-terminal. | Terminalizing the Run inside the denied `DecideApproval` transaction violates the frozen “denied writes only” branch; omitting it leaks a running Run. | **Resolved as product design.** After the minimal denied/expired transaction, a deterministic system `CancelRun` with fixed causation/correlation and command id cancels the waiting Action/Run; startup reconciliation replays it idempotently. |
| F07-25 | P0 | No canonical non-sensitive draft-report Artifact currently exists. | D3-06 produces a `text/plain` test result, not the required draft report; rendering bytes after Approval would invalidate the ActionHash. | **Resolved as product design.** Only canonical `public` inputs are eligible; a fixed UTF-8/NFC/LF `text/markdown` renderer (≤4096 bytes, one trailing LF, DRAFT marker, digest, 50 canaries) commits exact bytes before Approval. Escaping prevents injection and is not privacy sanitization. |
| F07-26 | P0 | Opaque-selection persistence/restart semantics were not frozen. | Canonical SQLite must not contain a raw user path, while a memory-only record disappears on restart. | **Resolved as product design.** Raw path, handle, clear volume/file identity and opaque token remain process-only. SQLite may persist only irreversible non-locating identity/target commitments, expiry, subject/binding and Event versions. Restart invalidates selection; no old-Action rebinding. |
| F07-27 | P0 | String/`Path.resolve` checks cannot prove Windows directory identity. | Reparse/mount/SUBST/short-name/case aliases and replacement races can evade prefix checks. | **Resolved as product design.** Retain a directory handle; use final identity and local volume/file identity, reject every reparse component/alias, compare Workspace overlap by handle identity and recheck before fixed-child write. Clear identities never leave process memory. |
| F07-28 | P1 | Selection TTL/reuse cardinality were unspecified. | Reuse can bind multiple subjects; indefinite lifetime is not short-term. | **Resolved as product design.** Maximum 60 minutes and current LocalSession lifetime; Approval expiry is clamped; one selection binds one Export Run/Action and closes on terminal/expiry/session/drain. Every attempt requires a fresh selection. |
| F07-29 | P1 | Real launcher/CLI raw-path transport was unspecified. | Browser input and harness impersonation are forbidden; command-line arguments can expose raw paths in process listings. | **Resolved as product design.** Interactive pre-serve launcher/CLI prompt only; no path argument. Separately labeled `test_harness` injection cannot claim `user_selected=true`; no pre-dev Tauri. |
| F07-30 | P0 | Requested/approved/writing restart outcomes were incomplete. | A new selection cannot safely resume an old approved Action and a post-write crash cannot be retried. | **Resolved as product design.** Durable first-write fence must commit before any probe/byte. Requested/denied states expire/cancel; approved/claimed without fence fail with empty effects; a durable fence converges to `effect_unknown`; no rebind/retry. |
| F07-31 | P0 | In-memory selection binding and SQLite CommandResult cannot commit atomically. | A false cross-resource atomicity claim would hide reservation/commit crash windows. | **Resolved as product design.** Use deterministic reserve→SQLite atomic commit→in-memory finalize with exact-match rollback release and explicit restart convergence; this is a compensation protocol, never a cross-resource atomicity claim. |

No runtime, route, capability, schema, or filesystem writer changed during this
third scan or the product-decision repair. The product decision in
`docs/d3_07_plan_aligned_decisions.md` now freezes F07-20 through F07-31 with
the corrections above. The missing D3-06 Claude exit, the independent review of
these frozen rules and the missing joint 07-00 signature still block
implementation. The evidence and composition for F07-22 through F07-25 are recorded in
`docs/codex_d3_07_export_subject_audit.md`; F07-26 through F07-31 are recorded in
`docs/codex_d3_07_selection_registry_audit.md`.
