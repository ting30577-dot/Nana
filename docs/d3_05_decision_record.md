# D3-05 design decision record

Date: 2026-08-08
Status: **joint design ACCEPT; D3-05 implementation authorized**

## Joint result

- Codex: ACCEPT after independent design, source inspection, and two rounds of
  counterargument/repair.
- Claude: ACCEPT for D3-05 implementation only, with explicit implementation
  exit gates.
- Joint decision: D3-05 implementation may begin. D3-06 and every later stage
  remain prohibited.

## Accepted decisions

| Item | Joint state |
|---|---|
| one strict closed-union POST | ACCEPT |
| server-injected local-user actor; body actor forbidden | ACCEPT |
| dedicated SQLite owner lane for start/write/close | ACCEPT |
| schema v6 conditional no-migration | ACCEPT with v7 fallback if gates fail |
| internal typed Workspace bootstrap; no HTTP Workspace creation | ACCEPT |
| verified-at-creation with existing Event types and explicit payload evidence | ACCEPT |
| revision binds the directly consumed revisioned input | ACCEPT |
| Hypothesis via curated CreateHypothesis; D3-06 owns Run relation | ACCEPT |
| Evidence duplicate and explicit cross-scope checks | ACCEPT |
| exact authenticated 64 KiB body gate and default-deny route inventory | ACCEPT |

## Mandatory exit gates

1. Prove `workspace.created`, `resource.registered`, `locator.created`,
   `evidence.attached`, and `hypothesis.created` already exist in the Event enum
   and schema-v6 CHECK; D3-05 must not add an Event type.
2. Prove no HTTP path creates Workspace and bootstrap never creates Hypothesis.
3. Prove actor injection, unknown/body actor rejection, and command/Event actor
   persistence.
4. Prove authentication occurs before body consumption and exact/overflow body
   boundaries.
5. Prove owner-thread lifecycle, command-ID uniqueness, transaction replay,
   active-edge cardinality, cross-scope denial, and strict ResourceWarning
   shutdown. Any active-edge/owner-lane failure VETOs schema v6 and triggers a
   D3-05-owned schema-v7 migration before exit.
6. Run the frozen fixture twice entirely through typed services from Workspace
   bootstrap onward and prove identical IDs/counts with no duplicate effects.

## Frozen exclusions

No StartRun, Action, admission, scheduler, executor, authorization,
PolicyGrant, Approval, Artifact commit, external effect, export, mutation UI,
arbitrary Resource path/kind, generic Python/shell, or broad sandbox claim is
authorized.

## Review protocol

After the complete candidate is implemented, freeze edits and perform a full
no-edit scan. Record every finding as F#, finish the scan before repairs, batch
repair all accepted findings, then perform a second full review and final
Claude exit review.

## Implementation scan status

- First frozen scan: complete; findings F-01 through F-19 recorded in
  `docs/d3_05_first_scan_findings.md`.
- Repairs: F-01 through F-17 and F-19 repaired locally; F-18 remains an
  explicit shutdown-warning attribution caveat.
- Second no-edit scan: local **ACCEPT**, recorded in
  `docs/d3_05_second_scan.md`.
- Evidence: D0 manifest self-check is green; D3-05 completion and manifest are
  synchronized.
- Claude first repair adjudication: **NOT YET CONSENSUS**. It accepted most
  implementation evidence but required an exact finding-to-test matrix and
  explicit schema-v6 no-migration proof; those gaps are now addressed.
- Claude final repair review: **NOT YET CONSENSUS**. It accepted F-01–F-05,
  F-07–F-12, F-14, and F-16–F-19; accepted F-06/F-15 with the explicit Windows
  symlink-privilege caveat; and kept F-13 open pending repeated/staggered race
  evidence. The local test now runs five fresh-workspace rounds with eight
  staggered command IDs per round, now released through an `asyncio.Barrier`
  with all eight arrivals asserted; the local test runs twenty rounds and
  checks exact duplicate-active-relation errors. A final Claude confirmation is still
  required, so this record does not claim joint implementation-exit ACCEPT.
- The final F-13 confirmation request returned HTTP 403
  `INSUFFICIENT_BALANCE` before a verdict. This is recorded as an external
  review-capacity blocker; D3-06 remains prohibited.

## Joint exit closure

- Clean current-packet Claude confirmation: **ACCEPT** for F-01 through F-19.
- D3-05: **joint ACCEPT**.
- Schema v6: **ACCEPT**, with the existing schema-v7 fallback gate.
- D3-06: **opened for its own design only**; no D3-06 implementation or
  acceptance is implied by this record.
