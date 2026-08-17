# Nana Tauri spike toolchain

This directory pins the repository-local Tauri CLI used by the gated Windows
shell spike. It is tooling, not product code. The only authorized future source
root is repository-root `src-tauri`, subject to
`config/tauri-spike-entry-policy.json` and the preflight script.

Do not run `tauri init`, create `src-tauri`, add plugins or broaden capabilities
until the preflight passes and the spike entry decision is reviewed.

Use `npm run preflight:windows` for the local executable/version checks and
`npm run audit:official` for the network advisory check. The latter command is
intentionally pinned to `https://registry.npmjs.org`; the configured default
npm mirror is not accepted as audit evidence.
