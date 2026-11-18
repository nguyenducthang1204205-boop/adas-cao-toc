"""
Mô hình camera theo tư thế (căn chỉnh đơn giản, kiểu camera hành trình / openpilot).

Camera trên mặt đường phẳng chỉ có vài đại lượng: tiêu cự f, chiều cao h, hướng nhìn (điểm tụ của mặt đường
phía trước trên ảnh, gồm góc chúc và góc lệch ngang), góc nghiêng ngang và khoảng cách tới đầu xe.
Người dùng chỉ nhập h và khoảng cách tới đầu xe (đo bằng thước hoặc chọn loại xe); điểm tụ lấy tự động từ
vạch kẻ đường (autocalib.estimate_vanishing_point khi căn chỉnh, online_calib.py khi chạy).

Từ tư thế, calib_from_pose chiếu một hình chữ nhật trên mặt đường lên ảnh để sinh 4 điểm image_points như
cách căn chỉnh thủ công: GroundPlaneMapper (ipm.py), CSDL và bản Android giữ nguyên cách tính.

Hệ tọa độ camera: x sang phải, y xuống dưới, z theo trục quang học. Tâm ảnh ở giữa khung, pixel vuông
(giống ipm._decompose). Điểm tụ được dùng làm tham số thay cho góc vì đó là thứ đo được trực tiếp trên ảnh:
đổi tiêu cự không làm dịch đường chân trời.
"""

import copy
import math
from typing import Optional, Tuple

import numpy as np

from adas.config import CalibrationConfig, CameraPose
from adas.distance.ipm import GroundPlaneMapper
from adas.formatting import vn

LANE_WIDTH_M = 3.75                           # làn cao tốc Việt Nam

# Giá trị điển hình khi gắn camera giữa kính lái, sau gương chiếu hậu: (nhãn, chiều cao m, tới đầu xe m)
VEHICLE_PRESETS = {
    "car": ("Xe con", 1.25, 2.0),
    "suv": ("SUV / bán tải", 1.55, 2.1),
    "bus": ("Xe khách", 2.30, 0.4),
    "truck": ("Xe tải", 2.20, 0.6),
}


def focal_px(pose: CameraPose, frame_size: Tuple[int, int], vfov_deg: float = 55.0) -> float:
    w, h = frame_size
    if pose.focal_w > 0:
        return pose.focal_w * w
    return (h / 2) / math.tan(math.radians(vfov_deg) / 2)


class PoseCamera:
    """Phép chiếu mặt đường <-> ảnh của một tư thế camera."""

    def __init__(self, pose: CameraPose, frame_size: Tuple[int, int], vfov_deg: float = 55.0):
        self.pose = pose
        self.w, self.h = frame_size
        self.f = focal_px(pose, frame_size, vfov_deg)
        self.cx, self.cy = self.w / 2.0, self.h / 2.0
        self.K = np.array([[self.f, 0, self.cx], [0, self.f, self.cy], [0, 0, 1.0]])
        self.K_inv = np.linalg.inv(self.K)
        self.vp = np.array([pose.vp_x * self.w, pose.vp_y * self.h])

        fwd = self.K_inv @ np.array([self.vp[0], self.vp[1], 1.0])
        fwd /= np.linalg.norm(fwd)
        # đường chân trời: đi qua điểm tụ, nghiêng theo roll; pháp tuyến mặt đường n = Kᵀ·l
        r = math.radians(pose.roll_deg)
        p0 = np.array([self.vp[0], self.vp[1], 1.0])
        line = np.cross(p0, p0 + np.array([math.cos(r), math.sin(r), 0.0]))
        down = self.K.T @ line
        down -= (down @ fwd) * fwd
        down /= np.linalg.norm(down)
        if down[1] < 0:
            down = -down
        self.fwd, self.down = fwd, down
        self.right = np.cross(down, fwd)

    @property
    def pitch_deg(self) -> float:
        """> 0: camera chúc xuống."""
        return math.degrees(math.asin(np.clip(self.down[2], -1, 1)))

    @property
    def yaw_deg(self) -> float:
        """> 0: trục camera lệch sang phải so với hướng xe chạy."""
        return math.degrees(math.atan2(-self.fwd[0], self.fwd[2]))

    def ground_to_image(self, X: float, Y: float) -> np.ndarray:
        P = X * self.right + (Y + self.pose.bumper_m) * self.fwd + self.pose.height_m * self.down
        p = self.K @ P
        return p[:2] / p[2]

    def image_to_ground(self, u: float, v: float) -> Optional[Tuple[float, float]]:
        ray = self.K_inv @ np.array([u, v, 1.0])
        s = ray @ self.down
        if s <= 1e-9:
            return None                       # trên đường chân trời
        P = ray * (self.pose.height_m / s)
        return float(P @ self.right), float(P @ self.fwd - self.pose.bumper_m)

    def horizon_points(self) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        """2 đầu đường chân trời ở mép trái / phải ảnh."""
        k = math.tan(math.radians(self.pose.roll_deg))
        u0, v0 = self.vp
        return (0.0, v0 - k * u0), (float(self.w), v0 + k * (self.w - u0))


def calib_from_pose(pose: CameraPose, frame_size: Tuple[int, int], base: CalibrationConfig) -> CalibrationConfig:
    """Sinh CalibrationConfig (4 điểm của 1 hình chữ nhật trên mặt đường) từ tư thế camera."""
    cam = PoseCamera(pose, frame_size, base.camera_vfov_deg)
    w, h = frame_size
    u0, v0 = cam.vp
    bottom = 0.85 * h
    if not v0 < bottom - 0.05 * h:
        raise ValueError("Đường chân trời quá thấp: hãy kéo lên cao hơn")
    near = cam.image_to_ground(u0, bottom)
    far = cam.image_to_ground(u0, v0 + 0.15 * (bottom - v0))
    if near is None or far is None:
        raise ValueError("Tư thế camera không nhìn thấy mặt đường")
    d0 = max(1.0, math.ceil(near[1] * 10) / 10)
    d1 = max(d0 + 5.0, math.floor(far[1] * 10) / 10)
    # bề rộng hình chữ nhật: 1 làn, thu hẹp nếu cạnh gần tràn khỏi ảnh (H vẫn đúng tuyệt đối)
    W = LANE_WIDTH_M
    for _ in range(4):
        us = [cam.ground_to_image(x, d0)[0] for x in (-W / 2, W / 2)]
        half = max(abs(us[0] - u0), abs(us[1] - u0), 1e-6)
        if min(us) >= 0.02 * w and max(us) <= 0.98 * w:
            break
        W *= min(u0 - 0.02 * w, 0.98 * w - u0) / half * 0.98
    pts = [cam.ground_to_image(x, y) for x, y in ((-W / 2, d0), (W / 2, d0), (W / 2, d1), (-W / 2, d1))]
    out = copy.deepcopy(base)
    out.image_points = [[float(p[0] / w), float(p[1] / h)] for p in pts]
    out.rect_width_m = float(round(W, 3))
    out.rect_length_m = float(round(d1 - d0, 2))
    out.near_distance_m = float(d0)
    out.camera_vfov_deg = float(round(math.degrees(2 * math.atan((h / 2) / cam.f)), 2))
    out.pose = copy.deepcopy(pose)
    out.pose.active = True
    if out.pose.focal_w <= 0:
        out.pose.focal_w = float(cam.f / w)
    return out


def pose_from_calib(calib: CalibrationConfig, frame_size: Tuple[int, int]) -> CameraPose:
    """
    Tư thế gần đúng của một hiệu chỉnh 4 điểm (để mở trình căn chỉnh với giá trị hiện có).
    Chiều cao / khoảng cách đầu xe vô lý (hình thang chấm lệch) thì lấy theo loại xe.
    """
    if calib.pose.active:
        return copy.deepcopy(calib.pose)
    w, h = frame_size
    pose = copy.deepcopy(calib.pose)
    _, ph, pb = VEHICLE_PRESETS.get(pose.vehicle, VEHICLE_PRESETS["car"])
    pose.height_m, pose.bumper_m = ph, pb
    try:
        mapper = GroundPlaneMapper(calib, frame_size)
    except Exception:
        return pose
    vy = mapper.H_inv @ np.array([0.0, 1.0, 0.0])         # điểm tụ của hướng Y (phía trước)
    if abs(vy[2]) > 1e-12:
        u, v = vy[0] / vy[2], vy[1] / vy[2]
        if 0 <= u <= w and 0 <= v <= h:
            pose.vp_x, pose.vp_y = float(u / w), float(v / h)
    vx = mapper.H_inv @ np.array([1.0, 0.0, 0.0])
    a, b, _ = np.cross(vy, vx)
    roll = math.degrees(math.atan2(-a, b))
    roll = roll - 180 if roll > 90 else roll + 180 if roll <= -90 else roll
    pose.roll_deg = float(round(roll, 2)) if abs(roll) < 10 else 0.0
    m = mapper.model
    if m["focal_px"]:
        pose.focal_w, pose.focal_source = float(m["focal_px"] / w), "fov"
    if m["camera_height_m"] and 0.5 <= m["camera_height_m"] <= 4.0:
        pose.height_m = float(round(m["camera_height_m"], 2))
    if m["camera_offset_m"] is not None and 0.3 <= m["camera_offset_m"] <= 4.0:
        pose.bumper_m = float(round(m["camera_offset_m"], 1))
    return pose


def generic_calibration(base: CalibrationConfig) -> CalibrationConfig:
    """Hình học camera mặc định (chưa căn chỉnh), giữ các cài đặt của người dùng: hành lang làn, tầm đo."""
    out = copy.deepcopy(base)
    d = CalibrationConfig()
    out.image_points = copy.deepcopy(d.image_points)
    out.rect_width_m, out.rect_length_m, out.near_distance_m = d.rect_width_m, d.rect_length_m, d.near_distance_m
    out.camera_vfov_deg = d.camera_vfov_deg
    out.pose = CameraPose()
    return out


def auto_initial_calibration(vp: Tuple[float, float], frame_size: Tuple[int, int],
                             base: Optional[CalibrationConfig] = None) -> CalibrationConfig:
    """
    Căn chỉnh khởi đầu từ điểm tụ vp (pixel): như trình 3 bước với giá trị mặc định (xe con, tiêu cự theo góc
    nhìn giả định). Bộ tự hoàn thiện khi chạy (online_calib.py) tinh chỉnh tiếp chân trời và chiều cao theo làn.
    """
    w, h = frame_size
    pose = CameraPose(active=True, vehicle="car", focal_w=0.0, focal_source="fov")
    _, pose.height_m, pose.bumper_m = VEHICLE_PRESETS["car"]
    pose.vp_x, pose.vp_y = float(vp[0] / w), float(vp[1] / h)
    return calib_from_pose(pose, frame_size, generic_calibration(CalibrationConfig() if base is None else base))


class AutoInitializer:
    """
    Tự khởi tạo căn chỉnh cho nguồn chưa có căn chỉnh riêng, không cần người dùng (đúng hướng "không nhập tay").
    Không bao giờ dùng lại căn chỉnh của camera khác: chân trời sai làm IPM, dò làn và đo tốc độ lấy mẫu sai chỗ
    (vd: vùng "mặt đường 5-26 m" nằm trên chân trời thật -> đèn ở xa đứng yên -> tốc độ ~0 km/h).

    Mỗi cửa sổ WINDOW khung (lấy 1 trong EVERY khung) cho 1 điểm tụ (autocalib.estimate_vanishing_point). Một
    cửa sổ đơn lẻ hay lệch (xe che, chữ sơn trên đường: hàng 520-550 thay vì ~475 trên video thử) nên chỉ nhận khi
    NEED lần đo liên tiếp khớp nhau (độ lệch trung vị <= MAD_ROW chiều cao, MAD_COL chiều rộng) và dùng trung vị.
    Thôi sau MAX_WINDOWS cửa sổ (video mở đầu màn đen, đường không vạch kẻ): failed = True.
    """
    EVERY = 2
    WINDOW = 15
    NEED = 5
    MAD_ROW = 0.02
    MAD_COL = 0.03
    MAX_WINDOWS = 90

    def __init__(self, frame_size: Tuple[int, int]):
        self.frame_size = frame_size
        self.frames = []
        self.vps = []
        self.n = 0
        self.windows = 0
        self.failed = False

    def update(self, frame: np.ndarray, base: CalibrationConfig) -> Optional[Tuple[CalibrationConfig, str]]:
        """Trả về (căn chỉnh, ghi chú) ở lần đầu đủ tin cậy, còn lại None."""
        from adas.distance.autocalib import estimate_vanishing_point

        self.n += 1
        if self.failed or self.n % self.EVERY:
            return None
        self.frames.append(frame)
        if len(self.frames) < self.WINDOW:
            return None
        frames, self.frames = self.frames, []
        self.windows += 1
        try:
            self.vps.append(estimate_vanishing_point(frames))
        except Exception:
            pass
        if len(self.vps) >= self.NEED:
            last = np.array(self.vps[-self.NEED:])
            med = np.median(last, axis=0)
            mad = np.median(np.abs(last - med), axis=0)
            w, h = self.frame_size
            if mad[0] <= self.MAD_COL * w and mad[1] <= self.MAD_ROW * h:
                try:
                    calib = auto_initial_calibration((med[0], med[1]), self.frame_size, base)
                except ValueError:          # chân trời quá thấp: tiếp tục đo
                    calib = None
                if calib is not None:
                    note = (f"Tự khởi tạo: chân trời hàng {med[1]:.0f} (trung vị {self.NEED} lần đo từ vạch kẻ), "
                            f"xe con cao {vn(calib.pose.height_m, 2)} m, tiêu cự theo góc nhìn giả định")
                    return calib, note
        if self.windows >= self.MAX_WINDOWS:
            self.failed = True
        return None


def longitudinal_scale(calib: CalibrationConfig, frame_size: Tuple[int, int],
                       rows: Tuple[float, float], u: float) -> Optional[float]:
    """Quãng đường (m) giữa 2 hàng ảnh theo hiệu chỉnh: thang mà phép đo tốc độ từ video nhìn thấy."""
    g = GroundPlaneMapper(calib, frame_size).image_to_ground(np.array([[u, rows[0]], [u, rows[1]]]))
    d = abs(g[0, 1] - g[1, 1])
    return float(d) if np.isfinite(d) and d > 0 else None
