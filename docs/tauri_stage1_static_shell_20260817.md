# Nana Tauri stage 1: minimal static Windows shell

Date: 2026-08-17
Decision: **ACCEPT for the stage-1 static shell spike; VETO for product migration**

## Scope and authority

This stage starts after the verified entry gate and creates only the repository-root
`src-tauri` source root. The Rust layer owns one desktop window and its local
navigation boundary. The `nana_web` Vite output remains the only frontend input.
Python remains the canonical business-data writer, but no Python sidecar is started
or embedded in this stage.

The D3 tag and final manifest remain frozen. `config/release-input-allowlist.json`
still has `product_code_allowed=false`; this document is a separate spike record,
not a product release claim.

## File-level contract

| File | Contract | Verification |
|---|---|---|
| `src-tauri/tauri.conf.json` | Local `../nana_web/dist`, explicit `main` capability, strict CSP, no dev URL, no bundle claim | JSON security test; `tauri build --no-bundle` |
| `src-tauri/capabilities/default.json` | Capability is explicitly named `main` and has zero permissions/scopes | capability test; Tauri ACL generation |
| `src-tauri/src/lib.rs` | Creates one `main` WebviewWindow, allows only packaged local app URLs, denies new windows, registers no commands/plugins | Rust source test; cargo fmt/clippy/test/check/build |
| `src-tauri/src/main.rs` | Windows entry point only | cargo build |
| `src-tauri/Cargo.toml` / `Cargo.lock` | Pinned Tauri crates; no plugin or local source override | dependency audit/read-only inspection |
| `tests/test_tauri_static_shell.py` | Machine-checkable security and scope assertions | Python focused test |

## Security boundary

- `connect-src 'none'` makes this a static shell; sidecar IPC is deliberately not
  part of the stage.
- `default-src`, `script-src`, `style-src`, `font-src` and `img-src` allow only
  packaged local assets plus the existing data favicon. Objects, frames and forms
  are denied.
- The capability file is explicitly selected by `app.security.capabilities`; no
  directory auto-discovery is relied on. `core:default` is intentionally absent.
- Rust navigation accepts only the Tauri local app host and denies all other URLs;
  ports, query strings, fragments and non-entry document paths are denied; new-window
  requests are denied. There is no invoke command, shell, filesystem,
  HTTP, opener, updater, process, dialog or log plugin.
- The packaged shell renders without a session request. Browser-only session
  bootstrap is failure-contained and cannot prevent the React root from rendering.
- The gate audits the complete Vite `frontendDist` tree, rejects unexpected or
  sensitive files, checks Git tracked/untracked changes against the stage allowlist,
  and requires a real `cargo audit` result.
- Bundle creation, signing, updater, sidecar identity, single-instance Workspace
  ownership, native picker and user-data migration are deferred to later gates.

## Acceptance commands

```text
$env:NANA_TAURI_GATE_SHA256 = '<protected CI baseline SHA-256 for check_tauri_spike_gate.ps1>'
powershell -ExecutionPolicy Bypass -File .\scripts\check_tauri_spike_gate.ps1
.\.venv\Scripts\python.exe -m unittest tests.test_tauri_static_shell tests.test_tauri_spike_gate
cd src-tauri && cargo fmt --check
cd src-tauri && cargo clippy -- -D warnings
cd src-tauri && cargo test
cd src-tauri && cargo check
cd src-tauri && cargo build
cd nana_web && npm.cmd run check
cd nana_web && npm.cmd test
cd nana_web && npm.cmd run build
.\.venv\Scripts\python.exe -m unittest discover -s tests
git diff --check
.\.venv\Scripts\python.exe scripts/refresh_evidence_manifest.py docs/evidence/v0.3.0-dev-tauri-stage1-static-shell-manifest.txt --check `
  --scope config/tauri-stage1-worktree-allowlist.json `
  --scope docs/evidence/v0.3.0-dev-tauri-stage1-static-shell.json `
  --scope docs/evidence/v0.3.0-dev-tauri-cargo-audit-20260817.json `
  --scope docs/evidence/v0.3.0-dev-tauri-spike-entry-manifest.sha256 `
  --scope docs/evidence/v0.3.0-dev-tauri-spike-entry-manifest.txt `
  --scope docs/tauri_stage1_static_shell_20260817.md `
  --scope nana_web/dist `
  --scope nana_web/package-lock.json `
  --scope nana_web/package.json `
  --scope nana_web/src/main.tsx `
  --scope scripts/check_tauri_cargo_audit.ps1 `
  --scope scripts/check_tauri_frontend_npm_audit.ps1 `
  --scope scripts/check_tauri_frontend_dist.py `
  --scope scripts/refresh_evidence_manifest.py `
  --scope src-tauri --exclude src-tauri/target --exclude src-tauri/gen `
  --scope tests/test_tauri_static_shell.py `
  --scope tools/tauri-spike/package-lock.json `
  --scope tools/tauri-spike/package.json
```

The stage does not claim the D3 full product gate, a signed installer, a Tauri
product migration, sidecar lifecycle correctness, or a release package.
