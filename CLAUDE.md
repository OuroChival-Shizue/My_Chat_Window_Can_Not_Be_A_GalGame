
## CLAUDE.md

# 🎮 My Chat Window Can Not Be A GalGame - AI 上下文文档

**文档版本**: 2.2 (手动发送模式)
**生成时间**: 2025-11-30
**项目类型**: Python 桌面应用 (Windows)
**核心技术栈**: PyQt6, Pillow, keyboard, pywin32
**Python 版本**: 3.10+

---

## 📋 项目愿景

将聊天体验 GalGame 化的通用工具，允许用户在任意聊天软件（QQ、微信、Discord 等）中输入文字后，自动渲染成带有角色立绘、对话框的精美图片，**粘贴到输入框后由用户手动确认发送**。

**核心价值**:

- 🚀 **自定义触发**: 支持用户自定义触发快捷键（默认 Enter，推荐 Shift+Enter）
- 🖼️ **预览后发送**: 图片生成后粘贴到输入框，用户确认无误后手动按 Enter 发送
- 🎭 **实时表情切换**: Alt+1~9 快捷键切换角色立绘
- 🛠️ **可视化编辑器**: 所见即所得的角色配置体验
- ⚡ **高性能缓存**: 预处理机制 + 内存缓存，生成速度极快
- 🔄 **热重载配置**: Ctrl+F5 无需重启即可应用新设置

---

## 🏗️ 架构总览

```mermaid
graph TB
    subgraph "用户入口层"
        A[main.py<br/>主程序入口]
        B[creator_gui.py<br/>编辑器入口]
    end

    subgraph "GUI 模块 (gui/)"
        C[MainWindow<br/>主窗口协调器]
        D[AssetsPanel<br/>资源面板]
        E[PropsPanel<br/>属性面板]
        F[canvas/items<br/>图形项]
        G[widgets/*<br/>自定义控件]
        G2[hotkey_dialog<br/>快捷键设置]
        H[workers/*<br/>后台任务]
    end

    subgraph "核心引擎层 (core/)"
        I[engine.py<br/>主引擎]
        J[listener.py<br/>键盘监听<br/>+热重载]
        K[renderer.py<br/>图像渲染]
        L[clipboard.py<br/>剪贴板]
        M[prebuild.py<br/>缓存预生成]
        N[utils.py<br/>配置管理]
    end

    subgraph "数据存储层"
        O[(assets/characters/<br/>角色数据)]
        P[(assets/cache/<br/>预渲染缓存)]
        Q[(assets/pre_scaled/<br/>预缩放背景)]
        R[global_config.json<br/>+trigger_hotkey]
    end

    A --> I
    B --> C
    C --> D
    C --> E
    C --> F
    C --> G
    C --> G2
    C --> H
    C --> K
    C --> M
    I --> J
    I --> K
    I --> L
    J --> N
    K --> O
    K --> P
    M --> O
    M --> P
    M --> Q
    N --> R

    style A fill:#e3f2fd
    style B fill:#e3f2fd
    style C fill:#fff3e0
    style I fill:#f3e5f5
    style J fill:#f3e5f5
    style K fill:#f3e5f5
    style G2 fill:#c8e6c9
```

---

## 📦 模块索引

### 🔹 用户入口

| 文件               | 职责                      |
| ------------------ | ------------------------- |
| `main.py`        | 角色选择、引擎启动        |
| `creator_gui.py` | 编辑器启动入口 (约 20 行) |

### 🔹 GUI 模块 (`gui/`)

| 子模块           | 文件                           | 职责                                               |
| ---------------- | ------------------------------ | -------------------------------------------------- |
| **入口**   | `__init__.py`                | 暴露 `MainWindow`                                |
| **常量**   | `constants.py`               | 全局常量、`CanvasConfig` 管理器                  |
| **主窗口** | `main_window.py`             | UI 组装、业务协调、设置菜单                        |
| **画布**   | `canvas/items.py`            | `ResizableTextItem`, `ScalableImageItem`       |
| **控件**   | `widgets/color_button.py`    | `ColorButton`                                    |
| **控件**   | `widgets/asset_list.py`      | `AssetListWidget`                                |
| **控件**   | `widgets/dialogs.py`         | `NewCharacterDialog`, `PrebuildProgressDialog` |
| **控件**   | `widgets/hotkey_dialog.py`   | `SettingsDialog`, `HotkeyEdit`                 |
| **面板**   | `panels/assets_panel.py`     | 左侧资源库面板                                     |
| **面板**   | `panels/props_panel.py`      | 右侧属性面板                                       |
| **后台**   | `workers/prebuild_worker.py` | 缓存生成线程                                       |

### 🔹 核心引擎 (`core/`)

| 文件             | 核心类/函数                                      | 职责                                             |
| ---------------- | ------------------------------------------------ | ------------------------------------------------ |
| `engine.py`    | `GalGameEngine`                                | 协调监听器、渲染器、剪贴板，**不自动发送** |
| `listener.py`  | `InputListener`                                | **可配置快捷键**、热重载、目标软件识别     |
| `renderer.py`  | `CharacterRenderer`                            | 加载资源、合成图像、绘制文字                     |
| `clipboard.py` | `get_text()`, `set_image()`                  | Win32 剪贴板读写                                 |
| `prebuild.py`  | `prebuild_character()`                         | 生成立绘×背景组合缓存                           |
| `utils.py`     | `load_global_config()`, `normalize_layout()` | 配置读写、布局归一化                             |

---

## 📂 目录结构

```text
项目根目录/
├── main.py                     # 主程序入口
├── creator_gui.py              # 编辑器入口 (精简后)
├── global_config.json          # 全局配置 (含 trigger_hotkey)
│
├── gui/                        # GUI 模块
│   ├── __init__.py             # 暴露 MainWindow
│   ├── constants.py            # 常量与 CanvasConfig
│   ├── main_window.py          # 主窗口 (~550 行)
│   ├── canvas/
│   │   ├── __init__.py
│   │   └── items.py            # 自定义图形项
│   ├── widgets/
│   │   ├── __init__.py
│   │   ├── color_button.py
│   │   ├── asset_list.py
│   │   ├── dialogs.py
│   │   └── hotkey_dialog.py    # 快捷键设置对话框
│   ├── panels/
│   │   ├── __init__.py
│   │   ├── assets_panel.py
│   │   └── props_panel.py
│   └── workers/
│       ├── __init__.py
│       └── prebuild_worker.py
│
├── core/                       # 核心引擎
│   ├── __init__.py
│   ├── engine.py               # ⭐ v2.2: 移除自动发送
│   ├── listener.py             # 支持可配置快捷键 + 热重载
│   ├── renderer.py
│   ├── clipboard.py
│   ├── prebuild.py
│   └── utils.py
│
└── assets/
    ├── characters/             # 角色数据
    │   └── <char_id>/
    │       ├── config.json
    │       ├── portrait/
    │       ├── background/
    │       └── textbox_bg.png
    ├── common/
    │   ├── fonts/
    │   │   └── LXGWWenKai-Medium.ttf
    │   └── background/         # 公共背景
    ├── cache/                  # 预渲染缓存
    │   └── <char_id>/
    │       ├── p_1__b_1.jpg
    │       └── _meta.json
    └── pre_scaled/             # 预缩放背景
        └── characters/<char_id>/background/
```

---

## ⌨️ 快捷键体系

### 主程序快捷键 (main.py)

| 快捷键                                | 功能                        | 说明                                |
| ------------------------------------- | --------------------------- | ----------------------------------- |
| **用户自定义** (默认 `enter`) | **生成图片并粘贴** ⭐ | 图片粘贴到输入框，需手动 Enter 发送 |
| `Enter` (手动)                      | 发送图片                    | 用户确认后手动按下发送              |
| `Alt + 1~9`                         | 切换立绘                    | 切换到列表中的第 1~9 张立绘         |
| `Ctrl + F5`                         | **热重载配置**        | 无需重启应用新的快捷键设置          |
| `Ctrl + F12`                        | 暂停/恢复                   | 临时暂停拦截功能                    |
| `Esc`                               | 退出程序                    | 完全关闭后台监听                    |

### 编辑器快捷键 (creator_gui.py)

| 快捷键       | 功能               |
| ------------ | ------------------ |
| `Ctrl + N` | 新建角色           |
| `Ctrl + S` | 保存配置           |
| `Ctrl + ,` | **打开设置** |
| `Ctrl + R` | 重载界面           |
| `F5`       | 渲染预览           |

---

## 🔧 自定义快捷键功能

### 设计背景

原本固定使用 `Enter` 作为触发键会导致以下问题：

- 发送图片时误触发（输入框为空时按 Enter）
- 无法正常换行
- 与某些聊天软件的快捷键冲突

### 解决方案

支持用户自定义触发快捷键，推荐使用 `Shift+Enter` 或 `Ctrl+Enter`：

- **组合键不会拦截原生 Enter**，保留正常发送功能
- 只有按下组合键时才触发"文字转图片"

### 配置流程

```
1. 打开 GUI 编辑器
   └─ python creator_gui.py

2. 打开设置对话框
   └─ 文件 → 设置 (Ctrl+,)

3. 设置快捷键
   ├─ 点击预设按钮 (如 "Shift+Enter")
   └─ 或点击输入框手动录制

4. 保存设置
   └─ 点击"保存"按钮

5. 在 main.py 中应用
   └─ 按 Ctrl+F5 热重载
   └─ 看到提示: "🔄 触发快捷键已更新: enter → shift+enter"
```

### 实现架构

```mermaid
graph LR
    A[SettingsDialog] -->|保存| B[global_config.json]
    B -->|trigger_hotkey| C[InputListener]
    D[Ctrl+F5] -->|reload_config| C
    C -->|动态注册| E[keyboard.add_hotkey]
```

---

## 🎨 GUI 模块详解 (`gui/`)

### `widgets/hotkey_dialog.py`

#### `HotkeyEdit` - 快捷键录制输入框

```python
class HotkeyEdit(QLineEdit):
    """支持按键录制的输入框"""
    hotkeyChanged = pyqtSignal(str)  # 快捷键变更信号

    def keyPressEvent(self, event):
        # 收集修饰键 (Ctrl/Alt/Shift)
        # 获取主键名称
        # 组合成 "ctrl+shift+enter" 格式
        # 发射 hotkeyChanged 信号
```

**键名转换**: Qt 键码 → keyboard 库兼容名称

```python
key_map = {
    Qt.Key.Key_Return: "enter",
    Qt.Key.Key_Space: "space",
    Qt.Key.Key_F1: "f1",
    # ...
}
```

#### `SettingsDialog` - 设置对话框

```python
class SettingsDialog(QDialog):
    """快捷键设置对话框"""

    def _init_ui(self):
        # 快捷键输入区域
        self.hotkey_edit = HotkeyEdit()
  
        # 预设按钮: Enter / Ctrl+Enter / Shift+Enter / Alt+S
  
        # 使用说明提示
  
        # 保存/取消按钮

    def _save_and_close(self):
        # 验证快捷键有效性
        # 检查是否与系统快捷键冲突
        # 保存到 global_config.json
```

### `main_window.py` 变更

新增菜单项和方法：

```python
# _create_menus() 中新增:
action_settings = QAction("设置 (&Settings)...", self)
action_settings.setShortcut("Ctrl+,")
action_settings.triggered.connect(self.open_settings)
file_menu.addAction(action_settings)

# 新增方法:
def open_settings(self):
    """打开设置对话框"""
    from .widgets import SettingsDialog
    dialog = SettingsDialog(self)
    dialog.exec()
```

---

## ⚙️ Core 模块详解 (`core/`)

### `utils.py` - 配置管理

```python
DEFAULT_CONFIG: Dict[str, Any] = {
    "current_character": "yuraa",
    "trigger_hotkey": "enter",  # 触发快捷键
    "global_hotkeys": {
        "copy_to_clipboard": "ctrl+shift+c",
        "show_character": "ctrl+shift+v",
    },
    "target_apps": ["QQ", "微信", "Discord", ...],
    "render": {
        "canvas_size": [2560, 1440],
        "cache_format": "jpeg",
        "jpeg_quality": 90,
        "use_memory_canvas_cache": True
    }
}
```

### `engine.py` - 主引擎 (v2.2 更新) ⭐

#### 核心变更：移除自动发送

```python
def _on_submit(self):
    # 1. 模拟 Ctrl+A 全选, Ctrl+X 剪切
    keyboard.send("ctrl+a")
    time.sleep(0.05)
    keyboard.send("ctrl+x")
    time.sleep(0.1)

    # 2. 获取剪贴板文本
    text = get_text().strip()

    if not text:
        print("🔕 剪贴板为空或非文本，尝试还原...")
        keyboard.send("ctrl+v")
        return

    print(f"📝 捕获文本: {text}")

    # 3. 渲染图片
    try:
        image = self.renderer.render(text, self.current_expression)
    except Exception as e:
        # ... 错误处理 ...

    # 4. 将图片写入剪贴板并粘贴（不自动发送）
    if set_image(image):
        time.sleep(0.1)
        keyboard.send("ctrl+v")
        # ⭐ v2.2: 移除自动发送，让用户手动确认
        # 旧代码: time.sleep(1); keyboard.press_and_release("enter")
        print("✅ 图片已粘贴到输入框，请按 Enter 发送")
    else:
        print("❌ 图片写入剪贴板失败")
        if set_text(text):
            keyboard.send("ctrl+v")
```

### `listener.py` - 键盘监听

#### 核心功能

```python
class InputListener:
    def __init__(self):
        config = load_global_config()
  
        # 读取可配置的触发快捷键
        self.trigger_hotkey: str = config.get("trigger_hotkey", "enter").lower().strip()
  
        # 判断是单键还是组合键（影响 suppress 行为）
        self._is_single_key = "+" not in self.trigger_hotkey
```

#### 快捷键注册逻辑

```python
def _register_trigger_hotkey(self):
    """注册触发快捷键"""
    # 单键（如 enter）需要 suppress=True 来拦截
    # 组合键（如 ctrl+enter）不需要 suppress
    suppress = self._is_single_key
    self.trigger_hotkey_handle = keyboard.add_hotkey(
        self.trigger_hotkey, 
        self._trigger_submit, 
        suppress=suppress
    )
```

#### 热重载功能

```python
def reload_config(self):
    """Ctrl+F5 触发的热重载"""
    config = load_global_config()
    new_hotkey = config.get("trigger_hotkey", "enter").lower().strip()

    if new_hotkey != self.trigger_hotkey:
        # 取消旧快捷键
        self._unregister_trigger_hotkey()
  
        # 更新配置
        self.trigger_hotkey = new_hotkey
        self._is_single_key = "+" not in self.trigger_hotkey
  
        # 注册新快捷键
        self._register_trigger_hotkey()
  
        print(f"🔄 触发快捷键已更新: {old} → {new_hotkey}")
```

---

## 📄 配置文件结构

### `global_config.json`

```json
{
    "current_character": "yuraa",
    "trigger_hotkey": "shift+enter",
    "global_hotkeys": {
        "copy_to_clipboard": "ctrl+shift+c",
        "show_character": "ctrl+shift+v"
    },
    "target_apps": ["QQ", "微信", "WeChat", "Discord", "Telegram", "钉钉", "Tim"],
    "render": {
        "canvas_size": [1920, 1080],
        "cache_format": "jpeg",
        "jpeg_quality": 90,
        "use_memory_canvas_cache": true
    }
}
```

### 快捷键格式说明

| 格式     | 示例                                       | 说明               |
| -------- | ------------------------------------------ | ------------------ |
| 单键     | `enter`, `space`, `f1`               | 需要 suppress 拦截 |
| 组合键   | `ctrl+enter`, `shift+enter`, `alt+s` | 不拦截原生按键     |
| 多修饰键 | `ctrl+shift+s`                           | 支持多个修饰键组合 |

---

## 🔄 核心工作流

### 主程序渲染流程 (v2.2 更新) ⭐

```
main.py → GalGameEngine
  ├─ ensure_character_cache()     # 检查/生成缓存
  ├─ CharacterRenderer(char_id)   # 初始化渲染器
  └─ InputListener 监听循环:
      ├─ 注册 trigger_hotkey (从配置读取)
      ├─ 注册 Ctrl+F5 → reload_config()  # 热重载
      ├─ 注册 Ctrl+F12 → toggle_pause()
      ├─ 注册 Alt+1~9 → 切换表情
      └─ trigger_hotkey 触发 (目标软件内):
          ├─ Ctrl+A, Ctrl+X 提取文本
          ├─ renderer.render(text, portrait_key, bg_key)
          ├─ set_image(pil_img)      # 写入剪贴板
          ├─ Ctrl+V 粘贴图片到输入框
          └─ ⭐ 等待用户手动按 Enter 发送
```

### 用户操作流程 (v2.2)

```
1. 用户在聊天输入框输入文字
2. 按下触发快捷键 (默认 Enter 或自定义)
3. 程序自动:
   ├─ 全选并剪切文字
   ├─ 渲染成 GalGame 风格图片
   └─ 粘贴图片到输入框
4. ⭐ 用户检查图片预览
5. ⭐ 用户手动按 Enter 发送
```

### 快捷键设置流程

```
GUI: SettingsDialog
  ├─ 用户点击 HotkeyEdit 输入框
  ├─ keyPressEvent 捕获按键
  │   ├─ 收集修饰键 (Ctrl/Alt/Shift)
  │   ├─ 获取主键名称
  │   └─ 组合成 "shift+enter" 格式
  ├─ 用户点击"保存"
  │   ├─ 验证快捷键有效性
  │   ├─ 检查冲突 (esc, ctrl+c, ctrl+v 等)
  │   └─ save_global_config({"trigger_hotkey": "shift+enter"})
  └─ 提示用户按 Ctrl+F5 应用

main.py: InputListener
  ├─ 用户按 Ctrl+F5
  ├─ reload_config() 被调用
  │   ├─ load_global_config()
  │   ├─ 比较新旧快捷键
  │   ├─ _unregister_trigger_hotkey()
  │   └─ _register_trigger_hotkey() (使用新快捷键)
  └─ 打印: "🔄 触发快捷键已更新: enter → shift+enter"
```

---

## 🎯 推荐快捷键配置

| 快捷键          | 优点           | 缺点               | 推荐场景                 |
| --------------- | -------------- | ------------------ | ------------------------ |
| `enter`       | 最自然         | 需要两次 Enter     | 习惯确认后发送           |
| `shift+enter` | 不影响正常发送 | 某些软件用这个换行 | **推荐大多数用户** |
| `ctrl+enter`  | 完全独立       | 需要记住           | 避免所有冲突             |
| `alt+s`       | 完全独立       | 不够直观           | 特殊需求                 |

---

## 🚀 快速上手

### 开发环境

```bash
# 克隆项目
git clone <repo_url>
cd My_Chat_Window_Can_Not_Be_A_GalGame

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 配置自定义快捷键

```bash
# 1. 运行编辑器
python creator_gui.py

# 2. 打开设置: 文件 → 设置 (Ctrl+,)

# 3. 选择 "Shift+Enter" 并保存

# 4. 运行主程序
python main.py

# 5. 按 Ctrl+F5 应用新快捷键
```

---

## 🔧 常见开发任务

### 添加新的快捷键预设

编辑 `gui/widgets/hotkey_dialog.py`:

```python
presets = [
    ("Enter", "enter"),
    ("Ctrl+Enter", "ctrl+enter"),
    ("Shift+Enter", "shift+enter"),
    ("Alt+S", "alt+s"),
    ("F9", "f9"),  # 新增预设
]
```

### 添加新的系统快捷键

编辑 `core/listener.py` 的 `start()` 方法:

```python
# 添加新的全局快捷键
keyboard.add_hotkey("ctrl+f6", self.some_new_function)
```

### 调试快捷键问题

```python
# 在 listener.py 中添加调试输出
def _trigger_submit(self):
    print(f"[DEBUG] 触发键: {self.trigger_hotkey}")
    print(f"[DEBUG] 是否单键: {self._is_single_key}")
    print(f"[DEBUG] 目标窗口: {self.is_target_window_active()}")
```

---

## ⚠️ 已知限制

1. **仅支持 Windows**: 依赖 `win32clipboard`, `win32gui`
2. **需要管理员权限**: 全局键盘钩子可能需要提权
3. **文本换行**: 简单按字符宽度计算，不支持复杂排版
4. **缓存占用**: N 立绘 × M 背景 = N×M 张图片
5. **快捷键冲突**: 部分组合键可能被系统或其他软件占用

---

## 📊 项目统计

### 代码规模 (v2.2)

| 模块           | 文件数 | 说明                |
| -------------- | ------ | ------------------- |
| `gui/`       | 13     | 含 hotkey_dialog.py |
| `core/`      | 6      | engine.py v2.2 更新 |
| **总计** | 19+    | -                   |

### 版本更新历史

| 版本 | 主要变更                          |
| ---- | --------------------------------- |
| v2.0 | GUI 模块化重构                    |
| v2.1 | 自定义快捷键、热重载              |
| v2.2 | ⭐ 移除自动发送，改为手动确认发送 |

---

**维护者**: OuroChival-Shizue, makoMako, IzumiShizuki

**开源协议**: MIT
