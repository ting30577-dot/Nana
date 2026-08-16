# Nana D3 full plan and boundaries

Status: D3-05 joint ACCEPT; D3-06 local implementation ACCEPT, independent
Claude exit unavailable; D3-07 implementation remains gated. The current
planning continuation is GPT-only by explicit product-owner instruction:
Claude is not called, retried, or awaited for this plan revision.

## 1. D3 outcome

D3 proves that D2's canonical execution facts can support the complete minimum
React development journey without moving authorization, execution, or truth
into the browser:

`create → provenance → editable Plan → locked test Run → Activity → Artifact →
Finding draft → one-time Approval → controlled external draft export → Receipt`

D3 is complete only when the journey passes ten consecutive real-browser E2E
runs with no retry. A fixture viewer, attractive UI, or green narrow unit suite
cannot substitute for the journey.

## 2. Frozen global boundaries

- UI and D3 queries consume D2 facts; they never re-derive authorization from
  PolicyGrant/Approval.
- Mutations use typed commands and delegate admission, scheduling, budget,
  execution, and Receipt semantics to D2.
- The frozen D0 app is not mounted or physically merged into runtime.
- One new authenticated runtime factory is the sole HTTP/OpenAPI authority.
- Before canonical runtime is reconciliation-ready, only exact public
  health/handshake routes respond; query, SSE, and mutation return not-ready.
- Browser SSE is authenticated `fetch + ReadableStream`, with strictly
  increasing but not necessarily dense Event IDs.
- The offline fixture adapter is not a server or second client contract; it
  feeds the same pure reducer used by the runtime UI.
- `effect_unknown` is a quarantined incident, never success and never locally
  dismissible/retryable/resumable.
- D2's frozen unittest security claim does not apply to T3 export.
- Alpha.1 counterexamples, three implementations, property tests, benchmark,
  Finding review, and final Decision remain excluded.
- Current canonical schema authority is v6. If a stage needs a schema change,
  that earliest stage owns the migration, failure rollback, read ceiling,
  old→new round-trip, registry/contract stability, and generated-client
  evidence; schema work may not be deferred silently to a later stage.
- D3-00 owns the Event/outbox/replay semantic contract. D3-03 proves it in the
  query/reducer layer and D3-04 proves it in a real browser; neither stage may
  redefine it.

## 3. Mandatory review protocol for every stage

Each stage follows the same sequence and may not interleave scanning with
repairs:

1. **Entry check**: confirm previous stage evidence and scope boundaries.
2. **Implement to candidate completion**: write tests and the smallest complete
   implementation for that stage.
3. **Full scan**: inspect every requirement, changed file, relevant upstream/
   downstream boundary, error path, test claim, and evidence statement. Do not
   edit during this scan.
4. **Consolidated findings**: after the scan ends, list all findings as
   `F<n>` with severity, evidence, consequence, and proposed correction. Mark
   each important decision ACCEPT, VETO, or NOT CONSENSUS.
5. **Batch repair**: resolve findings one by one, preferably red test first.
6. **Final re-review**: repeat the full checklist against the repaired state;
   do not only rerun the tests that originally failed.
7. **Evidence closure**: focused strict-warning tests, full Python regression,
   TypeScript check, browser tests where applicable, compileall, diff check,
   stage summary, and authoritative-sync summary.
8. **Claude review**: every stage exit packet goes to Claude after local final
   re-review. Any material objection reopens the stage and repeats steps 3–7.

For the current GPT-only planning continuation, the normal Claude-review step
is intentionally not invoked. This exception applies only to maintaining the
plan and its evidence references; it does not close an implementation stage,
change a joint decision, or authorize a gate.

No stage is `complete` merely because its implementation tests pass.

## 4. Stage decomposition

### D3-00 — design convergence and decomposition

**Purpose:** freeze the single D3 journey, architecture boundaries, review
protocol, complete stage order, and deferred scope.

**Entry:** D2 joint ACCEPT and handoff v3.

**Deliverables:**

- Codex and Claude independent proposals;
- reciprocal review and explicit decision table;
- this full phase plan;
- R1 Approval transaction, R2 sparse Event ID, R3 fixture contract decisions;
- R4 export enablement gaps explicitly recorded.
- freeze these exact R-level contracts:
  - **R1:** Approval decision, Action authorization, authorization Event/outbox,
    durable material, consumption, and stable command result commit in one D2
    admission-owned transaction; a two-transaction decide→consume flow is VETO;
  - **R2:** delivered committed Event IDs are stable and strictly increasing but
    not dense; integer holes are legal; duplicate IDs are idempotent; decreasing
    new IDs fail closed; snapshot cursor is read in the same SQLite transaction;
  - **R3:** one authenticated runtime HTTP/OpenAPI authority; offline fixture is
    a build/test data adapter for the same types/reducer, never a second server,
    client, production route, or auth mode;
  - **R4:** export transaction/idempotency/effect_unknown skeleton is accepted,
    but actual external write enablement remains disabled until D3-07 jointly
    freezes atomic-replace fallback and its security gate;
- freeze the existing D1/D2 Event+outbox transaction, Artifact reconciliation,
  command-result replay, action-authorization, and schema-v6 contracts as D3
  inputs rather than claiming D3-05 introduces them;
- freeze journey projection keys and the schema-migration ownership rule.
- freeze R1 stage ownership: D3-06's frozen T2 locked-test uses only the frozen
  PolicyGrant admission path and never requests/consumes one-time Approval;
  D3-07 is the first D3 stage to implement and prove the combined one-time
  Approval decision→Action authorization→consumption transaction for T3 export;
- freeze Workspace lock persistence: OS handle ownership is authoritative and
  is intentionally not stored as a SQLite lock row or trusted marker. Schema v6
  already includes the Event/outbox/Artifact reconciliation inputs used by
  D3-01, so D3-01 requires no schema migration. A later metadata hint may never
  substitute for the OS lock.

**Exit:** Claude accepts the decomposition or unresolved items are scoped to an
explicit later decision gate without weakening the final D3 journey.

### D3-01 — Workspace ownership lifecycle

**Purpose:** prove there is exactly one writable owner and readiness/close order
is fail-closed.

**Deliverables:**

- resolved Workspace identity and OS-exclusive lock;
- lock before writable SQLite/migration;
- reconciliation before ready;
- second instance rejection;
- shutdown order: stop writers → SQLite/WAL close → lock release;
- startup failure cleanup;
- real lock-owner child-process crash release and restart recovery (no HTTP
  runtime dependency);
- close failure retains ownership.
- integrate the real D1 Artifact reconciler under the frozen Event/outbox
  contract; a callback-only ordering test is insufficient for exit.
- no SQLite lock table or persistent ownership marker; the OS handle is the
  only ownership authority, so this stage has no canonical schema migration.

**Review focus:** path identity/aliasing, Windows handle correctness, reparse
points, partial initialization, close-failure recoverability, child-process
handle cleanup, and tests that prove real cross-process behavior.

**Exit:** strict ResourceWarning test passes; real D1 reconcile success/failure
is ordered before ready; and no code path in the new D3 runtime opens canonical
writable SQLite outside this ownership boundary. Legacy/test helpers are
inventoried rather than misreported as production owners.

### D3-02 — authenticated runtime authority and readiness

**Purpose:** create the sole D3 HTTP/OpenAPI authority without mounting the D0
app or weakening D1 default-deny security.

**Deliverables:**

- new runtime factory owned by WorkspaceRuntime;
- explicit startup/not-ready/ready/draining health model;
- exact public route inventory;
- default-deny auth for all other routes before routing/redirect;
- exact loopback Origin CORS/preflight for required methods and headers only;
- canonical query/SSE/mutation not-ready gate;
- regenerated runtime OpenAPI snapshot and TypeScript client;
- D0 frozen app/manifest regression remains intact;
- no mutation route yet.
- real authenticated runtime-process startup/crash/restart tests under the
  D3-01 ownership lifecycle; this is distinct from D3-01's lock-holder process
  crash test.

**Review focus:** middleware ordering, trailing slash/redirect bypass, anonymous
OPTIONS, Host/Origin ambiguity, duplicate headers, schema authority, startup
race, and shutdown requests.

**Exit:** route inventory/security matrix passes and the generated client has
one authority.

### D3-03 — canonical read models, consistent snapshot, and reducer

**Purpose:** project the complete frozen journey from canonical facts before
adding browser mutations.

**Deliverables:**

- task-oriented bootstrap snapshot containing Workspace status, Inquiry,
  Resource/Locator/Claim/Evidence, Plan revision, Run/Action, Activity,
  Artifact/Finding, Needs You, and Receipt views;
- snapshot high-water Event ID read in the same SQLite transaction;
- shared pure TypeScript reducer;
- sparse strictly increasing Event ID semantics;
- duplicate ignore, decreasing/out-of-order fail-closed, aggregate/run sequence
  validation, structured error preservation;
- offline replay fixture adapter using shared types/reducer;
- fixture/runtime projection equivalence test;
- no second OpenAPI or HTTP client.
- service-level Last-Event-ID tests prove that IDs such as `10, 12, 19` are
  legal, duplicates do not change projection, and decreasing new IDs fail
  closed; integer continuity is never used as a delivery-gap oracle.

**Review focus:** forbidden Grant/Approval re-derivation, snapshot/SSE race,
reconciled-versus-committed Artifact semantics, cancel/effect_unknown truth,
non-dense IDs, and canonical refresh.

**Exit:** D2 replay fixture and canonical database fixture produce the same
projection.

### D3-04 — read-only React Cockpit/Studio and browser SSE

**Purpose:** prove a real browser can understand D2 facts and recover across
refresh/disconnect before mutations are introduced.

**Design direction:** an industrial/editorial research control room. The
memorable element is a causality rail connecting Plan step → Action → Event →
Artifact/Finding → Receipt. It uses restrained motion, high information
clarity, distinctive typography, and no generic purple-gradient dashboard.

**Deliverables:**

- React/TypeScript build and test infrastructure;
- minimal Cockpit: Active, Needs You, Running/Failed;
- minimal Studio: provenance, Plan, Activity, tests, Artifact/Finding, Receipt;
- authenticated fetch/ReadableStream parser;
- cursor reconnect/backoff/duplicate handling and canonical refresh;
- real-browser Last-Event-ID tests repeat the sparse-ID, duplicate, disconnect,
  and replay semantics frozen in D3-00/D3-03;
- dirty editor state remains visibly non-canonical;
- explicit negative state language and accessible status indicators;
- keyboard navigation and 125%/150% DPI layout tests;
- fixture adapter excluded from production navigation/build.

**Review focus:** local-state truth leaks, optimistic terminal states,
EventSource use, auth header loss on reconnect, accessibility, focus order,
overflow/DPI, reduced motion, and error recovery.

**Exit:** real-browser read-only reload/reconnect and negative-state suite passes.

### D3-05 — canonical journey command writers

**Purpose:** implement the minimum domain mutations needed before execution,
without exposing raw Action or authorization decisions.

**Deliverables:**

- stable command ID/request hash/expected revision for every command;
- initialize/load the frozen dev Inquiry and provenance fixture using typed
  canonical writes;
- Resource, Locator, Claim/Evidence and relations needed by the journey;
- revise Plan using the D1 idempotent transaction pattern;
- DraftFinding linked to valid Evidence or a terminal Run;
- Events/outbox and command result in the same transaction;
- typed structured errors and replay-conflict behavior;
- no raw SQL/Action/capability/PolicyGrant browser input.

**Review focus:** incomplete cardinality, revision overwrite, rejected-command
replay binding, direct table shortcuts, cross-project leakage, and duplicate
side effects.

**Exit:** create/provenance/edit/draft mutations replay safely through the sole
runtime contract; execution remains disabled.

**Schema ownership:** if these writers require a canonical schema change,
D3-05 owns its migration and all migration evidence in this same stage. It may
not write ad-hoc tables or defer migration proof.

### D3-06 — locked test journey orchestration

**Purpose:** connect the UI journey to the real D2 frozen execution chain.

**Deliverables:**

- typed start/cancel commands;
- create Run/Action with frozen snapshot and exact locked test ID;
- delegate authorization to D2 admission;
- delegate claim/cancel to D2 scheduler;
- delegate execution/budget/Receipt to D2 executor/accounting;
- test result Artifact and terminal Finding linkage;
- accurate running, termination-in-progress, cancelled, failed, orphaned,
  budget-exceeded, and effect_unknown projections;
- crash/restart recovery without synthetic success;
- no generic shell/Python or unknown test target.
- authorization uses the frozen project PolicyGrant path for the exact T2
  `python.unittest.locked` Action. D3-06 does not create, decide, or consume a
  one-time Approval and therefore does not exercise R1's new combined Approval
  transaction.

**Review focus:** bypass of D2 primitives, race between start/cancel, reservation
leaks, double execution, terminal rollback, Receipt absence, Artifact
visibility, and UI false success. The joint design gate additionally requires
the owner-lane recovery coordinator as the sole terminal writer, CAS spawn
fence, unique Action-causation settlement transaction, deterministic
`unknown_pending` classification, Gate-G termination/reaping, and Gate-H audit.

**Exit:** frozen test journey succeeds, fails, cancels, and recovers through the
real runtime with Receipt/projection agreement.

### D3-07 — one-time Approval and controlled T3 export

**Purpose:** close the final dev journey side effect under a separately reviewed
security boundary.

This is the first D3 stage that implements and proves R1's one-time Approval
decision, Action authorization, and consumption transaction. Existing D2
approval admission evidence remains an input; D3-06 does not pre-exercise this
new combined writer.

**Entry decision gate:** Codex and Claude must first close the remaining R4
questions: unsupported atomic replace is fail-closed with no non-atomic
fallback; security gate scope/criteria/signers; effect_unknown operational
boundary. Until then external writes remain disabled.

**Deliverables after gate ACCEPT:**

- D2 admission-owned `DecideApproval(approved)` transaction for Approval
  decision, Action authorization, Approval/Action Event/outbox, durable
  authorization material, consumption, and stable command result; denied writes
  only decision/Event/outbox/result and there is no public `ConsumeApproval`;
- denial/expiry/action-change/replay fail closed;
- registered exact-target T3 export capability;
- user selects one Workspace-outside test root through the Nana launcher/CLI;
  it must be an existing dedicated empty target on a supported fixed local
  filesystem; the owner runtime gives the browser only a 60-minute/
  LocalSession-bound one-attempt opaque id plus redacted label; harness roots
  remain test support only;
- create a dedicated Export Run and exact Export Action whose frozen snapshot
  and canonical Relations bind the terminal algorithm Run, Finding and source
  Artifact; never reopen or prolong the D3-06 Run;
- create the exact public-only UTF-8/NFC/LF Markdown draft-report Artifact inside
  Workspace before its hash is approved; D3-06's `text/plain` test result is a
  source Artifact, not the report;
- compose the smallest existing canonical Command semantics behind a narrowed
  browser `RequestApproval` application request; do not expose raw Action,
  capability, path, bytes, hash or authorization inputs and do not silently add
  a parallel canonical Command;
- target/content hash in Action hash and one-time Approval;
- same-directory partial, flush/sync, supported atomic replace only;
- selection-time filesystem checks are read-only; after atomic Approval/
  consumption a durable first-write fence commits before the real probe or any
  external byte. Before-byte failure is empty-effect `failed`, proven-cleaned
  probe effects are recorded, and unverifiable residue/crash is
  `effect_unknown`; unsupported/unknown support never falls back and no retry or
  rebinding exists;
- exact before/after evidence and Receipt;
- path/reparse/size/media-type/canary/idempotency/crash security matrix;
- no remote publish and no D2 hostile-code safety claim; the capability
  candidate is T3 `export.draft_external`, never T4 `export.publish` or the
  `PublishExport` Command.
- **F07-10/F07-19 product resolution:** D3 uses launcher/CLI user selection and
  an opaque browser id; harness roots are test support and native picker stays
  post-dev. Joint security review and implementation evidence remain required.
- **F07-20/F07-21 product resolution:** durable fence-before-probe ordering and
  failure classes are frozen; target must be fixed-local/dedicated/empty and
  reject roots/system/Nana/Workspace/reparse/alias/UNC/network/cloud/collision/
  change with fixed filename/no overwrite. Joint review/evidence remain gates.
- **F07-22..F07-25 product resolution:** the existing Relation graph+snapshot,
  server-derived application composition, post-denial/expiry deterministic
  `CancelRun` and public-only exact renderer are frozen; see
  `docs/codex_d3_07_export_subject_audit.md`.
- **F07-26..F07-31 product resolution:** raw authority is process-only, durable
  commitments irreversible/non-locating, handle identity mandatory, lifetime
  60 minutes/LocalSession/one attempt, and reserve→commit→finalize is
  compensation rather than cross-resource atomicity; see
  `docs/codex_d3_07_selection_registry_audit.md`.

**Gate authority:** actual export enablement requires a dedicated D3-07 decision
record with both Codex and Claude `ACCEPT`. Either VETO or NOT CONSENSUS keeps
the capability disabled.

**Review focus:** decide/consume atomicity, external target aliasing, partial
write, changed target overwrite, unsupported filesystem behavior, secret
leakage, and Receipt effect accuracy.

**Exit:** no external target appears before one-time Approval; success is
verifiable and all uncertainty remains effect_unknown.

### D3-08A — core mutation UI and negative-state usability

**Purpose:** make the complete dev journey understandable without exposing
database objects or backend repair tools.

**Deliverables:**

- create/load, Plan edit/save, Run, cancel, Artifact, and Finding interactions;
- canonical command/result/Event reconciliation for every mutation;
- Needs You incident for effect_unknown with no retry/resume/mark-success/local-
  dismiss;
- keyboard-only complete journey;
- structured errors retain codes and actionable explanations;
- reload during every major state rebuilds correctly.

**Review focus:** button-to-state shortcuts, lost dirty edits, double submit,
stale revision, approval-content drift, false completion, focus traps, and DPI.

**Exit:** one real browser completes the journey and explains every state from
the UI alone through Finding draft; Approval/export remains disabled here.

### D3-08B — authorization-sensitive Approval/export/Receipt UI

**Purpose:** add the final side-effect interactions only after D3-07's joint
security gate passes.

**Deliverables:**

- pending Approval card derived from Action/Event/request material, not browser
  authorization inference;
- typed `DecideApproval` command with canonical `approved`/`denied` and exact
  Action/content/target summary;
- controlled export progress and Receipt causality;
- denial, expiry, changed content/target, duplicate submit, response loss,
  effect_unknown and reconciled result UX;
- explicit negative tests proving the UI cannot browse PolicyGrant, calculate
  Approval validity, retry an unknown effect, or mark success locally;
- keyboard/DPI/reload behavior for all authorization-sensitive states.

**Exit:** the real browser completes Approval→controlled export→Receipt without
any frontend authorization or terminal-state invention.

### D3-09 — ten-run gate, evidence manifest, and final Codex-only review

**Purpose:** prove D3 as a complete bridge rather than a collection of green
components.

**Deliverables:**

- ten consecutive clean-Workspace real-browser journeys with no retry;
- controlled export target per run and cleanup only after evidence capture;
- reload/reconnect, duplicate sparse Event IDs, cancel, failed/retry_of,
  second-instance denial, sidecar crash recovery, keyboard, 125%/150% DPI;
- compileall, full Python suite, D2 and D3 strict ResourceWarning suites,
  TypeScript, browser tests, diff check;
- D3 evidence manifest and digest;
- authoritative evidence-index/Vault sync or a byte-ready sanitized sync
  summary;
- Codex full exit scan, consolidated findings, repairs, final re-review;
- final Codex-only exit review and explicit decision under
  `docs/d3_codex_only_governance_decision_20260811.md`; historical Claude
  material remains historical and is not called, retried or relabelled.

**Exit:** all dev journey and D3 evidence gates pass; any unresolved material
issue is recorded as VETO or incomplete and D3 remains incomplete.

## 5. Dependency order

`D3-00 → D3-01 → D3-02 → D3-03 → D3-04 → D3-05 → D3-06 → D3-07 →
D3-08A → D3-08B → D3-09`

No later stage may be used to excuse a failed earlier invariant. Work may add
tests for later interfaces, but real mutation and external effect enabling must
respect the order above.

## 6. Current placement

> **Superseded historical snapshot (2026-08-10).** The placement text in this
> section below is retained only to preserve the earlier handoff record. It is
> not current authority. The live placement is recorded in section 8, the
> stage-gate matrix and the 2026-08-11 Codex-only governance decision.

- D3-00 through D3-04 are complete under their recorded stage gates.
- D3-05 has completed first scan, batch repair, second no-edit scan, evidence
  synchronization, and Claude joint exit: **ACCEPT**.
- D3-06 design has joint Claude/Codex **ACCEPT**. Implementation, first scan,
  batch repair, second scan, and local evidence sync are complete; Claude
  implementation-exit review is **尚未达成共识** because the configured
  gateway is blocked by the execution environment's network policy. D3-07
  remains gated until that independent review succeeds.
- D3-07 remains pending. `docs/d3_07_plan_aligned_decisions.md` freezes F07-20
  through F07-31 as product design, including the corrected 60-minute lifetime,
  strict fixed-local target, public-only renderer and durable-fence ordering,
  but this is not a joint implementation ACCEPT. D3-08A, D3-08B and D3-09
  planning remains on disk; the user directed this development run to pause once
  D3-07 is complete, so no later stage starts without an explicit resume.

D3-07 is further decomposed, for planning purposes, into 07-00 entry/security
gate, 07-01 Approval transaction, 07-02 exact T3 capability, 07-03 filesystem
atomic-write protocol, 07-04 matrix/projection evidence, and 07-05 scan/repair/
joint exit. See `docs/d3_07_stage_decomposition_draft.md`. This draft does not
enable export and is not a joint implementation decision.

The full stage-to-gate handoff is recorded in `docs/d3_stage_gate_matrix.md`.

The D3-06 Claude implementation-exit gate has now failed multiple ordinary
adapter retries with the same socket-permission error; the blocker is recorded
in `docs/d3_06_claude_exit_blocker.md`. D3-07 implementation remains disabled.

## 7. Current planning continuation (GPT-only)

> **Superseded historical boundary (2026-08-10).** The planning-only pause
> below was explicitly replaced by the owner's instruction to continue through
> D3-09 without calling, retrying or waiting for Claude. It must not be read as
> a current implementation prohibition or current gate state.

This section is an explicit operating-mode amendment for the current planning
continuation. It changes how the plan is maintained; it does not relax any
stage gate or authorize implementation.

- **Decision:** ACCEPT — GPT may complete the local D3 plan revision and
  consistency review without calling Claude. The historical Claude packets and
  transport records remain evidence only and are not treated as a new verdict.
- **Scope:** update the D3 plan, current placement, deferred-stage boundaries,
  and evidence synchronization notes to match the live workspace. Do not add
  product code, mutation routes, Approval/T3 capability registration, external
  write handling, or filesystem effects.
- **Canonical gate remains unchanged:**
  `docs/evidence/v0.3.0-dev-d3-07-gate-decision.json` remains authoritative;
  `joint_status=unresolved`, `implementation_authorized=false`,
  `capability_registered=false`, and `filesystem_write_authorized=false`.
- **Local review method:** GPT performs the entry check, no-edit scan, finding
  consolidation, plan-only repairs, final re-review, and evidence/diff checks.
  Any unresolved security or authorization question is recorded as
  `NOT CONSENSUS` or `VETO`; it is never silently promoted to `ACCEPT`.
- **Next planned work after this revision:** remain at D3-07 planning and
  readiness only. D3-08A, D3-08B, and D3-09 stay deferred. Real Approval,
  T3 export, or any external filesystem write requires a separately explicit
  authorization decision and must not be inferred from this GPT-only plan
  update.

**Plan-revision exit:** the plan text, stage placement, gate record, and
evidence index references are mutually consistent; no implementation or gate
flag changes are present; and the working-tree diff passes whitespace checks.

## 8. Live implementation placement (2026-08-13)

This section is current authority together with
`docs/d3_stage_gate_matrix.md` and
`docs/d3_codex_only_governance_decision_20260811.md`.

- D3-00 through D3-05: **ACCEPT**.
- D3-06: **Codex-only ACCEPT** for exact fixture-only T2
  `python.unittest.locked`; no hostile-code sandbox claim.
- D3-07: **Codex-only ACCEPT** for one-time Approval and exact
  `export.draft_external`. Historical `joint_status=unresolved` remains
  historical evidence, not a forged Claude result.
- D3-08A: **Codex-only ACCEPT** for typed core mutation UI.
- D3-08B: **Codex-only ACCEPT** for canonical Approval/export/Receipt UI.
- D3-09: **Codex-only ACCEPT**. Ten consecutive complete success journeys
  passed in new temporary Workspaces with Playwright `retries=0`; the complete
  25-test browser release/failure matrix, strict ResourceWarning suite, full
  regression, no-edit scan, manifests and final decision are synchronized.
- D3: **complete** within the frozen D3 scope. This does not authorize remote
  publish, arbitrary shell/Python, or a hostile-code sandbox claim.

Codex-only governance changes reviewer authority only. It does not weaken the
selection, transaction, first-write-fence, public renderer, crash uncertainty,
no-retry or external-effect boundaries.
