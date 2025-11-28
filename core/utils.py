import json
import os
from typing import Any, Dict, List

GLOBAL_CONFIG_PATH = os.path.join(os.getcwd(), "global_config.json")

DEFAULT_CONFIG: Dict[str, Any] = {
    "current_character": "yuraa",
    "global_hotkeys": {
        "copy_to_clipboard": "ctrl+shift+c",
        "show_character": "ctrl+shift+v",
    },
    "target_apps": [
        "QQ",
        "微信",
        "WeChat",
        "Discord",
        "Telegram",
        "钉钉",
        "DingTalk",
        "Tim",
    ],
}


def load_global_config() -> Dict[str, Any]:
    """Load global_config.json; create with defaults when missing or invalid."""
    config: Dict[str, Any] = {}
    if os.path.exists(GLOBAL_CONFIG_PATH):
        try:
            with open(GLOBAL_CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            config = {}

    # ensure defaults exist
    merged = DEFAULT_CONFIG.copy()
    merged.update(config)
    if "target_apps" not in merged or not isinstance(merged["target_apps"], list):
        merged["target_apps"] = DEFAULT_CONFIG["target_apps"]

    # persist if file missing or invalid
    if not os.path.exists(GLOBAL_CONFIG_PATH) or merged != config:
        save_global_config(merged)

    return merged


def save_global_config(config: Dict[str, Any]) -> None:
    """Persist global config to json file."""
    with open(GLOBAL_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)
