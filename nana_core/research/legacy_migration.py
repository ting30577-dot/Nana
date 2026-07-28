"""将用户明确选择的遗留记录迁移为 case Source。"""

from __future__ import annotations

import json
from dataclasses import asdict

from db.database import Database
from nana_core.research.models import Source
from nana_core.research.repository import ResearchRepository


def migrate_legacy_records(
    database: Database,
    repository: ResearchRepository,
    thread_id: str,
    record_ids: list[int],
) -> list[Source]:
    """只迁移明确选择的记录；重复迁移会被拒绝且原表保持不变。"""

    if not record_ids:
        raise ValueError("请至少选择一条有研究价值的遗留记录。")
    if len(record_ids) != len(set(record_ids)):
        raise ValueError("迁移列表中包含重复记录。")

    records_by_id = {record.id: record for record in database.list_problems()}
    missing = [record_id for record_id in record_ids if record_id not in records_by_id]
    if missing:
        raise KeyError(f"遗留记录不存在：{missing}")
    duplicates = [
        record_id
        for record_id in record_ids
        if repository.get_source_by_legacy_record(record_id) is not None
    ]
    if duplicates:
        raise ValueError(f"遗留记录已经迁移：{duplicates}")

    migrated: list[Source] = []
    for record_id in record_ids:
        record = records_by_id[record_id]
        metadata = json.dumps(
            asdict(record),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        migrated.append(
            repository.create_source(
                thread_id,
                source_type="case",
                title=f"LeetCode #{record.lc_number} · {record.title}",
                locator=f"leetcode:{record.lc_number}",
                version=record.date_solved,
                selection_reason="由用户从遗留刷题记录中选择，作为研究案例保留。",
                ai_permission="undecided",
                legacy_record_id=record.id,
                legacy_metadata=metadata,
            )
        )
    return migrated
