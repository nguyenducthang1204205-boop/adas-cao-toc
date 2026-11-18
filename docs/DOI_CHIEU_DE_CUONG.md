# Đối chiếu mã nguồn với đề cương (H01 - Nguyễn Đức Thắng)

Đề tài: *Xây dựng hệ thống cảnh báo khoảng cách an toàn giữa các phương tiện trên cao tốc thời gian thực ứng
dụng mô hình YOLOv11 và thị giác máy tính.* Đối chiếu ngày 25/10/2026, sau khi tái cấu trúc mã.

Ký hiệu: **Đạt** - có trong mã và đã kiểm tra · **Một phần** - có nhưng còn thiếu · **Ngoài mã** - thuộc quyển
báo cáo / Figma / dữ liệu, không nằm trong mã nguồn.

## Yêu cầu sản phẩm (mục 7a)

| Yêu cầu | Trạng thái | Nơi thực hiện |
|---|---|---|
| Nhận video file thử nghiệm và luồng camera thời gian thực | Đạt | `adas/stream/sources.py` (file video, camera USB, RTSP, ảnh); hộp thoại `gui/dialogs/sources.py` |
| Phát hiện, phân loại ô tô, xe tải, xe khách bằng YOLOv11 | Đạt | `adas/detection/detector.py`, `models/best.pt` (5 lớp; mặc định bật ô tô, xe tải, xe khách, Jeepney = xe khách nhỏ; xe máy tắt) |
| Quy đổi khoảng cách thực (mét) bằng IPM | Đạt | `adas/distance/ipm.py` (homography pixel → mét), `estimator.py` (+ Kalman, TTC) |
| Hiển thị khoảng cách trực tiếp trên màn hình | Đạt | `gui/rendering/overlay.py`, thẻ trạng thái `gui/widgets/panels.py` |
| Đổi màu khung định vị + cảnh báo âm thanh khi vi phạm | Đạt | `adas/alert/engine.py` (chống nhiễu + bíp), màu theo mức rủi ro trong overlay |
| Tùy chỉnh ngưỡng cảnh báo theo từng dải tốc độ | Đạt | `adas/alert/thresholds.py` (`band_gaps_m`, không thấp hơn Thông tư 31/2019), Cài đặt → Ngưỡng cảnh báo |
| Xử lý mượt, ổn định trên máy tính thử nghiệm | Đạt | ≈ 29 FPS trên GPU (đo từng tầng ở thanh trạng thái); YOLO thưa + bám vết dày cho máy CPU |

## Bảng PI (mục 7b)

| PI | Yêu cầu tối thiểu | Trạng thái | Ghi chú |
|---|---|---|---|
| 1.1 | Khảo sát quy trình, sơ đồ BPMN | Ngoài mã | Có sơ đồ trong `docs/so_do` và `docs/bao_cao_tien_do` |
| 1.2 | Bảng yêu cầu chức năng / phi chức năng | Ngoài mã | Số liệu phi chức năng lấy từ thanh trạng thái (ms/tầng) và màn hình đo hiệu năng của app Android |
| 1.3 | Sơ đồ UC tổng quát, 5 UC + đặc tả | Ngoài mã | 5 UC đều có trong mã, xem bảng dưới |
| 2.1 | Sơ đồ lớp, CSDL lưu cấu hình, ma trận camera, nhật ký | Đạt | SQLite `adas/storage/database.py`: `system_config`, `config_history`, `video_sources`, `camera_calibrations` (K, H, R), `monitoring_sessions`, `violations`; ERD trong `docs/THIET_KE_HE_THONG.md` |
| 2.2 | Kiến trúc Video Stream → YOLOv11 → IPM → Alert Engine → GUI | Đạt | Sau tái cấu trúc, mỗi tầng là một gói: `adas/stream` → `adas/detection` → `adas/distance` → `adas/alert` → `gui/` |
| 2.3 | Mockup Figma (giám sát, cài đặt IPM, nhật ký) | Đạt (18/11) | File Figma *ADAS Cao tốc - Mockup giao diện* (link trong `docs/giao_dien/figma/README.md`): 9 frame chia 3 section theo UC, có prototype nối các nút. Nguồn SVG + PNG cho quyển ở `docs/giao_dien/figma/`, tạo bằng `tools/export_mockups.py` |
| 3.1 | Xây dựng, khởi tạo CSDL | Đạt | `python tools/init_db.py`, tự tạo + nâng cấp lược đồ (v3) khi chạy |
| 3.2 | Thành phần AI/CV + giao diện điều khiển | Đạt | Lõi `adas/`, giao diện `gui/` (PySide6) |
| 3.3 | Thi công 5 UC | Đạt | Xem bảng UC |
| 3.4 | AI gợi ý ngưỡng theo tốc độ xe chủ | Đạt | `adas/assistant/` (offline mặc định, Claude tùy chọn); dùng tốc độ đo được hoặc tốc độ nêu trong câu |
| 4.1 | Đóng gói Desktop Executable | Đạt (mới) | `python tools/build_exe.py` → `dist/ADAS/ADAS.exe`. Máy này bật Smart App Control nên chặn exe chưa ký số; chạy trên máy khác hoặc ký số exe |
| 4.2 | Dataset ô tô / xe tải / xe khách + video ban ngày, ban đêm, thời tiết xấu | Một phần | Dataset hiện chủ yếu là cảnh đô thị ban đêm và có rò rỉ train/test (mAP 0,82 lạc quan). **Thiếu bộ video thử nghiệm có đủ 3 kịch bản** - mới có `videoplayback.mp4` (ban ngày) |

## 5 UC chính

| UC | Màn hình / module |
|---|---|
| UC1. Quản lý nguồn video/camera | `gui/dialogs/sources.py`: thêm / sửa / xóa / dò camera, nguồn gần đây; bảng `video_sources` |
| UC2. Cấu hình thông số IPM | `gui/dialogs/calibration.py`: 4 điểm + kích thước thực, tự động căn chỉnh (`adas/distance/autocalib.py`), lưu ma trận theo nguồn |
| UC3. Cấu hình ngưỡng cảnh báo | `gui/dialogs/settings.py` (ngưỡng theo dải tốc độ, điều kiện, TTC, âm thanh), thẻ tốc độ / điều kiện đường, Trợ lý AI |
| UC4. Giám sát realtime & cảnh báo | `gui/main_window.py` + `gui/worker.py` + `adas/pipeline.py` |
| UC5. Quản lý nhật ký cảnh báo | `gui/dialogs/history.py`: phiên, vi phạm, ảnh bằng chứng, xuất CSV, xóa; thẻ Vi phạm trong cửa sổ chính |

## Ngoài đề cương (điểm cộng)

- App Android (Kotlin + Jetpack Compose) trong `mobile/android`: cùng thuật toán, kiểm thử đối chiếu với Python.
- Nhận diện làn xe chủ, tự đo tốc độ xe từ video, lọc Kalman, bám vết dày giữa các lần YOLO.

## Việc cần làm tiếp để khớp hoàn toàn đề cương

1. Thu thập **video thử nghiệm ban đêm và thời tiết xấu** trên cao tốc; bổ sung ảnh ban ngày / cao tốc vào
   dataset và tách lại train/test theo video để hết rò rỉ (PI 4.2).
2. Chạy `tools/build_exe.py --zip` và thử bản đóng gói trên một máy không bật Smart App Control (PI 4.1).
