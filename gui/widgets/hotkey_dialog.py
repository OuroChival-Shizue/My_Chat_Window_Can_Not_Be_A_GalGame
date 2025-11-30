# gui/widgets/hotkey_dialog.py

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QMessageBox, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal

from ..constants import load_global_config, save_global_config


class HotkeyEdit(QLineEdit):
    """自定义快捷键输入框，支持录制按键"""
    
    hotkeyChanged = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlaceholderText("点击此处后按下快捷键...")
        self._recording = False
    
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self._recording = True
        self.setText("请按下快捷键...")
        self.setStyleSheet("background-color: #ffffcc;")
    
    def keyPressEvent(self, event):
        if not self._recording:
            return
        
        key = event.key()
        modifiers = event.modifiers()
        
        # 收集修饰键
        mod_parts = []
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            mod_parts.append("ctrl")
        if modifiers & Qt.KeyboardModifier.AltModifier:
            mod_parts.append("alt")
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            mod_parts.append("shift")
        
        # 获取主键
        key_name = self._get_key_name(key)
        
        if key_name:
            # 组合最终快捷键字符串
            if mod_parts:
                hotkey = "+".join(mod_parts) + "+" + key_name
            else:
                hotkey = key_name
            
            self.setText(hotkey)
            self._recording = False
            self.setStyleSheet("")
            self.hotkeyChanged.emit(hotkey)
    
    def _get_key_name(self, key: int) -> str:
        """将 Qt 键码转换为 keyboard 库兼容的名称"""
        key_map = {
            Qt.Key.Key_Return: "enter",
            Qt.Key.Key_Enter: "enter",
            Qt.Key.Key_Space: "space",
            Qt.Key.Key_Tab: "tab",
            Qt.Key.Key_Backspace: "backspace",
            Qt.Key.Key_Delete: "delete",
            Qt.Key.Key_Insert: "insert",
            Qt.Key.Key_Home: "home",
            Qt.Key.Key_End: "end",
            Qt.Key.Key_PageUp: "page up",
            Qt.Key.Key_PageDown: "page down",
            Qt.Key.Key_Up: "up",
            Qt.Key.Key_Down: "down",
            Qt.Key.Key_Left: "left",
            Qt.Key.Key_Right: "right",
            Qt.Key.Key_Escape: "esc",
            Qt.Key.Key_F1: "f1",
            Qt.Key.Key_F2: "f2",
            Qt.Key.Key_F3: "f3",
            Qt.Key.Key_F4: "f4",
            Qt.Key.Key_F5: "f5",
            Qt.Key.Key_F6: "f6",
            Qt.Key.Key_F7: "f7",
            Qt.Key.Key_F8: "f8",
            Qt.Key.Key_F9: "f9",
            Qt.Key.Key_F10: "f10",
            Qt.Key.Key_F11: "f11",
            Qt.Key.Key_F12: "f12",
        }
        
        if key in key_map:
            return key_map[key]
        
        # 字母和数字键
        if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
            return chr(key).lower()
        if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            return chr(key)
        
        # 忽略单独的修饰键
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Shift, Qt.Key.Key_Meta):
            return ""
        
        return ""
    
    def setHotkey(self, hotkey: str):
        """设置显示的快捷键"""
        self.setText(hotkey)


class SettingsDialog(QDialog):
    """设置对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(450)
        self.setModal(True)
        
        self._init_ui()
        self._load_settings()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # 快捷键设置组
        hotkey_group = QGroupBox("快捷键设置")
        hotkey_layout = QVBoxLayout(hotkey_group)
        
        # 触发快捷键
        trigger_layout = QHBoxLayout()
        trigger_label = QLabel("生成图片触发键:")
        trigger_label.setMinimumWidth(120)
        self.hotkey_edit = HotkeyEdit()
        self.hotkey_edit.setMinimumWidth(200)
        trigger_layout.addWidget(trigger_label)
        trigger_layout.addWidget(self.hotkey_edit)
        trigger_layout.addStretch()
        hotkey_layout.addLayout(trigger_layout)
        
        # 当前快捷键显示
        self.current_label = QLabel()
        self.current_label.setStyleSheet("color: #666; margin-top: 5px;")
        hotkey_layout.addWidget(self.current_label)
        
        layout.addWidget(hotkey_group)
        
        # 预设快捷键按钮
        preset_group = QGroupBox("快捷预设（点击直接应用）")
        preset_layout = QHBoxLayout(preset_group)
        
        presets = [
            ("Enter", "enter"),
            ("Ctrl+Enter", "ctrl+enter"),
            ("Shift+Enter", "shift+enter"),
            ("Alt+S", "alt+s"),
        ]
        
        for label, hotkey in presets:
            btn = QPushButton(label)
            btn.clicked.connect(lambda checked, h=hotkey: self._set_preset(h))
            preset_layout.addWidget(btn)
        
        layout.addWidget(preset_group)
        
        # 提示信息
        hint_group = QGroupBox("使用说明")
        hint_layout = QVBoxLayout(hint_group)
        
        # 修复：使用三引号字符串避免引号冲突
        hint_text = """
<b>💡 推荐使用 Shift+Enter 或 Ctrl+Enter</b><br><br>
• 这样可以保留原生 Enter 键用于正常发送文字/图片<br>
• 按下组合键时才会触发【文字转图片】功能<br><br>
<b>⚠️ 保存后需要在 main.py 中按 Ctrl+F5 重载配置</b>
"""
        hint_label = QLabel(hint_text.strip())
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet("color: #555;")
        hint_layout.addWidget(hint_label)
        layout.addWidget(hint_group)
        
        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_save = QPushButton("保存")
        self.btn_save.setMinimumWidth(80)
        self.btn_save.clicked.connect(self._save_and_close)
        
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setMinimumWidth(80)
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(btn_layout)
    
    def _set_preset(self, hotkey: str):
        """设置预设快捷键"""
        self.hotkey_edit.setHotkey(hotkey)
    
    def _load_settings(self):
        """加载当前设置"""
        config = load_global_config()
        current_hotkey = config.get("trigger_hotkey", "enter")
        self.hotkey_edit.setHotkey(current_hotkey)
        self.current_label.setText(f"当前配置: {current_hotkey}")
    
    def _save_and_close(self):
        """保存设置并关闭"""
        hotkey = self.hotkey_edit.text().strip().lower()
        
        if not hotkey or hotkey == "请按下快捷键...":
            QMessageBox.warning(self, "错误", "请设置有效的快捷键")
            return
        
        # 检查是否与系统快捷键冲突
        dangerous_keys = ["esc", "ctrl+c", "ctrl+v", "ctrl+x", "ctrl+a", "ctrl+z", "ctrl+f5", "ctrl+f12"]
        if hotkey in dangerous_keys:
            QMessageBox.warning(
                self, 
                "警告", 
                f"快捷键 '{hotkey}' 与系统功能冲突，请选择其他快捷键"
            )
            return
        
        try:
            config = load_global_config()
            old_hotkey = config.get("trigger_hotkey", "enter")
            config["trigger_hotkey"] = hotkey
            save_global_config(config)
            
            msg = f"快捷键已从 [{old_hotkey}] 更改为 [{hotkey}]\n\n"
            msg += "请在 main.py 控制台按 Ctrl+F5 使设置立即生效。"
            
            QMessageBox.information(self, "保存成功", msg)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {e}")
