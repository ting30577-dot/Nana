# D3-02 joint design decision record

Date: 2026-08-01
Status: design convergence after first Claude review

## Findings and decisions

| ID | Decision | Resolution |
|---|---|---|
| F3 | ACCEPT | Set `redirect_slashes=False`; security middleware is the outer pre-routing gate. Only exact `GET /healthz` and qualifying preflight bypass auth. |
| F4 | ACCEPT | Startup failure marks internal state `failed`, performs D3-01 cleanup, and re-raises so the runtime process exits. If cleanup cannot close SQLite, the lock is retained and process exit is fail-closed. No resident failed server is advertised. |
| F5 | ACCEPT | D3-02 freezes one canonical Origin form: `http://127.0.0.1:<port>` with a decimal port in 1-65535. IPv6, `localhost`, alternate loopback spellings, HTTPS, missing port, credentials, path/query/fragment are rejected. Host must equal the exact configured `127.0.0.1:<port>` authority. |
| F6 | ACCEPT | Track active SSE tasks. On drain, stop admission, signal a bounded termination event, wait a fixed deadline, cancel remaining stream tasks, await their `finally` cleanup, then call `WorkspaceRuntime.close()`. Tests assert stream end/SQLite close/lock release order and timeout behavior. |
| F7 | ACCEPT | Add graceful drain, failed-startup, and second-instance process evidence to D3-02; D3-01 remains the owner lifecycle authority. |
| F8 | ACCEPT | Freeze the existing D0 OpenAPI as a fixture. D3 runtime OpenAPI must contain every D0 path/method and component schema; D3 may add only explicitly reviewed read-only routes/fields. |
| F2 | ACCEPT | Add route matrix tests that call every runtime route through ASGI with missing token, wrong token, wrong Origin, wrong Host, and valid credentials; schema comparison is not treated as auth proof. |
| F9 | ACCEPT | Preflight requested headers are limited to `authorization` and `last-event-id`; `content-type` is removed while D3-02 has no mutation methods. A route/method guard fails the stage if any POST/PUT/PATCH/DELETE appears, and any future mutation stage must update this allow-list and its matrix in the same reviewed change. |
| F10 | ACCEPT | Origin is mandatory on every authenticated request, including non-browser local tools. Missing Origin is 403. The documented client contract is fetch/ReadableStream against the exact configured base URL, not EventSource or a permissive generic local client. |
| F11 | ACCEPT | The configured port is canonical decimal 1-65535: no zero, leading zero, whitespace, sign, non-decimal text, or out-of-range value. Host comparison is exact ASCII authority equality; alternate casing and a trailing dot fail closed. |
| F12 | ACCEPT | The no-mutation guard has a meta-test that injects a mutation route and asserts the inventory validator fails. The route-level negative matrix cross-products missing/wrong token, missing/wrong Origin, Host mismatch, duplicate security headers, and forwarded headers. |

## Final joint decision

Codex: ACCEPT after the above resolutions.

Claude: initial design `尚未达成共识`; all findings have explicit convergence
conditions recorded here. A resolution packet and final Claude review are
required before implementation.

Hard boundaries: no mutation route, no external export, no hostile-code
sandbox, and no public/bootstrap route beyond the exact reviewed inventory.

## Claude resolution follow-up

Claude's first resolution review marked only B3 (Origin value) and B7
(preflight/mutation coupling) as not-yet-consensus. The explicit `127.0.0.1`
form and executable no-mutation guard above close both design ambiguities;
Claude's final design review is ACCEPT at design level. F10-F12 record its
required implementation assertions; implementation may begin, but D3-02 exit
still requires all test evidence and a Claude exit review.
