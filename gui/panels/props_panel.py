# gui/panels/props_panel.py
"""右侧属性面板"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QScrollArea, QGroupBox, QLineEdit, QSpinBox,
    QCheckBox, QLabel, QPushButton, QComboBox
)

from ..widgets import ColorButton
from ..constants import COMMON_RESOLUTIONS


class PropsPanel(QScrollArea):
    """属性面板 - 基本信息、样式、布局、对话框设置"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        
        panel = QWidget()
        self.setWidget(panel)
        layout = QVBoxLayout(panel)

        # --- 基本信息 ---
        group_meta = QGroupBox("基本信息")
        form_meta = QFormLayout()
        self.edit_name = QLineEdit()
        form_meta.addRow("显示名称:", self.edit_name)
        group_meta.setLayout(form_meta)
        layout.addWidget(group_meta)

        # --- 样式设置 ---
        group_style = QGroupBox("样式设置")
        form_style = QFormLayout()

        # 正文样式
        self.spin_font_size = QSpinBox()
        self.spin_font_size.setRange(10, 200)
        self.btn_text_color = ColorButton([255, 255, 255])

        row_text = QHBoxLayout()
        row_text.addWidget(self.spin_font_size)
        row_text.addWidget(self.btn_text_color)
        form_style.addRow("正文 (大小/色):", row_text)

        # 名字样式
        self.spin_name_size = QSpinBox()
        self.spin_name_size.setRange(10, 200)
        self.btn_name_color = ColorButton([255, 0, 255])

        row_name = QHBoxLayout()
        row_name.addWidget(self.spin_name_size)
        row_name.addWidget(self.btn_name_color)
        form_style.addRow("名字 (大小/色):", row_name)

        group_style.setLayout(form_style)
        layout.addWidget(group_style)

        # --- 画布设置 ---
        group_canvas = QGroupBox("画布设置")
        form_canvas = QFormLayout()
        self.combo_resolution = QComboBox()
        self._populate_resolution_combo()
        form_canvas.addRow("分辨率:", self.combo_resolution)
        group_canvas.setLayout(form_canvas)
        layout.addWidget(group_canvas)

        # --- 布局微调 ---
        group_layout = QGroupBox("布局微调")
        form_layout = QFormLayout()

        self.check_on_top = QCheckBox("立绘覆盖对话框")
        form_layout.addRow(self.check_on_top)

        self.lbl_pos_info = QLabel("拖动画面元素以更新坐标")
        self.lbl_pos_info.setStyleSheet("color: gray; font-size: 10px;")
        form_layout.addRow(self.lbl_pos_info)

        group_layout.setLayout(form_layout)
        layout.addWidget(group_layout)

        # --- 对话框 ---
        group_box = QGroupBox("对话框")
        vbox_box = QVBoxLayout()
        self.btn_select_dialog_box = QPushButton("更换底图 (自动贴底)...")
        vbox_box.addWidget(self.btn_select_dialog_box)
        group_box.setLayout(vbox_box)
        layout.addWidget(group_box)

        layout.addStretch()

    def _populate_resolution_combo(self):
        self.combo_resolution.clear()
        for w, h in COMMON_RESOLUTIONS:
            label = f"{w} x {h}"
            self.combo_resolution.addItem(label, (w, h))
