# Nana Web contract workspace

This directory is the TypeScript side of the `v0.3.0-dev` boundary.

D0 contains the generated API types and their type check only, including the
discriminated `ArtifactLifecycleEvent` union used by the first D1 slice. The
React Cockpit/Studio implementation starts after the Artifact/Event and
Action/Policy runtime gates pass; this prevents the UI from becoming a mock
that bypasses canonical state.

Regenerate the client from the Python source of truth:

```powershell
.\.venv\Scripts\python.exe scripts\export_vnext_contracts.py
Set-Location nana_web
npm.cmd run generate:client
npm.cmd run check
```
