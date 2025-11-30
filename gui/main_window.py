
import os
import json
import shutil
import re
from typing import Dict, Any, Optional, Tuple, List, Union

import yaml

from PyQt6.QtWidgets import (
    QMainWindow, QGraphicsScene, QGraphicsView, QGraphicsPixmapItem, QGraphicsSimpleTextItem,
    QDockWidget, QMessageBox, QFileDialog, QInputDialog, QDialog
)
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPixmap, QPen, QBrush, QColor, QPainter, QFont, QFontDatabase, QAction

from .constants import (
    BASE_PATH, CanvasConfig, COMMON_RESOLUTIONS, DEFAULT_CANVAS_SIZE,
    Z_BG, Z_PORTRAIT_BOTTOM, Z_BOX, Z_PORTRAIT_TOP, Z_TEXT,
    load_global_config, save_global_config, normalize_layout, normalize_style,
    dump_yaml_inline, CharacterRenderer, prebuild_character
)
from .canvas import ResizableTextItem, ScalableImageItem
from .widgets import NewCharacterDialog, PrebuildProgressDialog
from .panels import AssetsPanel, PropsPanel


class MainWindow(QMainWindow):
    """主编辑器窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Box-of-GalGame-Sister 编辑器 (Refactored)")
        self.resize(1600, 900)

        # --- 状态变量 ---
        self.current_char_id: Optional[str] = None
        self.char_root: str = ""
        self.config: Dict[str, Any] = {}
        self.config_path: str = ""

        self.scene_items: Dict[str, Optional[Union[ResizableTextItem, ScalableImageItem]]] = {
            "bg": None,
            "portrait": None,
            "box": None,
            "name_text": None,
            "main_text": None
        }
        self.advanced_name_items: List[QGraphicsSimpleTextItem] = []

        self.custom_font_family = ""
        self.cache_outdated = False
        self.resolution_prompted = False
        self._ui_syncing = False

        # --- 初始化 ---
        self._load_custom_font()
        self._init_ui()
        self._connect_signals()
        self._load_initial_data()

    # =========================================================================
    # 初始化
    # =========================================================================
    def open_settings(self):
        """打开设置对话框"""
        from .widgets import SettingsDialog
        dialog = SettingsDialog(self)
        dialog.exec()
        
    def _load_custom_font(self):
        font_path = os.path.join(BASE_PATH, "common", "fonts", "LXGWWenKai-Medium.ttf")
        if os.path.exists(font_path):
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                families = QFontDatabase.applicationFontFamilies(font_id)
                if families:
                    self.custom_font_family = families[0]
                    print(f"已加载字体: {self.custom_font_family}")

    def _init_ui(self):
        self._create_menus()

        # 中央画布
        canvas_w, canvas_h = CanvasConfig.get_size()
        self.scene = QGraphicsScene(0, 0, canvas_w, canvas_h)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view.setBackgroundBrush(QBrush(QColor(40, 40, 40)))
        self.setCentralWidget(self.view)

        # 左侧资源面板
        self.assets_panel = AssetsPanel()
        self.dock_assets = QDockWidget("资源库 (Assets)", self)
        self.dock_assets.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.dock_assets.setWidget(self.assets_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock_assets)

        # 右侧属性面板
        self.props_panel = PropsPanel()
        self.dock_props = QDockWidget("属性 (Properties)", self)
        self.dock_props.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.dock_props.setWidget(self.props_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_props)

    def _create_menus(self):
        menubar = self.menuBar()
        if menubar is None:
            raise RuntimeError("Menu bar is not available")

        # 文件菜单
        file_menu = menubar.addMenu("文件 (&File)")
        if file_menu is None:
            raise RuntimeError("File menu is not available")
        
        action_new = QAction("新建角色 (New Character)", self)
        action_new.setShortcut("Ctrl+N")
        action_new.triggered.connect(self.create_new_character)
        file_menu.addAction(action_new)

        action_save = QAction("保存配置 (Save)", self)
        action_save.setShortcut("Ctrl+S")
        action_save.triggered.connect(self.save_config)
        file_menu.addAction(action_save)

        action_open_dir = QAction("打开角色目录", self)
        action_open_dir.triggered.connect(self.open_character_folder)
        file_menu.addAction(action_open_dir)

        file_menu.addSeparator()
        
        # ========== 新增：设置选项 ==========
        action_settings = QAction("设置 (&Settings)...", self)
        action_settings.setShortcut("Ctrl+,")
        action_settings.triggered.connect(self.open_settings)
        file_menu.addAction(action_settings)
        # ====================================
        
        file_menu.addSeparator()
        
        action_exit = QAction("退出", self)
        action_exit.triggered.connect(self.close)
        file_menu.addAction(action_exit)

        # 工具菜单
        tools_menu = menubar.addMenu("工具 (&Tools)")

        if tools_menu is None:
            raise RuntimeError("Tools menu is not available")
        action_preview = QAction("渲染预览 (Render Preview)", self)
        action_preview.setShortcut("F5")
        action_preview.triggered.connect(self.preview_render)
        tools_menu.addAction(action_preview)

        action_cache = QAction("生成缓存 (Build Cache)", self)
        action_cache.triggered.connect(self.generate_cache)
        tools_menu.addAction(action_cache)

        action_sync = QAction("同步/修复配置 (Sync Configs)", self)
        action_sync.triggered.connect(self.sync_all_configs)
        tools_menu.addAction(action_sync)

        tools_menu.addSeparator()

        action_reload = QAction("重载界面 (Reload UI)", self)
        action_reload.setShortcut("Ctrl+R")
        action_reload.triggered.connect(self.reload_current_character)
        tools_menu.addAction(action_reload)


    def _connect_signals(self):
        """连接所有信号槽"""
        # 资源面板
        ap = self.assets_panel
        ap.combo_char.currentIndexChanged.connect(self.on_character_changed)
        ap.btn_add_portrait.clicked.connect(self.add_portrait)
        ap.btn_add_background.clicked.connect(self.add_background)
        ap.list_portraits.currentTextChanged.connect(self.on_portrait_selected)
        ap.list_portraits.fileDropped.connect(lambda p: self.import_asset(p, "portrait"))
        ap.list_portraits.deleteRequested.connect(lambda f: self.delete_asset_file(f, "portrait"))
        ap.list_backgrounds.currentTextChanged.connect(self.on_background_selected)
        ap.list_backgrounds.fileDropped.connect(lambda p: self.import_asset(p, "background"))
        ap.list_backgrounds.deleteRequested.connect(lambda f: self.delete_asset_file(f, "background"))

        # 属性面板
        pp = self.props_panel
        pp.edit_name.textChanged.connect(self.on_name_changed)
        pp.spin_font_size.valueChanged.connect(self.on_style_changed)
        pp.spin_name_size.valueChanged.connect(self.on_style_changed)
        pp.btn_text_color.colorChanged.connect(self.on_style_changed)
        pp.btn_name_color.colorChanged.connect(self.on_style_changed)
        pp.combo_wrapper_mode.currentIndexChanged.connect(self.on_wrapper_changed)
        pp.edit_wrapper_prefix.textChanged.connect(self.on_wrapper_changed)
        pp.edit_wrapper_suffix.textChanged.connect(self.on_wrapper_changed)
        pp.check_name_advanced.toggled.connect(self.on_name_mode_toggled)
        pp.btn_apply_name_yaml.clicked.connect(self.on_apply_name_layers_yaml)
        pp.btn_reset_name_yaml.clicked.connect(self.on_reset_name_layers_yaml)
        pp.combo_resolution.currentIndexChanged.connect(self.on_resolution_changed)
        pp.check_on_top.toggled.connect(self.on_layout_changed)
        pp.btn_select_dialog_box.clicked.connect(self.select_dialog_box)

    # =========================================================================
    # 数据加载
    # =========================================================================

    def _load_initial_data(self):
        char_dir = os.path.join(BASE_PATH, "characters")
        if not os.path.exists(char_dir):
            os.makedirs(char_dir)

        chars = [d for d in os.listdir(char_dir) if os.path.isdir(os.path.join(char_dir, d))]
        chars.sort()

        combo = self.assets_panel.combo_char
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(chars)

        global_conf = load_global_config()
        last_char = global_conf.get("current_character", "")

        if last_char and last_char in chars:
            combo.setCurrentText(last_char)
        elif chars:
            combo.setCurrentIndex(0)

        combo.blockSignals(False)

        if combo.count() > 0:
            self.on_character_changed(combo.currentIndex())

    def load_config(self):
        default_style = normalize_style({
            "basic": {
                "font_size": 45,
                "text_color": [255, 255, 255],
                "name_font_size": 29,
                "name_color": [255, 0, 255],
            }
        })
        current_canvas = CanvasConfig.get_size()
        default_cfg = {
            "meta": {"name": self.current_char_id},
            "style": default_style,
            "layout": {
                "stand_scale": 1.0,
                "stand_on_top": False,
                "_canvas_size": [current_canvas[0], current_canvas[1]],
            },
            "assets": {"dialog_box": "textbox_bg.png"}
        }

        load_path = self.config_path
        legacy_path = os.path.join(self.char_root, "config.json")
        if not os.path.exists(load_path) and os.path.exists(legacy_path):
            load_path = legacy_path

        if os.path.exists(load_path):
            try:
                with open(load_path, 'r', encoding='utf-8') as f:
                    if load_path.endswith(('.yaml', '.yml')):
                        loaded = yaml.safe_load(f) or {}
                    else:
                        loaded = json.load(f)
                    self.config = self._merge_dicts(default_cfg, loaded)
            except Exception as e:
                print(f"Config load error: {e}")
                self.config = default_cfg
        else:
            self.config = default_cfg

        self.config["style"] = normalize_style(self.config.get("style"))
        layout = self.config.setdefault("layout", {})
        stored_canvas = self._extract_canvas_size(layout.get("_canvas_size"))
        if stored_canvas:
            CanvasConfig.set_size(*stored_canvas)
        else:
            CanvasConfig.set_size(*DEFAULT_CANVAS_SIZE)
        canvas_size = CanvasConfig.get_size()
        normalized = normalize_layout(layout, canvas_size)
        normalized["_canvas_size"] = [canvas_size[0], canvas_size[1]]
        self.config["layout"] = normalized
        self.scene.setSceneRect(0, 0, canvas_size[0], canvas_size[1])

    def _merge_dicts(self, base, update):
        for k, v in update.items():
            if isinstance(v, dict) and k in base:
                self._merge_dicts(base[k], v)
            else:
                base[k] = v
        return base

    def _ensure_style(self) -> Dict[str, Any]:
        style = self.config.get("style")
        normalized = normalize_style(style)
        self.config["style"] = normalized
        return normalized

    def _find_wrapper_index(self, wrapper: Dict[str, Any]) -> int:
        combo = self.props_panel.combo_wrapper_mode
        wrapper_type = wrapper.get("type", "none")
        preset = wrapper.get("preset")
        for i in range(combo.count()):
            data = combo.itemData(i)
            if not isinstance(data, dict):
                continue
            if data.get("type") != wrapper_type:
                continue
            if wrapper_type == "preset":
                if data.get("preset") == preset:
                    return i
            else:
                return i
        return -1

    def _set_wrapper_inputs(self, prefix: str, suffix: str) -> None:
        pp = self.props_panel
        pp.edit_wrapper_prefix.blockSignals(True)
        pp.edit_wrapper_prefix.setText(prefix)
        pp.edit_wrapper_prefix.blockSignals(False)
        pp.edit_wrapper_suffix.blockSignals(True)
        pp.edit_wrapper_suffix.setText(suffix)
        pp.edit_wrapper_suffix.blockSignals(False)

    def _dump_name_layers(self, style: Dict[str, Any]) -> str:
        layers = style.get("advanced", {}).get("name_layers", {})
        try:
            dumped = dump_yaml_inline(layers or {})
            return dumped if isinstance(dumped, str) else ""
        except Exception:
            return "default: []"

    @staticmethod
    def _wrapper_tokens(preset: str) -> Tuple[str, str]:
        if preset == "corner_double":
            return "『", "』"
        return "「", "」"

    def _build_default_name_layers(self) -> Dict[str, Any]:
        style = self._ensure_style()
        basic = style.get("basic", {})
        color = basic.get("name_color", [255, 255, 255])
        size = max(1, int(basic.get("name_font_size", 32)))
        meta_name = self.config.get("meta", {}).get("name") or self.current_char_id or "default"
        spacing = max(1, int(size * 0.8))
        entries: List[Dict[str, Any]] = []
        x_offset = 0
        for ch in meta_name:
            entries.append(
                {
                    "text": ch,
                    "position": [x_offset, 0],
                    "font_color": color,
                    "font_size": size,
                }
            )
            x_offset += spacing
        if not entries:
            entries.append(
                {
                    "text": "{name}",
                    "position": [0, 0],
                    "font_color": color,
                    "font_size": size,
                }
            )

        fallback = [
            {
                "text": "{name}",
                "position": [0, 0],
                "font_color": color,
                "font_size": size,
            }
        ]

        layers: Dict[str, Any] = {meta_name: entries}
        layers["default"] = fallback
        return layers

    # =========================================================================
    # UI 同步
    # =========================================================================

    def refresh_asset_lists(self):
        p_dir = os.path.join(self.char_root, "portrait")
        list_p = self.assets_panel.list_portraits
        list_p.blockSignals(True)
        list_p.clear()
        if os.path.exists(p_dir):
            files = [f for f in os.listdir(p_dir) if f.lower().endswith(('.png', '.jpg'))]
            files.sort()
            list_p.addItems(files)
        list_p.blockSignals(False)

        bg_dirs = [
            os.path.join(self.char_root, "background"),
            os.path.join(BASE_PATH, "common", "background")
        ]
        list_bg = self.assets_panel.list_backgrounds
        list_bg.blockSignals(True)
        list_bg.clear()
        for d in bg_dirs:
            if os.path.exists(d):
                files = [f for f in os.listdir(d) if f.lower().endswith(('.png', '.jpg'))]
                list_bg.addItems(files)
        list_bg.blockSignals(False)

    def update_ui_from_config(self):
        meta = self.config.get("meta", {})
        style = self._ensure_style()
        basic = style.get("basic", {})
        wrapper = style.get("text_wrapper", {})
        layout = self.config.get("layout", {})

        pp = self.props_panel
        ap = self.assets_panel

        self._ui_syncing = True
        pp.edit_name.blockSignals(True)
        pp.edit_name.setText(meta.get("name", ""))
        pp.edit_name.blockSignals(False)

        pp.spin_font_size.blockSignals(True)
        pp.spin_font_size.setValue(int(basic.get("font_size", 45)))
        pp.spin_font_size.blockSignals(False)

        pp.spin_name_size.blockSignals(True)
        pp.spin_name_size.setValue(int(basic.get("name_font_size", 45)))
        pp.spin_name_size.blockSignals(False)

        pp.btn_text_color.set_color(basic.get("text_color", [255, 255, 255]))
        pp.btn_name_color.set_color(basic.get("name_color", [255, 0, 255]))

        is_advanced = style.get("mode") == "advanced"
        pp.check_name_advanced.blockSignals(True)
        pp.check_name_advanced.setChecked(is_advanced)
        pp.check_name_advanced.blockSignals(False)
        pp.set_advanced_yaml_visible(is_advanced)
        pp.edit_name_yaml.blockSignals(True)
        pp.edit_name_yaml.setPlainText(self._dump_name_layers(style))
        pp.edit_name_yaml.blockSignals(False)

        pp.combo_wrapper_mode.blockSignals(True)
        wrapper_index = self._find_wrapper_index(wrapper)
        if wrapper_index < 0:
            wrapper_index = 0
        pp.combo_wrapper_mode.setCurrentIndex(wrapper_index)
        pp.combo_wrapper_mode.blockSignals(False)
        prefix = wrapper.get("prefix", "")
        suffix = wrapper.get("suffix", "")
        self._set_wrapper_inputs(prefix, suffix)
        pp.set_wrapper_custom_enabled(wrapper.get("type") == "custom")

        pp.check_on_top.blockSignals(True)
        pp.check_on_top.setChecked(layout.get("stand_on_top", False))
        pp.check_on_top.blockSignals(False)

        curr_p = layout.get("current_portrait")
        if curr_p:
            items = ap.list_portraits.findItems(curr_p, Qt.MatchFlag.MatchExactly)
            if items:
                ap.list_portraits.setCurrentItem(items[0])

        curr_bg = layout.get("current_background")
        if curr_bg:
            items = ap.list_backgrounds.findItems(curr_bg, Qt.MatchFlag.MatchExactly)
            if items:
                ap.list_backgrounds.setCurrentItem(items[0])

        self._sync_resolution_combo()
        self._ui_syncing = False

    def _sync_resolution_combo(self):
        combo = self.props_panel.combo_resolution
        current = CanvasConfig.get_size()
        idx = combo.findData(current)
        if idx == -1:
            label = f"{current[0]} x {current[1]}"
            combo.addItem(label, current)
            idx = combo.findData(current)
        combo.blockSignals(True)
        combo.setCurrentIndex(idx)
        combo.blockSignals(False)

    # =========================================================================
    # 画布重建
    # =========================================================================

    def rebuild_scene(self):
        self.scene_items = {k: None for k in self.scene_items}
        self.advanced_name_items = []
        self.scene.clear()

        canvas_w, canvas_h = CanvasConfig.get_size()

        # 背景矩形
        qGraphicsRectItem = self.scene.addRect(
            0, 0, canvas_w, canvas_h,
            QPen(Qt.GlobalColor.black),
            QBrush(Qt.GlobalColor.white)
        )
        if qGraphicsRectItem:
            qGraphicsRectItem.setZValue(Z_BG)

        layout = self.config.get("layout", {})
        assets = self.config.get("assets", {})

        # 背景图
        bg_name = layout.get("current_background")
        if bg_name:
            bg_path = self._find_asset_path(bg_name, "background")
            if bg_path:
                pix = QPixmap(bg_path).scaled(
                    canvas_w, canvas_h,
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                item = ScalableImageItem(pix)
                item.setZValue(Z_BG)
                self.scene.addItem(item)
                self.scene_items["bg"] = item

        # 对话框
        box_name = assets.get("dialog_box", "textbox_bg.png")
        box_path = os.path.join(self.char_root, box_name)
        if os.path.exists(box_path):
            pix = QPixmap(box_path)
            if pix.width() != canvas_w:
                new_h = int(pix.height() * (canvas_w / pix.width()))
                pix = pix.scaled(
                    canvas_w, new_h,
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )

            item = ScalableImageItem(pix)
            saved_pos = layout.get("box_pos")
            if saved_pos:
                item.setPos(saved_pos[0], saved_pos[1])
            else:
                item.setPos(0, canvas_h - pix.height())

            item.setZValue(Z_BOX)
            self.scene.addItem(item)
            self.scene_items["box"] = item

        # 立绘
        p_name = layout.get("current_portrait")
        if p_name:
            p_path = os.path.join(self.char_root, "portrait", p_name)
            if os.path.exists(p_path):
                pix = QPixmap(p_path)
                item = ScalableImageItem(pix)

                scale = layout.get("stand_scale", 1.0)
                pos = layout.get("stand_pos", [0, 0])

                item.setScale(scale)
                item.setPos(pos[0], pos[1])

                z = Z_PORTRAIT_TOP if layout.get("stand_on_top") else Z_PORTRAIT_BOTTOM
                item.setZValue(z)

                self.scene.addItem(item)
                self.scene_items["portrait"] = item

        # 文本项
        style = self._ensure_style()
        basic = style.get("basic", {})
        meta = self.config.get("meta", {})

        # 名字文本
        name_pos = layout.get("name_pos", [100, 100])
        name_color = basic.get("name_color", [255, 0, 255])
        name_size = basic.get("name_font_size", 45)
        name_str = meta.get("name", self.current_char_id)

        name_item = ResizableTextItem(
            QRectF(0, 0, 400, 100),
            name_str,
            name_color,
            name_size,
            font_family=self.custom_font_family
        )
        name_item.setPos(name_pos[0], name_pos[1])
        name_item.setZValue(Z_TEXT)
        self.scene.addItem(name_item)
        self.scene_items["name_text"] = name_item

        if style.get("mode") == "advanced":
            placeholder_color = [180, 180, 180]
            placeholder_size = max(12, int(name_size * 0.6))
            name_item.update_content(
                text="高级名称模式\n拖动此框调整基准点",
                color=placeholder_color,
                size=placeholder_size
            )
            name_item.setOpacity(0.6)
            self._create_advanced_name_preview(name_item, style, name_str)
        else:
            name_item.setOpacity(1.0)

        # 正文文本
        text_area = layout.get("text_area", [100, 800, 1800, 1000])
        text_color = basic.get("text_color", [255, 255, 255])
        text_size = basic.get("font_size", 45)
        sample_text = self._get_preview_sample_text(style)

        w = text_area[2] - text_area[0]
        h = text_area[3] - text_area[1]
        text_item = ResizableTextItem(
            QRectF(0, 0, w, h),
            sample_text,
            text_color,
            text_size,
            font_family=self.custom_font_family
        )
        text_item.setPos(text_area[0], text_area[1])
        text_item.setZValue(Z_TEXT)
        self.scene.addItem(text_item)
        self.scene_items["main_text"] = text_item

        self.fit_view()

    def _get_preview_sample_text(self, style: Dict[str, Any]) -> str:
        base = "预览文本区域\n拖动调整位置"
        wrapper = style.get("text_wrapper", {})
        if not isinstance(wrapper, dict):
            return base
        wrapper_type = wrapper.get("type", "none")
        prefix = ""
        suffix = ""
        if wrapper_type == "preset":
            preset = wrapper.get("preset", "corner_single")
            prefix, suffix = self._wrapper_tokens(preset)
        elif wrapper_type == "custom":
            prefix = str(wrapper.get("prefix", ""))
            suffix = str(wrapper.get("suffix", ""))

        if not prefix and not suffix:
            return base

        if not base:
            return f"{prefix}{suffix}"
        return f"{prefix}{base}{suffix}"

    def _update_preview_wrapper_text(self):
        text_item = self.scene_items.get("main_text")
        if isinstance(text_item, ResizableTextItem):
            sample = self._get_preview_sample_text(self._ensure_style())
            text_item.update_content(text=sample)

    def _extract_canvas_size(self, value: Any) -> Optional[Tuple[int, int]]:
        if (
            isinstance(value, (list, tuple))
            and len(value) == 2
        ):
            try:
                w = int(value[0])
                h = int(value[1])
            except Exception:
                return None
            if w > 0 and h > 0:
                return w, h
        return None

    def _create_advanced_name_preview(self, anchor_item: ResizableTextItem, style: Dict[str, Any], speaker_name: str):
        advanced = style.get("advanced", {})
        layers_map = advanced.get("name_layers")
        if not isinstance(layers_map, dict):
            return

        entries: Optional[List[Dict[str, Any]]] = None
        if speaker_name and speaker_name in layers_map:
            entries = layers_map[speaker_name]
        elif "default" in layers_map:
            entries = layers_map["default"]

        if not isinstance(entries, list):
            return

        basic = style.get("basic", {})
        fallback_color = basic.get("name_color", [255, 255, 255])
        fallback_size = basic.get("name_font_size", 32)

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            text_value = str(entry.get("text", ""))
            if not text_value:
                continue
            text_value = text_value.replace("{name}", speaker_name or "")

            pos = entry.get("position", [0, 0])
            if (
                isinstance(pos, (list, tuple))
                and len(pos) == 2
            ):
                offset_x = float(pos[0])
                offset_y = float(pos[1])
            else:
                offset_x = 0.0
                offset_y = 0.0

            color_src = entry.get("font_color", fallback_color)
            if (
                isinstance(color_src, (list, tuple))
                and len(color_src) == 3
            ):
                color_rgb = [max(0, min(255, int(c))) for c in color_src]
            else:
                color_rgb = fallback_color

            size_src = entry.get("font_size", fallback_size)
            try:
                font_size = max(1, int(size_src))
            except Exception:
                font_size = max(1, int(fallback_size))

            font = QFont()
            font.setPixelSize(font_size)
            if self.custom_font_family:
                font.setFamily(self.custom_font_family)
            else:
                font.setFamily("Microsoft YaHei")

            text_item = QGraphicsSimpleTextItem(text_value, anchor_item)
            text_item.setFont(font)
            text_item.setBrush(QColor(*color_rgb))
            bounds = text_item.boundingRect()
            text_item.setPos(offset_x - bounds.left(), offset_y - bounds.top())
            text_item.setZValue(anchor_item.zValue() + 0.1)
            self.advanced_name_items.append(text_item)

    def _find_asset_path(self, filename, type_folder):
        p1 = os.path.join(self.char_root, type_folder, filename)
        if os.path.exists(p1):
            return p1
        p2 = os.path.join(BASE_PATH, "common", type_folder, filename)
        if os.path.exists(p2):
            return p2
        return None

    def fit_view(self):
        canvas_w, canvas_h = CanvasConfig.get_size()
        self.view.resetTransform()
        self.view.fitInView(0, 0, canvas_w, canvas_h, Qt.AspectRatioMode.KeepAspectRatio)
        self.view.scale(0.95, 0.95)

    # =========================================================================
    # 事件处理
    # =========================================================================

    def on_character_changed(self, index: int):
        char_id = self.assets_panel.combo_char.currentText()
        if not char_id:
            return

        self.current_char_id = char_id
        self.char_root = os.path.join(BASE_PATH, "characters", char_id)
        self.config_path = os.path.join(self.char_root, "config.yaml")

        try:
            g_conf = load_global_config()
            if g_conf.get("current_character") != char_id:
                g_conf["current_character"] = char_id
                save_global_config(g_conf)
        except Exception as e:
            print(f"Global config save failed: {e}")

        self.load_config()
        self.refresh_asset_lists()
        self.update_ui_from_config()
        self.rebuild_scene()

    def on_portrait_selected(self, text):
        if not text:
            return
        self.config.setdefault("layout", {})["current_portrait"] = text
        self.rebuild_scene()

    def on_background_selected(self, text):
        if not text:
            return
        self.config.setdefault("layout", {})["current_background"] = text
        self.rebuild_scene()

    def on_name_changed(self, text):
        self.config.setdefault("meta", {})["name"] = text
        if isinstance(self.scene_items["name_text"], ResizableTextItem):
            self.scene_items["name_text"].update_content(text=text)

    def on_style_changed(self):
        pp = self.props_panel
        style = self._ensure_style()
        basic = style.setdefault("basic", {})

        basic["font_size"] = pp.spin_font_size.value()
        basic["name_font_size"] = pp.spin_name_size.value()
        basic["text_color"] = pp.btn_text_color.current_color
        basic["name_color"] = pp.btn_name_color.current_color

        if isinstance(self.scene_items["main_text"], ResizableTextItem):
            self.scene_items["main_text"].update_content(
                size=basic["font_size"],
                color=basic["text_color"]
            )
        if isinstance(self.scene_items["name_text"], ResizableTextItem):
            self.scene_items["name_text"].update_content(
                size=basic["name_font_size"],
                color=basic["name_color"]
            )

    def on_wrapper_changed(self):
        pp = self.props_panel
        style = self._ensure_style()
        wrapper = style.setdefault("text_wrapper", {})
        data = pp.combo_wrapper_mode.currentData()
        wrapper_type = data.get("type") if isinstance(data, dict) else "none"
        wrapper["type"] = wrapper_type

        if wrapper_type == "preset":
            preset = data.get("preset", "corner_single") if isinstance(data, dict) else "corner_single"
            wrapper["preset"] = preset
            prefix, suffix = self._wrapper_tokens(preset)
            wrapper["prefix"], wrapper["suffix"] = prefix, suffix
            pp.set_wrapper_custom_enabled(False)
            self._set_wrapper_inputs(prefix, suffix)
        elif wrapper_type == "custom":
            wrapper["preset"] = "corner_single"
            wrapper["prefix"] = pp.edit_wrapper_prefix.text()
            wrapper["suffix"] = pp.edit_wrapper_suffix.text()
            pp.set_wrapper_custom_enabled(True)
        else:
            wrapper["preset"] = "corner_single"
            wrapper["prefix"] = ""
            wrapper["suffix"] = ""
            pp.set_wrapper_custom_enabled(False)
            self._set_wrapper_inputs("", "")
        self._update_preview_wrapper_text()

    def on_name_mode_toggled(self, checked: bool):
        if getattr(self, "_ui_syncing", False):
            return
        style = self._ensure_style()
        style["mode"] = "advanced" if checked else "basic"
        if checked:
            advanced = style.setdefault("advanced", {})
            layers = advanced.get("name_layers")
            if not isinstance(layers, dict) or not layers:
                advanced["name_layers"] = self._build_default_name_layers()
                pp = self.props_panel
                pp.edit_name_yaml.blockSignals(True)
                pp.edit_name_yaml.setPlainText(self._dump_name_layers(style))
                pp.edit_name_yaml.blockSignals(False)
        self.props_panel.set_advanced_yaml_visible(checked)
        self.rebuild_scene()

    def on_apply_name_layers_yaml(self):
        pp = self.props_panel
        raw = pp.edit_name_yaml.toPlainText().strip()
        if not raw:
            layers: Dict[str, Any] = {}
        else:
            try:
                parsed = yaml.safe_load(raw)
            except yaml.YAMLError as exc:
                QMessageBox.warning(self, "YAML 错误", f"解析失败: {exc}")
                return
            if not isinstance(parsed, dict):
                QMessageBox.warning(self, "格式错误", "YAML 根节点必须是对象（字典）")
                return
            layers = {}
            for key, value in parsed.items():
                if not isinstance(key, str):
                    QMessageBox.warning(self, "格式错误", "所有键必须是字符串")
                    return
                if not isinstance(value, list):
                    QMessageBox.warning(self, "格式错误", f"「{key}」的值必须是列表")
                    return
                layers[key] = value

        style = self._ensure_style()
        advanced = style.setdefault("advanced", {})
        advanced["name_layers"] = layers
        pp.edit_name_yaml.blockSignals(True)
        pp.edit_name_yaml.setPlainText(self._dump_name_layers(style))
        pp.edit_name_yaml.blockSignals(False)
        status_bar = self.statusBar()
        if status_bar:
            status_bar.showMessage("高级名称 YAML 已应用", 3000)
        self.rebuild_scene()

    def on_reset_name_layers_yaml(self):
        style = self._ensure_style()
        advanced = style.setdefault("advanced", {})
        advanced["name_layers"] = self._build_default_name_layers()
        self.props_panel.edit_name_yaml.blockSignals(True)
        self.props_panel.edit_name_yaml.setPlainText(self._dump_name_layers(style))
        self.props_panel.edit_name_yaml.blockSignals(False)
        status_bar = self.statusBar()
        if status_bar:
            status_bar.showMessage("已恢复高级名称默认示例", 3000)
        self.rebuild_scene()
        self._update_preview_wrapper_text()

    def on_resolution_changed(self, index: int):
        if index < 0:
            return
        combo = self.props_panel.combo_resolution
        data = combo.itemData(index)
        if not data:
            return
        self._apply_canvas_size(tuple(data))

    def on_layout_changed(self):
        on_top = self.props_panel.check_on_top.isChecked()
        self.config.setdefault("layout", {})["stand_on_top"] = on_top
        if self.scene_items["portrait"]:
            z = Z_PORTRAIT_TOP if on_top else Z_PORTRAIT_BOTTOM
            self.scene_items["portrait"].setZValue(z)

    def _apply_canvas_size(self, size: Tuple[int, int]):
        old_w, old_h = CanvasConfig.get_size()
        if (old_w, old_h) == size:
            return

        layout = self.config.setdefault("layout", {})
        old_size = layout.get("_canvas_size")
        if isinstance(old_size, (list, tuple)) and len(old_size) == 2:
            old_tuple = (int(old_size[0]), int(old_size[1]))
        else:
            old_tuple = (old_w, old_h)

        self._scale_layout_for_canvas(layout, old_tuple, size)

        CanvasConfig.set_size(size[0], size[1])
        layout["_canvas_size"] = [size[0], size[1]]
        self.scene.setSceneRect(0, 0, size[0], size[1])
        self.update_ui_from_config()
        self.rebuild_scene()
        self.fit_view()
        self.cache_outdated = True
        self.resolution_prompted = False
        self.save_config()

    def _scale_layout_for_canvas(
        self,
        layout: Dict[str, Any],
        old_size: Tuple[int, int],
        new_size: Tuple[int, int]
    ):
        if not old_size or not new_size:
            return
        if old_size[0] <= 0 or old_size[1] <= 0:
            return
        if old_size == new_size:
            return

        scale_x = new_size[0] / old_size[0]
        scale_y = new_size[1] / old_size[1]

        def scale_point(value):
            if not isinstance(value, (list, tuple)) or len(value) != 2:
                return value
            return [int(round(value[0] * scale_x)), int(round(value[1] * scale_y))]

        def scale_rect(value):
            if not isinstance(value, (list, tuple)) or len(value) != 4:
                return value
            return [
                int(round(value[0] * scale_x)),
                int(round(value[1] * scale_y)),
                int(round(value[2] * scale_x)),
                int(round(value[3] * scale_y)),
            ]

        if "text_area" in layout:
            layout["text_area"] = scale_rect(layout["text_area"])
        if "name_pos" in layout:
            layout["name_pos"] = scale_point(layout["name_pos"])
        if "stand_pos" in layout:
            layout["stand_pos"] = scale_point(layout["stand_pos"])
        if "box_pos" in layout:
            layout["box_pos"] = scale_point(layout["box_pos"])

    # =========================================================================
    # 资源管理
    # =========================================================================

    def import_asset(self, file_path: str, asset_type: str):
        """通用导入逻辑 (拖拽用)"""
        if not self.current_char_id:
            return
        target_dir = os.path.join(self.char_root, asset_type)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)

        try:
            shutil.copy(file_path, target_dir)
            self.refresh_asset_lists()
            QMessageBox.information(self, "成功", f"已导入: {os.path.basename(file_path)}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导入失败: {e}")

    def add_portrait(self):
        """按钮添加立绘 (支持多选)"""
        if not self.current_char_id:
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择立绘图片", "", "Images (*.png *.jpg *.jpeg)"
        )
        if not paths:
            return

        target_dir = os.path.join(self.char_root, "portrait")
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)

        count = 0
        for path in paths:
            try:
                shutil.copy(path, target_dir)
                count += 1
            except Exception as e:
                print(f"Copy failed: {e}")

        if count > 0:
            self.refresh_asset_lists()
            QMessageBox.information(self, "成功", f"已添加 {count} 张立绘")

    def add_background(self):
        """按钮添加背景 (单张强制替换)"""
        if not self.current_char_id:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "选择背景图片", "", "Images (*.png *.jpg *.jpeg)"
        )
        if not path:
            return

        target_dir = os.path.join(self.char_root, "background")
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)

        # 检查是否已有背景
        existing = [f for f in os.listdir(target_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        if existing:
            reply = QMessageBox.question(
                self, "替换确认",
                "当前角色已有背景图片，是否删除旧图片并替换？\n(背景图只能有一张)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

            # 删除旧图
            for f in existing:
                try:
                    os.remove(os.path.join(target_dir, f))
                except Exception:
                    pass

        try:
            shutil.copy(path, target_dir)
            self.refresh_asset_lists()
            # 自动选中新背景
            new_name = os.path.basename(path)
            self.config.setdefault("layout", {})["current_background"] = new_name
            self.rebuild_scene()
            QMessageBox.information(self, "成功", "背景已替换")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"添加失败: {e}")

    def select_dialog_box(self):
        """选择对话框 (单张替换 + 自动贴底)"""
        if not self.current_char_id:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "选择对话框图片", "", "Images (*.png *.jpg *.jpeg)"
        )
        if not path:
            return

        # 检查替换
        current_box = self.config.get("assets", {}).get("dialog_box")
        if current_box and os.path.exists(os.path.join(self.char_root, current_box)):
            reply = QMessageBox.question(
                self, "替换确认",
                f"当前已有对话框 '{current_box}'，是否替换？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        try:
            target_name = os.path.basename(path)
            target_path = os.path.join(self.char_root, target_name)
            shutil.copy(path, target_path)

            # 更新配置
            self.config.setdefault("assets", {})["dialog_box"] = target_name

            # --- 自动计算贴底坐标 ---
            canvas_w, canvas_h = CanvasConfig.get_size()
            pix = QPixmap(target_path)
            if not pix.isNull():
                scale = canvas_w / pix.width()
                scaled_h = pix.height() * scale
                new_y = int(canvas_h - scaled_h)
                self.config.setdefault("layout", {})["box_pos"] = [0, new_y]
                print(f"Auto-positioned box at Y={new_y}")

            self.rebuild_scene()
            QMessageBox.information(self, "成功", "对话框已更换并自动贴底")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"操作失败: {e}")

    def delete_asset_file(self, filename: str, asset_type: str):
        """右键删除文件"""
        if not self.current_char_id:
            return

        reply = QMessageBox.question(
            self, "删除确认",
            f"确定要永久删除文件 '{filename}' 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        file_path = os.path.join(self.char_root, asset_type, filename)
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                self.refresh_asset_lists()

                # 如果删除的是当前正在用的，重置配置
                layout = self.config.get("layout", {})
                if asset_type == "portrait" and layout.get("current_portrait") == filename:
                    layout["current_portrait"] = ""
                elif asset_type == "background" and layout.get("current_background") == filename:
                    layout["current_background"] = ""

                self.rebuild_scene()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"删除失败: {e}")

    # =========================================================================
    # 角色操作
    # =========================================================================

    def create_new_character(self):
        dialog = NewCharacterDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            char_id, char_name = dialog.get_data()

            if not char_id:
                QMessageBox.warning(self, "错误", "角色ID不能为空")
                return

            if not re.match(r'^[a-zA-Z0-9_]+$', char_id):
                QMessageBox.warning(self, "错误", "角色ID只能包含字母、数字和下划线")
                return

            new_root = os.path.join(BASE_PATH, "characters", char_id)
            if os.path.exists(new_root):
                QMessageBox.warning(self, "错误", f"角色ID '{char_id}' 已存在")
                return

            try:
                os.makedirs(os.path.join(new_root, "portrait"))
                os.makedirs(os.path.join(new_root, "background"))

                canvas_w, canvas_h = CanvasConfig.get_size()
                default_style = normalize_style({
                    "basic": {
                        "text_color": [255, 255, 255],
                        "name_color": [255, 0, 255],
                        "font_size": 45,
                        "name_font_size": 45
                    }
                })
                canvas_size = CanvasConfig.get_size()
                default_config = {
                    "meta": {"name": char_name or char_id, "id": char_id},
                    "assets": {"dialog_box": "textbox_bg.png"},
                    "style": default_style,
                    "layout": {
                        "stand_pos": [0, 0],
                        "stand_scale": 1.0,
                        "box_pos": [0, canvas_h - 200],
                        "text_area": [100, 800, 1800, 1000],
                        "name_pos": [100, 100],
                        "stand_on_top": False,
                        "_canvas_size": [canvas_size[0], canvas_size[1]],
                    }
                }

                with open(os.path.join(new_root, "config.yaml"), "w", encoding="utf-8") as f:
                    dump_yaml_inline(default_config, f)

                QMessageBox.information(
                    self, "成功",
                    f"角色 '{char_name}' 创建成功！\n请在资源库中添加立绘和背景。"
                )

                self._load_initial_data()
                index = self.assets_panel.combo_char.findText(char_id)
                if index >= 0:
                    self.assets_panel.combo_char.setCurrentIndex(index)

            except Exception as e:
                QMessageBox.critical(self, "错误", f"创建失败: {e}")

    def open_character_folder(self):
        if self.char_root and os.path.exists(self.char_root):
            os.startfile(self.char_root)

    def reload_current_character(self):
        if self.current_char_id:
            self.on_character_changed(self.assets_panel.combo_char.currentIndex())

    def sync_all_configs(self):
        """同步/修复配置的具体实现"""
        try:
            char_dir = os.path.join(BASE_PATH, "characters")
            if not os.path.exists(char_dir):
                return

            count = 0
            for char_id in os.listdir(char_dir):
                root = os.path.join(char_dir, char_id)
                if not os.path.isdir(root):
                    continue

                yaml_path = os.path.join(root, "config.yaml")
                legacy_path = os.path.join(root, "config.json")
                cfg_path = yaml_path if os.path.exists(yaml_path) else legacy_path
                if not os.path.exists(cfg_path):
                    continue

                try:
                    with open(cfg_path, 'r', encoding='utf-8') as f:
                        if cfg_path.endswith(('.yaml', '.yml')):
                            data = yaml.safe_load(f) or {}
                        else:
                            data = json.load(f)
                except Exception:
                    continue

                modified = False
                normalized_style = normalize_style(data.get("style"))
                if data.get("style") != normalized_style:
                    data["style"] = normalized_style
                    modified = True
                layout = data.get("layout", {})
                assets = data.get("assets", {})

                # 1. 检查立绘是否存在
                p = layout.get("current_portrait")
                if p and not os.path.exists(os.path.join(root, "portrait", p)):
                    layout["current_portrait"] = ""
                    modified = True

                # 2. 检查背景是否存在
                bg = layout.get("current_background")
                if bg:
                    p1 = os.path.join(root, "background", bg)
                    p2 = os.path.join(BASE_PATH, "common", "background", bg)
                    if not os.path.exists(p1) and not os.path.exists(p2):
                        layout["current_background"] = ""
                        modified = True

                # 3. 检查对话框是否存在
                box = assets.get("dialog_box")
                if box and not os.path.exists(os.path.join(root, box)):
                    assets["dialog_box"] = "textbox_bg.png"
                    modified = True

                if modified or cfg_path != yaml_path:
                    with open(yaml_path, 'w', encoding='utf-8') as f:
                        dump_yaml_inline(data, f)
                    count += 1

            QMessageBox.information(self, "完成", f"已检查所有角色，修复了 {count} 个配置文件。")
            self.reload_current_character()

        except Exception as e:
            QMessageBox.critical(self, "错误", f"同步失败: {e}")

    # =========================================================================
    # 配置保存与采集
    # =========================================================================

    def _collect_scene_data(self):
        """从 Scene 采集位置/缩放数据"""
        layout = self.config.setdefault("layout", {})
        canvas_w, canvas_h = CanvasConfig.get_size()

        if self.scene_items["portrait"]:
            item = self.scene_items["portrait"]
            layout["stand_pos"] = [int(item.x()), int(item.y())]
            layout["stand_scale"] = round(item.scale(), 3)

        if self.scene_items["box"]:
            item = self.scene_items["box"]
            layout["box_pos"] = [int(item.x()), int(item.y())]

        if isinstance(self.scene_items["name_text"], ResizableTextItem):
            item = self.scene_items["name_text"]
            top_left = item.mapToScene(item.rect().topLeft())
            layout["name_pos"] = [int(top_left.x()), int(top_left.y())]

        if isinstance(self.scene_items["main_text"], ResizableTextItem):
            item = self.scene_items["main_text"]
            rect = item.rect()
            p1 = item.mapToScene(rect.topLeft())
            p2 = item.mapToScene(rect.bottomRight())
            x1, y1 = int(p1.x()), int(p1.y())
            x2, y2 = int(p2.x()), int(p2.y())
            layout["text_area"] = [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]

        layout["_canvas_size"] = [canvas_w, canvas_h]

    def save_config(self):
        if not self.current_char_id:
            return

        self._collect_scene_data()
        self._ensure_style()

        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                dump_yaml_inline(self.config, f)
            statusBar = self.statusBar()
            if not statusBar:
               raise RuntimeError("Status bar is not available") 
            statusBar.showMessage(f"已保存: {self.current_char_id}", 3000)
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))

    # =========================================================================
    # 渲染与缓存
    # =========================================================================

    def generate_cache(self):
        self._run_generate_cache(show_message=True)

    def _run_generate_cache(self, show_message: bool = True) -> bool:
        if prebuild_character is None or not self.current_char_id:
            QMessageBox.warning(self, "错误", "无法调用预处理模块")
            return False

        self.save_config()
        cache_dir = os.path.join(BASE_PATH, "cache")
        dialog = PrebuildProgressDialog(self, self.current_char_id, BASE_PATH, cache_dir)
        dialog.exec()

        if dialog.success:
            self.cache_outdated = False
            self.resolution_prompted = False
            if show_message:
                QMessageBox.information(self, "完成", "缓存生成完毕")
            return True
        return False

    def preview_render(self):
        if CharacterRenderer is None or not self.current_char_id:
            return

        if self.cache_outdated and not self.resolution_prompted:
            reply = QMessageBox.question(
                self,
                "是否重新生成缓存？",
                "检测到画布分辨率已更改，是否现在重新生成缓存？",
            )
            self.resolution_prompted = True
            if reply == QMessageBox.StandardButton.Yes:
                if not self._run_generate_cache(show_message=False):
                    return

        self.save_config()
        text, ok = QInputDialog.getText(self, "渲染预览", "输入测试台词:")
        if ok and text:
            try:
                renderer = CharacterRenderer(self.current_char_id, BASE_PATH)
                p_key = os.path.splitext(
                    self.config["layout"].get("current_portrait", "")
                )[0]
                bg_key = os.path.splitext(
                    self.config["layout"].get("current_background", "")
                )[0]

                try:
                    pil_img = renderer.render(text, portrait_key=p_key, bg_key=bg_key)
                except Exception:
                    # 缓存可能损坏，尝试重建
                    prebuild_character(
                        self.current_char_id,
                        BASE_PATH,
                        os.path.join(BASE_PATH, "cache"),
                        force=True
                    )
                    self.cache_outdated = False
                    self.resolution_prompted = False
                    renderer = CharacterRenderer(self.current_char_id, BASE_PATH)
                    pil_img = renderer.render(text, portrait_key=p_key, bg_key=bg_key)

                pil_img.show()
            except Exception as e:
                QMessageBox.critical(self, "渲染失败", str(e))
