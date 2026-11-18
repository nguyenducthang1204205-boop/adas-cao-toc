"""
Tự động hiệu chỉnh IPM từ video hành trình trên cao tốc.

Mô hình mặt đường phẳng, camera nhìn thẳng theo hướng đường:
    Y(v) = K / (v - v0)            khoảng cách dọc tới hàng ảnh v (v0 = hàng chân trời)
    w(v) = c · (v - v0)            bề rộng làn tính bằng pixel tại hàng v
với K = f · h_c (tiêu cự × chiều cao camera) và c = W_làn / h_c.

Ba đại lượng được đo từ chính video:
  1. Điểm tụ (u0, v0): giao điểm của các vạch kẻ đường (Hough + RANSAC).
  2. Hệ số bề rộng làn c: khoảng cách giữa 2 vạch làn xe chủ, đo trên từng khung
     (không bị ảnh hưởng khi xe trôi ngang trong làn) -> h_c = W_làn / c.
  3. Thang chiều sâu K: khi xe chạy với tốc độ v_xe, mọi điểm trên mặt đường tiến lại gần
     đúng v_xe·Δt mét. Đo độ dịch của hoa văn vạch đứt giữa 2 khung liên tiếp trong hệ
     tọa độ 1/(v - v0) (tuyến tính theo Y/K) -> K = v_xe·Δt / Δ(1/(v - v0)).
     Nếu không biết tốc độ, dùng góc nhìn camera giả định: K = f · h_c.
"""

from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

import cv2
import numpy as np

from adas.config import CalibrationConfig

ProgressFn = Optional[Callable[[int, str], None]]


@dataclass
class AutoCalibReport:
    vanishing_point: Tuple[float, float]
    horizon_ratio: float
    lane_width_coef: float           # c: pixel bề rộng làn trên mỗi pixel dưới chân trời
    camera_height_m: float
    depth_scale_K: float
    focal_px: float
    hfov_deg: float
    vfov_deg: float
    depth_from_motion: bool          # True: K đo từ chuyển động; False: từ góc nhìn giả định
    k_spread_pct: float              # độ phân tán (IQR/2) của K, %
    dash_length_m: Optional[float]
    dash_period_m: Optional[float]
    frames_used: int

    def summary(self) -> str:
        src = (f"đo từ chuyển động vạch kẻ đứt, sai số ±{self.k_spread_pct:.0f}%" if self.depth_from_motion
               else "theo góc nhìn camera đã nhập")
        lines = [
            f"Đường chân trời ở {self.horizon_ratio * 100:.1f}% chiều cao ảnh "
            f"(điểm tụ của các vạch làn: {self.vanishing_point[0]:.0f}, {self.vanishing_point[1]:.0f})",
            f"Camera cao {self.camera_height_m:.2f} m so với mặt đường",
            f"Góc nhìn camera: ngang {self.hfov_deg:.0f}°, dọc {self.vfov_deg:.0f}° "
            f"(tiêu cự {self.focal_px:.0f} điểm ảnh) - {src}",
        ]
        if self.dash_length_m and self.dash_period_m:
            lines.append(f"Kiểm tra: mỗi vạch đứt dài {self.dash_length_m:.1f} m, "
                         f"lặp lại sau mỗi {self.dash_period_m:.1f} m")
        return "\n".join(lines)


# ----------------------------------------------------------------------
# Tiện ích xử lý ảnh
# ----------------------------------------------------------------------

def _highpass(frame: np.ndarray) -> np.ndarray:
    """Làm nổi vạch sơn: độ sáng trừ trung bình ngang cục bộ."""
    g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
    return g - cv2.blur(g, (15, 1))


def _line_fill(hp: np.ndarray, u0: float, v0: float, a_values: np.ndarray,
               rows: np.ndarray, thresh: float = 12.0) -> np.ndarray:
    """Tỷ lệ điểm sáng dọc các đường x = u0 + a·(v - v0) (mỗi a một đường qua điểm tụ)."""
    w = hp.shape[1]
    xs = u0 + a_values[:, None] * (rows[None, :] - v0)
    inside = (xs >= 0) & (xs < w - 1)
    vals = hp[np.broadcast_to(rows, xs.shape), np.clip(xs, 0, w - 1).astype(int)]
    return ((vals > thresh) & inside).mean(1)


def _peaks(S: np.ndarray, min_val: float) -> List[int]:
    return [i for i in range(len(S)) if S[i] >= min_val and S[i] == S[max(i - 5, 0): i + 6].max()]


# ----------------------------------------------------------------------
# 1. Điểm tụ
# ----------------------------------------------------------------------

def estimate_vanishing_point(frames: List[np.ndarray]) -> Tuple[float, float]:
    h, w = frames[0].shape[:2]
    segs = []
    for fr in frames:
        hsv = cv2.cvtColor(fr, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, (0, 0, 160), (180, 70, 255))   # sơn trắng/vàng nhạt
        mask[: int(0.40 * h)] = 0
        mask[int(0.85 * h):] = 0
        edges = cv2.Canny(mask, 50, 150)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 20,
                                minLineLength=max(10, h // 30), maxLineGap=6)
        if lines is None:
            continue
        for x1, y1, x2, y2 in lines[:, 0]:
            if y1 != y2 and 0.25 < abs((x2 - x1) / (y2 - y1)) < 4.0:
                segs.append((x1, y1, x2, y2))
    if len(segs) < 10:
        raise RuntimeError("Không tìm thấy đủ vạch kẻ đường để xác định điểm tụ")

    L = np.array([np.cross([s[0], s[1], 1.0], [s[2], s[3], 1.0]) for s in segs])
    L /= np.linalg.norm(L[:, :2], axis=1, keepdims=True)
    rng = np.random.default_rng(0)
    best_n, best_p = 0, None
    for _ in range(3000):
        i, j = rng.choice(len(L), 2, replace=False)
        p = np.cross(L[i], L[j])
        if abs(p[2]) < 1e-9:
            continue
        p = p / p[2]
        if not (0 < p[0] < w and 0.2 * h < p[1] < 0.75 * h):
            continue
        n = int((np.abs(L @ p) < 2.0).sum())
        if n > best_n:
            best_n, best_p = n, p
    if best_p is None:
        raise RuntimeError("Không xác định được điểm tụ")
    A = L[np.abs(L @ best_p) < 2.0]
    u0, v0 = np.linalg.lstsq(A[:, :2], -A[:, 2], rcond=None)[0]
    return float(u0), float(v0)


# ----------------------------------------------------------------------
# 2. Bề rộng làn & 3. thang chiều sâu
# ----------------------------------------------------------------------

def _ego_lane_lines(hp, u0, v0, rows):
    """Trả về (a_trái, a_phải, fill_trái, fill_phải) của 2 vạch gần tâm nhất, hoặc None."""
    A = np.arange(-4.0, 4.0, 0.02)
    S = _line_fill(hp, u0, v0, A, rows)
    left = [i for i in _peaks(S, 0.15) if -3.0 < A[i] < -0.25]
    right = [i for i in _peaks(S, 0.15) if 0.25 < A[i] < 3.0]
    if not left or not right:
        return None
    il, ir = max(left, key=lambda i: A[i]), min(right, key=lambda i: A[i])
    return A[il], A[ir], S[il], S[ir]


def auto_calibrate(video_path: str, speed_kmh: Optional[float], base: CalibrationConfig,
                   lane_width_m: float = 3.75, bumper_offset_m: float = 2.0,
                   max_frames: int = 1800, progress: ProgressFn = None
                   ) -> Tuple[CalibrationConfig, AutoCalibReport]:
    """
    speed_kmh: tốc độ trung bình của xe trong đoạn video (xem trên màn hình camera hành trình).
               None -> dùng góc nhìn dọc trong `base.camera_vfov_deg`.
    bumper_offset_m: khoảng cách từ camera tới đầu xe (khoảng cách hiển thị tính từ đầu xe).
    """
    def report(pct, msg):
        if progress:
            progress(pct, msg)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"Không mở được video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = min(int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or max_frames, max_frames)

    # Đọc tuần tự (nhanh hơn tua), giữ các cặp khung liên tiếp cách nhau DT
    DT = 2
    step = max(1, total // 150)
    pairs = []
    idx = 0
    report(0, "Đang đọc video…")
    while idx < total:
        ok, fr = cap.read()
        if not ok:
            break
        if idx % step == 0:
            nxt = None
            for _ in range(DT):
                ok2, nxt = cap.read()
                idx += 1
                if not ok2:
                    nxt = None
                    break
            pairs.append((fr, nxt))
            report(int(40 * idx / total), "Đang đọc video…")
        idx += 1
    cap.release()
    if len(pairs) < 10:
        raise RuntimeError("Video quá ngắn để tự hiệu chỉnh")
    h, w = pairs[0][0].shape[:2]

    report(45, "Đang tìm điểm tụ của vạch kẻ đường…")
    u0, v0 = estimate_vanishing_point([p[0] for p in pairs[::2]])

    report(60, "Đang đo bề rộng làn…")
    rows = np.arange(int(v0 + 0.03 * h), int(min(v0 + 0.18 * h, 0.95 * h)))
    lane_obs = []
    for fr, nxt in pairs:
        hp = _highpass(fr)
        res = _ego_lane_lines(hp, u0, v0, rows)
        if res is not None:
            lane_obs.append((hp, nxt, *res))
    coefs = np.array([o[3] - o[2] for o in lane_obs])
    if len(coefs) < 5:
        raise RuntimeError("Không thấy rõ 2 vạch làn của xe chủ trong video")
    c = float(np.median(coefs))
    cam_h = lane_width_m / c

    # Thang chiều sâu từ chuyển động của vạch đứt
    report(75, "Đang đo thang chiều sâu từ chuyển động…")
    grid = np.arange(1 / (rows[-1] - v0), 1 / (rows[0] - v0), 0.0001)   # y' = 1/(v - v0)
    vs = v0 + 1 / grid

    def profile(hp, a):
        xs = u0 + a * (vs - v0)
        p = np.array([hp[int(round(v)), max(int(x) - 2, 0): int(x) + 3].max(initial=0.0)
                      for v, x in zip(vs, xs)])
        return (p - p.mean()) / (p.std() + 1e-6)

    Ks, dash_lens, periods = [], [], []
    for hp, nxt, aL, aR, fL, fR in lane_obs:
        dashed = [a for a, fill in ((aL, fL), (aR, fR)) if 0.15 <= fill <= 0.7]
        if not dashed or nxt is None or not speed_kmh:
            continue
        a = dashed[0]
        pa, pb = profile(hp, a), profile(_highpass(nxt), a)
        best, shift = -1.0, 0
        for s in range(2, min(120, len(grid) // 3)):
            cc = np.corrcoef(pa[s:], pb[:-s])[0, 1]
            if cc > best:
                best, shift = cc, s
        if best > 0.85:
            Ks.append((speed_kmh / 3.6) * (DT / fps) / (shift * 0.0001))

    from_motion = len(Ks) >= 8
    if from_motion:
        K = float(np.median(Ks))
        q1, q3 = np.percentile(Ks, [25, 75])
        spread = float((q3 - q1) / 2 / K * 100)
        focal = K / cam_h
    else:
        focal = (h / 2) / np.tan(np.radians(base.camera_vfov_deg) / 2)
        K = focal * cam_h
        spread = 0.0

    # Kiểm tra chéo: độ dài & chu kỳ vạch đứt theo thang vừa đo
    report(90, "Đang kiểm tra chéo…")
    Yg = np.arange(K / (rows[-1] - v0), min(40.0, K / (rows[0] - v0)), 0.1)
    for hp, _, aL, aR, fL, fR in lane_obs[::2]:
        dashed = [a for a, fill in ((aL, fL), (aR, fR)) if 0.15 <= fill <= 0.7]
        if not dashed or len(Yg) < 80:
            continue
        rr = v0 + K / Yg
        xx = u0 + dashed[0] * (rr - v0)
        on = np.array([hp[int(round(v)), max(int(x) - 2, 0): int(x) + 3].max(initial=0.0)
                       for v, x in zip(rr, xx)]) > 12
        if on.std() == 0:
            continue
        ac = [np.corrcoef(on[:-L], on[L:])[0, 1] for L in range(30, len(on) // 2)]
        if ac and max(ac) > 0.5:
            periods.append((30 + int(np.argmax(ac))) * 0.1)
        cuts = np.flatnonzero(np.diff(on.astype(int))) + 1
        for seg in np.split(np.arange(len(on)), cuts)[1:-1]:
            if on[seg[0]] and len(seg) > 5:
                dash_lens.append(len(seg) * 0.1)

    # Dựng hình chữ nhật hiệu chỉnh đối xứng quanh cột điểm tụ (trục hướng xe chạy)
    va, vb = v0 + 0.17 * h, v0 + 0.05 * h
    ya, yb = K / (va - v0), K / (vb - v0)
    pts_px = [
        (u0 - c / 2 * (va - v0), va), (u0 + c / 2 * (va - v0), va),
        (u0 + c / 2 * (vb - v0), vb), (u0 - c / 2 * (vb - v0), vb),
    ]
    calib = CalibrationConfig(
        image_points=[[float(x / w), float(y / h)] for x, y in pts_px],
        rect_width_m=lane_width_m,
        rect_length_m=float(yb - ya),
        near_distance_m=float(max(ya - bumper_offset_m, 0.0)),
        lane_half_width_m=base.lane_half_width_m,
        max_range_m=base.max_range_m,
        camera_vfov_deg=float(np.degrees(2 * np.arctan((h / 2) / focal))),
    )
    rep = AutoCalibReport(
        vanishing_point=(u0, v0), horizon_ratio=v0 / h, lane_width_coef=c,
        camera_height_m=cam_h, depth_scale_K=K, focal_px=focal,
        hfov_deg=float(np.degrees(2 * np.arctan((w / 2) / focal))),
        vfov_deg=calib.camera_vfov_deg, depth_from_motion=from_motion, k_spread_pct=spread,
        dash_length_m=float(np.median(dash_lens)) if dash_lens else None,
        dash_period_m=float(np.median(periods)) if periods else None,
        frames_used=len(lane_obs),
    )
    report(100, "Xong")
    return calib, rep
