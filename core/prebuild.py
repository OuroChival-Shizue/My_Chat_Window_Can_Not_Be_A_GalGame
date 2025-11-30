import hashlib
import json
import os
from typing import Callable, Dict, List, Tuple, Any, Optional

import yaml
from PIL import Image

try:
    from .utils import load_global_config, normalize_layout
except Exception:  # pragma: no cover - fallback for standalone runs
    def load_global_config() -> Dict[str, object]:
        return {}

    def normalize_layout(layout, canvas_size):
        return layout or {}

DEFAULT_CANVAS_SIZE: Tuple[int, int] = (2560, 1440)

def _load_render_preferences() -> Tuple[str, str, int]:
    cfg: dict = load_global_config() or {}
    render = cfg.get("render", {})
    cache_format = str(render.get("cache_format", "jpeg")).lower()
    if cache_format not in {"jpeg", "png"}:
        cache_format = "jpeg"
    cache_ext = ".jpg" if cache_format == "jpeg" else ".png"
    jpeg_quality = int(render.get("jpeg_quality", 90))
    return cache_format, cache_ext, jpeg_quality

CANVAS_SIZE: Tuple[int, int] = DEFAULT_CANVAS_SIZE
CACHE_FORMAT: str = "jpeg"
CACHE_EXT: str = ".jpg"
JPEG_QUALITY: int = 90
SCALED_TAG: str = "@2560x1440"


def _refresh_render_preferences() -> None:
    global CACHE_FORMAT, CACHE_EXT, JPEG_QUALITY
    CACHE_FORMAT, CACHE_EXT, JPEG_QUALITY = _load_render_preferences()


_refresh_render_preferences()

BASE_PATH = "assets"
CACHE_PATH = os.path.join(BASE_PATH, "cache")
SCALED_TAG = f"@{CANVAS_SIZE[0]}x{CANVAS_SIZE[1]}"

ProgressCallback = Callable[[str, int, int, str], None]


def _apply_canvas_size(canvas: Tuple[int, int]) -> None:
    global CANVAS_SIZE, SCALED_TAG
    CANVAS_SIZE = canvas
    SCALED_TAG = f"@{CANVAS_SIZE[0]}x{CANVAS_SIZE[1]}"


def ensure_dir(path: str) -> None:
    if not os.path.exists(path):
        os.makedirs(path)


def _notify_progress(
    callback: Optional[ProgressCallback],
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

def _character_config_path(char_root: str) -> Optional[str]:
    yaml_path = os.path.join(char_root, "config.yaml")
    legacy_path = os.path.join(char_root, "config.json")
    if os.path.exists(yaml_path):
        return yaml_path
    if os.path.exists(legacy_path):
        return legacy_path
    return None


def _load_character_config(char_id: str, base_path: str) -> Dict[str, Any]:
    char_root = os.path.join(base_path, "characters", char_id)
    config_path = _character_config_path(char_root)
    if not config_path:
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            if config_path.endswith((".yaml", ".yml")):
                data = yaml.safe_load(f)
            else:
                data = json.load(f)
            return data or {}
    except Exception:
        return {}

def _extract_canvas_size(value: Any) -> Optional[Tuple[int, int]]:
    if (
        isinstance(value, (list, tuple))
        and len(value) == 2
    ):
        try:
            w = int(value[0])
            h = int(value[1])
        except Exception:
            return None
        if w > 0 and h > 0:
            return w, h
    return None

def _resolve_canvas_size(layout: Dict[str, Any]) -> Tuple[int, int]:
    size = _extract_canvas_size(layout.get("_canvas_size"))
    if size:
        return size
    return DEFAULT_CANVAS_SIZE

def _configure_canvas_for_character(
    char_id: str,
    base_path: str,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    data = config if config is not None else _load_character_config(char_id, base_path)
    layout = data.get("layout", {}) if isinstance(data, dict) else {}
    canvas = _resolve_canvas_size(layout if isinstance(layout, dict) else {})
    _apply_canvas_size(canvas)
    return data if isinstance(data, dict) else {}


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
    config_path = _character_config_path(char_root)
    if config_path:
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
    if int(meta.get("portrait_count", -1)) != len(portraits): # type: ignore
        return False
    if int(meta.get("background_count", -1)) != len(backgrounds): # type: ignore
        return False
    if tuple(meta.get("canvas_size", [])) != CANVAS_SIZE: # type: ignore
        return False
    if meta.get("cache_format") != CACHE_FORMAT:
        return False
    if meta.get("source_signature") != _compute_source_signature(char_id, base_path):
        return False

    return True

def _fit_dialog_box_to_canvas(box_img: Image.Image) -> Tuple[Image.Image, Tuple[int, int]]:
    """Resize dialog box to canvas width and bottom align."""
    canvas_w, canvas_h = CANVAS_SIZE
    if box_img.width != canvas_w:
        scale = canvas_w / box_img.width
        new_h = int(box_img.height * scale)
        box_img = box_img.resize((canvas_w, new_h), Image.Resampling.LANCZOS)
    box_pos = (0, canvas_h - box_img.height)
    return box_img, box_pos

def _prepare_background_images(
    char_id: str,
    base_path: str,
    progress: Optional[ProgressCallback],
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
                img = img.resize(CANVAS_SIZE, Image.Resampling.LANCZOS)

            ensure_dir(pre_scaled_dir)
            img.save(pre_scaled_path, "PNG", optimize=True)

        if img.size != CANVAS_SIZE:
            img = img.resize(CANVAS_SIZE, Image.Resampling.LANCZOS)

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
    progress: Optional[ProgressCallback] = None,
) -> None:
    _refresh_render_preferences()
    print(f"🚧 开始预处理角色: {char_id}")
    _notify_progress(progress, "start", 0, 0, f"开始预处理角色 {char_id}")

    char_root = os.path.join(base_path, "characters", char_id)
    config_path = _character_config_path(char_root)
    if not config_path:
        expected = os.path.join(char_root, "config.yaml")
        msg = f"❌ 找不到配置 {expected}"
        print(msg)
        _notify_progress(progress, "error", 0, 0, msg)
        return

    config = _configure_canvas_for_character(char_id, base_path)
    if not config:
        msg = f"❌ 无法读取配置 {config_path}"
        print(msg)
        _notify_progress(progress, "error", 0, 0, msg)
        return

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
            portrait_img = portrait_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

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
        box_img = box_img.resize((canvas_w, new_h), Image.Resampling.LANCZOS)
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
    _configure_canvas_for_character(char_id, base_path)
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
