from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets


@dataclass(frozen=True)
class Box:
    x0: int
    y0: int
    x1: int
    y1: int

    def as_xyxy(self) -> tuple[int, int, int, int]:
        return (self.x0, self.y0, self.x1, self.y1)


class ImageCanvas(QtWidgets.QWidget):
    boxDrawn = QtCore.Signal(object)  # Box in image coords

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)

        self._img_rgb: Optional[np.ndarray] = None  # (H,W,3) uint8
        self._pixmap: Optional[QtGui.QPixmap] = None
        self._pixmap_rect = QtCore.QRectF()

        self._dragging = False
        self._drag_start: Optional[QtCore.QPointF] = None
        self._drag_end: Optional[QtCore.QPointF] = None

    def set_image_rgb(self, img_rgb: np.ndarray) -> None:
        self._img_rgb = np.ascontiguousarray(img_rgb, dtype=np.uint8)
        h, w, _c = self._img_rgb.shape
        qimg = QtGui.QImage(
            self._img_rgb.data,
            w,
            h,
            int(self._img_rgb.strides[0]),
            QtGui.QImage.Format.Format_RGB888,
        )
        self._pixmap = QtGui.QPixmap.fromImage(qimg.copy())
        # 保存原始宽高比
        self._aspect_ratio = w / h if h > 0 else 1.0
        self.update()

    def clear(self) -> None:
        self._img_rgb = None
        self._pixmap = None
        self._dragging = False
        self._drag_start = None
        self._drag_end = None
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: ARG002
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), QtGui.QColor(20, 20, 20))

        if self._pixmap is None:
            p.setPen(QtGui.QPen(QtGui.QColor(180, 180, 180)))
            p.drawText(self.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, "No image")
            return

        # Fit pixmap keeping aspect ratio
        r = QtCore.QRectF(self.rect())
        pm_size = QtCore.QSizeF(self._pixmap.size())
        # 检查是否是矢状位或冠状位（可能需要特殊处理）
        # 对于矢状位和冠状位，如果垂直方向应该是长边但数据中较短，
        # 可能需要调整显示比例
        pm_size.scale(r.size(), QtCore.Qt.AspectRatioMode.KeepAspectRatio)
        x = r.left() + (r.width() - pm_size.width()) / 2.0
        y = r.top() + (r.height() - pm_size.height()) / 2.0
        target = QtCore.QRectF(x, y, pm_size.width(), pm_size.height())
        self._pixmap_rect = target

        p.drawPixmap(target.toRect(), self._pixmap)

        # draw current drag rectangle (widget coords)
        if self._dragging and self._drag_start is not None and self._drag_end is not None:
            pen = QtGui.QPen(QtGui.QColor(0, 255, 0))
            pen.setWidth(2)
            p.setPen(pen)
            p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            rect = QtCore.QRectF(self._drag_start, self._drag_end).normalized()
            p.drawRect(rect)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            return
        if self._pixmap is None:
            return
        self._dragging = True
        self._drag_start = QtCore.QPointF(event.position())
        self._drag_end = QtCore.QPointF(event.position())
        self.update()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if not self._dragging:
            return
        self._drag_end = QtCore.QPointF(event.position())
        self.update()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            return
        if not self._dragging:
            return
        self._dragging = False
        self._drag_end = QtCore.QPointF(event.position())
        self.update()

        box = self._compute_box_image_coords()
        if box is not None:
            self.boxDrawn.emit(box)

    def _compute_box_image_coords(self) -> Optional[Box]:
        if self._img_rgb is None or self._pixmap is None:
            return None
        if self._drag_start is None or self._drag_end is None:
            return None

        rect_w = self._pixmap_rect
        if rect_w.isNull() or rect_w.width() <= 1 or rect_w.height() <= 1:
            return None

        w_img = int(self._img_rgb.shape[1])
        h_img = int(self._img_rgb.shape[0])

        def to_img(pt: QtCore.QPointF) -> tuple[int, int]:
            x = (pt.x() - rect_w.left()) / rect_w.width()
            y = (pt.y() - rect_w.top()) / rect_w.height()
            x = float(np.clip(x, 0.0, 1.0))
            y = float(np.clip(y, 0.0, 1.0))
            xi = int(round(x * (w_img - 1)))
            yi = int(round(y * (h_img - 1)))
            xi = int(np.clip(xi, 0, w_img - 1))
            yi = int(np.clip(yi, 0, h_img - 1))
            return xi, yi

        x0, y0 = to_img(self._drag_start)
        x1, y1 = to_img(self._drag_end)
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))

        # Reject too small boxes
        if (x1 - x0) < 2 or (y1 - y0) < 2:
            return None

        return Box(x0=x0, y0=y0, x1=x1, y1=y1)

