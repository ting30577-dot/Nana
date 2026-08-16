# Nana D3-00 Codex independent proposal

Status: independent proposal, not yet a joint decision.

## Outcome proposed

D3 should be implemented as six stop-line slices. The bridge starts with
Workspace ownership, then exposes one unified authenticated runtime contract,
then builds a replay-correct read surface, and only after those gates adds the
minimum typed mutations needed by the frozen dev journey. The React client is
an event-backed projection and command surface, never an alternate workflow
engine.

## Decision candidates

### C1 — Workspace owner is a lifecycle object

**Codex: ACCEPT.** Add one `WorkspaceRuntime`/equivalent lifecycle component
that owns, in order:

`resolved identity -> OS lock -> writable SQLite -> migrations -> artifact
reconciliation -> services/routes ready -> quiesce -> SQLite close -> lock
release`.

It must expose states such as `starting`, `reconciling`, `ready`, `draining`,
and `closed` for launcher/health reporting. A failure before `ready` closes any
opened database and releases the lock; lock contention fails closed. The lock
file contains no authority and is not trusted as a stale-process oracle; the OS
lock is authoritative. Read-only fixture/viewer mode remains a separate mode
and cannot be upgraded in place to a writer without acquiring ownership.

### C2 — Merge OpenAPI and runtime composition in D3

**Codex: ACCEPT with hard conditions.** Use one application factory as the
runtime contract source, while retaining the D0 factory as a frozen regression
input if required by its manifest. The merged runtime must preserve default-deny
auth, register SSE plus typed query/command routes, regenerate the checked-in
OpenAPI and TypeScript client, and prove that no route becomes public by
accident. CORS support is exact-origin and exact-header; no anonymous wildcard
`OPTIONS` path.

VETO a parallel hand-maintained UI API schema or silently adding routes only to
the runtime app without regenerating the contract.

### C3 — Query API returns task-oriented projections

**Codex: ACCEPT.** Add narrow read models rather than table-shaped CRUD:

- workspace bootstrap/status and compatibility;
- active inquiry/dev-journey summary;
- plan revision/editor projection;
- run/action/activity timeline ordered by Event ID;
- needs-user projection for pending one-time approval;
- artifacts/finding draft projection;
- Receipt detail, including authorization and effect fields.

Queries may join canonical tables but do not infer authorization. They present
the stored Action state, authorization snapshot, Events, and Receipt. Reconciled
Artifacts retain a recovery badge/reason.

### C4 — Minimal mutations are application services, not raw Action endpoints

**Codex: ACCEPT.** Implement only the typed service subset needed for the frozen
journey, each with stable command ID/request hash and expected revision where
applicable:

- initialize or load the frozen dev Inquiry/Resource/Locator/Evidence fixture;
- revise the Plan;
- start the frozen locked-test Run through existing D2 admission, scheduler,
  budget, and executor;
- request/decide the one-time T3 export Approval;
- execute a registered exact-target draft export capability and create its
  Receipt;
- cancel the active Run through D2 cancellation semantics.

The UI never submits PolicyGrant-derived authorization or a raw executable.
The export target is selected explicitly, included in the Action hash, and is
outside the canonical Workspace only after one-time approval. VETO generic
shell/Python, generic arbitrary capability execution, final Decision, publish,
or delete.

This slice may require a small registered export capability. It must be
reviewed as a new T3 surface and cannot inherit the locked unittest security
claim.

### C5 — Projection store is replay-first

**Codex: ACCEPT.** The React store is a reducer over a bootstrap snapshot plus
ordered SSE Events. It maintains the last fully applied Event ID in memory,
uses authenticated `fetch` with `ReadableStream`, reconnects with that cursor,
rejects malformed/out-of-order frames, ignores already-applied IDs, and
refreshes the canonical snapshot if it detects a gap or contract mismatch.
Local editor text is explicitly dirty/non-canonical until a command result and
subsequent Event reconcile it. No terminal state is synthesized from an HTTP
202 or optimistic click.

### C6 — Product surface is a focused research control room

**Codex: ACCEPT as design direction, subordinate to truth.** Use a restrained,
industrial/editorial two-pane workspace: a compact Cockpit rail for Active,
Needs You, Running/Failed; a Studio canvas for Inquiry/Plan, Activity, tests,
Artifact/Finding, and Receipt. State color is never the only signal. The most
memorable interaction should be a causality thread from Plan step to Action,
Event, Artifact/Finding, and Receipt, not decorative animation.

## Six slices and stop conditions

### D3-00 — joint design and contract map

Exit: Codex/Claude explicit decision table covers C1-C6, security boundaries,
route inventory, deferred work, and evidence plan. Any unresolved lock or
authorization objection stops implementation.

### D3-01 — Workspace ownership lifecycle

Exit: tests prove lock-before-writable-open, reconciliation-before-ready,
second-instance fail-closed, database-close-before-unlock, startup failure
cleanup, abrupt process death/reacquire, and no mutation while not ready.

### D3-02 — unified runtime contract and read projections

Exit: OpenAPI/client regenerated from the merged runtime; route inventory and
default-deny tests pass; exact-Origin preflight tests pass; replay fixture can
populate every required projection without querying grants/approvals.

### D3-03 — React read surface and browser SSE

Exit: real browser tests cover Bearer header, exact Origin/preflight,
ReadableStream parsing, reconnect, duplicate delivery, gap recovery, refresh,
negative states, keyboard navigation, and 125%/150% viewport scaling. Still no
real mutation if D3-01/D3-02 are not green.

### D3-04 — frozen test journey mutations

Exit: create/load fixture, revise plan, execute exactly the registered frozen
test via D2, render running/failure/cancel/orphan/effect-unknown accurately,
and produce test Artifact plus Finding draft. No UI-issued raw Action.

### D3-05 — T3 draft export approval and Receipt

Exit: exact target and content are action-hash bound; denial/expiry/change/replay
fail closed; no external file exists before approval; successful export produces
Receipt and UI provenance; effect uncertainty is never success.

### D3-06 — complete dev gate and evidence

Exit: ten consecutive real-browser journeys pass from a clean Workspace;
reload/reconnect, cancel, failure/retry, second instance, sidecar crash recovery,
keyboard/DPI, and structured-error interpretation are recorded. Compile, full
Python tests, strict warning subset, TypeScript check, browser suite, manifest,
and an authoritative evidence summary all pass before joint exit review.

## Principal risks and self-counterarguments

1. The full dev journey is much larger than a fixture viewer. If D3 time grows,
   scope must be reduced inside the same journey, not by declaring a read-only
   viewer to be D3 complete.
2. Adding a T3 export capability expands the security surface. It needs its own
   narrow registry, path/action-hash, approval, effect, crash, and Receipt tests;
   D2 evidence cannot be reused as proof.
3. A single merged factory can accidentally mutate the frozen D0 manifest.
   Composition should preserve frozen inputs and add a new generated runtime
   snapshot with explicit migration of authority.
4. Snapshot plus SSE can race. The API needs a bootstrap watermark/cursor so
   the client can request a consistent snapshot and then replay strictly after
   that Event ID.
5. Browser auth bootstrap is not yet implemented. For D3 automated development
   E2E, a test launcher may inject an in-memory session and exact Origin, but
   this must not be mislabeled as the Local Web Plan B security gate or a
   production bootstrap mechanism.
6. Cross-process Windows lock behavior cannot be proven by in-process mocks.
   Tests need real child processes and abrupt termination.

## Evidence policy

Each slice writes a repository-relative evidence summary and a decision record.
At D3 exit, prepare a manifest and a sanitized Vault synchronization summary in
the same session, so code/test success cannot become detached from the
authoritative evidence index again.
