# D3-05 Codex independent design: canonical journey writers

Date: 2026-08-08
State: candidate design; no implementation authorized

## 1. Outcome and boundary

D3-05 should open one narrow authenticated mutation surface for canonical
research-domain facts. It must not expose execution, authorization, Approval,
PolicyGrant, Artifact commit, export, arbitrary filesystem selection, raw SQL,
or the complete D0 Command union.

The stage owns these capabilities only:

1. create a Project and Inquiry under the already-owned Workspace;
2. propose and revise a Plan;
3. register one allowlisted frozen local-file Resource and its verified Locator;
4. create Claim, valid Evidence, the required research Relations, and a
   Hypothesis;
5. draft a Finding from valid Evidence and/or one terminal Run;
6. replay every accepted or rejected request without duplicate facts, Events,
   outbox rows, or generated identities.

Execution remains disabled. D3-06 is the first owner of StartRun, Action,
admission, scheduler, executor, budget, Artifact result, and Receipt
orchestration.

## 2. Independent findings that constrain the design

### 2.1 The first real writer needs a thread-owned SQLite lane

The D3 runtime starts `WorkspaceRuntime` through a generic worker thread. Its
SQLite connection therefore cannot safely be reused by a later arbitrary
thread-pool task under sqlite3's default thread check. D3-05 must not solve this
with uncoordinated `check_same_thread=False` access.

The runtime will own a single-thread executor for the whole writable lifecycle:

`WorkspaceRuntime.start -> all command transactions -> WorkspaceRuntime.close`

Only this lane may touch `workspace.connection`. Read models keep opening their
own verified read-only connections. Runtime draining stops admission of new
writes, waits for the one in-flight command, closes SQLite on the writer lane,
then releases the OS Workspace lock through the existing D3-01 lifecycle.

### 2.2 The browser must not supply audit identity or dangerous Command types

The HTTP request union omits `actor`. The runtime injects the fixed local
session actor (`kind=user`, a non-secret stable local-session identifier) before
constructing the canonical Command and request hash. A browser cannot claim to
be `system`, `agent`, or `tool`.

The accepted request discriminators are limited to:

- `CreateProject`
- `CreateInquiry`
- `ProposePlan`
- `RevisePlan`
- `RegisterResource`
- `CreateLocator`
- `CreateClaim`
- `AttachEvidence`
- `CreateHypothesis`
- `CreateRelation`
- `DraftFinding`

All Action, Run, authorization, Approval, PolicyGrant, Artifact commit, export,
status-repair, and arbitrary future Command types fail schema validation before
dispatch.

### 2.3 Existing schema v6 can represent the minimum stage

The existing tables already represent every D3-05 fact, Event, outbox row, and
command result. `findings.producer_run_id` and the Relation Registry permit at
most one producing Run, so the HTTP/canonical writer will reject more than one
`terminal_run_id` and reject duplicate Evidence IDs. No schema migration is
proposed.

This no-migration decision is conditional: if implementation cannot enforce
active-edge uniqueness/cardinality and replay binding transactionally through
the sole writer, D3-05 must stop and own a schema-v7 migration rather than add an
ad-hoc table or weaken the invariant.

## 3. HTTP authority and security inventory

Add exactly one authenticated route:

`POST /api/v1/journey/commands`

It accepts a closed `JourneyCommandRequest` discriminated union, not the full
`Command` union. The current no-mutation route guard becomes an exact runtime
route-inventory validator: the one POST above is accepted and every other
POST/PUT/PATCH/DELETE route is a configuration error. This is the explicit
D3-05 amendment to D3-02's default-deny decision.

The existing Host, Origin, single Bearer header, forwarded-header denial,
readiness, no-redirect, and default-route rules remain. Mutation-specific rules
are:

- authenticate before consuming a body;
- exact JSON media type and no content encoding;
- a 64 KiB maximum enforced while reading ASGI body chunks, including when
  Content-Length is absent;
- exact CORS preflight allowlist for this POST and only `Authorization` plus
  `Content-Type`;
- one request produces one `CommandResult` or one `ErrorResponse`; no token,
  local path, SQL detail, or traceback is echoed;
- accepted and replayed requests return 200 so response-loss retry is stable;
- request validation/locator errors return 422, conflicts return 409,
  authorization failures remain 401/403, oversized bodies return 413, runtime
  lifecycle denial returns 503, and unexpected failures return a data-safe 500.

The runtime handshake gains a runtime-specific response that truthfully says:
mutations are enabled only for the listed journey request types, while
execution and external effects are disabled. The read-only D0 app keeps its
existing handshake contract.

## 4. Command and revision semantics

Every HTTP request requires a UUID `command_id` and a non-null positive
`expected_revision`. The canonical request hash is SHA-256 over deterministic
JSON for the fully constructed Command, including the server actor. Mapping key
order cannot change the hash.

The expected revision binds the snapshot that authorized the request:

| Request | Revision-bound aggregate |
|---|---|
| CreateProject | Workspace |
| CreateInquiry, RegisterResource | Project |
| ProposePlan, CreateClaim, CreateHypothesis, DraftFinding | Inquiry |
| CreateLocator | Resource |
| AttachEvidence | Locator |
| RevisePlan | Plan |
| CreateRelation | Claim target; only Evidence-to-Claim direction relations are public in D3-05 |

Create operations do not increment their parent. The revision binds the
revisioned input whose content or validity the command consumes; it is not a
collection version. Every other endpoint's current state and scope is still
checked inside the same transaction. The created aggregate starts at revision
1. A different `command_id` may legitimately add another child under the same
parent revision.

`ProposePlan` creates revision 1 in `proposed`; `RevisePlan` preserves the D1
behavior of appending a new `draft` revision and never overwrites an earlier
revision. D3-05 does not approve a Plan or start execution.

## 5. Transaction protocol

Extend the D1 `CommandTransactionService` rather than creating a second
idempotency implementation. For each allowed command:

1. require an idle connection on the dedicated writer lane;
2. compute the canonical request hash;
3. pre-check `command_log` for fast replay;
4. `BEGIN IMMEDIATE` and re-check the same command ID;
5. validate revision, scope, state, cardinality, and allowlisted resource facts;
6. on acceptance, insert domain rows, one or more typed Events, matching outbox
   rows, and the accepted `CommandResult` in the same transaction;
7. on deterministic rejection, insert a bound structured error in
   `command_log` in the same transaction, then raise after commit;
8. commit, then permit response delivery.

An accepted replay validates that every stored Event has the command ID as
causation, has an outbox row, matches the expected aggregate/type/version, and
resolves to the exact domain row/revision named by `affected_revisions`.

A rejected replay validates the row type and request hash plus a normalized
binding embedded in safe error details: command ID/type, bound aggregate IDs,
expected/observed revisions where applicable, and the specific relation,
locator, state, or scope witness. It returns the original rejection with
`replayed=true`; it never silently re-evaluates into acceptance after the
database changes.

Same command ID plus changed type/content is always
`E_COMMAND_REPLAY_CONFLICT`. An incomplete or internally inconsistent stored
result/error fails closed as an internal integrity error.

## 6. Command-specific canonical facts

### Create and Plan

- Project starts `active`, revision 1.
- Inquiry starts `draft`, revision 1.
- Plan proposal writes `plan.proposed`; Plan revision writes `plan.revised`.
- Duplicate Plan step IDs are rejected even though tuple length is otherwise
  bounded by the contract.

### Frozen Resource and Locator

D3-05 does not permit arbitrary host-file selection. The service receives an
internal allowlist of frozen dev Resource descriptors. The public request must
match one descriptor's portable relative logical reference, media type, data
class, and license.

The service resolves each path under its configured read root, rejects absolute
paths, traversal, symlinks, junctions/reparse components, non-regular files, and
identity changes during reading. It computes the Resource raw-byte content hash
itself. The path and root are never returned as absolute paths.

The D3-05 public Locator is limited to `local_file` for the frozen descriptor.
Its logical path and artifact hash must match the verified Resource. A line span
must be in range. The writer computes the selected quote hash using UTF-8 text,
CRLF-to-LF normalization, one-based inclusive lines, and LF joins, and requires
the request's quote hash to match. The resulting Resource is `available` and
Locator is `valid` because their bytes and coordinates were positively checked
at creation.

The existing creation Events carry the verification evidence; no unregistered
Event type is invented. `resource.registered` records status, raw-byte content
hash, descriptor ID, and verification algorithm version. `locator.created`
records status, verified Resource hash, span, quote hash, and algorithm version.
`evidence.attached` records status, Locator ID, excerpt hash, and verification
basis. Payloads contain only portable logical identifiers, never host paths.

This is a narrow, validated creation path, not a claim that arbitrary Resource
or parser support exists.

### Claim, Evidence, Hypothesis, and Relations

- Claim starts `draft`, revision 1.
- Evidence may be attached only to a `valid` Locator whose Resource belongs to
  the Inquiry's Project. Its excerpt hash must match the Locator quote hash.
  The positively checked Evidence is stored `valid`.
- A second command with the same Inquiry, Locator, direction, and excerpt hash
  is a replayable duplicate rejection. A different direction remains a
  distinct research assertion and must later match its Claim Relation type.
- `AttachEvidence` atomically creates the Evidence and its required
  `resource_contains_evidence` Relation, with two Events/outbox rows in one
  command result. The browser cannot omit or redirect that relation.
- Public `CreateRelation` is limited to `evidence_supports_claim`,
  `evidence_opposes_claim`, or `evidence_limits_claim`. It loads both endpoints,
  invokes the frozen Relation Registry, enforces same Inquiry/Project and
  direction, and rejects an already-active identical edge.
- Hypothesis starts `proposed`. It is included because the authoritative first
  vertical-slice checklist explicitly requires defining one Hypothesis before
  the locked test. D3-06 owns creation of the `hypothesis_tested_by_run`
  Relation. D3-05 must add Hypothesis to the canonical bootstrap/reducer types
  so it is not an invisible fact; D3-04 UI behavior need not change here.

### DraftFinding

The writer requires at least one distinct valid, non-stale Evidence ID or one
terminal Run. Every Evidence and Run must belong to the same Inquiry and
Project. At most one terminal Run is accepted because schema v6 and the frozen
Relation Registry define a single producer.

The Finding starts `draft`, revision 1. Evidence IDs are stored in deterministic
sorted order. If a terminal Run is present, the same transaction creates the
`run_produces_finding` Relation and its Event/outbox row. A non-terminal Run,
cross-Inquiry reference, invalid Evidence, duplicate ID, or second producer is
a replayable structured rejection.

## 7. Frozen dev fixture loader

Add a checked-in, sanitized fixture definition with stable command IDs and
portable relative Resource/Locator facts. A loader constructs the typed
requests, executes them through `CommandTransactionService`, obtains generated
canonical IDs from `affected_revisions`, and feeds those IDs into subsequent
typed requests.

D3-05 adds an internal `WorkspaceBootstrapSpec` contract and
`WorkspaceBootstrapService`. It is not browser-accessible and is not added to
the frozen D0 user Command union. On the same writer lane, before runtime ready,
it either atomically creates the one configured Workspace plus
`workspace.created` Event/outbox row, accepts an exact existing match as an
idempotent no-op, or fails startup on multiple/mismatched rows. It stores a
portable logical data root, not a username-bearing path.

The fixture composition supplies this typed seed to runtime startup. Neither
the fixture loader nor tests insert Workspace or later domain facts directly.
From Project onward the loader uses only canonical Commands. Re-running it must
yield replayed results and identical counts/IDs.

The fixture covers the selected sliding-window/non-negative-input Inquiry,
acceptance criteria, one frozen repository Resource/Locator, Claim/Evidence,
Hypothesis, and locked-test Plan. It does not create Run, Action, Grant,
Approval, Receipt, export, benchmark, counterexample implementation, or final
Decision.

## 8. Required evidence matrix

Before D3-05 can exit, tests must prove:

- accepted/replayed/replay-conflict/rejected-replay behavior for every request
  family;
- injected failure before commit rolls back domain/Event/outbox/command rows;
- response loss after commit replays the exact result/error;
- same-ID races apply once; different commands remain serialized by the one
  writer lane;
- stale revisions, missing parents, archived/cross-project objects, wrong
  directions, duplicate edges, invalid/stale Evidence, non-terminal Runs,
  multiple producers, duplicate IDs, and malformed stored replay data fail
  closed;
- no earlier Plan revision is overwritten;
- Resource path escape, absolute path, symlink/junction/reparse, content change,
  hash/span/encoding/media mismatch, and unregistered descriptors fail closed;
- the exact POST security matrix, bounded body, exact preflight, route inventory,
  server actor injection, and full-Command-type rejection;
- SSE exposes only committed outbox Events; bootstrap after a response-loss
  retry shows one canonical effect;
- runtime startup/drain/write/SQLite close/lock release remain ordered on the
  dedicated writer lane;
- default sqlite thread affinity rejects an attempted access from outside the
  owner lane; the schema's `command_log.command_id TEXT PRIMARY KEY` is asserted;
  a second runtime remains denied by the OS Workspace lock; and relation
  duplicate checks occur after `BEGIN IMMEDIATE`;
- OpenAPI and generated TypeScript expose only the curated mutation request;
- the loader's second run performs no duplicate side effect;
- execution, Approval, PolicyGrant, external effect, export, and mutation UI
  remain absent.

## 9. Codex decisions and questions for equal review

### Codex ACCEPT

- One exact authenticated POST with a closed 11-request journey union.
- Server-injected actor and required non-null expected revision.
- One dedicated SQLite writer/lifecycle thread; no free thread-pool writes.
- D1 transaction/idempotency service is extended, not bypassed.
- No schema migration unless implementation proves schema v6 insufficient.
- Frozen allowlisted local-file provenance only.
- Automatic required Relations for Evidence and terminal-Run Finding.
- D3-05 includes Hypothesis because the authoritative dev slice requires it,
  while Run linkage remains D3-06.

### Codex VETO

- A generic endpoint accepting the complete D0 Command union.
- Browser-supplied actor, raw Action/capability/PolicyGrant/Approval fields, raw
  table identities for repair, arbitrary filesystem paths, or arbitrary
  Resource kinds.
- `check_same_thread=False` without a single serialized owner.
- Optimistic UI mutation or any execution/export enablement in this stage.
- More than one terminal producer for a schema-v6 Finding.
- Treating duplicate or changed command content as success.

### Requires Claude agreement or a reasoned counterproposal

1. Is storing a Resource/Locator/Evidence directly as available/valid after
   positive in-command verification consistent with the documented initial
   state machines, or must D3-05 add explicit transition commands/events?
2. Is the no-schema-v7 decision strong enough when active Relation uniqueness
   is enforced by the sole `BEGIN IMMEDIATE` writer rather than a database
   unique index?
3. Does revision binding to the listed parent/revisioned endpoint give every
   create command a meaningful stale-view witness without inventing collection
   revisions?
4. Should `CreateHypothesis` stay in D3-05 to satisfy the authoritative dev
   slice, despite the shorter D3 stage deliverable list not naming it?
5. Is one curated discriminated-union POST preferable to separate endpoints
   under the frozen default-deny route inventory?

## 10. First Claude review disposition

Claude's first overall verdict is **NOT YET CONSENSUS**. The normalized response
is in `docs/claude_d3_05_first_review_response_sanitized.md`.

- P0-1: ACCEPT the need for structural evidence; VETO the inference that schema
  v7 is already required. Schema v6 defines `command_log.command_id` as a
  primary key. The dedicated default-affinity connection, one executor, OS
  Workspace lock, and post-BEGIN duplicate check are now explicit hard gates.
  Failure of any gate reopens schema-v7 ownership before implementation exit.
- P0-2: ACCEPT. The candidate now includes an internal typed, idempotent
  Workspace bootstrap service and forbids fixture SQL even for the prerequisite.
- P1-1/P1-2/P1-4 and all P2 items: ACCEPT and incorporated above or in the
  evidence matrix.
- P1-3: ACCEPT. AttachEvidence now binds Locator revision. The uniform rule is
  the revisioned input whose content/validity is consumed; other endpoint scope
  and status are checked live in the same transaction.
- P1-5: VETO deferral. The authoritative first vertical-slice checklist requires
  a Hypothesis before the locked test. D3-05 owns its typed creation/projection;
  D3-06 explicitly owns `hypothesis_tested_by_run`, preventing a permanent
  orphan while preserving execution boundaries.
- Verified-at-creation audit: ACCEPT Claude's condition using richer existing
  creation Event payloads, without expanding the closed Event type registry.
