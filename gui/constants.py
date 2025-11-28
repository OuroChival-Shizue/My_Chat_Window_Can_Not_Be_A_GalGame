# gui/constants.py
"""
全局常量和画布配置管理
"""
from typing import Tuple, List

# --- 尝试导入后端模块 ---
try:
    from core.utils import load_global_config, save_global_config, normalize_layout
    from core.renderer import CharacterRenderer
    from core.prebuild import prebuild_character
except ImportError:
    print("Warning: Core modules not found. Some features may not work.")
    def load_global_config(): return {}
    def save_global_config(cfg): pass
    def normalize_layout(layout, canvas): return layout or {}
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
    def load_from_global_config(cls) -> Tuple[int, int]:
        """从 global_config.json 加载画布尺寸"""
        try:
            cfg = load_global_config()
            render_cfg = cfg.get("render", {})
            size = render_cfg.get("canvas_size")
            if (
                isinstance(size, (list, tuple))
                and len(size) == 2
                and int(size[0]) > 0
                and int(size[1]) > 0
            ):
                cls._width, cls._height = int(size[0]), int(size[1])
        except Exception as exc:
            print(f"⚠️ 读取画布配置失败，采用默认值: {exc}")
        return cls._width, cls._height

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


# 初始化时加载配置
CanvasConfig.load_from_global_config()
