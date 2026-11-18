# -*- coding: utf-8 -*-
"""Sơ đồ hoạt động (có làn) cho UC01-UC05 và luồng xử lý một khung hình."""
from svgdraw import E, Flow, N

U, S = "Người dùng", "Hệ thống"


def hd_uc01():
    B = 215   # lệch của nhánh phụ trong làn Hệ thống
    nodes = [
        N("st", "start", 0, 0),
        N("a1", "act", 0, 1, "Mở menu nguồn ▾ trên thanh tiêu đề, chọn “Quản lý nguồn…”"),
        N("a2", "act", 1, 2, "Mở SourceDialog; đọc bảng video_sources; hiển thị tên, loại, địa chỉ, "
                             "căn chỉnh, số phiên, lần dùng gần nhất"),
        N("a3", "act", 0, 3, "Bấm “Thêm file video” hoặc “Thêm camera / URL”; chọn file hoặc nhập tên, "
                             "địa chỉ (0, 1… / rtsp://…), ghi chú"),
        N("a4", "act", 1, 4, "Phân loại nguồn (classify_source), chuẩn hóa địa chỉ (normalize_source)"),
        N("d1", "decision", 1, 5, "Hợp lệ và chưa có?"),
        N("e1", "act", 1, 5, "Báo lỗi: “Chưa nhập địa chỉ nguồn” / “Không tìm thấy file” / "
                             "“Nguồn này đã có trong danh sách”", dc=B, w=150),
        N("a5", "act", 1, 6, "Thêm dòng vào video_sources; làm mới bảng"),
        N("a6", "act", 0, 7, "Chọn nguồn, bấm “Kiểm tra kết nối”"),
        N("a7", "act", 1, 8, "Mở nguồn ở luồng nền (probe_source), đọc thử một khung"),
        N("d2", "decision", 1, 9, "Kết nối được?"),
        N("e2", "act", 1, 9, "Hiển thị “Không kết nối được: <lỗi>”", dc=B, w=150),
        N("a8", "act", 1, 10, "Hiển thị khung xem trước, độ phân giải, FPS, số khung"),
        N("a9", "act", 0, 11, "Bấm “Mở nguồn đã chọn” (hoặc nhấp đúp vào dòng)"),
        N("a10", "act", 1, 12, "Dừng phiên đang chạy (nếu có), đặt nguồn mới làm nguồn hiện hành"),
        N("a11", "act", 1, 13, "Đăng ký nguồn, nạp căn chỉnh mới nhất của nguồn, bắt đầu giám sát (UC04)"),
        N("en", "end", 1, 14),
    ]
    edges = [
        E("st", "a1"), E("a1", "a2"), E("a2", "a3"), E("a3", "a4"), E("a4", "d1"),
        E("d1", "e1", "[Không]"), E("d1", "a5", "[Có]"), E("e1", "a3", route="loop", s=1, off=16),
        E("a5", "a6"), E("a6", "a7"), E("a7", "d2"),
        E("d2", "e2", "[Không]"), E("d2", "a8", "[Có]"), E("e2", "a6", route="loop", s=1, off=16),
        E("a8", "a9"), E("a9", "a10"), E("a10", "a11"), E("a11", "en"),
    ]
    return Flow("v", [U, S], nodes, edges, lane_size=[320, 680], act_w=180)


def hd_uc02():
    B = 215
    nodes = [
        N("st", "start", 0, 0),
        N("b1", "act", 0, 1, "Bấm “Căn chỉnh camera” (hoặc “Căn chỉnh ngay” trên thanh nhắc)"),
        N("b2", "act", 1, 2, "Lấy khung hình: khung đang giám sát → khung đầu của nguồn đã chọn → "
                             "hộp chọn ảnh / video"),
        N("d1", "decision", 1, 3, "Có khung hình?"),
        N("e1", "act", 1, 3, "Báo “Không đọc được khung hình”", dc=B, w=150),
        N("x1", "end", 1, 4, dc=B),
        N("b3", "act", 1, 4, "Tạm dừng luồng xử lý; mở CalibrationDialog với khung hình và 4 điểm hiện tại"),
        N("d2", "decision", 0, 5, "Cách căn chỉnh?"),
        N("b4", "act", 0, 6, "Chấm / kéo 4 điểm trên 2 vạch làn (gần trái → gần phải → xa phải → xa trái); "
                             "nhập W = 3,75 m, L, d₀, nửa làn, tầm đo, camera → đầu xe", dc=-115),
        N("b5", "act", 0, 6, "Bấm “Tự động căn chỉnh”, nhập tốc độ xe trong video (0 nếu không biết)", dc=150),
        N("b6", "act", 1, 7, "Phân tích video ở luồng nền: điểm tụ (Hough + RANSAC), bề rộng làn → chiều cao "
                             "camera, dịch chuyển vạch đứt → K = f·h"),
        N("d3", "decision", 1, 8, "Thành công?"),
        N("b7", "act", 1, 9, "Tự điền 4 điểm và thông số; method = auto, note = báo cáo tự căn chỉnh"),
        N("m1", "merge", 1, 10),
        N("b8", "act", 1, 11, "Tính homography H; vẽ Bird's-Eye View (lưới 10 m), chân trời, f, chiều cao, "
                              "góc chúc camera"),
        N("d4", "decision", 1, 12, "Đủ 4 điểm hợp lệ?"),
        N("b9", "act", 0, 13, "Kiểm tra vạch làn trên BEV song song, thẳng đứng; bấm “Áp dụng” hoặc “Hủy”"),
        N("d5", "decision", 1, 14, "Áp dụng?"),
        N("b10", "act", 1, 14, "Đóng hộp thoại, giữ nguyên căn chỉnh cũ", dc=B, w=150),
        N("b11", "act", 1, 15, "update_inplace(cfg.calibration); lưu system_config + config_history "
                               "“Căn chỉnh camera (IPM)”"),
        N("b12", "act", 1, 16, "Phân rã H → K, R; thêm dòng camera_calibrations (manual / auto) cho nguồn"),
        N("b13", "act", 1, 17, "Báo luồng xử lý calibration_changed(): dựng lại IPM ở khung kế tiếp"),
        N("m2", "merge", 1, 18),
        N("b14", "act", 1, 19, "Bỏ tạm dừng, tiếp tục giám sát"),
        N("en", "end", 1, 20),
    ]
    edges = [
        E("st", "b1"), E("b1", "b2"), E("b2", "d1"),
        E("d1", "e1", "[Không]"), E("e1", "x1"), E("d1", "b3", "[Có]"),
        E("b3", "d2"),
        E("d2", "b4", "[Thủ công]", route="side", s=-1), E("d2", "b5", "[Tự động]", route="side", s=1),
        E("b5", "b6"), E("b6", "d3"),
        E("d3", "b4", "[Không] báo lỗi, đề nghị chấm thủ công", route="loop", s=-1, off=34),
        E("d3", "b7", "[Có]"), E("b7", "m1"), E("b4", "m1"), E("m1", "b8"), E("b8", "d4"),
        E("d4", "b4", "[Không] khóa nút Áp dụng", route="loop", s=-1, off=18),
        E("d4", "b9", "[Có]", route="z"), E("b9", "d5"),
        E("d5", "b10", "[Hủy]"), E("d5", "b11", "[Áp dụng]"), E("b11", "b12"), E("b12", "b13"),
        E("b13", "m2"), E("b10", "m2"), E("m2", "b14"), E("b14", "en"),
    ]
    return Flow("v", [U, S], nodes, edges, lane_size=[560, 680], act_w=180, gap=34)


def hd_uc03a():
    nodes = [
        N("st", "start", 0, 0),
        N("d0", "decision", 0, 1, "Muốn đổi gì?"),
        N("u1", "act", 0, 2, "Bấm “Cài đặt” trên thanh tiêu đề", dc=-140),
        N("u2", "act", 0, 2, "Chọn nấc tốc độ trên thẻ “Tốc độ xe của bạn”: 60 / ≤80 / ≤100 / ≤120 km/h", dc=140),
        N("s1", "act", 1, 3, "cfg.speed_kmh = v; compute_thresholds → hiển thị “Cảnh báo < X m · Nguy hiểm "
                             "< Y m” và căn cứ (quy định / quy tắc 2 giây)", dc=165),
        N("s2", "act", 1, 4, "Mở SettingsDialog: 4 tab Chung, Điều kiện đường, Trợ lý AI, Nâng cao "
                             "(nạp cấu hình hiện hành)", dc=-130),
        N("u3", "act", 0, 5, "Tab “Chung”: chọn loại xe theo dõi, bật/tắt và nghe thử âm thanh, chỉ cảnh báo "
                             "cùng làn, tự nhận diện làn", dc=-140),
        N("u4", "act", 0, 6, "Tab “Điều kiện đường”: chọn thời tiết / mặt đường (5 mẫu), tầm nhìn xa", dc=-140),
        N("s3", "act", 1, 7, "Tự điền hệ số điều kiện, μ, TTC cảnh báo / nguy hiểm; hiển thị tóm tắt ngưỡng",
          dc=-130),
        N("u5", "act", 0, 8, "Tab “Nâng cao” (nếu cần): mô hình, độ tin cậy, IoU, hệ số, μ, giãn cách, tỷ lệ "
                             "nguy hiểm, TTC, chống báo nhầm; bấm “Lưu”", dc=-140),
        N("s4", "act", 1, 9, "Ràng buộc: TTC nguy hiểm ≤ TTC cảnh báo − 0,5 s; bỏ chọn hết loại xe → giữ “car”",
          dc=-130),
        N("s5", "act", 1, 10, "update_inplace(cfg); lưu system_config + config_history “Cài đặt hệ thống”",
          dc=-130),
        N("s6", "act", 1, 11, "Cập nhật thẻ tốc độ và điều kiện đường; báo luồng xử lý classes_changed(), "
                              "calibration_changed()", dc=-130),
        N("m", "merge", 1, 12),
        N("s7", "act", 1, 13, "Luồng xử lý đọc cfg.policy, cfg.speed_kmh ở khung kế tiếp → ngưỡng mới có hiệu lực"),
        N("en", "end", 1, 14),
    ]
    edges = [
        E("st", "d0"), E("d0", "u1", "[Tham số]", route="side", s=-1),
        E("d0", "u2", "[Tốc độ]", route="side", s=1),
        E("u2", "s1"), E("u1", "s2"), E("s2", "u3"), E("u3", "u4"), E("u4", "s3"), E("s3", "u5"),
        E("u5", "s4"), E("s4", "s5"), E("s5", "s6"), E("s6", "m"), E("s1", "m"), E("m", "s7"), E("s7", "en"),
    ]
    return Flow("v", [U, S], nodes, edges, lane_size=[560, 600], act_w=170)


def hd_uc03b():
    nodes = [
        N("st", "start", 0, 0),
        N("u1", "act", 0, 1, "Bấm 1 trong 8 nút điều kiện đường (Khô ráo, Mưa nhỏ, Mưa to, Sương mù, Trơn "
                             "trượt, Ban đêm, Chở nặng, Mệt mỏi) hoặc gõ mô tả vào khung chat"),
        N("g1", "act", 1, 2, "ChatPanel.submit(text): hiện câu hỏi, khóa nút Gửi"),
        N("g2", "act", 1, 3, "Chạy _AssistantTask trên QThreadPool kèm chính sách, tốc độ hiện tại và mô tả "
                             "cảnh quan (xe phía trước, TTC, mức cảnh báo)"),
        N("d1", "decision", 2, 4, "Dùng Claude (use_cloud)?"),
        N("c1", "act", 2, 5, "Gọi Claude API: messages.create, đầu ra JSON theo RESPONSE_SCHEMA, effort low",
          dc=120),
        N("d2", "decision", 2, 6, "Thành công?", dc=120),
        N("o1", "act", 2, 7, "Tư vấn offline: nhận diện từ khóa tiếng Việt (có / không dấu), tốc độ, tầm nhìn "
                             "→ condition_policy", dc=-120),
        N("c2", "act", 2, 7, "Đọc JSON: reply, policy, speed_kmh", dc=120),
        N("m", "merge", 2, 8),
        N("a1", "act", 2, 9, "clamp_policy: giới hạn tham số theo LIMITS; trả AssistantResult"),
        N("g3", "act", 1, 10, "Hiển thị trả lời; update_inplace(cfg.policy); đổi tốc độ nếu tài xế có nêu"),
        N("g4", "act", 1, 11, "Tính lại ngưỡng, báo “Đã áp dụng: … → ở V km/h: cảnh báo < X m, nguy hiểm < Y m”"),
        N("g5", "act", 1, 12, "Lưu system_config + config_history “Trợ lý AI (nguồn): điều kiện”"),
        N("u2", "act", 0, 13, "Xem ngưỡng mới trên thẻ “Tốc độ xe của bạn” và “Điều kiện đường”"),
        N("en", "end", 0, 14),
    ]
    edges = [
        E("st", "u1"), E("u1", "g1"), E("g1", "g2"), E("g2", "d1"),
        E("d1", "o1", "[Không – mặc định]", route="side", s=-1), E("d1", "c1", "[Có]", route="side", s=1),
        E("c1", "d2"), E("d2", "o1", "[Lỗi / không có mạng]", route="side", s=-1), E("d2", "c2", "[Có]"),
        E("o1", "m"), E("c2", "m"), E("m", "a1"), E("a1", "g3"), E("g3", "g4"), E("g4", "g5"), E("g5", "u2"),
        E("u2", "en"),
    ]
    return Flow("v", [U, "Giao diện (MainWindow)", "Trợ lý AI (offline / Claude)"], nodes, edges,
                lane_size=[300, 330, 520], act_w=170)


def hd_uc04():
    L = -100   # cột chính trong làn Giao diện
    nodes = [
        N("st", "start", 0, 0),
        N("u1", "act", 0, 1, "Bấm “Bắt đầu” (F5); có thể bật “Ghi video” trước"),
        N("d1", "decision", 1, 2, "Đã chọn nguồn?", dc=L),
        N("g0", "act", 1, 2, "Mở hộp chọn file video (UC01)", dc=150),
        N("x0", "end", 1, 3, dc=150),
        N("g1", "act", 1, 3, "Đăng ký nguồn (register_source); nạp căn chỉnh mới nhất của nguồn", dc=L),
        N("g2", "act", 1, 4, "Tạo và khởi động ProcessingWorker (QThread); hiện “Đang mở nguồn và tải mô hình…”",
          dc=L),
        N("w1", "act", 2, 5, "Mở nguồn (open_source); tải YOLOv11 models/best.pt (GPU nếu có, dự phòng "
                             "yolo11n.pt); warmup"),
        N("d2", "decision", 2, 6, "Mở được?"),
        N("g3", "act", 1, 6, "Hộp thoại “Lỗi xử lý: …”", dc=150),
        N("x1", "end", 1, 7, dc=150),
        N("w2", "act", 2, 7, "Đọc khung đầu; tạo ADASPipeline; mở phiên monitoring_sessions (lưu cấu hình lúc "
                             "chạy); tạo ViolationRecorder"),
        N("w3", "act", 2, 8, "① Đọc khung hình (bám nhịp thời gian thực, bỏ khung khi chậm)"),
        N("w4", "act", 2, 9, "② YOLOv11 + ByteTrack: bbox, lớp, độ tin cậy, track_id"),
        N("w5", "act", 2, 10, "③ Nhận diện làn xe chủ; IPM điểm chạm đất → khoảng cách, lệch ngang; EMA, "
                              "tốc độ tiếp cận, TTC"),
        N("w6", "act", 2, 11, "④ Ngưỡng theo tốc độ & điều kiện; phân loại rủi ro; chọn xe phía trước cùng làn"),
        N("w7", "act", 2, 12, "Chống nhiễu: nâng mức khi kéo dài ≥ 0,1 s (≥ 2 khung), giữ ≥ 0,8 s mới hạ; phát bíp "
                              "820 Hz / 1250 Hz"),
        N("w8", "act", 2, 13, "Ghi nhật ký: mở / cập nhật / đóng đợt vi phạm (bảng violations) + ảnh bằng chứng"),
        N("w9", "act", 2, 14, "⑤ Vẽ khung màu, nhãn, vùng nguy hiểm, banner, BEV; ghi video nếu bật; "
                              "phát tín hiệu frame_ready"),
        N("g4", "act", 1, 15, "Hiển thị video + BEV, thẻ trạng thái, thời gian 5 tầng, nhật ký vi phạm của phiên",
          dc=L),
        N("u2", "act", 0, 15, "Theo dõi cảnh báo; có thể “Tạm dừng” (Space) hoặc “Dừng” (Esc)"),
        N("d3", "decision", 2, 16, "Còn khung và chưa dừng?"),
        N("w10", "act", 2, 17, "Đóng đợt vi phạm đang mở; kết thúc phiên (số khung, FPS trung bình); giải phóng "
                               "nguồn, đóng file video"),
        N("g5", "act", 1, 18, "Báo “Phiên #id: đã ghi n vi phạm vào CSDL”; trở về trạng thái chờ", dc=L),
        N("en", "end", 1, 19, dc=L),
    ]
    edges = [
        E("st", "u1"), E("u1", "d1"), E("d1", "g0", "[Chưa]"), E("g0", "x0"), E("d1", "g1", "[Rồi]"),
        E("g1", "g2"), E("g2", "w1"), E("w1", "d2"), E("d2", "g3", "[Không]"), E("g3", "x1"),
        E("d2", "w2", "[Có]"), E("w2", "w3"), E("w3", "w4"), E("w4", "w5"), E("w5", "w6"), E("w6", "w7"),
        E("w7", "w8"), E("w8", "w9"), E("w9", "g4", "frame_ready", style="msg", route="side", s=-1),
        E("w9", "d3"), E("g4", "u2"),
        E("u2", "d3", "stop() / set_paused()", style="msg", route="z"),
        E("d3", "w3", "[Có]", route="loop", s=1, off=26),
        E("d3", "w10", "[Không]"), E("w10", "g5"), E("g5", "en"),
    ]
    return Flow("v", [U, "Giao diện (MainWindow)", "Luồng xử lý (ProcessingWorker)"], nodes, edges,
                lane_size=[290, 520, 380], act_w=170, gap=34)


def hd_uc05():
    X = [-300, -100, 100, 300]
    nodes = [
        N("st", "start", 0, 0),
        N("u1", "act", 0, 1, "Bấm “Lịch sử” (thanh tiêu đề hoặc tab “Vi phạm”)"),
        N("s1", "act", 1, 2, "Mở HistoryDialog; đọc thống kê (stats) và danh sách phiên (v_session_summary), "
                             "dòng đầu “Tất cả phiên”"),
        N("u2", "act", 0, 3, "Chọn phiên; đặt bộ lọc: từ ngày – đến ngày, mức (nguy hiểm / cảnh báo), loại xe"),
        N("s2", "act", 1, 4, "list_violations theo phiên và bộ lọc; hiển thị bảng vi phạm, số vi phạm khớp lọc"),
        N("u3", "act", 0, 5, "Chọn một vi phạm"),
        N("s3", "act", 1, 6, "Hiển thị ảnh bằng chứng (snapshot_path) và tóm tắt; ảnh đã bị xóa → để trống"),
        N("d1", "decision", 0, 7, "Thao tác tiếp?"),
        N("b1", "act", 1, 8, "Hộp chọn nơi lưu; ghi CSV UTF-8 BOM (không có vi phạm → báo “Không có vi phạm "
                             "nào để xuất”)", dc=X[0]),
        N("b2", "act", 1, 8, "Sau khi xác nhận: xóa vi phạm / phiên (CASCADE) và file ảnh; làm mới danh sách",
          dc=X[1]),
        N("b3", "act", 1, 8, "Tab “Lịch sử cấu hình”: xem bản chụp JSON; “Khôi phục cấu hình này” → "
                             "update_inplace(cfg), lưu", dc=X[2]),
        N("b4", "act", 1, 8, "Tab “Ma trận camera”: hiển thị K, H, R, f, chiều cao, góc chúc, chân trời",
          dc=X[3]),
        N("m1", "merge", 1, 9),
        N("m2", "merge", 0, 10),
        N("en", "end", 0, 11),
    ]
    edges = [
        E("st", "u1"), E("u1", "s1"), E("s1", "u2"), E("u2", "s2"), E("s2", "u3"), E("u3", "s3"),
        E("s3", "d1"),
        E("d1", "b1", "[Xuất CSV]", route="side", s=1, lab_end=True),
        E("d1", "b2", "[Xóa]", route="side", s=1, lab_end=True),
        E("d1", "b3", "[Khôi phục]", route="side", s=1, lab_end=True),
        E("d1", "b4", "[Ma trận]", route="side", s=1, lab_end=True),
        E("b1", "m1"), E("b2", "m1"), E("b3", "m1"), E("b4", "m1"),
        E("d1", "m2", "[Đóng]"), E("m1", "m2"), E("m2", "en"),
    ]
    return Flow("v", [U, S], nodes, edges, lane_size=[300, 860], act_w=150)


def hd_xu_ly_khung():
    nodes = [
        N("st", "start", 0, 0),
        N("a1", "act", 0, 1, "Nhận khung BGR và thời điểm t từ nguồn"),
        N("a2", "act", 0, 2, "VehicleDetector.detect: YOLOv11 model.track(persist=True) → bbox, lớp, độ tin cậy, "
                             "track_id (ByteTrack)"),
        N("a3", "act", 0, 3, "Giữ các lớp đang bật (mặc định car, truck, bus, Jeepney)"),
        N("d1", "decision", 1, 4, "auto_lane bật?"),
        N("b1", "act", 1, 5, "EgoLaneDetector.update: BEV mét, top-hat, che hộp xe, cửa sổ trượt, "
                             "X = c0 + c1·Y + c2·Y²; cần 3 khung liên tiếp để xác nhận", dc=-135),
        N("b2", "act", 1, 5, "Không dùng làn: hành lang cố định ±lane_half_width_m", dc=140),
        N("m1", "merge", 1, 6),
        N("b3", "act", 1, 7, "Với mỗi xe: điểm chạm đất = trung điểm cạnh dưới bbox"),
        N("d2", "decision", 1, 8, "Dưới chân trời và ≤ max_range?"),
        N("b4", "act", 1, 9, "IPM: image_to_ground → Y (khoảng cách, m), X (lệch ngang, m); method = IPM",
          dc=-135),
        N("b5", "act", 1, 9, "Pinhole với focal_px; method = “Xa”, khoảng cách ≥ max_range_m", dc=140),
        N("m2", "merge", 1, 10),
        N("b6", "act", 1, 11, "EMA α = 0,35 theo track_id; hồi quy tuyến tính 1 s → tốc độ tiếp cận; "
                              "TTC = d / v_tiếp cận"),
        N("b7", "act", 1, 12, "in_ego_lane = làn chứa (X, Y) (hoặc |X| ≤ nửa làn); sắp xếp xe gần → xa"),
        N("c1", "act", 2, 13, "compute_thresholds(speed_kmh, policy) → safe_m, danger_m"),
        N("d3", "decision", 2, 14, "Ngoài làn hoặc “Xa”?"),
        N("c2", "act", 2, 15, "risk = info (không cảnh báo)", dc=140),
        N("c3", "act", 2, 15, "classify_risk: danger nếu d < danger hoặc TTC < TTC nguy hiểm; warning nếu "
                              "d < safe hoặc TTC < TTC cảnh báo; còn lại safe", dc=-120),
        N("c4", "act", 2, 16, "raw_level = mức cao nhất; lead = xe cùng làn gần nhất"),
        N("c5", "act", 2, 17, "AlertManager.update: nâng mức sau escalate_seconds giây, hạ sau hold_seconds; "
                              "phát bíp theo mức"),
        N("c6", "act", 2, 18, "Trả FrameResult (vehicles, lead, lane, thresholds, raw_level, level, timings_ms)"),
        N("en", "end", 2, 19),
    ]
    edges = [
        E("st", "a1"), E("a1", "a2"), E("a2", "a3"), E("a3", "d1"),
        E("d1", "b1", "[Có]", route="side", s=-1), E("d1", "b2", "[Không]", route="side", s=1),
        E("b1", "m1"), E("b2", "m1"), E("m1", "b3"), E("b3", "d2"),
        E("d2", "b4", "[Có]", route="side", s=-1), E("d2", "b5", "[Không]", route="side", s=1),
        E("b4", "m2"), E("b5", "m2"), E("m2", "b6"), E("b6", "b7"), E("b7", "c1"), E("c1", "d3"),
        E("d3", "c2", "[Có]", route="side", s=1), E("d3", "c3", "[Không]", route="side", s=-1),
        E("c3", "c4", route="z"), E("c2", "c4", route="down_side", s=-1), E("c4", "c5"), E("c5", "c6"),
        E("c6", "en"),
    ]
    return Flow("v", ["② Nhận diện (detection/)", "③ Khoảng cách (distance/: lane, ipm, estimator)",
                      "④ Cảnh báo (alert/: thresholds, engine)"], nodes, edges, lane_size=[300, 580, 560], act_w=170)


DIAGRAMS = {
    "11_hoat_dong_UC01_nguon_video": hd_uc01,
    "12_hoat_dong_UC02_cau_hinh_IPM": hd_uc02,
    "13a_hoat_dong_UC03_cai_dat_nguong": hd_uc03a,
    "13b_hoat_dong_UC03_tro_ly_AI": hd_uc03b,
    "14_hoat_dong_UC04_giam_sat": hd_uc04,
    "15_hoat_dong_UC05_nhat_ky": hd_uc05,
    "16_hoat_dong_xu_ly_mot_khung": hd_xu_ly_khung,
}
