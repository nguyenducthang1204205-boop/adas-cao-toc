"""
Ước lượng khoảng cách, vị trí làn, tốc độ tiếp cận và TTC cho từng phương tiện.

Phương pháp chính: IPM - chiếu điểm tiếp xúc mặt đường sang hệ mét.
Phương pháp dự phòng: Pinhole - d = H_thực · f / h_pixel (khi điểm nằm ngoài
vùng IPM hợp lệ, ví dụ xe bị che khuất phần dưới hoặc quá xa).

Khoảng cách và tốc độ tiếp cận theo từng track ID lấy từ bộ lọc Kalman (kalman.py). Khung "coast"
(tracker mất dấu) không có phép đo: chỉ dự đoán.
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from adas.config import CalibrationConfig, REAL_HEIGHTS_M, REAL_WIDTHS_M
from adas.detection.detector import Detection
from adas.distance.ipm import GroundPlaneMapper
from adas.distance.kalman import RATE_STD_REPORT, RangeKalman, measurement_sigma
from adas.distance.lane import LaneEstimate


@dataclass
class VehicleState:
    det: Detection
    distance_m: float
    lateral_m: float
    method: str                          # "IPM" | "Xa" (ngoài tầm đo IPM)
    in_ego_lane: bool
    closing_speed_mps: Optional[float]   # > 0: đang tiến lại gần
    ttc_s: Optional[float]
    risk: str = "safe"                   # safe | warning | danger | info (ngoài làn)


class _Track:
    def __init__(self, kf: RangeKalman, t: float):
        self.kf = kf
        self.last_seen = t


class DistanceEstimator:
    MIN_CLOSING_MPS = 0.5     # Dưới mức này coi như không tiếp cận (TTC = None)
    TRACK_TIMEOUT_S = 2.0

    def __init__(self, mapper: GroundPlaneMapper, calib: CalibrationConfig):
        self.mapper = mapper
        self.calib = calib
        h = mapper.frame_h
        self.focal_px = mapper.focal_px or h / (2 * math.tan(math.radians(calib.camera_vfov_deg) / 2))
        self.tracks: Dict[int, _Track] = {}

    def reset(self) -> None:
        self.tracks.clear()

    def estimate(self, detections: List[Detection], t: float,
                 lane: Optional[LaneEstimate] = None) -> List[VehicleState]:
        """lane: làn nhận diện từ vạch kẻ; None -> hành lang cố định ±lane_half_width_m."""
        if not detections:
            self._drop_stale(t)
            return []

        ground_px = np.array([d.ground_point for d in detections])
        ground_m = self.mapper.image_to_ground(ground_px)

        states = []
        for det, (gx, gy) in zip(detections, ground_m):
            if not np.isnan(gy):
                distance, lateral, method = float(gy), float(gx), "IPM"
            else:
                # Điểm chạm đất ở trên chân trời hoặc ngoài tầm đo -> xe ở rất xa.
                # Không để ước lượng dự phòng cho ra số nhỏ hơn tầm đo (sẽ đảo thứ tự
                # với các xe gần hơn đo bằng IPM).
                distance, lateral = self._pinhole(det)
                distance = max(distance, self.calib.max_range_m)
                method = "Xa"

            distance, closing = self._update_track(det.track_id, distance, t, far=method == "Xa",
                                                   measured=det.source != "coast")
            ttc = distance / closing if (closing is not None and closing > self.MIN_CLOSING_MPS) else None
            if lane is not None:
                in_lane = lane.contains(lateral, distance)
            else:
                in_lane = abs(lateral) <= self.calib.lane_half_width_m

            states.append(VehicleState(
                det=det,
                distance_m=distance,
                lateral_m=lateral,
                method=method,
                in_ego_lane=in_lane,
                closing_speed_mps=closing,
                ttc_s=ttc,
            ))

        self._drop_stale(t)
        states.sort(key=lambda s: s.distance_m)
        return states

    # ------------------------------------------------------------------

    def _pinhole(self, det: Detection):
        """Ước lượng theo kích thước thật của xe (trung bình nhân theo chiều cao và chiều rộng)."""
        f = self.focal_px
        d_h = REAL_HEIGHTS_M.get(det.class_name, 1.5) * f / max(det.height, 1.0)
        d_w = REAL_WIDTHS_M.get(det.class_name, 1.8) * f / max(det.width, 1.0)
        d = math.sqrt(d_h * d_w)
        cx = (det.bbox[0] + det.bbox[2]) / 2
        lateral = (cx - self.mapper.frame_w / 2) * d / f
        return float(d), float(lateral)

    def _update_track(self, track_id: Optional[int], d: float, t: float, far: bool = False,
                      measured: bool = True):
        """Kalman theo track: trả về (khoảng cách đã lọc, tốc độ tiếp cận m/s hoặc None khi chưa đủ tin)."""
        if track_id is None:
            return d, None
        sigma = measurement_sigma(d, far)
        tr = self.tracks.get(track_id)
        if tr is None:
            tr = self.tracks[track_id] = _Track(RangeKalman(d, t, sigma), t)
        else:
            tr.kf.predict(t)
            if measured:
                tr.kf.update(d, sigma)
        if measured:
            tr.last_seen = t
        kf = tr.kf
        closing = kf.closing_speed if kf.rate_std < RATE_STD_REPORT else None
        return kf.distance, closing

    def _drop_stale(self, t: float) -> None:
        stale = [k for k, tr in self.tracks.items() if t - tr.last_seen > self.TRACK_TIMEOUT_S]
        for k in stale:
            del self.tracks[k]
