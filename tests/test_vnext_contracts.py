"""D0 command, domain, locator, state-machine, and fixture contracts."""

from __future__ import annotations

import hashlib
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from pydantic import TypeAdapter, ValidationError

from nana_sidecar.contracts.authorization import (
    ActionHashMaterial,
    GrantMatchContext,
    approval_authorizes,
    canonical_json_hash,
    compute_action_hash,
    policy_grant_matches,
)
from nana_sidecar.contracts.catalog import ContractCatalogSchema
from nana_sidecar.contracts.commands import (
    DEV_COMMAND_NAMES,
    Command,
    DraftFinding,
)
from nana_sidecar.contracts.common import (
    ActorKind,
    ActorRef,
    BudgetSnapshot,
    EffectScope,
    ResourceUsage,
    VersionedRef,
)
from nana_sidecar.contracts.domain import (
    ActionReceipt,
    Approval,
    ApprovalDecision,
    ArtifactLifecycleEvent,
    ArtifactReconciledPayload,
    ArtifactStagedPayload,
    AuthorizationSource,
    CapabilityConstraints,
    Event,
    EventType,
    PolicyGrant,
    PolicyGrantState,
    ReceiptResult,
    Run,
)
from nana_sidecar.contracts.errors import ErrorResponse
from nana_sidecar.contracts.locators import (
    CharacterSpan,
    DatasetCoordinates,
    LineSpan,
    LocalFileCoordinates,
    LocatorCoordinates,
    PdfCoordinates,
    RepoCoordinates,
    RunOutputCoordinates,
    WebCoordinates,
)
from nana_sidecar.contracts.state_machine import (
    INITIAL_STATES,
    TERMINAL_STATES,
    TRANSITIONS,
    StateTransitionError,
    assert_transition,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "v0.3.0-dev" / "inquiry.json"
NOW = datetime(2026, 7, 29, tzinfo=timezone.utc)
HASH = "sha256:" + "a" * 64


def budget() -> BudgetSnapshot:
    return BudgetSnapshot(
        wall_clock_seconds=60,
        cpu_seconds=30,
        memory_bytes=256_000_000,
        gpu_seconds=None,
        max_actions=4,
        max_concurrency=1,
        max_model_calls=0,
        max_model_tokens=0,
        max_cost_micros=0,
        max_retries=1,
        max_output_bytes=100_000,
        max_artifact_bytes=1_000_000,
        max_download_bytes=0,
        network_targets=(),
        read_roots=("project",),
        write_roots=("scratch",),
    )


class CommandContractTests(unittest.TestCase):
    def test_dev_command_registry_is_complete_and_scope_limited(self) -> None:
        self.assertEqual(
            DEV_COMMAND_NAMES,
            {
                "CreateProject",
                "CreateInquiry",
                "ProposePlan",
                "RevisePlan",
                "StartRun",
                "PauseRun",
                "CancelRun",
                "ProposeAction",
                "CreatePolicyGrant",
                "RevokePolicyGrant",
                "RequestApproval",
                "DecideApproval",
                "AuthorizeAction",
                "CommitArtifact",
                "RegisterResource",
                "CreateLocator",
                "CreateClaim",
                "AttachEvidence",
                "CreateHypothesis",
                "DraftFinding",
                "CreateRelation",
                "PublishExport",
            },
        )
        self.assertTrue(
            {"ReviewFinding", "DraftDecision", "ConfirmDecision"}.isdisjoint(
                DEV_COMMAND_NAMES
            )
        )

    def test_discriminated_command_rejects_unknown_fields(self) -> None:
        payload = {
            "type": "CreateProject",
            "command_id": str(uuid4()),
            "expected_revision": None,
            "actor": {"kind": "user", "id": "owner"},
            "workspace_id": str(uuid4()),
            "title": "Sliding-window boundary",
            "data_class": "public",
            "raw_sql": "DROP TABLE projects",
        }
        with self.assertRaises(ValidationError):
            TypeAdapter(Command).validate_python(payload)

    def test_finding_draft_requires_traceable_provenance(self) -> None:
        common = {
            "type": "DraftFinding",
            "command_id": uuid4(),
            "actor": ActorRef(kind=ActorKind.AGENT, id="fixture-agent"),
            "inquiry_id": uuid4(),
            "statement": "The locked test completed.",
            "confidence_basis": "Deterministic unit-test output.",
        }
        with self.assertRaisesRegex(ValidationError, "Evidence or a terminal Run"):
            DraftFinding(**common)
        finding = DraftFinding(**common, terminal_run_ids=(uuid4(),))
        self.assertEqual(len(finding.terminal_run_ids), 1)

    def test_catalog_schema_exposes_all_stable_objects(self) -> None:
        names = set(ContractCatalogSchema.model_json_schema()["$defs"])
        self.assertTrue(
            {
                "Workspace",
                "Project",
                "Inquiry",
                "Plan",
                "Run",
                "Action",
                "Event",
                "PolicyGrant",
                "Approval",
                "ActionReceipt",
                "Artifact",
                "Resource",
                "Locator",
                "Claim",
                "Evidence",
                "Hypothesis",
                "Method",
                "Finding",
                "Decision",
                "Relation",
                "ErrorResponse",
                "ActionHashMaterial",
                "GrantMatchContext",
                "AuthorizationMatch",
                "ArtifactStagedEvent",
                "ArtifactCommittedEvent",
                "ArtifactReconciledEvent",
                "ArtifactStagedPayload",
                "ArtifactCommittedPayload",
                "ArtifactReconciledPayload",
            }
            <= names
        )


class LocatorContractTests(unittest.TestCase):
    def test_every_locator_kind_round_trips(self) -> None:
        samples = (
            WebCoordinates(
                canonical_url="https://example.test/paper",
                retrieved_at=NOW,
                content_hash=HASH,
                quote_span=CharacterSpan(start_char=4, end_char=12),
            ),
            PdfCoordinates(
                artifact_hash=HASH,
                page=2,
                character_span=CharacterSpan(start_char=8, end_char=18),
                parser_id="fixture-parser",
                parser_version="1",
            ),
            RepoCoordinates(
                remote="https://example.test/repository.git",
                commit="abcdef1",
                path="src/window.py",
                line_span=LineSpan(start_line=3, end_line=9),
            ),
            LocalFileCoordinates(
                artifact_hash=HASH,
                logical_path="fixtures/resource.md",
                line_span=LineSpan(start_line=6, end_line=12),
            ),
            DatasetCoordinates(
                dataset="window-cases",
                version="1",
                content_hash=HASH,
                split="locked",
                row_start=0,
                row_end=2,
            ),
            RunOutputCoordinates(
                run_id=uuid4(),
                artifact_id=uuid4(),
                metric_key="shortest_length",
            ),
        )
        adapter = TypeAdapter(LocatorCoordinates)
        for coordinates in samples:
            with self.subTest(kind=coordinates.kind):
                restored = adapter.validate_json(adapter.dump_json(coordinates))
                self.assertEqual(restored, coordinates)

    def test_local_file_locator_round_trips_as_discriminated_schema(self) -> None:
        coordinates = LocalFileCoordinates(
            artifact_hash=HASH,
            logical_path="fixtures/resource.md",
            line_span=LineSpan(start_line=6, end_line=12),
        )
        adapter = TypeAdapter(LocatorCoordinates)
        restored = adapter.validate_json(adapter.dump_json(coordinates))

        self.assertEqual(restored, coordinates)
        self.assertEqual(restored.kind, "local_file")

    def test_local_file_locator_rejects_escape_and_absolute_paths(self) -> None:
        for unsafe in ("../secret.txt", "/etc/passwd", "C:\\Users\\name\\secret"):
            with self.subTest(unsafe=unsafe):
                with self.assertRaisesRegex(ValidationError, "relative logical"):
                    LocalFileCoordinates(
                        artifact_hash=HASH,
                        logical_path=unsafe,
                        line_span=LineSpan(start_line=1, end_line=1),
                    )

    def test_pdf_locator_requires_reopenable_position(self) -> None:
        with self.assertRaisesRegex(ValidationError, "bounding_box"):
            PdfCoordinates(
                artifact_hash=HASH,
                page=1,
                parser_id="fixture-parser",
                parser_version="1",
            )


class DomainInvariantTests(unittest.TestCase):
    def test_structured_error_envelope_is_closed(self) -> None:
        response = ErrorResponse(
            error={
                "code": "E_APPROVAL_INVALID",
                "category": "permission",
                "message": "Approval no longer matches the Action.",
                "retryable": False,
                "details": {"reason": "action_hash"},
                "data_safe": True,
                "suggested_actions": ("request_new_approval",),
            }
        )
        self.assertEqual(response.error.code, "E_APPROVAL_INVALID")
        with self.assertRaises(ValidationError):
            ErrorResponse(
                error={
                    **response.error.model_dump(),
                    "raw_secret": "must not be accepted",
                }
            )

    def test_event_type_is_closed_and_payload_is_exclusive(self) -> None:
        base = {
            "id": 1,
            "aggregate_type": "project",
            "aggregate_id": uuid4(),
            "aggregate_version": 1,
            "actor": ActorRef(kind=ActorKind.USER, id="owner"),
            "occurred_at": NOW,
        }
        with self.assertRaises(ValidationError):
            Event(**base, type="made.up", payload={})
        with self.assertRaisesRegex(ValidationError, "exactly one"):
            Event(
                **base,
                type=EventType.PROJECT_CREATED,
                payload={},
                payload_artifact_id=uuid4(),
            )

    def test_artifact_lifecycle_event_rejects_empty_or_mismatched_payload(
        self,
    ) -> None:
        artifact_id = uuid4()
        base = {
            "id": 1,
            "aggregate_type": "artifact",
            "aggregate_id": artifact_id,
            "aggregate_version": 1,
            "actor": ActorRef(kind=ActorKind.SYSTEM, id="reconciler"),
            "occurred_at": NOW,
        }
        for event_type in (
            EventType.ARTIFACT_STAGED,
            EventType.ARTIFACT_COMMITTED,
            EventType.ARTIFACT_RECONCILED,
        ):
            with self.subTest(event_type=event_type):
                with self.assertRaises(ValidationError):
                    Event(
                        **base,
                        type=event_type,
                        payload={},
                    )
        with self.assertRaisesRegex(ValidationError, "inline typed payload"):
            Event(
                **base,
                type=EventType.ARTIFACT_COMMITTED,
                payload_artifact_id=uuid4(),
            )
        with self.assertRaisesRegex(ValidationError, "match aggregate_id"):
            Event(
                **base,
                type=EventType.ARTIFACT_COMMITTED,
                payload={
                    "artifact_id": str(uuid4()),
                    "state": "available",
                    "blob_hash": HASH,
                    "size": 7,
                    "media_type": "text/plain",
                },
            )

    def test_artifact_lifecycle_event_is_a_discriminated_union(self) -> None:
        artifact_id = uuid4()
        raw = {
            "id": 1,
            "aggregate_type": "artifact",
            "aggregate_id": str(artifact_id),
            "aggregate_version": 1,
            "actor": {"kind": "system", "id": "artifact-store"},
            "type": "artifact.staged",
            "payload": {
                "artifact_id": str(artifact_id),
                "state": "staged",
                "temp_ref": "staging/probe.partial",
                "blob_hash": HASH,
                "size": 7,
                "media_type": "text/plain",
            },
            "payload_artifact_id": None,
            "occurred_at": NOW.isoformat(),
        }
        adapter = TypeAdapter(ArtifactLifecycleEvent)
        event = adapter.validate_python(raw)
        restored = adapter.validate_json(adapter.dump_json(event))
        self.assertEqual(restored, event)
        self.assertIsInstance(event.payload, ArtifactStagedPayload)

    def test_artifact_payloads_reject_path_escape_and_invalid_reconcile(
        self,
    ) -> None:
        with self.assertRaisesRegex(ValidationError, "relative logical"):
            ArtifactStagedPayload(
                artifact_id=uuid4(),
                temp_ref="../outside.partial",
                blob_hash=HASH,
                size=7,
                media_type="text/plain",
            )
        with self.assertRaisesRegex(ValidationError, "reconciliation transition"):
            ArtifactReconciledPayload(
                artifact_id=uuid4(),
                previous_state="staged",
                state="corrupt",
                reason_code="unexpected_transition",
            )

    def test_terminal_run_requires_finished_at(self) -> None:
        snapshot = {
            "plan_id": uuid4(),
            "plan_revision": 1,
            "capabilities": [
                VersionedRef(id="python.unittest.locked", version="1")
            ],
            "models": [],
            "backend": VersionedRef(id="builtin_local", version="1"),
            "policy": {},
            "budget": budget(),
            "code": {"commit_ref": "abc1234", "diff_hash": None, "dirty": False},
            "input_artifact_ids": [],
            "environment": {
                "os_name": "Windows",
                "os_version": "test",
                "python_version": "3.12.13",
                "dependency_lock_hash": HASH,
                "environment_keys": ["PYTHONUTF8"],
            },
            "random_seed": 7,
        }
        with self.assertRaisesRegex(ValidationError, "finished_at"):
            Run(
                id=uuid4(),
                project_id=uuid4(),
                inquiry_id=uuid4(),
                state="succeeded",
                snapshot=snapshot,
                created_at=NOW,
            )

    def test_decided_approval_requires_actor_and_time(self) -> None:
        common = {
            "id": uuid4(),
            "subject_type": "action",
            "subject_id": uuid4(),
            "subject_hash": HASH,
            "capability": VersionedRef(id="export.publish", version="1"),
            "parameter_summary": {},
            "requested_effects": EffectScope(writes=("external:test-target",)),
            "data_class": "public",
            "budget": budget(),
            "risk_tier": "T3",
            "reversible": True,
            "allowed_uses": 1,
            "expires_at": NOW + timedelta(minutes=5),
        }
        with self.assertRaisesRegex(ValidationError, "decided_at"):
            Approval(**common, decision=ApprovalDecision.APPROVED)

    def test_approval_receipt_requires_explicit_approver(self) -> None:
        common = {
            "id": uuid4(),
            "action_id": uuid4(),
            "action_hash": HASH,
            "authorization_source": AuthorizationSource.APPROVAL,
            "authorization_ref": "approval:test",
            "actual_effects": EffectScope(writes=("external:test-target",)),
            "result": ReceiptResult.SUCCEEDED,
            "resource_usage": ResourceUsage(wall_clock_ms=5),
            "created_at": NOW,
        }
        with self.assertRaisesRegex(ValidationError, "approver"):
            ActionReceipt(**common)


class AuthorizationContractTests(unittest.TestCase):
    def action_material(self, **changes: object) -> ActionHashMaterial:
        args = changes.pop("args", {"destination": "review/draft.md"})
        values = {
            "capability": VersionedRef(id="export.draft_external", version="1"),
            "args": args,
            "args_hash": canonical_json_hash(args),
            "data_class": "public",
            "provider": None,
            "requested_effects": EffectScope(
                writes=("external:review",),
            ),
            "network_methods": (),
            "budget": budget(),
            "risk_tier": "T3",
            "reversible": True,
        }
        values.update(changes)
        return ActionHashMaterial(**values)

    def approval(
        self,
        action_id: object,
        material: ActionHashMaterial,
    ) -> Approval:
        return Approval(
            id=uuid4(),
            subject_type="action",
            subject_id=action_id,
            subject_hash=compute_action_hash(material),
            capability=material.capability,
            parameter_summary={"destination": "external:review"},
            requested_effects=material.requested_effects,
            data_class=material.data_class,
            provider=material.provider,
            budget=material.budget,
            risk_tier=material.risk_tier,
            reversible=material.reversible,
            allowed_uses=1,
            expires_at=NOW + timedelta(minutes=5),
            decision=ApprovalDecision.APPROVED,
            decided_by=ActorRef(kind=ActorKind.USER, id="owner"),
            decided_at=NOW,
        )

    def grant(
        self,
        project_id: object,
        material: ActionHashMaterial,
    ) -> PolicyGrant:
        constraints = CapabilityConstraints(
            args_schema={
                "type": "object",
                "required": ["destination"],
                "properties": {
                    "destination": {
                        "type": "string",
                        "const": "review/draft.md",
                    }
                },
                "additionalProperties": False,
            },
            allowed_data_classes=("public",),
            allowed_providers=(),
            read_roots=(),
            write_roots=("external:review",),
            network_targets=(),
            network_methods=(),
            per_action_budget=budget(),
            cumulative_budget=budget(),
            max_concurrency=1,
            max_uses=2,
            valid_from=NOW - timedelta(minutes=1),
            expires_at=NOW + timedelta(minutes=5),
        )
        return PolicyGrant(
            id=uuid4(),
            project_id=project_id,
            capability=material.capability,
            constraints=constraints,
            state=PolicyGrantState.ACTIVE,
            uses=0,
            created_at=NOW,
        )

    def test_action_hash_is_canonical_and_covers_authorization_surface(
        self,
    ) -> None:
        first = self.action_material(args={"b": 2, "a": 1})
        same = self.action_material(args={"a": 1, "b": 2})
        self.assertEqual(first.args_hash, same.args_hash)
        self.assertEqual(compute_action_hash(first), compute_action_hash(same))

        mutations = (
            self.action_material(args={"destination": "review/other.md"}),
            self.action_material(data_class="personal"),
            self.action_material(
                requested_effects=EffectScope(writes=("external:other",))
            ),
            self.action_material(risk_tier="T4"),
            self.action_material(reversible=False),
        )
        original_hash = compute_action_hash(self.action_material())
        for changed in mutations:
            with self.subTest(changed=changed):
                self.assertNotEqual(original_hash, compute_action_hash(changed))

    def test_action_args_hash_mismatch_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValidationError, "canonical args"):
            self.action_material(args_hash=HASH)

    def test_approval_is_invalidated_by_action_change_expiry_or_replay(
        self,
    ) -> None:
        action_id = uuid4()
        material = self.action_material()
        approval = self.approval(action_id, material)
        valid = approval_authorizes(
            approval,
            action_id=action_id,
            material=material,
            at=NOW,
            prior_uses=0,
        )
        self.assertTrue(valid.matches)

        changed = self.action_material(
            requested_effects=EffectScope(writes=("external:other",))
        )
        changed_result = approval_authorizes(
            approval,
            action_id=action_id,
            material=changed,
            at=NOW,
            prior_uses=0,
        )
        self.assertFalse(changed_result.matches)
        self.assertIn("action_hash", changed_result.reasons)

        expired = approval_authorizes(
            approval,
            action_id=action_id,
            material=material,
            at=approval.expires_at,
            prior_uses=0,
        )
        replayed = approval_authorizes(
            approval,
            action_id=action_id,
            material=material,
            at=NOW,
            prior_uses=1,
        )
        self.assertIn("expired", expired.reasons)
        self.assertIn("uses", replayed.reasons)

    def test_policy_grant_matches_only_full_constraint_subset(self) -> None:
        project_id = uuid4()
        material = self.action_material()
        grant = self.grant(project_id, material)
        context = GrantMatchContext(
            project_id=project_id,
            projected_cumulative_budget=budget(),
            current_concurrency=0,
        )
        self.assertTrue(
            policy_grant_matches(
                grant,
                material=material,
                context=context,
                at=NOW,
            ).matches
        )

        escaped = self.action_material(
            requested_effects=EffectScope(writes=("external:other",))
        )
        result = policy_grant_matches(
            grant,
            material=escaped,
            context=context,
            at=NOW,
        )
        self.assertFalse(result.matches)
        self.assertIn("write_scope", result.reasons)

    def test_unknown_schema_keywords_and_t4_capabilities_fail_closed(
        self,
    ) -> None:
        project_id = uuid4()
        material = self.action_material()
        grant = self.grant(project_id, material)
        unsafe_constraints = grant.constraints.model_copy(
            update={"args_schema": {"oneOf": [{"type": "object"}]}}
        )
        unsafe_grant = grant.model_copy(
            update={"constraints": unsafe_constraints}
        )
        context = GrantMatchContext(
            project_id=project_id,
            projected_cumulative_budget=budget(),
            current_concurrency=0,
        )
        self.assertIn(
            "args_schema",
            policy_grant_matches(
                unsafe_grant,
                material=material,
                context=context,
                at=NOW,
            ).reasons,
        )

        t4_material = self.action_material(
            capability=VersionedRef(id="export.publish", version="1"),
            risk_tier="T4",
            reversible=False,
        )
        t4_grant = self.grant(project_id, t4_material)
        self.assertIn(
            "capability_requires_one_time_approval",
            policy_grant_matches(
                t4_grant,
                material=t4_material,
                context=context,
                at=NOW,
            ).reasons,
        )


class StateMachineContractTests(unittest.TestCase):
    def test_every_registered_object_has_an_initial_state(self) -> None:
        self.assertEqual(set(TRANSITIONS), set(INITIAL_STATES))
        for object_type, initial in INITIAL_STATES.items():
            self.assertIn(initial, TRANSITIONS[object_type])

    def test_method_and_decision_transitions_are_registered(self) -> None:
        assert_transition("method", "method-1", "draft", "validated", 1)
        assert_transition("decision", "decision-1", "in_review", "confirmed", 2)

    def test_run_terminal_state_cannot_move(self) -> None:
        with self.assertRaises(StateTransitionError) as captured:
            assert_transition("run", "run-1", "succeeded", "running", 5)
        self.assertEqual(captured.exception.code, "E_STATE_TRANSITION")
        self.assertIn("succeeded", TERMINAL_STATES["run"])

    def test_effect_unknown_is_terminal(self) -> None:
        with self.assertRaises(StateTransitionError):
            assert_transition(
                "action", "action-1", "effect_unknown", "succeeded", 8
            )


class DevFixtureContractTests(unittest.TestCase):
    def test_selected_fixture_is_frozen_and_within_scope_ceiling(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(fixture["milestone"], "v0.3.0-dev")
        self.assertEqual(
            fixture["registered_test"]["test_id"],
            "tests.test_sliding_window.VariableWindowTests."
            "test_finds_shortest_matching_window",
        )
        self.assertEqual(fixture["registered_test"]["network"], "denied")
        self.assertEqual(
            set(fixture["scope_ceiling"].values()), {"v0.3.0-alpha.1"}
        )

    def test_resource_and_locator_hashes_resolve(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        resource = ROOT / fixture["resource"]["logical_ref"]
        raw = resource.read_bytes()
        lines = raw.decode("utf-8").replace("\r\n", "\n").split("\n")
        locator = fixture["resource"]["locator"]
        quote = "\n".join(
            lines[locator["start_line"] - 1 : locator["end_line"]]
        ).encode("utf-8")
        self.assertEqual(
            fixture["resource"]["content_hash"],
            f"sha256:{hashlib.sha256(raw).hexdigest()}",
        )
        self.assertEqual(
            locator["quote_hash"],
            f"sha256:{hashlib.sha256(quote).hexdigest()}",
        )


class D0EvidenceManifestTests(unittest.TestCase):
    def test_manifest_files_and_digest_match(self) -> None:
        manifest_path = (
            ROOT / "docs" / "evidence" / "v0.3.0-dev-d0-manifest.txt"
        )
        digest_path = manifest_path.with_suffix(".sha256")
        normalized_lines = manifest_path.read_text(encoding="utf-8").splitlines()
        for line in normalized_lines:
            relative_path, expected = line.split("\t", maxsplit=1)
            target = (ROOT / relative_path).resolve()
            self.assertTrue(target.is_relative_to(ROOT))
            self.assertEqual(
                hashlib.sha256(target.read_bytes()).hexdigest(),
                expected,
                relative_path,
            )
        actual_manifest_digest = hashlib.sha256(
            "\n".join(normalized_lines).encode("utf-8")
        ).hexdigest()
        self.assertEqual(
            actual_manifest_digest,
            digest_path.read_text(encoding="ascii").strip(),
        )


if __name__ == "__main__":
    unittest.main()
