"""
Kiểm tra nhanh toàn bộ pipeline (không cần giao diện):
  - Kiểm tra IPM: điểm hiệu chỉnh phải ánh xạ đúng về tọa độ mét
  - Kiểm tra ngưỡng theo tốc độ và bộ tư vấn offline
  - Chạy YOLOv11 + khoảng cách trên vài ảnh test, lưu ảnh kết quả vào outputs/smoke/

    python tools/smoke_test.py [thư_mục_ảnh]
"""

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from adas.assistant import offline_advice  # noqa: E402
from adas.config import AppConfig, SafetyPolicy  # noqa: E402
from adas.distance.ipm import GroundPlaneMapper  # noqa: E402
from adas.alert.thresholds import (  # noqa: E402
    ROAD_CONDITIONS, compute_thresholds, condition_policy, legal_min_gap,
    recommended_speed_kmh, stopping_distance_m,
)


def test_ipm(cfg: AppConfig):
    w, h = 1280, 720
    mapper = GroundPlaneMapper(cfg.calibration, (w, h))
    got = mapper.image_to_ground(mapper.src_px)
    assert np.allclose(got, mapper.dst_m, atol=1e-3), (got, mapper.dst_m)
    back = mapper.ground_to_image(got)
    assert np.allclose(back, mapper.src_px, atol=1e-3)
    sky = mapper.image_to_ground(np.array([[w / 2, 5.0]]))
    assert np.isnan(sky).all(), "Điểm trên bầu trời phải không hợp lệ"
    # Khoảng cách tăng dần khi điểm tiến lên phía chân trời
    ys = mapper.image_to_ground(np.array([[w / 2, y] for y in (700, 650, 600, 550)]))[:, 1]
    assert np.all(np.diff(ys) > 0), ys
    print(f"[OK] IPM: chân trời ≈ y={mapper.horizon_y:.0f}px, khoảng cách theo hàng ảnh: "
          + ", ".join(f"{d:.1f}m" for d in ys))


def test_lane(cfg: AppConfig):
    """Ảnh đường tổng hợp: làn hẹp/rộng khác nhau, xe lệch tâm, vạch đứt bên trái + làn bên cạnh."""
    import cv2
    from adas.distance.lane import EgoLaneDetector

    w, h = 1280, 720
    mapper = GroundPlaneMapper(cfg.calibration, (w, h))
    rng = np.random.default_rng(0)

    def paint(img, x0, dashed):
        ys = np.arange(0.0, 80.0, 0.5)
        on = (ys % 15.0) < 6.0 if dashed else np.ones_like(ys, bool)   # vạch đứt 6 m, khoảng hở 9 m
        for y0, y1, o in zip(ys[:-1], ys[1:], on[:-1]):
            if o:
                quad = np.array([[x0 - 0.08, y0], [x0 + 0.08, y0], [x0 + 0.08, y1], [x0 - 0.08, y1]])
                cv2.fillConvexPoly(img, np.round(mapper.ground_to_image(quad) * 16).astype(np.int32),
                                   (235, 235, 235), cv2.LINE_AA, 4)

    for width, centre in ((3.75, 0.0), (3.0, 0.4), (3.5, -0.5)):
        img = np.full((h, w, 3), 95, np.uint8)
        img[: int(mapper.horizon_y) + 2] = (200, 180, 160)                 # bầu trời
        img = np.clip(img + rng.normal(0, 6, img.shape), 0, 255).astype(np.uint8)
        xl, xr = centre - width / 2, centre + width / 2
        paint(img, xl, dashed=True)
        paint(img, xl - width, dashed=False)                               # mép làn bên trái
        paint(img, xr, dashed=False)
        det = EgoLaneDetector(mapper)
        assert det.update(img) is None, "Khung đầu tiên chưa đủ xác nhận làn"
        for _ in range(5):
            lane = det.update(img)
        assert lane is not None and lane.found_left and lane.found_right, lane
        assert abs(lane.width_m - width) < 0.15, (width, lane.width_m)
        assert abs(lane.offset_m + centre) < 0.15, (centre, lane.offset_m)
        assert lane.contains(centre, 30.0) and not lane.contains(xr + 1.0, 30.0)
        print(f"[OK] Làn {width:.2f} m, tim làn lệch {centre:+.1f} m -> đo được {lane.width_m:.2f} m, "
              f"xe lệch {lane.offset_m:+.2f} m")
    blank = np.full((h, w, 3), 95, np.uint8)
    det = EgoLaneDetector(mapper)
    assert all(det.update(blank) is None for _ in range(5)), "Đường không có vạch -> dùng hành lang cố định"


def test_speed(cfg: AppConfig):
    """Video tổng hợp: vạch đứt trôi về phía xe đúng v·Δt -> tốc độ đo được phải khớp v."""
    import cv2
    from adas.distance.lane import EgoLaneDetector
    from adas.distance.ego_speed import EgoSpeedEstimator

    w, h, fps = 1280, 720, 30.0
    mapper = GroundPlaneMapper(cfg.calibration, (w, h))
    rng = np.random.default_rng(1)

    def quad(img, x0, y0, y1):
        q = np.array([[x0 - 0.08, y0], [x0 + 0.08, y0], [x0 + 0.08, y1], [x0 - 0.08, y1]])
        cv2.fillConvexPoly(img, np.round(mapper.ground_to_image(q) * 16).astype(np.int32),
                           (235, 235, 235), cv2.LINE_AA, 4)

    def frame(travel_m):
        img = np.full((h, w, 3), 95, np.uint8)
        img[: int(mapper.horizon_y) + 2] = (200, 180, 160)
        img = np.clip(img + rng.normal(0, 6, img.shape), 0, 255).astype(np.uint8)
        for n in range(-1, 8):                    # vạch đứt 3 m, chu kỳ 12 m, trôi theo quãng đường đã đi
            y0 = n * 12.0 - travel_m % 12.0
            if y0 + 3.0 > 0:
                quad(img, -1.875, max(y0, 0.0), y0 + 3.0)
        quad(img, 1.875, 0.0, 80.0)               # vạch liền: không cho thông tin chuyển động
        return img

    for v in (50.0, 80.0, 110.0):
        lane, sp = EgoLaneDetector(mapper), EgoSpeedEstimator(mapper)
        est = None
        for i in range(45):
            t = i / fps
            img = frame(v / 3.6 * t)
            est = sp.update(img, lane.update(img), t)
        assert est is not None and abs(est - v) / v < 0.03, (v, est)
        print(f"[OK] Tốc độ từ vạch đứt: thật {v:.0f} km/h -> đo được {est:.1f} km/h")
    lane, sp = EgoLaneDetector(mapper), EgoSpeedEstimator(mapper)
    still = frame(0.0)
    for i in range(20):
        est = sp.update(still, lane.update(still), i / fps)
        assert est is None or est < 3, ("Xe đứng yên -> tốc độ ≈ 0", est)


def test_kalman():
    """Xe trước chạy đều 2 s rồi phanh 6 m/s²: Kalman phải bám tốc độ tiếp cận và không trễ quá 0,6 s."""
    from adas.distance.kalman import RATE_STD_REPORT, RangeKalman, measurement_sigma
    rng = np.random.default_rng(0)
    lags, errs = [], []
    for _ in range(50):
        kf, lag = None, None
        for i in range(180):
            t = i / 30
            d_true = 40.0 - (3 * (t - 2) ** 2 if t > 2 else 0.0)
            z = d_true + rng.normal(0, measurement_sigma(d_true))
            if kf is None:
                kf = RangeKalman(z, t, measurement_sigma(z))
            else:
                kf.predict(t)
                kf.update(z, measurement_sigma(z))
            closing = kf.closing_speed if kf.rate_std < RATE_STD_REPORT else None
            if lag is None and t > 2 and closing is not None and closing > 3:
                lag = t - 2.5                       # tiếp cận thật vượt 3 m/s lúc t = 2,5 s
            if 3 < t < 5 and closing is not None:
                errs.append(abs(closing - 6 * (t - 2)))
        lags.append(lag)
    assert all(lag is not None for lag in lags), "Kalman không phát hiện được xe trước phanh"
    assert np.mean(lags) < 0.6 and np.mean(errs) < 2.5, (np.mean(lags), np.mean(errs))
    print(f"[OK] Kalman: phát hiện phanh 6 m/s² sau {np.mean(lags) * 1000:.0f} ms, "
          f"sai số tốc độ tiếp cận {np.mean(errs):.2f} m/s")
    # ngoại lai (một khung nhận nhầm) bị loại, không kéo lệch khoảng cách
    kf = RangeKalman(30.0, 0.0, measurement_sigma(30.0))
    for i in range(1, 30):
        kf.predict(i / 30)
        kf.update(30.0 if i != 15 else 60.0, measurement_sigma(30.0))
    assert abs(kf.distance - 30.0) < 0.5, kf.distance


def test_tracker():
    """Xe tổng hợp trôi ngang và to dần (tiến lại gần): YOLO mỗi 6 khung, bám vết ở giữa sai < 1,5 px."""
    import cv2
    from adas.detection.detector import Detection
    from adas.detection.tracking import TemplateTracker, to_work_gray, work_scale

    rng = np.random.default_rng(3)
    w, h = 1280, 720
    bg = cv2.GaussianBlur(rng.integers(60, 140, (h, w)).astype(np.uint8), (0, 0), 3)
    car = cv2.GaussianBlur(rng.integers(0, 255, (120, 160)).astype(np.uint8), (0, 0), 2)
    tr, errs = TemplateTracker(), []
    for i in range(60):
        t = i / 30
        s = 1.0 + 0.25 * t
        bw, bh = int(round(160 * s)), int(round(120 * s))
        x1, y1 = int(round(640 + 40 * t - bw / 2)), int(round(450 + 30 * t - bh))
        img = bg.copy()
        img[y1:y1 + bh, x1:x1 + bw] = cv2.resize(car, (bw, bh))
        box = np.array([x1, y1, x1 + bw, y1 + bh], float)
        gray = to_work_gray(cv2.cvtColor(img, cv2.COLOR_GRAY2BGR))
        if i % 6 == 0:
            tr.refresh([Detection(box, 0.9, "car", 7)], gray, t, work_scale(w))
        else:
            out = tr.track(gray, t)
            assert len(out) == 1 and out[0].source == "track" and out[0].track_id == 7, out
            errs.append(np.abs(out[0].bbox - box))
    e = np.array(errs)
    assert e.mean() < 1.0 and e[:, 3].max() < 1.5, e.mean(0)
    print(f"[OK] Bám vết so khớp mẫu: sai số hộp trung bình {e.mean():.2f} px, đáy hộp tối đa {e[:, 3].max():.2f} px")
    # YOLO bỏ sót 2 lần liên tiếp -> track bị bỏ (tránh "xe ma")
    tr.refresh([], gray, 2.0, work_scale(w))
    assert tr.tracks, "bỏ sót 1 lần vẫn phải bám tiếp"
    tr.refresh([], gray, 2.2, work_scale(w))
    assert not tr.tracks, "bỏ sót 2 lần liên tiếp phải bỏ track"


def test_thresholds():
    p = SafetyPolicy()
    # Bảng quy định (mặt đường khô ráo) - kiểm tra đúng các mốc biên "trên ... đến ..."
    expected = {59.9: None, 60: 35, 60.1: 55, 80: 55, 80.1: 70, 100: 70, 100.1: 100, 120: 100}
    for v, gap in expected.items():
        assert legal_min_gap(v) == gap, (v, legal_min_gap(v), gap)
    for v in (40, 59, 60, 70, 80, 90, 100, 110, 120):
        t = compute_thresholds(v, p)
        basis = f"quy định {t.legal_m:.0f} m" if t.legal_m is not None else f"ước tính 2 s = {t.gap_m:.1f} m"
        print(f"[OK] {v:>3} km/h khô ráo: cảnh báo < {t.safe_m:5.1f} m, nguy hiểm < {t.danger_m:5.1f} m ({basis})")
    assert compute_thresholds(100, p).safe_m == 70.0
    assert compute_thresholds(130, p).over_speed_limit

    # Ngưỡng tùy chỉnh theo dải tốc độ: chỉ đổi đúng dải đó, không bao giờ thấp hơn luật
    custom = SafetyPolicy(band_gaps_m=[40.0, 30.0, 90.0, 100.0])
    assert compute_thresholds(60, custom).safe_m == 40.0
    assert compute_thresholds(70, custom).safe_m == 55.0          # 30 m < luật 55 m -> giữ 55 m
    assert compute_thresholds(90, custom).safe_m == 90.0
    assert compute_thresholds(110, custom).safe_m == 100.0
    assert compute_thresholds(90, custom).legal_m == 70.0
    assert compute_thresholds(50, custom).band_m is None
    assert compute_thresholds(90, SafetyPolicy(band_gaps_m=[])).safe_m == 70.0   # dữ liệu hỏng -> luật
    rain = condition_policy("heavy_rain", base=custom)
    assert rain.band_gaps_m == custom.band_gaps_m                  # điều kiện đường không xóa ngưỡng dải
    assert abs(compute_thresholds(90, rain).safe_m - 90.0 * 2.0) < 1e-6
    assert offline_advice("trời mưa to", custom, 90).policy.band_gaps_m == custom.band_gaps_m
    print("[OK] Ngưỡng theo dải tốc độ: 80–100 km/h đặt 90 m → cảnh báo < 90 m; đặt dưới luật bị nâng lên")

    # Điều kiện bất lợi: hệ số nhân một lần trên mức quy định (không tính trùng time-gap)
    for key, c in ROAD_CONDITIONS.items():
        t = compute_thresholds(100, condition_policy(key))
        assert abs(t.safe_m - 70.0 * c.factor) < 1e-6, (key, t.safe_m)
        print(f"[OK] 100 km/h · {c.name:<38} ×{c.factor:<4g} → cảnh báo < {t.safe_m:5.1f} m")
    night_rain = condition_policy("heavy_rain", ["night"])
    assert night_rain.weather_factor == 2.4

    # Tầm nhìn: quãng đường dừng tại tốc độ khuyến nghị đúng bằng tầm nhìn
    rec = recommended_speed_kmh(100, 0.6)
    assert abs(stopping_distance_m(rec, 0.6) - 100) < 1e-6
    print(f"[OK] Sương mù, tầm nhìn 100 m → tốc độ khuyến nghị ≤ {rec:.0f} km/h")

    # Trợ lý offline
    r = offline_advice("trời mưa to, tôi chạy 90 km/h", p, 80)
    assert r.speed_kmh == 90 and r.policy.weather_factor == 2.0
    assert abs(compute_thresholds(90, r.policy).safe_m - 140.0) < 1e-6
    print(f"[OK] Offline AI: {r.reply}")
    r = offline_advice("sương mù, tầm nhìn 50 m", p, 80)
    assert r.policy.visibility_m == 50 and r.policy.weather_factor == 1.5
    print(f"[OK] Offline AI: {r.reply}")
    r2 = offline_advice("giờ là ban đêm", r.policy, 80)  # giữ điều kiện sương mù, cộng thêm ban đêm
    assert abs(r2.policy.weather_factor - 1.8) < 1e-9 and r2.policy.visibility_m == 50
    r3 = offline_advice("đường khô ráo trở lại", r2.policy, 80)
    assert r3.policy.weather_factor == 1.0 and r3.policy.visibility_m == 0
    print(f"[OK] Offline AI: {r3.reply}")


def test_alert():
    """Chống nhiễu theo thời gian: nâng mức sau escalate_seconds dù xử lý 30 hay 10 khung/giây."""
    from adas.alert.engine import AlertManager
    from adas.config import AlertConfig
    for fps in (30, 10):
        am = AlertManager(AlertConfig(sound_enabled=False, escalate_seconds=0.1, hold_seconds=0.8))
        t_up = None
        for i in range(fps):
            t = i / fps
            if am.update("danger", t) == "danger" and t_up is None:
                t_up = t
        assert t_up is not None and 0.1 - 1e-6 <= t_up <= 0.1 + 1 / fps, (fps, t_up)
        # một khung nhận nhầm đơn lẻ không bao giờ đủ để nâng mức
        am.reset()
        assert am.update("danger", 5.0) == "safe" and am.update("safe", 5.0 + 1 / fps) == "safe"
        print(f"[OK] Chống nhiễu {fps} khung/s: nâng mức sau {t_up:.2f} s, khung nhầm đơn lẻ bị bỏ qua")


def test_database():
    """CSDL trên file tạm: cấu hình, lịch sử, phiên, vi phạm, view thống kê, xóa dây chuyền."""
    import tempfile
    from dataclasses import asdict
    from adas.storage.database import Database

    with tempfile.TemporaryDirectory() as tmp:
        db = Database(Path(tmp) / "test.db")
        assert db.load_config() is None
        cfg = AppConfig()
        assert db.save_config(asdict(cfg), "Khởi tạo")
        assert not db.save_config(asdict(cfg), "Không đổi")        # không ghi lịch sử trùng
        cfg.policy.weather_factor = 2.0
        assert db.save_config(asdict(cfg), "Mưa to")
        loaded = AppConfig.load(db)
        assert loaded.policy.weather_factor == 2.0 and loaded.calibration.image_points == cfg.calibration.image_points
        assert [r["reason"] for r in db.config_history()] == ["Mưa to", "Khởi tạo"]

        sid = db.start_session("video.mp4", "video", "best.pt", "GPU", 640, 360, asdict(cfg))
        base = dict(session_id=sid, started_at="2026-01-01 00:00:00", level="warning", distance_m=60.0,
                    min_distance_m=60.0, ego_speed_kmh=100.0, safe_threshold_m=70.0, danger_threshold_m=35.0)
        v1 = db.insert_violation(base)
        db.update_violation(v1, {"level": "danger", "min_distance_m": 30.0, "duration_s": 2.5})
        db.insert_violation(base)
        db.end_session(sid, 900, 29.5)
        s = db.list_sessions()[0]
        assert (s["total_violations"], s["danger_count"], s["warning_count"], s["closest_distance_m"]) == (2, 1, 1, 30.0)
        assert len(db.list_violations(sid, "danger")) == 1
        try:
            db.insert_violation({**base, "level": "sai"})           # CHECK ràng buộc mức
            raise AssertionError("CHECK constraint không hoạt động")
        except Exception as e:
            assert "CHECK" in str(e)
        # Tìm kiếm nhật ký theo loại xe / thời gian, xóa từng vi phạm
        v3 = db.insert_violation({**base, "vehicle_class": "truck", "started_at": "2026-03-05 10:00:00"})
        assert [v["id"] for v in db.list_violations(vehicle_class="truck")] == [v3]
        assert [v["id"] for v in db.list_violations(date_from="2026-03-05", date_to="2026-03-05")] == [v3]
        assert db.list_violations(date_from="2026-03-06") == []
        db.delete_violations([v3])
        assert len(db.list_violations()) == 2

        # Nguồn video: đăng ký (chuẩn hóa đường dẫn), hiệu chỉnh riêng, liên kết phiên
        src = db.register_source("C:/x/video.mp4", "video")
        assert db.register_source("C:\\x\\video.mp4", "video") == src   # cùng 1 nguồn
        cid = db.save_calibration(src, asdict(cfg.calibration), (1280, 720), "auto", "thử")
        cal = db.latest_calibration(src)
        assert cal["id"] == cid and cal["method"] == "auto" and len(json.loads(cal["homography_matrix"])) == 3
        assert json.loads(cal["intrinsic_matrix"])[0][0] == cal["focal_px"] > 0
        assert db.list_sources()[0]["calibrations"] == 1 and db.list_calibrations()[0]["active"] == 1
        sid2 = db.start_session("C:/x/video.mp4", "video", "best.pt", "GPU", 640, 360, asdict(cfg), source_id=src)
        assert db.list_sources()[0]["sessions"] == 1
        db.delete_source(src)                                       # phiên vẫn còn, source_id -> NULL
        assert any(s["id"] == sid2 for s in db.list_sessions())

        db.delete_session(sid)
        assert db.list_violations() == []                          # ON DELETE CASCADE

        # Nâng cấp CSDL phiên bản 2 (hiệu chỉnh nằm trong video_sources.calibration_json) -> 3
        import sqlite3
        old = Path(tmp) / "v2.db"
        con = sqlite3.connect(str(old))
        con.executescript(
            "CREATE TABLE video_sources (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, "
            "source_type TEXT NOT NULL, uri TEXT NOT NULL UNIQUE, description TEXT, calibration_json TEXT, "
            "created_at TEXT NOT NULL, last_used_at TEXT);"
            "CREATE TABLE monitoring_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL, "
            "ended_at TEXT, source_id INTEGER, source TEXT NOT NULL, source_type TEXT NOT NULL, model_weights TEXT, "
            "device TEXT, frame_width INTEGER, frame_height INTEGER, frames_processed INTEGER NOT NULL DEFAULT 0, "
            "avg_fps REAL, config_json TEXT NOT NULL); PRAGMA user_version = 2;")
        con.execute("INSERT INTO video_sources(name, source_type, uri, calibration_json, created_at) "
                    "VALUES ('cam', 'video', 'C:\\x\\a.mp4', ?, 'x')", (json.dumps(asdict(cfg.calibration)),))
        con.execute("INSERT INTO monitoring_sessions(started_at, source_id, source, source_type, frame_width, "
                    "frame_height, config_json) VALUES ('x', 1, 'a', 'video', 640, 360, '{}')")
        con.commit()
        con.close()
        db2 = Database(old)
        cal = db2.latest_calibration(1)
        assert cal is not None and cal["method"] == "imported" and cal["frame_width"] == 640
        assert "calibration_json" not in db2.list_sources()[0].keys()

        # Nâng cấp phiên bản 3 -> 4: ràng buộc CHECK của camera_calibrations.method thêm 'pose', 'online'
        from adas.storage.database import SCHEMA
        v3 = Path(tmp) / "v3.db"
        con = sqlite3.connect(str(v3))
        con.executescript(SCHEMA.replace("'imported', 'pose', 'online'", "'imported'") + "PRAGMA user_version = 3;")
        assert "'online'" not in con.execute("SELECT sql FROM sqlite_master WHERE name = 'camera_calibrations'").fetchone()[0]
        con.execute("INSERT INTO camera_calibrations(source_id, created_at, method, frame_width, frame_height, "
                    "homography_matrix, params_json) VALUES (NULL, 'x', 'manual', 640, 360, '[]', '{}')")
        con.commit()
        con.close()
        db3 = Database(v3)
        cid = db3.save_calibration(None, asdict(cfg.calibration), (640, 360), "online", "tự hoàn thiện")
        rows = {r["id"]: r["method"] for r in db3.list_calibrations()}
        assert rows == {1: "manual", cid: "online"} and cid == 2, rows
    print("[OK] CSDL: cấu hình + lịch sử, nguồn, ma trận camera, phiên, vi phạm, view, ràng buộc, "
          "xóa dây chuyền, nâng cấp lược đồ v2→v3→v4")


def test_camera_matrix():
    """Phân rã H -> K, R, chiều cao, góc chúc trên camera giả lập có thông số biết trước."""
    import math
    from adas.config import CalibrationConfig

    def project(X, Y, f, h, d, pitch, w, hh):
        th = math.radians(pitch)
        v = np.array([X, Y + d, -h])
        zc = v @ np.array([0, math.cos(th), -math.sin(th)])
        yc = v @ np.array([0, -math.sin(th), -math.cos(th)])
        return f * X / zc + w / 2, f * yc / zc + hh / 2

    for f, h, d, pitch, w, hh in [(800, 1.3, 2.0, 3.0, 1280, 720), (500, 1.2, 2.0, 0.0, 1280, 720),
                                  (400, 1.5, 1.8, -1.5, 640, 360)]:
        W, d0, L = 3.75, 6.0, 25.0
        pts = [project(x, y, f, h, d, pitch, w, hh) for x, y in
               [(-W / 2, d0), (W / 2, d0), (W / 2, d0 + L), (-W / 2, d0 + L)]]
        c = CalibrationConfig(image_points=[[u / w, v / hh] for u, v in pts], rect_width_m=W,
                              rect_length_m=L, near_distance_m=d0)
        m = GroundPlaneMapper(c, (w, hh)).model
        assert abs(m["focal_px"] - f) < 0.5 and abs(m["camera_height_m"] - h) < 1e-3
        assert abs(m["camera_offset_m"] - d) < 1e-3 and abs(m["pitch_deg"] - pitch) < 0.01
    print("[OK] Ma trận camera: phân rã H tìm lại đúng f, chiều cao, vị trí, góc chúc (3 camera giả lập)")


def test_camera_model():
    """Căn chỉnh theo tư thế: 4 điểm sinh ra phải cho đúng camera (f, chiều cao, đầu xe, góc chúc) và đảo lại được."""
    import copy
    from adas.config import CalibrationConfig
    from adas.distance.camera_model import PoseCamera, calib_from_pose, pose_from_calib

    base = CalibrationConfig()
    for (w, hh), focal_w, height, bumper, vp, roll in [((1280, 720), 0.62, 1.25, 2.0, (0.5, 0.5), 0.0),
                                                        ((640, 360), 0.66, 1.55, 2.1, (0.53, 0.46), 1.5),
                                                        ((1920, 1080), 0.80, 2.3, 0.4, (0.47, 0.55), -2.0)]:
        pose = copy.deepcopy(base.pose)
        pose.focal_w, pose.height_m, pose.bumper_m, pose.roll_deg = focal_w, height, bumper, roll
        pose.vp_x, pose.vp_y = vp
        c = calib_from_pose(pose, (w, hh), base)
        mapper, cam = GroundPlaneMapper(c, (w, hh)), PoseCamera(c.pose, (w, hh))
        m = mapper.model
        assert abs(m["focal_px"] - focal_w * w) < 0.5 and abs(m["camera_height_m"] - height) < 1e-3, m
        assert abs(m["camera_offset_m"] - bumper) < 1e-3 and abs(m["pitch_deg"] - cam.pitch_deg) < 0.01, m
        for u, v in ((0.5 * w, 0.8 * hh), (0.2 * w, 0.95 * hh), (0.7 * w, 0.62 * hh)):
            g = mapper.image_to_ground(np.array([[u, v]]))[0]
            assert np.allclose(g, cam.image_to_ground(u, v), atol=1e-3), (g, cam.image_to_ground(u, v))
        plain = CalibrationConfig(image_points=c.image_points, rect_width_m=c.rect_width_m,
                                  rect_length_m=c.rect_length_m, near_distance_m=c.near_distance_m)
        back = pose_from_calib(plain, (w, hh))
        assert abs(back.vp_x - vp[0]) < 1e-4 and abs(back.vp_y - vp[1]) < 1e-4 and abs(back.roll_deg - roll) < 0.02
        assert abs(back.height_m - height) < 0.01 and abs(back.focal_w - focal_w) < 1e-4, back
    print("[OK] Mô hình camera: tư thế -> 4 điểm -> H đúng f, chiều cao, đầu xe, góc chúc; đảo lại ra đúng tư thế")


def test_auto_init():
    """
    Nguồn chưa có căn chỉnh: tự khởi tạo từ điểm tụ chỉ khi NEED lần đo liên tiếp khớp nhau (bỏ qua lần lệch đơn
    lẻ), giữ cài đặt hành lang / tầm đo của người dùng, và thôi thử khi đường không có vạch kẻ.
    """
    import adas.distance.autocalib as ac
    from adas.config import CalibrationConfig
    from adas.distance.camera_model import AutoInitializer

    W, Hh = 1280, 720
    base = CalibrationConfig(lane_half_width_m=1.6, max_range_m=120.0)
    base.pose.vp_y, base.pose.focal_w, base.pose.focal_source = 0.53, 0.66, "speed"   # căn chỉnh của camera khác
    frame = np.zeros((Hh, W, 3), np.uint8)
    orig = ac.estimate_vanishing_point
    try:
        # 3/5 lần đầu lệch (xe che, chữ sơn trên đường) -> chưa nhận; đa số khớp quanh hàng 478 -> nhận
        seq = iter([(600, 477), (590, 540), (595, 530), (606, 545), (589, 478), (602, 476), (598, 475)])
        ac.estimate_vanishing_point = lambda frames: next(seq)
        init, got, n = AutoInitializer((W, Hh)), None, 0
        while got is None:
            got = init.update(frame, base)
            n += 1
        calib, note = got
        assert init.windows == 7 and n == 7 * AutoInitializer.WINDOW * AutoInitializer.EVERY, (init.windows, n)
        assert abs(calib.pose.vp_y * Hh - 478) < 1 and abs(calib.pose.vp_x * W - 598) < 1, calib.pose
        assert calib.pose.active and calib.pose.focal_source == "fov" and abs(calib.pose.focal_w - 0.66) > 0.05
        assert calib.lane_half_width_m == 1.6 and calib.max_range_m == 120.0 and "478" in note

        def no_lines(frames):
            raise RuntimeError("không có vạch")
        ac.estimate_vanishing_point = no_lines
        init = AutoInitializer((W, Hh))
        for _ in range(AutoInitializer.MAX_WINDOWS * AutoInitializer.WINDOW * AutoInitializer.EVERY):
            assert init.update(frame, base) is None
        assert init.failed
    finally:
        ac.estimate_vanishing_point = orig
    print("[OK] Tự khởi tạo căn chỉnh: chỉ nhận khi 5 lần đo điểm tụ khớp nhau, không mang tiêu cự camera khác")


def test_online_calib():
    """
    Video tổng hợp từ camera có tư thế biết trước (vạch đứt trôi ở 80 km/h). Bắt đầu từ tư thế sai (điểm tụ lệch,
    chiều cao theo loại xe, tiêu cự giả định): tự hoàn thiện phải tìm lại điểm tụ, chiều cao (theo làn 3,75 m) và
    tiêu cự (theo tốc độ người dùng gõ khi video đang chạy). Chạy lại với bản đã hoàn thiện không lưu bản trùng.
    Căn chỉnh 4 điểm thì chỉ kiểm tra, không sửa.
    """
    import copy
    import cv2
    from adas.config import AppConfig, CalibrationConfig, update_inplace
    from adas.distance.camera_model import calib_from_pose
    from adas.pipeline import ADASPipeline

    class NoDetector:
        def detect(self, frame, track=True):
            return []

    w, hh, fps, v_kmh = 1280, 720, 30.0, 80.0
    base = CalibrationConfig()
    truth = copy.deepcopy(base.pose)
    truth.focal_w, truth.height_m, truth.bumper_m, truth.vp_x, truth.vp_y = 0.62, 1.30, 2.0, 0.51, 0.47
    true_map = GroundPlaneMapper(calib_from_pose(truth, (w, hh), base), (w, hh))
    rng = np.random.default_rng(2)

    def quad(img, x0, y0, y1):
        q = np.array([[x0 - 0.08, y0], [x0 + 0.08, y0], [x0 + 0.08, y1], [x0 - 0.08, y1]])
        cv2.fillConvexPoly(img, np.round(true_map.ground_to_image(q) * 16).astype(np.int32),
                           (235, 235, 235), cv2.LINE_AA, 4)

    def frame(t):
        img = np.full((hh, w, 3), 95, np.uint8)
        img[: int(true_map.horizon_y) + 2] = (200, 180, 160)
        img = np.clip(img + rng.normal(0, 6, img.shape), 0, 255).astype(np.uint8)
        travel = v_kmh / 3.6 * t
        for n in range(-1, 8):
            y0 = n * 12.0 - travel % 12.0
            if y0 + 3.0 > 0:
                quad(img, -1.875, max(y0, 0.0), y0 + 3.0)
        quad(img, 1.875, 0.0, 80.0)
        return img

    def run(calib, seconds, typed=None):
        cfg = AppConfig()
        update_inplace(cfg.calibration, calib)
        pipe = ADASPipeline(cfg, NoDetector(), (w, hh))
        statuses = []
        for i in range(int(seconds * fps)):
            if typed and i == int(typed[1] * fps):    # (bắt đầu gõ lúc, bấm Dùng lúc, km/h): video vẫn chạy
                pipe.online_calib.add_reference(typed[0], typed[2])
            r = pipe.process(frame(i / fps), i / fps)
            statuses.append(r.calib)
            if r.calib is not None and r.calib.new_calib is not None:
                update_inplace(cfg.calibration, r.calib.new_calib)
                pipe.update_calibration()
        return cfg.calibration, statuses

    start = copy.deepcopy(truth)
    start.vp_x, start.vp_y, start.height_m, start.focal_w = 0.51 + 12 / w, 0.47 - 9 / hh, 1.45, 0.0
    got, st = run(calib_from_pose(start, (w, hh), base), 7.5, typed=(2.0, 3.5, v_kmh))
    done = [s for s in st if s is not None and s.state == "done"]
    assert done and st[0].state == "collecting" and st[0].ask_speed, [s.message for s in st if s][-1:]
    assert not st[-1].ask_speed and got.pose.focal_source == "speed", (st[-1].message, got.pose.focal_source)
    p = got.pose
    assert p.refined and abs(p.vp_x - truth.vp_x) * w < 2 and abs(p.vp_y - truth.vp_y) * hh < 2, p
    assert abs(p.height_m / truth.height_m - 1) < 0.03 and abs(p.focal_w / truth.focal_w - 1) < 0.05, p
    print(f"[OK] Tự hoàn thiện căn chỉnh: điểm tụ lệch {(p.vp_x - truth.vp_x) * w:+.1f}/{(p.vp_y - truth.vp_y) * hh:+.1f} px, "
          f"chiều cao {p.height_m:.2f} m (thật {truth.height_m}), tiêu cự {p.focal_w * w:.0f} px "
          f"(thật {truth.focal_w * w:.0f}) - {done[0].message}")

    again, st = run(got, 6.0)             # lần chạy sau, camera không đổi: chỉ kiểm tra, không lưu bản trùng
    last = [s for s in st if s is not None][-1]
    assert last.state == "done" and all(s.new_calib is None for s in st if s) and again == got, last
    print(f"[OK] Chạy lại với bản đã tự hoàn thiện không lưu bản trùng: {last.message}")

    plain =CalibrationConfig(image_points=got.image_points, rect_width_m=got.rect_width_m,
                              rect_length_m=got.rect_length_m, near_distance_m=got.near_distance_m)
    kept, st = run(plain, 6.0)
    last = [s for s in st if s is not None][-1]
    assert last.state == "done" and "làn đo được" in last.message and not kept.pose.active, last
    assert kept.image_points == plain.image_points and all(s.new_calib is None for s in st if s)
    print(f"[OK] Căn chỉnh 4 điểm chỉ được kiểm tra, không bị sửa: {last.message}")


def test_pipeline(cfg: AppConfig, image_dir: Path, n: int = 4):
    from adas.detection.detector import VehicleDetector
    from adas.pipeline import ADASPipeline
    from gui.rendering import qimage_to_bgr, render_bev, render_overlay
    from adas.stream.sources import ImageSource
    import cv2
    from PySide6.QtGui import QGuiApplication

    global _QT_APP   # giữ QGuiApplication sống suốt bài kiểm tra (QFont cần nó)
    _QT_APP = QGuiApplication.instance() or QGuiApplication(sys.argv)
    m = cfg.model
    det = VehicleDetector(cfg.resolve_path(m.weights), cfg.resolve_path(m.fallback_weights), m.enabled_classes,
                          m.confidence, m.iou, m.imgsz, m.device)
    print(f"[OK] Mô hình: {det.weights_used} · thiết bị {det.device} · lớp {list(det.names.values())}")

    out_dir = ROOT / "outputs" / "smoke"
    out_dir.mkdir(parents=True, exist_ok=True)
    images = sorted(image_dir.glob("*.jpg"))[:n]
    if not images:
        print(f"[!] Không có ảnh trong {image_dir}")
        return
    pipe = None
    for path in images:
        frame = ImageSource(str(path)).frame
        h, w = frame.shape[:2]
        if pipe is None or pipe.frame_size != (w, h):
            pipe = ADASPipeline(cfg, det, (w, h))
        res = pipe.process(frame, 0.0, track=False)
        overlay = qimage_to_bgr(render_overlay(frame, res, pipe.mapper, cfg, 0.0))
        bev = qimage_to_bgr(render_bev(frame, res, pipe.mapper, cfg, (240, 496)))
        bev = cv2.resize(bev, (int(bev.shape[1] * h / bev.shape[0]), h))
        cv2.imencode(".jpg", np.hstack([overlay, bev]))[1].tofile(str(out_dir / path.name))
        desc = ", ".join(f"{v.det.class_name}:{v.distance_m:.1f}m[{v.method},{v.risk}]"
                         for v in res.vehicles) or "không có xe"
        print(f"[OK] {path.name[:40]}… {res.inference_ms:.0f}ms · {desc}")
    print(f"     Ảnh kết quả: {out_dir}")


if __name__ == "__main__":
    cfg = AppConfig()
    test_ipm(cfg)
    test_lane(cfg)
    test_speed(cfg)
    test_kalman()
    test_tracker()
    test_thresholds()
    test_alert()
    test_camera_matrix()
    test_camera_model()
    test_auto_init()
    test_online_calib()
    test_database()
    default_dir = ROOT.parent / "DEMO" / "Distance Estimation Model.v1i.yolov11" / "test" / "images"
    test_pipeline(cfg, Path(sys.argv[1]) if len(sys.argv) > 1 else default_dir)
