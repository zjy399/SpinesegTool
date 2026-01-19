from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

import numpy as np

from .nifti_io import NiftiVolume, ViewOrientation

Side = Literal["left", "right"]


@dataclass
class BoxAnnotation:
    side: Side
    slice_index: int
    orientation: ViewOrientation  # 新增：记录标注时的方向
    label: int
    color: str
    box_xyxy: tuple[int, int, int, int]


@dataclass
class ImageState:
    side: Side
    volume: Optional[NiftiVolume] = None
    mask: Optional[np.ndarray] = None  # uint8, shape matches volume (2D or 3D)
    boxes: list[BoxAnnotation] = field(default_factory=list)

    def clear(self) -> None:
        self.volume = None
        self.mask = None
        self.boxes.clear()

    def ensure_mask(self) -> None:
        if self.volume is None:
            return
        if self.mask is None or self.mask.shape != self.volume.data.shape:
            self.mask = np.zeros(self.volume.data.shape, dtype=np.uint8)

    def get_mask_slice(self, idx: int, orientation: ViewOrientation = ViewOrientation.AXIAL) -> Optional[np.ndarray]:
        """获取指定方向和索引的mask切片"""
        if self.mask is None:
            return None
        if self.mask.ndim == 2:
            return self.mask
        
        if orientation == ViewOrientation.AXIAL:
            idx = int(np.clip(idx, 0, self.mask.shape[2] - 1))
            slice_2d = self.mask[:, :, idx]  # (H, W)
            # 旋转90度以匹配图像显示
            return np.rot90(slice_2d, k=-1)
        elif orientation == ViewOrientation.CORONAL:
            # 冠状面：data[:, idx, :]，转置+翻转
            idx = int(np.clip(idx, 0, self.mask.shape[1] - 1))
            slice_2d = self.mask[:, idx, :]  # (H, Z) = (前后, 上下)
            transposed = slice_2d.T  # (Z, H) = (上下, 前后)
            # 上下翻转以匹配图像显示
            return np.flipud(transposed)
        else:  # SAGITTAL (需要转置+翻转以匹配图像显示)
            # 矢状面：data[idx, :, :]，转置+翻转
            idx = int(np.clip(idx, 0, self.mask.shape[0] - 1))
            slice_2d = self.mask[idx, :, :]  # (W, Z) = (左右, 上下)
            transposed = slice_2d.T  # (Z, W) = (上下, 左右)
            # 上下和左右翻转以匹配图像显示
            flipped_ud = np.flipud(transposed)
            flipped_lr = np.fliplr(flipped_ud)
            return flipped_lr

    def apply_slice_mask(
        self, idx: int, slice_mask_bool: np.ndarray, label_value: int, 
        orientation: ViewOrientation = ViewOrientation.AXIAL
    ) -> None:
        """在指定方向和索引的切片上应用mask
        
        注意：对于矢状面，slice_mask_bool 的形状应该是转置后的（与显示一致）
        """
        if self.volume is None:
            return
        self.ensure_mask()
        assert self.mask is not None

        if self.mask.ndim == 2:
            self.mask[slice_mask_bool] = np.uint8(label_value)
            return

        if orientation == ViewOrientation.AXIAL:
            idx = int(np.clip(idx, 0, self.mask.shape[2] - 1))
            sl = self.mask[:, :, idx]  # (H, W)
            # slice_mask_bool 是旋转后的，需要逆旋转回来
            mask_rotated_back = np.rot90(slice_mask_bool, k=1)  # 逆旋转（k=1是逆时针90度）
            sl[mask_rotated_back] = np.uint8(label_value)
            self.mask[:, :, idx] = sl
        elif orientation == ViewOrientation.CORONAL:
            idx = int(np.clip(idx, 0, self.mask.shape[1] - 1))
            sl = self.mask[:, idx, :]  # (H, Z)
            # slice_mask_bool 已经经过转置+上下翻转，需要逆处理
            mask_flipped_ud = np.flipud(slice_mask_bool)  # 逆上下翻转
            mask_final = mask_flipped_ud.T  # 转置回 (H, Z)
            sl[mask_final] = np.uint8(label_value)
            self.mask[:, idx, :] = sl
        else:  # SAGITTAL
            idx = int(np.clip(idx, 0, self.mask.shape[0] - 1))
            sl = self.mask[idx, :, :]  # (W, Z)
            # slice_mask_bool 已经经过转置+上下翻转+左右翻转，需要逆处理
            mask_flipped_lr = np.fliplr(slice_mask_bool)  # 逆左右翻转
            mask_flipped_ud = np.flipud(mask_flipped_lr)  # 逆上下翻转
            mask_final = mask_flipped_ud.T  # 转置回 (W, Z)
            sl[mask_final] = np.uint8(label_value)
            self.mask[idx, :, :] = sl


@dataclass
class AppState:
    left: ImageState = field(default_factory=lambda: ImageState(side="left"))
    right: ImageState = field(default_factory=lambda: ImageState(side="right"))
    sam_checkpoint: Optional[Path] = None
    sam_model_type: str = "vit_b"
    sam_device: str = "cuda"

