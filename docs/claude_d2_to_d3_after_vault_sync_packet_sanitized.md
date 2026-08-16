# Nana D2 -> D3 final gate after authoritative evidence sync

This packet is sanitized. It contains only relative file names, test counts,
manifest digest, and design conclusions. It contains no username-bearing
absolute paths, no API keys, no environment variable values, no local IP/MAC
addresses, no hardware serial numbers, and no credential-bearing logs.

## Review question

The previous joint review concluded:

- D2 technical/code layer: ACCEPT.
- D2 -> D3 official handoff: VETO / unresolved under strict gate, because the
  authoritative evidence index had not yet registered D2-00..D2-07.

The user says the evidence has now been registered. Please re-review strictly:

- Is the prior single blocker cleared?
- Can D2 now be officially accepted?
- Can D2 safely hand off to D3?
- Are there any remaining blockers that should keep D2 -> D3 as VETO?

Please return explicit ACCEPT / VETO / unresolved for:

1. D2 completion;
2. D2 official evidence/signoff;
3. D2 -> D3 handoff.

## Authoritative evidence sync observed by Codex

The authoritative execution checklist now contains a section equivalent to:

`2026-08-01: D2-00 through D2-07 completed and jointly accepted`.

It records:

- D2 scope is strictly the trusted, frozen, narrow
  `python.unittest.locked` local execution loop.
- It is not a general hostile-code sandbox.
- It does not expose HTTP mutation serving, general shell, arbitrary Python,
  external publish/export, or React UI.
- D2-00 through D2-07 are each marked complete and included in final joint
  ACCEPT.
- D2-06 records 23 manual corpus cases plus 360 D2-effective and 100
  supplemental cases, with 0 unauthorized T3/T4/T4-like passes within the
  corpus/matrix boundary.
- D2-07 records schema v6 append-only authorization snapshot, D2RuntimeHandoff
  v3, replay fixture, and D3 consumption boundaries.
- Remaining incomplete items are explicitly not considered completed by D2:
  general file read tool, scratch Artifact writing, locked benchmark, Git
  read-only, public web reading, T3 export, complete prompt/log/export canaries,
  provider unavailable, disk-full, general pause/resume, and UI E2E.
- Final verification in the authoritative checklist records:
  - focused regression: 68/68;
  - full regression: 269/269;
  - seven D2 modules: 55 tests under ResourceWarning-as-error;
  - Python compileall OK;
  - TypeScript `tsc --noEmit` OK;
  - evidence manifest and privacy scan OK.
- D3 before real mutation serving must complete:
  - OS-level Workspace lock;
  - lock before writable SQLite open;
  - reconciliation before ready;
  - second instance fail closed;
  - SQLite close before lock release;
  - OpenAPI/runtime app merge as an explicit D3 decision.
- D3 may consume D2 Action/Event/Receipt/outbox/Artifact projections and
  authorization snapshots; it must not recompute authorization or bypass
  admission/scheduler/executor.

The authoritative evidence index now contains a section equivalent to:

`v0.3.0-dev D2-00 through D2-07 security execution loop evidence`.

It records:

- execution dates: 2026-07-30 through 2026-08-01;
- final scope: trusted `python.unittest.locked` frozen worker, not a general
  sandbox;
- schema evolution: v2 authorization/receipt, v3 scheduler event, v4 full
  registry, v5 budget ledger, v6 append-only authorization snapshot;
- final joint conclusion: Codex ACCEPT, Claude second convergence review ACCEPT,
  no remaining D2 blocker;
- focused regression 68/68;
- full regression 269/269;
- strict warning regression 55/55 under ResourceWarning-as-error;
- security gate: 23 manual corpus cases; 460 executed scenarios; 360
  D2-effective and 100 supplemental; the 30 cancel/process-tree scenarios are
  the same 30 real descendant-process fixtures, not an extra second set;
  unauthorized high-risk passes = 0 within corpus/matrix boundary;
- compile/type gates OK;
- independent D2 manifest self-check and digest:
  `1cbb07d25a1333e0a860182f0a47f915601c90af083b6e8b9daf4ec5aedd7f5d`;
- stage evidence index maps D2-00 through D2-07 to relative repo evidence files
  and tests;
- key VETO/rebuttal history is registered: Windows Job suspended-create bind,
  real descendant-process fixtures, matrix effective/supplemental classification,
  args Artifact size/budget fail-closed, orphaned conservative usage, worker
  `-B`, observed-effects-as-advisory, and v4->v6 digest stability;
- D3 obligations and evidence strength boundaries are explicitly recorded;
- replay fixture, security corpus/matrix and D2 manifest paths are listed as
  relative repo evidence entries.

## Fresh verification rerun by Codex after sync

All current verification reruns passed:

- Python compileall for sidecar/tests/scripts: OK.
- TypeScript strict check: OK.
- D0 evidence manifest self-check: OK.
- Full Python unittest: 269 tests OK.
- D2 modules under ResourceWarning-as-error: 55 tests OK.
- D2 security matrix + runtime handoff: 14 tests OK.
- D2 manifest self-check:
  - 102 entries;
  - 0 bad hashes;
  - manifest digest
    `1cbb07d25a1333e0a860182f0a47f915601c90af083b6e8b9daf4ec5aedd7f5d`;
  - digest matches `.sha256`.

Known warning:

- Full unittest still emits one shutdown ResourceWarning. D2 modules pass when
  ResourceWarning is treated as error. The authoritative docs register this as
  isolated to legacy UI smoke and non-D2 handle/process code.

## Codex current conclusion before Claude

Codex now changes the prior VETO to ACCEPT:

- D2 technical layer: ACCEPT.
- D2 official evidence/signoff layer: ACCEPT, because the prior blocker
  (authoritative evidence index missing D2) is now cleared and D2 manifest
  self-check passes.
- D2 -> D3 handoff: ACCEPT, with hard D3 restrictions:
  - D3 may start only with read-only/replay/projection/OpenAPI-merge design;
  - real mutation serving remains blocked until Workspace lock lifecycle and
    second-instance/ready-order tests pass;
  - OpenAPI/runtime app merge must be explicit;
  - locked executor guarantees cannot be generalized beyond trusted frozen
    `python.unittest.locked`.

Please independently agree or VETO.
