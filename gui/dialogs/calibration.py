"""
Hộp thoại "Căn chỉnh camera" (hiệu chỉnh IPM).

Người dùng đặt 4 điểm lên ảnh tạo thành một hình chữ nhật trên mặt đường
(thường là 2 vạch kẻ làn + 2 mốc dọc đường) và nhập kích thước thực.
Ảnh "nhìn từ trên xuống" (Bird's-Eye View) xem trước giúp kiểm tra: căn đúng khi
các vạch kẻ làn trở nên song song và thẳng đứng.
"""

import copy
from pathlib import Path
from typing import Optional

import numpy as np
from PySide6.QtCore import QPointF, Qt, QThread, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QFrame, QGroupBox, QHBoxLayout,
    QInputDialog, QLabel, QMessageBox, QProgressDialog, QPushButton, QScrollArea, QVBoxLayout,
    QWidget,
)

from adas.config import CalibrationConfig
from adas.distance.autocalib import auto_calibrate
from adas.distance.ipm import GroundPlaneMapper
from adas.stream.sources import IMAGE_EXTS
from gui.rendering import bgr_to_qimage, font, icon
from gui.widgets import ImageView, fit_to_screen

POINT_NAMES = ["1 · Gần, trái", "2 · Gần, phải", "3 · Xa, phải", "4 · Xa, trái"]


class _AutoCalibThread(QThread):
    progress = Signal(int, str)
    done = Signal(object, object)
    failed = Signal(str)

    def __init__(self, video, speed, base, lane_w, offset):
        super().__init__()
        self.args = (video, speed, base, lane_w, offset)

    def run(self):
        video, speed, base, lane_w, offset = self.args
        try:
            calib, rep = auto_calibrate(video, speed, base, lane_width_m=lane_w,
                                        bumper_offset_m=offset,
                                        progress=lambda p, m: self.progress.emit(p, m))
            self.done.emit(calib, rep)
        except Exception as e:
            self.failed.emit(str(e))


class CalibrationView(ImageView):
    def __init__(self, calib: CalibrationConfig, on_change, parent=None):
        super().__init__("Chưa có khung hình", parent)
        self.points = [list(p) for p in calib.image_points]  # tỷ lệ 0..1
        self.on_change = on_change
        self._drag = None
        self.setMouseTracking(True)
        self.setMinimumSize(480, 270)

    def _to_widget(self, pt) -> QPointF:
        r = self.image_rect()
        return QPointF(r.x() + pt[0] * r.width(), r.y() + pt[1] * r.height())

    def _to_ratio(self, pos: QPointF):
        r = self.image_rect()
        x = min(max((pos.x() - r.x()) / r.width(), 0.0), 1.0)
        y = min(max((pos.y() - r.y()) / r.height(), 0.0), 1.0)
        return [x, y]

    def mousePressEvent(self, e):
        if self.image_rect().isEmpty():
            return
        pos = e.position()
        dists = [(QPointF(self._to_widget(p) - pos).manhattanLength(), i) for i, p in enumerate(self.points)]
        d, i = min(dists) if dists else (1e9, -1)
        if d < 24:
            self._drag = i
        elif len(self.points) < 4:
            self.points.append(self._to_ratio(pos))
            self._drag = len(self.points) - 1
            self._changed()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.points[self._drag] = self._to_ratio(e.position())
            self._changed()

    def mouseReleaseEvent(self, _):
        self._drag = None

    def clear_points(self):
        self.points = []
        self._changed()

    def _changed(self):
        self.update()
        self.on_change()

    def paint_extra(self, p: QPainter):
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pts = [self._to_widget(pt) for pt in self.points]
        if len(pts) >= 2:
            fill = QColor(0, 200, 255, 50)
            p.setBrush(fill if len(pts) == 4 else Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(0, 220, 255), 2))
            poly = QPolygonF(pts)
            p.drawPolygon(poly) if len(pts) == 4 else p.drawPolyline(poly)
        f = font(13, 700)
        p.setFont(f)
        fm = p.fontMetrics()
        for i, pt in enumerate(pts):
            p.setBrush(QColor(255, 210, 0))
            p.setPen(QPen(QColor(0, 0, 0), 1.5))
            p.drawEllipse(pt, 7, 7)
            p.setPen(QColor(255, 230, 80))
            name = POINT_NAMES[i]
            # Điểm bên trái (1, 4) ghi nhãn bên trái để hai nhãn phía trên không chồng nhau
            dx = -(fm.horizontalAdvance(name) + 10) if i in (0, 3) else 10
            p.drawText(pt + QPointF(dx, -8), name)


class CalibrationDialog(QDialog):
    def __init__(self, frame: np.ndarray, calib: CalibrationConfig, parent=None,
                 video_path: Optional[str] = None, speed_kmh: float = 80.0):
        super().__init__(parent)
        self.setWindowTitle("Căn chỉnh camera để đo khoảng cách")
        self.frame = frame
        self.calib = copy.deepcopy(calib)
        self.video_path = video_path if video_path and Path(video_path).is_file() \
            and Path(video_path).suffix.lower() not in IMAGE_EXTS else None
        self.speed_kmh = speed_kmh
        self._auto_summary = ""
        self.method = "manual"   # 'auto' khi dùng Tự động từ video (lưu vào camera_calibrations.method)
        self.note = ""
        self._auto_thread = None

        outer = QVBoxLayout(self)
        root = QHBoxLayout()
        outer.addLayout(root, 1)
        left = QVBoxLayout()
        guide = QLabel(
            "<b>Cách làm:</b> Nếu đang mở video, bấm <b>Tự động căn chỉnh</b> là xong. "
            "Nếu muốn tự làm: chấm 4 điểm lên <b>2 vạch kẻ của làn xe mình đang chạy</b> theo thứ tự "
            "<b>gần-trái, gần-phải, xa-phải, xa-trái</b>, rồi nhập số đo thực tế ở bên phải. "
            "Căn đúng khi ở ô <b>Nhìn từ trên xuống</b>, hai vạch làn <b>song song và thẳng đứng</b>.")
        guide.setWordWrap(True)
        left.addWidget(guide)
        self.view = CalibrationView(self.calib, self._manual_change)
        self.view.set_image(bgr_to_qimage(frame))
        left.addWidget(self.view, 1)
        btns = QHBoxLayout()
        auto = QPushButton("Tự động căn chỉnh")
        auto.setObjectName("primary")
        auto.setIcon(icon("auto_fix_high_outlined", "on_accent", 18))
        auto.setToolTip("Phần mềm tự dò vạch kẻ đường trong video để tính vị trí, độ cao và góc camera")
        auto.setEnabled(self.video_path is not None)
        if self.video_path is None:
            auto.setToolTip("Chỉ dùng được khi đang mở file video (không dùng cho ảnh hoặc camera trực tiếp)")
        auto.clicked.connect(self._auto_calibrate)
        btns.addWidget(auto)
        clear = QPushButton("Chấm lại 4 điểm")
        clear.clicked.connect(self.view.clear_points)
        default = QPushButton("Về vị trí mặc định")
        default.clicked.connect(self._reset_default)
        btns.addWidget(clear)
        btns.addWidget(default)
        btns.addStretch(1)
        root.addLayout(left, 3)

        # Cột phải đặt trong vùng cuộn để không bao giờ đẩy hộp thoại cao quá màn hình
        right_widget = QWidget()
        right = QVBoxLayout(right_widget)
        right.setContentsMargins(0, 0, 6, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(right_widget)
        scroll.setMaximumWidth(480)
        box = QGroupBox("Số đo thực tế trên mặt đường")
        form = QFormLayout(box)
        cam_box = QGroupBox("Camera và vùng đo")
        cam_form = QFormLayout(cam_box)
        self.width = self._spin(self.calib.rect_width_m, 0.5, 20, " m", 2)
        self.length = self._spin(self.calib.rect_length_m, 1, 200, " m", 1)
        self.near = self._spin(self.calib.near_distance_m, 0, 50, " m", 1)
        self.lane = self._spin(self.calib.lane_half_width_m, 0.5, 5, " m", 2)
        self.max_range = self._spin(self.calib.max_range_m, 20, 300, " m", 0)
        self.vfov = self._spin(self.calib.camera_vfov_deg, 20, 120, " °", 1)
        self.offset = self._spin(2.0, 0, 5, " m", 1)
        self.width.setToolTip("Khoảng cách giữa 2 vạch kẻ hai bên làn (giữa điểm 1 và 2). Làn cao tốc Việt Nam: 3,75 m")
        self.length.setToolTip("Khoảng cách dọc đường từ 2 điểm gần (1, 2) tới 2 điểm xa (3, 4)")
        self.near.setToolTip("Khoảng cách từ đầu xe mình tới đường nối 2 điểm gần (1, 2)")
        self.lane.setToolTip("Xe phía trước lệch khỏi giữa làn không quá khoảng này (mỗi bên) "
                             "thì được coi là cùng làn với xe mình. Làn 3,75 m: khoảng 1,9 m")
        self.max_range.setToolTip("Xe ở xa hơn khoảng này chỉ được ghi là \"ở xa\", không đo chính xác")
        self.vfov.setToolTip("Góc mở theo chiều dọc của ống kính camera hành trình. "
                             "Chỉ dùng khi không đo được bằng cách khác")
        self.offset.setToolTip("Khoảng cách từ camera (gắn ở kính lái) tới đầu xe. "
                               "Dùng khi tự động căn chỉnh")
        form.addRow("Bề rộng làn đường:", self.width)
        form.addRow("Chiều dài đoạn đã chấm:", self.length)
        form.addRow("Từ đầu xe tới 2 điểm gần:", self.near)
        cam_form.addRow("Phạm vi làn xe mình (mỗi bên):", self.lane)
        cam_form.addRow("Đo xa tối đa:", self.max_range)
        cam_form.addRow("Góc nhìn dọc của camera:", self.vfov)
        cam_form.addRow("Từ camera tới đầu xe:", self.offset)
        hint = QLabel("Làn đường cao tốc Việt Nam rộng 3,75 m. Với video, nên dùng <b>Tự động căn chỉnh</b>: "
                      "phần mềm đo độ xa dựa vào tốc độ xe và chuyển động của vạch kẻ đứt, "
                      "chính xác hơn tự ước lượng chiều dài.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        form.addRow(hint)
        right.addWidget(box)
        right.addWidget(cam_box)

        prev = QGroupBox("Xem trước: nhìn từ trên xuống")
        pl = QVBoxLayout(prev)
        self.bev = ImageView("Cần đủ 4 điểm")
        self.bev.setMinimumSize(160, 300)
        pl.addWidget(self.bev)
        self.info = QLabel()
        self.info.setObjectName("muted")
        self.info.setWordWrap(True)
        pl.addWidget(self.info)
        right.addWidget(prev, 1)
        # đủ rộng cho nhãn + ô số (không cắt mép khi không có thanh cuộn ngang)
        scroll.setMinimumWidth(min(right_widget.minimumSizeHint().width() + 16, 480))
        root.addWidget(scroll, 1)

        # Hàng nút cố định ở đáy hộp thoại: luôn nhìn thấy "Áp dụng" / "Hủy"
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setObjectName("primary")
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("Áp dụng")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Hủy")
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        self.ok_btn = bb.button(QDialogButtonBox.StandardButton.Ok)
        btns.addWidget(bb)
        outer.addLayout(btns)

        for s in (self.width, self.length, self.near, self.lane, self.max_range):
            s.valueChanged.connect(self._manual_change)
        fit_to_screen(self, 1280, 720)
        self._update_preview()

    def _spin(self, value, lo, hi, suffix, decimals):
        s = QDoubleSpinBox()
        s.setRange(lo, hi)
        s.setDecimals(decimals)
        s.setSuffix(suffix)
        s.setValue(value)
        return s

    def _reset_default(self):
        self.view.points = [list(p) for p in CalibrationConfig().image_points]
        self.view.update()
        self._update_preview()

    def _collect(self) -> CalibrationConfig:
        c = self.calib
        c.image_points = [list(map(float, p)) for p in self.view.points]
        c.rect_width_m = self.width.value()
        c.rect_length_m = self.length.value()
        c.near_distance_m = self.near.value()
        c.lane_half_width_m = self.lane.value()
        c.max_range_m = self.max_range.value()
        c.camera_vfov_deg = self.vfov.value()
        return c

    def _update_preview(self):
        ok = len(self.view.points) == 4
        self.ok_btn.setEnabled(ok)
        if not ok:
            self.bev.set_image(None)
            self.info.setText(f"Đã chọn {len(self.view.points)}/4 điểm.")
            return
        c = self._collect()
        h, w = self.frame.shape[:2]
        try:
            mapper = GroundPlaneMapper(c, (w, h))
        except Exception as e:
            self.info.setText(f"Điểm không hợp lệ: {e}")
            self.bev.set_image(None)
            return
        y_max = min(c.max_range_m, max(60.0, c.near_distance_m + c.rect_length_m * 2.5))
        bev = mapper.warp_to_bev(self.frame, (300, 600), 8.0, 0.0, y_max)
        img = bgr_to_qimage(bev)
        p = QPainter(img)
        M = mapper.bev_matrix((300, 600), 8.0, 0.0, y_max)
        p.setPen(QPen(QColor(0, 220, 255), 2))
        pts = [M @ np.array([x, y, 1.0]) for x, y in mapper.dst_m]
        p.drawPolygon(QPolygonF([QPointF(v[0], v[1]) for v in pts]))
        p.setPen(QColor(255, 255, 255, 160))
        for d in range(10, int(y_max) + 1, 10):
            v = M @ np.array([-8.0, d, 1.0])
            p.drawText(QPointF(4, v[1] - 2), f"{d} m")
        p.end()
        self.bev.set_image(img)
        horizon = mapper.horizon_y
        text = (f"Khung xanh = đoạn đường đã chấm ({c.rect_width_m:.2f} m × {c.rect_length_m:.1f} m). "
                f"Đường chân trời ở hàng {horizon:.0f}/{h} của ảnh." if horizon is not None else "")
        m = mapper.model
        if m["focal_px"]:
            text += (f"<br><b>Camera ước tính:</b> cao {m['camera_height_m']:.2f} m so với mặt đường · "
                     f"chúc xuống {m['pitch_deg']:.1f}° · cách đầu xe {m['camera_offset_m']:.1f} m · "
                     f"tiêu cự {m['focal_px']:.0f} điểm ảnh")
        if self._auto_summary:
            text = self._auto_summary.replace("\n", "<br>") + "<br><br>" + text
        self.info.setText(text)

    def _manual_change(self):
        """Người dùng tự kéo điểm / sửa số -> lần căn chỉnh được ghi nhận là thủ công."""
        self.method, self.note, self._auto_summary = "manual", "", ""
        self._update_preview()

    # ------------------------------------------------------------------
    # Tự động hiệu chỉnh
    # ------------------------------------------------------------------

    def _auto_calibrate(self):
        speed, ok = QInputDialog.getDouble(
            self, "Tự động căn chỉnh",
            "Tốc độ trung bình của xe trong video (km/h)\n"
            "- thường có ghi trên video camera hành trình (vd: 72KM/H).\n"
            "Nhập 0 nếu không biết (khi đó phần mềm dùng góc nhìn dọc của camera đã nhập).",
            self.speed_kmh, 0, 200, 0)
        if not ok:
            return
        prog = QProgressDialog("Đang phân tích video…", None, 0, 100, self)
        prog.setWindowTitle("Tự động căn chỉnh")
        prog.setWindowModality(Qt.WindowModality.WindowModal)
        prog.setMinimumDuration(0)
        prog.setValue(0)
        base = self._collect() if len(self.view.points) == 4 else copy.deepcopy(self.calib)
        th = _AutoCalibThread(self.video_path, speed or None, base, self.width.value(), self.offset.value())
        th.progress.connect(lambda p, m: (prog.setValue(p), prog.setLabelText(m)))
        th.done.connect(lambda c, r: (prog.close(), self._apply_auto(c, r)))
        th.failed.connect(lambda msg: (prog.close(), QMessageBox.warning(
            self, "Tự động căn chỉnh", f"Không tự căn chỉnh được: {msg}\nHãy tự chấm 4 điểm.")))
        self._auto_thread = th
        th.start()

    def _apply_auto(self, calib: CalibrationConfig, rep):
        self.view.points = [list(p) for p in calib.image_points]
        for spin, val in ((self.width, calib.rect_width_m), (self.length, calib.rect_length_m),
                          (self.near, calib.near_distance_m), (self.vfov, calib.camera_vfov_deg)):
            spin.blockSignals(True)
            spin.setValue(val)
            spin.blockSignals(False)
        self.method, self.note = "auto", rep.summary()
        self._auto_summary = "<b>Kết quả tự động căn chỉnh:</b>\n" + rep.summary()
        if not rep.depth_from_motion:
            self._auto_summary += "\nLưu ý: không đo được độ xa từ chuyển động của vạch kẻ - khoảng cách có thể sai lệch."
        self.view.update()
        self._update_preview()

    def _accept(self):
        self.result_calib = self._collect()
        self.accept()
