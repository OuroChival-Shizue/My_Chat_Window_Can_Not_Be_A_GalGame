# gui/widgets/color_button.py
"""颜色选择器按钮"""
from typing import List

from PyQt6.QtWidgets import QPushButton, QColorDialog
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor


class ColorButton(QPushButton):
    """点击弹出颜色选择器的按钮"""
    
    colorChanged = pyqtSignal(list)

    def __init__(self, color: List[int]):
        super().__init__()
        self.setFixedSize(60, 25)
        self.current_color = color
        self._update_style()
        self.clicked.connect(self._pick_color)

    def _update_style(self):
        c = self.current_color
        css = f"background-color: rgb({c[0]}, {c[1]}, {c[2]}); border: 1px solid #888; border-radius: 4px;"
        self.setStyleSheet(css)

    def set_color(self, color: List[int]):
        self.current_color = color
        self._update_style()

    def _pick_color(self):
        c = self.current_color
        initial = QColor(c[0], c[1], c[2])
        new_color = QColorDialog.getColor(initial, self, "选择颜色")
        if new_color.isValid():
            rgb = [new_color.red(), new_color.green(), new_color.blue()]
            self.set_color(rgb)
            self.colorChanged.emit(rgb)
