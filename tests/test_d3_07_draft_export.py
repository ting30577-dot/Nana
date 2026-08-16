"""Focused D3-07 Approval, selection and controlled export evidence."""

from __future__ import annotations

import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

from nana_sidecar.contracts.builtin_capabilities import (
    DRAFT_EXPORT_FILENAME,
    EXPORT_DRAFT_EXTERNAL_CAPABILITY,
    export_draft_external_registry_entry,
)
from nana_sidecar.contracts.journey import (
    DecideApprovalRequest,
    DraftFindingRequest,
    RequestApprovalRequest,
    StartRunRequest,
)
from nana_sidecar.dev_journey_fixture import (
    frozen_resource_descriptor,
    load_dev_journey,
    local_fixture_actor,
    read_dev_journey_definition,
    workspace_bootstrap_spec,
)
from nana_sidecar.export_selection import ExportSelectionRegistry
from nana_sidecar.sse import LocalSession
from nana_sidecar.storage.draft_export import (
    DRAFT_REPORT_RENDERER_DIGEST,
    DraftExportService,
    EXPORT_CREDENTIAL_CANARIES,
    render_draft_report,
)
from nana_sidecar.storage.command_transactions import CommandExecutionError
from nana_sidecar.storage.database import connect_database
from nana_sidecar.storage.journey_commands import (
    JourneyCommandService,
    WorkspaceBootstrapService,
)
from nana_sidecar.storage.workspace_lock import WorkspaceRuntime


TOKEN = "d3-07-selection-" + "s" * 40
ORIGIN = "http://127.0.0.1:43123"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class D307DraftExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.workspace_root = root / "workspace"
        self.target = root / "dedicated-export"
        self.target.mkdir()
        self.workspace = WorkspaceRuntime(self.workspace_root / "nana.db")
        self.workspace.start()
        self.definition = read_dev_journey_definition()
        self.actor = local_fixture_actor()
        self.session = LocalSession(token=TOKEN, origin=ORIGIN)
        self.selections = ExportSelectionRegistry(
            session=self.session,
            workspace_root=self.workspace_root,
            actor_id=str(self.actor.id),
            allow_test_harness=True,
        )
        self.summary = self.selections.register_test_harness_target(str(self.target))
        self.connection = self.workspace.connection
        assert self.connection is not None
        WorkspaceBootstrapService(self.connection).ensure(
            workspace_bootstrap_spec(self.definition)
        )
        self.service = JourneyCommandService(
            self.connection,
            actor=self.actor,
            resources=(frozen_resource_descriptor(self.definition),),
            now=_now,
            export_selections=self.selections,
        )
        loaded = load_dev_journey(self.service, self.definition)
        self.ids = {key: str(value) for key, value in loaded.ids.items()}
        run_result = self.service.execute(
            StartRunRequest(
                type="StartRun",
                command_id=uuid4(),
                expected_revision=1,
                project_id=self.ids["project"],
                inquiry_id=self.ids["inquiry"],
                plan_id=self.ids["plan"],
                plan_revision=1,
                random_seed=0,
            )
        )
        self.run_id = next(
            key.split(":", 1)[1]
            for key in run_result.affected_revisions
            if key.startswith("run:")
        )
        finding_result = self.service.execute(
            DraftFindingRequest(
                type="DraftFinding",
                command_id=uuid4(),
                expected_revision=1,
                inquiry_id=self.ids["inquiry"],
                statement="The locked public result supports the monotonicity premise.",
                confidence_basis="The canonical successful Run and Receipt provide deterministic evidence.",
                evidence_ids=(),
                terminal_run_ids=(self.run_id,),
            )
        )
        self.finding_id = next(
            key.split(":", 1)[1]
            for key in finding_result.affected_revisions
            if key.startswith("finding:")
        )

    def tearDown(self) -> None:
        self.selections.close()
        if self.workspace.state == "ready":
            self.workspace.close()
        self.tempdir.cleanup()

    def _prepare(self):
        result = self.service.execute(
            RequestApprovalRequest(
                type="RequestApproval",
                command_id=uuid4(),
                expected_revision=1,
                finding_id=self.finding_id,
                target_selection_id=self.summary.selection_id,
            )
        )
        approval_id = next(
            key.split(":", 1)[1]
            for key in result.affected_revisions
            if key.startswith("approval:")
        )
        action_id = next(
            key.split(":", 1)[1]
            for key in result.affected_revisions
            if key.startswith("action:")
        )
        subject_hash = str(
            self.connection.execute(
                "SELECT subject_hash FROM approvals WHERE id = ?",
                (approval_id,),
            ).fetchone()[0]
        )
        return result, approval_id, action_id, subject_hash

    def test_exact_capability_is_one_time_non_grantable_and_canary_set_is_fixed(self) -> None:
        entry = export_draft_external_registry_entry()
        self.assertEqual(entry.capability, EXPORT_DRAFT_EXTERNAL_CAPABILITY)
        self.assertEqual(entry.risk_tier.value, "T3")
        self.assertFalse(entry.grantable)
        self.assertFalse(entry.reversible)
        self.assertEqual(entry.authorization_mode.value, "one_time_approval")
        self.assertEqual(entry.write_roots, ("external:fixed_local_draft_target",))
        self.assertEqual(len(EXPORT_CREDENTIAL_CANARIES), 50)
        self.assertTrue(DRAFT_REPORT_RENDERER_DIGEST.startswith("sha256:"))

    def test_prepare_persists_no_raw_path_or_opaque_selection_token(self) -> None:
        self._prepare()
        dump = "\n".join(self.connection.iterdump())
        self.assertNotIn(str(self.target), dump)
        self.assertNotIn(self.summary.selection_id, dump)
        self.assertNotIn(str(self.target.parent), dump)

    def test_renderer_rejects_paths_markup_and_all_fixed_canaries(self) -> None:
        common = {
            "inquiry_question": "A public question?",
            "finding_statement": "A public finding.",
            "confidence_basis": "Canonical evidence.",
            "algorithm_run_id": str(uuid4()),
            "source_artifact_hash": "sha256:" + "a" * 64,
        }
        for unsafe in (
            "C:\\Users\\person\\secret.txt",
            "https://example.invalid/private",
            "<script>alert(1)</script>",
            "# injected heading",
            *EXPORT_CREDENTIAL_CANARIES,
        ):
            with self.subTest(unsafe=unsafe):
                with self.assertRaises(Exception):
                    render_draft_report(**{**common, "finding_statement": unsafe})

    def test_prepare_replays_after_terminal_selection_close(self) -> None:
        request = RequestApprovalRequest(
            type="RequestApproval",
            command_id=uuid4(),
            expected_revision=1,
            finding_id=self.finding_id,
            target_selection_id=self.summary.selection_id,
        )
        first = self.service.execute(request)
        approval_id = next(
            key.split(":", 1)[1]
            for key in first.affected_revisions
            if key.startswith("approval:")
        )
        subject_hash = self.connection.execute(
            "SELECT subject_hash FROM approvals WHERE id = ?",
            (approval_id,),
        ).fetchone()[0]
        self.service.execute(
            DecideApprovalRequest(
                type="DecideApproval",
                command_id=uuid4(),
                expected_revision=1,
                approval_id=approval_id,
                subject_hash=subject_hash,
                decision="approved",
            )
        )
        DraftExportService(
            self.connection,
            actor=self.actor,
            selections=self.selections,
            now=_now,
        ).execute_authorized(approval_id)
        replay = self.service.execute(request)
        self.assertEqual(replay.status.value, "replayed")

    def test_expired_decision_atomically_expires_then_cancels_without_authority(self) -> None:
        _result, approval_id, action_id, subject_hash = self._prepare()
        future = datetime.now(timezone.utc) + timedelta(hours=2)
        with self.assertRaises(CommandExecutionError) as captured:
            DraftExportService(
                self.connection,
                actor=self.actor,
                selections=self.selections,
                now=lambda: future.isoformat().replace("+00:00", "Z"),
            ).decide(
                DecideApprovalRequest(
                    type="DecideApproval",
                    command_id=uuid4(),
                    expected_revision=1,
                    approval_id=approval_id,
                    subject_hash=subject_hash,
                    decision="approved",
                )
            )
        self.assertEqual(captured.exception.error.code.value, "E_APPROVAL_EXPIRED")
        facts = self.connection.execute(
            "SELECT approvals.decision, actions.state, runs.state, "
            "(SELECT COUNT(*) FROM approval_consumptions WHERE approval_id = approvals.id), "
            "(SELECT COUNT(*) FROM action_authorizations WHERE action_id = actions.id), "
            "(SELECT COUNT(*) FROM action_receipts WHERE action_id = actions.id) "
            "FROM approvals JOIN actions ON actions.id = approvals.subject_id "
            "JOIN runs ON runs.id = actions.run_id WHERE approvals.id = ?",
            (approval_id,),
        ).fetchone()
        self.assertEqual(tuple(facts), ("expired", "cancelled", "cancelled", 0, 0, 0))
        self.assertEqual(tuple(self.target.iterdir()), ())

    def test_approved_decision_atomically_authorizes_consumes_and_writes_fixed_draft(self) -> None:
        _result, approval_id, action_id, subject_hash = self._prepare()
        decision = self.service.execute(
            DecideApprovalRequest(
                type="DecideApproval",
                command_id=uuid4(),
                expected_revision=1,
                approval_id=approval_id,
                subject_hash=subject_hash,
                decision="approved",
            )
        )
        self.assertEqual(decision.status.value, "accepted")
        facts = self.connection.execute(
            "SELECT approvals.decision, actions.state, "
            "(SELECT COUNT(*) FROM approval_consumptions WHERE approval_id = approvals.id), "
            "(SELECT COUNT(*) FROM action_authorizations WHERE action_id = actions.id) "
            "FROM approvals JOIN actions ON actions.id = approvals.subject_id WHERE approvals.id = ?",
            (approval_id,),
        ).fetchone()
        self.assertEqual(tuple(facts), ("approved", "authorized", 1, 1))

        DraftExportService(
            self.connection,
            actor=self.actor,
            selections=self.selections,
            now=_now,
        ).execute_authorized(approval_id)

        output = self.target / DRAFT_EXPORT_FILENAME
        self.assertTrue(output.is_file())
        content = output.read_bytes()
        self.assertTrue(content.startswith(b"# Nana D3 Draft Report\n"))
        self.assertTrue(content.endswith(b"\n"))
        terminal = self.connection.execute(
            "SELECT actions.state, runs.state, action_receipts.result, "
            "(SELECT COUNT(*) FROM external_write_fences WHERE action_id = actions.id) "
            "FROM actions JOIN runs ON runs.id = actions.run_id "
            "JOIN action_receipts ON action_receipts.action_id = actions.id "
            "WHERE actions.id = ?",
            (action_id,),
        ).fetchone()
        self.assertEqual(tuple(terminal), ("succeeded", "succeeded", "succeeded", 1))

    def test_denied_decision_never_authorizes_consumes_writes_or_receipts(self) -> None:
        _result, approval_id, action_id, subject_hash = self._prepare()
        self.service.execute(
            DecideApprovalRequest(
                type="DecideApproval",
                command_id=uuid4(),
                expected_revision=1,
                approval_id=approval_id,
                subject_hash=subject_hash,
                decision="denied",
            )
        )
        facts = self.connection.execute(
            "SELECT approvals.decision, actions.state, runs.state, "
            "(SELECT COUNT(*) FROM approval_consumptions WHERE approval_id = approvals.id), "
            "(SELECT COUNT(*) FROM action_authorizations WHERE action_id = actions.id), "
            "(SELECT COUNT(*) FROM action_receipts WHERE action_id = actions.id) "
            "FROM approvals JOIN actions ON actions.id = approvals.subject_id "
            "JOIN runs ON runs.id = actions.run_id WHERE approvals.id = ?",
            (approval_id,),
        ).fetchone()
        self.assertEqual(tuple(facts), ("denied", "cancelled", "cancelled", 0, 0, 0))
        self.assertEqual(tuple(self.target.iterdir()), ())

    def test_two_connections_racing_approval_consume_exactly_once(self) -> None:
        _result, approval_id, action_id, subject_hash = self._prepare()
        barrier = threading.Barrier(2)

        def decide_once(command_id: str) -> str:
            connection = connect_database(self.workspace.database_path)
            try:
                service = DraftExportService(
                    connection,
                    actor=self.actor,
                    selections=self.selections,
                    now=_now,
                )
                barrier.wait(timeout=5)
                try:
                    result = service.decide(
                        DecideApprovalRequest(
                            type="DecideApproval",
                            command_id=command_id,
                            expected_revision=1,
                            approval_id=approval_id,
                            subject_hash=subject_hash,
                            decision="approved",
                        )
                    )
                except CommandExecutionError:
                    return "rejected"
                return result.status.value
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = tuple(
                executor.map(decide_once, (str(uuid4()), str(uuid4())))
            )
        self.assertEqual(sorted(outcomes), ["accepted", "rejected"])
        counts = self.connection.execute(
            "SELECT "
            "(SELECT COUNT(*) FROM approval_consumptions WHERE approval_id = ?), "
            "(SELECT COUNT(*) FROM action_authorizations WHERE action_id = ?), "
            "(SELECT COUNT(*) FROM events WHERE aggregate_type = 'action' AND aggregate_id = ? AND type = 'action.authorized')",
            (approval_id, action_id, action_id),
        ).fetchone()
        self.assertEqual(tuple(counts), (1, 1, 1))

    def test_approved_transaction_rolls_back_every_fact_then_retries(self) -> None:
        _result, approval_id, action_id, subject_hash = self._prepare()
        request = DecideApprovalRequest(
            type="DecideApproval",
            command_id=uuid4(),
            expected_revision=1,
            approval_id=approval_id,
            subject_hash=subject_hash,
            decision="approved",
        )

        def fail_before_commit(name: str) -> None:
            if name == "before_commit":
                raise OSError("injected Approval commit failure")

        with self.assertRaisesRegex(OSError, "injected Approval"):
            DraftExportService(
                self.connection,
                actor=self.actor,
                selections=self.selections,
                now=_now,
                checkpoint=fail_before_commit,
            ).decide(request)
        facts = self.connection.execute(
            "SELECT approvals.decision, actions.state, "
            "(SELECT COUNT(*) FROM approval_consumptions WHERE approval_id = approvals.id), "
            "(SELECT COUNT(*) FROM action_authorizations WHERE action_id = actions.id), "
            "(SELECT COUNT(*) FROM command_log WHERE command_id = ?) "
            "FROM approvals JOIN actions ON actions.id = approvals.subject_id WHERE approvals.id = ?",
            (str(request.command_id), approval_id),
        ).fetchone()
        self.assertEqual(tuple(facts), ("requested", "waiting_approval", 0, 0, 0))

        replay = DraftExportService(
            self.connection,
            actor=self.actor,
            selections=self.selections,
            now=_now,
        ).decide(request)
        self.assertEqual(replay.status.value, "accepted")

    def test_preparation_crash_leaves_only_workspace_artifacts_and_retries_one_subject(self) -> None:
        request = RequestApprovalRequest(
            type="RequestApproval",
            command_id=uuid4(),
            expected_revision=1,
            finding_id=self.finding_id,
            target_selection_id=self.summary.selection_id,
        )

        def fail_before_commit(name: str) -> None:
            if name == "before_commit":
                raise OSError("injected subject commit failure")

        with self.assertRaisesRegex(OSError, "subject commit"):
            DraftExportService(
                self.connection,
                actor=self.actor,
                selections=self.selections,
                now=_now,
                checkpoint=fail_before_commit,
            ).prepare(request)
        counts = self.connection.execute(
            "SELECT "
            "(SELECT COUNT(*) FROM runs WHERE json_extract(snapshot_json, '$.kind') = 'draft_export_v1'), "
            "(SELECT COUNT(*) FROM actions WHERE capability_id = 'export.draft_external'), "
            "(SELECT COUNT(*) FROM approvals WHERE capability_json LIKE '%export.draft_external%'), "
            "(SELECT COUNT(*) FROM artifacts WHERE json_extract(retention_json, '$.kind') IN ('d3_public_draft_report', 'd3_export_action_args'))"
        ).fetchone()
        self.assertEqual(tuple(counts), (0, 0, 0, 2))
        accepted = self.service.execute(request)
        self.assertEqual(accepted.status.value, "accepted")
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM actions WHERE capability_id = 'export.draft_external'"
            ).fetchone()[0],
            1,
        )

    def test_approval_consumption_and_write_fence_are_append_only(self) -> None:
        _result, approval_id, action_id, subject_hash = self._prepare()
        self.service.execute(
            DecideApprovalRequest(
                type="DecideApproval",
                command_id=uuid4(),
                expected_revision=1,
                approval_id=approval_id,
                subject_hash=subject_hash,
                decision="approved",
            )
        )
        DraftExportService(
            self.connection,
            actor=self.actor,
            selections=self.selections,
            now=_now,
        ).execute_authorized(approval_id)
        import sqlite3

        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "UPDATE approvals SET subject_hash = ? WHERE id = ?",
                ("sha256:" + "f" * 64, approval_id),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "UPDATE approvals SET decision = 'denied' WHERE id = ?",
                (approval_id,),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "DELETE FROM approval_consumptions WHERE approval_id = ?",
                (approval_id,),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "DELETE FROM external_write_fences WHERE action_id = ?",
                (action_id,),
            )
        self.connection.rollback()

    def test_response_loss_replay_returns_one_committed_consumption(self) -> None:
        _result, approval_id, action_id, subject_hash = self._prepare()
        request = DecideApprovalRequest(
            type="DecideApproval",
            command_id=uuid4(),
            expected_revision=1,
            approval_id=approval_id,
            subject_hash=subject_hash,
            decision="approved",
        )
        raised = False

        def lose_response(name: str) -> None:
            nonlocal raised
            if name == "after_commit" and not raised:
                raised = True
                raise ConnectionError("injected response loss")

        service = DraftExportService(
            self.connection,
            actor=self.actor,
            selections=self.selections,
            now=_now,
            checkpoint=lose_response,
        )
        with self.assertRaisesRegex(ConnectionError, "response loss"):
            service.decide(request)
        replay = service.decide(request)
        self.assertEqual(replay.status.value, "replayed")
        counts = self.connection.execute(
            "SELECT "
            "(SELECT COUNT(*) FROM approval_consumptions WHERE approval_id = ?), "
            "(SELECT COUNT(*) FROM action_authorizations WHERE action_id = ?)",
            (approval_id, action_id),
        ).fetchone()
        self.assertEqual(tuple(counts), (1, 1))

    def test_probe_failure_cleans_target_and_records_observed_effect(self) -> None:
        _result, approval_id, action_id, subject_hash = self._prepare()
        self.service.execute(
            DecideApprovalRequest(
                type="DecideApproval",
                command_id=uuid4(),
                expected_revision=1,
                approval_id=approval_id,
                subject_hash=subject_hash,
                decision="approved",
            )
        )
        with patch("nana_sidecar.storage.draft_export.os.rename", side_effect=OSError("unsupported")):
            DraftExportService(
                self.connection,
                actor=self.actor,
                selections=self.selections,
                now=_now,
            ).execute_authorized(approval_id)
        row = self.connection.execute(
            "SELECT actions.state, action_receipts.result, action_receipts.actual_effects_json "
            "FROM actions JOIN action_receipts ON action_receipts.action_id = actions.id WHERE actions.id = ?",
            (action_id,),
        ).fetchone()
        self.assertEqual((row["state"], row["result"]), ("failed", "failed"))
        self.assertEqual(
            __import__("json").loads(str(row["actual_effects_json"]))["writes"],
            ["external:fixed_local_draft_target"],
        )
        self.assertEqual(tuple(self.target.iterdir()), ())

    def test_crash_after_external_write_is_effect_unknown_and_never_retried(self) -> None:
        _result, approval_id, action_id, subject_hash = self._prepare()
        self.service.execute(
            DecideApprovalRequest(
                type="DecideApproval",
                command_id=uuid4(),
                expected_revision=1,
                approval_id=approval_id,
                subject_hash=subject_hash,
                decision="approved",
            )
        )

        def crash(name: str) -> None:
            if name == "external_write_completed":
                raise OSError("injected post-write crash")

        DraftExportService(
            self.connection,
            actor=self.actor,
            selections=self.selections,
            now=_now,
            checkpoint=crash,
        ).execute_authorized(approval_id)
        row = self.connection.execute(
            "SELECT actions.state, runs.state, action_receipts.result FROM actions "
            "JOIN runs ON runs.id = actions.run_id JOIN action_receipts ON action_receipts.action_id = actions.id "
            "WHERE actions.id = ?",
            (action_id,),
        ).fetchone()
        self.assertEqual(tuple(row), ("effect_unknown", "orphaned", "effect_unknown"))
        self.assertTrue((self.target / DRAFT_EXPORT_FILENAME).exists())
        DraftExportService(
            self.connection,
            actor=self.actor,
            selections=self.selections,
            now=_now,
        ).execute_authorized(approval_id)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM action_receipts WHERE action_id = ?",
                (action_id,),
            ).fetchone()[0],
            1,
        )

    def test_crash_after_fence_before_first_os_write_is_effect_unknown(self) -> None:
        _result, approval_id, action_id, subject_hash = self._prepare()
        self.service.execute(
            DecideApprovalRequest(
                type="DecideApproval",
                command_id=uuid4(),
                expected_revision=1,
                approval_id=approval_id,
                subject_hash=subject_hash,
                decision="approved",
            )
        )

        def crash(name: str) -> None:
            if name == "first_write_fence_committed":
                raise OSError("injected fence crash")

        DraftExportService(
            self.connection,
            actor=self.actor,
            selections=self.selections,
            now=_now,
            checkpoint=crash,
        ).execute_authorized(approval_id)
        row = self.connection.execute(
            "SELECT actions.state, runs.state, action_receipts.result FROM actions "
            "JOIN runs ON runs.id = actions.run_id JOIN action_receipts ON action_receipts.action_id = actions.id "
            "WHERE actions.id = ?",
            (action_id,),
        ).fetchone()
        self.assertEqual(tuple(row), ("effect_unknown", "orphaned", "effect_unknown"))
        self.assertEqual(tuple(self.target.iterdir()), ())

    def test_restart_without_fence_fails_empty_and_with_fence_is_uncertain(self) -> None:
        for fenced in (False, True):
            with self.subTest(fenced=fenced):
                if tuple(self.target.iterdir()):
                    for path in self.target.iterdir():
                        path.unlink()
                if fenced:
                    # Each attempt needs a fresh selection and chain.
                    self.selections.close()
                    self.selections = ExportSelectionRegistry(
                        session=self.session,
                        workspace_root=self.workspace_root,
                        actor_id=str(self.actor.id),
                        allow_test_harness=True,
                    )
                    self.summary = self.selections.register_test_harness_target(str(self.target))
                    self.service = JourneyCommandService(
                        self.connection,
                        actor=self.actor,
                        resources=(frozen_resource_descriptor(self.definition),),
                        now=_now,
                        export_selections=self.selections,
                    )
                _result, approval_id, action_id, subject_hash = self._prepare()
                self.service.execute(
                    DecideApprovalRequest(
                        type="DecideApproval",
                        command_id=uuid4(),
                        expected_revision=1,
                        approval_id=approval_id,
                        subject_hash=subject_hash,
                        decision="approved",
                    )
                )
                active = DraftExportService(
                    self.connection,
                    actor=self.actor,
                    selections=self.selections,
                    now=_now,
                )
                if fenced:
                    run_id = active._action_run_id(action_id)
                    active._claim_action(run_id, action_id)
                    selection = self.selections.bound_for_action(action_id, actor_id=str(self.actor.id))
                    active._commit_first_write_fence(
                        action_id,
                        run_id,
                        selection.identity_digest,
                        selection.target_commitment,
                    )
                self.selections.close()
                self.workspace.close()
                self.workspace = WorkspaceRuntime(self.workspace_root / "nana.db")
                self.workspace.start()
                self.connection = self.workspace.connection
                assert self.connection is not None
                restarted_session = LocalSession(token=TOKEN + "r", origin=ORIGIN)
                self.selections = ExportSelectionRegistry(
                    session=restarted_session,
                    workspace_root=self.workspace_root,
                    actor_id=str(self.actor.id),
                    allow_test_harness=True,
                )
                reconciler = DraftExportService(
                    self.connection,
                    actor=self.actor,
                    selections=self.selections,
                    now=_now,
                )
                self.assertEqual(reconciler.reconcile_startup(), 1)
                row = self.connection.execute(
                    "SELECT actions.state, runs.state, action_receipts.result FROM actions "
                    "JOIN runs ON runs.id = actions.run_id JOIN action_receipts ON action_receipts.action_id = actions.id "
                    "WHERE actions.id = ?",
                    (action_id,),
                ).fetchone()
                expected = (
                    ("effect_unknown", "orphaned", "effect_unknown")
                    if fenced
                    else ("failed", "failed", "failed")
                )
                self.assertEqual(tuple(row), expected)
                self.assertEqual(tuple(self.target.iterdir()), ())


if __name__ == "__main__":
    unittest.main()
