"""
Luồng xử lý nền: đọc khung -> pipeline ADAS -> vẽ -> gửi lên giao diện.
Giao diện không bao giờ bị treo vì mọi tính toán nặng chạy ở đây.
"""

import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from adas.alert.violations import ViolationRecorder
from adas.config import AppConfig
from adas.detection.detector import VehicleDetector
from adas.distance.camera_model import AutoInitializer
from adas.pipeline import ADASPipeline
from adas.storage.database import Database
from adas.stream.sources import VideoFileSource, classify_source, open_source
from gui.rendering import qimage_to_bgr, render_bev, render_overlay, vehicle_label


class ProcessingWorker(QThread):
    frame_ready = Signal(QImage, QImage, dict)   # khung đã vẽ, BEV, thống kê
    violation = Signal(dict)                     # vi phạm mở / cập nhật / đóng (đã ghi CSDL)
    session_started = Signal(int)
    status = Signal(str)
    failed = Signal(str)
    progress = Signal(int, int, float)           # khung hiện tại, tổng số khung, fps của video
    calibration_refined = Signal(object, str)    # căn chỉnh tự hoàn thiện khi chạy (CalibrationConfig, ghi chú)
    calibration_initialized = Signal(object, str)  # nguồn chưa có căn chỉnh: tự khởi tạo từ vạch kẻ

    def __init__(self, cfg: AppConfig, source_spec: str, record: bool = False,
                 source_id: Optional[int] = None, auto_init: bool = False):
        super().__init__()
        self.cfg = cfg
        self.source_spec = source_spec
        self.source_id = source_id   # nguồn trong bảng video_sources (liên kết phiên -> nguồn)
        self.auto_init = auto_init   # nguồn chưa có căn chỉnh riêng: tự khởi tạo (camera_model.auto_initial_calibration)
        self.record = record
        self.last_frame = None       # khung gốc gần nhất (dùng cho hiệu chỉnh IPM)
        self.pipeline: Optional[ADASPipeline] = None
        self._running = True
        self._paused = False
        self._calib_dirty = False
        self._classes_dirty = False
        self._speed_refs = []        # tốc độ nhập khi video đang chạy, chờ luồng xử lý lấy
        self._video_file = False
        self.output_path: Optional[Path] = None

    # --- Điều khiển từ luồng giao diện ---
    def stop(self):
        self._running = False

    def set_paused(self, paused: bool):
        self._paused = paused

    def calibration_changed(self):
        self._calib_dirty = True

    def classes_changed(self):
        self._classes_dirty = True

    def speed_reference(self, t_video: float, kmh: float):
        """Tốc độ người dùng đọc trên video lúc t_video (giây video): áp dụng ở khung kế tiếp."""
        self._speed_refs.append((t_video, kmh))

    # ------------------------------------------------------------------

    def run(self):
        try:
            self._run()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.failed.emit(f"{type(e).__name__}: {e}")

    def _run(self):
        cfg = self.cfg
        self.status.emit("Đang mở nguồn video…")
        source = open_source(self.source_spec, realtime=cfg.realtime_playback)
        self._video_file = isinstance(source, VideoFileSource)   # chỉ video mới có tốc độ in trên hình để nhập

        self.status.emit("Đang tải mô hình YOLOv11…")
        m = cfg.model
        detector = VehicleDetector(
            weights=cfg.resolve_path(m.weights), fallback_weights=cfg.resolve_path(m.fallback_weights),
            enabled_classes=m.enabled_classes, confidence=m.confidence, iou=m.iou,
            imgsz=m.imgsz, device=m.device)
        detector.warmup()

        ok, frame, t = source.read()
        if not ok:
            raise IOError("Nguồn video không có khung hình nào")
        h, w = frame.shape[:2]
        self.pipeline = ADASPipeline(cfg, detector, (w, h))
        self.status.emit(
            f"Đang giám sát: {source.name} · {w}x{h} · mô hình {Path(detector.weights_used).name} "
            f"({'GPU' if detector.device != 'cpu' else 'CPU'})"
            + ("" if self.pipeline.alert.audio_available else " · không có thiết bị âm thanh"))

        # Mở phiên giám sát trong CSDL (lưu kèm cấu hình tại thời điểm chạy để truy vết)
        db = Database()
        session_id = db.start_session(
            source=self.source_spec, source_type=classify_source(self.source_spec),
            model_weights=Path(detector.weights_used).name,
            device="GPU" if detector.device != "cpu" else "CPU",
            frame_width=w, frame_height=h, config=asdict(cfg), source_id=self.source_id)
        recorder = ViolationRecorder(db, session_id, lambda: cfg.policy.weather_factor)
        self.session_started.emit(session_id)

        writer = self._open_writer(source, w, h) if self.record else None
        if isinstance(source, VideoFileSource):
            source.restart_clock()

        fps, fps_n, fps_t0 = 0.0, 0, time.perf_counter()
        n_frames, wall_t0 = 0, time.perf_counter()
        # Nguồn chưa có căn chỉnh riêng: tự tìm chân trời trên các khung đầu (camera_model.AutoInitializer).
        # Trong lúc chờ, phép chiếu chỉ là mặc định -> chưa ghi vi phạm vào CSDL.
        auto = AutoInitializer((w, h)) if self.auto_init and not source.is_image else None
        auto_pending = auto is not None
        try:
            while self._running and ok:
                self.last_frame = frame
                if self._calib_dirty:
                    self.pipeline.update_calibration()
                    self._calib_dirty = False
                    if auto is None:
                        auto_pending = False
                if self._classes_dirty:
                    detector.set_enabled_classes(cfg.model.enabled_classes)
                    self._classes_dirty = False
                while self._speed_refs:
                    self.pipeline.online_calib.add_reference(*self._speed_refs.pop(0))
                if auto is not None:
                    found = auto.update(frame, cfg.calibration)
                    if found is not None:
                        auto = None                 # chờ giao diện áp dụng + lưu rồi gọi calibration_changed
                        self.calibration_initialized.emit(*found)
                    elif auto.failed:
                        auto, auto_pending = None, False
                        self.status.emit("Không tự tìm được đường chân trời (không thấy rõ vạch kẻ): "
                                         "khoảng cách chỉ là ước lượng, hãy bấm Căn chỉnh camera.")

                # [Video Stream] -> [YOLOv11] -> [IPM] -> [Alert Engine]  (adas/pipeline.py)
                result = self.pipeline.process(frame, t, track=not source.is_image)
                result.timings_ms["stream"] = source.last_decode_ms
                if source.is_image:  # ảnh đơn: không có chuỗi khung để chống nhiễu
                    result.level = result.raw_level

                # Alert Engine - ghi nhật ký vi phạm vào CSDL
                t_log = time.perf_counter()
                events = [] if auto_pending else recorder.update(
                    result, t, result.speed_kmh, cfg.policy.condition,
                    lambda path: self._save_snapshot(
                        render_overlay(frame, result, self.pipeline.mapper, cfg, fps, info=True), path))
                result.timings_ms["alert"] += (time.perf_counter() - t_log) * 1000

                fps_n += 1
                now = time.perf_counter()
                if now - fps_t0 >= 0.5:
                    fps, fps_n, fps_t0 = fps_n / (now - fps_t0), 0, now

                # [GUI] vẽ lớp phủ + Bird's-Eye View rồi gửi sang luồng giao diện
                t_gui = time.perf_counter()
                # video ghi ra không có cột thông tin bên phải -> vẽ thêm khung thông số vào khung hình
                overlay = render_overlay(frame, result, self.pipeline.mapper, cfg, fps, info=writer is not None)
                bev = render_bev(frame, result, self.pipeline.mapper, cfg)
                result.timings_ms["gui"] = (time.perf_counter() - t_gui) * 1000
                if writer is not None:
                    writer.write(qimage_to_bgr(overlay))

                stats = self._stats(result, fps)
                if stats["calib"] is not None:      # mời nhập tốc độ in trên video (video không có GPS)
                    stats["calib"]["ask_speed"] = self._video_file and result.calib.ask_speed
                self.frame_ready.emit(overlay, bev, stats)
                if result.calib is not None and result.calib.new_calib is not None:
                    self.calibration_refined.emit(result.calib.new_calib, result.calib.note)
                if getattr(source, "total_frames", 0) > 1:
                    self.progress.emit(getattr(source, "frame_idx", 0), source.total_frames, float(source.fps))
                for ev in events:
                    if ev["action"] == "open":
                        ev.update(self._event(result))
                    self.violation.emit(ev)
                n_frames += 1

                if source.is_image:
                    break
                while self._paused and self._running:
                    time.sleep(0.05)
                    if not self._paused and isinstance(source, VideoFileSource):
                        source.restart_clock()
                ok, frame, t = source.read()
        finally:
            source.release()
            ev = recorder.close(t)
            if ev is not None:
                self.violation.emit(ev)
            elapsed = time.perf_counter() - wall_t0
            db.end_session(session_id, n_frames, round(n_frames / elapsed, 2) if elapsed > 0 else None)
            self.status.emit(f"Phiên #{session_id}: đã ghi {recorder.count} vi phạm vào CSDL")
            if writer is not None:
                writer.release()
                self.status.emit(f"Đã lưu video kết quả: {self.output_path}")

        if not source.is_image and self._running:
            self.status.emit("Đã phát hết video.")

    # ------------------------------------------------------------------

    def _open_writer(self, source, w, h):
        out_dir = self.cfg.resolve_path(self.cfg.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        self.output_path = out_dir / f"adas_{datetime.now():%Y%m%d_%H%M%S}.mp4"
        fps = source.fps if 1 <= source.fps <= 120 else 25
        writer = cv2.VideoWriter(str(self.output_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
        if not writer.isOpened():
            self.status.emit("Không tạo được file ghi video - bỏ qua ghi hình.")
            return None
        return writer

    @staticmethod
    def _stats(result, fps) -> dict:
        lead = result.lead
        thr = result.thresholds
        return {
            "fps": fps,
            "inference_ms": result.inference_ms,
            "detected": result.detected,
            "stride": result.stride,
            "timings_ms": dict(result.timings_ms),
            "level": result.level,
            "speed_kmh": result.speed_kmh,
            "speed_auto": result.speed_measured,
            "n_vehicles": len(result.vehicles),
            "safe_m": thr.safe_m if thr else None,
            "danger_m": thr.danger_m if thr else None,
            "lead_distance": lead.distance_m if lead else None,
            "lead_ttc": lead.ttc_s if lead else None,
            "lead_risk": lead.risk if lead else None,
            "lead_closing": lead.closing_speed_mps if lead else None,
            "lead_class": vehicle_label(lead.det.class_name) if lead else None,
            "lead_id": lead.det.track_id if lead else None,
            "lead_method": lead.method if lead else None,
            "calib": None if result.calib is None else {
                "state": result.calib.state, "progress": result.calib.progress,
                "message": result.calib.message, "ok": result.calib.ok},
        }

    @staticmethod
    def _save_snapshot(img: QImage, path: Path) -> bool:
        path.parent.mkdir(parents=True, exist_ok=True)
        return img.save(str(path), "JPG", 85)

    @staticmethod
    def _event(result) -> dict:
        lead = result.lead
        return {
            "time": datetime.now().strftime("%H:%M:%S"),
            "track_id": lead.det.track_id,
            "class": vehicle_label(lead.det.class_name),
            "safe_m": result.thresholds.safe_m,
            "speed_kmh": result.thresholds.speed_kmh,
        }
