"""
Đóng gói ứng dụng desktop thành thư mục chạy được trên Windows (PyInstaller, chế độ onedir):

    python tools/build_exe.py            # -> dist/ADAS/ADAS.exe (+ models/, assets/, data/ cạnh exe)
    python tools/build_exe.py --zip      # thêm dist/ADAS_win64.zip để mang sang máy khác

Bản đóng gói chứa Python, PyTorch, Ultralytics, OpenCV, PySide6 nên không cần cài gì trên máy chạy thử.
models/ và assets/ được chép cạnh ADAS.exe (adas/paths.py coi thư mục chứa exe là thư mục ứng dụng),
còn data/ khởi tạo rỗng: CSDL tự tạo ở lần chạy đầu.
Thư mục làm việc của PyInstaller đặt ở %LOCALAPPDATA% (đường dẫn ASCII) vì đường dẫn dự án có dấu.
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
NAME = "ADAS"
WORK = Path(os.environ.get("LOCALAPPDATA", ROOT)) / "adas_pyinstaller"


def make_icon() -> Path:
    """app_icon.png -> .ico nhiều kích thước cho exe."""
    from PIL import Image
    ico = WORK / "app_icon.ico"
    ico.parent.mkdir(parents=True, exist_ok=True)
    Image.open(ROOT / "assets" / "ui" / "app_icon.png").save(
        ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return ico


def build() -> Path:
    import PyInstaller.__main__

    args = [
        str(ROOT / "main.py"),
        "--name", NAME,
        "--noconfirm", "--clean", "--windowed",
        "--icon", str(make_icon()),
        "--distpath", str(DIST),
        "--workpath", str(WORK / "build"),
        "--specpath", str(WORK),
        "--paths", str(ROOT),
        # Ultralytics đọc cfg/*.yaml (bytetrack.yaml...) lúc chạy; anthropic chỉ import khi bật Claude
        "--collect-data", "ultralytics",
        "--hidden-import", "anthropic",
        "--hidden-import", "lap",
        "--exclude-module", "tkinter",
        "--exclude-module", "matplotlib.backends.backend_tkagg",
    ]
    PyInstaller.__main__.run(args)

    app_dir = DIST / NAME
    for sub in ("models", "assets"):
        dst = app_dir / sub
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(ROOT / sub, dst)
    (app_dir / "data").mkdir(exist_ok=True)
    (app_dir / "outputs").mkdir(exist_ok=True)
    shutil.copy2(ROOT / "README.md", app_dir / "README.md")
    return app_dir


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--zip", action="store_true", help="nén thư mục kết quả thành dist/ADAS_win64.zip")
    args = ap.parse_args()

    app_dir = build()
    exe = app_dir / f"{NAME}.exe"
    size_mb = sum(f.stat().st_size for f in app_dir.rglob("*") if f.is_file()) / 2**20
    print(f"\n[OK] {exe}  ({size_mb:,.0f} MB)")
    if args.zip:
        archive = shutil.make_archive(str(DIST / f"{NAME}_win64"), "zip", DIST, NAME)
        print(f"[OK] {archive}")
    return 0 if exe.exists() else 1


if __name__ == "__main__":
    sys.exit(main())
