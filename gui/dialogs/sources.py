"""UC Quản lý nguồn video/camera: danh sách nguồn lưu trong CSDL (bảng video_sources)."""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from adas.storage.database import Database
from adas.stream.sources import SOURCE_TYPE_VI, classify_source, find_cameras, normalize_source, probe_source
from gui.rendering import bgr_to_qimage, icon
from gui.theme import C
from gui.widgets import ImageView, fit_to_screen


class _Job(QThread):
    """Chạy tác vụ chậm (mở camera/luồng mạng) ở nền để giao diện không bị treo."""
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, *args):
        super().__init__()
        self.fn, self.args = fn, args

    def run(self):
        try:
            self.done.emit(self.fn(*self.args))
        except Exception as e:
            self.failed.emit(str(e))


class SourceEditDialog(QDialog):
    """Thêm / sửa một nguồn."""

    def __init__(self, parent=None, name="", uri="", description=""):
        super().__init__(parent)
        self.setWindowTitle("Nguồn video/camera")
        self.resize(560, 200)
        f = QFormLayout(self)
        self.name = QLineEdit(name)
        self.name.setPlaceholderText("vd: Camera hành trình xe 51A-123.45")
        row = QHBoxLayout()
        self.uri = QLineEdit(uri)
        self.uri.setPlaceholderText("Đường dẫn file video, chỉ số camera (0, 1…) hoặc rtsp://…")
        browse = QPushButton("…")
        browse.setFixedWidth(36)
        browse.clicked.connect(self._browse)
        row.addWidget(self.uri)
        row.addWidget(browse)
        self.kind = QLabel()
        self.kind.setObjectName("muted")
        self.uri.textChanged.connect(lambda t: self.kind.setText(
            SOURCE_TYPE_VI[classify_source(t)] if t.strip() else ""))
        self.uri.textChanged.emit(uri)
        self.desc = QLineEdit(description)
        f.addRow("Tên nguồn:", self.name)
        f.addRow("Địa chỉ nguồn:", row)
        f.addRow("Loại:", self.kind)
        f.addRow("Ghi chú:", self.desc)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setObjectName("primary")
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("Lưu")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Hủy")
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        f.addRow(bb)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn video/ảnh", "", "Video/Ảnh (*.mp4 *.avi *.mov *.mkv *.wmv *.jpg *.jpeg *.png *.bmp)")
        if path:
            self.uri.setText(path)
            if not self.name.text().strip():
                self.name.setText(Path(path).stem)

    def _accept(self):
        uri = self.uri.text().strip()
        if not uri:
            QMessageBox.warning(self, "Nguồn", "Chưa nhập địa chỉ nguồn.")
            return
        if classify_source(uri) in ("video", "image") and not Path(uri).is_file():
            QMessageBox.warning(self, "Nguồn", f"Không tìm thấy file:\n{uri}")
            return
        self.values = (self.name.text().strip() or Path(uri).stem or uri, classify_source(uri), uri,
                       self.desc.text().strip())
        self.accept()


class SourceDialog(QDialog):
    HEADERS = ["Tên", "Loại", "Địa chỉ nguồn", "Căn chỉnh camera", "Số phiên", "Dùng gần nhất"]

    def __init__(self, parent=None, current_uri: Optional[str] = None):
        super().__init__(parent)
        self.setWindowTitle("Quản lý nguồn video/camera")
        self.db = Database()
        self.selected_uri: Optional[str] = None
        self._job: Optional[_Job] = None

        root = QVBoxLayout(self)
        top = QHBoxLayout()
        for text, slot, ic in (("Thêm file video", self._add_file, "add_rounded"),
                               ("Thêm camera / URL", self._add_other, "add_rounded"),
                               ("Sửa", self._edit, "edit_outlined"), ("Xóa", self._delete, "delete_outline_rounded"),
                               ("Kiểm tra kết nối", self._test, "cable_outlined"),
                               ("Dò camera USB", self._scan, "search_rounded")):
            b = QPushButton(text)
            b.setIcon(icon(ic, "text", 18))
            b.clicked.connect(slot)
            top.addWidget(b)
        top.addStretch(1)
        root.addLayout(top)

        body = QHBoxLayout()
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setTextElideMode(Qt.TextElideMode.ElideMiddle)   # giữ được tên file ở cuối đường dẫn
        self.table.setWordWrap(False)
        self.table.doubleClicked.connect(self._open)
        body.addWidget(self.table, 3)
        right = QVBoxLayout()
        self.preview = ImageView("Bấm Kiểm tra kết nối\nđể xem trước")
        self.preview.setMinimumSize(280, 160)
        right.addWidget(self.preview, 1)
        self.info = QLabel()
        self.info.setObjectName("muted")
        self.info.setWordWrap(True)
        right.addWidget(self.info)
        body.addLayout(right, 2)
        root.addLayout(body, 1)

        bottom = QHBoxLayout()
        note = QLabel("Nguồn được tự thêm vào danh sách mỗi khi mở. Căn chỉnh camera được lưu riêng cho từng "
                      "nguồn và tự nạp lại khi mở nguồn đó.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        bottom.addWidget(note, 1)
        open_btn = QPushButton("Mở nguồn đã chọn")
        open_btn.setIcon(icon("play_arrow_rounded", "on_accent", 18))
        open_btn.setObjectName("primary")
        open_btn.clicked.connect(self._open)
        close = QPushButton("Đóng")
        close.clicked.connect(self.reject)
        bottom.addWidget(open_btn)
        bottom.addWidget(close)
        root.addLayout(bottom)

        fit_to_screen(self, 1180, 560)
        self.refresh(select_uri=current_uri)

    # ------------------------------------------------------------------

    def refresh(self, select_uri: Optional[str] = None):
        select_uri = normalize_source(select_uri) if select_uri else None
        self.rows = self.db.list_sources()
        self.table.setRowCount(0)
        for r in self.rows:
            i = self.table.rowCount()
            self.table.insertRow(i)
            values = [r["name"], SOURCE_TYPE_VI.get(r["source_type"], r["source_type"]), r["uri"],
                      f"Riêng ({r['calibrations']} lần)" if r["calibrations"] else "Dùng chung", str(r["sessions"]),
                      r["last_used_at"] or "chưa dùng"]
            for c, v in enumerate(values):
                item = QTableWidgetItem(v)
                if c == 2:
                    item.setToolTip(r["uri"] + (f"\n{r['description']}" if r["description"] else ""))
                self.table.setItem(i, c, item)
            if r["uri"] == select_uri:
                self.table.selectRow(i)
        if self.table.rowCount() and not self.table.selectedItems():
            self.table.selectRow(0)

    def _current(self):
        items = self.table.selectedItems()
        return self.rows[items[0].row()] if items else None

    def _add_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn video/ảnh", "", "Video/Ảnh (*.mp4 *.avi *.mov *.mkv *.wmv *.jpg *.jpeg *.png *.bmp)")
        if path:
            self._save_new(Path(path).stem, classify_source(path), path, "")

    def _add_other(self):
        dlg = SourceEditDialog(self, uri="0")
        if dlg.exec():
            self._save_new(*dlg.values)

    def _save_new(self, name, kind, uri, desc):
        if self.db.get_source(uri):
            QMessageBox.information(self, "Nguồn", "Nguồn này đã có trong danh sách.")
        else:
            self.db.add_source(name, kind, uri, desc)
        self.refresh(select_uri=uri)

    def _edit(self):
        r = self._current()
        if r is None:
            return
        dlg = SourceEditDialog(self, r["name"], r["uri"], r["description"] or "")
        if dlg.exec():
            try:
                self.db.update_source(r["id"], *dlg.values)
            except Exception as e:  # uri trùng (UNIQUE)
                QMessageBox.warning(self, "Nguồn", f"Không lưu được: {e}")
            self.refresh(select_uri=dlg.values[2])

    def _delete(self):
        r = self._current()
        if r is None:
            return
        if QMessageBox.question(self, "Xóa nguồn", f"Xóa nguồn '{r['name']}' khỏi danh sách?\n"
                                "(Nhật ký các phiên đã giám sát vẫn được giữ lại.)") == QMessageBox.StandardButton.Yes:
            self.db.delete_source(r["id"])
            self.refresh()

    def _test(self):
        r = self._current()
        if r is None or self._job is not None:
            return
        self.info.setText(f"Đang kết nối {r['uri']}…")
        self._run(probe_source, r["uri"], on_done=lambda res: self._show_probe(r, res),
                  on_fail=lambda msg: self.info.setText(
                      f"<span style='color:{C['danger']}'>Không kết nối được: {msg}</span>"))

    def _show_probe(self, r, res):
        self.preview.set_image(bgr_to_qimage(res["frame"]))
        extra = f" · {res['frames']} khung" if res["frames"] > 1 else ""
        self.info.setText(f"<span style='color:{C['safe']}'>Kết nối tốt</span> · {res['width']}×{res['height']} · "
                          f"{res['fps']} FPS{extra}")

    def _scan(self):
        if self._job is not None:
            return
        self.info.setText("Đang dò camera USB (chỉ số 0-4)…")
        self._run(find_cameras, on_done=self._scan_done,
                  on_fail=lambda msg: self.info.setText(f"Lỗi khi dò camera: {msg}"))

    def _scan_done(self, cams):
        if not cams:
            self.info.setText("Không tìm thấy camera USB nào.")
            return
        added = 0
        for i in cams:
            if not self.db.get_source(str(i)):
                self.db.add_source(f"Camera USB {i}", "camera", str(i), "Tìm thấy khi dò camera")
                added += 1
        self.info.setText(f"Tìm thấy camera: {', '.join(map(str, cams))} · đã thêm {added} nguồn mới.")
        self.refresh(select_uri=str(cams[0]))

    def _run(self, fn, *args, on_done, on_fail):
        job = _Job(fn, *args)
        job.done.connect(on_done)
        job.failed.connect(on_fail)
        job.finished.connect(lambda: setattr(self, "_job", None))
        self._job = job
        job.start()

    def _open(self):
        r = self._current()
        if r is not None:
            self.selected_uri = r["uri"]
            self.accept()

    def reject(self):
        if self._job is not None:
            self._job.wait(15000)
        super().reject()

    def accept(self):
        if self._job is not None:
            self._job.wait(15000)
        super().accept()
