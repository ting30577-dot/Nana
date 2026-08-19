# Review, retention, and retirement reference

Read `docs/DOCUMENT_RETENTION.md` and
`config/document-retention.json` as the repository authority. Apply these
additional execution rules:

- Review only changed code and the nearest contract by default.
- Count repeated findings by fingerprint, not by how many models restate them.
- After one repair and one targeted re-review, escalate persistent P0/P1 issues.
- Never create a Markdown file solely to say a test passed.
- Convert durable findings into ADRs, regression tests, or the single active
  state; discard the conversation that produced them.
- Use Git history rather than an active-tree archive for superseded material.
- Run `python scripts/nana_context.py cleanup-plan` before documentation cleanup.
- Treat `main.py`, `ui/`, `visualizer/`, `db/`, `nana_core/research/`, and their
  tests as migration/rollback assets until the kernel's legacy retirement gate
  is satisfied.
- Treat build/package/cache directories as reproducible output. Resolve every
  deletion target and verify it is inside the repository before removal.
- Never delete `backups/`, runtime data, or user content as documentation cleanup.
