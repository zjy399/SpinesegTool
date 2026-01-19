from __future__ import annotations

import numpy as np


def normalize_to_uint8(img2d: np.ndarray) -> np.ndarray:
    """
    Normalize a 2D array to uint8 [0,255] using robust percentiles.
    """
    a = np.asarray(img2d, dtype=np.float32)
    if not np.isfinite(a).any():
        return np.zeros_like(a, dtype=np.uint8)

    vmin = np.nanpercentile(a, 1.0)
    vmax = np.nanpercentile(a, 99.0)
    if vmax <= vmin:
        vmin = float(np.nanmin(a))
        vmax = float(np.nanmax(a))
        if vmax <= vmin:
            return np.zeros_like(a, dtype=np.uint8)

    a = (a - vmin) / (vmax - vmin)
    a = np.clip(a, 0.0, 1.0)
    return (a * 255.0).astype(np.uint8)


def compose_overlay_rgb(
    base_u8: np.ndarray,
    label_mask_u8: np.ndarray | None,
    label_to_rgb: dict[int, tuple[int, int, int]],
    alpha: float = 0.4,
) -> np.ndarray:
    """
    base_u8: (H,W) uint8
    label_mask_u8: (H,W) uint8 values 0..N
    returns: (H,W,3) uint8
    """
    base = np.stack([base_u8, base_u8, base_u8], axis=-1).astype(np.float32)
    if label_mask_u8 is None:
        return base.astype(np.uint8)

    out = base
    m = label_mask_u8.astype(np.uint8)
    for val, rgb in label_to_rgb.items():
        if val == 0:
            continue
        sel = m == val
        if not np.any(sel):
            continue
        color = np.array(rgb, dtype=np.float32).reshape(1, 1, 3)
        out[sel] = out[sel] * (1.0 - alpha) + color * alpha

    return np.clip(out, 0, 255).astype(np.uint8)

