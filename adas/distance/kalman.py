"""
Bộ lọc Kalman cho khoảng cách tới một xe phía trước (cùng thiết kế với mobile/android: core/Kalman.kt).

Trạng thái x = [d, ḋ, d̈]: khoảng cách (m), tốc độ thay đổi khoảng cách (m/s, âm = đang tiến lại gần)
và gia tốc tương đối (m/s²). Mô hình gia tốc không đổi, nhiễu quá trình là độ giật (jerk) ngẫu nhiên:
    F = [[1, Δt, Δt²/2], [0, 1, Δt], [0, 0, 1]],   Q = σj²·g·gᵀ,  g = [Δt³/6, Δt²/2, Δt]
Phép đo z = d (IPM) có σ_d = max(0,3 m; 4 %·d) - đo trên videoplayback.mp4: phần dư quanh đường cong
trơn 1 s của từng track là 3,8-4,2 % khoảng cách trong dải 25-100 m.

Chọn bằng mô phỏng (xe trước đang chạy đều ở 40 m rồi phanh 6 m/s², nhiễu đo như trên, 200 lần):
                                 nhiễu khi chạy đều   trễ phát hiện phanh   sai số tiếp cận khi phanh
  cách cũ (EMA + hồi quy 1 s)        0,75 m/s              608 ms                3,5 m/s
  CV (vận tốc không đổi) σa=2        0,41 m/s             1124 ms                6,0 m/s
  CA σj=10 (dùng ở đây)              0,77 m/s              415 ms                1,4 m/s
Mô hình vận tốc không đổi coi cú phanh là nhiễu nên phản ứng chậm; mô hình gia tốc theo kịp.
Tốc độ tiếp cận chỉ được báo khi độ lệch chuẩn của nó < RATE_STD_REPORT (~0,6 s sau khi thấy xe).
"""

import math

SIGMA_JERK = 10.0        # m/s³
SIGMA_D_MIN = 0.3        # m
SIGMA_D_REL = 0.04       # sai số đo IPM ≈ 4 % khoảng cách
RATE_STD_INIT = 8.0      # m/s - chưa biết tốc độ tiếp cận lúc mới thấy xe
ACC_STD_INIT = 1.0       # m/s²
RATE_STD_REPORT = 2.0    # m/s - dưới mức này mới báo tốc độ tiếp cận / TTC
GATE_SIGMA = 5.0         # phép đo lệch dự đoán > 5σ: coi là ngoại lai (nhận nhầm khung)
MAX_OUTLIERS = 3         # ngoại lai liên tiếp -> tin phép đo, khởi tạo lại


def measurement_sigma(d: float, far: bool = False) -> float:
    """Độ lệch chuẩn phép đo khoảng cách. far: ước lượng Pinhole ("Xa") kém tin cậy hơn nhiều."""
    return max(SIGMA_D_MIN, (0.25 if far else SIGMA_D_REL) * d)


class RangeKalman:
    __slots__ = ("x", "P", "t", "outliers")

    def __init__(self, d: float, t: float, sigma: float):
        self.x = [d, 0.0, 0.0]
        self.P = [[sigma * sigma, 0.0, 0.0], [0.0, RATE_STD_INIT ** 2, 0.0], [0.0, 0.0, ACC_STD_INIT ** 2]]
        self.t = t
        self.outliers = 0

    def predict(self, t: float) -> None:
        dt = t - self.t
        if dt <= 0:
            return
        x, P = self.x, self.P
        F = [[1.0, dt, dt * dt / 2], [0.0, 1.0, dt], [0.0, 0.0, 1.0]]
        g = [dt ** 3 / 6, dt * dt / 2, dt]
        q = SIGMA_JERK ** 2
        self.x = [sum(F[i][k] * x[k] for k in range(3)) for i in range(3)]
        FP = [[sum(F[i][k] * P[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
        self.P = [[sum(FP[i][k] * F[j][k] for k in range(3)) + q * g[i] * g[j] for j in range(3)]
                  for i in range(3)]
        self.t = t

    def update(self, z: float, sigma: float) -> bool:
        """Cập nhật với phép đo z (đã predict tới thời điểm đo). False nếu bị loại là ngoại lai."""
        P = self.P
        s = P[0][0] + sigma * sigma
        y = z - self.x[0]
        if y * y > GATE_SIGMA ** 2 * s:
            self.outliers += 1
            if self.outliers < MAX_OUTLIERS:
                return False
            self.__init__(z, self.t, sigma)    # dự đoán sai liên tục (đổi xe, lần đầu đo lệch): làm lại
            return True
        self.outliers = 0
        k = [P[i][0] / s for i in range(3)]
        self.x = [self.x[i] + k[i] * y for i in range(3)]
        self.P = [[P[i][j] - k[i] * P[0][j] for j in range(3)] for i in range(3)]
        return True

    @property
    def distance(self) -> float:
        return self.x[0]

    @property
    def closing_speed(self) -> float:
        """> 0: đang tiến lại gần (m/s)."""
        return -self.x[1]

    @property
    def rate_std(self) -> float:
        return math.sqrt(max(self.P[1][1], 0.0))
