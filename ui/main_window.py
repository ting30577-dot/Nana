"""AlgoMind 主窗口。"""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QMessageBox, QWidget, QHBoxLayout

from ui.algo_workspace import AlgorithmWorkspace
from ui.sidebar import Sidebar


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AlgoMind")
        self.resize(1280, 800)
        self.setMinimumSize(900, 600)

        self.sidebar = Sidebar()
        self.workspace = AlgorithmWorkspace()
        self.sidebar.navigation_requested.connect(self._handle_navigation)

        container = QWidget()
        container.setObjectName("appRoot")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.workspace, 1)
        self.setCentralWidget(container)

        self.setStyleSheet(
            """
            QMainWindow, QWidget#appRoot {
                background: #0f1117;
                color: #f9fafb;
                font-family: "Microsoft YaHei", "Microsoft YaHei UI", "Segoe UI";
            }
            QFrame#infoCard {
                background: #14172a;
                border: 1px solid #282c43;
                border-radius: 8px;
            }
            QLabel {
                color: #f9fafb;
                background: transparent;
            }
            QLabel#pageTitle {
                color: #f9fafb;
                font-size: 23px;
                font-weight: 700;
            }
            QLabel#mutedText {
                color: #9ca3af;
                font-size: 13px;
            }
            QLabel#cardLabel {
                color: #9ca3af;
                font-size: 11px;
            }
            QLabel#cardValue {
                color: #f9fafb;
                font-size: 14px;
                font-weight: 600;
            }
            QTreeWidget {
                background: #14172a;
                border: 0;
                color: #d1d5db;
                font-size: 13px;
                outline: 0;
            }
            QTreeWidget::item {
                height: 32px;
                padding-left: 5px;
            }
            QTreeWidget::item:hover {
                background: #242943;
            }
            QTreeWidget::item:selected {
                background: #30356b;
                color: #f9fafb;
                border-left: 2px solid #6366f1;
            }
            QTextEdit {
                background: #14172a;
                border: 1px solid #282c43;
                border-radius: 8px;
                color: #d1d5db;
                padding: 12px;
                selection-background-color: #30356b;
            }
            QPushButton {
                background: #1d2132;
                border: 1px solid #343957;
                border-radius: 6px;
                color: #f9fafb;
                min-height: 30px;
                padding: 0 12px;
            }
            QPushButton:hover {
                background: #2c3150;
                border-color: #6366f1;
            }
            QPushButton:pressed {
                background: #6366f1;
            }
            QSlider::groove:horizontal {
                height: 4px;
                background: #374151;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                width: 14px;
                margin: -5px 0;
                background: #6366f1;
                border-radius: 7px;
            }
            """
        )

    def _handle_navigation(self, index: int, name: str) -> None:
        if index == 0:
            return
        self.sidebar.keep_algorithm_selected()
        QMessageBox.information(
            self,
            "Coming soon",
            f"{name}模块将在后续版本开放。",
        )
