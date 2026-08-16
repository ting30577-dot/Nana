# D3-03 closure evidence packet (sanitized)

## Resolution of the prior no-consensus findings

1. Same token/same offset idempotence: implemented and tested in
   `tests/test_d3_read_models.py`. A research page is read, a later outbox Event
   is written above the token high-water, and the same token/offset/limit is
   read again; the responses must be identical.
2. Cross-section token reuse: `BootstrapReadModel.page` verifies the signed
   token `section` equals the requested `section` and rejects mismatch with
   `E_PAGE_TOKEN_SECTION`; explicit test added.
3. Section oversize: all section pages are bounded to 200 event envelopes and
   the same 2 MiB encoded-response ceiling. An oversized page returns structured
   413 `E_SECTION_PAGE_TOO_LARGE` with the section; it never truncates silently.
   A ceiling test forces this path. Client may retry with a smaller limit.

## Invariant evidence

- Every page reads `events WHERE id <= token.high_water`, ordered by ID.
- Section categories are aggregate-type partitions of the Event stream;
  aggregate tables are never live-paged after an oversized snapshot.
- Token payload is HMAC-SHA256 signed using the in-memory LocalSession token;
  it carries high-water, watermarks, section, and offset. Token values are not
  logged or included in ordinary bootstrap output; they occur only in the 413
  recovery response to the authenticated session.
- Full snapshot remains a same-transaction read-only `BEGIN` projection.

## Codex final independent position

ACCEPT D3-03. The prior three blocking gaps are closed by code and focused
tests. No mutation route, authorization derivation, or policy/approval read is
introduced. Request Claude's final ACCEPT/VETO/NO-CONSENSUS decision only.

## Final executed verification

- Python `compileall nana_sidecar tests scripts`: pass.
- Full Python `unittest`: `Ran 303 tests ... OK (skipped=1)`. The only trailing
  process-shutdown observation is the pre-existing PySide6 uncollectable-object
  `ResourceWarning`; no test fails and D3 still has no mutation service.
- Web projection self-test: pass.
- TypeScript check: pass.

The earlier expected count of 300 included the first two pagination cases. The
final 303 count adds three closure cases only: same-token/same-offset
idempotence after a later write, cross-section token rejection, and section
page over-ceiling failure. No unrelated test scope was added.

Ordinary successful bootstrap responses contain only the snapshot projection;
they contain neither `page_token` nor `next_page_token`. Recovery tokens appear
only in authenticated 413 responses and are HMAC-protected opaque values.
They are bound to the in-memory LocalSession secret: after launcher/sidecar
restart an old recovery token intentionally fails closed, and the client must
obtain a fresh bootstrap snapshot.
