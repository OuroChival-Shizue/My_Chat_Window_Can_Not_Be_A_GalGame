# gui/panels/props_panel.py
"""右侧属性面板"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QScrollArea, QGroupBox, QLineEdit, QSpinBox,
    QCheckBox, QLabel, QPushButton, QComboBox, QPlainTextEdit,
    QSizePolicy,
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
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # --- 基本信息 ---
        group_meta = QGroupBox("基本信息")
        form_meta = QFormLayout()
        form_meta.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form_meta.setHorizontalSpacing(8)
        form_meta.setVerticalSpacing(4)

        self.edit_name = QLineEdit()
        form_meta.addRow("显示名称:", self.edit_name)
        group_meta.setLayout(form_meta)
        layout.addWidget(group_meta)

        # --- 样式设置 ---
        group_style = QGroupBox("样式设置")
        form_style = QFormLayout()
        # 让右侧字段列尽量填满，减少留白
        form_style.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form_style.setHorizontalSpacing(8)
        form_style.setVerticalSpacing(4)

        # 正文样式
        self.spin_font_size = QSpinBox()
        self.spin_font_size.setRange(10, 200)
        self.btn_text_color = ColorButton([255, 255, 255])

        row_text = QHBoxLayout()
        row_text.setContentsMargins(0, 0, 0, 0)
        row_text.setSpacing(4)
        row_text.addWidget(self.spin_font_size)
        row_text.addWidget(self.btn_text_color)
        form_style.addRow("正文 (大小/色):", row_text)

        # 名字样式
        self.spin_name_size = QSpinBox()
        self.spin_name_size.setRange(10, 200)
        self.btn_name_color = ColorButton([255, 0, 255])

        row_name = QHBoxLayout()
        row_name.setContentsMargins(0, 0, 0, 0)
        row_name.setSpacing(4)
        row_name.addWidget(self.spin_name_size)
        row_name.addWidget(self.btn_name_color)
        form_style.addRow("名字 (大小/色):", row_name)

        self.check_name_advanced = QCheckBox("启用高级名称 YAML")
        form_style.addRow(self.check_name_advanced)

        # 高级 YAML 一行：用自己的 HBox，把标签和文本框紧贴在一起
        self.lbl_name_yaml = QLabel("高\n级\nY\nA\nM\nL")
        self.lbl_name_yaml.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.name_yaml_container = QWidget()
        yaml_policy = QSizePolicy(QSizePolicy.Policy.Expanding,
                                  QSizePolicy.Policy.Preferred)
        self.name_yaml_container.setSizePolicy(yaml_policy)

        yaml_layout = QVBoxLayout(self.name_yaml_container)
        yaml_layout.setContentsMargins(0, 0, 0, 0)
        yaml_layout.setSpacing(4)

        self.edit_name_yaml = QPlainTextEdit()
        self.edit_name_yaml.setPlaceholderText(
            "default:\n"
            "  - text: \"{name}\"\n"
            "    position: [0, 0]\n"
            "    font_color: [255, 255, 255]\n"
            "    font_size: 32"
        )
        self.btn_apply_name_yaml = QPushButton("应用 YAML")
        self.btn_reset_name_yaml = QPushButton("恢复默认示例")

        yaml_layout.addWidget(self.edit_name_yaml)
        yaml_layout.addWidget(self.btn_apply_name_yaml)
        yaml_layout.addWidget(self.btn_reset_name_yaml)

        # 关键：这里不用 addRow(label, field)，而是整行交给一个 HBox，
        # 这样标签和文本框之间就只有很小的 spacing，不会再被 QFormLayout 撑开。
        row_yaml = QHBoxLayout()
        row_yaml.setContentsMargins(0, 0, 0, 0)
        row_yaml.setSpacing(2)  # 几乎贴着
        row_yaml.addWidget(self.lbl_name_yaml)
        row_yaml.addWidget(self.name_yaml_container, 1)
        form_style.addRow(row_yaml)

        self.set_advanced_yaml_visible(False)

        group_style.setLayout(form_style)
        layout.addWidget(group_style)

        # --- 台词前后缀 ---
        group_wrapper = QGroupBox("台词前后缀")
        form_wrapper = QFormLayout()
        form_wrapper.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form_wrapper.setHorizontalSpacing(8)
        form_wrapper.setVerticalSpacing(4)

        self.combo_wrapper_mode = QComboBox()
        self.combo_wrapper_mode.addItem("无", {"type": "none"})
        self.combo_wrapper_mode.addItem("「」", {"type": "preset", "preset": "corner_single"})
        self.combo_wrapper_mode.addItem("『』", {"type": "preset", "preset": "corner_double"})
        self.combo_wrapper_mode.addItem("自定义", {"type": "custom"})
        form_wrapper.addRow("模式:", self.combo_wrapper_mode)

        self.edit_wrapper_prefix = QLineEdit()
        self.edit_wrapper_prefix.setPlaceholderText("前缀")
        form_wrapper.addRow("前缀:", self.edit_wrapper_prefix)

        self.edit_wrapper_suffix = QLineEdit()
        self.edit_wrapper_suffix.setPlaceholderText("后缀")
        form_wrapper.addRow("后缀:", self.edit_wrapper_suffix)

        group_wrapper.setLayout(form_wrapper)
        layout.addWidget(group_wrapper)
        self.set_wrapper_custom_enabled(False)

        # --- 画布设置 ---
        group_canvas = QGroupBox("画布设置")
        form_canvas = QFormLayout()
        form_canvas.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form_canvas.setHorizontalSpacing(8)
        form_canvas.setVerticalSpacing(4)

        self.combo_resolution = QComboBox()
        self._populate_resolution_combo()
        form_canvas.addRow("分辨率:", self.combo_resolution)
        group_canvas.setLayout(form_canvas)
        layout.addWidget(group_canvas)

        # --- 布局微调 ---
        group_layout = QGroupBox("布局微调")
        form_layout = QFormLayout()
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form_layout.setHorizontalSpacing(8)
        form_layout.setVerticalSpacing(4)

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
        vbox_box.setContentsMargins(0, 0, 0, 0)
        vbox_box.setSpacing(4)

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

    def set_wrapper_custom_enabled(self, enabled: bool) -> None:
        self.edit_wrapper_prefix.setEnabled(enabled)
        self.edit_wrapper_suffix.setEnabled(enabled)

    def set_advanced_yaml_visible(self, visible: bool) -> None:
        self.lbl_name_yaml.setVisible(visible)
        self.name_yaml_container.setVisible(visible)
