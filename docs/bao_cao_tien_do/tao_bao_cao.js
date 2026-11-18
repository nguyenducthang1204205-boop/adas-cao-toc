// Báo cáo tiến độ đồ án - tuần 1 đến tuần 3
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType, ShadingType,
  AlignmentType, ImageRun, PageOrientation, BorderStyle, LevelFormat, VerticalAlign, Footer, PageNumber,
} = require("docx");

const ROOT = "C:/A_Nam4/Đồ án/giaodien/docs";
const OUT = path.join(ROOT, "bao_cao_tien_do", "BAO_CAO_TIEN_DO_TUAN_1-3.docx");
const FONT = "Times New Roman";
const CM = 567;                       // DXA / cm
const PORTRAIT_W = 16 * CM;           // A4, lề trái 3 cm, phải 2 cm
const LANDSCAPE_W = 24.7 * CM;

// ---------------------------------------------------------------- tiện ích
function runs(content, base = {}) {
  // content: chuỗi, hoặc mảng [chuỗi | [chuỗi, {bold, italics}]]
  const parts = Array.isArray(content) ? content : [content];
  return parts.map((p) => (typeof p === "string"
    ? new TextRun({ text: p, font: FONT, ...base })
    : new TextRun({ text: p[0], font: FONT, ...base, ...p[1] })));
}
const P = (content, o = {}) => new Paragraph({
  children: runs(content, o.run || {}),
  alignment: o.align || AlignmentType.JUSTIFIED,
  spacing: { after: o.after ?? 100, before: o.before ?? 80, line: 300 },
  indent: o.indent,
  keepNext: o.keepNext,
});
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: runs(t), spacing: { before: 240, after: 120 } });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: runs(t), spacing: { before: 180, after: 100 } });
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: runs(t), spacing: { before: 140, after: 80 } });
const B = (content, level = 0) => new Paragraph({
  children: runs(content), numbering: { reference: "bullets", level },
  alignment: AlignmentType.JUSTIFIED, spacing: { after: 60, line: 300 },
});
const N = (content, ref) => new Paragraph({
  children: runs(content), numbering: { reference: ref, level: 0 },
  alignment: AlignmentType.JUSTIFIED, spacing: { after: 60, line: 300 },
});

const tableCaptions = new Set();
let figNo = 0;
let tabNo = 0;
function caption(kind, text) {
  const no = kind === "Hình" ? ++figNo : ++tabNo;
  const par = new Paragraph({
    children: runs([[`${kind} ${no}. `, { bold: true }], text], { italics: kind === "Hình", size: 24 }),
    alignment: AlignmentType.CENTER, spacing: { before: kind === "Hình" ? 60 : 200, after: kind === "Hình" ? 160 : 80 },
    keepNext: kind === "Bảng",
  });
  if (kind === "Bảng") tableCaptions.add(par);
  return par;
}
// Quy chuẩn: tên bảng đặt phía trên bảng -> đổi chỗ chú thích với bảng đứng ngay trước nó
function captionsAbove(arr) {
  for (let i = 1; i < arr.length; i++) {
    if (tableCaptions.has(arr[i]) && arr[i - 1] instanceof Table) [arr[i - 1], arr[i]] = [arr[i], arr[i - 1]];
  }
  return arr;
}
function figure(file, widthCm, text, maxHeightCm = 22) {
  const buf = fs.readFileSync(file);
  // kích thước gốc của ảnh PNG / JPG
  let w, h;
  if (buf[0] === 0x89) { w = buf.readUInt32BE(16); h = buf.readUInt32BE(20); }
  else {
    let i = 2;
    while (i < buf.length) {
      const len = buf.readUInt16BE(i + 2);
      if (buf[i + 1] >= 0xc0 && buf[i + 1] <= 0xc2) { h = buf.readUInt16BE(i + 5); w = buf.readUInt16BE(i + 7); break; }
      i += 2 + len;
    }
  }
  const PX = 37.795;   // px / cm (96 dpi)
  let ww = widthCm * PX;
  let hh = ww * h / w;
  if (hh > maxHeightCm * PX) { hh = maxHeightCm * PX; ww = hh * w / h; }
  return [
    new Paragraph({
      children: [new ImageRun({ type: file.endsWith(".png") ? "png" : "jpg", data: buf,
        transformation: { width: Math.round(ww), height: Math.round(hh) } })],
      alignment: AlignmentType.CENTER, spacing: { before: 80, after: 0 }, keepNext: true,
    }),
    caption("Hình", text),
  ];
}

const BORDER = { style: BorderStyle.SINGLE, size: 4, color: "000000" };
const BORDERS = { top: BORDER, bottom: BORDER, left: BORDER, right: BORDER };
function cell(content, width, o = {}) {
  const paras = (Array.isArray(content) && content.length && content[0] instanceof Paragraph)
    ? content
    : [].concat(content).map((c) => new Paragraph({
      children: runs(c, { size: 24, bold: o.bold }),
      alignment: o.align || AlignmentType.LEFT, spacing: { after: 20, line: 264 },
    }));
  return new TableCell({
    children: paras, borders: BORDERS, width: { size: width, type: WidthType.DXA },
    shading: o.fill ? { fill: o.fill, type: ShadingType.CLEAR, color: "auto" } : undefined,
    verticalAlign: o.valign || VerticalAlign.TOP,
    margins: { top: 50, bottom: 50, left: 90, right: 90 },
    columnSpan: o.span,
  });
}
function table(headers, rows, widthsCm, o = {}) {
  const widths = widthsCm.map((c) => Math.round(c * CM));
  const total = widths.reduce((a, b) => a + b, 0);
  const head = new TableRow({
    tableHeader: true,
    children: headers.map((h, i) => cell(h, widths[i], { bold: true, fill: "DCE6F1", align: AlignmentType.CENTER,
      valign: VerticalAlign.CENTER })),
  });
  const body = rows.map((r) => new TableRow({
    children: r.map((c, i) => cell(c, widths[i], { align: (o.center || []).includes(i) ? AlignmentType.CENTER : undefined })),
  }));
  return new Table({ width: { size: total, type: WidthType.DXA }, columnWidths: widths, rows: [head, ...body] });
}

// Đặc tả use case: bảng 2 cột, các bước là đoạn riêng
function ucSpec(rows) {
  const w = [3.4 * CM, 12.6 * CM];
  return new Table({
    width: { size: w[0] + w[1], type: WidthType.DXA }, columnWidths: w,
    rows: rows.map(([k, v], i) => new TableRow({
      children: [
        cell(k, w[0], { bold: true, fill: "EEF3F8" }),
        cell(i === 0 ? [[v, { bold: true }]] : v, w[1]),
      ],
    })),
  });
}

// ---------------------------------------------------------------- nội dung
const SO_DO = (n) => path.join(ROOT, "so_do", n);
const children1 = [];   // phần đầu (dọc)
const childrenL = [];   // BPMN (ngang)
const children2 = [];   // phần sau (dọc)

// Quốc hiệu
const NB = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const NOB = { top: NB, bottom: NB, left: NB, right: NB };
const hc = (lines, w) => new TableCell({
  borders: NOB, width: { size: w, type: WidthType.DXA }, margins: { left: 0, right: 0 },
  children: lines.map(([t, o]) => new Paragraph({ alignment: AlignmentType.CENTER, children: runs([[t, o]], { size: 24 }) })),
});
children1.push(new Table({
  width: { size: PORTRAIT_W, type: WidthType.DXA }, columnWidths: [6.8 * CM, 9.2 * CM],
  rows: [new TableRow({ children: [
    hc([["TRƯỜNG ĐẠI HỌC CÔNG NGHỆ", {}], ["THÔNG TIN VÀ TRUYỀN THÔNG", {}], ["KHOA CÔNG NGHỆ THÔNG TIN", { bold: true }]], 6.8 * CM),
    hc([["CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", { bold: true }], ["Độc lập - Tự do - Hạnh phúc", { bold: true }]], 9.2 * CM),
  ] })],
}));
children1.push(P(""));
children1.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 200, after: 60 },
  children: runs([["BÁO CÁO TIẾN ĐỘ ĐỒ ÁN TỐT NGHIỆP", { bold: true, size: 32 }]]) }));
children1.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 240 },
  children: runs([["Kỳ báo cáo: Tuần 1 - Tuần 3 (28/9/2026 - 18/10/2026)", { bold: true, size: 26 }]]) }));

children1.push(table(["Mục", "Thông tin"], [
  ["Sinh viên", "Nguyễn Đức Thắng - MSSV: DTC235200703 - Lớp: CNTT K22A CN"],
  ["Email", "dtc235200703@ictu.edu.vn"],
  ["Giảng viên hướng dẫn", "TS. Nguyễn Thành Trung - Bộ môn Kỹ thuật máy tính"],
  ["Tên đề tài", "Xây dựng hệ thống cảnh báo khoảng cách an toàn giữa các phương tiện trên cao tốc thời gian thực ứng dụng mô hình YOLOv11 và thị giác máy tính"],
  ["Thời gian thực hiện", "10 tuần, từ 28/9/2026 đến 7/12/2026"],
], [4.5, 11.5]));
children1.push(caption("Bảng", "Thông tin chung"));

// ---------------- I. Tổng hợp
children1.push(H1("I. TỔNG HỢP TIẾN ĐỘ"));
children1.push(P("Trong 3 tuần đầu, sinh viên thực hiện đúng các công việc theo mục 9 của đề cương: khảo sát thực tế, phân tích yêu cầu, xây dựng sơ đồ use case, viết đặc tả use case, thu thập và chuẩn hóa tập dữ liệu phương tiện. Bảng dưới tổng hợp kết quả so với kết quả dự kiến."));
children1.push(table(["Tuần", "Công việc (theo đề cương)", "Kết quả dự kiến", "Kết quả đạt được", "Tình trạng"], [
  [["1", "28/9 - 4/10"], "Khảo sát thực tế", "Các form mẫu dữ liệu, sơ đồ BPMN",
    ["Khảo sát quy định, giải pháp hiện có và quy trình giữ khoảng cách", "4 biểu mẫu dữ liệu", "3 sơ đồ BPMN"], "Hoàn thành"],
  [["2", "5/10 - 11/10"], "Phân tích yêu cầu chức năng / phi chức năng, xây dựng sơ đồ Use Case",
    "Bảng yêu cầu chức năng / phi chức năng, sơ đồ UC",
    ["16 yêu cầu chức năng", "10 yêu cầu phi chức năng", "1 sơ đồ UC tổng quát + 5 sơ đồ UC phân rã"], "Hoàn thành"],
  [["3", "12/10 - 18/10"], "Viết đặc tả Use Case, thu thập và chuẩn hóa Dataset phương tiện",
    "Bản đặc tả UC & tập Dataset phương tiện",
    ["Đặc tả đủ 5 UC chính", "Dataset 13.003 ảnh, 72.653 đối tượng, 5 lớp, định dạng YOLOv11, chia 70/20/10",
      "Phát hiện 4 vấn đề của dataset, có hướng xử lý ở tuần 6"], "Hoàn thành"],
], [1.9, 3.4, 3.2, 5.5, 2.0], { center: [0, 4] }));
children1.push(caption("Bảng", "Tổng hợp tiến độ tuần 1 - 3"));

// ---------------- II. Tuần 1
children1.push(H1("II. TUẦN 1 - KHẢO SÁT THỰC TẾ"));
children1.push(H2("1. Mục tiêu khảo sát"));
children1.push(B("Nắm quy định pháp lý về khoảng cách an toàn giữa các xe trên đường cao tốc Việt Nam."));
children1.push(B("Tìm hiểu các giải pháp cảnh báo khoảng cách đang có và hạn chế của chúng."));
children1.push(B("Mô tả quy trình giữ khoảng cách hiện tại và quy trình đề xuất khi có hệ thống (BPMN)."));
children1.push(B("Xác định các dữ liệu hệ thống cần thu thập, lưu trữ và xây dựng biểu mẫu dữ liệu."));

children1.push(H2("2. Quy định về khoảng cách an toàn"));
children1.push(P("Thông tư 31/2019/TT-BGTVT của Bộ Giao thông vận tải quy định khoảng cách an toàn tối thiểu giữa hai xe khi mặt đường khô ráo theo tốc độ lưu hành. Tốc độ tối đa trên đường cao tốc là 120 km/h. Khi trời mưa, có sương mù, mặt đường trơn trượt hoặc tầm nhìn hạn chế, người lái xe phải giữ khoảng cách lớn hơn trị số ghi trong bảng. Với tốc độ dưới 60 km/h, quy định để người lái xe tự chủ động giữ khoảng cách phù hợp."));
children1.push(table(["Tốc độ lưu hành V (km/h)", "Khoảng cách an toàn tối thiểu (m)"], [
  ["V = 60", "35"], ["60 < V ≤ 80", "55"], ["80 < V ≤ 100", "70"], ["100 < V ≤ 120", "100"],
], [8, 8], { center: [0, 1] }));
children1.push(caption("Bảng", "Khoảng cách an toàn tối thiểu khi mặt đường khô ráo (Thông tư 31/2019/TT-BGTVT)"));
children1.push(P([["Nhận xét: ", { bold: true }], "quy định cho trị số theo bậc tốc độ nhưng không cho hệ số cụ thể khi thời tiết xấu, và để trống vùng dưới 60 km/h. Hệ thống cần (1) tra bảng theo tốc độ xe chủ, (2) nhân thêm hệ số theo điều kiện mặt đường, (3) dùng quy tắc giãn cách 2 giây làm ước tính khi dưới 60 km/h."]));

children1.push(H2("3. Khảo sát các giải pháp hiện có"));
children1.push(table(["Giải pháp", "Nguyên lý", "Ưu điểm", "Hạn chế"], [
  ["Tài xế tự ước lượng", "Quan sát bằng mắt, quy tắc 2-3 giây, biển kiểm tra cự ly trên một số tuyến cao tốc",
    "Không cần thiết bị", "Chủ quan; khó ước lượng ở tốc độ cao, khi trời tối, mưa hoặc khi mệt mỏi"],
  ["ADAS tích hợp sẵn trên xe (cảnh báo va chạm phía trước)", "Radar / camera chuyên dụng của hãng xe",
    "Chính xác, ổn định", "Chủ yếu có trên xe đời mới, giá cao; không lắp thêm được cho xe đang sử dụng"],
  ["Thiết bị ADAS gắn thêm, camera hành trình có tính năng ADAS", "Camera + thuật toán nhúng trong thiết bị",
    "Lắp được cho xe cũ", "Ngưỡng do nhà sản xuất đặt sẵn, thường tính theo thời gian; người dùng khó chỉnh theo bảng quy định và điều kiện đường; ít khi có nhật ký vi phạm để tra cứu"],
  ["Nghiên cứu YOLO + ước lượng khoảng cách theo kích thước xe", "Mô hình camera lỗ kim, suy ra khoảng cách từ chiều cao / bề rộng khung bao",
    "Đơn giản, không cần căn chỉnh", "Sai số lớn vì kích thước thật của xe khác nhau; ít đề tài áp ngưỡng theo quy định Việt Nam"],
], [3.4, 4.2, 2.8, 5.6]));
children1.push(caption("Bảng", "So sánh các giải pháp cảnh báo khoảng cách"));
children1.push(P([["Hướng của đề tài: ", { bold: true }], "phần mềm chạy trên máy tính, dùng camera hành trình thông thường hoặc video đã ghi. YOLOv11 phát hiện xe; khoảng cách được đo bằng phép biến đổi phối cảnh ngược (IPM) trên mặt phẳng đường nên không phụ thuộc kích thước xe. Ngưỡng cảnh báo lấy theo bảng của Thông tư 31 nhân hệ số điều kiện đường. Mỗi lần vi phạm khoảng cách được ghi thành nhật ký kèm ảnh để tra cứu."]));

children1.push(H2("4. Quy trình nghiệp vụ"));
children1.push(P("Quy trình được mô hình hóa bằng BPMN 2.0 gồm 3 sơ đồ (Hình 1 - Hình 3):"));
children1.push(B([["Sơ đồ tổng quát: ", { bold: true }], "chọn nguồn → căn chỉnh camera (nếu nguồn chưa căn chỉnh) → cấu hình ngưỡng → giám sát và cảnh báo → xem lại nhật ký."]));
children1.push(B([["Chuẩn bị giám sát: ", { bold: true }], "tài xế chọn nguồn; hệ thống nạp căn chỉnh đã lưu của nguồn; nếu chưa có thì tài xế căn chỉnh camera và hệ thống lưu ma trận camera; tài xế chọn tốc độ, mô tả điều kiện đường; hệ thống tính và lưu ngưỡng an toàn."]));
children1.push(B([["Giám sát và cảnh báo (quy trình xử lý dữ liệu video/camera): ", { bold: true }], "với mỗi khung hình, hệ thống đọc khung → nhận diện và bám vết xe → xác định làn, tính khoảng cách IPM và thời gian va chạm (TTC) → so với ngưỡng; nếu có nguy cơ thì phát âm thanh và ghi đợt vi phạm kèm ảnh → hiển thị kết quả; lặp lại đến khi tài xế dừng hoặc hết video, cuối cùng đóng phiên giám sát."]));

childrenL.push(...figure(SO_DO("02_bpmn_quy_trinh_tong_quat.png"), 24.7, "BPMN quy trình tổng quát", 14));
children2.push(...figure(SO_DO("03_bpmn_chuan_bi_giam_sat.png"), 16, "BPMN chuẩn bị giám sát", 23));
children2.push(...figure(SO_DO("04_bpmn_giam_sat_canh_bao.png"), 16, "BPMN giám sát và cảnh báo (xử lý dữ liệu video/camera)", 23));

// ---------------- biểu mẫu
children2.push(H2("5. Biểu mẫu dữ liệu"));
children2.push(P("Từ khảo sát, hệ thống cần quản lý 4 nhóm dữ liệu. Mỗi biểu mẫu dưới đây liệt kê các trường cần thu thập kèm một giá trị ví dụ trên video thử nghiệm (camera hành trình VIETMAP, đường cao tốc, 640×360)."));
const formTable = (rows) => table(["STT", "Trường dữ liệu", "Kiểu / miền giá trị", "Ví dụ"],
  rows.map((r, i) => [String(i + 1), ...r]), [1.1, 5.0, 4.4, 5.5], { center: [0] });

children2.push(H3("Biểu mẫu 1. Phiếu thông tin nguồn video / camera"));
children2.push(formTable([
  ["Tên nguồn", "Chuỗi, bắt buộc", "Dashcam VIETMAP cao tốc"],
  ["Loại nguồn", "video | camera | stream | image", "video"],
  ["Địa chỉ nguồn", "Đường dẫn file / chỉ số camera / URL RTSP, không trùng", "…\\Downloads\\videoplayback.mp4"],
  ["Ghi chú", "Chuỗi, tùy chọn", "-"],
  ["Ngày thêm", "Ngày giờ", "29/09/2026 23:46"],
  ["Lần dùng gần nhất", "Ngày giờ", "04/10/2026 00:37"],
]));
children2.push(caption("Bảng", "Biểu mẫu nguồn video / camera"));

children2.push(H3("Biểu mẫu 2. Phiếu thông số căn chỉnh camera (IPM)"));
children2.push(formTable([
  ["Nguồn áp dụng", "Tham chiếu nguồn", "Dashcam VIETMAP cao tốc"],
  ["Phương pháp", "Thủ công | Tự động", "Thủ công"],
  ["Kích thước khung hình", "Rộng × cao (px)", "640 × 360"],
  ["4 điểm trên ảnh (tỷ lệ 0..1)", "Gần-trái, gần-phải, xa-phải, xa-trái", "(0,357; 0,698), (0,662; 0,698), (0,554; 0,578), (0,465; 0,578)"],
  ["Bề rộng làn W", "Mét", "3,75"],
  ["Chiều dài đoạn đánh dấu L", "Mét", "20"],
  ["Đầu xe → cạnh gần d₀", "Mét", "5,7"],
  ["Nửa bề rộng làn / tầm đo tối đa", "Mét", "1,9 / 150"],
  ["Tiêu cự f, chiều cao camera, góc chúc", "px, m, độ (tính từ H)", "432,3 px; 1,18 m; −1,33°"],
  ["Đường chân trời", "Hàng pixel", "190"],
  ["Ma trận K, H, R", "Ma trận 3×3", "K = [[432,3; 0; 320]; [0; 432,3; 180]; [0; 0; 1]]"],
]));
children2.push(caption("Bảng", "Biểu mẫu thông số căn chỉnh camera"));

children2.push(H3("Biểu mẫu 3. Phiếu cấu hình ngưỡng cảnh báo"));
children2.push(formTable([
  ["Tốc độ xe chủ", "0 - 150 km/h", "90 km/h"],
  ["Điều kiện mặt đường", "5 mẫu: khô ráo, ướt / mưa nhỏ, mưa to, sương mù, trơn trượt", "Mưa to, mặt đường đọng nước"],
  ["Hệ số điều kiện", "1,0 - 3,0", "2,0"],
  ["Hệ số bám mặt đường μ", "0,1 - 0,9", "0,35"],
  ["Tầm nhìn xa", "0 - 1000 m (0 = không hạn chế)", "0"],
  ["TTC cảnh báo / nguy hiểm", "2 - 8 s / 1 - 4 s", "6 s / 3 s"],
  ["Tỷ lệ ngưỡng nguy hiểm", "0,3 - 0,8", "0,5"],
  ["Khoảng cách luôn nguy hiểm", "3 - 20 m", "5 m"],
  ["Kết quả: ngưỡng cảnh báo / nguy hiểm", "Mét (tính tự động)", "Quy định 70 m × 2,0 → cảnh báo < 140 m, nguy hiểm < 70 m"],
]));
children2.push(caption("Bảng", "Biểu mẫu cấu hình ngưỡng cảnh báo"));

children2.push(H3("Biểu mẫu 4. Phiếu nhật ký vi phạm khoảng cách"));
children2.push(formTable([
  ["Phiên giám sát / mã vi phạm", "Số nguyên", "Phiên 1 / vi phạm 2"],
  ["Thời điểm bắt đầu, thời lượng", "Ngày giờ, giây", "29/09/2026 23:54:49, 5,43 s"],
  ["Thời điểm trong video", "Giây", "21,27"],
  ["Mức vi phạm", "Cảnh báo | Nguy hiểm", "Cảnh báo"],
  ["Phương tiện phía trước", "Loại xe + mã bám vết", "Ô tô #1"],
  ["Khoảng cách ban đầu / nhỏ nhất", "Mét", "34,38 / 34,09"],
  ["TTC nhỏ nhất, tốc độ tiếp cận", "Giây, km/h", "16,3 s; 6,4 km/h"],
  ["Tốc độ xe chủ", "km/h", "73"],
  ["Ngưỡng cảnh báo / nguy hiểm / quy định", "Mét", "55 / 27,5 / 55"],
  ["Điều kiện đường, hệ số", "Chuỗi, số thực", "Đường khô ráo, tầm nhìn tốt; 1,0"],
  ["Ảnh bằng chứng", "Đường dẫn ảnh", "data/snapshots/session_1/violation_2.jpg"],
]));
children2.push(caption("Bảng", "Biểu mẫu nhật ký vi phạm"));
children2.push(P([["Kết quả tuần 1: ", { bold: true }], "hoàn thành khảo sát quy định và giải pháp hiện có, 3 sơ đồ BPMN, 4 biểu mẫu dữ liệu (là cơ sở thiết kế CSDL ở tuần 4)."]));

// ---------------- III. Tuần 2
children2.push(H1("III. TUẦN 2 - PHÂN TÍCH YÊU CẦU VÀ SƠ ĐỒ USE CASE"));
children2.push(H2("1. Tác nhân"));
children2.push(table(["Tác nhân", "Loại", "Mô tả"], [
  ["Người dùng (tài xế / người vận hành)", "Chính", "Chọn nguồn, căn chỉnh camera, chọn tốc độ và điều kiện đường, theo dõi cảnh báo, tra cứu nhật ký"],
  ["Camera / nguồn video", "Phụ", "Cung cấp khung hình: camera USB, camera IP (RTSP/HTTP) hoặc file video, ảnh"],
  ["Dịch vụ Claude API", "Phụ, tùy chọn", "Gợi ý ngưỡng an toàn từ mô tả tình huống; mặc định hệ thống dùng trợ lý offline, không cần Internet"],
], [4.6, 2.4, 9.0]));
children2.push(caption("Bảng", "Các tác nhân của hệ thống"));

children2.push(H2("2. Yêu cầu chức năng"));
children2.push(table(["Mã", "Chức năng", "Mô tả", "UC"], [
  ["FR-01", "Quản lý nguồn video/camera", "Thêm, sửa, xóa, kiểm tra kết nối, dò camera USB, chọn nguồn để giám sát", "UC01"],
  ["FR-02", "Nhận nhiều loại nguồn", "File video, ảnh tĩnh, camera USB (chỉ số 0-4), luồng RTSP/HTTP", "UC01, UC04"],
  ["FR-03", "Căn chỉnh camera (IPM)", "Chấm 4 điểm trên vạch làn hoặc tự động từ video; lưu ma trận K, H, R theo từng nguồn", "UC02"],
  ["FR-04", "Nhận diện phương tiện", "YOLOv11 phát hiện, phân loại ô tô, xe tải, xe khách; ByteTrack gán mã bám vết", "UC04"],
  ["FR-05", "Nhận diện làn xe chủ", "Tìm 2 vạch làn đang đi để chỉ xét xe cùng làn phía trước", "UC04"],
  ["FR-06", "Tính khoảng cách thực", "Đổi điểm chạm đất (giữa cạnh dưới khung bao) sang mét bằng IPM", "UC04"],
  ["FR-07", "Tốc độ tiếp cận và TTC", "Làm mượt khoảng cách theo thời gian, ước lượng tốc độ tiếp cận và thời gian va chạm", "UC04"],
  ["FR-08", "Ngưỡng theo tốc độ", "Bảng Thông tư 31 (V ≥ 60 km/h), quy tắc 2 giây (V < 60) × hệ số điều kiện đường", "UC03, UC04"],
  ["FR-09", "Cảnh báo hình ảnh", "Khung xe đổi màu xanh / vàng / đỏ, vùng nguy hiểm, banner, ảnh nhìn từ trên xuống (BEV)", "UC04"],
  ["FR-10", "Cảnh báo âm thanh", "Hai mức âm: cảnh báo và nguy hiểm, có thể bật / tắt", "UC04"],
  ["FR-11", "Tùy chỉnh ngưỡng", "Tốc độ xe chủ, điều kiện đường, hệ số, TTC, tỷ lệ nguy hiểm, chống báo nhầm", "UC03"],
  ["FR-12", "Trợ lý AI gợi ý ngưỡng", "Tài xế mô tả tình huống bằng tiếng Việt, trợ lý đề xuất và áp dụng ngưỡng theo tốc độ xe chủ", "UC03"],
  ["FR-13", "Ghi nhật ký vi phạm", "Mỗi đợt vi phạm ghi 1 bản ghi kèm ảnh bằng chứng", "UC04, UC05"],
  ["FR-14", "Tra cứu nhật ký", "Lọc theo phiên, ngày, mức, loại xe; xem ảnh; xuất CSV; xóa", "UC05"],
  ["FR-15", "Lưu cấu hình và lịch sử", "Lưu cấu hình hiện hành, bản chụp mỗi lần thay đổi, cho phép khôi phục", "UC03, UC05"],
  ["FR-16", "Ghi video kết quả", "Lưu video đã vẽ lớp phủ cảnh báo", "UC04"],
], [1.5, 3.6, 8.9, 2.0], { center: [0, 3] }));
children2.push(caption("Bảng", "Yêu cầu chức năng"));

children2.push(H2("3. Yêu cầu phi chức năng"));
children2.push(table(["Mã", "Yêu cầu", "Chỉ tiêu", "Cách kiểm chứng"], [
  ["NFR-01", "Tốc độ xử lý thời gian thực", "≥ 25 FPS trên GPU", "Đo FPS khi chạy video thử nghiệm"],
  ["NFR-02", "Độ trễ xử lý 1 khung", "≤ 50 ms", "Đo thời gian từng tầng xử lý mỗi khung"],
  ["NFR-03", "Độ chính xác nhận dạng", "mAP@0,5 ≥ 0,80", "Đánh giá mô hình trên tập kiểm thử"],
  ["NFR-04", "Chạy được khi không có GPU", "≥ 5 FPS trên CPU", "Chạy ở chế độ CPU"],
  ["NFR-05", "Chống báo nhầm", "Chỉ nâng mức sau 3 khung liên tiếp (≈ 0,1 s ở 30 FPS)", "Kiểm thử với nhận diện chập chờn"],
  ["NFR-06", "Camera trực tiếp độ trễ thấp", "Luôn xử lý khung mới nhất", "Đọc camera ở luồng riêng"],
  ["NFR-07", "Giao diện không bị treo", "Xử lý ở luồng nền", "Thao tác giao diện khi đang giám sát"],
  ["NFR-08", "Lưu trữ tin cậy", "Ghi đồng thời từ giao diện và luồng xử lý; ràng buộc toàn vẹn", "Kiểm tra khóa ngoại, CHECK, chế độ WAL"],
  ["NFR-09", "Giao diện tiếng Việt", "Hiển thị đủ dấu trên giao diện và khung video", "Kiểm tra trực quan"],
  ["NFR-10", "Hoạt động không cần Internet", "Mọi chức năng chính chạy offline", "Ngắt mạng khi chạy"],
], [1.7, 4.3, 5.4, 4.6], { center: [0] }));
children2.push(caption("Bảng", "Yêu cầu phi chức năng"));

children2.push(H2("4. Sơ đồ use case"));
children2.push(P("Hệ thống có 5 use case chính đúng như đề cương: UC01 Quản lý nguồn video/camera, UC02 Cấu hình thông số IPM, UC03 Cấu hình ngưỡng cảnh báo, UC04 Giám sát realtime & cảnh báo, UC05 Quản lý nhật ký cảnh báo."));
children2.push(...figure(SO_DO("05_usecase_tong_quat.png"), 16, "Sơ đồ use case tổng quát"));
children2.push(...figure(SO_DO("06_usecase_UC01_nguon_video.png"), 16, "Phân rã UC01 - Quản lý nguồn video/camera"));
children2.push(...figure(SO_DO("07_usecase_UC02_cau_hinh_IPM.png"), 16, "Phân rã UC02 - Cấu hình thông số IPM"));
children2.push(...figure(SO_DO("08_usecase_UC03_nguong_canh_bao.png"), 16, "Phân rã UC03 - Cấu hình ngưỡng cảnh báo"));
children2.push(...figure(SO_DO("09_usecase_UC04_giam_sat.png"), 16, "Phân rã UC04 - Giám sát realtime & cảnh báo"));
children2.push(...figure(SO_DO("10_usecase_UC05_nhat_ky.png"), 16, "Phân rã UC05 - Quản lý nhật ký cảnh báo"));
children2.push(P([["Kết quả tuần 2: ", { bold: true }], "16 yêu cầu chức năng, 10 yêu cầu phi chức năng có chỉ tiêu đo được, 1 sơ đồ use case tổng quát và 5 sơ đồ phân rã."]));

// ---------------- IV. Tuần 3
children2.push(H1("IV. TUẦN 3 - ĐẶC TẢ USE CASE VÀ TẬP DỮ LIỆU"));
children2.push(H2("1. Đặc tả use case"));

const UC = [
  ["UC01 - Quản lý nguồn video/camera", {
    md: "Thêm, sửa, xóa, kiểm tra kết nối và chọn nguồn đầu vào (file video, ảnh, camera USB, luồng RTSP/HTTP).",
    ta: "Người dùng (chính); Camera / nguồn video (phụ).",
    pre: "Ứng dụng đã khởi động, CSDL đã khởi tạo.",
    post: "Bảng nguồn video được cập nhật; nguồn được chọn chuyển sang giám sát (UC04); thời điểm dùng gần nhất được cập nhật.",
    main: [
      "Người dùng bấm nút chọn nguồn (▾) trên thanh tiêu đề, chọn “Quản lý nguồn…”.",
      "Hệ thống mở cửa sổ Quản lý nguồn, hiển thị danh sách: tên, loại, địa chỉ nguồn, tình trạng căn chỉnh, số phiên, lần dùng gần nhất.",
      "Người dùng bấm “Thêm file video” và chọn file (mp4, avi, mov, mkv, wmv hoặc ảnh).",
      "Hệ thống xác định loại nguồn, chuẩn hóa đường dẫn và thêm nguồn mới.",
      "Người dùng chọn nguồn, bấm “Kiểm tra kết nối”.",
      "Hệ thống mở thử nguồn ở luồng nền, hiển thị khung xem trước và “Kết nối tốt · độ phân giải · FPS · số khung”.",
      "Người dùng bấm “Mở nguồn đã chọn” (hoặc nhấp đúp vào dòng).",
      "Hệ thống dừng phiên đang chạy (nếu có), đặt nguồn mới, nạp căn chỉnh camera đã lưu của nguồn và bắt đầu giám sát (UC04).",
    ],
    alt: [
      "A1. Thêm camera / URL: bấm “Thêm camera / URL”, nhập tên, địa chỉ (0, 1… hoặc rtsp://…), ghi chú → Lưu.",
      "A2. Dò camera USB: hệ thống thử chỉ số 0-4 và tự thêm các “Camera USB i” chưa có.",
      "A3. Sửa: chọn nguồn → “Sửa” → đổi tên / địa chỉ / ghi chú → Lưu.",
      "A4. Xóa: chọn nguồn → “Xóa” → xác nhận; ma trận camera của nguồn bị xóa theo, nhật ký các phiên cũ vẫn giữ.",
      "A5. Mở nhanh từ menu nguồn: “Mở video…” (Ctrl+O), “Mở ảnh…”, “Camera trực tiếp…” hoặc một nguồn trong mục “Dùng gần đây”; nguồn tự được đăng ký.",
    ],
    ex: [
      "E1. Địa chỉ trống: “Chưa nhập địa chỉ nguồn.”",
      "E2. File không tồn tại: “Không tìm thấy file: …”",
      "E3. Nguồn trùng: “Nguồn này đã có trong danh sách.”; sửa trùng địa chỉ: “Không lưu được: …”",
      "E4. Không mở được nguồn: “Không kết nối được: <lỗi>”",
      "E5. Không có camera: “Không tìm thấy camera USB nào.”",
    ],
  }],
  ["UC02 - Cấu hình thông số IPM (căn chỉnh camera)", {
    md: "Xác định ma trận homography H (pixel → mét trên mặt đường) và ma trận camera K, R cho từng nguồn để tính khoảng cách.",
    ta: "Người dùng.",
    pre: "Có khung hình tham chiếu: khung đang giám sát, khung đầu của nguồn đang chọn, hoặc ảnh / video người dùng chọn.",
    post: "Thông số căn chỉnh mới có hiệu lực từ khung kế tiếp; lưu ma trận camera (thủ công / tự động) gắn với nguồn; lưu lịch sử cấu hình.",
    main: [
      "Người dùng bấm “Căn chỉnh camera” (hoặc “Căn chỉnh ngay” trên thanh nhắc khi nguồn chưa được căn chỉnh).",
      "Hệ thống tạm dừng giám sát (nếu đang chạy), mở cửa sổ căn chỉnh với khung hình và 4 điểm hiện tại.",
      "Người dùng nhấp / kéo 4 điểm trên 2 vạch làn xe chủ theo thứ tự gần-trái → gần-phải → xa-phải → xa-trái.",
      "Người dùng nhập kích thước thực: bề rộng làn W (mặc định 3,75 m), chiều dài L, khoảng cách đầu xe → cạnh gần d₀, nửa bề rộng làn (1,9 m), tầm đo tối đa (150 m), góc nhìn dọc, khoảng cách camera → đầu xe.",
      "Hệ thống tính H, hiển thị ảnh nhìn từ trên xuống (BEV, lưới 10 m), đường chân trời, tiêu cự, chiều cao camera, góc chúc.",
      "Người dùng kiểm tra vạch làn trên BEV song song, thẳng đứng và bấm “Áp dụng”.",
      "Hệ thống cập nhật cấu hình, lưu CSDL (cấu hình hiện hành, lịch sử cấu hình, ma trận K, H, R của nguồn), báo “Đã lưu ma trận camera #id cho nguồn …” và tiếp tục giám sát.",
    ],
    alt: [
      "A1. Tự động căn chỉnh (nguồn là file video): bấm “Tự động căn chỉnh”, nhập tốc độ xe trong video (0 nếu không biết) → hệ thống phân tích ở luồng nền: điểm tụ (Hough + RANSAC), bề rộng làn → chiều cao camera, chuyển động vạch đứt → hệ số chiều sâu K = f·h → tự điền 4 điểm và thông số.",
      "A2. “Chấm lại 4 điểm” xóa các điểm đã chấm; “Về vị trí mặc định” khôi phục 4 điểm mặc định.",
      "A3. Mở lại một nguồn đã căn chỉnh: hệ thống tự nạp ma trận camera mới nhất của nguồn.",
    ],
    ex: [
      "E1. Chưa đủ 4 điểm: khóa nút Áp dụng, hiển thị “Đã chọn n/4 điểm.”",
      "E2. 4 điểm suy biến: “Điểm không hợp lệ: …”",
      "E3. Tự động thất bại: “Không tự căn chỉnh được: … Hãy tự chấm 4 điểm.”; không đo được chuyển động vạch kẻ: cảnh báo khoảng cách có thể sai lệch.",
      "E4. Không đọc được khung hình: “Không đọc được khung hình.”",
      "E5. Bấm “Hủy”: giữ nguyên căn chỉnh cũ, tiếp tục giám sát.",
    ],
  }],
  ["UC03 - Cấu hình ngưỡng cảnh báo", {
    md: "Điều chỉnh ngưỡng khoảng cách an toàn theo tốc độ xe chủ và điều kiện đường, thủ công hoặc nhờ Trợ lý AI gợi ý.",
    ta: "Người dùng; Dịch vụ Claude API (tùy chọn).",
    pre: "Ứng dụng đang mở (đang hoặc chưa giám sát).",
    post: "Tốc độ và chính sách ngưỡng mới có hiệu lực từ khung kế tiếp; lưu cấu hình hiện hành và lịch sử cấu hình.",
    main: [
      "Người dùng bấm “Cài đặt”, chọn tab “Điều kiện đường”.",
      "Người dùng chọn thời tiết / mặt đường (5 mẫu: khô ráo ×1; ướt, mưa nhỏ ×1,4; mưa to ×2; sương mù ×1,5; trơn trượt ×2,5) và tầm nhìn xa.",
      "Hệ thống tự điền hệ số điều kiện, μ, TTC cảnh báo / nguy hiểm và hiển thị tóm tắt ngưỡng.",
      "Tùy chọn, ở tab “Nâng cao” người dùng tinh chỉnh trong giới hạn: hệ số 1-3, μ 0,1-0,9, giãn cách dưới 60 km/h 2-6 s, tỷ lệ nguy hiểm 0,3-0,8, khoảng cách luôn nguy hiểm 3-20 m, TTC cảnh báo 2-8 s, TTC nguy hiểm 1-4 s, áp dụng bảng quy định Bộ GTVT; chống báo nhầm (1-15 khung xác nhận, thời gian giữ cảnh báo).",
      "Ở tab “Chung”: chọn loại xe theo dõi, bật / tắt và nghe thử âm thanh, chỉ cảnh báo xe cùng làn, tự nhận diện làn.",
      "Người dùng bấm “Lưu”.",
      "Hệ thống cập nhật cấu hình, lưu CSDL (“Cài đặt hệ thống”), cập nhật thẻ tốc độ và điều kiện đường; luồng xử lý dùng ngưỡng mới từ khung kế tiếp.",
    ],
    alt: [
      "A1. Đổi tốc độ xe chủ: chọn nấc 60 / ≤80 / ≤100 / ≤120 km/h trên thẻ “Tốc độ xe của bạn”; hệ thống tính lại và hiển thị ngay “Cảnh báo < X m · Nguy hiểm < Y m” cùng căn cứ (quy định hay ước tính 2 giây).",
      "A2. Trợ lý AI: bấm 1 trong 8 nút điều kiện (Khô ráo, Mưa nhỏ, Mưa to, Sương mù, Trơn trượt, Ban đêm, Chở nặng, Mệt mỏi) hoặc gõ mô tả (vd “đang mưa, tôi chạy 90 km/h”) → hệ thống phân tích ở luồng nền (mặc định trợ lý offline; nếu bật thì gọi Claude) → giới hạn tham số trong phạm vi cho phép → áp dụng, đổi tốc độ nếu tài xế nêu → báo “Đã áp dụng: … cảnh báo < X m, nguy hiểm < Y m” → lưu lịch sử “Trợ lý AI (…)”.",
      "A3. Nút “Mặc định” trên thẻ Điều kiện đường: khôi phục ngưỡng mặc định (đường khô ráo), xóa lịch sử hội thoại.",
      "A4. Khôi phục một cấu hình cũ từ “Lịch sử cấu hình” (UC05).",
    ],
    ex: [
      "E1. Đã bật Claude nhưng không có mạng / API key hoặc dịch vụ lỗi: tự chuyển sang tư vấn offline, hiển thị ghi chú lỗi.",
      "E2. TTC nguy hiểm không nhỏ hơn TTC cảnh báo: tự đặt TTC nguy hiểm = TTC cảnh báo − 0,5 s.",
      "E3. Không có thiết bị âm thanh khi nghe thử: “Không phát được âm thanh (không có thiết bị âm thanh).”",
      "E4. Bỏ chọn hết loại xe: tự giữ lớp ô tô.",
    ],
  }],
  ["UC04 - Giám sát realtime & cảnh báo", {
    md: "Xử lý liên tục video / camera: nhận diện xe, đo khoảng cách, phát cảnh báo hình ảnh và âm thanh, ghi nhật ký vi phạm.",
    ta: "Người dùng; Camera / nguồn video.",
    pre: "Đã chọn nguồn (UC01); có file trọng số YOLOv11 (models/best.pt hoặc dự phòng yolo11n.pt).",
    post: "Một phiên giám sát được lưu (số khung, FPS trung bình); các vi phạm kèm ảnh bằng chứng; tùy chọn video kết quả.",
    main: [
      "Người dùng bấm “Bắt đầu” (F5).",
      "Hệ thống đăng ký nguồn, nạp căn chỉnh camera của nguồn, khởi động luồng xử lý nền.",
      "Luồng xử lý mở nguồn, tải YOLOv11 (GPU nếu có), chạy khởi động, đọc khung đầu, mở phiên giám sát (lưu kèm cấu hình lúc chạy).",
      "Với mỗi khung: YOLOv11 + ByteTrack nhận diện xe (khung bao, loại xe, mã bám vết); nhận diện làn xe chủ; đổi điểm chạm đất sang mét bằng IPM → khoảng cách, độ lệch ngang; làm mượt, tính tốc độ tiếp cận và TTC.",
      "Tính ngưỡng theo tốc độ và điều kiện đường; phân loại từng xe cùng làn: an toàn / cảnh báo / nguy hiểm; xe phía trước là xe cùng làn gần nhất.",
      "Chống báo nhầm: chỉ nâng mức sau 3 khung liên tiếp, giữ mức tối thiểu 0,8 s mới hạ; phát âm (cảnh báo 820 Hz mỗi 0,9 s; nguy hiểm 1250 Hz mỗi 0,28 s).",
      "Ghi nhật ký: mở đợt vi phạm khi mức ổn định là cảnh báo / nguy hiểm (chụp ảnh); nâng mức thì cập nhật ảnh; an toàn trở lại hoặc đổi xe phía trước thì đóng đợt (thời lượng, khoảng cách nhỏ nhất, TTC nhỏ nhất).",
      "Vẽ khung màu (xanh / vàng / đỏ), nhãn “Ô tô #id 24,2 m”, vùng nguy hiểm, banner cảnh báo, ảnh nhìn từ trên xuống; cập nhật thẻ trạng thái (khoảng cách, TTC, tốc độ tiếp cận, FPS, thời gian từng tầng) và danh sách vi phạm của phiên.",
      "Người dùng bấm “Dừng” (Esc) hoặc video hết.",
      "Hệ thống đóng đợt vi phạm đang mở, kết thúc phiên, báo “Phiên #id: đã ghi n vi phạm vào CSDL”.",
    ],
    alt: [
      "A1. “Tạm dừng” (Space) / tiếp tục; video tiếp tục đúng nhịp thời gian thực.",
      "A2. Bật “Ghi video” trước khi bắt đầu → lưu video đã vẽ lớp phủ.",
      "A3. Nút “Âm thanh”: bật / tắt tiếng khi đang chạy.",
      "A4. Đổi tốc độ / ngưỡng (UC03) hoặc căn chỉnh camera (UC02) giữa chừng → áp dụng ở khung kế tiếp, không cần chạy lại.",
      "A5. Nguồn là ảnh tĩnh: xử lý 1 khung, không chống nhiễu.",
      "A6. Xe ngoài tầm đo (trên đường chân trời hoặc xa hơn 150 m): nhãn “Xa”, không cảnh báo.",
      "A7. Chưa nhận diện được làn (vạch mờ, ban đêm): dùng hành lang cố định ±1,9 m quanh trục xe.",
    ],
    ex: [
      "E1. Chưa chọn nguồn: mở hộp chọn file video.",
      "E2. Không mở được nguồn hoặc lỗi mô hình: hộp thoại “Lỗi xử lý: …”.",
      "E3. Nguồn không có khung hình: “Nguồn video không có khung hình nào”.",
      "E4. Không có best.pt: dùng yolo11n.pt (COCO); thiếu cả hai thì tự tải về.",
      "E5. Không có thiết bị âm thanh: vẫn cảnh báo hình ảnh, thanh trạng thái báo “không có thiết bị âm thanh”.",
      "E6. Không tạo được file ghi video: “Không tạo được file ghi video - bỏ qua ghi hình.”",
    ],
  }],
  ["UC05 - Quản lý nhật ký cảnh báo", {
    md: "Tra cứu, lọc, xem ảnh bằng chứng, xuất và xóa nhật ký vi phạm; xem lịch sử cấu hình và ma trận camera.",
    ta: "Người dùng.",
    pre: "CSDL tồn tại (có ít nhất 1 phiên giám sát để có dữ liệu).",
    post: "Dữ liệu được hiển thị / xuất CSV; nếu xóa: bản ghi và ảnh bằng chứng bị xóa; nếu khôi phục: cấu hình cũ được áp dụng.",
    main: [
      "Người dùng bấm “Lịch sử” trên thanh tiêu đề (hoặc nút “Lịch sử” ở tab Vi phạm).",
      "Hệ thống mở cửa sổ Lịch sử, hiển thị thống kê (số phiên, số vi phạm, nguy hiểm / cảnh báo, khoảng cách gần nhất) và danh sách phiên, dòng đầu là “Tất cả phiên”.",
      "Người dùng chọn một phiên.",
      "Hệ thống hiển thị các vi phạm: mã, thời điểm, giây trong video, mức, loại xe, khoảng cách ban đầu / nhỏ nhất, TTC nhỏ nhất, thời lượng, ngưỡng cảnh báo / nguy hiểm, quy định, tốc độ xe, điều kiện đường.",
      "Người dùng lọc theo khoảng ngày, mức (nguy hiểm / cảnh báo), loại xe.",
      "Người dùng chọn một vi phạm; hệ thống hiển thị ảnh bằng chứng và tóm tắt.",
      "Người dùng bấm “Xuất CSV”, chọn nơi lưu; hệ thống ghi file CSV mở được bằng Excel.",
    ],
    alt: [
      "A1. “Xóa vi phạm đã chọn” → xác nhận → xóa bản ghi và ảnh.",
      "A2. “Xóa phiên đã chọn” → xác nhận → xóa phiên, toàn bộ vi phạm và ảnh của phiên.",
      "A3. Tab “Lịch sử cấu hình”: xem bản chụp cấu hình theo thời gian và lý do; “Khôi phục cấu hình này” → xác nhận → áp dụng.",
      "A4. Tab “Ma trận camera”: xem K, H, R, tiêu cự, chiều cao, góc chúc, chân trời của từng lần căn chỉnh.",
      "A5. “Mở thư mục CSDL”: mở thư mục chứa dữ liệu.",
      "A6. Khi đang giám sát: tab “Vi phạm” ở cửa sổ chính hiển thị vi phạm của phiên hiện tại và cho xuất CSV.",
    ],
    ex: [
      "E1. Không có vi phạm để xuất: “Không có vi phạm nào để xuất.”",
      "E2. Ảnh bằng chứng đã bị xóa khỏi ổ đĩa: vùng ảnh để trống, ghi “không có ảnh”.",
      "E3. Chọn “No” ở hộp xác nhận: không xóa / không khôi phục.",
    ],
  }],
];
const stepParas = (items, numbered) => items.map((t, i) => new Paragraph({
  children: runs((numbered ? `${i + 1}. ` : "") + t, { size: 24 }), spacing: { after: 30, line: 264 },
  alignment: AlignmentType.LEFT,
}));
UC.forEach(([name, s]) => {
  children2.push(H3(name));
  children2.push(ucSpec([
    ["Mã / Tên", name],
    ["Mục đích", s.md],
    ["Tác nhân", s.ta],
    ["Tiền điều kiện", s.pre],
    ["Hậu điều kiện", s.post],
    ["Luồng chính", stepParas(s.main, true)],
    ["Luồng thay thế", stepParas(s.alt, false)],
    ["Ngoại lệ", stepParas(s.ex, false)],
  ]));
  children2.push(caption("Bảng", `Đặc tả ${name.split(" - ")[0]}`));
});

// ---------------- dataset
children2.push(H2("2. Thu thập và chuẩn hóa tập dữ liệu phương tiện"));
children2.push(H3("2.1. Nguồn dữ liệu"));
children2.push(B("Nguồn: Roboflow (workspace thang-nguyen-wrkwt, dự án distance-estimation-model, phiên bản 1), giấy phép CC BY 4.0."));
children2.push(B("Quy mô: 13.003 ảnh, 72.653 đối tượng được gán nhãn, 5 lớp: Jeepney, bus, car, motorcycle, truck."));
children2.push(B("Ảnh là các khung hình trích từ video camera hành trình; kích thước phần lớn 1280×720, một số ảnh 3840×2160."));
children2.push(H3("2.2. Chuẩn hóa"));
children2.push(B("Định dạng nhãn YOLOv11: mỗi ảnh một file .txt, mỗi dòng “lớp x_tâm y_tâm rộng cao” với tọa độ chuẩn hóa về 0..1; file data.yaml khai báo đường dẫn và tên lớp."));
children2.push(B("Chia tập: train 70% (9.102 ảnh), valid 20% (2.601 ảnh), test 10% (1.300 ảnh). Không tăng cường dữ liệu ở bước xuất; tăng cường (mosaic…) sẽ thực hiện khi huấn luyện ở tuần 6."));
children2.push(B("Ảnh nền không có đối tượng được giữ lại (57 / 17 / 8 ảnh ở train / valid / test) để mô hình học các khung không có xe."));
children2.push(B("Ánh xạ sang yêu cầu đề tài: ô tô (car), xe tải (truck), xe khách (bus) là 3 lớp mục tiêu; Jeepney (xe khách loại nhỏ) được cảnh báo cùng nhóm xe khách; xe máy (motorcycle) có trong tập dữ liệu nhưng mặc định không theo dõi vì không lưu thông trên cao tốc (có thể bật lại trong phần cài đặt)."));
children2.push(table(["Lớp", "Train", "Valid", "Test", "Tổng", "Tỷ lệ"], [
  ["Ô tô (car)", "29.244", "8.318", "4.078", "41.640", "57,3%"],
  ["Xe máy (motorcycle)", "15.697", "4.669", "2.195", "22.561", "31,1%"],
  ["Xe tải (truck)", "3.841", "1.063", "588", "5.492", "7,6%"],
  ["Jeepney", "1.625", "518", "219", "2.362", "3,3%"],
  ["Xe khách (bus)", "419", "126", "53", "598", "0,8%"],
  [[["Tổng số đối tượng", { bold: true }]], "50.826", "14.694", "7.133", "72.653", "100%"],
  [[["Số ảnh", { bold: true }]], "9.102", "2.601", "1.300", "13.003", ""],
], [4.4, 2.3, 2.3, 2.3, 2.4, 2.3], { center: [1, 2, 3, 4, 5] }));
children2.push(caption("Bảng", "Thống kê đối tượng theo lớp và theo tập"));
children2.push(...figure(path.join(ROOT, "bao_cao_tien_do", "hinh", "dataset_mau.jpg"), 16, "Ảnh mẫu trong tập dữ liệu kèm nhãn (vẽ lại từ file nhãn YOLO)"));

children2.push(H3("2.3. Đánh giá tập dữ liệu"));
children2.push(P("Khi kiểm tra tập dữ liệu, sinh viên phát hiện các đặc điểm cần xử lý trước khi huấn luyện:"));
children2.push(N([["Khác bối cảnh: ", { bold: true }], "gần như toàn bộ ảnh là cảnh đường phố đô thị ban đêm, trích từ 2 video (My-Video: 12.463 ảnh, test-real: 540 ảnh). Bối cảnh của đề tài là đường cao tốc Việt Nam, chủ yếu ban ngày."], "issues"));
children2.push(N([["Ảnh gần trùng giữa các tập: ", { bold: true }], "các khung liên tiếp của cùng video được chia ngẫu nhiên, nên 1.190 / 1.300 ảnh test (92%) có khung kề cận nằm trong tập train. Kết quả đánh giá trên tập test vì vậy sẽ cao hơn thực tế."], "issues"));
children2.push(N([["Mất cân bằng lớp: ", { bold: true }], "xe khách chỉ chiếm 0,8% số đối tượng."], "issues"));
children2.push(N([["Lớp Jeepney ", { bold: true }], "là loại xe đặc trưng của Philippines, không có trên đường Việt Nam."], "issues"));
children2.push(P([["Hướng xử lý (thực hiện ở tuần 6): ", { bold: true }], "bổ sung ảnh trích từ video camera hành trình trên cao tốc Việt Nam ban ngày và gán nhãn trên Roboflow; chia lại tập theo đoạn video liền (mỗi đoạn nằm trọn trong một tập) để tránh ảnh gần trùng; dùng riêng bộ video cao tốc Việt Nam làm tập kiểm thử độc lập; báo cáo mAP theo từng lớp để theo dõi lớp xe khách."]));

children2.push(H3("2.4. Video thử nghiệm"));
children2.push(table(["Kịch bản", "Nguồn", "Tình trạng"], [
  ["Cao tốc ban ngày", "Video camera hành trình VIETMAP, 640×360, 30 FPS", "Đã có"],
  ["Cao tốc ban đêm", "Video camera hành trình (cần thu thập)", "Đang thu thập"],
  ["Thời tiết xấu (mưa, sương mù)", "Video camera hành trình (cần thu thập)", "Đang thu thập"],
], [4.5, 8.0, 3.5]));
children2.push(caption("Bảng", "Bộ video thử nghiệm theo kịch bản (đề cương, PI 4.2)"));
children2.push(P([["Kết quả tuần 3: ", { bold: true }], "đặc tả đủ 5 use case chính; tập dữ liệu đã được chuẩn hóa ở định dạng YOLOv11 kèm thống kê và đánh giá; xác định kế hoạch bổ sung dữ liệu và video thử nghiệm."]));

// ---------------- V. Khó khăn
children2.push(H1("V. KHÓ KHĂN VÀ HƯỚNG GIẢI QUYẾT"));
children2.push(table(["Khó khăn", "Hướng giải quyết"], [
  ["Tập dữ liệu chủ yếu ảnh đô thị ban đêm, khác bối cảnh cao tốc Việt Nam", "Bổ sung ảnh cao tốc Việt Nam ban ngày, gán nhãn và huấn luyện tinh chỉnh ở tuần 6"],
  ["Ảnh gần trùng giữa tập train và test làm kết quả đánh giá lạc quan", "Chia lại theo đoạn video; đánh giá thêm trên bộ video cao tốc Việt Nam độc lập"],
  ["Khoảng cách IPM phụ thuộc vị trí lắp camera và giả định mặt đường phẳng", "Thiết kế chức năng căn chỉnh camera theo từng nguồn (UC02); giới hạn tầm đo tin cậy 150 m"],
  ["Chưa có tín hiệu tốc độ thực của xe (GPS / OBD)", "Người dùng chọn tốc độ xe chủ hoặc nêu tốc độ cho Trợ lý AI"],
  ["Thiếu video ban đêm và thời tiết xấu để kiểm thử", "Thu thập thêm từ camera hành trình trước tuần 10"],
], [8, 8]));
children2.push(caption("Bảng", "Khó khăn và hướng giải quyết"));

// ---------------- VI. Kế hoạch
children2.push(H1("VI. KẾ HOẠCH TUẦN 4 - TUẦN 6"));
children2.push(table(["Tuần", "Công việc", "Kết quả dự kiến"], [
  [["4", "19/10 - 25/10"], "Thiết kế CSDL (ERD), kiến trúc xử lý luồng video và sơ đồ lớp thực thể", "Sơ đồ ERD, Architecture Diagram, Class Diagram"],
  [["5", "26/10 - 1/11"], "Thiết kế giao diện (UI/UX) trên Figma", "Bản thiết kế các màn hình chính: giám sát, căn chỉnh camera, nhật ký"],
  [["6", "2/11 - 8/11"], "Xây dựng CSDL; bổ sung dữ liệu cao tốc Việt Nam, huấn luyện / tinh chỉnh YOLOv11", "CSDL hoàn thiện, file trọng số YOLOv11, kết quả đánh giá theo từng lớp"],
], [2.4, 7.6, 6.0], { center: [0] }));
children2.push(caption("Bảng", "Kế hoạch các tuần tiếp theo"));

// ---------------- VII. Ý kiến GVHD + ký
children2.push(H1("VII. NHẬN XÉT CỦA GIẢNG VIÊN HƯỚNG DẪN"));
for (let i = 0; i < 5; i++) {
  children2.push(new Paragraph({ children: runs(".".repeat(150), { size: 22 }), spacing: { after: 120 } }));
}
children2.push(P(""));
children2.push(new Paragraph({ alignment: AlignmentType.RIGHT, children: runs([["Thái Nguyên, ngày … tháng … năm 2026", { italics: true }]]) }));
const sig = (lines, w) => new TableCell({
  borders: NOB, width: { size: w, type: WidthType.DXA },
  children: lines.map(([t, o]) => new Paragraph({ alignment: AlignmentType.CENTER, children: runs([[t, o]]) })),
});
children2.push(new Table({
  width: { size: PORTRAIT_W, type: WidthType.DXA }, columnWidths: [8 * CM, 8 * CM],
  rows: [new TableRow({ children: [
    sig([["GIẢNG VIÊN HƯỚNG DẪN", { bold: true }], ["(Ký, ghi rõ họ tên)", { italics: true }], ["", {}], ["", {}], ["", {}], ["TS. Nguyễn Thành Trung", { bold: true }]], 8 * CM),
    sig([["SINH VIÊN THỰC HIỆN", { bold: true }], ["(Ký, ghi rõ họ tên)", { italics: true }], ["", {}], ["", {}], ["", {}], ["Nguyễn Đức Thắng", { bold: true }]], 8 * CM),
  ] })],
}));

// ---------------------------------------------------------------- tài liệu
const footer = new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
  children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 22 })] })] });
const portrait = { page: { size: { width: 21 * CM, height: 29.7 * CM },
  margin: { top: 2 * CM, bottom: 2 * CM, left: 3 * CM, right: 2 * CM } } };
const landscape = { page: { size: { width: 21 * CM, height: 29.7 * CM, orientation: PageOrientation.LANDSCAPE },
  margin: { top: 2 * CM, bottom: 2 * CM, left: 2.5 * CM, right: 2.5 * CM } } };

const doc = new Document({
  creator: "Nguyễn Đức Thắng",
  title: "Báo cáo tiến độ đồ án tốt nghiệp - tuần 1 đến tuần 3",
  styles: {
    default: { document: { run: { font: FONT, size: 26 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 28, bold: true, color: "000000" }, paragraph: { outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 26, bold: true, color: "000000" }, paragraph: { outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 26, bold: true, italics: true, color: "000000" }, paragraph: { outlineLevel: 2 } },
    ],
  },
  numbering: { config: [
    { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 567, hanging: 283 } } } }] },
    { reference: "issues", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1)", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 567, hanging: 340 } } } }] },
  ] },
  sections: [
    { properties: portrait, footers: { default: footer }, children: captionsAbove(children1) },
    { properties: landscape, footers: { default: footer }, children: childrenL },
    { properties: portrait, footers: { default: footer }, children: captionsAbove(children2) },
  ],
});

Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(OUT, buf); console.log("OK", OUT, figNo, "hình,", tabNo, "bảng"); });
