# gui/widgets/asset_list.py
"""支持拖拽导入和右键删除的资源列表"""
from PyQt6.QtWidgets import QListWidget, QMenu
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QAction, QDragEnterEvent, QDropEvent


class AssetListWidget(QListWidget):
    """资源列表控件，支持拖拽添加和右键删除"""
    
    fileDropped = pyqtSignal(str)      # 文件拖入信号
    deleteRequested = pyqtSignal(str)  # 请求删除信号

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.DragDropMode.DropOnly)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(('.png', '.jpg', '.jpeg')):
                self.fileDropped.emit(path)

    def contextMenuEvent(self, event):
        item = self.itemAt(event.pos())
        if item:
            menu = QMenu(self)
            delete_action = QAction("删除此文件", self)
            delete_action.triggered.connect(lambda: self.deleteRequested.emit(item.text()))
            menu.addAction(delete_action)
            menu.exec(event.globalPos())
