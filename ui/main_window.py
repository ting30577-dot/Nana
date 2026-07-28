"""Nana 主窗口。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QWidget,
)

from db.database import Database
from nana_core.research import ResearchRepository
from ui.legacy_migration_page import LegacyMigrationPage
from ui.method_lab_page import MethodLabPage
from ui.research_page import ResearchPage
from ui.sidebar import Sidebar
from ui.theme import APP_STYLESHEET


class MainWindow(QMainWindow):
    def __init__(
        self,
        database: Database | None = None,
        research_repository: ResearchRepository | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("Nana")
        self.resize(1280, 800)
        self.setMinimumSize(900, 600)

        self.database = database or Database()
        self.research_repository = research_repository or ResearchRepository(
            self.database.path
        )
        self.sidebar = Sidebar()
        self.research_page = ResearchPage(self.research_repository)
        self.legacy_migration_page = LegacyMigrationPage(
            self.database, self.research_repository
        )
        self.method_lab_page = MethodLabPage(self.research_repository)
        self.pages = QStackedWidget()
        self.pages.addWidget(self.research_page)
        self.pages.addWidget(self.legacy_migration_page)
        self.pages.addWidget(self.method_lab_page)
        self._active_navigation = 0
        self.sidebar.navigation_requested.connect(self._handle_navigation)

        container = QWidget()
        container.setObjectName("appRoot")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.pages, 1)
        self.setCentralWidget(container)

        self.setStyleSheet(APP_STYLESHEET)

    def _handle_navigation(self, index: int, name: str) -> None:
        if index == 0:
            self.research_page.refresh()
            self.pages.setCurrentWidget(self.research_page)
            self._active_navigation = index
            return
        if index == 1:
            self.legacy_migration_page.refresh()
            self.pages.setCurrentWidget(self.legacy_migration_page)
            self._active_navigation = index
            return
        if index == 2:
            self.method_lab_page.refresh()
            self.pages.setCurrentWidget(self.method_lab_page)
            self._active_navigation = index
            return
        self.sidebar.select_item(self._active_navigation)
        QMessageBox.information(
            self,
            "Coming soon",
            f"{name}模块将在后续版本开放。",
        )

    def closeEvent(self, event: object) -> None:
        self.research_repository.close()
        self.database.close()
        super().closeEvent(event)
