"""
IPM - Biến đổi phối cảnh ngược (Inverse Perspective Mapping).

Giả thiết mặt đường phẳng. Một hình chữ nhật trên mặt đường có kích thước
thực biết trước (W x L mét) xuất hiện trên ảnh dưới dạng hình thang.
Từ 4 cặp điểm tương ứng ta tính ma trận đồng nhất (homography) H 3x3:

        [X·s, Y·s, s]^T = H · [u, v, 1]^T

trong đó (u, v) là pixel trên ảnh, (X, Y) là tọa độ mặt đường tính bằng mét:
    X: lệch ngang so với trục xe chủ (âm = trái, dương = phải)
    Y: khoảng cách dọc phía trước, tính từ đầu xe chủ

Vì H ánh xạ trực tiếp sang mét nên khoảng cách tới xe phía trước chính là Y
của điểm tiếp xúc mặt đường (điểm giữa cạnh dưới bounding box).
"""

import math
from typing import Tuple

import cv2
import numpy as np

from adas.config import CalibrationConfig


class GroundPlaneMapper:
    def __init__(self, calib: CalibrationConfig, frame_size: Tuple[int, int]):
        self.calib = calib
        self.frame_w, self.frame_h = frame_size

        w, h = self.frame_w, self.frame_h
        self.src_px = np.float32([[x * w, y * h] for x, y in calib.image_points])

        W, L, d0 = calib.rect_width_m, calib.rect_length_m, calib.near_distance_m
        self.dst_m = np.float32([
            [-W / 2, d0],          # dưới-trái
            [W / 2, d0],           # dưới-phải
            [W / 2, d0 + L],       # trên-phải
            [-W / 2, d0 + L],      # trên-trái
        ])

        self.H = cv2.getPerspectiveTransform(self.src_px, self.dst_m)
        self.H_inv = np.linalg.inv(self.H)

        # Dấu của thành phần đồng nhất tại một điểm chắc chắn nằm trên mặt đường.
        # Điểm có dấu ngược lại nằm phía trên đường chân trời -> không hợp lệ.
        ref = self.H @ np.array([w / 2, self.src_px[0, 1], 1.0])
        self._valid_sign = np.sign(ref[2]) or 1.0

        # Hàng pixel của đường chân trời (nơi thành phần đồng nhất = 0) tại giữa ảnh
        h31, h32, h33 = self.H[2]
        self.horizon_y = -(h31 * (w / 2) + h33) / h32 if abs(h32) > 1e-12 else None

        # Ma trận camera (nội tham số K + tư thế) phân rã từ H - dùng cho phương pháp dự phòng
        # và lưu vào CSDL (bảng camera_calibrations)
        self.model = self._decompose()
        self.focal_px = self.model["focal_px"]

    # ------------------------------------------------------------------
    # Ma trận camera
    # ------------------------------------------------------------------

    def _decompose(self) -> dict:
        """
        Phân rã homography mặt đường -> ảnh  G = H⁻¹ ∝ K·[r1 r2 t]  (Zhang, 2000), với giả thiết
        tâm ảnh (cx, cy) ở giữa khung và pixel vuông. r1, r2 là 2 trục của mặt đường trong hệ camera
        nên phải trực chuẩn -> xác định được tiêu cự f, rồi R, t, vị trí camera C = -Rᵀt.
        """
        w, h = self.frame_w, self.frame_h
        cx, cy = w / 2.0, h / 2.0
        G = self.H_inv / self.H_inv[2, 2]
        g = G.copy()
        g[0] -= cx * g[2]
        g[1] -= cy * g[2]
        g1, g2 = g[:, 0], g[:, 1]

        # Ràng buộc ||r1|| = ||r2||; nếu suy biến dùng r1 ⟂ r2
        f2 = -1.0
        den = g2[2] ** 2 - g1[2] ** 2
        if abs(den) > 1e-12:
            f2 = ((g1[0] ** 2 + g1[1] ** 2) - (g2[0] ** 2 + g2[1] ** 2)) / den
        if not f2 > 0 and abs(g1[2] * g2[2]) > 1e-12:
            f2 = -(g1[0] * g2[0] + g1[1] * g2[1]) / (g1[2] * g2[2])
        model = {
            "frame_width": w, "frame_height": h,
            "principal_point": [cx, cy],
            "homography_matrix": self.H.tolist(),       # pixel -> mặt đường (m)
            "horizon_y": float(self.horizon_y) if self.horizon_y is not None else None,
            "focal_px": None, "intrinsic_matrix": None, "rotation_matrix": None,
            "camera_height_m": None, "camera_offset_m": None, "pitch_deg": None,
        }
        if not f2 > 0:
            return model

        f = math.sqrt(f2)
        K = np.array([[f, 0, cx], [0, f, cy], [0, 0, 1.0]])
        B = np.linalg.inv(K) @ G
        lam = 2.0 / (np.linalg.norm(B[:, 0]) + np.linalg.norm(B[:, 1]))
        if (lam * B[:, 2])[2] < 0:          # gốc mặt đường phải nằm trước camera
            lam = -lam
        r1 = lam * B[:, 0] / np.linalg.norm(lam * B[:, 0])
        r2 = lam * B[:, 1] - r1 * (r1 @ (lam * B[:, 1]))
        r2 /= np.linalg.norm(r2)
        R = np.column_stack([r1, r2, np.cross(r1, r2)])
        t = lam * B[:, 2]
        C = -R.T @ t                         # vị trí camera trong hệ mặt đường (X, Y, Z-lên)
        axis = R.T @ np.array([0, 0, 1.0])   # hướng trục quang học
        model.update({
            "focal_px": float(f),
            "intrinsic_matrix": K.tolist(),
            "rotation_matrix": R.tolist(),
            "camera_height_m": float(C[2]),
            "camera_offset_m": float(-C[1]),   # camera nằm sau đầu xe bao nhiêu mét
            "pitch_deg": float(math.degrees(math.asin(np.clip(-axis[2], -1, 1)))),  # > 0: chúc xuống
        })
        return model

    # ------------------------------------------------------------------
    # Ảnh -> mặt đường
    # ------------------------------------------------------------------

    def image_to_ground(self, pts: np.ndarray) -> np.ndarray:
        """
        pts: Nx2 pixel ảnh. Trả về Nx2 (X, Y) mét; NaN cho điểm không hợp lệ
        (trên đường chân trời hoặc ngoài tầm đo).
        """
        pts = np.asarray(pts, dtype=np.float64).reshape(-1, 2)
        homog = np.hstack([pts, np.ones((len(pts), 1))]) @ self.H.T
        s = homog[:, 2]
        out = np.full((len(pts), 2), np.nan)
        ok = (np.sign(s) == self._valid_sign) & (np.abs(s) > 1e-9)
        out[ok] = homog[ok, :2] / s[ok, None]
        too_far = ok & ((out[:, 1] < 0) | (out[:, 1] > self.calib.max_range_m))
        out[too_far] = np.nan
        return out

    def ground_to_image(self, pts_m: np.ndarray) -> np.ndarray:
        """pts_m: Nx2 (X, Y) mét -> Nx2 pixel ảnh."""
        pts_m = np.asarray(pts_m, dtype=np.float64).reshape(-1, 2)
        homog = np.hstack([pts_m, np.ones((len(pts_m), 1))]) @ self.H_inv.T
        return homog[:, :2] / homog[:, 2:3]

    # ------------------------------------------------------------------
    # Bird's-Eye View
    # ------------------------------------------------------------------

    def bev_matrix(self, bev_size: Tuple[int, int], x_half_m: float,
                   y_min_m: float, y_max_m: float) -> np.ndarray:
        """Ma trận ánh xạ mét -> pixel ảnh BEV (Y lớn = lên trên)."""
        bw, bh = bev_size
        sx = bw / (2 * x_half_m)
        sy = bh / (y_max_m - y_min_m)
        return np.array([
            [sx, 0.0, sx * x_half_m],
            [0.0, -sy, sy * y_max_m],
            [0.0, 0.0, 1.0],
        ])

    def warp_to_bev(self, frame: np.ndarray, bev_size: Tuple[int, int],
                    x_half_m: float, y_min_m: float, y_max_m: float) -> np.ndarray:
        """Tạo ảnh nhìn từ trên xuống (Bird's-Eye View) của mặt đường."""
        M = self.bev_matrix(bev_size, x_half_m, y_min_m, y_max_m) @ self.H
        return cv2.warpPerspective(frame, M, bev_size, flags=cv2.INTER_LINEAR,
                                   borderMode=cv2.BORDER_CONSTANT, borderValue=(25, 25, 25))
