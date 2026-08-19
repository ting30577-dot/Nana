"""Static contract tests for the protected Stage 1 CI trust boundary."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/tauri-stage1-protected.yml"
ACTIVE_STATE = ROOT / "docs/ACTIVE_STATE.json"


class TauriProtectedCITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_workflow_has_a_stable_read_only_required_job(self) -> None:
        self.assertIn("tauri-stage1-protected:", self.workflow)
        self.assertIn("name: Tauri Stage 1 protected gate", self.workflow)
        self.assertIn("runs-on: windows-latest", self.workflow)
        self.assertRegex(self.workflow, r"(?m)^permissions:\n  contents: read$")
        self.assertNotIn("pull_request_target", self.workflow)
        self.assertNotRegex(self.workflow, r"(?m)^\s+\w+-all: write$")

    def test_checkout_cannot_persist_credentials_and_actions_are_sha_pinned(self) -> None:
        self.assertIn("fetch-depth: 0", self.workflow)
        self.assertIn("persist-credentials: false", self.workflow)
        action_lines = re.findall(r"(?m)^\s+uses: ([^\s]+)$", self.workflow)
        self.assertGreaterEqual(len(action_lines), 3)
        for action in action_lines:
            with self.subTest(action=action):
                self.assertRegex(action, r"^[^@]+@[0-9a-f]{40}$")

    def test_detached_repository_variable_is_mandatory_and_not_inlined(self) -> None:
        self.assertIn(
            "NANA_TAURI_GATE_SHA256: ${{ vars.NANA_TAURI_STAGE1_GATE_SHA256 }}",
            self.workflow,
        )
        self.assertIn("[string]::IsNullOrWhiteSpace", self.workflow)
        self.assertIn("-cnotmatch '^[0-9a-f]{64}$'", self.workflow)
        self.assertIn("scripts/check_tauri_spike_gate.ps1", self.workflow)
        self.assertNotIn(
            "a2249052b11fb65b25cb201c956db70eeb82ad4eb81bd827aad76d2179fc65cb",
            self.workflow,
        )

    def test_release_privacy_scan_runs_against_the_pr_file_set(self) -> None:
        self.assertIn(
            "github.event.pull_request.base.sha || github.event.before",
            self.workflow,
        )
        self.assertIn("$base = 'HEAD~1'", self.workflow)
        self.assertIn(
            "python scripts/nana_context.py release-privacy-scan --base $base --head HEAD",
            self.workflow,
        )

    def test_ci_toolchain_and_security_auditor_are_version_pinned(self) -> None:
        for expected in (
            "python-version: 3.12.10",
            "architecture: x64",
            "sys.version_info[:3] == (3, 12, 10)",
            "struct.calcsize('P') * 8 == 64",
            "node-version: 24.15.0",
            "npm@11.12.1",
            "1.97.1-x86_64-pc-windows-msvc",
            "cargo-audit --version 0.22.2 --locked",
            "cargo audit --file src-tauri/Cargo.lock",
            "package-manager-cache: false",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, self.workflow)
        self.assertNotIn("cargo audit fetch", self.workflow)

    def test_owner_acceptance_does_not_authorize_product_migration(self) -> None:
        state = json.loads(ACTIVE_STATE.read_text(encoding="utf-8"))
        active = state["active_product_stage"]
        self.assertEqual(
            active["product_owner_decision"],
            "accept_static_shell_without_product_migration",
        )
        self.assertFalse(active["product_migration_authorized"])
        self.assertEqual(
            state["next_gate"]["id"],
            "tauri-stage-1-protected-ci-activation",
        )


if __name__ == "__main__":
    unittest.main()
