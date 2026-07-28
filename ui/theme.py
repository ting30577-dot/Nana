"""Nana 的暖色浅色主题。

界面颜色集中在这里，避免各页面继续硬编码深蓝、深紫色板。
算法状态仍可使用高辨识度颜色，但大面积背景保持温暖、轻盈。
"""

from __future__ import annotations

BACKGROUND = "#F6F0E7"
SURFACE = "#FFFCF7"
SURFACE_ALT = "#EFE3D5"
SURFACE_HOVER = "#E7D8C8"
BORDER = "#D8C5B2"

TEXT_PRIMARY = "#3D302B"
TEXT_SECONDARY = "#77675F"
TEXT_ON_ACCENT = "#FFFDF9"

ACCENT = "#9A7BB8"
ACCENT_STRONG = "#765A96"
ACCENT_SOFT = "#E8DDF0"

SUCCESS = "#789878"
SUCCESS_SOFT = "#DCE9DB"
WARNING = "#D39A49"
DANGER = "#C56F5D"
DANGER_SOFT = "#F3DDD7"
INFO = "#6F91A1"

CODE_KEYWORD = "#805A9B"
CODE_COMMENT = "#95857B"
GRID = "#DED1C4"
INACTIVE = "#C9BAAC"

PALETTE = {
    "app_bg": BACKGROUND,
    "surface": SURFACE,
    "surface_alt": SURFACE_ALT,
    "surface_strong": SURFACE_HOVER,
    "border": BORDER,
    "border_strong": "#C5AD98",
    "text": TEXT_PRIMARY,
    "text_soft": "#5F514B",
    "muted": TEXT_SECONDARY,
    "subtle": "#9E8F84",
    "primary": ACCENT,
    "primary_strong": ACCENT_STRONG,
    "primary_soft": ACCENT_SOFT,
    "success": SUCCESS,
    "danger": DANGER,
    "warning": WARNING,
    "info": INFO,
    "on_accent": TEXT_ON_ACCENT,
    "neutral_bar": INACTIVE,
}


def application_stylesheet() -> str:
    """返回应用全局 Qt 样式表。"""

    return f"""
        QMainWindow, QWidget#appRoot {{
            background: {BACKGROUND};
            color: {TEXT_PRIMARY};
            font-family: "Microsoft YaHei", "Microsoft YaHei UI", "Segoe UI";
        }}
        QFrame#infoCard, QFrame#codeCard {{
            background: {SURFACE};
            border: 1px solid {BORDER};
            border-radius: 9px;
        }}
        QFrame#codeCard QTextEdit {{
            background: transparent;
            border: 0;
            padding: 0 4px 4px 4px;
        }}
        QLabel {{
            color: {TEXT_PRIMARY};
            background: transparent;
        }}
        QLabel#pageTitle {{
            color: {TEXT_PRIMARY};
            font-size: 23px;
            font-weight: 700;
        }}
        QLabel#mutedText {{
            color: {TEXT_SECONDARY};
            font-size: 13px;
        }}
        QLabel#cardLabel {{
            color: {TEXT_SECONDARY};
            font-size: 11px;
        }}
        QLabel#cardValue {{
            color: {TEXT_PRIMARY};
            font-size: 14px;
            font-weight: 600;
        }}
        QLabel#codeSectionLabel {{
            color: {TEXT_PRIMARY};
            font-size: 14px;
            font-weight: 600;
        }}
        QLabel#statValue {{
            color: {TEXT_PRIMARY};
            font-size: 22px;
            font-weight: 700;
        }}
        QTreeWidget {{
            background: {SURFACE_ALT};
            border: 0;
            color: {TEXT_PRIMARY};
            font-size: 13px;
            outline: 0;
        }}
        QListWidget {{
            background: {SURFACE};
            border: 1px solid {BORDER};
            border-radius: 8px;
            color: {TEXT_PRIMARY};
            outline: 0;
            padding: 5px;
        }}
        QListWidget::item {{
            min-height: 38px;
            padding: 4px 8px;
            border-radius: 6px;
        }}
        QListWidget::item:hover {{
            background: {SURFACE_HOVER};
        }}
        QListWidget::item:selected {{
            background: {ACCENT_SOFT};
            color: {ACCENT_STRONG};
        }}
        QTreeWidget::item {{
            height: 32px;
            padding-left: 5px;
        }}
        QTreeWidget::item:hover {{
            background: {SURFACE_HOVER};
        }}
        QTreeWidget::item:selected {{
            background: {ACCENT_SOFT};
            color: {ACCENT_STRONG};
            border-left: 3px solid {ACCENT};
        }}
        QTextEdit {{
            background: {SURFACE};
            border: 1px solid {BORDER};
            border-radius: 8px;
            color: {TEXT_PRIMARY};
            padding: 12px;
            selection-background-color: {ACCENT_SOFT};
        }}
        QPushButton {{
            background: {SURFACE};
            border: 1px solid {BORDER};
            border-radius: 7px;
            color: {TEXT_PRIMARY};
            min-height: 30px;
            padding: 0 12px;
        }}
        QPushButton:hover {{
            background: {ACCENT_SOFT};
            border-color: {ACCENT};
        }}
        QPushButton:pressed {{
            background: {ACCENT};
            color: {TEXT_ON_ACCENT};
        }}
        QPushButton#dangerButton:hover {{
            background: {DANGER_SOFT};
            border-color: {DANGER};
            color: {DANGER};
        }}
        QLineEdit, QSpinBox, QDateEdit, QComboBox {{
            min-height: 30px;
            padding: 0 8px;
            color: {TEXT_PRIMARY};
            background: {SURFACE};
            border: 1px solid {BORDER};
            border-radius: 7px;
            selection-background-color: {ACCENT_SOFT};
        }}
        QComboBox::drop-down {{
            border: 0;
            width: 24px;
        }}
        QComboBox QAbstractItemView {{
            color: {TEXT_PRIMARY};
            background: {SURFACE};
            border: 1px solid {BORDER};
            selection-background-color: {ACCENT_SOFT};
            selection-color: {ACCENT_STRONG};
        }}
        QTableWidget {{
            color: {TEXT_PRIMARY};
            background: {SURFACE};
            alternate-background-color: {BACKGROUND};
            border: 1px solid {BORDER};
            border-radius: 8px;
            gridline-color: {GRID};
            selection-background-color: {ACCENT_SOFT};
            selection-color: {TEXT_PRIMARY};
        }}
        QTableWidget::item {{
            padding: 6px;
        }}
        QHeaderView::section {{
            color: {TEXT_SECONDARY};
            background: {SURFACE_ALT};
            border: 0;
            border-bottom: 1px solid {BORDER};
            padding: 7px;
            font-weight: 600;
        }}
        QSlider::groove:horizontal {{
            height: 4px;
            background: {BORDER};
            border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            width: 14px;
            margin: -5px 0;
            background: {ACCENT};
            border-radius: 7px;
        }}
    """


def sidebar_stylesheet() -> str:
    """返回侧边栏样式。"""

    return f"""
        Sidebar {{
            background: {SURFACE_ALT};
            border-right: 1px solid {BORDER};
        }}
        QPushButton {{
            min-width: 42px;
            max-width: 42px;
            min-height: 42px;
            max-height: 42px;
            padding: 0;
            border: 0;
            border-radius: 9px;
            color: {TEXT_SECONDARY};
            background: transparent;
            font-size: 15px;
            font-weight: 700;
        }}
        QPushButton:hover {{
            color: {ACCENT_STRONG};
            background: {ACCENT_SOFT};
        }}
        QPushButton:checked {{
            color: {TEXT_ON_ACCENT};
            background: {ACCENT};
        }}
    """


APP_STYLESHEET = application_stylesheet()
SIDEBAR_STYLESHEET = sidebar_stylesheet()
DIALOG_STYLESHEET = f"""
    QDialog {{
        background: {BACKGROUND};
        color: {TEXT_PRIMARY};
    }}
    QDialog QLabel {{
        color: {TEXT_SECONDARY};
    }}
"""
