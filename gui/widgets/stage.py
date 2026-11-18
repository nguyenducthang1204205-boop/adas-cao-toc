"""Vùng video: màn hình chào 3 bước, khung video + BEV, thanh điều khiển phát."""

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QToolButton, QVBoxLayout, QWidget,
)

from gui.styles import C
from gui.theme import FONT_FAMILY, ICON_FAMILY, icon_char
from gui.widgets.common import ImageView, icon_html, muted, repolish, set_icon


class WelcomePanel(QFrame):
    """Hướng dẫn 3 bước hiển thị trên khung video khi chưa giám sát."""
    open_video = Signal()
    open_camera = Signal()
    open_image = Signal()
    open_sources = Signal()
    calibrate = Signal()
    start = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("welcome")
        outer = QVBoxLayout(self)
        outer.addStretch(1)
        box = QVBoxLayout()
        box.setSpacing(10)
        title = QLabel("Bắt đầu giám sát khoảng cách")
        title.setObjectName("welcomeTitle")
        box.addWidget(title)
        box.addWidget(muted("Làm theo 3 bước dưới đây. Lần sau mở lại cùng nguồn, bước 2 được nhớ sẵn."))

        self.steps = []
        b_video = self._btn("Mở video", self.open_video, primary=True, icon_name="folder_open_outlined")
        b_cam = self._btn("Camera", self.open_camera, icon_name="videocam_outlined")
        b_img = self._btn("Ảnh", self.open_image, icon_name="image_outlined")
        b_list = self._btn("Danh sách nguồn", self.open_sources, icon_name="folder_copy_outlined")
        self.step_source = self._step(1, "Chọn nguồn video", "Video hành trình, camera USB/IP hoặc một ảnh",
                                      [b_video, b_cam, b_img, b_list])
        self.step_calib = self._step(2, "Căn chỉnh camera",
                                     "Làm một lần cho mỗi camera để khoảng cách đo được chính xác",
                                     [self._btn("Căn chỉnh camera", self.calibrate, icon_name="straighten_outlined")])
        self.btn_start = self._btn("Bắt đầu giám sát", self.start, primary=True, icon_name="play_arrow_rounded")
        self.step_start = self._step(3, "Bắt đầu", "Phím tắt: F5 bắt đầu · Space tạm dừng · Esc dừng",
                                     [self.btn_start])
        for s in (self.step_source, self.step_calib, self.step_start):
            box.addWidget(s)

        row = QHBoxLayout()
        row.addStretch(1)
        row.addLayout(box, 0)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)

    def _btn(self, text, signal, primary=False, icon_name=None):
        b = QPushButton(text)
        if icon_name:
            set_icon(b, icon_name, "on_accent" if primary else "text")
        if primary:
            b.setObjectName("primary")
        b.clicked.connect(signal.emit)
        return b

    def _step(self, n, title, desc, buttons):
        f = QFrame()
        f.setObjectName("step")
        f.setMinimumWidth(520)
        lay = QHBoxLayout(f)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(12)
        num = QLabel(str(n))
        num.setObjectName("stepNum")
        num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(num, 0, Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(4)
        t = QLabel(f"<b>{title}</b>")
        d = muted(desc)
        col.addWidget(t)
        col.addWidget(d)
        brow = QHBoxLayout()
        brow.setSpacing(6)
        for b in buttons:
            brow.addWidget(b)
        brow.addStretch(1)
        col.addLayout(brow)
        lay.addLayout(col, 1)
        f.n, f.num, f.desc, f.default_desc = n, num, d, desc
        self.steps.append(f)
        return f

    @staticmethod
    def _set_done(step, done: bool, desc: Optional[str] = None):
        step.setProperty("done", done)
        step.num.setProperty("done", done)
        f = step.num.font()
        f.setFamily(ICON_FAMILY if done else FONT_FAMILY)
        step.num.setFont(f)
        step.num.setText(icon_char("check_rounded") if done else str(step.n))
        step.desc.setText(desc or step.default_desc)
        repolish(step)
        repolish(step.num)

    def set_state(self, source: Optional[str], calibrated: Optional[bool], calib_desc: str = ""):
        """source: tên nguồn đã chọn (None = chưa); calibrated: None = chưa biết (chưa chọn nguồn)."""
        self._set_done(self.step_source, bool(source), f"Đã chọn: {source}" if source else None)
        self._set_done(self.step_calib, bool(calibrated), calib_desc or None)
        if source and calibrated is False:
            self.step_calib.desc.setText(f"{icon_html('error_outline_rounded', 'warning')} "
                                         "Nguồn này chưa được căn chỉnh - khoảng cách chỉ là ước lượng")


class VideoStage(QWidget):
    """
    Khung video + Bird's-Eye View. Khi khung đủ rộng, BEV nằm cạnh video (không che);
    khi hẹp, BEV thu nhỏ thành ô nổi ở góc dưới bên phải. Chưa chạy thì hiện hướng dẫn.
    """
    BEV_ASPECT = 300 / 620      # rộng / cao của ảnh BEV (gui.rendering.render_bev)
    GAP = 8

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(480, 300)
        self.video = ImageView("", self)
        self.bev = ImageView("Nhìn từ trên xuống", self)
        self.bev.setToolTip("Nhìn từ trên xuống (Bird's-Eye View): vị trí các xe trên mặt đường, "
                            "vạch vàng = ngưỡng cảnh báo, vạch đỏ = ngưỡng nguy hiểm")
        self.bev.setMinimumSize(60, 120)
        self.welcome = WelcomePanel(self)
        self.bev_btn = QToolButton(self)
        self.bev_btn.setText("Nhìn từ trên")
        self.bev_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        set_icon(self.bev_btn, "map_outlined", "text", 16)
        self.bev_btn.setCheckable(True)
        self.bev_btn.setChecked(True)
        self.bev_btn.setToolTip("Hiện/ẩn góc nhìn từ trên xuống")
        self.bev_btn.setStyleSheet("QToolButton { background: rgba(12,17,23,214); border: 1px solid "
                                   f"{C['border']}; border-radius: 14px; padding: 6px 12px; }}"
                                   f"QToolButton:checked {{ background: {C['accent_soft']}; "
                                   f"border-color: {C['accent']}; }}")
        self.bev_btn.toggled.connect(lambda _: self._layout())
        self._video_aspect = 16 / 9
        self.welcome_on = True
        self.show_welcome(True)

    def show_welcome(self, on: bool):
        self.welcome_on = on
        self.welcome.setVisible(on)
        self.video.setVisible(not on)
        self._layout()

    def set_message(self, text: str):
        """Thông báo giữa khung video khi chưa có hình (vd: đang tải mô hình)."""
        self.video.set_image(None)
        self.bev.set_image(None)
        self.video.set_placeholder(text)
        self._layout()

    def set_frames(self, overlay: QImage, bev: QImage):
        aspect = overlay.width() / max(overlay.height(), 1)
        first = not self.video.has_image()
        self.video.set_image(overlay)
        self.bev.set_image(bev)
        if first or abs(aspect - self._video_aspect) > 0.01:
            self._video_aspect = aspect
            self._layout()

    def resizeEvent(self, _):
        self._layout()

    def _layout(self):
        w, h = self.width(), self.height()
        self.welcome.setGeometry(0, 0, w, h)
        has_frame = self.video.has_image() and not self.welcome_on
        show_bev = self.bev_btn.isChecked() and has_frame
        self.bev_btn.setVisible(has_frame)
        self.bev.setVisible(show_bev)
        bev_w = int(h * self.BEV_ASPECT)
        video_need = int(h * self._video_aspect)
        if show_bev and w - bev_w - self.GAP >= 0.8 * video_need:
            # đủ chỗ: BEV nằm cạnh video
            vw = w - bev_w - self.GAP
            self.video.setGeometry(0, 0, vw, h)
            self.bev.setGeometry(vw + self.GAP, 0, bev_w, h)
        else:
            self.video.setGeometry(0, 0, w, h)
            if show_bev:
                ph = int(h * 0.5)
                pw = int(ph * self.BEV_ASPECT)
                self.bev.setGeometry(w - pw - 12, h - ph - 12, pw, ph)
                self.bev.raise_()
        self.bev_btn.adjustSize()
        bx = self.bev.x() + self.bev.width() - self.bev_btn.width() - 6 if show_bev else w - self.bev_btn.width() - 8
        self.bev_btn.move(bx, 8 if not show_bev or self.bev.y() == 0 else self.bev.y() + 6)
        self.bev_btn.raise_()


class PlayBar(QFrame):
    """Thanh dưới video: tạm dừng, tiến độ, thời gian, thông tin nguồn."""

    def __init__(self, pause_action, parent=None):
        super().__init__(parent)
        self.setObjectName("playbar")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 12, 6)
        lay.setSpacing(10)
        self.pause_btn = QToolButton()
        self.pause_btn.setDefaultAction(pause_action)
        self.pause_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        lay.addWidget(self.pause_btn)
        self.live = QLabel()
        lay.addWidget(self.live)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        lay.addWidget(self.bar, 1)
        self.time = QLabel()
        self.time.setObjectName("muted")
        lay.addWidget(self.time)
        self.info = QLabel()
        self.info.setObjectName("muted")
        lay.addWidget(self.info)
        self.reset()

    @staticmethod
    def _clock(sec: float) -> str:
        sec = max(int(sec), 0)
        return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60:02d}:{sec % 60:02d}"

    def reset(self):
        self.bar.setValue(0)
        self.bar.hide()
        self.time.clear()
        self.live.clear()

    def set_live(self, text: str):
        self.live.setText(f"{icon_html('circle_rounded', 'danger', 10)}&nbsp;{text}" if text else "")

    def set_progress(self, idx: int, total: int, fps: float):
        self.bar.show()
        self.live.clear()
        self.bar.setMaximum(max(total, 1))
        self.bar.setValue(idx)
        fps = fps if fps > 0 else 30.0
        self.time.setText(f"{self._clock(idx / fps)} / {self._clock(total / fps)}")

    def set_info(self, text: str):
        self.info.setText(text)


# ----------------------------------------------------------------------
# Cột bên phải
# ----------------------------------------------------------------------
