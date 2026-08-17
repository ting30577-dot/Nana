"""Executable gates for the post-D3 Tauri spike entry decision."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from scripts.refresh_evidence_manifest import recompute_manifest


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "config/tauri-spike-entry-policy.json"
ANCHOR = ROOT / "docs/evidence/v0.3.0-dev-d3-baseline-anchor-20260817.json"
TOOLCHAIN_EVIDENCE = (
    ROOT / "docs/evidence/v0.3.0-dev-tauri-toolchain-20260817.json"
)
SPIKE_MANIFEST = (
    ROOT / "docs/evidence/v0.3.0-dev-tauri-spike-entry-manifest.txt"
)


class TauriSpikeGateTests(unittest.TestCase):
    def test_spike_overlay_opens_only_src_tauri_and_not_product_code(self) -> None:
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        self.assertEqual(policy["allowed_source_roots"], ["src-tauri"])
        self.assertTrue(policy["spike_code_allowed"])
        self.assertFalse(policy["product_code_allowed"])
        self.assertEqual(policy["canonical_writer"], "python_sidecar_only")
        self.assertTrue(all(policy["forbidden"].values()))
        self.assertEqual(policy["source_root_presence"], "optional_until_scaffold_commit")
        source = ROOT / policy["allowed_source_roots"][0]
        self.assertEqual(source.parent.resolve(), ROOT.resolve())
        if source.exists():
            self.assertTrue(source.is_dir())
            self.assertFalse(source.is_symlink())
            attributes = getattr(os.lstat(source), "st_file_attributes", 0)
            self.assertEqual(attributes & 0x400, 0, "src-tauri must not be reparse")

    def test_toolchain_evidence_closes_prerequisites_not_product_gate(self) -> None:
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        evidence = json.loads(TOOLCHAIN_EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(
            policy["status"], "spike_entry_authorized_toolchain_verified"
        )
        self.assertEqual(evidence["status"], "PASS_FOR_MINIMAL_SPIKE_SCAFFOLD")
        self.assertEqual(evidence["execution_proof"]["preflight"], "PASS_10_OF_10")
        self.assertEqual(evidence["execution_proof"]["cargo_check"], "PASS")
        self.assertEqual(
            evidence["execution_proof"]["linked_probe_execution"],
            "PASS_HELLO_WORLD",
        )
        audit = evidence["execution_proof"]["tauri_cli_npm_audit"]
        self.assertEqual(audit["registry"], "https://registry.npmjs.org")
        self.assertEqual(audit["exit_code"], 0)
        self.assertEqual(audit["vulnerabilities_total"], 0)
        self.assertFalse(evidence["boundary"]["product_code_authorized"])
        self.assertEqual(
            evidence["boundary"]["src_tauri_state_record_kind"],
            "point_in_time_snapshot_not_presence_gate",
        )

    @unittest.skipUnless(sys.platform == "win32", "Windows host preflight")
    def test_live_windows_preflight_executes_and_validates_versions(self) -> None:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ROOT / "scripts/check_tauri_windows_prereqs.ps1"),
                "-RepositoryRoot",
                str(ROOT),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        live = json.loads(completed.stdout)
        self.assertTrue(live["passed"])
        self.assertEqual(len(live["checks"]), 10)
        for name in ("rustup", "rustc_msvc", "cargo", "node", "npm"):
            with self.subTest(name=name):
                self.assertTrue(live["checks"][name]["passed"])
                self.assertEqual(live["checks"][name]["exit_code"], 0)
        tauri = live["checks"]["project_local_tauri_cli"]
        self.assertTrue(tauri["passed"])
        self.assertEqual(tauri["exit_code"], 0)
        self.assertEqual(tauri["version"], "tauri-cli 2.11.4")
        self.assertEqual(tauri["expected_version"], "2.11.4")

    def test_release_baseline_tag_resolves_commit_and_real_parent(self) -> None:
        anchor = json.loads(ANCHOR.read_text(encoding="utf-8"))
        tag_type = subprocess.run(
            ["git", "cat-file", "-t", anchor["ref"]],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        tag_commit = subprocess.run(
            ["git", "rev-parse", f"{anchor['ref']}^{{}}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        parent = subprocess.run(
            ["git", "rev-parse", f"{anchor['ref']}^{{}}^"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self.assertEqual(tag_type, "tag")
        self.assertEqual(tag_commit, anchor["peeled_commit"])
        self.assertEqual(parent, anchor["expected_parent"])

    def test_tooling_is_pinned_without_creating_product_source(self) -> None:
        package = json.loads(
            (ROOT / "tools/tauri-spike/package.json").read_text(encoding="utf-8")
        )
        version = package["devDependencies"]["@tauri-apps/cli"]
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        self.assertNotIn("^", version)
        self.assertNotIn("~", version)
        lock = (ROOT / "tools/tauri-spike/package-lock.json").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("registry.npmmirror.com", lock)
        self.assertIn("registry.npmjs.org", lock)
        self.assertEqual(
            package["scripts"]["audit:official"],
            "npm audit --registry=https://registry.npmjs.org --json",
        )
        audit_gate = (ROOT / "scripts/check_tauri_npm_audit.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("https://registry.npmjs.org", audit_gate)
        self.assertNotIn("--omit=optional", audit_gate)
        self.assertIn("vulnerabilities_total", audit_gate)

    def test_spike_evidence_manifest_is_current(self) -> None:
        normalized, digest = recompute_manifest(SPIKE_MANIFEST)
        self.assertEqual(
            SPIKE_MANIFEST.read_text(encoding="utf-8").rstrip("\r\n"),
            normalized,
        )
        self.assertEqual(
            SPIKE_MANIFEST.with_suffix(".sha256")
            .read_text(encoding="ascii")
            .strip(),
            digest,
        )


if __name__ == "__main__":
    unittest.main()
