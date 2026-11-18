# -*- coding: utf-8 -*-
"""Sơ đồ BPMN: quy trình tổng quát, chuẩn bị giám sát, giám sát và cảnh báo."""
from svgdraw import E, Flow, N

POOL = "Hệ thống cảnh báo khoảng cách an toàn"
DRIVER = "Tài xế"


def bpmn_tong_quat():
    nodes = [
        N("st", "bstart", 0, 0, label="Bắt đầu hành trình"),
        N("p1", "sub", 0, 1, "Chọn nguồn video / camera (UC01)"),
        N("g1", "xor", 1, 2, label="Nguồn đã căn chỉnh?"),
        N("p2", "sub", 0, 3, "Căn chỉnh camera IPM (UC02)"),
        N("g2", "xor", 1, 4),
        N("p3", "sub", 0, 5, "Cấu hình ngưỡng cảnh báo (UC03)"),
        N("p4", "sub", 1, 6, "Giám sát realtime & cảnh báo (UC04)"),
        N("p5", "sub", 0, 7, "Xem lại nhật ký cảnh báo (UC05)"),
        N("en", "bend", 0, 8, label="Kết thúc"),
        N("db", "store", 1, 5, label="CSDL data/adas.db", dc=-38),
    ]
    edges = [
        E("st", "p1"), E("p1", "g1"), E("g1", "p2", "Chưa", route="side", s=-1),
        E("g1", "g2", "Rồi", route="hv_side", s=1, off=30), E("p2", "g2"), E("g2", "p3"), E("p3", "p4"),
        E("p4", "p5"), E("p5", "en"),
        E("p4", "db", style="data"),
    ]
    return Flow("h", [DRIVER, "Phần mềm ADAS"], nodes, edges, lane_size=[170, 190], pool=POOL,
                task_w=120, gap=44)


def bpmn_chuan_bi():
    # Bố cục dọc (làn là cột) để vừa trang A4 khi in
    nodes = [
        N("st", "bstart", 0, 0, label="Bắt đầu"),
        N("t1", "task", 0, 1, "Mở phần mềm, chọn nguồn video / camera"),
        N("t2", "task", 1, 2, "Đăng ký nguồn, nạp căn chỉnh mới nhất của nguồn"),
        N("g1", "xor", 1, 3, label="Đã căn chỉnh?"),
        N("t3", "task", 0, 4, "Căn chỉnh camera: chấm 4 điểm hoặc tự động"),
        N("t4", "task", 1, 5, "Tính H, K, R; lưu ma trận camera"),
        N("g2", "xor", 1, 6),
        N("t5", "task", 0, 7, "Chọn tốc độ, mô tả điều kiện đường"),
        N("t6", "task", 2, 8, "Phân tích mô tả (offline / Claude), đề xuất SafetyPolicy"),
        N("t7", "task", 1, 9, "Áp dụng & lưu ngưỡng, hiển thị khoảng cách an toàn"),
        N("t8", "task", 0, 10, "Bấm “Bắt đầu” giám sát"),
        N("en", "bend", 0, 11, label="Sẵn sàng giám sát"),
        N("db1", "store", 2, 5, label="camera_calibrations", lab_pos="below"),
        N("db2", "store", 2, 9, label="system_config, config_history", lab_pos="below", dc=20),
    ]
    edges = [
        E("st", "t1"), E("t1", "t2"), E("t2", "g1"), E("g1", "t3", "Chưa", route="side", s=-1),
        E("g1", "g2", "Rồi", route="hv_side", s=1, off=80), E("t3", "t4"), E("t4", "g2"), E("g2", "t5"),
        E("t5", "t6"), E("t6", "t7"), E("t7", "t8"), E("t8", "en"),
        E("t4", "db1", style="data"), E("t7", "db2", style="data"),
    ]
    return Flow("v", [DRIVER, "Giao diện ADAS", "Trợ lý AI / CSDL"], nodes, edges, lane_size=[280, 280, 260],
                pool=POOL, task_w=130, gap=30)


def bpmn_giam_sat():
    nodes = [
        N("st", "bstart", 0, 0, label="Bấm “Bắt đầu”"),
        N("t1", "task", 1, 1, "Khởi động luồng xử lý"),
        N("t2", "task", 2, 2, "Mở nguồn, tải YOLOv11, mở phiên giám sát"),
        N("t3", "task", 2, 3, "Đọc khung hình"),
        N("t4", "task", 2, 4, "Nhận diện & bám vết xe (YOLOv11 + ByteTrack)"),
        N("t5", "task", 2, 5, "Xác định làn, tính khoảng cách IPM, TTC"),
        N("g1", "xor", 2, 6, label="Có cảnh báo / nguy hiểm?"),
        N("t6", "task", 2, 7, "Phát âm thanh cảnh báo"),
        N("t7", "task", 2, 8, "Ghi / cập nhật đợt vi phạm + ảnh"),
        N("g2", "xor", 2, 9),
        N("t8", "task", 1, 10, "Hiển thị khung màu, banner, BEV, thẻ trạng thái"),
        N("g3", "xor", 1, 11, label="Dừng / hết video?"),
        N("t9", "task", 2, 12, "Đóng đợt vi phạm, kết thúc phiên"),
        N("t10", "task", 1, 13, "Báo số vi phạm đã ghi"),
        N("en", "bend", 0, 14, label="Kết thúc giám sát"),
        N("nt", "note", 0, 10, "Tài xế quan sát cảnh báo, giảm tốc / giữ khoảng cách; có thể Tạm dừng / Dừng",
          w=150),
        N("db1", "store", 1, 2, label="monitoring_sessions", lab_pos="below"),
        N("db2", "store", 1, 8, label="violations, snapshots", lab_pos="below"),
        N("db3", "store", 1, 12, label="monitoring_sessions", lab_pos="below", dc=-80),
    ]
    edges = [
        E("st", "t1"), E("t1", "t2"), E("t2", "t3"), E("t3", "t4"), E("t4", "t5"), E("t5", "g1"),
        E("g1", "t6", "Có"), E("g1", "g2", "Không (an toàn)", route="hv_side", s=1, off=36),
        E("t6", "t7"), E("t7", "g2"), E("g2", "t8"), E("t8", "g3"),
        E("g3", "t3", "Chưa", route="loop", s=-1, off=64), E("g3", "t9", "Có", route="side", s=1),
        E("t9", "t10"), E("t10", "en"),
        E("t2", "db1", style="data"), E("t7", "db2", style="data"), E("t9", "db3", style="data"),
        E("nt", "t8", style="assoc"),
    ]
    return Flow("v", [DRIVER, "Giao diện ADAS", "Luồng xử lý ADAS"], nodes, edges, lane_size=[270, 300, 300],
                pool=POOL, task_w=130, gap=28)


DIAGRAMS = {
    "02_bpmn_quy_trinh_tong_quat": bpmn_tong_quat,
    "03_bpmn_chuan_bi_giam_sat": bpmn_chuan_bi,
    "04_bpmn_giam_sat_canh_bao": bpmn_giam_sat,
}
