"""
Stylesheet "Night Drive" cho cửa sổ chính và mọi hộp thoại - cùng hệ thiết kế với bản mobile.

Token màu / chữ / biểu tượng ở gui/theme.py (dùng chung với gui/rendering và app Android: ui/theme/Theme.kt).
Widget được định kiểu theo objectName (card, primary, chip, speedStep, startButton[running], notice,
step[done]...). Đổi property dùng trong selector xong phải gọi widgets.repolish(w).
"""

from adas.paths import UI_ASSETS_DIR
from gui.theme import C, FONT_FAMILY, LEVEL_STYLE

__all__ = ["C", "LEVEL_STYLE", "STYLESHEET"]   # gui/widgets dùng lại token qua module này

ASSETS = UI_ASSETS_DIR.as_posix()

STYLESHEET = """
QWidget {
    background-color: %(bg)s;
    color: %(text)s;
    font-family: "%(font)s";
    font-size: 10pt;
}
QToolTip {
    background: %(surface2)s; color: %(text)s; border: 1px solid %(border)s;
    padding: 6px 8px; border-radius: 8px;
}

/* ---------- Thanh tiêu đề của cửa sổ chính ---------- */
QFrame#header { background: %(surface)s; border-bottom: 1px solid %(border)s; }
QFrame#header QLabel { background: transparent; }
QLabel#appTitle { font-size: 13pt; font-weight: 800; }
QLabel#appSubtitle { color: %(muted)s; font-size: 9pt; }
QFrame#headerSep { background: %(border)s; max-width: 1px; min-width: 1px; margin: 8px 4px; }

QToolButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 10px;
    padding: 7px 12px;
    color: %(text)s;
}
QToolButton:hover { background: %(hover)s; border-color: %(border)s; }
QToolButton:checked { background: %(accent_soft)s; border-color: %(accent)s; }
QToolButton:disabled { color: %(faint)s; }
QToolButton::menu-indicator { image: none; width: 0; }
QToolButton#sourceButton {
    background: %(surface2)s; border: 1px solid %(border)s; padding: 7px 14px; text-align: left;
}
QToolButton#sourceButton:hover { border-color: %(accent)s; }

/* nút chính Bắt đầu / Dừng: màu thương hiệu (xanh/hổ phách/đỏ chỉ dành cho mức rủi ro) */
QPushButton#startButton {
    background: %(accent)s; border: none; color: %(on_accent)s; font-weight: 800; font-size: 11pt;
    border-radius: 20px; padding: 8px 24px;
}
QPushButton#startButton:hover { background: %(accent_hover)s; }
QPushButton#startButton[running="true"] {
    background: %(surface2)s; color: %(text)s; border: 1px solid %(border_strong)s;
}
QPushButton#startButton[running="true"]:hover { border-color: %(danger)s; }

/* ---------- Thông báo dưới thanh tiêu đề ---------- */
QFrame#notice { background: #1e1708; border-bottom: 1px solid #5c4410; }
QFrame#notice QLabel { background: transparent; color: %(text)s; }
QFrame#notice QPushButton { background: transparent; border: 1px solid #8a6414; color: %(warning)s; }
QFrame#notice QPushButton:hover { background: #2e230b; }

/* ---------- Thẻ (card) ở cột phải: cùng kiểu cụm đồng hồ của bản mobile ---------- */
QFrame#card { background: %(surface)s; border: 1px solid %(border)s; border-radius: 16px; }
QFrame#card QLabel, QFrame#card QCheckBox { background: transparent; }
QFrame#card[level="warning"] { border: 2px solid %(warning)s; }
QFrame#card[level="danger"] { border: 2px solid %(danger)s; }
QLabel#cardTitle {
    color: %(muted)s; font-size: 8.5pt; font-weight: 700; letter-spacing: 1.4px;
}
QLabel#bigValue { font-size: 30pt; font-weight: 800; }
QLabel#numeral { font-size: 26pt; font-weight: 700; }
QLabel#unit { color: %(muted)s; font-size: 11pt; font-weight: 600; }
QLabel#levelPill {
    border-radius: 13px; font-size: 9.5pt; font-weight: 800; padding: 4px 12px; letter-spacing: 1px;
}
QLabel#metricValue { font-size: 12pt; font-weight: 700; }
QLabel#metricLabel { color: %(muted)s; font-size: 8.5pt; }
QFrame#metric { background: transparent; }
QFrame#metric QLabel { background: transparent; }

QPushButton#speedStep {
    background: %(surface2)s; border: 1px solid %(border)s; border-radius: 10px;
    padding: 6px 2px; color: %(muted)s;
}
QPushButton#speedStep:hover { border-color: %(accent)s; color: %(text)s; }
QPushButton#speedStep:checked {
    background: %(accent_soft)s; border: 2px solid %(accent)s; color: %(text)s; font-weight: 700;
}
/* đang dùng tốc độ đo từ video: nấc chọn tay chỉ là dự phòng */
QPushButton#speedStep[fallback="true"]:checked {
    background: %(surface2)s; border: 1px dashed %(accent)s; color: %(muted)s; font-weight: 400;
}

/* ---------- Khu vực video ---------- */
QFrame#welcome { background: transparent; }
QFrame#welcome QLabel { background: transparent; }
QLabel#welcomeTitle { font-size: 20pt; font-weight: 800; }
QFrame#step { background: %(surface)s; border: 1px solid %(border)s; border-radius: 14px; }
QFrame#step QLabel { background: transparent; }
QFrame#step[done="true"] { border-color: %(safe)s; }
QFrame#step QLabel#stepNum {
    background: %(accent_soft)s; color: %(accent)s; border-radius: 14px; font-weight: 800;
    min-width: 28px; max-width: 28px; min-height: 28px; max-height: 28px;
}
QFrame#step QLabel#stepNum[done="true"] { background: %(safe)s; color: %(on_accent)s; }
QFrame#playbar { background: %(surface)s; border-top: 1px solid %(border)s; }

/* ---------- Căn chỉnh camera ---------- */
QLabel#wizardTitle { font-size: 14pt; font-weight: 800; }
QLabel#wizardStep {
    padding: 6px 14px; border-radius: 13px; background: %(surface2)s; color: %(muted)s; font-weight: 700;
}
QLabel#wizardStep[state="current"] { background: %(accent_soft)s; color: %(accent)s; }
QLabel#wizardStep[state="done"] { color: %(safe)s; }
QFrame#calibBar { background: %(surface)s; border-bottom: 1px solid %(border)s; }
QFrame#calibBar QLabel { background: transparent; }
QFrame#calibBar[state="drift"] { background: #1e1708; border-bottom: 1px solid #5c4410; }
QFrame#calibBar QPushButton { background: transparent; border: none; }
QFrame#playbar QLabel { background: transparent; }

/* ---------- Thành phần chung ---------- */
QGroupBox {
    border: 1px solid %(border)s;
    border-radius: 14px;
    margin-top: 18px;
    padding: 14px 12px 12px 12px;
    background: %(surface)s;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 4px;
    color: %(accent)s;
    font-weight: 700;
}
QGroupBox QLabel, QGroupBox QCheckBox { background: transparent; }
QLabel#muted { color: %(muted)s; }
QLabel#tabCorner { color: %(muted)s; font-size: 8.5pt; background: transparent; padding: 0 8px 2px 0; }
QLabel#hint {
    color: %(muted)s; background: %(surface2)s; border-radius: 10px; padding: 8px 12px;
}
QPushButton {
    background: %(surface2)s;
    border: 1px solid %(border)s;
    border-radius: 10px;
    padding: 7px 14px;
}
QPushButton:hover { background: %(hover)s; border-color: %(border_strong)s; }
QPushButton:pressed { background: %(accent_soft)s; }
QPushButton:disabled { color: %(faint)s; }
QPushButton#primary {
    background: %(accent)s; border-color: %(accent)s; color: %(on_accent)s; font-weight: 700;
}
QPushButton#primary:hover { background: %(accent_hover)s; }
QPushButton#primary:disabled { background: %(accent_soft)s; border-color: %(accent_soft)s; color: %(muted)s; }
QPushButton#danger { color: %(danger)s; }
QPushButton#danger:hover { background: #2a1416; border-color: %(danger)s; }
QPushButton#chip {
    border-radius: 12px;
    padding: 6px 6px;
    font-size: 9pt;
    background: %(surface2)s;
    text-align: left;
}
QPushButton#chip:hover { border-color: %(accent)s; }
QPushButton#chip[selected="true"] { background: %(accent_soft)s; border: 1px solid %(accent)s; }
QPushButton#link { background: transparent; border: none; color: %(accent)s; padding: 2px 4px; }
QPushButton#link:hover { color: %(accent_hover)s; text-decoration: underline; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit {
    background: %(bg)s;
    border: 1px solid %(border)s;
    border-radius: 10px;
    padding: 6px 10px;
    selection-background-color: %(accent)s;
    selection-color: %(on_accent)s;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {
    border-color: %(accent)s;
}
QLineEdit:disabled, QComboBox:disabled { color: %(faint)s; }
QComboBox QAbstractItemView {
    background: %(surface2)s; border: 1px solid %(border)s; selection-background-color: %(accent)s;
    selection-color: %(on_accent)s;
}
QTextBrowser {
    background: %(bg)s;
    border: 1px solid %(border)s;
    border-radius: 10px;
}
QSlider::groove:horizontal { height: 6px; background: %(surface2)s; border-radius: 3px; }
QSlider::sub-page:horizontal { background: %(accent)s; border-radius: 3px; }
QSlider::handle:horizontal {
    background: #ffffff; width: 18px; margin: -6px 0; border-radius: 9px;
}
QTabWidget::pane { border: 1px solid %(border)s; border-radius: 14px; top: -1px; background: %(surface)s; }
QTabWidget::pane QWidget { background: %(surface)s; }
QTabWidget::pane QLineEdit, QTabWidget::pane QTextBrowser, QTabWidget::pane QTableWidget,
QTabWidget::pane QSpinBox, QTabWidget::pane QDoubleSpinBox, QTabWidget::pane QComboBox {
    background: %(bg)s;
}
QTabWidget::pane QPushButton { background: %(surface2)s; }
QTabWidget::pane QPushButton#primary { background: %(accent)s; }
QTabWidget::pane QPushButton#primary:disabled { background: %(accent_soft)s; }
QTabWidget::pane QPushButton#link { background: transparent; }
QTabWidget::pane QPushButton:hover { background: %(hover)s; }
QTabWidget::pane QPushButton#primary:hover { background: %(accent_hover)s; }
QTabBar::tab {
    background: transparent; padding: 8px 14px; border: none;
    border-bottom: 2px solid transparent; margin-right: 2px; color: %(muted)s; font-weight: 600;
}
QTabBar::tab:hover { color: %(text)s; }
QTabBar::tab:selected { color: %(text)s; border-bottom: 2px solid %(accent)s; }
QTableWidget, QTableView {
    background: %(bg)s; gridline-color: %(border)s; border: 1px solid %(border)s;
    border-radius: 10px; alternate-background-color: %(surface)s;
}
QTableWidget::item { padding: 3px 6px; border: none; }
QTableWidget::item:selected, QTableView::item:selected { background: %(accent_soft)s; color: %(text)s; }
QHeaderView::section {
    background: %(surface)s; color: %(muted)s; border: none; padding: 6px;
    border-right: 1px solid %(border)s; border-bottom: 1px solid %(border)s; font-weight: 700;
}
QProgressBar {
    background: %(surface2)s; border: none; border-radius: 3px;
    text-align: center; font-size: 8pt;
}
QProgressBar::chunk { background: %(accent)s; border-radius: 3px; }
QStatusBar { background: %(surface)s; color: %(muted)s; border-top: 1px solid %(border)s; }
QStatusBar QLabel { background: transparent; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator {
    width: 18px; height: 18px; border: 1px solid %(border_strong)s; border-radius: 5px; background: %(bg)s;
}
QCheckBox::indicator:hover { border-color: %(accent)s; }
QCheckBox::indicator:checked {
    background: %(accent)s; border-color: %(accent)s; image: url("%(assets)s/check.svg");
}
QCheckBox::indicator:disabled { background: %(surface2)s; border-color: %(border)s; }
QMenu {
    background: %(surface2)s; border: 1px solid %(border)s; border-radius: 12px; padding: 6px;
}
QMenu::item { padding: 8px 26px 8px 12px; border-radius: 8px; background: transparent; }
QMenu::item:selected { background: %(accent)s; color: %(on_accent)s; }
QMenu::item:disabled { color: %(faint)s; }
QMenu::separator { height: 1px; background: %(border)s; margin: 5px 8px; }
QMessageBox QLabel { min-width: 280px; }
QSplitter::handle { background: %(bg)s; }
QSplitter::handle:hover { background: %(border)s; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: %(border_strong)s; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #46546a; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: %(border_strong)s; border-radius: 4px; min-width: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }
QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
""" % dict(C, assets=ASSETS, font=FONT_FAMILY)
