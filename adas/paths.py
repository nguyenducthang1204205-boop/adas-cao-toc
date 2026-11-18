"""
Đường dẫn của ứng dụng - một chỗ duy nhất, chạy được cả từ mã nguồn lẫn bản đóng gói (.exe).

Khi đóng gói bằng PyInstaller (tools/build_exe.py), sys.frozen = True và thư mục ứng dụng là thư mục
chứa ADAS.exe: models/, assets/ được chép cạnh exe; data/ (CSDL, ảnh vi phạm) và outputs/ cũng nằm ở
đó để người dùng dễ tìm và sao lưu.
"""

import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = APP_DIR / "data"
DB_PATH = DATA_DIR / "adas.db"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
CONFIG_PATH = APP_DIR / "config" / "settings.json"     # chỉ để nhập cấu hình cũ lần đầu
ASSETS_DIR = APP_DIR / "assets"
FONT_DIR = ASSETS_DIR / "fonts"
UI_ASSETS_DIR = ASSETS_DIR / "ui"
