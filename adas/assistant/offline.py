"""
Bộ tư vấn offline: luật từ khóa tiếng Việt (gõ có dấu hoặc không dấu), không cần Internet.
App Android: core/Assistant.kt là bản port 1:1 và phải trả lời giống từng byte.
"""

import re
import unicodedata
from dataclasses import replace
from typing import Optional

from adas.alert.thresholds import ROAD_CONDITIONS, compute_thresholds, condition_policy
from adas.assistant.base import AssistantResult, clamp_policy
from adas.config import SafetyPolicy
from adas.formatting import vn_num


def _fold(text: str) -> str:
    """Chữ thường, bỏ dấu tiếng Việt (đ -> d) để hiểu cả câu gõ không dấu: "troi mua to"."""
    text = text.lower().replace("đ", "d")
    return "".join(ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn")


# Mỗi mục: (khóa, cụm từ, từ đơn). Cụm từ dùng cho cả câu có dấu lẫn không dấu. Từ đơn chỉ dùng
# khi câu có dấu, vì bỏ dấu sẽ trùng từ khác: mù/mưa -> "mu", mệt/mét -> "met", tối/tôi -> "toi",
# bão/báo -> "bao".
# Thứ tự ưu tiên: điều kiện nặng nhất được nhận trước. "Hết mưa" đứng đầu vì chứa chữ "mưa".
_CONDITION_PATTERNS = [
    ("dry", r"hết mưa|tạnh mưa|mưa tạnh|đã tạnh|trời tạnh|hết sương|tan sương|trời quang|"
            r"khô ráo|đường khô|trời nắng|nắng ráo|thời tiết tốt|trời đẹp|bình thường|"
            r"đặt lại|mặc định|reset|khôi phục", r"tạnh"),
    ("slippery", r"trơn trượt|đường trơn|mặt đường trơn|trơn lắm|rất trơn|dầu loang|dầu nhớt|tràn dầu|"
                 r"lầy lội|đường bùn|bùn đất|có bùn|đá sỏi|đường sỏi|có sỏi|băng giá|đóng băng",
     r"\btrơn\b|\bbùn\b|\bsỏi\b|\bcát\b"),
    ("heavy_rain", r"mưa (to|lớn|nặng hạt|rất to|xối xả|như trút|rào|dông|giông|bão)|mưa bão|trời bão|"
                   r"có bão|gió bão|giông bão|dông bão|có giông|có dông|đọng nước|ngập nước|"
                   r"nước lênh láng|trắng xóa", r"\bbão\b|\bgiông\b|\bdông\b|\bngập\b"),
    ("fog", r"sương mù|sương dày|có sương|nhiều sương|sương xuống|sương đêm|mù mịt|mù dày|trời mù|"
            r"tầm nhìn (kém|hạn chế|thấp|xấu|ngắn)|khói bụi|khói mù|nhiều khói|bụi mù|"
            r"không nhìn rõ|nhìn không rõ|nhìn mờ|mờ mịt", r"\bsương\b|\bmù\b|\bkhói\b|\bmờ\b"),
    ("wet", r"mưa|ướt|lất phất", ""),
]
_MODIFIER_PATTERNS = [
    ("night", r"ban đêm|buổi tối|trời tối|tối rồi|lúc tối|tối nay|đêm nay|đêm khuya|nửa đêm|"
              r"chạy đêm|lái đêm|thiếu sáng|không có đèn|đèn đường tắt|chạng vạng|hoàng hôn",
     r"\bđêm\b|\btối\b"),
    ("heavy_vehicle", r"tải nặng|chở nặng|quá tải|đầy hàng|chở hàng|chở khách|lái xe tải|lái xe khách|"
                      r"lái xe buýt|lái container|kéo container|chở container|lái xe đầu kéo|"
                      r"chạy xe tải|chạy xe khách|xe tôi (là|chở)", ""),
    ("tired", r"mệt mỏi|thấy mệt|hơi mệt|rất mệt|đang mệt|mệt quá|bị mệt|buồn ngủ|mỏi mắt|lái lâu|"
              r"thiếu ngủ|ngủ gật|díp mắt|uể oải", r"\bmệt\b|\bmỏi\b"),
]


def _compile(patterns):
    """-> [(khóa, regex cho câu có dấu, regex cho câu không dấu)]. Khớp trọn từ: "trời mù" ≠ "trời mưa"."""
    return [(k, re.compile(rf"\b(?:{phrases})\b" + (f"|{short}" if short else "")),
             re.compile(rf"\b(?:{_fold(phrases)})\b"))
            for k, phrases, short in patterns]


_CONDITION_RE = _compile(_CONDITION_PATTERNS)
_MODIFIER_RE = _compile(_MODIFIER_PATTERNS)
# Các mẫu dưới đây chạy trên chữ đã bỏ dấu
_NOT_SPEED = r"(?!\s*(m\b|met|giay|s\b|phut))"
_SPEED_RE = re.compile(r"(\d{2,3})\s*(km/?h|kmh|km\b|cay so|cay\b)|"
                       r"(toc do|chay|di|dang o|vuot|dat)\s*(khoang|tam|khong qua|duoi|tren)?\s*(\d{2,3})\b"
                       + _NOT_SPEED)
_VISIBILITY_RE = re.compile(r"(tam nhin|nhin (xa|thay|duoc)|thay duoc|chi thay)[^\d]{0,20}(\d{1,4})\s*m\b")
_HELP_RE = re.compile(_fold(r"giúp|hướng dẫn|làm (sao|gì|được gì)|biết gì|hiểu gì|xin chào|chào bạn|"
                            r"\bchào\b|hello|\bhi\b"))
_LAW_RE = re.compile(_fold(r"quy định|luật|thông tư|bộ gtvt|bảng khoảng cách|bao nhiêu mét|bao xa"))

HELP_TEXT = ("Tôi là trợ lý offline, không cần Internet. Hãy mô tả tình huống, ví dụ: "
             "\"trời mưa to\", \"sương mù tầm nhìn 80 m\", \"đường trơn do dầu loang\", "
             "\"lái ban đêm, chở nặng\", \"tôi đang chạy 100 km/h\", \"đã tạnh mưa\". "
             "Có thể gõ không dấu. Tôi sẽ đổi ngưỡng cảnh báo cho phù hợp.")

LAW_TEXT = ("Quy định (đường khô ráo): 60 km/h: 35 m; trên 60–80 km/h: 55 m; trên 80–100 km/h: 70 m; "
            "trên 100–120 km/h: 100 m. Dưới 60 km/h tài xế tự chủ động giữ khoảng cách phù hợp. "
            "Khi mưa, sương mù, đường trơn phải giữ khoảng cách lớn hơn.")


def _current_condition_key(policy: SafetyPolicy) -> str:
    """Suy ra điều kiện mặt đường đang áp dụng từ hệ số bám (để giữ nguyên khi chỉ đổi yếu tố khác)."""
    return min(ROAD_CONDITIONS.values(), key=lambda c: abs(c.mu - policy.road_mu)).key


def _parse_speed(text: str) -> Optional[float]:
    for m in _SPEED_RE.finditer(text):
        v = int(m.group(1) or m.group(5))
        if 10 <= v <= 200:
            return float(v)
    return None


def _r(v: float) -> int:
    """Làm tròn như Dart .round() (round() của Python là kiểu ngân hàng): câu trả lời giống hệt app mobile."""
    return int(v + 0.5)


def offline_advice(message: str, policy: SafetyPolicy, speed_kmh: float) -> AssistantResult:
    raw = unicodedata.normalize("NFC", message.lower())
    text = _fold(message)
    has_marks = text != raw.replace("đ", "d")   # người dùng có gõ dấu không
    speed = _parse_speed(text)
    v = speed if speed is not None else speed_kmh

    def found(marked_re, plain_re):
        return marked_re.search(raw) if has_marks else plain_re.search(text)

    cond_key = next((k for k, m_re, p_re in _CONDITION_RE if found(m_re, p_re)), None)
    mods = [k for k, m_re, p_re in _MODIFIER_RE if found(m_re, p_re)]
    vis_m = _VISIBILITY_RE.search(text)
    if vis_m and cond_key in (None, "dry"):
        cond_key = "fog"  # chỉ nêu tầm nhìn -> coi là tầm nhìn hạn chế
    visibility = float(vis_m.group(3)) if vis_m else (policy.visibility_m if cond_key in (None, "fog") else 0.0)

    changed = cond_key is not None or mods or vis_m
    if changed:
        key = cond_key or _current_condition_key(policy)
        if key == "fog" and not visibility:
            visibility = 100.0  # sương mù chưa rõ tầm nhìn -> giả định 100 m
        p = condition_policy(key, mods, visibility, base=policy)
    else:
        p = replace(policy)

    p = clamp_policy(p)
    thr = compute_thresholds(v, p)
    parts = []
    if not changed and speed is None:
        # Không nhận ra tình huống nào: trả lời câu hỏi quy định / hướng dẫn cách dùng
        if _LAW_RE.search(text):
            parts.append(LAW_TEXT)
        elif _HELP_RE.search(text):
            parts.append(HELP_TEXT)
        else:
            parts.append("Tôi chưa nhận ra tình huống trong câu này nên giữ nguyên ngưỡng. " + HELP_TEXT)
    if changed:
        cond = ROAD_CONDITIONS[_current_condition_key(p)]
        parts.append(f"Điều kiện: {p.condition.lower()}.")
        if p.weather_factor > 1.0:
            parts.append(f"Quy định yêu cầu giữ khoảng cách lớn hơn khi đường khô; ước tính "
                         f"×{vn_num(p.weather_factor)} so với bảng. {cond.advice}")
        else:
            parts.append(cond.advice)
    if thr.legal_m is not None:
        own = f", ngưỡng bạn đặt cho dải này {_r(thr.band_m)} m" if thr.band_m > thr.legal_m else ""
        parts.append(f"Ở {_r(v)} km/h, quy định (đường khô) tối thiểu {_r(thr.legal_m)} m{own}; "
                     f"hãy giữ ≥ {_r(thr.safe_m)} m (dưới {_r(thr.danger_m)} m là nguy hiểm).")
    else:
        parts.append(f"Dưới 60 km/h, quy định để tài xế tự chủ động giữ khoảng cách; ước tính theo quy tắc "
                     f"{vn_num(p.time_gap_s)} giây: ≥ {_r(thr.safe_m)} m ở {_r(v)} km/h.")
    if thr.over_speed_limit:
        parts.append("Lưu ý: tốc độ vượt mức tối đa 120 km/h trên cao tốc.")
    if thr.recommended_speed_kmh is not None:
        parts.append(f"Với tầm nhìn khoảng {_r(p.visibility_m)} m, không nên chạy quá "
                     f"{_r(thr.recommended_speed_kmh)} km/h để kịp dừng xe.")
    return AssistantResult(reply=" ".join(parts), policy=p, speed_kmh=speed, source="Offline")
