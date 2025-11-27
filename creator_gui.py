import sys
import os
import json
import shutil
from io import BytesIO
from typing import Dict, List, Optional

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QMessageBox,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsItem,
    QCheckBox,
    QSpinBox,
    QComboBox,
    QInputDialog,
    QFileDialog,
    QLineEdit,
    QDialog,
)
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPixmap, QColor, QPen, QBrush, QFont, QImage, QAction, QPainter


BASE_PATH = "assets"
CANVAS_W, CANVAS_H = 2560, 1440

Z_BG = 0
Z_PORTRAIT_BOTTOM = 10
Z_BOX = 20
Z_PORTRAIT_TOP = 25
Z_TEXT = 30


class ResizableTextItem(QGraphicsRectItem):
    """Simple draggable text preview rect."""

    def __init__(self, rect: QRectF, text: str, color: QColor, font_size: int = 40):
        super().__init__(rect)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setAcceptHoverEvents(True)

        self.preview_text = text
        self.color = color
        self.font_size = font_size

    def set_preview_text(self, text: str) -> None:
        self.preview_text = text
        self.update()

    def set_font_size(self, size: int) -> None:
        self.font_size = max(6, min(int(size), 400))
        self.update()

    def paint(self, painter: QPainter, option, widget=None) -> None:  # type: ignore[override]
        pen_color = QColor(0, 170, 255) if self.isSelected() else QColor(120, 120, 120)
        painter.setPen(QPen(pen_color, 2, Qt.PenStyle.DashLine))
        painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        painter.drawRect(self.rect())

        painter.setPen(QPen(self.color))
        font = QFont()
        font.setPointSize(self.font_size)
        painter.setFont(font)
        margin = 6
        text_rect = self.rect().adjusted(margin, margin, -margin, -margin)
        painter.drawText(text_rect, Qt.TextFlag.TextWordWrap, self.preview_text)


class ScalableImageItem(QGraphicsPixmapItem):
    """Movable pixmap item with wheel-to-scale."""

    def __init__(self, pixmap: QPixmap, label: str):
        super().__init__(pixmap)
        self.label = label
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        factor = 1.1 if event.angleDelta().y() > 0 else 0.9
        self.setScale(max(0.1, min(self.scale() * factor, 10.0)))


class EditorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Box-of-GalGame-Sister 配置器")
        self.resize(1400, 900)

        self.current_char_id: Optional[str] = None
        self.current_background_name: Optional[str] = None
        self.config: Dict[str, object] = {}
        self.char_root: str = ""
        self.config_path: str = ""

        self.scene = QGraphicsScene(0, 0, CANVAS_W, CANVAS_H, self)

        self._build_ui()
        self.load_characters()

    # -----------------
    # UI
    # -----------------
    def _build_ui(self) -> None:
        central = QWidget()
        main_layout = QHBoxLayout(central)

        self.view = QGraphicsView(self.scene)
        self.view.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        main_layout.addWidget(self.view, stretch=3)

        sidebar = QVBoxLayout()

        # Character selection
        row_char = QHBoxLayout()
        row_char.addWidget(QLabel("角色:"))
        self.combo_character = QComboBox()
        self.combo_character.currentIndexChanged.connect(self.on_character_changed)
        row_char.addWidget(self.combo_character)
        sidebar.addLayout(row_char)

        # Name edit
        self.edit_char_name = QLineEdit()
        self.edit_char_name.setPlaceholderText("显示名称")
        self.edit_char_name.textChanged.connect(self.update_character_name)
        sidebar.addWidget(self.edit_char_name)

        # Portrait switch
        row_portrait = QHBoxLayout()
        row_portrait.addWidget(QLabel("立绘:"))
        self.combo_portrait = QComboBox()
        self.combo_portrait.currentTextChanged.connect(self.switch_portrait)
        row_portrait.addWidget(self.combo_portrait)
        sidebar.addLayout(row_portrait)

        # Font sizes
        row_font_text = QHBoxLayout()
        row_font_text.addWidget(QLabel("正文字号"))
        self.spin_font_text = QSpinBox()
        self.spin_font_text.setRange(10, 200)
        self.spin_font_text.valueChanged.connect(self.update_font_size_text)
        row_font_text.addWidget(self.spin_font_text)
        sidebar.addLayout(row_font_text)

        row_font_name = QHBoxLayout()
        row_font_name.addWidget(QLabel("名字字号"))
        self.spin_font_name = QSpinBox()
        self.spin_font_name.setRange(10, 200)
        self.spin_font_name.valueChanged.connect(self.update_font_size_name)
        row_font_name.addWidget(self.spin_font_name)
        sidebar.addLayout(row_font_name)

        self.check_layer = QCheckBox("立绘覆盖对话框")
        self.check_layer.stateChanged.connect(lambda: self.update_layer_order(self.check_layer.isChecked()))
        sidebar.addWidget(self.check_layer)

        # Buttons
        btn_row_top = QHBoxLayout()
        btn_reload = QPushButton("重新加载")
        btn_reload.clicked.connect(self.reload_all)
        btn_row_top.addWidget(btn_reload)
        btn_open = QPushButton("打开角色目录")
        btn_open.clicked.connect(self.open_character_folder)
        btn_row_top.addWidget(btn_open)
        sidebar.addLayout(btn_row_top)

        btn_row_mid = QHBoxLayout()
        btn_save = QPushButton("保存配置")
        btn_save.clicked.connect(self.save_config)
        btn_row_mid.addWidget(btn_save)
        btn_preview = QPushButton("预览生成")
        btn_preview.clicked.connect(self.preview_render)
        btn_row_mid.addWidget(btn_preview)
        sidebar.addLayout(btn_row_mid)

        btn_row_cache = QHBoxLayout()
        btn_cache = QPushButton("生成缓存")
        btn_cache.clicked.connect(self.generate_cache)
        btn_row_cache.addWidget(btn_cache)
        btn_check = QPushButton("资源体检")
        btn_check.clicked.connect(self.check_resources)
        btn_row_cache.addWidget(btn_check)
        sidebar.addLayout(btn_row_cache)

        btn_row_add = QHBoxLayout()
        btn_add_portrait = QPushButton("添加立绘")
        btn_add_portrait.clicked.connect(lambda: self.add_asset("portrait"))
        btn_row_add.addWidget(btn_add_portrait)
        btn_add_bg = QPushButton("添加背景")
        btn_add_bg.clicked.connect(lambda: self.add_asset("background"))
        btn_row_add.addWidget(btn_add_bg)
        sidebar.addLayout(btn_row_add)

        btn_dialog = QPushButton("选择对话框底图")
        btn_dialog.clicked.connect(self.select_dialog_box)
        sidebar.addWidget(btn_dialog)

        sidebar.addStretch(1)

        main_layout.addLayout(sidebar, stretch=2)
        self.setCentralWidget(central)

        # Menu action for reload
        reload_action = QAction("重新加载", self)
        reload_action.setShortcut("Ctrl+R")
        reload_action.triggered.connect(self.reload_all)
        self.addAction(reload_action)

    # -----------------
    # Data loading
    # -----------------
    def load_characters(self) -> None:
        characters_dir = os.path.join(BASE_PATH, "characters")
        chars = []
        if os.path.exists(characters_dir):
            chars = [d for d in os.listdir(characters_dir) if os.path.isdir(os.path.join(characters_dir, d))]
        self.combo_character.blockSignals(True)
        self.combo_character.clear()
        if chars:
            chars.sort()
            self.combo_character.addItems(chars)
            self.current_char_id = chars[0]
            self.char_root = os.path.join(characters_dir, self.current_char_id)
            self.config_path = os.path.join(self.char_root, "config.json")
            self.combo_character.blockSignals(False)
            self.on_character_changed(0)
        else:
            self.combo_character.addItem("<无角色>")
            self.combo_character.blockSignals(False)
            QMessageBox.warning(self, "提示", "请在 assets/characters/ 下放置角色资源后再打开配置器。")

    def on_character_changed(self, index: int) -> None:  # noqa: ARG002
        char_id = self.combo_character.currentText()
        if not char_id or char_id == "<无角色>":
            return
        self.current_char_id = char_id
        self.char_root = os.path.join(BASE_PATH, "characters", char_id)
        self.config_path = os.path.join(self.char_root, "config.json")
        self.load_config()
        self.reload_ui_from_config()
        self.load_assets_to_scene()

    def load_config(self) -> None:
        default_cfg: Dict[str, object] = {
            "assets": {"dialog_box": "textbox_bg.png"},
            "layout": {
                "stand_pos": [0, 0],
                "stand_scale": 1.0,
                "box_pos": [0, CANVAS_H - 200],
                "text_area": [100, 800, 1800, 1000],
                "name_pos": [100, 100],
                "stand_on_top": False,
            },
            "style": {
                "font_size": 45,
                "name_font_size": 45,
                "text_color": [0, 0, 255],
                "name_color": [255, 0, 255],
            },
            "meta": {"name": self.current_char_id or "角色"},
        }

        loaded: Dict[str, object] = {}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
            except Exception as e:  # noqa: BLE001
                QMessageBox.warning(self, "警告", f"读取配置失败，将使用默认配置。\n{e}")

        self.config = self._merge_dict(default_cfg, loaded)
        layout = self.config.get("layout", {})  # type: ignore[assignment]
        self.current_background_name = layout.get("current_background") if isinstance(layout, dict) else None

    def _merge_dict(self, base: Dict[str, object], override: Dict[str, object]) -> Dict[str, object]:
        result: Dict[str, object] = dict(base)
        for k, v in override.items():
            if isinstance(v, dict) and isinstance(result.get(k), dict):
                result[k] = self._merge_dict(result[k], v)  # type: ignore[arg-type]
            else:
                result[k] = v
        return result

    def reload_ui_from_config(self) -> None:
        style = self.config.get("style", {})  # type: ignore[assignment]
        layout = self.config.get("layout", {})  # type: ignore[assignment]
        meta = self.config.get("meta", {})  # type: ignore[assignment]

        if isinstance(style, dict):
            self.spin_font_text.blockSignals(True)
            self.spin_font_text.setValue(int(style.get("font_size", 45)))
            self.spin_font_text.blockSignals(False)

            self.spin_font_name.blockSignals(True)
            self.spin_font_name.setValue(int(style.get("name_font_size", style.get("font_size", 45))))
            self.spin_font_name.blockSignals(False)

        if isinstance(layout, dict):
            self.check_layer.blockSignals(True)
            self.check_layer.setChecked(bool(layout.get("stand_on_top", False)))
            self.check_layer.blockSignals(False)

        if isinstance(meta, dict):
            self.edit_char_name.blockSignals(True)
            self.edit_char_name.setText(str(meta.get("name", self.current_char_id or "")))
            self.edit_char_name.blockSignals(False)

    # -----------------
    # Scene rendering
    # -----------------
    def load_assets_to_scene(self) -> None:
        self.scene.clear()

        bg_rect = self.scene.addRect(0, 0, CANVAS_W, CANVAS_H, QPen(Qt.GlobalColor.black), QBrush(Qt.GlobalColor.white))
        bg_rect.setZValue(Z_BG)

        layout = self.config.get("layout", {}) if isinstance(self.config.get("layout"), dict) else {}
        style = self.config.get("style", {}) if isinstance(self.config.get("style"), dict) else {}
        assets_cfg = self.config.get("assets", {}) if isinstance(self.config.get("assets"), dict) else {}

        # Background
        bg_candidates: List[str] = []
        char_bg_dir = os.path.join(self.char_root, "background")
        common_bg_dir = os.path.join(BASE_PATH, "common", "background")
        for folder in [char_bg_dir, common_bg_dir]:
            if os.path.exists(folder):
                bg_candidates.extend(
                    [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
                )

        self.bg_item = None
        selected_bg = None
        if bg_candidates:
            if self.current_background_name:
                for path in bg_candidates:
                    if os.path.basename(path) == self.current_background_name:
                        selected_bg = path
                        break
            if selected_bg is None:
                selected_bg = bg_candidates[0]
            bg_pixmap = QPixmap(selected_bg).scaled(
                CANVAS_W,
                CANVAS_H,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.bg_item = QGraphicsPixmapItem(bg_pixmap)
            self.bg_item.setZValue(Z_BG)
            self.scene.addItem(self.bg_item)
            self.current_background_name = os.path.basename(selected_bg)

        # Portraits
        portrait_dir = os.path.join(self.char_root, "portrait")
        portraits = []
        if os.path.exists(portrait_dir):
            portraits = [f for f in os.listdir(portrait_dir) if f.lower().endswith((".png", ".jpg", ".jpeg"))]

        self.combo_portrait.blockSignals(True)
        self.combo_portrait.clear()
        if portraits:
            portraits.sort()
            self.combo_portrait.addItems(portraits)
        self.combo_portrait.blockSignals(False)

        self.portrait_item: Optional[ScalableImageItem] = None
        if portraits:
            current_portrait = layout.get("current_portrait") if isinstance(layout, dict) else None
            if not current_portrait or current_portrait not in portraits:
                current_portrait = portraits[0]
            self.combo_portrait.setCurrentText(current_portrait)
            portrait_file = os.path.join(portrait_dir, current_portrait)
            self._load_portrait_item(portrait_file)

        # Dialog box
        self.box_item = None
        dialog_box = assets_cfg.get("dialog_box", "textbox_bg.png") if isinstance(assets_cfg, dict) else "textbox_bg.png"
        box_path = os.path.join(self.char_root, dialog_box)
        if os.path.exists(box_path):
            box_pixmap = QPixmap(box_path)
            if box_pixmap.width() != CANVAS_W:
                new_h = int(box_pixmap.height() * (CANVAS_W / box_pixmap.width()))
                box_pixmap = box_pixmap.scaled(CANVAS_W, new_h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            box_pos = (0, CANVAS_H - box_pixmap.height())
            layout.setdefault("box_pos", [box_pos[0], box_pos[1]])
            self.box_item = QGraphicsPixmapItem(box_pixmap)
            self.box_item.setPos(float(box_pos[0]), float(box_pos[1]))
            self.box_item.setZValue(Z_BOX)
            self.box_item.setOpacity(0.9)
            self.scene.addItem(self.box_item)

        # Text & name preview
        name_pos = layout.get("name_pos", [100, 100]) if isinstance(layout, dict) else [100, 100]
        text_area = layout.get("text_area", [100, 800, 1800, 1000]) if isinstance(layout, dict) else [100, 800, 1800, 1000]

        text_font_size = int(style.get("font_size", 45)) if isinstance(style, dict) else 45
        name_font_size = int(style.get("name_font_size", text_font_size)) if isinstance(style, dict) else text_font_size
        text_color = style.get("text_color", [0, 0, 255]) if isinstance(style, dict) else [0, 0, 255]
        name_color = style.get("name_color", [255, 0, 255]) if isinstance(style, dict) else [255, 0, 255]
        meta = self.config.get("meta", {}) if isinstance(self.config.get("meta"), dict) else {}
        char_name = meta.get("name", self.current_char_id or "") if isinstance(meta, dict) else (self.current_char_id or "")

        self.name_rect = ResizableTextItem(QRectF(0, 0, 320, 80), str(char_name), QColor(*name_color), name_font_size)
        self.name_rect.setPos(float(name_pos[0]), float(name_pos[1]))
        self.name_rect.setZValue(Z_TEXT)
        self.scene.addItem(self.name_rect)

        x1, y1, x2, y2 = text_area
        w, h = max(20, x2 - x1), max(20, y2 - y1)
        sample_text = "这里是对话内容的预览区域，拖拽矩形或调整字号使其贴合对话框。"
        self.text_rect = ResizableTextItem(QRectF(0, 0, w, h), sample_text, QColor(*text_color), text_font_size)
        self.text_rect.setPos(float(x1), float(y1))
        self.text_rect.setZValue(Z_TEXT)
        self.scene.addItem(self.text_rect)

        self.update_layer_order(layout.get("stand_on_top", False) if isinstance(layout, dict) else False)
        self.fit_view()

    def _load_portrait_item(self, portrait_path: str) -> None:
        if not os.path.exists(portrait_path):
            return
        pixmap = QPixmap(portrait_path)
        layout = self.config.get("layout", {}) if isinstance(self.config.get("layout"), dict) else {}
        stand_pos = layout.get("stand_pos", [0, 0]) if isinstance(layout, dict) else [0, 0]
        stand_scale = float(layout.get("stand_scale", 1.0)) if isinstance(layout, dict) else 1.0

        if hasattr(self, "portrait_item") and self.portrait_item:
            self.scene.removeItem(self.portrait_item)

        self.portrait_item = ScalableImageItem(pixmap, "Portrait")
        self.portrait_item.setPos(float(stand_pos[0]), float(stand_pos[1]))
        self.portrait_item.setScale(stand_scale)
        self.scene.addItem(self.portrait_item)
        self.update_layer_order(self.check_layer.isChecked())

    def fit_view(self) -> None:
        self.view.resetTransform()
        view_w = max(1, self.view.viewport().width() - 20)
        view_h = max(1, self.view.viewport().height() - 20)
        scale_w = view_w / CANVAS_W
        scale_h = view_h / CANVAS_H
        scale = min(scale_w, scale_h)
        self.view.scale(scale, scale)

    def update_layer_order(self, stand_on_top: bool) -> None:
        if hasattr(self, "portrait_item") and self.portrait_item:
            self.portrait_item.setZValue(Z_PORTRAIT_TOP if stand_on_top else Z_PORTRAIT_BOTTOM)
        if hasattr(self, "box_item") and self.box_item:
            self.box_item.setZValue(Z_BOX)
        self.scene.update()

    # -----------------
    # UI events
    # -----------------
    def switch_portrait(self, filename: str) -> None:
        if not filename:
            return
        portrait_dir = os.path.join(self.char_root, "portrait")
        portrait_path = os.path.join(portrait_dir, filename)
        self.config.setdefault("layout", {})["current_portrait"] = filename  # type: ignore[index]
        self._load_portrait_item(portrait_path)

    def update_font_size_text(self, value: int) -> None:
        self.config.setdefault("style", {})["font_size"] = int(value)  # type: ignore[index]
        if hasattr(self, "text_rect"):
            self.text_rect.set_font_size(int(value))

    def update_font_size_name(self, value: int) -> None:
        self.config.setdefault("style", {})["name_font_size"] = int(value)  # type: ignore[index]
        if hasattr(self, "name_rect"):
            self.name_rect.set_font_size(int(value))

    def update_character_name(self, name_text: str) -> None:
        self.config.setdefault("meta", {})["name"] = name_text  # type: ignore[index]
        if hasattr(self, "name_rect"):
            display_name = name_text or (self.current_char_id or "")
            self.name_rect.set_preview_text(display_name)

    # -----------------
    # Asset operations
    # -----------------
    def add_asset(self, category: str) -> None:
        if not self.current_char_id:
            return
        folder = os.path.join(self.char_root, category)
        os.makedirs(folder, exist_ok=True)
        file_filter = "Images (*.png *.jpg *.jpeg)"
        path, _ = QFileDialog.getOpenFileName(self, "选择图片", "", file_filter)
        if not path:
            return
        try:
            shutil.copy(path, folder)
            QMessageBox.information(self, "完成", f"已添加到 {folder}")
            self.load_assets_to_scene()
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "错误", f"复制失败: {e}")

    def select_dialog_box(self) -> None:
        if not self.current_char_id:
            return
        folder = self.char_root
        os.makedirs(folder, exist_ok=True)
        path, _ = QFileDialog.getOpenFileName(self, "选择对话框底图", "", "Images (*.png *.jpg *.jpeg)")
        if not path:
            return
        target = os.path.join(folder, os.path.basename(path))
        try:
            shutil.copy(path, target)
            assets_cfg = self.config.setdefault("assets", {})  # type: ignore[assignment]
            assets_cfg["dialog_box"] = os.path.basename(path)
            self.save_config(show_message=False)
            self.load_assets_to_scene()
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "错误", f"复制失败: {e}")

    # -----------------
    # Actions
    # -----------------
    def _collect_config_from_ui(self) -> None:
        layout = self.config.setdefault("layout", {})  # type: ignore[assignment]
        style = self.config.setdefault("style", {})  # type: ignore[assignment]
        meta = self.config.setdefault("meta", {})  # type: ignore[assignment]

        if hasattr(self, "portrait_item") and self.portrait_item:
            pos = self.portrait_item.pos()
            layout["stand_pos"] = [int(pos.x()), int(pos.y())]
            layout["stand_scale"] = round(self.portrait_item.scale(), 3)
            layout["current_portrait"] = self.combo_portrait.currentText()

        if hasattr(self, "box_item") and self.box_item:
            pos = self.box_item.pos()
            layout["box_pos"] = [int(pos.x()), int(pos.y())]

        if hasattr(self, "name_rect"):
            n_pos = self.name_rect.pos()
            layout["name_pos"] = [int(n_pos.x()), int(n_pos.y())]

        if hasattr(self, "text_rect"):
            t_pos = self.text_rect.pos()
            rect = self.text_rect.rect()
            x1 = int(t_pos.x())
            y1 = int(t_pos.y())
            layout["text_area"] = [x1, y1, int(x1 + rect.width()), int(y1 + rect.height())]

        layout["stand_on_top"] = self.check_layer.isChecked()
        style["font_size"] = int(self.spin_font_text.value())
        style["name_font_size"] = int(self.spin_font_name.value())
        if self.current_background_name:
            layout["current_background"] = self.current_background_name

        meta["name"] = self.edit_char_name.text() or (self.current_char_id or "")

    def save_config(self, show_message: bool = True) -> None:
        if not self.current_char_id:
            return
        os.makedirs(self.char_root, exist_ok=True)
        self._collect_config_from_ui()
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
            if show_message:
                QMessageBox.information(self, "成功", f"角色 [{self.current_char_id}] 配置已保存。")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "错误", f"保存失败: {e}")

    def reload_all(self) -> None:
        if not self.current_char_id:
            return
        self.load_config()
        self.reload_ui_from_config()
        self.load_assets_to_scene()

    def preview_render(self) -> None:
        if not self.current_char_id:
            return
        self._collect_config_from_ui()
        default_text = self.text_rect.preview_text if hasattr(self, "text_rect") else "测试台词"
        text, ok = QInputDialog.getText(self, "预览生成", "输入一段台词：", text=default_text)
        if not ok:
            return
        try:
            from core.renderer import CharacterRenderer
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "错误", f"无法导入渲染器: {e}")
            return

        try:
            portrait_filename = self.combo_portrait.currentText() if self.combo_portrait.count() else None
            portrait_key = os.path.splitext(portrait_filename)[0] if portrait_filename else None
            renderer = CharacterRenderer(self.current_char_id, base_path=BASE_PATH)
            img = renderer.render(text, portrait_key=portrait_key)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "错误", f"渲染失败: {e}")
            return

        buffer = BytesIO()
        img.save(buffer, format="PNG")
        qimg = QImage.fromData(buffer.getvalue(), "PNG")
        pixmap = QPixmap.fromImage(qimg)

        preview_dialog = QDialog(self)
        preview_dialog.setWindowTitle("渲染预览")
        vbox = QVBoxLayout(preview_dialog)
        label = QLabel()
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scaled = pixmap.scaled(1200, 675, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        label.setPixmap(scaled)
        vbox.addWidget(label)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(preview_dialog.accept)
        vbox.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        preview_dialog.resize(1280, 720)
        preview_dialog.exec()

    def generate_cache(self) -> None:
        if not self.current_char_id:
            return
        self._collect_config_from_ui()
        try:
            from core.prebuild import prebuild_character
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "错误", f"无法导入预处理模块: {e}")
            return
        try:
            prebuild_character(self.current_char_id, base_path=BASE_PATH, cache_path=os.path.join(BASE_PATH, "cache"), force=True)
            QMessageBox.information(self, "完成", "缓存生成已完成。")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "错误", f"生成缓存失败: {e}")

    def check_resources(self) -> None:
        issues: List[str] = []
        assets_root = os.path.join(BASE_PATH, "characters")
        if not os.path.exists(assets_root):
            issues.append(f"缺少目录: {assets_root}")
        if not self.current_char_id:
            issues.append("未指定角色")
        else:
            char_root = os.path.join(assets_root, self.current_char_id)
            if not os.path.exists(char_root):
                issues.append(f"缺少角色目录: {char_root}")
            else:
                cfg_path = os.path.join(char_root, "config.json")
                if not os.path.exists(cfg_path):
                    issues.append("缺少 config.json")
                else:
                    try:
                        with open(cfg_path, "r", encoding="utf-8") as f:
                            json.load(f)
                    except Exception as e:  # noqa: BLE001
                        issues.append(f"config.json 读取失败: {e}")

                portrait_dir = os.path.join(char_root, "portrait")
                portraits = [f for f in os.listdir(portrait_dir)] if os.path.exists(portrait_dir) else []
                portraits = [f for f in portraits if f.lower().endswith((".png", ".jpg", ".jpeg"))]
                if not portraits:
                    issues.append("缺少立绘: 请在 portrait/ 放入至少一张图片")

                bg_dir = os.path.join(char_root, "background")
                common_bg_dir = os.path.join(BASE_PATH, "common", "background")
                backgrounds = [f for f in os.listdir(bg_dir)] if os.path.exists(bg_dir) else []
                backgrounds = [f for f in backgrounds if f.lower().endswith((".png", ".jpg", ".jpeg"))]
                common_backgrounds = [f for f in os.listdir(common_bg_dir)] if os.path.exists(common_bg_dir) else []
                common_backgrounds = [f for f in common_backgrounds if f.lower().endswith((".png", ".jpg", ".jpeg"))]
                if not backgrounds and not common_backgrounds:
                    issues.append("背景缺失: character/background 与 common/background 均为空")
                elif not backgrounds and common_backgrounds:
                    issues.append("当前角色 background/ 为空，将使用 common/background 兜底")

                dialog_path = os.path.join(char_root, self.config.get("assets", {}).get("dialog_box", "textbox_bg.png"))
                if not os.path.exists(dialog_path):
                    issues.append(f"缺少对话框底图: {dialog_path}")

        font_path = os.path.join(BASE_PATH, "common", "fonts", "LXGWWenKai-Medium.ttf")
        if not os.path.exists(font_path):
            issues.append(f"缺少字体文件: {font_path}")

        if issues:
            msg = "发现以下问题：\n- " + "\n- ".join(issues)
            QMessageBox.warning(self, "资源体检", msg)
        else:
            QMessageBox.information(self, "资源体检", "资源看起来都齐全，可以正常使用。")

    def open_character_folder(self) -> None:
        if not self.current_char_id:
            return
        char_root = os.path.join(BASE_PATH, "characters", self.current_char_id)
        if not os.path.exists(char_root):
            QMessageBox.warning(self, "提示", f"目录不存在：{char_root}")
            return
        try:
            os.startfile(char_root)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "错误", f"无法打开目录: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = EditorWindow()
    window.show()
    sys.exit(app.exec())
