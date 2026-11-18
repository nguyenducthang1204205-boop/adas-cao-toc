"""Font, màu, biểu tượng Material và chuyển đổi numpy <-> QImage dùng chung cho toàn bộ giao diện."""

from typing import Optional

import numpy as np
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QImage, QPainter, QPixmap

from adas.paths import FONT_DIR
from gui.theme import C, FONT_FAMILY, ICON_FAMILY, icon_char

RISK_KEYS = ("safe", "warning", "danger", "info")


# ----------------------------------------------------------------------
# Font, màu, biểu tượng (dùng chung với gui/)
# ----------------------------------------------------------------------

_fonts_loaded = False


def ensure_fonts() -> None:
    """Nạp Be Vietnam Pro + Material Icons một lần (cần QGuiApplication đã tạo)."""
    global _fonts_loaded
    if _fonts_loaded:
        return
    for f in sorted(FONT_DIR.glob("*.[ot]tf")):
        QFontDatabase.addApplicationFont(str(f))
    _fonts_loaded = True


def qcolor(key_or_hex: str, alpha: Optional[float] = None) -> QColor:
    c = QColor(C.get(key_or_hex, key_or_hex))
    if alpha is not None:
        c.setAlphaF(alpha)
    return c


def risk_color(risk: str) -> QColor:
    return qcolor(risk if risk in RISK_KEYS else "info")


def risk_fill(risk: str) -> QColor:
    """Nền khối đặc theo mức (đỏ đậm hơn cho NGUY HIỂM để chữ trắng đủ tương phản)."""
    return qcolor("danger_fill" if risk == "danger" else risk)


def font(px: float, weight: int = 400) -> QFont:
    ensure_fonts()
    f = QFont(FONT_FAMILY)
    f.setPixelSize(max(9, int(round(px))))
    f.setWeight(QFont.Weight(weight))
    return f


def icon_font(px: float) -> QFont:
    ensure_fonts()
    f = QFont(ICON_FAMILY)
    f.setPixelSize(max(8, int(round(px))))
    return f


def icon_pixmap(name: str, color: str = "text", size: int = 20, dpr: float = 2.0) -> QPixmap:
    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.setFont(icon_font(size))
    p.setPen(qcolor(color))
    p.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, icon_char(name))
    p.end()
    return pm


def icon(name: str, color: str = "text", size: int = 20) -> QIcon:
    return QIcon(icon_pixmap(name, color, size))


# ----------------------------------------------------------------------
# Chuyển đổi numpy <-> QImage
# ----------------------------------------------------------------------

def bgr_to_qimage(frame: np.ndarray) -> QImage:
    frame = np.ascontiguousarray(frame)
    h, w = frame.shape[:2]
    return QImage(frame.data, w, h, frame.strides[0], QImage.Format.Format_BGR888).copy()


def qimage_to_bgr(img: QImage) -> np.ndarray:
    img = img.convertToFormat(QImage.Format.Format_BGR888)
    h, w, bpl = img.height(), img.width(), img.bytesPerLine()
    arr = np.frombuffer(img.constBits(), dtype=np.uint8, count=h * bpl).reshape(h, bpl)
    return arr[:, : w * 3].reshape(h, w, 3).copy()
