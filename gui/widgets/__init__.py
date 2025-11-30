# gui/widgets/__init__.py
from .color_button import ColorButton
from .asset_list import AssetListWidget
from .dialogs import NewCharacterDialog, PrebuildProgressDialog
from .hotkey_dialog import SettingsDialog, HotkeyEdit  # ✅ 添加这行

__all__ = [
    "ColorButton",
    "AssetListWidget", 
    "NewCharacterDialog",
    "PrebuildProgressDialog",
    "SettingsDialog",  # ✅ 添加
    "HotkeyEdit",      # ✅ 可选，如果其他地方需要用
]
