# Nana D3-00 decision record

Date: 2026-08-01

## Current status

**Overall: D3 core ACCEPT; external T3 export remains 尚未达成共识.**

Codex has completed an independent proposal in
`docs/codex_d3_00_independent_proposal.md`. A neutral, privacy-scanned evidence
packet for Claude is frozen in
`docs/claude_d3_00_evidence_packet_sanitized.md`.

Claude returned an independent proposal, a cross-review, and a final resolution
review. D3 core may enter implementation under the decision table below.
External T3 export serving remains disabled until its atomic-replace fallback and
security-gate criteria are explicitly closed.

## Local baseline

| Check | Result |
|---|---|
| Python compileall | ACCEPT |
| Python full unittest | ACCEPT — 269 tests OK |
| TypeScript strict check | ACCEPT — run from `nana_web` |
| Root-level `npm.cmd run check` handoff command | VETO as written — repository root has no `package.json`; the evidence-index working directory is `nana_web` |
| Known legacy UI shutdown ResourceWarning | Recorded, non-blocking for design; still a hard check before real D3 write serving touches related handles |

## Claude transport diagnosis

| Check | Result |
|---|---|
| Sanitized context privacy scan | ACCEPT — zero matches for absolute drive/user paths, credential patterns, or literal bearer values |
| Claude adapter unit tests | ACCEPT — 6/6 |
| Nana API key presence | ACCEPT — presence only checked; value not printed |
| Base URL syntax | ACCEPT — configured absolute HTTPS URL |
| Model configuration | ACCEPT — configured |
| Authenticated review request | VETO at transport — connection error before a review response |
| Credential-free HTTPS probe to configured gateway | VETO at transport — TCP/HTTPS connection could not be established from the local execution environment |
| Public gateway visibility from independent web fetch | Reachable externally; this does not prove the local authenticated path |

### Claude transport and output recovery

The first call failed at transport. The subsequent user-requested retry
reached Claude, but the local Windows console failed to print one response
because `ask_claude.py` wrote a non-GBK character. Re-running the same
single-packet request with process-local UTF-8 output recovered the complete
response. This was a local output-encoding failure, not a Claude design
objection. The adapter's six unit tests remain green; no secret or token was
printed.

## Final joint decision table

| Decision | Codex | Claude | Joint state |
|---|---|---|---|
| Workspace lock lifecycle first | ACCEPT | ACCEPT | ACCEPT |
| Physically mount/combine frozen D0 app | VETO | VETO | VETO |
| New authenticated runtime factory as OpenAPI authority | ACCEPT with gates | ACCEPT with gates | ACCEPT with gates |
| Canonical query/SSE before reconciliation-ready | VETO | VETO | VETO |
| Standalone fixture/replay viewer | ACCEPT as shared reducer adapter | ACCEPT, contract ownership fixed | ACCEPT |
| Typed journey layer over D2 primitives | ACCEPT with boundary tests | ACCEPT with boundary tests | ACCEPT |
| D3/UI re-derives authorization | VETO | VETO | VETO |
| R1 Approval decision + authorization consumption | ACCEPT | ACCEPT | ACCEPT |
| R2 sparse Event ID / non-dense gap semantics | ACCEPT | ACCEPT | ACCEPT |
| R3 one HTTP/OpenAPI authority and offline fixture adapter | ACCEPT | ACCEPT | ACCEPT |
| R4 export transaction/idempotency/effect_unknown skeleton | ACCEPT | ACCEPT | ACCEPT |
| R4 external export enablement and fallback policy | 尚未达成共识 | 尚未达成共识 | 尚未达成共识 |

## Final collaboration evidence

- `docs/claude_d3_00_independent_proposal_sanitized.md`
- `docs/claude_d3_00_convergence_response_sanitized.md`
- `docs/claude_d3_00_final_resolution_packet_sanitized.md`
- final Claude response: R1/R2/R3 ACCEPT; R4 core semantics ACCEPT; R4
  external enablement and security-gate criteria NOT CONSENSUS.

## Pending implementation gates

1. implement and test Workspace lock lifecycle before any canonical mutation;
2. implement R1/R2/R3 and runtime contract/read-only projection gates;
3. keep external T3 export disabled until R4 fallback and security-gate criteria
   are jointly closed;
4. after each slice, update the authoritative evidence summary and manifest.
