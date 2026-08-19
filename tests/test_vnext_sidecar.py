"""Read-only D0 FastAPI boundary tests."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from nana_sidecar.app import create_app


class VNextSidecarTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.client = AsyncClient(
            transport=ASGITransport(app=create_app()),
            base_url="http://test",
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def test_health_and_handshake_do_not_claim_runtime_mutations(
        self,
    ) -> None:
        health = await self.client.get("/healthz")
        self.assertEqual(health.json(), {"status": "ok"})

        response = await self.client.get("/api/v1/handshake")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "app_version": "0.3.0-dev",
                "api_version": "1",
                "schema_version": 7,
                "schema_read_ceiling": 7,
                "mode": "development_contract_only",
                "mutations_enabled": False,
            },
        )

    async def test_openapi_contains_shared_python_types(self) -> None:
        schema = (await self.client.get("/openapi.json")).json()
        components = schema["components"]["schemas"]

        self.assertTrue(
            {
                "CreateProject",
                "CreateInquiry",
                "ProposePlan",
                "Run",
                "Action",
                "Event",
                "Artifact",
                "Resource",
                "Locator",
                "Evidence",
                "Finding",
                "ArtifactStagedEvent",
                "ArtifactCommittedEvent",
                "ArtifactReconciledEvent",
            }
            <= set(components)
        )
        lifecycle = components["ContractCatalogSchema"]["properties"][
            "artifact_lifecycle_event"
        ]
        self.assertEqual(lifecycle["discriminator"]["propertyName"], "type")
        self.assertEqual(
            set(lifecycle["discriminator"]["mapping"]),
            {
                "artifact.staged",
                "artifact.committed",
                "artifact.reconciled",
            },
        )

    async def test_d0_has_no_mutation_route(self) -> None:
        schema = (await self.client.get("/openapi.json")).json()
        mutation_methods = {
            method
            for operations in schema["paths"].values()
            for method in operations
            if method in {"post", "put", "patch", "delete"}
        }
        self.assertEqual(mutation_methods, set())

    async def test_contract_catalog_has_stable_hash_and_names(self) -> None:
        first = (await self.client.get("/api/v1/contracts")).json()
        second = (await self.client.get("/api/v1/contracts")).json()

        self.assertEqual(first, second)
        self.assertRegex(first["schema_hash"], r"^sha256:[0-9a-f]{64}$")
        self.assertIn("DraftFinding", first["schema_names"])
        self.assertIn("ArtifactStagedEvent", first["schema_names"])

    async def test_checked_in_openapi_snapshot_is_current(self) -> None:
        root = Path(__file__).resolve().parents[1]
        snapshot = json.loads(
            (root / "fixtures" / "v0.3.0-dev" / "d0_openapi.json").read_text(
                encoding="utf-8"
            )
        )
        live = (await self.client.get("/openapi.json")).json()

        self.assertEqual(snapshot, live)


if __name__ == "__main__":
    unittest.main()
