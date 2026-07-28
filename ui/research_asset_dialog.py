"""线程内研究资产的紧凑创建对话框。"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.theme import DIALOG_STYLESHEET


@dataclass(frozen=True, slots=True)
class FieldSpec:
    key: str
    label: str
    required: bool = False
    choices: tuple[tuple[str, str], ...] = ()
    multiline: bool = False
    placeholder: str = ""


class ResearchAssetDialog(QDialog):
    def __init__(
        self,
        title: str,
        fields: tuple[FieldSpec, ...],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(520)
        self.setStyleSheet(DIALOG_STYLESHEET)
        self._fields = fields
        self.inputs: dict[str, QLineEdit | QTextEdit | QComboBox] = {}

        form = QFormLayout()
        form.setSpacing(10)
        for field in fields:
            if field.choices:
                widget = QComboBox()
                for label, value in field.choices:
                    widget.addItem(label, value)
            elif field.multiline:
                widget = QTextEdit()
                widget.setMaximumHeight(90)
                widget.setPlaceholderText(field.placeholder)
            else:
                widget = QLineEdit()
                widget.setPlaceholderText(field.placeholder)
            self.inputs[field.key] = widget
            form.addRow(field.label, widget)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("保存")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _value(self, field: FieldSpec) -> str:
        widget = self.inputs[field.key]
        if isinstance(widget, QComboBox):
            return str(widget.currentData())
        if isinstance(widget, QTextEdit):
            return widget.toPlainText().strip()
        return widget.text().strip()

    def _accept_if_valid(self) -> None:
        for field in self._fields:
            if field.required and not self._value(field):
                QMessageBox.warning(self, "无法保存", f"请填写{field.label}。")
                self.inputs[field.key].setFocus()
                return
        self.accept()

    def values(self) -> dict[str, str]:
        return {field.key: self._value(field) for field in self._fields}
