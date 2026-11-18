"""
Đo tốc độ xe chủ từ video (không cần GPS/OBD), dựa trên chuyển động của vạch kẻ đứt.

Khi xe chạy với tốc độ v, mọi điểm trên mặt đường tiến lại gần đúng v·Δt mét. Nhờ homography IPM,
ta lấy mẫu độ sáng dọc theo vạch làn (đã nhận diện ở lane.py) theo khoảng cách thực Y (mét):
vạch đứt cho hồ sơ dạng "có - không - có". So hồ sơ của khung hiện tại với khung cách ~0,1 s:
    p_now(Y) ≈ p_trước(Y + s)   ->   v = s / Δt
s tìm bằng tương quan chuẩn hóa lớn nhất (nội suy parabol để đạt độ phân giải dưới mẫu).
Kết quả = trung vị các lần đo trong 1 s -> làm mượt hàm mũ (τ = 1 s) -> số báo chỉ đổi khi lệch >= 1 km/h.

Vạch liền không chứa thông tin chuyển động dọc nên bị bỏ qua. Độ chính xác phụ thuộc trực tiếp vào
thang chiều sâu của hiệu chỉnh IPM: sai bao nhiêu % chiều sâu thì sai bấy nhiêu % tốc độ
(cũng là sai số của khoảng cách hiển thị).
"""

from collections import deque
from typing import Dict, Optional

import cv2
import numpy as np

from adas.distance.ipm import GroundPlaneMapper
from adas.distance.lane import LaneEstimate


class EgoSpeedEstimator:
    DY = 0.05                    # bước lấy mẫu dọc vạch (m)
    Y_MIN, Y_MAX = 5.0, 26.0     # đoạn mặt đường dùng để đo (gần: rõ nét; xa: kém phân giải)
    LAT = np.linspace(-0.25, 0.25, 11)   # quét ngang quanh vạch (m) để không lệch khỏi vạch
    MIN_CONTRAST = 20.0          # vạch phải sáng hơn mặt đường ít nhất chừng này (mức xám)
    REF_GAP_S = (0.08, 0.4)      # so với khung cách nhau trong khoảng này
    MIN_CORR = 0.8
    V_MAX_KMH = 160.0
    WINDOW_S = 1.0               # lấy trung vị các lần đo trong cửa sổ này
    MIN_SAMPLES = 3
    SMOOTH_TAU_S = 1.0           # làm mượt hàm mũ trung vị (từng lần đo rung ±8 km/h; xe thật đổi tốc chậm)
    DISPLAY_STEP = 1.0           # chỉ đổi số báo khi lệch >= 1 km/h, tránh số nhảy liên tục
    STALE_S = 2.0                # không đo được quá lâu -> trả None

    def __init__(self, mapper: GroundPlaneMapper):
        self.mapper = mapper
        self.ys = np.arange(self.Y_MIN, self.Y_MAX, self.DY)
        self.reset()

    def reset(self) -> None:
        self.history = deque(maxlen=20)          # (t, {bên: hồ sơ})
        self.samples = deque()                   # (t, km/h)
        self.value: Optional[float] = None       # tốc độ đã làm mượt (km/h)
        self.shown: Optional[float] = None       # số báo ra ngoài (km/h, có vùng chết)
        self.last_t = None
        self.prev_t = None
        self.start_t = None                      # lúc bắt đầu có số đo (giai đoạn khởi động)

    # ------------------------------------------------------------------

    def update(self, frame: np.ndarray, lane: Optional[LaneEstimate], t: float) -> Optional[float]:
        """Trả về tốc độ ước lượng (km/h) hoặc None khi chưa đo được."""
        if self.history and t < self.history[-1][0]:     # tua lại / nguồn mới
            self.reset()
        profiles = self._profiles(frame, lane) if lane is not None else {}
        ref = None
        for t0, p0 in reversed(self.history):
            if self.REF_GAP_S[0] <= t - t0 <= self.REF_GAP_S[1]:
                ref = (t0, p0)
                break
        self.history.append((t, profiles))

        if ref is not None and profiles:
            t0, p0 = ref
            dt = t - t0
            best = None
            for side, p in profiles.items():
                if side in p0:
                    s, c = self._shift(p0[side], p, dt)
                    if c >= self.MIN_CORR and (best is None or c > best[1]):
                        best = (s, c)
            if best is not None:
                self.samples.append((t, best[0] / dt * 3.6))
                self.last_t = t

        while self.samples and t - self.samples[0][0] > self.WINDOW_S:
            self.samples.popleft()
        if len(self.samples) >= self.MIN_SAMPLES:
            med = float(np.median([v for _, v in self.samples]))
            if self.value is None:
                self.start_t = t
            if t - self.start_t < self.WINDOW_S:  # khởi động: trung vị còn ít mẫu, theo sát nó
                self.value = med
            else:
                self.value += (1.0 - np.exp(-(t - self.prev_t) / self.SMOOTH_TAU_S)) * (med - self.value)
        if self.last_t is None or t - self.last_t > self.STALE_S:
            self.value = None
        self.prev_t = t
        if self.value is None:
            self.shown = None
        elif self.shown is None or abs(self.value - self.shown) >= self.DISPLAY_STEP:
            self.shown = float(round(self.value))
        return self.shown

    # ------------------------------------------------------------------

    def _profiles(self, frame, lane: LaneEstimate) -> Dict[str, np.ndarray]:
        """Hồ sơ độ sáng (vạch - mặt đường) dọc mỗi vạch làn nhìn thấy được, chỉ giữ vạch đứt."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        h, w = gray.shape[:2]
        n, m = len(self.ys), len(self.LAT)
        out = {}
        for side, coef, found in (("l", lane.left, lane.found_left), ("r", lane.right, lane.found_right)):
            if not found:          # vạch suy ra từ bề rộng làn: vị trí không chắc chắn
                continue
            xs = coef[0] + coef[1] * self.ys + coef[2] * self.ys ** 2
            pts = np.stack([xs[:, None] + self.LAT[None, :], np.repeat(self.ys[:, None], m, 1)], -1)
            uv = self.mapper.ground_to_image(pts.reshape(-1, 2)).reshape(n, m, 2).astype(np.float32)
            strip = cv2.remap(gray, uv[..., 0], uv[..., 1], cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=0).astype(np.float32)
            p = strip.max(1) - np.median(strip, 1)
            inside = ((uv[..., 0] >= 0) & (uv[..., 0] < w - 1) & (uv[..., 1] >= 0) & (uv[..., 1] < h - 1)).all(1)
            p[~inside] = np.nan
            valid = p[inside]
            if valid.size < n // 3 or np.nanmax(p) < self.MIN_CONTRAST:
                continue
            on = valid > 0.5 * valid.max()
            switches = int(np.count_nonzero(on[1:] != on[:-1]))
            if 0.05 <= on.mean() <= 0.75 and switches >= 2:     # vạch đứt: có đoạn sơn và khoảng hở
                out[side] = p
        return out

    def _shift(self, pa: np.ndarray, pb: np.ndarray, dt: float):
        """s (m) sao cho pb(Y) ≈ pa(Y + s); trả về (s, độ tương quan)."""
        lo, hi = 0.0, self.V_MAX_KMH / 3.6 * dt
        if self.value is not None:            # bám quanh tốc độ đã đo để tránh nhảy sang vạch đứt kế tiếp
            pred = self.value / 3.6 * dt
            lo, hi = max(0.0, 0.6 * pred - 0.3), min(hi, 1.4 * pred + 0.3)
        n = len(pa)
        k_lo, k_hi = int(lo / self.DY), min(int(hi / self.DY) + 1, n - n // 3)
        if k_hi - k_lo < 3:
            return 0.0, -1.0
        cs = np.full(k_hi - k_lo, -1.0)
        for i, k in enumerate(range(k_lo, k_hi)):
            a, b = pa[k:], pb[:n - k]
            ok = np.isfinite(a) & np.isfinite(b)
            if ok.sum() < n // 3:
                continue
            a, b = a[ok], b[ok]
            sa, sb = a.std(), b.std()
            if sa > 1e-6 and sb > 1e-6:
                cs[i] = float(((a - a.mean()) * (b - b.mean())).mean() / (sa * sb))
        i = int(np.argmax(cs))
        off = 0.0
        if 0 < i < len(cs) - 1 and cs[i - 1] > -1 and cs[i + 1] > -1:
            d = cs[i - 1] - 2 * cs[i] + cs[i + 1]
            if d < 0:
                off = 0.5 * (cs[i - 1] - cs[i + 1]) / d
        return (k_lo + i + off) * self.DY, cs[i]
