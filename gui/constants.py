# gui/constants.py
"""
全局常量和画布配置管理
"""
from typing import Any, Dict, Tuple, List

import yaml

# --- 尝试导入后端模块 ---
try:
    from core.utils import load_global_config, save_global_config, normalize_layout, normalize_style, dump_yaml_inline  # pyright: ignore[reportAssignmentType]
    from core.renderer import CharacterRenderer
    from core.prebuild import prebuild_character
except ImportError:
    print("Warning: Core modules not found. Some features may not work.")
    def load_global_config() -> Dict[str, Any]: return {}
    def save_global_config(cfg: Dict[str, Any]) -> None: pass
    def normalize_layout(layout, canvas): return layout or {}
    def normalize_style(style): return style or {}
    def dump_yaml_inline(data: Any, stream=None):
        return yaml.safe_dump(data, stream=stream, allow_unicode=True, sort_keys=False)
    CharacterRenderer = None
    prebuild_character = None

# --- 路径常量 ---
BASE_PATH = "assets"

# --- 画布配置 ---
DEFAULT_CANVAS_SIZE = (2560, 1440)
COMMON_RESOLUTIONS: List[Tuple[int, int]] = [
    (1280, 720),
    (1600, 900),
    (1920, 1080),
    (2560, 1440),
    (3440, 1440),
    (3840, 2160),
]

# --- Z-Index 层级 ---
Z_BG = 0
Z_PORTRAIT_BOTTOM = 10
Z_BOX = 20
Z_PORTRAIT_TOP = 25
Z_TEXT = 30


class CanvasConfig:
    """
    画布尺寸管理器 (单例模式替代全局变量)
    解决全局变量 CANVAS_W/CANVAS_H 难以跨模块同步的问题
    """
    _width: int = DEFAULT_CANVAS_SIZE[0]
    _height: int = DEFAULT_CANVAS_SIZE[1]

    @classmethod
    def get_size(cls) -> Tuple[int, int]:
        return cls._width, cls._height

    @classmethod
    def set_size(cls, width: int, height: int):
        cls._width = width
        cls._height = height

    @classmethod
    def width(cls) -> int:
        return cls._width

    @classmethod
    def height(cls) -> int:
        return cls._height


