"""SafetyAssistant: gọi Claude (structured output) khi bật, tự quay về tư vấn offline khi lỗi."""

import json
from dataclasses import asdict
from typing import List, Optional

from adas.alert.thresholds import compute_thresholds
from adas.assistant.base import AssistantResult, clamp_policy
from adas.assistant.offline import offline_advice
from adas.assistant.prompt import FALLBACK_MODELS, RESPONSE_SCHEMA, SYSTEM_PROMPT
from adas.config import AssistantConfig, SafetyPolicy


class SafetyAssistant:
    MAX_HISTORY_TURNS = 8

    def __init__(self, cfg: AssistantConfig, api_key: Optional[str] = None):
        self.cfg = cfg
        self.api_key = api_key
        self.history: List[dict] = []
        self._client = None

    def set_api_key(self, key: Optional[str]) -> None:
        self.api_key = key or None
        self._client = None

    def clear_history(self) -> None:
        self.history.clear()

    # ------------------------------------------------------------------

    def ask(self, message: str, policy: SafetyPolicy, speed_kmh: float,
            scene: str = "") -> AssistantResult:
        if self.cfg.use_cloud:
            try:
                return self._ask_claude(message, policy, speed_kmh, scene)
            except Exception as e:  # mạng, API key, SDK... -> dùng offline
                result = offline_advice(message, policy, speed_kmh)
                result.note = f"Không gọi được Claude ({_short_error(e)}) - dùng tư vấn offline."
                return result
        return offline_advice(message, policy, speed_kmh)

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = (anthropic.Anthropic(api_key=self.api_key, timeout=45.0)
                            if self.api_key else anthropic.Anthropic(timeout=45.0))
        return self._client

    def _ask_claude(self, message: str, policy: SafetyPolicy, speed_kmh: float,
                    scene: str) -> AssistantResult:
        client = self._get_client()
        thr = compute_thresholds(speed_kmh, policy)
        context = (
            f"[Trạng thái hệ thống]\n"
            f"Tốc độ xe chủ: {speed_kmh:.0f} km/h\n"
            f"Tham số hiện tại: {json.dumps(asdict(policy), ensure_ascii=False)}\n"
            f"Khoảng cách tối thiểu theo quy định (khô ráo): "
            f"{f'{thr.legal_m:.0f} m' if thr.legal_m is not None else 'dưới 60 km/h - tài xế tự chủ động'}\n"
            + (f"Ngưỡng người dùng đặt cho dải tốc độ này (khô ráo): {thr.band_m:.0f} m\n"
               if thr.band_m is not None else "")
            + f"Ngưỡng hiện tại: cảnh báo < {thr.safe_m:.1f} m, nguy hiểm < {thr.danger_m:.1f} m\n"
            f"{scene}\n\n[Tài xế]\n{message}"
        )
        messages = self.history + [{"role": "user", "content": context}]
        model = self.cfg.model
        output_config = {"format": {"type": "json_schema", "schema": RESPONSE_SCHEMA}}
        if not model.startswith("claude-haiku"):
            output_config["effort"] = "low"   # Haiku 4.5 không nhận tham số effort
        request = dict(
            model=model,
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            messages=messages,
            output_config=output_config,
        )

        response = None
        if model in FALLBACK_MODELS:
            try:
                # Tự chuyển sang mô hình dự phòng nếu yêu cầu bị bộ lọc an toàn từ chối
                response = client.beta.messages.create(
                    betas=["server-side-fallback-2026-07-01"], fallbacks="default", **request)
            except TypeError:
                pass  # SDK cũ chưa hỗ trợ tham số `fallbacks`
        if response is None:
            response = client.messages.create(**request)

        if response.stop_reason == "refusal":
            raise RuntimeError("Claude từ chối yêu cầu")
        text = next(b.text for b in response.content if b.type == "text")
        data = json.loads(text)

        new_policy = clamp_policy(SafetyPolicy(
            time_gap_s=data["time_gap_s"],
            weather_factor=data["weather_factor"],
            danger_ratio=data["danger_ratio"],
            min_distance_m=data["min_distance_m"],
            ttc_warning_s=data["ttc_warning_s"],
            ttc_danger_s=data["ttc_danger_s"],
            use_legal_table=True,  # luôn tuân thủ bảng quy định, AI chỉ được tăng thêm
            band_gaps_m=list(policy.band_gaps_m),  # ngưỡng theo dải do người dùng đặt, AI không đổi
            condition=data["condition"].strip() or policy.condition,
            road_mu=data["road_mu"],
            visibility_m=data["visibility_m"],
        ))
        speed = data["speed_kmh"]
        speed = float(speed) if speed and 0 < speed <= 200 else None

        self.history += [{"role": "user", "content": context},
                         {"role": "assistant", "content": text}]
        self.history = self.history[-2 * self.MAX_HISTORY_TURNS:]
        return AssistantResult(reply=data["reply"].strip(), policy=new_policy,
                               speed_kmh=speed, source="Claude")


def _short_error(e: Exception) -> str:
    name = type(e).__name__
    if name == "AuthenticationError" or "api_key" in str(e).lower() or "auth" in str(e).lower():
        return "chưa cấu hình API key hợp lệ"
    if name in ("APIConnectionError", "APITimeoutError"):
        return "lỗi kết nối mạng"
    if name == "ModuleNotFoundError":
        return "chưa cài thư viện anthropic"
    return name
