# D3-08B implementation and no-edit scan

Date: 2026-08-13  
Status: all findings closed

| ID | Severity | Finding | Repair / direct evidence | State |
|---|---|---|---|---|
| F08B-01 | P0 | Historical predecessors were absent. | D3-07 and D3-08A now have Codex-only implementation exits under the owner governance amendment. | closed |
| F08B-02 | P0 | Approval/export collections were absent from the browser projection. | Added strict bootstrap collections, keyed canonical maps and Approval event reduction; future Approval types still degrade. | closed |
| F08B-03 | P0 | No safe typed decision UI existed. | UI emits only RequestApproval and DecideApproval request contracts; subject hash/revision come from the canonical Approval. | closed |
| F08B-04 | P0 | Target meaning was unresolved. | Browser consumes only launcher-issued opaque selection ID plus redacted label/expiry/provenance. No path input or harness-as-user claim exists. | closed |
| F08B-05 | P1 | Receipt/effect-unknown interaction was absent. | Canonical Receipt, billing basis and write fence render; effect_unknown has no retry/resume/rebind/dismiss/success control. | closed |
| F08B-06 | P1 | Browser lifecycle evidence was absent. | Isolated success/denied/expired/fence-uncertain Chromium journeys pass; success survives reload and Axe serious/critical scan. | closed |
| F08B-07 | P0 | Handshake selection summaries were not shape-validated. | Store validates opaque ID, redacted label, parseable expiry and exact provenance, and requires external_effects_enabled plus at least one summary. | closed |
| F08B-08 | P1 | Terminal background export could commit a Receipt after the last command bootstrap. | A terminal Action SSE event triggers a canonical bootstrap so receipts/exports are never inferred from the command response. | closed |
| F08B-09 | P1 | Existing page-wide opacity animation created transient WCAG contrast failures with the full journey populated. | Removed opacity interpolation while retaining small positional motion; Axe passes on the complete export journey. | closed |
| F08B-10 | P2 | Historical read-only test treated now-canonical approval.requested as unknown. | Test now uses approval.future_unknown; all 17 read-only tests pass and still prove future-type degradation. | closed |

## Final read-only scan

- No `EventSource`, PublishExport, ConsumeApproval, AuthorizeAction or
  PolicyGrant control exists in production UI.
- Browser request bodies contain no path, filename, bytes, capability choice,
  authorization, risk or effects.
- Approval is displayed as requested/approved/denied/expired/consumed only
  from canonical facts.
- Command response never proves a filesystem effect. Success, failure and
  uncertainty appear only after canonical Receipt projection.
- `effect_unknown` remains terminal/quarantined and cannot be retried.

Conclusion: **ACCEPT** for D3-08B's exact Approval/export/Receipt UI boundary.
