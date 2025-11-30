import keyboard
import win32gui
import threading
from typing import Any, Callable, Optional, List

from .utils import load_global_config


class InputListener:
    def __init__(self):
        self.running = False
        self.enter_hotkey = None
        self.paused = False
        config = load_global_config()
        target_apps = config.get("target_apps", [])
        self.target_apps: List[str] = target_apps if isinstance(target_apps, list) else []
        self.on_submit: Optional[Callable[[], None]] = None
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

    def start(self, submit_callback: Callable[[], Any], switch_callback: Callable[[str], None]):
        """启动监听"""
        self.on_submit = submit_callback
        self.on_switch_expression = switch_callback
        self.running = True

        print("🎧 键盘监听已启动..")
        print(f"   支持软件: {self.target_apps}")
        print("   快捷键: Enter(发送), Alt+1~9(切表情), Ctrl+F12(暂停), Esc(退出)")

        # 使用 args 显式传递参数
        for i in range(1, 10):
            keyboard.add_hotkey(f"alt+{i}", self._safe_switch, args=(str(i),))

        keyboard.add_hotkey("ctrl+f12", self.toggle_pause)

        self.enter_hotkey = keyboard.add_hotkey("enter", self._trigger_submit, suppress=True)

        keyboard.wait("esc")

    def _safe_switch(self, key_idx: str):
        """安全的中转函数"""
        if self.on_switch_expression:
            try:
                self.on_switch_expression(key_idx)
            except Exception as e:
                print(f"❌ 切换表情回调出错: {e}")

    def toggle_pause(self):
        """切换暂停/恢复拦截"""
        self.paused = not self.paused
        status = "已暂停" if self.paused else "已恢复"
        print(f"⏯️ {status}")

    def _trigger_submit(self):
        """Enter 被按下时触发"""
        if self.paused:
            # 暂停状态下，直接透传 Enter
            if self.enter_hotkey:
                keyboard.remove_hotkey(self.enter_hotkey)
            try:
                keyboard.send("enter")
            finally:
                self.enter_hotkey = keyboard.add_hotkey(
                    "enter", self._trigger_submit, suppress=True
                )
            return

        if self.is_target_window_active():
            # 在目标软件内，拦截 Enter 并执行逻辑
            if self.on_submit:
                # 启动子线程执行耗时操作，防止阻塞键盘钩子
                threading.Thread(target=self._run_submit_async).start()
        else:
            # 非目标软件，透传 Enter
            if self.enter_hotkey:
                keyboard.remove_hotkey(self.enter_hotkey)
            try:
                keyboard.send("enter")
            finally:
                self.enter_hotkey = keyboard.add_hotkey(
                    "enter", self._trigger_submit, suppress=True
                )

    def _run_submit_async(self):
        """在子线程中执行发送逻辑"""
        try:
            if self.enter_hotkey:
                keyboard.remove_hotkey(self.enter_hotkey)
        except Exception:
            pass # 可能已经被移除了

        try:
            if(callable(self.on_submit)):
                self.on_submit()
        except Exception as e:
            print(f"❌ 发送回调出错: {e}")
        finally:
            # 恢复监听
            # 稍微延时一点点，确保模拟按键完全释放
            try:
                self.enter_hotkey = keyboard.add_hotkey(
                    "enter", self._trigger_submit, suppress=True
                )
            except Exception:
                pass # 防止重复添加

    def stop(self):
        self.running = False
        keyboard.unhook_all()
        print("🛑 监听已停止")
