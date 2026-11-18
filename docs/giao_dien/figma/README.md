# Mockup giao diện cho Figma (PI 2.3)

Các màn hình chính của ứng dụng Desktop ở dạng **SVG** (nhập vào Figma thành lớp vector và lớp chữ sửa
được) và **PNG** (chèn vào quyển báo cáo, độ phân giải ×1,25). Tạo lại bằng:

```bash
python tools/export_mockups.py [--video đường/dẫn/video.mp4]
```

Script chạy giao diện thật ở chế độ ẩn trên bản sao tạm của CSDL, nên mockup luôn khớp với phần mềm
và không ghi gì vào `data/adas.db`.

| File | Màn hình | Use Case | Hình trong quyển |
|---|---|---|---|
| `01_giam_sat_chao_mung` | Màn hình giám sát khi chưa chạy (3 bước bắt đầu) | UC04 | 3.8 |
| `02_giam_sat_dang_chay` | Màn hình giám sát đang chạy, xe phía trước ở mức cảnh báo | UC04 | 3.8 |
| `03_can_chinh_b1_xe_va_so_do` | Căn chỉnh camera - Bước 1: loại xe, chiều cao camera | UC02 | 3.9 |
| `04_can_chinh_b2_duong_chan_troi` | Căn chỉnh camera - Bước 2: đường chân trời | UC02 | 3.9 |
| `05_can_chinh_b3_hoan_tat` | Căn chỉnh camera - Bước 3: hoàn tất | UC02 | 3.9 |
| `06_can_chinh_nang_cao_4_diem` | Căn chỉnh nâng cao: chấm 4 điểm IPM | UC02 | 3.9 |
| `07_cai_dat_nguong_canh_bao` | Cài đặt ngưỡng cảnh báo theo dải tốc độ | UC03 | - |
| `08_nhat_ky_vi_pham` | Nhật ký vi phạm, phiên giám sát, ảnh bằng chứng | UC05 | 3.10 |
| `09_quan_ly_nguon` | Quản lý nguồn video/camera | UC01 | - |

## File Figma

**ADAS Cao tốc - Mockup giao diện**:
https://www.figma.com/design/O67gb4bI92BIcf1sHoiGRl/ADAS-Cao-t%E1%BB%91c---Mockup-giao-di%E1%BB%87n
(quyền "Anyone can view": ai có link đều xem được).

- Trang *Mockup giao diện Desktop* có 3 section: UC04 giám sát (01, 02), UC02 căn chỉnh IPM (03–06), UC01/UC03/UC05
  nguồn, ngưỡng, nhật ký (07–09). Mọi frame đều 1536×864 = màn hình 1080p ở tỉ lệ 125 %. Frame 03–09 là hộp thoại
  (có thanh tiêu đề và nút ✕) nổi trên cửa sổ chính được làm tối, như khi mở trong app; nội dung hộp thoại là lớp
  `Nội dung`, nền là bản sao khóa của frame 01/02.
- Prototype (bắt đầu từ frame 01):
  https://www.figma.com/proto/O67gb4bI92BIcf1sHoiGRl/ADAS-Cao-t%E1%BB%91c---Mockup-giao-di%E1%BB%87n?node-id=28-2&scaling=scale-down&content-scaling=fixed&starting-point-node-id=28%3A2&hide-ui=1
  Mở link, bấm **F11** cho trình duyệt toàn màn hình: frame khớp đúng màn hình như app đang mở tối đa. Không toàn màn
  hình thì Figma thu nhỏ vừa cửa sổ (menu thanh trượt góc trên phải → *Fit width and height*).
  Các nút "Căn chỉnh camera", "Bắt đầu giám sát", "Tiếp", "Quay lại", "Lịch sử", "Cài đặt", "Đóng", "✕"... có vùng
  bấm trong suốt (lớp `Vùng bấm · …`) nối tới màn hình tương ứng.

## Nhập lại vào Figma (khi giao diện thay đổi)

1. Cài 2 font của ứng dụng trên máy (nhấp đúp từng file trong `assets/fonts/` rồi chọn Install): Be Vietnam Pro
   và `MaterialIcons-Regular.otf`. Figma bản web cần cài thêm Figma Font Installer để dùng font trên máy.
   Thiếu Material Icons thì vài biểu tượng nhỏ nằm trong dòng chữ (chấm trạng thái, dấu !) sẽ hiện thành ô vuông.
2. Tạo file Figma mới, đặt tên như *ADAS Cao tốc - Mockup giao diện*.
3. Kéo thả cả 9 file `.svg` vào canvas (hoặc *File → Place image…*). Mỗi file thành một frame, có kích thước
   đúng như cửa sổ thật (màn hình chính 1536×864).
4. Đổi tên frame theo cột *Màn hình* ở bảng trên và xếp thành 3 nhóm (Giám sát, Căn chỉnh IPM, Nhật ký) bằng
   *Section*. Bấm chuột phải vào frame → *Ungroup* để tách lớp khi cần sửa.
5. Có thể dùng chức năng *Prototype* nối các nút: "Căn chỉnh camera" → frame 03, "Tiếp" → 04 → 05,
   "Lịch sử" → 08, "Cài đặt" → 07.
6. Bấm *Share* → *Copy link* để đưa link Figma vào quyển báo cáo hoặc gửi giảng viên.

## Bảng màu và chữ (hệ thiết kế "Night Drive", dùng chung với app Android)

| Token | Màu | Dùng cho |
|---|---|---|
| Nền | `#05070a` | Nền cửa sổ, khung video |
| Bề mặt | `#0f141b` / `#161d26` | Thẻ, thanh tiêu đề / ô nhập trên thẻ |
| Viền | `#222b37` | Viền thẻ, đường phân cách |
| Chữ | `#eef2f6` / `#a3aebb` | Chữ chính / chữ phụ |
| Nhấn | `#4c9eff` | Nút chính, mục đang chọn |
| An toàn | `#2fd27a` | Khoảng cách lớn hơn ngưỡng cảnh báo |
| Cảnh báo | `#ffb020` | Dưới ngưỡng cảnh báo |
| Nguy hiểm | `#ff4d4f` (nền đặc `#d92d20`) | Dưới ngưỡng nguy hiểm |

Font chữ: Be Vietnam Pro (Regular / Medium / SemiBold / Bold). Biểu tượng: Material Icons. Giá trị chính xác của
các token nằm trong `gui/theme.py`.
