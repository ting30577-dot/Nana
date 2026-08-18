# Legacy SQLite schema inventory

Inventory date: 2026-07-29
Source: baseline commit plus the user's current uncommitted tree
Method: source inspection and existing database/repository regression tests

The default legacy data file is under the operating system's local application
data directory. Its absolute path is intentionally excluded from portable
documentation.

| Table | Owner | Purpose | vNext treatment |
|---|---|---|---|
| `problems` | `db.database.Database` | Legacy solved-problem tracker | Read-only inventory/export |
| `nana_schema_versions` | `ResearchRepository` | Legacy research schema version | Do not reuse as vNext schema history |
| `research_threads` | `ResearchRepository` | Research thread shell | Candidate migration to Project/Inquiry after dry-run |
| `research_sources` | `ResearchRepository` | Source plus free-form locator | Resource candidate; only explicit locators become Evidence |
| `research_claims` | `ResearchRepository` | Source-bound statement | Migration requires semantic review |
| `research_evidence` | `ResearchRepository` | Source/claim evidence row | Migration only when locator remains resolvable |
| `research_methods` | `ResearchRepository` | Manually entered method | Archive or import as a draft revision |
| `research_experiments` | `ResearchRepository` | Manual experiment note | Legacy Artifact/Run note, never a reproducible Run by assumption |
| `research_insights` | `ResearchRepository` | Free-form insight | Draft Finding only; never auto-promote to Decision |

## Important constraints already covered by legacy tests

- Problem number uniqueness and enum checks.
- Research object required fields and enum checks.
- Cross-thread research relationships are rejected.
- Parent rows with research assets use restricted deletion.
- Version-one source rows migrate without data loss.
- Legacy archive export is lossless and hash-verified.

## D0 conclusion

The legacy schema is useful as migration input, not as the vNext canonical
contract. D0 therefore creates an isolated schema with Project/Inquiry/Plan,
Run/Action/Event, authorization records, Artifact metadata, and the minimum
research-semantic objects.
