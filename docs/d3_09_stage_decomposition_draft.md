# D3-09 stage decomposition draft — final dev journey and release evidence

Status: planning only; no implementation authorization.

## Boundary

D3-09 is the final release gate for the narrow dev vertical slice. It proves the
browser can understand and complete the journey while preserving D2 facts. It
does not broaden the sandbox, add remote publish, or waive unresolved prior F#.

## Sub-stages

| Sub-stage | Deliverable | Hard guard |
|---|---|---|
| 09-00 | Final entry decision and release matrix | all prior stage exits are joint ACCEPT |
| 09-01 | Ten clean end-to-end dev runs | each run starts from a clean fixture and has canonical trace |
| 09-02 | Fault matrix | crash/reconnect/cancel/response-loss/export uncertainty remain conservative |
| 09-03 | Evidence bundle and manifest synchronization | every claim has evidence path, hash, and source-of-truth index entry |
| 09-04 | Full static/test/second-scan audit | no F# silently deferred; no unrelated dirty-file scope expansion |
| 09-05 | Independent Claude final review | explicit ACCEPT, VETO, or unresolved with evidence and rebuttal |

## Required invariants

- Ten runs include success, denied, cancellation, worker crash, owner-context loss, reconnect, and export uncertainty cases.
- The final report distinguishes planning evidence from implemented evidence.
- Manifest/hash is regenerated only after source and test changes settle.
- D2 constrained unittest.locked conclusions are not generalized to hostile-code sandbox safety.

## Exit evidence

Clean-run logs/fixtures, failure matrix, browser evidence, Python and TypeScript
verification, manifest digest, synchronized authority index, complete F# scan,
and the final joint review record.

