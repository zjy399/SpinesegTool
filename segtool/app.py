from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6 import QtWidgets

if __package__ is None or __package__ == "":  # pragma: no cover
    # Running as a script: `python segtool/app.py`
    # Ensure project root is on sys.path so `import segtool...` works.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    # Package run: `python -m segtool`
    from .ui.main_window import MainWindow
except ImportError:  # pragma: no cover
    # Script run: `python segtool/app.py` (no parent package)
    from segtool.ui.main_window import MainWindow


def main() -> int:
    # Preflight: GUI environment check (common issue when running via SSH / headless)
    qt_platform = (os.environ.get("QT_QPA_PLATFORM") or "").strip().lower()
    has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    headless_ok_platforms = {"offscreen", "minimal", "vnc", "linuxfb", "eglfs", "minimalegl"}

    if not has_display and qt_platform not in headless_ok_platforms:
        sys.stderr.write(
            "无法启动 GUI：当前没有可用的显示环境（DISPLAY/WAYLAND_DISPLAY 为空）。\n"
            "这通常发生在：通过 SSH 登录服务器、在无桌面环境的终端里运行。\n\n"
            "解决方案：\n"
            "  1) 在有桌面环境的机器上运行（本机终端/远程桌面/VNC）。\n"
            "  2) SSH 场景：使用 X11 转发（例如 ssh -X / -Y），并确保本地有 X server。\n"
            "  3) 使用 Qt 的 VNC 后端：\n"
            "       QT_QPA_PLATFORM=vnc QT_QPA_VNC_PORT=5900 python -m segtool\n\n"
            "如果你是在桌面环境但仍提示 Qt xcb 插件问题，可尝试安装：libxcb-cursor0。\n"
        )
        return 1

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("segtool")
    win = MainWindow()
    win.resize(1400, 800)
    win.show()
    return app.exec()

