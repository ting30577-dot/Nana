# Tauri trust-boundary contract

Status: **frozen contract; Tauri product code is not implemented or authorized**

This contract prevents the future desktop shell from silently expanding the
verified Local Web boundary. The machine companion is
`config/release-input-allowlist.json`.

## Authority split

- Rust owns the desktop window, one-process lifecycle, packaged-sidecar
  identity verification and narrowly audited operating-system integration.
- The Python sidecar remains the only canonical business-data writer. Rust
  must not copy approval, policy, action, export or receipt rules.
- A native file picker may extend the existing memory-only opaque selection
  contract, but may not expose a raw path, directory handle or clear filesystem
  identity to the WebView or SQLite.

## IPC and navigation

- IPC is default-deny and every command requires an exact typed schema and an
  explicit allowlist entry.
- Arbitrary shell, Python, URL, path, process and network commands are forbidden.
- The WebView may load only packaged local content. Remote content, new windows,
  uncontrolled navigation and opener access are denied by policy and CSP.
- WebView-to-sidecar authentication must use an ephemeral, process-bound secret
  delivery mechanism; credentials never enter URLs, logs or persistent Web
  storage.

## Installation and lifecycle

- The packaged sidecar is pinned by version and SHA-256 and must be covered by
  the installer signature/version handshake before execution.
- One desktop instance owns one Workspace at a time. A second window or process
  cannot acquire the same Workspace ownership.
- Install, upgrade, rollback and uninstall preserve user data by default.
  Removing user data is a separate, explicit and recoverable operation.
- Logs, crash material and diagnostics are stored under the Nana user-data root
  and are redacted before any user-authorized disclosure.
- Updater metadata and installers require a separately frozen signing and
  rollback policy. This repair does not authorize an updater or Tauri code.

## Build gate

The current PyInstaller build supplies only the declared entrypoint and
specific runtime DLLs, then audits the produced directory. A build fails if it
contains a Workspace, SQLite database/WAL/SHM, lock, Artifact/export/session/log
tree, credential canary, unknown top-level item or stale package manifest. The
same explicit-input and output-audit rule is mandatory before any future Tauri
implementation can change this contract's status.
