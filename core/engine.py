import time

import keyboard

from .clipboard import get_text, set_image, set_text
from .listener import InputListener
from .prebuild import ensure_character_cache
from .renderer import CharacterRenderer


class GalGameEngine:
    def __init__(self, char_id: str = "yuraa"):
        self.char_id = char_id
        self.current_expression: str = "1"

        try:
            ensure_character_cache(char_id)
            self.renderer = CharacterRenderer(char_id)
        except Exception as e:
            print(f"❌ 引擎启动失败: 渲染器初始化错误 - {e}")
            raise

        self.listener = InputListener()

    def start(self):
        """对外暴露的启动方法，兼容 main.py 调用"""
        self.run()

    def run(self):
        """启动引擎主循环"""
        print(f"\n🚀 GalGame 对话框引擎已启动 [角色: {self.char_id}]")
        self.listener.start(
            submit_callback=self._on_submit,
            switch_callback=self._on_switch_expression,
        )

    def _on_switch_expression(self, key: str):
        """回调：切换表情"""
        if key in self.renderer.assets["portraits"]:
            self.current_expression = key
            print(f"😉 表情已切换 -> {key}")
        else:
            print(f"🤔 表情 {key} 不存在，保持不变")

    def _on_submit(self):
        """回调：处理 Enter 发送逻辑"""
        keyboard.send("ctrl+a")
        time.sleep(0.05)
        keyboard.send("ctrl+x")
        time.sleep(0.1)

        text = get_text().strip()

        if not text:
            print("🔕 剪贴板为空或非文本，尝试还原...")
            keyboard.send("ctrl+v")
            return

        print(f"📝 捕获文本: {text}")

        try:
            image = self.renderer.render(text, self.current_expression)
        except Exception as e:
            print(f"❌ 渲染失败: {e}")
            if set_text(text):
                keyboard.send("ctrl+v")
            return

        if set_image(image):
            time.sleep(0.1)
            keyboard.send("ctrl+v")
            time.sleep(1)
            keyboard.press_and_release("enter")
            print("✅ 已执行粘贴发送指令")
        else:
            print("❌ 图片写入剪贴板失败")
            if set_text(text):
                keyboard.send("ctrl+v")
