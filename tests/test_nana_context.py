"""Executable governance checks for bounded Nana task context."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import nana_context


ROOT = Path(__file__).resolve().parents[1]


class NanaContextTests(unittest.TestCase):
    def test_governance_inputs_are_consistent(self) -> None:
        results = nana_context.check()
        self.assertIn("D3 baseline and Tauri stage-1 boundary agree", results)

    def test_bootstrap_is_route_bounded_and_relative(self) -> None:
        capsule = nana_context.bootstrap("tauri-shell", external=True)
        self.assertIn("`tauri-shell`", capsule)
        self.assertIn("docs/PROJECT_KERNEL.md", capsule)
        self.assertIn("src-tauri", capsule)
        self.assertNotIn(str(ROOT), capsule)
        self.assertNotRegex(capsule, r"[A-Za-z]:[/\\]")
        self.assertNotIn("D:\\Obsidian Vault", capsule)

    def test_review_level_is_proportional(self) -> None:
        self.assertEqual(nana_context.review_level(["nana_web/src/App.tsx"])[0], "R1")
        self.assertEqual(nana_context.review_level(["nana_sidecar/auth.py"])[0], "R2")
        self.assertEqual(nana_context.review_level([], milestone=True)[0], "R3")

    def test_privacy_scan_reports_categories_without_echoing_values(self) -> None:
        secret = "sk-ant-abcdefghijklmnop"
        text = (
            "C:\\Users\\owner\\packet.md\n"
            f"token={secret}\n"
            "host=192.168.1.4\n"
            "mac=aa:bb:cc:dd:ee:ff\n"
            '\"license_key\": \"licensed-value\"\n'
        )
        findings = nana_context.privacy_findings(text)
        categories = {str(item["category"]) for item in findings}
        self.assertEqual(
            categories,
            {
                "windows_user_path",
                "api_key",
                "credential_field",
                "private_ipv4",
                "mac_address",
                "sensitive_identity_field",
            },
        )
        self.assertNotIn(secret, json.dumps(findings))

    def test_privacy_scan_allows_hardware_model_and_software_version(self) -> None:
        text = (
            "hardware_model=Example GPU\n"
            "software_version=1.2.3\n"
            "token=<redacted>\n"
            "Authorization: Bearer <redacted>\n"
            "password=***\n"
        )
        self.assertEqual(nana_context.privacy_findings(text), [])

    def test_privacy_scan_blocks_common_credential_forms(self) -> None:
        text = (
            "Authorization: Bearer bearer-value\n"
            "X-API-Key: relay-secret-value\n"
            "ANTHROPIC_API_KEY=provider-value\n"
            "password=password-value\n"
            "token=token-value\n"
            "session_cookie=session-value\n"
        )
        categories = {
            str(item["category"]) for item in nana_context.privacy_findings(text)
        }
        self.assertEqual(categories, {"authorization_header", "credential_field"})
        findings = json.dumps(nana_context.privacy_findings(text))
        for secret in (
            "bearer-value",
            "relay-secret-value",
            "provider-value",
            "password-value",
            "token-value",
            "session-value",
        ):
            self.assertNotIn(secret, findings)

    def test_cleanup_plan_respects_keep_set_and_legacy_gate(self) -> None:
        candidates = nana_context.cleanup_candidates()
        retention = json.loads(
            (ROOT / "config" / "document-retention.json").read_text(encoding="utf-8")
        )
        self.assertTrue(set(candidates).isdisjoint(retention["keep_exact"]))
        self.assertFalse(any(path.startswith("ui/") for path in candidates))
        self.assertFalse(any(path.startswith("db/") for path in candidates))
        self.assertTrue(nana_context.should_delete("docs/claude_example.md", retention))
        self.assertTrue(
            nana_context.should_delete(
                "obsidian_export/Nana_研究系统/README_废版.md", retention
            )
        )
        self.assertFalse(
            nana_context.should_delete("docs/PROJECT_KERNEL.md", retention)
        )

    def test_project_skill_has_valid_minimal_frontmatter(self) -> None:
        skill = (ROOT / ".agents" / "skills" / "nana-project-workflow" / "SKILL.md")
        text = skill.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\nname: nana-project-workflow\n"))
        self.assertEqual(text.split("---", 2)[1].count("\ndescription:"), 1)
        self.assertNotIn("TODO", text)
        metadata = (
            ROOT / ".agents" / "skills" / "nana-project-workflow" / "agents" / "openai.yaml"
        ).read_text(encoding="utf-8")
        self.assertIn("$nana-project-workflow", metadata)

    def test_cleanup_apply_requires_explicit_confirmation(self) -> None:
        with self.assertRaises(nana_context.GovernanceError):
            nana_context.apply_cleanup("")

    def test_generated_cleanup_is_explicit_and_never_targets_protected_roots(self) -> None:
        with self.assertRaises(nana_context.GovernanceError):
            nana_context.apply_generated_cleanup("")
        retention = json.loads(
            (ROOT / "config" / "document-retention.json").read_text(encoding="utf-8")
        )
        generated = set(retention["generated_cleanup_roots"])
        protected = set(retention["never_delete_without_gate"])
        self.assertTrue(generated.isdisjoint(protected))
        self.assertNotIn("backups", generated)
        self.assertNotIn(".venv", generated)

    def test_cleanup_path_validation_is_fail_closed(self) -> None:
        for unsafe in (
            "../outside",
            "..\\outside",
            "/absolute",
            "\\absolute",
            "C:/outside",
            "C:\\outside",
            "",
            ".",
        ):
            with self.subTest(path=unsafe):
                with self.assertRaises(nana_context.GovernanceError):
                    nana_context._safe_cleanup_target(unsafe)

    def test_status_paths_parse_nul_delimited_rename_records(self) -> None:
        records = ["R  docs/new.md", "docs/old.md", "?? notes/new.md"]
        with patch.object(nana_context, "_git_paths", return_value=records):
            self.assertEqual(
                nana_context._status_paths(),
                ["docs/new.md", "notes/new.md"],
            )


if __name__ == "__main__":
    unittest.main()
