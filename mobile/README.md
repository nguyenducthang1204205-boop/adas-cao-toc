# ADAS Cao tốc: bản Android (Kotlin + Jetpack Compose)

Cảnh báo khoảng cách an toàn bằng camera điện thoại. Thuật toán giống hệt bản desktop (`adas/`):
YOLOv11 → IPM → ngưỡng theo tốc độ và điều kiện đường → chống nhiễu cảnh báo. Dự án Android Studio nằm
trong `android/`; phần lõi (`core/`) là Kotlin thuần, kiểm thử trên JVM bằng dữ liệu chuẩn do chính mã
Python sinh ra (`tools/make_mobile_fixtures.py`).

> Bản Flutter trước đây được giữ nguyên trong `flutter_legacy/` để tham khảo, không còn phát triển.

## Mở và chạy

1. Android Studio → **Open** → chọn thư mục `mobile/android`. Studio tự tải Gradle và thư viện.
2. Cắm điện thoại (bật *Gỡ lỗi USB*) → **Run ▶**. Hoặc build từ dòng lệnh:

```powershell
powershell -ExecutionPolicy Bypass -File mobile\android\build_apk.ps1           # APK release -> mobile\android\dist\ADAS_CaoToc.apk
powershell -ExecutionPolicy Bypass -File mobile\android\build_apk.ps1 -Test     # + unit test đối chiếu Python
powershell -ExecutionPolicy Bypass -File mobile\android\build_apk.ps1 -Install  # + cài lên điện thoại
```

Đường dẫn dự án có dấu ("Đồ án") nên thư mục build được đặt ở `%LOCALAPPDATA%\adas_android_build`
(xem `android/build.gradle.kts`). Lý do: `java.exe` đọc tham số theo bảng mã ANSI làm hỏng chữ "Đ".

Yêu cầu: Android 8.0 (API 26) trở lên, chip ARM; camera sau **hoặc** camera hành trình cắm USB; GPS không bắt
buộc (không có thì nhập tốc độ tay).

## Màn hình Android ô tô + camera hành trình

App chạy được trên màn hình Android gắn taplo, lấy hình từ camera hành trình cắm USB (chuẩn UVC, thư viện
`org.uvccamera:lib`):

1. Gắn camera sau gương chiếu hậu, giữa kính lái. Đi dây USB của camera xuống cổng USB của màn hình (một dây
   vừa cấp điện vừa truyền hình).
2. Cài APK lên màn hình, mở app một lần để cấp quyền camera và vị trí.
3. Cắm camera: Android hỏi *"Mở ADAS Cao tốc khi kết nối thiết bị USB này?"*. Chọn **Luôn mở**. Từ đó mỗi lần bật
   máy xe (cổng USB có điện) app tự mở và có sẵn quyền dùng camera.
4. **Căn chỉnh camera**: chọn loại xe, chọn góc quay ghi trên hộp camera (120–170°), kéo đường chân trời hoặc
   để nguyên. Khi lái, app tự đo chân trời từ 2 vạch làn và tự chỉnh thang khoảng cách theo GPS của màn hình.

Cài đặt → Camera → *Nguồn camera*: **Tự động** (mặc định: có camera USB thì dùng, không thì camera của máy),
*Camera của máy*, *Camera hành trình USB*. Không có camera USB thì app dùng camera bất kỳ mà hệ thống khai báo
(một số màn hình đưa camera AHD phía trước vào Android).

Giới hạn hiện tại:
- Chưa khử méo ống kính góc rộng: khoảng cách ở giữa ảnh (xe phía trước) dùng được sau khi GPS chỉnh thang,
  xe ở mép ảnh lệch nhiều hơn.
- App phải ở màn hình chính mới cảnh báo (chưa chạy nền / bong bóng nổi khi mở bản đồ).
- Camera chỉ một app dùng được: khi ADAS Cao tốc mở, app ghi hình của hãng không ghi.
- Thư viện UVC chỉ có bản ARM (không chạy trên máy ảo x86) và căn trang 4 KB (máy dùng trang 16 KB sẽ báo
  không chạy được camera USB, camera của máy vẫn dùng bình thường).

## Kiến trúc

```
android/app/src/main/java/vn/adas/caotoc/
  core/        Thuật toán, Kotlin thuần (không Android) - port 1:1 bản Python
    Ipm.kt, Geometry.kt     IPM ảnh -> mét                     (adas/distance/ipm.py)
    Distance.kt, Kalman.kt  khoảng cách, tốc độ tiếp cận, TTC   (adas/distance/estimator.py, kalman.py)
    TemplateTracker.kt      bám vết dày giữa các lần YOLO       (adas/detection/tracking.py)
    Detection.kt            giải mã YOLO + NMS, letterbox
    Safety.kt, Config.kt    ngưỡng theo dải tốc độ, điều kiện  (adas/alert/thresholds.py, adas/config.py)
    Pipeline.kt             một khung: bám vết -> khoảng cách -> mức rủi ro -> chống nhiễu
    Violations.kt           nhật ký vi phạm theo đợt           (adas/alert/violations.py)
    Assistant.kt            trợ lý offline, trả lời giống từng byte bản desktop (adas/assistant/offline.py)
    Governor.kt, Roi.kt     bộ điều tốc hiệu năng, vùng cắt đường cho YOLO
  detector/    LiteRT (TensorFlow Lite): tiền xử lý YUV, ảnh xám, chọn GPU/CPU nhanh nhất
  engine/      FrameEngine: luồng xử lý + luồng YOLO (CameraX KEEP_ONLY_LATEST, không dồn khung)
  data/        Cài đặt, nhật ký vi phạm (SharedPreferences, JSON)
  service/     Âm thanh (SoundPool + giọng nói tiếng Việt), GPS, nhiệt độ máy
  ui/          Jetpack Compose, hệ thiết kế "Night Drive" (cùng token với gui/theme.py)
    drive/       màn hình lái: camera, overlay, HUD, bảng điều kiện đường, Trợ lý AI | Vi phạm
    calibration/ căn chỉnh camera 3 bước (loại xe, chân trời theo cảm biến) + nâng cao: kéo 4 điểm
    settings/    cài đặt (ngưỡng theo dải tốc độ, cảnh báo, hiệu năng, nhận diện)
    benchmark/   đo hiệu năng trên 48 khung video mẫu
    welcome/     màn hình chào + lời nhắc an toàn
android/app/src/test/   CoreTest.kt, AssistantTest.kt + resources/fixtures (sinh từ Python)
```

| Thành phần | Desktop (Python) | Android (Kotlin) |
|---|---|---|
| Nhận diện | `best.pt`, PyTorch/CUDA | `assets/models/*.tflite`: FP16 trên GPU, INT8 dynamic-range trên CPU |
| Bám vết | ByteTrack + so khớp mẫu | `TemplateTracker` (so khớp mẫu, port 1:1); `IouTracker` khi tắt bám vết |
| Tốc độ xe chủ | đo từ vạch kẻ đứt | **GPS điện thoại**; không có GPS thì nhập tay |
| Làn đang đi | nhận diện vạch kẻ | hành lang cố định ±`lane_half_width` |
| Trợ lý AI | offline + Claude | offline (cùng luật, cùng câu trả lời) |
| Cảnh báo | bíp (pygame) | bíp + giọng nói tiếng Việt (TTS) + viền phát sáng |
| Nhật ký vi phạm | SQLite + ảnh bằng chứng | SharedPreferences (500 đợt gần nhất), không ảnh |

## Mô hình

Tạo bằng `python tools/export_mobile.py` (ghi thẳng vào `android/app/src/main/assets/models/`). App đưa
vào YOLO **dải đường** cắt theo hiệu chỉnh, ô vào 288×640: ít hơn 25 % tính toán so với cả khung 384×640 mà
mAP như nhau (`tools/eval_mobile.py`, `docs/ket_qua_mobile.json`):

| Bản | 384×640 cả khung (mAP50 / 50-95) | 288×640 dải đường (mAP50 / 50-95) | Dung lượng |
|---|---|---|---|
| FP16 (GPU) | 0,814 / 0,534 | 0,813 / 0,531 | 5,3 MB |
| INT8 dynamic-range (CPU) | 0,809 / 0,526 | 0,810 / 0,529 | 2,8 MB |

## Hiệu năng trên máy yếu

- **Luồng giao diện không xử lý ảnh.** CameraX giao khung cho luồng xử lý (bám vết, khoảng cách, ngưỡng,
  chống nhiễu) theo chế độ KEEP_ONLY_LATEST: còn bận thì khung mới thay khung cũ ngay tại camera. YOLO chạy ở
  luồng riêng, kết quả ghép ở khung kế tiếp và được dời theo chuyển động đã bám từ lúc chụp.
- **Bộ điều tốc** chọn mức Cao / Trung bình / Thấp theo thời gian YOLO đo thật, nhiệt độ máy (Thermal API) và
  độ trễ xử lý; **nhịp YOLO theo rủi ro** (đường trống 3 lần/giây, có xe gần thì hết tốc lực).
- **Chọn bộ suy luận lúc khởi động**: đo GPU và CPU XNNPACK 1 / 2 / 4 luồng, giữ bộ nhanh nhất.
- **Đo hiệu năng**: Cài đặt → Hiệu năng → *Đo hiệu năng máy* (30 giây hoặc 5 phút) cho cùng một bảng số
  trên mọi máy, có nút sao chép vào luận văn.

## Đã kiểm tra

- 23 unit test JVM: IPM, ngưỡng (kể cả câu giải thích), Kalman, bám vết, giải mã YOLO trên đầu ra thật của
  mô hình, tiền xử lý (cả khung NV21 của camera USB), pipeline, bộ điều tốc, nhật ký vi phạm và 342 câu của trợ lý - tất cả khớp Python.
- Máy ảo Android (Pixel 6 Pro, Android 17): màn hình chào, HUD, camera, YOLO → IPM → cảnh báo NGUY HIỂM,
  overlay, bảng Trợ lý AI | Vi phạm.
- Chưa đo trên điện thoại thật: tốc độ GPU, giọng đọc tiếng Việt, hướng khung camera trên từng máy
  (có cài đặt "Xoay ảnh 180°" để sửa tay).
