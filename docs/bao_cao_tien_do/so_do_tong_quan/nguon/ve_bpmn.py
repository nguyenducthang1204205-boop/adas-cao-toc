# -*- coding: utf-8 -*-
"""Bản BPMN cho báo cáo tổng quan: dùng lại docs/so_do/nguon/bpmn.py, đổi nhãn kho dữ liệu
từ tên bảng sang tên khái niệm.

    python ve_bpmn.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[2] / "so_do" / "nguon"
sys.path.insert(0, str(SRC))
import build  # noqa: E402

NHAN = {
    "CSDL data/adas.db": "Cơ sở dữ liệu",
    "camera_calibrations": "Thông số camera",
    "system_config, config_history": "Cấu hình ngưỡng, lịch sử cấu hình",
    "monitoring_sessions": "Phiên giám sát",
    "violations, snapshots": "Nhật ký vi phạm, ảnh",
    "Phân tích mô tả (offline / Claude), đề xuất SafetyPolicy": "Phân tích mô tả (offline / Claude), đề xuất ngưỡng",
    "Khởi động luồng xử lý": "Khởi động xử lý giám sát",
    "Hiển thị khung màu, banner, BEV, thẻ trạng thái": "Hiển thị khung màu, khoảng cách, ảnh nhìn từ trên xuống",
}
code = (SRC / "bpmn.py").read_text(encoding="utf-8")
for cu, moi in NHAN.items():
    assert f'"{cu}"' in code, cu
    code = code.replace(f'"{cu}"', f'"{moi}"')
mod = {"__name__": "bpmn_tong_quan", "__file__": str(SRC / "bpmn.py")}
exec(compile(code, "bpmn_tong_quan", "exec"), mod)
for name, fn in mod["DIAGRAMS"].items():
    svg = HERE.parent / f"{name}.svg"
    svg.write_text(fn().draw(), encoding="utf-8")
    build.svg_to_png(svg, HERE.parent / f"{name}.png")
    print("✔", name)
