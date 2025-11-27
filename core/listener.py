import keyboard
import win32gui
from typing import Callable, Optional, List

from .utils import load_global_config


class InputListener:
    def __init__(self):
        self.running = False
        self.enter_hotkey = None
        self.paused = False
        config = load_global_config()
        target_apps = config.get("target_apps", [])
        self.target_apps: List[str] = target_apps if isinstance(target_apps, list) else []
        self.on_submit: Optional[Callable] = None
        self.on_switch_expression: Optional[Callable[[str], None]] = None

    def is_target_window_active(self) -> bool:
        """检查当前活动窗口是否在白名单内"""
        try:
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            for app in self.target_apps:
                if app in title:
                    return True
        except Exception:
            pass
        return False

    def start(self, submit_callback: Callable, switch_callback: Callable[[str], None]):
        """启动监听"""
        self.on_submit = submit_callback
        self.on_switch_expression = switch_callback
        self.running = True

        print("🎧 键盘监听已启动..")
        print(f"   支持软件: {self.target_apps}")
        print("   快捷键: Enter(发送), Alt+1~9(切表情), Ctrl+F12(暂停), Esc(退出)")

        for i in range(1, 10):
            keyboard.add_hotkey(f"alt+{i}", lambda x=str(i): self.on_switch_expression(x))
        keyboard.add_hotkey("ctrl+f12", self.toggle_pause)

        self.enter_hotkey = keyboard.add_hotkey("enter", self._trigger_submit, suppress=True)

        keyboard.wait("esc")

    def toggle_pause(self):
        """切换暂停/恢复拦截"""
        self.paused = not self.paused
        status = "已暂停" if self.paused else "已恢复"
        print(f"⏯️ {status}")

    def _trigger_submit(self):
        """Enter 被按下时触发"""
        if self.paused:
            keyboard.remove_hotkey(self.enter_hotkey)
            try:
                keyboard.send("enter")
            finally:
                self.enter_hotkey = keyboard.add_hotkey(
                    "enter", self._trigger_submit, suppress=True
                )
            return

        if self.is_target_window_active():
            if self.on_submit:
                keyboard.remove_hotkey(self.enter_hotkey)
                try:
                    self.on_submit()
                finally:
                    self.enter_hotkey = keyboard.add_hotkey(
                        "enter", self._trigger_submit, suppress=True
                    )
        else:
            keyboard.remove_hotkey(self.enter_hotkey)
            try:
                keyboard.send("enter")
            finally:
                self.enter_hotkey = keyboard.add_hotkey(
                    "enter", self._trigger_submit, suppress=True
                )

    def stop(self):
        self.running = False
        keyboard.unhook_all()
        print("🛑 监听已停止")


if __name__ == "__main__":
    def test_submit():
        print(">>> 触发生成图片逻辑")

    def test_switch(key):
        print(f">>> 切换表情: {key}")

    listener = InputListener()
    listener.target_apps.append("Visual Studio Code")
    listener.start(test_submit, test_switch)
