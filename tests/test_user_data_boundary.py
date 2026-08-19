"""Fail-closed tests for product/user data separation from the source tree."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from nana_sidecar.user_data import (
    UserDataBoundaryError,
    prepare_user_data_layout,
    resolve_user_data_root,
    validate_runtime_path,
)


ROOT = Path(__file__).resolve().parents[1]


class UserDataBoundaryTests(unittest.TestCase):
    def test_repository_ignore_rules_cover_runtime_sidecars_and_roots(self) -> None:
        rules = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertTrue(
            {
                "*.db-wal",
                "*.db-shm",
                "workspace.owner.lock",
                "/workspaces/",
                "/usability_sessions/",
                "/exports/",
                "/artifacts/",
                "/logs/",
                "/crash/",
            }
            <= set(rules)
        )
        self.assertFalse((ROOT / "workspaces").exists())
        self.assertFalse((ROOT / "usability_sessions").exists())

    def test_windows_default_uses_local_app_data_not_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            local_app_data = Path(directory) / "Local"
            root = resolve_user_data_root(
                environ={"LOCALAPPDATA": str(local_app_data)},
                application_root=ROOT,
                platform="nt",
            )
        self.assertEqual(root, local_app_data / "Nana")

    def test_relative_or_source_tree_override_is_rejected(self) -> None:
        with self.assertRaisesRegex(UserDataBoundaryError, "absolute"):
            resolve_user_data_root(
                environ={"NANA_DATA_ROOT": "relative-data"},
                application_root=ROOT,
            )
        with self.assertRaisesRegex(UserDataBoundaryError, "outside"):
            resolve_user_data_root(
                environ={"NANA_DATA_ROOT": str(ROOT / "workspaces")},
                application_root=ROOT,
            )

    def test_layout_creates_only_named_user_data_roots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_root = Path(directory) / "NanaData"
            layout = prepare_user_data_layout(
                environ={"NANA_DATA_ROOT": str(data_root)},
                application_root=ROOT,
            )
            self.assertEqual(
                {child.name for child in data_root.iterdir()},
                {
                    "workspaces",
                    "usability_sessions",
                    "exports",
                    "logs",
                    "crash",
                    "temp",
                },
            )
            self.assertEqual(
                layout.default_workspace_database,
                data_root / "workspaces" / "d3" / "nana.db",
            )

    def test_explicit_runtime_database_inside_source_tree_is_rejected(self) -> None:
        with self.assertRaisesRegex(UserDataBoundaryError, "must not be written"):
            validate_runtime_path(ROOT / "workspaces" / "d3" / "nana.db")

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_existing_symlink_component_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            real = base / "real"
            real.mkdir()
            link = base / "link"
            try:
                link.symlink_to(real, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink unavailable: {exc}")
            with self.assertRaisesRegex(UserDataBoundaryError, "reparse"):
                resolve_user_data_root(
                    environ={"NANA_DATA_ROOT": str(link / "Nana")},
                    application_root=ROOT,
                )


if __name__ == "__main__":
    unittest.main()
