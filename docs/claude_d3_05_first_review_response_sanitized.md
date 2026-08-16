# Claude D3-05 first design review response (sanitized)

Date: 2026-08-08
Overall verdict: **NOT YET CONSENSUS**

## Item decisions

| Item | Claude decision | Reason |
|---|---|---|
| Verified-at-creation states | ACCEPT with conditions | Server verification is deterministic and replayable; creation Events must retain verification evidence. |
| Schema v6 / no migration | NOT YET CONSENSUS | Correctness depends on the proposed single-writer invariant; structural enforcement and command-log uniqueness evidence were not included. |
| Expected-revision mapping | NOT YET CONSENSUS | AttachEvidence implicitly creates a Relation while binding Inquiry, whereas public CreateRelation binds Claim; the consumed-entity rule was not uniform. |
| Hypothesis ownership | NOT YET CONSENSUS | The short D3-05 purpose list did not name it and the packet did not freeze its later Run relation. |
| One closed-union POST | ACCEPT with conditions | The union must be strictly discriminated, unknown variants rejected, and the route inventory frozen by regression tests. |
| Single-writer lifecycle | ACCEPT with conditions | Start, transactions, and close must stay on the owner thread; draining must reject writes and failures must close fail-closed. |
| Server-injected actor | ACCEPT with conditions | Body actor fields must be forbidden and the injected principal must use a distinct audited namespace. |

## Findings

### P0-1 — single-writer invariant and the no-migration decision

Claude requested source evidence that the single-writer lane is structurally
enforced, that cross-thread access fails, and that command IDs are database
unique. If these cannot be proven, Claude proposed schema v7 uniqueness as the
fallback.

### P0-2 — Workspace fixture prerequisite

The request union begins with CreateProject and has no CreateWorkspace. A
fixture that inserts the prerequisite Workspace with ad-hoc SQL would violate
the typed-writer boundary. Claude required an existing controlled canonical
bootstrap mechanism or a typed initializer, plus a test that the fixture has no
direct domain writes from Project onward.

### P1 findings

1. Define whether two different command IDs may create semantically identical
   Evidence. Claude recommends rejecting the same Inquiry + Resource/quote fact.
2. Make cross-Project and cross-Inquiry validation explicit for every composed
   endpoint, especially Resource-to-Evidence and Run-to-Finding.
3. Unify the expected-revision rule for automatic and public Relation writes.
4. Close the persistent writer connection on its owner thread and include it in
   the strict ResourceWarning gate.
5. Keep Hypothesis only if its authoritative fixture role and later relation
   owner are explicit; otherwise defer it.

### P2 findings

- Rejected-replay witnesses must not expose host paths.
- Freeze the complete mutation-route inventory in a regression test.
- A writer-lane failure and shutdown-time request must fail closed.
- Verified-at-creation must retain its hash/verification basis in an Event.

## Conditions for a second decision

Claude requested:

1. structural single-writer and command-log uniqueness evidence, or schema v7;
2. a non-ad-hoc typed Workspace bootstrap path;
3. Evidence duplicate semantics, explicit scope checks, and a consistent
   revision rule;
4. owner-thread close in the strict warning gate;
5. a Hypothesis handoff decision;
6. verification evidence in creation Events and a frozen route-inventory test.

Claude did not execute tests, read raw source/logs, or modify files.
