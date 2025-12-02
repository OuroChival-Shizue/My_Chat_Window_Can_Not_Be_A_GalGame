# 🎨 Creator GUI - 可视化编辑器模块

**📍 导航**: [← 返回根目录](../CLAUDE.md) / **可视化编辑器**

---

## 📋 模块概览

Creator GUI 是项目的可视化配置工具，提供所见即所得的角色编辑体验。用户通过拖拽、调整元素位置和大小，配置角色的立绘、对话框、文本区域等参数。

**入口文件**: `creator_gui.py` (~30 行，启动入口)
**主要模块**: `gui/` 目录（模块化架构）
**技术栈**: PyQt6 (Graphics View Framework)
**依赖**: core.renderer, core.prebuild, core.utils

---

## 🏗️ 架构概览

```mermaid
graph TB
    subgraph "用户界面层"
        A[MainWindow<br/>主编辑器窗口]
        B[NewCharacterDialog<br/>新建角色对话框]
    end

    subgraph "自定义控件层"
        C[ResizableTextItem<br/>可调整文本框]
        D[ScalableImageItem<br/>可缩放图片]
        E[ColorButton<br/>颜色选择器]
        F[AssetListWidget<br/>拖拽资源列表]
    end

    subgraph "渲染层"
        G[QGraphicsScene<br/>2560×1440 画布]
        H[QGraphicsView<br/>视口]
    end

    subgraph "后端集成"
        I[CharacterRenderer<br/>渲染器预览]
        J[prebuild_character<br/>缓存生成]
        K[load/save_global_config<br/>配置管理]
    end

    A --> C
    A --> D
    A --> E
    A --> F
    A --> G
    A --> H
    A --> I
    A --> J
    A --> K
    B --> A

    style A fill:#ffeb3b
    style B fill:#ffc107
    style C fill:#4caf50
    style D fill:#4caf50
    style E fill:#4caf50
    style F fill:#4caf50
    style G fill:#2196f3
    style H fill:#2196f3
    style I fill:#9c27b0
    style J fill:#9c27b0
    style K fill:#9c27b0
```

---

## 📦 核心组件详解

### 1️⃣ MainWindow - 主编辑器窗口

**类路径**: `gui/main_window.py`

#### 职责

- 角色配置的主界面
- 管理 Graphics Scene 和所有可视化元素
- 协调资源加载、配置读写、预览渲染

#### 核心属性

| 属性                   | 类型               | 说明                                                   |
| ---------------------- | ------------------ | ------------------------------------------------------ |
| `current_char_id`    | `str`            | 当前编辑的角色 ID                                      |
| `config`             | `Dict`           | 当前角色的完整配置                                     |
| `scene`              | `QGraphicsScene` | 2560×1440 画布                                        |
| `scene_items`        | `Dict`           | 画布元素引用 (bg, portrait, box, name_text, main_text) |
| `custom_font_family` | `str`            | 加载的自定义字体名称                                   |

#### 界面布局

**Dock 面板**:

- **左侧 (资源库)**: 角色选择、立绘列表、背景列表
- **右侧 (属性面板)**: 基本信息、样式设置、布局微调、对话框配置

**中央画布**: QGraphicsView 显示 2560×1440 场景

#### 关键方法

| 方法                       | 签名                     | 功能                                |
| -------------------------- | ------------------------ | ----------------------------------- |
| `_load_custom_font()`    | `() -> None`           | 加载霞鹜文楷字体                    |
| `_init_ui()`             | `() -> None`           | 初始化菜单、Dock、Scene、View       |
| `_create_assets_panel()` | `() -> QWidget`        | 创建资源库面板                      |
| `_create_props_panel()`  | `() -> QWidget`        | 创建属性面板                        |
| `_load_initial_data()`   | `() -> None`           | 扫描角色目录并初始化                |
| `create_new_character()` | `() -> None`           | 新建角色流程                        |
| `on_character_changed()` | `(index: int) -> None` | 切换角色回调                        |
| `load_config()`          | `() -> None`           | 加载角色 config.yaml                |
| `refresh_asset_lists()`  | `() -> None`           | 刷新立绘/背景列表                   |
| `rebuild_scene()`        | `() -> None`           | 重建 Graphics Scene                 |
| `_collect_scene_data()`  | `() -> None`           | 从 Scene 采集位置/缩放数据          |
| `save_config()`          | `() -> None`           | 保存配置到 YAML                     |
| `generate_cache()`       | `() -> None`           | 调用 prebuild_character 生成缓存    |
| `preview_render()`       | `() -> None`           | 调用 CharacterRenderer 实时渲染预览 |
| `select_custom_font()`   | `() -> None`           | 选择并导入自定义字体 (v2.3 新增)    |
| `clear_custom_font()`    | `() -> None`           | 清除自定义字体配置 (v2.3 新增)      |

---

### 2️⃣ ResizableTextItem - 可调整文本框

**类路径**: `gui/canvas/items.py`

#### 职责

- 可拖动、可缩放的文本区域预览
- 8 个调整手柄（四角 + 四边）
- 实时显示文本、字号、颜色

#### 核心机制

**状态机**:

```python
STATE_IDLE = 0      # 空闲
STATE_MOVE = 1      # 拖动
STATE_RESIZE = 2    # 调整大小
```

**方向检测** (位掩码):

```python
DIR_LEFT = 0x01
DIR_RIGHT = 0x02
DIR_TOP = 0x04
DIR_BOTTOM = 0x08

DIR_TOP_LEFT = DIR_TOP | DIR_LEFT      # 左上角
DIR_BOTTOM_RIGHT = DIR_BOTTOM | DIR_RIGHT  # 右下角
# ...
```

#### 关键方法

| 方法                  | 功能           | 关键逻辑                                     |
| --------------------- | -------------- | -------------------------------------------- |
| `hoverMoveEvent()`  | 悬停时更新光标 | 调用 `_hit_test()` 检测手柄位置            |
| `mousePressEvent()` | 按下鼠标       | 判断点击位置决定进入 MOVE 或 RESIZE 状态     |
| `mouseMoveEvent()`  | 拖动鼠标       | RESIZE 状态时计算新矩形，限制最小尺寸 50×30 |
| `_hit_test()`       | 碰撞检测       | 检测鼠标是否在 HANDLE_SIZE (10px) 范围内     |
| `_update_cursor()`  | 更新光标       | 根据方向设置对应光标（↔ ↕ ⤡ ⤢）          |
| `paint()`           | 绘制           | 绘制矩形框 + 文本内容                        |

#### 缩放逻辑示例

```python
# gui/canvas/items.py (ResizableTextItem.mouseMoveEvent)
def mouseMoveEvent(self, event):
    if self._state == self.STATE_RESIZE:
        delta = event.scenePos() - self._start_mouse_pos
        new_rect = QRectF(self._start_rect)
        min_w, min_h = 50, 30  # 最小尺寸限制

        # 位掩码判断方向
        if self._resize_dir & self.DIR_LEFT:
            new_rect.setLeft(min(new_rect.right() - min_w, new_rect.left() + delta.x()))
        if self._resize_dir & self.DIR_RIGHT:
            new_rect.setRight(max(new_rect.left() + min_w, new_rect.right() + delta.x()))
        # ... TOP/BOTTOM 同理

        self.setRect(new_rect)
```

---

### 3️⃣ ScalableImageItem - 可缩放图片

**类路径**: `gui/canvas/items.py`

#### 职责

- 支持鼠标滚轮缩放的图片项
- 用于立绘的交互式调整

#### 核心逻辑

```python
# gui/canvas/items.py (ScalableImageItem.wheelEvent)
def wheelEvent(self, event):
    if self.isSelected():
        factor = 1.05 if event.delta() > 0 else 0.95  # 每次缩放 5%
        self.setScale(max(0.1, min(self.scale() * factor, 5.0)))  # 限制 0.1~5.0 倍
        event.accept()
```

---

### 4️⃣ ColorButton - 颜色选择器

**类路径**: `gui/widgets/color_button.py`

#### 职责

- 显示当前颜色的按钮
- 点击弹出 QColorDialog
- 发射 `colorChanged` 信号

#### 核心代码

```python
# gui/widgets/color_button.py (ColorButton.pick_color)
def pick_color(self):
    initial = QColor(self.current_color[0], self.current_color[1], self.current_color[2])
    new_color = QColorDialog.getColor(initial, self, "选择颜色")
    if new_color.isValid():
        rgb = [new_color.red(), new_color.green(), new_color.blue()]
        self.set_color(rgb)
        self.colorChanged.emit(rgb)  # 发送信号
```

---

### 5️⃣ AssetListWidget - 拖拽资源列表

**类路径**: `gui/widgets/asset_list.py`

#### 职责

- 支持文件拖拽导入
- 右键菜单删除文件
- 发射 `fileDropped` 和 `deleteRequested` 信号

#### 拖拽逻辑

```python
# gui/widgets/asset_list.py (AssetListWidget.dropEvent)
def dropEvent(self, event: QDropEvent):
    for url in event.mimeData().urls():
        path = url.toLocalFile()
        if path.lower().endswith(('.png', '.jpg', '.jpeg')):
            self.fileDropped.emit(path)  # 发送信号给主窗口处理
```

#### 右键删除

```python
# gui/widgets/asset_list.py (AssetListWidget.contextMenuEvent)
def contextMenuEvent(self, event):
    item = self.itemAt(event.pos())
    if item:
        menu = QMenu(self)
        delete_action = QAction("删除此文件", self)
        delete_action.triggered.connect(lambda: self.deleteRequested.emit(item.text()))
        menu.addAction(delete_action)
        menu.exec(event.globalPos())
```

---

### 6️⃣ NewCharacterDialog - 新建角色对话框

**类路径**: `gui/widgets/dialogs.py`

#### 职责

- 输入角色 ID（文件夹名）和显示名称
- ID 自动填充到名称（如果名称为空）
- 返回用户输入数据

#### 关键方法

```python
# gui/widgets/dialogs.py (NewCharacterDialog)
def _auto_fill_name(self, text):
    """ID 变化时自动填充名称"""
    if not self.edit_name.text():
        self.edit_name.setText(text)

def get_data(self):
    return self.edit_id.text().strip(), self.edit_name.text().strip()
```

---

## 🔄 核心流程详解

### 1️⃣ 启动与初始化流程

```
MainWindow.__init__()
  ├─ _load_custom_font()                  # 加载霞鹜文楷字体
  ├─ _init_ui()
  │   ├─ _create_menus()                  # 创建菜单栏
  │   ├─ QGraphicsScene(0, 0, 2560, 1440) # 创建画布
  │   ├─ QGraphicsView(scene)             # 创建视口
  │   ├─ _create_assets_panel()           # 创建资源库 Dock
  │   └─ _create_props_panel()            # 创建属性面板 Dock
  └─ _load_initial_data()
      ├─ 扫描 assets/characters/ 目录
      ├─ 加载 global_config.json 获取上次编辑的角色
      └─ 触发 on_character_changed()
```

---

### 2️⃣ 切换角色流程

```
on_character_changed(index)
  ├─ 更新 current_char_id, char_root, config_path
  ├─ 更新 global_config.json 记录当前角色
  ├─ load_config()                        # 加载角色 config.json
  ├─ refresh_asset_lists()                # 刷新立绘/背景列表
  ├─ update_ui_from_config()              # 同步 UI 控件状态
  └─ rebuild_scene()                      # 重建画布
      ├─ scene.clear()                    # 清空画布
      ├─ 加载背景图片 (current_background)
      ├─ 加载对话框图片 (dialog_box)
      │   └─ 自动缩放至画布宽度 2560px
      ├─ 加载立绘图片 (current_portrait)
      │   ├─ 应用 stand_scale 缩放
      │   └─ 设置位置 stand_pos
      ├─ 创建 ResizableTextItem (名字文本)
      │   └─ 位置: name_pos, 颜色: name_color
      ├─ 创建 ResizableTextItem (正文文本)
      │   └─ 区域: text_area, 颜色: text_color
      └─ 根据 stand_on_top 设置 Z 轴层级
```

---

### 3️⃣ 新建角色流程

```
create_new_character()
  ├─ 弹出 NewCharacterDialog 对话框
  ├─ 验证 ID 格式（仅字母数字下划线）
  ├─ 检查 ID 是否已存在
  ├─ 创建目录结构:
  │   ├─ assets/characters/{char_id}/
  │   ├─ assets/characters/{char_id}/portrait/
  │   └─ assets/characters/{char_id}/background/
  ├─ 生成默认 config.json:
  │   ├─ meta: {name, id}
  │   ├─ assets: {dialog_box: "textbox_bg.png"}
  │   ├─ style: {font_size: 45, text_color, name_color}
  │   └─ layout: {stand_pos, stand_scale, text_area, ...}
  ├─ 刷新角色列表
  └─ 自动切换到新角色
```

---

### 4️⃣ 保存配置流程

```
save_config()
  ├─ _collect_scene_data()                # 采集画布数据
  │   ├─ portrait_item.pos() → stand_pos
  │   ├─ portrait_item.scale() → stand_scale
  │   ├─ box_item.pos() → box_pos
  │   ├─ name_text.mapToScene() → name_pos
  │   └─ main_text.mapToScene() → text_area [x1, y1, x2, y2]
  ├─ 合并 UI 控件数据 (字号、颜色、名称等)
  └─ json.dump(config, config.json)       # 写入文件
```

---

### 5️⃣ 渲染预览流程

```
preview_render()
  ├─ save_config()                        # 先保存当前配置
  ├─ 弹出输入框获取测试台词
  ├─ CharacterRenderer(char_id)           # 初始化渲染器
  ├─ renderer.render(text, portrait_key, bg_key)
  ├─ PIL.Image.show()                     # 使用系统默认图片查看器
  └─ 异常处理 → QMessageBox.critical()
```

---

### 6️⃣ 缓存生成流程

```
generate_cache()
  ├─ save_config()                        # 保存最新配置
  ├─ prebuild_character(char_id, force=True)
  │   └─ 生成所有"立绘×背景"组合缓存
  └─ QMessageBox.information("缓存生成完毕")
```

---

## 🎨 Z-Index 层级体系

```python
# gui/constants.py
Z_BG = 0              # 背景层
Z_PORTRAIT_BOTTOM = 10  # 立绘（底层）
Z_BOX = 20            # 对话框
Z_PORTRAIT_TOP = 25   # 立绘（顶层）
Z_TEXT = 30           # 文本（最上层）
```

**层级逻辑**:

- `stand_on_top == False` → 立绘在对话框下方 (Z=10)
- `stand_on_top == True` → 立绘在对话框上方 (Z=25)
- 文本始终在最上层 (Z=30)

---

## 📄 配置文件结构

编辑器读写的 `config.json` 结构：

```json
{
  "meta": {
    "name": "角色显示名称",
    "id": "角色ID"
  },
  "assets": {
    "dialog_box": "textbox_bg.png"
  },
  "style": {
    "text_color": [255, 255, 255],
    "name_color": [253, 145, 175],
    "font_size": 46,
    "name_font_size": 46,
    "font_file": "可选：自定义字体"
  },
  "layout": {
    "stand_pos": [842, 126],          // 立绘左上角 (x, y)
    "stand_scale": 1.965,             // 立绘缩放比例
    "box_pos": [0, 0],                // 对话框左上角 (x, y)
    "text_area": [499, 1179, 2249, 1389],  // 文本区域 [x1, y1, x2, y2]
    "name_pos": [624, 1086],          // 角色名位置 (x, y)
    "stand_on_top": false,            // 立绘是否覆盖对话框
    "current_portrait": "1.png",      // 当前选中立绘
    "current_background": "1.png"     // 当前选中背景
  }
}
```

---

## 🔧 关键技术点

### 1. Graphics View Framework

**Scene-View 架构**:

```python
# gui/main_window.py (MainWindow.__init__)
self.scene = QGraphicsScene(0, 0, CANVAS_W, CANVAS_H)  # 固定 2560×1440
self.view = QGraphicsView(self.scene)
self.view.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)  # 手型拖动
```

**自适应缩放**:

```python
# gui/main_window.py (MainWindow.fit_view)
def fit_view(self):
    self.view.resetTransform()
    self.view.fitInView(0, 0, CANVAS_W, CANVAS_H, Qt.AspectRatioMode.KeepAspectRatio)
    self.view.scale(0.95, 0.95)  # 留出 5% 边距
```

---

### 2. 默认字体加载

```python
# gui/main_window.py (MainWindow._load_custom_font)
def _load_custom_font(self):
    """加载默认的霞鹜文楷字体"""
    font_path = os.path.join(BASE_PATH, "common", "fonts", "LXGWWenKai-Medium.ttf")
    if os.path.exists(font_path):
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                self.custom_font_family = families[0]  # 获取字体族名称
```

---

### 3. 角色自定义字体管理 (v2.3 新增) 🎨

#### 功能概述

允许为每个角色配置独立的 TrueType 字体文件，实现更个性化的文本渲染效果。

#### UI 组件

**属性面板新增控件** (`gui/panels/props_panel.py:73-86`):

```python
# 自定义字体区域
self.lbl_font_file = QLabel("默认字体")  # 状态显示标签
self.lbl_font_file.setStyleSheet("color: gray; font-size: 10px;")

self.btn_select_font = QPushButton("选择字体文件...")  # 导入按钮
self.btn_clear_font = QPushButton("清除")              # 清除按钮
self.btn_clear_font.setMaximumWidth(60)

# 布局
row_font = QHBoxLayout()
row_font.addWidget(self.btn_select_font)
row_font.addWidget(self.btn_clear_font)
form_style.addRow("自定义字体:", row_font)
form_style.addRow("", self.lbl_font_file)  # 状态显示行
```

#### 核心方法

**1. 选择并导入字体** (`gui/main_window.py:1140-1185`):

```python
def select_custom_font(self):
    """选择自定义字体文件"""
    # 1. 打开文件选择对话框
    path, _ = QFileDialog.getOpenFileName(
        self, "选择字体文件", "", "TrueType Fonts (*.ttf *.TTF)"
    )
    if not path:
        return

    # 2. 创建字体目录
    font_dir = os.path.join(self.char_root, "fonts")
    if not os.path.exists(font_dir):
        os.makedirs(font_dir)

    # 3. 复制字体文件到角色目录
    font_filename = os.path.basename(path)
    target_path = os.path.join(font_dir, font_filename)

    # 4. 检查文件是否已存在
    if os.path.exists(target_path):
        reply = QMessageBox.question(
            self, "替换确认",
            f"字体文件 '{font_filename}' 已存在，是否替换？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

    shutil.copy(path, target_path)

    # 5. 更新配置（保存相对路径）
    relative_path = os.path.join("fonts", font_filename)
    self.config.setdefault("style", {})["font_file"] = relative_path

    # 6. 更新 UI 显示
    self.props_panel.lbl_font_file.setText(font_filename)
    self.props_panel.lbl_font_file.setStyleSheet("color: green; font-size: 10px;")

    self.cache_outdated = True
    QMessageBox.information(self, "成功",
        f"字体已导入: {font_filename}\n\n请保存配置并重新生成缓存以应用更改。")
```

**2. 清除自定义字体** (`gui/main_window.py:1187-1202`):

```python
def clear_custom_font(self):
    """清除自定义字体"""
    # 1. 移除配置中的字体设置
    style = self.config.get("style", {})
    if "font_file" in style:
        del style["font_file"]

        # 2. 更新 UI 显示
        self.props_panel.lbl_font_file.setText("默认字体")
        self.props_panel.lbl_font_file.setStyleSheet("color: gray; font-size: 10px;")

        self.cache_outdated = True
        QMessageBox.information(self, "成功",
            "已清除自定义字体，将使用默认字体。\n\n请保存配置并重新生成缓存以应用更改。")
```

**3. 加载字体配置** (`gui/main_window.py:441-451`):

```python
# 在 sync_props_from_config() 中更新字体显示
font_file = style.get("font_file")
if font_file:
    font_name = os.path.basename(font_file)
    pp.lbl_font_file.setText(font_name)
    pp.lbl_font_file.setStyleSheet("color: green; font-size: 10px;")
else:
    pp.lbl_font_file.setText("默认字体")
    pp.lbl_font_file.setStyleSheet("color: gray; font-size: 10px;")
```

#### 配置存储格式

```yaml
# assets/characters/<角色ID>/config.yaml
style:
  font_file: fonts/lolita.ttf  # 相对于角色目录的路径
  basic:
    font_size: 40
    # ...
```

#### 使用流程

```
1. 用户点击"选择字体文件..."
   └─ 打开文件选择对话框（过滤 .ttf 文件）

2. 选择字体文件
   └─ 自动创建 assets/characters/<角色>/fonts/ 目录

3. 复制字体文件
   ├─ 检查是否已存在同名文件
   ├─ 询问是否替换（如果存在）
   └─ 复制到角色的 fonts/ 目录

4. 更新配置
   ├─ 保存相对路径到 config["style"]["font_file"]
   └─ 更新 UI 状态显示（绿色显示字体名）

5. 标记缓存过期
   └─ cache_outdated = True

6. 提示用户
   └─ "请保存配置并重新生成缓存以应用更改"
```

#### 状态显示逻辑

| 状态 | 显示文本 | 样式 | 说明 |
|------|---------|------|------|
| 未设置 | "默认字体" | `color: gray` | 使用霞鹜文楷 |
| 已设置 | 字体文件名 | `color: green` | 使用自定义字体 |

#### 注意事项

- **文件格式**: 仅支持 `.ttf` (TrueType Font) 格式
- **路径存储**: 配置中保存相对路径（如 `fonts/lolita.ttf`），便于项目迁移
- **缓存更新**: 修改字体后必须重新生成缓存才能在主程序中生效
- **文件管理**: 字体文件不会自动删除，清除配置只是移除引用

---

### 4. 对话框自动贴底

```python
# gui/main_window.py (MainWindow.select_dialog_box)
def select_dialog_box(self):
    # ...
    pix = QPixmap(target_path)
    if not pix.isNull():
        scale = CANVAS_W / pix.width()        # 计算缩放比例
        scaled_h = pix.height() * scale       # 缩放后高度
        new_y = int(CANVAS_H - scaled_h)      # 底部对齐 Y 坐标

        self.config.setdefault("layout", {})["box_pos"] = [0, new_y]
```

---

### 4. 配置合并策略

```python
# gui/main_window.py (MainWindow._merge_dicts)
def _merge_dicts(self, base, update):
    """递归合并配置，保留默认值同时应用用户修改"""
    for k, v in update.items():
        if isinstance(v, dict) and k in base:
            self._merge_dicts(base[k], v)  # 递归合并
        else:
            base[k] = v  # 覆盖或新增
    return base
```

---

### 5. Scene 数据采集

```python
# gui/main_window.py (MainWindow._collect_scene_data)
def _collect_scene_data(self):
    layout = self.config.setdefault("layout", {})

    # 立绘位置与缩放
    if self.scene_items["portrait"]:
        item = self.scene_items["portrait"]
        layout["stand_pos"] = [int(item.x()), int(item.y())]
        layout["stand_scale"] = round(item.scale(), 3)

    # 文本框 → text_area [x1, y1, x2, y2]
    if self.scene_items["main_text"]:
        item = self.scene_items["main_text"]
        rect = item.rect()
        p1 = item.mapToScene(rect.topLeft())    # 左上角
        p2 = item.mapToScene(rect.bottomRight()) # 右下角
        x1, y1 = int(p1.x()), int(p1.y())
        x2, y2 = int(p2.x()), int(p2.y())
        layout["text_area"] = [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]
```

---

## 🔗 与其他模块的交互

### 与 Core 模块的集成

```
creator_gui.py (入口 ~30 行)
  └─ 启动 gui.MainWindow

gui/main_window.py (主编辑器)
  ├─ 导入 core.utils
  │   ├─ load_global_config() → 获取上次编辑的角色 (从 global_config.yaml)
  │   └─ save_global_config() → 保存当前角色 (到 global_config.yaml)
  │
  ├─ 导入 core.renderer
  │   └─ CharacterRenderer.render() → 预览渲染 (preview_render)
  │
  └─ 导入 core.prebuild
      └─ prebuild_character() → 生成缓存 (generate_cache)
```

### 数据流

```
用户拖拽立绘调整位置
  ↓
ScalableImageItem.setPos()
  ↓
save_config() 触发
  ↓
_collect_scene_data()
  ├─ item.pos() → [x, y]
  └─ 写入 config["layout"]["stand_pos"]
  ↓
json.dump(config, config.json)
  ↓
main.py 启动时读取
  ↓
GalGameEngine → CharacterRenderer 使用配置渲染
```

---

## 📝 使用指南

### 新建角色完整流程

1. **启动编辑器**: `python creator_gui.py`
2. **新建角色**: `文件 → 新建角色` (Ctrl+N)
3. **填写信息**:
   - 角色 ID: `kotori` (仅字母数字下划线)
   - 显示名称: `五河琴里`
4. **导入资源**:
   - 点击 "立绘列表" 右侧 `+` 按钮，选择多张立绘
   - 点击 "背景列表" 右侧 `+` 按钮，选择一张背景
   - 点击 "更换底图" 按钮，选择对话框图片
5. **调整布局**:
   - 在画布中拖拽立绘到合适位置
   - 滚轮缩放立绘大小
   - 拖拽文本框调整位置和大小
6. **配置样式**:
   - 调整正文/名字字号
   - 点击颜色按钮选择文本颜色
7. **保存配置**: `Ctrl+S`
8. **生成缓存**: `工具 → 生成缓存`
9. **预览效果**: `F5` → 输入测试台词

---

## ⚠️ 已知限制

1. **缩放性能**: 大尺寸立绘实时缩放时可能卡顿
2. **撤销/重做**: 暂未实现操作历史功能
3. **自动保存**: 仅在手动保存时写入，易丢失未保存更改
4. **批量导入**: 仅支持单次多选，不支持拖拽导入

---

**维护者**: OuroChival-Shizue, makoMako
**最后更新**: 2025-11-28 14:14:40
**文档工具**: Claude Code + Serena MCP Server
