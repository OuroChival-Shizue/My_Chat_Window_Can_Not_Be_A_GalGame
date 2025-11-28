#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Box-of-GalGame-Sister 可视化编辑器
启动入口（重构后）
"""
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont

from gui import MainWindow


def main():
    app = QApplication(sys.argv)
    
    # 设置默认字体
    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)
    
    # 创建并显示主窗口
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
