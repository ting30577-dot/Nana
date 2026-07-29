# v0.2.0-alpha legacy baseline

Status: frozen legacy prototype  
Baseline commit: `2a313c063d6a21e23eee18162f0db277d301078b`  
Runtime: Python `3.12.13`

This baseline exists for regression, export, and migration comparison. It is
not a vNext implementation and receives no new product features.

## Recorded evidence

- `python -m unittest discover -s tests -v`: 61/61 passed before D0 changes.
- `schema-inventory.md`: source-level inventory of the legacy SQLite objects.
- `reuse-inventory.md`: explicit keep/archive boundaries.
- `ui-main-window.png`: empty-data screenshot rendered against a temporary
  database, so no user content is captured.

## Boundary

- The legacy PySide6 UI and repositories remain runnable for comparison.
- `nana_sidecar` uses a separate schema and never writes legacy tables.
- No new UI writes both old and vNext stores.
- Deletion and migration remain outside D0.
