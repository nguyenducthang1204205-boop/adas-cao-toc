# -*- coding: utf-8 -*-
"""Hình minh họa lý thuyết cho Chương 1 (matplotlib).

    python ve_hinh_ly_thuyet.py

Sinh vào thư mục cha:
  H1_quang_duong_dung.png   quãng đường dừng xe theo tốc độ và điều kiện đường, so với Thông tư 31
  H2_hinh_hoc_camera.png    hình học camera - mặt đường (nhìn ngang)
  H3_iou.png                minh họa IoU
và in bảng quãng đường dừng xe dùng cho Bảng 1.x.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle, Polygon  # noqa: E402

OUT = Path(__file__).resolve().parent.parent
plt.rcParams.update({"font.family": "Times New Roman", "font.size": 12, "axes.unicode_minus": False})
INK, MUTED, GRID = "#1f1f1f", "#6b6b6b", "#e4e4e0"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"   # bảng màu phân loại đã kiểm tra CVD
G, T_REACT = 9.81, 1.5
CONDS = [("Khô ráo, μ = 0,7", 0.7, BLUE, "-"), ("Ướt, mưa nhỏ, μ = 0,5", 0.5, ORANGE, "--"),
         ("Mưa to, đọng nước, μ = 0,35", 0.35, AQUA, ":")]


def stop(v_kmh, mu):
    v = v_kmh / 3.6
    return v * T_REACT + v * v / (2 * mu * G)


def legal(v):
    for vmax, gap in [(60, 35), (80, 55), (100, 70), (120, 100)]:
        if v <= vmax:
            return gap


def chart_stopping():
    fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=200)
    vs = [40 + i for i in range(81)]
    for name, mu, col, ls in CONDS:
        ys = [stop(v, mu) for v in vs]
        ax.plot(vs, ys, color=col, lw=2, ls=ls, label=name)
        ax.annotate(f"{ys[-1]:.0f} m", (vs[-1], ys[-1]), xytext=(4, 0), textcoords="offset points",
                    va="center", color=INK, fontsize=11)
    sx = [60, 60, 80, 80, 100, 100, 120]
    sy = [35, 55, 55, 70, 70, 100, 100]
    ax.plot(sx, sy, color=MUTED, lw=2, label="Thông tư 31 (đường khô)")
    ax.set_xlim(40, 128)
    ax.set_ylim(0, None)
    ax.set_xlabel("Tốc độ xe (km/h)", color=INK)
    ax.set_ylabel("Quãng đường dừng xe (m)", color=INK)
    ax.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED)
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(OUT / "H1_quang_duong_dung.png", facecolor="white")
    plt.close(fig)


def fig_camera():
    fig, ax = plt.subplots(figsize=(7.6, 3.4), dpi=200)
    ax.set_xlim(-1.2, 15.5)
    ax.set_ylim(-0.9, 3.4)
    ax.axis("off")
    ax.plot([-1.2, 15.5], [0, 0], color=INK, lw=1.5)                       # mặt đường
    ax.text(15.4, -0.3, "mặt đường (Z = 0)", ha="right", fontsize=11, color=MUTED)
    ax.add_patch(Rectangle((-1.1, 0.2), 1.45, 0.95, fc="#eef2f7", ec=INK, lw=1.2))   # xe chủ
    ax.text(-0.38, 0.6, "xe chủ", ha="center", fontsize=11)
    cam = (0.5, 1.4)
    ax.plot(*cam, marker="o", ms=7, color=INK)
    ax.text(0.5, 1.62, "camera", ha="center", fontsize=11)
    ax.annotate("", xy=(0.5, 0), xytext=(0.5, 1.34), arrowprops=dict(arrowstyle="<->", color=MUTED))
    ax.text(0.57, 0.55, "h", fontsize=13, style="italic")
    ax.add_patch(Rectangle((11.2, 0.0), 2.6, 1.4, fc="#f4f8fd", ec=INK, lw=1.2))   # xe phía trước
    ax.text(12.5, 0.62, "xe phía trước", ha="center", fontsize=11)
    gp = (11.2, 0.0)
    ax.plot(*gp, marker="o", ms=6, color=ORANGE)
    ax.text(11.2, -0.5, "điểm tiếp đất\n(đáy khung bao)", ha="center", fontsize=10, color=INK)
    ax.plot([cam[0], gp[0]], [cam[1], gp[1]], color=ORANGE, lw=1.6, ls="--")        # tia tới điểm tiếp đất
    ax.plot([cam[0], 15.3], [cam[1], cam[1] - 0.04], color=MUTED, lw=1, ls=":")      # trục quang học / chân trời
    ax.text(15.3, cam[1] + 0.1, "hướng chân trời (v₀)", ha="right", fontsize=10, color=MUTED)
    ax.annotate("", xy=(gp[0], -0.78), xytext=(0.5, -0.78), arrowprops=dict(arrowstyle="<->", color=INK))
    ax.text((0.5 + gp[0]) / 2, -0.72, "Y - khoảng cách cần đo", ha="center", va="bottom", fontsize=11)
    # mặt phẳng ảnh
    ax.plot([1.3, 1.3], [0.95, 1.85], color=BLUE, lw=2.2)
    ax.text(1.38, 2.0, "mặt phẳng ảnh", fontsize=10, color=BLUE)
    yhit = cam[1] + (gp[1] - cam[1]) * (1.3 - cam[0]) / (gp[0] - cam[0])
    ax.plot(1.3, yhit, marker="o", ms=5, color=BLUE)
    ax.text(1.42, 1.5, "hàng ảnh v", fontsize=10, color=BLUE)
    ax.annotate("", xy=(1.3, 3.05), xytext=(0.5, 3.05), arrowprops=dict(arrowstyle="<->", color=MUTED))
    ax.text(0.9, 3.12, "f", fontsize=13, style="italic", ha="center")
    ax.plot([0.5, 0.5], [1.4, 3.1], color=GRID, lw=0.8)
    ax.plot([1.3, 1.3], [1.85, 3.1], color=GRID, lw=0.8)
    fig.tight_layout()
    fig.savefig(OUT / "H2_hinh_hoc_camera.png", facecolor="white")
    plt.close(fig)


def fig_iou():
    fig, axs = plt.subplots(1, 3, figsize=(7.6, 2.6), dpi=200)
    a, b = (0.15, 0.25, 0.5, 0.5), (0.35, 0.15, 0.5, 0.5)
    titles = ["Khung dự đoán A và khung thật B", "Phần giao của A và B", "Phần hợp của A và B"]
    for k, ax in enumerate(axs):
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 0.9)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.set_title(titles[k], fontsize=11)
        fa = BLUE if k == 2 else "none"
        ax.add_patch(Rectangle(a[:2], a[2], a[3], fc=fa, alpha=0.35 if k == 2 else 1, ec=BLUE, lw=2))
        ax.add_patch(Rectangle(b[:2], b[2], b[3], fc=fa, alpha=0.35 if k == 2 else 1, ec=ORANGE, lw=2, ls="--"))
        if k == 1:
            ax.add_patch(Rectangle((0.35, 0.25), 0.3, 0.4, fc=BLUE, alpha=0.45, ec="none"))
        if k == 0:
            ax.text(0.17, 0.78, "A", color=BLUE, fontsize=12)
            ax.text(0.8, 0.08, "B", color=ORANGE, fontsize=12)
    fig.tight_layout()
    fig.savefig(OUT / "H3_iou.png", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    chart_stopping()
    fig_camera()
    fig_iou()
    for v in (60, 80, 100, 120):
        print(v, legal(v), *[round(stop(v, mu)) for _, mu, _, _ in CONDS])
