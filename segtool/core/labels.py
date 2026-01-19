from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LabelSpec:
    value: int
    name: str
    color_name: str
    rgb: tuple[int, int, int]


LABELS: dict[str, LabelSpec] = {
    "gray": LabelSpec(value=1, name="Gray", color_name="gray", rgb=(128, 128, 128)),
    "blue": LabelSpec(value=2, name="Blue", color_name="blue", rgb=(0, 0, 255)),
    "red": LabelSpec(value=3, name="Red", color_name="red", rgb=(255, 0, 0)),
    # 新增 15 种颜色
    "green": LabelSpec(value=4, name="Green", color_name="green", rgb=(0, 255, 0)),
    "yellow": LabelSpec(value=5, name="Yellow", color_name="yellow", rgb=(255, 255, 0)),
    "orange": LabelSpec(value=6, name="Orange", color_name="orange", rgb=(255, 165, 0)),
    "purple": LabelSpec(value=7, name="Purple", color_name="purple", rgb=(128, 0, 128)),
    "pink": LabelSpec(value=8, name="Pink", color_name="pink", rgb=(255, 192, 203)),
    "cyan": LabelSpec(value=9, name="Cyan", color_name="cyan", rgb=(0, 255, 255)),
    "magenta": LabelSpec(value=10, name="Magenta", color_name="magenta", rgb=(255, 0, 255)),
    "lime": LabelSpec(value=11, name="Lime", color_name="lime", rgb=(50, 205, 50)),
    "teal": LabelSpec(value=12, name="Teal", color_name="teal", rgb=(0, 128, 128)),
    "indigo": LabelSpec(value=13, name="Indigo", color_name="indigo", rgb=(75, 0, 130)),
    "brown": LabelSpec(value=14, name="Brown", color_name="brown", rgb=(165, 42, 42)),
    "navy": LabelSpec(value=15, name="Navy", color_name="navy", rgb=(0, 0, 128)),
    "olive": LabelSpec(value=16, name="Olive", color_name="olive", rgb=(128, 128, 0)),
    "maroon": LabelSpec(value=17, name="Maroon", color_name="maroon", rgb=(128, 0, 0)),
    "aqua": LabelSpec(value=18, name="Aqua", color_name="aqua", rgb=(0, 255, 127)),
}

