"""Vẽ hình minh họa cho báo cáo phân rã bài toán (PHAN_RA_BAI_TOAN.docx).

Chạy từ thư mục gốc dự án:  python docs/hinh_phan_ra/ve_hinh.py
Số liệu lấy thẳng từ code: GroundPlaneMapper với căn chỉnh mặc định, RangeKalman.
"""
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from adas.config import CalibrationConfig                      # noqa: E402
from adas.distance.ipm import GroundPlaneMapper                # noqa: E402
from adas.distance.kalman import RangeKalman, measurement_sigma  # noqa: E402

OUT = os.path.dirname(os.path.abspath(__file__))
plt.rcParams.update({"font.family": "Times New Roman", "font.size": 12, "axes.unicode_minus": False})


def vn(x, n=1):
    return f"{x:.{n}f}".replace(".", ",")


def hinh_ipm():
    W, H = 640, 360
    calib = CalibrationConfig()
    m = GroundPlaneMapper(calib, (W, H))
    src = m.src_px
    car_bottom = np.array([330.0, 226.0])
    X, Y = m.image_to_ground(car_bottom[None])[0]

    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.6), gridspec_kw={"width_ratios": [1.45, 1]})
    # --- ảnh camera
    a.add_patch(Rectangle((0, 0), W, m.horizon_y, color="#dfe9f5"))
    a.add_patch(Rectangle((0, m.horizon_y), W, H - m.horizon_y, color="#cfcfcf"))
    a.axhline(m.horizon_y, color="#555", ls="--", lw=1)
    a.text(8, m.horizon_y - 6, "đường chân trời", fontsize=11, color="#333")
    a.add_patch(Polygon(src, closed=True, fill=True, fc="#ffe9a8", ec="#c48a00", lw=2))
    for i, (u, v) in enumerate(src):
        a.plot(u, v, "o", color="#c48a00", ms=6)
    # vạch chia khoảng cách trên trục xe: càng xa càng dồn sát chân trời
    marks = (10, 20, 30, 40, 60, 100)
    for k, Yd in enumerate(marks):
        u, v = m.ground_to_image(np.array([[1.9, Yd]]))[0]
        ly = 330 - k * 24
        a.plot([u, 520], [v, ly], color="#666", lw=.7)
        a.plot(u, v, "|", color="#333", ms=6)
        a.text(525, ly + 4, f"{Yd} m  (hàng {v:.0f})", fontsize=10)
    a.add_patch(Rectangle((300, 192), 60, 34, fill=False, ec="#d62728", lw=2))
    a.plot(*car_bottom, "o", color="#d62728", ms=7)
    a.annotate("điểm chạm đất\n(330; 226)", car_bottom, (150, 255), fontsize=11, color="#d62728",
               arrowprops=dict(arrowstyle="->", color="#d62728"))
    a.set_xlim(0, W); a.set_ylim(H, 0); a.set_aspect("equal")
    a.set_title("Ảnh camera (pixel)"); a.set_xticks([0, 320, 640]); a.set_yticks([0, 180, 360])

    # --- mặt đường nhìn từ trên xuống
    Wm, L, d0 = calib.rect_width_m, calib.rect_length_m, calib.near_distance_m
    b.add_patch(Rectangle((-6, 0), 14, 45, color="#cfcfcf"))
    b.add_patch(Rectangle((-Wm / 2, d0), Wm, L, fc="#ffe9a8", ec="#c48a00", lw=2))
    for x in (-Wm / 2, Wm / 2):
        b.plot([x, x], [0, 45], color="white", lw=2)
    b.add_patch(Rectangle((-0.9, -4.5), 1.8, 4.5, fc="#1f77b4", ec="none"))
    b.text(1.3, -2.4, "xe mình", va="center", color="#1f77b4", fontsize=10)
    b.add_patch(Rectangle((X - 0.9, Y), 1.8, 4.5, fill=False, ec="#d62728", lw=2))
    b.plot(X, Y, "o", color="#d62728", ms=7)
    b.annotate("", (X - 1.5, Y), (X - 1.5, 0), arrowprops=dict(arrowstyle="<->", color="#d62728"))
    b.text(X - 1.8, Y / 2, f"Y = {vn(Y)} m", rotation=90, ha="right", va="center", color="#d62728")
    b.text(Wm / 2 + 0.3, d0 + L / 2, "hình chữ nhật\n" + f"{vn(Wm, 2)} m × {int(L)} m", fontsize=10, color="#7a5600")
    b.set_xlim(-6, 8); b.set_ylim(-5, 45); b.set_aspect("equal")
    b.set_xlabel("X (m)"); b.set_ylabel("Y (m) tính từ cản trước")
    b.set_title("Mặt đường nhìn từ trên xuống (mét)")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "h1_ipm.png"), dpi=200)
    plt.close(fig)
    return X, Y


def hinh_kalman():
    """Xe trước cách 40 m, đi cùng tốc độ; từ giây thứ 2 phanh 6 m/s² trong 1,5 s."""
    rng = np.random.default_rng(3)
    dt = 1 / 30
    t = np.arange(0, 5, dt)
    vrel = np.where(t < 2, 0.0, -6.0 * np.minimum(t - 2, 1.5))     # tốc độ thay đổi khoảng cách
    d_true = 40 + np.cumsum(vrel) * dt
    z = d_true + rng.normal(0, 1, len(t)) * np.array([measurement_sigma(d) for d in d_true])

    kf = None
    d_kf, v_kf = [], []
    for ti, zi in zip(t, z):
        s = measurement_sigma(zi)
        if kf is None:
            kf = RangeKalman(zi, ti, s)
        else:
            kf.predict(ti)
            kf.update(zi, s)
        d_kf.append(kf.distance)
        v_kf.append(kf.closing_speed if kf.rate_std < 2.0 else np.nan)
    v_raw = np.r_[np.nan, -np.diff(z) / dt]

    fig, (a, b) = plt.subplots(2, 1, figsize=(10, 6.2), sharex=True)
    a.plot(t, z, ".", color="#9e9e9e", ms=4, label="số đo IPM từng khung")
    a.plot(t, d_true, color="#2ca02c", lw=1.5, ls="--", label="khoảng cách thật")
    a.plot(t, d_kf, color="#d62728", lw=2, label="sau bộ lọc Kalman")
    a.set_ylabel("Khoảng cách (m)"); a.legend(loc="lower left", fontsize=10); a.grid(alpha=.3)
    b.plot(t, v_raw, color="#c8c8c8", lw=.7, label="lấy hiệu 2 khung liên tiếp")
    b.plot(t, -vrel, color="#2ca02c", lw=1.5, ls="--", label="tốc độ tiếp cận thật")
    b.plot(t, v_kf, color="#d62728", lw=2, label="Kalman")
    b.set_ylim(-30, 30); b.set_ylabel("Tốc độ tiếp cận (m/s)"); b.set_xlabel("Thời gian (s)")
    b.legend(loc="upper left", fontsize=10); b.grid(alpha=.3)
    for ax in (a, b):
        ax.axvline(2, color="#555", ls=":", lw=1)
    a.text(2.05, a.get_ylim()[1] - 1.5, "xe trước bắt đầu phanh", fontsize=10, va="top")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "h2_kalman.png"), dpi=200)
    plt.close(fig)
    i = np.searchsorted(t, 3.0)
    return float(np.nanstd(v_raw[: int(2 / dt)])), float(-vrel[i]), float(v_kf[i])


def hinh_toc_do():
    """Dải sáng dọc theo vạch kẻ đứt ở 2 thời điểm cách nhau 0,1 s, xe chạy 80 km/h."""
    Y = np.linspace(5, 26, 400)
    v = 80 / 3.6
    shift = v * 0.1

    def profile(y):
        phase = np.mod(y, 9.0)                       # minh họa: vạch 3 m, khoảng trống 6 m
        return np.where(phase < 3.0, 1.0, 0.15)

    p1 = profile(Y)
    p2 = profile(Y + shift)                          # vạch trôi về phía xe: Y giảm dần
    fig, a = plt.subplots(figsize=(10, 3.0))
    a.plot(Y, p1 + 1.3, color="#1f77b4", lw=2, label="khung trước")
    a.plot(Y, p2, color="#d62728", lw=2, label="0,1 s sau")
    y0 = 9.0 + 0.0
    a.annotate("", (y0 - shift, 1.15), (y0, 1.15), arrowprops=dict(arrowstyle="->", lw=1.5))
    a.text(y0 - shift / 2, 1.18, f"trôi {vn(shift)} m", ha="center", va="bottom", fontsize=11)
    a.set_yticks([]); a.set_xlabel("Khoảng cách dọc theo vạch kẻ, tính từ cản trước (m)")
    a.legend(loc="upper right", fontsize=10, ncol=2); a.set_xlim(5, 26); a.set_ylim(-0.1, 3.0)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "h3_toc_do.png"), dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    print("IPM: X=%.2f Y=%.2f" % hinh_ipm())
    print("Kalman: std hiệu 2 khung=%.1f m/s, tại 3 s thật=%.1f kalman=%.1f" % hinh_kalman())
    hinh_toc_do()
    print("Đã vẽ vào", OUT)
