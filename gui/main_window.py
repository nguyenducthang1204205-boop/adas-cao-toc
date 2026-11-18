"""Cửa sổ chính của hệ thống giám sát khoảng cách an toàn."""

import json
import os
from dataclasses import asdict
from typing import Optional, Tuple

from PySide6.QtCore import QObject, QRunnable, QSize, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QAction, QIntValidator, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox,
    QProgressBar, QPushButton, QScrollArea, QSplitter, QTabWidget, QToolButton, QVBoxLayout, QWidget,
)

from adas.alert.thresholds import compute_thresholds
from adas.assistant import AssistantResult, SafetyAssistant
from adas.config import AppConfig, CalibrationConfig, SafetyPolicy, _from_dict, update_inplace
from adas.distance.camera_model import generic_calibration
from adas.formatting import vn_factor, vn_num
from adas.paths import UI_ASSETS_DIR
from adas.storage.database import Database
from adas.stream.sources import classify_source, read_first_frame
from gui.dialogs.calibration import CalibrationDialog
from gui.dialogs.calibration_wizard import CalibrationWizard
from gui.dialogs.history import HistoryDialog
from gui.dialogs.settings import SettingsDialog
from gui.dialogs.sources import SourceDialog
from gui.rendering import icon, icon_pixmap
from gui.widgets import (
    ChatPanel, ConditionPanel, EventLog, PlayBar, SpeedPanel, StatusCard, VideoStage, fit_to_screen,
    icon_html, perf_text, repolish, set_icon,
)
from gui.worker import ProcessingWorker

SOURCE_ICONS = {"video": "movie_outlined", "camera": "videocam_outlined", "stream": "cell_tower_outlined",
                "image": "image_outlined"}   # Material Icons, giống bản mobile


class _AssistantSignals(QObject):
    done = Signal(object)


class _AssistantTask(QRunnable):
    """Gọi trợ lý AI ở luồng riêng để giao diện không bị treo khi chờ mạng."""

    def __init__(self, assistant: SafetyAssistant, message: str, policy: SafetyPolicy,
                 speed: float, scene: str):
        super().__init__()
        self.signals = _AssistantSignals()
        self.args = (assistant, message, policy, speed, scene)

    def run(self):
        assistant, message, policy, speed, scene = self.args
        try:
            result = assistant.ask(message, policy, speed, scene)
        except Exception as e:
            result = e
        self.signals.done.emit(result)


class _FillTabs(QTabWidget):
    """Tab ở cuối cột phải: chỉ đòi kích thước tối thiểu, phần dư của cột dành cho nó.
    (QScrollArea tính chiều cao cột theo kích thước mong muốn - nếu không, cột luôn bị cuộn.)"""

    def minimumSizeHint(self):
        # Không lấy tổng tối thiểu của nội dung (chat + bảng vi phạm, ~190 px): khung chat tự co lại
        hint = super().minimumSizeHint()
        return QSize(hint.width(), min(hint.height(), self.minimumHeight() or hint.height()))

    def sizeHint(self):
        return self.minimumSizeHint()

    def hasHeightForWidth(self):
        return False


class MainWindow(QMainWindow):
    def __init__(self, cfg: AppConfig, initial_source: Optional[str] = None):
        super().__init__()
        self.cfg = cfg
        self.source_spec: Optional[str] = initial_source
        self.source_id: Optional[int] = None
        self.worker: Optional[ProcessingWorker] = None
        self.last_stats: Optional[dict] = None
        self.api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.assistant = SafetyAssistant(cfg.assistant, self.api_key or None)
        self._assistant_tasks = []
        self._old_workers = []
        self._has_frame = False             # phiên hiện tại đã có khung hình nào chưa
        self._notice_dismissed = set()      # nguồn đã tắt nhắc "chưa căn chỉnh"
        self._frame_idx = 0                 # khung đang phát (để trình căn chỉnh dò điểm tụ quanh đó)
        self._calib_msg = None              # thông báo căn chỉnh khi chạy đang hiện
        self._video_fps = 0.0

        self.setWindowTitle("Hệ thống cảnh báo khoảng cách an toàn trên cao tốc - YOLOv11 + IPM")
        self._build_actions()
        self._build_header()
        self._build_body()
        self._build_statusbar()
        fit_to_screen(self, 1600, 900, ratio=0.96)
        if self.screen().availableGeometry().height() < 1000:
            self.setWindowState(Qt.WindowState.WindowMaximized)   # khôi phục thì về kích thước vừa màn hình
        self._update_actions()
        self._update_chat_source()
        self._policy_changed()
        self._refresh_source_state()
        self._show_welcome(True)

    # ------------------------------------------------------------------
    # Dựng giao diện
    # ------------------------------------------------------------------

    def _action(self, text, slot, shortcut=None, checkable=False, tip="", icon_name=None):
        act = QAction(" " + text if icon_name else text, self)   # chừa khoảng giữa biểu tượng và chữ
        if icon_name:
            act.setIcon(icon(icon_name, "text", 18))
        act.triggered.connect(slot)
        act.setCheckable(checkable)
        if shortcut:
            act.setShortcut(QKeySequence(shortcut))
        act.setToolTip(tip or text)
        self.addAction(act)   # phím tắt dùng được ở mọi nơi trong cửa sổ
        return act

    def _build_actions(self):
        self.act_video = self._action("Mở video…", self.open_video, "Ctrl+O", tip="Mở file video hành trình (Ctrl+O)",
                                      icon_name="folder_open_outlined")
        self.act_image = self._action("Mở ảnh…", self.open_image, tip="Kiểm tra trên một ảnh tĩnh",
                                      icon_name="image_outlined")
        self.act_camera = self._action("Camera trực tiếp…", self.open_camera,
                                       tip="Camera USB hoặc luồng RTSP/HTTP", icon_name="videocam_outlined")
        self.act_sources = self._action("Quản lý nguồn…", self.open_sources, icon_name="folder_copy_outlined",
                                        tip="Quản lý danh sách nguồn video/camera, kiểm tra kết nối, dò camera")
        self.act_start = self._action("Bắt đầu", self.start, "F5", tip="Bắt đầu giám sát (F5)",
                                      icon_name="play_arrow_rounded")
        self.act_pause = self._action("Tạm dừng", self.toggle_pause, "Space", checkable=True, icon_name="pause_rounded",
                                      tip="Tạm dừng / tiếp tục (Space)")
        self.act_stop = self._action("Dừng", self.stop, "Esc", tip="Dừng giám sát (Esc)", icon_name="stop_rounded")
        self.act_calib = self._action("Căn chỉnh camera", self.calibrate, icon_name="straighten_outlined",
                                      tip="Căn chỉnh camera để đo khoảng cách chính xác (IPM)")
        self.act_settings = self._action("Cài đặt", self.open_settings, tip="Cài đặt hệ thống",
                                         icon_name="tune_outlined")
        self.act_history = self._action("Lịch sử", self.open_history, icon_name="history_outlined",
                                        tip="Tra cứu nhật ký vi phạm, phiên giám sát và lịch sử cấu hình "
                                            "(CSDL data/adas.db)")
        self.act_record = self._action("Ghi video", lambda: None, checkable=True, icon_name="fiber_manual_record_outlined",
                                       tip="Lưu video kết quả vào thư mục outputs/ (bật trước khi Bắt đầu)")
        self.act_sound = self._action("Âm thanh", self.toggle_sound, checkable=True, icon_name="volume_up_outlined",
                                      tip="Bật/tắt âm thanh cảnh báo")
        self.act_sound.setChecked(self.cfg.alert.sound_enabled)

    @staticmethod
    def _tool(action) -> QToolButton:
        b = QToolButton()
        b.setDefaultAction(action)
        b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        b.setIconSize(QSize(18, 18))
        return b

    @staticmethod
    def _separator() -> QFrame:
        f = QFrame()
        f.setObjectName("headerSep")
        return f

    def _build_header(self):
        header = QFrame()
        header.setObjectName("header")
        lay = QHBoxLayout(header)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(8)

        logo = QLabel()
        logo.setPixmap(QPixmap(str(UI_ASSETS_DIR / "app_icon.png")).scaled(
            36, 36, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        lay.addWidget(logo)
        title = QVBoxLayout()
        title.setSpacing(0)
        t = QLabel("ADAS Cao tốc")
        t.setObjectName("appTitle")
        st = QLabel("Cảnh báo khoảng cách an toàn")
        st.setObjectName("appSubtitle")
        title.addWidget(t)
        title.addWidget(st)
        lay.addLayout(title)
        lay.addSpacing(10)

        # Chọn nguồn: một nút gom mở video / ảnh / camera / danh sách + các nguồn dùng gần đây
        self.source_menu = QMenu(self)
        self.source_menu.aboutToShow.connect(self._fill_source_menu)
        self.source_btn = QToolButton()
        self.source_btn.setObjectName("sourceButton")
        self.source_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.source_btn.setIconSize(QSize(18, 18))
        self.source_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.source_btn.setMenu(self.source_menu)
        self.source_btn.setMinimumWidth(220)
        self.source_btn.setToolTip("Chọn nguồn video / camera")
        lay.addWidget(self.source_btn)

        self.start_btn = QPushButton()
        self.start_btn.setObjectName("startButton")
        self.start_btn.clicked.connect(self._start_or_stop)
        lay.addWidget(self.start_btn)
        lay.addWidget(self._separator())
        lay.addWidget(self._tool(self.act_record))
        lay.addWidget(self._tool(self.act_sound))
        lay.addStretch(1)
        lay.addWidget(self._tool(self.act_calib))
        lay.addWidget(self._tool(self.act_history))
        lay.addWidget(self._tool(self.act_settings))
        self.setMenuWidget(header)

    def _build_notice(self) -> QFrame:
        """Nhắc căn chỉnh camera khi nguồn đang dùng chưa có hiệu chỉnh."""
        f = QFrame()
        f.setObjectName("notice")
        lay = QHBoxLayout(f)
        lay.setContentsMargins(14, 6, 10, 6)
        self.notice_text = QLabel()
        self.notice_text.setWordWrap(True)
        go = QPushButton("Căn chỉnh ngay")
        set_icon(go, "straighten_outlined", "warning")
        go.clicked.connect(self.calibrate)
        close = QPushButton()
        set_icon(close, "close_rounded", "text", 18)
        close.setToolTip("Ẩn nhắc nhở cho nguồn này")
        close.setFixedWidth(34)
        close.clicked.connect(self._dismiss_notice)
        lay.addWidget(self.notice_text, 1)
        lay.addWidget(go)
        lay.addWidget(close)
        f.hide()
        return f

    def _build_calib_bar(self) -> QFrame:
        """Tiến độ tự hoàn thiện căn chỉnh khi chạy (adas/distance/online_calib.py) và kết quả tự kiểm tra."""
        f = QFrame()
        f.setObjectName("calibBar")
        lay = QHBoxLayout(f)
        lay.setContentsMargins(14, 5, 8, 5)
        lay.setSpacing(10)
        self.calib_icon = QLabel()
        self.calib_text = QLabel()
        self.calib_text.setWordWrap(True)
        self.calib_progress = QProgressBar()
        self.calib_progress.setRange(0, 100)
        self.calib_progress.setFixedSize(150, 14)
        self.calib_go = QPushButton("Căn chỉnh lại")
        self.calib_go.setObjectName("link")
        self.calib_go.clicked.connect(self.calibrate)
        # Video không có GPS: nhập tốc độ đang in trên hình ngay lúc video chạy (không dừng). Lúc bắt đầu gõ là lúc
        # đọc số, nên ghi thời điểm video khi gõ ký tự đầu tiên.
        self.calib_ask = QWidget()
        ask = QHBoxLayout(self.calib_ask)
        ask.setContentsMargins(0, 0, 0, 0)
        ask.setSpacing(6)
        self.calib_speed = QLineEdit()
        self.calib_speed.setValidator(QIntValidator(20, 200, self))
        self.calib_speed.setPlaceholderText("vd: 74")
        self.calib_speed.setFixedWidth(84)
        self.calib_speed.setToolTip("Tốc độ xe đang in trên video (vd: 74KM/H ở góc ảnh). Video vẫn chạy; "
                                    "app so số này với tốc độ đo từ vạch kẻ đứt lúc bạn bắt đầu gõ.")
        self.calib_speed.textEdited.connect(self._speed_typing)
        self.calib_speed.returnPressed.connect(self._speed_submit)
        use = QPushButton("Dùng")
        use.clicked.connect(self._speed_submit)
        ask.addWidget(QLabel("Tốc độ trên video:"))
        ask.addWidget(self.calib_speed)
        ask.addWidget(QLabel("km/h"))
        ask.addWidget(use)
        self.calib_ask.hide()
        self._speed_t = None                # thời điểm video lúc bắt đầu gõ tốc độ
        close = QPushButton()
        set_icon(close, "close_rounded", "muted", 16)
        close.setFixedWidth(30)
        close.setToolTip("Ẩn")
        close.clicked.connect(f.hide)
        lay.addWidget(self.calib_icon)
        lay.addWidget(self.calib_text, 1)
        lay.addWidget(self.calib_progress)
        lay.addWidget(self.calib_ask)
        lay.addWidget(self.calib_go)
        lay.addWidget(close)
        self._calib_hide = QTimer(self)
        self._calib_hide.setSingleShot(True)
        self._calib_hide.timeout.connect(f.hide)
        f.hide()
        return f

    def _speed_typing(self, text: str):
        if not text:
            self._speed_t = None
        elif self._speed_t is None:
            self._speed_t = self._video_t()

    def _speed_submit(self):
        text = self.calib_speed.text()
        if self.worker is None or not self.calib_speed.hasAcceptableInput():
            return
        t = self._speed_t if self._speed_t is not None else self._video_t()
        self.worker.speed_reference(t, float(text))
        self.calib_speed.clear()
        self._speed_t = None
        self.calib_ask.hide()
        self.calib_text.setText(f"Đã nhận {text} km/h - đang so với tốc độ đo từ vạch kẻ đứt lúc đó…")

    def _video_t(self) -> float:
        """Thời điểm video đang hiện (giây), cùng thang thời gian với luồng xử lý (khung / fps)."""
        return self._frame_idx / self._video_fps if self._video_fps > 0 else 0.0

    def _update_calib_bar(self, st: Optional[dict]):
        if st is None:
            self.calib_bar.hide()
            self._calib_msg = None
            return
        if st["state"] == "collecting":
            self.calib_progress.setValue(st["progress"])
        ask = bool(st.get("ask_speed"))
        key = (st["state"], st["message"], ask)
        if key == self._calib_msg:
            return
        self._calib_msg = key
        state = st["state"]
        if state == "collecting":
            name, color = "straighten_outlined", "accent"
        elif state == "done" and st["ok"]:
            name, color = "check_circle_rounded", "safe"
        else:
            name, color = "error_outline_rounded", "warning"
        self.calib_icon.setPixmap(icon_pixmap(name, color, 18))
        self.calib_text.setText(st["message"])
        self.calib_progress.setVisible(state == "collecting")
        self.calib_ask.setVisible(ask)
        self.calib_go.setVisible(state != "collecting" and not st["ok"] and not ask)
        self.calib_bar.setProperty("state", state)
        repolish(self.calib_bar)
        self.calib_bar.show()
        # kết quả tốt: hiện 15 s rồi tự ẩn; đang đo / cần chú ý / đang mời nhập tốc độ: giữ lại
        if state == "done" and st["ok"] and not ask:
            self._calib_hide.start(15000)
        else:
            self._calib_hide.stop()

    def _build_body(self):
        central = QWidget()
        cv = QVBoxLayout(central)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(0)
        self.notice = self._build_notice()
        cv.addWidget(self.notice)
        self.calib_bar = self._build_calib_bar()
        cv.addWidget(self.calib_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Trái: video + nhìn từ trên xuống + thanh phát
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(0)
        self.stage = VideoStage()
        w = self.stage.welcome
        w.open_video.connect(self.open_video)
        w.open_camera.connect(self.open_camera)
        w.open_image.connect(self.open_image)
        w.open_sources.connect(self.open_sources)
        w.calibrate.connect(self.calibrate)
        w.start.connect(self.start)
        ll.addWidget(self.stage, 1)
        self.playbar = PlayBar(self.act_pause)
        ll.addWidget(self.playbar)
        splitter.addWidget(left)

        # Phải: trạng thái, tốc độ, điều kiện đường, trợ lý AI / nhật ký
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(8, 8, 8, 8)
        rl.setSpacing(8)
        self.status_card = StatusCard()
        rl.addWidget(self.status_card)
        self.speed_panel = SpeedPanel(self.cfg.speed_kmh)
        self.cfg.speed_kmh = self.speed_panel.speed()
        self.speed_panel.set_auto(self.cfg.auto_speed)
        self.speed_panel.speed_changed.connect(self._on_speed)
        self.speed_panel.auto_changed.connect(self._on_auto_speed)
        rl.addWidget(self.speed_panel)
        self.condition_panel = ConditionPanel()
        self.condition_panel.preset_requested.connect(self._quick_condition)
        self.condition_panel.reset_requested.connect(self.reset_policy)
        rl.addWidget(self.condition_panel)

        tabs = _FillTabs()
        self.chat = ChatPanel()
        self.chat.send_requested.connect(self.ask_assistant)
        self.events = EventLog()
        self.events.history_requested.connect(self.open_history)
        self.events.count_changed.connect(
            lambda n: self.tabs.setTabText(1, f"Vi phạm ({n})" if n else "Vi phạm"))
        tabs.addTab(self.chat, icon("smart_toy_outlined", "accent", 18), "Trợ lý AI")
        tabs.addTab(self.events, icon("receipt_long_outlined", "accent", 18), "Vi phạm")
        tabs.setMinimumHeight(120)
        self.chat.source_label.setMinimumHeight(tabs.tabBar().sizeHint().height())
        tabs.setCornerWidget(self.chat.source_label, Qt.Corner.TopRightCorner)
        self.tabs = tabs
        rl.addWidget(tabs, 1)

        # Cột phải cuộn được khi màn hình thấp, để cửa sổ không cao quá màn hình
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right_scroll.setWidget(right)
        right_scroll.setMinimumWidth(420)
        splitter.addWidget(right_scroll)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([1100, 470])
        cv.addWidget(splitter, 1)
        self.setCentralWidget(central)

    def _build_statusbar(self):
        self.perf_label = QLabel()
        self.perf_label.setObjectName("muted")
        self.perf_label.setToolTip("Thời gian xử lý từng tầng của một khung hình (mili giây)")
        self.statusBar().addPermanentWidget(self.perf_label)
        self.statusBar().showMessage("Sẵn sàng")

    # ------------------------------------------------------------------
    # Chọn nguồn
    # ------------------------------------------------------------------

    def _fill_source_menu(self):
        m = self.source_menu
        m.clear()
        for act in (self.act_video, self.act_camera, self.act_image):
            m.addAction(act)
        try:
            recent = Database().list_sources()[:6]
        except Exception:
            recent = []
        if recent:
            m.addSection("Dùng gần đây")
            for r in recent:
                mark = "  ·  đã căn chỉnh" if r["calibrations"] else ""
                act = m.addAction(icon(SOURCE_ICONS.get(r["source_type"], "movie_outlined"), "text", 18),
                                  f"{r['name']}{mark}")
                act.setToolTip(r["uri"])
                act.triggered.connect(lambda _=False, uri=r["uri"]: self._select_source(uri))
        m.addSeparator()
        m.addAction(self.act_sources)

    def open_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn video hành trình", "", "Video (*.mp4 *.avi *.mov *.mkv *.wmv);;Tất cả (*.*)")
        if path:
            self._select_source(path)

    def open_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn ảnh", "", "Ảnh (*.jpg *.jpeg *.png *.bmp *.webp)")
        if path:
            self._select_source(path)

    def open_camera(self):
        text, ok = QInputDialog.getText(
            self, "Camera trực tiếp",
            "Nhập chỉ số camera (0, 1, …) hoặc URL luồng (rtsp://…, http://…):", text="0")
        if ok and text.strip():
            self._select_source(text.strip())

    def open_sources(self):
        dlg = SourceDialog(self, current_uri=self.source_spec)
        if dlg.exec() and dlg.selected_uri:
            self._select_source(dlg.selected_uri)

    def _select_source(self, spec: str):
        self.stop()
        self.source_spec = spec
        self._refresh_source_state()
        self.start()

    def _source_name(self) -> str:
        return os.path.basename(self.source_spec) or self.source_spec

    def _calibration_state(self):
        """(đã căn chỉnh?, mô tả) của nguồn đang chọn, đọc từ CSDL."""
        try:
            db = Database()
            row = db.get_source(self.source_spec)
            cal = db.latest_calibration(row["id"]) if row is not None else None
        except Exception:
            return None, ""
        if cal is None:
            return False, ""
        kind = {"auto": "tự động", "manual": "thủ công", "pose": "chiều cao + chân trời",
                "online": "tự hoàn thiện khi chạy"}.get(cal["method"], "chuyển từ bản cũ")
        return True, f"Đã căn chỉnh ({kind}, {cal['created_at'][:16]}) - có thể căn chỉnh lại bất cứ lúc nào"

    def _refresh_source_state(self):
        """Cập nhật nút nguồn, hướng dẫn 3 bước và nhắc căn chỉnh theo nguồn đang chọn."""
        if not self.source_spec:
            self.source_btn.setText("Chọn nguồn video")
            set_icon(self.source_btn, "folder_open_outlined", "accent")
            self.stage.welcome.set_state(None, None)
            self.notice.hide()
            return
        name = self._source_name()
        kind = classify_source(self.source_spec)
        short = name if len(name) <= 30 else name[:27] + "…"
        self.source_btn.setText(short)
        set_icon(self.source_btn, SOURCE_ICONS.get(kind, "movie_outlined"), "accent")
        self.source_btn.setToolTip(f"Nguồn đang chọn: {self.source_spec}\nBấm để đổi nguồn")
        calibrated, desc = self._calibration_state()
        self.stage.welcome.set_state(name, calibrated, desc)
        show = calibrated is False and kind != "image" and self.source_spec not in self._notice_dismissed
        self.notice_text.setText(
            f"{icon_html('error_outline_rounded', 'warning', 16)}&nbsp; Nguồn <b>{name}</b> chưa được căn chỉnh "
            "camera - khoảng cách hiển thị chỉ là ước lượng. "
            "Căn chỉnh một lần, lần sau mở lại nguồn này sẽ tự dùng lại.")
        self.notice.setVisible(show)

    def _dismiss_notice(self):
        if self.source_spec:
            self._notice_dismissed.add(self.source_spec)
        self.notice.hide()

    def _activate_source(self, spec: str) -> Tuple[int, bool]:
        """
        Đăng ký nguồn vào CSDL và nạp hiệu chỉnh IPM riêng của nguồn. Trả về (id nguồn, đã có căn chỉnh riêng).
        Nguồn chưa có căn chỉnh: KHÔNG dùng lại căn chỉnh của nguồn trước (camera khác -> chân trời, tiêu cự sai:
        dò làn lệch, đo tốc độ lấy mẫu trên chân trời thật ra ~0 km/h); về hình học mặc định, luồng xử lý tự khởi tạo.
        """
        db = Database()
        source_id = db.register_source(spec, classify_source(spec), os.path.basename(spec) or spec)
        cal = db.latest_calibration(source_id)
        if cal is not None:
            calib = _from_dict(CalibrationConfig, json.loads(cal["params_json"]))
            if asdict(calib) != asdict(self.cfg.calibration):
                name = db.get_source(spec)["name"]
                update_inplace(self.cfg.calibration, calib)
                self.cfg.save(f"Nạp hiệu chỉnh IPM của nguồn: {name}")
                self.statusBar().showMessage(f"Đã nạp ma trận camera #{cal['id']} của nguồn '{name}'")
        else:
            update_inplace(self.cfg.calibration, generic_calibration(self.cfg.calibration))
        return source_id, cal is not None

    # ------------------------------------------------------------------
    # Điều khiển xử lý
    # ------------------------------------------------------------------

    def _start_or_stop(self):
        if self.worker is None:
            self.start()
        else:
            self.stop()

    def start(self):
        if self.worker is not None:
            return
        if not self.source_spec:
            self.open_video()
            return
        self.source_id, has_calib = self._activate_source(self.source_spec)
        self._refresh_source_state()
        w = ProcessingWorker(self.cfg, self.source_spec, record=self.act_record.isChecked(),
                             source_id=self.source_id, auto_init=not has_calib)
        w.frame_ready.connect(self._on_frame)
        w.session_started.connect(self.events.start_session)
        w.violation.connect(self.events.on_violation)
        w.status.connect(self._on_status)
        w.failed.connect(self._on_failed)
        w.progress.connect(self._on_progress)
        w.calibration_refined.connect(self._on_calibration_refined)
        w.calibration_initialized.connect(self._on_calibration_initialized)
        w.finished.connect(lambda w=w: self._on_finished(w))
        self.worker = w
        self._has_frame = False
        self.act_pause.setChecked(False)
        self._show_welcome(False)
        self.stage.set_message("Đang mở nguồn và tải mô hình nhận diện…")
        self.status_card.reset("Đang khởi động…")
        self._update_calib_bar(None)
        self.playbar.reset()
        if classify_source(self.source_spec) in ("camera", "stream"):
            self.playbar.set_live("TRỰC TIẾP")
        w.start()
        self._update_actions()

    def toggle_pause(self):
        if self.worker:
            self.worker.set_paused(self.act_pause.isChecked())
            self.statusBar().showMessage("Tạm dừng" if self.act_pause.isChecked() else "Tiếp tục giám sát")

    def stop(self):
        if self.worker is None:
            return
        w = self.worker
        w.stop()
        w.set_paused(False)
        if not w.wait(5000):
            # Luồng còn bận (vd: đang tải mô hình) - giữ tham chiếu để không bị hủy khi đang chạy
            self._old_workers.append(w)
        self._on_finished(w)

    def _on_finished(self, w: ProcessingWorker):
        if self.worker is not w:  # tín hiệu muộn của luồng cũ đã được xử lý
            return
        self.worker = None
        self.act_pause.setChecked(False)
        self.speed_panel.set_measured(None)
        self.playbar.set_live("")
        if not self._has_frame:
            self._show_welcome(True)
            self.status_card.reset()
        self._update_actions()

    def _show_welcome(self, on: bool):
        self.stage.show_welcome(on)
        self.playbar.setVisible(not on)

    def _on_failed(self, msg: str):
        QMessageBox.critical(self, "Lỗi xử lý", msg)
        self.status_card.reset()

    def _on_status(self, msg: str):
        self.statusBar().showMessage(msg)
        if not self._has_frame and self.worker is not None:
            self.stage.set_message(msg)

    def _update_actions(self):
        running = self.worker is not None
        self.act_start.setEnabled(not running)
        self.act_pause.setEnabled(running)
        self.act_stop.setEnabled(running)
        self.act_record.setEnabled(not running)
        self.start_btn.setText("Dừng" if running else "Bắt đầu")
        set_icon(self.start_btn, "stop_rounded" if running else "play_arrow_rounded",
                 "text" if running else "on_accent", 20)
        self.start_btn.setToolTip("Dừng giám sát (Esc)" if running else "Bắt đầu giám sát (F5)")
        self.start_btn.setProperty("running", running)
        repolish(self.start_btn)

    # ------------------------------------------------------------------
    # Nhận kết quả từ luồng xử lý
    # ------------------------------------------------------------------

    def _on_frame(self, overlay, bev, stats: dict):
        if self.worker is None or self.worker is not self.sender():
            return     # khung còn trong hàng đợi của luồng đã dừng
        self._has_frame = True
        self.stage.set_frames(overlay, bev)
        self.status_card.update_stats(stats)
        self.speed_panel.set_measured(stats["speed_kmh"] if stats.get("speed_auto") else None)
        self.perf_label.setText(perf_text(stats))
        self._update_calib_bar(stats.get("calib"))
        self.playbar.set_info(f"{overlay.width()}×{overlay.height()} · {stats['fps']:.0f} FPS")
        self.last_stats = stats

    def _on_progress(self, idx: int, total: int, fps: float):
        self._frame_idx = idx
        self._video_fps = fps
        self.playbar.set_progress(idx, total, fps)

    # ------------------------------------------------------------------
    # Tốc độ & chính sách an toàn
    # ------------------------------------------------------------------

    def _on_speed(self, v: float):
        self.cfg.speed_kmh = v

    def _on_auto_speed(self, on: bool):
        self.cfg.auto_speed = on
        if not on:
            self.speed_panel.set_measured(None)
        self.cfg.save("Bật tự đo tốc độ" if on else "Tắt tự đo tốc độ (chọn tay)")
        self.statusBar().showMessage("Tự đo tốc độ từ video: " + ("bật" if on else "tắt - dùng tốc độ chọn tay"))

    def _policy_changed(self):
        self.speed_panel.set_policy(self.cfg.policy)
        self.condition_panel.set_policy(self.cfg.policy)

    def toggle_sound(self):
        self.cfg.alert.sound_enabled = self.act_sound.isChecked()

    def reset_policy(self):
        # Chỉ khôi phục điều kiện đường; ngưỡng theo dải tốc độ là cài đặt của người dùng, giữ nguyên
        p = self.cfg.policy
        update_inplace(p, SafetyPolicy(time_gap_s=p.time_gap_s, band_gaps_m=list(p.band_gaps_m)))
        self._policy_changed()
        self.assistant.clear_history()
        self.chat.add_message("system", "Đã khôi phục tham số an toàn mặc định (đường khô ráo, tầm nhìn tốt). "
                                        "Ngưỡng theo dải tốc độ trong Cài đặt được giữ nguyên.")
        self.cfg.save("Khôi phục ngưỡng an toàn mặc định")
        self.statusBar().showMessage("Đã khôi phục ngưỡng an toàn mặc định.")

    def _quick_condition(self, text: str):
        """Nút điều kiện đường: gửi câu mô tả cho Trợ lý AI (cùng đường đi với khung chat)."""
        self.tabs.setCurrentWidget(self.chat)
        self.chat.submit(text)

    # ------------------------------------------------------------------
    # Trợ lý AI
    # ------------------------------------------------------------------

    def _update_chat_source(self):
        a = self.cfg.assistant
        if a.use_cloud:
            key = "API key đã cấu hình" if self.api_key else "dùng thông tin xác thực mặc định"
            self.chat.set_source(f"Claude · {a.model}",
                                 f"Chế độ: Claude ({a.model}) · {key} · tự chuyển offline khi lỗi")
        else:
            self.chat.set_source("Offline · miễn phí", "Chế độ: trợ lý offline · miễn phí, không cần Internet")

    def _scene_text(self) -> str:
        s = self.last_stats
        if not s or self.worker is None:
            return "[Cảnh quan] Chưa chạy giám sát."
        if s["lead_distance"] is None:
            return f"[Cảnh quan] {s['n_vehicles']} xe trong khung hình, không có xe cùng làn phía trước."
        ttc = f", TTC {s['lead_ttc']:.1f} s" if s["lead_ttc"] is not None else ""
        return (f"[Cảnh quan] Xe cùng làn gần nhất: {s['lead_class']} cách {s['lead_distance']:.1f} m{ttc}; "
                f"mức cảnh báo hiện tại: {s['level']}; tổng {s['n_vehicles']} xe.")

    def ask_assistant(self, text: str):
        self.chat.set_busy(True)
        task = _AssistantTask(self.assistant, text, self.cfg.policy, self.speed_panel.effective_speed(),
                              self._scene_text())
        task.signals.done.connect(self._on_assistant)
        self._assistant_tasks.append(task)  # giữ tham chiếu tới khi xong
        QThreadPool.globalInstance().start(task)

    def _on_assistant(self, result):
        self.chat.set_busy(False)
        self._assistant_tasks = [t for t in self._assistant_tasks if t.signals is not self.sender()]
        if isinstance(result, Exception):
            self.chat.add_message("system", f"Lỗi trợ lý: {result}")
            return
        r: AssistantResult = result
        meta = f"Claude · {self.cfg.assistant.model}" if r.source == "Claude" else "Tư vấn offline"
        self.chat.add_message("assistant", r.reply, meta)
        if r.note:
            self.chat.add_message("system", r.note)

        update_inplace(self.cfg.policy, r.policy)
        if r.speed_kmh is not None:
            # tài xế tự nêu tốc độ -> dùng tốc độ đó (chọn tay), tắt tự đo
            self.cfg.speed_kmh = self.speed_panel.set_speed(r.speed_kmh)
            if self.cfg.auto_speed:
                self.cfg.auto_speed = False
                self.speed_panel.set_auto(False)
                self.chat.add_message("system", "Đã chuyển sang tốc độ chọn tay theo câu bạn nhập "
                                                "(tắt tự đo - bật lại ở thẻ Tốc độ xe).")
        self._policy_changed()
        speed = self.speed_panel.effective_speed()
        thr = compute_thresholds(speed, self.cfg.policy)
        basis = (f"ngưỡng dải {thr.band_m:.0f} m" if thr.band_m is not None
                 else f"quy tắc {vn_num(self.cfg.policy.time_gap_s)} giây")
        self.chat.add_message(
            "system",
            f"Đã áp dụng: {self.cfg.policy.condition} · {basis} × {vn_factor(self.cfg.policy.weather_factor)}. "
            f"Ở {speed:.0f} km/h: cảnh báo < {thr.safe_m:.0f} m, nguy hiểm < {thr.danger_m:.0f} m.")
        self.cfg.save(f"Trợ lý AI ({r.source}): {self.cfg.policy.condition}")

    # ------------------------------------------------------------------
    # Hiệu chỉnh & cài đặt
    # ------------------------------------------------------------------

    def calibrate(self, *_, advanced: bool = False):
        """Trình căn chỉnh 3 bước (mặc định) hoặc chấm 4 điểm (advanced / chọn từ trình căn chỉnh)."""
        frame = self.worker.last_frame if self.worker is not None else None
        video_path = self.source_spec
        start_frame = self._frame_idx if self.worker is not None else 0
        if frame is None and self.source_spec:
            frame = read_first_frame(self.source_spec)
        if frame is None:
            path, _ = QFileDialog.getOpenFileName(
                self, "Chọn ảnh/video để căn chỉnh camera", "",
                "Ảnh/Video (*.jpg *.jpeg *.png *.bmp *.mp4 *.avi *.mov *.mkv)")
            if not path:
                return
            frame = read_first_frame(path)
            video_path = path
            start_frame = 0
            if frame is None:
                QMessageBox.warning(self, "Căn chỉnh camera", "Không đọc được khung hình.")
                return
        was_paused = self.act_pause.isChecked()
        if self.worker and not was_paused:
            self.worker.set_paused(True)
        if advanced:
            dlg = CalibrationDialog(frame.copy(), self.cfg.calibration, self,
                                    video_path=video_path, speed_kmh=self.cfg.speed_kmh)
        else:
            is_video = bool(video_path) and classify_source(video_path) == "video"
            dlg = CalibrationWizard(frame.copy(), self.cfg.calibration, self,
                                    video_path=video_path if is_video else None, start_frame=start_frame,
                                    auto_calib=self.cfg.auto_calib)
        accepted = dlg.exec()
        if accepted:
            if not advanced:
                self.cfg.auto_calib = dlg.auto_calib.isChecked()
            self._apply_calibration(dlg.result_calib, dlg.method, dlg.note, video_path, frame.shape,
                                    "Căn chỉnh camera (IPM)")
        if self.worker and not was_paused:
            self.worker.set_paused(False)
        if not accepted and not advanced and dlg.advanced:
            self.calibrate(advanced=True)

    def _apply_calibration(self, calib: CalibrationConfig, method: str, note: str, video_path: Optional[str],
                           shape, reason: str):
        update_inplace(self.cfg.calibration, calib)
        self.cfg.save(reason)
        msg = "Đã áp dụng căn chỉnh camera mới."
        if video_path:
            # Lưu riêng cho nguồn để lần sau mở lại nguồn này không phải hiệu chỉnh lại
            db = Database()
            sid = db.register_source(video_path, classify_source(video_path),
                                     os.path.basename(video_path) or video_path)
            cid = db.save_calibration(sid, asdict(self.cfg.calibration), (shape[1], shape[0]), method, note)
            msg += (f" Đã lưu ma trận camera #{cid} cho nguồn "
                    f"'{os.path.basename(video_path) or video_path}'.")
        if self.worker:
            self.worker.calibration_changed()
        self.statusBar().showMessage(msg)
        self._refresh_source_state()

    def _on_calibration_refined(self, calib: CalibrationConfig, note: str):
        """Luồng xử lý vừa tự hoàn thiện căn chỉnh: áp dụng, lưu thành 1 dòng mới (bản cũ vẫn còn trong lịch sử)."""
        w = self.sender()
        if w is None or w is not self.worker or w.last_frame is None:
            return
        self._apply_calibration(calib, "online", note, self.source_spec, w.last_frame.shape,
                                "Tự hoàn thiện căn chỉnh camera khi chạy")

    def _on_calibration_initialized(self, calib: CalibrationConfig, note: str):
        """Nguồn mới chưa có căn chỉnh: luồng xử lý vừa tự khởi tạo từ vạch kẻ -> áp dụng, lưu cho nguồn này."""
        w = self.sender()
        if w is None or w is not self.worker or w.last_frame is None:
            return
        self._apply_calibration(calib, "pose", note, self.source_spec, w.last_frame.shape,
                                "Tự khởi tạo căn chỉnh camera cho nguồn mới")

    def open_settings(self):
        dlg = SettingsDialog(self.cfg, self.api_key, self)
        if not dlg.exec():
            return
        update_inplace(self.cfg, dlg.cfg)
        self.cfg.save("Cài đặt hệ thống")
        self.api_key = dlg.api_key_value
        self.assistant.set_api_key(self.api_key or None)
        self._refresh_after_config_change()
        self.statusBar().showMessage("Đã lưu cài đặt.")

    def _refresh_after_config_change(self):
        self.act_sound.setChecked(self.cfg.alert.sound_enabled)
        self.cfg.speed_kmh = self.speed_panel.set_speed(self.cfg.speed_kmh)
        self.speed_panel.set_auto(self.cfg.auto_speed)
        self._policy_changed()
        self._update_chat_source()
        if self.worker:
            self.worker.classes_changed()
            self.worker.calibration_changed()

    # ------------------------------------------------------------------
    # Cơ sở dữ liệu
    # ------------------------------------------------------------------

    def open_history(self):
        dlg = HistoryDialog(self)
        dlg.restore_config.connect(self._restore_config)
        dlg.exec()

    def _restore_config(self, data: dict):
        update_inplace(self.cfg, _from_dict(AppConfig, data))
        self.cfg.save("Khôi phục từ lịch sử cấu hình")
        self._refresh_after_config_change()
        self.statusBar().showMessage("Đã khôi phục cấu hình từ CSDL.")

    def closeEvent(self, e):
        self.stop()
        self.cfg.save("Đóng ứng dụng")
        super().closeEvent(e)
