# D3-05 second no-edit scan

Date: 2026-08-08

This scan was performed after the first frozen findings were repaired. It did
not modify production code. D3-06 and later were not inspected.

## Itemized result

| Finding | Scan result | Evidence |
| --- | --- | --- |
| F-01/F-02 | PASS | owner-thread close and failed-control executor tests |
| F-03/F-04 | PASS | actor/error replay plus aggregate/payload/domain corruption tests |
| F-05/F-06 | PASS | all schema-allowed non-valid Evidence statuses, portable path, content drift, symlink/reparse tests |
| F-07/F-08/F-09/F-10 | PASS | OpenAPI refs plus runtime 409/422/500 bodies, duplicate route, constants, stable actor tests |
| F-11/F-12 | PASS | bootstrap corruption and lifecycle cleanup tests |
| F-13 | PASS locally | five fresh-workspace rounds; eight distinct command IDs with staggered jitter per round: one accepted, seven conflicts |
| F-14 | PASS | AttachEvidence before-commit rollback and after-commit replay |
| F-15 | PASS | path/reparse/content identity and registration-to-locator drift coverage |
| F-16 | PASS | raw ASGI duplicate Authorization/Origin/Host/Content-Length matrix |
| F-17 | PASS | HTTP response-loss replay and committed outbox SSE frame |
| F-18 | ACCEPT CAVEAT | `gc.DEBUG_UNCOLLECTABLE` attributes the graph to PySide6/legacy UI teardown; strict D3 subset is clean |
| F-19 | PASS | D0 manifest synchronized; D3-05 completion and manifest recorded |

## Verification commands

- `python -m compileall nana_sidecar tests scripts`: PASS
- Full Python unittest: 353 tests, 2 skips, PASS
- Strict D3 subset with `-W error::ResourceWarning`: 81 tests, 2 skips, PASS
- `npm run check`: PASS
- Vitest and projection self-test: 23 tests, PASS
- Vite production build: PASS
- Playwright read-only cockpit E2E: 11 tests, PASS
- D0 evidence manifest self-check: PASS

## Local scan decision

Codex local result: **ACCEPT** for D3-05 implementation closure, with F-18
retained as a non-blocking evidence caveat. Claude independent adjudication is
still **NOT YET CONSENSUS** because the configured gateway did not return a
review; no joint ACCEPT is claimed here.
