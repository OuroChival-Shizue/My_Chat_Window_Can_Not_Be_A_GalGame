import os
import json
from typing import List, Tuple
from PIL import Image

BASE_PATH = "assets"
CACHE_PATH = "assets/cache"
CANVAS_SIZE = (2560, 1440)


def ensure_dir(path: str) -> None:
    if not os.path.exists(path):
        os.makedirs(path)


def _list_images(folder: str) -> List[str]:
    exts = (".png", ".jpg", ".jpeg")
    if not os.path.exists(folder):
        return []
    return sorted([f for f in os.listdir(folder) if f.lower().endswith(exts)])


def _expected_cache_count(portraits: List[str], backgrounds: List[str]) -> int:
    return len(portraits) * len(backgrounds)


def _cache_is_complete(char_id: str, portraits: List[str], backgrounds: List[str]) -> bool:
    if not portraits or not backgrounds:
        return False
    cache_dir = os.path.join(CACHE_PATH, char_id)
    expected = _expected_cache_count(portraits, backgrounds)
    if not os.path.exists(cache_dir):
        return False
    existing = len([f for f in os.listdir(cache_dir) if f.lower().endswith(".png")])
    return existing >= expected


def _fit_dialog_box_to_canvas(box_img: Image.Image) -> Tuple[Image.Image, Tuple[int, int]]:
    """Resize dialog box to canvas width and bottom align."""
    canvas_w, canvas_h = CANVAS_SIZE
    if box_img.width != canvas_w:
        scale = canvas_w / box_img.width
        new_h = int(box_img.height * scale)
        box_img = box_img.resize((canvas_w, new_h), Image.LANCZOS)
    box_pos = (0, canvas_h - box_img.height)
    return box_img, box_pos


def prebuild_character(char_id: str, base_path: str = BASE_PATH, cache_path: str = CACHE_PATH, force: bool = False) -> None:
    """Generate cached background+portrait composites for a character."""
    print(f"🚧 开始预处理角色: {char_id}")

    char_root = os.path.join(base_path, "characters", char_id)
    config_path = os.path.join(char_root, "config.json")
    if not os.path.exists(config_path):
        print(f"❌ 找不到配置 {config_path}")
        return

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    layout = config.get("layout", {})
    stand_pos = tuple(layout.get("stand_pos", [0, 0]))
    stand_scale = layout.get("stand_scale", 1.0)
    stand_on_top = layout.get("stand_on_top", False)

    portrait_dir = os.path.join(char_root, "portrait")
    bg_dir = os.path.join(char_root, "background")
    box_path = os.path.join(char_root, config.get("assets", {}).get("dialog_box", "textbox_bg.png"))

    portraits = _list_images(portrait_dir)
    backgrounds = _list_images(bg_dir)

    if not portraits:
        print("⚠️ 没有立绘，跳过")
        return
    if not backgrounds:
        print("⚠️ 没有背景，跳过")
        return

    if not force and _cache_is_complete(char_id, portraits, backgrounds):
        print("✅ 缓存已存在，跳过预处理")
        return

    if not os.path.exists(box_path):
        print(f"❗ 找不到对话框图片 {box_path}")
        return
    raw_box_img = Image.open(box_path).convert("RGBA")
    box_img, box_pos = _fit_dialog_box_to_canvas(raw_box_img)

    char_cache_dir = os.path.join(cache_path, char_id)
    ensure_dir(char_cache_dir)

    total = _expected_cache_count(portraits, backgrounds)
    count = 0

    for p_file in portraits:
        p_img = Image.open(os.path.join(portrait_dir, p_file)).convert("RGBA")
        if stand_scale != 1.0:
            new_w = int(p_img.width * stand_scale)
            new_h = int(p_img.height * stand_scale)
            p_img = p_img.resize((new_w, new_h), Image.LANCZOS)

        p_key = os.path.splitext(p_file)[0]

        for b_file in backgrounds:
            b_key = os.path.splitext(b_file)[0]

            canvas = Image.new("RGBA", CANVAS_SIZE)

            bg_img = Image.open(os.path.join(bg_dir, b_file)).convert("RGBA")
            bg_resized = bg_img.resize(CANVAS_SIZE, Image.LANCZOS)
            canvas.paste(bg_resized, (0, 0))

            if stand_on_top:
                canvas.paste(box_img, box_pos, box_img)
                canvas.paste(p_img, stand_pos, p_img)
            else:
                canvas.paste(p_img, stand_pos, p_img)
                canvas.paste(box_img, box_pos, box_img)

            save_name = f"p_{p_key}__b_{b_key}.png"
            save_path = os.path.join(char_cache_dir, save_name)
            canvas.save(save_path, "PNG", optimize=True)

            count += 1
            print(f"[{count}/{total}] 已生成 {save_name}")

    print(f"✅ {char_id} 预处理完成，共生成 {count} 张底图。\n")


def ensure_character_cache(char_id: str, base_path: str = BASE_PATH, cache_path: str = CACHE_PATH) -> None:
    """Check cache presence; if incomplete, prebuild automatically."""
    char_root = os.path.join(base_path, "characters", char_id)
    portrait_dir = os.path.join(char_root, "portrait")
    bg_dir = os.path.join(char_root, "background")

    portraits = _list_images(portrait_dir)
    backgrounds = _list_images(bg_dir)

    if _cache_is_complete(char_id, portraits, backgrounds):
        return
    prebuild_character(char_id, base_path=base_path, cache_path=cache_path, force=True)


if __name__ == "__main__":
    characters_root = os.path.join(BASE_PATH, "characters")
    for d in os.listdir(characters_root):
        if os.path.isdir(os.path.join(characters_root, d)):
            prebuild_character(d)
