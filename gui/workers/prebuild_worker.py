# gui/workers/prebuild_worker.py
"""后台缓存生成线程"""
from PyQt6.QtCore import QThread, pyqtSignal

from ..constants import prebuild_character


class PrebuildWorker(QThread):
    """后台执行 prebuild_character 的工作线程"""
    
    progress = pyqtSignal(str, int, int, str)  # event, current, total, message
    finished_ok = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, char_id: str, base_path: str, cache_dir: str, parent=None):
        super().__init__(parent)
        self.char_id = char_id
        self.base_path = base_path
        self.cache_dir = cache_dir

    def _report(self, event: str, current: int, total: int, message: str):
        self.progress.emit(event, current, total, message or "")

    def run(self):
        try:
            if prebuild_character is None:
                raise RuntimeError("prebuild_character 模块未加载")
            prebuild_character(
                self.char_id,
                self.base_path,
                self.cache_dir,
                force=True,
                progress=self._report,
            )
            self.finished_ok.emit()
        except Exception as exc:
            self.failed.emit(str(exc))
