"""
Tự nhận diện làn đường xe chủ đang đi từ vạch kẻ đường (mỗi khung hình).

Dùng chính homography IPM đã hiệu chỉnh để chiếu ảnh sang góc nhìn từ trên xuống (BEV)
có đơn vị mét. Trên BEV, vạch kẻ là các dải sáng hẹp (~0.15-0.2 m) gần như thẳng đứng:
  1. Top-hat theo chiều ngang giữ lại các dải sáng hẹp hơn ~0.6 m (vạch sơn), bỏ mặt đường,
     dải phân cách, thân xe; vùng có xe (bounding box YOLO) bị loại bỏ.
  2. Tìm vị trí 2 vạch gần trục xe nhất ở hai bên: theo histogram cột (lần đầu) hoặc
     quanh đường đã tìm ở khung trước.
  3. Cửa sổ trượt từ gần ra xa thu điểm vạch, khớp X(Y) = c0 + c1·Y + c2·Y² (đường cong).
  4. Kiểm tra bề rộng làn hợp lý, làm mượt theo thời gian; thiếu một bên thì suy ra từ
     bên còn lại và bề rộng làn đã đo.

Bề rộng làn đo được là bề rộng thật (không giả định 3.75 m) với điều kiện IPM đúng tỷ lệ:
chiều cao camera không đổi nên chỉ cần hiệu chỉnh một lần trên đoạn đường biết bề rộng làn.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np

from adas.distance.ipm import GroundPlaneMapper


@dataclass
class LaneEstimate:
    left: np.ndarray           # (c0, c1, c2) của vạch trái: X = c0 + c1·Y + c2·Y²
    right: np.ndarray          # (c0, c1, c2) của vạch phải
    found_left: bool           # True: thấy vạch ở khung này; False: suy ra / giữ từ khung trước
    found_right: bool

    REF_Y = 10.0               # khoảng cách tham chiếu để báo bề rộng làn

    @staticmethod
    def _eval(c: np.ndarray, y) -> np.ndarray:
        y = np.asarray(y, dtype=np.float64)
        return c[0] + c[1] * y + c[2] * y * y

    def x_left(self, y) -> np.ndarray:
        return self._eval(self.left, y)

    def x_right(self, y) -> np.ndarray:
        return self._eval(self.right, y)

    @property
    def width_m(self) -> float:
        return float(self.x_right(self.REF_Y) - self.x_left(self.REF_Y))

    @property
    def offset_m(self) -> float:
        """Độ lệch của xe chủ so với tim làn (dương = xe lệch sang phải)."""
        return float(-(self.x_left(0.0) + self.x_right(0.0)) / 2)

    def contains(self, lateral_m: float, distance_m: float) -> bool:
        return bool(self.x_left(distance_m) <= lateral_m <= self.x_right(distance_m))


class EgoLaneDetector:
    X_HALF_M = 6.0             # quét ±6 m quanh trục xe
    Y_MIN_M, Y_MAX_M = 4.0, 36.0
    RES_X, RES_Y = 0.05, 0.1   # m / pixel BEV
    MIN_WIDTH_M, MAX_WIDTH_M = 2.2, 5.2   # rộng hơn thực tế (2.75-3.75 m) để chịu sai số hiệu chỉnh
    DEFAULT_WIDTH_M = 3.5
    PAINT_MAX_M = 0.6          # vạch sơn hẹp hơn mức này
    TOPHAT_MIN = 14            # độ sáng nổi lên tối thiểu so với mặt đường
    WINDOWS = 8
    WIN_HALF_M = 0.45
    MAX_CURV = 1 / (2 * 300)   # |c2| ứng với bán kính cong >= 300 m
    SMOOTH = 0.35              # hệ số EMA cho hệ số đường
    LOST_FRAMES = 20           # mất cả 2 vạch quá số khung này -> trả None
    ACQUIRE_FRAMES = 3         # bắt làn lần đầu: phải thấy đủ 2 vạch hợp lệ liên tiếp chừng này khung
    EGO_MARGIN_M = 0.4         # xe chủ phải nằm trong làn (cho phép đè vạch khi chuyển làn)

    def __init__(self, mapper: GroundPlaneMapper):
        self.mapper = mapper
        self.size = (int(round(2 * self.X_HALF_M / self.RES_X)),
                     int(round((self.Y_MAX_M - self.Y_MIN_M) / self.RES_Y)))
        bw, bh = self.size
        self.M = mapper.bev_matrix(self.size, self.X_HALF_M, self.Y_MIN_M, self.Y_MAX_M) @ mapper.H
        self.col_x = (np.arange(bw) + 0.5) * self.RES_X - self.X_HALF_M      # cột -> X (m)
        self.row_y = self.Y_MAX_M - (np.arange(bh) + 0.5) * self.RES_Y       # hàng -> Y (m)
        self._kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (int(self.PAINT_MAX_M / self.RES_X) | 1, 1))
        self._valid = None
        self.reset()

    def reset(self) -> None:
        self.state: Optional[LaneEstimate] = None
        self.width = self.DEFAULT_WIDTH_M
        self.missed = 0
        self.hits = 0
        self.confirmed = False

    # ------------------------------------------------------------------

    def update(self, frame: np.ndarray, boxes: List[Tuple[float, float, float, float]] = ()
               ) -> Optional[LaneEstimate]:
        """Trả về làn đã xác nhận, hoặc None (chưa bắt được / mất vạch -> dùng hành lang cố định)."""
        mask = self._paint_mask(frame, boxes)
        left, right = self._find_lines(mask)
        found_l, found_r = left is not None, right is not None
        if found_l and found_r and not self._plausible(left, right):
            if self.state is None:
                found_l = found_r = False
            else:   # cặp vạch vô lý -> giữ bên gần đường cũ hơn
                keep_left = self._closer_to_prev(left, right)
                found_l, found_r = keep_left, not keep_left

        if self.state is None and not (found_l and found_r):
            self.hits = 0           # chưa bắt được làn: chỉ nhận khi thấy đủ cả 2 vạch
            return None
        if not found_l and not found_r:
            self.missed += 1
            if self.missed > self.LOST_FRAMES:
                self.reset()
                return None
            self.state = LaneEstimate(self.state.left, self.state.right, False, False)
            return self.state if self.confirmed else None
        self.missed = 0

        if found_l and found_r:
            self.hits += 1
            w = float(LaneEstimate._eval(right - left, LaneEstimate.REF_Y))
            self.width += (0.5 if self.hits <= self.ACQUIRE_FRAMES else 0.1) * (w - self.width)
        if not found_l:
            left = right - np.array([self.width, 0.0, 0.0])
        if not found_r:
            right = left + np.array([self.width, 0.0, 0.0])

        prev = self.state
        if prev is not None and abs(self._centre(left, right) - self._centre(prev.left, prev.right)) < 0.5 * self.width:
            a = self.SMOOTH
            left = prev.left + a * (left - prev.left)
            right = prev.right + a * (right - prev.right)
        # lệch tâm quá nửa làn: xe vừa chuyển làn -> nhận làn mới ngay, không làm mượt
        self.state = LaneEstimate(left, right, found_l, found_r)
        self.confirmed = self.confirmed or self.hits >= self.ACQUIRE_FRAMES
        return self.state if self.confirmed else None

    def _plausible(self, left: np.ndarray, right: np.ndarray) -> bool:
        """Bề rộng làn hợp lý và làn chứa xe chủ (X = 0 tại đầu xe)."""
        w = float(LaneEstimate._eval(right - left, LaneEstimate.REF_Y))
        return (self.MIN_WIDTH_M <= w <= self.MAX_WIDTH_M
                and left[0] <= self.EGO_MARGIN_M and right[0] >= -self.EGO_MARGIN_M)

    # ------------------------------------------------------------------

    def _paint_mask(self, frame, boxes) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        bev = cv2.warpPerspective(gray, self.M, self.size, flags=cv2.INTER_LINEAR)
        if self._valid is None or self._valid_src != gray.shape:
            ones = np.full(gray.shape, 255, np.uint8)
            v = cv2.warpPerspective(ones, self.M, self.size, flags=cv2.INTER_NEAREST)
            self._valid = cv2.erode(v, self._kernel) > 0       # bỏ mép ảnh (tạo cạnh giả)
            self._valid_src = gray.shape
        tophat = cv2.morphologyEx(bev, cv2.MORPH_TOPHAT, self._kernel)
        mask = (tophat > self.TOPHAT_MIN) & self._valid
        if len(boxes):
            veh = np.zeros(gray.shape, np.uint8)
            for x1, y1, x2, y2 in boxes:
                cv2.rectangle(veh, (int(x1) - 4, int(y1)), (int(x2) + 4, int(y2) + 4), 255, -1)
            veh = cv2.warpPerspective(veh, self.M, self.size, flags=cv2.INTER_NEAREST)
            mask &= veh == 0
        return mask

    def _find_lines(self, mask):
        """Trả về hệ số (c0, c1, c2) của vạch trái và vạch phải, None nếu không thấy."""
        if self.state is not None:
            left = self._trace(mask, self.state.left)
            right = self._trace(mask, self.state.right)
            if left is not None and right is not None and self._plausible(left, right):
                return left, right
            # còn một vạch và vạch đó vẫn ở đúng phía của xe chủ
            if right is None and left is not None and left[0] <= self.EGO_MARGIN_M:
                return left, None
            if left is None and right is not None and right[0] >= -self.EGO_MARGIN_M:
                return None, right

        # Tìm lại từ đầu bằng histogram cột (lần đầu, hoặc đã mất dấu)
        hist = np.convolve(mask.sum(0).astype(np.float32), np.ones(5) / 5, mode="same")
        min_rows = 0.06 * mask.shape[0]           # ít nhất ~2 m vạch sơn
        peaks = [i for i in range(2, len(hist) - 2)
                 if hist[i] >= min_rows and hist[i] == hist[max(i - 8, 0): i + 9].max()]
        xs = self.col_x[peaks] if peaks else np.array([])
        lefts = sorted(xs[xs < -0.3], reverse=True)[:2]   # gần trục xe trước
        rights = sorted(xs[xs > 0.3])[:2]

        best, best_score = (None, None), None
        for xl in lefts:
            for xr in rights:
                w = xr - xl
                if self.MIN_WIDTH_M <= w <= self.MAX_WIDTH_M:
                    score = abs(w - self.width)
                    if best_score is None or score < best_score:
                        best, best_score = (xl, xr), score
        if best_score is None:          # không có cặp hợp lệ -> lấy vạch gần nhất một bên (chỉ khi đang bám làn)
            if self.state is None:
                return None, None
            if lefts and (not rights or -lefts[0] <= rights[0]):
                best = (lefts[0], None)
            elif rights:
                best = (None, rights[0])
        return tuple(None if x is None else self._trace(mask, np.array([x, 0.0, 0.0]))
                     for x in best)

    def _trace(self, mask, prior: np.ndarray) -> Optional[np.ndarray]:
        """Cửa sổ trượt dọc theo đường dự kiến `prior`, khớp đa thức qua các điểm vạch."""
        bh, bw = mask.shape
        ys, xs = np.nonzero(mask)
        if len(ys) == 0:
            return None
        Y, X = self.row_y[ys], self.col_x[xs]
        band = (self.Y_MAX_M - self.Y_MIN_M) / self.WINDOWS
        shift = 0.0                            # độ lệch so với prior, cập nhật dần từ gần ra xa
        sel_all = []
        for k in range(self.WINDOWS):
            y0 = self.Y_MIN_M + k * band
            yc = y0 + band / 2
            centre = float(LaneEstimate._eval(prior, yc)) + shift
            sel = np.flatnonzero((Y >= y0) & (Y < y0 + band) & (np.abs(X - centre) < self.WIN_HALF_M))
            if len(sel) >= 6:
                sel_all.append(sel)
                shift = float(np.median(X[sel])) - float(LaneEstimate._eval(prior, yc))
        if not sel_all:
            return None
        sel = np.concatenate(sel_all)
        Ys, Xs = Y[sel], X[sel]
        span = Ys.max() - Ys.min()
        if len(sel) < 25 or span < 3.0:
            return None
        if span >= 15.0 and len(sel_all) >= 4:
            c2, c1, c0 = np.polyfit(Ys, Xs, 2)
            c2 = float(np.clip(c2, -self.MAX_CURV, self.MAX_CURV))
            c0, c1 = np.polyfit(Ys, Xs - c2 * Ys * Ys, 1)[::-1]
        else:
            c1, c0 = np.polyfit(Ys, Xs, 1)
            c2 = 0.0
        if abs(c1) > 0.25:                     # lệch quá nhiều so với hướng xe chạy -> không phải vạch làn
            return None
        return np.array([c0, c1, c2], dtype=np.float64)

    @staticmethod
    def _centre(left, right) -> float:
        return float((left[0] + right[0]) / 2)

    def _closer_to_prev(self, left, right) -> bool:
        if self.state is None:
            return -left[0] <= right[0]
        return abs(left[0] - self.state.left[0]) <= abs(right[0] - self.state.right[0])
