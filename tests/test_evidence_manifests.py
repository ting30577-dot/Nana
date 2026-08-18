"""Executable checks for the current D3 evidence manifest."""

from __future__ import annotations

import hashlib
import unittest
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FINAL_MANIFEST = ROOT / "docs/evidence/v0.3.0-dev-d3-final-manifest.txt"
AUTHORITY = ROOT / "docs/CURRENT_D3_AUTHORITY.md"
README = ROOT / "README.md"
ACTIVE_STATE = ROOT / "docs/ACTIVE_STATE.json"
GATE = ROOT / "docs/evidence/v0.3.0-dev-d3-09-gate-decision.json"
OBSERVATION = (
    ROOT
    / "docs/evidence/v0.3.0-dev-d3-observed-session-owner-attestation-20260817.json"
)
VAULT = ROOT / "obsidian_export/Nana_研究系统_vNext"
BASELINE_REF = "refs/tags/v0.3.0-dev-d3-final"


def baseline_blob(relative: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{BASELINE_REF}:{relative}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout


class CurrentEvidenceManifestTests(unittest.TestCase):
    def test_final_manifest_hashes_and_digest_are_tag_bound(self) -> None:
        relative_manifest = FINAL_MANIFEST.relative_to(ROOT).as_posix()
        manifest_text = baseline_blob(relative_manifest).decode("utf-8")
        relative_paths = [
            line.split("\t", 1)[0] for line in manifest_text.splitlines()
        ]
        normalized = "\n".join(
            f"{relative}\t{hashlib.sha256(baseline_blob(relative)).hexdigest()}"
            for relative in relative_paths
        )
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        self.assertEqual(
            manifest_text.rstrip("\r\n"),
            normalized,
        )
        self.assertEqual(
            baseline_blob(
                FINAL_MANIFEST.with_suffix(".sha256").relative_to(ROOT).as_posix()
            )
            .decode("ascii")
            .strip(),
            digest,
        )
        self.assertEqual(FINAL_MANIFEST.read_bytes(), manifest_text.encode("utf-8"))

    def test_final_manifest_covers_live_launcher_authority(self) -> None:
        paths = {
            line.split("\t", 1)[0]
            for line in baseline_blob(FINAL_MANIFEST.relative_to(ROOT).as_posix())
            .decode("utf-8")
            .splitlines()
        }
        self.assertTrue(
            {
                ".gitattributes",
                "nana_web/src/main.tsx",
                "scripts/run_d3_dev_journey.py",
                "docs/CURRENT_D3_AUTHORITY.md",
                "docs/evidence/v0.3.0-dev-d3-09-gate-decision.json",
                "docs/evidence/v0.3.0-dev-d3-observed-session-owner-attestation-20260817.json",
                "docs/evidence/v0.3.0-dev-d3-release-baseline-freeze-20260817.md",
                "tests/test_evidence_manifests.py",
            }
            <= paths
        )
        self.assertIn(
            "* text=auto eol=lf",
            baseline_blob(".gitattributes").decode("utf-8").splitlines(),
        )

    def test_current_authority_readme_and_machine_gate_agree(self) -> None:
        authority = AUTHORITY.read_text(encoding="utf-8")
        readme = README.read_text(encoding="utf-8")
        active_state = json.loads(ACTIVE_STATE.read_text(encoding="utf-8"))
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
        self.assertEqual(
            marker["release_baseline_frozen"],
            str(gate["release_baseline_frozen"]).lower(),
        )
        self.assertEqual(active_state["stable_baseline"]["status"], gate["status"])
        self.assertEqual(
            active_state["stable_baseline"]["authority"],
            "docs/CURRENT_D3_AUTHORITY.md",
        )
        self.assertFalse(
            active_state["active_product_stage"]["product_migration_authorized"]
        )
        self.assertIn("docs/PROJECT_KERNEL.md", readme)
        self.assertIn("docs/ACTIVE_STATE.json", readme)
        self.assertIn("Tauri product migration is", readme)
        self.assertIn("**not** authorized", readme)
        self.assertEqual(
            gate["status"], "acceptance_complete_release_baseline_frozen"
        )
        self.assertIs(gate["d3_complete"], True)
        self.assertIs(gate["release_baseline_frozen"], True)
        self.assertTrue(gate["governance"]["claude_call_attempted_in_current_gate"])
        self.assertFalse(gate["governance"]["claude_verdict_obtained"])
        self.assertFalse(gate["governance"]["claude_required_in_current_gate"])
        self.assertTrue(gate["blocking_gate"]["required"])
        self.assertTrue(gate["blocking_gate"]["satisfied"])

    def test_current_vault_pages_share_the_frozen_baseline_conclusion(self) -> None:
        for name in (
            "07_版本路线图与验收门槛.md",
            "10_完整性_可行性_可执行性终审.md",
            "11_首个纵向切片执行清单.md",
            "12_验证记录与证据索引.md",
        ):
            with self.subTest(name=name):
                text = (VAULT / name).read_text(encoding="utf-8")
                self.assertIn("acceptance_complete_release_baseline_frozen", text)
                self.assertIn("d3_complete=true", text)
                self.assertIn("release_baseline_frozen=true", text)
        audit = (VAULT / "10_完整性_可行性_可执行性终审.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("verdict: d3-acceptance-complete-release-baseline-frozen", audit)

    def test_historical_acceptance_records_live_in_the_frozen_tag(self) -> None:
        historical = (
            "docs/d3_completion_audit.md",
            "docs/d3_09_codex_final_acceptance_20260813.md",
            "docs/evidence/v0.3.0-dev-d3-09-completion.md",
            "docs/evidence/v0.3.0-dev-d3-authority-sync-summary.md",
        )
        active_state = json.loads(ACTIVE_STATE.read_text(encoding="utf-8"))
        self.assertIn(
            "AI review packets and responses",
            active_state["non_authoritative_sources"],
        )
        for relative in historical:
            with self.subTest(path=relative):
                self.assertTrue(baseline_blob(relative))

    def test_current_verification_numbers_are_consistent(self) -> None:
        gate = json.loads(GATE.read_text(encoding="utf-8"))
        self.assertEqual(
            gate["evidence"]["snapshot_state"],
            "current_refrozen",
        )
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

    def test_manifest_is_current_and_bound_to_the_observation_result(self) -> None:
        gate = json.loads(GATE.read_text(encoding="utf-8"))
        manifest = gate["evidence"]["manifest"]
        self.assertEqual(
            manifest["path"],
            "docs/evidence/v0.3.0-dev-d3-final-manifest.txt",
        )
        self.assertEqual(manifest["record_kind"], "current_frozen_release_baseline")
        self.assertIs(manifest["current"], True)
        self.assertEqual(
            manifest["bound_result_commit"],
            "278f3a4186d7d0f85f6caf715c2882d63c589fc6",
        )
        self.assertEqual(
            gate["baseline_binding"]["result_commit"],
            manifest["bound_result_commit"],
        )

    def test_observation_gate_uses_an_honest_owner_evidence_exception(self) -> None:
        gate = json.loads(GATE.read_text(encoding="utf-8"))
        record = json.loads(OBSERVATION.read_text(encoding="utf-8"))
        self.assertEqual(
            gate["blocking_gate"]["evidence"],
            OBSERVATION.relative_to(ROOT).as_posix(),
        )
        self.assertTrue(record["duration"]["owner_attested_completed"])
        self.assertFalse(record["subjective_observation"]["satisfaction_claimed"])
        self.assertFalse(
            record["original_rubric_evidence"]["measured_rubric_pass_claimed"]
        )
        self.assertIsNone(
            record["original_rubric_evidence"]["clarifications_count"]
        )
        self.assertIsNone(
            record["original_rubric_evidence"]["state_questions_correct_out_of_10"]
        )
        self.assertEqual(
            record["governance_resolution"]["decision"],
            "ACCEPT_BY_PRODUCT_OWNER_EVIDENCE_EXCEPTION",
        )
        self.assertFalse(
            record["collaboration_governance"]["claude_required_for_this_gate"]
        )


if __name__ == "__main__":
    unittest.main()
