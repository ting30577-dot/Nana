"""D3-07 process-memory target selection security matrix."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from nana_sidecar.export_selection import ExportSelectionError, ExportSelectionRegistry
from nana_sidecar.sse import LocalSession


TOKEN = "d3-selection-matrix-" + "m" * 40
ORIGIN = "http://127.0.0.1:43123"


class D307SelectionRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.workspace = self.root / "workspace"
        self.target = self.root / "export"
        self.application = self.root / "application"
        self.workspace.mkdir()
        self.target.mkdir()
        self.application.mkdir()
        self.session = LocalSession(token=TOKEN, origin=ORIGIN)
        self.registries: list[ExportSelectionRegistry] = []

    def tearDown(self) -> None:
        for registry in self.registries:
            registry.close()
        self.tempdir.cleanup()

    def _registry(self, **changes: object) -> ExportSelectionRegistry:
        values = {
            "session": self.session,
            "workspace_root": self.workspace,
            "application_root": self.application,
            "actor_id": "local-session-user",
            "allow_test_harness": True,
        }
        values.update(changes)
        registry = ExportSelectionRegistry(**values)
        self.registries.append(registry)
        return registry

    def test_harness_registration_is_explicit_redacted_and_one_use(self) -> None:
        registry = self._registry()
        summary = registry.register_test_harness_target(str(self.target))
        self.assertEqual(len(summary.selection_id), 43)
        self.assertEqual(summary.provenance, "test_harness")
        self.assertNotIn(str(self.target), repr(summary))
        first = registry.reserve(
            summary.selection_id,
            actor_id="local-session-user",
            command_id="command-1",
            request_hash="sha256:" + "1" * 64,
            run_id="run-1",
            action_id="action-1",
        )
        registry.finalize(summary.selection_id, command_id="command-1")
        same = registry.reserve(
            summary.selection_id,
            actor_id="local-session-user",
            command_id="command-1",
            request_hash="sha256:" + "1" * 64,
            run_id="run-1",
            action_id="action-1",
        )
        self.assertIs(first, same)
        with self.assertRaisesRegex(ExportSelectionError, "another attempt"):
            registry.reserve(
                summary.selection_id,
                actor_id="local-session-user",
                command_id="command-2",
                request_hash="sha256:" + "2" * 64,
                run_id="run-2",
                action_id="action-2",
            )

    def test_actor_expiry_and_identity_change_fail_closed(self) -> None:
        clock = [0.0]
        registry = self._registry(monotonic=lambda: clock[0], ttl_seconds=2)
        summary = registry.register_test_harness_target(str(self.target))
        with self.assertRaisesRegex(ExportSelectionError, "another actor"):
            registry.reserve(
                summary.selection_id,
                actor_id="other-user",
                command_id="command",
                request_hash="sha256:" + "1" * 64,
                run_id="run",
                action_id="action",
            )
        (self.target / "intruder.txt").write_text("collision", encoding="utf-8")
        with self.assertRaisesRegex(ExportSelectionError, "no longer empty"):
            registry.reserve(
                summary.selection_id,
                actor_id="local-session-user",
                command_id="command",
                request_hash="sha256:" + "1" * 64,
                run_id="run",
                action_id="action",
            )
        (self.target / "intruder.txt").unlink()
        clock[0] = 3.0
        with self.assertRaisesRegex(ExportSelectionError, "unavailable"):
            registry.reserve(
                summary.selection_id,
                actor_id="local-session-user",
                command_id="command",
                request_hash="sha256:" + "1" * 64,
                run_id="run",
                action_id="action",
            )

    def test_dangerous_nonempty_cloud_and_injected_paths_are_rejected(self) -> None:
        registry = self._registry()
        with self.assertRaises(ExportSelectionError):
            registry.register_test_harness_target("relative/export")
        with self.assertRaises(ExportSelectionError):
            registry.register_test_harness_target(r"\\server\share\export")
        with self.assertRaisesRegex(ExportSelectionError, "Nana or the Workspace"):
            registry.register_test_harness_target(str(self.workspace))
        nonempty = self.root / "nonempty"
        nonempty.mkdir()
        (nonempty / "existing.txt").write_text("x", encoding="utf-8")
        with self.assertRaisesRegex(ExportSelectionError, "empty"):
            registry.register_test_harness_target(str(nonempty))
        cloud = self.root / "OneDrive" / "drafts"
        cloud.mkdir(parents=True)
        with self.assertRaisesRegex(ExportSelectionError, "cloud"):
            registry.register_test_harness_target(str(cloud))
        branded_cloud = self.root / "Dropbox (Nana Research)" / "drafts"
        branded_cloud.mkdir(parents=True)
        with self.assertRaisesRegex(ExportSelectionError, "cloud"):
            registry.register_test_harness_target(str(branded_cloud))

    @unittest.skipUnless(os.name == "nt", "real selection identity is Windows-only")
    def test_real_interactive_selection_retains_windows_identity(self) -> None:
        registry = self._registry(allow_test_harness=False)
        summary = registry.register_interactive_target(str(self.target))
        self.assertEqual(summary.provenance, "interactive_user")
        entry = registry.reserve(
            summary.selection_id,
            actor_id="local-session-user",
            command_id="command",
            request_hash="sha256:" + "1" * 64,
            run_id="run",
            action_id="action",
        )
        self.assertIsNotNone(entry.handle)
        self.assertRegex(entry.identity_digest, r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(entry.target_commitment, r"^sha256:[0-9a-f]{64}$")
        registry.finalize(summary.selection_id, command_id="command")
        self.target.rename(self.root / "replacement-attempt")
        with self.assertRaisesRegex(ExportSelectionError, "revalidated"):
            registry.bound_for_action("action", actor_id="local-session-user")

    def test_harness_cannot_be_silently_enabled(self) -> None:
        registry = self._registry(allow_test_harness=False)
        with self.assertRaisesRegex(ExportSelectionError, "disabled"):
            registry.register_test_harness_target(str(self.target))


if __name__ == "__main__":
    unittest.main()
