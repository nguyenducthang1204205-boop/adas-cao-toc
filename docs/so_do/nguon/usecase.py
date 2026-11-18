# -*- coding: utf-8 -*-
"""Sơ đồ use case tổng quát và phân rã 5 use case (UC01-UC05)."""
from svgdraw import UseCaseDiagram

USER = "Người dùng (tài xế / người vận hành)"
CAM = "Camera / nguồn video"
CLAUDE = "Dịch vụ Claude API"
SYSTEM = "Hệ thống cảnh báo khoảng cách an toàn (YOLOv11 + IPM)"


def uc_tong_quat():
    ucs = [
        ("u1", 520, 110, "UC01. Quản lý nguồn video/camera"),
        ("u4", 520, 215, "UC04. Giám sát realtime & cảnh báo"),
        ("u2", 520, 320, "UC02. Cấu hình thông số IPM (căn chỉnh camera)", 200),
        ("u3", 520, 425, "UC03. Cấu hình ngưỡng cảnh báo"),
        ("u5", 520, 530, "UC05. Quản lý nhật ký cảnh báo"),
    ]
    actors = [("user", 110, 320, USER), ("cam", 930, 165, CAM), ("ai", 930, 425, CLAUDE)]
    links = [("user", u, "assoc") for u in ("u1", "u2", "u3", "u4", "u5")]
    links += [("cam", "u1", "assoc"), ("cam", "u4", "assoc"), ("ai", "u3", "assoc")]
    return UseCaseDiagram(1040, 610, (250, 30, 540, 560, SYSTEM), actors, ucs, links)


def _phan_ra(base, subs, actors, extra_links, W=1120, row=74, top=95, base_x=330, sub_x=790, H=None, arc=150):
    """base = (id, text); subs = [(id, text, kiểu)] kiểu include: base→sub, extend: sub→base."""
    n = len(subs)
    H = H or top + n * row + 30
    mid = top + (n - 1) * row / 2
    ucs = [(base[0], base_x, mid, base[1], 180)]
    links = []
    for i, (sid, text, kind) in enumerate(subs):
        k = ((i - (n - 1) / 2) / max((n - 1) / 2, 1)) ** 2   # xếp theo cung tròn quanh use case gốc
        ucs.append((sid, sub_x - arc * k, top + i * row, text, 220))
        links.append((base[0], sid, "include") if kind == "include" else (sid, base[0], "extend"))
    acts = []
    for aid, name, side, y in actors:
        acts.append((aid, 80 if side == "L" else W - 80, mid if y is None else y, name))
    links = [(a[0], base[0], "assoc") for a in actors if a[2] == "L"] + links + extra_links
    return UseCaseDiagram(W, H, (175, 20, W - 350, H - 35, SYSTEM), acts, ucs, links)


def uc01():
    subs = [
        ("s1", "Xem danh sách nguồn (tên, loại, địa chỉ, căn chỉnh, số phiên)", "include"),
        ("s2", "Thêm file video / ảnh", "extend"),
        ("s3", "Thêm camera USB / URL RTSP-HTTP", "extend"),
        ("s4", "Dò camera USB (chỉ số 0-4)", "extend"),
        ("s5", "Kiểm tra kết nối & xem trước", "extend"),
        ("s6", "Sửa thông tin nguồn", "extend"),
        ("s7", "Xóa nguồn", "extend"),
        ("s8", "Mở nguồn để giám sát", "extend"),
        ("s9", "Mở nhanh: video / ảnh / camera / nguồn dùng gần đây", "extend"),
    ]
    actors = [("user", USER, "L", None), ("cam", CAM, "R", 390)]
    extra = [("cam", "s4", "assoc"), ("cam", "s5", "assoc")]
    return _phan_ra(("b", "UC01. Quản lý nguồn video/camera"), subs, actors, extra)


def uc02():
    subs = [
        ("s1", "Lấy khung hình tham chiếu (khung đang chạy / khung đầu / chọn file)", "include"),
        ("s2", "Chấm 4 điểm trên vạch làn & nhập kích thước thực", "extend"),
        ("s3", "Tự động căn chỉnh từ video", "extend"),
        ("s4", "Chấm lại / về vị trí mặc định", "extend"),
        ("s5", "Tính H, xem trước Bird's-Eye View", "include"),
        ("s6", "Lưu ma trận camera K, H, R theo nguồn", "include"),
        ("s7", "Tự nạp căn chỉnh khi mở lại nguồn", "extend"),
    ]
    actors = [("user", USER, "L", None)]
    return _phan_ra(("b", "UC02. Cấu hình thông số IPM (căn chỉnh camera)"), subs, actors, [])


def uc03():
    subs = [
        ("s3", "Hỏi Trợ lý AI gợi ý ngưỡng", "extend"),
        ("s2", "Chọn nhanh điều kiện đường (8 nút)", "extend"),
        ("s1", "Chọn tốc độ xe chủ (60 / ≤80 / ≤100 / ≤120 km/h)", "extend"),
        ("s4", "Tinh chỉnh tham số trong Cài đặt", "extend"),
        ("s5", "Bật/tắt và nghe thử âm thanh cảnh báo", "extend"),
        ("s6", "Khôi phục ngưỡng mặc định", "extend"),
        ("s7", "Tính lại & hiển thị ngưỡng cảnh báo / nguy hiểm", "include"),
    ]
    actors = [("user", USER, "L", None), ("ai", CLAUDE, "R", 95)]
    d = _phan_ra(("b", "UC03. Cấu hình ngưỡng cảnh báo"), subs, actors, [], sub_x=700, W=1300)
    # Gọi Claude API mở rộng cho Hỏi Trợ lý AI (mặc định trợ lý offline)
    d.ucs.append(("s8",) + _uc_shape(d, "s8", 1010, 95, "Gọi Claude API (tùy chọn, lỗi → offline)"))
    d.links += [("s2", "s3", "include"), ("s8", "s3", "extend"), ("ai", "s8", "assoc")]
    return d


def _uc_shape(d, uid, x, y, text):
    from svgdraw import wrap, block_size
    lines = wrap(text, 150, d.FS)
    tw, th = block_size(lines, d.FS)
    rx, ry = max(tw / 2 + 28, 78), max(th / 2 + 15, 26)
    d.shapes[uid] = ("e", x, y, rx, ry)
    return (x, y, lines, rx, ry)


def uc04():
    subs = [
        ("s1", "Đọc khung hình từ nguồn", "include"),
        ("s2", "Nhận diện & bám vết xe (YOLOv11 + ByteTrack)", "include"),
        ("s3", "Nhận diện làn xe chủ từ vạch kẻ", "include"),
        ("s4", "Tính khoảng cách IPM, tốc độ tiếp cận, TTC", "include"),
        ("s5", "Phân loại mức rủi ro theo ngưỡng", "include"),
        ("s6", "Cảnh báo hình ảnh & âm thanh", "include"),
        ("s7", "Ghi nhật ký vi phạm + ảnh bằng chứng", "include"),
        ("s8", "Tạm dừng / tiếp tục", "extend"),
        ("s9", "Ghi video kết quả", "extend"),
        ("s10", "Bật/tắt âm thanh", "extend"),
    ]
    actors = [("user", USER, "L", None), ("cam", CAM, "R", 95)]
    return _phan_ra(("b", "UC04. Giám sát realtime & cảnh báo"), subs, actors, [("cam", "s1", "assoc")], row=70)


def uc05():
    subs = [
        ("s1", "Xem thống kê & danh sách phiên giám sát", "include"),
        ("s2", "Lọc vi phạm theo ngày, mức, loại xe", "extend"),
        ("s3", "Xem ảnh bằng chứng", "extend"),
        ("s4", "Xuất CSV", "extend"),
        ("s5", "Xóa vi phạm / xóa phiên", "extend"),
        ("s6", "Xem & khôi phục lịch sử cấu hình", "extend"),
        ("s7", "Xem ma trận camera (K, H, R)", "extend"),
        ("s8", "Xem vi phạm của phiên đang chạy", "extend"),
    ]
    actors = [("user", USER, "L", None)]
    return _phan_ra(("b", "UC05. Quản lý nhật ký cảnh báo"), subs, actors, [])


DIAGRAMS = {
    "05_usecase_tong_quat": uc_tong_quat,
    "06_usecase_UC01_nguon_video": uc01,
    "07_usecase_UC02_cau_hinh_IPM": uc02,
    "08_usecase_UC03_nguong_canh_bao": uc03,
    "09_usecase_UC04_giam_sat": uc04,
    "10_usecase_UC05_nhat_ky": uc05,
}
