"""Recoverability tests for legacy checkout data migration."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from scripts.migrate_legacy_runtime_data import inventory_tree, migrate_runtime_roots


class RuntimeDataMigrationTests(unittest.TestCase):
    def test_copy_verify_commit_then_archive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = root / "repository"
            data = root / "user-data"
            backup = repository / "backups" / "migration"
            workspace = repository / "workspaces" / "d3"
            workspace.mkdir(parents=True)
            (workspace / "nana.db").write_bytes(b"canonical-db")
            (workspace / "nana.db-wal").write_bytes(b"wal")
            before = inventory_tree(repository / "workspaces")

            records = migrate_runtime_roots(
                repository_root=repository,
                data_root=data,
                backup_root=backup,
            )

            self.assertFalse((repository / "workspaces").exists())
            self.assertEqual(inventory_tree(data / "workspaces"), before)
            self.assertEqual(inventory_tree(backup / "workspaces"), before)
            self.assertEqual(records[0].digest, before.digest)
            self.assertNotIn(str(root), repr(records[0]))

    def test_nonempty_destination_fails_without_moving_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = root / "repository"
            source = repository / "usability_sessions"
            destination = root / "user-data" / "usability_sessions"
            source.mkdir(parents=True)
            destination.mkdir(parents=True)
            (source / "session.txt").write_text("source", encoding="utf-8")
            (destination / "existing.txt").write_text("destination", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "will not merge"):
                migrate_runtime_roots(
                    repository_root=repository,
                    data_root=root / "user-data",
                    backup_root=repository / "backups" / "migration",
                )

            self.assertTrue((source / "session.txt").exists())
            self.assertFalse((repository / "backups" / "migration").exists())

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_inventory_refuses_a_reparse_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            outside = root / "outside"
            source.mkdir()
            outside.mkdir()
            link = source / "linked"
            try:
                link.symlink_to(outside, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink unavailable: {exc}")
            with self.assertRaisesRegex(RuntimeError, "reparse"):
                inventory_tree(source)


if __name__ == "__main__":
    unittest.main()
