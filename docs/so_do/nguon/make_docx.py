# -*- coding: utf-8 -*-
"""Gom các sơ đồ PNG trong docs/so_do/ vào docs/SO_DO_HE_THONG.docx (mỗi hình một trang, có chú thích)."""
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt
from PIL import Image

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
DOCX = OUT.parent / "SO_DO_HE_THONG.docx"

GROUPS = [
    ("1. Kiến trúc hệ thống", [
        ("01_kien_truc_tong_the", "Kiến trúc phần mềm 5 tầng: Video Stream → YOLOv11 → IPM → Alert Engine → GUI"),
        ("31_kien_truc_luong_xu_ly", "Các luồng (thread) xử lý và cách trao đổi dữ liệu"),
        ("32_so_do_goi_thanh_phan", "Sơ đồ gói / thành phần của mã nguồn"),
        ("33_so_do_trien_khai", "Sơ đồ triển khai"),
    ]),
    ("2. Quy trình nghiệp vụ (BPMN)", [
        ("02_bpmn_quy_trinh_tong_quat", "BPMN quy trình tổng quát"),
        ("03_bpmn_chuan_bi_giam_sat", "BPMN chuẩn bị giám sát: chọn nguồn, căn chỉnh camera, cấu hình ngưỡng"),
        ("04_bpmn_giam_sat_canh_bao", "BPMN giám sát và cảnh báo khoảng cách"),
    ]),
    ("3. Sơ đồ use case", [
        ("05_usecase_tong_quat", "Sơ đồ use case tổng quát"),
        ("06_usecase_UC01_nguon_video", "Phân rã UC01 - Quản lý nguồn video/camera"),
        ("07_usecase_UC02_cau_hinh_IPM", "Phân rã UC02 - Cấu hình thông số IPM (căn chỉnh camera)"),
        ("08_usecase_UC03_nguong_canh_bao", "Phân rã UC03 - Cấu hình ngưỡng cảnh báo"),
        ("09_usecase_UC04_giam_sat", "Phân rã UC04 - Giám sát realtime & cảnh báo"),
        ("10_usecase_UC05_nhat_ky", "Phân rã UC05 - Quản lý nhật ký cảnh báo"),
    ]),
    ("4. Sơ đồ hoạt động", [
        ("11_hoat_dong_UC01_nguon_video", "Sơ đồ hoạt động UC01 - Quản lý nguồn video/camera"),
        ("12_hoat_dong_UC02_cau_hinh_IPM", "Sơ đồ hoạt động UC02 - Cấu hình thông số IPM"),
        ("13a_hoat_dong_UC03_cai_dat_nguong", "Sơ đồ hoạt động UC03 (a) - Chỉnh tốc độ và tham số trong Cài đặt"),
        ("13b_hoat_dong_UC03_tro_ly_AI", "Sơ đồ hoạt động UC03 (b) - Điều chỉnh ngưỡng nhờ Trợ lý AI"),
        ("14_hoat_dong_UC04_giam_sat", "Sơ đồ hoạt động UC04 - Giám sát realtime & cảnh báo"),
        ("15_hoat_dong_UC05_nhat_ky", "Sơ đồ hoạt động UC05 - Quản lý nhật ký cảnh báo"),
        ("16_hoat_dong_xu_ly_mot_khung", "Sơ đồ hoạt động xử lý một khung hình (ADASPipeline.process)"),
    ]),
    ("5. Sơ đồ tuần tự", [
        ("17_tuan_tu_UC01_nguon_video", "Sơ đồ tuần tự UC01 - Quản lý nguồn video/camera"),
        ("18_tuan_tu_UC02_cau_hinh_IPM", "Sơ đồ tuần tự UC02 - Cấu hình thông số IPM"),
        ("19_tuan_tu_UC03_nguong_canh_bao", "Sơ đồ tuần tự UC03 - Cấu hình ngưỡng cảnh báo"),
        ("20_tuan_tu_UC04_giam_sat", "Sơ đồ tuần tự UC04 - Giám sát realtime & cảnh báo"),
        ("21_tuan_tu_UC05_nhat_ky", "Sơ đồ tuần tự UC05 - Quản lý nhật ký cảnh báo"),
    ]),
    ("6. Sơ đồ lớp", [
        ("22_lop_tong_quat", "Sơ đồ lớp tổng quát (gói gui/ và adas/)"),
        ("23_lop_thuc_the", "Sơ đồ lớp thực thể (entity)"),
        ("24_lop_dieu_khien", "Sơ đồ lớp xử lý (control) - gói adas/"),
        ("25_lop_giao_dien", "Sơ đồ lớp giao diện (boundary) - gói gui/"),
    ]),
    ("7. Cơ sở dữ liệu", [
        ("26_erd_co_so_du_lieu", "Sơ đồ thực thể - liên kết (ERD) của CSDL data/adas.db (lược đồ phiên bản 3)"),
    ]),
    ("8. Sơ đồ trạng thái", [
        ("27_trang_thai_muc_canh_bao", "Trạng thái mức cảnh báo (AlertManager - chống nhiễu)"),
        ("28_trang_thai_dot_vi_pham", "Trạng thái đợt vi phạm (ViolationRecorder)"),
        ("29_trang_thai_nhan_dien_lan", "Trạng thái nhận diện làn xe chủ (EgoLaneDetector)"),
        ("30_trang_thai_phien_giam_sat", "Trạng thái phiên giám sát (ProcessingWorker)"),
    ]),
]


def _section(doc, landscape: bool, first=False):
    sec = doc.sections[0] if first else doc.add_section()
    w, h = Cm(21), Cm(29.7)
    sec.orientation = WD_ORIENT.LANDSCAPE if landscape else WD_ORIENT.PORTRAIT
    sec.page_width, sec.page_height = (h, w) if landscape else (w, h)
    sec.left_margin = sec.right_margin = Cm(2)
    sec.top_margin = sec.bottom_margin = Cm(2)
    return sec


def main():
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Times New Roman"
    st.font.size = Pt(13)
    _section(doc, False, first=True)
    doc.add_heading("SƠ ĐỒ PHÂN TÍCH THIẾT KẾ HỆ THỐNG", 0)
    doc.add_paragraph(
        "Hệ thống cảnh báo khoảng cách an toàn giữa các phương tiện trên cao tốc thời gian thực ứng dụng "
        "YOLOv11 và thị giác máy tính. Các sơ đồ được vẽ theo đúng mã nguồn hiện tại (thư mục giaodien/): "
        "tên lớp, phương thức, bảng CSDL và nhãn nút giữ nguyên như trong ứng dụng. Ảnh gốc (PNG độ phân giải "
        "gấp đôi và SVG) nằm trong docs/so_do/; mã nguồn để sửa sơ đồ nằm trong docs/so_do/nguon/.")
    n = 0
    for title, items in GROUPS:
        for i, (name, caption) in enumerate(items):
            png = OUT / f"{name}.png"
            w, h = Image.open(png).size
            landscape = w / h > 1.25
            _section(doc, landscape)
            if i == 0:
                doc.add_heading(title, 1)
            max_w, max_h = (Cm(25.7), Cm(14.5)) if landscape else (Cm(17), Cm(22.5))
            if i == 0:
                max_h -= Cm(1.2)
            scale = min(max_w / w, max_h / h)
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.add_run().add_picture(str(png), width=int(w * scale), height=int(h * scale))
            n += 1
            cap = doc.add_paragraph(f"Hình {n}. {caption}")
            cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            cap.runs[0].italic = True
    doc.save(DOCX)
    print("Đã ghi", DOCX, "-", n, "hình")


if __name__ == "__main__":
    main()
