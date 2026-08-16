# D3-05 first frozen scan findings

Date: 2026-08-08
Status: first scan complete; repairs applied and second local scan complete.

This list is intentionally written before any implementation repair. Findings
are separated into implementation defects and evidence gaps. D3-06 and later
stages are excluded.

## Implementation defects

### F-01 — prestarted read-only Workspace can close on the wrong thread (P1)

`create_runtime_app` permits a read-only `WorkspaceRuntime` already started by
the caller. `_RuntimeControl.start()` then returns without moving ownership, but
`close()` always calls `workspace.close` on the writer executor. A SQLite
connection created on the caller thread therefore raises `ProgrammingError`,
leaving the connection and OS lock held. A direct diagnostic reproduced
`close_failed` with the lock still held. This is outside mutation writes but is
the same runtime lifecycle handle and must be fixed before D3-05 exit.

### F-02 — failed second mutation control can leak its executor (P1)

When `_RuntimeControl.start()` sees an already-ready Workspace and journey config
is present, it raises before entering the cleanup `try` block. The newly created
single-thread executor is not shut down. The shared-Workspace race is rejected,
but the failed control still leaks a runtime handle.

### F-03 — rejected replay does not bind stored actor or full error integrity (P1)

The D3 rejected-replay validator checks only `error.details.binding`, rejects two
error codes, and applies a path regex. It does not verify the command-log
`actor_json`, nor does it reconstruct or authenticate the stored error's code,
category, message, retryability, data-safe flag, suggested actions, or reason
details. A valid-looking but modified rejection can therefore replay. The
generic command-log SELECT also omits actor_json.

### F-04 — accepted replay does not enforce command-specific aggregate shape (P1)

Accepted replay checks Event type, causation, actor, outbox, domain-row
existence, and the affected-revision map, but it does not assert the expected
aggregate type per command or validate the command-specific Event payload and
parent/scope facts. A database-corrupted Event/result pair can be made
self-consistent while pointing at a different aggregate table.

### F-05 — public relation writer accepts non-valid `lead` Evidence (P1)

The frozen rule says public Evidence-to-Claim relations require valid Evidence.
`_create_relation` rejects `rejected`, `stale`, `source_unavailable`, and
`tombstoned`, but permits `lead`. A manually introduced lead Evidence can be
related successfully.

### F-06 — frozen descriptor validation does not use the canonical portable-path guard (P1)

`_validate_descriptors` checks `PurePosixPath.is_absolute` and dot parts but does
not reject Windows-drive prefixes, backslashes, or normalize the descriptor
reference with `validate_logical_path`. The public request validator blocks many
of these values, but internal descriptor configuration can still accept an
invalid reference. The resource reader also does not explicitly assert the
resolved target remains relative to the resolved read root after every join.

### F-07 — mutation OpenAPI omits actual structured error responses (P1)

The POST implementation returns structured `ErrorResponse` for 409, 422, and
500, while the checked-in OpenAPI operation declares only 200 CommandResult and
the generic FastAPI 422 HTTPValidationError. The generated client therefore
cannot rely on the actual error contract.

### F-08 — mutation route inventory loses duplicate routes (P2)

`validate_runtime_route_inventory` compares a set of path/method pairs. Two
identical POST routes collapse to one set entry and pass the exact-inventory
guard. The validator must compare multiplicity and prevent duplicate handlers.

### F-09 — runtime handshake hardcodes schema version (P2)

Mutation and read-only handshake handlers return literal schema version 6 and
read ceiling 6 instead of the canonical package constants. This can drift from
the actual migration authority and would be wrong if the conditional v7 gate is
ever activated.

### F-10 — configured user actor may have no stable ID (P2)

`JourneyCommandService` and mutation app configuration require actor kind `user`
but permit `ActorRef(kind="user", id=None)`. The design requires a fixed local
user identity for auditable stored actor binding.

### F-11 — existing Workspace bootstrap fact is not fully integrity-checked (P2)

On idempotent bootstrap, the service checks Workspace identity/configuration and
the existence of a matching Event/outbox, but does not verify Event actor,
payload, occurred_at, or that the Event/outbox pair is the exact canonical
bootstrap fact. Corrupted bootstrap evidence can be accepted as a no-op.

### F-12 — mutation owner start failure cleanup is not reusable after control failure (P2)

Normal bootstrap failure closes and releases correctly, but the control is left
in `failed` with a shut-down executor. A caller cannot safely retry the same app
instance or obtain a structured lifecycle state proving whether the Workspace
remains owned after a close failure. This should be made explicit in lifecycle
tests and, where appropriate, fail closed with a preserved recovery path.

## Evidence and test gaps

### F-13 — different-command active-edge race is not tested (P1 evidence gap)

The suite tests sequential duplicate Evidence/Relation and concurrent identical
command IDs, but not two different command IDs racing to create the same active
edge. This is the CI-blocking proof for retaining schema v6 without a v7
migration.

### F-14 — D3 handler-specific before/after-commit fault matrix is incomplete (P1 evidence gap)

D1 generic transaction tests cover RevisePlan and generic engine behavior, while
D3 tests cover bootstrap before-commit. There is no D3 multi-event
AttachEvidence/DraftFinding fault test proving domain/Event/outbox/command-log
rollback and after-commit replay for the new handlers.

### F-15 — Resource security matrix is incomplete (P1 evidence gap)

Implementation contains checks for traversal, reparse components, regular-file
identity, hash, span, and encoding, but D3-05 tests do not exercise actual
symlink/junction/reparse cases, path escape against a temporary read root, file
identity change during read, or a content mutation between Resource registration
and Locator creation.

### F-16 — HTTP exact-header matrix is incomplete (P2 evidence gap)

Mutation tests cover Host/Origin/Forwarded, auth-before-body, content type,
encoding, length, and preflight, but do not exercise duplicate Authorization,
Origin, Host, or Content-Length headers through a raw ASGI scope.

### F-17 — committed-outbox SSE and HTTP response-loss evidence is incomplete (P1 evidence gap)

Bootstrap/activity proves a committed effect, and same-command retry is tested,
but there is no D3 mutation test proving an Event is invisible to SSE before its
outbox commit, or that a mutation response lost after commit replays the exact
stored result/error through HTTP.

### F-18 — full-suite shutdown warning attribution is incomplete (P2 evidence gap)

The full 332-test run prints one uncollectable-object ResourceWarning at process
shutdown, while the strict D3 runtime/lock/journey subset passes 63 tests with
ResourceWarning-as-error. The warning is not currently attributed to a D3
writer/lock/process path. It is non-blocking for starting D3-05 writes only if
the attribution remains outside this path and is recorded in final evidence.

### F-19 — stage evidence is not synchronized (P1 evidence gap)

The previous D3-04 manifest now mismatches changed D3-05 files, and no D3-05
manifest, completion summary, final scan record, or Claude exit verdict exists
yet. Full Python verification is therefore not currently green as an evidence
package even though the implementation tests pass.

## First-scan disposition

- Schema v6: **not yet final**. F-13 must pass with the owner-lane and
  `BEGIN IMMEDIATE` proof; any failure VETOes the no-migration decision and
  requires a D3-05-owned schema v7 migration.
- Claude independent scan: **not completed** because the configured gateway
  returned an account concurrency rate-limit error after the authorized retry;
  this remains a review dependency, not an ACCEPT.
- F-01 through F-17: **REPAIRED LOCALLY** and covered by the D3 strict subset;
  F-04 now includes command-specific payload and domain-row binding.
- F-18: **OPEN EVIDENCE CAVEAT**. The full suite still prints one uncollectable
  GC ResourceWarning at interpreter shutdown; the D3 strict subset remains
  clean under `-W error::ResourceWarning`, and the warning has not been traced
  to the D3 writer/lock path.
- F-19: **REPAIRED LOCALLY** by synchronizing the 102-entry D0 manifest and
  preparing a dedicated D3-05 manifest/completion record.
- Claude independent repair review: **NOT COMPLETED**. The configured gateway
  failed before returning a review after the authorized invocation; no Claude
  verdict is inferred.
- Overall local repair status: **READY FOR FINAL CLAUDE ADJUDICATION**, but not
  a joint ACCEPT until Claude returns a review and the evidence package is
  synchronized.
