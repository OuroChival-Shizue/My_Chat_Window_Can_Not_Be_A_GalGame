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
    QHBoxLayout,import sys
import os
import json
import shutil
import re
from typing import Dict, List, Optional, Any, Tuple

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QMessageBox, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsItem, QCheckBox,
    QSpinBox, QComboBox, QInputDialog, QFileDialog, QLineEdit, QDialog,
    QDockWidget, QListWidget, QListWidgetItem, QFormLayout, QColorDialog,
    QMenu, QToolBar, QSplitter, QFrame, QGroupBox, QScrollArea, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QRectF, pyqtSignal, QSize, QPointF, QPoint
from PyQt6.QtGui import (
    QPixmap, QColor, QPen, QBrush, QFont, QImage, QAction, 
    QPainter, QIcon, QDragEnterEvent, QDropEvent, QFontDatabase, QCursor
)

# 尝试导入后端模块
try:
    from core.utils import load_global_config, save_global_config
    from core.renderer import CharacterRenderer
    from core.prebuild import prebuild_character
except ImportError:
    print("Warning: Core modules not found. Some features may not work.")
    def load_global_config(): return {}
    def save_global_config(cfg): pass
    CharacterRenderer = None
    prebuild_character = None

BASE_PATH = "assets"
CANVAS_W, CANVAS_H = 2560, 1440

# Z-Index 层级定义
Z_BG = 0
Z_PORTRAIT_BOTTOM = 10
Z_BOX = 20
Z_PORTRAIT_TOP = 25
Z_TEXT = 30


# =============================================================================
# 自定义图形项 (Graphics Items)
# =============================================================================

class ResizableTextItem(QGraphicsRectItem):
    """高级可缩放文本框"""
    HANDLE_SIZE = 10
    STATE_IDLE = 0
    STATE_MOVE = 1
    STATE_RESIZE = 2

    DIR_NONE = 0x00
    DIR_LEFT = 0x01
    DIR_RIGHT = 0x02
    DIR_TOP = 0x04
    DIR_BOTTOM = 0x08
    
    DIR_TOP_LEFT = DIR_TOP | DIR_LEFT
    DIR_TOP_RIGHT = DIR_TOP | DIR_RIGHT
    DIR_BOTTOM_LEFT = DIR_BOTTOM | DIR_LEFT
    DIR_BOTTOM_RIGHT = DIR_BOTTOM | DIR_RIGHT

    def __init__(self, rect: QRectF, text: str, color: List[int], font_size: int = 40, font_family: str = ""):
        super().__init__(rect)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        
        self.preview_text = text
        self.text_color = QColor(*color)
        self.font_size = font_size
        self.font_family = font_family
        
        self.setPen(QPen(QColor(200, 200, 200, 150), 2, Qt.PenStyle.DashLine))
        self.setBrush(QBrush(QColor(255, 255, 255, 30)))

        self._state = self.STATE_IDLE
        self._resize_dir = self.DIR_NONE
        self._start_mouse_pos = QPointF()
        self._start_rect = QRectF()

    def update_content(self, text: str = None, color: List[int] = None, size: int = None):
        if text is not None: self.preview_text = text
        if color is not None: self.text_color = QColor(*color)
        if size is not None: self.font_size = size
        self.update()

    def hoverMoveEvent(self, event):
        if self.isSelected():
            direction = self._hit_test(event.pos())
            self._update_cursor(direction)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            direction = self._hit_test(pos)
            
            if direction != self.DIR_NONE:
                self._state = self.STATE_RESIZE
                self._resize_dir = direction
                self._start_mouse_pos = event.scenePos()
                self._start_rect = self.rect()
                event.accept()
            else:
                self._state = self.STATE_MOVE
                self.setCursor(Qt.CursorShape.SizeAllCursor)
                super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._state == self.STATE_RESIZE:
            delta = event.scenePos() - self._start_mouse_pos
            new_rect = QRectF(self._start_rect)
            min_w, min_h = 50, 30

            if self._resize_dir & self.DIR_LEFT:
                new_rect.setLeft(min(new_rect.right() - min_w, new_rect.left() + delta.x()))
            if self._resize_dir & self.DIR_RIGHT:
                new_rect.setRight(max(new_rect.left() + min_w, new_rect.right() + delta.x()))
            if self._resize_dir & self.DIR_TOP:
                new_rect.setTop(min(new_rect.bottom() - min_h, new_rect.top() + delta.y()))
            if self._resize_dir & self.DIR_BOTTOM:
                new_rect.setBottom(max(new_rect.top() + min_h, new_rect.bottom() + delta.y()))

            self.setRect(new_rect)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._state = self.STATE_IDLE
        self._resize_dir = self.DIR_NONE
        self._update_cursor(self._hit_test(event.pos()))
        super().mouseReleaseEvent(event)

    def _hit_test(self, pos: QPointF) -> int:
        rect = self.rect()
        x, y = pos.x(), pos.y()
        result = self.DIR_NONE
        
        on_left = abs(x - rect.left()) < self.HANDLE_SIZE
        on_right = abs(x - rect.right()) < self.HANDLE_SIZE
        on_top = abs(y - rect.top()) < self.HANDLE_SIZE
        on_bottom = abs(y - rect.bottom()) < self.HANDLE_SIZE
        
        if on_left: result |= self.DIR_LEFT
        if on_right: result |= self.DIR_RIGHT
        if on_top: result |= self.DIR_TOP
        if on_bottom: result |= self.DIR_BOTTOM
        
        return result

    def _update_cursor(self, direction):
        if direction == self.DIR_TOP_LEFT or direction == self.DIR_BOTTOM_RIGHT:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif direction == self.DIR_TOP_RIGHT or direction == self.DIR_BOTTOM_LEFT:
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif direction & self.DIR_LEFT or direction & self.DIR_RIGHT:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif direction & self.DIR_TOP or direction & self.DIR_BOTTOM:
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        pen_color = QColor(0, 120, 215) if self.isSelected() else QColor(150, 150, 150, 100)
        width = 2 if self.isSelected() else 1
        painter.setPen(QPen(pen_color, width, Qt.PenStyle.DashLine))
        painter.setBrush(self.brush())
        painter.drawRect(self.rect())

        painter.setPen(QPen(self.text_color))
        font = QFont()
        font.setPixelSize(self.font_size)
        if self.font_family:
            font.setFamily(self.font_family)
        else:
            font.setFamily("Microsoft YaHei")
        painter.setFont(font)
        
        margin = 10
        text_rect = self.rect().adjusted(margin, margin, -margin, -margin)
        painter.drawText(text_rect, Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft, self.preview_text)


class ScalableImageItem(QGraphicsPixmapItem):
    """支持滚轮缩放的图片项"""
    def __init__(self, pixmap: QPixmap):
        super().__init__(pixmap)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setTransformationMode(Qt.TransformationMode.SmoothTransformation)

    def wheelEvent(self, event) -> None:
        if self.isSelected():
            factor = 1.05 if event.delta() > 0 else 0.95
            self.setScale(max(0.1, min(self.scale() * factor, 5.0)))
            event.accept()
        else:
            super().wheelEvent(event)


# =============================================================================
# 界面组件 (Widgets)
# =============================================================================

class ColorButton(QPushButton):
    colorChanged = pyqtSignal(list)

    def __init__(self, color: List[int]):
        super().__init__()
        self.setFixedSize(60, 25)
        self.current_color = color
        self.update_style()
        self.clicked.connect(self.pick_color)

    def update_style(self):
        c = self.current_color
        css = f"background-color: rgb({c[0]}, {c[1]}, {c[2]}); border: 1px solid #888; border-radius: 4px;"
        self.setStyleSheet(css)

    def set_color(self, color: List[int]):
        self.current_color = color
        self.update_style()

    def pick_color(self):
        c = self.current_color
        initial = QColor(c[0], c[1], c[2])
        new_color = QColorDialog.getColor(initial, self, "选择颜色")
        if new_color.isValid():
            rgb = [new_color.red(), new_color.green(), new_color.blue()]
            self.set_color(rgb)
            self.colorChanged.emit(rgb)


class AssetListWidget(QListWidget):
    """支持拖拽和右键删除的列表"""
    fileDropped = pyqtSignal(str)
    deleteRequested = pyqtSignal(str) # 发送要删除的文件名

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.DragDropMode.DropOnly)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(('.png', '.jpg', '.jpeg')):
                self.fileDropped.emit(path)

    def contextMenuEvent(self, event):
        item = self.itemAt(event.pos())
        if item:
            menu = QMenu(self)
            delete_action = QAction("删除此文件", self)
            delete_action.triggered.connect(lambda: self.deleteRequested.emit(item.text()))
            menu.addAction(delete_action)
            menu.exec(event.globalPos())


class NewCharacterDialog(QDialog):
    """新建角色弹窗"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新建角色")
        self.resize(400, 200)
        
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        self.edit_id = QLineEdit()
        self.edit_id.setPlaceholderText("例如: kotori (仅限英文/数字/下划线)")
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText("例如: 五河琴里")
        
        form.addRow("角色ID (文件夹名):", self.edit_id)
        form.addRow("显示名称:", self.edit_name)
        layout.addLayout(form)
        
        self.edit_id.textChanged.connect(self._auto_fill_name)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _auto_fill_name(self, text):
        if not self.edit_name.text():
            self.edit_name.setText(text)

    def get_data(self):
        return self.edit_id.text().strip(), self.edit_name.text().strip()


# =============================================================================
# 主窗口 (Main Window)
# =============================================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Box-of-GalGame-Sister 编辑器 (Refactored)")
        self.resize(1600, 900)
        
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
        self._load_custom_font()

        self._init_ui()
        self._load_initial_data()

    def _load_custom_font(self):
        font_path = os.path.join(BASE_PATH, "common", "fonts", "LXGWWenKai-Medium.ttf")
        if os.path.exists(font_path):
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                families = QFontDatabase.applicationFontFamilies(font_id)
                if families:
                    self.custom_font_family = families[0]
                    print(f"已加载字体: {self.custom_font_family}")
        else:
            print(f"未找到字体文件: {font_path}")

    def _init_ui(self):
        self._create_menus()

        self.scene = QGraphicsScene(0, 0, CANVAS_W, CANVAS_H)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view.setBackgroundBrush(QBrush(QColor(40, 40, 40)))
        self.setCentralWidget(self.view)

        self.dock_assets = QDockWidget("资源库 (Assets)", self)
        self.dock_assets.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.dock_assets.setWidget(self._create_assets_panel())
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock_assets)

        self.dock_props = QDockWidget("属性 (Properties)", self)
        self.dock_props.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.dock_props.setWidget(self._create_props_panel())
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_props)

    def _create_menus(self):
        menubar = self.menuBar()
        
        # --- 文件菜单 ---
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

        # --- 工具菜单 ---
        tools_menu = menubar.addMenu("工具 (&Tools)")
        
        action_preview = QAction("渲染预览 (Render Preview)", self)
        action_preview.setShortcut("F5")
        action_preview.triggered.connect(self.preview_render)
        tools_menu.addAction(action_preview)
        
        action_cache = QAction("生成缓存 (Build Cache)", self)
        action_cache.triggered.connect(self.generate_cache)
        tools_menu.addAction(action_cache)
        
        # 新增：同步修复配置
        action_sync = QAction("同步/修复配置 (Sync Configs)", self)
        action_sync.triggered.connect(self.sync_all_configs)
        tools_menu.addAction(action_sync)
        
        tools_menu.addSeparator()
        
        action_reload = QAction("重载界面 (Reload UI)", self)
        action_reload.setShortcut("Ctrl+R")
        action_reload.triggered.connect(self.reload_current_character)
        tools_menu.addAction(action_reload)


    def _create_assets_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        layout.addWidget(QLabel("<b>当前角色:</b>"))
        self.combo_char = QComboBox()
        self.combo_char.currentIndexChanged.connect(self.on_character_changed)
        layout.addWidget(self.combo_char)
        
        layout.addSpacing(10)
        
        # 立绘区域
        row_p_label = QHBoxLayout()
        row_p_label.addWidget(QLabel("<b>立绘列表:</b>"))
        btn_add_p = QPushButton("+")
        btn_add_p.setFixedSize(24, 24)
        btn_add_p.setToolTip("添加立绘 (支持多张)")
        btn_add_p.clicked.connect(self.add_portrait)
        row_p_label.addWidget(btn_add_p)
        layout.addLayout(row_p_label)

        self.list_portraits = AssetListWidget()
        self.list_portraits.currentTextChanged.connect(self.on_portrait_selected)
        self.list_portraits.fileDropped.connect(lambda p: self.import_asset(p, "portrait"))
        self.list_portraits.deleteRequested.connect(lambda f: self.delete_asset_file(f, "portrait"))
        layout.addWidget(self.list_portraits)
        
        layout.addSpacing(10)
        
        # 背景区域
        row_bg_label = QHBoxLayout()
        row_bg_label.addWidget(QLabel("<b>背景列表:</b>"))
        btn_add_bg = QPushButton("+")
        btn_add_bg.setFixedSize(24, 24)
        btn_add_bg.setToolTip("添加背景 (单张替换)")
        btn_add_bg.clicked.connect(self.add_background)
        row_bg_label.addWidget(btn_add_bg)
        layout.addLayout(row_bg_label)

        self.list_backgrounds = AssetListWidget()
        self.list_backgrounds.currentTextChanged.connect(self.on_background_selected)
        self.list_backgrounds.fileDropped.connect(lambda p: self.import_asset(p, "background"))
        self.list_backgrounds.deleteRequested.connect(lambda f: self.delete_asset_file(f, "background"))
        layout.addWidget(self.list_backgrounds)

        lbl_tip = QLabel("<small>提示: 右键可删除，拖拽可添加</small>")
        lbl_tip.setStyleSheet("color: gray;")
        layout.addWidget(lbl_tip)
        
        return panel

    def _create_props_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        panel = QWidget()
        scroll.setWidget(panel)
        
        layout = QVBoxLayout(panel)
        
        group_meta = QGroupBox("基本信息")
        form_meta = QFormLayout()
        self.edit_name = QLineEdit()
        self.edit_name.textChanged.connect(self.on_name_changed)
        form_meta.addRow("显示名称:", self.edit_name)
        group_meta.setLayout(form_meta)
        layout.addWidget(group_meta)
        
        group_style = QGroupBox("样式设置")
        form_style = QFormLayout()
        
        self.spin_font_size = QSpinBox()
        self.spin_font_size.setRange(10, 200)
        self.spin_font_size.valueChanged.connect(self.on_style_changed)
        self.btn_text_color = ColorButton([255, 255, 255])
        self.btn_text_color.colorChanged.connect(self.on_style_changed)
        
        row_text = QHBoxLayout()
        row_text.addWidget(self.spin_font_size)
        row_text.addWidget(self.btn_text_color)
        form_style.addRow("正文 (大小/色):", row_text)
        
        self.spin_name_size = QSpinBox()
        self.spin_name_size.setRange(10, 200)
        self.spin_name_size.valueChanged.connect(self.on_style_changed)
        self.btn_name_color = ColorButton([255, 0, 255])
        self.btn_name_color.colorChanged.connect(self.on_style_changed)
        
        row_name = QHBoxLayout()
        row_name.addWidget(self.spin_name_size)
        row_name.addWidget(self.btn_name_color)
        form_style.addRow("名字 (大小/色):", row_name)
        
        group_style.setLayout(form_style)
        layout.addWidget(group_style)
        
        group_layout = QGroupBox("布局微调")
        form_layout = QFormLayout()
        
        self.check_on_top = QCheckBox("立绘覆盖对话框")
        self.check_on_top.toggled.connect(self.on_layout_changed)
        form_layout.addRow(self.check_on_top)
        
        self.lbl_pos_info = QLabel("拖动画面元素以更新坐标")
        self.lbl_pos_info.setStyleSheet("color: gray; font-size: 10px;")
        form_layout.addRow(self.lbl_pos_info)
        
        group_layout.setLayout(form_layout)
        layout.addWidget(group_layout)
        
        group_box = QGroupBox("对话框")
        vbox_box = QVBoxLayout()
        btn_box = QPushButton("更换底图 (自动贴底)...")
        btn_box.clicked.connect(self.select_dialog_box)
        vbox_box.addWidget(btn_box)
        group_box.setLayout(vbox_box)
        layout.addWidget(group_box)

        layout.addStretch()
        return scroll

    def _load_initial_data(self):
        char_dir = os.path.join(BASE_PATH, "characters")
        if not os.path.exists(char_dir):
            os.makedirs(char_dir)
            
        chars = [d for d in os.listdir(char_dir) if os.path.isdir(os.path.join(char_dir, d))]
        chars.sort()
        
        self.combo_char.blockSignals(True)
        self.combo_char.clear()
        self.combo_char.addItems(chars)
        
        global_conf = load_global_config()
        last_char = global_conf.get("current_character", "")
        
        if last_char and last_char in chars:
            self.combo_char.setCurrentText(last_char)
        elif chars:
            self.combo_char.setCurrentIndex(0)
            
        self.combo_char.blockSignals(False)
        
        if self.combo_char.count() > 0:
            self.on_character_changed(self.combo_char.currentIndex())

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
                        "box_pos": [0, CANVAS_H - 200],
                        "text_area": [100, 800, 1800, 1000],
                        "name_pos": [100, 100],
                        "stand_on_top": False
                    }
                }
                
                with open(os.path.join(new_root, "config.json"), "w", encoding="utf-8") as f:
                    json.dump(default_config, f, ensure_ascii=False, indent=4)
                
                QMessageBox.information(self, "成功", f"角色 '{char_name}' 创建成功！\n请在资源库中添加立绘和背景。")
                
                self._load_initial_data()
                index = self.combo_char.findText(char_id)
                if index >= 0:
                    self.combo_char.setCurrentIndex(index)
                    
            except Exception as e:
                QMessageBox.critical(self, "错误", f"创建失败: {e}")

    def on_character_changed(self, index: int):
        char_id = self.combo_char.currentText()
        if not char_id: return
        
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

    def load_config(self):
        default_cfg = {
            "meta": {"name": self.current_char_id},
            "style": {"font_size": 45, "text_color": [255,255,255], "name_color": [255,0,255]},
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

    def _merge_dicts(self, base, update):
        for k, v in update.items():
            if isinstance(v, dict) and k in base:
                self._merge_dicts(base[k], v)
            else:
                base[k] = v
        return base

    def refresh_asset_lists(self):
        p_dir = os.path.join(self.char_root, "portrait")
        self.list_portraits.blockSignals(True)
        self.list_portraits.clear()
        if os.path.exists(p_dir):
            files = [f for f in os.listdir(p_dir) if f.lower().endswith(('.png','.jpg'))]
            files.sort()
            self.list_portraits.addItems(files)
        self.list_portraits.blockSignals(False)
        
        bg_dirs = [
            os.path.join(self.char_root, "background"),
            os.path.join(BASE_PATH, "common", "background")
        ]
        self.list_backgrounds.blockSignals(True)
        self.list_backgrounds.clear()
        for d in bg_dirs:
            if os.path.exists(d):
                files = [f for f in os.listdir(d) if f.lower().endswith(('.png','.jpg'))]
                self.list_backgrounds.addItems(files)
        self.list_backgrounds.blockSignals(False)

    def update_ui_from_config(self):
        meta = self.config.get("meta", {})
        style = self.config.get("style", {})
        layout = self.config.get("layout", {})
        
        self.edit_name.blockSignals(True)
        self.edit_name.setText(meta.get("name", ""))
        self.edit_name.blockSignals(False)
        
        self.spin_font_size.blockSignals(True)
        self.spin_font_size.setValue(int(style.get("font_size", 45)))
        self.spin_font_size.blockSignals(False)
        
        self.spin_name_size.blockSignals(True)
        self.spin_name_size.setValue(int(style.get("name_font_size", 45)))
        self.spin_name_size.blockSignals(False)
        
        self.btn_text_color.set_color(style.get("text_color", [255,255,255]))
        self.btn_name_color.set_color(style.get("name_color", [255,0,255]))
        
        self.check_on_top.blockSignals(True)
        self.check_on_top.setChecked(layout.get("stand_on_top", False))
        self.check_on_top.blockSignals(False)
        
        curr_p = layout.get("current_portrait")
        if curr_p:
            items = self.list_portraits.findItems(curr_p, Qt.MatchFlag.MatchExactly)
            if items: self.list_portraits.setCurrentItem(items[0])
            
        curr_bg = layout.get("current_background")
        if curr_bg:
            items = self.list_backgrounds.findItems(curr_bg, Qt.MatchFlag.MatchExactly)
            if items: self.list_backgrounds.setCurrentItem(items[0])

    def rebuild_scene(self):
        self.scene_items = {k: None for k in self.scene_items}
        self.scene.clear()
        
        self.scene.addRect(0, 0, CANVAS_W, CANVAS_H, QPen(Qt.GlobalColor.black), QBrush(Qt.GlobalColor.white)).setZValue(Z_BG)
        
        layout = self.config.get("layout", {})
        assets = self.config.get("assets", {})
        
        bg_name = layout.get("current_background")
        if bg_name:
            bg_path = self._find_asset_path(bg_name, "background")
            if bg_path:
                pix = QPixmap(bg_path).scaled(CANVAS_W, CANVAS_H, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                item = QGraphicsPixmapItem(pix)
                item.setZValue(Z_BG)
                self.scene.addItem(item)
                self.scene_items["bg"] = item

        box_name = assets.get("dialog_box", "textbox_bg.png")
        box_path = os.path.join(self.char_root, box_name)
        if os.path.exists(box_path):
            pix = QPixmap(box_path)
            if pix.width() != CANVAS_W:
                new_h = int(pix.height() * (CANVAS_W / pix.width()))
                pix = pix.scaled(CANVAS_W, new_h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            
            item = QGraphicsPixmapItem(pix)
            saved_pos = layout.get("box_pos")
            if saved_pos:
                item.setPos(saved_pos[0], saved_pos[1])
            else:
                item.setPos(0, CANVAS_H - pix.height())
                
            item.setZValue(Z_BOX)
            self.scene.addItem(item)
            self.scene_items["box"] = item

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

        style = self.config.get("style", {})
        meta = self.config.get("meta", {})
        
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
        if os.path.exists(p1): return p1
        p2 = os.path.join(BASE_PATH, "common", type_folder, filename)
        if os.path.exists(p2): return p2
        return None

    def fit_view(self):
        self.view.resetTransform()
        self.view.fitInView(0, 0, CANVAS_W, CANVAS_H, Qt.AspectRatioMode.KeepAspectRatio)
        self.view.scale(0.95, 0.95)

    def on_portrait_selected(self, text):
        if not text: return
        self.config.setdefault("layout", {})["current_portrait"] = text
        self.rebuild_scene() 

    def on_background_selected(self, text):
        if not text: return
        self.config.setdefault("layout", {})["current_background"] = text
        self.rebuild_scene()

    def on_name_changed(self, text):
        self.config.setdefault("meta", {})["name"] = text
        if self.scene_items["name_text"]:
            self.scene_items["name_text"].update_content(text=text)

    def on_style_changed(self):
        style = self.config.setdefault("style", {})
        
        style["font_size"] = self.spin_font_size.value()
        style["name_font_size"] = self.spin_name_size.value()
        style["text_color"] = self.btn_text_color.current_color
        style["name_color"] = self.btn_name_color.current_color
        
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

    def on_layout_changed(self):
        self.config.setdefault("layout", {})["stand_on_top"] = self.check_on_top.isChecked()
        if self.scene_items["portrait"]:
            z = Z_PORTRAIT_TOP if self.check_on_top.isChecked() else Z_PORTRAIT_BOTTOM
            self.scene_items["portrait"].setZValue(z)

    def import_asset(self, file_path, asset_type):
        """通用导入逻辑 (拖拽用)"""
        if not self.current_char_id: return
        target_dir = os.path.join(self.char_root, asset_type)
        if not os.path.exists(target_dir): os.makedirs(target_dir)
        
        try:
            shutil.copy(file_path, target_dir)
            self.refresh_asset_lists()
            QMessageBox.information(self, "成功", f"已导入: {os.path.basename(file_path)}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导入失败: {e}")

    def add_portrait(self):
        """按钮添加立绘 (支持多选)"""
        if not self.current_char_id: return
        paths, _ = QFileDialog.getOpenFileNames(self, "选择立绘图片", "", "Images (*.png *.jpg *.jpeg)")
        if not paths: return
        
        target_dir = os.path.join(self.char_root, "portrait")
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
        if not self.current_char_id: return
        path, _ = QFileDialog.getOpenFileName(self, "选择背景图片", "", "Images (*.png *.jpg *.jpeg)")
        if not path: return
        
        target_dir = os.path.join(self.char_root, "background")
        
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
        if not self.current_char_id: return
        path, _ = QFileDialog.getOpenFileName(self, "选择对话框图片", "", "Images (*.png *.jpg *.jpeg)")
        if not path: return

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
            pix = QPixmap(target_path)
            if not pix.isNull():
                # 计算缩放后的高度
                scale = CANVAS_W / pix.width()
                scaled_h = pix.height() * scale
                # Y = 画布高度 - 图片高度
                new_y = int(CANVAS_H - scaled_h)
                
                self.config.setdefault("layout", {})["box_pos"] = [0, new_y]
                print(f"Auto-positioned box at Y={new_y}")

            self.rebuild_scene()
            QMessageBox.information(self, "成功", "对话框已更换并自动贴底")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"操作失败: {e}")

    def delete_asset_file(self, filename, asset_type):
        """右键删除文件"""
        if not self.current_char_id: return
        
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

    def open_character_folder(self):
        if self.char_root and os.path.exists(self.char_root):
            os.startfile(self.char_root)

    def reload_current_character(self):
        if self.current_char_id:
            self.on_character_changed(self.combo_char.currentIndex())
    def sync_all_configs(self):
        """同步/修复配置的具体实现"""
        try:
            char_dir = os.path.join(BASE_PATH, "characters")
            if not os.path.exists(char_dir): return
            
            count = 0
            # 遍历所有角色文件夹
            for char_id in os.listdir(char_dir):
                root = os.path.join(char_dir, char_id)
                if not os.path.isdir(root): continue
                
                cfg_path = os.path.join(root, "config.json")
                if not os.path.exists(cfg_path): continue
                
                # 读取配置
                try:
                    with open(cfg_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except Exception:
                    continue # 跳过损坏的文件
                
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
                    
                # 如果有修改，写回文件
                if modified:
                    with open(cfg_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=4)
                    count += 1
            
            QMessageBox.information(self, "完成", f"已检查所有角色，修复了 {count} 个配置文件。")
            # 刷新当前界面
            self.reload_current_character()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"同步失败: {e}")

    def _collect_scene_data(self):
        layout = self.config.setdefault("layout", {})
        
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

    def save_config(self):
        if not self.current_char_id: return
        
        self._collect_scene_data()
        
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
            self.statusBar().showMessage(f"已保存: {self.current_char_id}", 3000)
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))

    def generate_cache(self):
        if not prebuild_character or not self.current_char_id:
            QMessageBox.warning(self, "错误", "无法调用预处理模块")
            return
            
        self.save_config()
        try:
            cache_dir = os.path.join(BASE_PATH, "cache")
            prebuild_character(self.current_char_id, BASE_PATH, cache_dir, force=True)
            QMessageBox.information(self, "完成", "缓存生成完毕")
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))

    def preview_render(self):
        if not CharacterRenderer or not self.current_char_id:
            return
            
        self.save_config()
        text, ok = QInputDialog.getText(self, "渲染预览", "输入测试台词:")
        if ok and text:
            try:
                renderer = CharacterRenderer(self.current_char_id, BASE_PATH)
                p_key = os.path.splitext(self.config["layout"].get("current_portrait", ""))[0]
                bg_key = os.path.splitext(self.config["layout"].get("current_background", ""))[0]
                
                pil_img = renderer.render(text, portrait_key=p_key, bg_key=bg_key)
                pil_img.show()
            except Exception as e:
                QMessageBox.critical(self, "渲染失败", str(e))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

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
