# D3-03 closure evidence and complete finding map (sanitized)

## Original findings and contracts

| Finding | Original concern | Closed contract / future executable assertion |
|---|---|---|
| F2 | Authorization-display might re-derive PolicyGrant/Approval | Bootstrap returns no Authorization-display, Grant, Approval, or authorization ref. Needs You contains only stored Action `waiting_approval`; no other Needs You source exists in D3-03. |
| F3 | Blacklist could leak Action/Receipt/Finding data | Per-type whitelist: Workspace id/status/schema/revision; Inquiry/Claim/Finding text/status/provenance; Resource/Locator logical refs/hash/status only; Plan revision/status/step title+approval flag; Run/Action id/state/timestamps/capability only; Artifact id/hash/size/media/state/producer; Receipt id/action/result/effect-violation/usage counters only. Absence tests reject paths, args, policy JSON, effects, undo, logs, tokens, approval material. |
| F5 | Exact duplicate was undefined | `fingerprint = sha256(canonical_json(event))`; canonical JSON is UTF-8 sorted-key compact JSON with UTC timestamp normalization. Same id+fingerprint ignores; same id+other fingerprint is `E_EVENT_ID_CONFLICT`; lower new id is `E_EVENT_ID_DECREASING`. |
| F6 | Sequence violation was undefined | Snapshot carries `aggregate_version_by_id` and `run_seq_by_id`. Every incoming event, including unknown type, requires aggregate version exactly prior+1; if `run_id` is present it requires run seq exactly prior+1. No input sort/reorder. Invalid event returns structured error and cursor is unchanged. |
| F9 | Fixture equivalence was not executable | Canonical normalized projection JSON hash sorts maps/keys, omits transport timestamps only, and preserves event order. Six negative assertions: out-of-order, duplicate same fingerprint, duplicate conflict, decreasing ID, sequence jump, reducer error/fresh-bootstrap. |
| F10 | UI sufficiency was untestable | Read model supports Workspace status, Inquiry/Plan rail, Run/Action/Receipt, Artifact/Finding provenance, Activity, and literal Action waiting-approval cards. No mutation controls are in this stage. |
| F13 | Finding-to-contract closure was not traceable | This complete table is the F13 artifact. Every first-review finding above maps exactly once; F1/F4/F7/F14/F15 are independent rows below. |
| F14 | 2 MiB limit could dead-end clients | Oversize returns error with permitted sections. Section pages use opaque high-water/offset token and filter `event.id <= high_water`; no silent truncation. |
| F15 | Unknown event might conflict with sequence handling | Unknown event has normal Event envelope and therefore advances the same aggregate/run watermarks after +1 validation. It adds activity+degraded only, never a domain patch. A later known event observes the advanced watermark and must be +1. |

## Independent first-review items

- F1: `BEGIN` query-only transaction; all snapshot rows and high-water read in
  that snapshot; oversize is structured error.
- F4: any reducer conflict/sequence error keeps cursor unchanged and requires
  fresh bootstrap; no local repair.
- F7: unknown event is visible activity with degraded flag, never inferred
  domain success.

## Needs You coverage boundary

D3-03 supports exactly one authoritative Needs You fact: persisted Action state
`waiting_approval`. All other user-interaction surfaces (approval decision,
export, receipt actions) are deliberately later D3-08B work and are absent,
not silently hidden. Thus no D3-03 legal source is omitted.

## Sequence liveness

Every Event, known or unknown, participates in the same envelope watermarks.
There is no separate unknown-event sequence and no integer-ID continuity rule.
If a transport or server error produces a version gap, reducer stops and fetches
a new snapshot; if the canonical source still has a gap, it remains degraded
and performs no mutation. This is intentional fail-closed behavior.

## Decision request

Confirm F2/F3/F5/F6/F9/F10/F13/F14/F15 CLOSED and return final D3-03 design
ACCEPT, VETO, or 尚未达成共识. No implementation has begun.
