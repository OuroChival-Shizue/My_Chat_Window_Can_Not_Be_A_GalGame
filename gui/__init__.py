# gui/__init__.py
"""
GUI 模块入口
暴露 MainWindow 供外部调用，保持向后兼容
"""
from .main_window import MainWindow

__all__ = ["MainWindow"]
