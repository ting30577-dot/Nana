# Nana v0.3.0-dev D3 current authority

<!-- nana-current-authority
status: acceptance_complete_baseline_pending
technical_slice_status: sol_accept
d3_complete: true
release_baseline_frozen: false
gate_json: docs/evidence/v0.3.0-dev-d3-09-gate-decision.json
-->

Date: 2026-08-17
Status: **D3 acceptance complete; release-baseline refreeze pending**

This is the single repository authority for the current D3 worktree. Earlier
handoffs, completion audits, scan packets, acceptance records and evidence
summaries are historical snapshots unless this page explicitly cites them.

## Implemented scope

- Product launcher: OS-assigned loopback port, automatic browser open,
  fragment-only one-time bootstrap secret, memory-only Bearer exchange, no
  credential on stdout, replay rejection, and refresh recovery through an
  HttpOnly same-site recovery cookie. Product E2E performs the real exchange;
  it does not inject a global Authorization header.
- Run controls: browser-safe `PauseRun` and `ResumeRun`, durable canonical
  transitions, optimistic `expected_revision` checks for Pause/Resume/Cancel,
  real affected Run revisions, real Windows/POSIX worker suspension,
  pause-excluded timeout budget, cancel/shutdown compatibility and visible UI
  controls. A stale Cancel cannot trigger the in-memory worker signal.
- Failed Run retry: `StartRun.retry_of_run_id`, failed-only same-scope
  validation, atomic `runs.retry_of_run_id` plus `run_retry_of_run` Relation,
  isolated Run authorization budget, visible Retry control and browser proof.
- Workspace lifecycle: second owner rejection, second port/Workspace reuse
  rejection, crash lock release, startup reconciliation, browser reload while
  paused, and active-run shutdown settlement.
- Local Web security: exact loopback Host and Origin, forwarded-header denial,
  cross-Origin mutation rejection before writes, DNS-rebinding denial,
  one-use bootstrap replay denial and stale/invalid Bearer denial. Same-origin
  browser GETs without an Origin header require exact Fetch Metadata plus the
  in-memory Bearer.
- Runtime diagnostics: readiness polling reports early child exit code and
  bounded stderr instead of collapsing every startup failure into a five-second
  timeout message.
- Crash restart retries only the exact transient Windows SQLite `disk i/o
  error`, across both read-only schema probing and writable reopen, while the
  Workspace OS lock is held; all other SQLite failures remain fail-closed.

## Current verification

- Python unittest discovery, freshly rerun after the observation registration:
  446 run; 446 passed, 0 skipped.
- Vitest: 67/67; projection self-test passed.
- TypeScript no-emit check and Vite production build passed.
- Playwright: 10/10 consecutive complete success journeys, retries=0.
- Expanded release matrix: 27/27, retries=0 (18 read/reconnect/security,
  including fragment exchange and reload recovery; 3 mutation; 4
  export/Approval; 2 fault cases).
- Obsidian planning export and the live 13-file Vault are byte-identical
  (13/13 SHA-256 matches).
- D0 and current D3 manifests are regenerated from this worktree and checked
  by automated per-file/digest tests; the final manifest explicitly includes
  `main.tsx`, the launcher and this authority.
- Windows Developer Mode is enabled and both symlink escape tests execute their
  assertions and pass; neither is skipped with WinError 1314.
- Release package audit: 212 files, zero forbidden runtime/user-data paths or
  credential canaries; deterministic package digest
  `e7799935642bb4e94df0cd89ed634a3bf8ec76dbb0a5b04e58817d679c6824d6`.
- Legacy `workspaces` and `usability_sessions` were copied into the OS Nana
  user-data root, content-verified, and the source copies moved to a recoverable
  ignored backup. The migration receipt contains counts and hashes but no raw
  user path.

## Acceptance resolution and environment note

- The target user attested that the 30-minute observation ended and explicitly
  directed that the D3 observation gate be registered complete. The original
  observer log, clarification count and 10 state-question answers were not
  retained, so the evidence record does not fabricate those measurements or
  claim subjective satisfaction. D3 uses a one-time, product-owner-approved
  evidence exception recorded in
  `docs/evidence/v0.3.0-dev-d3-observed-session-owner-attestation-20260817.json`.
- The product owner temporarily waived Claude review for this gate and accepted
  Sol/Codex review as sufficient until the relay is repaired. A later Claude
  review may reopen a concrete finding, but its current absence is not a gate.
- PySide6 6.11.1 on Python 3.12.13 emits the same shutdown ResourceWarning on a
  bare `import PySide6.QtCore`; it is isolated to the frozen legacy UI stack and
  is not suppressed or misreported as repaired.

## Delivery boundary

The observation decision changes the current evidence set after commit
`76584af`. Therefore the only remaining D3 delivery gate is to regenerate the
manifest, bind the gate to the resulting commit, rerun the frozen verification
set and mark `release_baseline_frozen=true`. Until then D3 acceptance is
complete but Tauri construction is not authorized. Runtime/user data remains
outside the source tree and excluded from every release package. Historical
completion records do not override this page or the current machine gate.
