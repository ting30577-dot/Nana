"""Nana desktop application entry point."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow


def configure_application(app: QApplication) -> None:
    """加载 Windows 中文字体，避免 Qt 在精简环境中显示方框。"""

    font_paths = (
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\msyhbd.ttc"),
    )
    loaded_families: list[str] = []
    for font_path in font_paths:
        if not font_path.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id >= 0:
            loaded_families.extend(QFontDatabase.applicationFontFamilies(font_id))

    if loaded_families:
        app.setFont(QFont(loaded_families[0], 10))


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Nana")
    app.setOrganizationName("Nana")
    app.setApplicationVersion("0.2.0-alpha")
    configure_application(app)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
