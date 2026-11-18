"""
Phát hiện & bám vết phương tiện bằng YOLOv11 (Ultralytics) + ByteTrack.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import numpy as np


@dataclass
class Detection:
    bbox: np.ndarray              # [x1, y1, x2, y2] pixel
    confidence: float
    class_name: str
    track_id: Optional[int] = None
    source: str = "yolo"          # "yolo" | "track" (bám vết, có đo) | "coast" (mất dấu, chỉ dự đoán)

    @property
    def ground_point(self) -> tuple:
        """Điểm tiếp xúc mặt đường ≈ trung điểm cạnh dưới bounding box."""
        x1, _, x2, y2 = self.bbox
        return (float(x1 + x2) / 2.0, float(y2))

    @property
    def height(self) -> float:
        return float(self.bbox[3] - self.bbox[1])

    @property
    def width(self) -> float:
        return float(self.bbox[2] - self.bbox[0])


def _pick_device(device: str) -> str:
    if device and device != "auto":
        return device
    try:
        import torch
        return "0" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


class VehicleDetector:
    def __init__(self, weights: Path, fallback_weights: Path, enabled_classes: List[str],
                 confidence: float = 0.35, iou: float = 0.45, imgsz: int = 640,
                 device: str = "auto"):
        from ultralytics import YOLO

        if Path(weights).exists():
            self.weights_used = str(weights)
        elif Path(fallback_weights).exists():
            self.weights_used = str(fallback_weights)
        else:
            self.weights_used = Path(fallback_weights).name  # Ultralytics tự tải về
        self.using_fallback = self.weights_used != str(weights)
        self.model = YOLO(self.weights_used)
        self.names = self.model.names  # {id: name}
        self.device = _pick_device(device)
        self.confidence = confidence
        self.iou = iou
        self.imgsz = imgsz
        self.set_enabled_classes(enabled_classes)

    def set_enabled_classes(self, enabled: List[str]) -> None:
        ids = [i for i, n in self.names.items() if n in enabled]
        if not ids:
            # Mô hình không có lớp nào trùng (vd: tên lớp khác) -> lấy các lớp xe phổ biến
            ids = [i for i, n in self.names.items() if n in ("car", "truck", "bus")]
        self.class_ids = ids or None

    def warmup(self) -> None:
        dummy = np.zeros((self.imgsz, self.imgsz, 3), dtype=np.uint8)
        self.model.predict(dummy, imgsz=self.imgsz, device=self.device, verbose=False)

    def detect(self, frame: np.ndarray, track: bool = True) -> List[Detection]:
        kwargs = dict(conf=self.confidence, iou=self.iou, imgsz=self.imgsz,
                      device=self.device, classes=self.class_ids,
                      verbose=False)
        if track:
            result = self.model.track(frame, persist=True, tracker="bytetrack.yaml", **kwargs)[0]
        else:
            result = self.model.predict(frame, **kwargs)[0]

        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            return []

        xyxy = boxes.xyxy.cpu().numpy()
        confs = boxes.conf.cpu().numpy()
        clss = boxes.cls.cpu().numpy().astype(int)
        ids = boxes.id.cpu().numpy().astype(int) if (track and boxes.id is not None) else None

        return [
            Detection(
                bbox=xyxy[i],
                confidence=float(confs[i]),
                class_name=self.names[int(clss[i])],
                track_id=int(ids[i]) if ids is not None else None,
            )
            for i in range(len(xyxy))
        ]
