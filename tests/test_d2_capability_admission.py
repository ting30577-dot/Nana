"""D2-03b Capability admission service tests."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from nana_sidecar.contracts.authorization import (
    ActionHashMaterial,
    GrantMatchContext,
    canonical_json_hash,
    compute_action_hash,
)
from nana_sidecar.contracts.builtin_capabilities import (
    PYTHON_UNITTEST_LOCKED_CAPABILITY,
    PYTHON_UNITTEST_LOCKED_TEST_IDS,
    python_unittest_locked_registry_entry,
)
from nana_sidecar.contracts.common import (
    ActorKind,
    ActorRef,
    BudgetSnapshot,
    DataClass,
    EffectScope,
    RiskTier,
)
from nana_sidecar.contracts.domain import (
    Approval,
    ApprovalDecision,
    CapabilityConstraints,
    PolicyGrant,
    PolicyGrantState,
)
from nana_sidecar.storage import (
    AdmissionStateError,
    CapabilityAdmissionService,
    connect_database,
    initialize_database,
)


NOW = datetime(2026, 7, 31, tzinfo=timezone.utc)
NOW_TEXT = "2026-07-31T00:00:00Z"

WORKSPACE_ID = UUID("10000000-0000-0000-0000-000000000001")
PROJECT_ID = UUID("10000000-0000-0000-0000-000000000002")
INQUIRY_ID = UUID("10000000-0000-0000-0000-000000000003")
PLAN_ID = UUID("10000000-0000-0000-0000-000000000004")
RUN_ID = UUID("10000000-0000-0000-0000-000000000005")
ACTION_ID = UUID("10000000-0000-0000-0000-000000000006")
ARGS_ARTIFACT_ID = UUID("10000000-0000-0000-0000-000000000007")
GRANT_ID = UUID("10000000-0000-0000-0000-000000000008")
APPROVAL_ID = UUID("10000000-0000-0000-0000-000000000009")


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _budget(*, wall_clock_seconds: int = 60) -> BudgetSnapshot:
    return BudgetSnapshot(
        wall_clock_seconds=wall_clock_seconds,
        cpu_seconds=None,
        memory_bytes=None,
        gpu_seconds=None,
        max_actions=1,
        max_concurrency=1,
        max_model_calls=0,
        max_model_tokens=0,
        max_cost_micros=0,
        max_retries=0,
        max_output_bytes=4096,
        max_artifact_bytes=4096,
        max_download_bytes=0,
        network_targets=(),
        read_roots=("project:source", "project:tests"),
        write_roots=("project:scratch",),
    )


def _args() -> dict[str, object]:
    return {"test_id": PYTHON_UNITTEST_LOCKED_TEST_IDS[0]}


def _material(*, args: dict[str, object] | None = None) -> ActionHashMaterial:
    action_args = args or _args()
    return ActionHashMaterial(
        capability=PYTHON_UNITTEST_LOCKED_CAPABILITY,
        args=action_args,
        args_hash=canonical_json_hash(action_args),
        data_class=DataClass.PUBLIC,
        provider=None,
        requested_effects=EffectScope(
            reads=("project:source", "project:tests"),
            processes=("builtin:python.unittest.locked",),
        ),
        network_methods=(),
        budget=_budget(),
        risk_tier=RiskTier.T2,
        reversible=True,
    )


class D2CapabilityAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "workspace" / "nana-vnext.db"
        self.connection = initialize_database(self.path)
        self.material = _material()
        self.args_bytes = _json(self.material.args).encode("utf-8")
        self.actor = ActorRef(kind=ActorKind.SYSTEM, id="d2-admission-test")
        self.service = CapabilityAdmissionService(
            self.connection,
            now=lambda: NOW_TEXT,
            load_args_artifact=lambda row: self.args_bytes,
        )

    def tearDown(self) -> None:
        self.connection.close()
        self.tempdir.cleanup()

    def _seed_common(
        self,
        *,
        action_state: str = "proposed",
        material: ActionHashMaterial | None = None,
    ) -> None:
        material = material or self.material
        registry_entry = python_unittest_locked_registry_entry()
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO workspaces (
                    id, schema_version, data_root, policy_json, status,
                    revision, created_at
                ) VALUES (?, 4, ?, '{}', 'active', 1, ?)
                """,
                (str(WORKSPACE_ID), "workspace-root", NOW_TEXT),
            )
            self.connection.execute(
                """
                INSERT INTO projects (
                    id, workspace_id, title, status, data_class, revision,
                    created_at
                ) VALUES (?, ?, 'D2 admission', 'active', 'public', 1, ?)
                """,
                (str(PROJECT_ID), str(WORKSPACE_ID), NOW_TEXT),
            )
            self.connection.execute(
                """
                INSERT INTO inquiries (
                    id, project_id, question, acceptance, status, revision,
                    created_at
                ) VALUES (?, ?, 'Question', 'Acceptance', 'active', 1, ?)
                """,
                (str(INQUIRY_ID), str(PROJECT_ID), NOW_TEXT),
            )
            self.connection.execute(
                """
                INSERT INTO plans (
                    id, inquiry_id, revision, status, steps_json, policy_json,
                    budget_json, created_at
                ) VALUES (?, ?, 1, 'approved', ?, '{}', ?, ?)
                """,
                (
                    str(PLAN_ID),
                    str(INQUIRY_ID),
                    _json([{"id": "step-1", "title": "locked unittest"}]),
                    _json(_budget().model_dump(mode="json")),
                    NOW_TEXT,
                ),
            )
            self.connection.execute(
                """
                INSERT INTO runs (
                    id, project_id, inquiry_id, state, snapshot_json,
                    created_at
                ) VALUES (?, ?, ?, 'running', ?, ?)
                """,
                (
                    str(RUN_ID),
                    str(PROJECT_ID),
                    str(INQUIRY_ID),
                    _json({"budget": _budget().model_dump(mode="json")}),
                    NOW_TEXT,
                ),
            )
            self.connection.execute(
                """
                INSERT INTO artifacts (
                    id, media_type, blob_hash, size, state, retention_json,
                    created_at
                ) VALUES (?, 'application/json', ?, ?, 'available', '{}', ?)
                """,
                (
                    str(ARGS_ARTIFACT_ID),
                    f"sha256:{hashlib.sha256(self.args_bytes).hexdigest()}",
                    len(self.args_bytes),
                    NOW_TEXT,
                ),
            )
            self.connection.execute(
                """
                INSERT INTO capability_registry_entries (
                    capability_id, capability_version, executable_digest,
                    entry_json, contract_digest, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    registry_entry.capability.id,
                    registry_entry.capability.version,
                    registry_entry.capability.digest,
                    registry_entry.model_dump_json(),
                    registry_entry.contract_digest,
                    NOW_TEXT,
                ),
            )
            self.connection.execute(
                """
                INSERT INTO actions (
                    id, run_id, plan_step_id, capability_id,
                    capability_version, executable_digest, args_artifact_id,
                    args_hash, action_hash, risk_tier, requested_effects_json,
                    policy_decision, state
                ) VALUES (?, ?, 'step-1', ?, ?, ?, ?, ?, ?, ?, ?, 'auto', ?)
                """,
                (
                    str(ACTION_ID),
                    str(RUN_ID),
                    material.capability.id,
                    material.capability.version,
                    material.capability.digest,
                    str(ARGS_ARTIFACT_ID),
                    material.args_hash,
                    compute_action_hash(material),
                    material.risk_tier.value,
                    _json(material.requested_effects.model_dump(mode="json")),
                    action_state,
                ),
            )

    def _grant(self, *, max_uses: int = 2, uses: int = 0) -> PolicyGrant:
        constraints = CapabilityConstraints(
            args_schema=python_unittest_locked_registry_entry().args_schema,
            allowed_data_classes=(DataClass.PUBLIC,),
            allowed_providers=(),
            read_roots=self.material.requested_effects.reads,
            write_roots=self.material.requested_effects.writes,
            network_targets=(),
            network_methods=(),
            process_targets=self.material.requested_effects.processes,
            per_action_budget=_budget(),
            cumulative_budget=_budget(),
            max_concurrency=1,
            max_uses=max_uses,
            valid_from=NOW - timedelta(minutes=1),
            expires_at=NOW + timedelta(minutes=5),
        )
        return PolicyGrant(
            id=GRANT_ID,
            project_id=PROJECT_ID,
            capability=self.material.capability,
            constraints=constraints,
            state=PolicyGrantState.ACTIVE,
            uses=uses,
            created_at=NOW,
        )

    def _insert_grant(self, grant: PolicyGrant) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO policy_grants (
                    id, project_id, capability_id, capability_version,
                    executable_digest, constraints_json, state, uses,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(grant.id),
                    str(grant.project_id),
                    grant.capability.id,
                    grant.capability.version,
                    grant.capability.digest,
                    _json(grant.constraints.model_dump(mode="json")),
                    grant.state.value,
                    grant.uses,
                    NOW_TEXT,
                ),
            )

    def _approval(self) -> Approval:
        return Approval(
            id=APPROVAL_ID,
            subject_type="action",
            subject_id=ACTION_ID,
            subject_hash=compute_action_hash(self.material),
            capability=self.material.capability,
            parameter_summary={"test_id": PYTHON_UNITTEST_LOCKED_TEST_IDS[0]},
            requested_effects=self.material.requested_effects,
            data_class=self.material.data_class,
            provider=self.material.provider,
            budget=self.material.budget,
            risk_tier=self.material.risk_tier,
            reversible=self.material.reversible,
            allowed_uses=1,
            expires_at=NOW + timedelta(minutes=5),
            decision=ApprovalDecision.APPROVED,
            decided_by=ActorRef(kind=ActorKind.USER, id="owner"),
            decided_at=NOW,
        )

    def _insert_approval(self, approval: Approval) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO approvals (
                    id, subject_type, subject_id, subject_hash,
                    capability_json, parameter_summary_json,
                    requested_effects_json, data_class, provider,
                    budget_json, risk_tier, reversible, allowed_uses,
                    expires_at, decision, decided_by_json, decided_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(approval.id),
                    approval.subject_type,
                    str(approval.subject_id),
                    approval.subject_hash,
                    _json(approval.capability.model_dump(mode="json")),
                    _json(approval.parameter_summary),
                    _json(approval.requested_effects.model_dump(mode="json")),
                    approval.data_class.value,
                    approval.provider,
                    _json(approval.budget.model_dump(mode="json")),
                    approval.risk_tier.value,
                    1 if approval.reversible else 0,
                    approval.allowed_uses,
                    NOW_TEXT.replace("00:00:00", "00:05:00"),
                    approval.decision.value,
                    _json(approval.decided_by.model_dump(mode="json")),
                    NOW_TEXT,
                ),
            )

    def _context(self) -> GrantMatchContext:
        return GrantMatchContext(
            project_id=PROJECT_ID,
            projected_cumulative_budget=_budget(),
            current_concurrency=0,
        )

    def _event_payloads(self) -> list[dict[str, object]]:
        return [
            json.loads(str(row["payload_json"]))
            for row in self.connection.execute(
                "SELECT payload_json FROM events ORDER BY id"
            )
        ]

    def test_policy_grant_hit_authorizes_action_and_consumes_in_one_event(self) -> None:
        self._seed_common()
        self._insert_grant(self._grant())

        result = self.service.authorize_with_policy_grant(
            action_id=str(ACTION_ID),
            grant_id=str(GRANT_ID),
            material=self.material,
            context=self._context(),
            actor=self.actor,
        )

        self.assertEqual(result.authorization_ref, f"policy_grant:{GRANT_ID}")
        action = self.connection.execute(
            "SELECT state, policy_decision, authorization_ref FROM actions WHERE id = ?",
            (str(ACTION_ID),),
        ).fetchone()
        self.assertEqual(
            (action["state"], action["policy_decision"], action["authorization_ref"]),
            ("authorized", "grant", f"policy_grant:{GRANT_ID}"),
        )
        grant = self.connection.execute(
            "SELECT uses, state FROM policy_grants WHERE id = ?",
            (str(GRANT_ID),),
        ).fetchone()
        self.assertEqual((int(grant["uses"]), grant["state"]), (1, "active"))
        self.assertEqual(
            [(row["type"], row["event_id"]) for row in self.connection.execute(
                """
                SELECT events.type, outbox_events.event_id
                FROM events JOIN outbox_events ON outbox_events.event_id = events.id
                """
            )],
            [("action.authorized", result.event_ids[0])],
        )
        self.assertEqual(
            self._event_payloads()[0]["authorization_source"],
            "policy_grant",
        )
        durable = self.connection.execute(
            """
            SELECT action_hash, material_json, registry_contract_digest,
                   authorization_source, authorization_ref,
                   authorization_event_id
            FROM action_authorizations
            WHERE action_id = ?
            """,
            (str(ACTION_ID),),
        ).fetchone()
        self.assertEqual(durable["action_hash"], compute_action_hash(self.material))
        self.assertEqual(
            ActionHashMaterial.model_validate_json(durable["material_json"]),
            self.material,
        )
        self.assertEqual(
            durable["registry_contract_digest"],
            python_unittest_locked_registry_entry().contract_digest,
        )
        self.assertEqual(
            (durable["authorization_source"], durable["authorization_ref"]),
            ("policy_grant", f"policy_grant:{GRANT_ID}"),
        )
        self.assertEqual(int(durable["authorization_event_id"]), result.event_ids[0])
        with self.assertRaises(sqlite3.IntegrityError):
            with self.connection:
                self.connection.execute(
                    "UPDATE action_authorizations SET authorization_ref = 'changed'"
                )
        with self.assertRaises(sqlite3.IntegrityError):
            with self.connection:
                self.connection.execute("DELETE FROM action_authorizations")

    def test_grant_cumulative_budget_is_derived_not_caller_reported(self) -> None:
        self._seed_common()
        self._insert_grant(self._grant(max_uses=2))
        self.service.authorize_with_policy_grant(
            action_id=str(ACTION_ID),
            grant_id=str(GRANT_ID),
            material=self.material,
            context=self._context(),
            actor=self.actor,
        )
        second_action_id = UUID("10000000-0000-0000-0000-00000000000a")
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO actions (
                    id, run_id, plan_step_id, capability_id,
                    capability_version, executable_digest, args_artifact_id,
                    args_hash, action_hash, risk_tier, requested_effects_json,
                    policy_decision, state
                ) VALUES (?, ?, 'step-2', ?, ?, ?, ?, ?, ?, ?, ?, 'grant', 'proposed')
                """,
                (
                    str(second_action_id),
                    str(RUN_ID),
                    self.material.capability.id,
                    self.material.capability.version,
                    self.material.capability.digest,
                    str(ARGS_ARTIFACT_ID),
                    self.material.args_hash,
                    compute_action_hash(self.material),
                    self.material.risk_tier.value,
                    _json(self.material.requested_effects.model_dump(mode="json")),
                ),
            )

        with self.assertRaises(AdmissionStateError) as captured:
            self.service.authorize_with_policy_grant(
                action_id=str(second_action_id),
                grant_id=str(GRANT_ID),
                material=self.material,
                context=self._context(),
                actor=self.actor,
            )

        self.assertEqual(captured.exception.code, "E_POLICY_GRANT_DENIED")
        self.assertIn("cumulative_budget", str(captured.exception))
        self.assertEqual(
            self.connection.execute(
                "SELECT state FROM actions WHERE id = ?",
                (str(second_action_id),),
            ).fetchone()["state"],
            "proposed",
        )

    def test_policy_grant_miss_rolls_back_without_state_change(self) -> None:
        self._seed_common()
        grant = self._grant()
        too_small = _budget().model_copy(update={"wall_clock_seconds": 1})
        grant = grant.model_copy(
            update={
                "constraints": grant.constraints.model_copy(
                    update={"per_action_budget": too_small}
                )
            }
        )
        self._insert_grant(grant)

        with self.assertRaises(AdmissionStateError) as captured:
            self.service.authorize_with_policy_grant(
                action_id=str(ACTION_ID),
                grant_id=str(GRANT_ID),
                material=self.material,
                context=self._context(),
                actor=self.actor,
            )

        self.assertEqual(captured.exception.code, "E_POLICY_GRANT_DENIED")
        self.assertEqual(
            self.connection.execute(
                "SELECT state FROM actions WHERE id = ?",
                (str(ACTION_ID),),
            ).fetchone()["state"],
            "proposed",
        )
        self.assertEqual(
            int(self.connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]),
            0,
        )
        self.assertEqual(
            int(
                self.connection.execute(
                    "SELECT uses FROM policy_grants WHERE id = ?",
                    (str(GRANT_ID),),
                ).fetchone()[0]
            ),
            0,
        )

    def test_policy_grant_last_use_marks_grant_exhausted(self) -> None:
        self._seed_common()
        self._insert_grant(self._grant(max_uses=1))

        self.service.authorize_with_policy_grant(
            action_id=str(ACTION_ID),
            grant_id=str(GRANT_ID),
            material=self.material,
            context=self._context(),
            actor=self.actor,
        )

        grant = self.connection.execute(
            "SELECT uses, state FROM policy_grants WHERE id = ?",
            (str(GRANT_ID),),
        ).fetchone()
        self.assertEqual((int(grant["uses"]), grant["state"]), (1, "exhausted"))

    def test_outbox_failure_rolls_back_action_event_and_grant_use(self) -> None:
        self._seed_common()
        self._insert_grant(self._grant())
        self.connection.execute(
            """
            CREATE TRIGGER d2_admission_outbox_fault
            BEFORE INSERT ON outbox_events
            BEGIN
                SELECT RAISE(ABORT, 'injected outbox fault');
            END
            """
        )

        with self.assertRaises(Exception):
            self.service.authorize_with_policy_grant(
                action_id=str(ACTION_ID),
                grant_id=str(GRANT_ID),
                material=self.material,
                context=self._context(),
                actor=self.actor,
            )

        action = self.connection.execute(
                "SELECT state, authorization_ref FROM actions WHERE id = ?",
                (str(ACTION_ID),),
        ).fetchone()
        self.assertEqual(
            (action["state"], action["authorization_ref"]),
            ("proposed", None),
        )
        self.assertEqual(
            int(self.connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]),
            0,
        )
        self.assertEqual(
            int(
                self.connection.execute(
                    "SELECT uses FROM policy_grants WHERE id = ?",
                    (str(GRANT_ID),),
                ).fetchone()[0]
            ),
            0,
        )

    def test_approval_hit_consumes_once_and_replay_fails_closed(self) -> None:
        self._seed_common(action_state="waiting_approval")
        self._insert_approval(self._approval())

        self.service.authorize_with_approval(
            action_id=str(ACTION_ID),
            approval_id=str(APPROVAL_ID),
            material=self.material,
            actor=self.actor,
        )

        self.assertEqual(
            int(
                self.connection.execute(
                    "SELECT COUNT(*) FROM approval_consumptions"
                ).fetchone()[0]
            ),
            1,
        )
        with self.assertRaises(AdmissionStateError) as captured:
            self.service.authorize_with_approval(
                action_id=str(ACTION_ID),
                approval_id=str(APPROVAL_ID),
                material=self.material,
                actor=self.actor,
            )
        self.assertEqual(captured.exception.code, "E_ACTION_NOT_AUTHORIZEABLE")
        self.assertEqual(
            int(self.connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]),
            1,
        )

    def test_existing_approval_consumption_blocks_replay_before_state_change(self) -> None:
        self._seed_common(action_state="waiting_approval")
        self._insert_approval(self._approval())
        with self.connection:
            event_id = self.connection.execute(
                """
                INSERT INTO events (
                    aggregate_type, aggregate_id, aggregate_version,
                    run_id, run_seq, action_id, actor_json, type,
                    payload_json, occurred_at
                ) VALUES ('action', ?, 1, ?, 1, ?, ?, 'action.authorized', ?, ?)
                """,
                (
                    str(ACTION_ID),
                    str(RUN_ID),
                    str(ACTION_ID),
                    _json(self.actor.model_dump(mode="json")),
                    '{"state":"authorized"}',
                    NOW_TEXT,
                ),
            ).lastrowid
            self.connection.execute(
                """
                INSERT INTO approval_consumptions(
                    approval_id, action_id, event_id, consumed_at
                ) VALUES (?, ?, ?, ?)
                """,
                (str(APPROVAL_ID), str(ACTION_ID), int(event_id), NOW_TEXT),
            )

        with self.assertRaises(AdmissionStateError) as captured:
            self.service.authorize_with_approval(
                action_id=str(ACTION_ID),
                approval_id=str(APPROVAL_ID),
                material=self.material,
                actor=self.actor,
            )

        self.assertEqual(captured.exception.code, "E_APPROVAL_DENIED")
        self.assertEqual(
            self.connection.execute(
                "SELECT state FROM actions WHERE id = ?",
                (str(ACTION_ID),),
            ).fetchone()[0],
            "waiting_approval",
        )

    def test_material_must_match_args_artifact_and_action_hash(self) -> None:
        self._seed_common()
        self._insert_grant(self._grant())
        tampered = _material(args={"test_id": "not-allowlisted"})

        with self.assertRaises(AdmissionStateError) as captured:
            self.service.authorize_with_policy_grant(
                action_id=str(ACTION_ID),
                grant_id=str(GRANT_ID),
                material=tampered,
                context=self._context(),
                actor=self.actor,
            )

        self.assertEqual(captured.exception.code, "E_ARGS_MATERIAL_MISMATCH")
        self.assertEqual(
            self.connection.execute(
                "SELECT state FROM actions WHERE id = ?",
                (str(ACTION_ID),),
            ).fetchone()["state"],
            "proposed",
        )

    def test_second_connection_cannot_authorize_same_action_twice(self) -> None:
        self._seed_common()
        self._insert_grant(self._grant(max_uses=2))
        self.service.authorize_with_policy_grant(
            action_id=str(ACTION_ID),
            grant_id=str(GRANT_ID),
            material=self.material,
            context=self._context(),
            actor=self.actor,
        )
        other = connect_database(self.path)
        try:
            service = CapabilityAdmissionService(
                other,
                now=lambda: NOW_TEXT,
                load_args_artifact=lambda row: self.args_bytes,
            )
            with self.assertRaises(AdmissionStateError):
                service.authorize_with_policy_grant(
                    action_id=str(ACTION_ID),
                    grant_id=str(GRANT_ID),
                    material=self.material,
                    context=self._context(),
                    actor=self.actor,
                )
        finally:
            other.close()
        self.assertEqual(
            int(self.connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]),
            1,
        )


if __name__ == "__main__":
    unittest.main()
