# Hệ thống cảnh báo khoảng cách an toàn trên cao tốc (YOLOv11 + IPM)

Phần mềm ADAS giám sát khoảng cách tới xe phía trước theo thời gian thực từ video hành trình
hoặc camera trực tiếp. Hệ thống phát hiện phương tiện bằng YOLOv11, chuyển điểm tiếp xúc mặt đường
sang góc nhìn từ trên xuống (Bird's-Eye View) bằng IPM để tính khoảng cách thực (mét), rồi cảnh báo
bằng màu khung và âm thanh khi khoảng cách nhỏ hơn ngưỡng an toàn. Ngưỡng này thay đổi theo tốc độ
và được Trợ lý AI điều chỉnh theo điều kiện thực tế.

## Cài đặt & chạy

```bash
pip install -r requirements.txt
python main.py                          # mở giao diện
python main.py --source duong/video.mp4 # chạy ngay một video
python main.py --source 0               # camera USB
python main.py --source rtsp://...      # camera IP
python tools/smoke_test.py              # kiểm tra nhanh pipeline, không cần giao diện
```

Trợ lý AI mặc định chạy **offline** (luật từ khóa tiếng Việt, gõ có dấu hoặc không dấu): miễn phí,
không cần Internet. Có thể bật thêm Claude (Anthropic, trả phí theo lượt hỏi) trong
**⚙ Cài đặt → Trợ lý AI** và nhập API key (key chỉ giữ trong phiên, không ghi ra file). Khi mất mạng
hoặc key lỗi, trợ lý tự quay về chế độ offline nên phần mềm vẫn hoạt động đầy đủ.

## Cấu trúc

Mã chia theo đúng sơ đồ kiến trúc của đề cương (PI 2.2):
**Video Stream → YOLOv11 Detection → IPM Distance Calculation → Alert Engine → GUI**.

```
main.py                    Điểm khởi chạy (chỉ đọc tham số, gọi gui.app.run)
adas/                      Lõi xử lý - không phụ thuộc Qt
  stream/sources.py        [1] Nguồn: file video, camera USB, camera IP/RTSP, ảnh
  detection/               [2] YOLOv11 Detection
    detector.py              YOLOv11 + ByteTrack (phát hiện, phân loại, bám vết)
    tracking.py              Bám vết dày bằng so khớp mẫu giữa các lần YOLO
  distance/                [3] IPM Distance Calculation
    ipm.py                   Biến đổi phối cảnh ngược: ảnh -> mặt đường (mét)
    autocalib.py             Tự căn chỉnh camera (điểm tụ + vạch đứt)
    lane.py                  Nhận diện làn đang đi
    ego_speed.py             Tự đo tốc độ xe chủ từ vạch kẻ đứt
    kalman.py                Lọc Kalman khoảng cách / tốc độ tiếp cận
    estimator.py             Khoảng cách, làn, tốc độ tiếp cận, TTC (+ dự phòng Pinhole)
  alert/                   [4] Alert Engine
    thresholds.py            Ngưỡng an toàn theo dải tốc độ + điều kiện đường
    engine.py                Chống nhiễu cảnh báo + âm thanh
    violations.py            Ghi nhật ký vi phạm theo đợt + ảnh bằng chứng
  assistant/               Trợ lý AI gợi ý ngưỡng (PI 3.4)
    offline.py               Luật từ khóa tiếng Việt (mặc định, không cần Internet)
    prompt.py, service.py    Claude (structured output), tự quay về offline khi lỗi
  storage/database.py      CSDL SQLite: cấu hình, nguồn, ma trận camera, phiên, vi phạm
  pipeline.py              Ghép tầng [2] -> [4] cho một khung hình
  config.py                Cấu hình dùng chung (lưu trong CSDL)
  paths.py                 Đường dẫn ứng dụng (chạy từ mã nguồn hoặc bản .exe)
gui/                       [5] GUI - PySide6
  app.py, main_window.py   Khởi tạo ứng dụng, cửa sổ giám sát
  worker.py                Luồng xử lý nền (QThread)
  dialogs/                 Nguồn video, căn chỉnh IPM, cài đặt ngưỡng, nhật ký vi phạm
  widgets/                 Các vùng của màn hình giám sát
  rendering/               Lớp phủ cảnh báo + Bird's-Eye View (QPainter, vẽ được tiếng Việt)
  theme.py, styles.py      Hệ thiết kế "Night Drive" (dùng chung với app Android)
assets/                    Font Be Vietnam Pro + Material Icons, biểu tượng app
tools/                     smoke_test.py (kiểm thử), init_db.py, build_exe.py (đóng gói), xuất mô hình mobile
mobile/android/            App Android (Kotlin + Jetpack Compose) - xem mobile/README.md
models/best.pt             YOLOv11n đã huấn luyện (Jeepney, bus, car, motorcycle, truck)
data/adas.db               Cơ sở dữ liệu (tự tạo; hoặc: python tools/init_db.py)
data/snapshots/            Ảnh bằng chứng vi phạm (session_<mã phiên>/violation_<mã>.jpg)
outputs/                   Video kết quả khi bật Ghi video
```

## Đóng gói ứng dụng desktop (PI 4.1)

```bash
pip install pyinstaller
python tools/build_exe.py          # -> dist/ADAS/ADAS.exe (+ models/, assets/, data/ cạnh exe)
python tools/build_exe.py --zip    # thêm dist/ADAS_win64.zip để mang sang máy khác
```

Thư mục `dist/ADAS` chạy được trên Windows 64-bit không cần cài Python (khoảng 4,6 GB vì có PyTorch CUDA).
CSDL và ảnh vi phạm nằm trong `dist/ADAS/data`. Máy bật *Smart App Control* sẽ chặn exe chưa ký số: ký số
file exe, hoặc chạy trên máy tắt tính năng này.

## Phương pháp

### 1. Phát hiện & bám vết
YOLOv11 phát hiện ô tô, xe tải, xe khách; ByteTrack gán ID ổn định qua các khung để làm mượt
khoảng cách và ước lượng tốc độ tiếp cận. Điểm tiếp xúc mặt đường = trung điểm cạnh dưới bounding box.

### 2. IPM - Biến đổi phối cảnh ngược
Chọn 4 điểm trên ảnh tạo thành hình chữ nhật W × L mét trên mặt đường, cạnh gần cách đầu xe d₀.
Ma trận đồng nhất H (3×3) ánh xạ **trực tiếp** pixel sang tọa độ mặt đường tính bằng mét:

```
[X·s, Y·s, s]ᵀ = H · [u, v, 1]ᵀ     với (u,v) góc ảnh  ->  (±W/2, d₀), (±W/2, d₀+L)
```

X là độ lệch ngang (xác định xe có cùng làn không: |X| ≤ nửa bề rộng làn), Y là khoảng cách dọc
tới đuôi xe phía trước. Điểm nằm trên đường chân trời (thành phần đồng nhất đổi dấu) bị loại và
chuyển sang phương pháp dự phòng Pinhole: `d = H_thực · f / h_pixel`, với `f = H_ảnh / (2·tan(FOV_dọc/2))`.

### 3. Tốc độ tiếp cận & TTC
Khoảng cách từng track được làm mượt EMA; tốc độ tiếp cận là hệ số góc hồi quy tuyến tính
d(t) trên cửa sổ 1 giây. `TTC = d / v_tiếp_cận` (chỉ khi v_tiếp_cận > 0,5 m/s).

### 4. Ngưỡng an toàn theo tốc độ (`adas/alert/thresholds.py`)

**Mặt đường khô ráo - theo quy định của Bộ GTVT:**

| Tốc độ lưu hành | Khoảng cách an toàn tối thiểu |
|---|---|
| 60 km/h | 35 m |
| trên 60 đến 80 km/h | 55 m |
| trên 80 đến 100 km/h | 70 m |
| trên 100 đến 120 km/h | 100 m |
| dưới 60 km/h | Người lái tự chủ động theo mật độ và tình hình giao thông → hệ thống **ước tính** bằng quy tắc 2 giây (d = v·2 s) |

**Điều kiện bất lợi:** quy định chỉ yêu cầu giữ khoảng cách *lớn hơn* bảng trên, không nêu con số. Hệ thống
**ước tính** hệ số nhân dựa trên vật lý phanh (quãng phanh ∝ 1/μ, hệ số ≈ μ_khô/μ với μ_khô ≈ 0,7):

| Điều kiện | μ ước tính | Hệ số | Ví dụ ở 100 km/h |
|---|---|---|---|
| Khô ráo, tầm nhìn tốt | 0,70 | ×1,0 | 70 m |
| Mặt đường ướt, mưa nhỏ | 0,50 | ×1,4 | 98 m |
| Sương mù, tầm nhìn hạn chế | 0,60 | ×1,5 (+ khuyến nghị tốc độ theo tầm nhìn) | 105 m |
| Mưa to, đọng nước | 0,35 | ×2,0 | 140 m |
| Trơn trượt (dầu, bùn, sỏi) | 0,25 | ×2,5 | 175 m |

Yếu tố cộng thêm (nhân dồn, tối đa ×3,0): ban đêm ×1,2 · xe chủ chở nặng ×1,3 · tài xế mệt ×1,15.
Tầm nhìn hạn chế: tốc độ khuyến nghị là tốc độ để quãng đường dừng (phản xạ 1,5 s + phanh v²/2μg)
không vượt tầm nhìn (vd: sương mù, tầm nhìn 100 m → ≤ 96 km/h).

```
safe   = (bảng quy định nếu V ≥ 60, ngược lại v·2s) × hệ_số_điều_kiện   -> dưới ngưỡng: CẢNH BÁO
danger = max(d_min, safe × 0,5)                                         -> dưới ngưỡng: NGUY HIỂM
TTC < TTC_cảnh_báo -> CẢNH BÁO;  TTC < TTC_nguy_hiểm -> NGUY HIỂM
```
Cảnh báo chỉ được nâng mức khi xuất hiện liên tiếp N khung và được giữ tối thiểu một khoảng thời gian,
giúp giảm báo động giả.

### 5. Trợ lý AI
Tài xế mô tả tình huống ("mưa to, tôi chạy 90 km/h", "sương mù", "chở nặng", "buồn ngủ"...).
Claude trả về JSON theo schema cố định (lời khuyên + time-gap, hệ số điều kiện, ngưỡng TTC, tốc độ);
giá trị được kẹp trong giới hạn an toàn rồi áp dụng ngay. AI **không** nằm trong vòng lặp từng khung
hình - so sánh khoảng cách với ngưỡng luôn chạy cục bộ nên cảnh báo không phụ thuộc độ trễ mạng.

## Use case & chức năng tương ứng

| Use case | Chức năng trong ứng dụng |
|---|---|
| **UC1. Quản lý nguồn video/camera** | Nút chọn nguồn trên thanh tiêu đề (hoặc màn hình hướng dẫn 3 bước): 📂 Mở video · 📷 Camera trực tiếp (USB/RTSP) · 🖼 Mở ảnh · các nguồn dùng gần đây · **🗂 Quản lý nguồn**: danh sách nguồn lưu CSDL - thêm / sửa / xóa, 🔌 kiểm tra kết nối (xem trước, độ phân giải, FPS), 🔍 dò camera USB, mở nguồn · ▶ Bắt đầu / ⏹ Dừng (một nút) · ⏸ Tạm dừng trên thanh phát |
| **UC2. Cấu hình thông số IPM** | 📐 Căn chỉnh camera (thanh tiêu đề, hoặc nút *Căn chỉnh ngay* trên thanh nhắc khi nguồn chưa căn chỉnh): 🤖 tự động căn chỉnh hoặc đặt 4 điểm + kích thước thực, xem trước Bird's-Eye View, điểm mặc định · lưu CSDL **riêng cho từng nguồn** và tự nạp lại khi mở nguồn |
| **UC3. Cấu hình ngưỡng cảnh báo** | Thẻ *Tốc độ xe của bạn* (tự đo từ video, hoặc 4 nấc chọn tay theo bảng quy định) · thẻ *Điều kiện đường* (nút nhanh: khô ráo, mưa, sương mù, trơn trượt, ban đêm, chở nặng, mệt mỏi · ↺ Mặc định) · ⚙ Cài đặt → Ngưỡng an toàn (điều kiện đường, hệ số, μ, tầm nhìn, TTC) · 🤖 Trợ lý AI · ⚙ Cài đặt → Cảnh báo (bật/tắt, 🔊 nghe thử, chống nhiễu) · khôi phục mặc định / từ lịch sử |
| **UC4. Giám sát realtime & cảnh báo** | YOLOv11 + ByteTrack, khoảng cách IPM, TTC, đổi màu khung, vùng nguy hiểm trên mặt đường, banner + viền nhấp nháy, âm thanh, Bird's-Eye View (cạnh video hoặc ô nổi, bật/tắt được), thẻ *Xe phía trước* (khoảng cách, thanh đo so với ngưỡng, TTC, tốc độ tiếp cận), thanh phát (tiến độ, thời gian), ⏺ ghi video |
| **UC5. Quản lý nhật ký cảnh báo** | Tự ghi vi phạm (theo đợt, kèm ảnh) · tab 📋 Vi phạm (phiên hiện tại) · **🗄 Lịch sử**: xem theo phiên / tất cả phiên, lọc theo thời gian - mức - loại xe, xem ảnh bằng chứng, thống kê, xuất CSV, xóa vi phạm / xóa phiên |

## Cơ sở dữ liệu (`data/adas.db`, SQLite)

```bash
python tools/init_db.py          # khởi tạo lược đồ + nạp cấu hình, in cấu trúc CSDL
python tools/init_db.py --reset  # sao lưu CSDL cũ (adas_<thời gian>.db.bak) rồi tạo mới
```
Ứng dụng tự khởi tạo CSDL ở lần chạy đầu và tự nhập `config/settings.json` cũ (đổi tên thành
`settings.imported.json`). Tra cứu trong ứng dụng: **🗄 Lịch sử** trên thanh tiêu đề (hoặc tab 📋 Vi phạm → 🗄 Lịch sử).
Có thể mở file bằng DB Browser for SQLite để xem/truy vấn trực tiếp.

Sơ đồ kiến trúc, sơ đồ luồng và ERD đầy đủ: [docs/THIET_KE_HE_THONG.md](docs/THIET_KE_HE_THONG.md).

```
video_sources 1 ──── n camera_calibrations                       (ma trận camera)
video_sources 1 ──── n monitoring_sessions 1 ──── n violations   (ON DELETE SET NULL / CASCADE)
system_config ──(bản chụp)──► config_history
v_session_summary = monitoring_sessions ⟕ violations (thống kê theo phiên)
```

| Bảng | Cột chính | Ý nghĩa |
|---|---|---|
| `video_sources` | `id`, `name`, `source_type`, `uri` (duy nhất, đường dẫn đã chuẩn hóa), `description`, `created_at`, `last_used_at` | Danh sách nguồn video/camera |
| `camera_calibrations` | `id`, `source_id` (FK), `method` (manual/auto/imported), `frame_width/height`, `intrinsic_matrix` (K), `homography_matrix` (H), `rotation_matrix` (R), `focal_px`, `horizon_y`, `camera_height_m`, `camera_offset_m`, `pitch_deg`, `params_json`, `note` | **Ma trận camera** của từng nguồn - mỗi lần hiệu chỉnh 1 dòng, dòng mới nhất đang dùng |
| `system_config` | `section`, `key` (khóa chính), `value` (JSON), `updated_at` | Cấu hình hiện hành - mỗi tham số một dòng (model, calibration, policy, alert, assistant, app) |
| `config_history` | `id`, `changed_at`, `reason`, `config_json` | Lịch sử thay đổi cấu hình; chỉ ghi khi cấu hình thực sự thay đổi. Khôi phục được trong ứng dụng |
| `monitoring_sessions` | `id`, `started_at`, `ended_at`, `source`, `source_type` (video/camera/stream/image), `model_weights`, `device`, `frame_width/height`, `frames_processed`, `avg_fps`, `config_json` | Mỗi lần giám sát; lưu cấu hình tại thời điểm chạy để truy vết |
| `violations` | `id`, `session_id` (FK), `started_at`, `ended_at`, `video_time_s`, `duration_s`, `level` (warning/danger), `track_id`, `vehicle_class`, `distance_m`, `min_distance_m`, `min_ttc_s`, `closing_speed_kmh`, `ego_speed_kmh`, `safe_threshold_m`, `danger_threshold_m`, `legal_min_gap_m`, `road_condition`, `weather_factor`, `snapshot_path` | Nhật ký vi phạm khoảng cách |

**Một vi phạm = một đợt**: bắt đầu khi mức cảnh báo (sau chống nhiễu) chuyển sang CẢNH BÁO/NGUY HIỂM với
xe phía trước, kết thúc khi an toàn trở lại hoặc xe phía trước đổi sang xe khác. Trong đợt cập nhật khoảng
cách/TTC nhỏ nhất và mức cao nhất; ảnh bằng chứng chụp khi mở đợt và chụp lại khi nâng lên NGUY HIỂM.
CSDL chỉ được ghi khi mở / nâng mức / đóng đợt, không ghi mỗi khung hình.

Ví dụ truy vấn:
```sql
-- Top 10 vi phạm nguy hiểm nhất
SELECT started_at, vehicle_class, min_distance_m, safe_threshold_m, ego_speed_kmh, road_condition
FROM violations WHERE level = 'danger' ORDER BY min_distance_m LIMIT 10;
-- Thống kê theo phiên
SELECT * FROM v_session_summary ORDER BY id DESC;
```

## Căn chỉnh camera - hiệu chỉnh IPM (quan trọng)

Độ chính xác khoảng cách phụ thuộc hoàn toàn vào hiệu chỉnh cho **đúng camera và vị trí gắn**.
Cấu hình mặc định chỉ là ước lượng; nếu chưa hiệu chỉnh, đường chân trời sai sẽ làm khoảng cách
sai lệch lớn (xe xa có thể hiện số nhỏ hơn xe gần).

### 3 bước (mặc định) - `adas/distance/camera_model.py`, `online_calib.py`
Cách làm của camera hành trình / openpilot / Tesla: người dùng chỉ nhập số đo, góc camera do phần mềm tự đo.
**📐 Căn chỉnh camera** mở trình 3 bước:

1. **Xe và số đo** - chọn loại xe (điền sẵn chiều cao camera, khoảng cách tới đầu xe) hoặc nhập số đo bằng thước.
2. **Đường chân trời** - phần mềm tự tìm điểm tụ của vạch kẻ đường (desktop) / theo cảm biến trọng lực (Android,
   tiêu cự đọc từ thông số ống kính Camera2) và vẽ chân trời + tâm ngắm; lệch thì kéo trên ảnh.
   Không phải nhập tốc độ ở đây (video không bị dừng).
3. **Hoàn tất** - khi chạy, thanh *"Đang tự hoàn thiện căn chỉnh 0-100 %"* đo điểm tụ từ 2 vạch làn (~5 s
   thấy rõ vạch), chỉnh chiều cao theo làn 3,75 m nếu chưa đo, rồi báo kết quả (*"Làn đo được 3,72 m - đạt"*)
   và lưu thành một bản căn chỉnh mới (`method = 'online'`, bản cũ vẫn trong lịch sử). Sau đó tự phát hiện
   camera bị xê dịch và căn chỉnh lại. Căn chỉnh chấm 4 điểm chỉ được kiểm tra, không bị sửa.

Trên `videoplayback.mp4`, làm như người dùng chưa từng căn chỉnh video này (chọn *Xe con*, không đo chiều cao),
so với tốc độ GPS in trên video:

| Cách căn chỉnh | Thao tác | Tốc độ đo lệch (trung vị / MAE) | Làn đo được |
|---|---|---|---|
| 3 bước + gõ tốc độ trên hình khi video chạy (giây 2, 75 km/h) | 1 số, không dừng video | −0,5 / 1,3 km/h | 3,74 m |
| 3 bước + gõ tốc độ khi video chạy (giây 10 / 35) | 1 số, không dừng video | −1,9 / +4,0 km/h | 3,74 m |
| 3 bước, không biết tốc độ (góc nhìn mặc định) | 0 số | −10 … −14 km/h | 3,75 m |
| Điện thoại: 3 bước + tự chỉnh theo GPS (mô phỏng) | 0 số | +0,2 / 1,2 km/h | 3,74 m |
| Tự động cũ (nhập 74 km/h) | 1 số | −4,6 / 4,8 km/h | 3,77 m |
| Chấm 4 điểm (#18, căn tay nhiều lần) | 4 điểm + 3 số | −1,0 / 1,2 km/h | 3,87 m |

Không biết tốc độ thì chỉ vạch làn không đo được tiêu cự (bề rộng làn theo pixel không phụ thuộc tiêu cự), nên
thang khoảng cách theo góc nhìn giả định; trên điện thoại tiêu cự lấy từ Camera2 rồi tự chỉnh theo GPS.
Giả lập camera bị xê dịch 12 px giữa video: phát hiện sau 2,6 s, căn chỉnh lại xong sau 5 s.
Mỗi lần bấm Bắt đầu, app đo lại; nếu kết quả trùng bản đã tự hoàn thiện (lệch < 0,25°, chiều cao < 2 %) thì chỉ báo
*"Kiểm tra căn chỉnh: làn đo được … - đạt"*, không lưu thêm bản trùng.

**Trên điện thoại không phải nhập gì:** sau khoảng nửa phút chạy đều, app so tốc độ đo từ vạch kẻ đứt với GPS
(chỉ lấy lúc tốc độ GPS gần như không đổi, nên GPS trễ 1-2 s không ảnh hưởng) và tự chỉnh thang khoảng cách
(tiêu cự). Mô phỏng trên video demo, dùng số in trên hình làm GPS (1 lần/giây, làm tròn, trễ 1 hoặc 2 s), bắt
đầu từ góc nhìn mặc định (tốc độ lệch −10 km/h): tự chỉnh ở giây 24, sau đó lệch **+0,2 km/h** (MAE 1,2), ngang
bản chấm tay #18.

Video trên desktop không có GPS: **không phải dừng video để nhập**. Khi video chạy, thanh căn chỉnh phía trên
video có ô *"Tốc độ trên video: [..] km/h"* - gõ số đang in trên hình (vd 74KM/H) rồi Enter. App lấy thời điểm
bắt đầu gõ (lúc đọc số), so với tốc độ đo từ vạch kẻ ±2 s quanh lúc đó, rồi tự chỉnh thang khoảng cách; phần còn
lại tự động. Trên video demo, bắt đầu từ góc nhìn mặc định: gõ ở giây 2 → tốc độ lệch −0,5 km/h (MAE 1,3), giây
10 → −1,9, giây 35 → +4,0 (đoạn này tốc độ đo từ vạch kẻ vốn thấp ~4 %): nên gõ lúc xe chạy đều.

### Tự động từ cả video (nâng cao) - `adas/distance/autocalib.py`
**📐 Căn chỉnh camera → Căn chỉnh nâng cao → 🤖 Tự động căn chỉnh** → nhập tốc độ trung bình của xe trong video
(số km/h in trên video camera hành trình). Mô hình mặt đường phẳng `Y(v) = K/(v − v₀)`:

1. **Điểm tụ (u₀, v₀)** - giao điểm các vạch kẻ đường (Hough + RANSAC) → hàng chân trời.
2. **Chiều cao camera** - bề rộng làn xe chủ tính bằng pixel `w(v) = c·(v − v₀)`, đo từng khung
   (không bị ảnh hưởng khi xe trôi ngang trong làn) → `h_c = 3,75 m / c`.
3. **Thang chiều sâu K = f·h_c** - khi xe chạy với tốc độ `v`, hoa văn vạch đứt trên mặt đường tiến lại
   đúng `v·Δt` mét giữa 2 khung; đo độ dịch này trong hệ tọa độ `1/(v − v₀)` → `K`.
4. Kiểm tra chéo: đo lại độ dài nét và chu kỳ vạch đứt theo thang vừa tìm được - phải ra số tròn hợp lý.

Ví dụ với video thử (camera VIETMAP S720, 640×360, ~75 km/h, chạy mất ~2 giây): chân trời ở 52,8%
chiều cao ảnh, camera cao 1,18 m, tiêu cự ≈ 399 px ±5% (góc nhìn ngang ≈ 77°); kiểm tra chéo: vạch đứt
dài 2,9 m, chu kỳ 8,4 m. Trên cả 1800 khung, không có cặp xe nào bị đảo thứ tự khoảng cách.

### Chấm 4 điểm (nâng cao)
1. Mở một video/ảnh quay từ camera của bạn trên đoạn đường thẳng, bằng phẳng.
2. Nhấn **📐 Căn chỉnh camera → Căn chỉnh nâng cao**, nhấp 4 điểm lên 2 mép vạch làn xe chủ (gần → xa).
3. Nhập bề rộng làn (cao tốc VN: 3,75 m), chiều dài đoạn đã chọn và khoảng cách từ đầu xe tới cạnh dưới.
4. Ảnh Bird's-Eye View xem trước phải cho các vạch làn **song song, thẳng đứng**.

Giới hạn: IPM giả thiết mặt đường phẳng; ở khoảng cách > 80-100 m mỗi pixel tương ứng nhiều mét
nên sai số tăng. Dốc, cua gắt, xe bị che phần dưới cũng làm giảm độ chính xác.

## Tự đo tốc độ xe từ video - `adas/distance/ego_speed.py`

Không cần GPS/OBD. Khi xe chạy với tốc độ `v`, vạch kẻ đứt trên mặt đường trôi về phía xe đúng `v·Δt` mét.
Phần mềm lấy mẫu độ sáng dọc theo vạch làn (đã nhận diện ở `lane.py`) theo khoảng cách thực 5-26 m,
so hồ sơ "có sơn - khoảng hở" giữa khung hiện tại và khung cách ~0,1 s (tương quan chuẩn hóa, nội suy
dưới mẫu) → `v = độ dịch / Δt`, lấy trung vị trong 1 giây. Vạch liền không có thông tin chuyển động dọc nên
bị bỏ qua; khi chưa đo được (không thấy vạch đứt, ảnh tĩnh) dùng tốc độ chọn tay.
Bật/tắt: ô **Tự đo từ video** trên thẻ *Tốc độ xe của bạn* (hoặc ⚙ Cài đặt → Chung). Bấm một nấc tốc độ
hoặc nói tốc độ với Trợ lý AI ("tôi chạy 90 km/h") = chuyển sang chọn tay.

| Kiểm tra | Kết quả |
|---|---|
| Video tổng hợp, tốc độ biết chính xác 50 / 80 / 110 km/h | 50,1 / 79,9 / 109,9 km/h (`smoke_test.test_speed`) |
| Video thật (VIETMAP S720), so với tốc độ GPS in trên video (71-77 km/h), hiệu chỉnh **tự động** | sai trung bình −4 km/h (≈ −6 %), có số đo ở 99 % khung |
| Cùng video, hiệu chỉnh **thủ công** đang lưu | 53-60 km/h (thấp hơn ≈ 25 %) |

Tốc độ đo được **chỉ đúng khi thang chiều sâu của hiệu chỉnh IPM đúng**: sai bao nhiêu % chiều sâu thì sai
bấy nhiêu % tốc độ - và khoảng cách hiển thị cũng sai đúng chừng đó. Vì vậy tốc độ đo lệch xa tốc độ
thật (đồng hồ xe, GPS) là dấu hiệu cần căn chỉnh lại camera (nên dùng Tự động căn chỉnh).
