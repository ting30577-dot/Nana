"""Typed Evidence locator coordinate schemas."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import PurePosixPath
from typing import Annotated, Literal, Union

from pydantic import Field, HttpUrl, field_validator, model_validator

from nana_sidecar.contracts.common import (
    ContractModel,
    HashDigest,
    Identifier,
)


_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:")


def validate_logical_path(value: str) -> str:
    """Return a portable relative reference or reject path traversal."""

    normalized = value.replace("\\", "/").strip()
    path = PurePosixPath(normalized)
    if (
        not normalized
        or normalized.startswith("/")
        or _WINDOWS_DRIVE.match(normalized)
        or ".." in path.parts
        or "." in path.parts
    ):
        raise ValueError("locator paths must be normalized relative logical paths")
    return path.as_posix()


class LineSpan(ContractModel):
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)

    @model_validator(mode="after")
    def ordered(self) -> "LineSpan":
        if self.end_line < self.start_line:
            raise ValueError("end_line must be greater than or equal to start_line")
        return self


class ByteSpan(ContractModel):
    start_byte: int = Field(ge=0)
    end_byte: int = Field(gt=0)

    @model_validator(mode="after")
    def ordered(self) -> "ByteSpan":
        if self.end_byte <= self.start_byte:
            raise ValueError("end_byte must be greater than start_byte")
        return self


class CharacterSpan(ContractModel):
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)

    @model_validator(mode="after")
    def ordered(self) -> "CharacterSpan":
        if self.end_char <= self.start_char:
            raise ValueError("end_char must be greater than start_char")
        return self


class BoundingBox(ContractModel):
    x0: float = Field(ge=0)
    y0: float = Field(ge=0)
    x1: float = Field(gt=0)
    y1: float = Field(gt=0)

    @model_validator(mode="after")
    def ordered(self) -> "BoundingBox":
        if self.x1 <= self.x0 or self.y1 <= self.y0:
            raise ValueError("bounding-box maximums must exceed minimums")
        return self


class WebCoordinates(ContractModel):
    kind: Literal["web"] = "web"
    canonical_url: HttpUrl
    retrieved_at: datetime
    content_hash: HashDigest
    quote_span: CharacterSpan | None = None
    dom_anchor: str | None = Field(default=None, min_length=1, max_length=2000)

    @model_validator(mode="after")
    def require_anchor(self) -> "WebCoordinates":
        if self.quote_span is None and self.dom_anchor is None:
            raise ValueError("web locator requires quote_span or dom_anchor")
        return self


class PdfCoordinates(ContractModel):
    kind: Literal["pdf"] = "pdf"
    artifact_hash: HashDigest
    page: int = Field(ge=1)
    bounding_box: BoundingBox | None = None
    character_span: CharacterSpan | None = None
    parser_id: Annotated[str, Field(min_length=1, max_length=160)]
    parser_version: Annotated[str, Field(min_length=1, max_length=80)]

    @model_validator(mode="after")
    def require_position(self) -> "PdfCoordinates":
        if self.bounding_box is None and self.character_span is None:
            raise ValueError("PDF locator requires bounding_box or character_span")
        return self


class RepoCoordinates(ContractModel):
    kind: Literal["repo"] = "repo"
    remote: Annotated[str, Field(min_length=1, max_length=2000)]
    commit: Annotated[str, Field(pattern=r"^[0-9a-fA-F]{7,64}$")]
    path: Annotated[str, Field(min_length=1, max_length=2000)]
    symbol: str | None = Field(default=None, min_length=1, max_length=500)
    line_span: LineSpan | None = None

    _relative_path = field_validator("path")(validate_logical_path)

    @model_validator(mode="after")
    def require_position(self) -> "RepoCoordinates":
        if self.symbol is None and self.line_span is None:
            raise ValueError("repo locator requires symbol or line_span")
        return self


class LocalFileCoordinates(ContractModel):
    kind: Literal["local_file"] = "local_file"
    artifact_hash: HashDigest
    logical_path: Annotated[str, Field(min_length=1, max_length=2000)]
    line_span: LineSpan | None = None
    byte_span: ByteSpan | None = None

    _relative_path = field_validator("logical_path")(validate_logical_path)

    @model_validator(mode="after")
    def require_position(self) -> "LocalFileCoordinates":
        if self.line_span is None and self.byte_span is None:
            raise ValueError("local-file locator requires line_span or byte_span")
        return self


class DatasetCoordinates(ContractModel):
    kind: Literal["dataset"] = "dataset"
    dataset: Annotated[str, Field(min_length=1, max_length=500)]
    version: Annotated[str, Field(min_length=1, max_length=160)]
    content_hash: HashDigest
    split: str | None = Field(default=None, min_length=1, max_length=160)
    row_key: str | None = Field(default=None, min_length=1, max_length=500)
    row_start: int | None = Field(default=None, ge=0)
    row_end: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def require_position(self) -> "DatasetCoordinates":
        has_range = self.row_start is not None or self.row_end is not None
        if self.row_key is None and not has_range:
            raise ValueError("dataset locator requires row_key or row range")
        if has_range:
            if self.row_start is None or self.row_end is None:
                raise ValueError("dataset row range requires both endpoints")
            if self.row_end < self.row_start:
                raise ValueError("row_end must be greater than or equal to row_start")
        return self


class RunOutputCoordinates(ContractModel):
    kind: Literal["run_output"] = "run_output"
    run_id: Identifier
    artifact_id: Identifier
    record_key: str | None = Field(default=None, min_length=1, max_length=500)
    line_span: LineSpan | None = None
    metric_key: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def require_position(self) -> "RunOutputCoordinates":
        if (
            self.record_key is None
            and self.line_span is None
            and self.metric_key is None
        ):
            raise ValueError(
                "run-output locator requires record_key, line_span, or metric_key"
            )
        return self


LocatorCoordinates = Annotated[
    Union[
        WebCoordinates,
        PdfCoordinates,
        RepoCoordinates,
        LocalFileCoordinates,
        DatasetCoordinates,
        RunOutputCoordinates,
    ],
    Field(discriminator="kind"),
]


LOCATOR_KINDS = frozenset(
    {"web", "pdf", "repo", "local_file", "dataset", "run_output"}
)
