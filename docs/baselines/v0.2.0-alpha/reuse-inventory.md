# v0.2.0-alpha reuse inventory

| Asset | Decision | Reason / condition |
|---|---|---|
| `algorithms/` pure functions | Reuse | Deterministic, independent of PySide6, covered by tests |
| `tests/test_algorithm_patterns.py` | Reuse | Stable algorithm regression assets |
| `tests/test_sliding_window.py` | Reuse | Contains the locked dev test and an existing negative-input boundary test |
| `db/legacy_export.py` | Reuse for migration evidence | Lossless export and digest checks already exist |
| `nana_core/research/legacy_migration.py` | Reuse as read-only input logic | Must not become a vNext write path |
| Claude adapter and its tests | Conditionally reuse | Adapter behavior is tested; the missing final countersignature must never be claimed |
| PySide6 UI pages | Freeze | Screenshot/migration comparison only; no new product features |
| Legacy `Database` / `ResearchRepository` writes | Freeze | They do not satisfy the vNext canonical/event/receipt contract |
| Build artifacts under `build/` and `dist/` | Do not reuse as source | Rebuild from versioned source when needed |

The first registered runtime test is:

`tests.test_sliding_window.VariableWindowTests.test_finds_shortest_matching_window`

It is deliberately narrower than the alpha.1 investigation.
