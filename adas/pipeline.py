"""
Pipeline xử lý 1 khung hình theo kiến trúc:

    Video Stream ─► [1] YOLOv11 Detection ─► [2] IPM Distance Calculation ─► [3] Alert Engine ─► GUI
    adas/stream       adas/detection           adas/distance                    adas/alert           gui/

Tầng Video Stream (đọc khung) và GUI (vẽ + hiển thị) do luồng xử lý gui/worker.py điều phối;
lớp này thực hiện 3 tầng ở giữa và đo thời gian từng tầng (FrameResult.timings_ms).
"""

import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from adas.alert.engine import AlertManager
from adas.alert.thresholds import RISK_ORDER, Thresholds, classify_risk, compute_thresholds
from adas.config import AppConfig
from adas.detection.detector import VehicleDetector
from adas.detection.tracking import TemplateTracker, to_work_gray, work_scale
from adas.distance.ego_speed import EgoSpeedEstimator
from adas.distance.estimator import DistanceEstimator, VehicleState
from adas.distance.ipm import GroundPlaneMapper
from adas.distance.lane import EgoLaneDetector, LaneEstimate
from adas.distance.online_calib import CalibStatus, OnlineCalibrator

STAGES = ("stream", "detection", "ipm", "alert", "gui")
STAGE_LABELS = {"stream": "Video Stream", "detection": "YOLOv11", "ipm": "IPM",
                "alert": "Alert Engine", "gui": "GUI"}


@dataclass
class FrameResult:
    vehicles: List[VehicleState] = field(default_factory=list)
    lead: Optional[VehicleState] = None       # Xe gần nhất cùng làn phía trước
    lane: Optional[LaneEstimate] = None       # Làn xe chủ nhận diện từ vạch kẻ (None: dùng hành lang cố định)
    thresholds: Optional[Thresholds] = None
    speed_kmh: float = 0.0                    # tốc độ xe chủ dùng để tính ngưỡng
    speed_measured: bool = False              # True: đo từ video; False: tốc độ nhập tay
    calib: Optional[CalibStatus] = None       # tự hoàn thiện / kiểm tra căn chỉnh khi chạy (None: tắt)
    raw_level: str = "safe"
    level: str = "safe"                       # Mức cảnh báo sau chống nhiễu
    detected: bool = True                     # khung này chạy YOLO (False: chỉ bám vết)
    stride: int = 1                           # đang chạy YOLO mỗi bao nhiêu khung
    yolo_ms: float = 0.0                      # thời gian YOLO gần đây (trung bình trượt)
    timings_ms: Dict[str, float] = field(default_factory=dict)   # thời gian từng tầng

    @property
    def inference_ms(self) -> float:
        return self.timings_ms.get("detection", 0.0)


class ADASPipeline:
    def __init__(self, cfg: AppConfig, detector: VehicleDetector, frame_size: Tuple[int, int]):
        self.cfg = cfg
        self.detector = detector
        self.frame_size = frame_size
        self.mapper = GroundPlaneMapper(cfg.calibration, frame_size)
        self.estimator = DistanceEstimator(self.mapper, cfg.calibration)
        self.lane_detector = EgoLaneDetector(self.mapper)
        self.speed_estimator = EgoSpeedEstimator(self.mapper)
        self.online_calib = OnlineCalibrator(frame_size)
        self.alert = AlertManager(cfg.alert)
        self.tracker = TemplateTracker()
        self._tracker_ready = False             # tracker đã được YOLO neo (False: khung đầu, vừa đổi từ N=1)
        self._since_det = 0
        self._yolo_ms = 0.0
        self._yolo_runs = 0
        self._frame_dt = 1 / 30
        self._last_t: Optional[float] = None

    def update_calibration(self) -> None:
        """Gọi sau khi người dùng hiệu chỉnh lại IPM."""
        self.mapper = GroundPlaneMapper(self.cfg.calibration, self.frame_size)
        self.estimator = DistanceEstimator(self.mapper, self.cfg.calibration)
        self.lane_detector = EgoLaneDetector(self.mapper)
        self.speed_estimator = EgoSpeedEstimator(self.mapper)
        self.online_calib.calibration_changed(self.cfg.calibration)

    def stride(self) -> int:
        """YOLO mỗi N khung: cấu hình cố định, hoặc tự động để YOLO chiếm ≤ nửa thời gian một khung."""
        n = self.cfg.model.detect_every
        if n >= 1:
            return n
        if self._yolo_ms <= 0:
            return 1
        return max(1, min(4, math.ceil(self._yolo_ms / (500 * self._frame_dt))))

    def process(self, frame: np.ndarray, t: float, track: bool = True) -> FrameResult:
        timings = {}

        # [1] YOLOv11 Detection: phát hiện, phân loại, bám vết phương tiện. Nhận diện thưa: YOLO mỗi N
        #     khung, các khung giữa đo lại vị trí xe bằng so khớp mẫu (detection/tracking.py) - nhanh hơn hàng chục lần
        t0 = time.perf_counter()
        if self._last_t is not None and t > self._last_t:
            self._frame_dt = 0.9 * self._frame_dt + 0.1 * min(t - self._last_t, 0.5)
        self._last_t = t
        stride = self.stride() if track else 1
        detected = stride == 1 or not self._tracker_ready or self._since_det + 1 >= stride
        if detected:
            detections = self.detector.detect(frame, track=track)
            ms = (time.perf_counter() - t0) * 1000
            self._yolo_runs += 1
            if self._yolo_runs > 1:             # lần đầu gồm cả khởi động GPU (~1-2 s): không tính
                self._yolo_ms = ms if self._yolo_ms <= 0 else 0.8 * self._yolo_ms + 0.2 * ms
            if stride > 1:      # neo mẫu cho các khung bám vết sau
                detections = self.tracker.refresh(detections, to_work_gray(frame), t, work_scale(frame.shape[1]))
            else:
                self.tracker.reset()
            self._tracker_ready = stride > 1
            self._since_det = 0
        else:
            detections = self.tracker.track(to_work_gray(frame), t)
            self._since_det += 1
        t1 = time.perf_counter()
        timings["detection"] = (t1 - t0) * 1000

        # [2] IPM Distance Calculation: làn xe chủ từ vạch kẻ, tốc độ xe chủ, điểm chạm đất -> mặt đường (m), TTC
        cfg = self.cfg
        lane_seen = None
        if cfg.alert.auto_lane or cfg.auto_speed:      # đo tốc độ cũng cần vị trí vạch làn
            lane_seen = self.lane_detector.update(frame, [d.bbox for d in detections])
        else:
            self.lane_detector.reset()
        lane = lane_seen if cfg.alert.auto_lane else None
        measured = None
        if cfg.auto_speed and track:                   # ảnh tĩnh: không có chuyển động để đo
            measured = self.speed_estimator.update(frame, lane_seen, t)
        else:
            self.speed_estimator.reset()
        speed = measured if measured is not None else cfg.speed_kmh
        calib = None
        if cfg.auto_calib and track and (cfg.alert.auto_lane or cfg.auto_speed):
            calib = self.online_calib.update(lane_seen, self.mapper, cfg.calibration, t, measured)
        vehicles = self.estimator.estimate(detections, t, lane)
        t2 = time.perf_counter()
        timings["ipm"] = (t2 - t1) * 1000

        # [3] Alert Engine: ngưỡng theo tốc độ/điều kiện -> mức rủi ro -> chống nhiễu + âm thanh
        thr = compute_thresholds(speed, self.cfg.policy)
        only_lane = self.cfg.alert.only_ego_lane
        raw_level = "safe"
        lead = None
        for vs in vehicles:
            if (only_lane and not vs.in_ego_lane) or vs.method == "Xa":
                vs.risk = "info"  # ngoài làn, hoặc ngoài tầm đo tin cậy -> không cảnh báo
                continue
            vs.risk = classify_risk(vs.distance_m, vs.ttc_s, thr, self.cfg.policy)
            if RISK_ORDER[vs.risk] > RISK_ORDER[raw_level]:
                raw_level = vs.risk
            if vs.in_ego_lane and lead is None:
                lead = vs  # vehicles đã sắp xếp gần -> xa
        level = self.alert.update(raw_level)
        timings["alert"] = (time.perf_counter() - t2) * 1000

        return FrameResult(vehicles=vehicles, lead=lead, lane=lane, thresholds=thr,
                           speed_kmh=speed, speed_measured=measured is not None, calib=calib,
                           raw_level=raw_level, level=level, timings_ms=timings,
                           detected=detected, stride=stride, yolo_ms=self._yolo_ms)
