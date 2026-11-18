"""
Hệ thống cảnh báo khoảng cách an toàn giữa các phương tiện trên cao tốc
thời gian thực ứng dụng YOLOv11 và thị giác máy tính.

Chạy:
    python main.py                       # mở giao diện
    python main.py --source video.mp4    # mở giao diện và chạy ngay video
    python main.py --source 0            # camera USB số 0
    python main.py --source rtsp://...   # camera IP
"""

import argparse
import sys
from pathlib import Path

# Cho phép chạy từ thư mục bất kỳ
sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> int:
    parser = argparse.ArgumentParser(description="ADAS - cảnh báo khoảng cách an toàn trên cao tốc")
    parser.add_argument("--source", help="File video/ảnh, chỉ số camera hoặc URL RTSP")
    args = parser.parse_args()

    from gui.app import run
    return run(args.source)


if __name__ == "__main__":
    sys.exit(main())
