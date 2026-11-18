"""Xuất các màn hình chính của ứng dụng ra SVG (nhập vào Figma) và PNG (chèn vào quyển báo cáo).

Chạy giao diện thật ở chế độ ẩn (không hiện cửa sổ), đưa từng màn hình về trạng thái tiêu biểu rồi vẽ ra
QSvgGenerator: hình khối thành vector, chữ thành lớp chữ (font Be Vietnam Pro, Figma có sẵn), biểu tượng và
khung hình video thành ảnh nhúng. Dùng bản sao tạm của data/adas.db nên không ghi gì vào CSDL thật.

    python tools/export_mockups.py [--video PATH] [--out docs/giao_dien/figma]

Nhập vào Figma: kéo thả các file .svg vào một trang (mỗi file thành một frame), xem README.md trong thư mục ra.
"""

import argparse
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DEFAULT_VIDEO = Path.home() / "Downloads" / "videoplayback.mp4"


def _clean_svg(path: Path, title: str, w: int, h: int):
    """Kích thước theo px (Qt ghi mm), bỏ các nhóm rỗng để cây lớp trong Figma gọn hơn."""
    s = path.read_text(encoding="utf-8")
    s = re.sub(r'<svg width="[^"]*" height="[^"]*"', f'<svg width="{w}" height="{h}"', s, count=1)
    s = s.replace("<desc>Generated with Qt</desc>", "<desc>ADAS Cao tốc - mockup giao diện</desc>")
    s = re.sub(r"<title>.*?</title>", f"<title>{title}</title>", s, count=1)
    empty = re.compile(r"<g [^>]*>\s*</g>\s*")
    while True:
        s2 = empty.sub("", s)
        if s2 == s:
            break
        s = s2
    path.write_text(s, encoding="utf-8")


def export(widget, out: Path, name: str, title: str, app):
    from PySide6.QtCore import QRect
    from PySide6.QtSvg import QSvgGenerator

    for _ in range(5):
        app.processEvents()
    size = widget.size()
    svg = out / f"{name}.svg"
    gen = QSvgGenerator()
    gen.setFileName(str(svg))
    gen.setSize(size)
    gen.setViewBox(QRect(0, 0, size.width(), size.height()))
    gen.setTitle(title)
    widget.render(gen)
    del gen
    _clean_svg(svg, title, size.width(), size.height())
    widget.grab().save(str(out / f"{name}.png"))
    print(f"  {name}: {size.width()}×{size.height()}  {svg.stat().st_size // 1024} KB")


def _hidden(widget, w=None, h=None):
    from PySide6.QtCore import Qt
    widget.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    widget.show()
    if w and h:
        widget.resize(w, h)
    return widget


def _pump(app, seconds: float, until=None):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        if until is not None and until():
            return True
        time.sleep(0.01)
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--video", default=str(DEFAULT_VIDEO), help="video cao tốc dùng cho màn hình giám sát")
    ap.add_argument("--out", default=str(ROOT / "docs" / "giao_dien" / "figma"))
    ap.add_argument("--size", default="1536x864",
                    help="kích thước cửa sổ chính (px logic); 1536x864 = màn 1080p ở tỉ lệ 125 %%, khớp prototype "
                         "Figma toàn màn hình ở kích thước thật")
    ap.add_argument("--max-wait", type=float, default=90, help="số giây chạy video tối đa để chờ một cảnh báo")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    win_w, win_h = (int(x) for x in args.size.lower().split("x"))

    # CSDL và thư mục ảnh vi phạm tạm: không làm bẩn dữ liệu thật
    tmp = Path(tempfile.mkdtemp(prefix="adas_mockup_"))
    import adas.paths
    import adas.storage.database as dbm
    if adas.paths.DB_PATH.exists():
        shutil.copy(adas.paths.DB_PATH, tmp / "adas.db")
    dbm.Database.__init__.__defaults__ = (tmp / "adas.db",)
    import adas.alert.violations as violations
    violations.SNAPSHOT_DIR = tmp / "snapshots"

    from PySide6.QtCore import QLocale
    from PySide6.QtWidgets import QApplication, QTabWidget
    QLocale.setDefault(QLocale(QLocale.Language.Vietnamese, QLocale.Country.Vietnam))
    app = QApplication(sys.argv)
    from gui.rendering import ensure_fonts
    from gui.styles import STYLESHEET
    ensure_fonts()
    app.setStyleSheet(STYLESHEET)

    from adas.config import AppConfig
    from adas.stream.sources import read_first_frame
    from gui.dialogs.calibration import CalibrationDialog
    from gui.dialogs.calibration_wizard import CalibrationWizard
    from gui.dialogs.history import HistoryDialog
    from gui.dialogs.settings import SettingsDialog
    from gui.dialogs.sources import SourceDialog
    from gui.main_window import MainWindow

    cfg = AppConfig.load()
    cfg.alert.sound_enabled = False
    video = str(Path(args.video).resolve())
    print(f"Xuất mockup vào {out}")

    # ---- 1. Màn hình chính: chào mừng ----
    win = _hidden(MainWindow(cfg), win_w, win_h)
    export(win, out, "01_giam_sat_chao_mung", "Màn hình giám sát - chưa chạy", app)

    # ---- 2. Màn hình chính: đang giám sát, có xe phía trước ở mức cảnh báo ----
    frame = None
    if os.path.isfile(video):
        win.source_spec = video
        win.start()
        seen = {"n": 0, "hit": False}
        t0 = time.time()

        def on_frame(_o, _b, st):
            seen["n"] += 1
            if seen["hit"]:
                return
            # đợi tốc độ đo từ video ổn định rồi mới bắt một khung mà chính xe phía trước đang ở mức cảnh báo
            if (time.time() - t0 > 8 and st.get("lead_distance") and st.get("lead_risk") in ("warning", "danger")
                    and st.get("level") == st.get("lead_risk")):
                seen["hit"] = True
                win.worker.set_paused(True)
                win.worker.frame_ready.disconnect(win._on_frame)   # giữ nguyên khung này trên màn hình

        win.worker.frame_ready.connect(on_frame)
        hit = _pump(app, args.max_wait, lambda: seen["hit"])
        win.act_pause.setChecked(True)
        win.toggle_pause()
        _pump(app, 0.5)
        print(f"  ({seen['n']} khung, {'có' if hit else 'không có'} cảnh báo)")
        export(win, out, "02_giam_sat_dang_chay", "Màn hình giám sát - đang cảnh báo", app)
        frame = win.worker.last_frame.copy() if win.worker and win.worker.last_frame is not None else None
        win.stop()
    else:
        print(f"  Không thấy video {video} - bỏ qua màn hình đang giám sát")
    if frame is None and os.path.isfile(video):
        frame = read_first_frame(video)

    # ---- 3-5. Trình căn chỉnh 3 bước ----
    if frame is not None:
        wiz = CalibrationWizard(frame.copy(), cfg.calibration, win, video_path=video, start_frame=0,
                                auto_calib=cfg.auto_calib)
        _hidden(wiz)
        wiz._vp_thread.wait(30000)
        _pump(app, 0.5)
        export(wiz, out, "03_can_chinh_b1_xe_va_so_do", "Căn chỉnh camera - Bước 1: Xe và số đo", app)
        wiz._go(1)
        export(wiz, out, "04_can_chinh_b2_duong_chan_troi", "Căn chỉnh camera - Bước 2: Đường chân trời", app)
        wiz._go(2)
        export(wiz, out, "05_can_chinh_b3_hoan_tat", "Căn chỉnh camera - Bước 3: Hoàn tất", app)
        wiz.reject()

        adv = _hidden(CalibrationDialog(frame.copy(), cfg.calibration, win, video_path=video,
                                        speed_kmh=cfg.speed_kmh))
        export(adv, out, "06_can_chinh_nang_cao_4_diem", "Căn chỉnh nâng cao - chấm 4 điểm", app)
        adv.reject()

    # ---- 7. Cài đặt ngưỡng cảnh báo theo dải tốc độ ----
    st = _hidden(SettingsDialog(cfg, "", win))
    tabs = st.findChild(QTabWidget)
    tabs.setCurrentIndex(1)
    export(st, out, "07_cai_dat_nguong_canh_bao", "Cài đặt - Ngưỡng cảnh báo theo dải tốc độ", app)
    st.reject()

    # ---- 8. Nhật ký vi phạm: chọn phiên có nhiều vi phạm và một vi phạm có ảnh ----
    hist = _hidden(HistoryDialog(win))
    s = hist.sessions
    best, best_n = 0, -1
    for r in range(s.rowCount()):
        it = s.item(r, 4)
        n = int(it.text()) if it and it.text().isdigit() else 0
        if n > best_n:
            best, best_n = r, n
    if s.rowCount():
        s.selectRow(best)
        _pump(app, 0.2)
        v = hist.violations
        for r in range(v.rowCount()):
            v.selectRow(r)
            _pump(app, 0.05)
            if hist.snapshot.has_image():
                break
    export(hist, out, "08_nhat_ky_vi_pham", "Nhật ký vi phạm và lịch sử phiên giám sát", app)
    hist.reject()

    # ---- 9. Quản lý nguồn video/camera ----
    src = _hidden(SourceDialog(win, current_uri=video))
    export(src, out, "09_quan_ly_nguon", "Quản lý nguồn video/camera", app)
    src.reject()

    win.close()
    shutil.rmtree(tmp, ignore_errors=True)
    print("Xong.")


if __name__ == "__main__":
    main()
