"""
Trình căn chỉnh camera 3 bước (mặc định; chấm 4 điểm nằm ở "Căn chỉnh nâng cao" = dialogs/calibration.py).

  1. Xe và số đo: chọn loại xe (điền sẵn số đo điển hình) hoặc nhập chiều cao camera + khoảng cách tới đầu xe.
  2. Đường chân trời: app tự tìm điểm tụ của vạch kẻ đường (autocalib.estimate_vanishing_point) và vẽ đường
     chân trời + tâm ngắm; người dùng chỉ kiểm tra, kéo trên ảnh nếu lệch. Video: nhập tốc độ in trên hình (nếu có).
  3. Hoàn tất: khi chạy, app tự hoàn thiện căn chỉnh (adas/distance/online_calib.py) và báo kết quả tự kiểm tra.

Kết quả là CalibrationConfig sinh từ tư thế (camera_model.calib_from_pose) nên IPM, CSDL không đổi cách tính.
"""

import copy
import math
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np
from PySide6.QtCore import QPointF, Qt, QThread, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDoubleSpinBox, QFormLayout, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
)

from adas.config import CalibrationConfig, CameraPose
from adas.distance.autocalib import estimate_vanishing_point
from adas.distance.camera_model import (
    LANE_WIDTH_M, VEHICLE_PRESETS, PoseCamera, calib_from_pose, focal_px, pose_from_calib,
)
from adas.formatting import vn
from gui.rendering import bgr_to_qimage, font
from gui.styles import C
from gui.widgets import ImageView, fit_to_screen, muted, repolish, set_icon

VEHICLE_ICONS = {"car": "directions_car_outlined", "suv": "directions_car_outlined",
                 "bus": "local_shipping_outlined", "truck": "local_shipping_outlined"}
STEP_TITLES = ["Xe và số đo", "Đường chân trời", "Hoàn tất"]


class _VanishingThread(QThread):
    """Tìm điểm tụ từ ~3 s video quanh khung đang xem (hoặc chỉ khung đó nếu là camera trực tiếp)."""
    done = Signal(object)          # (u, v) pixel hoặc None

    def __init__(self, frame: np.ndarray, video_path: Optional[str], start_frame: int):
        super().__init__()
        self.frame, self.video_path, self.start_frame = frame, video_path, start_frame

    def run(self):
        frames: List[np.ndarray] = [self.frame]
        if self.video_path:
            cap = cv2.VideoCapture(self.video_path)
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(self.start_frame, 0))
            for i in range(90):
                ok, fr = cap.read()
                if not ok:
                    break
                if i % 3 == 0 and fr.shape == self.frame.shape:
                    frames.append(fr)
            cap.release()
        try:
            self.done.emit(estimate_vanishing_point(frames))
        except Exception:
            self.done.emit(None)


class HorizonView(ImageView):
    """Ảnh khung hình + đường chân trời, tâm ngắm và vạch khoảng cách theo tư thế; kéo để chỉnh điểm tụ."""

    def __init__(self, on_change, parent=None):
        super().__init__("Chưa có khung hình", parent)
        self.on_change = on_change
        self.pose: Optional[CameraPose] = None
        self.frame_size = (1, 1)
        self.vfov = 55.0
        self._drag: Optional[QPointF] = None
        self.setMinimumSize(560, 315)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setToolTip("Kéo trên ảnh để dời đường chân trời (lên/xuống) và tâm ngắm (trái/phải).\n"
                        "Phím mũi tên: dời từng điểm ảnh.")

    def set_pose(self, pose: CameraPose, frame_size, vfov: float):
        self.pose, self.frame_size, self.vfov = pose, frame_size, vfov
        self.update()

    def _move(self, dx_px: float, dy_px: float):
        w, h = self.frame_size
        self.pose.vp_x = float(np.clip(self.pose.vp_x + dx_px / w, 0.2, 0.8))
        self.pose.vp_y = float(np.clip(self.pose.vp_y + dy_px / h, 0.15, 0.8))
        self.update()
        self.on_change()

    def mousePressEvent(self, e):
        self._drag = e.position()

    def mouseMoveEvent(self, e):
        r = self.image_rect()
        if self._drag is None or r.isEmpty() or self.pose is None:
            return
        d = e.position() - self._drag
        self._drag = e.position()
        scale = self.frame_size[0] / r.width()
        self._move(d.x() * scale, d.y() * scale)

    def mouseReleaseEvent(self, _):
        self._drag = None

    def keyPressEvent(self, e):
        step = {Qt.Key.Key_Left: (-1, 0), Qt.Key.Key_Right: (1, 0), Qt.Key.Key_Up: (0, -1), Qt.Key.Key_Down: (0, 1)}
        if self.pose is not None and e.key() in step:
            self._move(*step[e.key()])
        else:
            super().keyPressEvent(e)

    def paint_extra(self, p: QPainter):
        if self.pose is None:
            return
        r = self.image_rect()
        w, h = self.frame_size
        s = r.width() / w

        def to_w(u, v) -> QPointF:
            return QPointF(r.x() + u * s, r.y() + v * s)

        cam = PoseCamera(self.pose, self.frame_size, self.vfov)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # hành lang 1 làn (±1,875 m) và vạch khoảng cách: phải nằm trên mặt đường, song song vạch kẻ
        lane = QPen(QColor(255, 255, 255, 150), 1.4, Qt.PenStyle.DashLine)
        p.setPen(lane)
        for x in (-LANE_WIDTH_M / 2, LANE_WIDTH_M / 2):
            pts = [cam.ground_to_image(x, y) for y in (2.0, 120.0)]
            p.drawLine(to_w(*pts[0]), to_w(*pts[1]))
        p.setFont(font(10, 600))
        last_y = float("inf")
        for d in (10, 20, 30, 50):
            a, b = cam.ground_to_image(-LANE_WIDTH_M / 2, d), cam.ground_to_image(LANE_WIDTH_M / 2, d)
            if not (0 <= a[1] <= h):
                continue
            p.setPen(QPen(QColor(255, 255, 255, 190), 1.4))
            p.drawLine(to_w(*a), to_w(*b))
            pos = to_w(*b)
            if last_y - pos.y() >= 14:      # gần chân trời các vạch dồn sát nhau: bỏ nhãn
                p.drawText(pos + QPointF(6, 4), f"{d} m")
                last_y = pos.y()
        # đường chân trời + trục hướng xe chạy + tâm ngắm (kiểu camera hành trình)
        (u1, v1), (u2, v2) = cam.horizon_points()
        accent = QColor(76, 158, 255)
        p.setPen(QPen(accent, 2.2))
        p.drawLine(to_w(u1, v1), to_w(u2, v2))
        u0, v0 = cam.vp
        p.setPen(QPen(accent, 1.4, Qt.PenStyle.DashLine))
        p.drawLine(to_w(u0, v0), to_w(*cam.ground_to_image(0.0, 2.0)))
        c = to_w(u0, v0)
        p.setPen(QPen(QColor(0, 0, 0, 160), 4))
        p.drawEllipse(c, 9, 9)
        p.setPen(QPen(accent, 2))
        p.drawEllipse(c, 9, 9)
        p.drawLine(c + QPointF(-18, 0), c + QPointF(-11, 0))
        p.drawLine(c + QPointF(11, 0), c + QPointF(18, 0))
        p.drawLine(c + QPointF(0, -18), c + QPointF(0, -11))
        p.setPen(QColor(220, 235, 255))
        p.drawText(to_w(u1, v1) + QPointF(8, -8), "Đường chân trời")


class CalibrationWizard(QDialog):
    """exec() == Accepted: result_calib, method ('pose'), note, auto_calib. advanced == True: mở chấm 4 điểm."""

    def __init__(self, frame: np.ndarray, calib: CalibrationConfig, parent=None, video_path: Optional[str] = None,
                 start_frame: int = 0, auto_calib: bool = True):
        super().__init__(parent)
        self.setWindowTitle("Căn chỉnh camera")
        self.frame = frame
        self.base = copy.deepcopy(calib)
        self.frame_size = (frame.shape[1], frame.shape[0])
        self.video_path = video_path if video_path and Path(video_path).is_file() else None
        self.advanced = False
        self.method, self.note = "pose", ""
        self.result_calib: Optional[CalibrationConfig] = None

        # tư thế ban đầu: tư thế đã nhập lần trước; chưa có thì số đo theo loại xe (chiều cao / đầu xe phân rã từ
        # 4 điểm chấm tay không đáng tin), chỉ giữ tiêu cự của hiệu chỉnh 4 điểm đã căn (không phải mặc định)
        self.pose = pose_from_calib(calib, self.frame_size)
        if not calib.pose.active:
            _, self.pose.height_m, self.pose.bumper_m = VEHICLE_PRESETS.get(self.pose.vehicle, VEHICLE_PRESETS["car"])
            self.pose.height_measured = False
            if calib.image_points == CalibrationConfig().image_points:
                self.pose.focal_w = 0.0
        self._had_pose = calib.pose.active
        self._vp_note = ""

        root = QVBoxLayout(self)
        root.setSpacing(12)
        self.steps = QHBoxLayout()
        self.step_labels = []
        for i, t in enumerate(STEP_TITLES):
            lab = QLabel(f"{i + 1}  {t}")
            lab.setObjectName("wizardStep")
            self.step_labels.append(lab)
            self.steps.addWidget(lab)
        self.steps.addStretch(1)
        root.addLayout(self.steps)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._page_vehicle())
        self.stack.addWidget(self._page_horizon())
        self.stack.addWidget(self._page_done(auto_calib))
        root.addWidget(self.stack, 1)

        nav = QHBoxLayout()
        adv = QPushButton("Căn chỉnh nâng cao (chấm 4 điểm)")
        adv.setObjectName("link")
        adv.setToolTip("Cách cũ: chấm 4 điểm lên vạch làn và nhập kích thước thật, hoặc quét cả video")
        adv.clicked.connect(self._advanced)
        nav.addWidget(adv)
        nav.addStretch(1)
        self.back_btn = QPushButton("Quay lại")
        self.back_btn.clicked.connect(lambda: self._go(self.stack.currentIndex() - 1))
        self.next_btn = QPushButton("Tiếp")
        self.next_btn.setObjectName("primary")
        self.next_btn.clicked.connect(self._next)
        cancel = QPushButton("Hủy")
        cancel.clicked.connect(self.reject)
        for b in (self.back_btn, cancel, self.next_btn):
            nav.addWidget(b)
        root.addLayout(nav)

        fit_to_screen(self, 1080, 680)
        self._go(0)
        self._vp_thread = _VanishingThread(frame, self.video_path, start_frame)
        self._vp_thread.done.connect(self._on_vanishing)
        self._vp_thread.start()

    # ------------------------------------------------------------------
    # Bước 1: xe và số đo
    # ------------------------------------------------------------------

    def _page_vehicle(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(10)
        title = QLabel("Camera gắn trên xe nào?")
        title.setObjectName("wizardTitle")
        lay.addWidget(title)
        lay.addWidget(muted("Chọn loại xe để điền sẵn số đo điển hình (camera gắn giữa kính lái, sau gương chiếu hậu). "
                            "Đo bằng thước thì chính xác hơn."))
        grid = QGridLayout()
        grid.setSpacing(8)
        self.vehicle_btns = {}
        for i, (key, (label, h, b)) in enumerate(VEHICLE_PRESETS.items()):
            btn = QPushButton(f"{label}\ncao {vn(h, 2)} m · tới đầu xe {vn(b, 1)} m")
            btn.setObjectName("chip")
            btn.setMinimumHeight(56)
            set_icon(btn, VEHICLE_ICONS[key], "accent", 22)
            btn.clicked.connect(lambda _=False, k=key: self._pick_vehicle(k))
            self.vehicle_btns[key] = btn
            grid.addWidget(btn, 0, i)
        lay.addLayout(grid)

        form = QFormLayout()
        form.setSpacing(10)
        self.height_spin = self._spin(self.pose.height_m, 0.5, 4.0, 2, " m")
        self.height_spin.setToolTip("Từ mặt đường lên tới ống kính camera")
        self.bumper_spin = self._spin(self.pose.bumper_m, 0.0, 5.0, 1, " m")
        self.bumper_spin.setToolTip("Từ ống kính camera tới mép trước của cản xe (khoảng cách hiển thị tính từ đầu xe)")
        form.addRow("Chiều cao camera so với mặt đường:", self.height_spin)
        form.addRow("Từ camera tới đầu xe:", self.bumper_spin)
        lay.addLayout(form)
        self.measured = QCheckBox("Tôi đã đo chiều cao bằng thước")
        self.measured.setChecked(self.pose.height_measured)
        self.measured.toggled.connect(self._measured_toggled)
        lay.addWidget(self.measured)
        self.measured_hint = muted()
        lay.addWidget(self.measured_hint)
        self.height_spin.valueChanged.connect(lambda _: self.measured.setChecked(True) if self.height_spin.hasFocus() else None)
        lay.addStretch(1)
        self._select_vehicle_chip(self.pose.vehicle)
        self._measured_toggled(self.measured.isChecked())
        return page

    def _spin(self, value, lo, hi, decimals, suffix) -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setRange(lo, hi)
        s.setDecimals(decimals)
        s.setSingleStep(10 ** -decimals * (5 if decimals == 2 else 1))
        s.setSuffix(suffix)
        s.setValue(value)
        s.setMaximumWidth(160)
        return s

    def _pick_vehicle(self, key: str):
        _, h, b = VEHICLE_PRESETS[key]
        self.pose.vehicle = key
        self.height_spin.setValue(h)
        self.bumper_spin.setValue(b)
        self.measured.setChecked(False)
        self._select_vehicle_chip(key)

    def _select_vehicle_chip(self, key: str):
        for k, btn in self.vehicle_btns.items():
            btn.setProperty("selected", k == key)
            repolish(btn)

    def _measured_toggled(self, on: bool):
        self.measured_hint.setText(
            "Giữ đúng chiều cao này; khi chạy app báo bề rộng làn đo được để bạn tự kiểm tra." if on else
            "Không đo cũng được: khi chạy, app tự ước lượng chiều cao theo bề rộng làn cao tốc 3,75 m.")

    # ------------------------------------------------------------------
    # Bước 2: đường chân trời
    # ------------------------------------------------------------------

    def _page_horizon(self) -> QWidget:
        page = QWidget()
        lay = QHBoxLayout(page)
        lay.setSpacing(14)
        self.view = HorizonView(self._horizon_changed)
        self.view.set_image(bgr_to_qimage(self.frame))
        lay.addWidget(self.view, 3)

        side = QVBoxLayout()
        side.setSpacing(10)
        title = QLabel("Kiểm tra đường chân trời")
        title.setObjectName("wizardTitle")
        side.addWidget(title)
        side.addWidget(muted("Đường xanh nằm ngang phải trùng chân trời (nơi mặt đường phẳng phía xa gặp bầu trời), "
                             "tâm ngắm chỉ đúng hướng đường chạy, hai nét đứt trắng song song với vạch làn."))
        side.addWidget(muted("Thấy hợp lý thì bấm Tiếp. Lệch thì kéo trên ảnh."))
        self.vp_status = QLabel("Đang tự tìm đường chân trời từ vạch kẻ đường…")
        self.vp_status.setWordWrap(True)
        side.addWidget(self.vp_status)
        redo = QPushButton("Tìm lại tự động")
        set_icon(redo, "auto_fix_high_outlined", "accent")
        redo.clicked.connect(self._redo_vanishing)
        self.redo_btn = redo
        side.addWidget(redo, 0, Qt.AlignmentFlag.AlignLeft)

        form = QFormLayout()
        self.hfov_spin = QDoubleSpinBox()
        self.hfov_spin.setRange(30, 150)
        self.hfov_spin.setDecimals(0)
        self.hfov_spin.setSuffix(" °")
        self.hfov_spin.setMaximumWidth(140)
        self.hfov_spin.setToolTip("Góc nhìn ngang của ống kính. Chỉ là giá trị ban đầu: có tốc độ thật (GPS, "
                                  "hoặc số nhập khi video chạy) thì app tự đo thông số này.")
        self.hfov_spin.valueChanged.connect(self._hfov_changed)
        form.addRow("Góc nhìn ngang camera:", self.hfov_spin)
        side.addLayout(form)
        side.addWidget(muted(
            "Video camera hành trình: không cần dừng để nhập gì ở đây. Khi video chạy, thanh phía trên video có ô "
            "\"Tốc độ trên video\" - gõ số km/h đang in trên hình (vd: 74KM/H) để app đo thang khoảng cách."
            if self.video_path is not None else
            "Camera trực tiếp: khoảng cách xa dựa trên góc nhìn camera ở trên."))
        side.addStretch(1)
        lay.addLayout(side, 2)
        return page

    def _on_vanishing(self, vp):
        if self._had_pose:
            self._vp_note = "Đang dùng đường chân trời đã căn chỉnh trước đó."
        elif vp is not None:
            self.pose.vp_x, self.pose.vp_y = vp[0] / self.frame_size[0], vp[1] / self.frame_size[1]
            self._vp_note = "Đã tự tìm thấy đường chân trời từ vạch kẻ đường."
        else:
            self._vp_note = "Không thấy rõ vạch kẻ đường: hãy kéo đường chân trời bằng tay."
        self._had_pose = False             # "Tìm lại tự động" lần sau thì dùng kết quả dò
        self.vp_status.setText(self._vp_note)
        self.redo_btn.setEnabled(True)
        self._refresh_view()

    def _redo_vanishing(self):
        self.redo_btn.setEnabled(False)
        self.vp_status.setText("Đang tự tìm đường chân trời từ vạch kẻ đường…")
        self._vp_thread.start()

    def _horizon_changed(self):
        self.vp_status.setText("Đã chỉnh tay đường chân trời.")

    def _hfov_changed(self, deg: float):
        if self.hfov_spin.hasFocus():
            self.pose.focal_w = 0.5 / math.tan(math.radians(deg) / 2)
            self.pose.focal_source = "fov"
            self._refresh_view()

    def _refresh_view(self):
        self._sync_pose()
        f = focal_px(self.pose, self.frame_size, self.base.camera_vfov_deg)
        self.hfov_spin.blockSignals(True)
        self.hfov_spin.setValue(math.degrees(2 * math.atan(self.frame_size[0] / 2 / f)))
        self.hfov_spin.blockSignals(False)
        self.hfov_spin.setEnabled(self.pose.focal_source != "camera")
        self.view.set_pose(self.pose, self.frame_size, self.base.camera_vfov_deg)

    # ------------------------------------------------------------------
    # Bước 3: hoàn tất
    # ------------------------------------------------------------------

    def _page_done(self, auto_calib: bool) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(10)
        title = QLabel("Xong. App sẽ tự hoàn thiện khi chạy")
        title.setObjectName("wizardTitle")
        lay.addWidget(title)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(self.summary)
        lay.addWidget(muted(
            "Khi bấm Bắt đầu, phía trên video hiện thanh \"Đang tự hoàn thiện căn chỉnh 0-100 %\". "
            "Cần khoảng 5-10 giây chạy thấy rõ 2 vạch làn. Xong sẽ báo kết quả tự kiểm tra, "
            "ví dụ \"Làn đo được 3,72 m - đạt\". Nếu sau đó camera bị xê dịch, app tự phát hiện và căn chỉnh lại."))
        self.auto_calib = QCheckBox("Tự hoàn thiện căn chỉnh và theo dõi camera bị xê dịch khi chạy")
        self.auto_calib.setChecked(auto_calib)
        lay.addWidget(self.auto_calib)
        lay.addStretch(1)
        return page

    def _summary_html(self) -> str:
        p = self.pose
        label = VEHICLE_PRESETS.get(p.vehicle, ("Khác",))[0]
        rows = [
            ("Loại xe", label),
            ("Chiều cao camera", f"{vn(p.height_m, 2)} m " + ("(đã đo)" if p.height_measured
                                                             else "(ước lượng, tự chỉnh theo làn 3,75 m khi chạy)")),
            ("Camera tới đầu xe", f"{vn(p.bumper_m, 1)} m"),
            ("Đường chân trời", f"hàng {p.vp_y * self.frame_size[1]:.0f}/{self.frame_size[1]} của ảnh"),
            ("Thang khoảng cách", "đã đo theo tốc độ thật trước đó" if p.focal_source in ("speed", "gps")
             else "theo góc nhìn camera" if self.video_path is None
             else f"<span style='color:{C['accent']}'>khi video chạy, gõ số km/h đang in trên hình vào ô "
                  f"\"Tốc độ trên video\" phía trên video (không cần dừng)</span>"),
        ]
        return "<table cellspacing='6'>" + "".join(
            f"<tr><td style='color:#a3aebb'>{k}</td><td><b>{v}</b></td></tr>" for k, v in rows) + "</table>"

    # ------------------------------------------------------------------

    def _sync_pose(self):
        p = self.pose
        p.height_m = self.height_spin.value()
        p.bumper_m = self.bumper_spin.value()
        p.height_measured = self.measured.isChecked()
        p.ref_speed_kmh = 0.0              # tốc độ giờ nhập lúc video chạy (online_calib.add_reference)
        p.refined = False

    def _go(self, i: int):
        if not 0 <= i < self.stack.count():
            return
        self._sync_pose()
        if i == 1:
            self._refresh_view()
            self.view.setFocus()
        if i == 2:
            self.summary.setText(self._summary_html())
        self.stack.setCurrentIndex(i)
        for k, lab in enumerate(self.step_labels):
            lab.setProperty("state", "current" if k == i else "done" if k < i else "todo")
            repolish(lab)
        self.back_btn.setEnabled(i > 0)
        self.next_btn.setText("Áp dụng" if i == 2 else "Tiếp")

    def _next(self):
        i = self.stack.currentIndex()
        if i < 2:
            self._go(i + 1)
            return
        self._sync_pose()
        try:
            self.result_calib = calib_from_pose(self.pose, self.frame_size, self.base)
        except ValueError as e:
            self.summary.setText(f"<span style='color:#ff4d4f'>{e}</span><br><br>" + self._summary_html())
            return
        p = self.pose
        self.note = (f"Chiều cao {vn(p.height_m, 2)} m ({'đo' if p.height_measured else 'ước lượng'}), "
                     f"tới đầu xe {vn(p.bumper_m, 1)} m, chân trời hàng {p.vp_y * self.frame_size[1]:.0f}")
        self.accept()

    def _advanced(self):
        self.advanced = True
        self.reject()

    def done(self, r):
        if self._vp_thread.isRunning():
            self._vp_thread.wait(3000)
        super().done(r)
