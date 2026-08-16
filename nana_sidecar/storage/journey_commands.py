"""D3-05 canonical research journey writers."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import stat
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Callable
from uuid import UUID, uuid4
from uuid import uuid5, NAMESPACE_URL

from nana_sidecar import SCHEMA_VERSION
from nana_sidecar.contracts.commands import (
    AttachEvidence,
    CommandBase,
    CommandResult,
    CommandStatus,
    CreateClaim,
    CreateHypothesis,
    CreateInquiry,
    CreateLocator,
    CreateProject,
    CreateRelation,
    DraftFinding,
    ProposePlan,
    RegisterResource,
    RevisePlan,
    StartRun,
    PauseRun,
    ResumeRun,
    CancelRun,
)
from nana_sidecar.contracts.common import ActorRef, DataClass
from nana_sidecar.contracts.authorization import ActionHashMaterial, GrantMatchContext, canonical_json_hash, compute_action_hash
from nana_sidecar.contracts.builtin_capabilities import (
    PYTHON_UNITTEST_LOCKED_CAPABILITY,
    PYTHON_UNITTEST_LOCKED_TEST_IDS,
    python_unittest_locked_registry_entry,
)
from nana_sidecar.contracts.capabilities import CapabilityAuthorizationMode, CapabilityProviderMode
from nana_sidecar.contracts.common import BudgetSnapshot, EffectScope, RiskTier, VersionedRef
from nana_sidecar.contracts.domain import CapabilityConstraints, PolicyGrant, PolicyGrantState
from nana_sidecar.contracts.domain import RelationType
from nana_sidecar.contracts.errors import (
    ErrorCategory,
    ErrorCode,
    StructuredError,
)
from nana_sidecar.contracts.journey import (
    DecideApprovalRequest,
    JourneyCommandRequest,
    RequestApprovalRequest,
    WorkspaceBootstrapSpec,
    to_canonical_command,
)
from nana_sidecar.export_selection import ExportSelectionRegistry
from nana_sidecar.storage.draft_export import DraftExportService
from nana_sidecar.contracts.relations import (
    RelationEndpoint,
    RelationValidationContext,
    TERMINAL_RUN_STATES,
    validate_relation,
)
from nana_sidecar.contracts.locators import validate_logical_path
from nana_sidecar.storage.command_transactions import (
    CommandExecutionError,
    CommandTransactionService,
)
from nana_sidecar.storage.artifact_commits import ArtifactCommitService, ArtifactReader
from nana_sidecar.storage.artifacts import ArtifactStore, StagedArtifact
from nana_sidecar.storage.admission import CapabilityAdmissionService, AdmissionStateError
from nana_sidecar.storage.locked_unittest_executor import (
    LockedExecutorError,
    LockedProcessResult,
    LockedUnittestExecutorService,
    default_locked_unittest_runner,
)
from nana_sidecar.storage.run_scheduler import RunSchedulerService, SchedulerStateError


# This is a server-owned fixture identity.  It is derived from the project
# identity only so each project has an isolated grant row; the browser cannot
# choose, mint, or submit a PolicyGrant reference.
_LOCKED_DEV_GRANT_NAMESPACE = "nana:d3-06:locked-dev-grant:v1"
_LOCKED_ARGS_ARTIFACT_NAMESPACE = "nana:d3-06:locked-args-artifact:v1"
_LOCKED_RESULT_ARTIFACT_NAMESPACE = "nana:d3-06:locked-result-artifact:v1"
_LOCKED_RESULT_RELATION_NAMESPACE = "nana:d3-06:locked-result-relation:v1"


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _actor_json(actor: ActorRef) -> str:
    return _json(actor.model_dump(mode="json"))


def _path_is_link_or_reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = int(getattr(metadata, "st_file_attributes", 0))
    return (
        path.is_symlink()
        or bool(reparse and attributes & reparse)
        or getattr(os.path, "isjunction", lambda _path: False)(path)
    )


class FrozenResourceError(ValueError):
    """A data-safe frozen Resource verification failure."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True, slots=True)
class FrozenResourceDescriptor:
    descriptor_id: str
    read_root: Path
    logical_ref: str
    media_type: str
    data_class: DataClass
    license: str | None = None


class WorkspaceBootstrapService:
    """Create the one canonical Workspace as an internal lifecycle fact."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        checkpoint: Callable[[str], None] | None = None,
    ) -> None:
        self.connection = connection
        self._checkpoint = checkpoint or (lambda _name: None)

    def ensure(self, spec: WorkspaceBootstrapSpec) -> int:
        if self.connection.in_transaction:
            raise RuntimeError("Workspace bootstrap requires an idle connection")
        actor = ActorRef(kind="system", id="workspace-bootstrap")
        created_at = spec.created_at.isoformat().replace("+00:00", "Z")
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            rows = self.connection.execute(
                "SELECT id, schema_version, data_root, policy_json, status, revision, created_at "
                "FROM workspaces ORDER BY id"
            ).fetchall()
            if not rows:
                self.connection.execute(
                    "INSERT INTO workspaces(id, schema_version, data_root, policy_json, status, revision, created_at) "
                    "VALUES (?, ?, ?, ?, ?, 1, ?)",
                    (
                        str(spec.workspace_id),
                        SCHEMA_VERSION,
                        spec.data_root,
                        _json(spec.policy),
                        spec.status,
                        created_at,
                    ),
                )
                event_id = self._insert_event(spec, actor, created_at)
            elif len(rows) == 1 and self._matches(rows[0], spec, created_at):
                event = self.connection.execute(
                    "SELECT event.id, event.actor_json, event.payload_json, "
                    "event.occurred_at, outbox.event_id AS outbox_id FROM events AS event "
                    "LEFT JOIN outbox_events AS outbox ON outbox.event_id = event.id "
                    "WHERE event.aggregate_type = 'workspace' AND event.aggregate_id = ? "
                    "AND event.aggregate_version = 1 AND event.type = 'workspace.created'",
                    (str(spec.workspace_id),),
                ).fetchone()
                expected_payload = _json(
                    {
                        "workspace_id": str(spec.workspace_id),
                        "schema_version": SCHEMA_VERSION,
                        "status": spec.status,
                    }
                )
                if (
                    event is None
                    or event["outbox_id"] is None
                    or event["actor_json"] != _actor_json(actor)
                    or event["payload_json"] != expected_payload
                    or event["occurred_at"] != created_at
                ):
                    raise RuntimeError("existing Workspace is missing its creation Event/outbox")
                event_id = int(event["id"])
            else:
                raise RuntimeError("Workspace bootstrap identity/configuration mismatch")
            self._checkpoint("before_commit")
            self.connection.commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise
        self._checkpoint("after_commit")
        return event_id

    @staticmethod
    def _matches(row: sqlite3.Row, spec: WorkspaceBootstrapSpec, created_at: str) -> bool:
        return (
            row["id"] == str(spec.workspace_id)
            and int(row["schema_version"]) == SCHEMA_VERSION
            and row["data_root"] == spec.data_root
            and row["policy_json"] == _json(spec.policy)
            and row["status"] == spec.status
            and int(row["revision"]) == 1
            and row["created_at"] == created_at
        )

    def _insert_event(
        self,
        spec: WorkspaceBootstrapSpec,
        actor: ActorRef,
        created_at: str,
    ) -> int:
        cursor = self.connection.execute(
            "INSERT INTO events(aggregate_type, aggregate_id, aggregate_version, actor_json, "
            "type, payload_json, occurred_at) VALUES ('workspace', ?, 1, ?, "
            "'workspace.created', ?, ?)",
            (
                str(spec.workspace_id),
                _actor_json(actor),
                _json(
                    {
                        "workspace_id": str(spec.workspace_id),
                        "schema_version": SCHEMA_VERSION,
                        "status": spec.status,
                    }
                ),
                created_at,
            ),
        )
        event_id = int(cursor.lastrowid)
        self.connection.execute("INSERT INTO outbox_events(event_id) VALUES (?)", (event_id,))
        return event_id


class JourneyCommandService:
    """Execute the closed D3-05 request union through the shared D1 engine."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        actor: ActorRef,
        resources: tuple[FrozenResourceDescriptor, ...],
        now: Callable[[], str],
        new_id: Callable[[], UUID] = uuid4,
        checkpoint: Callable[[str], None] | None = None,
        export_selections: ExportSelectionRegistry | None = None,
    ) -> None:
        if actor.kind.value != "user" or actor.id is None:
            raise ValueError("Journey HTTP actor must be a stable user")
        self.connection = connection
        self.actor = actor
        self._resources = self._validate_descriptors(resources)
        self._now = now
        self._new_id = new_id
        self._export_selections = export_selections
        self._transactions = CommandTransactionService(
            connection,
            now=now,
            checkpoint=checkpoint,
        )

    def execute(
        self,
        request: JourneyCommandRequest,
        *,
        defer_locked_execution: bool = False,
    ) -> CommandResult:
        if isinstance(request, RequestApprovalRequest):
            if self._export_selections is None:
                raise self._export_disabled_error()
            return DraftExportService(
                self.connection,
                actor=self.actor,
                selections=self._export_selections,
                now=self._now,
                new_id=self._new_id,
            ).prepare(request)
        if isinstance(request, DecideApprovalRequest):
            if self._export_selections is None:
                raise self._export_disabled_error()
            return DraftExportService(
                self.connection,
                actor=self.actor,
                selections=self._export_selections,
                now=self._now,
                new_id=self._new_id,
            ).decide(request)
        command = to_canonical_command(request, actor=self.actor)
        if isinstance(command, RevisePlan):
            return self._transactions.execute(command)
        if isinstance(command, StartRun):
            self._ensure_locked_args_artifact(command)
        result = self._transactions.execute_transactional(
            command,
            apply=self._apply,
            validate_result=self._validate_stored_result,
            validate_rejection=self._validate_stored_rejection,
        )
        if (
            isinstance(command, StartRun)
            and result.status is CommandStatus.ACCEPTED
            and not defer_locked_execution
        ):
            self._execute_locked_action(command, result)
        return result

    @staticmethod
    def _export_disabled_error() -> CommandExecutionError:
        return CommandExecutionError(
            StructuredError(
                code=ErrorCode.POLICY_DENIED,
                category=ErrorCategory.POLICY,
                message="draft export requires an active launcher selection",
                retryable=False,
                details={},
                data_safe=True,
                suggested_actions=("Restart the launcher and select a dedicated target.",),
            )
        )

    @staticmethod
    def _validate_descriptors(
        resources: tuple[FrozenResourceDescriptor, ...],
    ) -> dict[str, FrozenResourceDescriptor]:
        result: dict[str, FrozenResourceDescriptor] = {}
        descriptor_ids: set[str] = set()
        for descriptor in resources:
            if (
                not descriptor.descriptor_id
                or descriptor.descriptor_id in descriptor_ids
                or descriptor.logical_ref in result
            ):
                raise ValueError("frozen Resource descriptors must be uniquely named")
            try:
                normalized = validate_logical_path(descriptor.logical_ref)
            except ValueError as exc:
                raise ValueError(
                    "frozen Resource logical_ref must be portable"
                ) from exc
            if normalized != descriptor.logical_ref:
                raise ValueError("frozen Resource logical_ref must be portable")
            descriptor_ids.add(descriptor.descriptor_id)
            result[descriptor.logical_ref] = descriptor
        return result

    def _apply(
        self,
        command: CommandBase,
        request_hash: str,
    ) -> tuple[CommandResult | None, StructuredError | None]:
        handlers = {
            CreateProject: self._create_project,
            CreateInquiry: self._create_inquiry,
            ProposePlan: self._propose_plan,
            RegisterResource: self._register_resource,
            CreateLocator: self._create_locator,
            CreateClaim: self._create_claim,
            AttachEvidence: self._attach_evidence,
            CreateHypothesis: self._create_hypothesis,
            CreateRelation: self._create_relation,
            DraftFinding: self._draft_finding,
            StartRun: self._start_run,
            PauseRun: self._pause_run,
            ResumeRun: self._resume_run,
            CancelRun: self._cancel_run,
        }
        for command_type, handler in handlers.items():
            if isinstance(command, command_type):
                return handler(command, request_hash)
        raise TypeError(f"unsupported D3-05 Command: {command.type}")

    def _workspace_artifact_store(self) -> ArtifactStore:
        rows = self.connection.execute("PRAGMA database_list").fetchall()
        database_file = next(
            (str(row["file"]) for row in rows if str(row["name"]) == "main"),
            "",
        )
        if not database_file:
            raise LockedExecutorError(
                "E_WORKSPACE_ARTIFACT_ROOT",
                "Locked journey requires a file-backed canonical Workspace",
            )
        return ArtifactStore(Path(database_file).resolve(strict=True).parent)

    @staticmethod
    def _locked_args_artifact_id(test_id: str, args_hash: str) -> UUID:
        return uuid5(
            NAMESPACE_URL,
            f"{_LOCKED_ARGS_ARTIFACT_NAMESPACE}:{test_id}:{args_hash}",
        )

    def _ensure_locked_args_artifact(self, command: StartRun) -> None:
        """Provision and verify the immutable server-owned args blob.

        This is runtime fixture initialization, not a browser-selected command
        side effect. The deterministic Artifact is committed through the D1
        two-transaction protocol before the StartRun transaction may reference
        it.
        """
        if self.connection.in_transaction:
            raise RuntimeError("locked args provisioning requires an idle connection")
        project = self.connection.execute(
            "SELECT id FROM projects WHERE id = ?",
            (str(command.project_id),),
        ).fetchone()
        inquiry = self.connection.execute(
            "SELECT project_id FROM inquiries WHERE id = ?",
            (str(command.inquiry_id),),
        ).fetchone()
        plan = self.connection.execute(
            "SELECT inquiry_id, policy_json FROM plans WHERE id = ? AND revision = ?",
            (str(command.plan_id), command.plan_revision),
        ).fetchone()
        if (
            project is None
            or inquiry is None
            or str(inquiry["project_id"]) != str(command.project_id)
            or plan is None
            or str(plan["inquiry_id"]) != str(command.inquiry_id)
            or command.expected_revision != command.plan_revision
            or command.backend.id != PYTHON_UNITTEST_LOCKED_CAPABILITY.id
            or command.backend.version != PYTHON_UNITTEST_LOCKED_CAPABILITY.version
        ):
            return
        if command.retry_of_run_id is not None:
            retry_source = self.connection.execute(
                "SELECT project_id, inquiry_id, state FROM runs WHERE id = ?",
                (str(command.retry_of_run_id),),
            ).fetchone()
            if (
                retry_source is None
                or str(retry_source["project_id"]) != str(command.project_id)
                or str(retry_source["inquiry_id"]) != str(command.inquiry_id)
                or str(retry_source["state"]) != "failed"
            ):
                return
        try:
            policy = json.loads(str(plan["policy_json"]))
        except (TypeError, json.JSONDecodeError):
            return
        test_id = policy.get("test_id")
        if (
            test_id not in PYTHON_UNITTEST_LOCKED_TEST_IDS
            or policy.get("network") != "denied"
        ):
            return
        args = {"test_id": test_id}
        args_bytes = _json(args).encode("utf-8")
        args_hash = canonical_json_hash(args)
        artifact_id = str(self._locked_args_artifact_id(test_id, args_hash))
        store = self._workspace_artifact_store()
        row = self.connection.execute(
            "SELECT state, media_type, blob_hash, size FROM artifacts WHERE id = ?",
            (artifact_id,),
        ).fetchone()
        if row is None:
            staged = store.stage_bytes(args_bytes, "application/json")
            ArtifactCommitService(
                self.connection,
                store,
                now=self._now,
            ).commit(
                artifact_id,
                staged,
                retention={"kind": "d3_locked_fixture_args"},
            )
        content = ArtifactReader(self.connection, store).read_bytes(artifact_id)
        if content != args_bytes:
            raise LockedExecutorError(
                "E_ARGS_ARTIFACT_MISMATCH",
                "Server-owned locked args Artifact bytes changed",
            )

    def _read_artifact_row(self, row: sqlite3.Row) -> bytes:
        return ArtifactReader(
            self.connection,
            self._workspace_artifact_store(),
        ).read_bytes(str(row["id"]))

    def _start_run(
        self,
        command: StartRun,
        request_hash: str,
    ) -> tuple[CommandResult | None, StructuredError | None]:
        """Create the durable proposed Run/Action and frozen T2 fixture.

        Admission, scheduling, and execution happen only after this command
        transaction commits; the browser never supplies fixture or grant
        material.
        """
        project = self.connection.execute(
            "SELECT id, data_class, revision FROM projects WHERE id = ?",
            (str(command.project_id),),
        ).fetchone()
        inquiry = self.connection.execute(
            "SELECT id, project_id, revision FROM inquiries WHERE id = ?",
            (str(command.inquiry_id),),
        ).fetchone()
        plan = self.connection.execute(
            "SELECT id, inquiry_id, revision, status, steps_json, policy_json, budget_json "
            "FROM plans WHERE id = ? AND revision = ?",
            (str(command.plan_id), command.plan_revision),
        ).fetchone()
        if (
            project is None
            or inquiry is None
            or str(inquiry["project_id"]) != str(command.project_id)
            or plan is None
            or str(plan["inquiry_id"]) != str(command.inquiry_id)
        ):
            return None, self._error(
                command,
                request_hash,
                code=ErrorCode.REVISION_CONFLICT,
                category=ErrorCategory.CONFLICT,
                message="StartRun target revision or actor scope is invalid",
                details={"project_id": str(command.project_id)},
                retryable=True,
            )
        if command.expected_revision != command.plan_revision:
            return None, self._error(
                command,
                request_hash,
                code=ErrorCode.REVISION_CONFLICT,
                category=ErrorCategory.CONFLICT,
                message="StartRun expected_revision must match the selected Plan revision",
                details={
                    "expected_revision": command.expected_revision,
                    "plan_revision": command.plan_revision,
                },
                retryable=True,
            )
        retry_source = None
        if command.retry_of_run_id is not None:
            retry_source = self.connection.execute(
                "SELECT id, project_id, inquiry_id, state, created_at FROM runs WHERE id = ?",
                (str(command.retry_of_run_id),),
            ).fetchone()
            if retry_source is None:
                return None, self._state_error(
                    command, request_hash, "run", command.retry_of_run_id, "missing"
                )
            if (
                str(retry_source["project_id"]) != str(command.project_id)
                or str(retry_source["inquiry_id"]) != str(command.inquiry_id)
            ):
                return None, self._scope_error(
                    command, request_hash, "retry_run_scope"
                )
            if str(retry_source["state"]) != "failed":
                return None, self._state_error(
                    command,
                    request_hash,
                    "run",
                    command.retry_of_run_id,
                    str(retry_source["state"]),
                )
        if command.backend.id != PYTHON_UNITTEST_LOCKED_CAPABILITY.id or command.backend.version != PYTHON_UNITTEST_LOCKED_CAPABILITY.version:
            return None, self._error(
                command,
                request_hash,
                code=ErrorCode.CAPABILITY_UNKNOWN,
                category=ErrorCategory.POLICY,
                message="Only the frozen python.unittest.locked backend is accepted",
                details={"backend": command.backend.model_dump(mode="json")},
            )
        budget = BudgetSnapshot.model_validate_json(str(plan["budget_json"]))
        policy = json.loads(str(plan["policy_json"]))
        test_id = policy.get("test_id")
        if test_id not in PYTHON_UNITTEST_LOCKED_TEST_IDS or policy.get("network") != "denied":
            return None, self._error(
                command,
                request_hash,
                code=ErrorCode.POLICY_DENIED,
                category=ErrorCategory.POLICY,
                message="Plan does not select the frozen locked test fixture",
                details={"test_id": test_id},
            )

        now = self._now()
        run_id = self._new_id()
        action_id = self._new_id()
        args = {"test_id": test_id}
        args_bytes = _json(args).encode("utf-8")
        args_hash = canonical_json_hash(args)
        artifact_id = self._locked_args_artifact_id(test_id, args_hash)
        grant_id = uuid5(
            NAMESPACE_URL,
            f"{_LOCKED_DEV_GRANT_NAMESPACE}:{command.project_id}:{run_id}",
        )
        run_snapshot = {
            "plan_id": str(command.plan_id),
            "plan_revision": command.plan_revision,
            "budget": budget.model_dump(mode="json"),
            "fixture": {
                "test_id": test_id,
                "args_hash": args_hash,
                "capability_digest": PYTHON_UNITTEST_LOCKED_CAPABILITY.digest,
                "policy_grant_id": str(grant_id),
            },
            "random_seed": command.random_seed,
            "grant_provisioning": "server_owned_locked_fixture_v1",
        }
        entry = python_unittest_locked_registry_entry()
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
        self.connection.execute(
            "INSERT INTO runs(id, project_id, inquiry_id, state, snapshot_json, retry_of_run_id, created_at) "
            "VALUES (?, ?, ?, 'running', ?, ?, ?)",
            (
                str(run_id), str(command.project_id), str(command.inquiry_id),
                _json(run_snapshot),
                str(command.retry_of_run_id) if command.retry_of_run_id is not None else None,
                now,
            ),
        )
        artifact = self.connection.execute(
            "SELECT state, media_type, blob_hash, size FROM artifacts WHERE id = ?",
            (str(artifact_id),),
        ).fetchone()
        expected_blob_hash = f"sha256:{hashlib.sha256(args_bytes).hexdigest()}"
        if (
            artifact is None
            or str(artifact["state"]) != "available"
            or str(artifact["media_type"]) != "application/json"
            or str(artifact["blob_hash"]) != expected_blob_hash
            or int(artifact["size"]) != len(args_bytes)
        ):
            raise LockedExecutorError(
                "E_ARGS_ARTIFACT_UNAVAILABLE",
                "Server-owned locked args Artifact is not canonically available",
            )
        effects = EffectScope(
            reads=("project:source", "project:tests"),
            processes=("builtin:python.unittest.locked",),
        )
        material = ActionHashMaterial(
            capability=PYTHON_UNITTEST_LOCKED_CAPABILITY,
            args=args,
            args_hash=args_hash,
            data_class=DataClass(str(project["data_class"])),
            requested_effects=effects,
            budget=budget,
            risk_tier=RiskTier.T2,
            reversible=True,
        )
        self.connection.execute(
            "INSERT INTO actions(id, run_id, plan_step_id, capability_id, capability_version, executable_digest, "
            "args_artifact_id, args_hash, action_hash, risk_tier, requested_effects_json, policy_decision, authorization_ref, state) "
            "VALUES (?, ?, 'step-locked-test', ?, ?, ?, ?, ?, ?, 'T2', ?, 'grant', ?, 'proposed')",
            (
                str(action_id), str(run_id), PYTHON_UNITTEST_LOCKED_CAPABILITY.id,
                PYTHON_UNITTEST_LOCKED_CAPABILITY.version, PYTHON_UNITTEST_LOCKED_CAPABILITY.digest,
                str(artifact_id), args_hash, compute_action_hash(material),
                _json(effects.model_dump(mode="json")), f"policy_grant:{grant_id}",
            ),
        )
        valid_from = datetime.fromisoformat(now.replace("Z", "+00:00")) - timedelta(minutes=1)
        expires_at = valid_from + timedelta(days=1)
        constraints = CapabilityConstraints(
            args_schema=entry.args_schema,
            allowed_data_classes=(DataClass(str(project["data_class"])),),
            read_roots=("project:source", "project:tests"),
            process_targets=("builtin:python.unittest.locked",),
            per_action_budget=budget,
            cumulative_budget=budget,
            max_concurrency=budget.max_concurrency,
            max_uses=max(1, budget.max_actions),
            valid_from=valid_from,
            expires_at=expires_at,
        )
        self.connection.execute(
            "INSERT OR IGNORE INTO policy_grants(id, project_id, capability_id, capability_version, executable_digest, "
            "constraints_json, state, uses, created_at) VALUES (?, ?, ?, ?, ?, ?, 'active', 0, ?)",
            (str(grant_id), str(command.project_id), PYTHON_UNITTEST_LOCKED_CAPABILITY.id,
             PYTHON_UNITTEST_LOCKED_CAPABILITY.version, PYTHON_UNITTEST_LOCKED_CAPABILITY.digest,
             _json(constraints.model_dump(mode="json")), now),
        )
        event_id = self._event(
            command,
            aggregate_type="run",
            aggregate_id=run_id,
            aggregate_version=1,
            event_type="run.created",
            payload={"run_id": str(run_id), "action_id": str(action_id), "state": "running"},
            occurred_at=now,
        )
        action_event_id = self._event(
            command,
            aggregate_type="action",
            aggregate_id=action_id,
            aggregate_version=1,
            event_type="action.proposed",
            payload={"action_id": str(action_id), "run_id": str(run_id), "state": "proposed"},
            occurred_at=now,
        )
        revisions = {f"run:{run_id}": 1, f"action:{action_id}": 1}
        events = [event_id, action_event_id]
        if command.retry_of_run_id is not None:
            relation_id = self._new_id()
            source = RelationEndpoint(
                object_type="run", object_id=run_id,
                project_id=command.project_id, inquiry_id=command.inquiry_id,
                created_at=datetime.fromisoformat(now.replace("Z", "+00:00")),
                created_order=event_id,
            )
            retry_event = self.connection.execute(
                "SELECT MIN(id) AS id FROM events WHERE aggregate_type = 'run' AND aggregate_id = ?",
                (str(command.retry_of_run_id),),
            ).fetchone()
            target = RelationEndpoint(
                object_type="run", object_id=command.retry_of_run_id,
                project_id=UUID(str(retry_source["project_id"])),
                inquiry_id=UUID(str(retry_source["inquiry_id"])),
                state=str(retry_source["state"]),
                created_at=datetime.fromisoformat(str(retry_source["created_at"]).replace("Z", "+00:00")),
                created_order=int(retry_event["id"]),
            )
            validate_relation(RelationType.RUN_RETRY_OF_RUN.value, source, target)
            self._insert_relation(
                relation_id, RelationType.RUN_RETRY_OF_RUN.value,
                "run", run_id, "run", command.retry_of_run_id, command.actor,
                producer_run_id=run_id,
            )
            events.append(self._relation_event(
                command, relation_id, RelationType.RUN_RETRY_OF_RUN.value,
                run_id, command.retry_of_run_id, now,
            ))
            revisions[f"relation:{relation_id}"] = 1
        return self._result(command, revisions, events), None

    def _pause_run(self, command: PauseRun, request_hash: str):
        actual, error = self._load_run_revision(command, request_hash)
        if error:
            return None, error
        try:
            result = RunSchedulerService(self.connection, now=self._now).pause_run(
                run_id=str(command.run_id), actor=command.actor, reason=command.reason,
                causation_id=str(command.command_id), _in_transaction=True,
            )
        except SchedulerStateError as exc:
            return None, self._error(
                command, request_hash, code=ErrorCode.STATE_TRANSITION,
                category=ErrorCategory.CONFLICT, message=str(exc),
                details={"scheduler_code": exc.code},
            )
        return self._result(
            command,
            {f"run:{command.run_id}": actual + 1},
            list(result.event_ids),
        ), None

    def _resume_run(self, command: ResumeRun, request_hash: str):
        actual, error = self._load_run_revision(command, request_hash)
        if error:
            return None, error
        try:
            result = RunSchedulerService(self.connection, now=self._now).resume_run(
                run_id=str(command.run_id), actor=command.actor, reason=command.reason,
                causation_id=str(command.command_id), _in_transaction=True,
            )
        except SchedulerStateError as exc:
            return None, self._error(
                command, request_hash, code=ErrorCode.STATE_TRANSITION,
                category=ErrorCategory.CONFLICT, message=str(exc),
                details={"scheduler_code": exc.code},
            )
        return self._result(
            command,
            {f"run:{command.run_id}": actual + 1},
            list(result.event_ids),
        ), None

    def _cancel_run(
        self,
        command: CancelRun,
        request_hash: str,
    ) -> tuple[CommandResult | None, StructuredError | None]:
        actual, error = self._load_run_revision(command, request_hash)
        if error:
            return None, error
        try:
            result = RunSchedulerService(self.connection, now=self._now).cancel_run(
                run_id=str(command.run_id), actor=command.actor, reason=command.reason,
                causation_id=str(command.command_id),
                _in_transaction=True,
            )
        except SchedulerStateError as exc:
            return None, self._error(command, request_hash, code=ErrorCode.STATE_TRANSITION,
                                     category=ErrorCategory.CONFLICT, message=str(exc),
                                     details={"scheduler_code": exc.code})
        run_revision = actual
        if result.event_ids:
            run_revision += 1
        return self._result(
            command,
            {f"run:{command.run_id}": run_revision},
            list(result.event_ids),
        ), None

    def _load_run_revision(
        self,
        command: PauseRun | ResumeRun | CancelRun,
        request_hash: str,
    ) -> tuple[int, StructuredError | None]:
        row = self.connection.execute(
            "SELECT id FROM runs WHERE id = ?",
            (str(command.run_id),),
        ).fetchone()
        actual_row = self.connection.execute(
            "SELECT MAX(aggregate_version) FROM events "
            "WHERE aggregate_type = 'run' AND aggregate_id = ?",
            (str(command.run_id),),
        ).fetchone()
        actual = (
            int(actual_row[0])
            if row is not None and actual_row is not None and actual_row[0] is not None
            else None
        )
        if actual is None or command.expected_revision != actual:
            return 0, self._revision_error(
                command, request_hash, "run", command.run_id, actual
            )
        return actual, None

    def _locked_ids(self, result: CommandResult) -> tuple[str, str]:
        return (
            next(key.split(":", 1)[1] for key in result.affected_revisions if key.startswith("run:")),
            next(key.split(":", 1)[1] for key in result.affected_revisions if key.startswith("action:")),
        )

    def _locked_causation_id(self, action_id: str) -> str:
        row = self.connection.execute(
            "SELECT causation_id FROM events WHERE aggregate_type = 'action' "
            "AND aggregate_id = ? AND causation_id IS NOT NULL "
            "ORDER BY id LIMIT 1",
            (action_id,),
        ).fetchone()
        if row is not None:
            return str(row["causation_id"])
        return f"recovery:{action_id}"

    def prepare_locked_action(
        self,
        command: StartRun,
        result: CommandResult,
        *,
        cancel_requested: Callable[[], bool] | None = None,
    ) -> dict[str, object]:
        """Owner-lane admission/preflight/claim phase of D3-06."""
        run_id, action_id = self._locked_ids(result)
        row = self.connection.execute(
            "SELECT runs.snapshot_json, projects.data_class FROM actions "
            "JOIN runs ON runs.id = actions.run_id JOIN projects ON projects.id = runs.project_id "
            "WHERE actions.id = ?",
            (action_id,),
        ).fetchone()
        if row is None:
            raise LockedExecutorError("E_ACTION_NOT_FOUND", "StartRun Action disappeared")
        snapshot = json.loads(str(row["snapshot_json"]))
        budget = BudgetSnapshot.model_validate(snapshot["budget"])
        test_id = snapshot["fixture"]["test_id"]
        args = {"test_id": test_id}
        args_bytes = _json(args).encode("utf-8")
        material = ActionHashMaterial(
            capability=PYTHON_UNITTEST_LOCKED_CAPABILITY,
            args=args,
            args_hash=canonical_json_hash(args),
            data_class=DataClass(str(row["data_class"])),
            requested_effects=EffectScope(
                reads=("project:source", "project:tests"),
                processes=("builtin:python.unittest.locked",),
            ),
            budget=budget,
            risk_tier=RiskTier.T2,
            reversible=True,
        )
        grant_id = snapshot["fixture"]["policy_grant_id"]
        admission = CapabilityAdmissionService(
            self.connection,
            now=self._now,
            load_args_artifact=self._read_artifact_row,
        )
        try:
            admission.authorize_with_policy_grant(
                action_id=action_id,
                grant_id=str(grant_id),
                material=material,
                context=GrantMatchContext(
                    project_id=UUID(str(command.project_id)),
                    projected_cumulative_budget=budget,
                    current_concurrency=0,
                ),
                actor=self.actor,
                causation_id=str(command.command_id),
            )
        except AdmissionStateError as exc:
            raise LockedExecutorError(exc.code, str(exc)) from exc
        root = next(iter(self._resources.values())).read_root if self._resources else Path.cwd()
        executor = LockedUnittestExecutorService(
            self.connection,
            workspace_root=root,
            now=self._now,
            load_args_artifact=self._read_artifact_row,
        )
        preflight = executor._preflight_authorized_action(run_id, action_id)
        if cancel_requested is not None and cancel_requested():
            raise LockedExecutorError("E_ACTION_CANCELLED", "Action was cancelled before claim")
        try:
            started = RunSchedulerService(self.connection, now=self._now).claim_action(
                run_id=run_id,
                action_id=action_id,
                actor=self.actor,
                causation_id=str(command.command_id),
            )
        except SchedulerStateError as exc:
            raise LockedExecutorError(exc.code, str(exc)) from exc
        if started.kind != "claimed" or started.action_id != action_id:
            raise LockedExecutorError(
                "E_ACTION_NOT_CLAIMED",
                "Locked Action did not obtain a scheduler claim",
            )
        return {
            "run_id": run_id,
            "action_id": action_id,
            "preflight": preflight,
            "started_event_ids": started.event_ids,
            "workspace_root": root,
            "test_id": test_id,
            "timeout_seconds": float(preflight["timeout_seconds"]),
            "max_output_bytes": int(preflight["max_output_bytes"]),
            "max_artifact_bytes": int(preflight["max_artifact_bytes"]),
            "args_bytes": args_bytes,
            "causation_id": str(command.command_id),
        }

    def complete_locked_action(
        self,
        command: StartRun,
        context: dict[str, object],
        process: LockedProcessResult,
    ) -> None:
        """Owner-lane completion/Receipt/Artifact/Event phase."""
        self._complete_locked_context(context, process)

    def _complete_locked_context(
        self,
        context: dict[str, object],
        process: LockedProcessResult,
    ) -> None:
        output_artifact_id, publish_output_artifacts = (
            self._ensure_locked_result_artifact(context, process)
        )
        output_relation_id = self._locked_result_relation_id(
            context,
            output_artifact_id,
        )
        executor = LockedUnittestExecutorService(
            self.connection,
            workspace_root=context["workspace_root"],
            now=self._now,
            load_args_artifact=self._read_artifact_row,
        )
        executor._record_completion(
            action_id=context["action_id"],
            run_id=context["run_id"],
            actor=self.actor,
            started_event_ids=context["started_event_ids"],
            preflight=context["preflight"],
            process=process,
            after_artifact_ids=(output_artifact_id,),
            after_artifact_relation_ids=(output_relation_id,),
            settle_terminal_run=True,
            causation_id=str(context["causation_id"]),
            publish_output_artifacts=publish_output_artifacts,
        )

    def _locked_result_bytes(self, process: LockedProcessResult) -> bytes:
        content = process.stdout + process.stderr
        if content:
            return content
        status = (
            "pre_spawn_cancelled" if process.pre_spawn_cancelled else
            "runner_error" if process.runner_error else
            "termination_failed" if process.termination_failed else
            "cancelled" if process.cancelled else
            "timed_out" if process.timed_out else
            "output_truncated" if process.output_truncated else
            f"exit_code={process.exit_code}"
        )
        return f"locked_test_result={status}\n".encode("utf-8")

    def _ensure_locked_result_artifact(
        self,
        context: dict[str, object],
        process: LockedProcessResult,
    ) -> tuple[str, Callable[[], tuple[int, ...]]]:
        content = self._locked_result_bytes(process)
        max_artifact_bytes = int(context["max_artifact_bytes"])
        if len(content) > max_artifact_bytes:
            raise LockedExecutorError(
                "E_RESULT_ARTIFACT_BUDGET",
                "Locked test result exceeds the frozen Artifact budget",
            )
        digest = hashlib.sha256(content).hexdigest()
        artifact_id = str(uuid5(
            NAMESPACE_URL,
            f"{_LOCKED_RESULT_ARTIFACT_NAMESPACE}:{context['action_id']}:{digest}",
        ))
        store = self._workspace_artifact_store()
        row = self.connection.execute(
            "SELECT id, state, temp_ref, blob_hash, size, media_type "
            "FROM artifacts WHERE id = ?",
            (artifact_id,),
        ).fetchone()
        service = ArtifactCommitService(
            self.connection,
            store,
            now=self._now,
        )
        if row is None:
            staged = store.stage_bytes(content, "text/plain")
            needs_staged_record = True
        elif str(row["state"]) == "available":
            if ArtifactReader(self.connection, store).read_bytes(artifact_id) != content:
                raise LockedExecutorError(
                    "E_RESULT_ARTIFACT_MISMATCH",
                    "Locked test result Artifact bytes changed",
                )
            return artifact_id, lambda: ()
        elif str(row["state"]) == "staged" and row["temp_ref"] is not None:
            expected = (
                f"sha256:{digest}",
                len(content),
                "text/plain",
            )
            actual = (
                str(row["blob_hash"]),
                int(row["size"]),
                str(row["media_type"]),
            )
            if actual != expected:
                raise LockedExecutorError(
                    "E_RESULT_ARTIFACT_MISMATCH",
                    "Staged locked result Artifact metadata changed",
                )
            staged = StagedArtifact(
                partial_path=store.partial_path_from_temp_ref(str(row["temp_ref"])),
                temp_ref=str(row["temp_ref"]),
                blob_hash=str(row["blob_hash"]),
                size=int(row["size"]),
                media_type=str(row["media_type"]),
            )
            needs_staged_record = False
        else:
            raise LockedExecutorError(
                "E_RESULT_ARTIFACT_MISMATCH",
                "Locked test result Artifact is neither staged nor available",
            )

        def publish() -> tuple[int, ...]:
            event_ids: list[int] = []
            if needs_staged_record:
                event_ids.append(service.record_staged_in_transaction(
                    artifact_id,
                    staged,
                    retention={"kind": "d3_locked_test_result"},
                ))
            final_path = store.blob_path(staged.blob_hash)
            if needs_staged_record or staged.partial_path.exists():
                final_path = service.promote_blob(artifact_id, staged)
            else:
                store.verify_final(staged)
            published = service.publish_promoted_in_transaction(
                artifact_id,
                staged,
                final_path=final_path,
            )
            event_ids.append(published.committed_event_id)
            return tuple(event_ids)

        return artifact_id, publish

    @staticmethod
    def _locked_result_relation_id(
        context: dict[str, object],
        artifact_id: str,
    ) -> str:
        run_id = str(context["run_id"])
        return str(uuid5(
            NAMESPACE_URL,
            f"{_LOCKED_RESULT_RELATION_NAMESPACE}:{run_id}:{artifact_id}",
        ))

    def commit_spawn_fence(self, context: dict[str, object]) -> bool:
        """Durably win the claim-vs-cancel race before worker spawn."""
        run_id = str(context["run_id"])
        action_id = str(context["action_id"])
        executor = LockedUnittestExecutorService(
            self.connection,
            workspace_root=context["workspace_root"],
            now=self._now,
            load_args_artifact=self._read_artifact_row,
        )
        with executor._transaction():
            existing = self.connection.execute(
                "SELECT events.id FROM events JOIN outbox_events ON outbox_events.event_id = events.id "
                "WHERE events.aggregate_type = 'action' AND events.aggregate_id = ? "
                "AND events.type = 'action.output' "
                "AND json_extract(events.payload_json, '$.phase') = 'spawn_committed'",
                (action_id,),
            ).fetchone()
            if existing is not None:
                return True
            row = self.connection.execute(
                "SELECT runs.state AS run_state, runs.result_json AS run_result_json, "
                "actions.state AS action_state "
                "FROM runs JOIN actions ON actions.run_id = runs.id "
                "WHERE runs.id = ? AND actions.id = ?",
                (run_id, action_id),
            ).fetchone()
            try:
                run_result = json.loads(str(row["run_result_json"] or "{}")) if row is not None else {}
            except json.JSONDecodeError:
                run_result = {}
            user_paused = (
                row is not None
                and str(row["run_state"]) == "paused"
                and run_result.get("reason") == "user_paused"
            )
            if row is None or (
                str(row["run_state"]) != "running" and not user_paused
            ) or str(row["action_state"]) != "running":
                return False
            executor._append_event(
                aggregate_type="action",
                aggregate_id=action_id,
                run_id=run_id,
                action_id=action_id,
                actor=self.actor,
                event_type="action.output",
                payload={
                    "action_id": action_id,
                    "state": "running",
                    "phase": "spawn_committed",
                },
                occurred_at=self._now(),
                causation_id=str(context["causation_id"]),
            )
            return True

    def request_locked_timeout(self, command: StartRun, context: dict[str, object]) -> bool:
        """Record timeout intent without deciding the terminal outcome."""
        run_id = str(context["run_id"])
        now = self._now()
        if self.connection.in_transaction:
            raise RuntimeError("timeout intent requires an idle connection")
        with self.connection:
            updated = self.connection.execute(
                "UPDATE runs SET state = 'paused', result_json = ? "
                "WHERE id = ? AND state = 'running'",
                (_json({"reason": "timeout_requested"}), run_id),
            )
            if updated.rowcount != 1:
                return False
            version = int(self.connection.execute(
                "SELECT COALESCE(MAX(aggregate_version), 0) + 1 FROM events "
                "WHERE aggregate_type = 'run' AND aggregate_id = ?",
                (run_id,),
            ).fetchone()[0])
            self._event(
                command,
                aggregate_type="run",
                aggregate_id=UUID(run_id),
                aggregate_version=version,
                event_type="run.paused",
                payload={
                    "run_id": run_id,
                    "state": "paused",
                    "reason": "timeout_requested",
                },
                occurred_at=now,
            )
            return True

    def reconcile_stale_locked_runs(self) -> int:
        """Fail closed any spawn-committed worker left by a prior runtime.

        This is deliberately owner-lane only and treats process death as
        effect-unknown.  The executor still writes the Receipt and performs
        the exactly-once budget settlement before the Run is orphaned.
        """
        reconciled = self._reconcile_terminal_locked_runs()
        reconciled += self._reconcile_unstarted_actions_in_terminal_runs()
        reconciled += self._reconcile_pre_spawn_locked_runs()
        rows = self.connection.execute(
            "SELECT runs.id AS run_id, actions.id AS action_id, runs.snapshot_json "
            "FROM runs JOIN actions ON actions.run_id = runs.id "
            "WHERE runs.state IN ('running', 'paused') AND actions.state = 'running' "
            "AND actions.capability_id = ? "
            "AND EXISTS (SELECT 1 FROM events JOIN outbox_events "
            "ON outbox_events.event_id = events.id "
            "WHERE events.aggregate_type = 'action' "
            "AND events.aggregate_id = actions.id "
            "AND events.type = 'action.output' "
            "AND json_extract(events.payload_json, '$.phase') = 'spawn_committed')",
            (PYTHON_UNITTEST_LOCKED_CAPABILITY.id,),
        ).fetchall()
        root = next(iter(self._resources.values())).read_root if self._resources else Path.cwd()
        for row in rows:
            snapshot = json.loads(str(row["snapshot_json"]))
            run_id = str(row["run_id"])
            action_id = str(row["action_id"])
            args_bytes = _json({"test_id": snapshot["fixture"]["test_id"]}).encode("utf-8")
            executor = LockedUnittestExecutorService(
                self.connection,
                workspace_root=root,
                now=self._now,
                load_args_artifact=self._read_artifact_row,
            )
            preflight = executor._preflight_authorized_action(
                run_id, action_id, allow_running=True
            )
            started_ids = tuple(
                int(event[0])
                for event in self.connection.execute(
                    "SELECT id FROM events WHERE aggregate_type = 'action' "
                    "AND aggregate_id = ? AND type = 'action.started' ORDER BY id",
                    (action_id,),
                ).fetchall()
            )
            process = LockedProcessResult(
                exit_code=None,
                stdout=b"",
                stderr=b"",
                wall_clock_ms=0,
                runner_error=True,
                actual_effects=EffectScope(),
            )
            self._complete_locked_context(
                {
                    "run_id": run_id,
                    "action_id": action_id,
                    "preflight": preflight,
                    "started_event_ids": started_ids,
                    "workspace_root": root,
                    "test_id": snapshot["fixture"]["test_id"],
                    "timeout_seconds": float(preflight["timeout_seconds"]),
                    "max_output_bytes": int(preflight["max_output_bytes"]),
                    "max_artifact_bytes": int(preflight["max_artifact_bytes"]),
                    "args_bytes": args_bytes,
                    "causation_id": self._locked_causation_id(action_id),
                },
                process,
            )
            reconciled += 1
        return reconciled

    def _cancel_unstarted_locked_action(
        self,
        run_id: str,
        action_id: str,
        *,
        reason: str,
    ) -> bool:
        """Write one terminal Action fact when no process could have started."""
        root = next(iter(self._resources.values())).read_root if self._resources else Path.cwd()
        executor = LockedUnittestExecutorService(
            self.connection,
            workspace_root=root,
            now=self._now,
            load_args_artifact=self._read_artifact_row,
        )
        occurred_at = self._now()
        with executor._transaction():
            row = self.connection.execute(
                "SELECT state FROM actions WHERE id = ? AND run_id = ?",
                (action_id, run_id),
            ).fetchone()
            if row is None or str(row["state"]) == "cancelled":
                return False
            if str(row["state"]) not in {"proposed", "waiting_approval", "authorized"}:
                raise LockedExecutorError(
                    "E_ACTION_RECOVERY_STATE",
                    "Only an unstarted locked Action can use pre-claim recovery",
                )
            started_or_fenced = bool(self.connection.execute(
                "SELECT EXISTS(SELECT 1 FROM events WHERE aggregate_type = 'action' "
                "AND aggregate_id = ? AND (type = 'action.started' OR "
                "(type = 'action.output' "
                "AND json_extract(payload_json, '$.phase') = 'spawn_committed')))",
                (action_id,),
            ).fetchone()[0])
            if started_or_fenced:
                raise LockedExecutorError(
                    "E_ACTION_RECOVERY_FENCE",
                    "Unstarted Action recovery found a start or spawn fact",
                )
            updated = self.connection.execute(
                "UPDATE actions SET state = 'cancelled', finished_at = ? "
                "WHERE id = ? AND run_id = ? "
                "AND state IN ('proposed', 'waiting_approval', 'authorized')",
                (occurred_at, action_id, run_id),
            )
            if updated.rowcount != 1:
                raise LockedExecutorError(
                    "E_ACTION_RECOVERY_RACE",
                    "Unstarted locked Action changed during recovery",
                )
            executor._append_event(
                aggregate_type="action",
                aggregate_id=action_id,
                run_id=run_id,
                action_id=action_id,
                actor=self.actor,
                event_type="action.cancelled",
                payload={
                    "action_id": action_id,
                    "state": "cancelled",
                    "reason": reason,
                },
                occurred_at=occurred_at,
            )
            return True

    def _reconcile_unstarted_actions_in_terminal_runs(self) -> int:
        rows = self.connection.execute(
            "SELECT runs.id AS run_id, actions.id AS action_id "
            "FROM runs JOIN actions ON actions.run_id = runs.id "
            "WHERE runs.state IN ('succeeded', 'failed', 'cancelled', 'timed_out', "
            "'budget_exceeded', 'orphaned') "
            "AND actions.state IN ('proposed', 'waiting_approval', 'authorized') "
            "AND actions.capability_id = ? "
            "AND NOT EXISTS (SELECT 1 FROM actions AS other "
            "WHERE other.run_id = runs.id AND other.id <> actions.id)",
            (PYTHON_UNITTEST_LOCKED_CAPABILITY.id,),
        ).fetchall()
        return sum(
            1
            for row in rows
            if self._cancel_unstarted_locked_action(
                str(row["run_id"]),
                str(row["action_id"]),
                reason="terminal_run_recovery_before_locked_claim",
            )
        )

    def _reconcile_pre_spawn_locked_runs(self) -> int:
        """Settle restart windows that cannot have spawned a worker."""
        rows = self.connection.execute(
            "SELECT runs.id AS run_id, actions.id AS action_id, "
            "actions.state AS action_state, runs.snapshot_json "
            "FROM runs JOIN actions ON actions.run_id = runs.id "
            "WHERE runs.state IN ('running', 'paused') "
            "AND actions.state IN ('proposed', 'authorized', 'running') "
            "AND actions.capability_id = ? "
            "AND NOT EXISTS (SELECT 1 FROM actions AS other "
            "WHERE other.run_id = runs.id AND other.id <> actions.id) "
            "AND NOT EXISTS (SELECT 1 FROM events JOIN outbox_events "
            "ON outbox_events.event_id = events.id "
            "WHERE events.aggregate_type = 'action' "
            "AND events.aggregate_id = actions.id "
            "AND events.type = 'action.output' "
            "AND json_extract(events.payload_json, '$.phase') = 'spawn_committed')",
            (PYTHON_UNITTEST_LOCKED_CAPABILITY.id,),
        ).fetchall()
        root = next(iter(self._resources.values())).read_root if self._resources else Path.cwd()
        reconciled = 0
        for row in rows:
            run_id = str(row["run_id"])
            action_id = str(row["action_id"])
            action_state = str(row["action_state"])
            if action_state in {"proposed", "authorized"}:
                result = RunSchedulerService(
                    self.connection,
                    now=self._now,
                ).cancel_run(
                    run_id=run_id,
                    actor=self.actor,
                    reason="runtime_recovery_before_spawn",
                )
                if result.kind != "already_terminal":
                    reconciled += 1
                continue

            snapshot = json.loads(str(row["snapshot_json"]))
            executor = LockedUnittestExecutorService(
                self.connection,
                workspace_root=root,
                now=self._now,
                load_args_artifact=self._read_artifact_row,
            )
            preflight = executor._preflight_authorized_action(
                run_id,
                action_id,
                allow_running=True,
            )
            started_ids = tuple(
                int(event[0])
                for event in self.connection.execute(
                    "SELECT id FROM events WHERE aggregate_type = 'action' "
                    "AND aggregate_id = ? AND type = 'action.started' ORDER BY id",
                    (action_id,),
                ).fetchall()
            )
            self._complete_locked_context(
                {
                    "run_id": run_id,
                    "action_id": action_id,
                    "preflight": preflight,
                    "started_event_ids": started_ids,
                    "workspace_root": root,
                    "test_id": snapshot["fixture"]["test_id"],
                    "timeout_seconds": float(preflight["timeout_seconds"]),
                    "max_output_bytes": int(preflight["max_output_bytes"]),
                    "max_artifact_bytes": int(preflight["max_artifact_bytes"]),
                    "args_bytes": _json({
                        "test_id": snapshot["fixture"]["test_id"],
                    }).encode("utf-8"),
                    "causation_id": self._locked_causation_id(action_id),
                },
                LockedProcessResult(
                    exit_code=None,
                    stdout=b"",
                    stderr=b"",
                    wall_clock_ms=0,
                    pre_spawn_cancelled=True,
                    actual_effects=EffectScope(),
                ),
            )
            reconciled += 1
        return reconciled

    def _reconcile_terminal_locked_runs(self) -> int:
        """Repair the historical post-Action/pre-Run commit window."""
        rows = self.connection.execute(
            "SELECT runs.id AS run_id, runs.state AS run_state, runs.result_json, "
            "actions.id AS action_id, action_receipts.result AS receipt_result, "
            "(SELECT terminal.payload_json FROM events AS terminal "
            "WHERE terminal.aggregate_type = 'action' "
            "AND terminal.aggregate_id = actions.id "
            "AND terminal.type IN ('action.completed', 'action.cancelled', 'action.effect_unknown') "
            "ORDER BY terminal.id DESC LIMIT 1) AS terminal_payload_json "
            "FROM runs JOIN actions ON actions.run_id = runs.id "
            "JOIN action_receipts ON action_receipts.action_id = actions.id "
            "WHERE runs.state IN ('running', 'paused') "
            "AND actions.capability_id = ? "
            "AND actions.state IN ('succeeded', 'failed', 'cancelled', 'timed_out', 'effect_unknown') "
            "AND NOT EXISTS (SELECT 1 FROM actions AS pending WHERE pending.run_id = runs.id "
            "AND pending.state IN ('proposed', 'waiting_approval', 'authorized', 'running'))",
            (PYTHON_UNITTEST_LOCKED_CAPABILITY.id,),
        ).fetchall()
        root = next(iter(self._resources.values())).read_root if self._resources else Path.cwd()
        reconciled = 0
        for row in rows:
            run_id = str(row["run_id"])
            action_id = str(row["action_id"])
            receipt_result = str(row["receipt_result"])
            try:
                run_result = json.loads(str(row["result_json"] or "{}"))
            except json.JSONDecodeError:
                run_result = {}
            cancel_pending = (
                str(row["run_state"]) == "paused"
                and run_result.get("reason") == "cancel_requested"
            )
            try:
                terminal_payload = json.loads(str(row["terminal_payload_json"] or "{}"))
            except json.JSONDecodeError:
                terminal_payload = {}
            if receipt_result == "effect_unknown":
                next_state = (
                    "cancelled"
                    if cancel_pending
                    and terminal_payload.get("reason") == "cancelled_after_process_start"
                    else "orphaned"
                )
            else:
                next_state = {
                    "succeeded": "succeeded",
                    "failed": "failed",
                    "cancelled": "cancelled",
                    "timed_out": "timed_out",
                }.get(receipt_result)
            if next_state is None:
                raise LockedExecutorError(
                    "E_RUN_RESULT_INVALID",
                    "Persisted locked Receipt has an unsupported result",
                )
            event_type = {
                "succeeded": "run.succeeded",
                "failed": "run.failed",
                "cancelled": "run.cancelled",
                "timed_out": "run.timed_out",
                "orphaned": "run.orphaned",
            }[next_state]
            executor = LockedUnittestExecutorService(
                self.connection,
                workspace_root=root,
                now=self._now,
                load_args_artifact=self._read_artifact_row,
            )
            now = self._now()
            with executor._transaction():
                updated = self.connection.execute(
                    "UPDATE runs SET state = ?, finished_at = ?, result_json = ? "
                    "WHERE id = ? AND state IN ('running', 'paused')",
                    (
                        next_state,
                        now,
                        _json({
                            "state": next_state,
                            "result": receipt_result,
                            "reason": "terminal_action_reconciliation",
                        }),
                        run_id,
                    ),
                )
                if updated.rowcount != 1:
                    continue
                executor._append_event(
                    aggregate_type="run",
                    aggregate_id=run_id,
                    run_id=run_id,
                    action_id=action_id,
                    actor=self.actor,
                    event_type=event_type,
                    payload={
                        "run_id": run_id,
                        "state": next_state,
                        "result": receipt_result,
                        "reason": "terminal_action_reconciliation",
                    },
                    occurred_at=now,
                )
                reconciled += 1
        return reconciled

    def _execute_locked_action(self, command: StartRun, result: CommandResult) -> None:
        """Synchronous compatibility path; runtime uses the phased bridge."""
        context = self.prepare_locked_action(command, result)
        if self.commit_spawn_fence(context):
            process = default_locked_unittest_runner(
                context["test_id"],
                context["workspace_root"],
                context["timeout_seconds"],
                context["max_output_bytes"],
                lambda: False,
            )
        else:
            process = LockedProcessResult(
                exit_code=None,
                stdout=b"",
                stderr=b"",
                wall_clock_ms=0,
                pre_spawn_cancelled=True,
                actual_effects=EffectScope(),
            )
        self.complete_locked_action(command, context, process)

    def reconcile_locked_failure(
        self,
        command: StartRun,
        result: CommandResult,
        reason: str,
    ) -> None:
        """Owner-lane fail-closed recovery for a deferred bridge failure."""
        run_id, action_id = self._locked_ids(result)
        row = self.connection.execute(
            "SELECT actions.state AS action_state, runs.state AS run_state "
            "FROM actions JOIN runs ON runs.id = actions.run_id WHERE actions.id = ?",
            (action_id,),
        ).fetchone()
        if row is None or str(row["action_state"]) in {"succeeded", "failed", "cancelled", "timed_out", "effect_unknown"}:
            return
        action_state = str(row["action_state"])
        run_state = str(row["run_state"])
        if action_state in {"proposed", "waiting_approval", "authorized"}:
            if run_state in {"running", "paused"}:
                RunSchedulerService(
                    self.connection,
                    now=self._now,
                ).cancel_run(
                    run_id=run_id,
                    actor=self.actor,
                    reason="runtime_bridge_failure_before_claim",
                )
            else:
                self._cancel_unstarted_locked_action(
                    run_id,
                    action_id,
                    reason="run_terminal_before_locked_claim",
                )
            return
        if action_state != "running":
            return

        snapshot_row = self.connection.execute(
            "SELECT runs.snapshot_json FROM actions "
            "JOIN runs ON runs.id = actions.run_id WHERE actions.id = ?",
            (action_id,),
        ).fetchone()
        if snapshot_row is None:
            return
        snapshot = json.loads(str(snapshot_row["snapshot_json"]))
        root = next(iter(self._resources.values())).read_root if self._resources else Path.cwd()
        executor = LockedUnittestExecutorService(
            self.connection,
            workspace_root=root,
            now=self._now,
            load_args_artifact=self._read_artifact_row,
        )
        preflight = executor._preflight_authorized_action(
            run_id,
            action_id,
            allow_running=True,
        )
        started_ids = tuple(
            int(event[0])
            for event in self.connection.execute(
                "SELECT id FROM events WHERE aggregate_type = 'action' "
                "AND aggregate_id = ? AND type = 'action.started' ORDER BY id",
                (action_id,),
            ).fetchall()
        )
        spawn_committed = bool(self.connection.execute(
            "SELECT EXISTS(SELECT 1 FROM events JOIN outbox_events "
            "ON outbox_events.event_id = events.id "
            "WHERE events.aggregate_type = 'action' AND events.aggregate_id = ? "
            "AND events.type = 'action.output' "
            "AND json_extract(events.payload_json, '$.phase') = 'spawn_committed')",
            (action_id,),
        ).fetchone()[0])
        self.complete_locked_action(
            command,
            {
                "run_id": run_id,
                "action_id": action_id,
                "preflight": preflight,
                "started_event_ids": started_ids,
                "workspace_root": root,
                "test_id": snapshot["fixture"]["test_id"],
                "timeout_seconds": float(preflight["timeout_seconds"]),
                "max_output_bytes": int(preflight["max_output_bytes"]),
                "max_artifact_bytes": int(preflight["max_artifact_bytes"]),
                "args_bytes": _json({
                    "test_id": snapshot["fixture"]["test_id"],
                }).encode("utf-8"),
                "causation_id": self._locked_causation_id(action_id),
            },
            LockedProcessResult(
                exit_code=None,
                stdout=b"",
                stderr=b"",
                wall_clock_ms=0,
                pre_spawn_cancelled=not spawn_committed,
                runner_error=spawn_committed,
                actual_effects=EffectScope(),
            ),
        )

    def _binding(self, command: CommandBase, request_hash: str) -> dict[str, object]:
        return {
            "command_id": str(command.command_id),
            "command_type": command.type,
            "request_hash": request_hash,
        }

    def _error(
        self,
        command: CommandBase,
        request_hash: str,
        *,
        code: ErrorCode,
        category: ErrorCategory,
        message: str,
        details: dict[str, object],
        retryable: bool = False,
        suggested: tuple[str, ...] = (),
    ) -> StructuredError:
        return StructuredError(
            code=code,
            category=category,
            message=message,
            retryable=retryable,
            details={"binding": self._binding(command, request_hash), **details},
            data_safe=True,
            suggested_actions=suggested,
        )

    def _revision_error(
        self,
        command: CommandBase,
        request_hash: str,
        aggregate_type: str,
        aggregate_id: UUID,
        actual: int | None,
    ) -> StructuredError:
        return self._error(
            command,
            request_hash,
            code=ErrorCode.REVISION_CONFLICT,
            category=ErrorCategory.CONFLICT,
            message=f"{aggregate_type} revision conflict",
            retryable=True,
            details={
                "aggregate_type": aggregate_type,
                "aggregate_id": str(aggregate_id),
                "expected_revision": command.expected_revision,
                "actual_revision": actual,
            },
            suggested=("Reload canonical state and retry with a new command_id.",),
        )

    def _load_revisioned(
        self,
        command: CommandBase,
        request_hash: str,
        *,
        table: str,
        aggregate_type: str,
        aggregate_id: UUID,
        columns: str,
    ) -> tuple[sqlite3.Row | None, StructuredError | None]:
        if table not in {"workspaces", "projects", "inquiries", "resources", "locators", "claims"}:
            raise RuntimeError("unregistered revision lookup")
        row = self.connection.execute(
            f"SELECT {columns}, revision FROM {table} WHERE id = ?",  # noqa: S608 - closed table registry
            (str(aggregate_id),),
        ).fetchone()
        actual = int(row["revision"]) if row is not None else None
        if row is None or command.expected_revision != actual:
            return None, self._revision_error(
                command, request_hash, aggregate_type, aggregate_id, actual
            )
        return row, None

    def _event(
        self,
        command: CommandBase,
        *,
        aggregate_type: str,
        aggregate_id: UUID,
        aggregate_version: int,
        event_type: str,
        payload: dict[str, object],
        occurred_at: str,
    ) -> int:
        cursor = self.connection.execute(
            "INSERT INTO events(aggregate_type, aggregate_id, aggregate_version, actor_json, "
            "causation_id, type, payload_json, occurred_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                aggregate_type,
                str(aggregate_id),
                aggregate_version,
                _actor_json(command.actor),
                str(command.command_id),
                event_type,
                _json(payload),
                occurred_at,
            ),
        )
        event_id = int(cursor.lastrowid)
        self.connection.execute("INSERT INTO outbox_events(event_id) VALUES (?)", (event_id,))
        return event_id

    @staticmethod
    def _result(
        command: CommandBase,
        revisions: dict[str, int],
        events: list[int],
    ) -> CommandResult:
        return CommandResult(
            command_id=command.command_id,
            status=CommandStatus.ACCEPTED,
            affected_revisions=revisions,
            event_ids=tuple(events),
        )

    def _create_project(self, command: CreateProject, request_hash: str):
        row, error = self._load_revisioned(
            command,
            request_hash,
            table="workspaces",
            aggregate_type="workspace",
            aggregate_id=command.workspace_id,
            columns="status",
        )
        if error:
            return None, error
        if row["status"] != "active":
            return None, self._state_error(command, request_hash, "workspace", command.workspace_id, row["status"])
        entity_id, now = self._new_id(), self._now()
        self.connection.execute(
            "INSERT INTO projects(id, workspace_id, title, status, data_class, revision, created_at) "
            "VALUES (?, ?, ?, 'active', ?, 1, ?)",
            (str(entity_id), str(command.workspace_id), command.title, command.data_class.value, now),
        )
        event = self._event(
            command,
            aggregate_type="project",
            aggregate_id=entity_id,
            aggregate_version=1,
            event_type="project.created",
            payload={"project_id": str(entity_id), "workspace_id": str(command.workspace_id), "status": "active"},
            occurred_at=now,
        )
        return self._result(command, {f"project:{entity_id}": 1}, [event]), None

    def _create_inquiry(self, command: CreateInquiry, request_hash: str):
        row, error = self._load_revisioned(
            command,
            request_hash,
            table="projects",
            aggregate_type="project",
            aggregate_id=command.project_id,
            columns="status",
        )
        if error:
            return None, error
        if row["status"] != "active":
            return None, self._state_error(command, request_hash, "project", command.project_id, row["status"])
        entity_id, now = self._new_id(), self._now()
        self.connection.execute(
            "INSERT INTO inquiries(id, project_id, question, acceptance, status, revision, created_at) "
            "VALUES (?, ?, ?, ?, 'draft', 1, ?)",
            (str(entity_id), str(command.project_id), command.question, command.acceptance, now),
        )
        event = self._event(
            command,
            aggregate_type="inquiry",
            aggregate_id=entity_id,
            aggregate_version=1,
            event_type="inquiry.created",
            payload={"inquiry_id": str(entity_id), "project_id": str(command.project_id), "status": "draft"},
            occurred_at=now,
        )
        return self._result(command, {f"inquiry:{entity_id}": 1}, [event]), None

    def _propose_plan(self, command: ProposePlan, request_hash: str):
        row, error = self._load_revisioned(
            command,
            request_hash,
            table="inquiries",
            aggregate_type="inquiry",
            aggregate_id=command.inquiry_id,
            columns="status",
        )
        if error:
            return None, error
        if row["status"] in {"cancelled", "closed", "decided"}:
            return None, self._state_error(command, request_hash, "inquiry", command.inquiry_id, row["status"])
        entity_id, now = self._new_id(), self._now()
        self.connection.execute(
            "INSERT INTO plans(id, inquiry_id, revision, status, steps_json, policy_json, budget_json, created_at) "
            "VALUES (?, ?, 1, 'proposed', ?, ?, ?, ?)",
            (
                str(entity_id),
                str(command.inquiry_id),
                _json([step.model_dump(mode="json") for step in command.steps]),
                _json(command.policy),
                _json(command.budget.model_dump(mode="json")),
                now,
            ),
        )
        event = self._event(
            command,
            aggregate_type="plan",
            aggregate_id=entity_id,
            aggregate_version=1,
            event_type="plan.proposed",
            payload={"plan_id": str(entity_id), "inquiry_id": str(command.inquiry_id), "revision": 1, "status": "proposed"},
            occurred_at=now,
        )
        return self._result(command, {f"plan:{entity_id}": 1}, [event]), None

    def _descriptor(self, command: RegisterResource) -> FrozenResourceDescriptor | None:
        descriptor = self._resources.get(command.logical_ref)
        if descriptor is None:
            return None
        if (
            command.kind != "local_file"
            or command.media_type != descriptor.media_type
            or command.data_class != descriptor.data_class
            or command.license != descriptor.license
        ):
            return None
        return descriptor

    def _read_descriptor(self, descriptor: FrozenResourceDescriptor) -> bytes:
        root = descriptor.read_root.absolute()
        if _path_is_link_or_reparse(root):
            raise FrozenResourceError("read_root_reparse")
        try:
            resolved_root = root.resolve(strict=True)
        except OSError as exc:
            raise FrozenResourceError("read_root_unavailable") from exc
        if not resolved_root.is_dir() or _path_is_link_or_reparse(resolved_root):
            raise FrozenResourceError("read_root_invalid")
        target = resolved_root
        for part in PurePosixPath(descriptor.logical_ref).parts:
            target /= part
            if _path_is_link_or_reparse(target):
                raise FrozenResourceError("resource_reparse")
        try:
            target = target.resolve(strict=True)
        except OSError as exc:
            raise FrozenResourceError("resource_unavailable") from exc
        if not target.is_relative_to(resolved_root):
            raise FrozenResourceError("resource_path_escape")
        try:
            before = target.lstat()
            if not stat.S_ISREG(before.st_mode):
                raise FrozenResourceError("resource_not_regular")
            content = target.read_bytes()
            after = target.lstat()
        except FrozenResourceError:
            raise
        except OSError as exc:
            raise FrozenResourceError("resource_unavailable") from exc
        identity = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns)
        if identity(before) != identity(after) or _path_is_link_or_reparse(target):
            raise FrozenResourceError("resource_changed_during_read")
        return content

    def _register_resource(self, command: RegisterResource, request_hash: str):
        row, error = self._load_revisioned(
            command,
            request_hash,
            table="projects",
            aggregate_type="project",
            aggregate_id=command.project_id,
            columns="status",
        )
        if error:
            return None, error
        if row["status"] != "active":
            return None, self._state_error(command, request_hash, "project", command.project_id, row["status"])
        descriptor = self._descriptor(command)
        if descriptor is None:
            return None, self._locator_error(command, request_hash, "descriptor_not_allowlisted")
        try:
            content = self._read_descriptor(descriptor)
        except FrozenResourceError as exc:
            return None, self._locator_error(command, request_hash, exc.reason)
        content_hash = f"sha256:{hashlib.sha256(content).hexdigest()}"
        entity_id, now = self._new_id(), self._now()
        self.connection.execute(
            "INSERT INTO resources(id, project_id, kind, logical_ref, content_hash, media_type, "
            "data_class, license, captured_at, status, revision) VALUES (?, ?, 'local_file', ?, ?, ?, ?, ?, ?, 'available', 1)",
            (
                str(entity_id), str(command.project_id), descriptor.logical_ref,
                content_hash, descriptor.media_type, descriptor.data_class.value,
                descriptor.license, now,
            ),
        )
        event = self._event(
            command,
            aggregate_type="resource",
            aggregate_id=entity_id,
            aggregate_version=1,
            event_type="resource.registered",
            payload={
                "resource_id": str(entity_id), "project_id": str(command.project_id),
                "status": "available", "content_hash": content_hash,
                "descriptor_id": descriptor.descriptor_id, "verification": "raw-bytes-sha256-v1",
            },
            occurred_at=now,
        )
        return self._result(command, {f"resource:{entity_id}": 1}, [event]), None

    def _create_locator(self, command: CreateLocator, request_hash: str):
        row, error = self._load_revisioned(
            command,
            request_hash,
            table="resources",
            aggregate_type="resource",
            aggregate_id=command.resource_id,
            columns="project_id, logical_ref, content_hash, media_type, data_class, license, status",
        )
        if error:
            return None, error
        if row["status"] != "available":
            return None, self._state_error(command, request_hash, "resource", command.resource_id, row["status"])
        descriptor = self._resources.get(str(row["logical_ref"]))
        if descriptor is None:
            return None, self._locator_error(command, request_hash, "descriptor_not_allowlisted")
        try:
            content = self._read_descriptor(descriptor)
            text = content.decode("utf-8").replace("\r\n", "\n")
        except UnicodeDecodeError:
            return None, self._locator_error(command, request_hash, "resource_not_utf8")
        except FrozenResourceError as exc:
            return None, self._locator_error(command, request_hash, exc.reason)
        content_hash = f"sha256:{hashlib.sha256(content).hexdigest()}"
        coordinates = command.coordinates
        if (
            command.locator_type != "local_file"
            or coordinates.kind != "local_file"
            or coordinates.logical_path != descriptor.logical_ref
            or coordinates.artifact_hash != content_hash
            or str(row["content_hash"]) != content_hash
            or coordinates.line_span is None
            or coordinates.byte_span is not None
        ):
            return None, self._locator_error(command, request_hash, "locator_material_mismatch")
        lines = text.split("\n")
        if coordinates.line_span.end_line > len(lines):
            return None, self._locator_error(command, request_hash, "line_span_out_of_range")
        quote = "\n".join(
            lines[coordinates.line_span.start_line - 1 : coordinates.line_span.end_line]
        ).encode("utf-8")
        quote_hash = f"sha256:{hashlib.sha256(quote).hexdigest()}"
        if command.quote_hash != quote_hash:
            return None, self._locator_error(command, request_hash, "quote_hash_mismatch")
        entity_id, now = self._new_id(), self._now()
        self.connection.execute(
            "INSERT INTO locators(id, resource_id, locator_type, coordinates_json, quote_hash, status, revision) "
            "VALUES (?, ?, 'local_file', ?, ?, 'valid', 1)",
            (str(entity_id), str(command.resource_id), _json(coordinates.model_dump(mode="json")), quote_hash),
        )
        event = self._event(
            command,
            aggregate_type="locator",
            aggregate_id=entity_id,
            aggregate_version=1,
            event_type="locator.created",
            payload={
                "locator_id": str(entity_id), "resource_id": str(command.resource_id),
                "status": "valid", "resource_hash": content_hash,
                "line_span": coordinates.line_span.model_dump(mode="json"),
                "quote_hash": quote_hash, "verification": "utf8-lf-lines-sha256-v1",
            },
            occurred_at=now,
        )
        return self._result(command, {f"locator:{entity_id}": 1}, [event]), None

    def _create_claim(self, command: CreateClaim, request_hash: str):
        row, error = self._active_inquiry(command, request_hash, command.inquiry_id)
        if error:
            return None, error
        entity_id, now = self._new_id(), self._now()
        self.connection.execute(
            "INSERT INTO claims(id, inquiry_id, statement, status, revision, created_by_json) "
            "VALUES (?, ?, ?, 'draft', 1, ?)",
            (str(entity_id), str(command.inquiry_id), command.statement, _actor_json(command.actor)),
        )
        event = self._event(
            command,
            aggregate_type="claim", aggregate_id=entity_id, aggregate_version=1,
            event_type="claim.created",
            payload={"claim_id": str(entity_id), "inquiry_id": str(command.inquiry_id), "status": "draft"},
            occurred_at=now,
        )
        return self._result(command, {f"claim:{entity_id}": 1}, [event]), None

    def _create_hypothesis(self, command: CreateHypothesis, request_hash: str):
        _row, error = self._active_inquiry(command, request_hash, command.inquiry_id)
        if error:
            return None, error
        entity_id, now = self._new_id(), self._now()
        self.connection.execute(
            "INSERT INTO hypotheses(id, inquiry_id, statement, falsification_criteria, status, created_by_json) "
            "VALUES (?, ?, ?, ?, 'proposed', ?)",
            (
                str(entity_id), str(command.inquiry_id), command.statement,
                command.falsification_criteria, _actor_json(command.actor),
            ),
        )
        event = self._event(
            command,
            aggregate_type="hypothesis", aggregate_id=entity_id, aggregate_version=1,
            event_type="hypothesis.created",
            payload={"hypothesis_id": str(entity_id), "inquiry_id": str(command.inquiry_id), "status": "proposed"},
            occurred_at=now,
        )
        return self._result(command, {f"hypothesis:{entity_id}": 1}, [event]), None

    def _active_inquiry(self, command: CommandBase, request_hash: str, inquiry_id: UUID):
        row, error = self._load_revisioned(
            command,
            request_hash,
            table="inquiries",
            aggregate_type="inquiry",
            aggregate_id=inquiry_id,
            columns="project_id, status",
        )
        if error:
            return None, error
        if row["status"] in {"cancelled", "closed"}:
            return None, self._state_error(command, request_hash, "inquiry", inquiry_id, row["status"])
        return row, None

    def _attach_evidence(self, command: AttachEvidence, request_hash: str):
        locator, error = self._load_revisioned(
            command,
            request_hash,
            table="locators",
            aggregate_type="locator",
            aggregate_id=command.locator_id,
            columns="resource_id, quote_hash, status",
        )
        if error:
            return None, error
        inquiry = self.connection.execute(
            "SELECT project_id, status FROM inquiries WHERE id = ?",
            (str(command.inquiry_id),),
        ).fetchone()
        resource = self.connection.execute(
            "SELECT project_id, status FROM resources WHERE id = ?",
            (str(locator["resource_id"]),),
        ).fetchone()
        if inquiry is None or resource is None:
            return None, self._scope_error(command, request_hash, "missing_scope_endpoint")
        if (
            inquiry["status"] in {"cancelled", "closed"}
            or locator["status"] != "valid"
            or resource["status"] != "available"
        ):
            return None, self._state_error(command, request_hash, "provenance", command.locator_id, "not_valid")
        if inquiry["project_id"] != resource["project_id"]:
            return None, self._scope_error(command, request_hash, "resource_inquiry_project_mismatch")
        if locator["quote_hash"] != command.excerpt_hash:
            return None, self._locator_error(command, request_hash, "excerpt_hash_mismatch")
        duplicate = self.connection.execute(
            "SELECT id FROM evidence WHERE inquiry_id = ? AND locator_id = ? AND direction = ? "
            "AND excerpt_hash = ? AND status <> 'tombstoned'",
            (str(command.inquiry_id), str(command.locator_id), command.direction.value, command.excerpt_hash),
        ).fetchone()
        if duplicate is not None:
            return None, self._scope_error(command, request_hash, "duplicate_evidence")
        evidence_id, relation_id, now = self._new_id(), self._new_id(), self._now()
        source = RelationEndpoint(
            object_type="resource", object_id=UUID(str(locator["resource_id"])),
            project_id=UUID(str(resource["project_id"])),
        )
        target = RelationEndpoint(
            object_type="evidence", object_id=evidence_id,
            project_id=UUID(str(inquiry["project_id"])), inquiry_id=command.inquiry_id,
            resource_id=UUID(str(locator["resource_id"])), direction=command.direction.value,
        )
        validate_relation(RelationType.RESOURCE_CONTAINS_EVIDENCE.value, source, target)
        self.connection.execute(
            "INSERT INTO evidence(id, inquiry_id, locator_id, direction, excerpt_hash, status, created_by_json) "
            "VALUES (?, ?, ?, ?, ?, 'valid', ?)",
            (
                str(evidence_id), str(command.inquiry_id), str(command.locator_id),
                command.direction.value, command.excerpt_hash, _actor_json(command.actor),
            ),
        )
        self._insert_relation(
            relation_id, RelationType.RESOURCE_CONTAINS_EVIDENCE.value,
            "resource", UUID(str(locator["resource_id"])), "evidence", evidence_id,
            command.actor,
        )
        events = [
            self._event(
                command,
                aggregate_type="evidence", aggregate_id=evidence_id, aggregate_version=1,
                event_type="evidence.attached",
                payload={
                    "evidence_id": str(evidence_id), "inquiry_id": str(command.inquiry_id),
                    "locator_id": str(command.locator_id), "status": "valid",
                    "excerpt_hash": command.excerpt_hash, "verification": "locator-quote-match-v1",
                },
                occurred_at=now,
            ),
            self._relation_event(command, relation_id, RelationType.RESOURCE_CONTAINS_EVIDENCE.value, source.object_id, evidence_id, now),
        ]
        return self._result(
            command,
            {f"evidence:{evidence_id}": 1, f"relation:{relation_id}": 1},
            events,
        ), None

    def _create_relation(self, command: CreateRelation, request_hash: str):
        claim, error = self._load_revisioned(
            command,
            request_hash,
            table="claims",
            aggregate_type="claim",
            aggregate_id=command.target_id,
            columns="inquiry_id, status",
        )
        if error:
            return None, error
        evidence = self.connection.execute(
            "SELECT inquiry_id, direction, status FROM evidence WHERE id = ?",
            (str(command.source_id),),
        ).fetchone()
        if evidence is None:
            return None, self._scope_error(command, request_hash, "evidence_missing")
        if evidence["inquiry_id"] != claim["inquiry_id"]:
            return None, self._scope_error(command, request_hash, "evidence_claim_inquiry_mismatch")
        project = self.connection.execute(
            "SELECT project_id FROM inquiries WHERE id = ?",
            (claim["inquiry_id"],),
        ).fetchone()
        if project is None:
            return None, self._scope_error(command, request_hash, "inquiry_missing")
        if evidence["status"] != "valid":
            return None, self._state_error(command, request_hash, "evidence", command.source_id, evidence["status"])
        relation_type = command.relation_type.value
        duplicate = self.connection.execute(
            "SELECT id FROM relations WHERE type = ? AND source_type = 'evidence' AND source_id = ? "
            "AND target_type = 'claim' AND target_id = ? AND status = 'active'",
            (relation_type, str(command.source_id), str(command.target_id)),
        ).fetchone()
        if duplicate is not None:
            return None, self._scope_error(command, request_hash, "duplicate_active_relation")
        context = RelationValidationContext(
            outgoing_count=int(self.connection.execute(
                "SELECT COUNT(*) FROM relations WHERE type = ? AND source_id = ? AND status = 'active'",
                (relation_type, str(command.source_id)),
            ).fetchone()[0]),
            incoming_count=int(self.connection.execute(
                "SELECT COUNT(*) FROM relations WHERE type = ? AND target_id = ? AND status = 'active'",
                (relation_type, str(command.target_id)),
            ).fetchone()[0]),
        )
        source = RelationEndpoint(
            object_type="evidence", object_id=command.source_id,
            project_id=UUID(str(project["project_id"])), inquiry_id=UUID(str(evidence["inquiry_id"])),
            direction=str(evidence["direction"]),
        )
        target = RelationEndpoint(
            object_type="claim", object_id=command.target_id,
            project_id=UUID(str(project["project_id"])), inquiry_id=UUID(str(claim["inquiry_id"])),
        )
        try:
            validate_relation(relation_type, source, target, context)
        except ValueError:
            return None, self._scope_error(command, request_hash, "relation_registry_rejected")
        relation_id, now = self._new_id(), self._now()
        self._insert_relation(
            relation_id, relation_type, "evidence", command.source_id,
            "claim", command.target_id, command.actor,
        )
        event = self._relation_event(command, relation_id, relation_type, command.source_id, command.target_id, now)
        return self._result(command, {f"relation:{relation_id}": 1}, [event]), None

    def _draft_finding(self, command: DraftFinding, request_hash: str):
        inquiry, error = self._active_inquiry(command, request_hash, command.inquiry_id)
        if error:
            return None, error
        evidence_ids = tuple(sorted(command.evidence_ids, key=str))
        for evidence_id in evidence_ids:
            row = self.connection.execute(
                "SELECT inquiry_id, status FROM evidence WHERE id = ?",
                (str(evidence_id),),
            ).fetchone()
            if row is None or row["inquiry_id"] != str(command.inquiry_id):
                return None, self._scope_error(command, request_hash, "finding_evidence_scope")
            if row["status"] != "valid":
                return None, self._state_error(command, request_hash, "evidence", evidence_id, row["status"])
        producer = command.terminal_run_ids[0] if command.terminal_run_ids else None
        run = None
        if producer is not None:
            run = self.connection.execute(
                "SELECT project_id, inquiry_id, state FROM runs WHERE id = ?",
                (str(producer),),
            ).fetchone()
            if (
                run is None
                or run["project_id"] != inquiry["project_id"]
                or run["inquiry_id"] != str(command.inquiry_id)
            ):
                return None, self._scope_error(command, request_hash, "finding_run_scope")
            if run["state"] not in TERMINAL_RUN_STATES:
                return None, self._state_error(command, request_hash, "run", producer, run["state"])
        finding_id, now = self._new_id(), self._now()
        self.connection.execute(
            "INSERT INTO findings(id, inquiry_id, statement, status, confidence_basis, "
            "evidence_ids_json, producer_run_id, revision) VALUES (?, ?, ?, 'draft', ?, ?, ?, 1)",
            (
                str(finding_id), str(command.inquiry_id), command.statement,
                command.confidence_basis, _json([str(item) for item in evidence_ids]),
                str(producer) if producer is not None else None,
            ),
        )
        events = [
            self._event(
                command,
                aggregate_type="finding", aggregate_id=finding_id, aggregate_version=1,
                event_type="finding.drafted",
                payload={
                    "finding_id": str(finding_id), "inquiry_id": str(command.inquiry_id),
                    "status": "draft", "evidence_ids": [str(item) for item in evidence_ids],
                    "producer_run_id": str(producer) if producer is not None else None,
                },
                occurred_at=now,
            )
        ]
        revisions = {f"finding:{finding_id}": 1}
        if producer is not None:
            relation_id = self._new_id()
            source = RelationEndpoint(
                object_type="run", object_id=producer,
                project_id=UUID(str(run["project_id"])), inquiry_id=UUID(str(run["inquiry_id"])),
                state=str(run["state"]),
            )
            target = RelationEndpoint(
                object_type="finding", object_id=finding_id,
                project_id=UUID(str(inquiry["project_id"])), inquiry_id=command.inquiry_id,
                producer_run_id=producer,
            )
            validate_relation(RelationType.RUN_PRODUCES_FINDING.value, source, target)
            self._insert_relation(
                relation_id, RelationType.RUN_PRODUCES_FINDING.value,
                "run", producer, "finding", finding_id, command.actor,
                producer_run_id=producer,
            )
            events.append(self._relation_event(
                command, relation_id, RelationType.RUN_PRODUCES_FINDING.value,
                producer, finding_id, now,
            ))
            revisions[f"relation:{relation_id}"] = 1
        return self._result(command, revisions, events), None

    def _insert_relation(
        self,
        relation_id: UUID,
        relation_type: str,
        source_type: str,
        source_id: UUID,
        target_type: str,
        target_id: UUID,
        actor: ActorRef,
        *,
        producer_run_id: UUID | None = None,
    ) -> None:
        self.connection.execute(
            "INSERT INTO relations(id, type, source_type, source_id, target_type, target_id, "
            "producer_run_id, created_by_json, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')",
            (
                str(relation_id), relation_type, source_type, str(source_id),
                target_type, str(target_id),
                str(producer_run_id) if producer_run_id is not None else None,
                _actor_json(actor),
            ),
        )

    def _relation_event(
        self,
        command: CommandBase,
        relation_id: UUID,
        relation_type: str,
        source_id: UUID,
        target_id: UUID,
        now: str,
    ) -> int:
        return self._event(
            command,
            aggregate_type="relation", aggregate_id=relation_id, aggregate_version=1,
            event_type="relation.created",
            payload={
                "relation_id": str(relation_id), "relation_type": relation_type,
                "source_id": str(source_id), "target_id": str(target_id), "status": "active",
            },
            occurred_at=now,
        )

    def _state_error(
        self, command: CommandBase, request_hash: str,
        object_type: str, object_id: UUID, state: str,
    ) -> StructuredError:
        return self._error(
            command, request_hash,
            code=ErrorCode.STATE_TRANSITION, category=ErrorCategory.CONFLICT,
            message=f"{object_type} state does not allow this Command",
            details={"object_type": object_type, "object_id": str(object_id), "state": state},
        )

    def _scope_error(self, command: CommandBase, request_hash: str, reason: str) -> StructuredError:
        return self._error(
            command, request_hash,
            code=ErrorCode.RELATION_INVALID, category=ErrorCategory.CONFLICT,
            message="Command scope or cardinality is invalid",
            details={"reason": reason},
        )

    def _locator_error(self, command: CommandBase, request_hash: str, reason: str) -> StructuredError:
        return self._error(
            command, request_hash,
            code=ErrorCode.LOCATOR_INVALID, category=ErrorCategory.INPUT,
            message="Frozen Resource or Locator validation failed",
            details={"reason": reason},
        )

    def _validate_stored_result(self, command: CommandBase, stored: CommandResult) -> None:
        if isinstance(command, (PauseRun, ResumeRun, CancelRun)):
            if (
                stored.command_id != command.command_id
                or stored.status != CommandStatus.ACCEPTED
                or not stored.event_ids
                or len(set(stored.event_ids)) != len(stored.event_ids)
            ):
                raise RuntimeError("stored Run control result is not bound")
            rows = self.connection.execute(
                "SELECT aggregate_type, aggregate_id, aggregate_version, type, "
                "causation_id, actor_json FROM events WHERE id IN (%s)"
                % ",".join("?" for _ in stored.event_ids),
                tuple(stored.event_ids),
            ).fetchall()
            run_rows = [
                row
                for row in rows
                if row["aggregate_type"] == "run"
                and row["aggregate_id"] == str(command.run_id)
            ]
            if (
                len(rows) != len(stored.event_ids)
                or len(run_rows) != 1
                or any(row["causation_id"] != str(command.command_id) for row in rows)
                or any(row["actor_json"] != _actor_json(command.actor) for row in rows)
                or any(not (str(row["type"]).startswith("run.") or str(row["type"]).startswith("action.")) for row in rows)
                or dict(stored.affected_revisions) != {
                    f"run:{command.run_id}": int(run_rows[0]["aggregate_version"])
                }
            ):
                raise RuntimeError("stored Run control events are not bound")
            return
        expected_facts = {
            "CreateProject": (("project", "project.created"),),
            "CreateInquiry": (("inquiry", "inquiry.created"),),
            "ProposePlan": (("plan", "plan.proposed"),),
            "RegisterResource": (("resource", "resource.registered"),),
            "CreateLocator": (("locator", "locator.created"),),
            "CreateClaim": (("claim", "claim.created"),),
            "AttachEvidence": (("evidence", "evidence.attached"), ("relation", "relation.created")),
            "CreateHypothesis": (("hypothesis", "hypothesis.created"),),
            "CreateRelation": (("relation", "relation.created"),),
            "DraftFinding": (
                (("finding", "finding.drafted"), ("relation", "relation.created"))
                if isinstance(command, DraftFinding) and command.terminal_run_ids
                else (("finding", "finding.drafted"),)
            ),
            "StartRun": (
                (("run", "run.created"), ("action", "action.proposed"), ("relation", "relation.created"))
                if isinstance(command, StartRun) and command.retry_of_run_id is not None
                else (("run", "run.created"), ("action", "action.proposed"))
            ),
        }[command.type]
        if (
            stored.command_id != command.command_id
            or stored.status != CommandStatus.ACCEPTED
            or len(stored.event_ids) != len(expected_facts)
            or len(set(stored.event_ids)) != len(stored.event_ids)
        ):
            raise RuntimeError("stored journey CommandResult is not bound")
        revisions: dict[str, int] = {}
        for event_id, (aggregate_type, event_type) in zip(
            stored.event_ids, expected_facts, strict=True
        ):
            row = self.connection.execute(
                "SELECT event.aggregate_type, event.aggregate_id, event.aggregate_version, "
                "event.type, event.causation_id, event.actor_json, event.payload_json, "
                "outbox.event_id AS outbox_id "
                "FROM events AS event LEFT JOIN outbox_events AS outbox ON outbox.event_id = event.id "
                "WHERE event.id = ?",
                (event_id,),
            ).fetchone()
            if (
                row is None
                or row["aggregate_type"] != aggregate_type
                or row["type"] != event_type
                or row["causation_id"] != str(command.command_id)
                or row["actor_json"] != _actor_json(command.actor)
                or row["outbox_id"] != event_id
                or not self._domain_row_exists(row)
            ):
                raise RuntimeError("stored journey CommandResult Event/outbox is not bound")
            self._validate_event_payload(command, row)
            revisions[f"{row['aggregate_type']}:{row['aggregate_id']}"] = int(row["aggregate_version"])
        actor_row = self.connection.execute(
            "SELECT actor_json FROM command_log WHERE command_id = ?",
            (str(command.command_id),),
        ).fetchone()
        if (
            actor_row is None
            or actor_row["actor_json"] != _actor_json(command.actor)
            or dict(stored.affected_revisions) != revisions
        ):
            raise RuntimeError("stored journey CommandResult domain/actor binding is invalid")

    def _validate_event_payload(self, command: CommandBase, event: sqlite3.Row) -> None:
        try:
            payload = json.loads(str(event["payload_json"]))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("stored journey Event payload is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("stored journey Event payload is not an object")
        aggregate_id = str(event["aggregate_id"])
        event_type = str(event["type"])
        expected_id_key = {
            "project.created": "project_id", "inquiry.created": "inquiry_id",
            "plan.proposed": "plan_id", "resource.registered": "resource_id",
            "locator.created": "locator_id", "claim.created": "claim_id",
            "evidence.attached": "evidence_id", "hypothesis.created": "hypothesis_id",
            "finding.drafted": "finding_id", "relation.created": "relation_id",
            "run.created": "run_id", "action.proposed": "action_id",
        }.get(event_type)
        if expected_id_key is None or payload.get(expected_id_key) != aggregate_id:
            raise RuntimeError("stored journey Event payload is not bound to its aggregate")
        expected: dict[str, object] = {}
        if event_type == "relation.created":
            relation = self.connection.execute("SELECT type, source_id, target_id, status FROM relations WHERE id = ?", (aggregate_id,)).fetchone()
            if isinstance(command, CreateRelation):
                relation_type = command.relation_type.value
                source_id = str(command.source_id)
                target_id = str(command.target_id)
            elif isinstance(command, AttachEvidence):
                relation_type = RelationType.RESOURCE_CONTAINS_EVIDENCE.value
                source_id = str(payload.get("source_id"))
                target_id = str(payload.get("target_id"))
            elif isinstance(command, DraftFinding) and command.terminal_run_ids:
                relation_type = RelationType.RUN_PRODUCES_FINDING.value
                source_id = str(command.terminal_run_ids[0])
                target_id = str(payload.get("target_id"))
            elif isinstance(command, StartRun) and command.retry_of_run_id is not None:
                relation_type = RelationType.RUN_RETRY_OF_RUN.value
                source_id = str(payload.get("source_id"))
                target_id = str(command.retry_of_run_id)
            else:
                raise RuntimeError("stored relation Event is not bound to its command")
            expected = {"relation_type": relation_type, "source_id": source_id, "target_id": target_id, "status": "active"}
            if relation is None or any(relation[key] != value for key, value in (("type", relation_type), ("source_id", source_id), ("target_id", target_id), ("status", "active"))):
                raise RuntimeError("stored relation Event payload is not bound to its domain row")
        elif isinstance(command, CreateProject):
            expected = {"workspace_id": str(command.workspace_id), "status": "active"}
        elif isinstance(command, CreateInquiry):
            expected = {"project_id": str(command.project_id), "status": "draft"}
        elif isinstance(command, ProposePlan):
            expected = {"inquiry_id": str(command.inquiry_id), "revision": 1, "status": "proposed"}
        elif isinstance(command, RegisterResource):
            row = self.connection.execute("SELECT project_id, content_hash, status FROM resources WHERE id = ?", (aggregate_id,)).fetchone()
            expected = {"project_id": str(command.project_id), "status": "available"}
            if row is None or row["project_id"] != str(command.project_id) or row["status"] != "available" or payload.get("content_hash") != row["content_hash"]:
                raise RuntimeError("stored resource Event payload is not bound to its domain row")
        elif isinstance(command, CreateLocator):
            row = self.connection.execute("SELECT resource_id, status FROM locators WHERE id = ?", (aggregate_id,)).fetchone()
            resource = self.connection.execute("SELECT content_hash FROM resources WHERE id = ?", (str(command.resource_id),)).fetchone()
            expected = {"resource_id": str(command.resource_id), "status": "valid", "quote_hash": command.quote_hash}
            if row is None or row["resource_id"] != str(command.resource_id) or row["status"] != "valid" or resource is None or payload.get("resource_hash") != resource["content_hash"]:
                raise RuntimeError("stored locator Event payload is not bound to its domain row")
        elif isinstance(command, (CreateClaim, CreateHypothesis)):
            expected = {"inquiry_id": str(command.inquiry_id), "status": "draft" if isinstance(command, CreateClaim) else "proposed"}
        elif isinstance(command, AttachEvidence):
            expected = {"inquiry_id": str(command.inquiry_id), "locator_id": str(command.locator_id), "status": "valid", "excerpt_hash": command.excerpt_hash}
        elif isinstance(command, DraftFinding):
            expected = {"inquiry_id": str(command.inquiry_id), "status": "draft", "evidence_ids": [str(item) for item in sorted(command.evidence_ids, key=str)], "producer_run_id": str(command.terminal_run_ids[0]) if command.terminal_run_ids else None}
        if any(payload.get(key) != value for key, value in expected.items()):
            raise RuntimeError("stored journey Event payload is not bound to its command")

    def _domain_row_exists(self, event: sqlite3.Row) -> bool:
        aggregate_type = str(event["aggregate_type"])
        table_map = {
            "project": "projects", "inquiry": "inquiries", "resource": "resources",
            "locator": "locators", "claim": "claims", "evidence": "evidence",
            "hypothesis": "hypotheses", "finding": "findings", "relation": "relations",
            "run": "runs", "action": "actions",
        }
        table = table_map.get(aggregate_type)
        if aggregate_type == "plan":
            row = self.connection.execute(
                "SELECT 1 FROM plans WHERE id = ? AND revision = ?",
                (event["aggregate_id"], event["aggregate_version"]),
            ).fetchone()
            return row is not None
        if table is None:
            return False
        row = self.connection.execute(
            f"SELECT 1 FROM {table} WHERE id = ?",  # noqa: S608 - closed table registry
            (event["aggregate_id"],),
        ).fetchone()
        return row is not None and int(event["aggregate_version"]) == 1

    def _validate_stored_rejection(self, command: CommandBase, stored: StructuredError) -> None:
        binding = stored.details.get("binding")
        expected = self._binding(command, self._transactions._request_hash(command))
        if (
            binding != expected
            or stored.code in {ErrorCode.INTERNAL, ErrorCode.COMMAND_REPLAY_CONFLICT}
            or stored.data_safe is not True
        ):
            raise RuntimeError("stored journey Command rejection is not bound")

        details = dict(stored.details)
        expected_error: StructuredError
        if stored.code is ErrorCode.REVISION_CONFLICT:
            allowed_types = {
                "CreateProject": "workspace",
                "CreateInquiry": "project",
                "RegisterResource": "project",
                "ProposePlan": "inquiry",
                "CreateClaim": "inquiry",
                "CreateHypothesis": "inquiry",
                "DraftFinding": "inquiry",
                "CreateLocator": "resource",
                "AttachEvidence": "locator",
                "CreateRelation": "claim",
                "RevisePlan": "plan",
                "PauseRun": "run",
                "ResumeRun": "run",
                "CancelRun": "run",
            }
            if set(details) != {
                "binding", "aggregate_type", "aggregate_id",
                "expected_revision", "actual_revision",
            } or details.get("aggregate_type") != allowed_types.get(command.type):
                raise RuntimeError("stored journey revision rejection is not bound")
            try:
                aggregate_id = UUID(str(details["aggregate_id"]))
            except (TypeError, ValueError) as exc:
                raise RuntimeError("stored journey revision rejection is not bound") from exc
            actual = details["actual_revision"]
            if isinstance(actual, bool) or (actual is not None and (not isinstance(actual, int) or actual < 1)):
                raise RuntimeError("stored journey revision rejection is not bound")
            expected_error = self._revision_error(
                command,
                self._transactions._request_hash(command),
                str(details["aggregate_type"]),
                aggregate_id,
                actual,
            )
        elif stored.code is ErrorCode.STATE_TRANSITION:
            if set(details) != {"binding", "object_type", "object_id", "state"}:
                raise RuntimeError("stored journey state rejection is not bound")
            try:
                object_id = UUID(str(details["object_id"]))
            except (TypeError, ValueError) as exc:
                raise RuntimeError("stored journey state rejection is not bound") from exc
            if not isinstance(details["object_type"], str) or not isinstance(details["state"], str):
                raise RuntimeError("stored journey state rejection is not bound")
            expected_error = self._state_error(
                command,
                self._transactions._request_hash(command),
                str(details["object_type"]),
                object_id,
                str(details["state"]),
            )
        elif stored.code is ErrorCode.RELATION_INVALID:
            reasons = {
                "missing_scope_endpoint", "resource_inquiry_project_mismatch",
                "duplicate_evidence", "evidence_missing",
                "evidence_claim_inquiry_mismatch", "inquiry_missing",
                "duplicate_active_relation", "relation_registry_rejected",
                "finding_evidence_scope", "finding_run_scope",
            }
            if set(details) != {"binding", "reason"} or details.get("reason") not in reasons:
                raise RuntimeError("stored journey relation rejection is not bound")
            expected_error = self._scope_error(
                command,
                self._transactions._request_hash(command),
                str(details["reason"]),
            )
        elif stored.code is ErrorCode.LOCATOR_INVALID:
            reasons = {
                "descriptor_not_allowlisted", "read_root_reparse",
                "read_root_unavailable", "read_root_invalid", "resource_reparse",
                "resource_not_regular", "resource_unavailable",
                "resource_changed_during_read", "resource_path_escape",
                "resource_not_utf8", "locator_material_mismatch",
                "line_span_out_of_range", "quote_hash_mismatch",
                "excerpt_hash_mismatch",
            }
            if set(details) != {"binding", "reason"} or details.get("reason") not in reasons:
                raise RuntimeError("stored journey locator rejection is not bound")
            expected_error = self._locator_error(
                command,
                self._transactions._request_hash(command),
                str(details["reason"]),
            )
        else:
            raise RuntimeError("stored journey rejection code is not bound")

        if stored.model_dump(mode="json") != expected_error.model_dump(mode="json"):
            raise RuntimeError("stored journey Command rejection fields are not bound")
        serialized = _json(stored.model_dump(mode="json"))
        if re.search(r"(?i)(?:[A-Z]:[\\/]|(?:^|[\"'])/)", serialized):
            raise RuntimeError("stored journey Command rejection exposes a host path")
