# Nana v0.3.0-dev D3 current authority

Date: 2026-08-16  
Status: **current implementation and verification authority; user-observation gate pending**

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

## Current verification

- Python: 421 passed, 2 platform skips.
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

## Open acceptance and environment gates

- The planned 30-minute observed `create → plan → run → approve → artifact`
  session still requires the real target user and observer. No automated run is
  represented as a `UsabilitySession` Artifact.
- Two Windows symlink tests still skip with WinError 1314 because this process
  lacks symbolic-link privilege; they require Developer Mode or an elevated
  test environment.
- PySide6 6.11.1 on Python 3.12.13 emits the same shutdown ResourceWarning on a
  bare `import PySide6.QtCore`; it is isolated to the frozen legacy UI stack and
  is not suppressed or misreported as repaired.

## Delivery boundary

The inherited modified/untracked files were inventoried against the committed
D1 baseline. The staged set is limited to the D2/D3 implementation, tests,
evidence, planning exports and their required integration edits; generated
delivery archives, local backups and Playwright output are excluded. This
branch freezes that reviewed set as one replayable D2/D3 delivery commit.
