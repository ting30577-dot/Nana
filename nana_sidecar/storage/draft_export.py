"""D3-07 one-time Approval and controlled fixed-local draft export."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from pydantic import Field

from nana_sidecar.contracts.authorization import (
    ActionHashMaterial,
    canonical_json_bytes,
    canonical_json_hash,
    compute_action_hash,
)
from nana_sidecar.contracts.builtin_capabilities import (
    DRAFT_EXPORT_FILENAME,
    DRAFT_EXPORT_MAX_BYTES,
    DRAFT_EXPORT_MEDIA_TYPE,
    EXPORT_DRAFT_EXTERNAL_CAPABILITY,
    export_draft_external_registry_entry,
)
from nana_sidecar.contracts.commands import (
    CommandBase,
    CommandResult,
    CommandStatus,
    DecideApproval,
)
from nana_sidecar.contracts.common import (
    ActorRef,
    BudgetSnapshot,
    DataClass,
    EffectScope,
    ResourceUsage,
    RiskTier,
)
from nana_sidecar.contracts.errors import ErrorCategory, ErrorCode, StructuredError
from nana_sidecar.contracts.journey import (
    DecideApprovalRequest,
    RequestApprovalRequest,
)
from nana_sidecar.export_selection import (
    ExportSelectionError,
    ExportSelectionRegistry,
)
from nana_sidecar.storage.admission import (
    AdmissionStateError,
    CapabilityAdmissionService,
)
from nana_sidecar.storage.artifact_commits import ArtifactCommitService, ArtifactReader
from nana_sidecar.storage.artifact_reconciliation import ArtifactReconciler
from nana_sidecar.storage.artifacts import ArtifactStore
from nana_sidecar.storage.budget_accounting import BudgetAccountingService
from nana_sidecar.storage.command_transactions import (
    CommandExecutionError,
    CommandTransactionService,
)


_PREPARE_NAMESPACE = "nana:d3:export:prepare:v1"
_RENDERER_MATERIAL = "nana:d3:draft-report-renderer:v1:utf8-nfc-lf:public-only"
DRAFT_REPORT_RENDERER_DIGEST = (
    "sha256:" + hashlib.sha256(_RENDERER_MATERIAL.encode("utf-8")).hexdigest()
)

# Fixed detection strings only; values are never interpolated or logged.
EXPORT_CREDENTIAL_CANARIES = (
    "sk-", "sk_live_", "sk_test_", "rk_live_", "rk_test_",
    "AKIA", "ASIA", "A3T", "AIza", "ya29.",
    "ghp_", "gho_", "ghu_", "ghs_", "github_pat_",
    "xoxb-", "xoxp-", "xoxa-", "xoxr-", "xapp-",
    "-----BEGIN PRIVATE KEY-----", "-----BEGIN RSA PRIVATE KEY-----",
    "-----BEGIN OPENSSH PRIVATE KEY-----", "Bearer ", "Basic ",
    "password=", "passwd=", "secret=", "token=", "api_key=",
    "apikey=", "client_secret=", "access_token=", "refresh_token=",
    "sessionid=", "aws_access_key_id", "aws_secret_access_key",
    "AZURE_CLIENT_SECRET", "GOOGLE_APPLICATION_CREDENTIALS", "DATABASE_URL=",
    "postgres://", "mysql://", "mongodb://", "redis://", "amqp://",
    "ssh-rsa ", "ssh-ed25519 ", "BEGIN PGP PRIVATE KEY", "private_key_id",
    "authorization:",
)
if len(EXPORT_CREDENTIAL_CANARIES) != 50:  # pragma: no cover - import invariant
    raise RuntimeError("the D3 export credential canary set must contain 50 entries")


def _json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _directory_entries(path: Path) -> tuple[os.DirEntry[str], ...]:
    with os.scandir(path) as entries:
        return tuple(entries)


def _raise_unreachable() -> CommandResult:
    raise RuntimeError("stored draft-export command unexpectedly entered apply")


class DraftExportError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class _PrepareDraftExportCommand(CommandBase):
    type: Literal["RequestApproval"] = "RequestApproval"
    finding_id: UUID
    target_selection_id: str = Field(min_length=43, max_length=64)


@dataclass(frozen=True, slots=True)
class _PreparedSubject:
    run_id: str
    action_id: str
    approval_id: str
    draft_artifact_id: str
    args_artifact_id: str
    source_artifact_id: str
    source_run_id: str
    finding_id: str
    inquiry_id: str
    project_id: str
    finding_revision: int
    draft_bytes: bytes
    draft_hash: str
    args: dict[str, object]
    args_hash: str
    action_hash: str
    material: ActionHashMaterial
    selection_identity_digest: str
    target_commitment: str
    expires_at: str
    snapshot: dict[str, object]


@dataclass(frozen=True, slots=True)
class _WriteOutcome:
    result: Literal["succeeded", "failed", "effect_unknown"]
    actual_effects: EffectScope
    wall_clock_ms: int
    output_bytes: int
    detail: str


def _safe_public_text(value: str, *, field_name: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    normalized = " ".join(normalized.split())
    if not normalized or len(normalized) > 8000:
        raise DraftExportError("E_RENDER_INPUT", f"{field_name} is invalid")
    if any(ord(character) < 32 or ord(character) == 127 for character in normalized):
        raise DraftExportError("E_RENDER_INPUT", f"{field_name} contains controls")
    if re.search(r"(?i)(?:https?://|file:|[A-Z]:[\\/]|\\\\|/(?:home|users|etc|var)/)", normalized):
        raise DraftExportError("E_RENDER_PRIVATE", f"{field_name} contains a forbidden locator")
    if any(character in normalized for character in "<>[]{}*_#`|"):
        raise DraftExportError("E_RENDER_MARKUP", f"{field_name} contains markup")
    return normalized


def render_draft_report(
    *,
    inquiry_question: str,
    finding_statement: str,
    confidence_basis: str,
    algorithm_run_id: str,
    source_artifact_hash: str,
) -> bytes:
    """Render the frozen public-only D3 Markdown report."""

    question = _safe_public_text(inquiry_question, field_name="inquiry question")
    finding = _safe_public_text(finding_statement, field_name="finding statement")
    confidence = _safe_public_text(confidence_basis, field_name="confidence basis")
    report = (
        "# Nana D3 Draft Report\n\n"
        "> DRAFT — local review copy; not published.\n\n"
        "## Inquiry\n\n"
        f"{question}\n\n"
        "## Finding\n\n"
        f"{finding}\n\n"
        "## Confidence basis\n\n"
        f"{confidence}\n\n"
        "## Execution evidence\n\n"
        f"- Algorithm Run: `{algorithm_run_id}`\n"
        "- Run result: `succeeded`\n"
        "- Action Receipt: `succeeded`\n"
        f"- Source Artifact hash: `{source_artifact_hash}`\n\n"
        "## Scope\n\n"
        "This deterministic draft contains canonical public facts only.\n"
    )
    report = unicodedata.normalize("NFC", report).replace("\r\n", "\n").replace("\r", "\n")
    report = report.rstrip("\n") + "\n"
    encoded = report.encode("utf-8")
    if len(encoded) > DRAFT_EXPORT_MAX_BYTES:
        raise DraftExportError("E_RENDER_SIZE", "draft report exceeds its fixed size ceiling")
    lowered = report.casefold()
    matches = tuple(
        canary
        for canary in EXPORT_CREDENTIAL_CANARIES
        if canary.strip().casefold() in lowered
    )
    if matches:
        raise DraftExportError("E_RENDER_CANARY", "draft report matched a credential canary")
    return encoded


class DraftExportService:
    """Compose, approve, execute and reconcile the exact D3 T3 export."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        actor: ActorRef,
        selections: ExportSelectionRegistry,
        now: Callable[[], str],
        new_id: Callable[[], UUID] = uuid4,
        checkpoint: Callable[[str], None] | None = None,
    ) -> None:
        if actor.kind.value != "user" or actor.id is None:
            raise ValueError("draft export requires a stable user actor")
        self.connection = connection
        self.actor = actor
        self.selections = selections
        self._now = now
        self._new_id = new_id
        self._checkpoint = checkpoint or (lambda _name: None)
        self._transactions = CommandTransactionService(
            connection,
            now=now,
            checkpoint=checkpoint,
        )

    def prepare(self, request: RequestApprovalRequest) -> CommandResult:
        command = _PrepareDraftExportCommand(
            command_id=request.command_id,
            expected_revision=request.expected_revision,
            actor=self.actor,
            finding_id=request.finding_id,
            target_selection_id=request.target_selection_id,
        )
        request_hash = self._transactions._request_hash(command)
        existing = self.connection.execute(
            "SELECT 1 FROM command_log WHERE command_id = ?",
            (str(command.command_id),),
        ).fetchone()
        if existing is not None:
            return self._transactions.execute_transactional(
                command,
                apply=lambda _command, _hash: (_raise_unreachable(), None),
                validate_result=self._validate_prepare_result,
                validate_rejection=self._validate_rejection,
            )
        run_id = str(uuid5(NAMESPACE_URL, f"{_PREPARE_NAMESPACE}:run:{command.command_id}"))
        action_id = str(uuid5(NAMESPACE_URL, f"{_PREPARE_NAMESPACE}:action:{command.command_id}"))
        self.selections.reserve(
            request.target_selection_id,
            actor_id=str(self.actor.id),
            command_id=str(command.command_id),
            request_hash=request_hash,
            run_id=run_id,
            action_id=action_id,
        )
        try:
            prepared = self._prepare_subject(command, run_id=run_id, action_id=action_id)
            result = self._transactions.execute_transactional(
                command,
                apply=lambda current, current_hash: self._apply_prepare(
                    current,
                    current_hash,
                    prepared,
                ),
                validate_result=self._validate_prepare_result,
                validate_rejection=self._validate_rejection,
            )
        except BaseException:
            accepted = self.connection.execute(
                "SELECT state FROM command_log WHERE command_id = ?",
                (str(command.command_id),),
            ).fetchone()
            if accepted is not None and str(accepted["state"]) == "accepted":
                self.selections.finalize(
                    request.target_selection_id,
                    command_id=str(command.command_id),
                )
            else:
                self.selections.release(
                    request.target_selection_id,
                    command_id=str(command.command_id),
                )
            raise
        self.selections.finalize(
            request.target_selection_id,
            command_id=str(command.command_id),
        )
        return result

    def decide(self, request: DecideApprovalRequest) -> CommandResult:
        command = DecideApproval(
            type="DecideApproval",
            command_id=request.command_id,
            expected_revision=request.expected_revision,
            actor=self.actor,
            approval_id=request.approval_id,
            subject_hash=request.subject_hash,
            decision=request.decision,
        )
        try:
            result = self._transactions.execute_transactional(
                command,
                apply=self._apply_decision,
                validate_result=self._validate_decision_result,
                validate_rejection=self._validate_rejection,
            )
        except CommandExecutionError:
            terminal = self.connection.execute(
                "SELECT decision FROM approvals WHERE id = ?",
                (str(request.approval_id),),
            ).fetchone()
            if terminal is not None and str(terminal["decision"]) == "expired":
                self.converge_denied_or_expired(str(request.approval_id))
            raise
        if request.decision == "denied":
            self.converge_denied_or_expired(str(request.approval_id))
        return result

    def _prepare_subject(
        self,
        command: _PrepareDraftExportCommand,
        *,
        run_id: str,
        action_id: str,
    ) -> _PreparedSubject:
        selection = self.selections.bound_for_action(action_id, actor_id=str(self.actor.id)) if self._selection_is_bound(action_id) else self.selections.reserve(
            command.target_selection_id,
            actor_id=str(self.actor.id),
            command_id=str(command.command_id),
            request_hash=self._transactions._request_hash(command),
            run_id=run_id,
            action_id=action_id,
        )
        source = self._load_source(str(command.finding_id), int(command.expected_revision or 0))
        draft_bytes = render_draft_report(
            inquiry_question=str(source["question"]),
            finding_statement=str(source["statement"]),
            confidence_basis=str(source["confidence_basis"]),
            algorithm_run_id=str(source["source_run_id"]),
            source_artifact_hash=str(source["source_artifact_hash"]),
        )
        draft_hash = "sha256:" + hashlib.sha256(draft_bytes).hexdigest()
        draft_artifact_id = str(
            uuid5(
                NAMESPACE_URL,
                f"{_PREPARE_NAMESPACE}:draft:{run_id}:{draft_hash}",
            )
        )
        args = {
            "draft_artifact_id": draft_artifact_id,
            "draft_hash": draft_hash,
            "renderer_digest": DRAFT_REPORT_RENDERER_DIGEST,
            "selection_identity_digest": selection.identity_digest,
            "target_commitment": selection.target_commitment,
            "filename": DRAFT_EXPORT_FILENAME,
            "media_type": DRAFT_EXPORT_MEDIA_TYPE,
            "size": len(draft_bytes),
        }
        args_bytes = canonical_json_bytes(args)
        args_hash = canonical_json_hash(args)
        args_artifact_id = str(uuid5(NAMESPACE_URL, f"{_PREPARE_NAMESPACE}:args:{args_hash}"))
        self._ensure_artifact(
            draft_artifact_id,
            draft_bytes,
            DRAFT_EXPORT_MEDIA_TYPE,
            retention={"kind": "d3_public_draft_report", "renderer": DRAFT_REPORT_RENDERER_DIGEST},
        )
        self._ensure_artifact(
            args_artifact_id,
            args_bytes,
            "application/json",
            retention={"kind": "d3_export_action_args"},
        )
        budget = self._export_budget()
        effects = EffectScope(
            reads=("workspace:canonical_public_draft",),
            writes=("external:fixed_local_draft_target",),
        )
        material = ActionHashMaterial(
            capability=EXPORT_DRAFT_EXTERNAL_CAPABILITY,
            args=args,
            args_hash=args_hash,
            data_class=DataClass.PUBLIC,
            requested_effects=effects,
            budget=budget,
            risk_tier=RiskTier.T3,
            reversible=False,
        )
        action_hash = compute_action_hash(material)
        approval_id = str(uuid5(NAMESPACE_URL, f"{_PREPARE_NAMESPACE}:approval:{action_id}"))
        snapshot = {
            "kind": "draft_export_v1",
            "finding_id": str(command.finding_id),
            "finding_revision": int(command.expected_revision or 0),
            "source_run_id": str(source["source_run_id"]),
            "source_artifact_id": str(source["source_artifact_id"]),
            "source_artifact_hash": str(source["source_artifact_hash"]),
            "draft_artifact_id": draft_artifact_id,
            "draft_hash": draft_hash,
            "renderer_digest": DRAFT_REPORT_RENDERER_DIGEST,
            "capability_digest": EXPORT_DRAFT_EXTERNAL_CAPABILITY.digest,
            "selection_identity_digest": selection.identity_digest,
            "target_commitment": selection.target_commitment,
            "media_type": DRAFT_EXPORT_MEDIA_TYPE,
            "size": len(draft_bytes),
            "budget": budget.model_dump(mode="json"),
            "data_class": "public",
        }
        return _PreparedSubject(
            run_id=run_id,
            action_id=action_id,
            approval_id=approval_id,
            draft_artifact_id=draft_artifact_id,
            args_artifact_id=args_artifact_id,
            source_artifact_id=str(source["source_artifact_id"]),
            source_run_id=str(source["source_run_id"]),
            finding_id=str(command.finding_id),
            inquiry_id=str(source["inquiry_id"]),
            project_id=str(source["project_id"]),
            finding_revision=int(command.expected_revision or 0),
            draft_bytes=draft_bytes,
            draft_hash=draft_hash,
            args=args,
            args_hash=args_hash,
            action_hash=action_hash,
            material=material,
            selection_identity_digest=selection.identity_digest,
            target_commitment=selection.target_commitment,
            expires_at=selection.expires_at.isoformat().replace("+00:00", "Z"),
            snapshot=snapshot,
        )

    def _apply_prepare(
        self,
        command: CommandBase,
        request_hash: str,
        prepared: _PreparedSubject,
    ) -> tuple[CommandResult | None, StructuredError | None]:
        if not isinstance(command, _PrepareDraftExportCommand):
            raise TypeError("draft export prepare received another command")
        try:
            selection = self.selections.bound_for_action(
                prepared.action_id,
                actor_id=str(self.actor.id),
            ) if self._selection_is_bound(prepared.action_id) else self.selections.reserve(
                command.target_selection_id,
                actor_id=str(self.actor.id),
                command_id=str(command.command_id),
                request_hash=request_hash,
                run_id=prepared.run_id,
                action_id=prepared.action_id,
            )
            if (
                selection.identity_digest != prepared.selection_identity_digest
                or selection.target_commitment != prepared.target_commitment
            ):
                raise ExportSelectionError("E_SELECTION_CHANGED", "selection commitment changed")
            self._load_source(prepared.finding_id, prepared.finding_revision)
            self._verify_artifact(prepared.draft_artifact_id, prepared.draft_bytes)
            self._verify_artifact(prepared.args_artifact_id, canonical_json_bytes(prepared.args))
        except (DraftExportError, ExportSelectionError) as exc:
            return None, self._error(command, request_hash, exc.code, str(exc))

        now = self._now()
        entry = export_draft_external_registry_entry()
        self.connection.execute(
            "INSERT OR IGNORE INTO capability_registry_entries "
            "(capability_id, capability_version, executable_digest, entry_json, contract_digest, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                entry.capability.id,
                entry.capability.version,
                entry.capability.digest,
                entry.model_dump_json(),
                entry.contract_digest,
                now,
            ),
        )
        persisted_entry = self.connection.execute(
            "SELECT entry_json, contract_digest FROM capability_registry_entries "
            "WHERE capability_id = ? AND capability_version = ? AND executable_digest = ?",
            (
                entry.capability.id,
                entry.capability.version,
                entry.capability.digest,
            ),
        ).fetchone()
        if (
            persisted_entry is None
            or str(persisted_entry["entry_json"]) != entry.model_dump_json()
            or str(persisted_entry["contract_digest"]) != entry.contract_digest
        ):
            raise DraftExportError(
                "E_CAPABILITY_REGISTRY_MISMATCH",
                "persisted draft-export capability contract is not exact",
            )
        self.connection.execute(
            "INSERT INTO runs(id, project_id, inquiry_id, state, snapshot_json, created_at) "
            "VALUES (?, ?, ?, 'running', ?, ?)",
            (prepared.run_id, prepared.project_id, prepared.inquiry_id, _json(prepared.snapshot), now),
        )
        self.connection.execute(
            "UPDATE artifacts SET producer_run_id = ? WHERE id = ? AND producer_run_id IS NULL",
            (prepared.run_id, prepared.draft_artifact_id),
        )
        if self.connection.execute(
            "SELECT producer_run_id FROM artifacts WHERE id = ?",
            (prepared.draft_artifact_id,),
        ).fetchone()[0] != prepared.run_id:
            raise DraftExportError("E_DRAFT_PRODUCER", "draft Artifact producer binding failed")
        self.connection.execute(
            "INSERT INTO actions(id, run_id, plan_step_id, capability_id, capability_version, executable_digest, "
            "args_artifact_id, args_hash, action_hash, risk_tier, requested_effects_json, policy_decision, authorization_ref, state) "
            "VALUES (?, ?, 'step-export-draft', ?, ?, ?, ?, ?, ?, 'T3', ?, 'approval_required', NULL, 'waiting_approval')",
            (
                prepared.action_id,
                prepared.run_id,
                EXPORT_DRAFT_EXTERNAL_CAPABILITY.id,
                EXPORT_DRAFT_EXTERNAL_CAPABILITY.version,
                EXPORT_DRAFT_EXTERNAL_CAPABILITY.digest,
                prepared.args_artifact_id,
                prepared.args_hash,
                prepared.action_hash,
                _json(prepared.material.requested_effects.model_dump(mode="json")),
            ),
        )
        self.connection.execute(
            "INSERT INTO approvals(id, subject_type, subject_id, subject_hash, capability_json, parameter_summary_json, "
            "requested_effects_json, data_class, provider, budget_json, risk_tier, reversible, allowed_uses, expires_at, decision) "
            "VALUES (?, 'action', ?, ?, ?, ?, ?, 'public', NULL, ?, 'T3', 0, 1, ?, 'requested')",
            (
                prepared.approval_id,
                prepared.action_id,
                prepared.action_hash,
                _json(EXPORT_DRAFT_EXTERNAL_CAPABILITY.model_dump(mode="json")),
                _json({
                    "draft_hash": prepared.draft_hash,
                    "renderer_digest": DRAFT_REPORT_RENDERER_DIGEST,
                    "selection_identity_digest": prepared.selection_identity_digest,
                    "target_commitment": prepared.target_commitment,
                    "filename": DRAFT_EXPORT_FILENAME,
                    "media_type": DRAFT_EXPORT_MEDIA_TYPE,
                    "size": len(prepared.draft_bytes),
                }),
                _json(prepared.material.requested_effects.model_dump(mode="json")),
                _json(prepared.material.budget.model_dump(mode="json")),
                prepared.expires_at,
            ),
        )
        relation_ids = self._insert_export_relations(prepared, now)
        run_event = self._event(
            "run", prepared.run_id, prepared.run_id, None, "run.created",
            {"state": "running", "kind": "draft_export", "finding_id": prepared.finding_id},
            self.actor, str(command.command_id), now,
        )
        action_event = self._event(
            "action", prepared.action_id, prepared.run_id, prepared.action_id, "action.proposed",
            {"state": "waiting_approval", "action_hash": prepared.action_hash, "capability": EXPORT_DRAFT_EXTERNAL_CAPABILITY.model_dump(mode="json")},
            self.actor, str(command.command_id), now,
        )
        approval_event = self._event(
            "approval", prepared.approval_id, prepared.run_id, prepared.action_id, "approval.requested",
            {"decision": "requested", "subject_type": "action", "subject_id": prepared.action_id, "subject_hash": prepared.action_hash, "expires_at": prepared.expires_at},
            self.actor, str(command.command_id), now,
        )
        relation_payloads = (
            {
                "relation_type": "run_produces_artifact",
                "source_id": prepared.run_id,
                "target_id": prepared.draft_artifact_id,
                "status": "active",
            },
            {
                "relation_type": "artifact_derived_from_artifact",
                "source_id": prepared.draft_artifact_id,
                "target_id": prepared.source_artifact_id,
                "status": "active",
            },
        )
        relation_events = tuple(
            self._event(
                "relation", relation_id, prepared.run_id, prepared.action_id, "relation.created",
                payload, self.actor, str(command.command_id), now,
            )
            for relation_id, payload in zip(relation_ids, relation_payloads, strict=True)
        )
        events = (run_event, action_event, approval_event, *relation_events)
        return CommandResult(
            command_id=command.command_id,
            status=CommandStatus.ACCEPTED,
            affected_revisions={
                f"run:{prepared.run_id}": 1,
                f"action:{prepared.action_id}": 1,
                f"approval:{prepared.approval_id}": 1,
                **{f"relation:{relation_id}": 1 for relation_id in relation_ids},
            },
            event_ids=events,
        ), None

    def _apply_decision(
        self,
        command: CommandBase,
        request_hash: str,
    ) -> tuple[CommandResult | None, StructuredError | None]:
        if not isinstance(command, DecideApproval):
            raise TypeError("Approval decision received another command")
        row = self.connection.execute(
            "SELECT * FROM approvals WHERE id = ?",
            (str(command.approval_id),),
        ).fetchone()
        if row is None:
            return None, self._error(command, request_hash, "E_APPROVAL_INVALID", "Approval does not exist")
        version = self._aggregate_version("approval", str(command.approval_id))
        if command.expected_revision != version:
            return None, self._error(command, request_hash, "E_REVISION_CONFLICT", "Approval revision changed", retryable=True)
        if str(row["subject_hash"]) != command.subject_hash:
            return None, self._error(command, request_hash, "E_ACTION_HASH_MISMATCH", "Approval subject changed")
        if str(row["decision"]) != "requested":
            return None, self._error(command, request_hash, "E_APPROVAL_INVALID", "Approval is already terminal")
        if _utc(self._now()) >= _utc(str(row["expires_at"])):
            now = self._now()
            self.connection.execute(
                "UPDATE approvals SET decision = 'expired', decided_by_json = ?, decided_at = ? "
                "WHERE id = ? AND decision = 'requested'",
                (
                    _json({"kind": "system", "id": "d3-export-expiry"}),
                    now,
                    str(command.approval_id),
                ),
            )
            self._event(
                "approval",
                str(command.approval_id),
                self._action_run_id(str(row["subject_id"])),
                str(row["subject_id"]),
                "approval.expired",
                {"decision": "expired"},
                ActorRef(kind="system", id="d3-export-expiry"),
                str(command.command_id),
                now,
            )
            return None, self._error(command, request_hash, "E_APPROVAL_EXPIRED", "Approval expired")
        action_id = str(row["subject_id"])
        material = self._load_action_material(action_id)
        if compute_action_hash(material) != command.subject_hash:
            return None, self._error(command, request_hash, "E_ACTION_HASH_MISMATCH", "Action material changed")
        if command.decision == "approved":
            try:
                selection = self.selections.bound_for_action(action_id, actor_id=str(self.actor.id))
            except ExportSelectionError as exc:
                return None, self._error(command, request_hash, exc.code, str(exc))
            if (
                material.args.get("selection_identity_digest") != selection.identity_digest
                or material.args.get("target_commitment") != selection.target_commitment
            ):
                return None, self._error(command, request_hash, "E_SELECTION_CHANGED", "selection commitment changed")
        now = self._now()
        updated = self.connection.execute(
            "UPDATE approvals SET decision = ?, decided_by_json = ?, decided_at = ? "
            "WHERE id = ? AND decision = 'requested'",
            (command.decision, _json(self.actor.model_dump(mode="json")), now, str(command.approval_id)),
        )
        if updated.rowcount != 1:
            return None, self._error(command, request_hash, "E_APPROVAL_INVALID", "Approval changed concurrently")
        approval_event = self._event(
            "approval", str(command.approval_id), self._action_run_id(action_id), action_id,
            "approval.decided", {"decision": command.decision, "subject_hash": command.subject_hash},
            self.actor, str(command.command_id), now,
        )
        event_ids = [approval_event]
        affected = {f"approval:{command.approval_id}": version + 1}
        if command.decision == "approved":
            admission = CapabilityAdmissionService(
                self.connection,
                now=self._now,
                load_args_artifact=lambda artifact: ArtifactReader(
                    self.connection,
                    self._artifact_store(),
                ).read_bytes(str(artifact["id"])),
            )
            try:
                authorized = admission._authorize_with_approval_in_transaction(
                    action_id=action_id,
                    approval_id=str(command.approval_id),
                    material=material,
                    actor=self.actor,
                    causation_id=str(command.command_id),
                )
            except AdmissionStateError as exc:
                raise DraftExportError(exc.code, str(exc)) from exc
            event_ids.extend(authorized.event_ids)
            affected[f"action:{action_id}"] = self._aggregate_version("action", action_id)
        return CommandResult(
            command_id=command.command_id,
            status=CommandStatus.ACCEPTED,
            affected_revisions=affected,
            event_ids=tuple(event_ids),
        ), None

    def execute_authorized(self, approval_id: str) -> None:
        row = self.connection.execute(
            "SELECT subject_id, decision FROM approvals WHERE id = ?",
            (approval_id,),
        ).fetchone()
        if row is None or str(row["decision"]) != "approved":
            return
        action_id = str(row["subject_id"])
        action = self.connection.execute(
            "SELECT run_id, state FROM actions WHERE id = ?",
            (action_id,),
        ).fetchone()
        if action is None or str(action["state"]) in {"succeeded", "failed", "effect_unknown"}:
            self.selections.close_action(action_id)
            return
        run_id = str(action["run_id"])
        material = self._load_durable_authorization(action_id)
        try:
            self._claim_action(run_id, action_id)
            selection = self.selections.bound_for_action(action_id, actor_id=str(self.actor.id))
            self._verify_frozen_subject(run_id, material)
            draft = ArtifactReader(self.connection, self._artifact_store()).read_bytes(str(material.args["draft_artifact_id"]))
            if "sha256:" + hashlib.sha256(draft).hexdigest() != material.args["draft_hash"]:
                raise DraftExportError("E_DRAFT_HASH", "draft Artifact changed after approval")
            selection = self.selections.bound_for_action(action_id, actor_id=str(self.actor.id))
            self._commit_first_write_fence(action_id, run_id, selection.identity_digest, selection.target_commitment)
            outcome = self._write_external(action_id, selection.raw_path, draft)
            self._checkpoint("external_write_completed")
        except BaseException as exc:
            fenced = self.connection.execute(
                "SELECT 1 FROM external_write_fences WHERE action_id = ?",
                (action_id,),
            ).fetchone() is not None
            outcome = _WriteOutcome(
                result="effect_unknown" if fenced else "failed",
                actual_effects=(
                    EffectScope(writes=("external:fixed_local_draft_target",))
                    if fenced
                    else EffectScope()
                ),
                wall_clock_ms=0,
                output_bytes=0,
                detail="post-fence execution uncertainty" if fenced else "pre-fence execution failure",
            )
            self._settle(run_id, action_id, approval_id, material, outcome)
            self.selections.close_action(action_id)
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            return
        self._settle(run_id, action_id, approval_id, material, outcome)
        self.selections.close_action(action_id)

    def reconcile_startup(self) -> int:
        """Fail closed for process-local selection loss across restarts."""

        rows = self.connection.execute(
            "SELECT approvals.id, approvals.decision, approvals.subject_id, actions.state "
            "FROM approvals JOIN actions ON actions.id = approvals.subject_id "
            "WHERE approvals.subject_type = 'action' AND actions.capability_id = ? "
            "ORDER BY approvals.id",
            (EXPORT_DRAFT_EXTERNAL_CAPABILITY.id,),
        ).fetchall()
        changed = 0
        for row in rows:
            approval_id = str(row["id"])
            action_id = str(row["subject_id"])
            state = str(row["state"])
            decision = str(row["decision"])
            if state in {"succeeded", "failed", "cancelled", "effect_unknown"}:
                continue
            if decision == "requested":
                self._expire_approval(approval_id, action_id)
                self.converge_denied_or_expired(approval_id)
                changed += 1
            elif decision in {"denied", "expired"}:
                self.converge_denied_or_expired(approval_id)
                changed += 1
            elif decision == "approved":
                material = self._load_durable_authorization(action_id)
                run_id = self._action_run_id(action_id)
                fenced = self.connection.execute(
                    "SELECT 1 FROM external_write_fences WHERE action_id = ?",
                    (action_id,),
                ).fetchone() is not None
                if state == "authorized":
                    self._claim_action(run_id, action_id)
                outcome = _WriteOutcome(
                    result="effect_unknown" if fenced else "failed",
                    actual_effects=EffectScope(),
                    wall_clock_ms=0,
                    output_bytes=0,
                    detail="restart after durable write fence" if fenced else "restart proved no external write fence",
                )
                self._settle(run_id, action_id, approval_id, material, outcome)
                changed += 1
        return changed

    def converge_denied_or_expired(self, approval_id: str) -> None:
        row = self.connection.execute(
            "SELECT approvals.subject_id, approvals.decision, actions.run_id, actions.state "
            "FROM approvals JOIN actions ON actions.id = approvals.subject_id WHERE approvals.id = ?",
            (approval_id,),
        ).fetchone()
        if row is None or str(row["decision"]) not in {"denied", "expired"}:
            return
        if str(row["state"]) in {"cancelled", "denied", "expired"}:
            return
        action_id = str(row["subject_id"])
        run_id = str(row["run_id"])
        now = self._now()
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            updated = self.connection.execute(
                "UPDATE actions SET state = 'cancelled', policy_decision = 'denied', finished_at = ? "
                "WHERE id = ? AND state = 'waiting_approval'",
                (now, action_id),
            )
            if updated.rowcount == 1:
                self.connection.execute(
                    "UPDATE runs SET state = 'cancelled', result_json = ?, finished_at = ? "
                    "WHERE id = ? AND state = 'running'",
                    (_json({"result": "cancelled", "reason": str(row["decision"])}), now, run_id),
                )
                actor = ActorRef(kind="system", id="d3-export-reconciler")
                self._event("action", action_id, run_id, action_id, "action.cancelled", {"state": "cancelled", "reason": str(row["decision"])}, actor, f"approval:{approval_id}", now)
                self._event("run", run_id, run_id, action_id, "run.cancelled", {"state": "cancelled", "reason": str(row["decision"])}, actor, f"approval:{approval_id}", now)
            self.connection.commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise
        self.selections.close_action(action_id)

    def _claim_action(self, run_id: str, action_id: str) -> None:
        row = self.connection.execute("SELECT state FROM actions WHERE id = ?", (action_id,)).fetchone()
        if row is not None and str(row["state"]) == "running":
            return
        now = self._now()
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            budget = BudgetAccountingService(self.connection, now=self._now)
            reserved = budget.reserve_action_start(run_id=run_id, actor=self.actor, causation_id=f"action:{action_id}")
            if reserved.kind != "reserved":
                raise DraftExportError("E_BUDGET_EXCEEDED", "export budget could not be reserved")
            updated = self.connection.execute(
                "UPDATE actions SET state = 'running', started_at = ? WHERE id = ? AND state = 'authorized'",
                (now, action_id),
            )
            if updated.rowcount != 1:
                raise DraftExportError("E_ACTION_STATE", "export Action could not be claimed")
            self._event("action", action_id, run_id, action_id, "action.started", {"state": "running"}, self.actor, f"action:{action_id}", now)
            self.connection.commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

    def _commit_first_write_fence(
        self,
        action_id: str,
        run_id: str,
        identity_digest: str,
        target_commitment: str,
    ) -> None:
        if self.connection.execute("SELECT 1 FROM external_write_fences WHERE action_id = ?", (action_id,)).fetchone():
            raise DraftExportError("E_FENCE_REPLAY", "external write fence is one-shot")
        now = self._now()
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            state = self.connection.execute("SELECT state FROM actions WHERE id = ?", (action_id,)).fetchone()
            if state is None or str(state["state"]) != "running":
                raise DraftExportError("E_ACTION_STATE", "only a running Action may commit the write fence")
            event_id = self._event(
                "action", action_id, run_id, action_id, "action.output",
                {"gate": "first_external_write_fence", "state": "committed", "target_commitment": target_commitment},
                self.actor, f"action:{action_id}", now,
            )
            self.connection.execute(
                "INSERT INTO external_write_fences(action_id, selection_identity_digest, target_commitment, event_id, committed_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (action_id, identity_digest, target_commitment, event_id, now),
            )
            self.connection.commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise
        self._checkpoint("first_write_fence_committed")

    def _write_external(self, action_id: str, directory: Path, content: bytes) -> _WriteOutcome:
        started = time.monotonic()
        nonce = uuid4().hex
        probe_temp = directory / f".nana-probe-{nonce}.tmp"
        probe_final = directory / f".nana-probe-{nonce}.ok"
        report_temp = directory / f".nana-draft-{nonce}.tmp"
        report_final = directory / DRAFT_EXPORT_FILENAME
        created: set[Path] = set()
        final_committed = False
        try:
            self.selections.revalidate_for_effect(
                action_id,
                actor_id=str(self.actor.id),
                require_empty=True,
            )
            if _directory_entries(directory):
                raise FileExistsError("target directory changed before probe")
            with probe_temp.open("xb") as handle:
                created.add(probe_temp)
                handle.write(b"NANA atomic replace probe\n")
                handle.flush()
                os.fsync(handle.fileno())
            self.selections.revalidate_for_effect(
                action_id,
                actor_id=str(self.actor.id),
                require_empty=False,
            )
            os.rename(probe_temp, probe_final)
            created.discard(probe_temp)
            created.add(probe_final)
            probe_final.unlink()
            created.discard(probe_final)
            if _directory_entries(directory):
                raise FileExistsError("target directory changed after probe")
            self.selections.revalidate_for_effect(
                action_id,
                actor_id=str(self.actor.id),
                require_empty=True,
            )
            with report_temp.open("xb") as handle:
                created.add(report_temp)
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            self.selections.revalidate_for_effect(
                action_id,
                actor_id=str(self.actor.id),
                require_empty=False,
            )
            if report_final.exists() or report_final.is_symlink():
                raise FileExistsError("fixed draft filename already exists")
            os.rename(report_temp, report_final)
            created.discard(report_temp)
            created.add(report_final)
            final_committed = True
            self.selections.revalidate_for_effect(
                action_id,
                actor_id=str(self.actor.id),
                require_empty=False,
            )
            if report_final.read_bytes() != content:
                raise OSError("external draft verification failed")
            return _WriteOutcome(
                result="succeeded",
                actual_effects=EffectScope(writes=("external:fixed_local_draft_target",)),
                wall_clock_ms=max(0, int((time.monotonic() - started) * 1000)),
                output_bytes=len(content),
                detail="atomic draft write verified",
            )
        except BaseException:
            if not final_committed:
                cleanup_ok = True
                for path in tuple(created):
                    try:
                        path.unlink(missing_ok=True)
                    except OSError:
                        cleanup_ok = False
                try:
                    remaining = _directory_entries(directory)
                except OSError:
                    remaining = (object(),)
                if cleanup_ok and not remaining:
                    return _WriteOutcome(
                        result="failed",
                        actual_effects=EffectScope(
                            writes=("external:fixed_local_draft_target",) if created else ()
                        ),
                        wall_clock_ms=max(0, int((time.monotonic() - started) * 1000)),
                        output_bytes=0,
                        detail="external failure cleaned and verified",
                    )
            return _WriteOutcome(
                result="effect_unknown",
                actual_effects=EffectScope(writes=("external:fixed_local_draft_target",)),
                wall_clock_ms=max(0, int((time.monotonic() - started) * 1000)),
                output_bytes=len(content) if final_committed else 0,
                detail="external residue or final effect could not be proven",
            )

    def _settle(
        self,
        run_id: str,
        action_id: str,
        approval_id: str,
        material: ActionHashMaterial,
        outcome: _WriteOutcome,
    ) -> None:
        if self.connection.execute("SELECT 1 FROM action_receipts WHERE action_id = ?", (action_id,)).fetchone():
            return
        now = self._now()
        action_state = outcome.result
        run_state = "succeeded" if outcome.result == "succeeded" else ("orphaned" if outcome.result == "effect_unknown" else "failed")
        action_event_type = "action.effect_unknown" if outcome.result == "effect_unknown" else "action.completed"
        run_event_type = "run.succeeded" if run_state == "succeeded" else ("run.orphaned" if run_state == "orphaned" else "run.failed")
        approval = self.connection.execute(
            "SELECT decided_by_json, decided_at FROM approvals WHERE id = ?",
            (approval_id,),
        ).fetchone()
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            updated = self.connection.execute(
                "UPDATE actions SET state = ?, finished_at = ? WHERE id = ? AND state = 'running'",
                (action_state, now, action_id),
            )
            if updated.rowcount != 1:
                raise DraftExportError("E_ACTION_SETTLEMENT", "export Action was not running at settlement")
            usage = ResourceUsage(
                wall_clock_ms=outcome.wall_clock_ms,
                output_bytes=outcome.output_bytes,
            )
            self.connection.execute(
                "INSERT INTO action_receipts(id, action_id, action_hash, authorization_source, authorization_ref, "
                "approved_by_json, approved_at, actual_effects_json, result, before_artifact_ids_json, "
                "after_artifact_ids_json, resource_usage_json, created_at, authorized_effects_json, effect_violation) "
                "VALUES (?, ?, ?, 'approval', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
                (
                    str(self._new_id()), action_id, compute_action_hash(material), f"approval:{approval_id}",
                    approval["decided_by_json"], approval["decided_at"],
                    _json(outcome.actual_effects.model_dump(mode="json")), outcome.result,
                    _json([]), _json([str(material.args["draft_artifact_id"])]),
                    _json(usage.model_dump(mode="json")), now,
                    _json(material.requested_effects.model_dump(mode="json")),
                ),
            )
            BudgetAccountingService(self.connection, now=self._now).record_action_usage(
                run_id=run_id,
                action_id=action_id,
                usage=usage,
                actor=self.actor,
                causation_id=f"action:{action_id}",
            )
            self.connection.execute(
                "UPDATE runs SET state = ?, result_json = ?, finished_at = ? WHERE id = ? AND state = 'running'",
                (run_state, _json({"result": outcome.result, "detail": outcome.detail}), now, run_id),
            )
            self._event("action", action_id, run_id, action_id, action_event_type, {"state": action_state, "result": outcome.result, "detail": outcome.detail}, self.actor, f"action:{action_id}", now)
            self._event("run", run_id, run_id, action_id, run_event_type, {"state": run_state, "result": outcome.result}, self.actor, f"action:{action_id}", now)
            self.connection.commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

    def _expire_approval(self, approval_id: str, action_id: str) -> None:
        now = self._now()
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            updated = self.connection.execute(
                "UPDATE approvals SET decision = 'expired', decided_by_json = ?, decided_at = ? "
                "WHERE id = ? AND decision = 'requested'",
                (_json({"kind": "system", "id": "d3-export-reconciler"}), now, approval_id),
            )
            if updated.rowcount == 1:
                run_id = self._action_run_id(action_id)
                self._event("approval", approval_id, run_id, action_id, "approval.expired", {"decision": "expired"}, ActorRef(kind="system", id="d3-export-reconciler"), f"approval:{approval_id}", now)
            self.connection.commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

    def _load_source(self, finding_id: str, expected_revision: int) -> sqlite3.Row:
        row = self.connection.execute(
            "SELECT findings.id, findings.inquiry_id, findings.statement, findings.confidence_basis, findings.producer_run_id, findings.revision, "
            "inquiries.question, inquiries.project_id, projects.data_class, runs.state AS run_state "
            "FROM findings JOIN inquiries ON inquiries.id = findings.inquiry_id "
            "JOIN projects ON projects.id = inquiries.project_id "
            "LEFT JOIN runs ON runs.id = findings.producer_run_id WHERE findings.id = ?",
            (finding_id,),
        ).fetchone()
        if row is None or int(row["revision"]) != expected_revision:
            raise DraftExportError("E_REVISION_CONFLICT", "Finding revision changed")
        if str(row["data_class"]) != "public":
            raise DraftExportError("E_EXPORT_DATA_CLASS", "only canonical public findings may be exported")
        if row["producer_run_id"] is None or str(row["run_state"]) != "succeeded":
            raise DraftExportError("E_EXPORT_SOURCE", "Finding requires one succeeded producer Run")
        run_id = str(row["producer_run_id"])
        relation = self.connection.execute(
            "SELECT 1 FROM relations WHERE type = 'run_produces_finding' AND source_id = ? AND target_id = ? AND status = 'active'",
            (run_id, finding_id),
        ).fetchall()
        artifacts = self.connection.execute(
            "SELECT artifacts.id, artifacts.blob_hash FROM artifacts JOIN relations ON relations.target_id = artifacts.id "
            "WHERE artifacts.producer_run_id = ? AND artifacts.state = 'available' AND artifacts.media_type = 'text/plain' "
            "AND relations.type = 'run_produces_artifact' AND relations.source_id = ? AND relations.status = 'active'",
            (run_id, run_id),
        ).fetchall()
        receipts = self.connection.execute(
            "SELECT action_receipts.result FROM action_receipts JOIN actions ON actions.id = action_receipts.action_id "
            "WHERE actions.run_id = ? AND action_receipts.result = 'succeeded'",
            (run_id,),
        ).fetchall()
        if len(relation) != 1 or len(artifacts) != 1 or len(receipts) != 1:
            raise DraftExportError("E_EXPORT_SOURCE_GRAPH", "export source graph is not unique")
        values = dict(row)
        values.update(
            source_run_id=run_id,
            source_artifact_id=str(artifacts[0]["id"]),
            source_artifact_hash=str(artifacts[0]["blob_hash"]),
            project_id=str(row["project_id"]),
        )
        return _MappingRow(values)

    def _insert_export_relations(self, prepared: _PreparedSubject, now: str) -> tuple[str, str]:
        actor_json = _json(self.actor.model_dump(mode="json"))
        producer = str(uuid5(NAMESPACE_URL, f"{_PREPARE_NAMESPACE}:relation:producer:{prepared.run_id}"))
        lineage = str(uuid5(NAMESPACE_URL, f"{_PREPARE_NAMESPACE}:relation:lineage:{prepared.run_id}"))
        self.connection.execute(
            "INSERT INTO relations(id, type, source_type, source_id, target_type, target_id, producer_run_id, created_by_json, status) "
            "VALUES (?, 'run_produces_artifact', 'run', ?, 'artifact', ?, ?, ?, 'active')",
            (producer, prepared.run_id, prepared.draft_artifact_id, prepared.run_id, actor_json),
        )
        self.connection.execute(
            "INSERT INTO relations(id, type, source_type, source_id, target_type, target_id, producer_run_id, created_by_json, status) "
            "VALUES (?, 'artifact_derived_from_artifact', 'artifact', ?, 'artifact', ?, ?, ?, 'active')",
            (lineage, prepared.draft_artifact_id, prepared.source_artifact_id, prepared.run_id, actor_json),
        )
        return producer, lineage

    def _ensure_artifact(
        self,
        artifact_id: str,
        content: bytes,
        media_type: str,
        *,
        retention: dict[str, object],
    ) -> None:
        row = self.connection.execute("SELECT state FROM artifacts WHERE id = ?", (artifact_id,)).fetchone()
        store = self._artifact_store()
        if row is not None and str(row["state"]) == "staged":
            ArtifactReconciler(self.connection, store, grace_seconds=0).scan()
            row = self.connection.execute("SELECT state FROM artifacts WHERE id = ?", (artifact_id,)).fetchone()
        if row is None:
            staged = store.stage_bytes(content, media_type)
            ArtifactCommitService(self.connection, store, now=self._now).commit(
                artifact_id,
                staged,
                retention=retention,
            )
        self._verify_artifact(artifact_id, content)

    def _verify_artifact(self, artifact_id: str, content: bytes) -> None:
        actual = ArtifactReader(self.connection, self._artifact_store()).read_bytes(artifact_id)
        if actual != content:
            raise DraftExportError("E_ARTIFACT_MISMATCH", "canonical export Artifact bytes changed")

    def _artifact_store(self) -> ArtifactStore:
        row = next(
            (row for row in self.connection.execute("PRAGMA database_list") if str(row["name"]) == "main"),
            None,
        )
        if row is None or not str(row["file"]):
            raise DraftExportError("E_WORKSPACE_ARTIFACT_ROOT", "draft export requires a file-backed Workspace")
        return ArtifactStore(Path(str(row["file"])).resolve(strict=True).parent)

    def _load_action_material(self, action_id: str) -> ActionHashMaterial:
        row = self.connection.execute(
            "SELECT actions.action_hash, actions.args_artifact_id FROM actions WHERE actions.id = ?",
            (action_id,),
        ).fetchone()
        if row is None:
            raise DraftExportError("E_ACTION_NOT_FOUND", "export Action does not exist")
        args = json.loads(ArtifactReader(self.connection, self._artifact_store()).read_bytes(str(row["args_artifact_id"])).decode("utf-8"))
        run = self.connection.execute("SELECT snapshot_json FROM runs WHERE id = ?", (self._action_run_id(action_id),)).fetchone()
        snapshot = json.loads(str(run["snapshot_json"]))
        material = ActionHashMaterial(
            capability=EXPORT_DRAFT_EXTERNAL_CAPABILITY,
            args=args,
            args_hash=canonical_json_hash(args),
            data_class=DataClass.PUBLIC,
            requested_effects=EffectScope(reads=("workspace:canonical_public_draft",), writes=("external:fixed_local_draft_target",)),
            budget=BudgetSnapshot.model_validate(snapshot["budget"]),
            risk_tier=RiskTier.T3,
            reversible=False,
        )
        if compute_action_hash(material) != str(row["action_hash"]):
            raise DraftExportError("E_ACTION_HASH_MISMATCH", "export Action material is not canonical")
        return material

    def _load_durable_authorization(self, action_id: str) -> ActionHashMaterial:
        row = self.connection.execute(
            "SELECT material_json, authorization_source FROM action_authorizations WHERE action_id = ?",
            (action_id,),
        ).fetchone()
        if row is None or str(row["authorization_source"]) != "approval":
            raise DraftExportError("E_ACTION_UNAUTHORIZED", "durable Approval authorization is missing")
        material = ActionHashMaterial.model_validate_json(str(row["material_json"]))
        if material.capability != EXPORT_DRAFT_EXTERNAL_CAPABILITY:
            raise DraftExportError("E_CAPABILITY_MISMATCH", "durable export capability changed")
        return material

    def _verify_frozen_subject(self, run_id: str, material: ActionHashMaterial) -> None:
        run = self.connection.execute("SELECT snapshot_json FROM runs WHERE id = ?", (run_id,)).fetchone()
        snapshot = json.loads(str(run["snapshot_json"]))
        source = self._load_source(str(snapshot["finding_id"]), int(snapshot["finding_revision"]))
        draft = render_draft_report(
            inquiry_question=str(source["question"]),
            finding_statement=str(source["statement"]),
            confidence_basis=str(source["confidence_basis"]),
            algorithm_run_id=str(source["source_run_id"]),
            source_artifact_hash=str(source["source_artifact_hash"]),
        )
        if (
            snapshot["source_artifact_hash"] != source["source_artifact_hash"]
            or snapshot["renderer_digest"] != DRAFT_REPORT_RENDERER_DIGEST
            or "sha256:" + hashlib.sha256(draft).hexdigest() != material.args["draft_hash"]
            or snapshot["draft_hash"] != material.args["draft_hash"]
        ):
            raise DraftExportError("E_EXPORT_SOURCE_DRIFT", "frozen export source or renderer changed")

    def _selection_is_bound(self, action_id: str) -> bool:
        try:
            self.selections.bound_for_action(action_id, actor_id=str(self.actor.id))
            return True
        except ExportSelectionError:
            return False

    def _action_run_id(self, action_id: str) -> str:
        row = self.connection.execute("SELECT run_id FROM actions WHERE id = ?", (action_id,)).fetchone()
        if row is None or row["run_id"] is None:
            raise DraftExportError("E_ACTION_RUN", "export Action has no Run")
        return str(row["run_id"])

    def _event(
        self,
        aggregate_type: str,
        aggregate_id: str,
        run_id: str | None,
        action_id: str | None,
        event_type: str,
        payload: dict[str, object],
        actor: ActorRef,
        causation_id: str | None,
        occurred_at: str,
    ) -> int:
        cursor = self.connection.execute(
            "INSERT INTO events(aggregate_type, aggregate_id, aggregate_version, run_id, run_seq, action_id, actor_json, causation_id, type, payload_json, occurred_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                aggregate_type, aggregate_id, self._aggregate_version(aggregate_type, aggregate_id) + 1,
                run_id, self._run_seq(run_id) + 1 if run_id else None, action_id,
                _json(actor.model_dump(mode="json")), causation_id, event_type, _json(payload), occurred_at,
            ),
        )
        event_id = int(cursor.lastrowid)
        self.connection.execute("INSERT INTO outbox_events(event_id) VALUES (?)", (event_id,))
        return event_id

    def _aggregate_version(self, aggregate_type: str, aggregate_id: str) -> int:
        return int(self.connection.execute(
            "SELECT COALESCE(MAX(aggregate_version), 0) FROM events WHERE aggregate_type = ? AND aggregate_id = ?",
            (aggregate_type, aggregate_id),
        ).fetchone()[0])

    def _run_seq(self, run_id: str) -> int:
        return int(self.connection.execute(
            "SELECT COALESCE(MAX(run_seq), 0) FROM events WHERE run_id = ?",
            (run_id,),
        ).fetchone()[0])

    def _validate_prepare_result(self, command: CommandBase, stored: CommandResult) -> None:
        if stored.command_id != command.command_id or not any(key.startswith("approval:") for key in stored.affected_revisions):
            raise RuntimeError("stored draft-export preparation result is not bound")
        for event_id in stored.event_ids:
            if self.connection.execute(
                "SELECT 1 FROM events JOIN outbox_events ON outbox_events.event_id = events.id WHERE events.id = ? AND events.causation_id = ?",
                (event_id, str(command.command_id)),
            ).fetchone() is None:
                raise RuntimeError("stored draft-export Event/outbox is not bound")

    def _validate_decision_result(self, command: CommandBase, stored: CommandResult) -> None:
        if stored.command_id != command.command_id or not any(key.startswith("approval:") for key in stored.affected_revisions):
            raise RuntimeError("stored Approval decision result is not bound")
        row = self.connection.execute("SELECT decision FROM approvals WHERE id = ?", (str(getattr(command, "approval_id")),)).fetchone()
        if row is None or str(row["decision"]) != str(getattr(command, "decision")):
            raise RuntimeError("stored Approval decision does not match canonical state")

    def _validate_rejection(self, command: CommandBase, stored: StructuredError) -> None:
        binding = stored.details.get("binding")
        if binding != self._transactions._request_hash(command) or stored.data_safe is not True:
            raise RuntimeError("stored draft-export rejection is not bound")

    def _error(
        self,
        command: CommandBase,
        request_hash: str,
        code: str,
        message: str,
        *,
        retryable: bool = False,
    ) -> StructuredError:
        enum = ErrorCode(code) if code in ErrorCode._value2member_map_ else ErrorCode.POLICY_DENIED
        category = ErrorCategory.CONFLICT if enum in {ErrorCode.REVISION_CONFLICT, ErrorCode.COMMAND_REPLAY_CONFLICT} else ErrorCategory.POLICY
        return StructuredError(
            code=enum,
            category=category,
            message=message,
            retryable=retryable,
            details={"binding": request_hash},
            data_safe=True,
            suggested_actions=("Reload canonical state before creating a fresh export attempt.",),
        )

    @staticmethod
    def _export_budget() -> BudgetSnapshot:
        return BudgetSnapshot(
            wall_clock_seconds=30,
            cpu_seconds=None,
            memory_bytes=None,
            gpu_seconds=None,
            max_actions=1,
            max_concurrency=1,
            max_model_calls=0,
            max_model_tokens=0,
            max_cost_micros=0,
            max_retries=0,
            max_output_bytes=DRAFT_EXPORT_MAX_BYTES,
            max_artifact_bytes=DRAFT_EXPORT_MAX_BYTES * 2,
            max_download_bytes=0,
            network_targets=(),
            read_roots=("workspace:canonical_public_draft",),
            write_roots=("external:fixed_local_draft_target",),
        )


class _MappingRow(dict[str, object]):
    """Small mapping with sqlite.Row-like indexing for derived source facts."""
