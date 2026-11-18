"""Tiện ích và widget nền: biểu tượng, cửa sổ vừa màn hình, khung ảnh, thẻ."""

from typing import Optional

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from gui.rendering import icon, icon_pixmap
from gui.styles import C
from gui.theme import ICON_FAMILY, icon_char


def icon_html(name: str, color: str, px: int = 14) -> str:
    """Biểu tượng Material chèn trong rich text (Be Vietnam Pro thiếu ● ⚠ ✓...)."""
    return (f"<span style=\"font-family:'{ICON_FAMILY}'; font-size:{px}px; color:{C.get(color, color)}\">"
            f"{icon_char(name)}</span>")


def set_icon(button, name: str, color: str = "text", size: int = 18):
    button.setIcon(icon(name, color, size))
    button.setIconSize(QSize(size, size))
    text = button.text()
    if text and not text.startswith(" "):   # Qt đặt biểu tượng sát chữ -> chừa một khoảng
        button.setText(" " + text)



def fit_to_screen(win: QWidget, width: int, height: int, ratio: float = 0.92) -> None:
    """
    Đặt kích thước cửa sổ không vượt quá vùng làm việc của màn hình (đã trừ taskbar,
    tính theo tỷ lệ scale của Windows) rồi căn giữa - để thanh tiêu đề và nút luôn nhìn thấy.
    """
    TITLE_BAR = 40  # resize() tính phần ruột cửa sổ; chừa chỗ cho thanh tiêu đề + viền Windows
    screen = win.screen() or QGuiApplication.primaryScreen()
    avail = screen.availableGeometry()
    w = min(width, int(avail.width() * ratio))
    h = min(height, int(avail.height() * ratio) - TITLE_BAR)
    win.resize(w, h)
    win.move(avail.x() + (avail.width() - w) // 2,
             avail.y() + max(0, (avail.height() - h - TITLE_BAR) // 2))


def repolish(w: QWidget) -> None:
    """Áp lại stylesheet sau khi đổi thuộc tính động (setProperty) dùng trong bộ chọn."""
    w.style().unpolish(w)
    w.style().polish(w)


def muted(text: str = "", wrap: bool = True) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("muted")
    lbl.setWordWrap(wrap)
    return lbl


class ImageView(QWidget):
    """Hiển thị QImage giữ nguyên tỷ lệ, căn giữa."""

    def __init__(self, placeholder: str = "", parent=None):
        super().__init__(parent)
        self._img: Optional[QImage] = None
        self._placeholder = placeholder
        self.setMinimumSize(160, 120)

    def set_image(self, img: Optional[QImage]):
        self._img = img
        self.update()

    def has_image(self) -> bool:
        return self._img is not None and not self._img.isNull()

    def set_placeholder(self, text: str):
        self._placeholder = text
        self.update()

    def image_rect(self) -> QRectF:
        if not self.has_image():
            return QRectF()
        iw, ih = self._img.width(), self._img.height()
        scale = min(self.width() / iw, self.height() / ih)
        w, h = iw * scale, ih * scale
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(C["video_bg"]))
        if not self.has_image():
            p.setPen(QColor(C["muted"]))
            p.drawText(self.rect().adjusted(12, 12, -12, -12),
                       Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self._placeholder)
            return
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.drawImage(self.image_rect(), self._img)
        self.paint_extra(p)

    def paint_extra(self, p: QPainter):
        pass


class Card(QFrame):
    """Thẻ có tiêu đề nhỏ viết hoa - khối cơ bản của cột bên phải."""

    def __init__(self, title: str = "", parent=None, icon_name: Optional[str] = None):
        super().__init__(parent)
        self.setObjectName("card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(14, 10, 14, 10)
        self.body.setSpacing(6)
        if title:
            self.title_row = QHBoxLayout()
            self.title_row.setSpacing(6)
            if icon_name:
                ic = QLabel()
                ic.setPixmap(icon_pixmap(icon_name, "muted", 15))
                self.title_row.addWidget(ic)
            self.title_label = QLabel(title.upper())
            self.title_label.setObjectName("cardTitle")
            self.title_row.addWidget(self.title_label, 1)
            self.body.addLayout(self.title_row)


# ----------------------------------------------------------------------
# Khu vực video
# ----------------------------------------------------------------------
