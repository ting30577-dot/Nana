"""Static checks for the minimal Tauri shell security boundary."""

from __future__ import annotations

import json
import os
import re
import unittest
from pathlib import Path

from scripts.refresh_evidence_manifest import recompute_manifest
from scripts.check_tauri_frontend_dist import audit_frontend_dist


ROOT = Path(__file__).resolve().parents[1]
TAURI = ROOT / "src-tauri"
STAGE_MANIFEST = ROOT / "docs/evidence/v0.3.0-dev-tauri-stage1-static-shell-manifest.txt"
STAGE_SCOPES = (
    ROOT / "config/tauri-stage1-worktree-allowlist.json",
    ROOT / "docs/evidence/v0.3.0-dev-tauri-stage1-static-shell.json",
    ROOT / "docs/evidence/v0.3.0-dev-tauri-cargo-audit-20260817.json",
    ROOT / "docs/evidence/v0.3.0-dev-tauri-spike-entry-manifest.sha256",
    ROOT / "docs/evidence/v0.3.0-dev-tauri-spike-entry-manifest.txt",
    ROOT / "docs/tauri_stage1_static_shell_20260817.md",
    ROOT / "nana_web/dist",
    ROOT / "nana_web/package-lock.json",
    ROOT / "nana_web/package.json",
    ROOT / "nana_web/src/main.tsx",
    ROOT / "scripts/check_tauri_cargo_audit.ps1",
    ROOT / "scripts/check_tauri_frontend_npm_audit.ps1",
    ROOT / "scripts/check_tauri_frontend_dist.py",
    ROOT / "scripts/refresh_evidence_manifest.py",
    ROOT / "src-tauri",
    ROOT / "tests/test_tauri_static_shell.py",
    ROOT / "tools/tauri-spike/package-lock.json",
    ROOT / "tools/tauri-spike/package.json",
)
STAGE_EXCLUDED = (ROOT / "src-tauri/target", ROOT / "src-tauri/gen")


class TauriStaticShellTests(unittest.TestCase):
    def test_source_root_is_direct_non_reparse_directory(self) -> None:
        self.assertTrue(TAURI.is_dir())
        self.assertFalse(TAURI.is_symlink())
        attributes = getattr(os.lstat(TAURI), "st_file_attributes", 0)
        self.assertEqual(attributes & 0x400, 0)

    def test_config_is_local_static_shell_with_explicit_capability(self) -> None:
        config = json.loads((TAURI / "tauri.conf.json").read_text(encoding="utf-8"))
        self.assertEqual(config["build"], {
            "frontendDist": "../nana_web/dist",
            "beforeBuildCommand": "npm run build",
        })
        self.assertEqual(config["app"]["windows"], [])
        self.assertEqual(config["app"]["security"]["capabilities"], ["main"])
        self.assertFalse(config["app"]["withGlobalTauri"])
        self.assertFalse(config["app"]["security"]["dangerousDisableAssetCspModification"])
        self.assertTrue(config["app"]["security"]["freezePrototype"])
        self.assertFalse(config["bundle"]["active"])
        self.assertNotIn("externalBin", config["bundle"])
        self.assertNotIn("plugins", config)

        csp = config["app"]["security"]["csp"]
        self.assertEqual(csp["default-src"], "'self'")
        self.assertEqual(csp["connect-src"], "'none'")
        self.assertEqual(csp["object-src"], "'none'")
        self.assertNotIn("http:", json.dumps(csp))
        self.assertNotIn("https:", json.dumps(csp))

    def test_capability_has_no_permissions_or_remote_scope(self) -> None:
        capability = json.loads(
            (TAURI / "capabilities" / "default.json").read_text(encoding="utf-8")
        )
        self.assertEqual(capability["identifier"], "main")
        self.assertEqual(capability["windows"], ["main"])
        self.assertEqual(capability["webviews"], ["main"])
        self.assertEqual(capability["permissions"], [])
        self.assertNotIn("remote", capability)

    def test_rust_boundary_denies_navigation_and_new_windows_without_ipc(self) -> None:
        source = (TAURI / "src" / "lib.rs").read_text(encoding="utf-8")
        self.assertIn("on_navigation", source)
        self.assertIn("NewWindowResponse::Deny", source)
        self.assertIn("WebviewUrl::App", source)
        self.assertNotRegex(source, r"invoke_handler|generate_handler|plugin\s*\(")
        self.assertNotIn("tauri-plugin", (TAURI / "Cargo.toml").read_text(encoding="utf-8"))

    def test_rust_navigation_boundary_is_exact_origin_and_document_path(self) -> None:
        source = (TAURI / "src" / "lib.rs").read_text(encoding="utf-8")
        self.assertIn("url.port().is_some()", source)
        self.assertIn('matches!(url.path(), "/" | "/index.html")', source)

    def test_static_shell_does_not_bootstrap_over_network(self) -> None:
        source = (ROOT / "nana_web/src/main.tsx").read_text(encoding="utf-8")
        self.assertIn("isPackagedShellLocation", source)
        self.assertIn("if (isPackagedShellLocation())", source)
        self.assertIn("renderApp(null)", source)
        self.assertIn("} catch {", source)

    def test_gate_has_trusted_allowlist_and_real_build_audits(self) -> None:
        gate = (ROOT / "scripts/check_tauri_spike_gate.ps1").read_text(encoding="utf-8")
        policy = json.loads(
            (ROOT / "config/tauri-stage1-worktree-allowlist.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertNotIn("scripts/check_tauri_spike_gate.ps1", policy["allowed_exact"])
        self.assertIn("scripts/check_tauri_spike_gate.ps1", policy["trusted_exact"])
        self.assertIn("039fd4945e22bd7dbe0021086c5c416c4399c19eeba5d4f0c84614a7550216b0", gate)
        self.assertNotIn("TrimStart", gate)
        self.assertIn("check_tauri_frontend_npm_audit.ps1", gate)
        self.assertIn("build --no-bundle", gate)
        self.assertIn("cargoEvidenceMatches", gate)
        self.assertIn("Test-NoReparseTree", gate)
        self.assertIn("expectedTauriConfigSha256", gate)
        self.assertIn("expectedFrontendPackageSha256", gate)
        self.assertIn("frontendDist", gate)
        self.assertIn("NANA_TAURI_GATE_SHA256", gate)

    def test_build_inputs_are_pinned_to_static_commands(self) -> None:
        package = json.loads((ROOT / "nana_web/package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["scripts"]["build"], "vite build")
        audit = (ROOT / "scripts/check_tauri_frontend_npm_audit.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("--ignore-scripts", audit)
        self.assertIn("--no-audit", audit)
        self.assertIn(".Arguments", audit)
        self.assertNotIn("ArgumentList", audit)
        cargo_audit = (ROOT / "scripts/check_tauri_cargo_audit.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("expectedCargoAuditVersion", cargo_audit)
        self.assertIn("vulnerabilities.found -eq $false", cargo_audit)
        self.assertIn("tool_installed = [bool]$cargoAudit", cargo_audit)
        self.assertNotIn("cargo_audit_executable", cargo_audit)

    def test_frontend_dist_checks_reparse_before_resolve(self) -> None:
        source = (ROOT / "scripts/check_tauri_frontend_dist.py").read_text(encoding="utf-8")
        self.assertIn("supplied = Path(os.path.abspath", source)
        self.assertIn("if _is_reparse(current)", source)
        self.assertLess(source.index("if _is_reparse(current)"), source.index("supplied.resolve"))

    def test_frontend_dist_is_a_complete_and_safe_vite_output(self) -> None:
        result = audit_frontend_dist(ROOT / "nana_web/dist")
        paths = {entry["path"] for entry in result["entries"]}
        self.assertIn("index.html", paths)
        self.assertIn(".vite/manifest.json", paths)
        self.assertTrue(any(path.startswith("assets/") for path in paths))

    def test_cargo_has_pinned_tauri_dependencies_and_no_local_source_override(self) -> None:
        cargo = (TAURI / "Cargo.toml").read_text(encoding="utf-8")
        self.assertRegex(cargo, r'tauri\s*=\s*\{\s*version\s*=\s*"=2\.11\.5"')
        self.assertRegex(cargo, r'tauri-build\s*=\s*\{\s*version\s*=\s*"=2\.6\.3"')
        self.assertNotIn("path =", cargo)
        self.assertNotIn("tauri-plugin", cargo)

    def test_stage_manifest_is_current(self) -> None:
        normalized, digest = recompute_manifest(
            STAGE_MANIFEST,
            scopes=STAGE_SCOPES,
            excluded=STAGE_EXCLUDED,
            strict_scope=True,
        )
        self.assertEqual(STAGE_MANIFEST.read_text(encoding="utf-8").rstrip("\r\n"), normalized)
        self.assertEqual(
            STAGE_MANIFEST.with_suffix(".sha256").read_text(encoding="ascii").strip(),
            digest,
        )


if __name__ == "__main__":
    unittest.main()
