
import os
import json
import shutil
import re
from typing import Dict, Any, Optional, Tuple

from PyQt6.QtWidgets import (
    QMainWindow, QGraphicsScene, QGraphicsView, QGraphicsPixmapItem,
    QDockWidget, QMessageBox, QFileDialog, QInputDialog, QDialog
)
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPixmap, QPen, QBrush, QColor, QPainter, QFont, QFontDatabase, QAction

from .constants import (
    BASE_PATH, CanvasConfig, COMMON_RESOLUTIONS,
    Z_BG, Z_PORTRAIT_BOTTOM, Z_BOX, Z_PORTRAIT_TOP, Z_TEXT,
    load_global_config, save_global_config, normalize_layout,
    CharacterRenderer, prebuild_character
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

        self.scene_items = {
            "bg": None,
            "portrait": None,
            "box": None,
            "name_text": None,
            "main_text": None
        }

        self.custom_font_family = ""
        self.cache_outdated = False
        self.resolution_prompted = False

        # --- 初始化 ---
        self._load_custom_font()
        self._init_ui()
        self._connect_signals()
        self._load_initial_data()

    # =========================================================================
    # 初始化
    # =========================================================================

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

        # 文件菜单
        file_menu = menubar.addMenu("文件 (&File)")

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
        action_exit = QAction("退出", self)
        action_exit.triggered.connect(self.close)
        file_menu.addAction(action_exit)

        # 工具菜单
        tools_menu = menubar.addMenu("工具 (&Tools)")

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
        canvas_w, canvas_h = CanvasConfig.get_size()
        default_cfg = {
            "meta": {"name": self.current_char_id},
            "style": {"font_size": 45, "text_color": [255, 255, 255], "name_color": [255, 0, 255]},
            "layout": {"stand_scale": 1.0, "stand_on_top": False},
            "assets": {"dialog_box": "textbox_bg.png"}
        }

        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    self.config = self._merge_dicts(default_cfg, loaded)
            except Exception as e:
                print(f"Config load error: {e}")
                self.config = default_cfg
        else:
            self.config = default_cfg

        layout = self.config.setdefault("layout", {})
        normalized = normalize_layout(layout, (canvas_w, canvas_h))
        normalized["_canvas_size"] = [canvas_w, canvas_h]
        self.config["layout"] = normalized

    def _merge_dicts(self, base, update):
        for k, v in update.items():
            if isinstance(v, dict) and k in base:
                self._merge_dicts(base[k], v)
            else:
                base[k] = v
        return base

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
        style = self.config.get("style", {})
        layout = self.config.get("layout", {})

        pp = self.props_panel
        ap = self.assets_panel

        pp.edit_name.blockSignals(True)
        pp.edit_name.setText(meta.get("name", ""))
        pp.edit_name.blockSignals(False)

        pp.spin_font_size.blockSignals(True)
        pp.spin_font_size.setValue(int(style.get("font_size", 45)))
        pp.spin_font_size.blockSignals(False)

        pp.spin_name_size.blockSignals(True)
        pp.spin_name_size.setValue(int(style.get("name_font_size", 45)))
        pp.spin_name_size.blockSignals(False)

        pp.btn_text_color.set_color(style.get("text_color", [255, 255, 255]))
        pp.btn_name_color.set_color(style.get("name_color", [255, 0, 255]))

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
        self.scene.clear()

        canvas_w, canvas_h = CanvasConfig.get_size()

        # 背景矩形
        self.scene.addRect(
            0, 0, canvas_w, canvas_h,
            QPen(Qt.GlobalColor.black),
            QBrush(Qt.GlobalColor.white)
        ).setZValue(Z_BG)

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
                item = QGraphicsPixmapItem(pix)
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

            item = QGraphicsPixmapItem(pix)
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
        style = self.config.get("style", {})
        meta = self.config.get("meta", {})

        # 名字文本
        name_pos = layout.get("name_pos", [100, 100])
        name_color = style.get("name_color", [255, 0, 255])
        name_size = style.get("name_font_size", 45)
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

        # 正文文本
        text_area = layout.get("text_area", [100, 800, 1800, 1000])
        text_color = style.get("text_color", [255, 255, 255])
        text_size = style.get("font_size", 45)

        w = text_area[2] - text_area[0]
        h = text_area[3] - text_area[1]
        text_item = ResizableTextItem(
            QRectF(0, 0, w, h),
            "预览文本区域\n拖动调整位置",
            text_color,
            text_size,
            font_family=self.custom_font_family
        )
        text_item.setPos(text_area[0], text_area[1])
        text_item.setZValue(Z_TEXT)
        self.scene.addItem(text_item)
        self.scene_items["main_text"] = text_item

        self.fit_view()

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
        self.config_path = os.path.join(self.char_root, "config.json")

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
        if self.scene_items["name_text"]:
            self.scene_items["name_text"].update_content(text=text)

    def on_style_changed(self):
        pp = self.props_panel
        style = self.config.setdefault("style", {})

        style["font_size"] = pp.spin_font_size.value()
        style["name_font_size"] = pp.spin_name_size.value()
        style["text_color"] = pp.btn_text_color.current_color
        style["name_color"] = pp.btn_name_color.current_color

        if self.scene_items["main_text"]:
            self.scene_items["main_text"].update_content(
                size=style["font_size"],
                color=style["text_color"]
            )
        if self.scene_items["name_text"]:
            self.scene_items["name_text"].update_content(
                size=style["name_font_size"],
                color=style["name_color"]
            )

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

        try:
            cfg = load_global_config()
        except Exception:
            cfg = {}
        render_cfg = cfg.setdefault("render", {})
        render_cfg["canvas_size"] = [size[0], size[1]]
        try:
            save_global_config(cfg)
        except Exception as exc:
            print(f"保存全局分辨率失败: {exc}")

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
                default_config = {
                    "meta": {"name": char_name or char_id, "id": char_id},
                    "assets": {"dialog_box": "textbox_bg.png"},
                    "style": {
                        "text_color": [255, 255, 255],
                        "name_color": [255, 0, 255],
                        "font_size": 45,
                        "name_font_size": 45
                    },
                    "layout": {
                        "stand_pos": [0, 0],
                        "stand_scale": 1.0,
                        "box_pos": [0, canvas_h - 200],
                        "text_area": [100, 800, 1800, 1000],
                        "name_pos": [100, 100],
                        "stand_on_top": False
                    }
                }

                with open(os.path.join(new_root, "config.json"), "w", encoding="utf-8") as f:
                    json.dump(default_config, f, ensure_ascii=False, indent=4)

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

                cfg_path = os.path.join(root, "config.json")
                if not os.path.exists(cfg_path):
                    continue

                try:
                    with open(cfg_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except Exception:
                    continue

                modified = False
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

                if modified:
                    with open(cfg_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=4)
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

        if self.scene_items["name_text"]:
            item = self.scene_items["name_text"]
            top_left = item.mapToScene(item.rect().topLeft())
            layout["name_pos"] = [int(top_left.x()), int(top_left.y())]

        if self.scene_items["main_text"]:
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

        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
            self.statusBar().showMessage(f"已保存: {self.current_char_id}", 3000)
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
