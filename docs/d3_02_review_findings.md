# D3-02 candidate scan findings

Date: 2026-08-01
Status: first no-edit scan complete

| ID | Severity | Finding | Decision |
|---|---|---|---|
| F1 | high | D3 runtime OpenAPI/TS changed the web contract but the frozen D0 equality test still pointed at the live web snapshot | repaired: D0 snapshot moved to a frozen fixture; runtime snapshot is now the web authority |
| F2 | high | A configurable event-stream object could bypass the Workspace-derived database identity | repaired: runtime factory now constructs SQLiteEventStream only from WorkspaceRuntime.database_path; test customization uses patching, not a public factory argument |
| F3 | high | Existing D1 route tests treated handshake/OpenAPI as public and did not exercise the D3 owner lifecycle | repaired: they use a real pre-started WorkspaceRuntime and assert authenticated runtime semantics |
| F4 | medium | D0/D2 evidence manifests no longer matched the intentional runtime OpenAPI/client/export updates | repaired: both 102-entry manifests and digests were revalidated; D3-02 has its own scoped manifest summary |
| F5 | medium | Full-suite PySide6 shutdown diagnostic remains after success | recorded non-blocking under the inherited pre-mutation hard gate; focused D3 runtime tests are strict-warning clean |

All F1-F4 were repaired before the final no-edit re-review. F5 is an inherited
known boundary, not a D3-02 mutation authorization.

## Final joint decision

- F1-F4: CLOSED
- F5: non-blocking boundary with a hard re-evaluation before the first real
  mutation stage
- Codex: ACCEPT
- Claude: ACCEPT
- D3-02: ACCEPT for read-only runtime authority

Claude's review was evidence-bound because it received only the sanitized
packet; Codex's local scan and manifest recomputation are the executable
evidence. No mutation serving is authorized by this decision.
