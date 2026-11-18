"""
Tự hoàn thiện căn chỉnh camera khi chạy (kiểu openpilot / Tesla: "Đang hiệu chỉnh 0-100 %").

Mỗi khung có đủ 2 vạch làn của xe chủ (lane.py) là một mẫu đo điểm tụ: giao điểm của 2 vạch trên ảnh (dây cung
đoạn 6-24 m). Vị trí 2 vạch trên ảnh không phụ thuộc hiệu chỉnh đang dùng nên phép đo không tự khuếch đại sai.
Đường cong ngang chỉ làm điểm tụ dịch ngang (2 dây cung của 2 vạch song song vẫn song song) nên hàng điểm tụ
(chân trời, góc chúc) lấy từ mọi mẫu, còn cột (góc lệch ngang) chỉ lấy từ mẫu trên đoạn thẳng. Không lọc độ cong
cho hàng còn vì lý do khác: camera bị xê dịch làm ảnh nhìn từ trên xuống méo đi, vạch thẳng trông như cong.
Đủ mẫu (trải ít nhất vài giây, độ phân tán nhỏ) thì lấy trung vị:
  - căn chỉnh theo tư thế (CalibrationConfig.pose.active): đặt điểm tụ mới; chiều cao camera chưa đo bằng
    thước thì chỉnh theo làn 3,75 m; có tốc độ thật lúc quay (pose.ref_speed_kmh) thì chỉnh tiêu cự để tốc độ
    đo từ video khớp tốc độ thật. Kết quả trả về trong CalibStatus.new_calib để giao diện áp dụng và lưu CSDL.
  - căn chỉnh 4 điểm (thủ công / tự động cũ): chỉ kiểm tra (bề rộng làn đo được), không sửa gì.
Sau đó tiếp tục theo dõi: điểm tụ lệch xa khỏi hiệu chỉnh đang dùng -> camera bị xê dịch (tư thế: tự hiệu chỉnh
lại; 4 điểm: nhắc người dùng căn chỉnh lại).
"""

import copy
import math
from collections import deque
from dataclasses import asdict, dataclass
from typing import List, Optional, Tuple

import numpy as np

from adas.config import CalibrationConfig
from adas.distance.camera_model import LANE_WIDTH_M, calib_from_pose, focal_px, longitudinal_scale
from adas.distance.ipm import GroundPlaneMapper
from adas.distance.lane import LaneEstimate
from adas.formatting import vn

Y_NEAR, Y_FAR = 6.0, 24.0                     # đoạn vạch làn (m) dùng để dựng đường thẳng trên ảnh
Y_WIDTH = LaneEstimate.REF_Y                  # khoảng cách đo bề rộng làn


@dataclass
class CalibStatus:
    state: str                                # collecting | done | drift
    progress: int                             # 0..100
    message: str
    ok: Optional[bool] = None                 # kết quả tự kiểm tra (None: chưa có)
    new_calib: Optional[CalibrationConfig] = None   # chỉ ở khung vừa hoàn tất: cần áp dụng + lưu
    note: str = ""                            # tóm tắt lưu vào CSDL
    ask_speed: bool = False                   # nên mời nhập tốc độ đang in trên video (không có GPS)


@dataclass
class LaneObservation:
    """
    2 vạch làn của xe chủ trên ảnh, mỗi vạch 2 điểm pixel: đầu vào chung của bộ tự hoàn thiện. Desktop lấy từ
    lane.py (observation_from_lane), Android từ bộ dò vạch gọn trên ảnh xám (core/LaneLines.kt).
    """
    left: np.ndarray                          # 2x2: 2 điểm ảnh của vạch trái
    right: np.ndarray
    straight: bool                            # đoạn đường thẳng: dùng được cho cột điểm tụ


def observation_from_lane(lane: Optional[LaneEstimate], mapper: GroundPlaneMapper,
                          max_curv: float = 1 / (2 * 1000)) -> Optional[LaneObservation]:
    """Dây cung Y_NEAR-Y_FAR của 2 vạch làn thấy ở khung này (|c2| <= max_curv: bán kính >= 1000 m là đường thẳng)."""
    if lane is None or not (lane.found_left and lane.found_right):
        return None
    ys = np.array([Y_NEAR, Y_FAR])
    left = mapper.ground_to_image(np.column_stack([lane.x_left(ys), ys]))
    right = mapper.ground_to_image(np.column_stack([lane.x_right(ys), ys]))
    return LaneObservation(left, right, abs(lane.left[2]) <= max_curv and abs(lane.right[2]) <= max_curv)


@dataclass
class _Sample:
    t: float
    vp: Tuple[float, float]
    left: np.ndarray                          # 2 điểm ảnh của vạch trái (Y_NEAR, Y_FAR)
    right: np.ndarray
    speed: Optional[float]                    # tốc độ đo từ video (km/h) theo hiệu chỉnh lúc lấy mẫu
    straight: bool                            # đoạn đường thẳng: dùng được cho cột điểm tụ


def _intersect(a: np.ndarray, b: np.ndarray) -> Optional[Tuple[float, float]]:
    la = np.cross([*a[0], 1.0], [*a[1], 1.0])
    lb = np.cross([*b[0], 1.0], [*b[1], 1.0])
    p = np.cross(la, lb)
    if abs(p[2]) < 1e-9:
        return None
    return float(p[0] / p[2]), float(p[1] / p[2])


def lane_width_under(calib: CalibrationConfig, frame_size, samples: List[_Sample]) -> Optional[float]:
    """Trung vị bề rộng làn (m) tại Y_WIDTH nếu dùng hiệu chỉnh `calib` cho các vạch đã thấy trên ảnh."""
    mapper = GroundPlaneMapper(calib, frame_size)
    widths = []
    for s in samples:
        xs = []
        for line in (s.left, s.right):
            g = mapper.image_to_ground(line)
            if not np.all(np.isfinite(g)) or abs(g[1, 1] - g[0, 1]) < 1e-6:
                break
            k = (Y_WIDTH - g[0, 1]) / (g[1, 1] - g[0, 1])
            xs.append(g[0, 0] + k * (g[1, 0] - g[0, 0]))
        if len(xs) == 2:
            widths.append(xs[1] - xs[0])
    return float(np.median(widths)) if widths else None


def width_verdict(w: float) -> Tuple[bool, str]:
    err = abs(w - LANE_WIDTH_M)
    if err <= 0.25:
        return True, "đạt"
    if err <= 0.5:
        return True, "hơi lệch"
    return False, "lệch nhiều, kiểm tra lại chiều cao camera"


class OnlineCalibrator:
    SAMPLES_NEEDED = 150      # mẫu điểm tụ hợp lệ (~5 s chạy thẳng có vạch kẻ ở 30 khung/s; Android đo ~15 lần/s: 90)
    MIN_SPAN_S = 5.0          # các mẫu phải trải ít nhất ngần này giây
    MIN_SPEED_KMH = 30.0      # đứng yên / chạy chậm (tắc đường): bỏ qua
    MIN_STRAIGHT = 0.2        # tỷ lệ mẫu đường thẳng tối thiểu để đo cột điểm tụ (ít hơn: giữ cột cũ)
    MAX_SPREAD_DEG = (1.5, 1.0)   # độ phân tán (ngang, dọc) cho phép của điểm tụ
    DRIFT_DEG = (1.5, 1.0)    # điểm tụ lệch khỏi hiệu chỉnh đang dùng quá mức này -> camera bị xê dịch
    DRIFT_WINDOW = 150
    MIN_SPEED_SAMPLES = 30
    SAME_DEG, SAME_REL = 0.25, 0.02   # đo lại lệch ít hơn (góc điểm tụ, chiều cao): coi như căn chỉnh không đổi
    # thang khoảng cách theo GPS: so tốc độ đo từ vạch kẻ đường với GPS lúc chạy đều, gom đủ lâu rồi lấy trung vị
    GPS_STEADY_S, GPS_STEADY_KMH = 2.0, 2.0   # GPS đổi ít hơn ngần này trong ngần ấy giây: chạy đều (GPS trễ ~1 s)
    GPS_SETTLE_S = 2.0        # sau khi hiệu chỉnh đổi: chờ tốc độ video (làm mượt ~1 s) theo thang mới
    GPS_MIN_PAIRS = 200
    GPS_MIN_SPAN_S = 20.0
    GPS_MAX_SPREAD = 0.06     # độ phân tán (MAD tương đối) tối đa của tỷ lệ GPS / video
    GPS_KEEP = 3000           # giữ chừng này cặp gần nhất
    GPS_FIT_REL = 0.015       # lần đầu: lệch ít hơn -> chỉ báo "khớp GPS"
    GPS_REFIT_REL, GPS_REFIT_S = 0.03, 30.0   # đã chỉnh theo GPS: chỉ chỉnh lại khi lệch hơn và đã qua ngần này giây
    # tốc độ nhập tay khi video chạy (desktop): so với tốc độ đo từ vạch kẻ trong ±REF_WINDOW_S quanh lúc đọc số
    REF_WINDOW_S = 2.0
    REF_MIN_SAMPLES = 15
    REF_KEEP_S = 15.0         # nhớ tốc độ video ngần này giây (người dùng gõ chậm)
    REF_FAILED_MSG = "Chưa đo được tốc độ từ vạch kẻ lúc bạn nhập - hãy nhập lại khi thấy rõ vạch đứt"

    def __init__(self, frame_size: Tuple[int, int], samples_needed: int = SAMPLES_NEEDED):
        self.frame_size = frame_size
        self.SAMPLES_NEEDED = self.DRIFT_WINDOW = samples_needed
        self.reset()

    def reset(self) -> None:
        self.samples: List[_Sample] = []
        self.recent = deque(maxlen=self.DRIFT_WINDOW)
        self.result: Optional[CalibStatus] = None     # kết quả lần hoàn tất gần nhất (đang theo dõi)
        self.pending: Optional[CalibrationConfig] = None
        self.drifted = False
        self.check_only = False
        self.gps_hist = deque()                       # (t, km/h GPS) trong GPS_STEADY_S gần nhất
        self.scale_obs = deque(maxlen=self.GPS_KEEP)  # (t, quãng đường thật giữa 2 hàng ảnh cố định, m)
        self.scale_rows = None                        # (hàng gần, hàng xa, cột) cố định từ lần đo đầu
        self._scale_key = self._scale_val = None
        self._scale_changed, self._scale_t0 = False, -1e9
        self.gps_checked = False
        self.gps_fit_t = -1e9
        self.gps_check_t = -1e9
        self.unit_hist = deque()                      # (t, thang hiệu chỉnh / tốc độ video)
        self.refs: List[Tuple[float, float]] = []     # tốc độ nhập tay (t video, km/h) chưa quy đổi
        self.ref_obs: List[float] = []                # quãng đường thật giữa 2 hàng cố định theo các lần nhập
        self.ref_used = 0
        self.ref_failed = False

    def calibration_changed(self, calib: CalibrationConfig) -> None:
        """Hiệu chỉnh vừa đổi: do chính bộ này đề xuất -> chuyển sang theo dõi; do người dùng -> đo lại từ đầu."""
        if self.pending is not None and asdict(calib) == asdict(self.pending):
            self.pending = None
            self.recent.clear()
            return
        self.reset()

    # ------------------------------------------------------------------

    def update(self, lane: Optional[LaneEstimate], mapper: GroundPlaneMapper, calib: CalibrationConfig,
               t: float, speed_measured: Optional[float], gps_kmh: Optional[float] = None) -> CalibStatus:
        return self.update_obs(observation_from_lane(lane, mapper), mapper, calib, t, speed_measured, gps_kmh)

    def update_obs(self, obs: Optional[LaneObservation], mapper: GroundPlaneMapper, calib: CalibrationConfig,
                   t: float, speed: Optional[float], gps_kmh: Optional[float] = None) -> CalibStatus:
        """
        speed: tốc độ đo từ vạch kẻ đường theo hiệu chỉnh đang dùng (km/h), None = chưa đo được.
        gps_kmh: tốc độ thật (GPS), None = không có. Lọc đứng yên / chạy chậm theo GPS nếu có, không thì theo speed.
        """
        status = self._update_obs(obs, mapper, calib, t, speed, gps_kmh)
        status.ask_speed = self._wants_speed(calib, gps_kmh)
        return status

    def _update_obs(self, obs, mapper, calib, t, speed, gps_kmh) -> CalibStatus:
        self._scale_sample(calib, t, speed, gps_kmh)
        sample = self._sample(obs, t, gps_kmh if gps_kmh is not None else speed, speed)
        if self.result is not None:
            return self._monitor(sample, mapper, calib, t)
        self.check_only = not calib.pose.active
        if sample is not None:
            self.samples.append(sample)
        n = len(self.samples)
        span = self.samples[-1].t - self.samples[0].t if n else 0.0
        progress = int(min(n / self.SAMPLES_NEEDED, span / self.MIN_SPAN_S, 0.99) * 100)
        if n >= self.SAMPLES_NEEDED and span >= self.MIN_SPAN_S:
            done = self._finish(mapper, calib)
            if done is not None:
                return done
            progress = int(len(self.samples) / self.SAMPLES_NEEDED * 100)
        return self._collecting(progress)

    def _collecting(self, progress: int) -> CalibStatus:
        if self.check_only:
            msg = "Đang kiểm tra căn chỉnh camera"
        elif self.drifted:
            msg = "Camera bị xê dịch - đang hiệu chỉnh lại"
        else:
            msg = "Đang tự hoàn thiện căn chỉnh camera"
        if self.ref_failed:
            return CalibStatus("collecting", progress, self.REF_FAILED_MSG)
        if self.refs or self.ref_obs:
            msg += ", đã nhận tốc độ trên video"
        return CalibStatus("collecting", progress, msg + " (cần thấy rõ 2 vạch làn)")

    # ------------------------------------------------------------------

    def _sample(self, obs: Optional[LaneObservation], t, moving, speed) -> Optional[_Sample]:
        if obs is None or (moving is not None and moving < self.MIN_SPEED_KMH):
            return None
        vp = _intersect(obs.left, obs.right)
        w, h = self.frame_size
        if vp is None or not (0 <= vp[0] <= w and 0.1 * h <= vp[1] <= 0.9 * h):
            return None
        return _Sample(t, vp, np.asarray(obs.left, float), np.asarray(obs.right, float), speed, obs.straight)

    def _spread_deg(self, vps: np.ndarray, f: float) -> np.ndarray:
        mad = np.median(np.abs(vps - np.median(vps, axis=0)), axis=0) * 1.4826
        return np.degrees(np.arctan(mad / f))

    def _finish(self, mapper: GroundPlaneMapper, calib: CalibrationConfig) -> Optional[CalibStatus]:
        w, h = self.frame_size
        f = focal_px(calib.pose, self.frame_size, calib.camera_vfov_deg) if calib.pose.active \
            else (mapper.focal_px or focal_px(calib.pose, self.frame_size, calib.camera_vfov_deg))
        vps = np.array([s.vp for s in self.samples])
        straight = np.array([s.vp for s in self.samples if s.straight]).reshape(-1, 2)
        use_u = len(straight) >= self.MIN_STRAIGHT * len(vps)
        spread_u = self._spread_deg(straight, f)[0] if use_u else 0.0
        if spread_u > self.MAX_SPREAD_DEG[0] or self._spread_deg(vps, f)[1] > self.MAX_SPREAD_DEG[1]:
            self.samples = self.samples[len(self.samples) // 2:]     # xóc / nhận nhầm vạch: bỏ nửa cũ, đo thêm
            return None
        v = float(np.median(vps[:, 1]))
        u = float(np.median(straight[:, 0])) if use_u else calib.pose.vp_x * w

        if self.check_only:
            width = lane_width_under(calib, self.frame_size, self.samples)
            if width is None:
                self.samples = self.samples[len(self.samples) // 2:]
                return None
            ok, verdict = width_verdict(width)
            msg = f"Kiểm tra căn chỉnh: làn đo được {vn(width, 2)} m - {verdict}"
            self.result = CalibStatus("done", 100, msg, ok=ok)
            self.samples = []
            return self.result

        pose = copy.deepcopy(calib.pose)
        pose.vp_x, pose.vp_y = float(u / w), float(v / h)
        pose.refined = True
        new = calib_from_pose(pose, self.frame_size, calib)
        width = lane_width_under(new, self.frame_size, self.samples)
        if width is None:
            self.samples = self.samples[len(self.samples) // 2:]
            return None
        notes = []
        if pose.height_measured:
            ok, verdict = width_verdict(width)
            msg = f"Căn chỉnh xong: làn đo được {vn(width, 2)} m - {verdict}"
        else:
            # bề rộng mặt đường tỷ lệ thuận với chiều cao camera (cùng các tia nhìn)
            old_h = pose.height_m
            pose.height_m = float(np.clip(pose.height_m * LANE_WIDTH_M / width, 0.6, 4.0))
            if pose.focal_source in ("gps", "speed"):   # thang dọc (tỷ lệ với f·h) đã khớp tốc độ thật: giữ nguyên
                pose.focal_w = float(pose.focal_w * old_h / pose.height_m)
            new = calib_from_pose(pose, self.frame_size, calib)
            ok = 0.8 <= pose.height_m / calib.pose.height_m <= 1.25
            msg = (f"Căn chỉnh xong: camera cao khoảng {vn(pose.height_m, 2)} m "
                   f"(theo làn {vn(LANE_WIDTH_M, 2)} m)")
            notes.append(f"làn theo chiều cao đã nhập: {vn(width, 2)} m")

        speeds = [s.speed for s in self.samples if s.speed is not None]
        extra = ""
        target, source = self._gps_target(), "gps"
        if target is None and self.ref_obs:            # tốc độ nhập tay khi video chạy
            target, source = float(np.median(self.ref_obs)), "speed"
            self.ref_used = len(self.ref_obs)
        if target is not None:
            err = longitudinal_scale(new, self.frame_size, self.scale_rows[:2], self.scale_rows[2]) / target - 1
            new = self._fit_scale(new, pose, target, source)
            what = "GPS" if source == "gps" else "tốc độ đã nhập"
            if source == "gps":
                self.gps_checked, self.gps_fit_t = True, self.samples[-1].t
            extra = f" · thang khoảng cách theo {what}"
            notes.append(f"thang khoảng cách theo {what} (lệch {vn(err * 100, 1)} %) -> tiêu cự "
                         f"{vn(new.pose.focal_w * self.frame_size[0], 0)} px")
        # tiêu cự là thông số ống kính: chỉnh 1 lần (camera xê dịch không đổi tiêu cự, tốc độ đo lúc lệch cũng sai)
        elif pose.ref_speed_kmh > 0 and pose.focal_source == "fov" and len(speeds) >= self.MIN_SPEED_SAMPLES:
            v_measured = float(np.median(speeds))
            new = self._fit_focal(calib, new, pose, v_measured)
            extra = f" · thang khoảng cách theo tốc độ {vn(pose.ref_speed_kmh, 0)} km/h"
            notes.append(f"tốc độ thật {vn(pose.ref_speed_kmh, 0)} km/h, video đo được {vn(v_measured, 1)} km/h "
                         f"-> tiêu cự {vn(new.pose.focal_w * self.frame_size[0], 0)} px")
        elif pose.focal_source == "fov":
            extra = " · chưa có tốc độ thật để đo thang khoảng cách nên khoảng cách xa có thể lệch"
            notes.append("tiêu cự theo góc nhìn giả định")

        if calib.pose.refined and not self.drifted and self._same_pose(calib.pose, new.pose):
            # lần chạy trước đã tự hoàn thiện, đo lại vẫn vậy: chỉ báo kết quả kiểm tra, không lưu thêm bản trùng
            width = lane_width_under(calib, self.frame_size, self.samples) or width
            ok, verdict = width_verdict(width)
            self.samples = []
            self.result = CalibStatus("done", 100, f"Kiểm tra căn chỉnh: làn đo được {vn(width, 2)} m - {verdict}",
                                      ok=ok)
            return self.result

        self.pending = new
        self.drifted = False
        self.samples = []
        self.result = CalibStatus("done", 100, msg + extra, ok=ok, new_calib=new,
                                  note="Tự hoàn thiện khi chạy: " + msg.split(": ", 1)[1]
                                       + "".join(f"; {n}" for n in notes))
        return self.result

    def _same_pose(self, a, b) -> bool:
        w, h = self.frame_size
        f = a.focal_w * w
        if f <= 0 or a.height_m <= 0:
            return False
        du = math.degrees(math.atan(abs(a.vp_x - b.vp_x) * w / f))
        dv = math.degrees(math.atan(abs(a.vp_y - b.vp_y) * h / f))
        return (du < self.SAME_DEG and dv < self.SAME_DEG and abs(b.height_m / a.height_m - 1) < self.SAME_REL
                and abs(b.focal_w / a.focal_w - 1) < 0.01)

    def _fit_focal(self, old: CalibrationConfig, new: CalibrationConfig, pose, v_measured: float):
        """Chỉnh tiêu cự để quãng đường giữa 2 hàng ảnh (thang đo tốc độ) khớp tốc độ thật."""
        old_map = GroundPlaneMapper(old, self.frame_size)
        pa, pb = old_map.ground_to_image(np.array([[0.0, 8.0], [0.0, 22.0]]))
        rows = (pa[1], pb[1], pa[0])
        s_old = longitudinal_scale(old, self.frame_size, rows[:2], rows[2])
        if not s_old:
            return new
        return self._fit_scale(new, pose, s_old * pose.ref_speed_kmh / v_measured, "speed", rows)

    def _fit_scale(self, new: CalibrationConfig, pose, target: float, source: str, rows=None) -> CalibrationConfig:
        """Chỉnh tiêu cự cho quãng đường giữa 2 hàng ảnh `rows` (mặc định: hàng cố định của GPS) bằng `target` (m)."""
        size = self.frame_size
        rows = rows or self.scale_rows
        for _ in range(3):
            s_new = longitudinal_scale(new, size, rows[:2], rows[2])
            if not s_new:
                return new
            pose.focal_w = float(np.clip(pose.focal_w * target / s_new, 0.2, 3.0))
            new = calib_from_pose(pose, size, new)
        pose.focal_source = source
        new.pose.focal_source = source
        return new

    # ------------------------------------------------------------------
    # Thang khoảng cách theo GPS
    # ------------------------------------------------------------------

    def _scale_of(self, calib: CalibrationConfig) -> Optional[float]:
        """Quãng đường (m) giữa 2 hàng ảnh cố định theo hiệu chỉnh `calib` (tốc độ đo từ video tỷ lệ với nó)."""
        if self.scale_rows is None:
            pa, pb = GroundPlaneMapper(calib, self.frame_size).ground_to_image(np.array([[0.0, 8.0], [0.0, 22.0]]))
            self.scale_rows = (float(pa[1]), float(pb[1]), float(pa[0]))
        key = (str(calib.image_points), calib.rect_width_m, calib.rect_length_m, calib.near_distance_m)
        if key != self._scale_key:
            self._scale_key = key
            self._scale_val = longitudinal_scale(calib, self.frame_size, self.scale_rows[:2], self.scale_rows[2])
            self._scale_changed = True
        return self._scale_val

    def _scale_sample(self, calib: CalibrationConfig, t: float, speed: Optional[float], gps: Optional[float]) -> None:
        """
        Lúc chạy đều: quãng đường thật giữa 2 hàng ảnh cố định = thang hiệu chỉnh đang dùng × GPS / tốc độ video.
        Không phụ thuộc hiệu chỉnh lúc đo nên gom được qua các lần tự hoàn thiện; GPS trễ ~1 s không ảnh hưởng
        vì chỉ lấy lúc tốc độ gần như không đổi.
        """
        if gps is None:
            self.gps_hist.clear()
            self._unit_sample(calib, t, speed)
            return
        self.gps_hist.append((t, gps))
        while len(self.gps_hist) > 1 and t - self.gps_hist[1][0] >= self.GPS_STEADY_S:
            self.gps_hist.popleft()
        if (not calib.pose.active or self.drifted or speed is None or speed <= 0 or gps < self.MIN_SPEED_KMH
                or t - self.gps_hist[0][0] < self.GPS_STEADY_S):
            return
        s = self._scale_of(calib)
        if self._scale_changed:          # hiệu chỉnh vừa đổi: tốc độ video còn làm mượt theo thang cũ vài giây
            self._scale_changed, self._scale_t0 = False, t
        gs = [g for _, g in self.gps_hist]
        if s and max(gs) - min(gs) <= self.GPS_STEADY_KMH and t - self._scale_t0 >= self.GPS_SETTLE_S:
            self.scale_obs.append((t, s * gps / speed))

    # --- Tốc độ nhập tay khi video đang chạy (desktop, video không có GPS) ---

    def add_reference(self, t_ref: float, kmh: float) -> None:
        """Người dùng đọc tốc độ in trên video lúc t_ref (giây video) là kmh: so với tốc độ đo quanh lúc đó."""
        self.refs.append((float(t_ref), float(kmh)))
        self.ref_failed = False

    def _unit_sample(self, calib: CalibrationConfig, t: float, speed: Optional[float]) -> None:
        """Ghi thang hiệu chỉnh / tốc độ video vài giây gần nhất; tới lúc thì quy các lần nhập tay ra thang thật."""
        if calib.pose.active and not self.drifted and speed is not None and speed > 0:
            s = self._scale_of(calib)
            if self._scale_changed:
                self._scale_changed, self._scale_t0 = False, t
            if s and t - self._scale_t0 >= self.GPS_SETTLE_S:
                self.unit_hist.append((t, s / speed))
        while self.unit_hist and t - self.unit_hist[0][0] > self.REF_KEEP_S:
            self.unit_hist.popleft()
        for ref in [r for r in self.refs if t >= r[0] + self.REF_WINDOW_S]:
            self.refs.remove(ref)
            units = [u for tt, u in self.unit_hist if abs(tt - ref[0]) <= self.REF_WINDOW_S]
            if len(units) >= self.REF_MIN_SAMPLES:
                self.ref_obs.append(float(np.median(units)) * ref[1])
            else:                         # lúc đó không thấy vạch đứt: không so được
                self.ref_failed = True

    def _ref_check(self, calib: CalibrationConfig) -> Optional[CalibStatus]:
        """Đang theo dõi: có lần nhập tay mới đã quy ra thang thật thì chỉnh thang khoảng cách (hoặc báo đã khớp)."""
        if self.ref_failed:
            self.ref_failed = False
            self.result = CalibStatus("done", 100, self.REF_FAILED_MSG, ok=False)
            return self.result
        if not calib.pose.active or len(self.ref_obs) <= self.ref_used:
            return None
        self.ref_used = len(self.ref_obs)
        target = float(np.median(self.ref_obs))
        cur = self._scale_of(calib)
        if not cur:
            return None
        err = cur / target - 1
        if abs(err) < self.GPS_FIT_REL:
            self.result = CalibStatus("done", 100, f"Thang khoảng cách khớp tốc độ đã nhập (lệch {vn(err * 100, 1)} %)",
                                      ok=True)
            return self.result
        pose = copy.deepcopy(calib.pose)
        new = self._fit_scale(calib_from_pose(pose, self.frame_size, calib), pose, target, "speed")
        self.pending = new
        self.result = CalibStatus(
            "done", 100, f"Đã chỉnh thang khoảng cách theo tốc độ đã nhập (tốc độ đo từ vạch kẻ lệch {vn(err * 100, 1)} %)",
            ok=True, new_calib=new,
            note=f"Chỉnh theo tốc độ nhập khi video chạy: thang khoảng cách lệch {vn(err * 100, 1)} % -> tiêu cự "
                 f"{vn(new.pose.focal_w * self.frame_size[0], 0)} px")
        return self.result

    def _wants_speed(self, calib: CalibrationConfig, gps: Optional[float]) -> bool:
        """Nên mời nhập tốc độ: không có GPS, thang khoảng cách chưa theo tốc độ thật, chưa có lần nhập đang chờ."""
        return (gps is None and calib.pose.active and calib.pose.focal_source not in ("speed", "gps")
                and not self.refs and not self.ref_obs and self.pending is None)

    def _gps_target(self) -> Optional[float]:
        """Quãng đường thật giữa 2 hàng cố định (trung vị) khi đã gom đủ và ổn định; chưa đủ: None."""
        if len(self.scale_obs) < self.GPS_MIN_PAIRS or self.scale_obs[-1][0] - self.scale_obs[0][0] < self.GPS_MIN_SPAN_S:
            return None
        s = np.array([x for _, x in self.scale_obs])
        med = float(np.median(s))
        spread = float(np.median(np.abs(s - med))) * 1.4826 / med
        return med if spread <= self.GPS_MAX_SPREAD else None

    def _gps_check(self, calib: CalibrationConfig, t: float) -> Optional[CalibStatus]:
        """Đang theo dõi: đủ dữ liệu GPS thì chỉnh thang khoảng cách (hoặc báo đã khớp)."""
        if not calib.pose.active or t - self.gps_check_t < 1.0:
            return None
        self.gps_check_t = t
        refit = calib.pose.focal_source == "gps"
        if refit and t - self.gps_fit_t < self.GPS_REFIT_S:
            return None
        target = self._gps_target()
        cur = self._scale_of(calib)
        if target is None or not cur:
            return None
        err = cur / target - 1
        if abs(err) < (self.GPS_REFIT_REL if refit or self.gps_checked else self.GPS_FIT_REL):
            if self.gps_checked:
                return None
            self.gps_checked = True
            self.result = CalibStatus("done", 100, f"Thang khoảng cách khớp GPS (lệch {vn(err * 100, 1)} %)", ok=True)
            return self.result
        pose = copy.deepcopy(calib.pose)
        new = self._fit_scale(calib_from_pose(pose, self.frame_size, calib), pose, target, "gps")
        self.gps_checked, self.gps_fit_t = True, t
        self.pending = new
        self.result = CalibStatus(
            "done", 100, f"Đã chỉnh thang khoảng cách theo GPS (tốc độ đo từ vạch kẻ lệch {vn(err * 100, 1)} %)",
            ok=True, new_calib=new,
            note=f"Tự chỉnh theo GPS: thang khoảng cách lệch {vn(err * 100, 1)} % -> tiêu cự "
                 f"{vn(new.pose.focal_w * self.frame_size[0], 0)} px")
        return self.result

    # ------------------------------------------------------------------

    def _monitor(self, sample: Optional[_Sample], mapper: GroundPlaneMapper, calib: CalibrationConfig,
                 t: float) -> CalibStatus:
        if self.pending is None:
            scaled = self._ref_check(calib) or self._gps_check(calib, t)
            if scaled is not None:
                return scaled
        if self.refs:                    # tốc độ vừa nhập: chờ đủ ±REF_WINDOW_S quanh lúc đọc số
            return CalibStatus(self.result.state, 100, f"Đang so {vn(self.refs[-1][1], 0)} km/h đã nhập với tốc độ "
                                                       f"đo từ vạch kẻ đứt…", ok=self.result.ok)
        status = CalibStatus(self.result.state, 100, self.result.message, ok=self.result.ok)
        if sample is None or self.pending is not None:
            return status
        self.recent.append(sample)
        if len(self.recent) < self.DRIFT_WINDOW:
            return status
        vy = mapper.H_inv @ np.array([0.0, 1.0, 0.0])
        if abs(vy[2]) < 1e-12:
            return status
        f = mapper.focal_px or focal_px(calib.pose, self.frame_size, calib.camera_vfov_deg)
        dv = abs(np.median([s.vp[1] for s in self.recent]) - vy[1] / vy[2])
        straight = [s.vp[0] for s in self.recent if s.straight]
        du = abs(np.median(straight) - vy[0] / vy[2]) if len(straight) >= self.MIN_STRAIGHT * len(self.recent) else 0.0
        if math.degrees(math.atan(du / f)) <= self.DRIFT_DEG[0] and math.degrees(math.atan(dv / f)) <= self.DRIFT_DEG[1]:
            return status
        self.recent.clear()
        if calib.pose.active:            # tư thế: đo lại từ đầu rồi tự áp dụng
            self.result = None
            self.samples = []
            self.drifted = True
            self.scale_obs.clear()       # quãng đường thật giữa 2 hàng ảnh đổi theo tư thế camera: gom lại
            self.scale_rows = self._scale_key = None
            return self._collecting(0)
        self.result = CalibStatus("drift", 100, "Camera có vẻ đã bị xê dịch so với lúc căn chỉnh - nên căn chỉnh lại",
                                  ok=False)
        return self.result
