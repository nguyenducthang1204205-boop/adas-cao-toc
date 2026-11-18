"""
Lõi xử lý của hệ thống ADAS cảnh báo khoảng cách an toàn trên cao tốc (không phụ thuộc Qt).

Các gói con theo đúng sơ đồ kiến trúc (đề cương, PI 2.2):

    stream/      Video Stream            nguồn khung hình: file video, camera USB, RTSP, ảnh
    detection/   YOLOv11 Detection       YOLOv11 + ByteTrack, bám vết so khớp mẫu giữa các lần YOLO
    distance/    IPM Distance            IPM ảnh -> mét, làn xe chủ, tốc độ xe chủ, Kalman, TTC
    alert/       Alert Engine            ngưỡng theo dải tốc độ, chống nhiễu + âm thanh, nhật ký vi phạm
    assistant/   Trợ lý AI               gợi ý ngưỡng theo điều kiện lái (offline hoặc Claude)
    storage/     Dữ liệu                 CSDL SQLite

    pipeline.py  ghép tầng 2 -> 4 cho một khung hình (ADASPipeline.process -> FrameResult)
    config.py    cấu hình dùng chung (AppConfig), lưu trong CSDL
    paths.py     đường dẫn ứng dụng (mã nguồn hoặc bản .exe)

Tầng GUI (PySide6) nằm ở gói gui/ cạnh đây.
"""

__version__ = "1.1.0"
