# Claude D3-04 design response (sanitized)

Final design decision: ACCEPT.

Claude accepted the authenticated, E2E-only React/SSE bridge after the design
specified three mutually exclusive Playwright orchestration modes:

- `addInitScript` controls delay/randomness only;
- transport tests abort counted real requests and never synthesize a body;
- parser/reducer negative tests alone synthesize malformed SSE or invalid
  watermark Events inside browser automation, after asserting the original
  request fields.

No synthesized response is shipped in the sidecar, static build, Vite manifest,
runtime route inventory, or production fixture. The implementation review must
prove matcher-mode mutual exclusion, Node/browser step coordination, and exact
identification of the single recovery bootstrap. No design-level disagreement
remains.
