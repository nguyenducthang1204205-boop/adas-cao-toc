"""
Cấu hình ứng dụng - lưu/đọc từ config/settings.json.

Mọi tham số đều có giá trị mặc định hợp lý nên ứng dụng chạy được
ngay cả khi chưa có file cấu hình.
"""

import copy
import json
from dataclasses import dataclass, field, asdict, fields, is_dataclass
from pathlib import Path
from typing import List

from adas.paths import APP_DIR, CONFIG_PATH

# Tên hiển thị tiếng Việt cho các lớp phương tiện
CLASS_LABELS_VI = {
    "car": "Ô tô",
    "truck": "Xe tải",
    "bus": "Xe khách",
    "Jeepney": "Xe khách",
    "motorcycle": "Xe máy",
}

# Chiều cao thực tế trung bình (m) - dùng cho phương pháp dự phòng Pinhole
REAL_HEIGHTS_M = {
    "car": 1.50,
    "truck": 3.00,
    "bus": 3.20,
    "Jeepney": 2.10,
    "motorcycle": 1.25,
}

# Bề rộng thực tế trung bình (m)
REAL_WIDTHS_M = {
    "car": 1.80,
    "truck": 2.50,
    "bus": 2.50,
    "Jeepney": 2.00,
    "motorcycle": 0.80,
}


@dataclass
class ModelConfig:
    weights: str = "models/best.pt"           # Mô hình YOLOv11 đã huấn luyện
    fallback_weights: str = "models/yolo11n.pt"  # Dự phòng: YOLOv11n COCO
    confidence: float = 0.35
    iou: float = 0.45
    imgsz: int = 640
    device: str = "auto"                      # auto | cpu | 0
    # Nhận diện thưa, bám vết dày (detection/tracking.py): YOLO mỗi N khung, các khung giữa bám vết bằng so khớp mẫu.
    # 0 = tự động (YOLO chiếm không quá nửa thời gian một khung); 1 = YOLO mọi khung.
    detect_every: int = 0
    enabled_classes: List[str] = field(
        default_factory=lambda: ["car", "truck", "bus", "Jeepney"]
    )


@dataclass
class CameraPose:
    """
    Căn chỉnh theo tư thế camera (adas/distance/camera_model.py): người dùng nhập chiều cao camera và khoảng cách
    tới đầu xe, điểm tụ (hướng xe chạy trên ảnh) lấy tự động rồi được tinh chỉnh khi chạy (distance/online_calib.py).
    Khi active, 4 điểm image_points của CalibrationConfig được sinh từ tư thế này nên IPM không đổi cách tính.
    """
    active: bool = False
    vehicle: str = "car"                      # khóa trong camera_model.VEHICLE_PRESETS
    height_m: float = 1.25                    # camera cao hơn mặt đường
    height_measured: bool = False             # True: đo bằng thước -> giữ nguyên; False: tự chỉnh theo làn 3,75 m
    bumper_m: float = 2.0                     # camera nằm sau đầu xe bao nhiêu mét
    focal_w: float = 0.0                      # tiêu cự / chiều rộng khung (0 = theo camera_vfov_deg)
    focal_source: str = "fov"                 # camera (thông số ống kính) | speed (theo tốc độ thật) | fov (giả định)
    vp_x: float = 0.5                         # điểm tụ của mặt đường phía trước, tỷ lệ 0..1 theo W, H
    vp_y: float = 0.5
    roll_deg: float = 0.0                     # nghiêng ngang (> 0: chân trời dốc xuống bên phải)
    ref_speed_kmh: float = 0.0                # tốc độ thật lúc quay video (0 = không biết)
    refined: bool = False                     # đã tự hoàn thiện khi chạy


@dataclass
class CalibrationConfig:
    """
    Hiệu chỉnh IPM bằng một hình chữ nhật trên mặt đường có kích thước biết trước.

    image_points: 4 góc của hình chữ nhật trên ảnh (tỷ lệ 0..1 theo W, H),
                  thứ tự: dưới-trái, dưới-phải, trên-phải, trên-trái.
    rect_width_m: bề rộng thực của hình chữ nhật (vd: 1 làn cao tốc = 3.75 m).
    rect_length_m: chiều dài thực theo hướng xe chạy.
    near_distance_m: khoảng cách từ đầu xe chủ tới cạnh gần (cạnh dưới) của hình chữ nhật.
    """
    image_points: List[List[float]] = field(default_factory=lambda: [
        [0.33, 0.90], [0.67, 0.90], [0.535, 0.62], [0.465, 0.62]
    ])
    rect_width_m: float = 3.75
    rect_length_m: float = 30.0
    near_distance_m: float = 6.0
    lane_half_width_m: float = 1.9            # Nửa bề rộng hành lang làn xe chủ
    max_range_m: float = 150.0                # Giới hạn tầm đo tin cậy
    camera_vfov_deg: float = 55.0             # Góc nhìn dọc (cho phương pháp Pinhole)
    pose: CameraPose = field(default_factory=CameraPose)


@dataclass
class SafetyPolicy:
    """
    Chính sách ngưỡng an toàn - được Trợ lý AI điều chỉnh (xem adas/alert/thresholds.py).

    base   = ngưỡng của dải tốc độ (V >= 60 km/h, không thấp hơn bảng quy định)
             hoặc v * time_gap_s (V < 60 km/h), tối thiểu min_distance_m
    safe   = base * weather_factor          (hệ số điều kiện đường, khô ráo = 1.0)
    danger = max(min_distance_m, safe * danger_ratio)
    Ngoài ra dùng TTC (time-to-collision) để nâng mức cảnh báo.
    """
    time_gap_s: float = 2.0                   # Quy tắc 2 giây, chỉ dùng khi V < 60 km/h
    # Ngưỡng cảnh báo khi đường khô cho từng dải (60, 60-80, 80-100, 100-120 km/h), người dùng
    # tự đặt; thresholds.py luôn nâng lên ít nhất bằng LEGAL_GAP_TABLE. Mặc định = mức luật.
    band_gaps_m: List[float] = field(default_factory=lambda: [35.0, 55.0, 70.0, 100.0])
    weather_factor: float = 1.0
    danger_ratio: float = 0.5
    min_distance_m: float = 5.0
    ttc_warning_s: float = 4.0
    ttc_danger_s: float = 2.0
    use_legal_table: bool = True
    condition: str = "Đường khô ráo, tầm nhìn tốt"
    road_mu: float = 0.7                      # Hệ số bám mặt đường ước tính
    visibility_m: float = 0.0                 # Tầm nhìn (m); 0 = không hạn chế


@dataclass
class AlertConfig:
    sound_enabled: bool = True
    only_ego_lane: bool = True                # Chỉ cảnh báo xe cùng làn phía trước
    auto_lane: bool = True                    # Tự nhận diện làn đang đi theo vạch kẻ (distance/lane.py)
    escalate_seconds: float = 0.1             # Mức mới phải kéo dài ngần này giây (>= 2 khung) mới nâng
    hold_seconds: float = 0.8                 # Giữ mức cảnh báo tối thiểu trước khi hạ


# Mô hình Claude cho Trợ lý AI (API tính phí theo token, không có mô hình miễn phí).
# Mỗi lần hỏi ~2-3 nghìn token vào + vài trăm token ra.
ASSISTANT_MODELS = [
    ("claude-haiku-4-5", "Claude Haiku 4.5 - rẻ nhất, nhanh (khuyên dùng)"),
    ("claude-sonnet-5-5", "Claude Sonnet 5.5 - cân bằng"),
    ("claude-opus-5-5", "Claude Opus 5.5 - mạnh nhất, đắt nhất"),
]
DEFAULT_ASSISTANT_MODEL = ASSISTANT_MODELS[0][0]


@dataclass
class AssistantConfig:
    model: str = DEFAULT_ASSISTANT_MODEL
    use_cloud: bool = False                   # Mặc định trợ lý offline (miễn phí); True -> gọi Claude


@dataclass
class AppConfig:
    model: ModelConfig = field(default_factory=ModelConfig)
    calibration: CalibrationConfig = field(default_factory=CalibrationConfig)
    policy: SafetyPolicy = field(default_factory=SafetyPolicy)
    alert: AlertConfig = field(default_factory=AlertConfig)
    assistant: AssistantConfig = field(default_factory=AssistantConfig)
    speed_kmh: float = 80.0                   # Tốc độ nhập tay (dùng khi tắt tự đo hoặc chưa đo được)
    auto_speed: bool = True                   # Tự đo tốc độ từ chuyển động vạch kẻ đứt (distance/ego_speed.py)
    auto_calib: bool = True                   # Tự hoàn thiện căn chỉnh khi chạy + báo camera xê dịch (distance/online_calib.py)
    realtime_playback: bool = True            # Bỏ khung để bám thời gian thực khi đọc file
    output_dir: str = "outputs"

    # ---------- Lưu / đọc (CSDL SQLite: data/adas.db, bảng system_config) ----------

    @classmethod
    def load(cls, db=None) -> "AppConfig":
        """
        Đọc cấu hình từ CSDL. Lần đầu (CSDL trống): nhập từ config/settings.json nếu có,
        ngược lại dùng mặc định - rồi ghi vào CSDL.
        """
        from adas.storage.database import Database
        db = db or Database()
        data = db.load_config()
        if data is not None:
            try:
                cfg = _from_dict(cls, data)
            except (TypeError, ValueError) as e:
                print(f"[Config] Cấu hình trong CSDL lỗi: {e}. Dùng cấu hình mặc định.")
                return cls()
            if cfg.assistant.model not in dict(ASSISTANT_MODELS):
                # Mô hình cũ (vd: claude-opus-5) không còn trong danh sách -> dùng mô hình rẻ nhất
                cfg.assistant.model = DEFAULT_ASSISTANT_MODEL
                cfg.save("Đổi mô hình Trợ lý AI sang mặc định", db=db)
            return cfg

        cfg, reason = cls(), "Khởi tạo cấu hình mặc định"
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    cfg = _from_dict(cls, json.load(f))
                reason = "Nhập từ config/settings.json"
            except (OSError, ValueError, TypeError) as e:
                print(f"[Config] Không đọc được {CONFIG_PATH}: {e}. Dùng cấu hình mặc định.")
        db.save_config(asdict(cfg), reason)
        if reason.startswith("Nhập"):
            # CSDL là nguồn cấu hình duy nhất từ nay; giữ file cũ làm bản lưu
            CONFIG_PATH.replace(CONFIG_PATH.with_name("settings.imported.json"))
        return cfg

    def save(self, reason: str = "", db=None) -> None:
        from adas.storage.database import Database
        (db or Database()).save_config(asdict(self), reason)

    def resolve_path(self, p: str) -> Path:
        """Đường dẫn tương đối được tính theo thư mục ứng dụng."""
        path = Path(p)
        return path if path.is_absolute() else APP_DIR / path


def update_inplace(dst, src) -> None:
    """
    Chép giá trị từ src sang dst (cùng kiểu dataclass) mà giữ nguyên đối tượng dst,
    để các thành phần đang giữ tham chiếu (luồng xử lý, bộ cảnh báo) thấy thay đổi.
    """
    for f in fields(src):
        a, b = getattr(dst, f.name), getattr(src, f.name)
        if is_dataclass(a) and is_dataclass(b):
            update_inplace(a, b)
        else:
            setattr(dst, f.name, copy.deepcopy(b))


def _from_dict(cls, data: dict):
    """Tạo dataclass lồng nhau từ dict, bỏ qua khóa lạ."""
    kwargs = {}
    for f in fields(cls):
        if f.name not in data:
            continue
        value = data[f.name]
        default = f.default_factory() if callable(f.default_factory) else f.default  # type: ignore
        if is_dataclass(default) and isinstance(value, dict):
            kwargs[f.name] = _from_dict(type(default), value)
        else:
            kwargs[f.name] = value
    return cls(**kwargs)
