"""Kiểu dữ liệu chung của trợ lý: kết quả trả lời và giới hạn an toàn cho tham số."""

from dataclasses import dataclass, replace
from typing import Optional

from adas.config import SafetyPolicy

# Giới hạn hợp lệ cho từng tham số (kẹp giá trị AI trả về để đảm bảo an toàn)
LIMITS = {
    "time_gap_s": (2.0, 6.0),          # không thấp hơn quy tắc 2 giây
    "weather_factor": (1.0, 3.0),      # không bao giờ nhỏ hơn bảng quy định khô ráo
    "danger_ratio": (0.3, 0.8),
    "min_distance_m": (3.0, 20.0),
    "ttc_warning_s": (2.0, 8.0),
    "ttc_danger_s": (1.0, 4.0),
    "road_mu": (0.1, 0.9),
    "visibility_m": (0.0, 1000.0),
}


@dataclass
class AssistantResult:
    reply: str
    policy: SafetyPolicy
    speed_kmh: Optional[float]
    source: str                   # "Claude" | "Offline"
    note: str = ""                # Ghi chú kỹ thuật (vd: lý do chuyển sang offline)


def clamp_policy(p: SafetyPolicy) -> SafetyPolicy:
    values = {}
    for k, (lo, hi) in LIMITS.items():
        values[k] = float(min(max(getattr(p, k), lo), hi))
    if values["ttc_danger_s"] >= values["ttc_warning_s"]:
        values["ttc_danger_s"] = max(1.0, values["ttc_warning_s"] - 1.0)
    return replace(p, **values)
