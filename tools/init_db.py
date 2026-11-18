"""
Khởi tạo cơ sở dữ liệu SQLite của hệ thống (data/adas.db).

    python tools/init_db.py            # tạo lược đồ (nếu chưa có) + nạp cấu hình, in cấu trúc
    python tools/init_db.py --reset    # sao lưu CSDL cũ thành adas_<thời gian>.db.bak rồi tạo mới

Ứng dụng cũng tự khởi tạo CSDL khi chạy lần đầu; script này để chủ động tạo/kiểm tra.
"""

import argparse
import sqlite3
import sys
from contextlib import closing
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from adas.config import AppConfig  # noqa: E402
from adas.paths import DB_PATH  # noqa: E402
from adas.storage.database import SCHEMA_VERSION, Database


def main():
    ap = argparse.ArgumentParser(description="Khởi tạo CSDL hệ thống ADAS")
    ap.add_argument("--reset", action="store_true", help="Sao lưu CSDL hiện có rồi tạo mới")
    args = ap.parse_args()

    if args.reset and DB_PATH.exists():
        backup = DB_PATH.with_name(f"adas_{datetime.now():%Y%m%d_%H%M%S}.db.bak")
        for suffix in ("-wal", "-shm"):
            Path(str(DB_PATH) + suffix).unlink(missing_ok=True)
        DB_PATH.replace(backup)
        print(f"Đã sao lưu CSDL cũ: {backup.name}")

    db = Database()                     # tạo bảng / chỉ mục / view nếu chưa có
    cfg = AppConfig.load(db)            # nạp cấu hình (từ CSDL, settings.json hoặc mặc định)
    print(f"CSDL: {DB_PATH}  (phiên bản lược đồ {SCHEMA_VERSION})")
    print(f"Cấu hình hiện hành: tốc độ {cfg.speed_kmh:.0f} km/h · {cfg.policy.condition} · "
          f"mô hình {cfg.model.weights}")

    with closing(sqlite3.connect(str(DB_PATH))) as con:
        objs = con.execute("SELECT type, name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' "
                           "ORDER BY type DESC, name").fetchall()
        print("\nĐối tượng CSDL:")
        for typ, name in objs:
            if typ == "table":
                n = con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                cols = [r[1] for r in con.execute(f"PRAGMA table_info({name})")]
                print(f"  [bảng] {name:<20} {n:>6} dòng · {', '.join(cols)}")
            else:
                print(f"  [{'chỉ mục' if typ == 'index' else typ}] {name}")


if __name__ == "__main__":
    main()
