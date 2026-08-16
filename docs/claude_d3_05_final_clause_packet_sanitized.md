# D3-05 final design clauses (sanitized)

Date: 2026-08-08
State: final clarification before implementation decision

## Privacy statement

This packet contains only relative module facts and design clauses. It contains
no secret, environment value, identity, private address, hardware identifier,
or username-bearing absolute path.

## Clause 1 — Event registry facts

No Event type is added by D3-05.

The existing closed `EventType` enum in
`nana_sidecar/contracts/domain.py` already contains all five types used by the
revised D3-05 design:

- `workspace.created`
- `resource.registered`
- `locator.created`
- `evidence.attached`
- `hypothesis.created`

The schema-v6 `events.type` CHECK constraint in
`nana_sidecar/storage/schema.py` also already contains all five literals. The
D0 contract catalog and generated OpenAPI already expose them. D3-05 only makes
the existing creation payloads more explicit; it does not amend the enum or
schema constraint.

The internal Workspace bootstrap emits existing `workspace.created`.
The public CreateHypothesis writer emits existing `hypothesis.created`.

## Clause 2 — creation channels are distinct and frozen

Workspace and Hypothesis do not share a channel.

- Workspace is a storage-lifecycle prerequisite. It is created only by the
  internal typed `WorkspaceBootstrapService` on the owner lane before ready.
  It is not a browser Command and is not in the mutation route inventory.
- Hypothesis is a normal research-domain user mutation. `CreateHypothesis` is
  one of the 11 explicitly listed members of the closed
  `JourneyCommandRequest` union accepted by the sole
  `POST /api/v1/journey/commands` route. It is already a member of the frozen
  D0 Command catalog. It is never created by bootstrap.
- The fixture loader calls the same curated CreateHypothesis service path as the
  HTTP adapter; it does not insert Hypothesis, Event, or outbox rows directly.
- D3-05 adds Hypothesis to canonical bootstrap/reducer data. D3-06 owns the
  existing `hypothesis_tested_by_run` Relation after it creates a Run.

Route-inventory tests therefore treat CreateHypothesis as a discriminator under
the one allowed POST, while Workspace bootstrap remains a traced internal
lifecycle service with no HTTP route.

## Clause 3 — server actor is closed

Every HTTP request variant derives from the strict contract base with unknown
fields forbidden, and the curated request models omit `actor`. A body containing
`actor` is therefore a validation error; it is not ignored.

After validation, the HTTP adapter constructs the canonical existing Command
with a configured non-secret local principal:

- actor kind: `user`
- actor ID namespace: `local-session-user`
- no browser-provided kind, ID, or version is copied
- the injected actor is included in the deterministic request hash, Event actor,
  and command-log actor

Tests submit `system`, `agent`, `tool`, nested actor, duplicate discriminator,
and unknown-field variants and require rejection before service dispatch. They
also assert the stored command/Event actor equals the injected local user.

## Clause 4 — body limit is closed

The runtime security gate authenticates exact Host, Origin, and single Bearer
header before consuming mutation body bytes.

For the one POST it then:

- requires exactly one JSON Content-Type with no unsupported parameters;
- rejects any Content-Encoding;
- rejects a declared Content-Length above 64 KiB before body parsing;
- wraps the ASGI receive stream and counts actual chunks, returning 413 as soon
  as the cumulative body exceeds 64 KiB even when Content-Length is absent,
  false, or smaller;
- passes only the already-bounded bytes to strict Pydantic validation;
- never includes body content, token, path, or traceback in an error.

Tests cover absent/duplicate/invalid media type, encoded content, truthful and
lying Content-Length, chunked overflow, exact-boundary success, unauthorized
oversized input (authentication fails before body consumption), and body parser
non-invocation on rejected security requests.

## Clause 5 — schema-v6 defense in depth

The schema-v7 partial-index idea is recorded as a non-blocking defense-in-depth
candidate, not silently rejected. The D3-05 v6 decision remains conditional on
all owner-lane and transaction tests.

Add an explicit regression guard that scans active Relations after sequential,
racing, replay, crash, and response-loss matrices and asserts:

- no duplicate active exact edge;
- at most one incoming active `resource_contains_evidence` edge per Evidence;
- at most one incoming active `run_produces_finding` edge per Finding;
- every stored Finding producer agrees with its active Relation.

Any failure before D3-05 exit changes the decision to a D3-05-owned schema-v7
migration with full migration evidence.

## Requested final design decision

Please decide whether clauses 1-5 close every remaining design blocker. Return
one of ACCEPT, VETO, or NOT YET CONSENSUS for:

1. existing Event registry coverage;
2. distinct Workspace/Hypothesis creation channels;
3. server-injected actor;
4. 64 KiB authenticated body gate;
5. schema-v6 defense-in-depth guard.

Then give one overall D3-05 design verdict. ACCEPT authorizes implementation of
D3-05 only. It does not authorize D3-06 execution or any later-stage scope.
