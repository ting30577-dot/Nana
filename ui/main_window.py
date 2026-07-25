"""Main application window."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.algo_workspace import AlgorithmWorkspace
from ui.sidebar import Sidebar


class PlaceholderPage(QWidget):
    def __init__(self, title: str, description: str) -> None:
        super().__init__()

        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")
        description_label = QLabel(description)
        description_label.setObjectName("mutedText")
        description_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.addWidget(title_label)
        layout.addWidget(description_label)
        layout.addStretch()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AlgoMind · AI/CS 学习工作台")
        self.resize(1280, 800)
        self.setMinimumSize(1024, 640)

        self.sidebar = Sidebar()
        self.pages = QStackedWidget()
        self.pages.addWidget(AlgorithmWorkspace())
        self.pages.addWidget(
            PlaceholderPage("论文库", "论文阅读、标注和结构化笔记将在 v0.3 实现。")
        )
        self.pages.addWidget(
            PlaceholderPage("刷题追踪", "LeetCode 记录与模式统计将在 v0.2 实现。")
        )
        self.pages.addWidget(
            PlaceholderPage("知识图谱", "算法模式与论文知识点的连接将在后续版本实现。")
        )
        self.pages.addWidget(
            PlaceholderPage("设置", "主题、数据目录和快捷键设置将在后续版本实现。")
        )
        self.sidebar.page_selected.connect(self.pages.setCurrentIndex)

        content = QWidget()
        layout = QHBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.pages, 1)
        self.setCentralWidget(content)

        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #11151c;
                color: #e6edf3;
                font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
            }
            QLabel#pageTitle {
                font-size: 28px;
                font-weight: 700;
                color: #f0f6fc;
            }
            QLabel#mutedText {
                color: #8b949e;
                font-size: 14px;
            }
            QFrame#panel {
                background: #161b22;
                border: 1px solid #30363d;
                border-radius: 10px;
            }
            QPushButton {
                background: #21262d;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 7px 12px;
                color: #e6edf3;
            }
            QPushButton:hover {
                background: #30363d;
            }
            QPushButton:pressed {
                background: #388bfd;
            }
            QTreeWidget, QPlainTextEdit {
                background: #0d1117;
                border: 1px solid #30363d;
                border-radius: 8px;
                color: #c9d1d9;
            }
            QSlider::groove:horizontal {
                height: 4px;
                background: #30363d;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                width: 14px;
                margin: -5px 0;
                background: #58a6ff;
                border-radius: 7px;
            }
            """
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

