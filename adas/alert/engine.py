"""
Quản lý cảnh báo: chống nhiễu (hysteresis) + phát âm thanh.

- Nâng mức cảnh báo chỉ khi mức mới kéo dài liên tục `escalate_seconds` giây (và ít nhất 2 khung)
  -> tránh báo động giả do một khung phát hiện sai. Tính theo thời gian chứ không theo số khung, để
  máy xử lý 10 hay 30 khung/giây (app mobile tự hạ nhịp trên máy yếu) thì cảnh báo vẫn kịp như nhau.
- Hạ mức chỉ sau khi mức thấp hơn kéo dài `hold_seconds`
  -> tránh nhấp nháy bật/tắt liên tục.
- Âm thanh: NGUY HIỂM = bíp cao, dồn dập; CẢNH BÁO = bíp trầm, thưa.
"""

import time
from typing import Optional

import numpy as np

from adas.alert.thresholds import RISK_ORDER
from adas.config import AlertConfig

try:
    import pygame
    _HAS_PYGAME = True
except ImportError:
    _HAS_PYGAME = False


def _tone(freq: float, duration: float, volume: float, sample_rate: int = 44100) -> np.ndarray:
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    wave = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(4 * np.pi * freq * t)
    fade = min(len(t) // 5, 400)
    env = np.ones_like(t)
    env[:fade] = np.linspace(0, 1, fade)
    env[-fade:] = np.linspace(1, 0, fade)
    return (wave / 1.3 * env * volume * 32767).astype(np.int16)


class AlertManager:
    INTERVALS = {"danger": 0.28, "warning": 0.9}

    def __init__(self, cfg: AlertConfig):
        self.cfg = cfg
        self.level = "safe"
        self._candidate = "safe"
        self._candidate_count = 0
        self._candidate_since = 0.0
        self._last_raise_time = 0.0
        self._last_beep = 0.0
        self._sounds = {}
        self._audio_ok = False
        self._init_audio()

    def _init_audio(self) -> None:
        if not _HAS_PYGAME:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
            channels = pygame.mixer.get_init()[2]
            for level, (freq, dur, vol) in {
                "danger": (1250.0, 0.16, 0.9),
                "warning": (820.0, 0.22, 0.6),
            }.items():
                wave = _tone(freq, dur, vol)
                if channels == 2:
                    wave = np.column_stack([wave, wave])
                self._sounds[level] = pygame.sndarray.make_sound(np.ascontiguousarray(wave))
            self._audio_ok = True
        except Exception as e:  # thiết bị âm thanh không khả dụng
            print(f"[Alert] Không khởi tạo được âm thanh: {e}")

    @property
    def audio_available(self) -> bool:
        return self._audio_ok

    def update(self, raw_level: str, now: Optional[float] = None) -> str:
        """Nhận mức rủi ro thô của khung hiện tại, trả về mức cảnh báo ổn định."""
        now = time.monotonic() if now is None else now
        raw_level = raw_level if raw_level in ("warning", "danger") else "safe"

        if raw_level == self._candidate:
            self._candidate_count += 1
        else:
            self._candidate, self._candidate_count, self._candidate_since = raw_level, 1, now

        raw_rank, cur_rank = RISK_ORDER[raw_level], RISK_ORDER[self.level]
        if raw_rank > cur_rank:
            if self._confirmed(now):
                self.level = raw_level
                self._last_raise_time = now
        elif raw_rank < cur_rank:
            if now - self._last_raise_time >= self.cfg.hold_seconds:
                self.level = raw_level
        else:
            self._last_raise_time = now

        self._play(now)
        return self.level

    def _confirmed(self, now: float) -> bool:
        """Mức ứng viên đã kéo dài đủ lâu để nâng (0 giây = nâng ngay từ khung đầu)."""
        if self.cfg.escalate_seconds <= 0:
            return True
        return self._candidate_count >= 2 and now - self._candidate_since >= self.cfg.escalate_seconds - 1e-9

    def _play(self, now: float) -> None:
        if not (self._audio_ok and self.cfg.sound_enabled):
            return
        interval = self.INTERVALS.get(self.level)
        if interval and now - self._last_beep >= interval:
            self._sounds[self.level].play()
            self._last_beep = now

    def preview(self, level: str) -> bool:
        """Phát thử âm cảnh báo ('warning' | 'danger') - dùng trong màn hình cấu hình."""
        if self._audio_ok and level in self._sounds:
            self._sounds[level].play()
            return True
        return False

    def reset(self) -> None:
        self.level = "safe"
        self._candidate, self._candidate_count = "safe", 0
