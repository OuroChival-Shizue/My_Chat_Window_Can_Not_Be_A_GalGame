import os
import json

BASE_PATH = "assets"
CHAR_DIR = os.path.join(BASE_PATH, "characters")

def sync_character(char_id: str):
    char_root = os.path.join(CHAR_DIR, char_id)
    config_path = os.path.join(char_root, "config.json")
    
    if not os.path.exists(config_path):
        print(f"⚠️ [{char_id}] 缺少 config.json，跳过")
        return

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ [{char_id}] 配置文件损坏: {e}")
        return

    modified = False
    layout = config.get("layout", {})
    assets = config.get("assets", {})

    # 1. 检查当前立绘是否存在
    curr_p = layout.get("current_portrait")
    if curr_p:
        p_path = os.path.join(char_root, "portrait", curr_p)
        if not os.path.exists(p_path):
            print(f"  🔧 [{char_id}] 立绘 '{curr_p}' 不存在，已重置")
            layout["current_portrait"] = ""
            modified = True

    # 2. 检查当前背景是否存在
    curr_bg = layout.get("current_background")
    if curr_bg:
        # 背景可能在角色目录，也可能在 common 目录
        bg_path_1 = os.path.join(char_root, "background", curr_bg)
        bg_path_2 = os.path.join(BASE_PATH, "common", "background", curr_bg)
        if not os.path.exists(bg_path_1) and not os.path.exists(bg_path_2):
            print(f"  🔧 [{char_id}] 背景 '{curr_bg}' 不存在，已重置")
            layout["current_background"] = ""
            modified = True

    # 3. 检查对话框底图
    box_name = assets.get("dialog_box")
    if box_name:
        box_path = os.path.join(char_root, box_name)
        if not os.path.exists(box_path):
            print(f"  🔧 [{char_id}] 对话框 '{box_name}' 不存在，重置为默认")
            assets["dialog_box"] = "textbox_bg.png"
            modified = True

    # 4. (可选) 扫描文件夹，如果发现 config 里没记录的新字段可以补全
    # 目前 config.json 主要是存状态，不需要存文件列表，所以这里不做额外操作

    if modified:
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            print(f"✅ [{char_id}] 配置已修复并保存")
        except Exception as e:
            print(f"❌ [{char_id}] 保存失败: {e}")
    else:
        print(f"ok [{char_id}] 配置正常")

def main():
    if not os.path.exists(CHAR_DIR):
        print(f"❌ 找不到目录: {CHAR_DIR}")
        return

    print("🔄 开始同步角色配置...")
    chars = [d for d in os.listdir(CHAR_DIR) if os.path.isdir(os.path.join(CHAR_DIR, d))]
    
    if not chars:
        print("没有找到任何角色。")
        return

    for char_id in chars:
        sync_character(char_id)
    
    print("\n✨ 同步完成！")

if __name__ == "__main__":
    main()
