# D3-03 completion evidence

Date: 2026-08-01

Decision: ACCEPT (Codex and Claude).

- Read-only bootstrap high-water and aggregate/run watermarks share one SQLite
  `BEGIN` snapshot.
- Oversized bootstrap recovery pages are signed, section-bound event projections
  with a fixed high-water; they fail closed after LocalSession restart.
- Projection reducer validates canonical fingerprints, sparse ordering, and
  aggregate/run sequences without inferring success or authorization.
- Python `compileall nana_sidecar tests scripts`: pass.
- Full Python `unittest`: 303 tests passed, 1 existing skip.
- Web projection self-test and TypeScript check: pass.

The only trailing observation was the pre-existing PySide6 shutdown
uncollectable-object `ResourceWarning`; D3-03 adds no mutation path.
