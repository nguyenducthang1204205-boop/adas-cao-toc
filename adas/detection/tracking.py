"""
Bám vết dày giữa các lần chạy YOLO ("nhận diện thưa, bám vết dày"). Cùng thuật toán với
mobile/android: core/TemplateTracker.kt.

YOLO chạy thưa (mỗi N khung, hoặc trên điện thoại: bất cứ khi nào luồng nền rảnh). Ở các khung giữa,
mỗi xe được bám bằng so khớp mẫu trên ảnh xám thu nhỏ:
  - mẫu "neo" lấy từ khung YOLO gần nhất: lưới tối đa 16x16 điểm (nội suy song tuyến) trong hộp xe,
    chuẩn hóa trung bình 0, độ dài 1;
  - tìm vị trí + tỉ lệ có tương quan chuẩn hóa (NCC) lớn nhất: dò thô vị trí bước 2 px ở tỉ lệ hiện tại,
    rồi dò tinh ±1 px x 3 tỉ lệ (0,97 / 1 / 1,03 - xe tiến lại gần thì to ra) quanh điểm tốt nhất, cuối
    cùng nội suy parabol dưới pixel (ở 20 m, 1 px theo chiều dọc ~ 0,3-0,7 m khoảng cách);
  - NCC < MIN_NCC (bị che, quá tối...): không đo, hộp giữ nguyên, khoảng cách chỉ dự đoán ("coast").
Đây là phép đo thật trên từng khung nên Kalman (kalman.py) vẫn nhận khoảng cách mới ở mọi khung.
"""

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import cv2
import numpy as np

from adas.detection.detector import Detection

WORK_W = 640            # ảnh xám làm việc rộng tối đa 640 px (khung nhỏ hơn giữ nguyên)
GRID = 16               # lưới mẫu tối đa GRID x GRID điểm
SCALES = (0.97, 1.0, 1.03)
MIN_NCC = 0.6
SEARCH_BASE = 4.0       # bán kính dò (px ảnh làm việc) = SEARCH_BASE + SEARCH_REL * cạnh lớn của hộp
SEARCH_REL = 0.08
SEARCH_MAX = 10
MAX_TRACKED = 4         # chỉ bám chi tiết các xe gần nhất (đáy hộp thấp nhất); còn lại giữ hộp cũ
COAST_MAX_S = 0.5       # mất dấu lâu hơn -> bỏ track tới lần YOLO sau
MAX_YOLO_MISSES = 2     # YOLO bỏ sót 1 lần: bám tiếp; 2 lần liên tiếp: bỏ (tránh "xe ma" khi xe đã rời làn)
HISTORY_S = 1.5         # lịch sử hộp (cho kết quả YOLO về trễ trên điện thoại)


def work_scale(frame_w: int) -> float:
    return min(1.0, WORK_W / frame_w)


def to_work_gray(frame: np.ndarray) -> np.ndarray:
    """BGR -> ảnh xám float32 thu nhỏ về chiều rộng WORK_W."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    k = work_scale(gray.shape[1])
    if k < 1.0:
        gray = cv2.resize(gray, (round(gray.shape[1] * k), round(gray.shape[0] * k)), interpolation=cv2.INTER_AREA)
    return gray.astype(np.float32)


def _grid(bw: float, bh: float):
    nx = max(4, min(GRID, int(bw + 0.5)))      # làm tròn như Dart (round() của Python là kiểu banker)
    ny = max(4, min(GRID, int(bh + 0.5)))
    return nx, ny


def _sample(gray: np.ndarray, cx: np.ndarray, cy: np.ndarray, bw: float, bh: float, nx: int, ny: int) -> np.ndarray:
    """Lấy mẫu song tuyến lưới nx x ny trong các hộp tâm (cx[i], cy[i]) cỡ bw x bh -> (n, ny*nx)."""
    h, w = gray.shape
    gx = (np.arange(nx) + 0.5) * (bw / nx) - bw / 2
    gy = (np.arange(ny) + 0.5) * (bh / ny) - bh / 2
    X = np.clip(cx[:, None, None] + gx[None, None, :], 0, w - 1.001).astype(np.float32)
    Y = np.clip(cy[:, None, None] + gy[None, :, None], 0, h - 1.001).astype(np.float32)
    X, Y = np.broadcast_to(X, (len(cx), ny, nx)), np.broadcast_to(Y, (len(cx), ny, nx))
    v = cv2.remap(gray, np.ascontiguousarray(X.reshape(-1, nx)), np.ascontiguousarray(Y.reshape(-1, nx)),
                  cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return v.reshape(len(cx), -1)


def _normalize(v: np.ndarray) -> Optional[np.ndarray]:
    v = v - v.mean(axis=-1, keepdims=True)
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, 1e-6)


def _parabola(cm: float, c0: float, cp: float) -> float:
    d = cm - 2 * c0 + cp
    return 0.5 * (cm - cp) / d if d < 0 else 0.0


@dataclass
class _Track:
    tid: int
    det: Detection                 # hộp hiện tại (pixel khung gốc) + lớp
    template: np.ndarray           # mẫu neo đã chuẩn hóa (ny*nx,)
    nx: int
    ny: int
    anchor_w: float                # kích thước hộp neo (px ảnh làm việc)
    anchor_h: float
    scale: float = 1.0             # kích thước hiện tại / kích thước neo
    last_meas_t: float = 0.0
    ncc: float = 1.0
    yolo_misses: int = 0
    history: deque = field(default_factory=lambda: deque(maxlen=64))   # (t, bbox)


class TemplateTracker:
    def __init__(self):
        self.tracks: Dict[int, _Track] = {}
        self._next_id = 1_000_000       # id riêng khi detection không có id (tránh trùng ByteTrack)
        self.k = 1.0

    def reset(self) -> None:
        self.tracks.clear()

    # ------------------------------------------------------------------ YOLO -> neo lại

    def refresh(self, dets: List[Detection], gray: np.ndarray, t: float, k: float,
                det_t: Optional[float] = None) -> List[Detection]:
        """
        Kết quả YOLO mới: ghép với track cũ (theo id, hoặc IoU tại thời điểm chụp det_t), neo lại mẫu
        ở khung hiện tại. det_t < t khi YOLO chạy nền và trả kết quả trễ (điện thoại): hộp YOLO được
        dời theo chuyển động mà tracker đã đo từ det_t tới t. Trả về danh sách hộp hiện tại.
        """
        self.k = k
        det_t = t if det_t is None else det_t
        used, out = set(), []
        for d in dets:
            box = np.asarray(d.bbox, dtype=np.float64)
            tr = self.tracks.get(d.track_id) if d.track_id is not None else None
            if tr is None and d.track_id is None:
                tr = self._match_iou(box, d.class_name, det_t, used)
            if tr is not None and det_t < t:
                past = self._box_at(tr, det_t)
                if past is not None:
                    box = box + (np.asarray(tr.det.bbox) - past)
            tid = d.track_id if d.track_id is not None else (tr.tid if tr is not None else self._new_id())
            det = Detection(bbox=box, confidence=d.confidence, class_name=d.class_name, track_id=tid, source="yolo")
            out.append(det)
            used.add(tid)
            nt = self._anchor(tid, det, gray, t)
            if nt is None:                      # không lấy được mẫu: vẫn báo xe ở khung này, không bám tiếp
                self.tracks.pop(tid, None)
                continue
            if tr is not None:
                nt.history = tr.history
            nt.history.append((t, box.copy()))
            self.tracks[tid] = nt
        # track YOLO lần này không thấy: bám tiếp ngay trên khung này (YOLO có thể bỏ sót một lần)
        for tid in list(self.tracks):
            if tid in used:
                continue
            tr = self.tracks[tid]
            tr.yolo_misses += 1
            if tr.yolo_misses >= MAX_YOLO_MISSES:
                del self.tracks[tid]
                continue
            self._step(tr, gray, t)
            if tr.det.source == "coast" and t - tr.last_meas_t > COAST_MAX_S:
                del self.tracks[tid]
                continue
            tr.history.append((t, np.asarray(tr.det.bbox, dtype=np.float64).copy()))
            out.append(tr.det)
        return out

    def _new_id(self) -> int:
        self._next_id += 1
        return self._next_id

    def _match_iou(self, box, cls, det_t, used) -> Optional[_Track]:
        best, best_iou = None, 0.3
        for tr in self.tracks.values():
            if tr.tid in used or tr.det.class_name != cls:
                continue
            past = self._box_at(tr, det_t)
            if past is None:
                continue
            v = _iou(box, past)
            if v > best_iou:
                best, best_iou = tr, v
        return best

    @staticmethod
    def _box_at(tr: _Track, t: float) -> Optional[np.ndarray]:
        if not tr.history:
            return None
        return min(tr.history, key=lambda e: abs(e[0] - t))[1]

    def _anchor(self, tid: int, det: Detection, gray: np.ndarray, t: float) -> Optional[_Track]:
        x1, y1, x2, y2 = (float(v) * self.k for v in det.bbox)
        bw, bh = x2 - x1, y2 - y1
        if bw < 4 or bh < 4:
            return None
        nx, ny = _grid(bw, bh)
        v = _sample(gray, np.array([(x1 + x2) / 2]), np.array([(y1 + y2) / 2]), bw, bh, nx, ny)[0]
        if v.std() < 2.0:                      # mẫu phẳng (đêm tối, sương): không bám được
            return None
        return _Track(tid, det, _normalize(v), nx, ny, bw, bh, last_meas_t=t)

    # ------------------------------------------------------------------ khung không chạy YOLO

    def track(self, gray: np.ndarray, t: float) -> List[Detection]:
        order = sorted(self.tracks.values(), key=lambda tr: -tr.det.bbox[3])   # gần trước (đáy hộp thấp)
        out = []
        for i, tr in enumerate(order):
            if i < MAX_TRACKED:
                self._step(tr, gray, t)
            elif t - tr.last_meas_t > 0:
                tr.det = Detection(tr.det.bbox, tr.det.confidence, tr.det.class_name, tr.tid, "coast")
            if tr.det.source == "coast" and t - tr.last_meas_t > COAST_MAX_S:
                del self.tracks[tr.tid]
                continue
            tr.history.append((t, np.asarray(tr.det.bbox, dtype=np.float64).copy()))
            out.append(tr.det)
        return out

    def _step(self, tr: _Track, gray: np.ndarray, t: float) -> None:
        k = self.k
        x1, y1, x2, y2 = (float(v) * k for v in tr.det.bbox)
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        bw0, bh0 = tr.anchor_w * tr.scale, tr.anchor_h * tr.scale
        r = int(min(SEARCH_MAX, math.ceil(SEARCH_BASE + SEARCH_REL * max(bw0, bh0))))
        # dò thô vị trí (bước 2 px) ở tỉ lệ hiện tại
        coarse = np.arange(-r, r + 1, 2)
        dx, dy = np.meshgrid(coarse, coarse)
        dx, dy = dx.ravel().astype(np.float64), dy.ravel().astype(np.float64)
        c = _normalize(_sample(gray, cx + dx, cy + dy, bw0, bh0, tr.nx, tr.ny)) @ tr.template
        i = int(np.argmax(c))
        bx, by = dx[i], dy[i]
        # dò tinh ±1 px x 3 tỉ lệ quanh điểm tốt nhất, rồi nội suy parabol theo bảng 3x3 của tỉ lệ được chọn
        fx, fy = np.meshgrid(np.arange(-1, 2), np.arange(-1, 2))
        fxs, fys = bx + fx.ravel(), by + fy.ravel()
        best = None
        for s in SCALES:
            cs = (_normalize(_sample(gray, cx + fxs, cy + fys, bw0 * s, bh0 * s, tr.nx, tr.ny)) @ tr.template).reshape(3, 3)
            j = int(np.argmax(cs))
            if best is None or cs.flat[j] > best[0]:
                best = (float(cs.flat[j]), j, s, cs)
        ncc, j, s, c = best
        jy, jx = divmod(j, 3)
        ox, oy = bx + jx - 1, by + jy - 1
        if jx == 1:
            ox += _parabola(c[1, 0], c[1, 1], c[1, 2])
        if jy == 1:
            oy += _parabola(c[0, 1], c[1, 1], c[2, 1])
        tr.ncc = ncc
        if ncc < MIN_NCC:
            tr.det = Detection(tr.det.bbox, tr.det.confidence, tr.det.class_name, tr.tid, "coast")
            return
        tr.scale *= s
        bw, bh = tr.anchor_w * tr.scale, tr.anchor_h * tr.scale
        ncx, ncy = cx + ox, cy + oy
        box = np.array([ncx - bw / 2, ncy - bh / 2, ncx + bw / 2, ncy + bh / 2]) / k
        tr.det = Detection(box, tr.det.confidence, tr.det.class_name, tr.tid, "track")
        tr.last_meas_t = t


def _iou(a, b) -> float:
    xx1, yy1 = max(a[0], b[0]), max(a[1], b[1])
    xx2, yy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, xx2 - xx1) * max(0.0, yy2 - yy1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0
