"""迁移期遗留界面、动画控制和导航的无窗口冒烟测试。"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from db.database import Database  # noqa: E402
from nana_core.research import (  # noqa: E402
    Claim,
    Evidence,
    Experiment,
    Insight,
    Method,
    ResearchRepository,
    Source,
)
from main import configure_application  # noqa: E402
from ui.algo_workspace import (  # noqa: E402
    AlgorithmWorkspace,
    FIXED_INFO,
    PATTERNS,
    SUPPORTED_LANGUAGES,
    VARIABLE_INFO,
)
from ui.main_window import MainWindow  # noqa: E402
from ui.research_page import ResearchThreadFormData  # noqa: E402


class MainWindowSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        configure_application(cls.app)

    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        database = Database(Path(self.temp_directory.name) / "test.db")
        repository = ResearchRepository(database.path)
        self.window = MainWindow(database, repository)

    def tearDown(self) -> None:
        self.window.close()
        self.app.processEvents()
        self.temp_directory.cleanup()

    def test_main_window_and_sidebar_dimensions(self) -> None:
        self.assertEqual(self.window.windowTitle(), "Nana")
        self.assertEqual(self.window.minimumWidth(), 900)
        self.assertEqual(self.window.minimumHeight(), 600)
        self.assertEqual(self.window.sidebar.width(), 60)
        self.assertIs(
            self.window.pages.currentWidget(),
            self.window.research_page,
        )

    def test_pattern_switch_updates_code_canvas_and_links(self) -> None:
        workspace = AlgorithmWorkspace()
        self.addCleanup(workspace.close)
        tree = workspace.pattern_tree
        root = tree.topLevelItem(0)
        self.assertEqual(root.childCount(), 2)
        self.assertIs(workspace._pattern, FIXED_INFO)

        workspace._pattern_clicked(root.child(1), 0)

        self.assertIs(workspace._pattern, VARIABLE_INFO)
        self.assertEqual(workspace.canvas._mode, "variable")
        self.assertIn("LeetCode #239", workspace.links_label.text())

    def test_language_selection_is_scoped_to_each_pattern(self) -> None:
        workspace = AlgorithmWorkspace()
        self.addCleanup(workspace.close)

        self.assertEqual(workspace.language_combo.currentText(), "C")
        workspace.language_combo.setCurrentText("C++")
        self.assertIn("vector<int>", workspace.code_view.toPlainText())

        variable_item = workspace.pattern_tree.topLevelItem(0).child(1)
        workspace._pattern_clicked(variable_item, 0)
        self.assertEqual(workspace.language_combo.currentText(), "C")
        self.assertNotIn("vector<int>", workspace.code_view.toPlainText())

        fixed_item = workspace.pattern_tree.topLevelItem(0).child(0)
        workspace._pattern_clicked(fixed_item, 0)
        self.assertEqual(workspace.language_combo.currentText(), "C++")
        self.assertIn("vector<int>", workspace.code_view.toPlainText())

    def test_each_pattern_has_all_supported_code_languages(self) -> None:
        for pattern in PATTERNS.values():
            for language in SUPPORTED_LANGUAGES:
                with self.subTest(pattern=pattern.key, language=language):
                    self.assertTrue(pattern.code_for(language).strip())

    def test_animation_controls_and_speed(self) -> None:
        workspace = AlgorithmWorkspace()
        self.addCleanup(workspace.close)
        canvas = workspace.canvas

        canvas.set_speed(10)
        self.assertEqual(canvas._timer.interval(), 100)
        canvas.start()
        self.assertTrue(canvas._timer.isActive())
        canvas.pause()
        self.assertFalse(canvas._timer.isActive())
        canvas.reset()
        self.assertEqual(canvas._index, -1)
        canvas.step_once()
        self.assertEqual(canvas._index, 0)

    def test_every_animation_mode_renders_first_and_last_frames(self) -> None:
        workspace = AlgorithmWorkspace()
        self.addCleanup(workspace.close)
        canvas = workspace.canvas

        for mode in canvas._factories:
            with self.subTest(mode=mode):
                canvas.set_mode(mode)
                canvas.step_once()
                canvas.draw()
                while canvas._index < len(canvas._states) - 1:
                    canvas.step_once()
                canvas.draw()

    def test_unavailable_navigation_shows_coming_soon(self) -> None:
        with patch("ui.main_window.QMessageBox.information") as information:
            self.window._handle_navigation(3, "设置")
        information.assert_called_once()

    def test_research_navigation_opens_real_page(self) -> None:
        self.window._handle_navigation(0, "研究")

        self.assertIs(
            self.window.pages.currentWidget(),
            self.window.research_page,
        )

    def test_research_thread_creation_is_persisted_and_selected(self) -> None:
        page = self.window.research_page
        thread = page.create_thread(
            ResearchThreadFormData(
                title="验证滑动窗口边界",
                question="变量窗口为何需要非负输入？",
                scope_exclusions="不讨论含负数的替代算法。",
                completion_criteria="正常用例和负数反例均有证据。",
                next_step="运行最小反例。",
            )
        )

        self.assertEqual(page.thread_list.count(), 1)
        self.assertEqual(page.detail_title.text(), thread.title)
        self.assertEqual(
            self.window.research_repository.get_thread(thread.id),
            thread,
        )

    def test_complete_research_assets_appear_in_thread_and_method_lab(self) -> None:
        repository = self.window.research_repository
        thread = repository.create_thread(title="二分边界", question="左边界如何收敛？")
        source = repository.create_source(
            thread.id,
            source_type="case",
            title="重复元素案例",
            locator="case:binary-left",
        )
        claim = repository.create_claim(
            thread.id, source.id, statement="收缩右端可以保留最左候选。"
        )
        repository.create_evidence(
            thread.id,
            source.id,
            claim.id,
            locator="binary_search_left_steps",
            evidence_type="experiment",
            content="[1,3,3,5] 返回索引 1。",
            verification_status="verified",
        )
        method = repository.create_method(
            thread.id,
            name="二分左边界",
            problem="定位第一个目标值。",
            mechanism="命中后继续收缩右边界。",
            failure_boundaries="输入必须非递减。",
        )
        repository.create_experiment(
            thread.id,
            method.id,
            title="重复元素验证",
            purpose="验证最左候选不会丢失。",
            result="返回 1。",
        )
        repository.create_insight(
            thread.id,
            method.id,
            statement="循环不变量比模板记忆更可迁移。",
            confidence="high",
        )

        self.window.research_page.refresh(select_id=thread.id)
        self.assertEqual(self.window.research_page.asset_list.count(), 6)
        self.window.method_lab_page.refresh()
        self.assertEqual(self.window.method_lab_page.method_list.count(), 1)
        self.assertEqual(self.window.method_lab_page.experiments.count(), 1)
        self.window.method_lab_page.array_input.setText("[1, 2, 4, 6, 10]")
        self.window.method_lab_page.target_input.setText("8")
        self.window.method_lab_page.run_collision_experiment()
        self.assertIn("命中", self.window.method_lab_page.run_result.text())
        self.assertEqual(self.window.method_lab_page.experiments.count(), 2)
        self.assertEqual(repository.list_for_thread(Source, thread.id), [source])
        self.assertEqual(repository.list_for_thread(Claim, thread.id), [claim])
        self.assertEqual(len(repository.list_for_thread(Evidence, thread.id)), 1)
        self.assertEqual(repository.list_for_thread(Method, thread.id), [method])
        self.assertEqual(len(repository.list_for_thread(Experiment, thread.id)), 2)
        self.assertEqual(len(repository.list_for_thread(Insight, thread.id)), 1)

        with patch(
            "ui.research_page.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            self.window.research_page.complete_current_thread()
        self.assertEqual(repository.get_thread(thread.id).status, "completed")

    def test_method_lab_records_unsorted_input_as_failure_boundary(self) -> None:
        repository = self.window.research_repository
        thread = repository.create_thread(title="反例线程", question="何时不能用双指针？")
        method = repository.create_method(
            thread.id,
            name="碰撞指针",
            problem="目标和",
            mechanism="单调排除",
        )
        self.window.method_lab_page.refresh()
        self.window.method_lab_page.array_input.setText("[3, 1, 2]")
        self.window.method_lab_page.target_input.setText("4")

        self.window.method_lab_page.run_collision_experiment()

        experiments = repository.list_for_thread(Experiment, thread.id)
        self.assertEqual(len(experiments), 1)
        self.assertEqual(experiments[0].method_id, method.id)
        self.assertIn("边界检查拒绝", experiments[0].result)
        self.assertIn("非递减数组", experiments[0].limitations)

    def test_legacy_migration_navigation_opens_read_only_page(self) -> None:
        self.window._handle_navigation(1, "数据迁移")

        self.assertIs(
            self.window.pages.currentWidget(),
            self.window.legacy_migration_page,
        )

    def test_method_lab_navigation_opens_real_page(self) -> None:
        self.window._handle_navigation(2, "方法实验室")

        self.assertIs(
            self.window.pages.currentWidget(),
            self.window.method_lab_page,
        )


if __name__ == "__main__":
    unittest.main()
