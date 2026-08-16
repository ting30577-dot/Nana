# Nana

> **Current D3 authority:** [`docs/CURRENT_D3_AUTHORITY.md`](docs/CURRENT_D3_AUTHORITY.md).
> Any conflicting handoff, audit or acceptance document is historical.

Nana is a Windows-first, local-first personal **Research & Engineering OS**. Its
target is to turn a real research or engineering question into traceable
evidence, reproducible runs, reusable artifacts, and a user-approved decision.

> Current implementation: legacy `v0.2.0-alpha` plus a verified
> `v0.3.0-dev` React/FastAPI vertical slice
> Current product direction: `v0.3.0`; D3 is accepted by the current authority

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

The detailed and authoritative rebuild specification is staged in
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
New-Item -ItemType Directory -Force .\workspaces\d3 | Out-Null
New-Item -ItemType Directory -Force .\exports\d3-draft | Out-Null
.\.venv\Scripts\python.exe .\scripts\run_d3_dev_journey.py .\workspaces\d3\nana.db
```

At the prompt, select the absolute path of `.\exports\d3-draft`. It must remain
an empty dedicated local directory when selected. The browser consumes a
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
new vertical slice and Tauri decision gate are complete.

## Repository map

```text
.
├── main.py                         # current legacy entry point
├── algorithms/                     # reusable algorithm assets
├── db/                             # legacy SQLite implementation
├── ui/                             # frozen PySide6 UI
├── visualizer/                     # legacy visualizations
├── nana_core/ai/                   # model collaboration adapter
├── tests/                          # current regression baseline
├── docs/                           # evidence and peer-review working record
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
