# Nana documentation and review retention

Status: active governance policy  
Machine policy: `config/document-retention.json`

## Keep

- One stable product kernel and one machine-readable active state.
- Accepted ADRs, current stage contracts, final gate decisions, and the minimum
  evidence needed to reproduce or audit a release claim.
- Executable tests and regression cases for confirmed bugs.
- The vNext Obsidian export as the user-facing product-design mirror.
- The frozen v0.2 baseline inventory until its migration and rollback gate is
  complete.

## Do not keep in the active tree

- Model prompts, complete model discussions, review packets, review responses,
  repeated scans, convergence attempts, and transport troubleshooting.
- Handoff snapshots that restate current state.
- A separate Markdown report for each test run or bug-fix loop.
- Generated build outputs, dependency caches, and packaged copies.
- An `archive/` directory full of superseded files. Git tags and history are the
  archive; the active tree should remain searchable and current.

For an external model review, generate a minimal sanitized context pack, keep
the returned finding fingerprint and accepted decision, then delete the packet
and dialogue. A durable architecture decision belongs in an ADR. A confirmed
bug belongs in a regression test. A current-stage change belongs in
`docs/ACTIVE_STATE.json`.

Before sending any repository-created packet, run
`python scripts/nana_context.py privacy-scan --files <relative packet paths>`.
The scanner reports only category/file/line and never echoes a detected value.

## Review levels

### R0 — mechanical, every change

Run only relevant format, lint/type, unit, diff, and privacy checks. Do not
create a review document.

### R1 — normal change

Review the changed diff and adjacent contracts. Record only actionable
findings, each with a stable fingerprint (`path + contract + failure mode`).
Allow one main review and one targeted re-review after fixes.

### R2 — high risk

Use for authentication, authorization, paths, external writes, process
execution, migrations, schemas, privacy, or security boundaries. Add an
independent security/data pass and failure injection. Persist only accepted
decisions, unresolved risks, and regression tests.

### R3 — milestone/release

Use only for a version gate, release candidate, stable release, destructive
migration, or product-boundary change. Run the full release matrix and real
user journey. Create one final gate record; do not preserve every intermediate
packet.

If a P0/P1 finding survives two fix/re-review cycles, stop looping and ask the
product owner. Never inflate an R1 task into a repository-wide audit solely
because another model is available.

## Cleanup process

1. Run `python scripts/nana_context.py cleanup-plan`.
2. Confirm candidates are tracked history or reproducible output and do not
   overlap the current dirty worktree.
3. Delete tracked historical files in one reviewable cleanup change.
4. Remove generated roots only after resolving and checking their absolute
   paths remain under the repository.
5. Run `python scripts/nana_context.py check`, focused tests, full regression,
   and `git diff --check`.

Use `python scripts/nana_context.py generated-cleanup` for a size-aware dry run
of configured build/package/cache roots. Applying it requires the explicit
`DELETE_REGENERABLE_OUTPUTS` confirmation and refuses reparse points or targets
outside the repository.

Legacy source retirement follows the gate in `docs/PROJECT_KERNEL.md`; document
cleanup does not authorize product-code deletion.
