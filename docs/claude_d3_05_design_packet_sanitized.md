# D3-05 equal design review packet (sanitized)

Date: 2026-08-08
Purpose: joint decision before any D3-05 implementation

## Privacy statement

This packet contains only relative module names, public contract facts, test
counts, software versions, and design arguments. It contains no credential,
environment value, machine/user identity, private network address, hardware
identifier, or username-bearing absolute path.

## Accepted entry state

- D0, D1, and D2 are complete.
- D3-00 through D3-04 have joint Codex + Claude ACCEPT.
- D3-04 proves an authenticated read-only React cockpit, canonical bootstrap,
  fetch + ReadableStream SSE, sparse replay/recovery, static route default deny,
  and no mutation serving.
- D3-04 exit evidence: 306 Python tests OK with one existing skip; 37 strict
  D3 ResourceWarning-as-error tests OK with one skip; 23 Vitest tests; 11
  system-browser E2E tests with no retries; D3-04 26-entry manifest with zero
  mismatch.
- The pre-existing interpreter-shutdown ResourceWarning was not observed in the
  strict D3 lock/runtime/read-model gate.
- D3-05 is authorized for design only. Implementation remains prohibited until
  this review reaches a joint decision.

Claude previously noted two non-blocking D3-04 evidence-strength questions:
whether F6 merits an additional clean-environment direct replay record, and
whether F1/F2 merit another independent code-level audit. They do not authorize
or broaden D3-05.

## Frozen D3-05 purpose

Implement the minimum canonical journey mutations before execution:

- stable command ID, deterministic request hash, and expected revision;
- typed creation/loading of the frozen dev Inquiry/provenance fixture;
- Resource, Locator, Claim/Evidence, required Relations, Plan revision, and
  DraftFinding linked to valid Evidence or a terminal Run;
- domain facts, Events, outbox rows, and command result in one transaction;
- structured rejection replay and replay conflict;
- no raw SQL, Action, capability, PolicyGrant, Approval, export, or generic
  Python/shell browser input;
- execution remains disabled.

Schema-v6 and D1 facts are inputs, not claims newly introduced by D3-05.

## Current implementation facts relevant to review

1. `CommandTransactionService` currently supports only `RevisePlan`. It uses a
   deterministic full-command hash, `BEGIN IMMEDIATE`, command-log double-check,
   atomic Plan/Event/outbox/result writes, accepted/rejected replay binding, and
   fail-closed corruption checks.
2. Existing schema-v6 tables already include Workspace, Project, Inquiry, Plan,
   Resource, Locator, Claim, Evidence, Hypothesis, Finding, Relation, Run, Event,
   outbox, and command log.
3. `findings` stores multiple Evidence IDs but one nullable producer Run. The
   Relation Registry also limits `run_produces_finding` to one incoming
   producer and requires a terminal same-Inquiry Run.
4. The Relation Registry constrains shapes, direction, same Project/Inquiry,
   cardinality, producer identity, cycles, and minimum Finding provenance.
5. The runtime currently validates that no mutation method exists. Any D3-05
   POST therefore needs an explicit replacement with an exact route allowlist;
   default deny must remain for future routes.
6. Runtime startup currently calls `WorkspaceRuntime.start` on a generic worker
   thread. The resulting default sqlite3 connection cannot safely be used by
   arbitrary later worker threads. This becomes material only when D3-05 opens
   writes.
7. Existing command contracts require an `actor` and allow optional
   `expected_revision`. A browser must not be able to claim a system/agent/tool
   audit identity.
8. `RegisterResource` does not accept a content hash. A valid frozen local-file
   registration therefore needs server-side path confinement and hash/Locator
   verification, not trust in a browser assertion.
9. `AttachEvidence` has no separate public Evidence status transition command.
   `DraftFinding` must nevertheless accept only valid Evidence.

## Codex candidate design

The full independent proposal is in
`docs/codex_d3_05_independent_design.md`. Its core choices are:

### Runtime and HTTP

- Add exactly `POST /api/v1/journey/commands`.
- Accept a closed request union of CreateProject, CreateInquiry, ProposePlan,
  RevisePlan, RegisterResource, CreateLocator, CreateClaim, AttachEvidence,
  CreateHypothesis, CreateRelation, and DraftFinding.
- Do not accept the complete D0 Command union.
- Omit actor from HTTP input; inject a fixed local-session user actor.
- Require non-null positive expected revision for every public request.
- Authenticate before reading the body; exact JSON media type; reject content
  encoding; enforce 64 KiB while consuming ASGI chunks; exact POST preflight.
- Replace the no-mutation validator with an exact route inventory allowing only
  this POST and rejecting every other mutation method/path.
- Add a runtime-specific truthful handshake: curated mutations enabled,
  execution/external effects disabled. Keep the D0 read-only handshake intact.

### Writer ownership and transactions

- Run `WorkspaceRuntime.start`, every command transaction, and
  `WorkspaceRuntime.close` on one dedicated single-thread executor. Do not use
  unconstrained `check_same_thread=False` access.
- Extend the D1 transaction service instead of creating a parallel idempotency
  system.
- Atomic sequence: hash, replay pre-check, BEGIN IMMEDIATE, replay re-check,
  validation, domain rows, Event/outbox, accepted or rejected command log,
  commit, response.
- Accepted replay validates domain revision plus every Event/causation/outbox
  binding. Rejected replay validates command type/hash and a normalized safe
  witness stored in error details. Changed content is always replay conflict.

### Revisions and scope

- CreateProject binds Workspace revision.
- CreateInquiry/RegisterResource bind Project revision.
- ProposePlan/CreateClaim/AttachEvidence/CreateHypothesis/DraftFinding bind
  Inquiry revision.
- CreateLocator binds Resource revision.
- RevisePlan binds Plan revision.
- Public CreateRelation is limited to Evidence-to-Claim direction relations
  and binds Claim revision.
- Creates do not increment the parent; expected revision witnesses the source
  view/scope. Created facts start at revision 1.
- ProposePlan creates revision 1 `proposed`; RevisePlan appends a new `draft`
  revision and never overwrites history.

### Provenance

- D3-05 accepts only internal allowlisted frozen local-file descriptors, never
  arbitrary host paths or Resource kinds.
- Resolve under a configured read root; reject traversal, absolute paths,
  links/junctions/reparse components, non-regular files, or identity change.
- Compute Resource raw-byte hash server-side.
- Require local-file Locator path/hash/span and quote hash to match; quote hash
  uses UTF-8, CRLF-to-LF normalization, one-based inclusive lines, and LF joins.
- Store positively verified Resource/Locator/Evidence as
  available/valid/valid.
- AttachEvidence atomically adds the required resource_contains_evidence
  Relation and two Events/outbox rows.
- Public CreateRelation allows only supports/opposes/limits Evidence-to-Claim,
  validates the registry, and rejects active duplicates.
- Include Hypothesis in D3-05 because the authoritative dev slice requires it;
  Run linkage remains D3-06.
- DraftFinding accepts distinct valid same-Inquiry Evidence and at most one
  terminal same-Inquiry/Project Run. A Run producer atomically creates
  run_produces_finding. Evidence IDs are sorted for deterministic storage.

### Schema and fixture

- Do not migrate schema v6 unless implementation proves writer-only enforcement
  insufficient. If insufficient, stop and own schema v7 plus migration evidence
  in D3-05; never add an ad-hoc table.
- A sanitized fixture definition has stable command IDs and relative resource
  facts. Its loader uses typed service commands from Project onward and feeds
  returned IDs into later commands. The sole prerequisite is an already-created
  Workspace row. A second load must replay with identical IDs/counts.

## Codex current decisions

- ACCEPT: one exact closed-union POST; server actor; required revisions; one
  SQLite writer/lifecycle thread; D1 transaction extension; allowlisted frozen
  provenance; automatic mandatory Relations; Hypothesis inclusion.
- VETO: full Command-union route; browser actor; arbitrary path/resource kind;
  raw Action/authorization inputs; unowned thread writes; optimistic UI facts;
  multiple Finding producers; execution/export in D3-05.
- NOT YET CONSENSUS: verified-at-creation statuses versus explicit transition
  events; no schema-v7 unique index; exact expected-revision mapping; Hypothesis
  ownership; one union POST versus separate routes.

## Review request

Please independently assess the proposal rather than merely endorsing it.
Return:

1. P0/P1/P2 findings with concrete contract evidence and a counterproposal;
2. an explicit ACCEPT, VETO, or NOT YET CONSENSUS for each of these five items:
   verified-at-creation status, schema-v6/no migration, revision mapping,
   Hypothesis ownership, one closed-union POST;
3. a decision on the single-thread writer lifecycle and server-injected actor;
4. any missing replay-binding, cardinality, cross-project, route-security,
   shutdown, or fixture-direct-SQL failure mode;
5. an overall D3-05 design verdict: ACCEPT, VETO, or NOT YET CONSENSUS.

An ACCEPT authorizes implementation of D3-05 only. It does not authorize D3-06
execution, D3-07 Approval/export, D3-08 mutation UI, arbitrary Resource access,
or any broad sandbox claim.
