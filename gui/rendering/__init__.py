"""Lớp trình bày: vẽ lớp phủ cảnh báo, ảnh Bird's-Eye View, font và biểu tượng (QPainter, không cv2)."""

from gui.rendering.qt import (  # noqa: F401
    RISK_KEYS, ensure_fonts, qcolor, risk_color, risk_fill, font, icon_font, icon_pixmap, icon,
    bgr_to_qimage, qimage_to_bgr,
)
from gui.rendering.overlay import (  # noqa: F401
    VEHICLE_SIZE_M, vehicle_label, render_overlay, lane_edges, bev_range, render_bev,
)

__all__ = [
    'RISK_KEYS', 'ensure_fonts', 'qcolor', 'risk_color', 'risk_fill', 'font', 'icon_font', 'icon_pixmap',
    'icon', 'bgr_to_qimage', 'qimage_to_bgr', 'VEHICLE_SIZE_M', 'vehicle_label', 'render_overlay',
    'lane_edges', 'bev_range', 'render_bev',
]
