# Box-of-GalGame-Sister（简要说明）

## 环境准备
- 安装 Python 3.9+（建议 64 位）。
- 安装依赖：`pip install -r requirements.txt`
- 运行环境需支持 Windows（键盘监听、剪贴板写入依赖 win32）。

## 目录概览
- `main.py`：监听聊天窗口，按 Enter 生成图片并粘贴发送。
- `creator_gui.py`：图形化配置器，调整立绘/背景/对话框与文本区域。
- `core/`：渲染、预构建缓存、监听等核心模块。
- `assets/characters/<char_id>/`：角色资源（立绘、背景、对话框底图、config）。
- `assets/common/`：通用字体、UI 资源，背景可作为回退。
- `assets/cache/`：预构建的背景+立绘合成底图。
- `run_main.bat` / `run_gui.bat`：一键启动脚本（需已安装依赖）。

## 快速开始
1. 依赖安装：`pip install -r requirements.txt`
2. 运行配置器：双击 `run_gui.bat`（或 `python creator_gui.py`）  
   - 资源菜单可添加立绘、背景、对话框底图；支持资源体检、生成缓存、预览生成。
   - 顶部可改显示名、调整布局和字号，保存后写入 `config.json`。
3. 运行主程序：双击 `run_main.bat`（或 `python main.py`）  
   - 控制台选择角色后进入监听模式：Enter 发送、Alt+1~9 切换表情，Esc 退出。

## 角色资源要求
- 立绘：放入 `assets/characters/<char_id>/portrait/`，支持 png/jpg/jpeg。
- 背景：放入 `assets/characters/<char_id>/background/`；若为空会回退到 `assets/common/background/`（如存在）。
- 对话框底图：放入角色根目录，`config.json` 的 `assets.dialog_box` 指向文件名。
- 字体：默认使用 `assets/common/fonts/LXGWWenKai-Medium.ttf`，缺失会回退系统字体。

## 常用操作（GUI）
- 新建角色：菜单「文件 -> 新建角色」。
+- 添加资源：菜单「资源 -> 添加立绘/背景/对话框底图」。
- 预览生成：菜单「工具 -> 预览生成」。
- 生成缓存：菜单「工具 -> 生成缓存」以减轻运行时合成。
- 资源体检：菜单「工具 -> 资源体检」检查缺失资源并提示修复。

## 运行提示
- 监听模式默认白名单窗口包含 QQ/微信/Discord/Telegram/钉钉等，可在 `core/listener.py` 修改。
- 若剪贴板写入失败，可尝试以管理员运行或关闭安全/防护软件拦截。
- 预览或运行时渲染出错，多半是资源缺失或路径配置错误，可先用资源体检排查。

