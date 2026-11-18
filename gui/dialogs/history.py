"""Tra cứu CSDL: phiên giám sát, nhật ký vi phạm khoảng cách, lịch sử cấu hình."""

import csv
import json
import os
from pathlib import Path

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog, QFileDialog, QHBoxLayout, QHeaderView, QLabel,
    QMessageBox, QPlainTextEdit, QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget,
    QVBoxLayout, QWidget,
)

from adas.config import CLASS_LABELS_VI
from adas.paths import APP_DIR, DB_PATH
from adas.storage.database import Database
from gui.rendering import icon
from gui.theme import C
from gui.widgets import LEVEL_COLOR, LEVEL_TEXT_VI, ImageView, fit_to_screen

SOURCE_TYPE_VI = {"video": "Video", "camera": "Camera", "stream": "Luồng IP", "image": "Ảnh"}
ALL_SESSIONS = -1   # khóa của dòng "Tất cả phiên"
METHOD_VI = {"manual": "Thủ công", "auto": "Tự động", "imported": "Chuyển đổi",
             "pose": "Chiều cao + chân trời", "online": "Tự hoàn thiện"}


def _fmt(v, fmt="{:.1f}", suffix=""):
    return "--" if v is None else fmt.format(v) + suffix


def _table(headers):
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    t.horizontalHeader().setStretchLastSection(True)
    t.verticalHeader().setVisible(False)
    t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    t.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    return t


def _fill(table: QTableWidget, rows):
    table.setRowCount(0)
    for values, key, color_col, color in rows:
        r = table.rowCount()
        table.insertRow(r)
        for c, v in enumerate(values):
            item = QTableWidgetItem(str(v))
            if c == 0:
                item.setData(Qt.ItemDataRole.UserRole, key)
            if c == color_col and color:
                item.setForeground(QColor(color))
            table.setItem(r, c, item)


class HistoryDialog(QDialog):
    restore_config = Signal(dict)   # người dùng chọn khôi phục một cấu hình cũ

    SESSION_HEADERS = ["Mã", "Bắt đầu", "Loại", "Nguồn", "Vi phạm", "Nguy hiểm", "K/c gần nhất", "Khung", "FPS"]
    VIOLATION_HEADERS = ["Mã", "Bắt đầu", "Giây video", "Mức", "Xe", "K/c ban đầu", "K/c nhỏ nhất",
                         "TTC nhỏ nhất", "Thời lượng", "Ngưỡng cảnh báo", "Ngưỡng nguy hiểm",
                         "Quy định", "Tốc độ xe", "Điều kiện"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Cơ sở dữ liệu - {DB_PATH.name}")
        self.db = Database()
        self._violations = []

        root = QVBoxLayout(self)
        self.stats = QLabel()
        root.addWidget(self.stats)
        tabs = QTabWidget()
        root.addWidget(tabs, 1)

        # ---------------- Tab vi phạm ----------------
        vt = QWidget()
        vl = QVBoxLayout(vt)
        split = QSplitter(Qt.Orientation.Vertical)

        top = QWidget()
        tl = QVBoxLayout(top)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.addWidget(QLabel("<b>Phiên giám sát</b> (chọn một phiên để xem vi phạm)"))
        self.sessions = _table(self.SESSION_HEADERS)
        self.sessions.itemSelectionChanged.connect(self._load_violations)
        tl.addWidget(self.sessions)
        split.addWidget(top)

        bottom = QWidget()
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(0, 0, 0, 0)
        left = QVBoxLayout()
        row = QHBoxLayout()
        row.addWidget(QLabel("<b>Nhật ký vi phạm</b>"))
        row.addStretch(1)
        # Bộ lọc tìm kiếm: thời gian, mức, loại xe
        self.use_dates = QCheckBox("Từ ngày")
        self.date_from = QDateEdit(QDate.currentDate().addDays(-7))
        self.date_to = QDateEdit(QDate.currentDate())
        for d in (self.date_from, self.date_to):
            d.setCalendarPopup(True)
            d.setDisplayFormat("dd/MM/yyyy")
            d.dateChanged.connect(self._load_violations)
        self.use_dates.toggled.connect(self._load_violations)
        row.addWidget(self.use_dates)
        row.addWidget(self.date_from)
        row.addWidget(QLabel("đến"))
        row.addWidget(self.date_to)
        row.addWidget(QLabel("  Mức:"))
        self.level_filter = QComboBox()
        self.level_filter.addItem("Tất cả", None)
        self.level_filter.addItem("Nguy hiểm", "danger")
        self.level_filter.addItem("Cảnh báo", "warning")
        self.level_filter.currentIndexChanged.connect(self._load_violations)
        row.addWidget(self.level_filter)
        row.addWidget(QLabel("  Loại xe:"))
        self.class_filter = QComboBox()
        self.class_filter.addItem("Tất cả", None)
        for label, classes in (("Ô tô", "car"), ("Xe tải", "truck"), ("Xe khách", "bus,Jeepney"),
                               ("Xe máy", "motorcycle")):
            self.class_filter.addItem(label, classes)
        self.class_filter.currentIndexChanged.connect(self._load_violations)
        row.addWidget(self.class_filter)
        left.addLayout(row)
        self.violations = _table(self.VIOLATION_HEADERS)
        self.violations.itemSelectionChanged.connect(self._show_snapshot)
        left.addWidget(self.violations, 1)
        self.result_count = QLabel()
        self.result_count.setObjectName("muted")
        left.addWidget(self.result_count)
        bl.addLayout(left, 3)
        right = QVBoxLayout()
        right.addWidget(QLabel("<b>Ảnh bằng chứng</b>"))
        self.snapshot = ImageView("Chọn một vi phạm")
        self.snapshot.setMinimumSize(280, 160)
        right.addWidget(self.snapshot, 1)
        self.snap_info = QLabel()
        self.snap_info.setObjectName("muted")
        self.snap_info.setWordWrap(True)
        right.addWidget(self.snap_info)
        bl.addLayout(right, 2)
        split.addWidget(bottom)
        split.setSizes([220, 420])
        vl.addWidget(split, 1)

        btns = QHBoxLayout()
        export = QPushButton("Xuất CSV")
        export.clicked.connect(self._export_csv)
        delete_v = QPushButton("Xóa vi phạm đã chọn")
        delete_v.clicked.connect(self._delete_violations)
        delete = QPushButton("Xóa phiên đã chọn")
        delete.clicked.connect(self._delete_session)
        open_dir = QPushButton("Mở thư mục CSDL")
        open_dir.clicked.connect(lambda: os.startfile(str(DB_PATH.parent)))
        btns.addWidget(export)
        btns.addWidget(delete_v)
        btns.addWidget(delete)
        btns.addStretch(1)
        btns.addWidget(open_dir)
        vl.addLayout(btns)
        tabs.addTab(vt, icon("receipt_long_outlined", "accent", 18), "Nhật ký vi phạm")

        # ---------------- Tab lịch sử cấu hình ----------------
        ct = QWidget()
        cl = QHBoxLayout(ct)
        self.configs = _table(["Mã", "Thời gian", "Nội dung thay đổi"])
        self.configs.itemSelectionChanged.connect(self._show_config)
        cl.addWidget(self.configs, 2)
        cr = QVBoxLayout()
        self.config_text = QPlainTextEdit()
        self.config_text.setReadOnly(True)
        cr.addWidget(self.config_text, 1)
        restore = QPushButton("Khôi phục cấu hình này")
        restore.clicked.connect(self._restore)
        cr.addWidget(restore)
        cl.addLayout(cr, 3)
        tabs.addTab(ct, icon("tune_outlined", "accent", 18), "Lịch sử cấu hình")

        # ---------------- Tab ma trận camera ----------------
        mt = QWidget()
        ml = QHBoxLayout(mt)
        self.calibs = _table(["Mã", "Thời gian", "Nguồn", "Phương pháp", "Khung", "f (px)",
                              "Cao (m)", "Chúc (°)", "Chân trời", "Đang dùng"])
        self.calibs.itemSelectionChanged.connect(self._show_calibration)
        ml.addWidget(self.calibs, 3)
        self.calib_text = QPlainTextEdit()
        self.calib_text.setReadOnly(True)
        self.calib_text.setStyleSheet("font-family: Consolas, monospace;")
        ml.addWidget(self.calib_text, 2)
        tabs.addTab(mt, icon("photo_camera_outlined", "accent", 18), "Ma trận camera")

        close = QPushButton("Đóng")
        close.clicked.connect(self.accept)
        root.addWidget(close, 0, Qt.AlignmentFlag.AlignRight)

        fit_to_screen(self, 1400, 820)
        self.refresh()

    # ------------------------------------------------------------------

    def refresh(self):
        s = self.db.stats()
        self.stats.setText(
            f"<b>CSDL:</b> {DB_PATH.relative_to(APP_DIR).as_posix()} &nbsp;·&nbsp; "
            f"{s['sessions']} phiên giám sát &nbsp;·&nbsp; {s['total']} vi phạm "
            f"(<span style='color:{LEVEL_COLOR['danger']}'>{s['danger']} nguy hiểm</span>, "
            f"<span style='color:{LEVEL_COLOR['warning']}'>{s['warning']} cảnh báo</span>)"
            + (f" &nbsp;·&nbsp; gần nhất {s['closest']:.1f} m" if s["closest"] is not None else ""))
        all_row = (["*", "Tất cả phiên", "", "", s["total"], s["danger"],
                    _fmt(s["closest"], suffix=" m"), "", ""], ALL_SESSIONS, -1, None)
        _fill(self.sessions, [all_row] + [
            ([r["id"], r["started_at"], SOURCE_TYPE_VI.get(r["source_type"], r["source_type"]),
              Path(r["source"]).name or r["source"], r["total_violations"], r["danger_count"],
              _fmt(r["closest_distance_m"], suffix=" m"), r["frames_processed"], _fmt(r["avg_fps"])],
             r["id"], 5 if r["danger_count"] else -1, LEVEL_COLOR["danger"])
            for r in self.db.list_sessions()])
        _fill(self.configs, [([r["id"], r["changed_at"], r["reason"]], r["id"], -1, None)
                             for r in self.db.config_history()])
        self._calibs = self.db.list_calibrations()
        _fill(self.calibs, [
            ([c["id"], c["created_at"], c["source_name"] or "(chung)", METHOD_VI.get(c["method"], c["method"]),
              f"{c['frame_width']}×{c['frame_height']}", _fmt(c["focal_px"], "{:.0f}"),
              _fmt(c["camera_height_m"], "{:.2f}"), _fmt(c["pitch_deg"], "{:+.1f}"),
              _fmt(c["horizon_y"], "{:.0f}"), "Đang dùng" if c["active"] else ""],
             c["id"], 9, C["safe"])
            for c in self._calibs])
        # Mặc định chọn phiên mới nhất (dòng 1); dòng 0 là "Tất cả phiên"
        self.sessions.selectRow(1 if self.sessions.rowCount() > 1 else 0)

    def _selected_key(self, table: QTableWidget):
        items = table.selectedItems()
        return items[0].tableWidget().item(items[0].row(), 0).data(Qt.ItemDataRole.UserRole) if items else None

    def _load_violations(self):
        sid = self._selected_key(self.sessions)
        dates = self.use_dates.isChecked()
        self._violations = [] if sid is None else self.db.list_violations(
            session_id=None if sid == ALL_SESSIONS else sid,
            level=self.level_filter.currentData(),
            vehicle_class=self.class_filter.currentData(),
            date_from=self.date_from.date().toString("yyyy-MM-dd") if dates else None,
            date_to=self.date_to.date().toString("yyyy-MM-dd") if dates else None)
        self.result_count.setText(f"{len(self._violations)} vi phạm khớp bộ lọc")
        _fill(self.violations, [
            ([v["id"], v["started_at"], _fmt(v["video_time_s"]),
              LEVEL_TEXT_VI.get(v["level"], v["level"]),
              f"{CLASS_LABELS_VI.get(v['vehicle_class'], v['vehicle_class'])}"
              + (f" #{v['track_id']}" if v["track_id"] is not None else ""),
              _fmt(v["distance_m"], suffix=" m"), _fmt(v["min_distance_m"], suffix=" m"),
              _fmt(v["min_ttc_s"], suffix=" s"), _fmt(v["duration_s"], suffix=" s"),
              _fmt(v["safe_threshold_m"], "{:.0f}", " m"), _fmt(v["danger_threshold_m"], "{:.0f}", " m"),
              _fmt(v["legal_min_gap_m"], "{:.0f}", " m"), _fmt(v["ego_speed_kmh"], "{:.0f}", " km/h"),
              v["road_condition"] or ""],
             v["id"], 3, LEVEL_COLOR.get(v["level"]))
            for v in self._violations])
        self.snapshot.set_image(None)
        self.snap_info.setText("")

    def _show_snapshot(self):
        vid = self._selected_key(self.violations)
        v = next((x for x in self._violations if x["id"] == vid), None)
        if v is None:
            return
        img = QImage(str(APP_DIR / v["snapshot_path"])) if v["snapshot_path"] else QImage()
        self.snapshot.set_image(None if img.isNull() else img)
        self.snap_info.setText(
            f"Vi phạm #{v['id']} · {LEVEL_TEXT_VI.get(v['level'])} · gần nhất {v['min_distance_m']:.1f} m "
            f"(ngưỡng {v['safe_threshold_m']:.0f} m ở {v['ego_speed_kmh']:.0f} km/h) · "
            f"hệ số điều kiện ×{v['weather_factor'] or 1:.2f}"
            + ("" if not img.isNull() else " · không có ảnh"))

    def _export_csv(self):
        if not self._violations:
            QMessageBox.information(self, "Xuất CSV", "Không có vi phạm nào để xuất.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Xuất nhật ký vi phạm", "nhat_ky_vi_pham.csv", "CSV (*.csv)")
        if not path:
            return
        cols = self._violations[0].keys()
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(cols)
            for v in self._violations:
                w.writerow([v[c] for c in cols])
        QMessageBox.information(self, "Xuất CSV", f"Đã xuất {len(self._violations)} vi phạm:\n{path}")

    def _delete_violations(self):
        vid = self._selected_key(self.violations)
        if vid is None:
            return
        if QMessageBox.question(self, "Xóa vi phạm", f"Xóa vi phạm #{vid} và ảnh bằng chứng?") \
                != QMessageBox.StandardButton.Yes:
            return
        self._remove_files(self.db.delete_violations([vid]))
        self.refresh()

    @staticmethod
    def _remove_files(rel_paths):
        for rel in rel_paths:
            try:
                (APP_DIR / rel).unlink(missing_ok=True)
            except OSError:
                pass

    def _delete_session(self):
        sid = self._selected_key(self.sessions)
        if sid is None or sid == ALL_SESSIONS:
            return
        if QMessageBox.question(self, "Xóa phiên", f"Xóa phiên #{sid} cùng toàn bộ vi phạm và ảnh của phiên?") \
                != QMessageBox.StandardButton.Yes:
            return
        self._remove_files(self.db.delete_session(sid))
        self.refresh()

    def _show_calibration(self):
        cid = self._selected_key(self.calibs)
        c = next((x for x in self._calibs if x["id"] == cid), None)
        if c is None:
            return

        def mat(name, js, fmt="{:>12.5g}"):
            if not js:
                return f"{name}: (không xác định)\n"
            rows = json.loads(js)
            clean = lambda v: 0.0 if abs(v) < 1e-9 else v  # noqa: E731 - bỏ nhiễu dấu phẩy động
            return f"{name}:\n" + "\n".join("  [" + " ".join(fmt.format(clean(v)) for v in r) + " ]"
                                            for r in rows) + "\n"

        params = json.loads(c["params_json"])
        text = (f"Hiệu chỉnh #{c['id']} · {c['source_name'] or '(chung)'} · {METHOD_VI.get(c['method'])}\n"
                f"Khung {c['frame_width']}×{c['frame_height']} · f = {_fmt(c['focal_px'], '{:.1f}')} px · "
                f"cao {_fmt(c['camera_height_m'], '{:.3f}')} m · chúc {_fmt(c['pitch_deg'], '{:+.2f}')}° · "
                f"sau đầu xe {_fmt(c['camera_offset_m'], '{:.2f}')} m\n\n"
                + mat("K - ma trận nội tham số", c["intrinsic_matrix"], "{:>10.2f}")
                + mat("H - ma trận IPM (từ pixel sang mặt đường, m)", c["homography_matrix"])
                + mat("R - ma trận quay (từ mặt đường sang camera)", c["rotation_matrix"], "{:>9.4f}")
                + "\nTham số hiệu chỉnh:\n" + json.dumps(params, ensure_ascii=False, indent=2)
                + (f"\n\nGhi chú:\n{c['note']}" if c["note"] else ""))
        self.calib_text.setPlainText(text)

    def _show_config(self):
        cid = self._selected_key(self.configs)
        row = next((r for r in self.db.config_history() if r["id"] == cid), None)
        self.config_text.setPlainText(
            json.dumps(json.loads(row["config_json"]), ensure_ascii=False, indent=2) if row else "")

    def _restore(self):
        text = self.config_text.toPlainText()
        if not text:
            return
        if QMessageBox.question(self, "Khôi phục cấu hình", "Áp dụng lại cấu hình đã chọn?") \
                == QMessageBox.StandardButton.Yes:
            self.restore_config.emit(json.loads(text))
            self.refresh()
