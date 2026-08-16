# D3-09 final implementation/no-edit scan

Date: 2026-08-13  
Status: all findings closed; final full verification pending at record creation

| ID | Severity | Finding | Resolution / evidence | State |
|---|---|---|---|---|
| F09-01 | P0 | Historical predecessor/joint gates were incomplete. | Owner explicitly replaced Claude prerequisite; D3-06 through 08B each received fresh Codex-only implementation exits without relabelling historical results. | closed |
| F09-02 | P0 | Ten consecutive complete browser journeys were absent. | `scripts/run_d3_ten_success.mjs` ran 10/10 complete create-to-Receipt journeys, each new temporary Workspace/selection, `retries=0`, fail-fast. | closed |
| F09-03 | P1 | Failure matrix was absent. | 25-test release matrix covers read/reconnect/session/stream faults, response loss/conflict, cancel, denied, expired, export uncertainty, worker crash and owner-context loss. | closed |
| F09-04 | P1 | Evidence/manifests were incomplete. | Stage evidence, authority index, completion audit, final machine gate and scoped manifests are synchronized after final source changes. | closed after manifest refresh |
| F09-05 | P0 | Historical plan demanded Claude final review. | Current owner governance expressly forbids further Claude calls and makes Codex sole current authority; historical lack of verdict remains recorded, not forged. | closed by governance, not by pretend review |
| F09-06 | P1 | Final full scan/repair was absent. | This scan plus F09-07..F09-14 and post-repair full gates provide the final Codex no-edit review. | closed after final gates |
| F09-07 | P1 | Canonical Projects were missing from bootstrap, blocking real UI progression. | Field-whitelisted project read model and tests added in D3-08A. | closed |
| F09-08 | P0 | Frontend known-event set diverged for Relation/budget/Approval. | Exact backend parity added; future types still degrade and 17-test read baseline proves it. | closed |
| F09-09 | P0 | Background export settlement could arrive after command reconciliation without Receipt projection. | Terminal Action SSE triggers canonical bootstrap; dedicated store test and browser Receipt evidence pass. | closed |
| F09-10 | P1 | Fully populated UI exposed transient contrast failure during opacity animation. | Opacity interpolation removed; complete export Axe serious/critical scan passes. | closed |
| F09-11 | P1 | Ten-run Node launcher could not spawn `npx.cmd` on Windows. | Invokes the workspace Playwright CLI with current Node directly; 10/10 completed. | closed |
| F09-12 | P1 | Test harness could be mistaken for genuine user target selection. | Harness summaries say `test_harness`; separate launcher composition test proves stdin-based `interactive_user` source and redacted summary. | closed |
| F09-13 | P2 | Authoritative full-plan footer still described a historical D3-07 pause. | Preserved it as explicitly superseded history and added a current live-placement section. | closed |
| F09-14 | P2 | Windows Proactor logs a connection reset when Playwright tears down the last passed uvicorn harness. | Release matrix exits 0 after 25/25; recorded as post-test harness shutdown noise, not a source result. | accepted environment attribution |

## No-edit scope audit

- Production React contains no native EventSource, raw command editor,
  PublishExport, public ConsumeApproval, PolicyGrant or AuthorizeAction UI.
- Generated OpenAPI types retain the complete backend schema, but production
  components never render the broader mutation types. The runtime handshake
  and explicit component map are the active default-deny browser boundary.
- StartRun still excludes backend/capability/test ID from browser input.
- RequestApproval includes only command ID, Finding revision/ID and opaque
  selection ID. DecideApproval includes only canonical Approval ID/revision,
  subject hash and approve/deny decision.
- Browser never writes a file and never reports command-response success as an
  external effect. Receipt is canonical; effect_unknown is quarantined.
- No Claude command, relay or adapter was called in the current implementation
  or final verification.
- D2 safety scope remains exact trusted fixture-only `python.unittest.locked`,
  not a general hostile-code sandbox.

No unresolved material F09 finding remains after final green verification and
manifest refresh.
