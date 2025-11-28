# 🎮 My Chat Window Can Not Be A GalGame
**(我的聊天窗口不可能是 GalGame)**

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)![PyQt6](https://img.shields.io/badge/PyQt-6.0+-green.svg)![License](https://img.shields.io/badge/License-MIT-yellow.svg)![Status](https://img.shields.io/badge/Status-Student%20Project-orange)

## 📖 简介
**这是一个出于对二次元角色的热爱，由一名学生开发者（也就是我）利用课余时间“拉”出来的项目。**

你是否想过，在 QQ、微信或 Discord 上与朋友聊天时，能像 GalGame（美少女游戏）一样，配合着角色的立绘、精美的对话框和表情差分来传达你的心意？

**My_Chat_Window_Can_Not_Be_A_GalGame** 就是为此而生的。它是一个无缝集成的聊天辅助工具，当你输入文字并按下回车时，它会自动将你的文字渲染成一张精美的 GalGame 对话截图，并自动发送出去。

本项目包含一个可视化的编辑器，虽然界面可能不算最华丽，但希望能让你轻松配置自己心爱的角色。

## ✨ 核心功能
*   **🚀 无感触发**：在任何聊天软件中输入文字，按下 `Enter` 键，瞬间生成图片并发送，无需手动截图。
*   **🎭 实时表情切换**：通过 `Alt + 1~9` 快捷键，在对话中实时切换角色的不同立绘（表情），让对话生动起来。
*   **🛠️ 可视化编辑器**：
    *   **所见即所得**：实时预览渲染效果。
    *   **自由布局**：鼠标拖拽调整立绘、文字区域的位置和大小。
    *   **自动贴合**：智能计算对话框位置，自动贴合底部。
*   **🎨 高度定制化**：支持自定义字体（内置霞鹜文楷）、字号、颜色、背景图、对话框样式。
*   **⚡ 高性能缓存**：内置预处理和缓存机制，生成速度极快，几乎无延迟。

## 🖼️ 效果展示

<img width="2560" height="1321" alt="image" src="https://github.com/user-attachments/assets/68a23079-4a58-4791-8c27-5e2a205f82a6" />
<img width="2560" height="1440" alt="cb3e3f5ab8c8dd52b808fdb1b096285c" src="https://github.com/user-attachments/assets/76ae7636-2367-440b-b6b2-d4f92725e9af" />

---
## 🙌 致敬与灵感
**本项目的灵感直接来源于大佬的项目：[manosaba_text_box (魔法少女的魔女裁判 文本框生成器)](https://github.com/oplivilqo/manosaba_text_box)**

*   **关于原项目**：`manosaba_text_box` 的功能已经很完善了，这里也推荐大家去玩魔裁，确实是很好的GalGame，记得给manosaba_text_box点个Star谢谢喵~
*   **关于本项目**：在惊叹于原项目创意的同时，我萌生了一个想法——**“如果能把这个功能做成通用的，让大家能把任何自己喜欢的老婆/女儿放进对话框里，岂不是更快乐？”**
    *   于是便有了这个通用的版本。
    *   希望能作为一种补充，为大家提供更多自定义的乐趣。

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
*   **新建角色**：点击 `文件` -> `新建角色`。
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

## ⌨️ 快捷键说明

| 快捷键 | 功能 | 说明 |
| :--- | :--- | :--- |
| **Enter** | 生成并发送 | 拦截回车键，将输入框文字转为图片发送 |
| **Alt + 1~9** | 切换立绘 | 切换到列表中的第 1~9 张立绘 (支持文件名排序) |
| **Esc** | 退出程序 | 完全关闭后台监听 |

## 📂 目录结构
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

## 📝 碎碎念 & 开发者说

作为一个还在摸索中的**学生党**，这个项目主要是为了满足自己的中二幻想而开发的。

*   **关于代码**：说实话，代码写得比较**菜**（甚至可能有点“屎山”的味道...）。很多功能都借助了AI工具，逻辑上可能不够严谨，架构也不算完美。
*   **关于Bug**：虽然我已经尽力修复了遇到的闪退和逻辑死锁，但难免会有漏网之鱼。如果你在使用过程中遇到了 Bug，或者觉得程序运行得不够优雅，**请大佬们轻喷** 🙏。
*   **关于期望**：这是一个“用爱发电”的练手项目，请不要对它抱有商业级软件的稳定性期望。

从最初简陋的脚本，到后来为了方便调整而重构的 GUI 编辑器，这个项目确实倾注了我很多心血。

特别感谢在开发过程中提供帮助的朋友。如果你也觉得这个项目有趣，或者它帮你更好地表达了对角色的爱，欢迎给一个 **Star ⭐**！这对我这个菜鸟开发者来说是最大的鼓励！

*本项目暂时为早期版本，未来（如果不挂科的话）会更新一些其他的功能，并努力优化一下。*

## 📄 开源协议
本项目采用 MIT 协议开源。你可以自由地使用、修改和分发，但请保留原作者的版权声明。

---
*Made with ❤️ (and a lot of bugs) by OuroChival-Shizue*
