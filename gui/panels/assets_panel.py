# gui/panels/assets_panel.py
"""左侧资源库面板"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QComboBox
)

from ..widgets import AssetListWidget


class AssetsPanel(QWidget):
    """资源库面板 - 角色选择、立绘列表、背景列表"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 角色选择
        layout.addWidget(QLabel("<b>当前角色:</b>"))
        self.combo_char = QComboBox()
        layout.addWidget(self.combo_char)

        layout.addSpacing(10)

        # 立绘区域
        row_p_label = QHBoxLayout()
        row_p_label.addWidget(QLabel("<b>立绘列表:</b>"))
        self.btn_add_portrait = QPushButton("+")
        self.btn_add_portrait.setFixedSize(24, 24)
        self.btn_add_portrait.setToolTip("添加立绘 (支持多张)")
        row_p_label.addWidget(self.btn_add_portrait)
        layout.addLayout(row_p_label)

        self.list_portraits = AssetListWidget()
        layout.addWidget(self.list_portraits)

        layout.addSpacing(10)

        # 背景区域
        row_bg_label = QHBoxLayout()
        row_bg_label.addWidget(QLabel("<b>背景列表:</b>"))
        self.btn_add_background = QPushButton("+")
        self.btn_add_background.setFixedSize(24, 24)
        self.btn_add_background.setToolTip("添加背景 (单张替换)")
        row_bg_label.addWidget(self.btn_add_background)
        layout.addLayout(row_bg_label)

        self.list_backgrounds = AssetListWidget()
        layout.addWidget(self.list_backgrounds)

        # 提示
        lbl_tip = QLabel("<small>提示: 右键可删除，拖拽可添加</small>")
        lbl_tip.setStyleSheet("color: gray;")
        layout.addWidget(lbl_tip)
