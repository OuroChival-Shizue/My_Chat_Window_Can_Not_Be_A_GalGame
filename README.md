# 🎮 My Chat Window Can Not Be A GalGame
### (我的聊天窗口不可能是 GalGame)


![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![PyQt6](https://img.shields.io/badge/GUI-PyQt6-green) ![License](https://img.shields.io/badge/License-MIT-orange)


## 📖 简介 (Introduction)

这是一个出于对二次元角色的热爱而诞生的项目。

你是否想过，在 QQ、微信或 Discord 上与朋友聊天时，能像 GalGame（美少女游戏）一样，配合着角色的立绘、精美的对话框和表情差分来传达你的心意？

**My_Chat_Window_Can_Not_Be_A_GalGame** 就是为此而生的。它是一个**无缝集成**的聊天辅助工具，当你输入文字并按下回车时，它会自动将你的文字渲染成一张精美的 GalGame 对话截图，并自动发送出去。

本项目包含一个**强大的可视化编辑器**，让你能轻松配置自己心爱的角色。

---

## ✨ 核心功能 (Features)

*   **🚀 无感触发**：在任何聊天软件中输入文字，按下 `Enter` 键，瞬间生成图片并发送，无需手动截图。
*   **🎭 实时表情切换**：通过 `Alt + 1~9` 快捷键，在对话中实时切换角色的不同立绘（表情），让对话生动起来。
*   **🛠️ 强大的可视化编辑器**：
    *   **所见即所得**：实时预览渲染效果。
    *   **拖拽操作**：支持直接拖拽图片文件导入立绘和背景。
    *   **自由布局**：鼠标拖拽调整对话框、立绘、文字区域的位置和大小。
    *   **自动贴合**：智能计算对话框位置，自动贴合底部。
*   **🎨 高度定制化**：支持自定义字体（内置霞鹜文楷）、字号、颜色、背景图、对话框样式。
*   **⚡ 高性能缓存**：内置预处理和缓存机制，生成速度极快，几乎无延迟。

---

## 🖼️ 效果展示 (Demo)

<img width="2560" height="1321" alt="image" src="https://github.com/user-attachments/assets/68a23079-4a58-4791-8c27-5e2a205f82a6" />
<img width="2560" height="1440" alt="cb3e3f5ab8c8dd52b808fdb1b096285c" src="https://github.com/user-attachments/assets/76ae7636-2367-440b-b6b2-d4f92725e9af" />

---

## 📦 安装与使用 (Installation & Usage)

### 1. 环境准备
确保你的电脑上安装了 Python 3.10 或更高版本。

```bash
# 克隆项目
git clone https://github.com/OuroChival-Shizue/My_Chat_Window_Can_Not_Be_A_GalGame.git
cd My_Chat_Window_Can_Not_Be_A_GalGame

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置角色 (GUI)
运行编辑器，配置你的老婆/女儿：

```bash
# 运行可视化编辑器
python creator_gui.py
# 或者直接运行 run_gui.bat
```

*   **新建角色**：点击 `文件 -> 新建角色`。
*   **导入素材**：将立绘文件（PNG）和背景图导入左侧的资源列表。
*   **调整布局**：在中间画布上拖动立绘文字框，调整到你满意的位置。
*   **保存**：`Ctrl + S` 保存配置。

### 3. 启动引擎
配置完成后，启动主程序开始使用：

```bash
# 启动监听引擎
python main.py
# 或者直接运行 run_main.bat
```

在控制台选择你要加载的角色，看到 `🚀 引擎已启动` 字样后，即可去聊天软件里使用了！

---

## ⌨️ 快捷键说明 (Hotkeys)

| 快捷键 | 功能 | 说明 |
| :--- | :--- | :--- |
| **Enter** | **生成并发送** | 拦截回车键，将输入框文字转为图片发送 |
| **Alt + 1~9** | **切换立绘** | 切换到列表中的第 1~9 张立绘 (支持文件名排序) |
| **Esc** | **退出程序** | 完全关闭后台监听 |

---

## 📂 目录结构 (Structure)

```text
My_Chat_Window.../
├── assets/
│   ├── characters/       # 存放所有角色的数据
│   │   └── [角色ID]/
│   │       ├── portrait/    # 立绘文件夹
│   │       ├── background/  # 背景文件夹
│   │       └── config.json  # 角色配置文件
│   ├── common/           # 公共资源 (字体、通用背景)
│   └── cache/            # 生成的图片缓存 (自动生成)
├── core/                 # 核心代码 (渲染器、监听器、引擎)
├── creator_gui.py        # 可视化编辑器入口
├── main.py               # 主程序入口
└── requirements.txt      # 依赖列表
```

---

## 📝 开发者说 (Developer's Note)

从最初简陋的脚本，到后来为了方便调整而重构的 GUI 编辑器，再到解决各种闪退和逻辑死锁的 Bug，这个项目倾注了我很多心血。(指tokens)

特别感谢在开发过程中提供帮助的朋友。如果你也觉得这个项目有趣，或者它帮你更好地表达了对角色的爱，欢迎给一个 Star ⭐！

本项目暂时为早期版本，未来会更新一些其他的功能，并对已有功能做出优化。

## 📄 开源协议 (License)

本项目采用 MIT 协议开源。你可以自由地使用、修改和分发，但请保留原作者的版权声明。

---
