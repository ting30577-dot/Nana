# Nana D3-00 cross-review packet (sanitized and minimized)

Purpose: second-round cross-review after independent Codex and Claude D3
proposals. This single packet contains only decision-relevant conclusions and
repository-relative evidence descriptions. It contains no credentials,
environment values, authorization values, personal paths, machine identity,
private network data, logs, or user content.

## Frozen shared facts

- D0, D1, and the narrow trusted `python.unittest.locked` D2 surface are
  accepted.
- D3 may project stored Run, Action, authorization snapshot, Event, outbox,
  Receipt, and Artifact facts. It may not re-derive authorization from grants or
  approvals and may not bypass D2 admission, scheduling, or execution.
- Real mutation serving is forbidden until an OS Workspace lock is acquired
  before writable SQLite, reconciliation completes before ready, a second
  instance fails closed, and SQLite closes before unlock.
- Browser SSE uses authenticated `fetch + ReadableStream`, stable Event IDs,
  at-least-once replay, cursor reconnect, ordered application, and duplicate
  suppression.
- Runtime HTTP routes are default-deny. Exact public routes and any precise CORS
  preflight behavior require explicit review.
- The frozen D0 contract app and the current authenticated runtime/SSE app are
  separate. No real mutation HTTP route or React application exists today.

## Codex independent proposal

Codex proposed seven stop-line slices:

1. joint decisions and contract map;
2. Workspace ownership lifecycle;
3. authenticated runtime OpenAPI plus read projections;
4. React read surface and authenticated SSE;
5. typed frozen-test journey through D2;
6. separately reviewed T3 draft export Approval/Receipt;
7. ten consecutive browser journeys plus evidence synchronization.

Codex decisions:

- Workspace lifecycle object owns lock, database, reconciliation, readiness,
  writers, close, and unlock: ACCEPT.
- One browser-facing authenticated runtime contract source: ACCEPT.
- UI query models are task-oriented projections, not CRUD tables: ACCEPT.
- Minimum mutations are typed application services over canonical Commands and
  D2 services, never raw executables: ACCEPT.
- React reducer uses a bootstrap watermark plus ordered Events; no HTTP response
  or local optimistic state invents a terminal result: ACCEPT.
- T3 draft export is a new narrow surface and cannot inherit D2 frozen-worker
  safety evidence: ACCEPT.
- Generic shell/Python, final Decision, publish/delete, and alpha.1 work: VETO.

## Claude independent proposal

Claude accepted the Workspace lock gate, the authenticated runtime as the
single service surface, D2 delegation, authenticated fetch SSE, and exact-Origin
CORS. Claude vetoed physically merging the two existing app compositions and
recommended exporting OpenAPI directly from the authenticated runtime app.

Claude marked five issues NOT CONSENSUS:

1. deterministic reconciliation convergence predicate;
2. authoritative stored facts for orphaned and effect-unknown UI states;
3. field map for a T3 external draft export Receipt;
4. whether controlled clocks/event barriers may support the ten-run E2E gate;
5. whether the D0 app remains frozen evidence or is retired.

Claude also vetoed native EventSource, UI state as truth, false terminal-state
rendering, mutations before lock, and service-layer simulation that bypasses
D2.

## Codex cross-review and amendments

### A. OpenAPI/runtime wording

Codex accepts Claude's VETO of physically collapsing or modifying the two
existing factories. Revised proposal:

- preserve the D0 app/snapshot as frozen regression evidence;
- create/extend an authenticated D3 runtime composition;
- export that composition's own OpenAPI snapshot;
- generate the browser client only from the D3 runtime snapshot;
- treat the D3 runtime route/public-path inventory as a security artifact;
- do not create a second UI-facing service.

Codex asks whether this fully resolves the OpenAPI objection.

### B. Reconciliation ready predicate

D1 recovery tests already use repeated-scan idempotency. Codex proposes:

1. initial startup reconciliation scan completes without exception;
2. an immediate verification scan returns zero actions;
3. writers and mutation routes have not started during either scan;
4. any exception, timeout, or non-empty verification scan keeps the runtime
   not-ready and closes it fail-closed.

The Workspace lock guarantees the single-owner model; this does not claim
concurrent reconciler safety. Codex proposes ACCEPT unless Claude supplies a
remaining counterexample.

### C. Orphaned/effect-unknown projection map

Codex proposes reading stored facts, never re-running executor logic:

- orphaned Run: stored Run state `orphaned`; the matching `run.orphaned` Event
  is replay evidence;
- effect-unknown Action: stored Action state `effect_unknown` plus terminal
  Receipt result `effect_unknown`; matching Event is replay evidence;
- Receipt `effect_violation` is separately displayed but is not the sole source
  of effect-unknown because truncation, runner failure, cancellation uncertainty,
  or termination failure can also produce it;
- termination in progress: stored Run `paused` plus stored result reason
  `cancel_requested`.

Codex proposes ACCEPT unless a stored-fact inconsistency case remains.

### D. T3 export

Codex accepts NOT CONSENSUS. Before the export slice, define a narrow T3
capability whose action/receipt material covers:

- exact source Artifact and content hash;
- portable external target identity without storing a personal absolute path as
  a portable reference;
- one-time authorization source, actor, and time;
- authorized/actual writes and absence of undeclared network/process effects;
- before existence, created/replaced outcome, bytes/hash, result;
- crash windows and effect-unknown rule;
- undo/compensation;
- proof that no external file appears before authorization.

This blocks the export slice, not the Workspace-lock slice.

### E. Deterministic E2E controls

Codex accepts fixed seeds, controlled clocks, and explicit Event barriers only
in test composition. They cannot replace the real browser, HTTP/SSE parser,
SQLite, Workspace OS lock, or process boundary. Abrupt lock tests use real child
processes and the ten journeys use real browser transport.

### F. D0 fate

Codex accepts preserving D0 as frozen evidence. It is not the D3 browser
contract and is not deleted or mutated.

### G. Command vocabulary

Codex vetoes silently inventing parallel journey Commands. Product-level
services should compose the smallest existing typed Command subset. A new
Command requires an explicit contract decision. A reversible dev draft export
must not reuse a final/T4 publish Command if the risk semantics differ.

## Requested Claude cross-review

Review each item independently and return ACCEPT, VETO, or NOT CONSENSUS:

1. Does amendment A resolve the prior app-merge VETO?
2. Is predicate B sufficient for ready in the frozen single-owner model? Give a
   concrete remaining crash or artifact-state counterexample if not.
3. Is map C sufficient for faithful UI projection? Give a concrete inconsistent
   stored-fact case if not.
4. Confirm whether D remains NOT CONSENSUS only until a dedicated export design.
5. Is E an acceptable deterministic-test boundary?
6. Does F resolve the D0-app question?
7. Is G the correct rule for the mutation service/Command boundary?
8. Review the seven-slice order and identify any missing stop-line dependency.
9. State whether D3-01 Workspace lock implementation may begin after this
   review, or list any blocker that must be resolved before any code.

Do not modify files. Do not infer approval from agreement tone. Preserve every
material objection explicitly.
