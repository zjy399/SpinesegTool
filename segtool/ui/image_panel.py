from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
from PySide6 import QtCore, QtWidgets

from ..core.image_utils import compose_overlay_rgb, normalize_to_uint8
from ..core.labels import LABELS
from ..core.nifti_io import NiftiVolume, ViewOrientation
from ..core.session import Side
from .image_canvas import Box, ImageCanvas


class ImagePanel(QtWidgets.QWidget):
    boxDrawn = QtCore.Signal(str, int, object)  # side, slice_idx, Box
    sliceChanged = QtCore.Signal(str, int)  # side, slice_idx

    def __init__(self, side: Side, title: str, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.side: Side = side
        self._volume: Optional[NiftiVolume] = None
        self._mask: Optional[np.ndarray] = None
        self._slice_idx: int = 0
        self._orientation: ViewOrientation = ViewOrientation.AXIAL

        self.title_label = QtWidgets.QLabel(title)
        self.path_label = QtWidgets.QLabel("")
        self.path_label.setWordWrap(True)
        
        # 方向选择（仅对3D图像显示）
        orient_row = QtWidgets.QHBoxLayout()
        orient_row.addWidget(QtWidgets.QLabel("Orientation:"))
        self.orient_combo = QtWidgets.QComboBox()
        self.orient_combo.addItems(["Axial (横断面)", "Coronal (冠状面)", "Sagittal (矢状面)"])
        self.orient_combo.setCurrentIndex(0)
        self.orient_combo.currentIndexChanged.connect(self._on_orientation_changed)
        self.orient_combo.setVisible(False)  # 默认隐藏，加载3D图像时显示
        orient_row.addWidget(self.orient_combo)
        orient_row.addStretch()
        
        self.canvas = ImageCanvas()
        self.slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(0)
        self.slider.setEnabled(False)
        self.slice_label = QtWidgets.QLabel("slice: -")

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.title_label)
        layout.addWidget(self.path_label)
        layout.addLayout(orient_row)
        layout.addWidget(self.canvas, stretch=1)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.slider, stretch=1)
        row.addWidget(self.slice_label)
        layout.addLayout(row)
        self.setLayout(layout)

        self.slider.valueChanged.connect(self._on_slider_changed)
        self.canvas.boxDrawn.connect(self._on_box_drawn)
    
    @property
    def orientation(self) -> ViewOrientation:
        return self._orientation

    @property
    def volume(self) -> Optional[NiftiVolume]:
        return self._volume

    @property
    def slice_index(self) -> int:
        return self._slice_idx

    def set_volume(self, vol: Optional[NiftiVolume]) -> None:
        self._volume = vol
        self._mask = None
        self._slice_idx = 0
        self._orientation = ViewOrientation.AXIAL

        if vol is None:
            self.path_label.setText("")
            self.orient_combo.setVisible(False)
            self.slider.setEnabled(False)
            self.slider.setMinimum(0)
            self.slider.setMaximum(0)
            self.slice_label.setText("slice: -")
            self.canvas.clear()
            return

        self.path_label.setText(str(Path(vol.path)))
        
        # 对于3D图像，显示方向选择；对于2D图像，隐藏
        is_3d = vol.is_3d
        self.orient_combo.setVisible(is_3d)
        
        if is_3d:
            self._update_slider_for_orientation()
        else:
            self.slider.setEnabled(False)
            self.slider.setMinimum(0)
            self.slider.setMaximum(0)
        
        self.slider.setValue(0)
        self._render()
    
    def _on_orientation_changed(self, index: int) -> None:
        """方向选择改变时的回调"""
        orientations = [ViewOrientation.AXIAL, ViewOrientation.CORONAL, ViewOrientation.SAGITTAL]
        self._orientation = orientations[index]
        if self._volume and self._volume.is_3d:
            self._update_slider_for_orientation()
        self._render()
    
    def _update_slider_for_orientation(self) -> None:
        """根据当前方向更新滑块范围"""
        if self._volume is None:
            return
        num_slices = self._volume.num_slices(self._orientation)
        self.slider.setEnabled(num_slices > 1)
        self.slider.setMinimum(0)
        self.slider.setMaximum(max(0, num_slices - 1))
        # 调整当前索引到新方向的有效范围
        current_idx = min(self._slice_idx, num_slices - 1)
        self.slider.setValue(current_idx)
        self._slice_idx = current_idx

    def set_mask(self, mask: Optional[np.ndarray]) -> None:
        self._mask = mask
        self._render()

    def _on_slider_changed(self, v: int) -> None:
        self._slice_idx = int(v)
        self._render()
        self.sliceChanged.emit(self.side, self._slice_idx)

    def _on_box_drawn(self, box: Box) -> None:
        self.boxDrawn.emit(self.side, self._slice_idx, box)

    def _render(self) -> None:
        if self._volume is None:
            return

        img2d = self._volume.get_slice(self._slice_idx, self._orientation)
        base_u8 = normalize_to_uint8(img2d)
        
        # 获取对应方向的mask切片（使用 session 的方法，确保与图像显示一致）
        mask2d: Optional[np.ndarray] = None
        if self._mask is not None:
            if self._mask.ndim == 2:
                mask2d = self._mask
            else:
                # 使用与图像相同的逻辑提取mask切片
                if self._orientation == ViewOrientation.AXIAL:
                    idx = int(np.clip(self._slice_idx, 0, self._mask.shape[2] - 1))
                    slice_2d = self._mask[:, :, idx]  # (H, W)
                    mask2d = np.rot90(slice_2d, k=-1)  # 旋转以匹配图像显示
                elif self._orientation == ViewOrientation.CORONAL:
                    idx = int(np.clip(self._slice_idx, 0, self._mask.shape[1] - 1))
                    slice_2d = self._mask[:, idx, :]  # (H, Z) = (前后, 上下)
                    transposed = slice_2d.T  # (Z, H) = (上下, 前后)
                    mask2d = np.flipud(transposed)  # 上下翻转以匹配图像显示
                else:  # SAGITTAL (需要转置+翻转以匹配图像显示)
                    idx = int(np.clip(self._slice_idx, 0, self._mask.shape[0] - 1))
                    slice_2d = self._mask[idx, :, :]  # (W, Z) = (左右, 上下)
                    transposed = slice_2d.T  # (Z, W) = (上下, 左右)
                    flipped_ud = np.flipud(transposed)
                    mask2d = np.fliplr(flipped_ud)  # 上下和左右翻转以匹配图像显示

        label_to_rgb = {spec.value: spec.rgb for spec in LABELS.values()}
        rgb = compose_overlay_rgb(base_u8, mask2d, label_to_rgb=label_to_rgb, alpha=0.4)
        self.canvas.set_image_rgb(rgb)

        num_slices = self._volume.num_slices(self._orientation)
        if num_slices == 1:
            self.slice_label.setText("slice: 0/0")
        else:
            self.slice_label.setText(f"slice: {self._slice_idx}/{num_slices - 1}")

