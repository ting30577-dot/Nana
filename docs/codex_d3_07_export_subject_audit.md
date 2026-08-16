# Codex D3-07 export-subject and lifecycle audit

Date: 2026-08-09  
Status: planning-only; no route, capability, schema or filesystem writer is
authorized by this record.

## Audited authority and current runtime facts

1. Authority 05 exposes the canonical Commands `StartRun`, `ProposeAction`,
   `CommitArtifact`, `RequestApproval`, `DecideApproval`, `CreateRelation` and
   `PublishExport`. D3-00 Command-vocabulary decision G requires product-level
   services to compose the smallest existing typed Command subset; a new
   canonical Command requires an explicit contract decision. The reversible D3
   draft export must not reuse T4 `PublishExport`.
2. The current D3 journey `StartRun` writer is intentionally specialized to
   `python.unittest.locked`. It creates the D3-06 algorithm Run and Action and
   cannot be reused as-is for `export.draft_external`.
3. The Relation Registry is closed. Existing relevant edges are
   `run_produces_artifact`, `run_produces_finding`, and
   `artifact_derived_from_artifact`; unknown relations must enter an explicit
   extension proposal and may not be written as arbitrary strings.
4. The frozen dev fixture's initial Finding is Evidence-backed and predates the
   algorithm Run. D3-06 produces one `text/plain` test-result Artifact with a
   canonical `run_produces_artifact` edge. It does not produce the required
   non-sensitive Markdown draft-report Artifact.
5. The product-owner-frozen denied branch of `DecideApproval` may write only the
   denied decision, Event/outbox and stable CommandResult. It cannot also
   terminalize the independent Export Run in that transaction.

## Findings

| ID | Severity | Finding | Consequence | Current decision |
|---|---|---|---|---|
| F07-22 | P0 | “Canonical Relation + frozen snapshot” had not been mapped to the closed Relation Registry. | No current RelationType directly means Export Run consumes a Finding or source Run. Reusing `run_retry_of_run` or inventing a string would be false provenance. | **Resolved as product design:** use the existing producer/Artifact-lineage graph below plus the frozen snapshot; no Registry extension. Joint review/evidence remain gated. |
| F07-23 | P0 | No accepted request composition created the Export Run, exact Action and Approval subject. | Current browser `StartRun` is T2-only; raw `ProposeAction`, capability, ActionHash or authorization material cannot enter the browser. A silent new canonical Command would violate D3-00 G. | **Resolved as product design:** narrow Finding-version + opaque-selection application request; owner derives every subject and composes existing semantics. Joint review/evidence remain gated. |
| F07-24 | P0 | Denial/expiry would otherwise leave the independent Export Run non-terminal. | Adding Run cancellation to the denied `DecideApproval` transaction violates the frozen denied branch; omitting cleanup leaves a permanent running Run. | **Resolved as product design:** deterministic system-owned `CancelRun` after the minimal transaction, with fixed identity/correlation and startup idempotent replay. Joint evidence remains gated. |
| F07-25 | P0 | The exact draft-report Artifact did not exist and its renderer contract was unspecified. | Exporting the D3-06 test-result bytes would not prove the authoritative “draft report” journey. Rendering mutable bytes after Approval would invalidate the ActionHash. | **Resolved as product design:** only canonically `public` inputs; exact fixed UTF-8/NFC/LF Markdown ≤4096 bytes, renderer digest/DRAFT marker and 50 canaries; commit before Approval. Joint evidence remains gated. |

## Recommended no-new-Command/no-new-Relation composition

This composition is product-frozen by
`docs/d3_07_plan_aligned_decisions.md` and remains subject to independent/joint
security review; it is not an implementation authorization.

1. The post-algorithm Finding used for export must include the terminal
   algorithm Run, creating the existing `run_produces_finding` edge. The same
   Run must already own the selected result Artifact through
   `run_produces_artifact`.
2. A narrow browser `RequestApproval` journey request supplies only
   `command_id`, the current Finding aggregate/Event version, Finding id and
   opaque selection id. It supplies no Run id, source/draft/args Artifact id,
   Action id, capability, path, bytes, hash, authorization reference, risk or
   effect declaration. The owner derives the unique terminal algorithm Run from
   the Finding producer edge and the exact D3-06 result Artifact from that Run's
   Receipt plus producer edge.
3. After command-id/request-hash replay preflight and all non-writing source,
   selection, size and canary checks pass, the owner service derives
   deterministic ids and composes the existing
   `StartRun`/`ProposeAction`/`CommitArtifact`/`RequestApproval` semantics. The
   product-level request is not a new canonical Command and never invokes T4
   `PublishExport`.
4. D1 Artifact commit uses its accepted multi-phase protocol. The exact Markdown
   draft Artifact and a canonical JSON Action-args Artifact are first committed
   inside Workspace under deterministic content-bound ids. The args object
   contains only server-derived draft Artifact id/hash, renderer digest, opaque
   target-selection identity/digest, fixed target filename, media type and size;
   it contains no absolute path. A crash after these commits but before the
   request transaction leaves only unreferenced Workspace Artifacts; replay
   reuses the same verified bytes. The subsequent owner-lane transaction
   atomically creates the separate Export Run, attaches the draft Artifact's
   producer/provenance Relations, creates the exact T3 Action and Approval,
   appends Events/outbox, and stores the stable CommandResult.
5. The existing-edge provenance graph is:

   ```text
   algorithm Run --run_produces_finding--> Finding
   algorithm Run --run_produces_artifact--> test-result Artifact
   Export Run    --run_produces_artifact--> draft-report Artifact
   draft-report Artifact --artifact_derived_from_artifact--> test-result Artifact
   ```

   The Export Run snapshot additionally freezes all four ids, the Finding
   revision/content commitment, source and draft Artifact hashes, capability
   digest, target selection identity, exact effects, policy/budget, public
   data-class proof, renderer version and output constraints. No direct Export Run→Finding/algorithm-Run
   Relation is claimed.
6. `DecideApproval(approved)` follows the already-frozen atomic authorization
   transaction. The owner then commits a durable first-write fence before the
   real probe or any external byte. `denied` remains the exact minimal
   transaction; a correlated deterministic `CancelRun` follows separately and
   is recovered idempotently after restart. Expiry uses the same rule.

## Product-frozen draft-report renderer

The D3 fixture is a UTF-8 `text/markdown` renderer with a fixed version/digest.
Export eligibility requires every input to be canonically `public`; unknown,
mixed or non-public input is rejected rather than “sanitized.” It includes only
allowlisted public fields:
Inquiry question, escaped/plain-text Finding statement and confidence basis,
terminal algorithm Run result summary, source Artifact hash, and a clear
`DRAFT` marker. It should exclude absolute/logical paths, raw stdout/stderr,
environment values, credentials, provider material, active user-supplied
Markdown/HTML and external links. Escaping prevents injection and is not a
privacy classifier or sanitization mechanism.

## Gate effect

F07-22 through F07-25 now have product decisions but no independent/joint
verdict or implementation evidence. They add no permission to
the machine-readable gate: `joint_status=unresolved`,
`implementation_authorized=false`, `capability_registered=false`, and
`filesystem_write_authorized=false` remain authoritative.

## Candidate browser request shape

```text
RequestApproval {
  type: "RequestApproval"
  command_id: UUID
  expected_revision: integer  // current Finding aggregate/Event version
  finding_id: UUID
  target_selection_id: opaque string
}
```

The owner rejects an Evidence-only Finding, a non-terminal/missing producer Run,
zero or multiple eligible D3-06 result Artifacts, stale Finding Event version,
expired/mismatched selection, non-public source data, renderer/canary failure,
or any graph/hash inconsistency before creating the Export subject. Approval
expiry may not exceed the 60-minute/LocalSession-bound selection expiry. No field in this request names
`export.draft_external`; capability choice remains server-owned.

## Candidate D3 renderer v1

The candidate byte contract uses UTF-8 without BOM, Unicode NFC, LF line endings
and exactly one trailing LF. The maximum encoded size is 4,096 bytes; overflow
fails before creating an Export subject. Canonical text fields are converted to
plain text by rejecting control characters and escaping Markdown/HTML/link
syntax before interpolation.

```text
# Nana D3 Draft Report

> DRAFT — This is not a final Decision or a published result.

## Inquiry
{escaped inquiry question}

## Finding
{escaped finding statement}

## Confidence basis
{escaped confidence basis}

## Execution evidence
- Algorithm Run: `{run id}`
- Run result: `succeeded`
- Action Receipt: `succeeded`
- Source Artifact: `{artifact id}`
- Source SHA-256: `{artifact hash}`

## Scope
This report contains only the frozen v0.3.0-dev fixture summary.
```

The renderer never interpolates paths, source Artifact bytes, stdout/stderr,
environment/provider values, arbitrary metadata or external URLs. The rendered
bytes must also pass the dedicated export credential-canary corpus with zero
matches. Renderer source/template digest, exact escaping vectors and 50 canary
cases remain implementation evidence after product and joint acceptance.
