# Nana D3 full-plan final closure (sanitized)

This final closure packet addresses only F10/F11 from Claude's post-repair
review. It contains no credentials, environment values, literal authorization
values, absolute user paths, machine identity, private network information, or
hardware identifiers.

## F10 — R1 stage ownership

- D3-06 executes only the exact frozen T2 `python.unittest.locked` Action using
  the frozen project PolicyGrant admission path.
- D3-06 does not create, decide, authorize from, or consume a one-time Approval.
- D3-07 is the first D3 stage that implements and proves the new combined R1
  transaction: Approval decision → Action authorization → authorization Event/
  outbox → durable authorization material → Approval consumption → stable
  command result, all under D2 admission ownership in one transaction.
- Thus D3-06 cannot silently exercise R1 before D3-07 proves it.

Codex decision: ACCEPT this mapping; any one-time Approval use in D3-06 is VETO.

## F11 — schema v6 and lock persistence

- Workspace ownership is intentionally not persisted in SQLite. The live OS
  lock handle is the only authority.
- A database row or file marker cannot authorize ownership because it becomes
  stale after process death; relying on one is VETO.
- Schema v6 already contains the Event/outbox/Artifact metadata required by the
  existing D1 reconciler that D3-01 integrates.
- D3-01 adds no canonical table and requires no schema migration.
- The global rule remains: the earliest later stage that needs a schema change
  owns migration, rollback, read ceiling, round-trip, contract stability, and
  generated-client evidence in that stage.

Codex decision: ACCEPT; persisted lock authority is VETO.

## Requested final verdict

Please determine whether F10/F11 are closed. If they are, state whether D3-00
and the overall D3-00→01→02→03→04→05→06→07→08A→08B→09 order are ACCEPT and
whether D3-01 formal no-edit scan may begin. If not, preserve the exact
remaining NOT CONSENSUS item. Do not claim local test execution or file edits.
