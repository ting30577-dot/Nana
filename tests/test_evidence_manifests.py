"""Executable checks for the current D3 evidence manifest."""

from __future__ import annotations

import unittest
from pathlib import Path

from scripts.refresh_evidence_manifest import recompute_manifest


ROOT = Path(__file__).resolve().parents[1]
FINAL_MANIFEST = ROOT / "docs/evidence/v0.3.0-dev-d3-final-manifest.txt"


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
                "nana_web/src/main.tsx",
                "scripts/run_d3_dev_journey.py",
                "docs/CURRENT_D3_AUTHORITY.md",
            }
            <= paths
        )


if __name__ == "__main__":
    unittest.main()
