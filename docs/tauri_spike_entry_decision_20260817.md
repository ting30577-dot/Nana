# Tauri spike entry decision

Date: 2026-08-17

Decision: **authorize the minimal Windows shell spike; do not authorize Tauri
product code**.

## Exact opening

The only newly allowed Tauri source root is repository-root `src-tauri`. Its
absence before the scaffold commit and its presence after that commit are both
valid states. If present, it must be a direct, non-reparse directory under the
repository root. Scaffolding may begin only after the machine-readable prerequisite list in
`config/tauri-spike-entry-policy.json` is verified on the build host.

The existing `config/release-input-allowlist.json` remains the product-package
boundary and continues to say `product_code_allowed=false`. This decision is a
narrow overlay for the spike; it does not silently convert the PyInstaller
release input policy into a Tauri packaging policy.

## Ownership and denial boundary

- Rust owns only the window, single-instance/process lifecycle, packaged
  sidecar identity verification and explicitly audited OS integration.
- Python remains the only canonical business-data writer. Approval, policy,
  action, export and Receipt rules may not be copied into Rust.
- IPC is default-deny and typed. Arbitrary shell, Python, path, URL, remote
  content, publish and updater behavior remain forbidden.
- A native picker may later supply the existing owner-memory opaque selection;
  it may not expose a raw path or filesystem identity to the WebView or SQLite.
- The spike cannot claim installer signing, updater safety, rollback readiness,
  production authorization or replacement of the Local Web authority.

## Entry and exit checks

Entry requires a verified D3 baseline tag, executable Node/npm, Rust MSVC,
Microsoft C++ Build Tools, Windows SDK, WebView2, an executable
repository-local pinned Tauri CLI, and a zero-vulnerability audit against the
explicit npm official registry. Local preflight is
`scripts/check_tauri_windows_prereqs.ps1`; the complete local-plus-network gate
is `scripts/check_tauri_spike_gate.ps1`.

The first spike implementation must still pass a separate review before it is
called product code. That review must cover CSP/navigation, typed IPC,
sidecar-hash/version handshake, single-instance Workspace ownership, data-root
permissions, package allowlist/leak audit and crash/restart behavior.
