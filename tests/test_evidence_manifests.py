"""Executable checks for the current D3 evidence manifest."""

from __future__ import annotations

import unittest
import json
import re
from pathlib import Path

from scripts.refresh_evidence_manifest import recompute_manifest


ROOT = Path(__file__).resolve().parents[1]
FINAL_MANIFEST = ROOT / "docs/evidence/v0.3.0-dev-d3-final-manifest.txt"
AUTHORITY = ROOT / "docs/CURRENT_D3_AUTHORITY.md"
README = ROOT / "README.md"
GATE = ROOT / "docs/evidence/v0.3.0-dev-d3-09-gate-decision.json"
VAULT = ROOT / "obsidian_export/Nana_研究系统_vNext"


class CurrentEvidenceManifestTests(unittest.TestCase):
    def test_final_manifest_hashes_and_digest_are_current(self) -> None:
        normalized, digest = recompute_manifest(FINAL_MANIFEST)
        self.assertEqual(
            FINAL_MANIFEST.read_text(encoding="utf-8").rstrip("\r\n"),
            normalized,
        )
        self.assertEqual(
            FINAL_MANIFEST.with_suffix(".sha256")
            .read_text(encoding="ascii")
            .strip(),
            digest,
        )

    def test_final_manifest_covers_live_launcher_authority(self) -> None:
        paths = {
            line.split("\t", 1)[0]
            for line in FINAL_MANIFEST.read_text(encoding="utf-8").splitlines()
        }
        self.assertTrue(
            {
                ".gitattributes",
                "nana_web/src/main.tsx",
                "scripts/run_d3_dev_journey.py",
                "docs/CURRENT_D3_AUTHORITY.md",
                "docs/evidence/v0.3.0-dev-d3-09-gate-decision.json",
                "tests/test_evidence_manifests.py",
            }
            <= paths
        )
        self.assertIn(
            "* text=auto eol=lf",
            (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines(),
        )

    def test_current_authority_readme_and_machine_gate_agree(self) -> None:
        authority = AUTHORITY.read_text(encoding="utf-8")
        readme = README.read_text(encoding="utf-8")
        gate = json.loads(GATE.read_text(encoding="utf-8"))
        marker_match = re.search(
            r"<!-- nana-current-authority\s+(.*?)-->", authority, re.DOTALL
        )
        self.assertIsNotNone(marker_match)
        marker = dict(
            line.strip().split(": ", 1)
            for line in marker_match.group(1).splitlines()
            if ": " in line
        )
        self.assertEqual(marker["status"], gate["status"])
        self.assertEqual(marker["d3_complete"], str(gate["d3_complete"]).lower())
        self.assertIn(f"`{gate['status']}`", readme)
        self.assertIn(f"`d3_complete={str(gate['d3_complete']).lower()}`", readme)
        self.assertEqual(gate["status"], "acceptance_pending")
        self.assertIs(gate["d3_complete"], False)
        self.assertTrue(gate["blocking_gate"]["required"])
        self.assertFalse(gate["blocking_gate"]["satisfied"])

    def test_current_vault_pages_share_the_pending_conclusion(self) -> None:
        for name in (
            "07_版本路线图与验收门槛.md",
            "10_完整性_可行性_可执行性终审.md",
            "11_首个纵向切片执行清单.md",
            "12_验证记录与证据索引.md",
        ):
            with self.subTest(name=name):
                text = (VAULT / name).read_text(encoding="utf-8")
                self.assertIn("acceptance_pending", text)
                self.assertIn("d3_complete=false", text)
        audit = (VAULT / "10_完整性_可行性_可执行性终审.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("verdict: d3-acceptance-pending", audit)

    def test_historical_acceptance_records_are_explicitly_noncurrent(self) -> None:
        historical = (
            ROOT / "docs/d3_completion_audit.md",
            ROOT / "docs/d3_09_codex_final_acceptance_20260813.md",
            ROOT / "docs/evidence/v0.3.0-dev-d3-09-completion.md",
            ROOT / "docs/evidence/v0.3.0-dev-d3-authority-sync-summary.md",
        )
        for path in historical:
            with self.subTest(path=path.name):
                first_block = "\n".join(
                    path.read_text(encoding="utf-8").splitlines()[:12]
                ).casefold()
                self.assertRegex(first_block, r"historical|superseded")
                self.assertRegex(first_block, r"current authority|current status")

    def test_current_verification_numbers_are_consistent(self) -> None:
        gate = json.loads(GATE.read_text(encoding="utf-8"))
        self.assertEqual(gate["evidence"]["snapshot_state"], "current_refrozen")
        python_total = gate["evidence"]["full_python"]["total"]
        python_skips = gate["evidence"]["full_python"]["skipped"]
        browser_total = gate["evidence"]["browser_release_matrix"]["total"]
        authority = AUTHORITY.read_text(encoding="utf-8")
        vault_11 = (VAULT / "11_首个纵向切片执行清单.md").read_text(
            encoding="utf-8"
        )
        vault_12 = (VAULT / "12_验证记录与证据索引.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            f"{python_total} run; {python_total - python_skips} passed, "
            f"{python_skips} skipped",
            authority,
        )
        self.assertIn(f"release matrix: {browser_total}/{browser_total}", authority)
        self.assertIn(f"Python {python_total} passed / {python_skips} skipped", vault_11)
        self.assertIn(f"{browser_total}/{browser_total}", vault_11)
        self.assertIn(f"Python {python_total} passed / {python_skips} skipped", vault_12)
        self.assertIn(f"{browser_total}/{browser_total}", vault_12)

    def test_current_manifest_is_labeled_as_current_not_an_acceptance_claim(self) -> None:
        gate = json.loads(GATE.read_text(encoding="utf-8"))
        manifest = gate["evidence"]["manifest"]
        self.assertEqual(
            manifest["path"],
            "docs/evidence/v0.3.0-dev-d3-final-manifest.txt",
        )
        self.assertEqual(manifest["record_kind"], "current_worktree")
        self.assertNotIn("complete", manifest["record_kind"])


if __name__ == "__main__":
    unittest.main()
