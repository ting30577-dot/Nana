"""遗留刷题数据的无损 JSON 归档与完整性校验。"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from db.database import Database


SCHEMA_VERSION = "nana.legacy-problems.v1"
RECORD_FIELDS = (
    "id",
    "lc_number",
    "title",
    "difficulty",
    "pattern",
    "date_solved",
    "status",
    "notes",
    "created_at",
)


class LegacyArchiveError(ValueError):
    """归档内容缺失、损坏或不受当前版本支持。"""


@dataclass(frozen=True, slots=True)
class LegacyArchive:
    schema_version: str
    exported_at: str
    record_count: int
    records: tuple[dict[str, Any], ...]
    content_sha256: str


def _canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _content_digest(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _archive_content(
    records: Sequence[Mapping[str, Any]],
    *,
    exported_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "exported_at": exported_at,
        "record_count": len(records),
        "records": [dict(record) for record in records],
    }


def _validate_record(record: object, index: int) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise LegacyArchiveError(f"第 {index + 1} 条记录不是 JSON 对象。")
    if tuple(record.keys()) != RECORD_FIELDS:
        raise LegacyArchiveError(f"第 {index + 1} 条记录字段与归档规范不一致。")
    if not isinstance(record["id"], int) or not isinstance(record["lc_number"], int):
        raise LegacyArchiveError(f"第 {index + 1} 条记录的编号字段类型错误。")
    for field in RECORD_FIELDS[2:]:
        if not isinstance(record[field], str):
            raise LegacyArchiveError(
                f"第 {index + 1} 条记录的 {field} 字段类型错误。"
            )
    return record


def load_legacy_archive(path: str | Path) -> LegacyArchive:
    """读取并完整校验归档，返回可供迁移流程使用的只读快照。"""

    archive_path = Path(path)
    try:
        payload = json.loads(archive_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise LegacyArchiveError(f"无法读取遗留数据归档：{error}") from error

    if not isinstance(payload, dict):
        raise LegacyArchiveError("归档根节点必须是 JSON 对象。")

    expected_keys = {
        "schema_version",
        "exported_at",
        "record_count",
        "records",
        "content_sha256",
    }
    if set(payload) != expected_keys:
        raise LegacyArchiveError("归档顶层字段与当前规范不一致。")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise LegacyArchiveError("归档 schema_version 不受当前版本支持。")
    if not isinstance(payload["exported_at"], str):
        raise LegacyArchiveError("归档时间字段类型错误。")
    try:
        datetime.fromisoformat(payload["exported_at"].replace("Z", "+00:00"))
    except ValueError as error:
        raise LegacyArchiveError("归档时间不是有效的 ISO 8601 时间。") from error
    if not isinstance(payload["record_count"], int):
        raise LegacyArchiveError("归档记录数类型错误。")
    if not isinstance(payload["records"], list):
        raise LegacyArchiveError("归档 records 字段必须是数组。")

    records = tuple(
        _validate_record(record, index)
        for index, record in enumerate(payload["records"])
    )
    if payload["record_count"] != len(records):
        raise LegacyArchiveError("归档声明的记录数与实际记录数不一致。")

    content = {key: payload[key] for key in expected_keys if key != "content_sha256"}
    digest = _content_digest(content)
    if not isinstance(payload["content_sha256"], str) or not hmac.compare_digest(
        payload["content_sha256"], digest
    ):
        raise LegacyArchiveError("归档内容摘要校验失败，文件可能已损坏或被修改。")

    return LegacyArchive(
        schema_version=payload["schema_version"],
        exported_at=payload["exported_at"],
        record_count=payload["record_count"],
        records=records,
        content_sha256=payload["content_sha256"],
    )


def export_legacy_problems(
    database: Database,
    path: str | Path,
    *,
    overwrite: bool = False,
    exported_at: datetime | None = None,
) -> LegacyArchive:
    """原子写入遗留数据归档，并在成功返回前重新读取校验。"""

    archive_path = Path(path)
    if archive_path.exists() and not overwrite:
        raise FileExistsError(f"归档文件已存在：{archive_path}")

    records = [asdict(record) for record in database.list_problems(newest_first=False)]
    if database.total_count() != len(records):
        raise LegacyArchiveError("数据库记录数在归档期间发生变化，请重试。")

    timestamp = exported_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise ValueError("exported_at 必须包含时区信息。")
    exported_at_text = timestamp.astimezone(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    content = _archive_content(records, exported_at=exported_at_text)
    payload = {**content, "content_sha256": _content_digest(content)}

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{archive_path.name}.",
            suffix=".tmp",
            dir=archive_path.parent,
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if archive_path.exists() and not overwrite:
            raise FileExistsError(f"归档文件已存在：{archive_path}")
        os.replace(temporary_path, archive_path)
        temporary_path = None
        return load_legacy_archive(archive_path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
