"""Canonical vNext schema introduced by migration 0001."""

from __future__ import annotations

import hashlib


SCHEMA_V1_SQL = r"""
CREATE TABLE schema_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
) STRICT;

CREATE TABLE migration_history (
    version INTEGER PRIMARY KEY CHECK (version >= 1),
    name TEXT NOT NULL UNIQUE,
    contract_hash TEXT NOT NULL,
    applied_at TEXT NOT NULL
) STRICT;

CREATE TABLE workspaces (
    id TEXT PRIMARY KEY,
    schema_version INTEGER NOT NULL CHECK (schema_version >= 1),
    data_root TEXT NOT NULL,
    policy_json TEXT NOT NULL CHECK (json_valid(policy_json)),
    status TEXT NOT NULL CHECK (status IN ('active', 'safe_mode', 'read_only')),
    revision INTEGER NOT NULL CHECK (revision >= 1),
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE RESTRICT,
    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
    status TEXT NOT NULL CHECK (status IN ('active', 'paused', 'archived')),
    data_class TEXT NOT NULL CHECK (
        data_class IN ('public', 'personal', 'confidential', 'secret')
    ),
    revision INTEGER NOT NULL CHECK (revision >= 1),
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE inquiries (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    question TEXT NOT NULL CHECK (length(trim(question)) > 0),
    acceptance TEXT NOT NULL CHECK (length(trim(acceptance)) > 0),
    status TEXT NOT NULL CHECK (
        status IN (
            'draft', 'ready', 'active', 'blocked', 'in_review', 'decided',
            'cancelled', 'closed'
        )
    ),
    revision INTEGER NOT NULL CHECK (revision >= 1),
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE plans (
    id TEXT NOT NULL,
    inquiry_id TEXT NOT NULL REFERENCES inquiries(id) ON DELETE RESTRICT,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    status TEXT NOT NULL CHECK (
        status IN (
            'draft', 'proposed', 'approved', 'running', 'completed',
            'rejected', 'superseded'
        )
    ),
    steps_json TEXT NOT NULL CHECK (json_valid(steps_json)),
    policy_json TEXT NOT NULL CHECK (json_valid(policy_json)),
    budget_json TEXT NOT NULL CHECK (json_valid(budget_json)),
    created_at TEXT NOT NULL,
    PRIMARY KEY (id, revision)
) STRICT;

CREATE TABLE runs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    inquiry_id TEXT NOT NULL REFERENCES inquiries(id) ON DELETE RESTRICT,
    state TEXT NOT NULL CHECK (
        state IN (
            'proposed', 'queued', 'running', 'paused', 'succeeded', 'failed',
            'cancelled', 'timed_out', 'budget_exceeded', 'orphaned'
        )
    ),
    snapshot_json TEXT NOT NULL CHECK (json_valid(snapshot_json)),
    retry_of_run_id TEXT REFERENCES runs(id) ON DELETE RESTRICT,
    result_json TEXT CHECK (result_json IS NULL OR json_valid(result_json)),
    created_at TEXT NOT NULL,
    finished_at TEXT,
    CHECK (
        (
            state IN (
                'succeeded', 'failed', 'cancelled', 'timed_out',
                'budget_exceeded', 'orphaned'
            )
            AND finished_at IS NOT NULL
        )
        OR (
            state NOT IN (
                'succeeded', 'failed', 'cancelled', 'timed_out',
                'budget_exceeded', 'orphaned'
            )
            AND finished_at IS NULL
        )
    )
) STRICT;

CREATE TABLE artifacts (
    id TEXT PRIMARY KEY,
    media_type TEXT NOT NULL,
    blob_hash TEXT NOT NULL,
    size INTEGER NOT NULL CHECK (size >= 0),
    state TEXT NOT NULL CHECK (
        state IN (
            'staged', 'available', 'failed', 'orphan_quarantined', 'corrupt',
            'tombstoned', 'garbage_collected'
        )
    ),
    temp_ref TEXT,
    producer_run_id TEXT REFERENCES runs(id) ON DELETE RESTRICT,
    license TEXT,
    retention_json TEXT NOT NULL CHECK (json_valid(retention_json)),
    created_at TEXT NOT NULL,
    CHECK (
        state <> 'staged'
        OR (temp_ref IS NOT NULL AND length(trim(temp_ref)) > 0)
    ),
    CHECK (state <> 'available' OR temp_ref IS NULL)
) STRICT;

CREATE TABLE actions (
    id TEXT PRIMARY KEY,
    run_id TEXT REFERENCES runs(id) ON DELETE RESTRICT,
    plan_step_id TEXT,
    capability_id TEXT NOT NULL,
    capability_version TEXT NOT NULL,
    executable_digest TEXT,
    args_artifact_id TEXT NOT NULL REFERENCES artifacts(id) ON DELETE RESTRICT,
    args_hash TEXT NOT NULL,
    action_hash TEXT NOT NULL,
    risk_tier TEXT NOT NULL CHECK (risk_tier IN ('T0', 'T1', 'T2', 'T3', 'T4')),
    requested_effects_json TEXT NOT NULL CHECK (json_valid(requested_effects_json)),
    policy_decision TEXT NOT NULL CHECK (
        policy_decision IN ('auto', 'grant', 'approval_required', 'denied')
    ),
    authorization_ref TEXT,
    state TEXT NOT NULL CHECK (
        state IN (
            'proposed', 'waiting_approval', 'authorized', 'running', 'succeeded',
            'failed', 'cancelled', 'timed_out', 'denied', 'expired',
            'effect_unknown'
        )
    ),
    started_at TEXT,
    finished_at TEXT
) STRICT;

CREATE TABLE policy_grants (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    capability_id TEXT NOT NULL,
    capability_version TEXT NOT NULL,
    executable_digest TEXT,
    constraints_json TEXT NOT NULL CHECK (json_valid(constraints_json)),
    state TEXT NOT NULL CHECK (
        state IN ('proposed', 'active', 'rejected', 'revoked', 'expired', 'exhausted')
    ),
    uses INTEGER NOT NULL CHECK (uses >= 0),
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE approvals (
    id TEXT PRIMARY KEY,
    subject_type TEXT NOT NULL CHECK (subject_type IN ('action', 'policy_grant')),
    subject_id TEXT NOT NULL,
    subject_hash TEXT NOT NULL,
    capability_json TEXT NOT NULL CHECK (json_valid(capability_json)),
    parameter_summary_json TEXT NOT NULL CHECK (json_valid(parameter_summary_json)),
    requested_effects_json TEXT NOT NULL CHECK (json_valid(requested_effects_json)),
    data_class TEXT NOT NULL CHECK (
        data_class IN ('public', 'personal', 'confidential', 'secret')
    ),
    provider TEXT,
    budget_json TEXT NOT NULL CHECK (json_valid(budget_json)),
    risk_tier TEXT NOT NULL CHECK (risk_tier IN ('T0', 'T1', 'T2', 'T3', 'T4')),
    reversible INTEGER NOT NULL CHECK (reversible IN (0, 1)),
    allowed_uses INTEGER NOT NULL CHECK (allowed_uses >= 1),
    expires_at TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (
        decision IN ('requested', 'approved', 'denied', 'expired')
    ),
    decided_by_json TEXT CHECK (
        decided_by_json IS NULL OR json_valid(decided_by_json)
    ),
    decided_at TEXT,
    CHECK (
        (
            decision = 'requested'
            AND decided_by_json IS NULL
            AND decided_at IS NULL
        )
        OR (
            decision <> 'requested'
            AND decided_by_json IS NOT NULL
            AND decided_at IS NOT NULL
        )
    )
) STRICT;

CREATE TABLE action_receipts (
    id TEXT PRIMARY KEY,
    action_id TEXT NOT NULL UNIQUE REFERENCES actions(id) ON DELETE RESTRICT,
    action_hash TEXT NOT NULL,
    authorization_source TEXT NOT NULL CHECK (
        authorization_source IN ('auto_policy', 'policy_grant', 'approval')
    ),
    authorization_ref TEXT NOT NULL,
    approved_by_json TEXT CHECK (
        approved_by_json IS NULL OR json_valid(approved_by_json)
    ),
    approved_at TEXT,
    actual_effects_json TEXT NOT NULL CHECK (json_valid(actual_effects_json)),
    result TEXT NOT NULL CHECK (
        result IN ('succeeded', 'failed', 'cancelled', 'timed_out', 'effect_unknown')
    ),
    exit_code INTEGER,
    before_artifact_ids_json TEXT NOT NULL CHECK (
        json_valid(before_artifact_ids_json)
    ),
    after_artifact_ids_json TEXT NOT NULL CHECK (
        json_valid(after_artifact_ids_json)
    ),
    diff_artifact_id TEXT REFERENCES artifacts(id) ON DELETE RESTRICT,
    resource_usage_json TEXT NOT NULL CHECK (json_valid(resource_usage_json)),
    undo_ref TEXT,
    compensating_action_id TEXT REFERENCES actions(id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL,
    CHECK (
        (
            authorization_source = 'approval'
            AND approved_by_json IS NOT NULL
            AND approved_at IS NOT NULL
        )
        OR (
            authorization_source <> 'approval'
            AND approved_by_json IS NULL
            AND approved_at IS NULL
        )
    )
) STRICT;

CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    aggregate_type TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    aggregate_version INTEGER NOT NULL CHECK (aggregate_version >= 1),
    run_id TEXT REFERENCES runs(id) ON DELETE RESTRICT,
    run_seq INTEGER CHECK (run_seq IS NULL OR run_seq >= 1),
    action_id TEXT REFERENCES actions(id) ON DELETE RESTRICT,
    actor_json TEXT NOT NULL CHECK (json_valid(actor_json)),
    causation_id TEXT,
    correlation_id TEXT,
    type TEXT NOT NULL CHECK (
        type IN (
            'workspace.created',
            'project.created', 'project.status_changed',
            'inquiry.created', 'inquiry.status_changed',
            'plan.proposed', 'plan.revised', 'plan.status_changed',
            'run.created', 'run.started', 'run.heartbeat', 'run.paused',
            'run.cancelled', 'run.timed_out', 'run.failed', 'run.succeeded',
            'run.budget_exceeded', 'run.orphaned',
            'plan.step.started', 'plan.step.completed', 'plan.step.failed',
            'action.proposed', 'action.authorized', 'action.started',
            'action.output', 'action.completed', 'action.cancelled',
            'action.effect_unknown',
            'artifact.staged', 'artifact.committed', 'artifact.reconciled',
            'budget.updated', 'budget.threshold_reached',
            'policy_grant.created', 'policy_grant.revoked',
            'policy_grant.expired',
            'approval.requested', 'approval.decided', 'approval.expired',
            'resource.registered', 'locator.created', 'claim.created',
            'evidence.attached', 'hypothesis.created', 'finding.drafted',
            'relation.created', 'export.published'
        )
    ),
    payload_json TEXT CHECK (payload_json IS NULL OR json_valid(payload_json)),
    payload_artifact_id TEXT REFERENCES artifacts(id) ON DELETE RESTRICT,
    occurred_at TEXT NOT NULL,
    CHECK (
        (payload_json IS NOT NULL AND payload_artifact_id IS NULL)
        OR (payload_json IS NULL AND payload_artifact_id IS NOT NULL)
    ),
    CHECK (
        type <> 'artifact.staged'
        OR COALESCE((
            aggregate_type = 'artifact'
            AND payload_json IS NOT NULL
            AND json_type(payload_json, '$') = 'object'
            AND json_extract(payload_json, '$.artifact_id') = aggregate_id
            AND json_extract(payload_json, '$.state') = 'staged'
            AND json_type(payload_json, '$.temp_ref') = 'text'
            AND length(trim(json_extract(payload_json, '$.temp_ref'))) > 0
            AND json_type(payload_json, '$.blob_hash') = 'text'
            AND json_type(payload_json, '$.size') = 'integer'
            AND json_extract(payload_json, '$.size') >= 0
            AND json_type(payload_json, '$.media_type') = 'text'
            AND length(trim(json_extract(payload_json, '$.media_type'))) > 0
        ), 0)
    ),
    CHECK (
        type <> 'artifact.committed'
        OR COALESCE((
            aggregate_type = 'artifact'
            AND payload_json IS NOT NULL
            AND json_type(payload_json, '$') = 'object'
            AND json_extract(payload_json, '$.artifact_id') = aggregate_id
            AND json_extract(payload_json, '$.state') = 'available'
            AND json_type(payload_json, '$.blob_hash') = 'text'
            AND json_type(payload_json, '$.size') = 'integer'
            AND json_extract(payload_json, '$.size') >= 0
            AND json_type(payload_json, '$.media_type') = 'text'
            AND length(trim(json_extract(payload_json, '$.media_type'))) > 0
        ), 0)
    ),
    CHECK (
        type <> 'artifact.reconciled'
        OR COALESCE((
            aggregate_type = 'artifact'
            AND payload_json IS NOT NULL
            AND json_type(payload_json, '$') = 'object'
            AND json_extract(payload_json, '$.artifact_id') = aggregate_id
            AND json_type(payload_json, '$.previous_state') = 'text'
            AND json_type(payload_json, '$.state') = 'text'
            AND json_type(payload_json, '$.reason_code') = 'text'
            AND length(trim(json_extract(payload_json, '$.reason_code'))) > 0
        ), 0)
    ),
    CHECK (run_seq IS NULL OR run_id IS NOT NULL),
    UNIQUE (aggregate_type, aggregate_id, aggregate_version),
    UNIQUE (run_id, run_seq)
) STRICT;

CREATE TABLE outbox_events (
    event_id INTEGER PRIMARY KEY REFERENCES events(id) ON DELETE RESTRICT,
    dispatched_at TEXT,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0)
) STRICT;

CREATE TABLE command_log (
    command_id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    actor_json TEXT NOT NULL CHECK (json_valid(actor_json)),
    state TEXT NOT NULL CHECK (state IN ('accepted', 'rejected')),
    result_json TEXT CHECK (result_json IS NULL OR json_valid(result_json)),
    error_json TEXT CHECK (error_json IS NULL OR json_valid(error_json)),
    created_at TEXT NOT NULL,
    finished_at TEXT,
    CHECK (
        NOT (result_json IS NOT NULL AND error_json IS NOT NULL)
    )
) STRICT;

CREATE TABLE resources (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    kind TEXT NOT NULL,
    logical_ref TEXT NOT NULL,
    content_hash TEXT,
    media_type TEXT NOT NULL,
    data_class TEXT NOT NULL CHECK (
        data_class IN ('public', 'personal', 'confidential', 'secret')
    ),
    license TEXT,
    captured_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('draft', 'available', 'stale', 'failed', 'tombstoned')
    ),
    revision INTEGER NOT NULL CHECK (revision >= 1)
) STRICT;

CREATE TABLE locators (
    id TEXT PRIMARY KEY,
    resource_id TEXT NOT NULL REFERENCES resources(id) ON DELETE RESTRICT,
    locator_type TEXT NOT NULL CHECK (
        locator_type IN ('web', 'pdf', 'repo', 'local_file', 'dataset', 'run_output')
    ),
    coordinates_json TEXT NOT NULL CHECK (json_valid(coordinates_json)),
    quote_hash TEXT,
    parser_id TEXT,
    parser_version TEXT,
    status TEXT NOT NULL CHECK (
        status IN (
            'draft', 'valid', 'invalid', 'stale', 'source_unavailable',
            'tombstoned'
        )
    ),
    revision INTEGER NOT NULL CHECK (revision >= 1),
    CHECK (json_extract(coordinates_json, '$.kind') = locator_type)
) STRICT;

CREATE TABLE claims (
    id TEXT PRIMARY KEY,
    inquiry_id TEXT NOT NULL REFERENCES inquiries(id) ON DELETE RESTRICT,
    statement TEXT NOT NULL CHECK (length(trim(statement)) > 0),
    status TEXT NOT NULL CHECK (
        status IN (
            'draft', 'in_review', 'verified', 'contested', 'rejected',
            'superseded'
        )
    ),
    revision INTEGER NOT NULL CHECK (revision >= 1),
    created_by_json TEXT NOT NULL CHECK (json_valid(created_by_json))
) STRICT;

CREATE TABLE evidence (
    id TEXT PRIMARY KEY,
    inquiry_id TEXT NOT NULL REFERENCES inquiries(id) ON DELETE RESTRICT,
    locator_id TEXT NOT NULL REFERENCES locators(id) ON DELETE RESTRICT,
    direction TEXT NOT NULL CHECK (direction IN ('supports', 'opposes', 'limits')),
    excerpt_hash TEXT,
    status TEXT NOT NULL CHECK (
        status IN (
            'lead', 'valid', 'rejected', 'stale', 'source_unavailable',
            'tombstoned'
        )
    ),
    created_by_json TEXT NOT NULL CHECK (json_valid(created_by_json))
) STRICT;

CREATE TABLE hypotheses (
    id TEXT PRIMARY KEY,
    inquiry_id TEXT NOT NULL REFERENCES inquiries(id) ON DELETE RESTRICT,
    statement TEXT NOT NULL CHECK (length(trim(statement)) > 0),
    falsification_criteria TEXT NOT NULL CHECK (
        length(trim(falsification_criteria)) > 0
    ),
    status TEXT NOT NULL CHECK (
        status IN (
            'proposed', 'testing', 'supported', 'falsified', 'inconclusive',
            'superseded'
        )
    ),
    created_by_json TEXT NOT NULL CHECK (json_valid(created_by_json))
) STRICT;

CREATE TABLE methods (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    preconditions TEXT NOT NULL CHECK (length(trim(preconditions)) > 0),
    procedure_artifact_id TEXT NOT NULL
        REFERENCES artifacts(id) ON DELETE RESTRICT,
    status TEXT NOT NULL CHECK (
        status IN ('draft', 'validated', 'deprecated', 'superseded')
    ),
    revision INTEGER NOT NULL CHECK (revision >= 1),
    created_by_json TEXT NOT NULL CHECK (json_valid(created_by_json))
) STRICT;

CREATE TABLE findings (
    id TEXT PRIMARY KEY,
    inquiry_id TEXT NOT NULL REFERENCES inquiries(id) ON DELETE RESTRICT,
    statement TEXT NOT NULL CHECK (length(trim(statement)) > 0),
    status TEXT NOT NULL CHECK (
        status IN ('draft', 'in_review', 'accepted', 'rejected', 'superseded')
    ),
    confidence_basis TEXT NOT NULL CHECK (length(trim(confidence_basis)) > 0),
    evidence_ids_json TEXT NOT NULL CHECK (json_valid(evidence_ids_json)),
    producer_run_id TEXT REFERENCES runs(id) ON DELETE RESTRICT,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    CHECK (
        json_array_length(evidence_ids_json) > 0
        OR producer_run_id IS NOT NULL
    )
) STRICT;

CREATE TABLE decisions (
    id TEXT PRIMARY KEY,
    inquiry_id TEXT NOT NULL REFERENCES inquiries(id) ON DELETE RESTRICT,
    statement TEXT NOT NULL CHECK (length(trim(statement)) > 0),
    alternatives_json TEXT NOT NULL CHECK (json_valid(alternatives_json)),
    limitations_json TEXT NOT NULL CHECK (json_valid(limitations_json)),
    reevaluate_when TEXT NOT NULL CHECK (length(trim(reevaluate_when)) > 0),
    status TEXT NOT NULL CHECK (
        status IN ('draft', 'in_review', 'confirmed', 'rejected', 'superseded')
    ),
    revision INTEGER NOT NULL CHECK (revision >= 1),
    confirmed_by_json TEXT CHECK (
        confirmed_by_json IS NULL OR json_valid(confirmed_by_json)
    ),
    confirmed_at TEXT,
    CHECK (
        (
            status = 'confirmed'
            AND confirmed_by_json IS NOT NULL
            AND confirmed_at IS NOT NULL
        )
        OR (
            status <> 'confirmed'
            AND confirmed_by_json IS NULL
            AND confirmed_at IS NULL
        )
    )
) STRICT;

CREATE TABLE relations (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK (
        type IN (
            'resource_contains_evidence',
            'evidence_supports_claim',
            'evidence_opposes_claim',
            'evidence_limits_claim',
            'hypothesis_tested_by_run',
            'run_produces_artifact',
            'run_produces_finding',
            'finding_informs_decision',
            'decision_accepts_method',
            'artifact_derived_from_artifact',
            'run_retry_of_run',
            'object_supersedes_object'
        )
    ),
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    producer_run_id TEXT REFERENCES runs(id) ON DELETE RESTRICT,
    created_by_json TEXT NOT NULL CHECK (json_valid(created_by_json)),
    status TEXT NOT NULL CHECK (status IN ('active', 'tombstoned'))
) STRICT;

CREATE INDEX idx_inquiries_project ON inquiries(project_id);
CREATE INDEX idx_plans_inquiry ON plans(inquiry_id, revision);
CREATE INDEX idx_runs_project ON runs(project_id);
CREATE INDEX idx_actions_run ON actions(run_id);
CREATE INDEX idx_events_aggregate
    ON events(aggregate_type, aggregate_id, aggregate_version);
CREATE INDEX idx_events_run ON events(run_id, run_seq);
CREATE INDEX idx_resources_project ON resources(project_id);
CREATE INDEX idx_evidence_inquiry ON evidence(inquiry_id);
CREATE INDEX idx_findings_inquiry ON findings(inquiry_id);
CREATE INDEX idx_relations_source ON relations(source_type, source_id, type);
CREATE INDEX idx_relations_target ON relations(target_type, target_id, type);
"""


SCHEMA_V1_HASH = (
    "sha256:" + hashlib.sha256(SCHEMA_V1_SQL.encode("utf-8")).hexdigest()
)

# Compatibility alias for callers that only need the initial SQL text.
SCHEMA_SQL = SCHEMA_V1_SQL

SCHEMA_V2_SQL = r"""
CREATE TEMP TABLE __d2_00_guard (
    value INTEGER NOT NULL CHECK (value = 0)
) STRICT;

INSERT INTO __d2_00_guard(value)
SELECT 1
WHERE EXISTS (
    SELECT 1
    FROM actions
    WHERE executable_digest IS NULL
       OR length(trim(executable_digest)) = 0
);

INSERT INTO __d2_00_guard(value)
SELECT 1
WHERE EXISTS (
    SELECT 1
    FROM policy_grants
    WHERE executable_digest IS NULL
       OR length(trim(executable_digest)) = 0
);

INSERT INTO __d2_00_guard(value)
SELECT 1
WHERE EXISTS (
    SELECT 1
    FROM approvals
    WHERE allowed_uses <> 1
       OR json_extract(capability_json, '$.digest') IS NULL
       OR length(trim(json_extract(capability_json, '$.digest'))) = 0
);

INSERT INTO __d2_00_guard(value)
SELECT 1
WHERE EXISTS (
    SELECT 1
    FROM action_receipts
);

DROP TABLE __d2_00_guard;

CREATE TABLE capability_registry_entries (
    capability_id TEXT NOT NULL,
    capability_version TEXT NOT NULL,
    executable_digest TEXT NOT NULL,
    args_schema_json TEXT NOT NULL CHECK (json_valid(args_schema_json)),
    risk_tier TEXT NOT NULL CHECK (
        risk_tier IN ('T0', 'T1', 'T2', 'T3', 'T4')
    ),
    reversible INTEGER NOT NULL CHECK (reversible IN (0, 1)),
    authorization_mode TEXT NOT NULL CHECK (
        authorization_mode IN (
            'auto_policy',
            'policy_grant',
            'one_time_approval'
        )
    ),
    grantable INTEGER NOT NULL CHECK (grantable IN (0, 1)),
    provider_mode TEXT NOT NULL CHECK (
        provider_mode IN ('forbidden', 'optional', 'required')
    ),
    allowed_providers_json TEXT NOT NULL CHECK (json_valid(allowed_providers_json)),
    contract_digest TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (capability_id, capability_version, executable_digest)
) STRICT;

CREATE TABLE approval_consumptions (
    approval_id TEXT PRIMARY KEY REFERENCES approvals(id) ON DELETE RESTRICT,
    action_id TEXT NOT NULL UNIQUE REFERENCES actions(id) ON DELETE RESTRICT,
    event_id INTEGER UNIQUE REFERENCES events(id) ON DELETE RESTRICT,
    consumed_at TEXT NOT NULL
) STRICT;

ALTER TABLE action_receipts ADD COLUMN authorized_effects_json TEXT NOT NULL
    DEFAULT '{"reads":[],"writes":[],"network":[],"processes":[]}'
    CHECK (json_valid(authorized_effects_json));

ALTER TABLE action_receipts ADD COLUMN effect_violation INTEGER NOT NULL
    DEFAULT 0
    CHECK (effect_violation IN (0, 1));

CREATE TRIGGER actions_require_executable_digest_insert
BEFORE INSERT ON actions
WHEN NEW.executable_digest IS NULL
   OR length(trim(NEW.executable_digest)) = 0
BEGIN
    SELECT RAISE(ABORT, 'actions require executable_digest');
END;

CREATE TRIGGER actions_require_executable_digest_update
BEFORE UPDATE ON actions
WHEN NEW.executable_digest IS NULL
   OR length(trim(NEW.executable_digest)) = 0
BEGIN
    SELECT RAISE(ABORT, 'actions require executable_digest');
END;

CREATE TRIGGER policy_grants_require_executable_digest_insert
BEFORE INSERT ON policy_grants
WHEN NEW.executable_digest IS NULL
   OR length(trim(NEW.executable_digest)) = 0
BEGIN
    SELECT RAISE(ABORT, 'policy_grants require executable_digest');
END;

CREATE TRIGGER policy_grants_require_executable_digest_update
BEFORE UPDATE ON policy_grants
WHEN NEW.executable_digest IS NULL
   OR length(trim(NEW.executable_digest)) = 0
BEGIN
    SELECT RAISE(ABORT, 'policy_grants require executable_digest');
END;

CREATE TRIGGER approvals_require_digest_and_one_use_insert
BEFORE INSERT ON approvals
WHEN NEW.allowed_uses <> 1
   OR json_extract(NEW.capability_json, '$.digest') IS NULL
   OR length(trim(json_extract(NEW.capability_json, '$.digest'))) = 0
BEGIN
    SELECT RAISE(ABORT, 'approvals require digest and allowed_uses = 1');
END;

CREATE TRIGGER approvals_require_digest_and_one_use_update
BEFORE UPDATE ON approvals
WHEN NEW.allowed_uses <> 1
   OR json_extract(NEW.capability_json, '$.digest') IS NULL
   OR length(trim(json_extract(NEW.capability_json, '$.digest'))) = 0
BEGIN
    SELECT RAISE(ABORT, 'approvals require digest and allowed_uses = 1');
END;

CREATE TRIGGER action_receipts_reconcile_effect_violation_insert
BEFORE INSERT ON action_receipts
WHEN NEW.effect_violation = 1
   AND NEW.result <> 'effect_unknown'
BEGIN
    SELECT RAISE(ABORT, 'effect_violation requires effect_unknown result');
END;

CREATE TRIGGER action_receipts_reconcile_effect_violation_update
BEFORE UPDATE ON action_receipts
WHEN NEW.effect_violation = 1
   AND NEW.result <> 'effect_unknown'
BEGIN
    SELECT RAISE(ABORT, 'effect_violation requires effect_unknown result');
END;

CREATE TRIGGER events_are_append_only_update
BEFORE UPDATE ON events
BEGIN
    SELECT RAISE(ABORT, 'events are append-only');
END;

CREATE TRIGGER events_are_append_only_delete
BEFORE DELETE ON events
BEGIN
    SELECT RAISE(ABORT, 'events are append-only');
END;

CREATE TRIGGER outbox_events_are_retain_only_delete
BEFORE DELETE ON outbox_events
BEGIN
    SELECT RAISE(ABORT, 'outbox events are retained');
END;

CREATE TRIGGER outbox_events_event_id_immutable
BEFORE UPDATE OF event_id ON outbox_events
BEGIN
    SELECT RAISE(ABORT, 'outbox event_id is immutable');
END;

CREATE INDEX idx_capability_registry_entries_capability
    ON capability_registry_entries(capability_id, capability_version);
CREATE INDEX idx_approval_consumptions_action ON approval_consumptions(action_id);
CREATE INDEX idx_approval_consumptions_event ON approval_consumptions(event_id);
"""

SCHEMA_V2_HASH = (
    "sha256:" + hashlib.sha256(SCHEMA_V2_SQL.encode("utf-8")).hexdigest()
)

SCHEMA_V3_SQL = r"""
DROP TRIGGER events_are_append_only_update;
DROP TRIGGER events_are_append_only_delete;
DROP TRIGGER outbox_events_are_retain_only_delete;
DROP TRIGGER outbox_events_event_id_immutable;

ALTER TABLE approval_consumptions RENAME TO approval_consumptions_v2;
ALTER TABLE outbox_events RENAME TO outbox_events_v2;
ALTER TABLE events RENAME TO events_v2;

CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    aggregate_type TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    aggregate_version INTEGER NOT NULL CHECK (aggregate_version >= 1),
    run_id TEXT REFERENCES runs(id) ON DELETE RESTRICT,
    run_seq INTEGER CHECK (run_seq IS NULL OR run_seq >= 1),
    action_id TEXT REFERENCES actions(id) ON DELETE RESTRICT,
    actor_json TEXT NOT NULL CHECK (json_valid(actor_json)),
    causation_id TEXT,
    correlation_id TEXT,
    type TEXT NOT NULL CHECK (
        type IN (
            'workspace.created',
            'project.created', 'project.status_changed',
            'inquiry.created', 'inquiry.status_changed',
            'plan.proposed', 'plan.revised', 'plan.status_changed',
            'run.created', 'run.started', 'run.heartbeat', 'run.paused',
            'run.cancelled', 'run.timed_out', 'run.failed', 'run.succeeded',
            'run.budget_exceeded', 'run.orphaned',
            'plan.step.started', 'plan.step.completed', 'plan.step.failed',
            'action.proposed', 'action.authorized', 'action.started',
            'action.output', 'action.completed', 'action.cancelled',
            'action.effect_unknown',
            'artifact.staged', 'artifact.committed', 'artifact.reconciled',
            'budget.updated', 'budget.threshold_reached',
            'policy_grant.created', 'policy_grant.revoked',
            'policy_grant.expired',
            'approval.requested', 'approval.decided', 'approval.expired',
            'resource.registered', 'locator.created', 'claim.created',
            'evidence.attached', 'hypothesis.created', 'finding.drafted',
            'relation.created', 'export.published'
        )
    ),
    payload_json TEXT CHECK (payload_json IS NULL OR json_valid(payload_json)),
    payload_artifact_id TEXT REFERENCES artifacts(id) ON DELETE RESTRICT,
    occurred_at TEXT NOT NULL,
    CHECK (
        (payload_json IS NOT NULL AND payload_artifact_id IS NULL)
        OR (payload_json IS NULL AND payload_artifact_id IS NOT NULL)
    ),
    CHECK (
        type <> 'artifact.staged'
        OR COALESCE((
            aggregate_type = 'artifact'
            AND payload_json IS NOT NULL
            AND json_type(payload_json, '$') = 'object'
            AND json_extract(payload_json, '$.artifact_id') = aggregate_id
            AND json_extract(payload_json, '$.state') = 'staged'
            AND json_type(payload_json, '$.temp_ref') = 'text'
            AND length(trim(json_extract(payload_json, '$.temp_ref'))) > 0
            AND json_type(payload_json, '$.blob_hash') = 'text'
            AND json_type(payload_json, '$.size') = 'integer'
            AND json_extract(payload_json, '$.size') >= 0
            AND json_type(payload_json, '$.media_type') = 'text'
            AND length(trim(json_extract(payload_json, '$.media_type'))) > 0
        ), 0)
    ),
    CHECK (
        type <> 'artifact.committed'
        OR COALESCE((
            aggregate_type = 'artifact'
            AND payload_json IS NOT NULL
            AND json_type(payload_json, '$') = 'object'
            AND json_extract(payload_json, '$.artifact_id') = aggregate_id
            AND json_extract(payload_json, '$.state') = 'available'
            AND json_type(payload_json, '$.blob_hash') = 'text'
            AND json_type(payload_json, '$.size') = 'integer'
            AND json_extract(payload_json, '$.size') >= 0
            AND json_type(payload_json, '$.media_type') = 'text'
            AND length(trim(json_extract(payload_json, '$.media_type'))) > 0
        ), 0)
    ),
    CHECK (
        type <> 'artifact.reconciled'
        OR COALESCE((
            aggregate_type = 'artifact'
            AND payload_json IS NOT NULL
            AND json_type(payload_json, '$') = 'object'
            AND json_extract(payload_json, '$.artifact_id') = aggregate_id
            AND json_type(payload_json, '$.previous_state') = 'text'
            AND json_type(payload_json, '$.state') = 'text'
            AND json_type(payload_json, '$.reason_code') = 'text'
            AND length(trim(json_extract(payload_json, '$.reason_code'))) > 0
        ), 0)
    ),
    CHECK (run_seq IS NULL OR run_id IS NOT NULL),
    UNIQUE (aggregate_type, aggregate_id, aggregate_version),
    UNIQUE (run_id, run_seq)
) STRICT;

INSERT INTO events (
    id, aggregate_type, aggregate_id, aggregate_version, run_id, run_seq,
    action_id, actor_json, causation_id, correlation_id, type, payload_json,
    payload_artifact_id, occurred_at
)
SELECT
    id, aggregate_type, aggregate_id, aggregate_version, run_id, run_seq,
    action_id, actor_json, causation_id, correlation_id, type, payload_json,
    payload_artifact_id, occurred_at
FROM events_v2;

CREATE TABLE outbox_events (
    event_id INTEGER PRIMARY KEY REFERENCES events(id) ON DELETE RESTRICT,
    dispatched_at TEXT,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0)
) STRICT;

INSERT INTO outbox_events(event_id, dispatched_at, attempts)
SELECT event_id, dispatched_at, attempts FROM outbox_events_v2;

CREATE TABLE approval_consumptions (
    approval_id TEXT PRIMARY KEY REFERENCES approvals(id) ON DELETE RESTRICT,
    action_id TEXT NOT NULL UNIQUE REFERENCES actions(id) ON DELETE RESTRICT,
    event_id INTEGER UNIQUE REFERENCES events(id) ON DELETE RESTRICT,
    consumed_at TEXT NOT NULL
) STRICT;

INSERT INTO approval_consumptions(approval_id, action_id, event_id, consumed_at)
SELECT approval_id, action_id, event_id, consumed_at
FROM approval_consumptions_v2;

DROP TABLE approval_consumptions_v2;
DROP TABLE outbox_events_v2;
DROP TABLE events_v2;

CREATE INDEX idx_events_aggregate
    ON events(aggregate_type, aggregate_id, aggregate_version);
CREATE INDEX idx_events_run ON events(run_id, run_seq);
CREATE INDEX idx_approval_consumptions_action ON approval_consumptions(action_id);
CREATE INDEX idx_approval_consumptions_event ON approval_consumptions(event_id);

CREATE TRIGGER events_are_append_only_update
BEFORE UPDATE ON events
BEGIN
    SELECT RAISE(ABORT, 'events are append-only');
END;

CREATE TRIGGER events_are_append_only_delete
BEFORE DELETE ON events
BEGIN
    SELECT RAISE(ABORT, 'events are append-only');
END;

CREATE TRIGGER outbox_events_are_retain_only_delete
BEFORE DELETE ON outbox_events
BEGIN
    SELECT RAISE(ABORT, 'outbox events are retained');
END;

CREATE TRIGGER outbox_events_event_id_immutable
BEFORE UPDATE OF event_id ON outbox_events
BEGIN
    SELECT RAISE(ABORT, 'outbox event_id is immutable');
END;
"""

SCHEMA_V3_HASH = (
    "sha256:" + hashlib.sha256(SCHEMA_V3_SQL.encode("utf-8")).hexdigest()
)

SCHEMA_V4_SQL = r"""
CREATE TEMP TABLE __d2_03a_registry_guard (
    value INTEGER NOT NULL CHECK (value = 0)
) STRICT;

INSERT INTO __d2_03a_registry_guard(value)
SELECT 1
WHERE EXISTS (
    SELECT 1 FROM capability_registry_entries
);

DROP TABLE __d2_03a_registry_guard;

DROP INDEX idx_capability_registry_entries_capability;

ALTER TABLE capability_registry_entries RENAME TO capability_registry_entries_v3;

CREATE TABLE capability_registry_entries (
    capability_id TEXT NOT NULL,
    capability_version TEXT NOT NULL,
    executable_digest TEXT NOT NULL,
    entry_json TEXT NOT NULL CHECK (json_valid(entry_json)),
    contract_digest TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (capability_id, capability_version, executable_digest),
    CHECK (json_extract(entry_json, '$.capability.id') = capability_id),
    CHECK (json_extract(entry_json, '$.capability.version') = capability_version),
    CHECK (json_extract(entry_json, '$.capability.digest') = executable_digest),
    CHECK (json_extract(entry_json, '$.contract_digest') = contract_digest),
    CHECK (json_type(entry_json, '$.read_roots') = 'array'),
    CHECK (json_type(entry_json, '$.write_roots') = 'array'),
    CHECK (json_type(entry_json, '$.network_targets') = 'array'),
    CHECK (json_type(entry_json, '$.network_methods') = 'array'),
    CHECK (json_type(entry_json, '$.env_keys') = 'array'),
    CHECK (json_type(entry_json, '$.process_targets') = 'array'),
    CHECK (json_type(entry_json, '$.default_effect') = 'text')
) STRICT;

INSERT INTO capability_registry_entries (
    capability_id, capability_version, executable_digest, entry_json,
    contract_digest, created_at
)
SELECT
    capability_id,
    capability_version,
    executable_digest,
    json_object(
        'capability', json_object(
            'id', capability_id,
            'version', capability_version,
            'digest', executable_digest
        ),
        'args_schema', json(args_schema_json),
        'risk_tier', risk_tier,
        'reversible', CASE reversible WHEN 1 THEN json('true') ELSE json('false') END,
        'authorization_mode', authorization_mode,
        'grantable', CASE grantable WHEN 1 THEN json('true') ELSE json('false') END,
        'provider_mode', provider_mode,
        'allowed_providers', json(allowed_providers_json),
        'read_roots', json('[]'),
        'write_roots', json('[]'),
        'network_targets', json('[]'),
        'network_methods', json('[]'),
        'env_keys', json('[]'),
        'process_targets', json('[]'),
        'timeout_seconds', NULL,
        'default_effect', 'effect_unknown',
        'contract_digest', contract_digest
    ),
    contract_digest,
    created_at
FROM capability_registry_entries_v3;

DROP TABLE capability_registry_entries_v3;

CREATE INDEX idx_capability_registry_entries_capability
    ON capability_registry_entries(capability_id, capability_version);
"""

SCHEMA_V4_HASH = (
    "sha256:" + hashlib.sha256(SCHEMA_V4_SQL.encode("utf-8")).hexdigest()
)

SCHEMA_V5_SQL = r"""
CREATE TABLE run_budget_ledger (
    run_id TEXT PRIMARY KEY REFERENCES runs(id) ON DELETE RESTRICT,
    limits_json TEXT NOT NULL CHECK (json_valid(limits_json)),
    usage_json TEXT NOT NULL CHECK (json_valid(usage_json)),
    started_actions INTEGER NOT NULL CHECK (started_actions >= 0),
    running_actions INTEGER NOT NULL CHECK (running_actions >= 0),
    exhausted INTEGER NOT NULL CHECK (exhausted IN (0, 1)),
    exhausted_reason TEXT,
    exhausted_at TEXT,
    updated_at TEXT NOT NULL,
    CHECK (
        (
            exhausted = 0
            AND exhausted_reason IS NULL
            AND exhausted_at IS NULL
        )
        OR (
            exhausted = 1
            AND exhausted_reason IS NOT NULL
            AND length(trim(exhausted_reason)) > 0
            AND exhausted_at IS NOT NULL
        )
    )
) STRICT;

CREATE INDEX idx_run_budget_ledger_exhausted
    ON run_budget_ledger(exhausted, run_id);
"""

SCHEMA_V5_HASH = (
    "sha256:" + hashlib.sha256(SCHEMA_V5_SQL.encode("utf-8")).hexdigest()
)

SCHEMA_V6_SQL = r"""
CREATE TEMP TABLE __d2_08_authorization_guard (
    value INTEGER NOT NULL CHECK (value = 0)
) STRICT;

INSERT INTO __d2_08_authorization_guard(value)
SELECT 1
WHERE EXISTS (
    SELECT 1
    FROM actions
    WHERE authorization_ref IS NOT NULL
       OR state IN (
           'authorized', 'running', 'succeeded', 'failed', 'cancelled',
           'timed_out', 'effect_unknown'
       )
);

DROP TABLE __d2_08_authorization_guard;

CREATE TABLE action_authorizations (
    action_id TEXT PRIMARY KEY REFERENCES actions(id) ON DELETE RESTRICT,
    action_hash TEXT NOT NULL,
    material_json TEXT NOT NULL CHECK (json_valid(material_json)),
    registry_contract_digest TEXT NOT NULL,
    authorization_source TEXT NOT NULL CHECK (
        authorization_source IN ('policy_grant', 'approval')
    ),
    authorization_ref TEXT NOT NULL,
    authorization_event_id INTEGER NOT NULL UNIQUE
        REFERENCES events(id) ON DELETE RESTRICT,
    authorized_at TEXT NOT NULL,
    CHECK (json_extract(material_json, '$.args_hash') IS NOT NULL),
    CHECK (json_extract(material_json, '$.capability.digest') IS NOT NULL),
    CHECK (json_extract(material_json, '$.budget') IS NOT NULL),
    CHECK (json_extract(material_json, '$.requested_effects') IS NOT NULL)
) STRICT;

CREATE TRIGGER action_authorizations_are_append_only_update
BEFORE UPDATE ON action_authorizations
BEGIN
    SELECT RAISE(ABORT, 'action authorizations are append-only');
END;

CREATE TRIGGER action_authorizations_are_append_only_delete
BEFORE DELETE ON action_authorizations
BEGIN
    SELECT RAISE(ABORT, 'action authorizations are append-only');
END;

CREATE TRIGGER authorized_action_material_is_immutable
BEFORE UPDATE OF
    capability_id, capability_version, executable_digest, args_artifact_id,
    args_hash, action_hash, risk_tier, requested_effects_json,
    policy_decision, authorization_ref
ON actions
WHEN EXISTS (
    SELECT 1 FROM action_authorizations
    WHERE action_id = OLD.id
)
BEGIN
    SELECT RAISE(ABORT, 'authorized action material is immutable');
END;

CREATE INDEX idx_action_authorizations_ref
    ON action_authorizations(authorization_source, authorization_ref);
"""

SCHEMA_V6_HASH = (
    "sha256:" + hashlib.sha256(SCHEMA_V6_SQL.encode("utf-8")).hexdigest()
)

SCHEMA_V7_SQL = r"""
CREATE TEMP TABLE __d3_07_approval_guard (
    value INTEGER NOT NULL CHECK (value = 0)
) STRICT;

INSERT INTO __d3_07_approval_guard(value)
SELECT 1
WHERE EXISTS (
    SELECT subject_id
    FROM approvals
    WHERE subject_type = 'action'
    GROUP BY subject_id
    HAVING COUNT(*) > 1
);

DROP TABLE __d3_07_approval_guard;

CREATE UNIQUE INDEX idx_approvals_one_per_action
    ON approvals(subject_id)
    WHERE subject_type = 'action';

CREATE TRIGGER approvals_subject_is_immutable
BEFORE UPDATE OF
    subject_type, subject_id, subject_hash, capability_json,
    parameter_summary_json, requested_effects_json, data_class, provider,
    budget_json, risk_tier, reversible, allowed_uses, expires_at
ON approvals
BEGIN
    SELECT RAISE(ABORT, 'approval subject is immutable');
END;

CREATE TRIGGER approvals_decide_once
BEFORE UPDATE OF decision, decided_by_json, decided_at
ON approvals
WHEN OLD.decision <> 'requested'
   OR NEW.decision = 'requested'
BEGIN
    SELECT RAISE(ABORT, 'approval decision is terminal');
END;

CREATE TRIGGER approval_consumptions_are_append_only_update
BEFORE UPDATE ON approval_consumptions
BEGIN
    SELECT RAISE(ABORT, 'approval consumptions are append-only');
END;

CREATE TRIGGER approval_consumptions_are_append_only_delete
BEFORE DELETE ON approval_consumptions
BEGIN
    SELECT RAISE(ABORT, 'approval consumptions are append-only');
END;

CREATE TABLE external_write_fences (
    action_id TEXT PRIMARY KEY REFERENCES actions(id) ON DELETE RESTRICT,
    selection_identity_digest TEXT NOT NULL,
    target_commitment TEXT NOT NULL,
    event_id INTEGER NOT NULL UNIQUE REFERENCES events(id) ON DELETE RESTRICT,
    committed_at TEXT NOT NULL
) STRICT;

CREATE TRIGGER external_write_fences_are_append_only_update
BEFORE UPDATE ON external_write_fences
BEGIN
    SELECT RAISE(ABORT, 'external write fences are append-only');
END;

CREATE TRIGGER external_write_fences_are_append_only_delete
BEFORE DELETE ON external_write_fences
BEGIN
    SELECT RAISE(ABORT, 'external write fences are append-only');
END;
"""

SCHEMA_V7_HASH = (
    "sha256:" + hashlib.sha256(SCHEMA_V7_SQL.encode("utf-8")).hexdigest()
)
