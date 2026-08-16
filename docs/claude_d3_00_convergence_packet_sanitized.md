# Nana D3-00 convergence packet (sanitized)

Purpose: one minimal packet for Claude's convergence review after independent
proposals and Codex's reciprocal review. It contains no credentials, literal
authorization values, environment values, user-specific absolute paths,
machine identity, private network information, or hardware identifiers.

Claude is a read-only equal co-designer. It must not edit files or claim local
test execution. Every material decision must be ACCEPT, VETO, or NOT CONSENSUS.

## Neutral verified facts

- D0/D1/D2 are complete within their recorded scopes. D2 only proves the
  trusted frozen `python.unittest.locked` surface, not a hostile-code sandbox.
- Fresh baseline: compileall passes; Python 269 tests OK; TypeScript strict
  check passes from the web package directory. The legacy PySide6 shutdown
  warning remains isolated but must be reconsidered before real D3 write
  serving touches relevant handles.
- D3 facts are runs, actions, append-only action authorization material,
  Events/outbox, Receipts, Artifacts, idempotency results, lifecycle projection,
  structured errors, and the replay fixture.
- D3/UI must not query PolicyGrant/Approval to re-derive authorization, bypass
  D2 admission/scheduler/executor, synthesize terminal success, or generalize
  the frozen worker safety claim.
- Before real mutation serving: acquire OS Workspace lock before writable
  SQLite; migrate/reconcile before ready; second instance fails closed; stop
  mutations and writers, close SQLite/WAL, then release lock; test crash
  release/restart and exact ordering.
- Browser SSE uses authenticated fetch plus ReadableStream, ordered Event IDs,
  cursor reconnect, and client de-duplication. Native EventSource is forbidden.
- The frozen D0 app and D1 runtime/SSE app are currently separate. D3 must make
  an explicit runtime contract decision and regenerate the client.
- The web package has generated contracts only; React/browser E2E start in D3.
- The unique dev journey is create, provenance, editable Plan, locked test Run,
  Activity, Artifact, Finding draft, one-time Approval, external draft export
  Receipt. Alpha.1 work remains deferred.

## Codex independent proposal — complete decision content

Codex proposed six stop-line slices:

1. **Workspace lifecycle object — ACCEPT.** One owner controls resolved
   identity, OS lock, writable database, migrations, reconciliation, services,
   draining, database close, and lock release in that order. Lock contention
   fails closed. Fixture viewer is a separate non-writer mode.
2. **Runtime OpenAPI authority — ACCEPT with gates.** Create one new
   authenticated runtime factory as contract authority, preserve frozen D0
   inputs for regression, keep default-deny auth, regenerate snapshot/client,
   and test route inventory/exact-Origin preflight. Codex VETOes parallel
   hand-maintained UI schemas and silent runtime-only routes.
3. **Task-oriented read projections — ACCEPT.** Workspace status, active
   Inquiry/provenance, Plan revision, Run/Action/Activity, Needs You, Artifact/
   Finding, and Receipt detail. They display stored authorization/state facts
   and retain reconciled-Artifact recovery semantics.
4. **Journey application services over D2 — ACCEPT.** Only initialize/load the
   frozen fixture, revise Plan, start frozen locked-test journey, cancel via D2,
   draft Finding, request/decide exact one-time export Approval, and execute a
   separately registered exact-target T3 export capability. No raw Action,
   arbitrary capability, shell, Python, final Decision, publish, or delete.
5. **Replay-first React store — ACCEPT.** Consistent snapshot plus high-water
   cursor, ordered SSE reducer, de-duplication, gap/contract mismatch refresh,
   and explicit dirty editor state. No HTTP response synthesizes a terminal
   state.
6. **Focused research control room — ACCEPT.** Cockpit rail for Active/Needs
   You/Running/Failed and Studio for provenance, Plan, Activity, tests,
   Artifact/Finding, and Receipt. Causality is the visual organizing principle;
   style is subordinate to truth and accessibility.

Codex phases:

- D3-00 joint decisions;
- D3-01 Workspace lock lifecycle;
- D3-02 runtime contract/read projections;
- D3-03 React read surface/browser SSE;
- D3-04 frozen test journey mutations;
- D3-05 T3 export Approval/Receipt;
- D3-06 ten consecutive no-retry browser journeys and final evidence.

Codex principal risks: full journey is larger than viewer; T3 export is a new
security surface; frozen D0 manifest must be preserved; snapshot/SSE needs one
consistent high-water transaction; development auth bootstrap is not a Local
Web production security claim; Windows locks require real child-process crash
tests.

## Claude independent proposal — complete decision content

Claude proposed five layers: Workspace ownership/OS lock, D2 fact storage,
read models, minimal mutation application services reusing D2, and one
authenticated default-deny runtime HTTP/SSE app with React SPA.

Claude decisions:

- Workspace gate first: ACCEPT.
- Physically mounting/combining the frozen D0 app into runtime: VETO.
- One regenerated runtime contract/client: CONDITIONAL ACCEPT with auth and
  regression gates.
- fetch/ReadableStream SSE, no authorization re-derivation, no direct test
  subprocess, exact CORS, no optimistic truth, and ten no-retry E2E runs:
  ACCEPT.
- Suggested read models: Run list/detail, Activity, Artifact with recovery
  semantics, Finding, authorization status, Receipt.
- Suggested mutations: Run creation/start, Resource/Locator, Plan revision,
  Finding, one-time Approval, external export, all via D2.
- Suggested phases: lock; read projections/SSE/React shell; minimal mutation
  composition/runtime contract; full E2E negative states/DPI/keyboard/ten-run.

Claude raised five NOT CONSENSUS items:

1. whether D2 has a reusable mutation composition entry;
2. how one-time Approval durably creates action authorization without D3
   re-derivation;
3. evidence for global ordered Event/outbox cursor semantics;
4. whether canonical queries/SSE may run before reconciliation-ready;
5. the allowed user action for `effect_unknown`.

Claude also warned that missing public composition and a new React/E2E stack
may make D3 larger than expected, and that Windows shutdown ordering is risky.

## Codex reciprocal review and resolution evidence

### Physical merge versus contract authority

Codex accepts Claude's VETO: the frozen D0 application must not be mounted or
physically combined into runtime. “Merge” is narrowed to authority migration:
a new authenticated runtime factory owns runtime routes and generated OpenAPI,
while frozen D0 inputs remain regression evidence.

Proposed label: physical mount VETO; new runtime contract authority ACCEPT with
default-deny/regeneration/route-inventory gates.

### Open question 1 — mutation composition

D2 has reusable repository-internal primitives:

- capability admission by PolicyGrant or one-time Approval;
- scheduler claim/cancel;
- locked executor;
- budget and Receipt services.

It has no public or journey-level mutation composition. D3 adds a thin typed
orchestrator and missing canonical command writers, but delegates all
authorization, scheduling, budget, execution, and Receipt decisions to D2.
Browser contracts expose journey commands, never raw executable/Action/grant.

Proposed label: ACCEPT this boundary.

### Open question 2 — one-time Approval writer

D2's approval admission method is the canonical authorization writer. In one
transaction it validates stored Approval, full Action material, registry,
expiry, decision, hash, use count and consumption; changes the Action; appends
authorized Event/outbox; writes append-only authorization material/event
binding; and records consumption.

D3 must add typed RequestApproval/DecideApproval command writers because tests
currently seed Approval rows and there is no journey handler. Those writers
create/decide Approval facts, then call D2 approval admission for authorization.
The UI does not compute whether the Approval is valid.

Proposed label: ACCEPT with implementation gate.

### Open question 3 — Event/outbox order

Events use SQLite-assigned integer primary keys. Writers insert Event and its
outbox row in the same transaction. The stream joins outbox, filters IDs above
the cursor, and orders by Event ID. The D1 10,000-Event test verifies the actual
complete ID sequence across disconnect/reconnect plus aggregate versions and
Run sequences. The handoff freezes global append-only ID semantics. Network
delivery remains at-least-once, not exactly-once.

Proposed label: ACCEPT; evidence gap resolved.

### Open question 4 — reads before ready

- Standalone fixture/replay viewer may run without a writable Workspace owner.
- Canonical Workspace runtime exposes only exact public health/handshake startup
  state until lock, writable open, migrations, and reconciliation converge.
- Canonical query, SSE, and mutation routes return not-ready until then.
- A future schema-too-new read-only compatibility lifecycle is separate work,
  not an implicit startup shortcut.

Proposed label: canonical query/SSE before ready VETO; fixture viewer ACCEPT.

### Open question 5 — `effect_unknown` UX

Show a high-priority Needs You incident with Action/Run identity, Receipt,
effect violation, authorized versus actual/observed effects, artifacts,
structured error, timeline, and explicit quarantined/unproven language. Provide
no retry, resume, mark-success, or local dismissal. Reconciliation/compensation
requires a later typed Action and is not part of the frozen D3 journey.

Proposed label: ACCEPT this read-only incident boundary.

## Codex additional findings for Claude review

F1. A Run-only read surface is insufficient. Add Inquiry, Resource, Locator,
Claim/Evidence, and editable Plan projection for provenance. Codex VETOes a
Run-only UI.

F2. UI pending state derives from Action/Event/request material. A typed server
decision command may update stored Approval then delegate authorization to D2;
the browser never receives a PolicyGrant browser or computes validity. Codex
ACCEPT with contract tests.

F3. T3 export is not covered by the frozen unittest claim. It needs separate
exact-target validation, action-hash binding, one-time Approval, idempotency/
crash behavior, effect evidence, Receipt, canary, denial/expiry/change/replay
tests. Codex VETOes reusing D2 security claims and ACCEPTs a separately gated
narrow capability.

F4. Snapshot and cursor must come from the same consistent SQLite read
transaction. A cursor sampled outside the snapshot is insufficient. Codex
ACCEPT with race tests.

## Proposed final decision table

| Decision | Proposed state |
|---|---|
| Workspace lock lifecycle first | ACCEPT |
| Physical mount/combination of frozen D0 app | VETO |
| New authenticated runtime factory as OpenAPI authority | ACCEPT with gates |
| Canonical query/SSE before reconciliation-ready | VETO |
| Standalone fixture/replay viewer before mutation | ACCEPT |
| Thin journey application layer over D2 internal primitives | ACCEPT with typed boundary tests |
| D3/UI re-derives authorization | VETO |
| Narrow exact-target T3 export capability | ACCEPT with separate security gate |
| Browser EventSource or optimistic terminal states | VETO |
| Transaction-consistent snapshot plus ordered fetch stream | ACCEPT |
| Ten E2E runs with retries | VETO; they must be consecutive no-retry runs |

## Review requested

Claude should independently determine whether the evidence resolves all five
NOT CONSENSUS items and whether F1-F4 are acceptable. It must actively search
for a final counterexample and keep any unresolved item as NOT CONSENSUS.
