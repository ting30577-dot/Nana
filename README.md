# Nana

> **Product direction:** [`docs/PROJECT_KERNEL.md`](docs/PROJECT_KERNEL.md)
> **Current execution state:** [`docs/ACTIVE_STATE.json`](docs/ACTIVE_STATE.json)
> The accepted D3 baseline remains frozen in
> [`docs/CURRENT_D3_AUTHORITY.md`](docs/CURRENT_D3_AUTHORITY.md).

Nana is a Windows-first, local-first personal **Research & Engineering OS**. Its
target is to turn a real research or engineering question into traceable
evidence, reproducible runs, reusable artifacts, and a user-approved decision.

> Current implementation: a frozen legacy `v0.2.0-alpha`, the accepted
> `v0.3.0-dev` React/FastAPI D3 vertical slice, and a post-D3 Tauri Stage 1
> static-shell spike awaiting worktree revalidation. Tauri product migration is
> **not** authorized.

The present PySide6 application is still runnable and its tests are retained as
a regression baseline. It is not the target UI or data architecture. New
product work is frozen on the old Qt/CRUD flow. The dev slice now includes a
typed browser journey, locked T2 fixture, controlled draft export and Receipt,
Pause/Resume, failed-to-retry lineage, the Local Web lifecycle/security matrix,
and current release proof.

## Target product loop

```text
goal / inquiry
→ research and evidence
→ hypothesis and editable plan
→ implementation and experiment
→ comparison and counter-evidence
→ user-approved decision and delivery
→ cross-project reuse
```

The first three project templates are:

1. Algorithm Investigation
2. Paper/Repo Reproduction
3. Engineering Optimization

They share one Project/Plan/Run/Action/Event/PolicyGrant/Approval runtime. Capability growth is a
derived view of real work, not a separate score-driven product loop.

## Target architecture

- React + TypeScript for the Cockpit and Research Studio
- Python 3.12 + FastAPI for domain services, agents, scientific tools, and adapters
- SQLite WAL as canonical metadata/event storage
- content-addressed Artifact Store
- Tauri 2/Rust as the Windows desktop shell only after a browser-based vertical
  slice passes; local Web workspace is the fallback
- adapters for Git/DVC, MLflow/SwanLab, Jupyter, Obsidian, parsers, model
  providers, and execution backends

The stable mission and engineering authority are the project kernel and active
state above. The detailed user-facing rebuild specification is mirrored in
[`obsidian_export/Nana_研究系统_vNext`](obsidian_export/Nana_研究系统_vNext/00_Nana_总览与导航.md).
It covers product, version-history research, user journeys, UI, architecture,
security, roadmap, migration, peer review, final audit, and the first
implementation slice.

## Current prototype

The current code still uses:

- Python 3.12（审计时 `.venv` 为 3.12.13）
- PySide6 and Matplotlib
- SQLite
- PyInstaller
- legacy research objects and algorithm visualizations

Useful pure algorithm functions, tests, and verified integrations may be reused
as artifacts or adapters. The old PySide6 UI and legacy database schema do not
constrain the rebuild.

### Run

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

### Run the D3 Web journey

Build the browser assets once, then start the authenticated product launcher.
The launcher asks for an existing, dedicated empty export directory, binds an
OS-selected loopback port, opens the browser after readiness, and keeps the
Bearer credential out of stdout and persistent browser storage.

```powershell
Set-Location .\nana_web
npm.cmd ci
npm.cmd run build
Set-Location ..
.\.venv\Scripts\python.exe .\scripts\run_d3_dev_journey.py
```

The launcher stores its default Workspace under the OS Nana user-data root
(`%LOCALAPPDATA%\Nana` on Windows), never in the source checkout. At the
prompt, select an existing empty dedicated local directory outside this
repository; the launcher prints the recommended user-data export parent. The browser consumes a
one-time URL fragment, holds the Bearer only in JavaScript memory, and uses an
HttpOnly, same-site recovery cookie to obtain a fresh in-memory copy after a
page refresh. Closing the launcher process ends that recovery session.

### Test

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

### Build the legacy Windows prototype

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

The output is `dist\Nana\Nana.exe`. This build path is retained only until the
Tauri product-migration and old-data recovery gates are complete. Generated
packages are intentionally not retained in the repository working tree.

### Start a new Nana development task

Do not scan the entire repository or Obsidian Vault. The root `AGENTS.md` and
project skill require a bounded route:

```powershell
python .\scripts\nana_context.py check
python .\scripts\nana_context.py bootstrap --route tauri-shell
```

Available routes are in `config/context-routes.json`. Documentation and review
retention rules are in `docs/DOCUMENT_RETENTION.md`.

## Repository map

```text
.
├── main.py                         # frozen legacy entry point/migration fallback
├── algorithms/                     # reusable algorithm assets
├── db/                             # legacy SQLite implementation
├── ui/                             # frozen PySide6 UI
├── visualizer/                     # legacy visualizations
├── nana_core/ai/                   # model collaboration adapter
├── src-tauri/                      # currently authorized static shell spike
├── tests/                          # executable contracts and regression proof
├── docs/                           # kernel, active state, decisions, minimal evidence
└── obsidian_export/
    └── Nana_研究系统_vNext/          # authoritative rebuild specification
```

## Version interpretation

- `v0.1.0`: historical algorithm-learning prototype
- `v0.2.0-alpha`: current runnable research skeleton, now frozen as a legacy prototype
- `v0.3.0-dev`: unified runtime vertical slice
- `v0.3.0-alpha.1`: Algorithm Investigation
- `v0.3.0-alpha.2`: Paper/Repo Reproduction
- `v0.3.0-beta`: Engineering Optimization
- `v0.3.0-rc`: migration, recovery, security, and Windows release hardening
- `v0.3.0`: all three journeys and release gates pass
- `v0.4.x`: cross-project reuse and CapabilityEvidence
- `v0.5.x`: one user-confirmed domain pack

Versions are acceptance boundaries, not feature-count or calendar promises.

## License

[MIT](LICENSE)
