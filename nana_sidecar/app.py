"""FastAPI application factory for the vNext sidecar."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI

from nana_sidecar import (
    API_VERSION,
    APP_VERSION,
    SCHEMA_READ_CEILING,
    SCHEMA_VERSION,
)
from nana_sidecar.api_models import (
    ContractCatalogInfo,
    HandshakeResponse,
    HealthResponse,
)
from nana_sidecar.contracts.catalog import ContractCatalogSchema
from nana_sidecar.contracts.commands import DEV_COMMAND_NAMES
from nana_sidecar.contracts.domain import EventType, RelationType
from nana_sidecar.contracts.locators import LOCATOR_KINDS


def _catalog_schema() -> dict[str, Any]:
    return ContractCatalogSchema.model_json_schema(
        ref_template="#/components/schemas/{model}"
    )


def _schema_hash(schema: dict[str, Any]) -> str:
    payload = json.dumps(
        schema, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _install_contract_openapi(app: FastAPI) -> None:
    original_openapi: Callable[[], dict[str, Any]] = app.openapi

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is not None:
            return app.openapi_schema
        schema = original_openapi()
        catalog = _catalog_schema()
        definitions = catalog.pop("$defs", {})
        components = schema.setdefault("components", {}).setdefault("schemas", {})
        components.update(definitions)
        components["ContractCatalogSchema"] = catalog
        app.openapi_schema = schema
        return schema

    app.openapi = openapi


def create_app() -> FastAPI:
    """Build a read-only D0 app; command mutations arrive in later slices."""

    app = FastAPI(
        title="Nana Sidecar",
        version=APP_VERSION,
        docs_url="/api/docs",
        redoc_url=None,
    )

    @app.get("/healthz", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse()

    @app.get(
        "/api/v1/handshake",
        response_model=HandshakeResponse,
        tags=["system"],
    )
    def handshake() -> HandshakeResponse:
        return HandshakeResponse(
            app_version=APP_VERSION,
            api_version=API_VERSION,
            schema_version=SCHEMA_VERSION,
            schema_read_ceiling=SCHEMA_READ_CEILING,
        )

    @app.get(
        "/api/v1/contracts",
        response_model=ContractCatalogInfo,
        tags=["system"],
    )
    def contract_catalog() -> ContractCatalogInfo:
        schema = _catalog_schema()
        names = tuple(sorted(schema.get("$defs", {})))
        return ContractCatalogInfo(
            schema_hash=_schema_hash(schema),
            schema_names=names,
            command_names=tuple(sorted(DEV_COMMAND_NAMES)),
            event_types=tuple(sorted(item.value for item in EventType)),
            locator_kinds=tuple(sorted(LOCATOR_KINDS)),
            relation_types=tuple(sorted(item.value for item in RelationType)),
        )

    _install_contract_openapi(app)
    return app
