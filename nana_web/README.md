# Nana Web contract workspace

This directory is the TypeScript side of the `v0.3.0-dev` boundary.

D0 contains the generated API types, including the discriminated
`ArtifactLifecycleEvent` union used by the first D1 slice. D3-04 adds an
authenticated React Cockpit/Studio that consumes the D3 bootstrap and Event
reducer. The current product launcher is `scripts/run_d3_dev_journey.py`: it
opens a one-time fragment bootstrap, exchanges it for a memory-only Bearer,
and restores the in-memory session after refresh through an HttpOnly,
same-site recovery cookie. No Authorization header is injected by the product
browser test configuration.

Regenerate the client from the Python source of truth:

```powershell
.\.venv\Scripts\python.exe scripts\export_vnext_contracts.py
Set-Location nana_web
npm.cmd run generate:client
npm.cmd run check
npm.cmd test
npm.cmd run test:e2e
```

`test:e2e` always builds the production Vite assets before launching the
locked local fixture server and system Chrome. Its setup project performs the
real fragment exchange and reload recovery before the remaining browser
matrix. The fixture supplies canonical SQLite facts through a real
`WorkspaceRuntime`; browser state and local Plan notes remain non-canonical.
