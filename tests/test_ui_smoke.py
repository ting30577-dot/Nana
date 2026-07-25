"""PySide6 界面的无窗口冒烟测试。"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from main import configure_application  # noqa: E402
from ui.algo_workspace import FIXED_INFO, VARIABLE_INFO  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402


class MainWindowSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        configure_application(cls.app)

    def setUp(self) -> None:
        self.window = MainWindow()

    def tearDown(self) -> None:
        self.window.close()
        self.app.processEvents()

    def test_main_window_and_sidebar_dimensions(self) -> None:
        self.assertEqual(self.window.windowTitle(), "AlgoMind")
        self.assertEqual(self.window.minimumWidth(), 900)
        self.assertEqual(self.window.minimumHeight(), 600)
        self.assertEqual(self.window.sidebar.width(), 60)

    def test_pattern_switch_updates_code_canvas_and_links(self) -> None:
        tree = self.window.workspace.pattern_tree
        root = tree.topLevelItem(0)
        self.assertEqual(root.childCount(), 2)
        self.assertIs(self.window.workspace._pattern, FIXED_INFO)

        self.window.workspace._pattern_clicked(root.child(1), 0)

        self.assertIs(self.window.workspace._pattern, VARIABLE_INFO)
        self.assertEqual(self.window.workspace.canvas._mode, "variable")
        self.assertIn("LeetCode #239", self.window.workspace.links_label.text())

    def test_animation_controls_and_speed(self) -> None:
        canvas = self.window.workspace.canvas

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

    def test_unavailable_navigation_shows_coming_soon(self) -> None:
        with patch("ui.main_window.QMessageBox.information") as information:
            self.window._handle_navigation(1, "论文")
        information.assert_called_once()


if __name__ == "__main__":
    unittest.main()

