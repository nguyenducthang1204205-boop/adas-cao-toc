"""Hai thẻ dưới cột phải: trò chuyện với Trợ lý AI và nhật ký vi phạm của phiên."""

import csv
import html

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QTextBrowser, QVBoxLayout, QWidget,
)

from gui.styles import C
from gui.widgets.common import muted, set_icon


class ChatPanel(QWidget):
    """Khung hội thoại với Trợ lý AI."""
    send_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)
        # Chế độ trợ lý: đặt ở góc phải thanh tab (MainWindow gắn vào), không chiếm một dòng của khung chat
        self.source_label = QLabel()
        self.source_label.setObjectName("tabCorner")
        self.source_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(False)
        self.view.setMinimumHeight(40)
        lay.addWidget(self.view, 1)

        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Mô tả tình huống, vd: đang mưa, tôi chạy 90 km/h…")
        self.input.returnPressed.connect(lambda: self.submit(self.input.text()))
        self.send_btn = QPushButton("Gửi")
        self.send_btn.setObjectName("primary")
        self.send_btn.clicked.connect(lambda: self.submit(self.input.text()))
        row.addWidget(self.input, 1)
        row.addWidget(self.send_btn)
        lay.addLayout(row)

        self.add_message("assistant",
                         "Xin chào! Tôi là Trợ lý An toàn. Hãy cho tôi biết tốc độ, thời tiết, mặt đường "
                         "hoặc tình trạng của bạn - tôi sẽ điều chỉnh ngưỡng cảnh báo khoảng cách cho phù hợp.")

    def submit(self, text: str):
        """Hiện câu hỏi của người dùng rồi phát tín hiệu gửi (bỏ qua khi trợ lý đang trả lời)."""
        text = text.strip()
        if not text or not self.send_btn.isEnabled():
            return
        self.input.clear()
        self.add_message("user", text)
        self.send_requested.emit(text)

    def set_busy(self, busy: bool):
        self.send_btn.setEnabled(not busy)
        self.send_btn.setText("Đang trả lời…" if busy else "Gửi")

    def set_source(self, text: str, tip: str = ""):
        self.source_label.setText(text)
        self.source_label.setToolTip(tip or text)

    def add_message(self, role: str, text: str, meta: str = ""):
        text = html.escape(text).replace("\n", "<br>")
        if role == "user":
            block = (f"<div style='margin:6px 0 6px 40px; padding:8px; background:{C['accent_soft']}; "
                     f"border-radius:8px'>{text}</div>")
        elif role == "system":
            block = f"<div style='margin:4px 0; color:{C['muted']}; font-size:9pt'>{text}</div>"
        else:
            meta_html = f"<span style='color:{C['accent']}; font-size:8pt'>{html.escape(meta)}</span><br>" if meta else ""
            block = (f"<div style='margin:6px 40px 6px 0; padding:8px; background:{C['surface2']}; "
                     f"border-radius:8px'>{meta_html}{text}</div>")
        self.view.append(block)
        self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().maximum())


LEVEL_TEXT_VI = {"warning": "CẢNH BÁO", "danger": "NGUY HIỂM"}
LEVEL_COLOR = {"warning": C["warning"], "danger": C["danger"]}


class EventLog(QWidget):
    """Nhật ký vi phạm của phiên hiện tại (mỗi dòng = 1 đợt vi phạm đã ghi vào CSDL)."""
    HEADERS = ["Mã", "Thời gian", "Mức", "Xe", "K/c nhỏ nhất", "TTC nhỏ nhất", "Thời lượng", "Ngưỡng", "Tốc độ"]
    history_requested = Signal()
    count_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)
        top = QHBoxLayout()
        self.session_label = muted("Chưa có phiên giám sát")
        self.count = QLabel("0 vi phạm")
        top.addWidget(self.session_label, 1)
        top.addWidget(self.count)
        lay.addLayout(top)
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        lay.addWidget(self.table, 1)
        row = QHBoxLayout()
        history = QPushButton("Lịch sử")
        set_icon(history, "history_outlined")
        history.setToolTip("Tra cứu mọi phiên và vi phạm đã lưu trong CSDL, kèm ảnh chụp")
        history.clicked.connect(self.history_requested.emit)
        export = QPushButton("Xuất CSV")
        set_icon(export, "download_outlined")
        export.setToolTip("Lưu nhật ký phiên hiện tại ra file CSV (mở được bằng Excel)")
        export.clicked.connect(self.export_csv)
        row.addStretch(1)
        row.addWidget(history)
        row.addWidget(export)
        lay.addLayout(row)
        self._rows = {}  # mã vi phạm -> QTableWidgetItem ở cột "Mã" (để tìm dòng)

    def start_session(self, session_id: int):
        self.table.setRowCount(0)
        self._rows.clear()
        self.session_label.setText(f"Phiên giám sát #{session_id} · đang ghi vào data/adas.db")
        self._update_count()

    def on_violation(self, e: dict):
        vid = e["id"]
        if e["action"] == "open":
            tid = f" #{e['track_id']}" if e.get("track_id") is not None else ""
            self.table.insertRow(0)
            values = [str(vid), e["time"], "", f"{e['class']}{tid}", "", "", "đang diễn ra",
                      f"{e['safe_m']:.0f} m", f"{e['speed_kmh']:.0f} km/h"]
            for c, v in enumerate(values):
                self.table.setItem(0, c, QTableWidgetItem(v))
            self._rows[vid] = self.table.item(0, 0)
        item = self._rows.get(vid)
        if item is None:
            return
        r = item.row()
        level = QTableWidgetItem(LEVEL_TEXT_VI.get(e["level"], e["level"]))
        level.setForeground(QColor(LEVEL_COLOR.get(e["level"], C["text"])))
        self.table.setItem(r, 2, level)
        self.table.item(r, 4).setText(f"{e['min_distance']:.1f} m")
        ttc = e.get("min_ttc")
        self.table.item(r, 5).setText(f"{ttc:.1f} s" if ttc is not None and ttc < 60 else "--")
        if e["action"] == "close":
            self.table.item(r, 6).setText(f"{e['duration']:.1f} s")
        self._update_count()

    def _update_count(self):
        n = self.table.rowCount()
        self.count.setText(f"{n} vi phạm")
        self.count_changed.emit(n)

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Xuất nhật ký", "nhat_ky_canh_bao.csv", "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(self.HEADERS)
            for r in range(self.table.rowCount() - 1, -1, -1):
                w.writerow([self.table.item(r, c).text() for c in range(self.table.columnCount())])
