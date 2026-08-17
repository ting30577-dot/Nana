"""Executable release allowlist and package leak gates."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from scripts.audit_release_package import (
    POLICY_PATH,
    ReleaseBoundaryError,
    audit_package,
    load_policy,
)


ROOT = Path(__file__).resolve().parents[1]


class ReleasePackageBoundaryTests(unittest.TestCase):
    def _package(self, root: Path) -> Path:
        package = root / "Nana"
        (package / "_internal").mkdir(parents=True)
        (package / "Nana.exe").write_bytes(b"portable-entry")
        (package / "_internal" / "runtime.bin").write_bytes(b"runtime")
        return package

    def test_clean_package_manifest_is_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package = self._package(Path(directory))
            count, digest = audit_package(package, write_manifest=True)
            checked_count, checked_digest = audit_package(package, check_manifest=True)
            self.assertEqual((checked_count, checked_digest), (count, digest))
            self.assertEqual(count, 2)

    def test_runtime_database_wal_lock_and_user_roots_are_rejected(self) -> None:
        forbidden = (
            Path("_internal/workspaces/nana.db"),
            Path("_internal/nana.db-wal"),
            Path("_internal/nana.db-shm"),
            Path("_internal/workspace.owner.lock"),
            Path("_internal/usability_sessions/session.json"),
            Path("_internal/artifacts/blob"),
        )
        for relative in forbidden:
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                package = self._package(Path(directory))
                target = package / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"private")
                with self.assertRaises(ReleaseBoundaryError):
                    audit_package(package)

    def test_unknown_top_level_and_credential_canary_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package = self._package(Path(directory))
            (package / "unexpected").mkdir()
            with self.assertRaisesRegex(ReleaseBoundaryError, "non-allowlisted"):
                audit_package(package)
        with tempfile.TemporaryDirectory() as directory:
            package = self._package(Path(directory))
            (package / "_internal" / "payload.bin").write_bytes(
                b"NANA_RELEASE_CREDENTIAL_CANARY_DO_NOT_PACKAGE"
            )
            with self.assertRaisesRegex(ReleaseBoundaryError, "credential canary"):
                audit_package(package)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_package_reparse_directory_is_rejected_without_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = self._package(root)
            outside = root / "outside"
            outside.mkdir()
            (outside / "nana.db").write_bytes(b"must-not-be-traversed")
            link = package / "_internal" / "linked"
            try:
                link.symlink_to(outside, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink unavailable: {exc}")
            with self.assertRaisesRegex(ReleaseBoundaryError, "reparse"):
                audit_package(package)

    def test_build_is_guarded_and_tauri_remains_contract_only(self) -> None:
        policy = load_policy(POLICY_PATH)
        self.assertEqual(policy["entrypoints"], ["main.py"])
        self.assertEqual(policy["tauri"]["status"], "contract_frozen_not_implemented")
        self.assertIs(policy["tauri"]["product_code_allowed"], False)
        build_script = (ROOT / "scripts/build_windows.ps1").read_text(encoding="utf-8")
        self.assertIn("audit_release_package.py", build_script)
        self.assertNotIn("Copy-Item -Recurse", build_script)
        self.assertFalse((ROOT / "Nana.spec").exists())
        self.assertFalse((ROOT / "src-tauri").exists())


if __name__ == "__main__":
    unittest.main()
