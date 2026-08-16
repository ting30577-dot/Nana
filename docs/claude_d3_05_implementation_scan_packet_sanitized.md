# D3-05 implementation candidate: independent Claude scan packet

Date: 2026-08-08
Scope: D3-05 implementation review only
Privacy: sanitized; all paths below are repository-relative; no credentials,
host identity, environment values, or machine identifiers are included.

## Review instruction

Independently scan this candidate against the frozen D3-05 design. Do not assume
Codex has accepted the implementation. List every correctness, security,
idempotency, lifecycle, API-contract, privacy, and evidence gap before proposing
repairs. Give each item a severity and an ACCEPT/VETO implication. D3-06 and
later work are out of scope.

The review protocol freezes production edits until both reviewers finish their
first scan. Codex findings are intentionally not included in this packet.

## Frozen implementation boundary

- Exactly one authenticated mutation route:
  `POST /api/v1/journey/commands`.
- Closed 11-request discriminated union: CreateProject, CreateInquiry,
  ProposePlan, RevisePlan, RegisterResource, CreateLocator, CreateClaim,
  AttachEvidence, CreateHypothesis, CreateRelation, DraftFinding.
- Browser requests have no actor field and require positive expected_revision.
- Server injects one configured user ActorRef.
- Workspace bootstrap is internal and has no HTTP request type.
- Mutation Workspace start, bootstrap, all writes, SQLite close, and lock
  release use one max_workers=1 executor and default SQLite thread affinity.
- D1 CommandTransactionService owns request hashing, command-log replay,
  BEGIN IMMEDIATE, commit/rollback, and response-loss semantics.
- Only allowlisted local-file descriptors are accepted. Resource bytes, Locator
  span, and quote hash are verified by the service.
- D3-05 does not enable execution, external effects, authorization, Approval,
  PolicyGrant, export, or mutation UI.
- Schema v6 is conditionally retained only if owner-lane and active-edge tests
  pass; otherwise D3-05 must own schema v7.

## Candidate file inventory

New or materially changed modules:

- `nana_sidecar/contracts/journey.py`
- `nana_sidecar/storage/command_transactions.py`
- `nana_sidecar/storage/journey_commands.py`
- `nana_sidecar/runtime_app.py`
- `nana_sidecar/api_models.py`
- `nana_sidecar/read_models.py`
- `nana_sidecar/dev_journey_fixture.py`
- `scripts/load_d3_dev_journey.py`
- `scripts/export_vnext_contracts.py`
- `fixtures/v0.3.0-dev/d3_journey_commands.json`
- `nana_web/openapi.json`
- `nana_web/src/generated/api.ts`
- `nana_web/src/contracts.ts`
- `nana_web/src/projection.ts`
- `tests/test_d3_journey_commands.py`
- `tests/test_d3_journey_runtime.py`

## Exact implementation facts and selected excerpts

### Runtime ownership

`_RuntimeControl` always constructs one ThreadPoolExecutor(max_workers=1).
When Workspace state is closed, `start()` calls WorkspaceRuntime.start on that
executor, then calls internal bootstrap on the same executor. Every journey
request constructs JourneyCommandService and executes it on the same executor.
`close()` drains SSE/tasks and writers, calls WorkspaceRuntime.close on the
executor, then shuts down the executor. If Workspace state is already ready and
journey config is absent, `start()` returns ready without moving start to the
executor. Journey config rejects an already-ready Workspace at app creation.

On a startup exception after Workspace becomes ready, control calls
WorkspaceRuntime.close on the executor, shuts down the executor, and re-raises.

### Authentication and body gate

The middleware order is: readiness; reject Forwarded/X-Forwarded headers;
require exactly one exact Host; LocalSession validates exactly one Bearer and
one exact Origin; then mutation-specific Content-Type/Content-Encoding/
Content-Length checks; then consume ASGI chunks with an actual 64 KiB cap; then
replay those chunks to FastAPI validation. Declared and actual lengths must
match. No Content-Length is allowed. Authorization occurs before any receive.

Mutation preflight recognizes only the exact command path and POST, exact
Origin, at most one requested-header line, and a requested-header set contained
in `{authorization, content-type}`.

Route inventory is computed as a set of `(route.path, mutation_method)` pairs
and compared to `{('/api/v1/journey/commands', 'POST')}`.

### HTTP response implementation and generated contract

The endpoint declares `response_model=CommandResult`. It returns:

- 200 CommandResult for accepted/replayed;
- 409 ErrorResponse for conflict-category CommandExecutionError;
- 422 ErrorResponse for other CommandExecutionError;
- 422 ErrorResponse from the custom RequestValidationError handler;
- 500 data-safe ErrorResponse for all other endpoint exceptions.

The generated OpenAPI operation currently lists a 200 CommandResult and a 422
HTTPValidationError response. Its request-body discriminator maps exactly 11
request schemas; each lacks actor and requires expected_revision. The global
contract catalog still contains the frozen D0 full Command/Event schemas, while
the POST request references only the curated request union.

### Transaction/replay

The generic engine does an out-of-transaction replay precheck, then
`BEGIN IMMEDIATE`, then a second command-ID check. Accepted domain/Event/outbox/
command-log rows commit together. Deterministic errors are stored in
command_log and raised after commit. A checkpoint supports before_commit and
after_commit fault injection.

The canonical request hash covers the fully constructed canonical Command,
including the injected actor. Accepted D3-05 replay validates command ID/status,
expected Event count/order/types, distinct Event IDs, causation ID, Event actor,
outbox row, a domain row at the affected revision, command-log actor, and the
affected_revisions map.

Rejected D3-05 replay validates that error.details.binding equals command ID,
command type, and recomputed request hash; it rejects INTERNAL and
COMMAND_REPLAY_CONFLICT error codes and applies a host-path regex to the stored
serialized error. The generic replay SELECT retrieves type, request_hash,
state, result_json, and error_json.

### Workspace bootstrap

Internal bootstrap uses BEGIN IMMEDIATE. On no Workspace it inserts one exact
Workspace, existing `workspace.created` Event, and outbox row. On one exact
Workspace match it selects the workspace.created Event/outbox and returns its
ID. It compares Workspace identity, schema version, logical data root, policy,
status, revision, and created_at. The existing Event lookup checks aggregate
type/id/version/type and outbox presence. Bootstrap never inserts Hypothesis.

### Frozen Resource path handling

Descriptor registration checks nonempty unique descriptor IDs, unique logical
refs, `PurePosixPath.is_absolute`, and `.`/`..` parts. It does not call the
public logical-path normalizer at descriptor registration. The public request
normalizer replaces backslashes, rejects root paths, Windows-drive prefixes,
dot/traversal, and returns a portable POSIX path.

Read verification resolves the configured read root, rejects link/reparse root,
walks descriptor logical-ref parts while rejecting link/reparse components,
uses lstat/read/lstat identity `(device, inode, size, mtime_ns)`, requires a
regular file, and computes raw-byte SHA-256. Locator creation re-reads bytes,
requires stored and requested content hashes to match, decodes UTF-8, requires
line_span and no byte_span, normalizes CRLF to LF, bounds the inclusive span,
and checks the computed quote hash.

### Domain rules

- Parent revision is loaded after BEGIN IMMEDIATE according to the frozen
  revision-binding table.
- Evidence creation requires valid Locator, available Resource, same Project,
  quote/excerpt match, and rejects an active duplicate. It atomically creates
  Evidence plus `resource_contains_evidence` Relation and two Events/outbox.
- Public relation request types and endpoints are contract literals. Service
  loads Claim revision and Evidence, checks same Inquiry, rejects Evidence
  states in `{rejected, stale, source_unavailable, tombstoned}`, rejects an
  identical active relation, derives RelationValidationContext counts, and
  invokes the frozen registry (which checks Evidence direction).
- Finding requires distinct request Evidence IDs and/or at most one terminal
  Run. Service requires every Evidence status exactly `valid`, same Inquiry;
  Run must share Inquiry/Project and be terminal. Evidence IDs are sorted. A
  Run-backed Finding atomically adds `run_produces_finding` Relation/Event.
- Hypothesis uses only curated CreateHypothesis and starts proposed.

### Fixture and projection

The checked fixture has ten stable command IDs and portable public facts. The
loader obtains generated IDs only from CommandResult. From Project onward it
calls only JourneyCommandService; it performs no SQL. The CLI acquires
WorkspaceRuntime, bootstraps, executes the typed loader, and closes in finally.

Bootstrap now contains a `hypotheses` collection. TypeScript requires that
collection, stores Hypothesis records, clones them, and patches Hypothesis SSE
facts. Other research aggregate Events remain activity/watermark facts and set
the existing degraded projection flag according to the frozen D3-03 unknown-
aggregate rule. There is no mutation UI.

## Candidate verification evidence

- compileall over sidecar/tests/scripts: passed.
- D3-05 command tests: 15 passed.
- D3-05 HTTP/owner-lane tests under ResourceWarning-as-error: 11 passed.
- D3 handle/lock/read/runtime/journey strict ResourceWarning subset: 63 passed,
  1 skipped, no warning.
- D1 transaction + D3 runtime/read/journey regression: passed.
- full Python suite: 332 run, 1 skipped; only failure is the intentionally
  not-yet-updated older evidence manifest hash for a changed D3-05 file.
- frontend TypeScript: passed.
- Vitest: 23 passed; projection self-test passed.
- production build: passed.
- existing read-only Playwright E2E: 11 passed.
- real fixture CLI on one clean temporary database: first load ten accepted;
  second load ten replayed; all generated canonical IDs identical.

Tests presently exercise accepted/replayed fixture families, stale Plan,
missing parent, cross-Project Evidence, duplicate Evidence/Relation, invalid
Locator span/hash, invalid Evidence/nonterminal and terminal Run Finding,
stored accepted-result corruption, descriptor ID/ref uniqueness, actor storage,
same-command concurrency, exact 64 KiB, 64 KiB+1, no-length ASGI chunks, lying
length, auth-before-body, content/preflight/forwarded rejection, owner-thread
affinity, bootstrap rollback/mismatch cleanup, and OpenAPI request closure.

The older stage manifests have not yet been regenerated and no D3-05 evidence
manifest/exit record exists because this is the first frozen scan.

## Requested output

Return:

1. a complete numbered finding list with severity and evidence;
2. any missing test/evidence gates required by the frozen design;
3. whether schema v6 remains acceptable or must be VETOed for schema v7;
4. an overall `ACCEPT`, `VETO`, or `NOT YET CONSENSUS` for moving from first
   scan to repair (not for D3-05 exit).
