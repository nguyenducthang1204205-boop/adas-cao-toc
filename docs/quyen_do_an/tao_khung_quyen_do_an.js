// Khung quyển đồ án theo mẫu của trường (bố cục 4 chương của đề cương H01): đủ trang bìa, phần đầu,
// đề mục Chương 1-4, chú thích hình/bảng dự kiến và các trang cuối; chưa có nội dung chi tiết.
//   NODE_PATH=<thư mục node_modules có docx@9> node tao_khung_quyen_do_an.js   (biến OUT để đổi file ra)
// Sau khi tạo: chạy cap_nhat_muc_luc.ps1 <file> để điền số trang cho mục lục / danh mục hình / bảng.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType, ShadingType,
  AlignmentType, BorderStyle, VerticalAlign, Footer, PageNumber, NumberFormat,
  TableOfContents, StyleLevel, PageBorderDisplay, PageBorderOffsetFrom,
} = require("docx");

const OUT = process.env.OUT || path.join(__dirname, "KHUNG_QUYEN_DO_AN.docx");
const FONT = "Times New Roman";
const CM = 567;
const DE_TAI = "Xây dựng hệ thống cảnh báo khoảng cách an toàn giữa các phương tiện trên cao tốc thời gian thực ứng dụng mô hình YOLOv11 và thị giác máy tính";
const SV = "Nguyễn Đức Thắng";
const GVHD = "TS. Nguyễn Thành Trung";

// ---------------------------------------------------------------- tiện ích văn bản
function runs(content, base = {}) {
  const parts = Array.isArray(content) ? content : [content];
  return parts.map((p) => (typeof p === "string"
    ? new TextRun({ text: p, font: FONT, ...base })
    : new TextRun({ text: p[0], font: FONT, ...base, ...p[1] })));
}
const P = (content, o = {}) => new Paragraph({
  children: runs(content, o.run || {}), alignment: o.align || AlignmentType.JUSTIFIED,
  spacing: { before: 0, after: 120, line: 360 }, indent: o.noIndent ? undefined : { firstLine: 567 },
});
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: runs(t), alignment: AlignmentType.CENTER,
  pageBreakBefore: true, spacing: { before: 0, after: 360 }, keepNext: true });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: runs(t), spacing: { before: 240, after: 120 }, keepNext: true });
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: runs(t), spacing: { before: 180, after: 100 }, keepNext: true });
const SUB = (t) => new Paragraph({ children: runs([[t, { bold: true, italics: true }]]), spacing: { before: 120, after: 80, line: 360 }, keepNext: true });
const TITLE = (t, pageBreak = true, style = "TieuDePhu") => new Paragraph({ style, children: runs(t), alignment: AlignmentType.CENTER,
  pageBreakBefore: pageBreak, spacing: { before: 0, after: 360 } });
const NOTE = (t) => new Paragraph({ children: runs([[t, { italics: true, color: "808080" }]]), alignment: AlignmentType.CENTER, spacing: { after: 120 } });
const RIGHT = (t, o = {}) => new Paragraph({ alignment: AlignmentType.RIGHT, spacing: { before: o.before || 0 },
  indent: o.indent ? { right: o.indent } : undefined, children: runs([[t, o.run || {}]]) });

const BORDER = { style: BorderStyle.SINGLE, size: 4, color: "000000" };
const BORDERS = { top: BORDER, bottom: BORDER, left: BORDER, right: BORDER };
const NB = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const NOB = { top: NB, bottom: NB, left: NB, right: NB };
function cell(content, width, o = {}) {
  return new TableCell({
    children: [].concat(content).map((c) => new Paragraph({ children: runs(c, { size: o.size || 24, bold: o.bold }),
      alignment: o.align || AlignmentType.LEFT, spacing: { after: 20, line: 276 } })),
    borders: o.noBorder ? NOB : BORDERS, width: { size: width, type: WidthType.DXA },
    shading: o.fill ? { fill: o.fill, type: ShadingType.CLEAR, color: "auto" } : undefined,
    verticalAlign: o.valign || VerticalAlign.TOP, margins: { top: 50, bottom: 50, left: 90, right: 90 },
  });
}

// ---------------------------------------------------------------- hình / bảng dự kiến (đánh số theo chương)
let chap = 0;
let figNo = 0;
let tabNo = 0;
const ghost = (t) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 40 },
  border: { top: BORDER, bottom: BORDER, left: BORDER, right: BORDER }, children: runs([[t, { italics: true, color: "808080", size: 22 }]]) });
function fig(text) {
  add(ghost("[Vị trí hình]"));
  add(new Paragraph({ style: "CaptionHinh", alignment: AlignmentType.CENTER, spacing: { before: 40, after: 200 },
    children: runs([[`Hình ${chap}.${++figNo}: `, {}], text]) }));
}
function tab(text) {
  add(new Paragraph({ style: "CaptionBang", alignment: AlignmentType.CENTER, spacing: { before: 200, after: 40 }, keepNext: true,
    children: runs([[`Bảng ${chap}.${++tabNo}: `, {}], text]) }));
  add(ghost("[Vị trí bảng]"));
}

// ---------------------------------------------------------------- section
const sections = [];
let cur;
function section(kind) { cur = { kind, children: [] }; sections.push(cur); }
const add = (...xs) => cur.children.push(...xs);

// Một chương: [tiêu đề mục cấp 2, [mục con]], mục con là chuỗi (cấp 3), {f: hình}, {t: bảng} hoặc {s: tiểu mục a), b)}
function chapter(n, title, parts) {
  chap = n; figNo = 0; tabNo = 0;
  add(H1(`CHƯƠNG ${n}. ${title}`));
  for (const [h2, items] of parts) {
    add(H2(h2));
    for (const it of items || []) {
      if (typeof it === "string") add(H3(it));
      else if (it.f) fig(it.f);
      else if (it.t) tab(it.t);
      else if (it.s) add(SUB(it.s));
    }
  }
}

// ================================================================ BÌA NGOÀI
section("cover");
const C = (t, o = {}) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: o.before ?? 0, after: o.after ?? 0, line: 300 },
  children: runs([[t, { bold: o.bold, size: o.size || 28, italics: o.italics, color: o.color }]]) });
add(C("ĐẠI HỌC THÁI NGUYÊN", { bold: true, size: 26 }));
add(C("TRƯỜNG ĐẠI HỌC CÔNG NGHỆ THÔNG TIN VÀ TRUYỀN THÔNG", { bold: true, size: 26, after: 2200 }));
add(C(SV.toUpperCase(), { bold: true, size: 28, after: 2000 }));
add(C(DE_TAI.toUpperCase(), { bold: true, size: 28, after: 2200 }));
add(C("ĐỒ ÁN TỐT NGHIỆP ĐẠI HỌC", { bold: true, size: 44, after: 120 }));
add(C("NGÀNH CÔNG NGHỆ THÔNG TIN", { bold: true, size: 28, after: 3200 }));
add(C("THÁI NGUYÊN, THÁNG 12 NĂM 2026", { bold: true, size: 26 }));

// ================================================================ BÌA TRONG
section("cover");
add(C("ĐẠI HỌC THÁI NGUYÊN", { bold: true, size: 26 }));
add(C("TRƯỜNG ĐẠI HỌC CÔNG NGHỆ THÔNG TIN VÀ TRUYỀN THÔNG", { bold: true, size: 26, after: 400 }));
{
  const box = (t) => [new Paragraph({ children: [], spacing: { before: 700 } }),
    new Paragraph({ alignment: AlignmentType.CENTER, children: runs([[t, { italics: true, color: "808080", size: 22 }]]) })];
  add(new Table({
    width: { size: 16 * CM, type: WidthType.DXA }, columnWidths: [4.5 * CM, 8 * CM, 3.5 * CM],
    rows: [new TableRow({ height: { value: 4.5 * CM, rule: "atLeast" }, children: [
      new TableCell({ borders: NOB, width: { size: 4.5 * CM, type: WidthType.DXA }, children: box("[Logo trường]") }),
      new TableCell({ borders: NOB, width: { size: 8 * CM, type: WidthType.DXA }, children: [new Paragraph({ children: [] })] }),
      new TableCell({ borders: BORDERS, width: { size: 3.5 * CM, type: WidthType.DXA }, children: box("[Ảnh 3×4]") }),
    ] })],
  }));
}
add(C("ĐỒ ÁN TỐT NGHIỆP ĐẠI HỌC", { bold: true, size: 36, color: "C00000", before: 600, after: 120 }));
add(C("KHOA CÔNG NGHỆ THÔNG TIN", { bold: true, size: 28, after: 600 }));
add(C("ĐỀ TÀI:", { bold: true, size: 28, after: 120 }));
add(C(DE_TAI.toUpperCase(), { bold: true, size: 28, after: 1400 }));
{
  const row = (k, v) => new TableRow({ children: [
    cell([[k, { bold: true }]], 6 * CM, { noBorder: true, size: 26 }), cell([[v, { bold: true }]], 8 * CM, { noBorder: true, size: 26 })] });
  add(new Table({
    width: { size: 14 * CM, type: WidthType.DXA }, columnWidths: [6 * CM, 8 * CM], alignment: AlignmentType.CENTER,
    rows: [row("Giảng viên hướng dẫn:", GVHD), row("Sinh viên thực hiện:", SV), row("Lớp:", "CNTT K22A CN"), row("Mã SV:", "DTC235200703")],
  }));
}
add(C("Thái Nguyên, tháng 12 năm 2026", { bold: true, italics: true, size: 26, before: 1600 }));

// ================================================================ PHẦN ĐẦU (số trang La Mã)
section("front");
add(TITLE("LỜI CẢM ƠN", false));
add(NOTE("(Nội dung sẽ viết sau: cảm ơn nhà trường, khoa, giảng viên hướng dẫn, gia đình, bạn bè)"));

add(TITLE("LỜI CAM ĐOAN"));
add(NOTE("(Nội dung sẽ viết sau: cam đoan đồ án là kết quả tự thực hiện dưới sự hướng dẫn của giảng viên)"));
add(RIGHT("Thái Nguyên, ngày … tháng … năm 2026", { before: 480, run: { italics: true } }));
add(RIGHT("Sinh viên thực hiện", { indent: 700, run: { bold: true } }));

add(TITLE("MỤC LỤC"));
add(new TableOfContents("Mục lục", { hyperlink: true, headingStyleRange: "1-3", stylesWithLevels: [new StyleLevel("TieuDePhu", 1)] }));

add(TITLE("DANH MỤC TỪ VIẾT TẮT"));
{
  const ab = [
    ["Advanced Driver Assistance Systems (ADAS)", "Hệ thống hỗ trợ lái xe nâng cao"],
    ["Artificial Intelligence (AI)", "Trí tuệ nhân tạo"],
    ["Application Programming Interface (API)", "Giao diện lập trình ứng dụng"],
    ["Bird's-Eye View (BEV)", "Ảnh nhìn từ trên xuống"],
    ["Business Process Model and Notation (BPMN)", "Ký pháp mô hình hóa quy trình nghiệp vụ"],
    ["Convolutional Neural Network (CNN)", "Mạng nơ-ron tích chập"],
    ["Cơ sở dữ liệu (CSDL)", "Cơ sở dữ liệu"],
    ["Entity Relationship Diagram (ERD)", "Sơ đồ thực thể - liên kết"],
    ["Forward Collision Warning (FCW)", "Cảnh báo va chạm phía trước"],
    ["Frames Per Second (FPS)", "Số khung hình mỗi giây"],
    ["Graphics Processing Unit (GPU)", "Bộ xử lý đồ họa"],
    ["Intersection over Union (IoU)", "Tỷ lệ giao trên hợp"],
    ["Inverse Perspective Mapping (IPM)", "Biến đổi phối cảnh ngược"],
    ["Large Language Model (LLM)", "Mô hình ngôn ngữ lớn"],
    ["Mean Absolute Error (MAE)", "Sai số tuyệt đối trung bình"],
    ["mean Average Precision (mAP)", "Độ chính xác trung bình"],
    ["Real Time Streaming Protocol (RTSP)", "Giao thức truyền luồng thời gian thực"],
    ["Time To Collision (TTC)", "Thời gian còn lại trước va chạm"],
    ["Use Case (UC)", "Ca sử dụng"],
    ["You Only Look Once (YOLO)", "Họ mô hình phát hiện đối tượng một giai đoạn"],
  ];
  const w = [1.4, 7.6, 7.0].map((c) => Math.round(c * CM));
  add(new Table({
    width: { size: w[0] + w[1] + w[2], type: WidthType.DXA }, columnWidths: w,
    rows: [new TableRow({ tableHeader: true, children: ["STT", "Thuật ngữ", "Ý nghĩa"].map((h, i) => cell(h, w[i], { bold: true, align: AlignmentType.CENTER })) }),
      ...ab.map((r, k) => new TableRow({ children: [cell(`${k + 1}.`, w[0], { align: AlignmentType.CENTER }), cell(r[0], w[1]), cell(r[1], w[2])] }))],
  }));
}

add(TITLE("DANH MỤC HÌNH ẢNH"));
add(new TableOfContents("Danh mục hình", { hyperlink: true, stylesWithLevels: [new StyleLevel("CaptionHinh", 4)] }));
add(TITLE("DANH MỤC BẢNG BIỂU"));
add(new TableOfContents("Danh mục bảng", { hyperlink: true, stylesWithLevels: [new StyleLevel("CaptionBang", 4)] }));

add(TITLE("LỜI NÓI ĐẦU"));
for (const s of ["1. Tính cấp thiết của đề tài", "2. Mục tiêu của đề tài", "3. Phương pháp nghiên cứu", "4. Bố cục của báo cáo"]) {
  add(SUB(s)); add(NOTE("(Nội dung sẽ viết sau)"));
}

// ================================================================ NỘI DUNG (số trang Ả Rập)
section("body");
chapter(1, "CƠ SỞ LÝ THUYẾT", [
  ["1.1. Tổng quan về đề tài", [
    "1.1.1. Bối cảnh và lý do chọn đề tài",
    "1.1.2. Mục tiêu, đối tượng và phạm vi nghiên cứu",
    "1.1.3. Phát biểu bài toán cảnh báo khoảng cách an toàn",
    { t: "Đầu vào, đầu ra và ràng buộc của bài toán" },
  ]],
  ["1.2. Khoảng cách an toàn trên đường cao tốc", [
    "1.2.1. Hệ thống hỗ trợ lái xe và cảnh báo va chạm phía trước",
    "1.2.2. Quy định khoảng cách an toàn theo Thông tư 31/2019/TT-BGTVT",
    { t: "Khoảng cách an toàn tối thiểu theo dải tốc độ" },
    "1.2.3. Quãng đường dừng xe và ảnh hưởng của điều kiện đường",
  ]],
  ["1.3. Phát hiện và bám vết phương tiện bằng học sâu", [
    "1.3.1. Học sâu và mạng nơ-ron tích chập",
    { f: "Cấu trúc cơ bản của mạng nơ-ron tích chập" },
    "1.3.2. Mô hình phát hiện đối tượng YOLOv11",
    { f: "Kiến trúc mô hình YOLOv11" },
    "1.3.3. Bám vết phương tiện qua các khung hình",
  ]],
  ["1.4. Ước lượng khoảng cách bằng một camera", [
    "1.4.1. Mô hình camera và tư thế camera",
    { f: "Mô hình camera lỗ kim" },
    { s: "a) Điểm tụ và đường chân trời" },
    { s: "b) Chiều cao, góc nghiêng và tiêu cự" },
    "1.4.2. Biến đổi phối cảnh ngược (IPM)",
    { f: "Ánh xạ mặt đường từ ảnh sang ảnh nhìn từ trên xuống" },
    "1.4.3. Nhận diện vạch kẻ làn đường",
    "1.4.4. Bộ lọc Kalman, tốc độ tiếp cận và thời gian va chạm",
  ]],
  ["1.5. Mô hình ngôn ngữ lớn trong gợi ý ngưỡng an toàn"],
  ["1.6. Các chỉ số đánh giá", [
    { s: "a) Đánh giá mô hình phát hiện phương tiện" },
    { s: "b) Đánh giá đo khoảng cách, tốc độ và hiệu năng" },
  ]],
  ["1.7. Công nghệ phát triển phần mềm", [
    { t: "Các công nghệ sử dụng trong đồ án" },
  ]],
  ["1.8. Các hệ thống liên quan và định hướng giải quyết", [
    "1.8.1. Các giải pháp cảnh báo khoảng cách hiện có",
    { t: "So sánh các giải pháp cảnh báo khoảng cách" },
    "1.8.2. Định hướng giải quyết của đề tài",
  ]],
  ["1.9. Kết luận chương 1"],
]);

const UC = ["UC01 - Quản lý nguồn video/camera", "UC02 - Cấu hình thông số IPM", "UC03 - Cấu hình ngưỡng cảnh báo",
  "UC04 - Giám sát realtime và cảnh báo", "UC05 - Quản lý nhật ký cảnh báo"];
chapter(2, "KHẢO SÁT VÀ PHÂN TÍCH HỆ THỐNG", [
  ["2.1. Khảo sát hiện trạng", [
    "2.1.1. Thực trạng giữ khoảng cách trên cao tốc Việt Nam",
    "2.1.2. Khảo sát các giải pháp và người dùng mục tiêu",
    "2.1.3. Phạm vi hệ thống",
  ]],
  ["2.2. Quy trình nghiệp vụ", [
    { f: "Sơ đồ BPMN quy trình tổng quát" },
    "2.2.1. Quy trình chuẩn bị giám sát",
    { f: "Sơ đồ BPMN quy trình chuẩn bị giám sát" },
    "2.2.2. Quy trình giám sát và cảnh báo",
    { f: "Sơ đồ BPMN quy trình giám sát và cảnh báo" },
    "2.2.3. Quy trình điều chỉnh ngưỡng và tra cứu nhật ký",
    { f: "Sơ đồ BPMN quy trình điều chỉnh ngưỡng" },
    { f: "Sơ đồ BPMN quy trình tra cứu nhật ký" },
    "2.2.4. Biểu mẫu dữ liệu",
    { t: "Biểu mẫu thông tin nguồn video và hiệu chỉnh camera" },
    { t: "Biểu mẫu bản ghi vi phạm khoảng cách" },
  ]],
  ["2.3. Yêu cầu chức năng", [
    { t: "Tổng hợp yêu cầu chức năng" },
  ]],
  ["2.4. Yêu cầu phi chức năng", [
    { t: "Tổng hợp yêu cầu phi chức năng" },
  ]],
  ["2.5. Tác nhân và sơ đồ Use Case", [
    "2.5.1. Các tác nhân của hệ thống",
    { t: "Danh sách tác nhân" },
    "2.5.2. Sơ đồ Use Case tổng quát",
    { f: "Sơ đồ Use Case tổng quát" },
    "2.5.3. Phân rã các Use Case",
    ...UC.map((u) => ({ f: `Sơ đồ phân rã ${u}` })),
  ]],
  ["2.6. Đặc tả Use Case", [
    ...UC.flatMap((u, i) => [`2.6.${i + 1}. Đặc tả ${u}`, { t: `Đặc tả ${u}` }]),
    { t: "Ma trận Use Case - yêu cầu chức năng" },
  ]],
  ["2.7. Kết luận chương 2"],
]);

chapter(3, "THIẾT KẾ HỆ THỐNG", [
  ["3.1. Thiết kế kiến trúc phần mềm", [
    "3.1.1. Kiến trúc tổng thể",
    { f: "Kiến trúc tổng thể: Video Stream → YOLOv11 → IPM → Alert Engine → GUI" },
    "3.1.2. Luồng xử lý một khung hình",
    { f: "Luồng xử lý một khung hình" },
    { s: "Mô hình đa luồng giữa giao diện và luồng xử lý" },
    "3.1.3. Sơ đồ gói và sơ đồ triển khai",
    { f: "Sơ đồ gói và thành phần" },
    { f: "Sơ đồ triển khai" },
  ]],
  ["3.2. Thiết kế chi tiết các Use Case", [
    "3.2.1. Sơ đồ hoạt động",
    ...UC.map((u) => ({ f: `Sơ đồ hoạt động ${u}` })),
    "3.2.2. Sơ đồ tuần tự",
    ...UC.map((u) => ({ f: `Sơ đồ tuần tự ${u}` })),
  ]],
  ["3.3. Thiết kế lớp", [
    { f: "Sơ đồ lớp tổng quát" },
    { s: "a) Lớp thực thể" },
    { s: "b) Lớp xử lý và điều khiển" },
    { s: "c) Lớp giao diện" },
  ]],
  ["3.4. Thiết kế cơ sở dữ liệu", [
    "3.4.1. Sơ đồ thực thể - liên kết",
    { f: "Sơ đồ thực thể - liên kết" },
    "3.4.2. Mô tả chi tiết các bảng",
    ...["video_sources", "camera_calibrations", "system_config", "config_history", "monitoring_sessions", "violations"]
      .map((t) => ({ t: `Cấu trúc bảng ${t}` })),
    { s: "Ràng buộc toàn vẹn và nâng cấp lược đồ" },
  ]],
  ["3.5. Thiết kế thuật toán", [
    "3.5.1. Nhận diện thưa và bám vết dày",
    "3.5.2. Căn chỉnh camera và tự hiệu chỉnh",
    { s: "a) Căn chỉnh ba bước và căn chỉnh nâng cao bốn điểm" },
    { f: "Lưu đồ căn chỉnh camera ba bước" },
    { s: "b) Tự hiệu chỉnh trong khi chạy" },
    "3.5.3. Đo khoảng cách và lọc Kalman",
    "3.5.4. Nhận diện làn xe chủ và ước lượng tốc độ",
    "3.5.5. Tính ngưỡng an toàn và chống báo nhầm",
    { f: "Lưu đồ tính ngưỡng và phân loại mức cảnh báo" },
    "3.5.6. Ghi nhận vi phạm khoảng cách",
    "3.5.7. Trợ lý AI gợi ý ngưỡng",
    { s: "a) Gọi Claude với lược đồ JSON" },
    { s: "b) Chế độ ngoại tuyến bằng luật từ khóa" },
  ]],
  ["3.6. Thiết kế giao diện (mockup Figma)", [
    { s: "a) Hệ thống thiết kế: màu sắc, phông chữ, biểu tượng" },
    { s: "b) Màn hình giám sát chính" },
    { f: "Mockup màn hình giám sát chính" },
    { s: "c) Màn hình căn chỉnh camera" },
    { f: "Mockup màn hình căn chỉnh camera" },
    { s: "d) Màn hình cài đặt ngưỡng" },
    { f: "Mockup màn hình cài đặt ngưỡng" },
    { s: "e) Màn hình Trợ lý AI và nhật ký vi phạm" },
    { f: "Mockup màn hình Trợ lý AI và nhật ký vi phạm" },
    { s: "f) Màn hình lịch sử phiên giám sát" },
    { f: "Mockup màn hình lịch sử phiên giám sát" },
  ]],
  ["3.7. Kết luận chương 3"],
]);

chapter(4, "TRIỂN KHAI", [
  ["4.1. Môi trường cài đặt", [
    { t: "Cấu hình phần cứng thử nghiệm" },
    { t: "Phần mềm và thư viện sử dụng" },
  ]],
  ["4.2. Chuẩn bị dữ liệu và huấn luyện mô hình", [
    "4.2.1. Bộ dữ liệu phương tiện",
    { t: "Thống kê bộ dữ liệu phương tiện" },
    "4.2.2. Huấn luyện và đánh giá mô hình YOLOv11",
    { t: "Tham số huấn luyện mô hình YOLOv11" },
    { f: "Biểu đồ hàm mất mát và chỉ số trong quá trình huấn luyện" },
    { t: "Kết quả đánh giá mô hình trên tập kiểm tra" },
    "4.2.3. Bộ video thử nghiệm theo kịch bản",
    { t: "Danh sách video thử nghiệm theo kịch bản ban ngày, ban đêm, thời tiết xấu" },
  ]],
  ["4.3. Cài đặt hệ thống", [
    "4.3.1. Cài đặt cơ sở dữ liệu",
    "4.3.2. Cài đặt các module xử lý",
    "4.3.3. Cài đặt giao diện và các Use Case",
    { f: "Giao diện màn hình giám sát chính" },
    { f: "Giao diện trình căn chỉnh camera" },
    { f: "Giao diện cài đặt ngưỡng cảnh báo" },
    { f: "Giao diện nhật ký và lịch sử vi phạm" },
    "4.3.4. Cài đặt Trợ lý AI gợi ý ngưỡng",
    { f: "Giao diện Trợ lý AI" },
  ]],
  ["4.4. Kiểm thử và đánh giá", [
    "4.4.1. Kiểm thử chức năng",
    { t: "Kết quả kiểm thử chức năng" },
    "4.4.2. Đánh giá hiệu năng",
    { t: "Thời gian xử lý từng khâu và tốc độ khung hình" },
    "4.4.3. Đánh giá độ chính xác đo khoảng cách và tốc độ",
    { t: "Sai số đo khoảng cách" },
    { t: "Sai số ước lượng tốc độ xe chủ" },
    "4.4.4. Kiểm thử theo kịch bản ban ngày, ban đêm, thời tiết xấu",
    { t: "Kết quả cảnh báo theo kịch bản" },
  ]],
  ["4.5. Đóng gói và triển khai ứng dụng Desktop", [
    { s: "a) Đóng gói thành file thực thi" },
    { s: "b) Cài đặt trên máy thử nghiệm" },
    { s: "c) Bảo mật khóa API và dữ liệu cục bộ" },
  ]],
  ["4.6. Hướng dẫn sử dụng"],
  ["4.7. Kết luận chương 4"],
]);

// ================================================================ PHẦN CUỐI
chap = 0;
add(H1("KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN"));
add(H2("Kết luận"));
add(H2("Hướng phát triển"));
add(H1("TÀI LIỆU THAM KHẢO"));
add(NOTE("(Danh sách tài liệu đánh số theo thứ tự trích dẫn trong bài)"));
add(H1("PHỤ LỤC"));
add(H2("Phụ lục A. Hướng dẫn cài đặt chi tiết"));
add(H2("Phụ lục B. Phiên bản Android và định hướng lắp trên xe"));

// Trang cam đoan kiểm tra trùng lặp (mẫu của trường)
{
  const w = [7 * CM, 9 * CM];
  const hc = (lines) => new TableCell({ borders: NOB, width: { size: w[lines.length === 2 ? 1 : 0], type: WidthType.DXA },
    children: lines.map(([t, o]) => new Paragraph({ alignment: AlignmentType.CENTER, children: runs([[t, { size: 24, ...o }]]) })) });
  add(new Paragraph({ pageBreakBefore: true, children: [] }));
  add(new Table({ width: { size: 16 * CM, type: WidthType.DXA }, columnWidths: w, rows: [new TableRow({ children: [
    hc([["ĐẠI HỌC THÁI NGUYÊN", {}], ["TRƯỜNG ĐẠI HỌC CÔNG NGHỆ", { bold: true }], ["THÔNG TIN VÀ TRUYỀN THÔNG", { bold: true }]]),
    hc([["CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", { bold: true }], ["Độc lập - Tự do - Hạnh phúc", { bold: true }]]),
  ] })] }));
  add(new Paragraph({ children: [], spacing: { after: 240 } }));
  add(TITLE("LỜI CAM ĐOAN", false, "TieuDeCuoi"));
  add(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 240 },
    children: runs("(kèm theo Thông báo số: … /TB-ĐH CNTT&TT ngày … tháng … năm 2026 của Hiệu trưởng Trường ĐH CNTT&TT)") }));
  add(P("Em xin cam đoan đã thực hiện việc kiểm tra mức độ tương đồng nội dung (ĐA/KLTN) qua phần mềm Turnitin một cách trung thực và đạt kết quả mức độ tương đồng …%. Bản đề tài (ĐA/KLTN) kiểm tra qua phần mềm là bản cứng đã nộp để bảo vệ trước hội đồng."));
  add(P("Nếu sai em xin hoàn toàn chịu trách nhiệm."));
  add(P("Xin chân thành cảm ơn."));
  add(RIGHT("Thái Nguyên, ngày … tháng … năm 2026", { before: 240, run: { italics: true } }));
  add(RIGHT("TÁC GIẢ CỦA SẢN PHẨM", { indent: 500, run: { bold: true } }));
  add(RIGHT("(Ký và ghi rõ họ tên)", { indent: 800, run: { italics: true } }));
}

add(TITLE("NHẬN XÉT CỦA GIÁO VIÊN HƯỚNG DẪN", true, "TieuDeCuoi"));
for (let i = 0; i < 14; i++) add(new Paragraph({ spacing: { after: 160 }, children: runs("…".repeat(38)) }));
add(RIGHT("Thái Nguyên, ngày … tháng … năm 2026", { before: 120, run: { italics: true } }));
add(RIGHT("GIÁO VIÊN HƯỚNG DẪN", { indent: 500, run: { bold: true } }));

add(TITLE("ĐỀ CƯƠNG ĐỒ ÁN TỐT NGHIỆP", true, "TieuDeCuoi"));
add(NOTE("(Đính kèm bản đề cương có chữ ký của giảng viên hướng dẫn và lãnh đạo bộ môn)"));

// ---------------------------------------------------------------- tài liệu
const footer = new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
  children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 24 })] })] });
const size = { width: 21 * CM, height: 29.7 * CM };
const margin = { top: 2 * CM, bottom: 2 * CM, left: 3 * CM, right: 2 * CM };
const DBL = { style: BorderStyle.THICK_THIN_SMALL_GAP, size: 24, color: "000000", space: 24 };
const props = {
  cover: { page: { size, margin, borders: { pageBorders: { display: PageBorderDisplay.ALL_PAGES, offsetFrom: PageBorderOffsetFrom.PAGE },
    pageBorderTop: DBL, pageBorderBottom: DBL, pageBorderLeft: DBL, pageBorderRight: DBL } } },
  front: { page: { size, margin, pageNumbers: { start: 1, formatType: NumberFormat.UPPER_ROMAN } } },
  body: { page: { size, margin, pageNumbers: { start: 1, formatType: NumberFormat.DECIMAL } } },
};

const doc = new Document({
  creator: SV,
  title: "Khung quyển đồ án tốt nghiệp - " + DE_TAI,
  styles: {
    default: { document: { run: { font: FONT, size: 26 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 28, bold: true, color: "000000" }, paragraph: { outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 26, bold: true, color: "000000" }, paragraph: { outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 26, bold: true, italics: true, color: "000000" }, paragraph: { outlineLevel: 2 } },
      ...["TieuDePhu", "TieuDeCuoi"].map((id) => ({ id, name: id, basedOn: "Normal", next: "Normal",
        run: { font: FONT, size: 28, bold: true, color: "000000" } })),
      { id: "CaptionHinh", name: "CaptionHinh", basedOn: "Normal", next: "Normal", run: { font: FONT, size: 26, italics: true } },
      { id: "CaptionBang", name: "CaptionBang", basedOn: "Normal", next: "Normal", run: { font: FONT, size: 26, italics: true } },
      ...[1, 2, 3].map((l) => ({ id: `TOC${l}`, name: `toc ${l}`, basedOn: "Normal", next: "Normal",
        run: { font: FONT, size: 26, bold: l <= 2 },
        paragraph: { spacing: { after: 60, line: 300 }, indent: { left: (l - 1) * 450 } } })),
      { id: "TOC4", name: "toc 4", basedOn: "Normal", next: "Normal",
        run: { font: FONT, size: 26 }, paragraph: { spacing: { after: 40, line: 288 }, indent: { left: 0 } } },
    ],
  },
  sections: sections.map((s) => ({
    properties: props[s.kind],
    footers: s.kind === "cover" ? undefined : { default: footer },
    children: s.children,
  })),
});

Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(OUT, buf); console.log("OK", OUT); });
