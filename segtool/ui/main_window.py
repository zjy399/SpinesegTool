from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Optional

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from ..core.labels import LABELS, LabelSpec
from ..core.nifti_io import load_nifti, save_mask_nifti, ViewOrientation
from ..core.session import AppState, BoxAnnotation, ImageState, Side
from ..sam.engine import SamConfig, SamEngine, ensure_rgb_from_gray_u8
from .image_panel import ImagePanel


class _SamJob(QtCore.QObject):
    finished = QtCore.Signal(str, int, object, object)  # side, slice_idx, mask_bool, err_or_none

    def __init__(
        self,
        engine: SamEngine,
        image_rgb_u8: np.ndarray,
        side: Side,
        slice_idx: int,
        box_xyxy: tuple[int, int, int, int],
    ) -> None:
        super().__init__()
        self._engine = engine
        self._img = image_rgb_u8
        self._side = side
        self._slice_idx = slice_idx
        self._box = box_xyxy

    @QtCore.Slot()
    def run(self) -> None:
        try:
            m = self._engine.predict_mask_from_box(self._img, self._box)
            self.finished.emit(self._side, self._slice_idx, m, None)
        except Exception as e:  # noqa: BLE001
            self.finished.emit(self._side, self._slice_idx, None, str(e))


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Spine Data segtool V-1.0")

        self.state = AppState()
        self.sam = SamEngine()
        self._sam_thread: Optional[QtCore.QThread] = None
        self._sam_busy = False

        self.left_panel = ImagePanel(side="left", title="Left (X-ray)")
        self.right_panel = ImagePanel(side="right", title="Right (MRI)")
        self.tools = self._build_tools_panel()

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.addWidget(self.left_panel)
        splitter.addWidget(self.tools)
        splitter.addWidget(self.right_panel)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 4)

        central = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout()
        lay.addWidget(splitter)
        central.setLayout(lay)
        self.setCentralWidget(central)

        self.left_panel.boxDrawn.connect(self._on_box_drawn)
        self.right_panel.boxDrawn.connect(self._on_box_drawn)

        self._refresh_status()

    # -------------------- UI --------------------
    def _build_tools_panel(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()

        # Load
        grp_load = QtWidgets.QGroupBox("Load NIfTI")
        gl = QtWidgets.QVBoxLayout()
        self.btn_load_left = QtWidgets.QPushButton("Load Left (X-ray) .nii/.nii.gz")
        self.btn_load_right = QtWidgets.QPushButton("Load Right (MRI) .nii/.nii.gz")
        gl.addWidget(self.btn_load_left)
        gl.addWidget(self.btn_load_right)
        grp_load.setLayout(gl)

        self.btn_load_left.clicked.connect(lambda: self._load_volume("left"))
        self.btn_load_right.clicked.connect(lambda: self._load_volume("right"))

        # Labels (18 colors)
        grp_label = QtWidgets.QGroupBox("Label (18 colors)")
        glb = QtWidgets.QVBoxLayout()
        self.label_group = QtWidgets.QButtonGroup(self)
        
        # Create scrollable area for labels
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(200)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        label_widget = QtWidgets.QWidget()
        label_layout = QtWidgets.QGridLayout()
        label_layout.setSpacing(4)
        
        self.label_buttons: dict[str, QtWidgets.QRadioButton] = {}
        row, col = 0, 0
        for key, label_spec in sorted(LABELS.items(), key=lambda x: x[1].value):
            rb = QtWidgets.QRadioButton(label_spec.name)
            # Set button color as background
            color = QtGui.QColor(*label_spec.rgb)
            rb.setStyleSheet(
                f"QRadioButton::indicator {{"
                f"  width: 16px;"
                f"  height: 16px;"
                f"}}"
                f"QRadioButton {{"
                f"  background-color: rgb({color.red()}, {color.green()}, {color.blue()});"
                f"  padding: 2px 4px;"
                f"  border-radius: 3px;"
                f"}}"
            )
            self.label_buttons[key] = rb
            self.label_group.addButton(rb, label_spec.value)
            label_layout.addWidget(rb, row, col)
            col += 1
            if col >= 2:  # 2 columns
                col = 0
                row += 1
            if key == "gray":  # Default selection
                rb.setChecked(True)
        
        label_widget.setLayout(label_layout)
        scroll.setWidget(label_widget)
        glb.addWidget(scroll)
        grp_label.setLayout(glb)

        # SAM
        grp_sam = QtWidgets.QGroupBox("SAM")
        gs = QtWidgets.QVBoxLayout()
        self.btn_pick_ckpt = QtWidgets.QPushButton("选择 SAM checkpoint (.pth)")
        self.ckpt_label = QtWidgets.QLabel("checkpoint: (none)")
        self.ckpt_label.setWordWrap(True)

        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("model:"))
        self.combo_model = QtWidgets.QComboBox()
        self.combo_model.addItems(["vit_b", "vit_l", "vit_h"])
        row.addWidget(self.combo_model, stretch=1)
        gs.addWidget(self.btn_pick_ckpt)
        gs.addWidget(self.ckpt_label)
        gs.addLayout(row)

        row2 = QtWidgets.QHBoxLayout()
        row2.addWidget(QtWidgets.QLabel("device:"))
        self.combo_device = QtWidgets.QComboBox()
        self.combo_device.addItems(["cuda", "cpu"])
        row2.addWidget(self.combo_device, stretch=1)
        gs.addLayout(row2)

        self.btn_load_sam = QtWidgets.QPushButton("Load SAM")
        gs.addWidget(self.btn_load_sam)
        grp_sam.setLayout(gs)

        self.btn_pick_ckpt.clicked.connect(self._pick_checkpoint)
        self.btn_load_sam.clicked.connect(self._load_sam)

        # Actions
        grp_act = QtWidgets.QGroupBox("Actions")
        ga = QtWidgets.QVBoxLayout()
        self.btn_undo_left = QtWidgets.QPushButton("Undo last box record (Left)")
        self.btn_undo_right = QtWidgets.QPushButton("Undo last box record (Right)")
        self.btn_clear_left = QtWidgets.QPushButton("Clear Left mask/boxes")
        self.btn_clear_right = QtWidgets.QPushButton("Clear Right mask/boxes")
        self.btn_save = QtWidgets.QPushButton("Save (mask .nii.gz + boxes .json)")
        ga.addWidget(self.btn_undo_left)
        ga.addWidget(self.btn_undo_right)
        ga.addWidget(self.btn_clear_left)
        ga.addWidget(self.btn_clear_right)
        ga.addSpacing(8)
        ga.addWidget(self.btn_save)
        grp_act.setLayout(ga)

        self.btn_undo_left.clicked.connect(lambda: self._undo("left"))
        self.btn_undo_right.clicked.connect(lambda: self._undo("right"))
        self.btn_clear_left.clicked.connect(lambda: self._clear("left"))
        self.btn_clear_right.clicked.connect(lambda: self._clear("right"))
        self.btn_save.clicked.connect(self._save_all)

        # Status
        grp_status = QtWidgets.QGroupBox("Status")
        gst = QtWidgets.QVBoxLayout()
        self.status_label = QtWidgets.QLabel("")
        self.status_label.setWordWrap(True)
        gst.addWidget(self.status_label)
        grp_status.setLayout(gst)

        # Logo and Copyright
        grp_logo = QtWidgets.QGroupBox("")
        grp_logo.setStyleSheet("QGroupBox { border: none; }")
        logo_layout = QtWidgets.QVBoxLayout()
        logo_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        # Load and display logo
        logo_path = Path(__file__).parent.parent.parent / "logo.png"
        if logo_path.exists():
            logo_label = QtWidgets.QLabel()
            pixmap = QtGui.QPixmap(str(logo_path))
            # Scale logo to fit (max width 200px, maintain aspect ratio)
            if pixmap.width() > 200:
                pixmap = pixmap.scaledToWidth(200, QtCore.Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(pixmap)
            logo_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            logo_layout.addWidget(logo_label)
        
        # Copyright text
        copyright_label = QtWidgets.QLabel("© Junyong Zhao, NUAA")
        copyright_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        copyright_label.setStyleSheet("color: #666; font-size: 10pt; margin-top: 5px;")
        logo_layout.addWidget(copyright_label)
        logo_layout.addSpacing(5)
        
        grp_logo.setLayout(logo_layout)

        layout.addWidget(grp_load)
        layout.addWidget(grp_label)
        layout.addWidget(grp_sam)
        layout.addWidget(grp_act)
        layout.addWidget(grp_status)
        layout.addWidget(grp_logo)
        layout.addStretch(1)
        w.setLayout(layout)
        w.setMinimumWidth(320)
        return w

    # -------------------- Helpers --------------------
    def _current_label(self) -> LabelSpec:
        # Find which radio button is checked
        for key, rb in self.label_buttons.items():
            if rb.isChecked():
                return LABELS[key]
        # Fallback to gray if none selected (should not happen)
        return LABELS["gray"]

    def _get_image_state(self, side: Side) -> ImageState:
        return self.state.left if side == "left" else self.state.right

    def _get_panel(self, side: Side) -> ImagePanel:
        return self.left_panel if side == "left" else self.right_panel

    def _refresh_status(self, msg: Optional[str] = None) -> None:
        parts: list[str] = []
        parts.append(f"SAM ready: {self.sam.is_ready}")
        if self.sam.config is not None:
            parts.append(f"SAM device: {self.sam.config.device}, model: {self.sam.config.model_type}")
        parts.append(f"Busy: {self._sam_busy}")
        if msg:
            parts.append("")
            parts.append(msg)
        self.status_label.setText("\n".join(parts))

    def _message(self, title: str, text: str) -> None:
        QtWidgets.QMessageBox.information(self, title, text)

    # -------------------- Load --------------------
    def _load_volume(self, side: Side) -> None:
        fn, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            f"Load {side} NIfTI",
            str(Path.home()),
            "NIfTI (*.nii *.nii.gz)",
        )
        if not fn:
            return
        try:
            vol = load_nifti(fn)
        except Exception as e:  # noqa: BLE001
            self._message("Load failed", str(e))
            return

        st = self._get_image_state(side)
        st.volume = vol
        st.mask = np.zeros(vol.data.shape, dtype=np.uint8)
        st.boxes.clear()

        panel = self._get_panel(side)
        panel.set_volume(vol)
        panel.set_mask(st.mask)
        self._refresh_status(f"Loaded {side}: {fn}")

    # -------------------- SAM --------------------
    def _pick_checkpoint(self) -> None:
        fn, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select SAM checkpoint (.pth)",
            str(Path.home()),
            "PyTorch checkpoint (*.pth)",
        )
        if not fn:
            return
        self.state.sam_checkpoint = Path(fn)
        self.ckpt_label.setText(f"checkpoint: {fn}")
        self._refresh_status("Checkpoint selected. Click 'Load SAM'.")

    def _load_sam(self) -> None:
        if self.state.sam_checkpoint is None:
            self._message("SAM", "请先选择一个 SAM checkpoint (.pth)。")
            return
        cfg = SamConfig(
            checkpoint_path=self.state.sam_checkpoint,
            model_type=self.combo_model.currentText(),
            device=self.combo_device.currentText(),
        )
        try:
            self.sam.load(cfg)
        except Exception as e:  # noqa: BLE001
            self._message("SAM load failed", str(e))
            self._refresh_status("SAM load failed.")
            return
        self._refresh_status("SAM loaded.")

    # -------------------- Annotation workflow --------------------
    def _on_box_drawn(self, side: str, slice_idx: int, box_obj: object) -> None:
        side_t: Side = "left" if side == "left" else "right"
        box_xyxy = box_obj.as_xyxy()  # type: ignore[attr-defined]
        label = self._current_label()

        st = self._get_image_state(side_t)
        panel = self._get_panel(side_t)
        if st.volume is None:
            return

        # 获取当前显示方向
        orientation = panel.orientation

        # record bbox for json (包含方向信息)
        st.boxes.append(
            BoxAnnotation(
                side=side_t,
                slice_index=int(slice_idx),
                orientation=orientation,
                label=int(label.value),
                color=label.color_name,
                box_xyxy=tuple(map(int, box_xyxy)),
            )
        )

        if not self.sam.is_ready:
            self._refresh_status("Box recorded, but SAM not ready.")
            return
        if self._sam_busy:
            self._refresh_status("SAM busy; box recorded but not executed.")
            return

        # Prepare slice for SAM (使用当前方向)
        img2d = st.volume.get_slice(int(slice_idx), orientation)
        from ..core.image_utils import normalize_to_uint8  # local import to avoid cycles

        gray_u8 = normalize_to_uint8(img2d)
        rgb_u8 = ensure_rgb_from_gray_u8(gray_u8)
        self._run_sam(side_t, int(slice_idx), rgb_u8, tuple(map(int, box_xyxy)), label, orientation)

    def _run_sam(
        self,
        side: Side,
        slice_idx: int,
        image_rgb_u8: np.ndarray,
        box_xyxy: tuple[int, int, int, int],
        label: LabelSpec,
        orientation: ViewOrientation = ViewOrientation.AXIAL,
    ) -> None:
        self._sam_busy = True
        orient_name = orientation.value
        self._refresh_status(f"Running SAM on {side} slice {slice_idx} ({orient_name}) ...")

        thread = QtCore.QThread(self)
        job = _SamJob(self.sam, image_rgb_u8, side, slice_idx, box_xyxy)
        job.moveToThread(thread)
        thread.started.connect(job.run)

        def _done(side_s: str, slice_i: int, mask_bool: object, err: object) -> None:
            self._sam_busy = False
            try:
                if err is not None:
                    self._refresh_status(f"SAM error: {err}")
                    return

                m = mask_bool  # type: ignore[assignment]
                if m is None:
                    self._refresh_status("SAM returned empty mask.")
                    return

                st = self._get_image_state(side_s)  # type: ignore[arg-type]
                # 使用正确的方向应用mask
                st.apply_slice_mask(slice_i, np.asarray(m, dtype=bool), label.value, orientation)
                self._get_panel(side_s).set_mask(st.mask)  # type: ignore[arg-type]
                self._refresh_status(f"SAM done: {side_s} slice {slice_i} ({orient_name}), label={label.name}")
            finally:
                thread.quit()
                thread.wait()
                job.deleteLater()
                thread.deleteLater()
                self._sam_thread = None

        job.finished.connect(_done)
        self._sam_thread = thread
        thread.start()

    # -------------------- Actions --------------------
    def _clear(self, side: Side) -> None:
        st = self._get_image_state(side)
        if st.volume is None:
            return
        st.mask = np.zeros(st.volume.data.shape, dtype=np.uint8)
        st.boxes.clear()
        self._get_panel(side).set_mask(st.mask)
        self._refresh_status(f"Cleared {side}.")

    def _undo(self, side: Side) -> None:
        st = self._get_image_state(side)
        if st.volume is None or st.mask is None:
            return
        if not st.boxes:
            self._refresh_status(f"No boxes to undo on {side}.")
            return

        # MVP: only remove the last bbox record; mask rollback would require storing per-action deltas.
        st.boxes.pop()
        self._refresh_status(f"Removed last box record on {side} (mask unchanged).")

    def _save_all(self) -> None:
        out_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Choose output directory", str(Path.home())
        )
        if not out_dir:
            return
        out_p = Path(out_dir)
        out_p.mkdir(parents=True, exist_ok=True)

        saved_any = False
        for side in ("left", "right"):
            st = self._get_image_state(side)  # type: ignore[arg-type]
            if st.volume is None:
                continue
            st.ensure_mask()
            assert st.mask is not None

            # 获取原始文件名（不含路径和扩展名）
            original_name = st.volume.path.stem
            # 移除可能的 .nii 后缀（如果原始文件是 .nii.gz，stem 会包含 .nii）
            if original_name.endswith('.nii'):
                original_name = original_name[:-4]
            
            # 添加前缀：左边加 "l"，右边加 "r"
            prefix = "l" if side == "left" else "r"
            base_name = f"{prefix}{original_name}"

            mask_path = out_p / f"{base_name}_mask.nii.gz"
            save_mask_nifti(mask_path, st.mask, reference=st.volume)

            boxes_path = out_p / f"{base_name}_boxes.json"
            # Convert BoxAnnotation to dict, handling Enum serialization
            payload = []
            for b in st.boxes:
                d = asdict(b)
                # Convert ViewOrientation enum to string value for JSON
                if isinstance(d.get("orientation"), ViewOrientation):
                    d["orientation"] = d["orientation"].value
                payload.append(d)
            boxes_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            saved_any = True

        if not saved_any:
            self._message("Save", "没有可保存的图像（请先加载 left/right）。")
            return
        self._refresh_status(f"Saved outputs to: {out_p}")

