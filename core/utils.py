# core/utils.py

import json
import os
from copy import deepcopy
from typing import Any, Dict, List, Tuple, Mapping, Optional, TextIO

import yaml
from yaml.representer import SafeRepresenter

GLOBAL_CONFIG_FILENAME = "global_config.yaml"
LEGACY_GLOBAL_CONFIG_FILENAME = "global_config.json"
GLOBAL_CONFIG_PATH = os.path.join(os.getcwd(), GLOBAL_CONFIG_FILENAME)
LEGACY_GLOBAL_CONFIG_PATH = os.path.join(os.getcwd(), LEGACY_GLOBAL_CONFIG_FILENAME)

DEFAULT_CANVAS_SIZE: Tuple[int, int] = (2560, 1440)

DEFAULT_RENDER_CONFIG: Dict[str, Any] = {
    "cache_format": "jpeg",
    "jpeg_quality": 90,
    "use_memory_canvas_cache": True,
}

DEFAULT_TEXT_WRAPPER: Dict[str, Any] = {
    "type": "none",  # none | preset | custom
    "preset": "corner_single",  # corner_single → 「」, corner_double → 『』
    "prefix": "",
    "suffix": "",
}

DEFAULT_BASIC_STYLE: Dict[str, Any] = {
    "font_size": 40,
    "text_color": [255, 255, 255],
    "name_font_size": 32,
    "name_color": [255, 85, 255],
}

DEFAULT_ADVANCED_STYLE: Dict[str, Any] = {
    "name_layers": {}
}

DEFAULT_CONFIG: Dict[str, Any] = {
    "current_character": "yuraa",
    "trigger_hotkey": "enter",  # 新增：触发生成图片的快捷键
    "global_hotkeys": {
        "copy_to_clipboard": "ctrl+shift+c",
        "show_character": "ctrl+shift+v",
    },
    "render": DEFAULT_RENDER_CONFIG,
}

class _InlineSeqDumper(yaml.SafeDumper):
    pass

def _represent_inline_list(dumper: _InlineSeqDumper, data: List[Any]):
    inline = (
        len(data) <= 4
        and all(isinstance(item, (int, float)) for item in data)
    )
    return SafeRepresenter.represent_sequence(
        dumper,
        "tag:yaml.org,2002:seq",
        data,
        flow_style=inline,
    )

_InlineSeqDumper.add_representer(list, _represent_inline_list)  # type: ignore[arg-type]

def dump_yaml_inline(data: Any, stream: Optional[TextIO] = None) -> str | None:
    """
    Dump YAML with inline lists (e.g. [1, 2, 3]) for better readability.
    Returns the serialized string when stream is None.
    """
    return yaml.dump(
        data,
        stream=stream,
        Dumper=_InlineSeqDumper,
        allow_unicode=True,
        sort_keys=False,
    )



def _read_config_file(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            if path.endswith((".yaml", ".yml")):
                data = yaml.safe_load(f)
            else:
                data = json.load(f)
            return data or {}
    except Exception:
        return {}


def load_global_config() -> Dict[str, Any]:
    """Load global_config.yaml (with JSON fallback) and ensure defaults."""
    source_path = None
    config: Dict[str, Any] = {}
    if os.path.exists(GLOBAL_CONFIG_PATH):
        source_path = GLOBAL_CONFIG_PATH
        config = _read_config_file(GLOBAL_CONFIG_PATH)
    elif os.path.exists(LEGACY_GLOBAL_CONFIG_PATH):
        source_path = LEGACY_GLOBAL_CONFIG_PATH
        config = _read_config_file(LEGACY_GLOBAL_CONFIG_PATH)

    merged = DEFAULT_CONFIG.copy()
    merged.update(config)

    _ensure_dict(merged, "render", DEFAULT_RENDER_CONFIG)
    
    # 确保 trigger_hotkey 存在
    if "trigger_hotkey" not in merged or not merged["trigger_hotkey"]:
        merged["trigger_hotkey"] = DEFAULT_CONFIG["trigger_hotkey"]

    if (source_path != GLOBAL_CONFIG_PATH) or merged != config:
        save_global_config(merged)

    return merged



def save_global_config(config: Dict[str, Any]) -> None:
    """Persist global config to YAML file."""
    with open(GLOBAL_CONFIG_PATH, "w", encoding="utf-8") as f:
        dump_yaml_inline(config, f)


def normalize_layout(
    layout: Optional[Dict[str, Any]],
    canvas_size: Tuple[int, int],
) -> Dict[str, Any]:
    """
    Normalize a layout dict so it always matches the provided canvas size.
    Keeps the refactored style while offering backward compatibility.
    """
    normalized: Dict[str, Any] = {}
    if layout:
        normalized.update(layout)

    src_size = _determine_source_canvas_size(normalized, canvas_size)
    if src_size != canvas_size:
        normalized = _scale_layout(normalized, src_size, canvas_size)

    normalized["_canvas_size"] = [canvas_size[0], canvas_size[1]]
    normalized["text_area"] = _clamp_rect_to_canvas(
        normalized.get("text_area"),
        canvas_size,
    )
    normalized["name_pos"] = _clamp_point_to_canvas(
        normalized.get("name_pos"),
        canvas_size,
    )

    if "stand_pos" in normalized:
        normalized["stand_pos"] = _ensure_point(
            normalized.get("stand_pos"),
            canvas_size,
            allow_negative=True,
        )
    if "box_pos" in normalized:
        normalized["box_pos"] = _ensure_point(
            normalized.get("box_pos"),
            canvas_size,
            allow_negative=True,
        )

    return normalized


def normalize_style(style: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Normalize style dict for per-character config, keeping backward compatibility."""
    src: Dict[str, Any] = dict(style) if isinstance(style, Mapping) else {}

    normalized: Dict[str, Any] = {
        "mode": "basic",
        "text_wrapper": deepcopy(DEFAULT_TEXT_WRAPPER),
        "basic": deepcopy(DEFAULT_BASIC_STYLE),
        "advanced": deepcopy(DEFAULT_ADVANCED_STYLE),
    }

    mode = src.get("mode")
    if isinstance(mode, str) and mode.lower() in {"basic", "advanced"}:
        normalized["mode"] = mode.lower()

    wrapper_candidate = src.get("text_wrapper")
    wrapper_src: Dict[str, Any] = dict(wrapper_candidate) if isinstance(wrapper_candidate, Mapping) else {}
    wrapper = normalized["text_wrapper"]
    w_type = wrapper_src.get("type")
    if isinstance(w_type, str) and w_type in {"none", "preset", "custom"}:
        wrapper["type"] = w_type
    preset = wrapper_src.get("preset")
    if isinstance(preset, str):
        wrapper["preset"] = preset
    prefix = wrapper_src.get("prefix")
    if isinstance(prefix, str):
        wrapper["prefix"] = prefix
    suffix = wrapper_src.get("suffix")
    if isinstance(suffix, str):
        wrapper["suffix"] = suffix
    if wrapper["type"] == "preset":
        wrapper["prefix"], wrapper["suffix"] = _wrapper_tokens_from_preset(wrapper["preset"])
    elif wrapper["type"] == "none":
        wrapper["prefix"] = ""
        wrapper["suffix"] = ""

    basic_candidate = src.get("basic")
    basic_src: Dict[str, Any] = dict(basic_candidate) if isinstance(basic_candidate, Mapping) else {}
    normalized["basic"]["font_size"] = _coerce_int(
        basic_src.get("font_size", src.get("font_size")),
        DEFAULT_BASIC_STYLE["font_size"],
    )
    normalized["basic"]["name_font_size"] = _coerce_int(
        basic_src.get("name_font_size", src.get("name_font_size")),
        DEFAULT_BASIC_STYLE["name_font_size"],
    )
    normalized["basic"]["text_color"] = _coerce_color(
        basic_src.get("text_color", src.get("text_color")),
        DEFAULT_BASIC_STYLE["text_color"],
    )
    normalized["basic"]["name_color"] = _coerce_color(
        basic_src.get("name_color", src.get("name_color")),
        DEFAULT_BASIC_STYLE["name_color"],
    )

    advanced_candidate = src.get("advanced")
    advanced_src: Dict[str, Any] = dict(advanced_candidate) if isinstance(advanced_candidate, Mapping) else {}
    layers = advanced_src.get("name_layers")
    if isinstance(layers, dict):
        normalized["advanced"]["name_layers"] = deepcopy(layers)
    else:
        normalized["advanced"]["name_layers"] = {}

    for extra_key, extra_value in src.items():
        if extra_key not in {"mode", "text_wrapper", "basic", "advanced"}:
            normalized[extra_key] = extra_value

    return normalized


def _ensure_dict(config: Dict[str, Any], key: str, fallback: Dict[str, Any]) -> None:
    if key not in config or not isinstance(config[key], dict):
        config[key] = dict(fallback)
    else:
        merged = dict(fallback)
        merged.update(config[key])
        config[key] = merged


def _coerce_int(value: Any, fallback: int) -> int:
    if isinstance(value, (int, float)):
        result = int(value)
        return result if result > 0 else fallback
    return fallback


def _coerce_color(value: Any, fallback: List[int]) -> List[int]:
    if (
        isinstance(value, (list, tuple))
        and len(value) == 3
        and all(isinstance(v, (int, float)) for v in value)
    ):
        return [max(0, min(255, int(v))) for v in value]  # clamp to RGB range
    return list(fallback)


def _wrapper_tokens_from_preset(preset: str) -> Tuple[str, str]:
    if preset == "corner_double":
        return "『", "』"
    return "「", "」"


def _determine_source_canvas_size(
    layout: Dict[str, Any],
    canvas_size: Tuple[int, int],
) -> Tuple[int, int]:
    stored = layout.get("_canvas_size")
    parsed = _parse_canvas_size(stored)
    if parsed:
        return parsed

    max_x, max_y = _estimate_layout_extent(layout)
    canvas_w, canvas_h = canvas_size
    if max_x > canvas_w or max_y > canvas_h:
        return DEFAULT_CANVAS_SIZE
    return canvas_size


def _parse_canvas_size(value: Any) -> Optional[Tuple[int, int]]:
    if (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and int(value[0]) > 0
        and int(value[1]) > 0
    ):
        return int(value[0]), int(value[1])
    return None


def _estimate_layout_extent(layout: Dict[str, Any]) -> Tuple[int, int]:
    max_x = 0
    max_y = 0

    def update_point(point: Any) -> None:
        nonlocal max_x, max_y
        if (
            point
            and isinstance(point, (list, tuple))
            and len(point) == 2
        ):
            max_x = max(max_x, int(point[0]))
            max_y = max(max_y, int(point[1]))

    def update_rect(rect: Any) -> None:
        nonlocal max_x, max_y
        if (
            rect
            and isinstance(rect, (list, tuple))
            and len(rect) == 4
        ):
            max_x = max(max_x, int(rect[2]))
            max_y = max(max_y, int(rect[3]))

    update_rect(layout.get("text_area"))
    update_point(layout.get("name_pos"))
    update_point(layout.get("stand_pos"))
    update_point(layout.get("box_pos"))

    return max_x, max_y


def _scale_layout(
    layout: Dict[str, Any],
    source_size: Tuple[int, int],
    target_size: Tuple[int, int],
) -> Dict[str, Any]:
    src_w, src_h = source_size
    tgt_w, tgt_h = target_size
    if src_w <= 0 or src_h <= 0:
        return layout

    scale_x = tgt_w / src_w
    scale_y = tgt_h / src_h

    def scale_point(point: Any) -> List[int]:
        if (
            not point
            or not isinstance(point, (list, tuple))
            or len(point) != 2
        ):
            return [0, 0]
        return [
            int(round(point[0] * scale_x)),
            int(round(point[1] * scale_y)),
        ]

    def scale_rect(rect: Any) -> List[int]:
        if (
            not rect
            or not isinstance(rect, (list, tuple))
            or len(rect) != 4
        ):
            return [0, 0, tgt_w, tgt_h]
        return [
            int(round(rect[0] * scale_x)),
            int(round(rect[1] * scale_y)),
            int(round(rect[2] * scale_x)),
            int(round(rect[3] * scale_y)),
        ]

    if "stand_pos" in layout:
        layout["stand_pos"] = scale_point(layout.get("stand_pos"))
    if "box_pos" in layout:
        layout["box_pos"] = scale_point(layout.get("box_pos"))
    if "name_pos" in layout:
        layout["name_pos"] = scale_point(layout.get("name_pos"))
    if "text_area" in layout:
        layout["text_area"] = scale_rect(layout.get("text_area"))

    return layout


def _clamp_rect_to_canvas(rect: Any, canvas_size: Tuple[int, int]) -> List[int]:
    canvas_w, canvas_h = canvas_size
    if (
        not rect
        or not isinstance(rect, (list, tuple))
        or len(rect) != 4
    ):
        top = int(canvas_h * 0.6)
        return [0, top, canvas_w, canvas_h - 40]

    x1, y1, x2, y2 = [int(v) for v in rect]
    x1 = max(0, min(x1, canvas_w))
    y1 = max(0, min(y1, canvas_h))
    x2 = max(x1 + 10, min(x2, canvas_w))
    y2 = max(y1 + 10, min(y2, canvas_h))
    return [x1, y1, x2, y2]


def _clamp_point_to_canvas(point: Any, canvas_size: Tuple[int, int]) -> List[int]:
    canvas_w, canvas_h = canvas_size
    if (
        not point
        or not isinstance(point, (list, tuple))
        or len(point) != 2
    ):
        return [0, 0]
    x = min(max(0, int(point[0])), canvas_w)
    y = min(max(0, int(point[1])), canvas_h)
    return [x, y]


def _ensure_point(
    point: Any,
    canvas_size: Tuple[int, int],
    allow_negative: bool = False,
) -> List[int]:
    if (
        not point
        or not isinstance(point, (list, tuple))
        or len(point) != 2
    ):
        return [0, 0]

    x = int(point[0])
    y = int(point[1])
    if not allow_negative:
        x = max(0, min(x, canvas_size[0]))
        y = max(0, min(y, canvas_size[1]))
    return [x, y]
