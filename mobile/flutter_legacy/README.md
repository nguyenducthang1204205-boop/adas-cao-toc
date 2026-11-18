> **Lưu trữ.** Bản Flutter này đã được thay bằng dự án Android Studio (Kotlin + Jetpack Compose) trong
> `mobile/android/` - xem `mobile/README.md`. Giữ lại để tham khảo; đường dẫn trong file này là của bản cũ.

# ADAS Cao tốc: bản mobile (Flutter, Android + iOS)

Cảnh báo khoảng cách an toàn bằng camera điện thoại. Thuật toán giống bản desktop (`adas/`):
YOLOv11 → IPM → ngưỡng theo tốc độ và điều kiện đường → chống nhiễu cảnh báo. Mã Dart nằm trong
`app/lib/core/` và có kiểm thử đối chiếu với bản Python.

| Thành phần | Desktop (Python) | Mobile (Dart) |
|---|---|---|
| Nhận diện | `best.pt`, PyTorch/CUDA | `assets/models/*.tflite`: FP16 trên GPU, INT8 dynamic-range trên CPU |
| Bám vết | ByteTrack (Ultralytics) | `core/tracker.dart`, ghép theo IoU |
| IPM, khoảng cách, TTC | `ipm.py`, `distance.py` | `core/ipm.dart`, `core/distance.dart` (port 1:1) |
| Ngưỡng, điều kiện đường | `safety.py` | `core/safety.dart` (port 1:1) |
| Tốc độ xe chủ | đo từ vạch kẻ đứt (`speed.py`) | **GPS điện thoại**; không có GPS thì nhập tay |
| Làn đang đi | nhận diện vạch kẻ (`lane.py`) | hành lang cố định ±`lane_half_width` (chưa port) |
| Trợ lý AI | offline + Claude | các chip điều kiện đường (cùng bảng `ROAD_CONDITIONS`) |
| Cảnh báo | bíp (pygame) | bíp + giọng nói tiếng Việt (TTS), viền màu |

## Mô hình

Tạo bằng `python tools/export_mobile.py` (xem phần đầu file đó để biết cách dựng venv TensorFlow).
App đưa vào YOLO **dải đường** cắt theo hiệu chỉnh (bỏ phần trời), ô vào 288×640, thay cho cả khung
16:9 ở 384×640: ít hơn 25 % tính toán, xe giữ nguyên độ phân giải. Đo trên 1300 ảnh test bằng
`tools/eval_mobile.py` (cùng bộ nhãn cho hai cột; kết quả: `docs/ket_qua_mobile.json`):

| Bản | 384×640 cả khung (mAP50 / 50-95) | 288×640 dải đường (mAP50 / 50-95) | Dung lượng |
|---|---|---|---|
| FP16 (GPU) | 0,814 / 0,534 | 0,813 / 0,531 | 5,3 MB |
| INT8 dynamic-range (CPU) | 0,809 / 0,526 | 0,810 / 0,529 | 2,8 MB |
| INT8 đầy đủ | 0 / 0 | – | không dùng: nhánh tọa độ hộp sập về 0 |

`best.pt` gốc: 0,817 / 0,533 (Ultralytics). Trên PC, INT8 17 ms → 14 ms một ảnh (gồm tiền xử lý).

## Hiệu năng trên máy yếu

Thiết kế theo cách các hệ thống thị giác thời gian thực trên phần cứng hạn chế đang làm (openpilot,
CameraX/MediaPipe, Android ADPF, CarSafe), sau khi bản đầu bị giật trên Redmi Note 11S (Helio G96):

- **Luồng giao diện không xử lý ảnh.** Khung camera được chép sang một isolate xử lý
  (`engine/frame_engine.dart`: bám vết, khoảng cách, ngưỡng, chống nhiễu) chỉ khi khung trước đã xong;
  còn không thì bỏ ngay (không xếp hàng, không tăng trễ). YOLO chạy ở isolate thứ ba và trả kết quả
  thẳng về isolate xử lý. Overlay vẽ lại theo nhịp kết quả, các cụm số chỉ dựng lại ~10 lần/giây.
- **Bộ điều tốc** (`core/governor.dart`) chọn mức Cao / Trung bình / Thấp theo thời gian YOLO đo thật,
  nhiệt độ máy (Thermal API) và độ trễ xử lý. Thấp: bám vết 10 lần/giây, camera 480p.
- **Nhịp YOLO theo rủi ro**: đường trống thì 3 lần/giây, có xe gần / TTC nhỏ thì hết tốc lực.
- **Chống nhiễu theo thời gian** (0,1 s thay cho "3 khung"), nên máy 10 lần/giây báo kịp như máy
  30 lần/giây. Bản desktop đổi theo cùng quy tắc.
- **Số luồng CPU đo trên máy**: `XNNPackDelegate()` mặc định chỉ 1 luồng; app thử 1, 2, 4 luồng và giữ
  bộ nhanh nhất (chip 2 nhân mạnh + 6 nhân yếu thường nhanh nhất với 2). Không dùng
  `XNNPackDelegateOptions` của tflite_flutter 0.12.1: làm app crash (SIGSEGV) khi tạo delegate.
- **Cắt vùng đường** (`core/roi.dart`) và **thấy xa** (cứ 3 lần nhận diện có 1 lần nhìn kỹ vùng quanh
  điểm tụ, chỉ khi đường không gấp).
- **Tự kiểm tra + đo hiệu năng**: sau vài giây chạy, app báo "Máy của bạn: mức …"; máy dưới cấu hình
  tối thiểu (YOLO > 300 ms) được báo rõ là cảnh báo chỉ mang tính tham khảo. Cài đặt → Hiệu năng →
  **Đo hiệu năng máy** chạy 30 giây (hoặc 5 phút để đo nhiệt) trên video mẫu đóng gói sẵn, cho ra cùng
  một bảng số trên mọi máy (khung/giây, % khung giật, thời gian YOLO và bám vết, mức, nhiệt độ) và nút
  sao chép kết quả.

## Chạy trên điện thoại

Cần: Flutter SDK, Android Studio (đã có Android SDK). Với iPhone cần thêm máy Mac có Xcode.

```powershell
# tạo file cài: mobile\dist\ADAS_CaoToc.apk (chép sang điện thoại rồi mở để cài)
powershell -ExecutionPolicy Bypass -File mobile\build_apk.ps1
# hoặc cài và chạy thẳng trên điện thoại đang cắm cáp (bật Gỡ lỗi USB)
powershell -ExecutionPolicy Bypass -File mobile\build_apk.ps1 -Run
```

Không chạy `flutter build` / `flutter run` trực tiếp trong `mobile/app`: CMake/Ninja hỏng với đường dẫn
có chữ "Đồ án". Script đồng bộ mã sang `%LOCALAPPDATA%\adas_mobile_build` và build ở đó.
Kiểm thử thì chạy được tại chỗ: `cd mobile/app`, `flutter test` (so khớp phần lõi với Python) và
`dart analyze` (không dùng `flutter analyze`, cũng hỏng vì đường dẫn).

Bật Gỡ lỗi USB trên Android: Cài đặt → Thông tin điện thoại → chạm 7 lần vào "Số hiệu bản tạo" →
Tùy chọn nhà phát triển → Gỡ lỗi USB.

## Sử dụng

1. Gắn điện thoại cố định, màn hình nằm ngang, camera nhìn thẳng ra đường.
2. Mở **Căn chỉnh** và kéo 4 điểm vào mép trong 2 vạch kẻ của làn đang đi (1-2 gần, 3-4 xa). Nhập
   bề rộng làn (cao tốc VN: 3,75 m), chiều dài đoạn chọn và khoảng cách từ đầu xe tới cạnh gần.
   Lưới 10–60 m phải rơi đúng chỗ trên mặt đường. Làm lại mỗi khi thay đổi vị trí gắn máy.
3. Chọn điều kiện đường (khô ráo, mưa, sương mù…). Tốc độ lấy từ GPS.

Ứng dụng chỉ hỗ trợ cảnh báo, không thay thế sự chú ý của người lái.
