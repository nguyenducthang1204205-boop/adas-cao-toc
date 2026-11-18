# Thiết kế hệ thống - Cảnh báo khoảng cách an toàn trên cao tốc (YOLOv11 + IPM)

## 1. Kiến trúc phần mềm - luồng xử lý

```
Video Stream ──► YOLOv11 Detection ──► IPM Distance Calculation ──► Alert Engine ──► GUI
```

```mermaid
flowchart LR
    subgraph S["① Video Stream<br/>adas/stream/sources.py"]
        S1[File video<br/>VideoFileSource]
        S2[Camera USB / RTSP<br/>CameraSource]
        S3[Ảnh<br/>ImageSource]
    end
    subgraph D["② YOLOv11 Detection<br/>adas/detection/detector.py · tracking.py"]
        D1[YOLOv11 models/best.pt<br/>phát hiện + phân loại]
        D2[ByteTrack<br/>gán ID theo thời gian]
    end
    subgraph I["③ IPM Distance Calculation<br/>adas/distance/ ipm.py · lane.py · estimator.py"]
        I0[Nhận diện làn xe chủ<br/>vạch kẻ trên BEV]
        I1[Điểm chạm đất<br/>giữa cạnh dưới bbox]
        I2[Homography H<br/>pixel → mét]
        I3[Làn xe · làm mượt EMA<br/>tốc độ tiếp cận · TTC]
    end
    subgraph A["④ Alert Engine<br/>adas/alert/ thresholds.py · engine.py · violations.py"]
        A1[Ngưỡng theo tốc độ<br/>+ điều kiện đường]
        A2[Phân loại rủi ro<br/>an toàn / cảnh báo / nguy hiểm]
        A3[Chống nhiễu + âm thanh]
        A4[Ghi nhật ký vi phạm]
    end
    subgraph G["⑤ GUI<br/>gui/ (rendering/, widgets/, dialogs/)"]
        G1[Khung màu + nhãn<br/>vùng nguy hiểm, banner]
        G2[Bird's-Eye View]
        G3[Thẻ trạng thái · nhật ký<br/>Trợ lý AI · cấu hình]
    end
    S -- "khung BGR (ndarray), t" --> D
    D -- "List[Detection]<br/>bbox, lớp, độ tin cậy, track_id" --> I
    I -- "List[VehicleState]<br/>khoảng cách m, lệch ngang, TTC" --> A
    A -- "FrameResult<br/>mức cảnh báo, xe phía trước, ngưỡng" --> G
    A4 -.-> DB[(SQLite<br/>data/adas.db)]
    DB -. "cấu hình, ma trận camera" .-> I
    DB -. "ngưỡng, âm thanh" .-> A
    AI[Trợ lý AI<br/>adas/assistant/] -. "SafetyPolicy" .-> A1
```

Điều phối: `gui/worker.py::ProcessingWorker` (luồng nền) đọc khung ① → gọi `adas/pipeline.py::ADASPipeline.process`
(② → ③ → ④) → vẽ ⑤ → gửi `QImage` sang luồng giao diện qua tín hiệu Qt.

| Tầng | Đầu vào → đầu ra | Thuật toán | Thời gian đo được* |
|---|---|---|---|
| ① Video Stream | nguồn → khung BGR + thời điểm t | OpenCV; bám thời gian thực (bỏ khung khi chậm); camera: luồng đọc riêng luôn lấy khung mới nhất | 0,5 ms |
| ② YOLOv11 Detection | khung → danh sách xe (bbox, lớp, ID) | YOLOv11n fine-tune (mAP50 0,84) + ByteTrack | 18,6 ms |
| ③ IPM Distance | khung + danh sách xe → làn xe chủ, tốc độ xe chủ, khoảng cách (m), cùng làn?, TTC | Homography mặt phẳng đường; nhận diện vạch làn trên BEV (top-hat + cửa sổ trượt + đa thức bậc 2); tốc độ từ độ dịch vạch đứt giữa các khung (tương quan chuẩn hóa); EMA; hồi quy tuyến tính d(t) | ≈ 7 ms |
| ④ Alert Engine | khoảng cách → mức cảnh báo, âm thanh, nhật ký | Bảng quy định × hệ số điều kiện; TTC; hysteresis N khung | 0,02 ms |
| ⑤ GUI | kết quả → ảnh hiển thị | QPainter (tiếng Việt), BEV warpPerspective | 8,7 ms |
| **Tổng** | | | **≈ 35 ms/khung ≈ 29 FPS** |

\* Đo trên 600 khung video 640×360, GPU (CUDA). Khi chạy, thanh trạng thái (đáy cửa sổ) hiển thị trực tiếp
`Luồng xử lý (ms): Video Stream → YOLOv11 → IPM → Alert Engine → GUI`.

### Các luồng (thread)

```mermaid
flowchart TB
    GT["Luồng giao diện (Qt)<br/>MainWindow, hộp thoại"] -- "start / stop / tạm dừng<br/>đổi tốc độ, cấu hình" --> WT
    WT["Luồng xử lý - ProcessingWorker (QThread)<br/>① → ② → ③ → ④ → ⑤ vẽ"] -- "frame_ready(QImage, BEV, thống kê)<br/>violation(dict)" --> GT
    CT["Luồng đọc camera (CameraSource)"] -- "khung mới nhất" --> WT
    AT["QThreadPool - Trợ lý AI (Claude / offline)"] -- "SafetyPolicy mới" --> GT
    WT -- "ghi phiên, vi phạm" --> DB[(SQLite WAL)]
    GT -- "cấu hình, nguồn, ma trận camera" --> DB
```

Cấu hình (`AppConfig`) dùng chung theo tham chiếu giữa luồng giao diện và luồng xử lý; mọi thay đổi đi qua
`update_inplace()` nên luồng xử lý thấy giá trị mới ở khung kế tiếp mà không cần khởi động lại.

## 2. Cơ sở dữ liệu

**Hệ quản trị:** SQLite (file `data/adas.db`, có sẵn trong Python, không cần máy chủ - phù hợp phần mềm
chạy trên máy tính trong xe). Giá trị cấu hình và các ma trận 3×3 lưu dạng **JSON** trong cột TEXT.
Chế độ WAL cho phép luồng giao diện đọc trong khi luồng xử lý ghi.

**Khởi tạo:**
```bash
python tools/init_db.py            # tạo lược đồ (nếu chưa có), nâng cấp phiên bản cũ, nạp cấu hình
python tools/init_db.py --reset    # sao lưu CSDL cũ rồi tạo mới
```
Ứng dụng cũng tự khởi tạo khi chạy lần đầu (`adas/storage/database.py::Database.init_schema`), tự nhập
`config/settings.json` cũ và tự nâng cấp lược đồ (phiên bản hiện tại: 3, lưu trong `PRAGMA user_version`).

```mermaid
erDiagram
    video_sources ||--o{ camera_calibrations : "có ma trận camera"
    video_sources ||--o{ monitoring_sessions : "được giám sát trong"
    monitoring_sessions ||--o{ violations : "ghi nhận"
    system_config ||--o{ config_history : "bản chụp khi thay đổi"

    video_sources {
        INTEGER id PK
        TEXT name
        TEXT source_type "video|camera|stream|image"
        TEXT uri UK "đường dẫn / chỉ số / URL"
        TEXT description
        TEXT created_at
        TEXT last_used_at
    }
    camera_calibrations {
        INTEGER id PK
        INTEGER source_id FK
        TEXT created_at
        TEXT method "manual|auto|imported"
        INTEGER frame_width
        INTEGER frame_height
        TEXT intrinsic_matrix "K 3x3 JSON"
        TEXT homography_matrix "H 3x3 JSON pixel->m"
        TEXT rotation_matrix "R 3x3 JSON"
        REAL focal_px
        REAL horizon_y
        REAL camera_height_m
        REAL camera_offset_m
        REAL pitch_deg
        TEXT params_json "4 điểm, W, L, d0..."
        TEXT note
    }
    system_config {
        TEXT section PK
        TEXT key PK
        TEXT value "JSON"
        TEXT updated_at
    }
    config_history {
        INTEGER id PK
        TEXT changed_at
        TEXT reason
        TEXT config_json
    }
    monitoring_sessions {
        INTEGER id PK
        INTEGER source_id FK
        TEXT started_at
        TEXT ended_at
        TEXT source
        TEXT source_type
        TEXT model_weights
        TEXT device
        INTEGER frame_width
        INTEGER frame_height
        INTEGER frames_processed
        REAL avg_fps
        TEXT config_json
    }
    violations {
        INTEGER id PK
        INTEGER session_id FK
        TEXT started_at
        TEXT ended_at
        REAL video_time_s
        REAL duration_s
        TEXT level "warning|danger"
        INTEGER track_id
        TEXT vehicle_class
        REAL distance_m
        REAL min_distance_m
        REAL min_ttc_s
        REAL closing_speed_kmh
        REAL ego_speed_kmh
        REAL safe_threshold_m
        REAL danger_threshold_m
        REAL legal_min_gap_m
        TEXT road_condition
        REAL weather_factor
        TEXT snapshot_path
    }
```

| Nhóm dữ liệu yêu cầu | Bảng |
|---|---|
| **Thông số cấu hình** | `system_config` (hiện hành) + `config_history` (lịch sử, khôi phục được) |
| **Ma trận camera** | `camera_calibrations`: K (nội tham số), H (ma trận IPM), R (tư thế), f, chiều cao, góc chúc, chân trời - theo từng nguồn trong `video_sources`; dòng mới nhất là ma trận đang dùng |
| **Nhật ký cảnh báo** | `violations` (mỗi đợt vi phạm 1 dòng, kèm ảnh) thuộc `monitoring_sessions`; view `v_session_summary` thống kê theo phiên |

Ràng buộc toàn vẹn: khóa ngoại bật (`PRAGMA foreign_keys = ON`); xóa phiên → xóa vi phạm (CASCADE);
xóa nguồn → xóa ma trận camera của nguồn (CASCADE), phiên cũ giữ lại (`source_id` → NULL);
`CHECK` trên `level`, `source_type`, `method`; `uri` duy nhất (đường dẫn file được chuẩn hóa).

### Ma trận camera được tính thế nào
Từ 4 điểm hiệu chỉnh → homography **H** (ảnh → mặt đường, mét). Phân rã ngược
`H⁻¹ ∝ K·[r₁ r₂ t]` (Zhang, 2000) với tâm ảnh ở giữa khung: ràng buộc ‖r₁‖ = ‖r₂‖ cho tiêu cự f
→ **K** = [[f, 0, cx], [0, f, cy], [0, 0, 1]]; tiếp theo **R** = [r₁ r₂ r₁×r₂], vị trí camera C = −Rᵀt
→ chiều cao camera, khoảng cách camera tới đầu xe, góc chúc. Kiểm chứng trên camera giả lập:
tìm lại đúng f, chiều cao, vị trí và góc chúc (`tools/smoke_test.py::test_camera_matrix`).
