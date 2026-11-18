# -*- coding: utf-8 -*-
"""Dựng các sơ đồ tổng quan (mức khái niệm) cho báo cáo tiến độ.

    MMDC=<đường dẫn mmdc> python ve.py

Dùng lại cấu hình và cách chụp PNG của docs/so_do/nguon/build.py.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "so_do" / "nguon"))
import build  # noqa: E402

build.HERE = HERE
build.OUT = HERE.parent
build.build_mermaid(set(sys.argv[1:]))
