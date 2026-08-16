# Codex D3-07 opaque-selection registry audit

Date: 2026-08-09  
Status: planning-only; no launcher input, browser surface, schema migration,
capability or filesystem writer is authorized by this record.

## Current-state facts

1. `LocalSession` is an in-memory bearer-token + exact-Origin authority. It has
   no durable session row or public session id.
2. `JourneyRuntimeConfig` currently owns the stable user actor and fixture
   inputs but no external target registry.
3. Schema v6 has no target-selection table. Authority 05 says canonical data
   must not preserve absolute user directories as portable references.
4. The current `scripts/run_d3_readonly_ui.py` is a read-only harness that
   creates a temporary Workspace. It is not a user-directory launcher and may
   not masquerade as one.
5. Existing `WorkspaceLock` Windows code proves only lock-file exclusivity. It
   does not provide directory File-ID/final-path/reparse identity needed by the
   export selection boundary.

## Findings

| ID | Severity | Finding | Consequence | Current decision |
|---|---|---|---|---|
| F07-26 | P0 | Selection persistence and restart semantics were not frozen. | Storing raw paths in canonical SQLite violates portability/privacy; memory-only target authority disappears on restart. | **Resolved as product design:** raw path/handle/token/clear identity memory-only; durable storage permits only irreversible non-locating commitment/expiry/binding/version facts. Restart invalidates authority; no rebinding. |
| F07-27 | P0 | `Path.resolve`/string comparison alone cannot prove Windows directory identity or alias safety. | Junction/reparse, mount-point, SUBST/short-name/case aliases and replacement races can bypass string allow-root checks. | **Resolved as product design:** retained-handle final/local volume-file identity, per-component reparse/alias rejection, Workspace identity comparison and live recheck; clear identity process-only. Exact API evidence remains gated. |
| F07-28 | P1 | Selection TTL and reuse cardinality were unspecified. | A reusable opaque id could authorize multiple target preparations; too-short expiry conflicts with the observed journey. | **Resolved as product design:** 60-minute maximum and LocalSession bound; Approval expiry clamped; exactly one Export Run/Action/attempt; close on terminal/expiry/session/drain. |
| F07-29 | P1 | Launcher/CLI raw-path transport was unspecified. | A browser field is forbidden; a normal command-line path may be exposed in process listings and a harness injection is not user choice. | **Resolved as product design:** interactive pre-serve prompt, no path argument; separately named `test_harness`; no user-selected claim and no pre-dev Tauri. |
| F07-30 | P0 | Restart outcomes for requested/approved/writing exports were not fully classified. | Retrying an approved Action after its machine-local selection disappears could target a different path or duplicate an uncertain effect. | **Resolved as product design:** committed first-write fence precedes all probe/write; no-fence states fail empty, fenced states become `effect_unknown`; no rebind/retry. |
| F07-31 | P0 | An in-memory selection transition and durable SQLite CommandResult cannot commit atomically. | Claiming a single cross-resource transaction would be false; a crash can occur before or after either side changes. | **Resolved as product design:** reserve→SQLite commit→finalize compensation protocol with deterministic ids, exact rollback release and fail-closed restart; explicitly not cross-resource atomic. |

## Recommended registry ownership

`TargetSelectionRegistry` belongs to the same runtime app instance as
`LocalSession` and `JourneyRuntimeConfig`. It is constructed before
`create_runtime_app`, receives the already-selected directory from the
launcher/CLI, and never appears in the canonical database or portable Event
payloads.

Each private entry contains:

```text
selection_id                 random 256-bit opaque token
actor_id                     stable local user principal
session_instance_binding     implicit owning LocalSession/app instance
opened_directory_handle      private owner-runtime handle
canonical_final_identity     volume id + file id + normalized final identity
workspace_identity_digest    irreversible comparison binding; no raw Workspace path
selection_identity_digest    irreversible hash used in Action material/durable subject
redacted_label               leaf display name only
created_at / expires_at      monotonic + UTC audit times
bound_export_run_id          absent until request preparation
bound_action_id              absent until request preparation
state                        available / reserved / bound / expired / closed
```

The raw absolute path, live directory handle, clear volume/file identity and
opaque selection token remain private process memory.
They are never placed in browser JSON, OpenAPI examples, canonical rows,
Events/outbox, CommandResult, Action args Artifact, Receipt, logs or Claude
evidence. Browser/API equality uses the opaque id; ActionHash material uses the
selection identity digest and exact fixed child target commitment.

## Recommended Windows identity protocol

This is a security protocol candidate, not accepted implementation:

1. Require an existing directory selected explicitly by the CLI user.
2. Reject `..`/relative syntax before resolution and walk every existing
   component without following a reparse point.
3. Open the directory with Windows directory-handle semantics, reject reparse
   attributes/tags, obtain its final normalized identity plus volume/file id,
   and retain a handle that prevents delete/rename replacement while allowing
   the controlled export operation.
4. Require a supported fixed local filesystem and compare handle identities,
   not path prefixes, against Workspace and the frozen F07-21 set. Reject volume/
   profile/system/Nana roots, Workspace overlap both ways, UNC/network/mapped/
   cloud-sync targets, aliases, non-empty/colliding/changing targets and
   unverifiable filesystems.
5. Record only the identity digest/redacted label in the Action subject. Before
   report/probe write, re-read the live handle/final identity and fail closed on
   any mismatch.
6. Use read-only volume/filesystem information only for selection eligibility.
   After atomic Approval/consumption, commit the durable first-write fence before
   the real positive probe or any external byte.

The exact API flags, sharing mode, directory-ancestor walk, volume capability
allowlist and handle transfer to the export worker require Windows tests; this
document does not claim them proven.

## Recommended lifetime and request binding

- Frozen TTL: 60 minutes from creation and no later than LocalSession end;
  monotonic time is authoritative for live expiry, UTC is audit/display only.
- Approval expiry is clamped to the selection expiry.
- The owner lane reserves an `available` entry to `(command_id, request_hash,
  derived Export Run id, derived Action id)` before the SQLite transaction. A
  second request with the id is rejected while reserved or bound, even if the
  Finding is the same. SQLite rollback releases the matching reservation;
  successful commit finalizes it as `bound`. This is an explicit coordination
  protocol, not a claimed atomic transaction across memory and SQLite.
- Binding does not constitute Approval consumption or filesystem authorization.
  It only prevents subject/target reuse.
- The registry closes the handle and removes raw path material when the Action
  becomes terminal, the selection expires, the session closes, or the app
  drains.
- A new export attempt, including retry of the same Finding to the same
  directory, requires a fresh user selection and new opaque id.

### F07-31 crash windows

| Window | Required convergence |
|---|---|
| crash before memory reservation | No SQLite subject; selection disappears with process |
| crash after reservation, before SQLite begin/commit | No SQLite subject; selection disappears with process |
| SQLite rollback | Owner lane releases only the matching reservation; no subject facts |
| SQLite commit, before memory finalize | Durable subject/CommandResult exists; same-process recovery finalizes only if reservation matches, while process restart invalidates selection and uses the no-write recovery classification below |
| response lost after commit | Same command replay returns stored CommandResult; it never creates a second subject or binds the selection to another Action |

Deterministic derived ids and request hash are mandatory so a replay cannot
reinterpret a reservation. No Event or CommandResult may claim that the
in-memory target remains available after process loss.

## Restart and crash classification candidate

| Durable state at owner loss | Restart result |
|---|---|
| Approval requested; no authorization | Mark Approval expired through its typed expiry path, then deterministic system `CancelRun`; no external bytes |
| Approval denied; cancellation not yet committed | Replay deterministic system `CancelRun`; no external bytes |
| Approval approved/consumed; Action authorized; no write/probe fence | Instrumentation must prove zero operations; settle Action/Receipt as failed with empty actual effects and terminalize Export Run failed; no retry |
| Action claimed but durable first-write fence absent | Same proven fail-before-effect result; release/settle budget exactly once |
| Durable first-write/probe fence present | Selection and effect cannot be re-proven; settle `effect_unknown`, terminalize Export Run conservatively; no retry/rebind |
| Action/Run already terminal | Replay stored facts; close any surviving in-memory selection only |

No restart branch asks the user for a new path and then resumes the old Action.
A fresh selection always creates a fresh Export Run, Action, Approval and
Receipt chain.

## Candidate real-user CLI boundary

The D3 real-user launcher/CLI should prompt for one directory before starting
the browser-serving runtime. It validates and creates the registry entry before
the handshake reports export target availability. The browser sees only:

```text
{
  "selection_id": "opaque",
  "display_name": "redacted leaf label",
  "expires_at": "UTC timestamp"
}
```

An automation/test constructor may inject a temporary test root, but its type,
configuration field and handshake label must explicitly say `test_harness`; it
cannot set `user_selected=true` or satisfy the real-user E2E acceptance.

## Gate effect

F07-26 through F07-31 are product-frozen design findings. They do not alter the
current closed machine gate. Runtime implementation still requires the D3-06
independent exit, independent review of the frozen rules and joint D3-07 07-00
ACCEPT.
