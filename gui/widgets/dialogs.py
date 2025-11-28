# gui/widgets/dialogs.py
"""对话框组件"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
    QDialogButtonBox, QLabel, QProgressBar, QMessageBox
)
from PyQt6.QtCore import Qt

from ..workers.prebuild_worker import PrebuildWorker


class NewCharacterDialog(QDialog):
    """新建角色对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新建角色")
        self.resize(400, 200)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.edit_id = QLineEdit()
        self.edit_id.setPlaceholderText("例如: kotori (仅限英文/数字/下划线)")
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText("例如: 五河琴里")

        form.addRow("角色ID (文件夹名):", self.edit_id)
        form.addRow("显示名称:", self.edit_name)
        layout.addLayout(form)

        self.edit_id.textChanged.connect(self._auto_fill_name)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _auto_fill_name(self, text):
        if not self.edit_name.text():
            self.edit_name.setText(text)

    def get_data(self):
        return self.edit_id.text().strip(), self.edit_name.text().strip()


class PrebuildProgressDialog(QDialog):
    """缓存生成进度对话框"""

    def __init__(self, parent, char_id: str, base_path: str, cache_dir: str):
        super().__init__(parent)
        self.setWindowTitle(f"生成缓存 - {char_id}")
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)

        self.success = False
        self._had_error = False
        self._error_message = ""

        layout = QVBoxLayout(self)
        self.label_stage = QLabel("准备中...")
        self.label_detail = QLabel("")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)

        layout.addWidget(self.label_stage)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.label_detail)

        self.worker = PrebuildWorker(char_id, base_path, cache_dir, self)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_ok.connect(self._on_done)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()

    def _on_progress(self, event: str, current: int, total: int, message: str):
        if event == "error":
            self._had_error = True
            self._error_message = message or "未知错误"

        if total > 0:
            if self.progress_bar.maximum() != total:
                self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(min(current, total))
        else:
            self.progress_bar.setRange(0, 0)

        stage_map = {
            "start": "准备素材...",
            "prepare_bg": "处理中...",
            "composite": "生成底图",
            "skip": "缓存已存在",
            "done": "完成",
        }
        if event in stage_map:
            if total:
                self.label_stage.setText(f"{stage_map[event]} ({current}/{max(total, 1)})")
            else:
                self.label_stage.setText(stage_map[event])

        if message:
            self.label_detail.setText(message)

    def _finish(self):
        self.accept()

    def _on_done(self):
        if self._had_error:
            QMessageBox.warning(self, "警告", self._error_message)
        else:
            self.success = True
        self._finish()

    def _on_failed(self, message: str):
        QMessageBox.critical(self, "生成失败", message)
        self._finish()
