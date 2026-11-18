"""
Vẽ lớp hiển thị lên khung hình và tạo ảnh Bird's-Eye View - cùng thiết kế "Night Drive" với bản mobile
(app Android: ui/drive/Overlay.kt, Hud.kt):
  - hành lang làn trung tính; CHỈ khoảng trống tới xe phía trước được tô theo mức rủi ro của xe đó;
  - vạch ngưỡng nét đứt, nhãn nguy hiểm bên trái / cảnh báo bên phải (không bao giờ chồng nhau);
  - chevron dẫn tới xe phía trước; hộp xe dạng góc ngoặc; nhãn viên thuốc, nhãn xe phía trước ưu tiên chỗ;
  - banner trạng thái giữa trên + viền phát sáng quanh khung khi CẢNH BÁO / NGUY HIỂM.

Dùng QPainter (thay cho cv2.putText) để hiển thị được tiếng Việt có dấu; vẽ trên QImage an toàn trong
luồng xử lý nền. Font Be Vietnam Pro + Material Icons nạp từ assets/fonts (ensure_fonts).
"""

import math
import time
from typing import List, Optional

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPen, QPolygonF

from adas.config import AppConfig, CLASS_LABELS_VI
from adas.distance.ipm import GroundPlaneMapper
from adas.formatting import vn
from adas.pipeline import FrameResult
from gui.rendering.qt import bgr_to_qimage, font, icon_font, qcolor, risk_color, risk_fill
from gui.theme import C, LEVEL_STYLE, icon_char

VEHICLE_SIZE_M = {  # (rộng, dài) để vẽ trên BEV
    "car": (1.8, 4.5), "truck": (2.5, 10.0), "bus": (2.5, 12.0),
    "Jeepney": (2.0, 6.0), "motorcycle": (0.8, 2.0),
}


def vehicle_label(class_name: str) -> str:
    return CLASS_LABELS_VI.get(class_name, class_name)


# ----------------------------------------------------------------------
# Lớp phủ trên khung hình camera
# ----------------------------------------------------------------------

def render_overlay(frame: np.ndarray, result: FrameResult, mapper: GroundPlaneMapper,
                   cfg: AppConfig, fps: float, info: bool = False) -> QImage:
    """info=True: thêm khung thông số (tốc độ, ngưỡng, làn, FPS) - dùng khi ghi video, vì video ghi ra
    không có cột thông tin bên phải của cửa sổ."""
    img = bgr_to_qimage(frame)
    w, h = img.width(), img.height()
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    unit = h / 720.0  # kích thước thiết kế ở khung 720p; cửa sổ phóng ảnh lên gần bằng kích thước đó

    labels: List[QRectF] = []
    if result.thresholds is not None:
        _draw_corridor(p, mapper, cfg, result, unit)
    lead = result.lead
    if lead is not None:
        _draw_vehicle(p, lead, True, unit, labels)        # nhãn xe phía trước được ưu tiên chỗ
    for vs in reversed(result.vehicles):
        if vs is not lead:
            _draw_vehicle(p, vs, False, unit, labels)
    _draw_edge_glow(p, w, h, result.level, unit)
    _draw_banner(p, w, result.level, len(result.vehicles), unit)
    if info:
        _draw_info(p, result, cfg, fps, unit)
    p.end()
    return img


def lane_edges(cfg: AppConfig, lane, ys):
    """Mép trái/phải (m) của làn xe chủ tại các khoảng cách ys: theo vạch kẻ nhận diện được,
    hoặc hành lang cố định ±lane_half_width_m khi không có."""
    ys = np.asarray(ys, dtype=np.float64)
    if lane is not None:
        return lane.x_left(ys), lane.x_right(ys)
    hw = cfg.calibration.lane_half_width_m
    return np.full_like(ys, -hw), np.full_like(ys, hw)


def _ground(mapper, x, y) -> QPointF:
    (u, v), = mapper.ground_to_image(np.array([[x, y]], dtype=np.float64))
    return QPointF(float(u), float(v))


def _band(mapper, cfg, lane, y0, y1) -> QPolygonF:
    ys = np.linspace(y0, y1, 14)
    xl, xr = lane_edges(cfg, lane, ys)
    left = mapper.ground_to_image(np.column_stack([xl, ys]))
    right = mapper.ground_to_image(np.column_stack([xr, ys]))
    return QPolygonF([QPointF(x, y) for x, y in np.vstack([left, right[::-1]])])


def _vertical_gradient(p0: QPointF, p1: QPointF, c0: QColor, c1: QColor) -> QLinearGradient:
    g = QLinearGradient(p0, p1)
    g.setColorAt(0, c0)
    g.setColorAt(1, c1)
    return g


def _draw_corridor(p: QPainter, mapper: GroundPlaneMapper, cfg: AppConfig, result: FrameResult, unit: float):
    thr, lane, lead = result.thresholds, result.lane, result.lead
    near = max(cfg.calibration.near_distance_m * 0.5, 2.5)
    far = min(thr.safe_m * 1.35, cfg.calibration.max_range_m)
    pn, pf = _ground(mapper, 0, near), _ground(mapper, 0, far)
    p.setPen(Qt.PenStyle.NoPen)

    # hành lang trung tính tới ngưỡng an toàn (không tô đỏ khi đang an toàn)
    p.setBrush(_vertical_gradient(pn, pf, QColor(255, 255, 255, 26), QColor(255, 255, 255, 0)))
    p.drawPolygon(_band(mapper, cfg, lane, near, far))

    # khoảng trống tới xe phía trước, tô theo mức rủi ro của chính xe đó
    has_gap = lead is not None and lead.method == "IPM" and lead.distance_m > near
    if has_gap:
        col = risk_color(lead.risk)
        p.setBrush(_vertical_gradient(pn, _ground(mapper, 0, lead.distance_m),
                                      QColor(col.red(), col.green(), col.blue(), 20),
                                      QColor(col.red(), col.green(), col.blue(), 97)))
        p.drawPolygon(_band(mapper, cfg, lane, near, lead.distance_m))

    # mép hành lang: vạch mảnh sáng, mờ dần về xa
    ys = np.linspace(near, far, 24)
    for xs in lane_edges(cfg, lane, ys):
        pts = mapper.ground_to_image(np.column_stack([xs, ys]))
        a, b = QPointF(*pts[0]), QPointF(*pts[-1])
        pen = QPen(_vertical_gradient(a, b, QColor(255, 255, 255, 166), QColor(255, 255, 255, 0)), 2 * unit)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawPolyline(QPolygonF([QPointF(x, y) for x, y in pts]))

    # vạch mốc ngưỡng: nhãn nguy hiểm bên trái, cảnh báo bên phải; không vẽ đè lên xe phía trước
    limit = lead.distance_m - 1.0 if has_gap else far
    for d, key, right in ((thr.danger_m, "danger", False), (thr.safe_m, "warning", True)):
        if not near < d < min(far, limit):
            continue
        (el,), (er,) = lane_edges(cfg, lane, [d])
        a, b = _ground(mapper, el, d), _ground(mapper, er, d)
        pen = QPen(qcolor(key, 0.9), 2 * unit, Qt.PenStyle.CustomDashLine)
        pen.setDashPattern([4, 3])
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(a, b)
        p.setFont(font(13 * unit, 700))
        fm = p.fontMetrics()
        text = f"{d:.0f} m"
        x = b.x() + 8 * unit if right else a.x() - 8 * unit - fm.horizontalAdvance(text)
        _shadow_text(p, QPointF(x, a.y() - 4 * unit if not right else b.y() - 4 * unit), text, qcolor(key), unit)

    # chevron dẫn tới xe phía trước
    if has_gap and lead.distance_m > near + 2:
        col = risk_color(lead.risk)
        for f in (0.3, 0.55, 0.8):
            y = near + (lead.distance_m - near) * f
            (el,), (er,) = lane_edges(cfg, lane, [y])
            mid, half = (el + er) / 2, (er - el) / 2
            pen = QPen(QColor(col.red(), col.green(), col.blue(), int(255 * (0.35 + 0.5 * f))), 3 * unit)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPolyline(QPolygonF([_ground(mapper, mid - half * 0.35, y), _ground(mapper, mid, y + 1.5),
                                      _ground(mapper, mid + half * 0.35, y)]))


def _shadow_text(p: QPainter, at: QPointF, text: str, color: QColor, unit: float) -> None:
    p.setPen(QColor(0, 0, 0, 170))
    p.drawText(at + QPointF(0, 1.2 * unit), text)
    p.setPen(color)
    p.drawText(at, text)


def _pill(p: QPainter, text: str, center_x: float, bottom_y: float, fill: QColor, fg: QColor,
          px: float, unit: float, labels: List[QRectF], avoid: bool) -> None:
    p.setFont(font(px * unit, 700))
    fm = p.fontMetrics()
    pad_h, pad_v = 9 * unit, 4 * unit
    w, h = fm.horizontalAdvance(text) + 2 * pad_h, fm.height() + 2 * pad_v
    r = QRectF(center_x - w / 2, max(0.0, bottom_y - h), w, h)
    if avoid and any(r.adjusted(-2, -2, 2, 2).intersects(o) for o in labels):
        return
    labels.append(r)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(fill)
    p.drawRoundedRect(r, h / 2, h / 2)
    p.setPen(fg)
    p.drawText(r, Qt.AlignmentFlag.AlignCenter, text)


def _draw_vehicle(p: QPainter, vs, is_lead: bool, unit: float, labels: List[QRectF]) -> None:
    x1, y1, x2, y2 = [float(v) for v in vs.det.bbox]
    rect = QRectF(x1, y1, x2 - x1, y2 - y1)
    out_of_lane = vs.risk == "info"
    color = risk_color(vs.risk) if is_lead else QColor(255, 255, 255, 115 if out_of_lane else 190)
    c = min(rect.width(), rect.height()) * 0.22 + 4 * unit
    if is_lead:   # quầng nhẹ trong hộp xe đang được theo dõi
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(color.red(), color.green(), color.blue(), 26))
        p.drawRoundedRect(rect, 6 * unit, 6 * unit)
    pen = QPen(color, (3 if is_lead else 1.6) * unit)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    for (ox, oy), dx, dy in (((x1, y1), 1, 1), ((x2, y1), -1, 1), ((x1, y2), 1, -1), ((x2, y2), -1, -1)):
        p.drawPolyline(QPolygonF([QPointF(ox, oy + dy * c), QPointF(ox, oy), QPointF(ox + dx * c, oy)]))
    if vs.method != "IPM":
        return
    if is_lead:
        text = f"{vn(vs.distance_m)} m"
        if vs.ttc_s is not None and vs.ttc_s < 15:
            text += f"  ·  {vn(vs.ttc_s)} s"
        fg = qcolor("on_warning") if vs.risk == "warning" else (
            qcolor("on_accent") if vs.risk == "safe" else QColor(255, 255, 255))
        _pill(p, text, rect.center().x(), y1 - 8 * unit, risk_fill(vs.risk), fg, 17, unit, labels, avoid=False)
    elif vs.distance_m < 90:
        _pill(p, f"{vehicle_label(vs.det.class_name)} {vs.distance_m:.0f} m", rect.center().x(), y1 - 6 * unit,
              QColor(12, 17, 23, 204), qcolor("text"), 13, unit, labels, avoid=True)


def _draw_edge_glow(p: QPainter, w: int, h: int, level: str, unit: float) -> None:
    """Viền phát sáng quanh khung - thấy được bằng thị giác ngoại vi. NGUY HIỂM: nhịp đập ~1,1 s."""
    if level not in ("warning", "danger"):
        return
    strength = 0.7
    if level == "danger":
        strength = 0.45 + 0.55 * (0.5 + 0.5 * math.sin(time.monotonic() * 2 * math.pi / 2.2))
    col = risk_color(level)
    c0 = QColor(col.red(), col.green(), col.blue(), int(255 * 0.55 * strength))
    c1 = QColor(col.red(), col.green(), col.blue(), 0)
    g = min(w, h) * 0.12
    p.setPen(Qt.PenStyle.NoPen)
    for rect, a, b in (
        (QRectF(0, 0, w, g), QPointF(0, 0), QPointF(0, g)),
        (QRectF(0, h - g, w, g), QPointF(0, h), QPointF(0, h - g)),
        (QRectF(0, 0, g, h), QPointF(0, 0), QPointF(g, 0)),
        (QRectF(w - g, 0, g, h), QPointF(w, 0), QPointF(w - g, 0)),
    ):
        p.setBrush(_vertical_gradient(a, b, c0, c1))
        p.drawRect(rect)


def _draw_banner(p: QPainter, w: int, level: str, n_vehicles: int, unit: float) -> None:
    """Banner giữa trên: CẢNH BÁO / NGUY HIỂM dạng viên thuốc đặc (biểu tượng + nhãn + câu ngắn)."""
    if level not in ("warning", "danger"):
        return
    fill, fg, label, msg, icon_name = LEVEL_STYLE[level]
    fill_c, fg_c = qcolor(fill), qcolor(fg)
    lf, mf, ic = font(19 * unit, 800), font(19 * unit, 600), icon_font(26 * unit)
    p.setFont(lf)
    lw = p.fontMetrics().horizontalAdvance(label) * 1.06 + 1.2 * unit * len(label)   # chữ giãn 1,2
    p.setFont(mf)
    mw = p.fontMetrics().horizontalAdvance(msg)
    gap, sep, iw = 12 * unit, 25 * unit, 26 * unit
    pad_h, h = 22 * unit, 50 * unit
    tw = pad_h * 2 + iw + gap + lw + sep + mw
    x, y = (w - tw) / 2, 16 * unit
    glow = risk_color(level)
    p.setPen(Qt.PenStyle.NoPen)
    for i in range(3, 0, -1):     # quầng sáng mềm quanh banner
        p.setBrush(QColor(glow.red(), glow.green(), glow.blue(), 18 * i))
        e = (4 - i) * 4 * unit
        p.drawRoundedRect(QRectF(x - e, y - e, tw + 2 * e, h + 2 * e), h / 2 + e, h / 2 + e)
    p.setBrush(fill_c)
    p.drawRoundedRect(QRectF(x, y, tw, h), h / 2, h / 2)
    p.setPen(fg_c)
    cx = x + pad_h
    p.setFont(ic)
    p.drawText(QRectF(cx, y, iw, h), Qt.AlignmentFlag.AlignCenter, icon_char(icon_name))
    cx += iw + gap
    lf.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.2 * unit)
    p.setFont(lf)
    p.drawText(QRectF(cx, y, lw, h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)
    cx += lw + sep / 2
    p.setPen(QPen(QColor(fg_c.red(), fg_c.green(), fg_c.blue(), 100), max(1.0, unit)))
    p.drawLine(QPointF(cx, y + h * 0.3), QPointF(cx, y + h * 0.7))
    cx += sep / 2
    p.setPen(fg_c)
    p.setFont(mf)
    p.drawText(QRectF(cx, y, mw + 4, h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, msg)


def _draw_info(p: QPainter, result: FrameResult, cfg: AppConfig, fps: float, unit: float) -> None:
    """Khung thông số kiểu kính mờ ở góc trái trên (chỉ khi ghi video)."""
    thr = result.thresholds
    lines = [f"Tốc độ {result.speed_kmh:.0f} km/h" + (" · đo từ video" if result.speed_measured else "")]
    if thr is not None:
        lines.append(f"Giữ tối thiểu {thr.safe_m:.0f} m · nguy hiểm dưới {thr.danger_m:.0f} m")
    lead = result.lead
    lines.append(f"Xe phía trước {vn(lead.distance_m)} m" if lead is not None else "Không có xe cùng làn")
    if result.lane is not None:
        lines.append(f"Làn rộng {vn(result.lane.width_m)} m theo vạch kẻ")
    lines.append(f"{fps:.0f} FPS · YOLO {result.yolo_ms or result.inference_ms:.0f} ms"
                 + (f" mỗi {result.stride} khung" if result.stride > 1 else ""))
    p.setFont(font(16 * unit, 500))
    fm = p.fontMetrics()
    m, pad = 16 * unit, 12 * unit
    w = max(fm.horizontalAdvance(s) for s in lines) + 2 * pad
    hgt = fm.height() * len(lines) + 2 * pad
    p.setPen(QPen(QColor(255, 255, 255, 26), unit))
    p.setBrush(qcolor(C["glass"]))
    p.drawRoundedRect(QRectF(m, m, w, hgt), 14 * unit, 14 * unit)
    for i, s in enumerate(lines):
        p.setPen(qcolor("text") if i in (0, 2) else qcolor("muted"))
        p.drawText(QPointF(m + pad, m + pad + fm.ascent() + i * fm.height()), s)


# ----------------------------------------------------------------------
# Bird's-Eye View
# ----------------------------------------------------------------------

def bev_range(safe_m: Optional[float], max_range_m: float) -> float:
    target = (safe_m or 40.0) * 1.3
    return float(min(max(math.ceil(target / 20.0) * 20.0, 60.0), max(60.0, max_range_m)))


def render_bev(frame: np.ndarray, result: FrameResult, mapper: GroundPlaneMapper,
               cfg: AppConfig, size=(300, 620)) -> QImage:
    bw, bh = size
    x_half, y_min = 10.0, -6.0
    thr = result.thresholds
    y_max = bev_range(thr.safe_m if thr else None, cfg.calibration.max_range_m)

    warped = mapper.warp_to_bev(frame, size, x_half, y_min, y_max)
    warped = (warped * 0.5).astype(np.uint8)  # làm tối để lớp phủ nổi bật
    img = bgr_to_qimage(warped)
    M = mapper.bev_matrix(size, x_half, y_min, y_max)

    def to_px(x, y):
        v = M @ np.array([x, y, 1.0])
        return QPointF(v[0], v[1])

    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setFont(font(11, 500))

    # Lưới khoảng cách
    for d in range(10, int(y_max) + 1, 10):
        p.setPen(QPen(QColor(255, 255, 255, 36), 1))
        p.drawLine(to_px(-x_half, d), to_px(x_half, d))
        p.setPen(qcolor("muted"))
        p.drawText(to_px(-x_half, d) + QPointF(4, -3), f"{d} m")

    # Hành lang làn xe chủ + khoảng trống tới xe phía trước
    ys = np.linspace(0, y_max, 30)
    edges = lane_edges(cfg, result.lane, ys)
    lead = result.lead
    if lead is not None and lead.method == "IPM":
        gy = np.linspace(0, min(lead.distance_m, y_max), 12)
        gl, gr = lane_edges(cfg, result.lane, gy)
        col = risk_color(lead.risk)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(col.red(), col.green(), col.blue(), 60))
        p.drawPolygon(QPolygonF([to_px(x, y) for x, y in zip(gl, gy)] +
                                [to_px(x, y) for x, y in zip(gr[::-1], gy[::-1])]))
    p.setPen(QPen(QColor(255, 255, 255, 150), 1.5))
    p.setBrush(Qt.BrushStyle.NoBrush)
    for xs in edges:
        p.drawPolyline(QPolygonF([to_px(x, y) for x, y in zip(xs, ys)]))

    # Vạch ngưỡng theo tốc độ
    if thr is not None:
        p.setFont(font(12, 700))
        for dist, key in ((thr.safe_m, "warning"), (thr.danger_m, "danger")):
            if dist <= y_max:
                (el,), (er,) = lane_edges(cfg, result.lane, [dist])
                pen = QPen(qcolor(key), 2, Qt.PenStyle.CustomDashLine)
                pen.setDashPattern([4, 3])
                p.setPen(pen)
                p.drawLine(to_px(el - 1.5, dist), to_px(er + 1.5, dist))
                p.setPen(qcolor(key))
                p.drawText(to_px(er + 1.8, dist) + QPointF(0, 4), f"{dist:.0f} m")
        p.setFont(font(11, 600))

    # Xe chủ (màu thương hiệu)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(qcolor("accent"))
    tl, br = to_px(-0.9, 0), to_px(0.9, -4.5)
    p.drawRoundedRect(QRectF(tl, br), 4, 4)

    # Các phương tiện
    for vs in result.vehicles:
        if vs.distance_m > y_max:
            continue
        w_m, l_m = VEHICLE_SIZE_M.get(vs.det.class_name, (1.8, 4.5))
        r = QRectF(to_px(vs.lateral_m - w_m / 2, vs.distance_m + l_m),
                   to_px(vs.lateral_m + w_m / 2, vs.distance_m)).normalized()
        col = risk_color(vs.risk) if vs is lead else QColor(255, 255, 255, 120 if vs.risk == "info" else 190)
        fill = QColor(col)
        fill.setAlpha(150)
        p.setPen(QPen(col, 2 if vs is lead else 1))
        p.setBrush(fill)
        p.drawRoundedRect(r, 3, 3)
        p.setPen(qcolor("text"))
        p.drawText(r.bottomRight() + QPointF(3, 0), f"{vs.distance_m:.0f} m")

    p.end()
    return img
