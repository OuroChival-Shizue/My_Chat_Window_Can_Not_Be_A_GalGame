# 🎮 My Chat Window Can Not Be A GalGame
**(我的聊天窗口不可能是 GalGame)**

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![PyQt6](https://img.shields.io/badge/PyQt-6.0+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)
![Status](https://img.shields.io/badge/Status-Student%20Project-orange)

## 📖 简介

**这是一个出于对二次元角色的热爱，由一名学生开发者（也就是我）利用课余时间"拉"出来的项目。**

你是否想过，在 QQ、微信或 Discord 上与朋友聊天时，能像 GalGame（美少女游戏）一样，配合着角色的立绘、精美的对话框和表情差分来传达你的心意？

**My_Chat_Window_Can_Not_Be_A_GalGame** 就是为此而生的。它是一个无缝集成的聊天辅助工具，当你输入文字并按下回车时，它会自动将你的文字渲染成一张精美的 GalGame 对话截图，并自动发送出去。

本项目包含一个可视化的编辑器，虽然界面可能不算最华丽，但希望能让你轻松配置自己心爱的角色。

## ✨ 核心功能

* **🚀 无感触发**：在任何聊天软件中输入文字，按下 `Enter` 键，瞬间生成图片并发送，无需手动截图。
* **🎭 实时表情切换**：通过 `Alt + 1~9` 快捷键，在对话中实时切换角色的不同立绘（表情），让对话生动起来。
* **🛠️ 可视化编辑器**：
    * **所见即所得**：实时预览渲染效果。
    * **自由布局**：鼠标拖拽调整立绘、文字区域的位置和大小。
    * **多分辨率支持**：从 720p 到 4K，自由切换画布尺寸。
    * **自动贴合**：智能计算对话框位置，自动贴合底部。
* **🎨 高度定制化**：支持为每个角色配置独立字体（内置霞鹜文楷）、字号、颜色、背景图、对话框样式、台词前后缀。
* **⚡ 高性能缓存**：三级缓存体系（内存 → 磁盘 → 预缩放），生成速度极快，几乎无延迟。

## 🖼️ 效果展示

<img width="2560" height="1321" alt="编辑器界面" src="https://github.com/user-attachments/assets/68a23079-4a58-4791-8c27-5e2a205f82a6" />
<img width="2560" height="1440" alt="渲染效果" src="https://github.com/user-attachments/assets/76ae7636-2367-440b-b6b2-d4f92725e9af" />

---

## 🙌 致敬与灵感

**本项目的灵感直接来源于大佬的项目：[manosaba_text_box (魔法少女的魔女裁判 文本框生成器)](https://github.com/oplivilqo/manosaba_text_box)**

* **关于原项目**：`manosaba_text_box` 的功能已经很完善了，这里也推荐大家去玩魔裁，确实是很好的 GalGame，记得给 manosaba_text_box 点个 Star 谢谢喵~
* **关于本项目**：在惊叹于原项目创意的同时，我萌生了一个想法——**"如果能把这个功能做成通用的，让大家能把任何自己喜欢的老婆/女儿放进对话框里，岂不是更快乐？"**
    * 于是便有了这个通用的版本。
    * 希望能作为一种补充，为大家提供更多自定义的乐趣。

---

## 📦 安装与使用

### 1. 环境准备

确保你的电脑上安装了 Python 3.10 或更高版本。

```bash
# 克隆项目
git clone https://github.com/OuroChival-Shizue/My_Chat_Window_Can_Not_Be_A_GalGame.git
cd My_Chat_Window_Can_Not_Be_A_GalGame

# 方式 A: 使用虚拟环境（推荐，不污染系统 Python）
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt

# 方式 B: 直接安装到系统 Python
pip install -r requirements.txt
```

> 💡 **提示**: 批处理文件 (`run_gui.bat`, `run_main.bat`) 已兼容两种方式。如果存在 `.venv` 目录则自动使用虚拟环境，否则使用系统 Python。

### 2. 配置角色

运行编辑器，配置你的老婆/女儿：

```bash
# 运行可视化编辑器
python creator_gui.py
# 或者直接运行 run_gui.bat
```

* **新建角色**：点击 `文件` → `新建角色`
* **导入素材**：将立绘文件（PNG）和背景图导入左侧的资源列表
* **调整布局**：在中间画布上拖动立绘、文字框，调整到你满意的位置
* **滚轮缩放**：选中立绘后滚动鼠标滚轮调整大小
* **保存**：`Ctrl + S` 保存配置
* **生成缓存**：`工具` → `生成缓存`（首次使用或修改后需要执行）

### 3. 启动引擎

配置完成后，启动主程序开始使用：

```bash
# 启动监听引擎
python main.py
# 或者直接运行 run_main.bat
```

在控制台选择你要加载的角色，看到 `🚀 引擎已启动` 字样后，即可去聊天软件里使用了！

---

## ⌨️ 快捷键说明

| 快捷键 | 功能 | 说明 |
| :--- | :--- | :--- |
| **Enter** | 生成并发送 | 拦截回车键，将输入框文字转为图片发送 |
| **Alt + 1~9** | 切换立绘 | 切换到列表中的第 1~9 张立绘（按文件名排序） |
| **Ctrl + F12** | 暂停/恢复 | 临时暂停拦截功能 |
| **Esc** | 退出程序 | 完全关闭后台监听 |

---

## 📂 目录结构

```text
My_Chat_Window.../
├── assets/
│   ├── characters/           # 角色数据
│   │   └── [角色ID]/
│   │       ├── portrait/     # 立绘文件夹
│   │       ├── background/   # 背景文件夹
│   │       ├── fonts/        # 自定义字体文件夹 (可选)
│   │       ├── config.yaml   # 角色配置
│   │       └── textbox_bg.png
│   ├── common/               # 公共资源
│   │   ├── fonts/            # 默认字体 (霞鹜文楷)
│   │   └── background/       # 通用背景
│   ├── cache/                # 预渲染缓存 (自动生成)
│   └── pre_scaled/           # 预缩放背景 (自动生成)
│
├── gui/                      # GUI 模块 (v2.0 重构)
│   ├── main_window.py        # 主窗口
│   ├── constants.py          # 常量与配置
│   ├── canvas/               # 画布组件
│   ├── widgets/              # 自定义控件
│   ├── panels/               # 面板组件
│   └── workers/              # 后台任务
│
├── core/                     # 核心引擎
│   ├── engine.py             # 主引擎
│   ├── renderer.py           # 图像渲染
│   ├── listener.py           # 键盘监听
│   ├── clipboard.py          # 剪贴板操作
│   ├── prebuild.py           # 缓存预生成
│   └── utils.py              # 工具函数
│
├── creator_gui.py            # 编辑器入口
├── main.py                   # 主程序入口
├── global_config.yaml        # 全局配置
└── requirements.txt          # 依赖列表
```

---

## ⚙️ 高级配置

### 全局配置 (global_config.yaml)

```yaml
current_character: your_waifu          # 编辑器启动时默认选择的角色
trigger_hotkey: enter                  # 控制台模式下触发图片生成的快捷键
global_hotkeys:
  copy_to_clipboard: ctrl+shift+c     # 控制台模式: 复制最后一张图到剪贴板
  show_character: ctrl+shift+v        # 控制台模式: 显示/隐藏角色窗口
render:
  cache_format: jpeg                  # 预构建缓存格式：jpeg / png
  jpeg_quality: 90                    # cache_format 为 jpeg 时使用的质量
  use_memory_canvas_cache: true       # 是否在内存缓存画布，减少 IO
```

| 配置项 | 说明 |
|--------|------|
| `trigger_hotkey` | 触发图片生成的快捷键（支持单键或组合键） |
| `global_hotkeys.copy_to_clipboard` | 将渲染结果复制到剪贴板的快捷键 |
| `global_hotkeys.show_character` | 显示角色窗口的快捷键 |
| `cache_format` | 缓存格式：`jpeg`（小而快）或 `png`（无损） |
| `jpeg_quality` | JPEG 质量 (1-100) |
| `use_memory_canvas_cache` | 是否在内存缓存画布，减少 IO |

> 注意：台词前后缀和高级名称样式配置已移至各角色的 `config.yaml` 文件中的 `style` 字段。
> 画布分辨率由每个角色 `config.yaml` 的 `layout._canvas_size` 决定，切换角色时会自动加载对应分辨率。

### 角色配置 (assets/characters/[角色ID]/config.yaml)

每个角色的样式配置在其各自的 `config.yaml` 文件中：

```yaml
style:
  mode: basic                       # 名字样式模式: basic / advanced
  font_file: fonts/custom.ttf       # 自定义字体路径 (可选，相对于角色目录)
  text_wrapper:
    type: preset                    # 台词前后缀类型: none / preset / custom
    preset: corner_single           # 预设类型: corner_single (「」) / corner_double (『』)
    prefix: "「"
    suffix: "」"
  basic:
    font_size: 40
    text_color: [255, 255, 255]
    name_font_size: 30
    name_color: [255, 85, 255]
  advanced:
    name_layers:
      warden:                       # 特定角色名的高级样式
        - text: "典"
          position: [0, 0]
          font_color: [195, 209, 231]
          font_size: 196
        - text: "狱"
          position: [200, 100]
          font_color: [255, 255, 255]
          font_size: 92
        - text: "长"
          position: [300, 50]
          font_color: [255, 255, 255]
          font_size: 147
      default:                      # 默认样式
        - text: "{name}"
          position: [0, 0]
          font_color: [255, 85, 255]
          font_size: 32
```

#### 样式配置说明

- **自定义字体** (v2.3 新增)：通过 `font_file` 字段为角色指定专属字体，支持 `.ttf` 格式。路径相对于角色目录（如 `fonts/lolita.ttf`）。未设置时使用默认的霞鹜文楷字体。
- **台词前后缀**：`text_wrapper.type` 可选 `none`、`preset`（内置「」「」/『』『』）、`custom`（自定义前后缀）
- **名字样式模式**：`mode` 可选 `basic`（使用字号/颜色）或 `advanced`（启用多层叠加）
- **高级名称配置**：`name_layers` 支持为不同角色名配置多层文本效果，键为角色名，值为图层数组（支持 `{name}` 占位符）

#### 高级名称字段说明

- `text`：要绘制的字符，可使用 `{name}` 占位符自动替换为当前角色名称
- `position`：相对 `layout.name_pos` 的偏移量 `[x, y]`，单位为像素
- `font_color`：RGB 颜色数组
- `font_size`：字号，单位为像素
- `name_layers` 字典的键为角色名称；若找不到匹配的键，将使用 `default` 作为回退

#### 在 GUI 中配置

- **自定义字体**：在属性面板的"自定义字体"区域，点击"选择字体文件..."导入 `.ttf` 字体，字体会自动复制到角色的 `fonts/` 目录
- **台词前后缀**：在属性面板直接切换（「」「」 / 『』『』 / 自定义）
- **高级名称**：勾选"启用高级名称 YAML"后展开输入框编辑 `name_layers` 配置

---

## 📝 碎碎念 & 开发者说

作为一个还在摸索中的**学生党**，这个项目主要是为了满足自己的中二幻想而开发的。

* **关于代码**：经过 v2.0 的重构，代码结构已经比最初好了很多。GUI 部分从一个 1400+ 行的"屎山"拆分成了模块化的架构，维护起来终于不那么头疼了。
* **关于 Bug**：虽然我已经尽力修复了遇到的闪退和逻辑死锁，但难免会有漏网之鱼。如果你在使用过程中遇到了 Bug，欢迎提 Issue 或 PR！
* **关于期望**：这是一个"用爱发电"的练手项目，请不要对它抱有商业级软件的稳定性期望。

从最初简陋的脚本，到后来为了方便调整而重构的 GUI 编辑器，再到现在模块化的架构，这个项目确实倾注了很多心血。

如果你也觉得这个项目有趣，或者它帮你更好地表达了对角色的爱，欢迎给一个 **Star ⭐**！这对我这个菜鸟开发者来说是最大的鼓励！

---

## 🤝 致谢

感谢以下朋友对本项目的贡献：

* **[makoMako](https://github.com/makoMako)** - 代码优化与功能完善
* **[IzumiShizuki](https://github.com/IzumiShizuki)** - 代码贡献与问题修复
* **[ProjektMing](https://github.com/ProjektMing)** - 代码质量提升和健壮性改进
---

## 📄 开源协议

本项目采用 MIT 协议开源。你可以自由地使用、修改和分发，但请保留原作者的版权声明。

---

<p align="center">
  <i>Made with ❤️ (and a lot of bug) by OuroChival-Shizue</i>
  <br>
  <i>愿每个人都能和自己喜欢的角色愉快地聊天~</i>
</p>
