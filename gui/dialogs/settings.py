"""
Hộp thoại cài đặt.

Các tab cơ bản chỉ chứa thứ người dùng thường cần chỉnh (loại xe, âm thanh, ngưỡng cảnh báo
theo dải tốc độ, điều kiện đường, trợ lý AI). Tham số kỹ thuật (mô hình YOLO, công thức ngưỡng, chống nhiễu) nằm ở tab "Nâng cao".
"""

import copy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout,
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QScrollArea, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from adas.config import (
    ASSISTANT_MODELS, DEFAULT_ASSISTANT_MODEL, AlertConfig, AppConfig, ModelConfig, SafetyPolicy,
)
from adas.alert.thresholds import LEGAL_GAP_TABLE, ROAD_CONDITIONS, compute_thresholds, condition_policy
from gui.rendering import icon
from gui.theme import C
from gui.widgets import fit_to_screen

CLASS_CHOICES = [("car", "Ô tô"), ("truck", "Xe tải"), ("bus", "Xe khách"),
                 ("Jeepney", "Xe Jeepney"), ("motorcycle", "Xe máy")]
DEVICE_CHOICES = [("auto", "Tự động (ưu tiên card đồ họa)"), ("0", "Card đồ họa NVIDIA (GPU)"),
                  ("cpu", "Bộ xử lý (CPU) - chậm")]
IMGSZ_CHOICES = [(480, "480 - nhanh nhất"), (640, "640 - mặc định"), (800, "800"),
                 (960, "960 - thấy xe xa tốt hơn"), (1280, "1280 - chậm nhất")]


def _dspin(value, lo, hi, step=0.1, decimals=2, suffix="", tip=""):
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setSingleStep(step)
    s.setDecimals(decimals)
    s.setSuffix(suffix)
    s.setValue(value)
    if tip:
        s.setToolTip(tip)
    return s


def _combo(choices, current):
    """ComboBox hiển thị nhãn tiếng Việt, lưu giá trị gốc trong userData."""
    c = QComboBox()
    for value, label in choices:
        c.addItem(label, value)
    i = c.findData(current)
    if i < 0:
        c.addItem(str(current), current)
        i = c.count() - 1
    c.setCurrentIndex(i)
    return c


class SettingsDialog(QDialog):
    def __init__(self, cfg: AppConfig, api_key: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cài đặt hệ thống")
        self.cfg = copy.deepcopy(cfg)
        fit_to_screen(self, 620, 560)
        root = QVBoxLayout(self)
        tabs = QTabWidget()
        root.addWidget(tabs)

        tabs.addTab(self._general_tab(), icon("settings_outlined", "accent", 18), "Chung")
        tabs.addTab(self._threshold_tab(), icon("social_distance_outlined", "accent", 18), "Ngưỡng cảnh báo")
        tabs.addTab(self._road_tab(), icon("water_drop_outlined", "accent", 18), "Điều kiện đường")
        tabs.addTab(self._assistant_tab(api_key), icon("smart_toy_outlined", "accent", 18), "Trợ lý AI")
        tabs.addTab(self._advanced_tab(), icon("memory_outlined", "accent", 18), "Nâng cao")

        for w in (self.weather, self.road_mu, self.visibility, self.time_gap, self.danger_ratio,
                  self.min_dist, *self.band_spins):
            w.valueChanged.connect(self._update_summary)
        self.legal.toggled.connect(self._update_summary)
        self.legal.toggled.connect(self._on_legal_toggled)
        self._on_legal_toggled(self.legal.isChecked())
        self._update_summary()

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setObjectName("primary")
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("Lưu")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Hủy")
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

    # ------------------------------------------------------------------
    # Các tab
    # ------------------------------------------------------------------

    def _general_tab(self) -> QWidget:
        m, a = self.cfg.model, self.cfg.alert
        w = QWidget()
        f = QFormLayout(w)
        grid = QGridLayout()
        self.class_checks = {}
        for i, (name, label) in enumerate(CLASS_CHOICES):
            cb = QCheckBox(label)
            cb.setChecked(name in m.enabled_classes)
            self.class_checks[name] = cb
            grid.addWidget(cb, i // 3, i % 3)
        f.addRow("Loại xe cần theo dõi:", grid)

        self.sound = QCheckBox("Phát âm thanh khi có cảnh báo")
        self.sound.setChecked(a.sound_enabled)
        test_row = QHBoxLayout()
        for text, level in (("Nghe thử CẢNH BÁO", "warning"), ("Nghe thử NGUY HIỂM", "danger")):
            b = QPushButton(text)
            b.setIcon(icon("play_arrow_rounded", level, 18))
            b.clicked.connect(lambda _=False, lv=level: self._preview_sound(lv))
            test_row.addWidget(b)
        self.only_lane = QCheckBox("Chỉ cảnh báo xe chạy cùng làn phía trước")
        self.only_lane.setToolTip("Bỏ chọn để cảnh báo cả xe ở làn bên cạnh")
        self.only_lane.setChecked(a.only_ego_lane)
        f.addRow(self.sound)
        f.addRow("Âm thanh:", test_row)
        self.auto_lane = QCheckBox("Tự nhận diện làn đang đi theo vạch kẻ đường")
        self.auto_lane.setToolTip("Vùng cảnh báo bám theo 2 vạch làn của xe (đúng cả khi làn rộng/hẹp khác nhau,\n"
                                  "xe đi lệch trong làn, đường cong). Bỏ chọn hoặc khi không thấy vạch:\n"
                                  "dùng hành lang cố định ± nửa bề rộng làn trong Căn chỉnh camera")
        self.auto_lane.setChecked(a.auto_lane)
        self.auto_speed = QCheckBox("Tự đo tốc độ xe từ video (theo chuyển động của vạch kẻ đứt)")
        self.auto_speed.setToolTip("Không cần GPS: đo quãng đường vạch kẻ trôi về phía xe giữa các khung hình.\n"
                                   "Chính xác khi camera đã được căn chỉnh đúng (nên dùng Tự động căn chỉnh).\n"
                                   "Khi chưa đo được (không thấy vạch đứt, ảnh tĩnh): dùng tốc độ chọn tay")
        self.auto_speed.setChecked(self.cfg.auto_speed)
        self.auto_calib = QCheckBox("Tự hoàn thiện căn chỉnh camera khi chạy, báo khi camera bị xê dịch")
        self.auto_calib.setToolTip("Đo đường chân trời từ 2 vạch làn trong lúc chạy (kiểu Tesla / openpilot).\n"
                                   "Căn chỉnh theo chiều cao camera: tự chỉnh và lưu thành bản căn chỉnh mới.\n"
                                   "Căn chỉnh chấm 4 điểm: chỉ kiểm tra (bề rộng làn đo được), không sửa")
        self.auto_calib.setChecked(self.cfg.auto_calib)
        f.addRow(self.only_lane)
        f.addRow(self.auto_lane)
        f.addRow(self.auto_speed)
        f.addRow(self.auto_calib)
        return w

    def _threshold_tab(self) -> QWidget:
        """Ngưỡng cảnh báo khi đường khô ráo, tùy chỉnh cho từng dải tốc độ (không thấp hơn luật)."""
        p = self.cfg.policy
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(self._note(
            "Đặt khoảng cách CẢNH BÁO cho từng dải tốc độ khi đường khô ráo. Từ 60 km/h, mỗi dải không được "
            "thấp hơn mức tối thiểu của Bộ GTVT (Thông tư 31/2019/TT-BGTVT); chỉ được đặt xa hơn."))
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        for col, text in enumerate(("Dải tốc độ", "Cảnh báo khi xe trước gần hơn", "Tối thiểu theo luật",
                                    "Đang áp dụng (gồm điều kiện đường)")):
            grid.addWidget(QLabel(f"<b>{text}</b>"), 0, col)

        self.time_gap = _dspin(p.time_gap_s, 2.0, 6.0, 0.5, 1, " giây", (
            "Dưới 60 km/h luật không quy định số mét; phần mềm giữ khoảng cách bằng quãng đường "
            "xe đi được trong số giây này (quy tắc 2 giây)"))
        grid.addWidget(QLabel("Dưới 60 km/h"), 1, 0)
        grid.addWidget(self.time_gap, 1, 1)
        grid.addWidget(QLabel("Tài xế tự chủ động"), 1, 2)

        gaps = list(p.band_gaps_m) + [g for _, g in LEGAL_GAP_TABLE][len(p.band_gaps_m):]
        self.band_spins, self.band_applied = [], [QLabel()]
        grid.addWidget(self.band_applied[0], 1, 3)
        for i, (vmax, legal) in enumerate(LEGAL_GAP_TABLE):
            rng = f"{vmax} km/h" if i == 0 else f"Trên {LEGAL_GAP_TABLE[i - 1][0]} đến {vmax} km/h"
            spin = _dspin(max(gaps[i], legal), legal, 300.0, 5.0, 0, " m",
                          f"Tốc độ {rng.lower()}: cảnh báo khi xe trước gần hơn khoảng này "
                          f"(không thể đặt dưới {legal:.0f} m theo quy định)")
            applied = QLabel()
            self.band_spins.append(spin)
            self.band_applied.append(applied)
            grid.addWidget(QLabel(rng), i + 2, 0)
            grid.addWidget(spin, i + 2, 1)
            grid.addWidget(QLabel(f"≥ {legal:.0f} m"), i + 2, 2)
            grid.addWidget(applied, i + 2, 3)
        lay.addLayout(grid)

        reset = QPushButton("Đặt lại bằng mức tối thiểu theo luật")
        reset.setIcon(icon("restart_alt_rounded", "text", 18))
        reset.clicked.connect(self._reset_bands)
        lay.addWidget(reset, 0, Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(self._note(
            "Khi mưa, sương mù, đường trơn... các ngưỡng trên được nhân thêm hệ số theo điều kiện đường "
            "(tab Điều kiện đường hoặc Trợ lý AI). Ngưỡng NGUY HIỂM = ngưỡng cảnh báo × tỷ lệ ở tab Nâng cao."))
        lay.addStretch(1)
        return w

    def _road_tab(self) -> QWidget:
        p = self.cfg.policy
        w = QWidget()
        f = QFormLayout(w)
        self.preset = QComboBox()
        self.preset.addItem("- Giữ như hiện tại -", None)
        for c in ROAD_CONDITIONS.values():
            self.preset.addItem(c.name, c.key)
        self.preset.currentIndexChanged.connect(self._apply_preset)
        self.visibility = _dspin(p.visibility_m, 0, 1000, 10, 0, " m",
                                 "Khoảng xa nhất tài xế còn nhìn rõ (sương mù, mưa to...). "
                                 "Phần mềm sẽ gợi ý tốc độ tối đa để kịp dừng xe trong tầm nhìn")
        self.visibility.setSpecialValueText("Không hạn chế")
        self.condition = QLineEdit(p.condition)
        f.addRow("Thời tiết / mặt đường:", self.preset)
        f.addRow("Tầm nhìn xa:", self.visibility)
        f.addRow("Ghi chú điều kiện:", self.condition)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        f.addRow(self.summary)
        f.addRow(self._note(
            "Khoảng cách tối thiểu khi đường khô ráo (Bộ GTVT): 60 km/h: 35 m; trên 60–80 km/h: 55 m; "
            "trên 80–100 km/h: 70 m; trên 100–120 km/h: 100 m. Khi mưa, sương mù, đường trơn... "
            "phần mềm tự tăng khoảng cách theo điều kiện đã chọn."))
        return w

    def _assistant_tab(self, api_key: str) -> QWidget:
        s = self.cfg.assistant
        w = QWidget()
        f = QFormLayout(w)
        self.use_cloud = QCheckBox("Dùng Claude qua Internet thay cho trợ lý offline (trả phí, cần API key)")
        self.use_cloud.setChecked(s.use_cloud)
        self.model_name = _combo(ASSISTANT_MODELS, s.model)
        self.api_key = QLineEdit(api_key)
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("Để trống nếu đã đặt biến môi trường ANTHROPIC_API_KEY")
        self.use_cloud.toggled.connect(self.model_name.setEnabled)
        self.use_cloud.toggled.connect(self.api_key.setEnabled)
        self.model_name.setEnabled(s.use_cloud)
        self.api_key.setEnabled(s.use_cloud)
        f.addRow(self.use_cloud)
        f.addRow("Mô hình:", self.model_name)
        f.addRow("API key:", self.api_key)
        f.addRow(self._note(
            "Mặc định dùng trợ lý offline: miễn phí, không cần Internet, hiểu các câu mô tả thời tiết, "
            "mặt đường, tầm nhìn, tốc độ, ban đêm, chở nặng, mệt mỏi (gõ có dấu hoặc không dấu).\n"
            "Tùy chọn Claude hiểu câu tự do tốt hơn nhưng là dịch vụ trả phí: Claude Haiku 4.5 rẻ nhất, "
            "mỗi lần hỏi khoảng 0,005 USD (~100–200 đồng); API key tạo tại console.anthropic.com và cần "
            "nạp tiền trước. Khi mất mạng hoặc key lỗi, trợ lý tự quay về chế độ offline. "
            "API key chỉ được giữ trong phiên làm việc, không ghi ra file."))
        return w

    def _advanced_tab(self) -> QWidget:
        m, p, a = self.cfg.model, self.cfg.policy, self.cfg.alert
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.addWidget(self._note("Chỉ thay đổi khi hiểu rõ ý nghĩa của thông số. Rê chuột lên từng ô "
                                 "để xem giải thích."))

        # --- Mô hình nhận diện ---
        box = QGroupBox("Mô hình nhận diện xe (YOLOv11)")
        f = QFormLayout(box)
        row = QHBoxLayout()
        self.weights = QLineEdit(m.weights)
        browse = QPushButton("…")
        browse.setFixedWidth(36)
        browse.clicked.connect(self._browse_weights)
        row.addWidget(self.weights)
        row.addWidget(browse)
        self.conf = _dspin(m.confidence, 0.05, 0.95, 0.05, tip=(
            "Mô hình phải chắc chắn ít nhất bao nhiêu mới tính là có xe. "
            "Thấp: bắt được nhiều xe hơn nhưng dễ nhận nhầm; cao: ít nhầm nhưng dễ sót xe"))
        self.iou = _dspin(m.iou, 0.1, 0.9, 0.05, tip=(
            "Hai khung chồng lên nhau nhiều hơn mức này sẽ được gộp thành một xe (NMS)"))
        self.imgsz = _combo(IMGSZ_CHOICES, m.imgsz)
        self.imgsz.setToolTip("Ảnh lớn hơn giúp nhận ra xe ở xa tốt hơn nhưng xử lý chậm hơn")
        self.device = _combo(DEVICE_CHOICES, m.device)
        self.detect_every = QSpinBox()
        self.detect_every.setRange(0, 6)
        self.detect_every.setSpecialValueText("Tự động")
        self.detect_every.setSuffix(" khung")
        self.detect_every.setValue(m.detect_every)
        self.detect_every.setToolTip(
            "Nhận diện thưa, bám vết dày: chạy YOLO mỗi N khung, các khung giữa đo lại vị trí xe bằng so khớp "
            "mẫu (nhanh hơn hàng chục lần). Tự động: chọn N để YOLO chiếm không quá nửa thời gian một khung "
            "(máy có card đồ họa thường là mọi khung). 1 = YOLO mọi khung.")
        f.addRow("File mô hình đã huấn luyện:", row)
        f.addRow("Độ chắc chắn tối thiểu:", self.conf)
        f.addRow("Ngưỡng gộp khung trùng (IoU):", self.iou)
        f.addRow("Kích thước ảnh xử lý:", self.imgsz)
        f.addRow("Thiết bị xử lý:", self.device)
        f.addRow("Chạy YOLO mỗi:", self.detect_every)
        f.addRow(self._note("Đổi mô hình/thiết bị có hiệu lực ở lần bấm Bắt đầu tiếp theo."))
        lay.addWidget(box)

        # --- Công thức ngưỡng ---
        box = QGroupBox("Cách tính khoảng cách an toàn")
        f = QFormLayout(box)
        self.weather = _dspin(p.weather_factor, 1.0, 3.0, 0.05, tip=(
            "Khoảng cách theo quy định được nhân với hệ số này. Đường khô = 1,00; mưa, trơn... lớn hơn. "
            "Tự điền khi chọn thời tiết / mặt đường"))
        self.road_mu = _dspin(p.road_mu, 0.1, 0.9, 0.05, tip=(
            "Hệ số bám của lốp với mặt đường: khô ≈ 0,7; ướt ≈ 0,5; đọng nước ≈ 0,35. "
            "Dùng để tính quãng đường phanh"))
        self.danger_ratio = _dspin(p.danger_ratio, 0.3, 0.8, 0.05, tip=(
            "Ngưỡng NGUY HIỂM = ngưỡng CẢNH BÁO × tỷ lệ này. Ví dụ 0,50: cảnh báo dưới 70 m "
            "thì nguy hiểm dưới 35 m"))
        self.min_dist = _dspin(p.min_distance_m, 3, 20, 0.5, 1, " m",
                               "Dù chạy chậm, xe trước gần hơn khoảng này luôn bị coi là nguy hiểm")
        self.ttc_w = _dspin(p.ttc_warning_s, 2, 8, 0.5, 1, " giây", (
            "Thời gian đến va chạm (TTC): nếu giữ nguyên tốc độ mà sẽ đâm vào xe trước "
            "sau ít hơn số giây này thì CẢNH BÁO"))
        self.ttc_d = _dspin(p.ttc_danger_s, 1, 4, 0.5, 1, " giây",
                            "Thời gian đến va chạm ít hơn số giây này thì báo NGUY HIỂM")
        self.legal = QCheckBox("Áp dụng bảng khoảng cách tối thiểu của Bộ GTVT (từ 60 km/h)")
        self.legal.setToolTip("Bỏ chọn: mọi tốc độ đều tính theo quy tắc giãn cách thời gian, "
                              "ngưỡng theo dải tốc độ không còn tác dụng")
        self.legal.setChecked(p.use_legal_table)
        f.addRow("Hệ số theo điều kiện đường:", self.weather)
        f.addRow("Hệ số bám mặt đường:", self.road_mu)
        f.addRow("Tỷ lệ ngưỡng nguy hiểm:", self.danger_ratio)
        f.addRow("Khoảng cách luôn nguy hiểm:", self.min_dist)
        f.addRow("Cảnh báo khi sắp va chạm sau:", self.ttc_w)
        f.addRow("Nguy hiểm khi sắp va chạm sau:", self.ttc_d)
        f.addRow(self.legal)
        lay.addWidget(box)

        # --- Chống nhiễu cảnh báo ---
        box = QGroupBox("Chống báo nhầm")
        f = QFormLayout(box)
        self.escalate = _dspin(a.escalate_seconds, 0, 1, 0.05, 2, " giây",
                               "Chỉ báo khi tình huống nguy hiểm kéo dài liên tục ngần này giây, "
                               "tránh báo nhầm do nhận diện chập chờn")
        self.hold = _dspin(a.hold_seconds, 0, 5, 0.1, 1, " giây",
                           "Sau khi hết nguy hiểm, giữ cảnh báo thêm một lúc để không nhấp nháy liên tục")
        self.realtime = QCheckBox("Bỏ bớt khung hình khi máy xử lý chậm (để video chạy đúng thời gian thực)")
        self.realtime.setChecked(self.cfg.realtime_playback)
        f.addRow("Xác nhận qua:", self.escalate)
        f.addRow("Giữ cảnh báo thêm:", self.hold)
        f.addRow(self.realtime)
        lay.addWidget(box)

        reset = QPushButton("Khôi phục mặc định phần nâng cao")
        reset.setIcon(icon("restart_alt_rounded", "text", 18))
        reset.clicked.connect(self._reset_advanced)
        lay.addWidget(reset, 0, Qt.AlignmentFlag.AlignLeft)
        lay.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(body)
        return scroll

    # ------------------------------------------------------------------

    @staticmethod
    def _note(text):
        lbl = QLabel(text)
        lbl.setObjectName("muted")
        lbl.setWordWrap(True)
        return lbl

    def _preview_sound(self, level: str):
        from adas.alert.engine import AlertManager
        if not hasattr(self, "_alert"):
            self._alert = AlertManager(self.cfg.alert)
        if not self._alert.preview(level):
            QMessageBox.warning(self, "Âm thanh", "Không phát được âm thanh (không có thiết bị âm thanh).")

    def _apply_preset(self):
        key = self.preset.currentData()
        if not key:
            return
        p = condition_policy(key, visibility_m=100.0 if key == "fog" else 0.0, base=self.cfg.policy)
        self.weather.setValue(p.weather_factor)
        self.road_mu.setValue(p.road_mu)
        self.visibility.setValue(p.visibility_m)
        self.ttc_w.setValue(p.ttc_warning_s)
        self.ttc_d.setValue(p.ttc_danger_s)
        self.legal.setChecked(True)
        self.condition.setText(p.condition)

    def _reset_advanced(self):
        m, p, a = ModelConfig(), SafetyPolicy(), AlertConfig()
        self.weights.setText(m.weights)
        self.conf.setValue(m.confidence)
        self.iou.setValue(m.iou)
        self.imgsz.setCurrentIndex(self.imgsz.findData(m.imgsz))
        self.device.setCurrentIndex(self.device.findData(m.device))
        self.detect_every.setValue(m.detect_every)
        self.weather.setValue(p.weather_factor)
        self.road_mu.setValue(p.road_mu)
        self.danger_ratio.setValue(p.danger_ratio)
        self.min_dist.setValue(p.min_distance_m)
        self.ttc_w.setValue(p.ttc_warning_s)
        self.ttc_d.setValue(p.ttc_danger_s)
        self.legal.setChecked(p.use_legal_table)
        self.escalate.setValue(a.escalate_seconds)
        self.hold.setValue(a.hold_seconds)
        self.realtime.setChecked(True)

    def _reset_bands(self):
        self.time_gap.setValue(SafetyPolicy().time_gap_s)
        for spin, (_, legal) in zip(self.band_spins, LEGAL_GAP_TABLE):
            spin.setValue(legal)

    def _on_legal_toggled(self, on: bool):
        for spin in self.band_spins:
            spin.setEnabled(on)

    def _browse_weights(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn file mô hình", "", "PyTorch (*.pt);;ONNX (*.onnx)")
        if path:
            self.weights.setText(path)

    def _fill_policy(self, p: SafetyPolicy) -> SafetyPolicy:
        p.time_gap_s = self.time_gap.value()
        p.band_gaps_m = [s.value() for s in self.band_spins]
        p.weather_factor = self.weather.value()
        p.danger_ratio = self.danger_ratio.value()
        p.min_distance_m = self.min_dist.value()
        p.ttc_warning_s = self.ttc_w.value()
        p.ttc_danger_s = min(self.ttc_d.value(), self.ttc_w.value() - 0.5)
        p.use_legal_table = self.legal.isChecked()
        p.road_mu = self.road_mu.value()
        p.visibility_m = self.visibility.value()
        p.condition = self.condition.text().strip() or p.condition
        return p

    def _update_summary(self):
        """Xem trước ngưỡng ở tốc độ hiện tại với các giá trị đang chỉnh."""
        speed = self.cfg.speed_kmh
        policy = self._fill_policy(copy.deepcopy(self.cfg.policy))
        for label, v in zip(self.band_applied, [50] + [vmax for vmax, _ in LEGAL_GAP_TABLE]):
            t = compute_thresholds(v, policy)
            label.setText(f"{'Ở 50 km/h: ' if v < 60 else ''}"
                          f"<span style='color:{C['warning']}'>cảnh báo &lt; {int(t.safe_m + 0.5)} m</span> · "
                          f"<span style='color:{C['danger']}'>nguy hiểm &lt; {int(t.danger_m + 0.5)} m</span>")
        thr = compute_thresholds(speed, policy)
        text = (f"Ở tốc độ {speed:.0f} km/h: <span style='color:{C['warning']}'>cảnh báo khi xe trước gần hơn "
                f"<b>{thr.safe_m:.0f} m</b></span>, <span style='color:{C['danger']}'>nguy hiểm khi gần hơn "
                f"<b>{thr.danger_m:.0f} m</b></span>.")
        if thr.recommended_speed_kmh is not None:
            text += f"<br>Với tầm nhìn này nên chạy không quá <b>{thr.recommended_speed_kmh:.0f} km/h</b>."
        self.summary.setText(text)

    def _accept(self):
        c = self.cfg
        c.model.weights = self.weights.text().strip()
        c.model.confidence = self.conf.value()
        c.model.iou = self.iou.value()
        c.model.imgsz = int(self.imgsz.currentData())
        c.model.device = str(self.device.currentData())
        c.model.detect_every = self.detect_every.value()
        c.model.enabled_classes = [n for n, cb in self.class_checks.items() if cb.isChecked()] or ["car"]
        self._fill_policy(c.policy)
        c.alert.sound_enabled = self.sound.isChecked()
        c.alert.only_ego_lane = self.only_lane.isChecked()
        c.alert.auto_lane = self.auto_lane.isChecked()
        c.auto_speed = self.auto_speed.isChecked()
        c.auto_calib = self.auto_calib.isChecked()
        c.alert.escalate_seconds = self.escalate.value()
        c.alert.hold_seconds = self.hold.value()
        c.realtime_playback = self.realtime.isChecked()
        c.assistant.use_cloud = self.use_cloud.isChecked()
        c.assistant.model = self.model_name.currentData() or DEFAULT_ASSISTANT_MODEL
        self.api_key_value = self.api_key.text().strip()
        self.accept()
