# gui/canvas/items.py
"""
自定义 QGraphicsItem 实现
- ResizableTextItem: 可拖动、可调整大小的文本框
- ScalableImageItem: 支持滚轮缩放的图片
"""
from typing import List

from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsPixmapItem, QGraphicsItem
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPixmap, QColor, QPen, QBrush, QFont, QPainter


class ResizableTextItem(QGraphicsRectItem):
    """可缩放、可拖动的文本预览框"""
    
    HANDLE_SIZE = 10
    STATE_IDLE = 0
    STATE_MOVE = 1
    STATE_RESIZE = 2

    # 方向位掩码
    DIR_NONE = 0x00
    DIR_LEFT = 0x01
    DIR_RIGHT = 0x02
    DIR_TOP = 0x04
    DIR_BOTTOM = 0x08
    DIR_TOP_LEFT = DIR_TOP | DIR_LEFT
    DIR_TOP_RIGHT = DIR_TOP | DIR_RIGHT
    DIR_BOTTOM_LEFT = DIR_BOTTOM | DIR_LEFT
    DIR_BOTTOM_RIGHT = DIR_BOTTOM | DIR_RIGHT

    def __init__(
        self,
        rect: QRectF,
        text: str,
        color: List[int],
        font_size: int = 40,
        font_family: str = ""
    ):
        super().__init__(rect)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)

        self.preview_text = text
        self.text_color = QColor(*color)
        self.font_size = font_size
        self.font_family = font_family

        self.setPen(QPen(QColor(200, 200, 200, 150), 2, Qt.PenStyle.DashLine))
        self.setBrush(QBrush(QColor(255, 255, 255, 30)))

        self._state = self.STATE_IDLE
        self._resize_dir = self.DIR_NONE
        self._start_mouse_pos = QPointF()
        self._start_rect = QRectF()

    def update_content(
        self,
        text: str = None,
        color: List[int] = None,
        size: int = None
    ):
        if text is not None:
            self.preview_text = text
        if color is not None:
            self.text_color = QColor(*color)
        if size is not None:
            self.font_size = size
        self.update()

    def hoverMoveEvent(self, event):
        if self.isSelected():
            direction = self._hit_test(event.pos())
            self._update_cursor(direction)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            direction = self._hit_test(pos)

            if direction != self.DIR_NONE:
                self._state = self.STATE_RESIZE
                self._resize_dir = direction
                self._start_mouse_pos = event.scenePos()
                self._start_rect = self.rect()
                event.accept()
            else:
                self._state = self.STATE_MOVE
                self.setCursor(Qt.CursorShape.SizeAllCursor)
                super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._state == self.STATE_RESIZE:
            delta = event.scenePos() - self._start_mouse_pos
            new_rect = QRectF(self._start_rect)
            min_w, min_h = 50, 30

            if self._resize_dir & self.DIR_LEFT:
                new_rect.setLeft(min(new_rect.right() - min_w, new_rect.left() + delta.x()))
            if self._resize_dir & self.DIR_RIGHT:
                new_rect.setRight(max(new_rect.left() + min_w, new_rect.right() + delta.x()))
            if self._resize_dir & self.DIR_TOP:
                new_rect.setTop(min(new_rect.bottom() - min_h, new_rect.top() + delta.y()))
            if self._resize_dir & self.DIR_BOTTOM:
                new_rect.setBottom(max(new_rect.top() + min_h, new_rect.bottom() + delta.y()))

            self.setRect(new_rect)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._state = self.STATE_IDLE
        self._resize_dir = self.DIR_NONE
        self._update_cursor(self._hit_test(event.pos()))
        super().mouseReleaseEvent(event)

    def _hit_test(self, pos: QPointF) -> int:
        rect = self.rect()
        x, y = pos.x(), pos.y()
        result = self.DIR_NONE

        on_left = abs(x - rect.left()) < self.HANDLE_SIZE
        on_right = abs(x - rect.right()) < self.HANDLE_SIZE
        on_top = abs(y - rect.top()) < self.HANDLE_SIZE
        on_bottom = abs(y - rect.bottom()) < self.HANDLE_SIZE

        if on_left:
            result |= self.DIR_LEFT
        if on_right:
            result |= self.DIR_RIGHT
        if on_top:
            result |= self.DIR_TOP
        if on_bottom:
            result |= self.DIR_BOTTOM

        return result

    def _update_cursor(self, direction):
        if direction == self.DIR_TOP_LEFT or direction == self.DIR_BOTTOM_RIGHT:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif direction == self.DIR_TOP_RIGHT or direction == self.DIR_BOTTOM_LEFT:
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif direction & self.DIR_LEFT or direction & self.DIR_RIGHT:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif direction & self.DIR_TOP or direction & self.DIR_BOTTOM:
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        pen_color = QColor(0, 120, 215) if self.isSelected() else QColor(150, 150, 150, 100)
        width = 2 if self.isSelected() else 1
        painter.setPen(QPen(pen_color, width, Qt.PenStyle.DashLine))
        painter.setBrush(self.brush())
        painter.drawRect(self.rect())

        painter.setPen(QPen(self.text_color))
        font = QFont()
        font.setPixelSize(self.font_size)
        if self.font_family:
            font.setFamily(self.font_family)
        else:
            font.setFamily("Microsoft YaHei")
        painter.setFont(font)

        text_rect = self.rect()
        painter.drawText(
            text_rect,
            Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft,
            self.preview_text
        )


class ScalableImageItem(QGraphicsPixmapItem):
    """支持滚轮缩放的图片项"""

    def __init__(self, pixmap: QPixmap):
        super().__init__(pixmap)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setTransformationMode(Qt.TransformationMode.SmoothTransformation)

    def wheelEvent(self, event) -> None:
        if self.isSelected():
            factor = 1.05 if event.delta() > 0 else 0.95
            self.setScale(max(0.1, min(self.scale() * factor, 5.0)))
            event.accept()
        else:
            super().wheelEvent(event)
