"""Vẽ các hình minh họa Chương 1 của quyển đồ án (chạy từ thư mục gốc dự án):
    python docs/quyen_do_an/hinh_c1/ve_hinh_c1.py
Sinh: H1_1_cnn.png (cấu trúc CNN), H1_4_ipm.png (ảnh gốc ↔ ảnh nhìn từ trên xuống),
H1_0_quang_duong_dung.png (như bao_cao_tien_do/.../H1 nhưng ghi "Quy định" thay cho "Thông tư 31").
"""
import json
import os
import sqlite3
import sys

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Polygon
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, ROOT)
OUT = os.path.dirname(os.path.abspath(__file__))
plt.rcParams["font.family"] = "Times New Roman"
plt.rcParams["font.size"] = 12


def ve_cnn():
    fig, ax = plt.subplots(figsize=(12.5, 4.2), dpi=200)
    ax.set_xlim(0, 12.6)
    ax.set_ylim(0, 4.2)
    ax.axis("off")

    def khoi(x, y, w, h, n, dx, mau, nhan, phu):
        for k in range(n - 1, -1, -1):
            ox, oy = x + k * dx, y + k * dx * 0.6
            ax.add_patch(Polygon([[ox, oy], [ox + w, oy], [ox + w, oy + h], [ox, oy + h]], closed=True,
                                 fc=mau, ec="#333333", lw=0.8))
        cx = x + (n - 1) * dx / 2 + w / 2
        ax.text(cx, 0.6, nhan, ha="center", va="center", fontsize=11.5, fontweight="bold")
        ax.text(cx, 0.22, phu, ha="center", va="center", fontsize=10.5, color="#444444")
        return x + (n - 1) * dx + w

    def mui_ten(x0, x1, y=2.35):
        ax.add_patch(FancyArrowPatch((x0 + 0.08, y), (x1 - 0.08, y), arrowstyle="-|>", mutation_scale=14, color="#333333"))

    e = khoi(0.3, 1.3, 1.6, 2.1, 3, 0.07, "#dbe7f5", "Ảnh đầu vào", "640×640×3")
    s = 2.75; mui_ten(e, s)
    e = khoi(s, 1.5, 1.2, 1.7, 6, 0.09, "#f3d9b1", "Tích chập + SiLU", "bản đồ đặc trưng")
    s = e + 0.95; mui_ten(e, s)
    e = khoi(s, 1.75, 0.9, 1.2, 6, 0.08, "#f6e7c8", "Gộp / bước nhảy 2", "giảm độ phân giải")
    s = e + 0.95; mui_ten(e, s)
    e = khoi(s, 1.9, 0.65, 0.9, 9, 0.07, "#f3d9b1", "Tích chập sâu hơn", "đặc trưng trừu tượng")
    s = e + 0.95; mui_ten(e, s)
    # đầu ra: các nơ-ron / đầu dự đoán
    ys = np.linspace(1.4, 3.3, 6)
    for y in ys:
        ax.add_patch(plt.Circle((s + 0.35, y), 0.12, fc="#cfe8d5", ec="#333333", lw=0.8))
    ax.text(s + 0.35, 0.6, "Lớp đầu ra", ha="center", va="center", fontsize=11.5, fontweight="bold")
    ax.text(s + 0.35, 0.22, "lớp + khung bao", ha="center", va="center", fontsize=10.5, color="#444444")
    ax.text(4.2, 3.95, "Trích xuất đặc trưng (backbone)", fontsize=11.5, style="italic", color="#555555")
    ax.plot([2.75, s - 0.9], [3.8, 3.8], color="#888888", lw=0.8)
    fig.savefig(os.path.join(OUT, "H1_1_cnn.png"), bbox_inches="tight", facecolor="white")
    plt.close(fig)


def ve_ipm():
    from adas.config import CalibrationConfig, _from_dict
    from adas.distance.ipm import GroundPlaneMapper

    con = sqlite3.connect(os.path.join(ROOT, "data", "adas.db"))
    row = con.execute("SELECT params_json FROM camera_calibrations WHERE source_id = 1 ORDER BY id DESC LIMIT 1").fetchone()
    calib = _from_dict(CalibrationConfig, json.loads(row[0]))
    cap = cv2.VideoCapture(os.path.expanduser(r"~\Downloads\videoplayback.mp4"))
    cap.set(cv2.CAP_PROP_POS_MSEC, 12000)
    ok, frame = cap.read()
    assert ok, "không đọc được video"
    frame = cv2.resize(frame, (960, 540))
    h, w = frame.shape[:2]
    mp = GroundPlaneMapper(calib, (w, h))

    xh, y0, y1 = 6.0, 4.0, 44.0
    bw, bh = 300, 600
    bev = mp.warp_to_bev(frame, (bw, bh), xh, y0, y1)
    B = mp.bev_matrix((bw, bh), xh, y0, y1)

    img = frame.copy()
    lane = 3.75 / 2
    for yy in (10, 20, 30):
        p = mp.ground_to_image([[-xh, yy], [xh, yy]]).astype(int)
        cv2.line(img, tuple(p[0]), tuple(p[1]), (255, 255, 255), 1, cv2.LINE_AA)
    xl, xr = 2.4 - 3.75, 2.4   # làn xe chủ đo trên ảnh BEV (camera lệch phải ~0,5 m)
    corners = np.array([[xl, y0 + 4], [xr, y0 + 4], [xr, y1], [xl, y1]])
    pi = mp.ground_to_image(corners).astype(np.int32)
    cv2.polylines(img, [pi], True, (40, 140, 255), 2, cv2.LINE_AA)
    pb = (B @ np.hstack([corners, np.ones((4, 1))]).T).T
    pb = (pb[:, :2] / pb[:, 2:3]).astype(np.int32)
    cv2.polylines(bev, [pb], True, (40, 140, 255), 2, cv2.LINE_AA)

    fig, axs = plt.subplots(1, 2, figsize=(11, 4.5), dpi=200, gridspec_kw={"width_ratios": [960 / 540, 0.6], "wspace": 0.22})
    axs[0].imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    axs[0].set_title("a) Ảnh từ camera hành trình (u, v)", fontsize=12)
    axs[1].imshow(cv2.cvtColor(bev, cv2.COLOR_BGR2RGB), extent=[-xh, xh, y0, y1], aspect="auto")
    axs[1].set_title("b) Ảnh nhìn từ trên xuống (X, Y)", fontsize=12)
    axs[1].set_xlabel("X (m)")
    axs[1].set_ylabel("Y (m)")
    axs[1].set_yticks(range(10, 45, 10))
    for yy in range(10, 45, 10):
        axs[1].axhline(yy, color="white", lw=0.6)
    axs[0].axis("off")
    for yy in (10, 20, 30):
        trai = yy == 30
        p = mp.ground_to_image([[-xh if trai else xh, yy]])[0]
        axs[0].text(p[0] + (-6 if trai else 6), p[1], f"Y = {yy} m", color="white", fontsize=9.5,
                     ha="right" if trai else "left", va="center",
                     bbox=dict(fc="black", alpha=0.45, lw=0, pad=1.2))
    fig.savefig(os.path.join(OUT, "H1_4_ipm.png"), bbox_inches="tight", facecolor="white")
    plt.close(fig)


def ve_quang_duong_dung():
    import importlib.util
    from pathlib import Path
    src = os.path.join(ROOT, "docs", "bao_cao_tien_do", "so_do_tong_quan", "nguon", "ve_hinh_ly_thuyet.py")
    code = open(src, encoding="utf-8").read()
    code = code.replace('label="Thông tư 31 (đường khô)"', 'label="Khoảng cách tối thiểu theo quy định (đường khô)"')
    code = code.replace('OUT / "H1_quang_duong_dung.png"', 'OUT / "H1_0_quang_duong_dung.png"')
    ns = {"__file__": src, "__name__": "hinh_ly_thuyet"}
    exec(compile(code, src, "exec"), ns)
    ns["OUT"] = Path(OUT)
    ns["chart_stopping"]()


if __name__ == "__main__":
    ve_quang_duong_dung()
    ve_cnn()
    ve_ipm()
    print("xong")
