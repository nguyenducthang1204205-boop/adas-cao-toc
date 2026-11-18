"""
Sinh dữ liệu chuẩn cho kiểm thử app Android (mobile/android/app/src/test: CoreTest.kt, AssistantTest.kt) từ bản Python.

    python tools/make_mobile_fixtures.py [--tf-python <python của venv TensorFlow>]

- ipm_python.json: adas.distance.ipm (H, tiêu cự, chân trời, ảnh <-> mặt đường) + adas.alert.thresholds (ngưỡng).
- kalman_python.json: adas.distance.kalman trên kịch bản xe trước phanh 6 m/s² (phép đo có nhiễu cố định).
- assistant_python.json: adas.assistant.offline_advice trên các câu mẫu (AssistantTest.kt).
- tracker_frames.bin + tracker_python.json: adas.detection.tracking trên 8 khung tổng hợp 200x112 (xe trôi + to dần).
- calib_python.json: adas.distance.camera_model (tư thế -> 4 điểm) + adas.distance.online_calib (tự hoàn thiện,
  camera xê dịch, chỉ kiểm tra, chạy lại, thang khoảng cách theo GPS) trên chuỗi quan sát 2 vạch làn tổng hợp.
- egospeed_frames.bin.gz + egospeed_python.json: adas.distance.ego_speed trên 24 khung liên tiếp của video demo
  với 2 vạch thẳng - kiểm EgoSpeed.kt.
- lane_frames.bin.gz + lane_python.json: 4 khung xám 640x360 của video demo (VIDEO_DEMO, nếu có) và điểm tụ do
  bộ dò làn desktop (lane.py) đo được - kiểm bộ dò vạch gọn LaneLines.kt.
- yolo_raw.bin + yolo_expected.json: đầu ra thô của mô hình fp16 app đang dùng trên ảnh test #7 và kết quả
  hậu xử lý tham chiếu (numpy). Cần venv TensorFlow (xem tools/export_mobile.py); bỏ qua nếu không có.
Chạy lại khi đổi thuật toán Python hoặc mô hình.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
ANDROID = ROOT / "mobile" / "android" / "app" / "src"
FX = ANDROID / "test" / "resources" / "fixtures"
MODEL = ANDROID / "main" / "assets" / "models" / "adas_yolo_288x640_fp16.tflite"
TEST_IMAGES = ROOT.parent / "DEMO" / "Distance Estimation Model.v1i.yolov11" / "test" / "images"

YOLO_SNIPPET = r'''
import glob, json, sys
import cv2, numpy as np, tensorflow as tf
model, images, fx = sys.argv[1:4]

def letterbox(img, h, w):
    r = min(h / img.shape[0], w / img.shape[1])
    nh, nw = round(img.shape[0] * r), round(img.shape[1] * r)
    top, left = (h - nh) // 2, (w - nw) // 2
    out = np.full((h, w, 3), 114, np.uint8)
    out[top:top + nh, left:left + nw] = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    return out, r, left, top

def nms(b, s, thr):
    order, keep = s.argsort()[::-1], []
    while order.size:
        i = order[0]; keep.append(i)
        xx1 = np.maximum(b[i, 0], b[order[1:], 0]); yy1 = np.maximum(b[i, 1], b[order[1:], 1])
        xx2 = np.minimum(b[i, 2], b[order[1:], 2]); yy2 = np.minimum(b[i, 3], b[order[1:], 3])
        inter = np.clip(xx2 - xx1, 0, None) * np.clip(yy2 - yy1, 0, None)
        area = lambda q: (q[..., 2] - q[..., 0]) * (q[..., 3] - q[..., 1])
        order = order[1:][inter / (area(b[i]) + area(b[order[1:]]) - inter + 1e-9) <= thr]
    return keep

f = sorted(glob.glob(images + "/*"))[7]
img = cv2.imdecode(np.fromfile(f, np.uint8), 1)
it = tf.lite.Interpreter(model_content=open(model, "rb").read())   # model_path hỏng với đường dẫn Unicode
it.allocate_tensors()
i, o = it.get_input_details()[0], it.get_output_details()[0]
_, h, w, _ = i["shape"]
lb, r, left, top = letterbox(img, h, w)
it.set_tensor(i["index"], (lb[..., ::-1].astype(np.float32) / 255)[None]); it.invoke()
out = it.get_tensor(o["index"])[0].astype("<f4")
open(fx + "/yolo_raw.bin", "wb").write(out.tobytes())
p = out.T
xywh = p[:, :4] * [w, h, w, h]
cls, conf = p[:, 4:].argmax(1), p[:, 4:].max(1)
m = conf > 0.35
xywh, cls, conf = xywh[m], cls[m], conf[m]
b = np.stack([xywh[:, 0] - xywh[:, 2] / 2, xywh[:, 1] - xywh[:, 3] / 2,
              xywh[:, 0] + xywh[:, 2] / 2, xywh[:, 1] + xywh[:, 3] / 2], 1)
k = nms(b + cls[:, None] * 4096.0, conf, 0.45)
b, conf, cls = b[k], conf[k], cls[k]
b[:, [0, 2]] = (b[:, [0, 2]] - left) / r; b[:, [1, 3]] = (b[:, [1, 3]] - top) / r
det = np.concatenate([b, conf[:, None], cls[:, None]], 1)
json.dump({"image": f.replace("\\", "/").split("/")[-1], "src": [img.shape[1], img.shape[0]],
           "input": [int(h), int(w)], "shape": list(out.shape), "detections": det.tolist()}, open(fx + "/yolo_expected.json", "w"), indent=1)
print(f"yolo: {len(det)} hộp trên {f}")
'''


def ipm_fixture():
    from adas.config import CalibrationConfig
    from adas.distance.ipm import GroundPlaneMapper
    from adas.config import SafetyPolicy
    from adas.alert.thresholds import compute_thresholds, condition_policy, threshold_basis

    m = GroundPlaneMapper(CalibrationConfig(), (1280, 720))
    pts = [[640, 650], [500, 600], [800, 470], [640, 446], [640, 300], [100, 700]]
    ground_in = [[0, 10], [-1.875, 20], [1.875, 50]]
    g = m.image_to_ground(np.array(pts, float))
    thr = {}
    for k in ("dry", "heavy_rain"):
        for v in (40, 60, 75, 100, 130):
            t = compute_thresholds(v, condition_policy(k, ["night"] if k == "heavy_rain" else []))
            thr[f"{k}|{v}"] = [round(t.safe_m, 6), round(t.danger_m, 6)]
    # Ngưỡng người dùng đặt theo dải (60 km/h giữ mức luật, dải 80 đặt dưới luật -> bị kẹp lên 55 m)
    user = SafetyPolicy(time_gap_s=2.5, band_gaps_m=[35.0, 40.0, 90.0, 120.0])
    bands = []
    for k in ("dry", "wet"):
        p = condition_policy(k, base=user)
        for v in (30, 59.9, 60, 70, 80.1, 100, 110, 130):
            t = compute_thresholds(v, p)
            bands.append({"cond": k, "v": v, "safe": round(t.safe_m, 6), "danger": round(t.danger_m, 6),
                          "band": t.band_m, "basis": threshold_basis(t, p)})
    data = {"frame": [1280, 720], "H": m.H.tolist(), "focal_px": m.focal_px, "horizon_y": m.horizon_y,
            "image_points": pts, "ground": [None if np.isnan(p[1]) else list(p) for p in g.tolist()],
            "ground_in": ground_in, "image_back": m.ground_to_image(np.array(ground_in, float)).tolist(),
            "thresholds": thr, "band_policy": {"time_gap_s": user.time_gap_s, "band_gaps_m": user.band_gaps_m},
            "bands": bands}
    (FX / "ipm_python.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
    print("ipm: ipm_python.json")


def kalman_fixture():
    from adas.distance.kalman import RATE_STD_REPORT, RangeKalman, measurement_sigma

    rng = np.random.default_rng(0)
    rows, kf = [], None
    for i in range(150):
        t = i / 30
        d = 40.0 - (3 * (t - 2) ** 2 if t > 2 else 0.0)
        z = d + float(rng.normal(0, measurement_sigma(d)))
        if i == 40:
            z += 25.0                                   # một khung nhận nhầm: phải bị loại
        if kf is None:
            kf = RangeKalman(z, t, measurement_sigma(z))
            ok = True
        else:
            kf.predict(t)
            ok = kf.update(z, measurement_sigma(z))
        rows.append({"t": t, "z": z, "accepted": ok, "d": kf.distance, "closing": kf.closing_speed,
                     "rate_std": kf.rate_std, "report": kf.rate_std < RATE_STD_REPORT})
    (FX / "kalman_python.json").write_text(json.dumps(rows, indent=0), encoding="utf-8")
    print("kalman: kalman_python.json")


def tracker_fixture():
    import cv2
    from adas.detection.detector import Detection
    from adas.detection.tracking import TemplateTracker, to_work_gray, work_scale

    rng = np.random.default_rng(5)
    w, h = 200, 112
    bg = cv2.GaussianBlur(rng.integers(60, 140, (h, w)).astype(np.uint8), (0, 0), 1.5)
    car = cv2.GaussianBlur(rng.integers(0, 255, (30, 40)).astype(np.uint8), (0, 0), 1)
    frames, rows, tr = [], [], TemplateTracker()
    for i in range(8):
        t = i / 30
        s = 1.0 + 0.6 * t
        bw, bh = int(round(40 * s)), int(round(30 * s))
        x1, y1 = int(round(90 + 30 * t - bw / 2)), int(round(70 + 20 * t - bh))
        img = bg.copy()
        img[y1:y1 + bh, x1:x1 + bw] = cv2.resize(car, (bw, bh))
        frames.append(img)
        gray = to_work_gray(img)
        if i == 0:
            out = tr.refresh([Detection(np.array([x1, y1, x1 + bw, y1 + bh], float), 0.9, "car", 7)],
                             gray, t, work_scale(w))
        else:
            out = tr.track(gray, t)
        rows.append({"t": t, "true": [x1, y1, x1 + bw, y1 + bh],
                     "boxes": [{"id": d.track_id, "box": [float(v) for v in d.bbox], "source": d.source} for d in out]})
    (FX / "tracker_frames.bin").write_bytes(np.stack(frames).astype(np.uint8).tobytes())
    (FX / "tracker_python.json").write_text(json.dumps({"size": [w, h], "frames": rows}, indent=1), encoding="utf-8")
    print("tracker: tracker_frames.bin + tracker_python.json")


# Câu mẫu cho trợ lý offline: có dấu, không dấu, chữ hoa, dấu rời (bộ gõ tổ hợp), tốc độ, tầm nhìn,
# và các từ dễ trùng khi bỏ dấu (mù/mưa, mệt/mét, tối/tôi, bão/báo).
ASSISTANT_MESSAGES = [
    "trời mưa to", "troi mua to", "Trời đang mưa to, mặt đường đọng nước", "mưa nhỏ, đường ướt",
    "đã tạnh mưa", "da tanh mua", "sương mù tầm nhìn 80 m", "suong mu tam nhin 80 m",
    "Có sương mù dày, tầm nhìn khoảng 100 m", "tầm nhìn chỉ thấy được 50 m", "trời mù quá",
    "đường trơn do dầu loang", "mat duong tron truot", "lái ban đêm, chở nặng", "lai ban dem, cho nang",
    "tôi đang chạy 100 km/h", "toi chay 85", "chạy 130km/h trời mưa", "đi khoảng 50 km/h",
    "tôi mệt quá", "toi met qua", "tối nay có bão", "tôi muốn biết quy định", "xin chào",
    "abc xyz", "Tôi đã lái lâu và cảm thấy buồn ngủ", "Tôi lái xe tải đang chở nặng",
    "Đang lái xe ban đêm trên cao tốc", "Đường khô ráo, trời nắng, tầm nhìn tốt", "giữ cách 30 m",
    "MƯA TO QUÁ", "đường có cát và sỏi", "trời mưa, đêm khuya, tôi buồn ngủ",
    "đặt lại mặc định", "tốc độ 60", "tôi chạy 61 km/h trên đường khô",
]


def assistant_fixture():
    """adas.assistant.offline_advice: câu trả lời + chính sách mới, để app mobile trả lời giống hệt."""
    import unicodedata
    from dataclasses import replace

    from adas.assistant import offline_advice
    from adas.config import SafetyPolicy
    from adas.alert.thresholds import condition_policy

    messages = ASSISTANT_MESSAGES + [unicodedata.normalize("NFD", m) for m in ("trời mưa to, sương mù", "tôi mệt mỏi")]
    bases = {
        "default": SafetyPolicy(),
        "rain_bands": condition_policy("heavy_rain", ["night"],
                                       base=replace(SafetyPolicy(), band_gaps_m=[40.0, 80.0, 90.0, 120.0],
                                                    time_gap_s=3.0)),
        "fog": condition_policy("fog", [], 120.0),
    }

    def pol(p):
        return {"time_gap_s": p.time_gap_s, "band_gaps_m": list(p.band_gaps_m), "weather_factor": p.weather_factor,
                "danger_ratio": p.danger_ratio, "min_distance_m": p.min_distance_m,
                "ttc_warning_s": p.ttc_warning_s, "ttc_danger_s": p.ttc_danger_s, "condition": p.condition,
                "road_mu": p.road_mu, "visibility_m": p.visibility_m}

    cases = []
    for name, base in bases.items():
        for speed in (50.0, 90.0, 125.0):
            for m in messages:
                r = offline_advice(m, base, speed)
                cases.append({"message": m, "base": name, "speed": speed, "reply": r.reply,
                              "speed_out": r.speed_kmh, "policy": pol(r.policy)})
    (FX / "assistant_python.json").write_text(
        json.dumps({"bases": {k: pol(v) for k, v in bases.items()}, "cases": cases}, ensure_ascii=False, indent=0),
        encoding="utf-8")
    print(f"assistant: assistant_python.json ({len(cases)} câu)")


VIDEO_DEMO = Path.home() / "Downloads" / "videoplayback.mp4"


def _obs_json(o):
    return None if o is None else {"left": np.asarray(o.left).tolist(), "right": np.asarray(o.right).tolist(),
                                   "straight": bool(o.straight)}


def calib_fixture():
    """Mô hình camera theo tư thế + tự hoàn thiện căn chỉnh (CoreTest.calibrationMatchesPython)."""
    import copy
    from dataclasses import asdict
    from adas.config import CalibrationConfig, _from_dict
    from adas.distance.camera_model import PoseCamera, calib_from_pose, longitudinal_scale
    from adas.distance.ipm import GroundPlaneMapper
    from adas.distance.online_calib import LaneObservation, OnlineCalibrator, Y_FAR, Y_NEAR

    W, H = 1280, 720
    base = CalibrationConfig()
    poses = []
    for focal_w, height, bumper, vp, roll, measured in [(0.62, 1.25, 2.0, (0.5, 0.5), 0.0, False),
                                                        (0.66, 1.55, 2.1, (0.53, 0.46), 1.5, True),
                                                        (0.80, 2.3, 0.4, (0.47, 0.55), -2.0, False)]:
        pose = copy.deepcopy(base.pose)
        pose.focal_w, pose.height_m, pose.bumper_m, pose.roll_deg = focal_w, height, bumper, roll
        pose.vp_x, pose.vp_y = vp
        pose.height_measured, pose.focal_source = measured, "camera"
        c = calib_from_pose(pose, (W, H), base)
        cam = PoseCamera(c.pose, (W, H))
        probe = [[0.0, 10.0], [-1.875, 25.0], [3.0, 60.0]]
        poses.append({"pose": asdict(pose), "calib": asdict(c), "pitch_deg": cam.pitch_deg,
                      "probe": probe, "image": [cam.ground_to_image(x, y).tolist() for x, y in probe]})

    # Chuỗi quan sát: camera thật (truth) khác tư thế ban đầu; 15 lần/giây như Android; có khung không thấy vạch,
    # đoạn cong (cột điểm tụ lệch); từ t = 12 s camera bị chúc xuống thêm 14 px (xê dịch)
    truth = copy.deepcopy(base.pose)
    truth.focal_w, truth.height_m, truth.bumper_m, truth.vp_x, truth.vp_y = 0.62, 1.30, 2.0, 0.51, 0.47
    truth.focal_source = "camera"
    rng = np.random.default_rng(5)

    def observe(pose, t):
        if rng.random() < 0.15:
            return None
        cam = PoseCamera(pose, (W, H))
        curved = 4.0 <= t % 9.0 < 5.5
        bend = 0.004 if curved else 0.0               # độ cong (1/m): đoạn cong đẩy dây cung sang ngang
        lines = []
        for x0 in (-1.875 + 0.1 * np.sin(t), 1.875 + 0.1 * np.sin(t)):
            pts = [cam.ground_to_image(x0 + bend * y * y, y) + rng.normal(0, 0.6, 2) for y in (Y_NEAR, Y_FAR)]
            lines.append(np.array(pts))
        return LaneObservation(lines[0], lines[1], not curved)

    shifted = copy.deepcopy(truth)
    shifted.vp_y += 14 / H

    def run(start_calib, samples_needed, seconds, drift_at=None, speed_fn=None, gps_fn=None):
        cal = OnlineCalibrator((W, H), samples_needed)
        calib = start_calib
        mapper = GroundPlaneMapper(calib, (W, H))
        steps = []
        for i in range(int(seconds * 15)):
            t = i / 15
            obs = observe(truth if drift_at is None or t < drift_at else shifted, t)
            speed = speed_fn(t, calib) if speed_fn else None
            gps = gps_fn(t) if gps_fn else None
            st = cal.update_obs(obs, mapper, calib, t, speed, gps)
            step = {"t": t, "obs": _obs_json(obs), "speed": speed, "gps": gps, "state": st.state,
                    "progress": st.progress, "message": st.message, "ok": st.ok, "new": None}
            if st.new_calib is not None:
                step["new"] = asdict(st.new_calib)
                calib = st.new_calib
                mapper = GroundPlaneMapper(calib, (W, H))
                cal.calibration_changed(calib)
            steps.append(step)
        return steps

    start = copy.deepcopy(truth)
    start.vp_x, start.vp_y, start.height_m = 0.51 + 12 / W, 0.47 - 9 / H, 1.45
    refine = run(calib_from_pose(start, (W, H), base), 60, 26.0, drift_at=12.0)
    plain_src = calib_from_pose(truth, (W, H), base)
    plain = CalibrationConfig(image_points=plain_src.image_points, rect_width_m=plain_src.rect_width_m,
                              rect_length_m=plain_src.rect_length_m, near_distance_m=plain_src.near_distance_m)
    check = run(plain, 60, 8.0)
    # lần chạy sau với bản đã tự hoàn thiện, camera không đổi: chỉ báo kiểm tra, không đề xuất bản mới
    refined = _from_dict(CalibrationConfig, next(s["new"] for s in refine if s["new"]))
    rerun = run(refined, 60, 8.0)
    assert not any(s["new"] for s in rerun), "chạy lại không được lưu bản trùng"

    # Thang khoảng cách theo GPS: tiêu cự ban đầu sai 10 % (vd ảnh bị cắt để chống rung), tốc độ đo từ vạch kẻ tỷ
    # lệ với thang của hiệu chỉnh đang dùng (nhiễu 2 %, đôi khi mất); GPS làm tròn, 1 lần/giây, trễ 1 s
    truth_cal = calib_from_pose(truth, (W, H), base)
    gps_start = copy.deepcopy(truth)
    gps_start.focal_w, gps_start.height_m, gps_start.vp_y = truth.focal_w * 0.9, 1.25, truth.vp_y - 6 / H
    gps_start = calib_from_pose(gps_start, (W, H), base)
    pa, pb = GroundPlaneMapper(gps_start, (W, H)).ground_to_image(np.array([[0.0, 8.0], [0.0, 22.0]]))
    rows = ((pa[1], pb[1]), pa[0])            # = hàng cố định bộ tự hoàn thiện chọn ở lần đo đầu
    s_true = longitudinal_scale(truth_cal, (W, H), *rows)

    def v_true(t):
        return 80 + 4 * np.sin(t / 6)

    def speed_fn(t, calib):
        if rng.random() < 0.1:
            return None
        return float(round(v_true(t) * longitudinal_scale(calib, (W, H), *rows) / s_true * (1 + rng.normal(0, 0.02))))

    def gps_fn(t):
        return float(round(v_true(max(np.floor(t) - 1.0, 0.0))))

    gps_steps = run(gps_start, 60, 40.0, speed_fn=speed_fn, gps_fn=gps_fn)
    final = _from_dict(CalibrationConfig, [s["new"] for s in gps_steps if s["new"]][-1])
    gps_err = longitudinal_scale(final, (W, H), *rows) / s_true - 1
    assert any("GPS" in s["message"] for s in gps_steps if s["new"]) and abs(gps_err) < 0.015, gps_err
    data = {"frame": [W, H], "poses": poses,
            "scenarios": [{"name": "refine", "samples_needed": 60, "start": asdict(calib_from_pose(start, (W, H), base)),
                           "steps": refine},
                          {"name": "check", "samples_needed": 60, "start": asdict(plain), "steps": check},
                          {"name": "rerun", "samples_needed": 60, "start": asdict(refined), "steps": rerun},
                          {"name": "gps", "samples_needed": 60, "start": asdict(gps_start), "steps": gps_steps}]}
    (FX / "calib_python.json").write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding="utf-8")
    news = [s["t"] for s in refine if s["new"]]
    print(f"calib: calib_python.json (tự hoàn thiện lúc t = {news}, kiểm tra: {check[-1]['message']}, "
          f"chạy lại: {rerun[-1]['message']}, GPS: {[(round(s['t'], 1), s['message']) for s in gps_steps if s['new']]}"
          f" -> thang lệch {gps_err * 100:+.2f} %)")


def lane_fixture():
    """4 khung xám của video demo + điểm tụ do bộ dò làn desktop đo (CoreTest.laneLinesFindDemoVanishingPoint)."""
    import copy
    import gzip
    import cv2
    from dataclasses import asdict
    from adas.config import CalibrationConfig
    from adas.distance.camera_model import calib_from_pose
    from adas.distance.ipm import GroundPlaneMapper
    from adas.distance.lane import EgoLaneDetector
    from adas.distance.online_calib import _intersect, observation_from_lane

    if not VIDEO_DEMO.exists():
        print(f"Bỏ qua fixture làn: không thấy {VIDEO_DEMO}")
        return
    # Hiệu chỉnh ban đầu kiểu Android: điểm tụ gần đúng (cảm biến), tiêu cự đúng (Camera2), chiều cao theo loại xe
    pose = copy.deepcopy(CalibrationConfig().pose)
    pose.vp_x, pose.vp_y, pose.focal_w, pose.height_m, pose.focal_source = 326 / 640, 192 / 360, 0.655, 1.25, "camera"
    calib = calib_from_pose(pose, (640, 360), CalibrationConfig())
    det = EgoLaneDetector(GroundPlaneMapper(calib, (640, 360)))
    mapper = det.mapper
    cap = cv2.VideoCapture(str(VIDEO_DEMO))
    want = {90, 450, 1020, 1350}
    frames, rows = [], []
    for i in range(max(want) + 1):
        ok, fr = cap.read()
        if not ok:
            break
        obs = observation_from_lane(det.update(fr, []), mapper)
        if i in want and obs is not None:
            frames.append(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY))
            rows.append({"frame": i, "vp": list(_intersect(obs.left, obs.right)), "straight": bool(obs.straight)})
    cap.release()
    (FX / "lane_frames.bin.gz").write_bytes(gzip.compress(np.stack(frames).astype(np.uint8).tobytes(), 9))
    (FX / "lane_python.json").write_text(json.dumps({"size": [640, 360], "calib": asdict(calib), "frames": rows},
                                                    ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"lane: lane_frames.bin.gz ({len(frames)} khung) + lane_python.json")


def egospeed_fixture():
    """
    Tốc độ đo từ vạch kẻ (adas/distance/ego_speed.py) trên 24 khung liên tiếp ở 15 Hz của video demo, với 2 vạch
    thẳng như LaneLines.kt đưa ra (CalibTest.egoSpeedMatchesPython). Ngoài dải mặt đường được đo thì xóa đen cho
    tệp nhỏ.
    """
    import copy
    import gzip
    import cv2
    from dataclasses import asdict
    from adas.config import CalibrationConfig
    from adas.distance.camera_model import calib_from_pose
    from adas.distance.ego_speed import EgoSpeedEstimator
    from adas.distance.ipm import GroundPlaneMapper
    from adas.distance.lane import EgoLaneDetector, LaneEstimate
    from adas.distance.online_calib import observation_from_lane

    if not VIDEO_DEMO.exists():
        print(f"Bỏ qua fixture tốc độ vạch kẻ: không thấy {VIDEO_DEMO}")
        return
    pose = copy.deepcopy(CalibrationConfig().pose)
    pose.vp_x, pose.vp_y, pose.focal_w, pose.height_m, pose.focal_source = 326 / 640, 190 / 360, 0.655, 1.17, "camera"
    calib = calib_from_pose(pose, (640, 360), CalibrationConfig())
    mapper = GroundPlaneMapper(calib, (640, 360))
    det = EgoLaneDetector(mapper)
    est = EgoSpeedEstimator(mapper)
    first, count = 420, 24
    rows, cols = slice(195, 300), slice(150, 490)
    cap = cv2.VideoCapture(str(VIDEO_DEMO))
    frames, steps = [], []
    for i in range(first + 2 * count):
        ok, fr = cap.read()
        if not ok:
            break
        obs = observation_from_lane(det.update(fr, []), mapper)
        if i < first or (i - first) % 2:
            continue
        gray = np.zeros((360, 640), np.uint8)       # chỉ giữ dải mặt đường Y 5-26 m quanh làn xe chủ
        gray[rows, cols] = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)[rows, cols]
        lane = None
        if obs is not None:      # 2 vạch thẳng trên mặt đường qua 2 điểm ảnh của mỗi vạch
            coef = []
            for line in (obs.left, obs.right):
                g = mapper.image_to_ground(np.asarray(line, float))
                c1 = (g[1, 0] - g[0, 0]) / (g[1, 1] - g[0, 1])
                coef.append(np.array([g[0, 0] - c1 * g[0, 1], c1, 0.0]))
            lane = LaneEstimate(coef[0], coef[1], True, True)
        t = (i - first) / 30.0
        shown = est.update(gray, lane, t)
        frames.append(gray)
        steps.append({"t": t, "obs": _obs_json(obs), "shown": shown, "value": est.value})
    cap.release()
    (FX / "egospeed_frames.bin.gz").write_bytes(gzip.compress(np.stack(frames).astype(np.uint8).tobytes(), 9))
    (FX / "egospeed_python.json").write_text(json.dumps({"size": [640, 360], "calib": asdict(calib), "steps": steps},
                                                        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"egospeed: {len(frames)} khung, tốc độ {[s['shown'] for s in steps]}")


def main():
    from export_mobile import DEFAULT_TF_PY
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tf-python", default=str(DEFAULT_TF_PY))
    args = ap.parse_args()
    FX.mkdir(parents=True, exist_ok=True)
    ipm_fixture()
    kalman_fixture()
    tracker_fixture()
    assistant_fixture()
    calib_fixture()
    lane_fixture()
    egospeed_fixture()
    if not Path(args.tf_python).exists():
        print(f"Bỏ qua fixture YOLO: không thấy {args.tf_python}")
        return
    subprocess.run([args.tf_python, "-c", YOLO_SNIPPET, str(MODEL), str(TEST_IMAGES), str(FX)], check=True,
                   env={**__import__("os").environ, "TF_CPP_MIN_LOG_LEVEL": "3", "PYTHONIOENCODING": "utf-8"})


if __name__ == "__main__":
    main()
