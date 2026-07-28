"""v0.2.0-alpha 研究对象与 SQLite 关系测试。"""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from nana_core.research import (
    Claim,
    Evidence,
    Experiment,
    Insight,
    Method,
    ResearchRepository,
    Source,
)


class ResearchRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_directory.name) / "nana.db"
        self.repository = ResearchRepository(self.path)

    def tearDown(self) -> None:
        self.repository.close()
        self.temp_directory.cleanup()

    def test_complete_non_ai_research_thread_survives_reopen(self) -> None:
        thread = self.repository.create_thread(
            title="验证有序数组双指针",
            question="双指针为何不会错过目标解？",
            scope_exclusions="不讨论无序数组。",
            completion_criteria="实现并通过正常、边界和反例测试。",
            status="active",
            next_step="构造重复元素边界。",
        )
        source = self.repository.create_source(
            thread.id,
            source_type="case",
            title="两数之和 II",
            locator="LeetCode 167",
            version="2026-07-27",
            selection_reason="验证碰撞指针的不变量。",
            ai_permission="denied",
        )
        claim = self.repository.create_claim(
            thread.id,
            source.id,
            statement="当和偏小时移动左指针不会漏掉可行解。",
        )
        evidence = self.repository.create_evidence(
            thread.id,
            source.id,
            claim.id,
            locator="最小实现 collision_steps",
            evidence_type="experiment",
            content="[1,2,4,6,10] 中找到 2+6=8。",
            verification_status="verified",
        )
        method = self.repository.create_method(
            thread.id,
            name="有序数组碰撞指针",
            problem="在线性时间内寻找目标和。",
            mechanism="根据当前和与目标的关系单调排除一侧。",
            assumptions="输入非递减。",
            applicability="具有单调排除条件的区间搜索。",
            failure_boundaries="无序输入不能使用该排除逻辑。",
        )
        experiment = self.repository.create_experiment(
            thread.id,
            method.id,
            title="正常用例与无序反例",
            purpose="验证不变量及失败边界。",
            environment="Python 3.11+",
            inputs="[1,2,4,6,10], target=8; [3,1,2], target=4",
            result="正常用例命中；无序输入被拒绝。",
            limitations="尚未覆盖整数溢出语言。",
        )
        insight = self.repository.create_insight(
            thread.id,
            method.id,
            statement="关键资产是单调排除证明，而不是题目完成记录。",
            confidence="high",
            next_action="验证三数之和中的迁移边界。",
        )
        self.repository.close()

        reopened = ResearchRepository(self.path)
        self.addCleanup(reopened.close)

        self.assertEqual(reopened.get_thread(thread.id), thread)
        self.assertEqual(reopened.list_for_thread(Source, thread.id), [source])
        self.assertEqual(reopened.list_for_thread(Claim, thread.id), [claim])
        self.assertEqual(reopened.list_for_thread(Evidence, thread.id), [evidence])
        self.assertEqual(reopened.list_for_thread(Method, thread.id), [method])
        self.assertEqual(
            reopened.list_for_thread(Experiment, thread.id), [experiment]
        )
        self.assertEqual(reopened.list_for_thread(Insight, thread.id), [insight])

    def test_cross_thread_relationships_are_rejected(self) -> None:
        first = self.repository.create_thread(title="线程一", question="问题一")
        second = self.repository.create_thread(title="线程二", question="问题二")
        source = self.repository.create_source(
            first.id,
            source_type="paper",
            title="来源",
            locator="本地文件",
        )
        method = self.repository.create_method(
            first.id,
            name="方法",
            problem="问题",
            mechanism="机制",
        )

        with self.assertRaisesRegex(ValueError, "线程不一致"):
            self.repository.create_claim(
                second.id, source.id, statement="错误跨线程主张"
            )
        with self.assertRaisesRegex(ValueError, "线程不一致"):
            self.repository.create_experiment(
                second.id,
                method.id,
                title="错误实验",
                purpose="验证关系约束",
            )

    def test_evidence_must_use_claim_source(self) -> None:
        thread = self.repository.create_thread(title="线程", question="问题")
        first = self.repository.create_source(
            thread.id, source_type="code", title="来源一", locator="a.py"
        )
        second = self.repository.create_source(
            thread.id, source_type="code", title="来源二", locator="b.py"
        )
        claim = self.repository.create_claim(
            thread.id, first.id, statement="来自来源一"
        )

        with self.assertRaisesRegex(ValueError, "证据来源"):
            self.repository.create_evidence(
                thread.id,
                second.id,
                claim.id,
                locator="b.py:1",
                evidence_type="code",
                content="不属于主张来源",
            )

    def test_required_fields_and_enums_are_validated(self) -> None:
        with self.assertRaisesRegex(ValueError, "研究问题不能为空"):
            self.repository.create_thread(title="标题", question=" ")
        thread = self.repository.create_thread(title="标题", question="问题")
        with self.assertRaisesRegex(ValueError, "来源类型"):
            self.repository.create_source(
                thread.id,
                source_type="pdf-manager",
                title="错误类型",
                locator="x",
            )
        with self.assertRaisesRegex(ValueError, "置信度"):
            method = self.repository.create_method(
                thread.id, name="方法", problem="问题", mechanism="机制"
            )
            self.repository.create_insight(
                thread.id,
                method.id,
                statement="判断",
                confidence="certain",
            )

    def test_thread_status_update_is_persisted(self) -> None:
        thread = self.repository.create_thread(
            title="待完成线程",
            question="何时可以完成？",
            status="active",
            next_step="运行实验",
        )

        updated = self.repository.update_thread_status(
            thread.id, "completed", next_step=""
        )

        self.assertEqual(updated.status, "completed")
        self.assertEqual(updated.next_step, "")
        self.assertEqual(self.repository.get_thread(thread.id), updated)
        with self.assertRaisesRegex(ValueError, "线程状态"):
            self.repository.update_thread_status(thread.id, "done")

    def test_database_restricts_deleting_thread_with_research_assets(self) -> None:
        thread = self.repository.create_thread(title="线程", question="问题")
        self.repository.create_source(
            thread.id, source_type="case", title="案例", locator="case:1"
        )

        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "DELETE FROM research_threads WHERE id = ?", (thread.id,)
                )

        self.assertIsNotNone(self.repository.get_thread(thread.id))

    def test_legacy_problem_table_can_coexist_in_same_database(self) -> None:
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute(
                "CREATE TABLE problems (id INTEGER PRIMARY KEY, title TEXT NOT NULL)"
            )
            connection.execute("INSERT INTO problems(title) VALUES ('保留记录')")
            connection.commit()

        reopened = ResearchRepository(self.path)
        reopened.close()

        with closing(sqlite3.connect(self.path)) as connection:
            row = connection.execute("SELECT title FROM problems").fetchone()
        self.assertEqual(row[0], "保留记录")

    def test_version_one_source_table_is_migrated_without_data_loss(self) -> None:
        legacy_path = Path(self.temp_directory.name) / "schema-v1.db"
        with closing(sqlite3.connect(legacy_path)) as connection:
            connection.executescript(
                """
                CREATE TABLE nana_schema_versions (
                    component TEXT PRIMARY KEY, version INTEGER NOT NULL
                );
                INSERT INTO nana_schema_versions VALUES ('research', 1);
                CREATE TABLE research_threads (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, question TEXT NOT NULL,
                    scope_exclusions TEXT NOT NULL, completion_criteria TEXT NOT NULL,
                    status TEXT NOT NULL, next_step TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE research_sources (
                    id TEXT PRIMARY KEY, thread_id TEXT NOT NULL,
                    source_type TEXT NOT NULL, title TEXT NOT NULL,
                    locator TEXT NOT NULL, version TEXT NOT NULL,
                    selection_reason TEXT NOT NULL, ai_permission TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                INSERT INTO research_threads VALUES (
                    't1','旧线程','旧问题','','','active','','now','now'
                );
                INSERT INTO research_sources VALUES (
                    's1','t1','case','旧来源','case:1','','','undecided','now'
                );
                """
            )
            connection.commit()

        migrated = ResearchRepository(legacy_path)
        self.addCleanup(migrated.close)
        source = migrated.list_for_thread(Source, "t1")[0]

        self.assertEqual(source.title, "旧来源")
        self.assertIsNone(source.legacy_record_id)
        self.assertEqual(source.legacy_metadata, "")


if __name__ == "__main__":
    unittest.main()
