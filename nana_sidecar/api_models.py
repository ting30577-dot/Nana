"""Read-only D0 sidecar endpoint models."""

from __future__ import annotations

from typing import Literal

from nana_sidecar.contracts.common import ContractModel


class ExportSelectionInfo(ContractModel):
    selection_id: str
    label: str
    expires_at: str
    provenance: Literal["interactive_user", "test_harness"]


class HealthResponse(ContractModel):
    status: Literal["ok"] = "ok"


class HandshakeResponse(ContractModel):
    app_version: str
    api_version: str
    schema_version: int
    schema_read_ceiling: int
    mode: Literal["development_contract_only"] = "development_contract_only"
    mutations_enabled: Literal[False] = False


class RuntimeHandshakeResponse(ContractModel):
    app_version: str
    api_version: str
    schema_version: int
    schema_read_ceiling: int
    mode: Literal["development_runtime"] = "development_runtime"
    mutations_enabled: Literal[True] = True
    enabled_mutations: tuple[str, ...]
    execution_enabled: bool = False
    external_effects_enabled: bool = False
    export_selections: tuple[ExportSelectionInfo, ...] = ()


class ContractCatalogInfo(ContractModel):
    schema_hash: str
    schema_names: tuple[str, ...]
    command_names: tuple[str, ...]
    event_types: tuple[str, ...]
    locator_kinds: tuple[str, ...]
    relation_types: tuple[str, ...]
