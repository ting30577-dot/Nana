"""D3-05 curated research-journey transaction tests."""

from __future__ import annotations

import inspect
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from pydantic import TypeAdapter

from nana_sidecar.contracts.commands import CommandStatus
from nana_sidecar.contracts.common import DataClass
from nana_sidecar.contracts.domain import EventType
from nana_sidecar.contracts.journey import JourneyCommandRequest
from nana_sidecar.dev_journey_fixture import (
    frozen_resource_descriptor,
    load_dev_journey,
    local_fixture_actor,
    read_dev_journey_definition,
    workspace_bootstrap_spec,
)
from nana_sidecar.storage.command_transactions import CommandExecutionError
from nana_sidecar.storage.database import initialize_database
from nana_sidecar.storage.journey_commands import (
    FrozenResourceDescriptor,
    JourneyCommandService,
    WorkspaceBootstrapService,
)
from nana_sidecar.storage.schema import SCHEMA_V1_SQL


REQUESTS = TypeAdapter(JourneyCommandRequest)
NOW = "2026-08-08T00:00:01Z"


class D3JourneyCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.tempdir.name) / "nana.db"
        self.connection = initialize_database(self.database_path)
        self.definition = read_dev_journey_definition()
        self.spec = workspace_bootstrap_spec(self.definition)
        self.descriptor = frozen_resource_descriptor(self.definition)
        WorkspaceBootstrapService(self.connection).ensure(self.spec)
        self.service = JourneyCommandService(
            self.connection,
            actor=local_fixture_actor(),
            resources=(self.descriptor,),
            now=lambda: NOW,
        )

    def tearDown(self) -> None:
        self.connection.close()
        self.tempdir.cleanup()

    def test_existing_event_registry_covers_d3_05_without_new_types(self) -> None:
        required = {
            "workspace.created",
            "resource.registered",
            "locator.created",
            "evidence.attached",
            "hypothesis.created",
        }
        self.assertTrue(required <= {event.value for event in EventType})
        for event_type in required:
            self.assertIn(f"'{event_type}'", SCHEMA_V1_SQL)

    def test_workspace_bootstrap_is_exactly_idempotent_and_creates_no_hypothesis(self) -> None:
        before = self._counts()
        event_id = WorkspaceBootstrapService(self.connection).ensure(self.spec)
        self.assertEqual(self._counts(), before)
        self.assertEqual(
            event_id,
            self.connection.execute(
                "SELECT id FROM events WHERE type = 'workspace.created'"
            ).fetchone()["id"],
        )
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM hypotheses").fetchone()[0],
            0,
        )

    def test_workspace_bootstrap_rolls_back_before_commit_failure(self) -> None:
        other = Path(self.tempdir.name) / "rollback.db"
        connection = initialize_database(other)
        try:
            def fail(name: str) -> None:
                if name == "before_commit":
                    raise RuntimeError("injected bootstrap fault")

            with self.assertRaisesRegex(RuntimeError, "injected bootstrap fault"):
                WorkspaceBootstrapService(connection, checkpoint=fail).ensure(self.spec)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM workspaces").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM events").fetchone()[0], 0)
            self.assertFalse(connection.in_transaction)
        finally:
            connection.close()

    def test_fixture_loader_replays_identical_ids_without_duplicate_effects(self) -> None:
        first = load_dev_journey(self.service, self.definition)
        counts = self._counts()
        second = load_dev_journey(self.service, self.definition)
        self.assertEqual(second.ids, first.ids)
        self.assertTrue(all(result.status is CommandStatus.ACCEPTED for result in first.command_results))
        self.assertTrue(all(result.status is CommandStatus.REPLAYED for result in second.command_results))
        self.assertEqual(self._counts(), counts)
        loader_source = inspect.getsource(load_dev_journey)
        self.assertNotIn("connection.execute", loader_source)
        self.assertNotIn("sqlite3", loader_source)

    def test_fixture_actor_is_server_injected_in_commands_and_events(self) -> None:
        load_dev_journey(self.service, self.definition)
        command_actors = {
            row["actor_json"]
            for row in self.connection.execute("SELECT actor_json FROM command_log")
        }
        event_actors = {
            row["actor_json"]
            for row in self.connection.execute(
                "SELECT actor_json FROM events WHERE causation_id IS NOT NULL"
            )
        }
        expected = json.dumps(
            local_fixture_actor().model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        self.assertEqual(command_actors, {expected})
        self.assertEqual(event_actors, {expected})

    def test_changed_payload_with_same_command_id_fails_closed(self) -> None:
        load_dev_journey(self.service, self.definition)
        payload = {
            "type": "CreateProject",
            "command_id": self.definition["commands"]["project"],
            "expected_revision": 1,
            "workspace_id": self.definition["workspace"]["id"],
            "title": "changed title",
            "data_class": "public",
        }
        with self.assertRaises(CommandExecutionError) as caught:
            self.service.execute(REQUESTS.validate_python(payload))
        self.assertFalse(caught.exception.replayed)
        self.assertEqual(caught.exception.error.category.value, "conflict")

    def test_rejected_command_is_bound_and_replayed_without_side_effects(self) -> None:
        payload = {
            "type": "CreateInquiry",
            "command_id": str(uuid4()),
            "expected_revision": 1,
            "project_id": str(uuid4()),
            "question": "missing project",
            "acceptance": "must reject",
        }
        request = REQUESTS.validate_python(payload)
        before = self._counts()
        with self.assertRaises(CommandExecutionError) as first:
            self.service.execute(request)
        with self.assertRaises(CommandExecutionError) as replay:
            self.service.execute(request)
        self.assertFalse(first.exception.replayed)
        self.assertTrue(replay.exception.replayed)
        after = self._counts()
        self.assertEqual(after["events"], before["events"])
        self.assertEqual(after["outbox_events"], before["outbox_events"])
        self.assertEqual(after["command_log"], before["command_log"] + 1)

    def test_duplicate_evidence_and_relation_are_transactional_rejections(self) -> None:
        loaded = load_dev_journey(self.service, self.definition)
        resource = self.definition["resource"]
        duplicate_evidence = REQUESTS.validate_python({
            "type": "AttachEvidence",
            "command_id": str(uuid4()),
            "expected_revision": 1,
            "inquiry_id": str(loaded.ids["inquiry"]),
            "locator_id": str(loaded.ids["locator"]),
            "direction": self.definition["evidence"]["direction"],
            "excerpt_hash": resource["quote_hash"],
        })
        duplicate_relation = REQUESTS.validate_python({
            "type": "CreateRelation",
            "command_id": str(uuid4()),
            "expected_revision": 1,
            "relation_type": "evidence_supports_claim",
            "source_type": "evidence",
            "source_id": str(loaded.ids["evidence"]),
            "target_type": "claim",
            "target_id": str(loaded.ids["claim"]),
        })
        before = self._counts()
        for request in (duplicate_evidence, duplicate_relation):
            with self.assertRaises(CommandExecutionError):
                self.service.execute(request)
            self.assertFalse(self.connection.in_transaction)
        after = self._counts()
        self.assertEqual(after["evidence"], before["evidence"])
        self.assertEqual(after["relations"], before["relations"])
        self.assertEqual(after["events"], before["events"])
        self.assertEqual(after["command_log"], before["command_log"] + 2)

    def test_frozen_descriptor_ids_and_refs_are_both_unique(self) -> None:
        duplicate_id = FrozenResourceDescriptor(
            descriptor_id=self.descriptor.descriptor_id,
            read_root=self.descriptor.read_root,
            logical_ref="fixtures/v0.3.0-dev/resources/another.md",
            media_type="text/markdown",
            data_class=DataClass.PUBLIC,
        )
        with self.assertRaisesRegex(ValueError, "uniquely"):
            JourneyCommandService(
                self.connection,
                actor=local_fixture_actor(),
                resources=(self.descriptor, duplicate_id),
                now=lambda: NOW,
            )

    def test_command_log_primary_key_and_begin_immediate_guard_are_present(self) -> None:
        columns = self.connection.execute("PRAGMA table_info(command_log)").fetchall()
        primary = [row["name"] for row in columns if int(row["pk"]) == 1]
        self.assertEqual(primary, ["command_id"])
        source = inspect.getsource(JourneyCommandService)
        transaction_source = inspect.getsource(
            __import__(
                "nana_sidecar.storage.command_transactions",
                fromlist=["CommandTransactionService"],
            ).CommandTransactionService
        )
        self.assertIn("execute_transactional", source)
        self.assertIn("BEGIN IMMEDIATE", transaction_source)

    def test_corrupted_stored_result_is_not_replayed(self) -> None:
        load_dev_journey(self.service, self.definition)
        command_id = self.definition["commands"]["project"]
        self.connection.execute(
            "UPDATE command_log SET result_json = ? WHERE command_id = ?",
            ('{"command_id":"broken"}', command_id),
        )
        self.connection.commit()
        payload = {
            "type": "CreateProject",
            "command_id": command_id,
            "expected_revision": 1,
            "workspace_id": self.definition["workspace"]["id"],
            "title": self.definition["project"]["title"],
            "data_class": self.definition["project"]["data_class"],
        }
        with self.assertRaises((RuntimeError, ValueError)):
            self.service.execute(REQUESTS.validate_python(payload))

    def test_rejected_replay_binds_actor_and_error_fields(self) -> None:
        payload = {
            "type": "CreateInquiry",
            "command_id": str(uuid4()),
            "expected_revision": 1,
            "project_id": str(uuid4()),
            "question": "missing project",
            "acceptance": "must reject",
        }
        request = REQUESTS.validate_python(payload)
        with self.assertRaises(CommandExecutionError):
            self.service.execute(request)
        command_id = str(request.command_id)
        self.connection.execute(
            "UPDATE command_log SET actor_json = ? WHERE command_id = ?",
            (json.dumps({"kind": "user", "id": "other", "version": None}, separators=(",", ":"), sort_keys=True), command_id),
        )
        self.connection.commit()
        with self.assertRaises(CommandExecutionError):
            self.service.execute(request)
        expected_actor = json.dumps(
            local_fixture_actor().model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        self.connection.execute(
            "UPDATE command_log SET actor_json = ? WHERE command_id = ?",
            (expected_actor, command_id),
        )
        self.connection.execute(
            "UPDATE command_log SET error_json = json_set(error_json, '$.message', 'tampered') "
            "WHERE command_id = ?",
            (command_id,),
        )
        self.connection.commit()
        with self.assertRaises(RuntimeError):
            self.service.execute(request)

    def test_accepted_replay_rejects_wrong_event_aggregate(self) -> None:
        loaded = load_dev_journey(self.service, self.definition)
        event_id = loaded.command_results[0].event_ids[0]
        self.connection.execute("DROP TRIGGER events_are_append_only_update")
        self.connection.execute(
            "UPDATE events SET aggregate_type = 'inquiry' WHERE id = ?",
            (event_id,),
        )
        self.connection.commit()
        payload = {
            "type": "CreateProject",
            "command_id": self.definition["commands"]["project"],
            "expected_revision": 1,
            "workspace_id": self.definition["workspace"]["id"],
            "title": self.definition["project"]["title"],
            "data_class": self.definition["project"]["data_class"],
        }
        with self.assertRaises(RuntimeError):
            self.service.execute(REQUESTS.validate_python(payload))

    def test_accepted_replay_rejects_tampered_event_payload(self) -> None:
        loaded = load_dev_journey(self.service, self.definition)
        event_id = loaded.command_results[0].event_ids[0]
        self.connection.execute("DROP TRIGGER events_are_append_only_update")
        self.connection.execute(
            "UPDATE events SET payload_json = json_set(payload_json, '$.workspace_id', ?) WHERE id = ?",
            (str(uuid4()), event_id),
        )
        self.connection.commit()
        payload = {
            "type": "CreateProject",
            "command_id": self.definition["commands"]["project"],
            "expected_revision": 1,
            "workspace_id": self.definition["workspace"]["id"],
            "title": self.definition["project"]["title"],
            "data_class": self.definition["project"]["data_class"],
        }
        with self.assertRaises(RuntimeError):
            self.service.execute(REQUESTS.validate_python(payload))

    def test_relation_requires_valid_evidence_not_lead(self) -> None:
        loaded = load_dev_journey(self.service, self.definition)
        self.connection.execute(
            "UPDATE evidence SET status = 'lead' WHERE id = ?",
            (str(loaded.ids["evidence"]),),
        )
        self.connection.commit()
        claim = self.service.execute(REQUESTS.validate_python({
            "type": "CreateClaim",
            "command_id": str(uuid4()),
            "expected_revision": 1,
            "inquiry_id": str(loaded.ids["inquiry"]),
            "statement": "A second claim for state validation",
        }))
        claim_id = self._affected_id(claim, "claim")
        with self.assertRaises(CommandExecutionError):
            self.service.execute(REQUESTS.validate_python({
                "type": "CreateRelation",
                "command_id": str(uuid4()),
                "expected_revision": 1,
                "relation_type": "evidence_supports_claim",
                "source_type": "evidence",
                "source_id": str(loaded.ids["evidence"]),
                "target_type": "claim",
                "target_id": str(claim_id),
            }))

    def test_relation_rejects_every_non_valid_evidence_status(self) -> None:
        loaded = load_dev_journey(self.service, self.definition)
        claim = self.service.execute(REQUESTS.validate_python({
            "type": "CreateClaim",
            "command_id": str(uuid4()),
            "expected_revision": 1,
            "inquiry_id": str(loaded.ids["inquiry"]),
            "statement": "Reject every non-valid evidence state",
        }))
        claim_id = self._affected_id(claim, "claim")
        for status in ("lead", "rejected", "stale", "source_unavailable", "tombstoned"):
            with self.subTest(status=status):
                self.connection.execute(
                    "UPDATE evidence SET status = ? WHERE id = ?",
                    (status, str(loaded.ids["evidence"])),
                )
                self.connection.commit()
                with self.assertRaises(CommandExecutionError):
                    self.service.execute(REQUESTS.validate_python({
                        "type": "CreateRelation",
                        "command_id": str(uuid4()),
                        "expected_revision": 1,
                        "relation_type": "evidence_supports_claim",
                        "source_type": "evidence",
                        "source_id": str(loaded.ids["evidence"]),
                        "target_type": "claim",
                        "target_id": str(claim_id),
                    }))
        self.connection.execute(
            "UPDATE evidence SET status = 'valid' WHERE id = ?",
            (str(loaded.ids["evidence"]),),
        )
        self.connection.commit()

    def test_descriptor_validation_rejects_drive_and_backslash_paths(self) -> None:
        for logical_ref in ("C:/host/secret.txt", "fixtures\\secret.txt"):
            with self.subTest(logical_ref=logical_ref):
                descriptor = FrozenResourceDescriptor(
                    descriptor_id="invalid",
                    read_root=self.descriptor.read_root,
                    logical_ref=logical_ref,
                    media_type="text/plain",
                    data_class=DataClass.PUBLIC,
                )
                with self.assertRaisesRegex(ValueError, "portable"):
                    JourneyCommandService._validate_descriptors((descriptor,))

    def test_bootstrap_corrupted_creation_fact_fails_closed(self) -> None:
        self.connection.execute("DROP TRIGGER events_are_append_only_update")
        self.connection.execute(
            "UPDATE events SET payload_json = ? WHERE type = 'workspace.created'",
            (json.dumps({"workspace_id": "tampered"}, separators=(",", ":")),),
        )
        self.connection.commit()
        with self.assertRaisesRegex(RuntimeError, "missing its creation"):
            WorkspaceBootstrapService(self.connection).ensure(self.spec)

    def test_user_actor_requires_stable_id(self) -> None:
        from nana_sidecar.contracts.common import ActorRef

        with self.assertRaisesRegex(ValueError, "stable"):
            JourneyCommandService(
                self.connection,
                actor=ActorRef(kind="user"),
                resources=(self.descriptor,),
                now=lambda: NOW,
            )

    def test_multievent_attach_evidence_rolls_back_before_commit_and_replays_after_commit(self) -> None:
        loaded = load_dev_journey(self.service, self.definition)
        base = {
            "type": "AttachEvidence",
            "expected_revision": 1,
            "inquiry_id": str(loaded.ids["inquiry"]),
            "locator_id": str(loaded.ids["locator"]),
            "excerpt_hash": self.definition["resource"]["quote_hash"],
        }
        before = self._counts()
        before_request = REQUESTS.validate_python({
            **base, "command_id": str(uuid4()), "direction": "opposes"
        })

        def crash_before(name: str) -> None:
            if name == "before_commit":
                raise RuntimeError("D3 attach before-commit fault")

        faulty = JourneyCommandService(
            self.connection,
            actor=local_fixture_actor(),
            resources=(self.descriptor,),
            now=lambda: NOW,
            checkpoint=crash_before,
        )
        with self.assertRaisesRegex(RuntimeError, "before-commit"):
            faulty.execute(before_request)
        self.assertEqual(self._counts(), before)
        accepted = self.service.execute(before_request)
        self.assertIs(accepted.status, CommandStatus.ACCEPTED)

        after_request = REQUESTS.validate_python({
            **base, "command_id": str(uuid4()), "direction": "limits"
        })

        def crash_after(name: str) -> None:
            if name == "after_commit":
                raise RuntimeError("D3 attach after-commit response loss")

        faulty_after = JourneyCommandService(
            self.connection,
            actor=local_fixture_actor(),
            resources=(self.descriptor,),
            now=lambda: NOW,
            checkpoint=crash_after,
        )
        with self.assertRaisesRegex(RuntimeError, "response loss"):
            faulty_after.execute(after_request)
        replay = self.service.execute(after_request)
        self.assertIs(replay.status, CommandStatus.REPLAYED)

    def test_resource_content_change_between_register_and_locator_fails_closed(self) -> None:
        root = Path(self.tempdir.name) / "resource-root"
        root.mkdir()
        resource_path = root / "frozen.md"
        resource_path.write_text("alpha\nbeta\n", encoding="utf-8")
        descriptor = FrozenResourceDescriptor(
            descriptor_id="temp-resource-v1",
            read_root=root,
            logical_ref="frozen.md",
            media_type="text/markdown",
            data_class=DataClass.PUBLIC,
        )
        service = JourneyCommandService(
            self.connection,
            actor=local_fixture_actor(),
            resources=(descriptor,),
            now=lambda: NOW,
        )
        project = service.execute(REQUESTS.validate_python({
            "type": "CreateProject", "command_id": str(uuid4()),
            "expected_revision": 1, "workspace_id": str(self.spec.workspace_id),
            "title": "Resource drift", "data_class": "public",
        }))
        project_id = self._affected_id(project, "project")
        registered = service.execute(REQUESTS.validate_python({
            "type": "RegisterResource", "command_id": str(uuid4()),
            "expected_revision": 1, "project_id": str(project_id),
            "kind": "local_file", "logical_ref": "frozen.md",
            "media_type": "text/markdown", "data_class": "public",
        }))
        resource_id = self._affected_id(registered, "resource")
        resource_path.write_text("changed\nbeta\n", encoding="utf-8")
        with self.assertRaises(CommandExecutionError):
            service.execute(REQUESTS.validate_python({
                "type": "CreateLocator", "command_id": str(uuid4()),
                "expected_revision": 1, "resource_id": str(resource_id),
                "locator_type": "local_file",
                "coordinates": {
                    "kind": "local_file",
                    "artifact_hash": "sha256:" + ("0" * 64),
                    "logical_path": "frozen.md",
                    "line_span": {"start_line": 1, "end_line": 1},
                },
                "quote_hash": "sha256:" + ("0" * 64),
            }))

    def test_plan_revision_appends_and_stale_revision_is_rejected(self) -> None:
        loaded = load_dev_journey(self.service, self.definition)
        plan_id = loaded.ids["plan"]
        revised_payload = {
            "type": "RevisePlan",
            "command_id": str(uuid4()),
            "expected_revision": 1,
            "plan_id": str(plan_id),
            **self.definition["plan"],
        }
        revised_payload["steps"] = [
            {**self.definition["plan"]["steps"][0], "title": "Revised locked test"}
        ]
        result = self.service.execute(REQUESTS.validate_python(revised_payload))
        self.assertEqual(result.affected_revisions, {f"plan:{plan_id}": 2})
        rows = self.connection.execute(
            "SELECT revision, status FROM plans WHERE id = ? ORDER BY revision",
            (str(plan_id),),
        ).fetchall()
        self.assertEqual(
            [(row["revision"], row["status"]) for row in rows],
            [(1, "proposed"), (2, "draft")],
        )
        replay = self.service.execute(REQUESTS.validate_python(revised_payload))
        self.assertIs(replay.status, CommandStatus.REPLAYED)
        stale_payload = {**revised_payload, "command_id": str(uuid4())}
        with self.assertRaises(CommandExecutionError):
            self.service.execute(REQUESTS.validate_python(stale_payload))
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM plans WHERE id = ?", (str(plan_id),)
            ).fetchone()[0],
            2,
        )

    def test_locator_rejects_changed_resource_and_bad_span_without_fact(self) -> None:
        loaded = load_dev_journey(self.service, self.definition)
        resource = self.definition["resource"]
        base = {
            "type": "CreateLocator",
            "command_id": str(uuid4()),
            "expected_revision": 1,
            "resource_id": str(loaded.ids["resource"]),
            "locator_type": "local_file",
            "coordinates": {
                "kind": "local_file",
                "artifact_hash": resource["content_hash"],
                "logical_path": resource["logical_ref"],
                "line_span": {"start_line": 6, "end_line": 9999},
            },
            "quote_hash": resource["quote_hash"],
        }
        before = self._counts()
        with self.assertRaises(CommandExecutionError):
            self.service.execute(REQUESTS.validate_python(base))
        bad_quote = {
            **base,
            "command_id": str(uuid4()),
            "coordinates": {
                **base["coordinates"],
                "line_span": {"start_line": 6, "end_line": 12},
            },
            "quote_hash": "sha256:" + ("0" * 64),
        }
        with self.assertRaises(CommandExecutionError):
            self.service.execute(REQUESTS.validate_python(bad_quote))
        after = self._counts()
        self.assertEqual(after["locators"], before["locators"])
        self.assertEqual(after["events"], before["events"])

    def test_resource_symlink_is_rejected_when_platform_allows_symlink_creation(self) -> None:
        root = Path(self.tempdir.name) / "symlink-root"
        root.mkdir()
        outside = Path(self.tempdir.name) / "outside.md"
        outside.write_text("outside\n", encoding="utf-8")
        link = root / "linked.md"
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")
        descriptor = FrozenResourceDescriptor(
            descriptor_id="symlink-resource-v1",
            read_root=root,
            logical_ref="linked.md",
            media_type="text/markdown",
            data_class=DataClass.PUBLIC,
        )
        service = JourneyCommandService(
            self.connection,
            actor=local_fixture_actor(),
            resources=(descriptor,),
            now=lambda: NOW,
        )
        project = service.execute(REQUESTS.validate_python({
            "type": "CreateProject",
            "command_id": str(uuid4()),
            "expected_revision": 1,
            "workspace_id": str(self.spec.workspace_id),
            "title": "Symlink rejection",
            "data_class": "public",
        }))
        project_id = self._affected_id(project, "project")
        with self.assertRaises(CommandExecutionError) as caught:
            service.execute(REQUESTS.validate_python({
                "type": "RegisterResource",
                "command_id": str(uuid4()),
                "expected_revision": 1,
                "project_id": str(project_id),
                "kind": "local_file",
                "logical_ref": descriptor.logical_ref,
                "media_type": descriptor.media_type,
                "data_class": descriptor.data_class.value,
            }))
        self.assertEqual(caught.exception.error.details["reason"], "resource_reparse")

    def test_cross_project_evidence_is_rejected(self) -> None:
        loaded = load_dev_journey(self.service, self.definition)
        project = self.service.execute(REQUESTS.validate_python({
            "type": "CreateProject",
            "command_id": str(uuid4()),
            "expected_revision": 1,
            "workspace_id": self.definition["workspace"]["id"],
            "title": "Other project",
            "data_class": "public",
        }))
        project_id = self._affected_id(project, "project")
        inquiry = self.service.execute(REQUESTS.validate_python({
            "type": "CreateInquiry",
            "command_id": str(uuid4()),
            "expected_revision": 1,
            "project_id": str(project_id),
            "question": "Other inquiry",
            "acceptance": "Must not consume first-project provenance",
        }))
        inquiry_id = self._affected_id(inquiry, "inquiry")
        before = self._counts()
        with self.assertRaises(CommandExecutionError):
            self.service.execute(REQUESTS.validate_python({
                "type": "AttachEvidence",
                "command_id": str(uuid4()),
                "expected_revision": 1,
                "inquiry_id": str(inquiry_id),
                "locator_id": str(loaded.ids["locator"]),
                "direction": "supports",
                "excerpt_hash": self.definition["resource"]["quote_hash"],
            }))
        after = self._counts()
        self.assertEqual(after["evidence"], before["evidence"])
        self.assertEqual(after["relations"], before["relations"])
        self.assertEqual(after["events"], before["events"])

    def test_finding_requires_valid_evidence_or_same_scope_terminal_run(self) -> None:
        loaded = load_dev_journey(self.service, self.definition)
        running_id = uuid4()
        terminal_id = uuid4()
        for run_id, state, finished_at in (
            (running_id, "running", None),
            (terminal_id, "succeeded", NOW),
        ):
            self.connection.execute(
                "INSERT INTO runs(id, project_id, inquiry_id, state, snapshot_json, created_at, finished_at) "
                "VALUES (?, ?, ?, ?, '{}', ?, ?)",
                (
                    str(run_id), str(loaded.ids["project"]), str(loaded.ids["inquiry"]),
                    state, NOW, finished_at,
                ),
            )
        self.connection.commit()
        base = {
            "type": "DraftFinding",
            "expected_revision": 1,
            "inquiry_id": str(loaded.ids["inquiry"]),
            "statement": "Run-backed finding",
            "confidence_basis": "Terminal run fact",
            "evidence_ids": [],
        }
        with self.assertRaises(CommandExecutionError):
            self.service.execute(REQUESTS.validate_python({
                **base,
                "command_id": str(uuid4()),
                "terminal_run_ids": [str(running_id)],
            }))
        result = self.service.execute(REQUESTS.validate_python({
            **base,
            "command_id": str(uuid4()),
            "terminal_run_ids": [str(terminal_id)],
        }))
        finding_id = self._affected_id(result, "finding")
        relation = self.connection.execute(
            "SELECT type, source_id, target_id, producer_run_id FROM relations "
            "WHERE target_type = 'finding' AND target_id = ?",
            (str(finding_id),),
        ).fetchone()
        self.assertEqual(
            tuple(relation),
            ("run_produces_finding", str(terminal_id), str(finding_id), str(terminal_id)),
        )

        self.connection.execute(
            "UPDATE evidence SET status = 'stale' WHERE id = ?",
            (str(loaded.ids["evidence"]),),
        )
        self.connection.commit()
        with self.assertRaises(CommandExecutionError):
            self.service.execute(REQUESTS.validate_python({
                **base,
                "command_id": str(uuid4()),
                "evidence_ids": [str(loaded.ids["evidence"])],
                "terminal_run_ids": [],
            }))

    def test_failed_run_retry_is_atomic_and_lineage_bound(self) -> None:
        loaded = load_dev_journey(self.service, self.definition)
        failed_id = uuid4()
        self.connection.execute(
            "INSERT INTO runs(id, project_id, inquiry_id, state, snapshot_json, created_at, finished_at) "
            "VALUES (?, ?, ?, 'failed', '{}', ?, ?)",
            (
                str(failed_id), str(loaded.ids["project"]),
                str(loaded.ids["inquiry"]), NOW, NOW,
            ),
        )
        self.connection.execute(
            "INSERT INTO events(aggregate_type, aggregate_id, aggregate_version, run_id, run_seq, "
            "actor_json, type, payload_json, occurred_at) VALUES ('run', ?, 1, ?, 1, ?, "
            "'run.failed', ?, ?)",
            (
                str(failed_id), str(failed_id),
                json.dumps(local_fixture_actor().model_dump(mode="json"), separators=(",", ":"), sort_keys=True),
                json.dumps({"run_id": str(failed_id), "state": "failed"}, separators=(",", ":")),
                NOW,
            ),
        )
        failed_event = int(self.connection.execute("SELECT last_insert_rowid()").fetchone()[0])
        self.connection.execute("INSERT INTO outbox_events(event_id) VALUES (?)", (failed_event,))
        self.connection.commit()
        request = REQUESTS.validate_python({
            "type": "StartRun", "command_id": str(uuid4()),
            "expected_revision": 1, "project_id": str(loaded.ids["project"]),
            "inquiry_id": str(loaded.ids["inquiry"]),
            "plan_id": str(loaded.ids["plan"]), "plan_revision": 1,
            "random_seed": 307, "retry_of_run_id": str(failed_id),
        })
        result = self.service.execute(request, defer_locked_execution=True)
        retry_id = self._affected_id(result, "run")
        row = self.connection.execute(
            "SELECT retry_of_run_id FROM runs WHERE id = ?", (str(retry_id),)
        ).fetchone()
        relation = self.connection.execute(
            "SELECT type, source_id, target_id, producer_run_id FROM relations "
            "WHERE source_id = ?", (str(retry_id),)
        ).fetchone()
        self.assertEqual(row["retry_of_run_id"], str(failed_id))
        self.assertEqual(tuple(relation), (
            "run_retry_of_run", str(retry_id), str(failed_id), str(retry_id)
        ))
        self.assertEqual(
            [row["type"] for row in self.connection.execute(
                "SELECT type FROM events WHERE causation_id = ? ORDER BY id",
                (str(request.command_id),),
            )],
            ["run.created", "action.proposed", "relation.created"],
        )

    def test_run_controls_enforce_expected_revision_and_return_actual_revision(self) -> None:
        loaded = load_dev_journey(self.service, self.definition)
        start = REQUESTS.validate_python({
            "type": "StartRun",
            "command_id": str(uuid4()),
            "expected_revision": 1,
            "project_id": str(loaded.ids["project"]),
            "inquiry_id": str(loaded.ids["inquiry"]),
            "plan_id": str(loaded.ids["plan"]),
            "plan_revision": 1,
            "random_seed": 307,
        })
        started = self.service.execute(start, defer_locked_execution=True)
        run_id = self._affected_id(started, "run")

        pause = REQUESTS.validate_python({
            "type": "PauseRun",
            "command_id": str(uuid4()),
            "expected_revision": 1,
            "run_id": str(run_id),
            "reason": "inspect",
        })
        paused = self.service.execute(pause)
        self.assertEqual(paused.affected_revisions, {f"run:{run_id}": 2})

        stale = REQUESTS.validate_python({
            "type": "CancelRun",
            "command_id": str(uuid4()),
            "expected_revision": 1,
            "run_id": str(run_id),
            "reason": "stale stop",
        })
        for replayed in (False, True):
            with self.assertRaises(CommandExecutionError) as caught:
                self.service.execute(stale)
            self.assertEqual(caught.exception.replayed, replayed)
            self.assertEqual(caught.exception.error.code.value, "E_REVISION_CONFLICT")
            self.assertEqual(caught.exception.error.details["actual_revision"], 2)
        self.assertEqual(
            self.connection.execute(
                "SELECT state FROM runs WHERE id = ?", (str(run_id),)
            ).fetchone()["state"],
            "paused",
        )

        resume = REQUESTS.validate_python({
            "type": "ResumeRun",
            "command_id": str(uuid4()),
            "expected_revision": 2,
            "run_id": str(run_id),
            "reason": "continue",
        })
        resumed = self.service.execute(resume)
        self.assertEqual(resumed.affected_revisions, {f"run:{run_id}": 3})

        cancel = REQUESTS.validate_python({
            "type": "CancelRun",
            "command_id": str(uuid4()),
            "expected_revision": 3,
            "run_id": str(run_id),
            "reason": "stop",
        })
        cancelled = self.service.execute(cancel)
        self.assertEqual(cancelled.affected_revisions, {f"run:{run_id}": 4})

    def test_retry_rejects_nonfailed_source_without_side_effects(self) -> None:
        loaded = load_dev_journey(self.service, self.definition)
        before = self._counts()
        request = REQUESTS.validate_python({
            "type": "StartRun", "command_id": str(uuid4()),
            "expected_revision": 1, "project_id": str(loaded.ids["project"]),
            "inquiry_id": str(loaded.ids["inquiry"]),
            "plan_id": str(loaded.ids["plan"]), "plan_revision": 1,
            "random_seed": 307, "retry_of_run_id": str(uuid4()),
        })
        with self.assertRaises(CommandExecutionError):
            self.service.execute(request, defer_locked_execution=True)
        after = self._counts()
        self.assertEqual(after["relations"], before["relations"])
        self.assertEqual(after["events"], before["events"])

    @staticmethod
    def _affected_id(result: object, aggregate_type: str):
        values = [
            key.split(":", 1)[1]
            for key in result.affected_revisions
            if key.startswith(f"{aggregate_type}:")
        ]
        if len(values) != 1:
            raise AssertionError(f"missing {aggregate_type} revision")
        return __import__("uuid").UUID(values[0])

    def _counts(self) -> dict[str, int]:
        names = (
            "workspaces", "projects", "inquiries", "plans", "resources",
            "locators", "claims", "evidence", "hypotheses", "findings",
            "relations", "events", "outbox_events", "command_log",
        )
        return {
            name: int(self.connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0])
            for name in names
        }


if __name__ == "__main__":
    unittest.main()
