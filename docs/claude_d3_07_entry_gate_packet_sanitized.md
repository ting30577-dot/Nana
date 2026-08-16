# Claude review packet — D3-07 07-00 entry gate

This packet is sanitized and planning-only. It contains no absolute paths,
user identity, credentials, environment values, or machine identifiers.

## Preconditions

D3-06 implementation has local evidence but its independent Claude exit review
is still unresolved. D3-07 must not register or enable an export capability
until that gate is ACCEPT.

The product owner has now frozen F07-20 through F07-31 in
`docs/d3_07_plan_aligned_decisions.md`. The rules below include those corrections
and request an independent security challenge; they are not implementation
evidence or a joint ACCEPT.

## Proposed 07-00 invariants

1. The one-time Approval subject is the exact Action id plus ActionHash. Any
   Action/content/target change invalidates the Approval.
2. `DecideApproval(decision="approved")` commits Approval decision, durable
   Action authorization, one-time consumption, Approval/Action Event/outbox and
   stored command result in one owner-lane SQLite transaction through D2
   admission primitives. There is no public `ConsumeApproval`. `denied` commits
   only decision/Event/outbox/result and never authorization or consumption.
3. The reversible local draft write uses the unregistered T3 capability
   candidate `export.draft_external`, never the T4 `export.publish` or
   `PublishExport` command. It is one-time Approval only, `grantable=false`, and
   the browser cannot choose a capability or authorization reference. Local
   success is proven by Action/Receipt facts, not a remote-publish claim.
4. After the algorithm Run is terminal, a separate Export Run and exact Export
   Action are created. Their frozen snapshot and canonical Relations bind the
   source algorithm Run, Finding and source Artifact/content hash. The algorithm
   Run is never reopened or prolonged, and export failure cannot rewrite it.
5. During D3 the user selects one existing dedicated empty Workspace-outside
   directory on a supported fixed local filesystem through an interactive Nana
   launcher/CLI prompt. The owner issues a 60-minute/LocalSession-bound,
   one-Export opaque id plus redacted label; the browser never submits or
   receives a path. Harness roots remain explicit test support and Tauri remains
   post-dev.
6. Selection checks are read-only. After atomic Approval/authorization/
   consumption, a durable first-write fence must commit before the real
   atomic-replace probe or any external byte. Probe success permits the report;
   before-byte failure is empty-effect `failed`, proven-cleaned probe bytes are
   recorded as `failed`, and unverifiable residue/crash is `effect_unknown`.
   No non-atomic fallback, retry or target rebinding is permitted.
7. Target validation rejects volume/profile/system/Nana roots, Workspace
   overlap in either direction, every reparse/mount/SUBST/short-name/case alias,
   UNC/network/mapped drives, known cloud-sync roots, unsupported/unverifiable
   filesystems, non-empty/colliding/changing targets and overwrite. A fixed
   filename and handle-identity recheck are mandatory.
8. Raw path, directory handle, clear volume/file identity and opaque token stay
   in process memory. Only irreversible non-locating commitment/expiry/subject/
   binding/version facts may be durable. Restart never rebinds a selection;
   no-fence authorized/claimed work fails empty, while a durable fence makes
   lost-effect proof `effect_unknown`.

## Product-frozen subjects requiring independent review

- F07-22: the closed Relation Registry has no direct Export Run→Finding or
  Export Run→source-Run edge. The frozen design validates existing algorithm-Run
  producer edges, uses only existing Artifact producer/lineage Relations, and
  freezes all source ids/hashes in the Export Run snapshot.
- F07-23: current browser `StartRun` is T2-only and D3-00 forbids a silent new
  canonical Command. The frozen design exposes a narrowed `RequestApproval`
  application request and composes existing canonical Command semantics with
  all Action/security material server-derived. The current specialized
  `StartRun` already creates the wrong T2 Action, so the composition must reuse
  internal domain primitives under one outer idempotency transaction rather
  than invoke that handler or nest multiple command transactions.
- F07-24: denied/expired Approval must not leave the Export Run running, but the
  denied transaction may not write Run state. The frozen design invokes a separate
  deterministic system `CancelRun` after commit and during restart recovery.
- F07-25: D3-06 produces a test-result Artifact, not the exact Markdown draft
  report. A deterministic versioned renderer must commit and hash the Workspace
  Artifact before the Approval subject is created. Only canonical `public`
  inputs are eligible; escaping prevents injection and is not privacy
  sanitization. The frozen renderer uses UTF-8/NFC/LF, a 4,096-byte ceiling,
  allowlisted plain-text Inquiry/Finding fields,
  terminal Run/Receipt summary and source Artifact id/hash only; it excludes
  paths, source bytes, stdout/stderr, environment/provider data and URLs, then
  requires zero credential-canary matches.
- F07-26..F07-31 freeze process-only raw target authority, retained-handle final
  identity, irreversible durable commitments, a 60-minute/LocalSession one-
  Export binding, interactive CLI distinct from harness, no restart rebinding,
  fence-based failure classification and explicit reserve→SQLite commit→finalize
  compensation without claiming a cross-resource atomic transaction.
- The current `approvals` and `actions` rows have no revision column. Approval
  and Action concurrency must use their append-only Event aggregate versions.
  The existing Approval admission method opens its own transaction and assumes
  an already-approved row, so D3-07 must extract a private in-transaction
  primitive. Both the one-time consumption and immutable authorization records
  can bind the same `action.authorized` Event; the denied branch creates neither.

## Questions for independent review

- Does the frozen Approval transaction correctly implement the already-accepted
  D3-00 R1 boundary without a public consume command?
- Is the independent Export Run plus launcher/CLI opaque-selection contract a
  sufficient reading of the authoritative user-selected test-directory fixture?
- Does the frozen Approval→durable-fence→probe ordering and three-way failure
  classification prove zero unapproved effects and honest uncertainty?
- Is the strict fixed-local/empty target policy complete against root/system/
  Nana/Workspace/reparse/alias/UNC/network/cloud/collision/change risks without
  leaking machine identity?
- Does the product-frozen existing-edge provenance graph close F07-22 without a
  Registry extension?
- Does the narrowed `RequestApproval` composition close F07-23 without creating
  a parallel canonical Command?
- Does post-commit deterministic `CancelRun` correctly close F07-24 while
  preserving the exact denied transaction?
- Does the public-only exact renderer/provenance/50-canary contract close
  F07-25 without treating escaping as privacy sanitization?
- Do the F07-26..F07-31 selection registry, handle identity, lifetime, CLI,
  60-minute lifetime, restart and compensation rules fail closed without
  persisting a raw path, opaque token or clear machine identity?
- Should any invariant be VETOed or strengthened before implementation?
- What evidence must be required for the allow-root, atomic-replace probe,
  changed-target race, and post-write crash matrix?

Return an explicit `ACCEPT`, `VETO`, or `尚未达成共识`, with evidence, risks,
counterarguments and required repairs. Do not modify files.

Codex's separate implementation proposal is in
`docs/codex_d3_07_independent_design.md`; please challenge its flow and nine
independent-review questions rather than treating product acceptance as a joint
security verdict.

The product-owner-frozen typed Approval contract is additionally recorded in
`docs/codex_d3_07_approval_contract_design.md`; it is design-only and does not
authorize runtime or filesystem changes.

The current-code transaction and integration map is in
`docs/codex_d3_07_transaction_integration_map.md`; it is design-only and must be
reviewed for nested-transaction, aggregate-version and replay correctness.

The independent F07-10 negative/positive test matrix is in
`docs/codex_f07_10_test_matrix_design.md`; it is also planning-only.

The product-frozen selection registry and restart design is in
`docs/codex_d3_07_selection_registry_audit.md`; it is planning-only.
