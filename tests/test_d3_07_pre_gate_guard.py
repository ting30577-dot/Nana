"""Executable governance and residual D3-07 safety guards."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from nana_sidecar.api_models import RuntimeHandshakeResponse
from nana_sidecar.contracts.builtin_capabilities import python_unittest_locked_registry_entry
from nana_sidecar.contracts.journey import JOURNEY_COMMAND_NAMES


class D307PreGateGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]

    def test_machine_gate_records_codex_only_implementation_exit(self) -> None:
        gate_path = self.root / "docs" / "evidence" / "v0.3.0-dev-d3-07-gate-decision.json"
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
        self.assertEqual(gate["stage"], "D3-07")
        self.assertEqual(gate["substage"], "07-00")
        self.assertEqual(gate["joint_status"], "unresolved")
        self.assertEqual(gate["governance"]["mode"], "codex_only")
        self.assertEqual(gate["governance"]["codex_only_entry_status"], "accepted")
        self.assertIs(gate["implementation_authorized"], True)
        self.assertIs(gate["capability_registered"], True)
        self.assertIs(gate["filesystem_write_authorized"], True)
        self.assertEqual(gate["codex"]["decision"], "ACCEPT")
        for record in gate["source_records"]:
            with self.subTest(record=record):
                self.assertTrue((self.root / record).is_file())

    def test_curated_journey_union_exposes_only_narrow_approval_requests(self) -> None:
        forbidden = {
            "AuthorizeAction",
            "PublishExport",
            "ConsumeApproval",
        }
        self.assertTrue({"RequestApproval", "DecideApproval"} <= JOURNEY_COMMAND_NAMES)
        self.assertTrue(forbidden.isdisjoint(JOURNEY_COMMAND_NAMES))

    def test_browser_sse_surface_does_not_use_native_eventsource(self) -> None:
        source_root = self.root / "nana_web" / "src"
        source_files = tuple(source_root.rglob("*.ts")) + tuple(source_root.rglob("*.tsx"))
        self.assertTrue(source_files)
        offenders = [
            path.relative_to(self.root).as_posix()
            for path in source_files
            if "EventSource" in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(offenders, [])

    def test_historical_pre_gate_handshake_defaults_to_no_external_effects(self) -> None:
        entry = python_unittest_locked_registry_entry()
        self.assertEqual(entry.capability.id, "python.unittest.locked")
        self.assertEqual(entry.risk_tier.value, "T2")
        self.assertEqual(entry.write_roots, ())
        self.assertEqual(entry.network_targets, ())
        self.assertEqual(entry.network_methods, ())
        handshake = RuntimeHandshakeResponse(
            app_version="0.3.0-dev",
            api_version="1",
            schema_version=7,
            schema_read_ceiling=7,
            enabled_mutations=tuple(sorted(JOURNEY_COMMAND_NAMES)),
            execution_enabled=True,
        )
        self.assertIs(handshake.external_effects_enabled, False)

    def test_handoff_records_current_no_claude_continuation_boundary(self) -> None:
        handoff = (self.root / "D3_HANDOFF_START_HERE.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Snapshot date: 2026-08-10", handoff)
        self.assertIn("not call, retry, or wait for Claude", handoff)
        self.assertIn(
            "docs/evidence/v0.3.0-dev-d3-local-regression-and-manifest-refresh-20260810.md",
            handoff,
        )
        self.assertNotIn("372 full Python tests pass", handoff)


if __name__ == "__main__":
    unittest.main()
