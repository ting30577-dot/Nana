# Nana D3-00 Claude convergence response (sanitized)

Claude reviewed the single sanitized convergence packet as an equal, read-only
co-designer. It did not claim repository edits or local test execution.

## Overall result

Claude accepted most of the proposed boundary but did **not** accept that all
five original NOT CONSENSUS items were resolved. It retained three blockers:

1. the decide-Approval to consume/authorize crash window lacked an explicit
   atomicity or idempotent-recovery test;
2. Event ID gaps caused by rollback could conflict with a client algorithm that
   incorrectly treats integer non-contiguity as missing delivery;
3. the standalone fixture/replay viewer had not been fixed as either the same
   or a second client/API contract.

Claude also required the narrow T3 export test target to be controlled and
partial/crashed export to become `effect_unknown` rather than synthetic
success.

## Five original questions

| Question | Claude result |
|---|---|
| D2 mutation composition entry | ACCEPT: internal primitives exist; D3 adds typed orchestration and missing writers |
| One-time Approval path | Boundary accepted, evidence not closed until decide/consume crash semantics are explicit |
| Event/outbox order | Ordering accepted; client gap semantics not yet closed |
| Canonical reads before ready | ACCEPT the proposed VETO; only health/handshake before convergence |
| `effect_unknown` UX | ACCEPT the read-only incident/quarantine boundary |

## F1-F4

- F1 provenance projections beyond a Run-only UI: **ACCEPT**.
- F2 pending Action/Event projection plus server-side typed Approval decision:
  **ACCEPT with contract tests**.
- F3 separate T3 export security gate: **ACCEPT with strongest gate**;
  external-target partial crash must be `effect_unknown`.
- F4 snapshot and cursor from the same SQLite read transaction: **ACCEPT**.

## Decision table

| Decision | Claude result |
|---|---|
| Workspace lifecycle first | ACCEPT |
| Physical mount/combine frozen D0 app | VETO |
| New authenticated runtime factory as OpenAPI authority | ACCEPT with gates |
| Canonical query/SSE before ready | VETO |
| Standalone fixture/replay viewer before mutation | ACCEPT, contract ownership unresolved |
| Typed journey application layer over D2 | ACCEPT with boundary/Event tests |
| D3/UI authorization re-derivation | VETO |
| Narrow exact-target T3 export | ACCEPT with separate controlled security gate |
| EventSource or optimistic terminal state | VETO |
| Transaction-consistent snapshot plus ordered fetch stream | ACCEPT, ID-gap semantics required |
| Ten E2E runs with retries | VETO; consecutive no-retry only |

## Required closure conditions

1. Name and design a test for crash between Approval decision and authorization
   consumption, proving restart applies authorization at most once or proving
   atomic rollback.
2. Specify that Event gap semantics are not based on dense integer IDs.
3. Fix fixture/replay viewer contract ownership without creating a second
   public client/API authority.
4. Make the D3 T3 export target controlled for E2E and classify partial/crashed
   unverifiable effects as `effect_unknown`.

Claude explicitly withheld final D3-00 signature until conditions 1-3 are
closed. This status must remain NOT CONSENSUS until a final review accepts the
resolution.

