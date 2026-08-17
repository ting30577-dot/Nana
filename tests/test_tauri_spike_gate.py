"""Executable gates for the post-D3 Tauri spike entry decision."""

from __future__ import annotations

import json
import subprocess
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
        self.assertFalse((ROOT / "src-tauri").exists())

    def test_toolchain_evidence_closes_prerequisites_not_product_gate(self) -> None:
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        evidence = json.loads(TOOLCHAIN_EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(
            policy["status"], "spike_entry_authorized_toolchain_verified"
        )
        self.assertEqual(evidence["status"], "PASS_FOR_MINIMAL_SPIKE_SCAFFOLD")
        self.assertEqual(evidence["execution_proof"]["preflight"], "PASS_8_OF_8")
        self.assertEqual(evidence["execution_proof"]["cargo_check"], "PASS")
        self.assertEqual(
            evidence["execution_proof"]["linked_probe_execution"],
            "PASS_HELLO_WORLD",
        )
        self.assertFalse(evidence["boundary"]["product_code_authorized"])
        self.assertFalse(evidence["boundary"]["src_tauri_created"])

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
