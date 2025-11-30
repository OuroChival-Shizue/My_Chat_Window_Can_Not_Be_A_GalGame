# core/listener.py

import keyboard
import win32gui
import threading
from typing import Any, Callable, Optional, List

from .utils import load_global_config


class InputListener:
    def __init__(self):
        self.running = False
        self.trigger_hotkey_handle = None
        self.paused = False
        
        config = load_global_config()
        target_apps = config.get("target_apps", [])
        self.target_apps: List[str] = target_apps if isinstance(target_apps, list) else []
        
        # 读取触发快捷键配置
        self.trigger_hotkey: str = config.get("trigger_hotkey", "enter").lower().strip()
        
        # 判断是否为单键（需要拦截）还是组合键（不需要拦截）
        self._is_single_key = "+" not in self.trigger_hotkey
        
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
        print(f"   触发快捷键: {self.trigger_hotkey}")
        print("   Alt+1~9(切表情), Ctrl+F5(重载配置), Ctrl+F12(暂停), Esc(退出)")

        # 表情切换快捷键
        for i in range(1, 10):
            keyboard.add_hotkey(f"alt+{i}", self._safe_switch, args=(str(i),))

        # 暂停/恢复快捷键
        keyboard.add_hotkey("ctrl+f12", self.toggle_pause)
        
        # 热重载快捷键
        keyboard.add_hotkey("ctrl+f5", self.reload_config)

        # 注册触发快捷键
        self._register_trigger_hotkey()

        keyboard.wait("esc")

    def _register_trigger_hotkey(self):
        """注册触发快捷键"""
        # 单键（如 enter）需要 suppress 来拦截，组合键不需要
        suppress = self._is_single_key
        self.trigger_hotkey_handle = keyboard.add_hotkey(
            self.trigger_hotkey, 
            self._trigger_submit, 
            suppress=suppress
        )

    def _unregister_trigger_hotkey(self):
        """取消注册触发快捷键"""
        if self.trigger_hotkey_handle:
            try:
                keyboard.remove_hotkey(self.trigger_hotkey_handle)
            except Exception:
                pass
            self.trigger_hotkey_handle = None

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

    def reload_config(self):
        """热重载配置"""
        try:
            config = load_global_config()
            new_hotkey = config.get("trigger_hotkey", "enter").lower().strip()
            new_target_apps = config.get("target_apps", [])
            
            # 更新目标应用列表
            self.target_apps = new_target_apps if isinstance(new_target_apps, list) else []
            
            # 如果快捷键有变化，重新注册
            if new_hotkey != self.trigger_hotkey:
                old_hotkey = self.trigger_hotkey
                self._unregister_trigger_hotkey()
                self.trigger_hotkey = new_hotkey
                self._is_single_key = "+" not in self.trigger_hotkey
                self._register_trigger_hotkey()
                print(f"🔄 触发快捷键已更新: {old_hotkey} → {new_hotkey}")
            else:
                print(f"🔄 配置已重载 (快捷键未变: {self.trigger_hotkey})")
                
        except Exception as e:
            print(f"❌ 重载配置失败: {e}")

    def _trigger_submit(self):
        """触发快捷键被按下时触发"""
        if self.paused:
            # 暂停状态下，如果是单键则透传
            if self._is_single_key:
                self._passthrough_key()
            return

        if self.is_target_window_active():
            # 在目标软件内，执行发送逻辑
            if self.on_submit:
                threading.Thread(target=self._run_submit_async).start()
        else:
            # 非目标软件，如果是单键则透传
            if self._is_single_key:
                self._passthrough_key()

    def _passthrough_key(self):
        """透传单键"""
        self._unregister_trigger_hotkey()
        try:
            keyboard.send(self.trigger_hotkey)
        finally:
            self._register_trigger_hotkey()

    def _run_submit_async(self):
        """在子线程中执行发送逻辑"""
        # 如果是单键，先取消监听避免冲突
        if self._is_single_key:
            self._unregister_trigger_hotkey()

        try:
            if callable(self.on_submit):
                self.on_submit()
        except Exception as e:
            print(f"❌ 发送回调出错: {e}")
        finally:
            # 恢复监听
            if self._is_single_key:
                try:
                    self._register_trigger_hotkey()
                except Exception:
                    pass

    def stop(self):
        self.running = False
        keyboard.unhook_all()
        print("🛑 监听已停止")
