"""
Ngưỡng khoảng cách an toàn theo tốc độ và điều kiện đường.

1. Mặt đường khô ráo - theo quy định của Bộ GTVT (Thông tư 31/2019/TT-BGTVT, Điều 11):
       V = 60 km/h            -> tối thiểu  35 m
       60 < V <= 80 km/h      -> tối thiểu  55 m
       80 < V <= 100 km/h     -> tối thiểu  70 m
       100 < V <= 120 km/h    -> tối thiểu 100 m
   V < 60 km/h: quy định để người lái tự chủ động giữ khoảng cách phù hợp với mật độ
   phương tiện và tình hình giao thông -> hệ thống ƯỚC TÍNH bằng quy tắc 2 giây (d = v·2s).
   Người dùng tùy chỉnh ngưỡng cảnh báo cho từng dải tốc độ (SafetyPolicy.band_gaps_m,
   time_gap_s); ngưỡng của mỗi dải không bao giờ thấp hơn mức quy định ở trên.

2. Điều kiện bất lợi (mưa, sương mù, ban đêm, trơn trượt...): quy định chỉ yêu cầu giữ
   khoảng cách LỚN HƠN bảng trên, không nêu con số. Hệ thống ước tính hệ số nhân dựa trên
   vật lý phanh: quãng phanh tỷ lệ nghịch với hệ số bám μ, nên
       hệ số ≈ μ_khô / μ_điều_kiện     (μ_khô ≈ 0,7)
   và cộng thêm biên cho thời gian phản xạ khi thiếu sáng / tài xế mệt.

3. Tầm nhìn hạn chế (sương mù): khuyến nghị tốc độ tối đa sao cho quãng đường dừng xe
   (phản xạ + phanh) không vượt quá tầm nhìn.
"""

import math
from dataclasses import dataclass
from typing import Dict, Optional

from adas.config import SafetyPolicy
from adas.formatting import vn_num

# (tốc độ tối đa của khoảng km/h, khoảng cách tối thiểu m) - mặt đường khô ráo
LEGAL_GAP_TABLE = [(60, 35.0), (80, 55.0), (100, 70.0), (120, 100.0)]
LEGAL_MIN_SPEED = 60.0
LEGAL_MAX_SPEED = 120.0           # Tốc độ tối đa trên cao tốc Việt Nam
DEFAULT_TIME_GAP_S = 2.0          # Quy tắc 2 giây - ước tính cho V < 60 km/h
DRY_MU = 0.7
G = 9.81

RISK_ORDER = {"none": 0, "info": 0, "safe": 0, "warning": 1, "danger": 2}


@dataclass(frozen=True)
class RoadCondition:
    key: str
    name: str
    factor: float          # Hệ số nhân khoảng cách so với mặt đường khô
    mu: float              # Hệ số bám ước tính
    ttc_warning_s: float
    ttc_danger_s: float
    advice: str


# Ước tính cho các điều kiện bất lợi (hệ số ≈ 0,7/μ, làm tròn)
ROAD_CONDITIONS: Dict[str, RoadCondition] = {c.key: c for c in [
    RoadCondition("dry", "Đường khô ráo, tầm nhìn tốt", 1.0, 0.70, 4.0, 2.0,
                  "Giữ khoảng cách tối thiểu theo bảng quy định."),
    RoadCondition("wet", "Mặt đường ướt, mưa nhỏ", 1.4, 0.50, 5.0, 2.5,
                  "Độ bám giảm (hệ số bám ≈ 0,5), quãng phanh dài hơn khoảng 1,4 lần."),
    RoadCondition("heavy_rain", "Mưa to, mặt đường đọng nước", 2.0, 0.35, 6.0, 3.0,
                  "Nguy cơ trượt nước (hệ số bám ≈ 0,35): giảm tốc độ, giữ khoảng cách gấp đôi."),
    RoadCondition("fog", "Sương mù, tầm nhìn hạn chế", 1.5, 0.60, 5.5, 3.0,
                  "Bật đèn sương mù/đèn cốt, giảm tốc để dừng kịp trong phạm vi nhìn thấy."),
    RoadCondition("slippery", "Mặt đường trơn trượt (dầu, bùn, sỏi)", 2.5, 0.25, 6.0, 3.0,
                  "Độ bám rất thấp (hệ số bám ≈ 0,25): giảm tốc rõ rệt, tránh phanh gấp."),
]}

# Hệ số cộng thêm (nhân dồn) cho các yếu tố không phụ thuộc mặt đường
MODIFIERS = {
    "night": ("Ban đêm, thiếu ánh sáng", 1.2),       # Nhận biết chậm hơn
    "heavy_vehicle": ("Xe chủ chở nặng", 1.3),        # Quãng phanh xe tải/xe khách dài hơn
    "tired": ("Tài xế mệt mỏi", 1.15),                # Thời gian phản xạ tăng
}
MAX_FACTOR = 3.0


def condition_policy(condition_key: str, modifiers=(), visibility_m: float = 0.0,
                     base: Optional[SafetyPolicy] = None) -> SafetyPolicy:
    """Tạo SafetyPolicy từ một điều kiện mặt đường + các yếu tố cộng thêm."""
    cond = ROAD_CONDITIONS[condition_key]
    factor = cond.factor
    names = [cond.name]
    ttc_w, ttc_d = cond.ttc_warning_s, cond.ttc_danger_s
    for m in modifiers:
        label, mul = MODIFIERS[m]
        factor *= mul
        names.append(label.lower())
        ttc_w, ttc_d = ttc_w + 0.5, ttc_d + 0.25
    b = base or SafetyPolicy()
    return SafetyPolicy(
        time_gap_s=b.time_gap_s,              # Ngưỡng theo dải tốc độ do người dùng đặt, giữ nguyên
        band_gaps_m=list(b.band_gaps_m),
        weather_factor=round(min(factor, MAX_FACTOR), 2),
        danger_ratio=b.danger_ratio,
        min_distance_m=b.min_distance_m,
        ttc_warning_s=min(ttc_w, 8.0),
        ttc_danger_s=min(ttc_d, 4.0),
        use_legal_table=True,
        condition=", ".join(names),
        road_mu=cond.mu,
        visibility_m=visibility_m,
    )


@dataclass
class Thresholds:
    speed_kmh: float
    safe_m: float                 # Dưới ngưỡng này -> CẢNH BÁO
    danger_m: float               # Dưới ngưỡng này -> NGUY HIỂM
    gap_m: float                  # Thành phần theo quy tắc thời gian (time-gap)
    legal_m: Optional[float]      # Khoảng cách tối thiểu theo quy định (None nếu < 60 km/h)
    band_m: Optional[float]       # Ngưỡng người dùng đặt cho dải tốc độ này, đường khô (>= legal_m)
    over_speed_limit: bool        # Vượt 120 km/h
    recommended_speed_kmh: Optional[float]  # Tốc độ tối đa khuyến nghị theo tầm nhìn


def legal_min_gap(speed_kmh: float) -> Optional[float]:
    """
    Khoảng cách an toàn tối thiểu khi mặt đường khô ráo theo quy định.
    Trả về None khi V < 60 km/h (người lái tự chủ động).
    Trên 120 km/h (vượt tốc độ tối đa cho phép) ngoại suy tuyến tính để vẫn an toàn.
    """
    if speed_kmh < LEGAL_MIN_SPEED:
        return None
    for vmax, gap in LEGAL_GAP_TABLE:
        if speed_kmh <= vmax:
            return gap
    return LEGAL_GAP_TABLE[-1][1] * speed_kmh / LEGAL_MAX_SPEED


def band_gap_m(speed_kmh: float, policy: SafetyPolicy) -> Optional[float]:
    """
    Ngưỡng cảnh báo (đường khô) người dùng đặt cho dải tốc độ chứa V, không bao giờ thấp hơn
    mức tối thiểu theo quy định. None khi V < 60 km/h. Trên 120 km/h ngoại suy như legal_min_gap.
    """
    legal = legal_min_gap(speed_kmh)
    if legal is None:
        return None
    i = next((i for i, (vmax, _) in enumerate(LEGAL_GAP_TABLE) if speed_kmh <= vmax),
             len(LEGAL_GAP_TABLE) - 1)
    try:
        user = float(policy.band_gaps_m[i])
    except (IndexError, TypeError, ValueError):
        return legal
    if speed_kmh > LEGAL_MAX_SPEED:
        user *= speed_kmh / LEGAL_MAX_SPEED
    return max(user, legal)


def stopping_distance_m(speed_kmh: float, mu: float, reaction_s: float = 1.5) -> float:
    """Quãng đường dừng xe = quãng phản xạ + quãng phanh v²/(2μg)."""
    v = speed_kmh / 3.6
    return v * reaction_s + v * v / (2 * mu * G)


def recommended_speed_kmh(visibility_m: float, mu: float, reaction_s: float = 1.5) -> float:
    """Tốc độ lớn nhất để quãng đường dừng xe không vượt quá tầm nhìn."""
    a = mu * G
    v = a * (-reaction_s + math.sqrt(reaction_s ** 2 + 2 * visibility_m / a))
    return v * 3.6


def compute_thresholds(speed_kmh: float, policy: SafetyPolicy) -> Thresholds:
    speed_kmh = max(speed_kmh, 0.0)
    gap = speed_kmh / 3.6 * policy.time_gap_s
    legal = legal_min_gap(speed_kmh) if policy.use_legal_table else None
    band = band_gap_m(speed_kmh, policy) if legal is not None else None
    # Khô ráo: >= 60 km/h theo ngưỡng của dải (>= bảng quy định); < 60 km/h theo quy tắc thời gian
    base = max(band if band is not None else gap, policy.min_distance_m)
    safe = base * policy.weather_factor
    danger = max(policy.min_distance_m, safe * policy.danger_ratio)
    rec = (recommended_speed_kmh(policy.visibility_m, policy.road_mu)
           if policy.visibility_m and policy.visibility_m > 0 else None)
    return Thresholds(speed_kmh=speed_kmh, safe_m=safe, danger_m=danger, gap_m=gap,
                      legal_m=legal, band_m=band, over_speed_limit=speed_kmh > LEGAL_MAX_SPEED,
                      recommended_speed_kmh=rec)


def _m(v: float) -> int:
    return int(v + 0.5)                 # làm tròn như Dart .round() (Python round() là kiểu ngân hàng)


def threshold_basis(thr: Thresholds, policy: SafetyPolicy) -> str:
    """Câu giải thích ngưỡng đang áp dụng; giống hệt thresholdBasis() của app mobile."""
    if thr.legal_m is not None and thr.band_m is not None and thr.band_m > thr.legal_m:
        s = f"Bạn đặt {_m(thr.band_m)} m (luật ≥ {_m(thr.legal_m)} m)"
    elif thr.legal_m is not None:
        s = f"Theo luật (đường khô): {_m(thr.legal_m)} m"
    else:
        s = f"Quy tắc {vn_num(policy.time_gap_s)} giây: {_m(thr.gap_m)} m"
    if policy.weather_factor > 1.0:
        s += f"\n× {vn_num(policy.weather_factor)} do điều kiện đường"
    return s


def classify_risk(distance_m: float, ttc_s: Optional[float],
                  thr: Thresholds, policy: SafetyPolicy) -> str:
    """Phân loại mức rủi ro: 'danger' | 'warning' | 'safe'."""
    if distance_m < thr.danger_m or (ttc_s is not None and ttc_s < policy.ttc_danger_s):
        return "danger"
    if distance_m < thr.safe_m or (ttc_s is not None and ttc_s < policy.ttc_warning_s):
        return "warning"
    return "safe"
