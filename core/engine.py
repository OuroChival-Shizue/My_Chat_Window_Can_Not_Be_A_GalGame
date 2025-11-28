import time

import keyboard

from .clipboard import get_text, set_image, set_text
from .listener import InputListener
from .prebuild import ensure_character_cache
from .renderer import CharacterRenderer


class GalGameEngine:
    def __init__(self, char_id: str = "yuraa"):
        self.char_id = char_id
        
        try:
            ensure_character_cache(char_id)
            self.renderer = CharacterRenderer(char_id)
        except Exception as e:
            print(f"❌ 引擎启动失败: 渲染器初始化错误 - {e}")
            raise

        # 初始化默认表情
        portrait_keys = sorted(list(self.renderer.assets["portraits"].keys()))
        if portrait_keys:
            self.current_expression = portrait_keys[0]
            print(f"ℹ️ 默认加载立绘: {self.current_expression}")
        else:
            self.current_expression = "default"
            print("⚠️ 警告: 未找到任何立绘，使用默认占位符")

        self.listener = InputListener()

    def start(self):
        self.run()

    def run(self):
        print(f"\n🚀 GalGame 对话框引擎已启动 [角色: {self.char_id}]")
        self.listener.start(
            submit_callback=self._on_submit,
            switch_callback=self._on_switch_expression,
        )

    def _on_switch_expression(self, key: str):
        """回调：切换表情 (按数字索引)"""
        try:
            index = int(key) - 1
        except ValueError:
            print(f"⚠️ 无效的快捷键参数: {key}")
            return

        portrait_keys = sorted(list(self.renderer.assets["portraits"].keys()))
        
        if 0 <= index < len(portrait_keys):
            target_key = portrait_keys[index]
            self.current_expression = target_key
            print(f"😉 已切换到第 [{key}] 号立绘: {target_key}")
        else:
            print(f"🤔 序号 {key} 超出范围 (当前只有 {len(portrait_keys)} 张立绘)")

    def _on_submit(self):
        # 1. 模拟 Ctrl+A 全选, Ctrl+X 剪切
        keyboard.send("ctrl+a")
        time.sleep(0.05)
        keyboard.send("ctrl+x")
        time.sleep(0.1)

        # 2. 获取剪贴板文本
        text = get_text().strip()

        if not text:
            print("🔕 剪贴板为空或非文本，尝试还原...")
            keyboard.send("ctrl+v")
            return

        print(f"📝 捕获文本: {text}")

        # 3. 渲染图片
        try:
            image = self.renderer.render(text, self.current_expression)
        except Exception as e:
            print(f"❌ 渲染失败: {e}")
            if set_text(text):
                keyboard.send("ctrl+v")
            return

        # 4. 将图片写入剪贴板并粘贴
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
