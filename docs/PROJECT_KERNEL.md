# Nana project kernel

Status: **stable product authority**  
Owner: product owner  
Last reviewed: 2026-08-18

This file defines Nana's durable direction. It changes only when the product
owner changes the product mission, the core loop, or a release boundary. The
machine-readable execution state lives in `docs/ACTIVE_STATE.json`.

## Mission

Nana is a Windows-first, local-first personal Research & Engineering OS. It
helps one person turn a real research or engineering question into traceable
evidence, reproducible runs, reusable artifacts, and a user-approved decision.
Its purpose is to increase the user's research and engineering capability, not
to maximize features, agents, documents, tests, or lines of code.

## Core product loop

```text
goal / inquiry
-> research and evidence
-> hypothesis and editable plan
-> implementation and experiment
-> comparison and counter-evidence
-> user-approved decision and delivery
-> cross-project reuse
```

Algorithm Investigation, Paper/Repo Reproduction, and Engineering
Optimization are templates over one shared Project/Plan/Run/Action/Event/
PolicyGrant/Approval runtime. Capability growth is derived from real work; it
is not a separate score-driven loop.

## Product principles

1. User value before infrastructure volume. Every release must make at least
   one real end-to-end journey materially better.
2. Evidence before confidence. Conclusions link to sources, runs, artifacts,
   versions, and receipts; uncertainty and counter-evidence remain visible.
3. Local-first and private by default. External disclosure is explicit,
   minimal, sanitized, and approved by the user.
4. Human authority at consequential boundaries. AI may plan and execute within
   capability, budget, and policy grants; publishing, destructive migration,
   sensitive disclosure, and other material effects require approval.
5. One canonical writer. Python owns business rules and canonical data. Rust
   owns only the desktop shell, process lifecycle, and narrowly audited OS
   integration.
6. Replaceable adapters. Model providers, retrieval, notebooks, experiment
   trackers, Git/DVC, Obsidian, and execution backends do not define the core.
7. No permanent dual system. Legacy components remain only behind an explicit
   migration or rollback gate and receive no new product features.
8. Tests buy confidence; documents record durable truth. Neither may become a
   substitute for product progress.

## Target architecture

- React + TypeScript: Cockpit and Research Studio.
- Python 3.12 + FastAPI: domain services, agents, scientific tools, and
  adapters; the only canonical business-data writer.
- SQLite WAL: canonical metadata and event storage.
- Content-addressed Artifact Store: immutable research and run outputs.
- Tauri 2 + Rust: Windows desktop shell after staged security and lifecycle
  gates; Local Web remains the fallback.
- Typed, default-deny boundaries: Command, Action, Event, PolicyGrant,
  Approval, Receipt, capability registry, and opaque path selections.

## Current version interpretation

- `v0.2.0-alpha`: frozen legacy prototype; retained for export, migration,
  comparison, and rollback only.
- `v0.3.0-dev D3`: accepted and tag-frozen browser vertical-slice baseline.
- Post-D3 Tauri stages: shell experiments layered on the frozen D3 baseline;
  they are not product migration until a gate explicitly says so.
- `v0.3.0-alpha.1`: usable Algorithm Investigation journey.
- `v0.3.0-alpha.2`: usable Paper/Repo Reproduction journey.
- `v0.3.0-beta`: usable Engineering Optimization journey.
- `v0.3.0-rc`: migration, recovery, security, installer, and Windows release
  hardening.
- `v0.3.0`: all three journeys and release gates pass.
- `v0.4.x`: cross-project reuse and CapabilityEvidence.
- `v0.5.x`: one user-confirmed domain pack.

Versions are acceptance boundaries, not feature-count or calendar promises.

## Explicit non-goals

- Reimplementing full IDE, notebook, PDF, Git, experiment-tracking, or model
  platforms when a bounded adapter can reuse them.
- Copying canonical business rules into Rust, React, or provider prompts.
- Adding features to the PySide6/legacy SQLite product path.
- Treating AI discussion transcripts, review loops, test counts, or code volume
  as product deliverables.
- Reading the complete repository or Obsidian Vault for every task.
- Sending credentials, authorization data, serial numbers, usernames in paths,
  machine names, private IPs, MAC addresses, or user content to model services.

## Authority order

When sources disagree, use this order:

1. Product-owner instruction in the active task.
2. This kernel for durable product direction.
3. `docs/ACTIVE_STATE.json` for the current execution phase and next gate.
4. Accepted ADRs and the current stage contract named by active state.
5. Executable code, tests, and current verification evidence.
6. The vNext Obsidian export for detailed product design and long-form reading.
7. Historical tags and Git history.

Obsidian is the user-facing thinking and reading view. The repository is the
canonical authority for engineering execution state. AI packets, scan notes,
old handoffs, and superseded evidence never override the items above.

## Definition of meaningful progress

A change is progress only when it satisfies all applicable conditions:

- advances a named user journey or removes measured friction/risk;
- stays within the active stage and authority boundary;
- has proportional automated verification and, for milestones, real journey
  evidence;
- preserves privacy, migration, recovery, and failure-closed behavior;
- updates the single active state instead of creating another competing status
  document;
- leaves the next task smaller and clearer than before.

## Legacy retirement gate

Do not delete `main.py`, `ui/`, `visualizer/`, legacy database/export code, or
their migration tests until all of the following are true:

1. A Tauri product-migration gate is explicitly accepted.
2. The replacement launches the real Python sidecar and passes the three
   required user-journey gates applicable to that release.
3. Existing v0.2 data has a verified read-only export, migration, backup, and
   recovery path tested on a copy of real user data.
4. The product owner accepts removal of the rollback executable.

Pure algorithm assets may later move into an example/domain pack instead of
being deleted.
