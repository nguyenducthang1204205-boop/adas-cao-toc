"""
Trợ lý AI tư vấn ngưỡng khoảng cách an toàn.

Người dùng mô tả tình huống bằng ngôn ngữ tự nhiên (tốc độ, thời tiết, mặt đường,
tải trọng, tình trạng tài xế...). Trợ lý trả về:
  - Lời khuyên ngắn gọn bằng tiếng Việt
  - Bộ tham số SafetyPolicy mới (time gap, hệ số thời tiết, ngưỡng TTC...)
  - Tốc độ xe nếu người dùng có nhắc tới

Hai chế độ:
  - Claude (Anthropic API) với structured output -> JSON đúng schema
  - Offline (luật từ khóa) khi không có API key / mất mạng
Trợ lý KHÔNG nằm trong vòng lặp xử lý từng khung hình: nó chỉ cập nhật tham số,
còn việc so sánh khoảng cách với ngưỡng vẫn chạy cục bộ theo thời gian thực.
"""

from adas.assistant.base import LIMITS, AssistantResult, clamp_policy  # noqa: F401
from adas.assistant.offline import offline_advice  # noqa: F401
from adas.assistant.prompt import FALLBACK_MODELS, RESPONSE_SCHEMA, SYSTEM_PROMPT  # noqa: F401
from adas.assistant.service import SafetyAssistant  # noqa: F401

__all__ = ["LIMITS", "AssistantResult", "clamp_policy", "offline_advice", "FALLBACK_MODELS",
           "RESPONSE_SCHEMA", "SYSTEM_PROMPT", "SafetyAssistant"]
