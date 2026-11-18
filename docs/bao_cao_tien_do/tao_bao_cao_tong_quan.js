// Báo cáo tiến độ đồ án - tổng hợp: bài toán, khảo sát, yêu cầu, use case, dữ liệu,
// khung dự án, công nghệ, mô hình, thuật toán, thiết kế, giao diện, kết quả, tiến độ
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType, ShadingType,
  AlignmentType, ImageRun, PageOrientation, BorderStyle, LevelFormat, VerticalAlign, Footer, PageNumber,
} = require("docx");

const ROOT = "C:/A_Nam4/Đồ án/giaodien/docs";
const OUT = process.env.OUT || path.join(ROOT, "bao_cao_tien_do", "BAO_CAO_TIEN_DO_CHUONG_1-2.docx");
const FONT = "Times New Roman";
const CM = 567;                       // DXA / cm
const PORTRAIT_W = 16 * CM;           // A4, lề trái 3 cm, phải 2 cm

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
// Công thức: căn giữa, nghiêng
const EQ = (text) => new Paragraph({
  children: runs([[text, { italics: true }]]), alignment: AlignmentType.CENTER,
  spacing: { before: 80, after: 100, line: 300 },
});
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: runs(t), spacing: { before: 240, after: 120 }, keepNext: true });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: runs(t), spacing: { before: 180, after: 100 }, keepNext: true });
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: runs(t), spacing: { before: 140, after: 80 }, keepNext: true });
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
    children: r.map((c, i) => cell(c, widths[i], {
      align: (o.center || []).includes(i) ? AlignmentType.CENTER : undefined,
    })),
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
const stepParas = (items, numbered) => items.map((t, i) => new Paragraph({
  children: runs((numbered ? `${i + 1}. ` : "") + t, { size: 24 }), spacing: { after: 30, line: 264 },
  alignment: AlignmentType.LEFT,
}));

// Các section: dọc / ngang (cho sơ đồ khổ rộng)
const sections = [];
let cur;
function section(landscape = false) { cur = { landscape, children: [] }; sections.push(cur); }
const add = (...xs) => cur.children.push(...xs);

const SO_DO = (n) => path.join(ROOT, "so_do", n);
const HINH = (n) => path.join(ROOT, "bao_cao_tien_do", "hinh", n);
const TQ = (n) => path.join(ROOT, "bao_cao_tien_do", "so_do_tong_quan", n);

// ================================================================ trang đầu
// Tiêu đề mục con không vào mục lục (biểu mẫu, tên UC)
const SUB = (t) => new Paragraph({ children: runs([[t, { bold: true, italics: true }]]), spacing: { before: 140, after: 80 }, keepNext: true });

// ================================================================ trang đầu
section();
const NB = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const NOB = { top: NB, bottom: NB, left: NB, right: NB };
const hc = (lines, w) => new TableCell({
  borders: NOB, width: { size: w, type: WidthType.DXA }, margins: { left: 0, right: 0 },
  children: lines.map(([t, o]) => new Paragraph({ alignment: AlignmentType.CENTER, children: runs([[t, o]], { size: 24 }) })),
});
add(new Table({
  width: { size: PORTRAIT_W, type: WidthType.DXA }, columnWidths: [6.8 * CM, 9.2 * CM],
  rows: [new TableRow({ children: [
    hc([["TRƯỜNG ĐẠI HỌC CÔNG NGHỆ", {}], ["THÔNG TIN VÀ TRUYỀN THÔNG", {}], ["KHOA CÔNG NGHỆ THÔNG TIN", { bold: true }]], 6.8 * CM),
    hc([["CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", { bold: true }], ["Độc lập - Tự do - Hạnh phúc", { bold: true }]], 9.2 * CM),
  ] })],
}));
add(P(""));
add(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 200, after: 60 },
  children: runs([["BÁO CÁO TIẾN ĐỘ ĐỒ ÁN TỐT NGHIỆP", { bold: true, size: 32 }]]) }));
add(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 240 },
  children: runs([["Chương 1. Cơ sở lý thuyết - Chương 2. Khảo sát và phân tích hệ thống", { bold: true, size: 26 }]]) }));

add(table(["Mục", "Thông tin"], [
  ["Sinh viên", "Nguyễn Đức Thắng - MSSV: DTC235200703 - Lớp: CNTT K22A CN"],
  ["Email", "dtc235200703@ictu.edu.vn"],
  ["Giảng viên hướng dẫn", "TS. Nguyễn Thành Trung - Bộ môn Kỹ thuật máy tính"],
  ["Tên đề tài", "Xây dựng hệ thống cảnh báo khoảng cách an toàn giữa các phương tiện trên cao tốc thời gian thực ứng dụng mô hình YOLOv11 và thị giác máy tính"],
  ["Thời gian thực hiện", "10 tuần, từ 28/9/2026 đến 7/12/2026"],
  ["Kỳ báo cáo", "Tuần 1 - Tuần 2 (28/9/2026 - 11/10/2026)"],
], [4.5, 11.5]));
add(caption("Bảng", "Thông tin chung"));

add(P([["Mục đích báo cáo: ", { bold: true }], "trình bày nội dung đã thực hiện sau 2 tuần đầu theo đúng khung Chương 1 và Chương 2 của quyển báo cáo đồ án (mục 8 của đề cương). Chương 1 giải thích nền tảng lý thuyết, phân tích các hệ thống và nghiên cứu liên quan, rồi nêu định hướng giải quyết; Chương 2 trình bày khảo sát, quy trình nghiệp vụ, yêu cầu và use case. Báo cáo dừng ở mức phân tích và định hướng, chưa đi vào thiết kế chi tiết và cài đặt (Chương 3, Chương 4)."]));
add(P([["Cách phân chia nội dung: ", { bold: true }], "mục 1.2 chỉ giải thích lý thuyết; mục 1.3 phân tích hệ thống, nghiên cứu có nguồn tham khảo; mục 1.4 trình bày cách áp dụng vào đề tài. Phần cuối báo cáo là tiến độ, khó khăn và kế hoạch các tuần tiếp theo."]));

// ================================================================ CHƯƠNG 1
add(H1("CHƯƠNG 1. CƠ SỞ LÝ THUYẾT"));

// ---------- 1.1
add(H2("1.1. Tổng quan đề tài"));
add(H3("1.1.1. Bối cảnh và lý do lựa chọn đề tài"));
add(P("Mạng lưới đường cao tốc Việt Nam đang mở rộng nhanh, lưu lượng xe và tốc độ khai thác ngày càng cao. Ở tốc độ 80-120 km/h, chỉ một chút chậm trễ trong phản xạ cũng đủ khiến xe không dừng kịp khi xe phía trước phanh gấp; vì vậy giữ khoảng cách không an toàn là một trong những nguyên nhân chính gây tai nạn liên hoàn trên cao tốc."));
add(P("Thông tư 31/2019/TT-BGTVT [1] quy định khoảng cách an toàn tối thiểu theo tốc độ, nhưng tài xế khó ước lượng chính xác khoảng cách bằng mắt, nhất là khi trời tối, mưa hoặc khi mệt mỏi. Các hệ thống cảnh báo va chạm phía trước chủ yếu có trên xe đời mới, giá cao. Trong khi đó, camera hành trình đã rất phổ biến trên xe ở Việt Nam. Đề tài tận dụng camera này cùng mô hình học sâu và kỹ thuật thị giác máy tính để cảnh báo khoảng cách theo đúng quy định, với chi phí thấp và lắp được cho mọi xe."));

add(H3("1.1.2. Giới thiệu bài toán cảnh báo khoảng cách an toàn trên cao tốc"));
add(P("Bài toán: từ hình ảnh camera hành trình đặt phía trước xe chủ, theo thời gian thực, xác định các phương tiện phía trước, ước lượng khoảng cách thực (mét) tới xe cùng làn gần nhất, so sánh với khoảng cách an toàn theo tốc độ xe chủ và điều kiện đường, rồi cảnh báo tài xế khi khoảng cách vi phạm ngưỡng."));
add(table(["Hạng mục", "Nội dung"], [
  ["Đầu vào", ["Hình ảnh từ file video hành trình, ảnh tĩnh, camera USB hoặc camera IP (RTSP/HTTP)",
    "Tốc độ xe chủ do người dùng chọn hoặc nêu qua Trợ lý AI",
    "Mô tả điều kiện đường (khô ráo, mưa, sương mù, trơn trượt, ban đêm, chở nặng, mệt mỏi)"]],
  ["Đầu ra", ["Hình ảnh hiển thị khung xe đổi màu xanh / vàng / đỏ, nhãn khoảng cách (m), vùng nguy hiểm, ảnh nhìn từ trên xuống",
    "Âm thanh cảnh báo 2 mức (cảnh báo / nguy hiểm)",
    "Nhật ký vi phạm khoảng cách kèm ảnh bằng chứng, có thể tra cứu và xuất file"]],
], [3.2, 12.8]));
add(caption("Bảng", "Đầu vào và đầu ra của bài toán"));

add(H3("1.1.3. Mục tiêu nghiên cứu và phát triển hệ thống"));
add(B("Nghiên cứu mô hình YOLOv11 để phát hiện và phân loại phương tiện (ô tô, xe tải, xe khách) theo thời gian thực, bám vết từng xe qua các khung hình."));
add(B("Nghiên cứu phép biến đổi phối cảnh ngược (IPM) để quy đổi vị trí xe trên ảnh sang khoảng cách thực trên mặt đường; xác định xe cùng làn phía trước."));
add(B("Xây dựng quy tắc ngưỡng an toàn theo tốc độ xe chủ (Thông tư 31) và điều kiện đường; cảnh báo 2 mức bằng hình ảnh và âm thanh."));
add(B("Xây dựng Trợ lý AI gợi ý ngưỡng từ mô tả tình huống bằng tiếng Việt."));
add(B("Phát triển ứng dụng desktop hoàn chỉnh: quản lý nguồn video, căn chỉnh camera, cấu hình ngưỡng, giám sát, nhật ký vi phạm; đóng gói chạy thử nghiệm."));

add(H3("1.1.4. Đối tượng và phạm vi nghiên cứu"));
add(B([["Đối tượng: ", { bold: true }], "phương tiện cơ giới trên đường cao tốc (ô tô con, xe tải, xe khách); hình ảnh từ camera hành trình đơn (một camera) đặt phía trước xe; quy định khoảng cách an toàn của Việt Nam."]));
add(B([["Phạm vi: ", { bold: true }], "xe chủ đi theo làn trên cao tốc; mặt đường xem như phẳng; tầm đo tin cậy khoảng 150 m; tốc độ xe chủ nhập tay (chưa lấy từ GPS / OBD); chạy trên máy tính Windows có hoặc không có GPU."]));
add(B([["Ngoài phạm vi: ", { bold: true }], "điều khiển xe (phanh tự động), xe máy và người đi bộ, đường đô thị, camera nhiều mắt (stereo) hoặc radar / lidar."]));

// ---------- 1.2
add(H2("1.2. Cơ sở lý thuyết"));
add(H3("1.2.1. Hệ thống hỗ trợ lái xe nâng cao và cảnh báo va chạm phía trước"));
add(P("Hệ thống hỗ trợ lái xe nâng cao (ADAS - Advanced Driver Assistance Systems) là tập hợp các chức năng dùng cảm biến trên xe để hỗ trợ tài xế, ví dụ cảnh báo lệch làn, cảnh báo điểm mù, kiểm soát hành trình thích ứng. Cảnh báo va chạm phía trước (FCW - Forward Collision Warning) là chức năng theo dõi xe phía trước và cảnh báo khi khoảng cách hoặc thời gian va chạm xuống dưới mức an toàn; khi kết hợp với phanh tự động gọi là AEB."));
add(P("Cảm biến thường dùng gồm radar (đo khoảng cách trực tiếp, ít chịu ảnh hưởng thời tiết nhưng khó phân loại vật thể), lidar (chính xác nhưng đắt) và camera (rẻ, nhận dạng tốt loại vật thể và vạch làn nhưng phải suy ra khoảng cách từ ảnh). Đề tài thuộc nhóm FCW dùng một camera, chỉ cảnh báo, không can thiệp điều khiển xe."));

add(H3("1.2.2. Quy định về khoảng cách an toàn và quãng đường dừng xe"));
add(P("Thông tư 31/2019/TT-BGTVT [1] quy định khoảng cách an toàn tối thiểu giữa hai xe khi mặt đường khô ráo theo tốc độ lưu hành. Tốc độ tối đa trên đường cao tốc là 120 km/h. Khi trời mưa, có sương mù, mặt đường trơn trượt hoặc tầm nhìn hạn chế, người lái xe phải giữ khoảng cách lớn hơn trị số ghi trong bảng. Với tốc độ dưới 60 km/h, quy định để người lái xe tự chủ động giữ khoảng cách phù hợp."));
add(table(["Tốc độ lưu hành V (km/h)", "Khoảng cách an toàn tối thiểu (m)"], [
  ["V = 60", "35"], ["60 < V ≤ 80", "55"], ["80 < V ≤ 100", "70"], ["100 < V ≤ 120", "100"],
], [8, 8], { center: [0, 1] }));
const TAB_LEGAL = tabNo + 1;
add(caption("Bảng", "Khoảng cách an toàn tối thiểu khi mặt đường khô ráo (Thông tư 31/2019/TT-BGTVT)"));
add(P("Về mặt vật lý, quãng đường dừng xe gồm quãng đường đi trong thời gian phản xạ của tài xế và quãng phanh:"));
add(EQ("S_dừng = v · t_phản xạ + v² / (2 · μ · g)"));
add(P("trong đó v là vận tốc (m/s), t_phản xạ thường lấy 1-1,5 s, μ là hệ số bám giữa lốp và mặt đường (khô ≈ 0,7; ướt ≈ 0,5; đọng nước ≈ 0,35), g = 9,81 m/s². Quãng phanh tỷ lệ nghịch với μ, nên khi đường trơn khoảng cách an toàn phải tăng tương ứng. Quy tắc giãn cách theo thời gian (giữ cách xe trước tối thiểu 2 giây) là cách ước lượng đơn giản thường dùng khi không có bảng quy định."));

add(H3("1.2.3. Học sâu và bài toán phát hiện đối tượng"));
add(P("Phát hiện đối tượng là bài toán xác định vị trí (khung bao) và loại của các đối tượng trong ảnh. Các phương pháp hiện đại dùng mạng nơ-ron tích chập (CNN) học đặc trưng trực tiếp từ dữ liệu, chia làm 2 nhóm:"));
add(B([["Hai giai đoạn ", { bold: true }], "(họ R-CNN): sinh vùng đề xuất rồi phân loại từng vùng - chính xác nhưng chậm."]));
add(B([["Một giai đoạn ", { bold: true }], "(họ YOLO [2], SSD): dự đoán khung bao và lớp trong một lần lan truyền qua mạng - nhanh, phù hợp xử lý thời gian thực trên video."]));
add(P("Mô hình thường được huấn luyện sẵn trên tập dữ liệu lớn như COCO [10] (80 lớp, có car, truck, bus), sau đó huấn luyện tinh chỉnh (fine-tune) trên tập dữ liệu của bài toán để đạt độ chính xác cao với ít dữ liệu hơn."));

add(H3("1.2.4. Mô hình YOLOv11"));
add(P("YOLOv11 (Ultralytics, 2024) [3] là phiên bản mới của họ YOLO. Kiến trúc gồm 3 phần:"));
add(B([["Backbone: ", { bold: true }], "các khối C3k2 trích đặc trưng, SPPF gộp đặc trưng đa tỷ lệ, C2PSA (cơ chế chú ý theo vùng) giúp tập trung vào đối tượng."]));
add(B([["Neck: ", { bold: true }], "kết hợp đặc trưng 3 mức phân giải theo kiểu FPN [11] / PAN [12] để phát hiện cả đối tượng lớn (xe ở gần) và nhỏ (xe ở xa)."]));
add(B([["Head: ", { bold: true }], "không dùng anchor (anchor-free), tách nhánh phân loại và nhánh hồi quy khung bao; khử trùng khung bằng NMS (Non-Maximum Suppression)."]));
add(P("YOLOv11 có 5 kích cỡ n, s, m, l, x; bản nano (YOLOv11n, khoảng 2,6 triệu tham số) nhẹ nhất, chạy được thời gian thực cả trên máy không có GPU mạnh."));

add(H3("1.2.5. Bám vết đa đối tượng ByteTrack"));
add(P("Bám vết đa đối tượng gán cho mỗi đối tượng một mã cố định qua các khung hình. ByteTrack [4] dự đoán vị trí mới của từng đối tượng bằng bộ lọc Kalman [13], rồi ghép với các phát hiện ở khung hiện tại theo độ trùng khớp IoU qua 2 vòng: vòng 1 với các phát hiện có độ tin cậy cao, vòng 2 dùng cả các phát hiện độ tin cậy thấp để giữ được đối tượng bị che khuất một phần. Mã cố định của mỗi xe cho phép theo dõi khoảng cách của chính xe đó theo thời gian."));

add(H3("1.2.6. Mô hình camera và biến đổi phối cảnh ngược (IPM)"));
add(P("Theo mô hình camera lỗ kim [9], điểm 3D được chiếu lên ảnh qua ma trận nội tham số K (tiêu cự f, tâm ảnh) và tư thế camera (ma trận quay R, vector tịnh tiến t). Khi các điểm cùng nằm trên một mặt phẳng (mặt đường), phép chiếu giữa mặt đường và ảnh là một phép biến đổi homography H kích thước 3×3:"));
add(EQ("[X·w, Y·w, w]ᵀ = H · [u, v, 1]ᵀ"));
add(P("với (u, v) là tọa độ pixel và (X, Y) là tọa độ trên mặt đường (mét). Biến đổi phối cảnh ngược (IPM) [6] dùng H để đưa ảnh về góc nhìn từ trên xuống (Bird's-Eye View), trên đó khoảng cách đo được trực tiếp bằng mét [7]. H có 8 bậc tự do nên xác định được từ 4 cặp điểm tương ứng (ví dụ 4 góc của một đoạn làn đường có kích thước biết trước). Từ H có thể phân rã ra K, R và chiều cao camera theo phương pháp của Zhang [5]."));
add(P("Giới hạn: IPM giả định mặt đường phẳng; điểm phải nằm trên mặt đường (với xe là điểm bánh xe chạm đất); sai số tăng nhanh theo khoảng cách vì mỗi pixel ở xa tương ứng với nhiều mét hơn."));

add(H3("1.2.7. Phát hiện vạch kẻ làn đường"));
add(P("Vạch kẻ làn là các nét sơn sáng, mảnh trên nền mặt đường tối hơn. Trên ảnh nhìn từ trên xuống, vạch làn gần như song song và thẳng đứng nên dễ tìm hơn trên ảnh gốc. Các kỹ thuật thường dùng: lọc hình thái top-hat để giữ nét sáng mảnh; tìm vị trí vạch bằng biểu đồ tổng cường độ theo cột và cửa sổ trượt dọc theo vạch; khớp đường cong đa thức bậc 2 X = c₀ + c₁Y + c₂Y² cho mỗi vạch. Biến đổi Hough [15] kết hợp RANSAC [14] dùng để tìm các đoạn thẳng vạch làn và điểm tụ (vanishing point) của chúng."));

add(H3("1.2.8. Ước lượng chuyển động: làm mượt, tốc độ tiếp cận và TTC"));
add(B([["Làm mượt theo hàm mũ (EMA): ", { bold: true }], "dₜ = α·d + (1 − α)·dₜ₋₁ (0 < α < 1), giảm dao động của số đo giữa các khung."]));
add(B([["Tốc độ tiếp cận: ", { bold: true }], "độ dốc của đường hồi quy tuyến tính khoảng cách theo thời gian trong một cửa sổ ngắn (khoảng 1 giây); dương khi hai xe đang tiến lại gần."]));
add(B([["Thời gian va chạm (TTC - Time To Collision) ", { bold: true }], "[16]: TTC = d / v_tiếp cận, là thời gian còn lại trước khi va chạm nếu hai xe giữ nguyên tốc độ; TTC nhỏ (vài giây) là dấu hiệu nguy hiểm kể cả khi khoảng cách chưa quá gần."]));

add(H3("1.2.9. Mô hình ngôn ngữ lớn và trợ lý AI"));
add(P("Mô hình ngôn ngữ lớn (LLM) như Claude [17] hiểu và sinh văn bản tự nhiên, kể cả tiếng Việt. Khi tích hợp vào phần mềm, LLM có thể được yêu cầu trả lời theo cấu trúc dữ liệu cố định (JSON schema) để chương trình đọc được kết quả. Với các tác vụ có tập ý định hữu hạn, một bộ luật nhận dạng từ khóa (rule-based) chạy offline là phương án thay thế miễn phí, không cần Internet."));

add(H3("1.2.10. Các phương pháp đánh giá"));
add(table(["Đối tượng đánh giá", "Chỉ số", "Ý nghĩa"], [
  ["Mô hình phát hiện", "IoU", "Tỷ lệ diện tích giao / hợp giữa khung dự đoán và khung thật; dự đoán đúng khi IoU ≥ ngưỡng (thường 0,5)"],
  ["Mô hình phát hiện", "Precision, Recall", "Precision = TP / (TP + FP): tỷ lệ phát hiện đúng; Recall = TP / (TP + FN): tỷ lệ xe thật được phát hiện"],
  ["Mô hình phát hiện", "mAP@0,5; mAP@0,5:0,95 [18]", "Trung bình diện tích dưới đường Precision-Recall của các lớp, tại IoU 0,5 hoặc trung bình các ngưỡng IoU 0,5-0,95"],
  ["Đo khoảng cách", "Sai số tuyệt đối / tương đối", "So khoảng cách ước lượng với khoảng cách thật (mốc vạch kẻ, biển báo khoảng cách) theo từng dải khoảng cách"],
  ["Hệ thống thời gian thực", "FPS, độ trễ mỗi khung", "Số khung xử lý mỗi giây và thời gian xử lý một khung"],
  ["Cảnh báo", "Báo đúng, báo nhầm, bỏ sót", "Đối chiếu cảnh báo với các tình huống vi phạm thật trong video kịch bản"],
], [3.6, 4.0, 8.4]));
add(caption("Bảng", "Các chỉ số đánh giá"));

add(H3("1.2.11. Công nghệ phát triển phần mềm"));
add(table(["Nhóm", "Công nghệ", "Đặc điểm"], [
  ["Ngôn ngữ", "Python", "Hệ sinh thái AI / thị giác máy tính đầy đủ, viết nhanh, nhiều thư viện"],
  ["Học sâu", "PyTorch + CUDA", "Nền tảng huấn luyện và chạy mạng nơ-ron, tăng tốc bằng GPU NVIDIA"],
  ["Phát hiện đối tượng", "Ultralytics", "Thư viện huấn luyện, đánh giá, suy luận YOLOv11, tích hợp sẵn ByteTrack"],
  ["Thị giác máy tính", "OpenCV, NumPy", "Đọc video / camera, tính homography, biến đổi phối cảnh, xử lý ảnh, tính toán ma trận"],
  ["Giao diện", "PySide6 (Qt 6)", "Thư viện giao diện desktop đa nền tảng, hỗ trợ đa luồng, hiển thị tiếng Việt"],
  ["Âm thanh", "pygame", "Phát âm thanh cảnh báo"],
  ["Cơ sở dữ liệu", "SQLite", "CSDL quan hệ nhúng, không cần máy chủ, lưu trong một file"],
  ["Trợ lý AI", "Anthropic Claude API", "Dịch vụ LLM, hỗ trợ đầu ra có cấu trúc JSON"],
  ["Dữ liệu", "Roboflow", "Nền tảng gán nhãn, quản lý và xuất dataset định dạng YOLO"],
  ["Mô hình hóa", "BPMN 2.0, UML, Mermaid; Figma", "Vẽ sơ đồ quy trình, use case, thiết kế; thiết kế mockup giao diện"],
  ["Đóng gói", "PyInstaller", "Đóng gói ứng dụng Python thành file .exe chạy trên Windows"],
], [3.0, 4.6, 8.4]));
const TAB_TECH = tabNo + 1;
add(caption("Bảng", "Công nghệ phát triển phần mềm"));

// ---------- 1.3
add(H2("1.3. Các công trình và hệ thống liên quan"));
add(H3("1.3.1. Hệ thống cảnh báo va chạm phía trước tích hợp trên ô tô"));
add(P("Nhiều hãng xe trang bị FCW / AEB trong các gói an toàn chủ động, dùng radar, camera hoặc kết hợp cả hai. Ưu điểm là cảm biến chuyên dụng, được hiệu chỉnh tại nhà máy nên chính xác và ổn định. Hạn chế: chủ yếu có trên xe đời mới hoặc phiên bản cao cấp; không lắp thêm được cho xe đang lưu hành; ngưỡng cảnh báo do nhà sản xuất đặt sẵn, thường theo thời gian va chạm, không bám bảng khoảng cách của quy định Việt Nam."));
add(H3("1.3.2. Thiết bị ADAS gắn thêm và camera hành trình có cảnh báo"));
add(P("Trên thị trường có các thiết bị ADAS gắn thêm và camera hành trình tích hợp cảnh báo va chạm phía trước, cảnh báo lệch làn. Ưu điểm là lắp được cho xe cũ, giá hợp lý. Hạn chế: thuật toán đóng, ngưỡng cố định do nhà sản xuất; người dùng khó điều chỉnh theo tốc độ, bảng quy định và điều kiện thời tiết; ít khi lưu nhật ký vi phạm để tra cứu lại."));
add(H3("1.3.3. Nghiên cứu ước lượng khoảng cách bằng một camera"));
add(B([["Theo hình học mặt đường: ", { bold: true }], "Stein, Mano và Shashua [8] ước lượng khoảng cách tới xe phía trước từ vị trí điểm tiếp đất trên ảnh với giả định mặt đường phẳng và chiều cao camera biết trước, đồng thời phân tích sai số: sai số khoảng cách tăng theo bình phương khoảng cách. Đây là cơ sở cho cách đo bằng IPM của đề tài."]));
add(B([["IPM cho nhận diện làn và vật cản: ", { bold: true }], "Mallot và cộng sự [6] đề xuất IPM; hệ thống GOLD của Bertozzi và Broggi [7] dùng IPM để phát hiện làn đường và vật cản theo thời gian thực trên xe thử nghiệm."]));
add(B([["Theo kích thước vật thể: ", { bold: true }], "nhiều nghiên cứu kết hợp YOLO với mô hình camera lỗ kim, suy ra khoảng cách từ chiều cao hoặc bề rộng khung bao và kích thước thật giả định của xe. Cách này đơn giản, không cần căn chỉnh, nhưng sai số lớn vì kích thước thật của các xe khác nhau và khung bao dao động."]));
add(H3("1.3.4. Nhận xét và so sánh các giải pháp"));
add(table(["Giải pháp", "Nguyên lý", "Ưu điểm", "Hạn chế"], [
  ["Tài xế tự ước lượng", "Quan sát bằng mắt, quy tắc 2-3 giây, biển kiểm tra cự ly trên một số tuyến cao tốc",
    "Không cần thiết bị", "Chủ quan; khó ước lượng ở tốc độ cao, khi trời tối, mưa hoặc khi mệt mỏi"],
  ["FCW / AEB tích hợp trên xe", "Radar / camera chuyên dụng của hãng xe",
    "Chính xác, ổn định", "Chủ yếu có trên xe đời mới, giá cao; không lắp thêm được; ngưỡng không theo quy định Việt Nam"],
  ["Thiết bị ADAS gắn thêm", "Camera + thuật toán nhúng trong thiết bị",
    "Lắp được cho xe cũ", "Ngưỡng cố định; khó chỉnh theo quy định và điều kiện đường; ít có nhật ký vi phạm"],
  ["YOLO + kích thước xe", "Camera lỗ kim, khoảng cách từ kích thước khung bao",
    "Đơn giản, không cần căn chỉnh", "Sai số lớn vì kích thước thật của xe khác nhau"],
  ["Hình học mặt đường / IPM [6][7][8]", "Điểm tiếp đất của xe trên mặt đường phẳng",
    "Không phụ thuộc kích thước xe; đo trực tiếp bằng mét", "Cần căn chỉnh camera; giả định đường phẳng; sai số tăng theo khoảng cách"],
], [3.4, 4.2, 3.0, 5.4]));
const TAB_CMP = tabNo + 1;
add(caption("Bảng", "So sánh các giải pháp cảnh báo khoảng cách"));
add(P([["Nhận xét: ", { bold: true }], "chưa có giải pháp phổ thông nào vừa dùng camera thông thường, vừa áp ngưỡng theo bảng khoảng cách của Thông tư 31 có điều chỉnh theo điều kiện đường, vừa lưu nhật ký vi phạm. Đề tài kết hợp phát hiện xe bằng YOLOv11 với đo khoảng cách bằng IPM (không phụ thuộc kích thước xe) để lấp khoảng trống này."]));

// ---------- 1.4
add(H2("1.4. Định hướng giải quyết"));
add(H3("1.4.1. Định hướng tổng thể"));
add(P("Hệ thống được định hướng như một chuỗi xử lý ảnh theo thời gian thực: mỗi khung hình từ camera hành trình đi qua các bước nhận diện xe, ước lượng khoảng cách, đánh giá rủi ro và hiển thị cảnh báo. Khoảng cách đo trên mặt phẳng đường (IPM) nên không phụ thuộc loại xe. Ngưỡng cảnh báo bám theo Thông tư 31 và được điều chỉnh theo điều kiện đường; tài xế có thể nhờ Trợ lý AI gợi ý ngưỡng bằng câu mô tả tiếng Việt."));

add(H3("1.4.2. Định hướng kiến trúc và công nghệ"));
add(P("Theo yêu cầu PI 2.2 của đề cương, kiến trúc gồm 5 tầng nối tiếp: Video Stream → YOLOv11 Detection → IPM Distance Calculation → Alert Engine → GUI. Cơ sở dữ liệu cung cấp thông số camera, cấu hình ngưỡng và lưu nhật ký vi phạm; Trợ lý AI nằm ngoài vòng xử lý khung hình, chỉ thay đổi cấu hình ngưỡng. Phần mềm là ứng dụng desktop viết bằng Python, dùng các công nghệ ở Bảng " + TAB_TECH + " (mục 1.2.11).", { keepNext: true }));
add(...figure(TQ("T1_kien_truc_tong_quan.png"), 16, "Kiến trúc tổng quan của hệ thống", 21));
add(table(["Tầng", "Nhiệm vụ", "Kỹ thuật", "Đầu ra"], [
  ["① Thu nhận dữ liệu", "Đọc khung hình từ file video, camera USB / IP hoặc ảnh; giữ nhịp thời gian thực", "OpenCV; bỏ khung khi xử lý chậm", "Khung hình + thời điểm"],
  ["② Nhận diện phương tiện", "Phát hiện, phân loại ô tô, xe tải, xe khách; theo dõi từng xe qua các khung", "YOLOv11 + ByteTrack", "Khung bao, loại xe, mã xe"],
  ["③ Ước lượng khoảng cách", "Xác định làn xe chủ, đổi vị trí xe sang mét, tính tốc độ tiếp cận và TTC", "IPM, nhận diện vạch làn, EMA, hồi quy tuyến tính", "Khoảng cách (m), cùng làn hay không, TTC"],
  ["④ Đánh giá và cảnh báo", "Tính ngưỡng; phân loại rủi ro; phát âm thanh; ghi nhật ký", "Bảng Thông tư 31 × hệ số điều kiện; chống báo nhầm", "Mức an toàn / cảnh báo / nguy hiểm"],
  ["⑤ Giao diện", "Hiển thị video có khung màu, khoảng cách, ảnh nhìn từ trên xuống; cấu hình; tra cứu nhật ký", "PySide6", "Màn hình giám sát, cảnh báo"],
], [3.0, 5.2, 4.6, 3.2]));
add(caption("Bảng", "Năm tầng của kiến trúc tổng quan"));
add(P("Luồng xử lý một khung hình trong quá trình giám sát (chi tiết hóa quy trình BPMN “Giám sát và cảnh báo” ở mục 2.2):", { keepNext: true }));
add(...figure(TQ("T2_luong_xu_ly_khung_hinh.png"), 16, "Luồng xử lý một khung hình", 22));

add(H3("1.4.3. Định hướng nhận diện phương tiện và chuẩn bị dữ liệu"));
add(P("Dùng YOLOv11n khởi tạo từ trọng số COCO, huấn luyện tinh chỉnh trên tập dữ liệu phương tiện; dùng ByteTrack để bám vết. Kế hoạch huấn luyện (tuần 6):"));
add(table(["Tham số", "Giá trị dự kiến"], [
  ["Mô hình gốc", "YOLOv11n huấn luyện sẵn trên COCO"],
  ["Epoch / batch / kích thước ảnh", "50 / 16 / 640 × 640"],
  ["Tăng cường dữ liệu", "Mosaic, lật ngang, thay đổi độ sáng"],
  ["Chỉ số đánh giá", "Precision, Recall, mAP@0,5, mAP@0,5:0,95 theo từng lớp"],
  ["Mục tiêu", "mAP@0,5 ≥ 0,80 (NFR-03)"],
], [5.5, 10.5]));
add(caption("Bảng", "Kế hoạch huấn luyện YOLOv11"));
add(P([["Tập dữ liệu dự kiến: ", { bold: true }], "Roboflow (dự án distance-estimation-model, phiên bản 1, giấy phép CC BY 4.0), 13.003 ảnh khung hình camera hành trình, 72.653 đối tượng, 5 lớp, đã ở định dạng YOLOv11 (mỗi ảnh một file nhãn “lớp x_tâm y_tâm rộng cao” chuẩn hóa 0..1), chia train / valid / test = 70 / 20 / 10. Ô tô, xe tải, xe khách là 3 lớp mục tiêu; Jeepney cảnh báo cùng nhóm xe khách; xe máy không theo dõi vì không lưu thông trên cao tốc."]));
add(table(["Lớp", "Train", "Valid", "Test", "Tổng", "Tỷ lệ"], [
  ["Ô tô (car)", "29.244", "8.318", "4.078", "41.640", "57,3%"],
  ["Xe máy (motorcycle)", "15.697", "4.669", "2.195", "22.561", "31,1%"],
  ["Xe tải (truck)", "3.841", "1.063", "588", "5.492", "7,6%"],
  ["Jeepney", "1.625", "518", "219", "2.362", "3,3%"],
  ["Xe khách (bus)", "419", "126", "53", "598", "0,8%"],
  [[["Tổng số đối tượng", { bold: true }]], "50.826", "14.694", "7.133", "72.653", "100%"],
  [[["Số ảnh", { bold: true }]], "9.102", "2.601", "1.300", "13.003", ""],
], [4.4, 2.3, 2.3, 2.3, 2.4, 2.3], { center: [1, 2, 3, 4, 5] }));
add(caption("Bảng", "Thống kê đối tượng theo lớp và theo tập"));
add(...figure(HINH("dataset_mau.jpg"), 16, "Ảnh mẫu trong tập dữ liệu kèm nhãn"));
add(P([["Đánh giá ban đầu: ", { bold: true }], "(1) gần như toàn bộ ảnh là cảnh đô thị ban đêm trích từ 2 video, khác bối cảnh cao tốc Việt Nam ban ngày; (2) các khung liên tiếp được chia ngẫu nhiên nên 92% ảnh test có khung kề cận trong tập train, kết quả đánh giá sẽ lạc quan; (3) xe khách chỉ chiếm 0,8%; (4) lớp Jeepney là xe đặc trưng của Philippines. Hướng xử lý: bổ sung ảnh cao tốc Việt Nam ban ngày, chia lại tập theo đoạn video, đánh giá trên bộ video độc lập, báo cáo mAP theo từng lớp."]));
add(table(["Kịch bản", "Nguồn", "Tình trạng"], [
  ["Cao tốc ban ngày", "Video camera hành trình, 640×360, 30 FPS", "Đã có"],
  ["Cao tốc ban đêm", "Video camera hành trình", "Đang thu thập"],
  ["Thời tiết xấu (mưa, sương mù)", "Video camera hành trình", "Đang thu thập"],
], [4.5, 8.0, 3.5]));
add(caption("Bảng", "Bộ video thử nghiệm theo kịch bản (đề cương, PI 4.2)"));

add(H3("1.4.4. Định hướng đo khoảng cách và xác định làn xe chủ"));
add(B("Căn chỉnh camera cho từng nguồn video bằng 4 điểm trên 2 vạch làn xe chủ, ứng với hình chữ nhật bề rộng W = 3,75 m (làn cao tốc Việt Nam), chiều dài L, cách đầu xe d₀ → tính H, phân rã K, R; lưu theo nguồn."));
add(B("Điểm đo của mỗi xe là điểm giữa cạnh dưới khung bao (điểm tiếp đất); điểm trên đường chân trời hoặc xa hơn khoảng 150 m chỉ hiển thị là “xa”, không cảnh báo."));
add(B("Xác định làn xe chủ trên ảnh nhìn từ trên xuống bằng top-hat, cửa sổ trượt và đa thức bậc 2; khi không thấy vạch (ban đêm, vạch mờ) dùng hành lang cố định quanh trục xe. Xe phía trước là xe cùng làn gần nhất."));
add(B("Làm mượt khoảng cách bằng EMA, tốc độ tiếp cận bằng hồi quy tuyến tính trong khoảng 1 giây, tính TTC khi xe đang tiến lại gần."));
add(B([["Hướng mở rộng - tự động căn chỉnh: ", { bold: true }], "với mặt đường phẳng Y = K / (v − v₀) (v₀ là hàng của điểm tụ, K = tiêu cự × chiều cao camera); điểm tụ tìm bằng Hough + RANSAC, chiều cao camera suy từ bề rộng làn 3,75 m, hệ số K từ độ dịch chuyển của vạch kẻ đứt khi biết tốc độ xe."]));

add(H3("1.4.5. Định hướng ngưỡng an toàn và cảnh báo"));
add(P(`Ngưỡng tính theo tốc độ xe chủ V, dựa trên Bảng ${TAB_LEGAL}:`, { keepNext: true }));
add(EQ("base = bảng Thông tư 31 (V ≥ 60 km/h)  hoặc  V · 2 s (V < 60 km/h)"));
add(EQ("ngưỡng cảnh báo = max(base, d_min) × hệ số điều kiện đường"));
add(EQ("ngưỡng nguy hiểm = max(d_min, ngưỡng cảnh báo × 0,5)"));
add(P("Hệ số điều kiện đường ước tính theo quãng phanh (mục 1.2.2): hệ số ≈ 0,7 / μ, nhân thêm các yếu tố ban đêm, xe chở nặng, tài xế mệt mỏi, tối đa ×3."));
add(table(["Điều kiện", "Hệ số", "μ", "TTC cảnh báo / nguy hiểm (s)"], [
  ["Khô ráo, tầm nhìn tốt", "1,0", "0,70", "4 / 2"],
  ["Mặt đường ướt, mưa nhỏ", "1,4", "0,50", "5 / 2,5"],
  ["Mưa to, đọng nước", "2,0", "0,35", "6 / 3"],
  ["Sương mù, tầm nhìn hạn chế", "1,5", "0,60", "5,5 / 3"],
  ["Trơn trượt (dầu, bùn, sỏi)", "2,5", "0,25", "6 / 3"],
], [6.0, 2.4, 2.4, 5.2], { center: [1, 2, 3] }));
add(caption("Bảng", "Hệ số điều kiện đường (đề xuất)"));
add(P("Ví dụ: V = 90 km/h, mưa to → 70 m × 2,0: cảnh báo khi < 140 m, nguy hiểm khi < 70 m. Khi tầm nhìn hạn chế, hệ thống khuyến nghị tốc độ tối đa sao cho quãng đường dừng xe không vượt tầm nhìn."));
add(B([["Phân loại rủi ro: ", { bold: true }], "nguy hiểm khi khoảng cách < ngưỡng nguy hiểm hoặc TTC < TTC nguy hiểm; cảnh báo khi khoảng cách < ngưỡng cảnh báo hoặc TTC < TTC cảnh báo; còn lại an toàn."]));
add(B([["Chống báo nhầm: ", { bold: true }], "chỉ nâng mức khi điều kiện đúng trong N khung liên tiếp (dự kiến N = 3) và giữ mức một thời gian tối thiểu trước khi hạ."]));
add(B([["Nhật ký theo đợt: ", { bold: true }], "mỗi đợt vi phạm liên tục với cùng một xe ghi thành một bản ghi (khoảng cách nhỏ nhất, TTC nhỏ nhất, thời lượng, ảnh bằng chứng)."]));
add(...figure(TQ("T3_trang_thai_muc_canh_bao.png"), 16, "Trạng thái mức cảnh báo và cơ chế chống báo nhầm"));

add(H3("1.4.6. Định hướng Trợ lý AI gợi ý ngưỡng"));
add(B([["Chế độ offline (mặc định): ", { bold: true }], "nhận dạng từ khóa / cụm từ tiếng Việt (kể cả khi gõ không dấu), tra bảng điều kiện đường - miễn phí, không cần Internet."]));
add(B([["Chế độ Claude (tùy chọn): ", { bold: true }], "gọi Claude API, yêu cầu trả lời theo cấu trúc JSON cố định; lỗi mạng tự chuyển về offline."]));
add(B([["An toàn: ", { bold: true }], "mọi giá trị trả về bị giới hạn trong phạm vi cho phép, hệ số không bao giờ nhỏ hơn 1 (không thấp hơn quy định)."]));

add(H3("1.4.7. Phạm vi triển khai và kết quả dự kiến"));
add(table(["PI", "Yêu cầu trong đề cương", "Kết quả dự kiến", "Tuần"], [
  ["1.1", "BPMN, mô tả quy trình xử lý video/camera", "3 sơ đồ BPMN, 4 biểu mẫu dữ liệu (mục 2.2)", "1"],
  ["1.2", "Bảng yêu cầu chức năng / phi chức năng", "16 FR, 10 NFR (mục 2.3, 2.4)", "2"],
  ["1.3", "Sơ đồ UC tổng quát 5 UC + đặc tả", "UC tổng quát, 5 UC phân rã, đặc tả (mục 2.5, 2.6)", "2-3"],
  ["2.1", "Sơ đồ lớp thực thể, sơ đồ CSDL", "Sơ đồ lớp, ERD", "4"],
  ["2.2", "Kiến trúc Video Stream → YOLOv11 → IPM → Alert → GUI", "Kiến trúc tổng quan (mục 1.4.2), kiến trúc chi tiết", "4"],
  ["2.3", "Mockup giao diện trên Figma", "Mockup màn hình giám sát, căn chỉnh, nhật ký", "5"],
  ["3.1", "Khởi tạo CSDL cấu hình và nhật ký", "CSDL SQLite", "6"],
  ["3.2", "Thành phần AI/CV và GUI", "Mô hình YOLOv11 đã huấn luyện, module IPM, giao diện", "6-9"],
  ["3.3", "Thi công 5 UC", "Phần mềm hoàn chỉnh", "7-9"],
  ["3.4", "AI gợi ý ngưỡng theo tốc độ xe chủ", "Module Trợ lý AI", "8"],
  ["4.1", "Đóng gói ứng dụng desktop", "Bản cài đặt .exe", "10"],
  ["4.2", "Dataset + video kịch bản ngày / đêm / thời tiết xấu", "Dataset phương tiện, bộ video kịch bản", "3, 6, 10"],
], [1.1, 5.6, 7.1, 2.2], { center: [0, 3] }));
add(caption("Bảng", "Kết quả dự kiến theo yêu cầu PI của đề cương"));

// ================================================================ CHƯƠNG 2
add(H1("CHƯƠNG 2. KHẢO SÁT VÀ PHÂN TÍCH HỆ THỐNG"));
add(H2("2.1. Khảo sát và xác định bài toán"));
add(H3("2.1.1. Bối cảnh giữ khoảng cách trên đường cao tốc"));
add(P("Mục tiêu khảo sát: nắm quy định pháp lý về khoảng cách an toàn; tìm hiểu cách tài xế đang giữ khoảng cách và các giải pháp hỗ trợ hiện có; mô tả quy trình hiện tại và quy trình đề xuất khi có hệ thống; xác định dữ liệu cần thu thập, lưu trữ."));
add(P("Quy định (mục 1.2.2) cho trị số theo bậc tốc độ khi đường khô, nhưng không cho hệ số cụ thể khi thời tiết xấu và để trống vùng dưới 60 km/h. Trên thực tế tài xế giữ khoảng cách chủ yếu bằng cảm giác, quy tắc 2-3 giây hoặc biển kiểm tra cự ly (0 m, 50 m, 100 m, 150 m) đặt ở một số đoạn cao tốc; các cách này đều phụ thuộc vào sự chú ý của tài xế."));
add(H3("2.1.2. Khảo sát các giải pháp cảnh báo khoảng cách hiện có"));
add(P(`Kết quả khảo sát các giải pháp đã trình bày ở mục 1.3 (Bảng ${TAB_CMP}). Điểm chung là chưa có giải pháp giá rẻ, lắp được cho mọi xe, áp ngưỡng đúng quy định Việt Nam có điều chỉnh theo điều kiện đường và cho phép tra cứu lại các lần vi phạm.`));
add(H3("2.1.3. Phân tích những vấn đề cần giải quyết"));
add(B("Phát hiện đúng và ổn định các xe phía trước trong video camera hành trình, kể cả xe ở xa và khi trời tối."));
add(B("Đo khoảng cách thực (mét) từ một camera, không phụ thuộc kích thước xe; căn chỉnh được cho từng vị trí lắp camera."));
add(B("Chỉ xét xe cùng làn phía trước để tránh cảnh báo nhầm với xe ở làn bên."));
add(B("Tính ngưỡng theo tốc độ (bảng quy định, quy tắc 2 giây dưới 60 km/h) và điều kiện đường; cho phép người dùng điều chỉnh dễ dàng."));
add(B("Cảnh báo kịp thời nhưng không gây phiền (chống báo nhầm); ghi nhật ký có ảnh bằng chứng."));
add(B("Xử lý thời gian thực trên máy tính thông thường; hoạt động không cần Internet."));
add(H3("2.1.4. Xác định phạm vi hệ thống"));
add(P("Hệ thống là ứng dụng desktop gồm 5 nhóm chức năng ứng với 5 use case của đề cương: quản lý nguồn video/camera, cấu hình thông số IPM (căn chỉnh camera), cấu hình ngưỡng cảnh báo (có Trợ lý AI), giám sát realtime & cảnh báo, quản lý nhật ký cảnh báo. Phạm vi kỹ thuật như mục 1.1.4."));

// ---------- 2.2
add(H2("2.2. Khảo sát và mô hình hóa quy trình nghiệp vụ"));
add(H3("2.2.1. Quy trình chuẩn bị giám sát"));
add(P("Tài xế chọn nguồn video / camera; hệ thống nạp thông số căn chỉnh đã lưu của nguồn; nếu nguồn chưa được căn chỉnh thì tài xế căn chỉnh camera (chấm 4 điểm hoặc tự động) và hệ thống lưu ma trận camera; tài xế chọn tốc độ và mô tả điều kiện đường; hệ thống (có thể qua Trợ lý AI) tính và lưu ngưỡng an toàn."));
add(H3("2.2.2. Quy trình giám sát và cảnh báo"));
add(P("Với mỗi khung hình, hệ thống đọc khung → nhận diện và bám vết xe → xác định làn, tính khoảng cách IPM và TTC → so với ngưỡng; nếu có nguy cơ thì phát âm thanh và ghi đợt vi phạm kèm ảnh → hiển thị kết quả; lặp lại đến khi tài xế dừng hoặc hết video, cuối cùng đóng phiên giám sát."));
add(H3("2.2.3. Quy trình tra cứu nhật ký cảnh báo"));
add(P("Sau hành trình, người dùng mở lịch sử, chọn phiên giám sát, lọc vi phạm theo ngày, mức, loại xe; xem ảnh bằng chứng; xuất CSV hoặc xóa bản ghi; xem và khôi phục cấu hình cũ."));
add(H3("2.2.4. Sơ đồ BPMN quy trình tổng quát"));
add(P("Quy trình được mô hình hóa bằng BPMN 2.0. Sơ đồ tổng quát nối các quy trình: chọn nguồn → căn chỉnh camera (nếu nguồn chưa căn chỉnh) → cấu hình ngưỡng → giám sát và cảnh báo → xem lại nhật ký (trang ngang kế tiếp)."));

section(true);
add(...figure(TQ("02_bpmn_quy_trinh_tong_quat.png"), 24.7, "BPMN quy trình tổng quát", 14));

section();
add(H3("2.2.5. Sơ đồ BPMN quy trình chuẩn bị giám sát"));
add(...figure(TQ("03_bpmn_chuan_bi_giam_sat.png"), 16, "BPMN chuẩn bị giám sát", 22));
add(H3("2.2.6. Sơ đồ BPMN quy trình giám sát và cảnh báo"));
add(...figure(TQ("04_bpmn_giam_sat_canh_bao.png"), 16, "BPMN giám sát và cảnh báo (xử lý dữ liệu video/camera)", 22));

add(H3("2.2.7. Biểu mẫu dữ liệu"));
add(P("Từ khảo sát, hệ thống cần quản lý 4 nhóm dữ liệu. Mỗi biểu mẫu dưới đây liệt kê các trường cần thu thập kèm một giá trị ví dụ minh họa (camera hành trình trên đường cao tốc, khung hình 640×360)."));
const formTable = (rows) => table(["STT", "Trường dữ liệu", "Kiểu / miền giá trị", "Ví dụ"],
  rows.map((r, i) => [String(i + 1), ...r]), [1.1, 5.0, 4.4, 5.5], { center: [0] });

add(SUB("Biểu mẫu 1. Phiếu thông tin nguồn video / camera"));
add(formTable([
  ["Tên nguồn", "Chuỗi, bắt buộc", "Camera hành trình - cao tốc"],
  ["Loại nguồn", "video | camera | stream | image", "video"],
  ["Địa chỉ nguồn", "Đường dẫn file / chỉ số camera / URL RTSP, không trùng", "D:\\Video\\cao_toc_01.mp4"],
  ["Ghi chú", "Chuỗi, tùy chọn", "-"],
  ["Ngày thêm", "Ngày giờ", "01/10/2026 08:30"],
  ["Lần dùng gần nhất", "Ngày giờ", "05/10/2026 14:10"],
]));
add(caption("Bảng", "Biểu mẫu nguồn video / camera"));

add(SUB("Biểu mẫu 2. Phiếu thông số căn chỉnh camera (IPM)"));
add(formTable([
  ["Nguồn áp dụng", "Tham chiếu nguồn", "Camera hành trình - cao tốc"],
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
add(caption("Bảng", "Biểu mẫu thông số căn chỉnh camera"));

add(SUB("Biểu mẫu 3. Phiếu cấu hình ngưỡng cảnh báo"));
add(formTable([
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
add(caption("Bảng", "Biểu mẫu cấu hình ngưỡng cảnh báo"));

add(SUB("Biểu mẫu 4. Phiếu nhật ký vi phạm khoảng cách"));
add(formTable([
  ["Phiên giám sát / mã vi phạm", "Số nguyên", "Phiên 1 / vi phạm 2"],
  ["Thời điểm bắt đầu, thời lượng", "Ngày giờ, giây", "05/10/2026 14:12:05, 5,4 s"],
  ["Thời điểm trong video", "Giây", "21,27"],
  ["Mức vi phạm", "Cảnh báo | Nguy hiểm", "Cảnh báo"],
  ["Phương tiện phía trước", "Loại xe + mã bám vết", "Ô tô #1"],
  ["Khoảng cách ban đầu / nhỏ nhất", "Mét", "34,38 / 34,09"],
  ["TTC nhỏ nhất, tốc độ tiếp cận", "Giây, km/h", "16,3 s; 6,4 km/h"],
  ["Tốc độ xe chủ", "km/h", "73"],
  ["Ngưỡng cảnh báo / nguy hiểm / quy định", "Mét", "55 / 27,5 / 55"],
  ["Điều kiện đường, hệ số", "Chuỗi, số thực", "Đường khô ráo, tầm nhìn tốt; 1,0"],
  ["Ảnh bằng chứng", "Đường dẫn ảnh", "anh_vi_pham/phien_1/vi_pham_2.jpg"],
]));
add(caption("Bảng", "Biểu mẫu nhật ký vi phạm"));
add(P("Từ 4 biểu mẫu, dữ liệu của hệ thống gồm 6 nhóm với quan hệ như hình dưới (mức khái niệm; thiết kế CSDL chi tiết thuộc Chương 3, tuần 4).", { keepNext: true }));
add(...figure(TQ("T4_mo_hinh_du_lieu_khai_niem.png"), 16, "Mô hình dữ liệu khái niệm"));

// ---------- 2.3
add(H2("2.3. Phân tích yêu cầu chức năng"));
add(H3("2.3.1. Yêu cầu quản lý nguồn video / camera"));
add(P("Người dùng thêm, sửa, xóa, kiểm tra kết nối và chọn nguồn đầu vào; hệ thống nhận file video, ảnh tĩnh, camera USB và luồng camera IP (FR-01, FR-02)."));
add(H3("2.3.2. Yêu cầu căn chỉnh camera"));
add(P("Người dùng căn chỉnh camera bằng 4 điểm trên vạch làn hoặc tự động từ video; hệ thống tính và lưu ma trận camera theo từng nguồn (FR-03)."));
add(H3("2.3.3. Yêu cầu nhận diện phương tiện và đo khoảng cách"));
add(P("Hệ thống phát hiện, phân loại và bám vết xe; nhận diện làn xe chủ; tính khoảng cách thực, tốc độ tiếp cận và TTC (FR-04 đến FR-07)."));
add(H3("2.3.4. Yêu cầu cảnh báo và cấu hình ngưỡng"));
add(P("Hệ thống tính ngưỡng theo tốc độ và điều kiện đường, cảnh báo bằng hình ảnh và âm thanh; người dùng tùy chỉnh ngưỡng trực tiếp hoặc nhờ Trợ lý AI; có thể ghi video kết quả (FR-08 đến FR-12, FR-16)."));
add(H3("2.3.5. Yêu cầu nhật ký và cấu hình"));
add(P("Hệ thống ghi mỗi đợt vi phạm kèm ảnh; người dùng tra cứu, lọc, xuất, xóa nhật ký; cấu hình được lưu kèm lịch sử thay đổi và khôi phục được (FR-13 đến FR-15)."));
add(H3("2.3.6. Bảng tổng hợp yêu cầu chức năng"));
add(table(["Mã", "Chức năng", "Mô tả", "UC"], [
  ["FR-01", "Quản lý nguồn video/camera", "Thêm, sửa, xóa, kiểm tra kết nối, dò camera USB, chọn nguồn để giám sát", "UC01"],
  ["FR-02", "Nhận nhiều loại nguồn", "File video, ảnh tĩnh, camera USB, luồng RTSP/HTTP", "UC01, UC04"],
  ["FR-03", "Căn chỉnh camera (IPM)", "Chấm 4 điểm trên vạch làn hoặc tự động từ video; lưu ma trận K, H, R theo từng nguồn", "UC02"],
  ["FR-04", "Nhận diện phương tiện", "YOLOv11 phát hiện, phân loại ô tô, xe tải, xe khách; ByteTrack gán mã bám vết", "UC04"],
  ["FR-05", "Nhận diện làn xe chủ", "Tìm 2 vạch làn đang đi để chỉ xét xe cùng làn phía trước", "UC04"],
  ["FR-06", "Tính khoảng cách thực", "Đổi điểm chạm đất (giữa cạnh dưới khung bao) sang mét bằng IPM", "UC04"],
  ["FR-07", "Tốc độ tiếp cận và TTC", "Làm mượt khoảng cách theo thời gian, ước lượng tốc độ tiếp cận và thời gian va chạm", "UC04"],
  ["FR-08", "Ngưỡng theo tốc độ", "Bảng Thông tư 31 (V ≥ 60 km/h), quy tắc 2 giây (V < 60) × hệ số điều kiện đường", "UC03, UC04"],
  ["FR-09", "Cảnh báo hình ảnh", "Khung xe đổi màu xanh / vàng / đỏ, vùng nguy hiểm, ảnh nhìn từ trên xuống", "UC04"],
  ["FR-10", "Cảnh báo âm thanh", "Hai mức âm: cảnh báo và nguy hiểm, có thể bật / tắt", "UC04"],
  ["FR-11", "Tùy chỉnh ngưỡng", "Tốc độ xe chủ, điều kiện đường, hệ số, TTC, tỷ lệ nguy hiểm, chống báo nhầm", "UC03"],
  ["FR-12", "Trợ lý AI gợi ý ngưỡng", "Tài xế mô tả tình huống bằng tiếng Việt, trợ lý đề xuất và áp dụng ngưỡng theo tốc độ xe chủ", "UC03"],
  ["FR-13", "Ghi nhật ký vi phạm", "Mỗi đợt vi phạm ghi 1 bản ghi kèm ảnh bằng chứng", "UC04, UC05"],
  ["FR-14", "Tra cứu nhật ký", "Lọc theo phiên, ngày, mức, loại xe; xem ảnh; xuất CSV; xóa", "UC05"],
  ["FR-15", "Lưu cấu hình và lịch sử", "Lưu cấu hình hiện hành, bản chụp mỗi lần thay đổi, cho phép khôi phục", "UC03, UC05"],
  ["FR-16", "Ghi video kết quả", "Lưu video đã vẽ lớp phủ cảnh báo", "UC04"],
], [1.5, 3.6, 8.9, 2.0], { center: [0, 3] }));
add(caption("Bảng", "Tổng hợp yêu cầu chức năng"));

// ---------- 2.4
add(H2("2.4. Phân tích yêu cầu phi chức năng"));
add(H3("2.4.1. Yêu cầu về hiệu năng và thời gian phản hồi"));
add(P("Xử lý ≥ 25 FPS trên GPU, độ trễ mỗi khung ≤ 50 ms; vẫn chạy được ≥ 5 FPS khi không có GPU; với camera trực tiếp luôn xử lý khung mới nhất để không bị trễ dồn (NFR-01, 02, 04, 06)."));
add(H3("2.4.2. Yêu cầu về độ chính xác và độ tin cậy của module AI"));
add(P("Mô hình nhận dạng đạt mAP@0,5 ≥ 0,80; cảnh báo chỉ nâng mức sau 3 khung liên tiếp để tránh báo nhầm do nhận diện chập chờn (NFR-03, 05)."));
add(H3("2.4.3. Yêu cầu về tính ổn định và lưu trữ"));
add(P("Giao diện không bị treo khi đang xử lý; dữ liệu ghi đồng thời từ giao diện và phần xử lý vẫn toàn vẹn (NFR-07, 08)."));
add(H3("2.4.4. Yêu cầu về tính dễ sử dụng"));
add(P("Giao diện và chữ trên khung video hiển thị tiếng Việt đầy đủ dấu; mọi chức năng chính hoạt động không cần Internet (NFR-09, 10)."));
add(H3("2.4.5. Bảng tổng hợp yêu cầu phi chức năng"));
add(table(["Mã", "Yêu cầu", "Chỉ tiêu", "Cách kiểm chứng"], [
  ["NFR-01", "Tốc độ xử lý thời gian thực", "≥ 25 FPS trên GPU", "Đo FPS khi chạy video thử nghiệm"],
  ["NFR-02", "Độ trễ xử lý 1 khung", "≤ 50 ms", "Đo thời gian từng tầng xử lý mỗi khung"],
  ["NFR-03", "Độ chính xác nhận dạng", "mAP@0,5 ≥ 0,80", "Đánh giá mô hình trên tập kiểm thử độc lập"],
  ["NFR-04", "Chạy được khi không có GPU", "≥ 5 FPS trên CPU", "Chạy ở chế độ CPU"],
  ["NFR-05", "Chống báo nhầm", "Chỉ nâng mức sau 3 khung liên tiếp (≈ 0,1 s ở 30 FPS)", "Kiểm thử với nhận diện chập chờn"],
  ["NFR-06", "Camera trực tiếp độ trễ thấp", "Luôn xử lý khung mới nhất", "Đọc camera ở luồng riêng"],
  ["NFR-07", "Giao diện không bị treo", "Xử lý ở luồng nền", "Thao tác giao diện khi đang giám sát"],
  ["NFR-08", "Lưu trữ tin cậy", "Ghi đồng thời từ giao diện và phần xử lý; ràng buộc toàn vẹn", "Kiểm tra ràng buộc toàn vẹn CSDL"],
  ["NFR-09", "Giao diện tiếng Việt", "Hiển thị đủ dấu trên giao diện và khung video", "Kiểm tra trực quan"],
  ["NFR-10", "Hoạt động không cần Internet", "Mọi chức năng chính chạy offline", "Ngắt mạng khi chạy"],
], [1.7, 4.3, 5.4, 4.6], { center: [0] }));
add(caption("Bảng", "Tổng hợp yêu cầu phi chức năng"));

// ---------- 2.5
add(H2("2.5. Xác định tác nhân và Use Case"));
add(H3("2.5.1. Các tác nhân của hệ thống"));
add(table(["Tác nhân", "Loại", "Mô tả"], [
  ["Người dùng (tài xế / người vận hành)", "Chính", "Chọn nguồn, căn chỉnh camera, chọn tốc độ và điều kiện đường, theo dõi cảnh báo, tra cứu nhật ký"],
  ["Camera / nguồn video", "Phụ", "Cung cấp khung hình: camera USB, camera IP (RTSP/HTTP) hoặc file video, ảnh"],
  ["Dịch vụ Claude API", "Phụ, tùy chọn", "Gợi ý ngưỡng an toàn từ mô tả tình huống; mặc định hệ thống dùng trợ lý offline, không cần Internet"],
], [4.6, 2.4, 9.0]));
add(caption("Bảng", "Các tác nhân của hệ thống"));
add(H3("2.5.2. Sơ đồ Use Case tổng quát"));
add(P("Hệ thống có 5 use case chính đúng như đề cương: UC01 Quản lý nguồn video/camera, UC02 Cấu hình thông số IPM, UC03 Cấu hình ngưỡng cảnh báo, UC04 Giám sát realtime & cảnh báo, UC05 Quản lý nhật ký cảnh báo.", { keepNext: true }));
add(...figure(SO_DO("05_usecase_tong_quat.png"), 16, "Sơ đồ use case tổng quát"));
add(H3("2.5.3. Phân rã UC01 - Quản lý nguồn video/camera"));
add(...figure(SO_DO("06_usecase_UC01_nguon_video.png"), 16, "Phân rã UC01 - Quản lý nguồn video/camera"));
add(H3("2.5.4. Phân rã UC02 - Cấu hình thông số IPM"));
add(...figure(SO_DO("07_usecase_UC02_cau_hinh_IPM.png"), 16, "Phân rã UC02 - Cấu hình thông số IPM"));
add(H3("2.5.5. Phân rã UC03 - Cấu hình ngưỡng cảnh báo"));
add(...figure(SO_DO("08_usecase_UC03_nguong_canh_bao.png"), 16, "Phân rã UC03 - Cấu hình ngưỡng cảnh báo"));
add(H3("2.5.6. Phân rã UC04 - Giám sát realtime & cảnh báo"));
add(...figure(SO_DO("09_usecase_UC04_giam_sat.png"), 16, "Phân rã UC04 - Giám sát realtime & cảnh báo"));
add(H3("2.5.7. Phân rã UC05 - Quản lý nhật ký cảnh báo"));
add(...figure(SO_DO("10_usecase_UC05_nhat_ky.png"), 16, "Phân rã UC05 - Quản lý nhật ký cảnh báo"));

// ---------- 2.6
add(H2("2.6. Đặc tả Use Case"));
add(H3("2.6.1. Quy ước và cấu trúc bảng đặc tả Use Case"));
add(P("Mỗi use case được đặc tả bằng một bảng 2 cột gồm các mục: Mã / Tên; Mục đích; Tác nhân; Tiền điều kiện (điều kiện phải đúng trước khi bắt đầu); Hậu điều kiện (trạng thái hệ thống sau khi kết thúc thành công); Luồng chính (các bước đánh số, xen kẽ hành động của tác nhân và phản hồi của hệ thống); Luồng thay thế (ký hiệu A1, A2…); Ngoại lệ (ký hiệu E1, E2…, kèm thông báo hiển thị). Đây là bản đặc tả sơ bộ, hoàn thiện ở tuần 3."));
add(H3("2.6.2. Đặc tả UC01 - UC05"));
const UC = [
  ["UC01 - Quản lý nguồn video/camera", {
    md: "Thêm, sửa, xóa, kiểm tra kết nối và chọn nguồn đầu vào (file video, ảnh, camera USB, luồng RTSP/HTTP).",
    ta: "Người dùng (chính); Camera / nguồn video (phụ).",
    pre: "Ứng dụng đã khởi động, CSDL đã khởi tạo.",
    post: "Bảng nguồn video được cập nhật; nguồn được chọn chuyển sang giám sát (UC04); thời điểm dùng gần nhất được cập nhật.",
    main: [
      "Người dùng chọn chức năng “Quản lý nguồn”.",
      "Hệ thống mở cửa sổ Quản lý nguồn, hiển thị danh sách: tên, loại, địa chỉ nguồn, tình trạng căn chỉnh, số phiên, lần dùng gần nhất.",
      "Người dùng bấm “Thêm file video” và chọn file (mp4, avi, mov, mkv, wmv hoặc ảnh).",
      "Hệ thống xác định loại nguồn, chuẩn hóa đường dẫn và thêm nguồn mới.",
      "Người dùng chọn nguồn, bấm “Kiểm tra kết nối”.",
      "Hệ thống mở thử nguồn, hiển thị khung xem trước và “Kết nối tốt · độ phân giải · FPS · số khung”.",
      "Người dùng bấm “Mở nguồn đã chọn” (hoặc nhấp đúp vào dòng).",
      "Hệ thống dừng phiên đang chạy (nếu có), đặt nguồn mới, nạp căn chỉnh camera đã lưu của nguồn và bắt đầu giám sát (UC04).",
    ],
    alt: [
      "A1. Thêm camera / URL: bấm “Thêm camera / URL”, nhập tên, địa chỉ (0, 1… hoặc rtsp://…), ghi chú → Lưu.",
      "A2. Dò camera USB: hệ thống thử chỉ số 0-4 và tự thêm các “Camera USB i” chưa có.",
      "A3. Sửa: chọn nguồn → “Sửa” → đổi tên / địa chỉ / ghi chú → Lưu.",
      "A4. Xóa: chọn nguồn → “Xóa” → xác nhận; ma trận camera của nguồn bị xóa theo, nhật ký các phiên cũ vẫn giữ.",
      "A5. Mở nhanh một file video, ảnh, camera hoặc một nguồn dùng gần đây; nguồn tự được đăng ký.",
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
      "A1. Tự động căn chỉnh (nguồn là file video): bấm “Tự động căn chỉnh”, nhập tốc độ xe trong video (0 nếu không biết) → hệ thống phân tích: điểm tụ (Hough + RANSAC), bề rộng làn → chiều cao camera, chuyển động vạch đứt → hệ số chiều sâu K = f·h → tự điền 4 điểm và thông số.",
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
      "Hệ thống cập nhật và lưu cấu hình; ngưỡng mới có hiệu lực từ khung hình kế tiếp.",
    ],
    alt: [
      "A1. Đổi tốc độ xe chủ: chọn nấc 60 / ≤80 / ≤100 / ≤120 km/h trên thẻ “Tốc độ xe của bạn”; hệ thống tính lại và hiển thị ngay “Cảnh báo < X m · Nguy hiểm < Y m” cùng căn cứ (quy định hay ước tính 2 giây).",
      "A2. Trợ lý AI: bấm 1 trong 8 nút điều kiện (Khô ráo, Mưa nhỏ, Mưa to, Sương mù, Trơn trượt, Ban đêm, Chở nặng, Mệt mỏi) hoặc gõ mô tả (vd “đang mưa, tôi chạy 90 km/h”) → hệ thống phân tích (mặc định trợ lý offline; nếu bật thì gọi Claude) → giới hạn tham số trong phạm vi cho phép → áp dụng, đổi tốc độ nếu tài xế nêu → báo “Đã áp dụng: … cảnh báo < X m, nguy hiểm < Y m” → lưu lịch sử “Trợ lý AI (…)”.",
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
    pre: "Đã chọn nguồn (UC01); có mô hình YOLOv11 đã huấn luyện.",
    post: "Một phiên giám sát được lưu (số khung, FPS trung bình); các vi phạm kèm ảnh bằng chứng; tùy chọn video kết quả.",
    main: [
      "Người dùng bấm “Bắt đầu”.",
      "Hệ thống đăng ký nguồn, nạp thông số căn chỉnh camera của nguồn.",
      "Hệ thống mở nguồn, tải mô hình YOLOv11 (dùng GPU nếu có), đọc khung đầu, mở phiên giám sát (lưu kèm cấu hình lúc chạy).",
      "Với mỗi khung: YOLOv11 + ByteTrack nhận diện xe (khung bao, loại xe, mã bám vết); nhận diện làn xe chủ; đổi điểm chạm đất sang mét bằng IPM → khoảng cách, độ lệch ngang; làm mượt, tính tốc độ tiếp cận và TTC.",
      "Tính ngưỡng theo tốc độ và điều kiện đường; phân loại từng xe cùng làn: an toàn / cảnh báo / nguy hiểm; xe phía trước là xe cùng làn gần nhất.",
      "Chống báo nhầm: chỉ nâng mức sau 3 khung liên tiếp, giữ mức tối thiểu 0,8 s mới hạ; phát âm (cảnh báo 820 Hz mỗi 0,9 s; nguy hiểm 1250 Hz mỗi 0,28 s).",
      "Ghi nhật ký: mở đợt vi phạm khi mức ổn định là cảnh báo / nguy hiểm (chụp ảnh); nâng mức thì cập nhật ảnh; an toàn trở lại hoặc đổi xe phía trước thì đóng đợt (thời lượng, khoảng cách nhỏ nhất, TTC nhỏ nhất).",
      "Vẽ khung màu (xanh / vàng / đỏ), nhãn “Ô tô #id 24,2 m”, vùng nguy hiểm, banner cảnh báo, ảnh nhìn từ trên xuống; cập nhật thẻ trạng thái (khoảng cách, TTC, tốc độ tiếp cận, FPS, thời gian từng tầng) và danh sách vi phạm của phiên.",
      "Người dùng bấm “Dừng” hoặc video hết.",
      "Hệ thống đóng đợt vi phạm đang mở, kết thúc phiên, báo “Phiên #id: đã ghi n vi phạm vào CSDL”.",
    ],
    alt: [
      "A1. “Tạm dừng” / tiếp tục; video tiếp tục đúng nhịp thời gian thực.",
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
      "Người dùng chọn chức năng “Lịch sử”.",
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
            "A6. Khi đang giám sát: tab “Vi phạm” ở cửa sổ chính hiển thị vi phạm của phiên hiện tại và cho xuất CSV.",
    ],
    ex: [
      "E1. Không có vi phạm để xuất: “Không có vi phạm nào để xuất.”",
      "E2. Ảnh bằng chứng đã bị xóa khỏi ổ đĩa: vùng ảnh để trống, ghi “không có ảnh”.",
      "E3. Chọn “No” ở hộp xác nhận: không xóa / không khôi phục.",
    ],
  }],
];
UC.forEach(([name, s]) => {
  add(SUB(name));
  add(ucSpec([
    ["Mã / Tên", name],
    ["Mục đích", s.md],
    ["Tác nhân", s.ta],
    ["Tiền điều kiện", s.pre],
    ["Hậu điều kiện", s.post],
    ["Luồng chính", stepParas(s.main, true)],
    ["Luồng thay thế", stepParas(s.alt, false)],
    ["Ngoại lệ", stepParas(s.ex, false)],
  ]));
  add(caption("Bảng", `Đặc tả ${name.split(" - ")[0]}`));
});

add(H3("2.6.3. Tổng hợp quan hệ giữa Use Case và yêu cầu chức năng"));
add(table(["Use case", "Yêu cầu chức năng", "Tác nhân"], [
  ["UC01 - Quản lý nguồn video/camera", "FR-01, FR-02", "Người dùng; Camera / nguồn video"],
  ["UC02 - Cấu hình thông số IPM", "FR-03", "Người dùng"],
  ["UC03 - Cấu hình ngưỡng cảnh báo", "FR-08, FR-11, FR-12, FR-15", "Người dùng; Dịch vụ Claude API"],
  ["UC04 - Giám sát realtime & cảnh báo", "FR-02, FR-04, FR-05, FR-06, FR-07, FR-08, FR-09, FR-10, FR-13, FR-16", "Người dùng; Camera / nguồn video"],
  ["UC05 - Quản lý nhật ký cảnh báo", "FR-13, FR-14, FR-15", "Người dùng"],
], [5.6, 5.8, 4.6]));
add(caption("Bảng", "Quan hệ giữa use case và yêu cầu chức năng"));

// ================================================================ Tiến độ
add(H1("TIẾN ĐỘ VÀ KẾ HOẠCH"));
add(H2("1. Tiến độ so với đề cương"));
add(table(["Tuần", "Công việc (đề cương)", "Kết quả / tình trạng"], [
  [["1", "28/9-4/10"], "Khảo sát thực tế: biểu mẫu dữ liệu, BPMN", "Hoàn thành: khảo sát quy định và giải pháp, 4 biểu mẫu, 3 BPMN"],
  [["2", "5/10-11/10"], "Yêu cầu chức năng / phi chức năng, sơ đồ Use Case", "Hoàn thành: 16 FR, 10 NFR, UC tổng quát + 5 UC phân rã; cơ sở lý thuyết và định hướng giải quyết"],
  [["3", "12/10-18/10"], "Đặc tả Use Case, thu thập và chuẩn hóa Dataset", "Đang thực hiện: đã có đặc tả sơ bộ 5 UC; đã có dataset 13.003 ảnh, cần bổ sung ảnh cao tốc Việt Nam"],
  [["4", "19/10-25/10"], "ERD, kiến trúc xử lý luồng video, sơ đồ lớp", "Kế hoạch"],
  [["5", "26/10-1/11"], "Thiết kế giao diện (UI/UX)", "Kế hoạch"],
  [["6", "2/11-8/11"], "Xây dựng CSDL, huấn luyện YOLOv11", "Kế hoạch"],
  [["7", "9/11-15/11"], "Module IPM đo khoảng cách", "Kế hoạch"],
  [["8", "16/11-22/11"], "Module cảnh báo và Trợ lý AI", "Kế hoạch"],
  [["9", "23/11-29/11"], "GUI, tích hợp, kiểm thử", "Kế hoạch"],
  [["10", "30/11-7/12"], "Đóng gói, kiểm thử video kịch bản, viết báo cáo", "Kế hoạch"],
], [2.4, 6.4, 7.2], { center: [0] }));
add(caption("Bảng", "Tiến độ thực hiện so với đề cương"));

add(H2("2. Hệ thống sơ đồ"));
add(table(["Loại sơ đồ", "Nội dung", "Vị trí / tuần", "Tình trạng"], [
  ["BPMN 2.0 (3)", "Quy trình tổng quát; chuẩn bị giám sát; giám sát và cảnh báo", "Mục 2.2 - tuần 1", "Đã xong"],
  ["Use case (6)", "Tổng quát; phân rã UC01-UC05", "Mục 2.5 - tuần 2", "Đã xong"],
  ["Kiến trúc tổng quan", "5 tầng xử lý, CSDL, Trợ lý AI", "Mục 1.4.2", "Đã xong (mức tổng quan)"],
  ["Luồng xử lý một khung hình", "Các bước xử lý mỗi khung hình khi giám sát", "Mục 1.4.2", "Đã xong (mức tổng quan)"],
  ["Trạng thái mức cảnh báo", "An toàn / cảnh báo / nguy hiểm, chống báo nhầm", "Mục 1.4.5", "Đã xong (mức tổng quan)"],
  ["Mô hình dữ liệu khái niệm", "6 nhóm dữ liệu và quan hệ", "Mục 2.2.7", "Đã xong (mức khái niệm)"],
  ["Hoạt động (activity)", "Luồng thực hiện từng UC01-UC05", "Tuần 3", "Kế hoạch"],
  ["Tuần tự (sequence)", "Tương tác giữa các thành phần cho từng UC", "Tuần 4", "Kế hoạch"],
  ["Lớp (class)", "Lớp thực thể, điều khiển, giao diện", "Tuần 4", "Kế hoạch"],
  ["ERD", "Thiết kế CSDL chi tiết", "Tuần 4", "Kế hoạch"],
  ["Kiến trúc chi tiết, triển khai", "Thành phần phần mềm, luồng xử lý, môi trường chạy", "Tuần 4", "Kế hoạch"],
  ["Mockup giao diện (Figma)", "Màn hình giám sát, căn chỉnh camera, nhật ký", "Tuần 5", "Kế hoạch"],
], [3.8, 5.6, 3.4, 3.2]));
add(caption("Bảng", "Hệ thống sơ đồ của dự án"));

add(H2("3. Khó khăn dự kiến và hướng giải quyết"));
add(table(["Khó khăn", "Hướng giải quyết"], [
  ["Dataset hiện có chủ yếu là ảnh đô thị ban đêm, ảnh gần trùng giữa tập train và test", "Bổ sung ảnh cao tốc Việt Nam ban ngày, chia lại theo đoạn video, đánh giá trên bộ video độc lập (tuần 6)"],
  ["Độ chính xác IPM phụ thuộc vị trí lắp camera và độ chính xác căn chỉnh", "Căn chỉnh riêng cho từng nguồn video (UC02); kiểm chứng khoảng cách bằng mốc thực trên đường (vạch kẻ đứt, biển báo khoảng cách)"],
  ["IPM giả định mặt đường phẳng; sai số tăng nhanh ở khoảng cách xa (sau 80-100 m)", "Giới hạn tầm đo tin cậy khoảng 150 m, xe xa hơn không cảnh báo; nêu rõ giới hạn trong báo cáo"],
  ["Chưa có tốc độ thực của xe (GPS / OBD)", "Người dùng chọn nấc tốc độ hoặc nêu qua Trợ lý AI; hướng phát triển: đọc GPS"],
  ["Thiếu video ban đêm và thời tiết xấu để kiểm thử (PI 4.2)", "Thu thập thêm từ camera hành trình trước tuần 9"],
], [7.5, 8.5]));
add(caption("Bảng", "Khó khăn dự kiến và hướng giải quyết"));

add(H2("4. Các vấn đề xin ý kiến thầy"));
add(B("Phạm vi lớp phương tiện: giữ 3 lớp mục tiêu (ô tô, xe tải, xe khách) và không theo dõi xe máy trên cao tốc có phù hợp không?"));
add(B("Cách kiểm chứng độ chính xác khoảng cách: dùng mốc vạch kẻ / biển khoảng cách trên cao tốc có được chấp nhận không?"));
add(B("Trợ lý AI dùng chế độ offline làm mặc định, Claude API là tùy chọn - có đáp ứng yêu cầu PI 3.4 không?"));

// ================================================================ Tài liệu tham khảo
add(H1("TÀI LIỆU THAM KHẢO"));
[
  "Bộ Giao thông vận tải, Thông tư 31/2019/TT-BGTVT ngày 29/8/2019 quy định về tốc độ và khoảng cách an toàn của xe cơ giới, xe máy chuyên dùng tham gia giao thông đường bộ.",
  "J. Redmon, S. Divvala, R. Girshick, A. Farhadi, “You Only Look Once: Unified, Real-Time Object Detection,” in Proc. IEEE CVPR, 2016.",
  "G. Jocher, J. Qiu, “Ultralytics YOLO11,” 2024. [Online]. https://github.com/ultralytics/ultralytics",
  "Y. Zhang et al., “ByteTrack: Multi-Object Tracking by Associating Every Detection Box,” in Proc. ECCV, 2022.",
  "Z. Zhang, “A flexible new technique for camera calibration,” IEEE Trans. Pattern Analysis and Machine Intelligence, vol. 22, no. 11, pp. 1330-1334, 2000.",
  "H. A. Mallot, H. H. Bülthoff, J. J. Little, S. Bohrer, “Inverse perspective mapping simplifies optical flow computation and obstacle detection,” Biological Cybernetics, vol. 64, no. 3, pp. 177-185, 1991.",
  "M. Bertozzi, A. Broggi, “GOLD: A parallel real-time stereo vision system for generic obstacle and lane detection,” IEEE Trans. Image Processing, vol. 7, no. 1, pp. 62-81, 1998.",
  "G. P. Stein, O. Mano, A. Shashua, “Vision-based ACC with a single camera: bounds on range and range rate accuracy,” in Proc. IEEE Intelligent Vehicles Symposium, 2003.",
  "R. Hartley, A. Zisserman, Multiple View Geometry in Computer Vision, 2nd ed. Cambridge University Press, 2004.",
  "T.-Y. Lin et al., “Microsoft COCO: Common Objects in Context,” in Proc. ECCV, 2014.",
  "T.-Y. Lin et al., “Feature Pyramid Networks for Object Detection,” in Proc. IEEE CVPR, 2017.",
  "S. Liu, L. Qi, H. Qin, J. Shi, J. Jia, “Path Aggregation Network for Instance Segmentation,” in Proc. IEEE CVPR, 2018.",
  "R. E. Kalman, “A New Approach to Linear Filtering and Prediction Problems,” Journal of Basic Engineering, vol. 82, no. 1, pp. 35-45, 1960.",
  "M. A. Fischler, R. C. Bolles, “Random Sample Consensus: A Paradigm for Model Fitting with Applications to Image Analysis and Automated Cartography,” Communications of the ACM, vol. 24, no. 6, pp. 381-395, 1981.",
  "R. O. Duda, P. E. Hart, “Use of the Hough Transformation to Detect Lines and Curves in Pictures,” Communications of the ACM, vol. 15, no. 1, pp. 11-15, 1972.",
  "J. C. Hayward, “Near-miss determination through use of a scale of danger,” Highway Research Record, no. 384, 1972.",
  "Anthropic, “Claude API Documentation.” [Online]. https://docs.anthropic.com",
  "M. Everingham et al., “The Pascal Visual Object Classes (VOC) Challenge,” International Journal of Computer Vision, vol. 88, no. 2, pp. 303-338, 2010.",
].forEach((t, i) => add(new Paragraph({
  children: runs(`[${i + 1}] ${t}`), alignment: AlignmentType.JUSTIFIED,
  spacing: { after: 60, line: 288 }, indent: { left: 567, hanging: 567 },
})));

add(H1("NHẬN XÉT CỦA GIẢNG VIÊN HƯỚNG DẪN"));
for (let i = 0; i < 5; i++) {
  add(new Paragraph({ children: runs(".".repeat(150), { size: 22 }), spacing: { after: 120 } }));
}
add(P(""));
add(new Paragraph({ alignment: AlignmentType.RIGHT, children: runs([["Thái Nguyên, ngày … tháng … năm 2026", { italics: true }]]) }));
const sig = (lines, w) => new TableCell({
  borders: NOB, width: { size: w, type: WidthType.DXA },
  children: lines.map(([t, o]) => new Paragraph({ alignment: AlignmentType.CENTER, children: runs([[t, o]]) })),
});
add(new Table({
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
  title: "Báo cáo tiến độ đồ án tốt nghiệp - Chương 1, Chương 2",
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
  sections: sections.map((s) => ({
    properties: s.landscape ? landscape : portrait, footers: { default: footer }, children: captionsAbove(s.children),
  })),
});

Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(OUT, buf); console.log("OK", OUT, figNo, "hình,", tabNo, "bảng"); });
