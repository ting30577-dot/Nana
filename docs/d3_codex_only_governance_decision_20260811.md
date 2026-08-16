# D3 Codex-only governance decision

Date: 2026-08-11  
Decision authority: product owner  
Applies to: D3-06 implementation exit, D3-07, D3-08A, D3-08B and D3-09

## Decision

The product owner explicitly withdraws Claude review as a prerequisite for
continuing or accepting the remaining D3 stages. Codex is the sole current
design reviewer, implementation owner, security reviewer, test operator,
evidence synchronizer and final acceptance authority for D3.

Claude must not be called, retried, awaited or replaced by a manual relay. All
historical Claude packets, screenshots, responses and transport failures remain
historical evidence only. A transport failure is not an ACCEPT or VETO, and the
historical `NOT YET CONSENSUS` results remain truthful historical states rather
than current decisions.

## What this changes

- The missing Claude D3-06 implementation-exit verdict no longer blocks a
  Codex independent implementation audit.
- The former joint-signature requirement for D3-07 through D3-09 is replaced by
  an explicit Codex-only stage decision after the same implementation, test,
  no-edit scan, repair and evidence-closure protocol.
- The latest product-owner instruction supersedes the historical pause after
  D3-07. After each real stage exit, Codex continues through D3-08A, D3-08B and
  D3-09 until the complete D3 journey is proven.

## What this does not change

This governance change is not an automatic security ACCEPT and does not itself
authorize Approval implementation, capability registration, mutation-route
expansion or a Workspace-outside byte.

The machine gate remains closed at the time of this record:

```text
implementation_authorized=false
capability_registered=false
filesystem_write_authorized=false
```

D3-07 may open for implementation only after Codex completes and records:

1. an independent D3-06 code-and-evidence audit that closes historical gaps
   F-A through F-E without relying on narrative test counts;
2. a D3-07 07-00 design/security re-review of F1 through F9 and F07-16 through
   F07-31 against the live implementation seams;
3. an explicit Codex-only entry decision preserving every fail-closed rule.

## Preserved non-negotiable invariants

- The browser never derives authorization, selects a capability, supplies a
  path/filename/raw bytes/hash/risk/effect or treats local state as canonical.
- D2 admission, scheduler, budget, executor, durable authorization and Receipt
  remain the owner-lane authority. D3 does not re-query PolicyGrant/Approval to
  invent authorization and does not bypass those primitives.
- D3-06 remains the exact trusted fixture-only T2
  `python.unittest.locked` boundary. It is not a hostile-code sandbox and does
  not authorize arbitrary shell, arbitrary Python, network or external writes.
- D3-07 may register only the exact one-time, non-grantable T3 candidate
  `export.draft_external`; T4 `export.publish`, `PublishExport`, remote publish
  and public `ConsumeApproval` remain forbidden.
- Approved Approval decision, Action authorization, one-time consumption,
  Approval/Action Event/outbox, durable authorization and stable command result
  must commit in one owner-lane SQLite transaction. Denied, expired, changed or
  replayed subjects never authorize or consume.
- Selection remains 60-minute maximum, LocalSession-bound and one-attempt.
  Raw path, handle, clear filesystem identity and opaque token remain owner
  process memory only; durable commitments are irreversible and non-locating.
- Selection checks are read-only. Atomic Approval/consumption commits before a
  durable first-write fence, which commits before any probe or external byte.
  There is no non-atomic fallback, overwrite, retry, resume or rebinding.
- Before-byte failure is `failed` with empty effects; a proven-cleaned probe is
  `failed` with its actual effects; unverifiable residue or any post-fence
  uncertainty is terminal `effect_unknown`. The UI never displays uncertainty
  as success or offers retry/resume/local dismissal.
- Draft bytes are deterministic public-only UTF-8/NFC/LF `text/markdown`, have
  exactly one trailing LF, are at most 4096 bytes, use the frozen renderer and
  DRAFT marker, and pass 50 export credential canaries with zero matches.
- Workspace lock, reconciliation readiness, sole authenticated runtime,
  canonical projection, sparse SSE semantics, Artifact visibility and
  response-loss idempotency remain mandatory.

## Stage evidence rule

Every remaining stage still requires candidate implementation, complete
no-edit scan, consolidated F-numbered findings, batch repair, final no-edit
re-review, focused strict verification, full verification, browser evidence
where applicable, decision record, evidence summary, manifest and digest,
authority-index synchronization and an explicit Codex-only ACCEPT or VETO.

No historical filename, screenshot, packet, passing count or transport record
may substitute for direct live-worktree evidence. D3 is complete only after the
real React journey, controlled export, Receipt, crash/restart and
`effect_unknown` paths, ten consecutive no-retry browser journeys, manifest
integrity and final Codex-only acceptance all pass.

## Current decision state

- Governance change: **ACCEPT**.
- D3-06 Codex independent re-audit: **ACCEPT**, recorded in
  `docs/d3_06_codex_independent_exit_20260811.md`.
- D3-07 Codex-only entry/security decision: **pending live review**.
- D3-07 implementation/capability/filesystem write: **not authorized yet**.
- D3-08A, D3-08B and D3-09: remain ordered after real predecessor exits; they
  are no longer globally paused by the historical handoff.
