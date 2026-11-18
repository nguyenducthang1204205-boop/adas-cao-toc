"""Cột phải: thẻ trạng thái + đồng hồ khoảng cách, tốc độ xe chủ, điều kiện đường."""

import html
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget,
)

from adas.alert.thresholds import LEGAL_GAP_TABLE, MODIFIERS, ROAD_CONDITIONS, compute_thresholds, threshold_basis
from adas.config import SafetyPolicy
from adas.formatting import vn, vn_factor
from adas.pipeline import STAGE_LABELS, STAGES
from gui.styles import C, LEVEL_STYLE
from gui.theme import CONDITION_ICONS
from gui.widgets.common import Card, icon_html, muted, repolish, set_icon

SPEED_STEPS = [(int(v), gap) for v, gap in LEGAL_GAP_TABLE]   # các nấc tốc độ của SpeedPanel


class DistanceGauge(QWidget):
    """Thước khoảng cách (giống GapGauge của mobile): đỏ / hổ phách / xanh theo 2 ngưỡng, chấm trắng = xe phía trước."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.safe_m: Optional[float] = None
        self.danger_m: Optional[float] = None
        self.value: Optional[float] = None
        self.setToolTip("Vị trí xe phía trước (chấm trắng) so với ngưỡng nguy hiểm (đỏ) và cảnh báo (hổ phách)")

    def set_values(self, safe_m, danger_m, value):
        self.safe_m, self.danger_m, self.value = safe_m, danger_m, value
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        top, bar_h = 4.0, 6.0
        if not self.safe_m:
            p.setBrush(QColor(C["surface2"]))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(0, top, w, bar_h), 3, 3)
            return
        d = self.value
        vmax = max(self.safe_m * 1.6, (d or 0) * 1.1)
        x = lambda v: min(max(v / vmax, 0.0), 1.0) * w   # noqa: E731
        segs = [(0, self.danger_m, C["danger"]), (self.danger_m, self.safe_m, C["warning"]),
                (self.safe_m, vmax, C["safe"])]
        p.setPen(Qt.PenStyle.NoPen)
        for i, (a, b, col) in enumerate(segs):
            c = QColor(col)
            c.setAlphaF(0.85 if d is not None else 0.35)
            p.setBrush(c)
            x0 = x(a) + (0 if i == 0 else 1.5)
            x1 = x(b) - (0 if i == 2 else 1.5)
            p.drawRoundedRect(QRectF(x0, top, max(0.0, x1 - x0), bar_h), 2, 2)
        p.setPen(QColor(C["muted"]))
        f = self.font()
        f.setPixelSize(11)
        f.setWeight(f.Weight.DemiBold)
        p.setFont(f)
        fm = p.fontMetrics()
        for v in (self.danger_m, self.safe_m):
            label = f"{v:.0f}"
            tw = fm.horizontalAdvance(label)
            p.drawText(QPointF(min(max(x(v) - tw / 2, 0), w - tw), top + bar_h + 5 + fm.ascent()), label)
        if d is not None:
            c = QPointF(x(d), top + bar_h / 2)
            p.setBrush(QColor(0, 0, 0, 128))
            p.drawEllipse(c, 8, 8)
            p.setBrush(QColor("#ffffff"))
            p.drawEllipse(c, 6.5, 6.5)


class StatusCard(Card):
    """Xe phía trước (giống DistanceCluster của mobile): số lớn theo màu rủi ro, thước, va chạm sau / tiếp cận."""

    def __init__(self, parent=None):
        super().__init__("Xe phía trước", parent, icon_name="directions_car_outlined")
        self.pill = QLabel()
        self.pill.setObjectName("levelPill")
        self.title_row.addWidget(self.pill)
        self.distance = QLabel()
        self.distance.setObjectName("bigValue")
        self.distance.setTextFormat(Qt.TextFormat.RichText)
        self.lead_info = muted("Chưa chạy giám sát")
        self.lead_info.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        top = QHBoxLayout()
        top.setSpacing(12)
        top.addWidget(self.distance)
        top.addWidget(self.lead_info, 1)
        self.body.addLayout(top)
        self.gauge = DistanceGauge()
        self.body.addWidget(self.gauge)
        metrics = QFrame()
        metrics.setObjectName("metric")
        grid = QGridLayout(metrics)
        grid.setContentsMargins(0, 2, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(0)
        self.ttc = self._metric(grid, 0, "Va chạm sau",
                                "TTC: nếu giữ nguyên tốc độ, sau bao nhiêu giây sẽ chạm xe phía trước")
        self.closing = self._metric(grid, 1, "Tiếp cận", "Tốc độ tiến lại gần xe phía trước")
        self.count = self._metric(grid, 2, "Xe trong khung", "Số phương tiện nhận diện được trong khung hình")
        self.body.addWidget(metrics)
        self._level = "idle"
        self._set_distance(None)
        self.set_level("idle")

    @staticmethod
    def _metric(grid, col, label, tip):
        lbl = QLabel(label)
        lbl.setObjectName("metricLabel")
        lbl.setToolTip(tip)
        v = QLabel("—")
        v.setObjectName("metricValue")
        v.setToolTip(tip)
        grid.addWidget(lbl, 0, col)
        grid.addWidget(v, 1, col)
        return v

    def _set_distance(self, d: Optional[float], risk: str = "info"):
        if d is None:
            self.distance.setText(f"<span style='color:{C['muted']}'>—</span>")
            return
        col = C.get(risk, C["text"]) if risk in ("safe", "warning", "danger") else C["text"]
        self.distance.setText(f"<span style='color:{col}'>{vn(d)}</span>"
                              f"<span style='color:{C['muted']}; font-size:15pt; font-weight:600'> m</span>")

    def set_level(self, level: str):
        bg, fg, text, _, icon_name = LEVEL_STYLE.get(level, LEVEL_STYLE["idle"])
        self.pill.setText(f"{icon_html(icon_name, fg, 15)}&nbsp;{text}")
        self.pill.setStyleSheet(f"background:{bg}; color:{fg};")
        self._level = level
        if self.property("level") != level:
            self.setProperty("level", level)
            repolish(self)

    def update_stats(self, s: dict):
        self.set_level(s["level"])
        self.count.setText(str(s["n_vehicles"]))
        if s["lead_distance"] is not None:
            self._set_distance(s["lead_distance"], s.get("lead_risk", s["level"]))
            tid = f" #{s['lead_id']}" if s["lead_id"] is not None else ""
            method = "đo bằng IPM" if s["lead_method"] == "IPM" else "ở xa, ngoài tầm đo"
            self.lead_info.setText(f"{s['lead_class']}{tid} cùng làn · {method}")
            ttc = s["lead_ttc"]
            self.ttc.setText(f"{vn(ttc)} s" if ttc is not None and ttc < 60 else "—")
            cl = s["lead_closing"]
            self.closing.setText("—" if cl is None or abs(cl) < 0.5 else
                                 (f"{cl * 3.6:.0f} km/h" if cl > 0 else "Xa dần"))
            warn = ttc is not None and ttc < 4
            self.ttc.setStyleSheet(f"color:{C['warning']}" if warn else "")
        else:
            self._set_distance(None)
            self.lead_info.setText("Không có xe cùng làn phía trước")
            self.ttc.setText("—")
            self.closing.setText("—")
            self.ttc.setStyleSheet("")
        self.gauge.set_values(s.get("safe_m"), s.get("danger_m"), s["lead_distance"])

    def reset(self, text: str = "Chưa chạy giám sát"):
        self.set_level("idle")
        self._set_distance(None)
        self.lead_info.setText(text)
        for v in (self.ttc, self.closing, self.count):
            v.setText("—")
        self.gauge.set_values(None, None, None)


def perf_text(s: dict) -> str:
    """Thời gian từng tầng theo kiến trúc: Video Stream -> YOLOv11 -> IPM -> Alert Engine -> GUI."""
    tm = s.get("timings_ms", {})
    labels = dict(STAGE_LABELS)
    if not s.get("detected", True):          # khung chỉ bám vết (YOLO chạy thưa)
        labels["detection"] = "Bám vết"
    chain = " › ".join(f"{labels[k]} {tm.get(k, 0):.1f}" for k in STAGES)
    stride = s.get("stride", 1)
    return f"FPS {s['fps']:.1f} · Luồng xử lý (ms): {chain}" + (f" · YOLO mỗi {stride} khung" if stride > 1 else "")


class SpeedPanel(Card):
    """
    Tốc độ xe chủ + ngưỡng an toàn tương ứng. Tự đo từ video (adas/distance/ego_speed.py) khi bật; các nấc của bảng
    quy định là tốc độ chọn tay - dùng khi tắt tự đo hoặc chưa đo được. Bấm một nấc = chuyển sang chọn tay.
    """
    speed_changed = Signal(float)      # nấc chọn tay
    auto_changed = Signal(bool)        # bật/tắt tự đo

    def __init__(self, speed: float, parent=None):
        super().__init__("Tốc độ xe của bạn", parent, icon_name="speed_outlined")
        self.auto = QCheckBox("Tự đo từ video")
        self.auto.setToolTip("Đo tốc độ từ chuyển động của vạch kẻ đứt trên mặt đường (không cần GPS).\n"
                             "Chính xác khi camera đã căn chỉnh đúng. Chưa đo được thì dùng nấc chọn tay")
        self.auto.toggled.connect(self._on_auto)
        self.title_row.addWidget(self.auto)
        self.measured_label = QLabel()
        self.measured_label.setWordWrap(True)
        self.body.addWidget(self.measured_label)
        self._measured: Optional[float] = None
        row = QHBoxLayout()
        row.setSpacing(6)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for i, (v, gap) in enumerate(SPEED_STEPS):
            b = QPushButton(f"{v} km/h" if i == 0 else f"≤ {v} km/h")
            b.setObjectName("speedStep")
            b.setCheckable(True)
            b.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)   # chia đều bề rộng thẻ
            b.setMinimumHeight(32)
            rng = f"{v} km/h" if i == 0 else f"trên {SPEED_STEPS[i - 1][0]} đến {v} km/h"
            b.setToolTip(f"Tốc độ {rng}: quy định giữ tối thiểu {gap:.0f} m khi đường khô ráo")
            self.group.addButton(b, i)
            row.addWidget(b)
        self.body.addLayout(row)
        self.thr_label = QLabel()
        self.thr_label.setWordWrap(True)
        self.body.addWidget(self.thr_label)
        self.basis_label = muted()
        self.body.addWidget(self.basis_label)

        self.group.idClicked.connect(self._on_index)
        self._policy = SafetyPolicy()
        self.set_speed(speed)

    @staticmethod
    def snap(v: float) -> int:
        """Chỉ số nấc chứa tốc độ v: (60, 80] → nấc 80 ... Dưới 60 về nấc 60, trên 120 về nấc 120."""
        for i, (vmax, _) in enumerate(SPEED_STEPS):
            if v <= vmax:
                return i
        return len(SPEED_STEPS) - 1

    def index(self) -> int:
        return max(self.group.checkedId(), 0)

    def speed(self) -> float:
        return float(SPEED_STEPS[self.index()][0])

    def effective_speed(self) -> float:
        """Tốc độ đang dùng để tính ngưỡng: số đo từ video nếu có, ngược lại nấc chọn tay."""
        if self.auto.isChecked() and self._measured is not None:
            return self._measured
        return self.speed()

    def _on_index(self, _i: int):
        if self.auto.isChecked():
            self.auto.setChecked(False)          # người dùng chủ động chọn tay
        self.refresh()
        self.speed_changed.emit(self.speed())

    def _on_auto(self, on: bool):
        self.refresh()
        self.auto_changed.emit(on)

    def set_auto(self, on: bool):
        self.auto.blockSignals(True)
        self.auto.setChecked(on)
        self.auto.blockSignals(False)
        self.refresh()

    def set_measured(self, v: Optional[float]):
        """Số đo từ luồng xử lý (None: chưa đo được / không chạy)."""
        if v is None and self._measured is None:
            return
        self._measured = v
        self.refresh()

    def set_speed(self, v: float) -> float:
        """Chọn nấc chứa v (không phát tín hiệu). Trả về tốc độ của nấc đó."""
        self.group.button(self.snap(v)).setChecked(True)
        self.refresh()
        return self.speed()

    def set_policy(self, policy: SafetyPolicy):
        self._policy = policy
        self.refresh()

    def refresh(self):
        p = self._policy
        if not self.auto.isChecked():
            self.measured_label.hide()
        elif self._measured is not None:
            self.measured_label.setText(
                f"<span style='font-size:20pt; font-weight:700'>{self._measured:.0f}</span>"
                f"<span style='color:{C['muted']}; font-size:11pt; font-weight:600'> km/h</span>"
                f"&nbsp;&nbsp;{icon_html('circle_rounded', 'safe', 9)}"
                f"<span style='color:{C['muted']}'>&nbsp;đo từ vạch kẻ đường</span>")
            self.measured_label.show()
        else:
            self.measured_label.setText(f"{icon_html('circle_rounded', 'warning', 9)}<span style='color:"
                                        f"{C['muted']}'>&nbsp;Đang chờ đo (cần thấy vạch kẻ đứt) - tạm dùng nấc "
                                        f"{self.speed():.0f} km/h</span>")
            self.measured_label.show()
        measuring = self.auto.isChecked() and self._measured is not None
        for b in self.group.buttons():
            if b.property("fallback") != measuring:
                b.setProperty("fallback", measuring)
                note = "\nĐang dùng tốc độ đo từ video - bấm để chọn tay" if measuring else ""
                b.setToolTip(b.toolTip().split("\n")[0] + note)
                repolish(b)
        thr = compute_thresholds(self.effective_speed(), p)
        basis = threshold_basis(thr, p)
        warn = []
        if thr.over_speed_limit:
            warn.append("Vượt tốc độ tối đa 120 km/h trên cao tốc!")
        if thr.recommended_speed_kmh is not None:
            too_fast = thr.speed_kmh > thr.recommended_speed_kmh
            warn.append(f"Tầm nhìn {p.visibility_m:.0f} m: nên chạy ≤ {thr.recommended_speed_kmh:.0f} km/h"
                        + (" (đang quá nhanh)" if too_fast else ""))
        warn_html = "".join(f"<br>{icon_html('warning_rounded', 'danger', 14)}"
                            f"<span style='color:{C['danger']}'>&nbsp;{w}</span>" for w in warn)
        self.thr_label.setText(
            f"<span style='color:{C['muted']}; font-size:8.5pt; font-weight:700; letter-spacing:1.4px'>"
            f"GIỮ TỐI THIỂU</span>&nbsp;&nbsp;"
            f"<span style='font-size:20pt; font-weight:700'>{thr.safe_m:.0f}</span>"
            f"<span style='color:{C['muted']}; font-size:11pt; font-weight:600'> m</span>"
            f"&nbsp;&nbsp;&nbsp;{icon_html('circle_rounded', 'danger', 9)}"
            f"<span style='color:{C['text']}'>&nbsp;Nguy hiểm dưới {thr.danger_m:.0f} m</span>{warn_html}")
        self.basis_label.setText(basis)


class ConditionPanel(Card):
    """Điều kiện đường hiện tại + nút chọn nhanh (gửi qua Trợ lý AI để điều chỉnh ngưỡng)."""
    preset_requested = Signal(str)
    reset_requested = Signal()

    QUICK = [   # (khóa điều kiện, nhãn, câu gửi Trợ lý AI)
        ("dry", "Khô ráo", "Đường khô ráo, trời nắng, tầm nhìn tốt"),
        ("wet", "Mưa nhỏ", "Trời mưa nhỏ, mặt đường ướt"),
        ("heavy_rain", "Mưa to", "Trời đang mưa to, mặt đường đọng nước"),
        ("fog", "Sương mù", "Có sương mù dày, tầm nhìn khoảng 100 m"),
        ("slippery", "Trơn trượt", "Mặt đường trơn trượt do dầu loang"),
        ("night", "Ban đêm", "Đang lái xe ban đêm trên cao tốc"),
        ("heavy_vehicle", "Chở nặng", "Tôi lái xe tải đang chở nặng"),
        ("tired", "Mệt mỏi", "Tôi đã lái lâu và cảm thấy buồn ngủ"),
    ]

    def __init__(self, parent=None):
        super().__init__("Điều kiện đường", parent, icon_name="tune_outlined")
        reset = QPushButton("Mặc định")
        reset.setObjectName("link")
        set_icon(reset, "restart_alt_rounded", "accent", 16)
        reset.setToolTip("Khôi phục tham số an toàn mặc định (đường khô ráo, tầm nhìn tốt)")
        reset.clicked.connect(self.reset_requested.emit)
        self.title_row.addWidget(reset)
        self.current = QLabel()
        self.current.setWordWrap(True)
        self.body.addWidget(self.current)
        grid = QGridLayout()
        grid.setSpacing(6)
        self.chips = {}
        for i, (key, label, text) in enumerate(self.QUICK):
            b = QPushButton(label)
            b.setObjectName("chip")
            set_icon(b, CONDITION_ICONS[key], "accent", 17)
            b.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)   # chia đều bề rộng thẻ
            b.setMinimumWidth(60)
            b.setMinimumHeight(30)
            b.setToolTip(f"Gửi cho Trợ lý AI: “{text}”")
            b.clicked.connect(lambda _=False, t=text: self.preset_requested.emit(t))
            grid.addWidget(b, i // 4, i % 4)
            self.chips[key] = b
        self.body.addLayout(grid)

    def set_policy(self, p: SafetyPolicy):
        extra = f" · khoảng cách × {vn_factor(p.weather_factor)}" if p.weather_factor > 1.0 else ""
        vis = f" · tầm nhìn {p.visibility_m:.0f} m" if p.visibility_m > 0 else ""
        self.current.setText(f"<b>{html.escape(p.condition)}</b>"
                             f"<span style='color:{C['muted']}'>{extra}{vis}</span>")
        cond = p.condition.lower()
        for key, b in self.chips.items():
            name = ROAD_CONDITIONS[key].name if key in ROAD_CONDITIONS else MODIFIERS[key][0]
            on = name.lower() in cond
            if b.property("selected") != on:
                b.setProperty("selected", on)
                repolish(b)
