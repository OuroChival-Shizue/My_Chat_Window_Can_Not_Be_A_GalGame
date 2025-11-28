import hashlib
import json
import os
from typing import Callable, Dict, List, Tuple

from PIL import Image

try:
    from .utils import load_global_config, normalize_layout
except Exception:  # pragma: no cover - fallback for standalone runs
    def load_global_config() -> Dict[str, object]:
        return {}

    def normalize_layout(layout, canvas_size):
        return layout or {}

def _load_render_preferences() -> Tuple[Tuple[int, int], str, str, int]:
    cfg = load_global_config() or {}
    render = cfg.get("render", {})
    canvas = tuple(render.get("canvas_size", (2560, 1440)))  # type: ignore[arg-type]
    cache_format = str(render.get("cache_format", "jpeg")).lower()
    if cache_format not in {"jpeg", "png"}:
        cache_format = "jpeg"
    cache_ext = ".jpg" if cache_format == "jpeg" else ".png"
    jpeg_quality = int(render.get("jpeg_quality", 90))
    return canvas, cache_format, cache_ext, jpeg_quality

CANVAS_SIZE: Tuple[int, int] = (2560, 1440)
CACHE_FORMAT: str = "jpeg"
CACHE_EXT: str = ".jpg"
JPEG_QUALITY: int = 90
SCALED_TAG: str = "@2560x1440"


def _refresh_render_preferences() -> None:
    global CANVAS_SIZE, CACHE_FORMAT, CACHE_EXT, JPEG_QUALITY, SCALED_TAG
    CANVAS_SIZE, CACHE_FORMAT, CACHE_EXT, JPEG_QUALITY = _load_render_preferences()
    SCALED_TAG = f"@{CANVAS_SIZE[0]}x{CANVAS_SIZE[1]}"


_refresh_render_preferences()

BASE_PATH = "assets"
CACHE_PATH = os.path.join(BASE_PATH, "cache")
SCALED_TAG = f"@{CANVAS_SIZE[0]}x{CANVAS_SIZE[1]}"

ProgressCallback = Callable[[str, int, int, str], None]


def ensure_dir(path: str) -> None:
    if not os.path.exists(path):
        os.makedirs(path)


def _notify_progress(
    callback: ProgressCallback | None,
    event: str,
    current: int,
    total: int,
    message: str,
) -> None:
    if not callback:
        return
    try:
        callback(event, current, total, message)
    except Exception:
        pass


def _list_images(folder: str) -> List[str]:
    if not os.path.exists(folder):
        return []
    return sorted(
        f
        for f in os.listdir(folder)
        if f.lower().endswith((".png", ".jpg", ".jpeg"))
    )


def _collect_background_entries(char_id: str, base_path: str) -> List[Tuple[str, str]]:
    char_dir = os.path.join(base_path, "characters", char_id, "background")
    common_dir = os.path.join(base_path, "common", "background")

    entries: List[Tuple[str, str]] = []
    seen: set[str] = set()
    if os.path.isdir(char_dir):
        for name in _list_images(char_dir):
            entries.append((name, os.path.join(char_dir, name)))
            seen.add(name)
    if os.path.isdir(common_dir):
        for name in _list_images(common_dir):
            if name in seen:
                continue
            entries.append((name, os.path.join(common_dir, name)))
            seen.add(name)
    return entries


def _expected_cache_count(portraits: List[str], backgrounds: List[str]) -> int:
    return len(portraits) * len(backgrounds)


def _cache_meta_path(char_id: str, cache_path: str = CACHE_PATH) -> str:
    return os.path.join(cache_path, char_id, "_meta.json")


def _update_hash_with_file(h: "hashlib._Hash", path: str) -> None:
    try:
        stat = os.stat(path)
    except FileNotFoundError:
        return
    normalized = path.replace("\\", "/")
    h.update(normalized.encode("utf-8"))
    h.update(str(stat.st_mtime_ns).encode("utf-8"))
    h.update(str(stat.st_size).encode("utf-8"))


def _compute_source_signature(char_id: str, base_path: str) -> str:
    h = hashlib.sha1()
    h.update(repr(CANVAS_SIZE).encode("utf-8"))
    h.update(CACHE_FORMAT.encode("utf-8"))

    char_root = os.path.join(base_path, "characters", char_id)
    config_path = os.path.join(char_root, "config.json")
    _update_hash_with_file(h, config_path)

    portrait_dir = os.path.join(char_root, "portrait")
    for file in _list_images(portrait_dir):
        _update_hash_with_file(h, os.path.join(portrait_dir, file))

    bg_entries = _collect_background_entries(char_id, base_path)
    for _, bg_path in bg_entries:
        _update_hash_with_file(h, bg_path)

    return h.hexdigest()


def _load_cache_meta(char_id: str, cache_path: str = CACHE_PATH) -> Dict[str, object]:
    meta_path = _cache_meta_path(char_id, cache_path)
    if not os.path.exists(meta_path):
        return {}
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_cache_meta(
    char_id: str,
    portraits: List[str],
    backgrounds: List[str],
    base_path: str,
    cache_path: str,
) -> None:
    cache_dir = os.path.join(cache_path, char_id)
    ensure_dir(cache_dir)
    meta = {
        "source_signature": _compute_source_signature(char_id, base_path),
        "canvas_size": list(CANVAS_SIZE),
        "cache_format": CACHE_FORMAT,
        "portrait_count": len(portraits),
        "background_count": len(backgrounds),
    }
    meta_path = _cache_meta_path(char_id, cache_path)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def _cache_is_complete(
    char_id: str,
    portraits: List[str],
    backgrounds: List[str],
    base_path: str,
    cache_path: str,
) -> bool:
    if not portraits or not backgrounds:
        return False

    cache_dir = os.path.join(cache_path, char_id)
    if not os.path.isdir(cache_dir):
        return False

    expected = _expected_cache_count(portraits, backgrounds)
    existing = len([f for f in os.listdir(cache_dir) if f.lower().endswith(CACHE_EXT)])
    if existing < expected:
        return False

    meta = _load_cache_meta(char_id, cache_path)
    if not meta:
        return False

    if int(meta.get("portrait_count", -1)) != len(portraits):
        return False
    if int(meta.get("background_count", -1)) != len(backgrounds):
        return False
    if tuple(meta.get("canvas_size", [])) != CANVAS_SIZE:
        return False
    if meta.get("cache_format") != CACHE_FORMAT:
        return False
    if meta.get("source_signature") != _compute_source_signature(char_id, base_path):
        return False

    return True


def _prepare_background_images(
    char_id: str,
    base_path: str,
    progress: ProgressCallback | None,
) -> Dict[str, Image.Image]:
    """Load/scale backgrounds and persist them into assets/pre_scaled."""
    entries = _collect_background_entries(char_id, base_path)
    if not entries:
        return {}

    pre_scaled_dir = os.path.join(
        base_path, "pre_scaled", "characters", char_id, "background"
    )
    result: Dict[str, Image.Image] = {}
    _notify_progress(progress, "prepare_bg", 0, len(entries), "正在预处理背景...")

    for idx, (name, src_path) in enumerate(entries, start=1):
        base, ext = os.path.splitext(name)
        scaled_name = f"{base}{SCALED_TAG}{ext}"
        pre_scaled_path = os.path.join(pre_scaled_dir, scaled_name)
        legacy_path = os.path.join(pre_scaled_dir, name)

        if os.path.exists(pre_scaled_path):
            img = Image.open(pre_scaled_path).convert("RGBA")
        else:
            if os.path.exists(legacy_path):
                img = Image.open(legacy_path).convert("RGBA")
            else:
                img = Image.open(src_path).convert("RGBA")

            if img.size != CANVAS_SIZE:
                img = img.resize(CANVAS_SIZE, Image.LANCZOS)

            ensure_dir(pre_scaled_dir)
            img.save(pre_scaled_path, "PNG", optimize=True)

        if img.size != CANVAS_SIZE:
            img = img.resize(CANVAS_SIZE, Image.LANCZOS)

        result[name] = img
        _notify_progress(
            progress,
            "prepare_bg",
            idx,
            len(entries),
            f"背景处理 {name}",
        )

    return result


def prebuild_character(
    char_id: str,
    base_path: str = BASE_PATH,
    cache_path: str = CACHE_PATH,
    force: bool = False,
    progress: ProgressCallback | None = None,
) -> None:
    _refresh_render_preferences()
    print(f"🚧 开始预处理角色: {char_id}")
    _notify_progress(progress, "start", 0, 0, f"开始预处理角色 {char_id}")

    char_root = os.path.join(base_path, "characters", char_id)
    config_path = os.path.join(char_root, "config.json")
    if not os.path.exists(config_path):
        msg = f"❌ 找不到配置 {config_path}"
        print(msg)
        _notify_progress(progress, "error", 0, 0, msg)
        return

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    layout = normalize_layout(config.get("layout", {}), CANVAS_SIZE)
    config["layout"] = layout
    stand_pos = tuple(layout.get("stand_pos", [0, 0]))
    stand_scale = layout.get("stand_scale", 1.0)
    stand_on_top = bool(layout.get("stand_on_top", False))

    portrait_dir = os.path.join(char_root, "portrait")
    portraits = _list_images(portrait_dir)

    bg_images = _prepare_background_images(char_id, base_path, progress)
    backgrounds = list(bg_images.keys())

    if not portraits:
        msg = "⚠️ 没有立绘，跳过预处理"
        print(msg)
        _notify_progress(progress, "error", 0, 0, msg)
        return
    if not backgrounds:
        msg = "⚠️ 没有背景，跳过预处理"
        print(msg)
        _notify_progress(progress, "error", 0, 0, msg)
        return

    if not force and _cache_is_complete(char_id, portraits, backgrounds, base_path, cache_path):
        print("✅ 缓存已存在，跳过预处理")
        _notify_progress(progress, "skip", 0, 0, "缓存已存在，无需重新生成")
        return

    box_name = config.get("assets", {}).get("dialog_box", "textbox_bg.png")
    box_path = os.path.join(char_root, box_name)
    if not os.path.exists(box_path):
        msg = f"❗ 找不到对话框图片 {box_path}"
        print(msg)
        _notify_progress(progress, "error", 0, 0, msg)
        return

    raw_box_img = Image.open(box_path).convert("RGBA")
    box_img = _scale_box_to_canvas(raw_box_img)
    box_pos = _resolve_box_position(layout, box_img)

    char_cache_dir = os.path.join(cache_path, char_id)
    ensure_dir(char_cache_dir)

    total = _expected_cache_count(portraits, backgrounds)
    count = 0
    _notify_progress(progress, "composite", 0, total, "开始生成底图")

    for p_file in portraits:
        portrait_img = Image.open(os.path.join(portrait_dir, p_file)).convert("RGBA")
        if stand_scale != 1.0:
            new_w = int(portrait_img.width * stand_scale)
            new_h = int(portrait_img.height * stand_scale)
            portrait_img = portrait_img.resize((new_w, new_h), Image.LANCZOS)
        p_key = os.path.splitext(p_file)[0]

        for b_name in backgrounds:
            canvas = Image.new("RGBA", CANVAS_SIZE)
            canvas.paste(bg_images[b_name], (0, 0))

            if stand_on_top:
                canvas.paste(box_img, box_pos, box_img)
                canvas.paste(portrait_img, stand_pos, portrait_img)
            else:
                canvas.paste(portrait_img, stand_pos, portrait_img)
                canvas.paste(box_img, box_pos, box_img)

            save_name = f"p_{p_key}__b_{os.path.splitext(b_name)[0]}{CACHE_EXT}"
            save_path = os.path.join(char_cache_dir, save_name)

            if CACHE_FORMAT == "jpeg":
                canvas_rgb = canvas.convert("RGB")
                canvas_rgb.save(
                    save_path,
                    "JPEG",
                    quality=JPEG_QUALITY,
                    optimize=True,
                )
            else:
                canvas.save(save_path, "PNG", optimize=True)

            count += 1
            _notify_progress(
                progress,
                "composite",
                count,
                total,
                f"[{count}/{total}] 已生成 {save_name}",
            )

    _write_cache_meta(char_id, portraits, backgrounds, base_path, cache_path)
    print(f"✅ {char_id} 预处理完成，共生成 {count} 张底图。\n")
    _notify_progress(progress, "done", count, total, f"{char_id} 预处理完成")


def _scale_box_to_canvas(box_img: Image.Image) -> Image.Image:
    canvas_w, _ = CANVAS_SIZE
    if box_img.width != canvas_w:
        scale = canvas_w / box_img.width
        new_h = int(box_img.height * scale)
        box_img = box_img.resize((canvas_w, new_h), Image.LANCZOS)
    return box_img


def _resolve_box_position(layout: Dict[str, object], box_img: Image.Image) -> Tuple[int, int]:
    canvas_w, canvas_h = CANVAS_SIZE
    pos = layout.get("box_pos")
    if (
        isinstance(pos, (list, tuple))
        and len(pos) == 2
    ):
        x = int(pos[0])
        y = int(pos[1])
        x = max(-box_img.width, min(x, canvas_w))
        y = max(-box_img.height, min(y, canvas_h))
        return x, y
    return (0, canvas_h - box_img.height)


def ensure_character_cache(
    char_id: str,
    base_path: str = BASE_PATH,
    cache_path: str = CACHE_PATH,
) -> None:
    _refresh_render_preferences()
    portrait_dir = os.path.join(base_path, "characters", char_id, "portrait")
    portraits = _list_images(portrait_dir)
    backgrounds = [name for name, _ in _collect_background_entries(char_id, base_path)]

    if _cache_is_complete(char_id, portraits, backgrounds, base_path, cache_path):
        return

    prebuild_character(
        char_id,
        base_path=base_path,
        cache_path=cache_path,
        force=True,
    )


if __name__ == "__main__":
    characters_root = os.path.join(BASE_PATH, "characters")
    for folder in os.listdir(characters_root):
        if os.path.isdir(os.path.join(characters_root, folder)):
            prebuild_character(folder)
