from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Literal, Optional

import nibabel as nib
import numpy as np


class ViewOrientation(str, Enum):
    """图像显示方向"""
    AXIAL = "axial"  # 横断面 (沿Z轴)
    CORONAL = "coronal"  # 冠状面 (沿Y轴)
    SAGITTAL = "sagittal"  # 矢状面 (沿X轴)


@dataclass
class NiftiVolume:
    path: Path
    data: np.ndarray  # float/integers, shape: (H,W) or (H,W,Z) (we support 2D/3D)
    affine: np.ndarray
    header: nib.Nifti1Header

    @property
    def is_3d(self) -> bool:
        return self.data.ndim == 3

    def num_slices(self, orientation: ViewOrientation = ViewOrientation.AXIAL) -> int:
        """获取指定方向的切片数量"""
        if self.data.ndim == 2:
            return 1
        if orientation == ViewOrientation.AXIAL:
            return int(self.data.shape[2])
        elif orientation == ViewOrientation.CORONAL:
            return int(self.data.shape[1])  # 固定左右方向
        else:  # SAGITTAL
            return int(self.data.shape[0])  # 固定前后方向

    def get_slice(self, idx: int, orientation: ViewOrientation = ViewOrientation.AXIAL) -> np.ndarray:
        """获取指定方向和索引的切片
        
        Args:
            idx: 切片索引
            orientation: 显示方向 (axial/coronal/sagittal)
        """
        if self.data.ndim == 2:
            return self.data
        
        if orientation == ViewOrientation.AXIAL:
            # 横断面: data[:, :, idx] - 显示 H×W
            # 需要旋转使后背向下（用户说后背向右但应该向下）
            idx = int(np.clip(idx, 0, self.data.shape[2] - 1))
            slice_2d = self.data[:, :, idx]  # (H, W)
            # 顺时针旋转90度使后背向下
            rotated = np.rot90(slice_2d, k=-1)
            return rotated
        elif orientation == ViewOrientation.CORONAL:
            # 冠状面：应该显示 (上下=Z, 前后=H)
            # 用户说方向是对的但上下被压缩，说明Z应该在垂直方向且是长边
            idx = int(np.clip(idx, 0, self.data.shape[1] - 1))  # 固定左右方向
            slice_2d = self.data[:, idx, :]  # (H, Z) = (前后, 上下)
            # 转置使Z在垂直方向：(Z, H) = (上下, 前后)
            transposed = slice_2d.T
            # 如果转置后高度 < 宽度，说明垂直方向（Z）被压缩了
            # 需要旋转使垂直方向成为长边，但保持Z轴在垂直方向
            # 如果 (Z, H) = (231, 512)，高度 < 宽度，需要让高度成为长边
            # 旋转90度得到 (H, Z) = (512, 231)，但这样Z不在垂直
            # 用户说方向是对的，所以可能是数据本身的问题，或者需要不同的处理
            
            # 保持Z在垂直方向
            rotated = transposed
            # 上下翻转以修正方向
            flipped = np.flipud(rotated)
            return flipped
        else:  # SAGITTAL
            # 矢状面：应该显示 (上下=Z, 左右=W)
            idx = int(np.clip(idx, 0, self.data.shape[0] - 1))  # 固定前后方向
            slice_2d = self.data[idx, :, :]  # (W, Z) = (左右, 上下)
            # 转置使Z在垂直方向：(Z, W) = (上下, 左右)
            transposed = slice_2d.T
            # 用户说方向是对的但上下被压缩
            # 保持Z在垂直方向，即使它维度较小
            rotated = transposed
            
            # 上下翻转以修正方向
            flipped_ud = np.flipud(rotated)
            # 左右翻转
            flipped_lr = np.fliplr(flipped_ud)
            return flipped_lr
    
    def get_slice_shape(self, orientation: ViewOrientation = ViewOrientation.AXIAL) -> tuple[int, int]:
        """获取指定方向切片的形状 (height, width)"""
        if self.data.ndim == 2:
            return tuple(self.data.shape)
        if orientation == ViewOrientation.AXIAL:
            # 横断面旋转90度后，形状从 (H, W) 变成 (W, H)
            return (self.data.shape[1], self.data.shape[0])
        elif orientation == ViewOrientation.CORONAL:
            # 冠状面：转置后 (Z, H)，如果高度<宽度则旋转，最终形状取决于哪个维度更大
            h, w = self.data.shape[2], self.data.shape[0]
            return (max(h, w), min(h, w)) if h < w else (h, w)
        else:  # SAGITTAL
            # 矢状面：转置后 (Z, W)，如果高度<宽度则旋转
            h, w = self.data.shape[2], self.data.shape[1]
            return (max(h, w), min(h, w)) if h < w else (h, w)


def load_nifti(path: str | Path) -> NiftiVolume:
    p = Path(path)
    img = nib.load(str(p))
    data = img.get_fdata(dtype=np.float32)

    # Accept 2D, 3D. If 4D, take first volume.
    if data.ndim == 4:
        data = data[:, :, :, 0]
    if data.ndim not in (2, 3):
        raise ValueError(f"Unsupported NIfTI dimensions: {data.shape}")

    return NiftiVolume(path=p, data=data, affine=img.affine, header=img.header)


def save_mask_nifti(
    out_path: str | Path,
    mask: np.ndarray,
    reference: Optional[NiftiVolume],
) -> None:
    out_p = Path(out_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    if reference is not None:
        affine = reference.affine
        header = reference.header.copy()
    else:
        affine = np.eye(4, dtype=np.float32)
        header = nib.Nifti1Header()

    header.set_data_dtype(np.uint8)
    img = nib.Nifti1Image(mask.astype(np.uint8), affine=affine, header=header)
    nib.save(img, str(out_p))

