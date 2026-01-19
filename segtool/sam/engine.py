from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np


@dataclass
class SamConfig:
    checkpoint_path: Path
    model_type: str = "vit_b"
    device: str = "cuda"


class SamEngine:
    """
    Thin wrapper around Meta Segment-Anything predictor.
    Loaded lazily so the GUI can run without SAM dependencies/checkpoint.
    """

    def __init__(self) -> None:
        self._predictor = None
        self._cfg: Optional[SamConfig] = None

    @property
    def is_ready(self) -> bool:
        return self._predictor is not None

    @property
    def config(self) -> Optional[SamConfig]:
        return self._cfg

    def load(self, cfg: SamConfig) -> None:
        try:
            import torch
            from segment_anything import SamPredictor, sam_model_registry
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "SAM 依赖未安装：请先 `pip install -r requirements.txt`"
            ) from e

        if not cfg.checkpoint_path.exists():
            raise FileNotFoundError(str(cfg.checkpoint_path))

        device = cfg.device
        if device == "cuda":
            if not torch.cuda.is_available():
                device = "cpu"

        sam = sam_model_registry[cfg.model_type](checkpoint=str(cfg.checkpoint_path))
        sam.to(device=device)
        self._predictor = SamPredictor(sam)
        self._cfg = SamConfig(
            checkpoint_path=cfg.checkpoint_path,
            model_type=cfg.model_type,
            device=device,
        )

    def predict_mask_from_box(
        self,
        image_rgb_u8: np.ndarray,
        box_xyxy: tuple[int, int, int, int],
    ) -> np.ndarray:
        """
        image_rgb_u8: (H,W,3) uint8
        box_xyxy: (x0,y0,x1,y1) in pixel coords, inclusive/exclusive doesn't matter much.
        returns: (H,W) bool mask
        """
        if self._predictor is None:
            raise RuntimeError("SAM 尚未加载 checkpoint。")

        pred = self._predictor
        pred.set_image(image_rgb_u8)

        x0, y0, x1, y1 = box_xyxy
        box = np.array([x0, y0, x1, y1], dtype=np.float32)
        masks, scores, _logits = pred.predict(
            box=box[None, :],
            multimask_output=False,
        )
        _ = scores
        return masks[0].astype(bool)


def ensure_rgb_from_gray_u8(gray_u8: np.ndarray) -> np.ndarray:
    if gray_u8.ndim != 2:
        raise ValueError(f"Expected 2D grayscale, got {gray_u8.shape}")
    return np.stack([gray_u8, gray_u8, gray_u8], axis=-1)

