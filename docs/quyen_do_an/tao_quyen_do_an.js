// Quyển báo cáo đồ án tốt nghiệp: phần đầu, Chương 1 (đầy đủ), khung Chương 2-4, phần cuối.
//   node tao_quyen_do_an.js            (cần thư viện docx; biến OUT để đổi file ra)
// Mục lục / danh mục hình / danh mục bảng là trường TOC: mở bằng Word và cập nhật trường (F9)
// hoặc chạy cap_nhat_muc_luc.ps1 để điền sẵn số trang.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType, ShadingType,
  AlignmentType, ImageRun, BorderStyle, LevelFormat, VerticalAlign, Footer, PageNumber, NumberFormat,
  TableOfContents, StyleLevel, Tab, TabStopType, PageBorderDisplay, PageBorderOffsetFrom,
} = require("docx");

const DOCS = "C:/A_Nam4/Đồ án/giaodien/docs";
const OUT = process.env.OUT || path.join(DOCS, "quyen_do_an", "BAO_CAO_DO_AN_TOT_NGHIEP.docx");
const TQ = (n) => path.join(DOCS, "bao_cao_tien_do", "so_do_tong_quan", n);
const HINH = (n) => path.join(DOCS, "bao_cao_tien_do", "hinh", n);
const FONT = "Times New Roman";
const CM = 567;                       // DXA / cm
const TEXT_W = 16 * CM;               // A4, lề trái 3 cm, phải 2 cm

// ---------------------------------------------------------------- tài liệu tham khảo (đánh số theo thứ tự trích dẫn)
const REFS = {
  tt31: "Bộ Giao thông vận tải, Thông tư 31/2019/TT-BGTVT ngày 29/8/2019 quy định về tốc độ và khoảng cách an toàn của xe cơ giới, xe máy chuyên dùng tham gia giao thông đường bộ.",
  goodfellow: "I. Goodfellow, Y. Bengio, A. Courville, Deep Learning. MIT Press, 2016.",
  lecun: "Y. LeCun, L. Bottou, Y. Bengio, P. Haffner, “Gradient-based learning applied to document recognition,” Proceedings of the IEEE, vol. 86, no. 11, pp. 2278-2324, 1998.",
  coco: "T.-Y. Lin et al., “Microsoft COCO: Common Objects in Context,” in Proc. ECCV, 2014.",
  frcnn: "S. Ren, K. He, R. Girshick, J. Sun, “Faster R-CNN: Towards Real-Time Object Detection with Region Proposal Networks,” in Proc. NeurIPS, 2015.",
  ssd: "W. Liu et al., “SSD: Single Shot MultiBox Detector,” in Proc. ECCV, 2016.",
  yolo1: "J. Redmon, S. Divvala, R. Girshick, A. Farhadi, “You Only Look Once: Unified, Real-Time Object Detection,” in Proc. IEEE CVPR, 2016.",
  yolo4: "A. Bochkovskiy, C.-Y. Wang, H.-Y. M. Liao, “YOLOv4: Optimal Speed and Accuracy of Object Detection,” arXiv:2004.10934, 2020.",
  yolo7: "C.-Y. Wang, A. Bochkovskiy, H.-Y. M. Liao, “YOLOv7: Trainable bag-of-freebies sets new state-of-the-art for real-time object detectors,” in Proc. IEEE CVPR, 2023.",
  yolo11: "G. Jocher, J. Qiu, “Ultralytics YOLO11,” 2024. [Online]. https://github.com/ultralytics/ultralytics",
  fpn: "T.-Y. Lin et al., “Feature Pyramid Networks for Object Detection,” in Proc. IEEE CVPR, 2017.",
  pan: "S. Liu, L. Qi, H. Qin, J. Shi, J. Jia, “Path Aggregation Network for Instance Segmentation,” in Proc. IEEE CVPR, 2018.",
  ciou: "Z. Zheng et al., “Distance-IoU Loss: Faster and Better Learning for Bounding Box Regression,” in Proc. AAAI, 2020.",
  gfl: "X. Li et al., “Generalized Focal Loss: Learning Qualified and Distributed Bounding Boxes for Dense Object Detection,” in Proc. NeurIPS, 2020.",
  sort: "A. Bewley, Z. Ge, L. Ott, F. Ramos, B. Upcroft, “Simple Online and Realtime Tracking,” in Proc. IEEE ICIP, 2016.",
  bytetrack: "Y. Zhang et al., “ByteTrack: Multi-Object Tracking by Associating Every Detection Box,” in Proc. ECCV, 2022.",
  kalman: "R. E. Kalman, “A New Approach to Linear Filtering and Prediction Problems,” Journal of Basic Engineering, vol. 82, no. 1, pp. 35-45, 1960.",
  kuhn: "H. W. Kuhn, “The Hungarian method for the assignment problem,” Naval Research Logistics Quarterly, vol. 2, no. 1-2, pp. 83-97, 1955.",
  hartley: "R. Hartley, A. Zisserman, Multiple View Geometry in Computer Vision, 2nd ed. Cambridge University Press, 2004.",
  mallot: "H. A. Mallot, H. H. Bülthoff, J. J. Little, S. Bohrer, “Inverse perspective mapping simplifies optical flow computation and obstacle detection,” Biological Cybernetics, vol. 64, no. 3, pp. 177-185, 1991.",
  gold: "M. Bertozzi, A. Broggi, “GOLD: A parallel real-time stereo vision system for generic obstacle and lane detection,” IEEE Trans. Image Processing, vol. 7, no. 1, pp. 62-81, 1998.",
  zhang: "Z. Zhang, “A flexible new technique for camera calibration,” IEEE Trans. Pattern Analysis and Machine Intelligence, vol. 22, no. 11, pp. 1330-1334, 2000.",
  stein: "G. P. Stein, O. Mano, A. Shashua, “Vision-based ACC with a single camera: bounds on range and range rate accuracy,” in Proc. IEEE Intelligent Vehicles Symposium, 2003.",
  gonzalez: "R. C. Gonzalez, R. E. Woods, Digital Image Processing, 4th ed. Pearson, 2018.",
  hough: "R. O. Duda, P. E. Hart, “Use of the Hough Transformation to Detect Lines and Curves in Pictures,” Communications of the ACM, vol. 15, no. 1, pp. 11-15, 1972.",
  ransac: "M. A. Fischler, R. C. Bolles, “Random Sample Consensus: A Paradigm for Model Fitting with Applications to Image Analysis and Automated Cartography,” Communications of the ACM, vol. 24, no. 6, pp. 381-395, 1981.",
  hayward: "J. C. Hayward, “Near-miss determination through use of a scale of danger,” Highway Research Record, no. 384, 1972.",
  transformer: "A. Vaswani et al., “Attention Is All You Need,” in Proc. NeurIPS, 2017.",
  claude: "Anthropic, “Claude API Documentation.” [Online]. https://docs.anthropic.com",
  voc: "M. Everingham et al., “The Pascal Visual Object Classes (VOC) Challenge,” International Journal of Computer Vision, vol. 88, no. 2, pp. 303-338, 2010.",
  pytorch: "A. Paszke et al., “PyTorch: An Imperative Style, High-Performance Deep Learning Library,” in Proc. NeurIPS, 2019.",
  opencv: "G. Bradski, “The OpenCV Library,” Dr. Dobb's Journal of Software Tools, 2000.",
};
const refOrder = [];
const cite = (...keys) => keys.map((k) => {
  if (!REFS[k]) throw new Error("Thiếu tài liệu " + k);
  if (!refOrder.includes(k)) refOrder.push(k);
  return `[${refOrder.indexOf(k) + 1}]`;
}).join(", ");

// ---------------------------------------------------------------- tiện ích văn bản
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
  spacing: { before: 0, after: 120, line: 360 },
  indent: o.noIndent ? undefined : { firstLine: 567 },
  keepNext: o.keepNext,
});
const B = (content) => new Paragraph({
  children: runs(content), numbering: { reference: "gach", level: 0 },
  alignment: AlignmentType.JUSTIFIED, spacing: { after: 60, line: 360 },
});
const N = (content) => new Paragraph({
  children: runs(content), numbering: { reference: "so", level: 0, instance: nInstance },
  alignment: AlignmentType.JUSTIFIED, spacing: { after: 60, line: 360 },
});
let nInstance = 0;
const newList = () => { nInstance += 1; };
const SUB = (t) => new Paragraph({ children: runs([[t, { bold: true, italics: true }]]), spacing: { before: 120, after: 80, line: 360 }, keepNext: true });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: runs(t), alignment: AlignmentType.CENTER,
  pageBreakBefore: true, spacing: { before: 0, after: 360 }, keepNext: true });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: runs(t), spacing: { before: 240, after: 120 }, keepNext: true });
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: runs(t), spacing: { before: 180, after: 100 }, keepNext: true });
const TITLE = (t, pageBreak = true) => new Paragraph({ style: "TieuDePhu", children: runs(t), alignment: AlignmentType.CENTER,
  pageBreakBefore: pageBreak, spacing: { before: 0, after: 360 } });
const NOTE = (t) => new Paragraph({ children: runs([[t, { italics: true }]]), alignment: AlignmentType.CENTER, spacing: { after: 240 } });

// ---------------------------------------------------------------- đánh số theo chương: hình, bảng, công thức
let chap = 0;
let figNo = 0;
let tabNo = 0;
let eqNo = 0;
const nextFig = () => `${chap}.${figNo + 1}`;
const nextTab = () => `${chap}.${tabNo + 1}`;
const tableCaptions = new Set();
function caption(kind, text) {
  const no = kind === "Hình" ? `${chap}.${++figNo}` : `${chap}.${++tabNo}`;
  const par = new Paragraph({
    style: kind === "Hình" ? "CaptionHinh" : "CaptionBang",
    children: runs([[`${kind} ${no}. `, { bold: true }], text]),
    alignment: AlignmentType.CENTER,
    spacing: { before: kind === "Hình" ? 60 : 200, after: kind === "Hình" ? 200 : 80 },
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
// Công thức: căn giữa, số thứ tự (c.n) căn phải; trả về chuỗi "(c.n)" để dẫn trong văn bản
function EQ(text) {
  const no = `(${chap}.${++eqNo})`;
  add(new Paragraph({
    tabStops: [{ type: TabStopType.CENTER, position: TEXT_W / 2 }, { type: TabStopType.RIGHT, position: TEXT_W }],
    children: [new TextRun({ font: FONT, children: [new Tab()] }), new TextRun({ text, font: FONT, italics: true }),
      new TextRun({ font: FONT, children: [new Tab(), no] })],
    spacing: { before: 60, after: 120, line: 360 },
  }));
  return no;
}
function figure(file, widthCm, text, maxHeightCm = 21) {
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
  add(new Paragraph({
    children: [new ImageRun({ type: file.endsWith(".png") ? "png" : "jpg", data: buf,
      transformation: { width: Math.round(ww), height: Math.round(hh) } })],
    alignment: AlignmentType.CENTER, spacing: { before: 120, after: 0 }, keepNext: true,
  }));
  add(caption("Hình", text));
}

const BORDER = { style: BorderStyle.SINGLE, size: 4, color: "000000" };
const BORDERS = { top: BORDER, bottom: BORDER, left: BORDER, right: BORDER };
function cell(content, width, o = {}) {
  const paras = [].concat(content).map((c) => new Paragraph({
    children: runs(c, { size: 24, bold: o.bold }),
    alignment: o.align || AlignmentType.LEFT, spacing: { after: 20, line: 276 },
  }));
  return new TableCell({
    children: paras, borders: BORDERS, width: { size: width, type: WidthType.DXA },
    shading: o.fill ? { fill: o.fill, type: ShadingType.CLEAR, color: "auto" } : undefined,
    verticalAlign: o.valign || VerticalAlign.TOP,
    margins: { top: 50, bottom: 50, left: 90, right: 90 },
  });
}
function table(headers, rows, widthsCm, captionText, o = {}) {
  const widths = widthsCm.map((c) => Math.round(c * CM));
  const total = widths.reduce((a, b) => a + b, 0);
  const head = new TableRow({
    tableHeader: true,
    children: headers.map((h, i) => cell(h, widths[i], { bold: true, fill: "DCE6F1", align: AlignmentType.CENTER,
      valign: VerticalAlign.CENTER })),
  });
  const body = rows.map((r) => new TableRow({
    cantSplit: true,
    children: r.map((c, i) => cell(c, widths[i], { align: (o.center || []).includes(i) ? AlignmentType.CENTER : undefined })),
  }));
  add(new Table({ width: { size: total, type: WidthType.DXA }, columnWidths: widths, rows: [head, ...body] }));
  add(caption("Bảng", captionText));
  add(new Paragraph({ children: [], spacing: { after: 60 } }));
}

// Các section: bìa / phần đầu (số trang La Mã) / nội dung (số trang Ả Rập)
const sections = [];
let cur;
function section(kind) { cur = { kind, children: [] }; sections.push(cur); }
const add = (...xs) => cur.children.push(...xs);
function chapter(n, title) {
  chap = n; figNo = 0; tabNo = 0; eqNo = 0;
  add(H1(`CHƯƠNG ${n}. ${title}`));
}

// ================================================================ BÌA
section("cover");
const C = (t, o = {}) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: o.before ?? 0, after: o.after ?? 0, line: 300 },
  children: runs([[t, { bold: o.bold, size: o.size || 28, italics: o.italics }]]) });
add(C("ĐẠI HỌC THÁI NGUYÊN", { size: 28 }));
add(C("TRƯỜNG ĐẠI HỌC CÔNG NGHỆ THÔNG TIN VÀ TRUYỀN THÔNG", { bold: true, size: 28 }));
add(C("KHOA CÔNG NGHỆ THÔNG TIN", { bold: true, size: 28, after: 1800 }));
add(C("ĐỒ ÁN TỐT NGHIỆP", { bold: true, size: 40, after: 120 }));
add(C("NGÀNH CÔNG NGHỆ THÔNG TIN", { bold: true, size: 28, after: 900 }));
add(C("ĐỀ TÀI:", { bold: true, size: 28, after: 120 }));
add(C("XÂY DỰNG HỆ THỐNG CẢNH BÁO KHOẢNG CÁCH AN TOÀN GIỮA CÁC PHƯƠNG TIỆN TRÊN CAO TỐC THỜI GIAN THỰC ỨNG DỤNG MÔ HÌNH YOLOv11 VÀ THỊ GIÁC MÁY TÍNH",
  { bold: true, size: 32, after: 1500 }));
const NB = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const NOB = { top: NB, bottom: NB, left: NB, right: NB };
const infoRow = (k, v) => new TableRow({ children: [
  new TableCell({ borders: NOB, width: { size: 6.2 * CM, type: WidthType.DXA }, children: [new Paragraph({ children: runs([[k, { size: 28 }]]) })] }),
  new TableCell({ borders: NOB, width: { size: 7.8 * CM, type: WidthType.DXA }, children: [new Paragraph({ children: runs([[v, { size: 28, bold: true }]]) })] }),
] });
add(new Table({
  width: { size: 14 * CM, type: WidthType.DXA }, columnWidths: [6.2 * CM, 7.8 * CM], alignment: AlignmentType.CENTER,
  rows: [
    infoRow("Giảng viên hướng dẫn:", "TS. Nguyễn Thành Trung"),
    infoRow("Sinh viên thực hiện:", "Nguyễn Đức Thắng"),
    infoRow("Mã sinh viên:", "DTC235200703"),
    infoRow("Lớp:", "CNTT K22A CN"),
  ],
}));
add(C("Thái Nguyên, năm 2026", { bold: true, size: 28, before: 2000 }));

// ================================================================ PHẦN ĐẦU
section("front");
add(TITLE("LỜI CẢM ƠN", false));
add(P("Em xin gửi lời cảm ơn chân thành tới TS. Nguyễn Thành Trung, giảng viên Bộ môn Kỹ thuật máy tính, Khoa Công nghệ thông tin, Trường Đại học Công nghệ Thông tin và Truyền thông - Đại học Thái Nguyên, người đã tận tình hướng dẫn, định hướng và góp ý cho em trong suốt quá trình thực hiện đồ án."));
add(P("Em xin cảm ơn các thầy cô trong Khoa Công nghệ thông tin đã truyền đạt cho em những kiến thức nền tảng trong những năm học vừa qua, là cơ sở để em hoàn thành đồ án này. Em cũng xin cảm ơn gia đình và bạn bè đã luôn động viên, hỗ trợ em trong quá trình học tập và nghiên cứu."));
add(P("Do thời gian và kiến thức còn hạn chế, đồ án không tránh khỏi những thiếu sót. Em rất mong nhận được ý kiến đóng góp của các thầy cô để đồ án được hoàn thiện hơn."));
add(P("Em xin chân thành cảm ơn!"));
add(new Paragraph({ alignment: AlignmentType.RIGHT, spacing: { before: 240 }, children: runs([["Thái Nguyên, ngày … tháng … năm 2026", { italics: true }]]) }));
add(new Paragraph({ alignment: AlignmentType.RIGHT, indent: { right: 900 }, children: runs([["Sinh viên", { bold: true }]]) }));
add(new Paragraph({ alignment: AlignmentType.RIGHT, spacing: { before: 1000 }, indent: { right: 400 }, children: runs([["Nguyễn Đức Thắng", { bold: true }]]) }));

add(TITLE("LỜI CAM ĐOAN"));
add(P("Em xin cam đoan đồ án tốt nghiệp với đề tài “Xây dựng hệ thống cảnh báo khoảng cách an toàn giữa các phương tiện trên cao tốc thời gian thực ứng dụng mô hình YOLOv11 và thị giác máy tính” là kết quả nghiên cứu của bản thân em dưới sự hướng dẫn của TS. Nguyễn Thành Trung."));
add(P("Các nội dung tham khảo trong đồ án đều được trích dẫn nguồn rõ ràng trong danh mục tài liệu tham khảo. Các kết quả trình bày trong đồ án là trung thực, không sao chép từ công trình của người khác. Nếu có sai phạm, em xin hoàn toàn chịu trách nhiệm."));
add(new Paragraph({ alignment: AlignmentType.RIGHT, spacing: { before: 240 }, children: runs([["Thái Nguyên, ngày … tháng … năm 2026", { italics: true }]]) }));
add(new Paragraph({ alignment: AlignmentType.RIGHT, indent: { right: 900 }, children: runs([["Sinh viên", { bold: true }]]) }));
add(new Paragraph({ alignment: AlignmentType.RIGHT, spacing: { before: 1000 }, indent: { right: 400 }, children: runs([["Nguyễn Đức Thắng", { bold: true }]]) }));

add(TITLE("MỤC LỤC"));
add(new TableOfContents("Mục lục", { hyperlink: true, headingStyleRange: "1-3" }));
add(TITLE("DANH MỤC HÌNH VẼ"));
add(new TableOfContents("Danh mục hình", { hyperlink: true, stylesWithLevels: [new StyleLevel("CaptionHinh", 4)] }));
add(TITLE("DANH MỤC BẢNG BIỂU"));
add(new TableOfContents("Danh mục bảng", { hyperlink: true, stylesWithLevels: [new StyleLevel("CaptionBang", 4)] }));

add(TITLE("DANH MỤC CÁC TỪ VIẾT TẮT"));
{
  const ab = [
    ["ADAS", "Advanced Driver Assistance Systems", "Hệ thống hỗ trợ lái xe nâng cao"],
    ["AEB", "Autonomous Emergency Braking", "Phanh khẩn cấp tự động"],
    ["AI", "Artificial Intelligence", "Trí tuệ nhân tạo"],
    ["AP / mAP", "(mean) Average Precision", "Độ chính xác trung bình (trung bình các lớp)"],
    ["API", "Application Programming Interface", "Giao diện lập trình ứng dụng"],
    ["BEV", "Bird's-Eye View", "Ảnh nhìn từ trên xuống"],
    ["BPMN", "Business Process Model and Notation", "Ký pháp mô hình hóa quy trình nghiệp vụ"],
    ["CNN", "Convolutional Neural Network", "Mạng nơ-ron tích chập"],
    ["CSDL", "-", "Cơ sở dữ liệu"],
    ["EMA", "Exponential Moving Average", "Trung bình trượt hàm mũ"],
    ["FCW", "Forward Collision Warning", "Cảnh báo va chạm phía trước"],
    ["FPN / PAN", "Feature Pyramid Network / Path Aggregation Network", "Mạng kim tự tháp đặc trưng / mạng gộp đường dẫn"],
    ["FPS", "Frames Per Second", "Số khung hình mỗi giây"],
    ["GPU", "Graphics Processing Unit", "Bộ xử lý đồ họa"],
    ["IoU", "Intersection over Union", "Tỷ lệ giao trên hợp"],
    ["IPM", "Inverse Perspective Mapping", "Biến đổi phối cảnh ngược"],
    ["LLM", "Large Language Model", "Mô hình ngôn ngữ lớn"],
    ["NMS", "Non-Maximum Suppression", "Khử các khung không cực đại"],
    ["RANSAC", "Random Sample Consensus", "Đồng thuận mẫu ngẫu nhiên"],
    ["RTSP", "Real Time Streaming Protocol", "Giao thức truyền luồng thời gian thực"],
    ["TTC", "Time To Collision", "Thời gian còn lại trước va chạm"],
    ["UC", "Use Case", "Ca sử dụng"],
    ["YOLO", "You Only Look Once", "Họ mô hình phát hiện đối tượng một giai đoạn"],
  ];
  const w = [2.6, 6.4, 7.0].map((c) => Math.round(c * CM));
  add(new Table({
    width: { size: w[0] + w[1] + w[2], type: WidthType.DXA }, columnWidths: w,
    rows: [new TableRow({ tableHeader: true, children: ["Từ viết tắt", "Tiếng Anh", "Ý nghĩa"].map((h, i) => cell(h, w[i], { bold: true, fill: "DCE6F1", align: AlignmentType.CENTER })) }),
      ...ab.map((r) => new TableRow({ children: r.map((c, i) => cell(c, w[i])) }))],
  }));
}

// ================================================================ NỘI DUNG
section("body");
add(H1("LỜI MỞ ĐẦU"));
add(SUB("1. Tính cấp thiết của đề tài"));
add(P("Giữ khoảng cách không an toàn là một trong những nguyên nhân chính gây tai nạn liên hoàn trên đường cao tốc, nơi xe chạy với tốc độ 80-120 km/h. Quy định về khoảng cách an toàn đã có, nhưng tài xế khó ước lượng chính xác khoảng cách bằng mắt, còn các hệ thống cảnh báo va chạm trang bị sẵn chủ yếu có trên xe đời mới. Trong khi đó camera hành trình đã rất phổ biến; nếu kết hợp với mô hình học sâu và kỹ thuật thị giác máy tính, có thể xây dựng một hệ thống cảnh báo khoảng cách chi phí thấp, lắp được cho mọi xe và áp ngưỡng đúng theo quy định của Việt Nam."));
add(SUB("2. Mục tiêu của đề tài"));
add(P("Nghiên cứu, thiết kế và xây dựng ứng dụng phần mềm cảnh báo khoảng cách an toàn giữa các phương tiện trên cao tốc theo thời gian thực: phát hiện phương tiện bằng YOLOv11, ước lượng khoảng cách thực bằng biến đổi phối cảnh ngược (IPM), so sánh với ngưỡng an toàn theo tốc độ và điều kiện đường, cảnh báo bằng hình ảnh và âm thanh, ghi nhật ký vi phạm, kèm Trợ lý AI gợi ý ngưỡng."));
add(SUB("3. Phương pháp nghiên cứu"));
add(B([["Nghiên cứu tài liệu: ", { bold: true }], "quy định pháp luật về khoảng cách an toàn; lý thuyết học sâu, phát hiện và bám vết đối tượng, hình học camera, xử lý ảnh; các công trình liên quan."]));
add(B([["Khảo sát và mô hình hóa: ", { bold: true }], "khảo sát quy trình giữ khoảng cách và các giải pháp hiện có; mô hình hóa bằng BPMN và UML."]));
add(B([["Thực nghiệm: ", { bold: true }], "huấn luyện, đánh giá mô hình trên tập dữ liệu phương tiện; kiểm thử hệ thống trên các video hành trình theo kịch bản ban ngày, ban đêm, thời tiết xấu."]));
add(SUB("4. Bố cục của báo cáo"));
add(P("Ngoài phần mở đầu, kết luận và tài liệu tham khảo, báo cáo gồm 4 chương:"));
add(B([["Chương 1. Cơ sở lý thuyết: ", { bold: true }], "tổng quan đề tài, các kiến thức nền tảng và công nghệ sử dụng, các công trình liên quan và định hướng giải quyết."]));
add(B([["Chương 2. Khảo sát và phân tích hệ thống: ", { bold: true }], "khảo sát bài toán, quy trình nghiệp vụ, yêu cầu chức năng, yêu cầu phi chức năng, use case và đặc tả."]));
add(B([["Chương 3. Thiết kế hệ thống: ", { bold: true }], "kiến trúc phần mềm, thiết kế chi tiết chức năng, sơ đồ lớp, cơ sở dữ liệu, thuật toán và giao diện."]));
add(B([["Chương 4. Triển khai: ", { bold: true }], "môi trường cài đặt, chuẩn bị dữ liệu và huấn luyện mô hình, cài đặt chức năng, kiểm thử, đóng gói và hướng dẫn sử dụng."]));

// ================================================================ CHƯƠNG 1
chapter(1, "CƠ SỞ LÝ THUYẾT");

// ---------------------------------------------------------------- 1.1
add(H2("1.1. Tổng quan đề tài"));
add(H3("1.1.1. Bối cảnh và lý do lựa chọn đề tài"));
add(P("Mạng lưới đường cao tốc Việt Nam đang được mở rộng nhanh chóng, lưu lượng phương tiện và tốc độ khai thác ngày càng cao. Ở tốc độ 80-120 km/h, mỗi giây xe đi được 22-33 m; chỉ một chút chậm trễ trong phản xạ cũng đủ khiến xe không dừng kịp khi xe phía trước phanh gấp. Vì vậy, giữ khoảng cách không an toàn là một trong những nguyên nhân chính dẫn đến các vụ va chạm liên hoàn trên cao tốc."));
add(P(`Thông tư 31/2019/TT-BGTVT ${cite("tt31")} đã quy định khoảng cách an toàn tối thiểu theo từng dải tốc độ. Tuy nhiên trên thực tế tài xế rất khó ước lượng chính xác khoảng cách bằng mắt, đặc biệt khi trời tối, mưa, sương mù hoặc khi mệt mỏi sau hành trình dài. Các hệ thống cảnh báo va chạm phía trước dùng radar hoặc camera chuyên dụng chủ yếu được trang bị trên xe đời mới, phiên bản cao cấp; số lượng lớn xe đang lưu hành không có chức năng này.`));
add(P("Trong khi đó, camera hành trình đã trở nên phổ biến trên xe ô tô ở Việt Nam, và các mô hình học sâu phát hiện đối tượng như YOLO đã đạt tốc độ xử lý thời gian thực trên máy tính thông thường. Kết hợp camera hành trình với mô hình học sâu và kỹ thuật thị giác máy tính cho phép xây dựng một hệ thống cảnh báo khoảng cách chi phí thấp, lắp được cho mọi xe, áp ngưỡng theo đúng quy định của Việt Nam. Đó là lý do em lựa chọn đề tài “Xây dựng hệ thống cảnh báo khoảng cách an toàn giữa các phương tiện trên cao tốc thời gian thực ứng dụng mô hình YOLOv11 và thị giác máy tính”."));

add(H3("1.1.2. Giới thiệu bài toán cảnh báo khoảng cách an toàn trên cao tốc"));
add(P("Bài toán được phát biểu như sau: từ chuỗi hình ảnh của camera hành trình đặt phía trước xe chủ, theo thời gian thực, hệ thống cần (1) phát hiện và phân loại các phương tiện phía trước; (2) xác định xe đi cùng làn gần nhất; (3) ước lượng khoảng cách thực (mét) và xu hướng tiếp cận tới xe đó; (4) so sánh với khoảng cách an toàn tính theo tốc độ xe chủ và điều kiện đường; (5) cảnh báo tài xế khi khoảng cách vi phạm ngưỡng và lưu lại các lần vi phạm."));
table(["Hạng mục", "Nội dung"], [
  ["Đầu vào", ["Hình ảnh từ file video hành trình, ảnh tĩnh, camera USB hoặc camera IP (RTSP/HTTP)",
    "Tốc độ xe chủ do người dùng chọn hoặc nêu qua Trợ lý AI",
    "Mô tả điều kiện đường (khô ráo, mưa, sương mù, trơn trượt, ban đêm, chở nặng, mệt mỏi)"]],
  ["Đầu ra", ["Hình ảnh hiển thị khung xe đổi màu xanh / vàng / đỏ, nhãn khoảng cách (m), vùng nguy hiểm, ảnh nhìn từ trên xuống",
    "Âm thanh cảnh báo 2 mức (cảnh báo / nguy hiểm)",
    "Nhật ký vi phạm khoảng cách kèm ảnh bằng chứng, có thể tra cứu và xuất file"]],
  ["Ràng buộc", ["Xử lý thời gian thực (≥ 25 khung hình/giây khi có GPU)",
    "Chỉ dùng một camera thông thường, không dùng radar / lidar"]],
], [3.2, 12.8], "Đầu vào, đầu ra và ràng buộc của bài toán");

add(H3("1.1.3. Mục tiêu nghiên cứu và phát triển hệ thống"));
add(B("Nghiên cứu mô hình YOLOv11 để phát hiện và phân loại phương tiện (ô tô, xe tải, xe khách) theo thời gian thực; bám vết từng xe qua các khung hình bằng ByteTrack."));
add(B("Nghiên cứu mô hình camera và phép biến đổi phối cảnh ngược (IPM) để quy đổi vị trí xe trên ảnh sang khoảng cách thực trên mặt đường; xác định làn xe chủ từ vạch kẻ đường."));
add(B("Xây dựng quy tắc ngưỡng an toàn theo tốc độ xe chủ (Thông tư 31) và điều kiện đường; cảnh báo 2 mức bằng hình ảnh và âm thanh, có cơ chế chống báo nhầm."));
add(B("Xây dựng Trợ lý AI gợi ý ngưỡng từ mô tả tình huống bằng tiếng Việt, hoạt động được cả khi không có Internet."));
add(B("Phát triển ứng dụng desktop hoàn chỉnh gồm 5 chức năng chính: quản lý nguồn video/camera, cấu hình thông số IPM, cấu hình ngưỡng cảnh báo, giám sát realtime & cảnh báo, quản lý nhật ký cảnh báo; đóng gói chạy thử nghiệm."));

add(H3("1.1.4. Đối tượng và phạm vi nghiên cứu"));
add(B([["Đối tượng nghiên cứu: ", { bold: true }], "phương tiện cơ giới trên đường cao tốc (ô tô con, xe tải, xe khách); hình ảnh từ camera hành trình đơn đặt phía trước xe; quy định về khoảng cách an toàn của Việt Nam; các mô hình phát hiện, bám vết đối tượng và kỹ thuật thị giác máy tính liên quan."]));
add(B([["Phạm vi: ", { bold: true }], "xe chủ đi theo làn trên đường cao tốc; mặt đường được xem là phẳng; tầm đo tin cậy khoảng 150 m; tốc độ xe chủ do người dùng nhập (chưa lấy từ GPS / OBD); phần mềm chạy trên máy tính Windows có hoặc không có GPU."]));
add(B([["Ngoài phạm vi: ", { bold: true }], "can thiệp điều khiển xe (phanh tự động); xe máy và người đi bộ; đường đô thị; hệ thống nhiều camera (stereo), radar hoặc lidar."]));

// ---------------------------------------------------------------- 1.2
add(H2("1.2. Cơ sở lý thuyết"));
add(H3("1.2.1. Hệ thống hỗ trợ lái xe nâng cao và cảnh báo va chạm phía trước"));
add(P("Hệ thống hỗ trợ lái xe nâng cao (ADAS - Advanced Driver Assistance Systems) là tập hợp các chức năng dùng cảm biến trên xe để nhận biết môi trường xung quanh và hỗ trợ tài xế, ví dụ cảnh báo lệch làn, cảnh báo điểm mù, kiểm soát hành trình thích ứng, nhận diện biển báo. Trong đó, cảnh báo va chạm phía trước (FCW - Forward Collision Warning) theo dõi xe phía trước và cảnh báo khi khoảng cách hoặc thời gian còn lại trước va chạm xuống dưới mức an toàn; khi kết hợp với chức năng tự động phanh thì gọi là phanh khẩn cấp tự động (AEB)."));
add(P("Một hệ thống FCW gồm 3 khối: cảm nhận (phát hiện xe phía trước và đo khoảng cách, tốc độ tương đối), đánh giá rủi ro (so với ngưỡng khoảng cách hoặc thời gian va chạm) và cảnh báo (hình ảnh, âm thanh, rung). Khối cảm nhận có thể dùng các loại cảm biến khác nhau:"));
table(["Cảm biến", "Nguyên lý", "Ưu điểm", "Hạn chế"], [
  ["Radar", "Phát sóng vô tuyến, đo thời gian và độ lệch tần số sóng phản xạ", "Đo trực tiếp khoảng cách và vận tốc; ít chịu ảnh hưởng của mưa, sương, bóng tối", "Khó phân loại vật thể; độ phân giải góc thấp; chi phí cao hơn camera"],
  ["Lidar", "Phát xung laser, đo thời gian bay của tia phản xạ", "Đám mây điểm 3D chính xác cao", "Giá thành cao; giảm hiệu quả khi mưa, sương mù"],
  ["Camera đơn", "Thu ảnh màu, suy ra vật thể và khoảng cách bằng thuật toán", "Rẻ, phổ biến (camera hành trình); nhận dạng tốt loại xe, vạch làn, biển báo", "Không đo trực tiếp khoảng cách; phụ thuộc ánh sáng; cần căn chỉnh"],
  ["Camera kép (stereo)", "Hai camera đặt cách nhau, tính độ sâu từ độ lệch ảnh (disparity)", "Đo được độ sâu", "Cần phần cứng chuyên dụng, hiệu chỉnh phức tạp"],
], [2.6, 4.2, 4.6, 4.6], "So sánh các loại cảm biến dùng cho cảnh báo va chạm phía trước");
add(P("Đề tài thuộc nhóm FCW dùng một camera thông thường, chỉ cảnh báo, không can thiệp điều khiển xe. Khó khăn chính là phải suy ra khoảng cách từ ảnh 2D, được giải quyết bằng hình học camera ở mục 1.2.7."));

add(H3("1.2.2. Quy định về khoảng cách an toàn và quãng đường dừng xe"));
add(P(`Thông tư 31/2019/TT-BGTVT ${cite("tt31")} quy định khoảng cách an toàn tối thiểu giữa hai xe khi mặt đường khô ráo theo tốc độ lưu hành (Bảng ${nextTab()}). Tốc độ tối đa trên đường cao tốc là 120 km/h. Khi trời mưa, có sương mù, mặt đường trơn trượt, đường có địa hình quanh co, đèo dốc, tầm nhìn hạn chế, người lái xe phải điều chỉnh khoảng cách lớn hơn trị số ghi trong bảng. Với tốc độ dưới 60 km/h, quy định để người lái xe chủ động giữ khoảng cách phù hợp với mật độ phương tiện và tình hình giao thông thực tế.`));
const TAB_LEGAL = nextTab();
table(["Tốc độ lưu hành V (km/h)", "Khoảng cách an toàn tối thiểu (m)"], [
  ["V = 60", "35"], ["60 < V ≤ 80", "55"], ["80 < V ≤ 100", "70"], ["100 < V ≤ 120", "100"],
], [8, 8], "Khoảng cách an toàn tối thiểu khi mặt đường khô ráo (Thông tư 31/2019/TT-BGTVT)", { center: [0, 1] });
add(P("Về mặt vật lý, quãng đường dừng xe gồm quãng đường xe đi trong thời gian phản xạ của tài xế (chưa phanh) và quãng phanh:", { keepNext: true }));
const eqStop = EQ("S_dừng = v · t_px + v² / (2 · μ · g)");
add(P(`trong đó v là vận tốc (m/s), t_px là thời gian phản xạ (thường lấy 1-1,5 s), μ là hệ số bám giữa lốp và mặt đường, g = 9,81 m/s². Hệ số bám phụ thuộc mặt đường: khô ráo μ ≈ 0,7; ướt μ ≈ 0,5; đọng nước μ ≈ 0,35; trơn trượt (dầu, bùn) μ ≈ 0,25. Bảng ${nextTab()} và Hình ${nextFig()} tính theo công thức ${eqStop} với t_px = 1,5 s.`));
table(["Tốc độ (km/h)", "Thông tư 31 (m)", "Dừng xe - khô ráo (m)", "Dừng xe - ướt (m)", "Dừng xe - mưa to (m)"], [
  ["60", "35", "45", "53", "65"], ["80", "55", "69", "84", "105"], ["100", "70", "98", "120", "154"], ["120", "100", "131", "163", "212"],
], [2.8, 3.0, 3.4, 3.4, 3.4], "Quãng đường dừng xe theo tốc độ và điều kiện mặt đường (t_px = 1,5 s)", { center: [0, 1, 2, 3, 4] });
figure(TQ("H1_quang_duong_dung.png"), 15, "Quãng đường dừng xe theo tốc độ và điều kiện mặt đường so với Thông tư 31");
add(P("Nhận xét: trị số của Thông tư 31 nhỏ hơn quãng đường dừng hẳn của xe sau, vì khi xe trước phanh nó cũng cần một quãng đường để dừng; khoảng cách cần giữ là phần chênh lệch do thời gian phản xạ và do xe trước có thể phanh gấp hơn. Tuy vậy, Hình cho thấy rõ quãng đường dừng tăng theo bình phương tốc độ và tăng mạnh khi hệ số bám giảm: ở 100 km/h, mưa to làm quãng đường dừng tăng khoảng 1,6 lần so với đường khô. Vì quy định chỉ yêu cầu “lớn hơn” khi thời tiết xấu mà không cho con số, đề tài dùng tỷ số quãng phanh (≈ μ_khô / μ) làm hệ số nhân ngưỡng (mục 1.4.5)."));
add(P("Ngoài bảng quy định, quy tắc giãn cách theo thời gian (giữ cách xe trước ít nhất 2 giây, tức khoảng cách d = v · 2 s) là cách ước lượng đơn giản, được dùng phổ biến khi không có bảng tra; đề tài dùng quy tắc này cho vùng tốc độ dưới 60 km/h mà quy định để trống."));

add(H3("1.2.3. Học sâu và mạng nơ-ron tích chập"));
add(P(`Học sâu (deep learning) là nhánh của học máy dùng mạng nơ-ron nhiều lớp để tự học biểu diễn đặc trưng từ dữ liệu ${cite("goodfellow")}. Với dữ liệu ảnh, kiến trúc phổ biến là mạng nơ-ron tích chập (CNN) ${cite("lecun")}, gồm các thành phần chính:`));
add(B([["Lớp tích chập: ", { bold: true }], "trượt một bộ lọc (kernel) K kích thước nhỏ trên ảnh hoặc bản đồ đặc trưng I để tạo bản đồ đặc trưng mới, phát hiện các mẫu cục bộ như cạnh, góc, kết cấu; các lớp sâu hơn kết hợp thành mẫu phức tạp (bánh xe, kính, thân xe)."]));
EQ("(I * K)(i, j) = Σₘ Σₙ I(i + m, j + n) · K(m, n)");
add(B([["Hàm kích hoạt phi tuyến: ", { bold: true }], "ReLU f(x) = max(0, x) hoặc SiLU f(x) = x · σ(x) (dùng trong YOLO), giúp mạng biểu diễn được quan hệ phi tuyến."]));
add(B([["Giảm kích thước: ", { bold: true }], "lớp gộp (pooling) hoặc tích chập bước nhảy 2 làm giảm độ phân giải, mở rộng vùng nhìn (receptive field) của các lớp sau."]));
add(B([["Huấn luyện: ", { bold: true }], "tối thiểu hóa hàm mất mát L(θ) trên tập dữ liệu có nhãn bằng lan truyền ngược và thuật toán tối ưu dạng gradient (SGD, Adam): θ ← θ − η · ∇L(θ), với η là tốc độ học."]));
add(P(`Huấn luyện một mạng sâu từ đầu đòi hỏi rất nhiều dữ liệu. Kỹ thuật học chuyển giao (transfer learning) khởi tạo mạng từ trọng số đã huấn luyện trên tập dữ liệu lớn như COCO ${cite("coco")} (khoảng 118 nghìn ảnh huấn luyện, 80 lớp, trong đó có car, truck, bus), rồi huấn luyện tinh chỉnh (fine-tune) trên tập dữ liệu nhỏ hơn của bài toán; nhờ đó mô hình hội tụ nhanh và chính xác hơn.`));

add(H3("1.2.4. Bài toán phát hiện đối tượng"));
add(P("Phát hiện đối tượng (object detection) là bài toán xác định vị trí (khung bao chữ nhật) và loại của mọi đối tượng quan tâm trong ảnh, kèm độ tin cậy. Các phương pháp học sâu chia làm 2 nhóm:"));
add(B([["Hai giai đoạn: ", { bold: true }], `tiêu biểu là Faster R-CNN ${cite("frcnn")}: giai đoạn 1 sinh các vùng đề xuất có khả năng chứa đối tượng, giai đoạn 2 phân loại và tinh chỉnh từng vùng. Độ chính xác cao nhưng tốc độ chậm.`]));
add(B([["Một giai đoạn: ", { bold: true }], `tiêu biểu là YOLO ${cite("yolo1")} và SSD ${cite("ssd")}: dự đoán trực tiếp khung bao và lớp trên lưới đặc trưng trong một lần lan truyền qua mạng. Tốc độ cao, phù hợp xử lý video thời gian thực.`]));
add(P(`Mức độ trùng khớp giữa hai khung bao A và B được đo bằng IoU (Intersection over Union) - tỷ lệ giữa diện tích phần giao và phần hợp (Hình ${nextFig()}):`, { keepNext: true }));
const eqIoU = EQ("IoU(A, B) = |A ∩ B| / |A ∪ B|");
figure(TQ("H3_iou.png"), 14, "Minh họa IoU giữa khung dự đoán và khung thật");
add(P(`Mô hình thường dự đoán nhiều khung chồng lên nhau cho cùng một đối tượng. Thuật toán khử các khung không cực đại (NMS) giữ lại khung có độ tin cậy cao nhất, loại bỏ các khung còn lại có IoU với nó lớn hơn một ngưỡng (ví dụ 0,45), lặp lại cho đến khi hết khung.`));

add(H3("1.2.5. Họ mô hình YOLO và YOLOv11"));
add(P(`YOLO (You Only Look Once) do Redmon và cộng sự đề xuất năm 2016 ${cite("yolo1")}, coi phát hiện đối tượng là một bài toán hồi quy duy nhất trên toàn ảnh. Qua nhiều phiên bản, họ YOLO liên tục cải thiện cả độ chính xác và tốc độ (Bảng ${nextTab()}).`));
table(["Phiên bản", "Năm", "Đóng góp chính"], [
  ["YOLOv1", "2016", `Lưới S×S, mỗi ô dự đoán khung và lớp; xử lý thời gian thực ${cite("yolo1")}`],
  ["YOLOv2, YOLOv3", "2017, 2018", "Anchor box, dự đoán ở nhiều tỷ lệ, backbone Darknet"],
  ["YOLOv4", "2020", `Tổng hợp các kỹ thuật huấn luyện (bag of freebies), CSPDarknet, tăng cường mosaic ${cite("yolo4")}`],
  ["YOLOv5", "2020", "Triển khai trên PyTorch (Ultralytics), dễ huấn luyện và triển khai"],
  ["YOLOv6, YOLOv7", "2022", `Tối ưu cho triển khai công nghiệp; tái tham số hóa, E-ELAN ${cite("yolo7")}`],
  ["YOLOv8", "2023", "Đầu dự đoán anchor-free, tách nhánh phân loại / hồi quy (Ultralytics)"],
  ["YOLOv9, YOLOv10", "2024", "Thông tin gradient có thể lập trình (PGI); bỏ NMS khi suy luận"],
  ["YOLOv11", "2024", `Khối C3k2, C2PSA; ít tham số hơn với độ chính xác cao hơn YOLOv8 ${cite("yolo11")}`],
], [3.4, 2.4, 10.2], "Quá trình phát triển của họ mô hình YOLO", { center: [1] });
add(P(`YOLOv11 ${cite("yolo11")} gồm 3 phần (Hình ${nextFig()}):`, { keepNext: true }));
add(B([["Backbone: ", { bold: true }], "chuỗi lớp tích chập và khối C3k2 trích xuất đặc trưng, độ phân giải giảm dần; SPPF (Spatial Pyramid Pooling - Fast) gộp đặc trưng ở nhiều kích thước vùng; C2PSA (khối chú ý theo vùng) giúp mạng tập trung vào vùng chứa đối tượng."]));
add(B([["Neck: ", { bold: true }], `kết hợp đặc trưng 3 mức phân giải theo kiểu FPN ${cite("fpn")} (đường từ trên xuống, đưa thông tin ngữ nghĩa xuống lớp độ phân giải cao) và PAN ${cite("pan")} (đường từ dưới lên, đưa thông tin vị trí chi tiết lên).`]));
add(B([["Head: ", { bold: true }], "dự đoán ở 3 tỷ lệ P3, P4, P5 (lưới 80×80, 40×40, 20×20 với ảnh 640×640) để phát hiện cả đối tượng nhỏ (xe ở xa) và lớn (xe ở gần); không dùng anchor; tách riêng nhánh phân loại và nhánh hồi quy khung bao."]));
figure(TQ("T5_kien_truc_yolov11.png"), 16, "Kiến trúc tổng quát của YOLOv11");
add(P(`Hàm mất mát khi huấn luyện là tổng có trọng số của 3 thành phần: mất mát hồi quy khung bao theo CIoU ${cite("ciou")} (xét đồng thời độ trùng khớp, khoảng cách tâm và tỷ lệ cạnh), mất mát phân phối DFL ${cite("gfl")} (biểu diễn tọa độ cạnh dưới dạng phân phối) và mất mát phân loại BCE (entropy chéo nhị phân):`, { keepNext: true }));
EQ("L = λ_box · L_CIoU + λ_dfl · L_DFL + λ_cls · L_BCE");
add(P(`với hệ số mặc định của Ultralytics λ_box = 7,5; λ_dfl = 1,5; λ_cls = 0,5. YOLOv11 có 5 kích cỡ, đánh đổi giữa tốc độ và độ chính xác (Bảng ${nextTab()}).`));
table(["Mô hình", "Số tham số (triệu)", "FLOPs (tỷ)", "mAP@0,5:0,95 trên COCO"], [
  ["YOLOv11n", "2,6", "6,5", "39,5"], ["YOLOv11s", "9,4", "21,5", "47,0"], ["YOLOv11m", "20,1", "68,0", "51,5"],
  ["YOLOv11l", "25,3", "86,9", "53,4"], ["YOLOv11x", "56,9", "194,9", "54,7"],
], [3.4, 4.2, 3.4, 5.0], `Các kích cỡ của YOLOv11 (ảnh 640×640, số liệu công bố của Ultralytics ${cite("yolo11")})`, { center: [1, 2, 3] });
add(P("Đề tài chọn YOLOv11n: số tham số và khối lượng tính toán nhỏ nhất nên đạt tốc độ thời gian thực cả trên máy tính không có GPU mạnh; độ chính xác được bù lại bằng huấn luyện tinh chỉnh trên dữ liệu phương tiện của bài toán."));

add(H3("1.2.6. Bám vết đa đối tượng và thuật toán ByteTrack"));
add(P(`Mô hình phát hiện xử lý từng khung hình độc lập, không biết xe ở khung này là xe nào ở khung trước. Bám vết đa đối tượng (multi-object tracking) gán cho mỗi đối tượng một mã định danh cố định qua các khung, theo hướng “phát hiện rồi liên kết” (tracking-by-detection) như SORT ${cite("sort")}. Hai thành phần cơ bản:`));
add(B([["Bộ lọc Kalman ", { bold: true }], `${cite("kalman")}: mô hình chuyển động vận tốc không đổi, trạng thái mỗi vết gồm tâm, tỷ lệ cạnh, chiều cao khung bao và vận tốc của chúng. Bước dự đoán và bước cập nhật:`]));
EQ("x̂ₜ = F · xₜ₋₁ ;   Pₜ = F · Pₜ₋₁ · Fᵀ + Q");
EQ("Kₜ = Pₜ · Hᵀ · (H · Pₜ · Hᵀ + R)⁻¹ ;   xₜ = x̂ₜ + Kₜ · (zₜ − H · x̂ₜ)");
add(P("trong đó F là ma trận chuyển trạng thái, P là hiệp phương sai ước lượng, Q và R là nhiễu quá trình và nhiễu đo, H là ma trận đo, zₜ là khung bao phát hiện được, Kₜ là hệ số Kalman.", { noIndent: true }));
add(B([["Ghép cặp: ", { bold: true }], `tính ma trận chi phí 1 − IoU giữa các vết dự đoán và các phát hiện, giải bài toán phân công tối ưu bằng thuật toán Hungary ${cite("kuhn")}.`]));
add(P(`ByteTrack ${cite("bytetrack")} cải tiến ở chỗ tận dụng cả các phát hiện có độ tin cậy thấp thay vì loại bỏ chúng (Hình ${nextFig()}): lần ghép thứ nhất dùng các phát hiện tin cậy cao; các vết còn lại được ghép lần hai với các phát hiện tin cậy thấp - thường là xe bị che khuất một phần hoặc mờ do chuyển động. Nhờ đó giảm hiện tượng mất vết và đổi mã. Mã cố định của mỗi xe là cơ sở để làm mượt khoảng cách theo thời gian, tính tốc độ tiếp cận và gom các khung vi phạm liên tiếp thành một đợt vi phạm.`));
figure(TQ("T6_bytetrack.png"), 13, "Các bước liên kết của thuật toán ByteTrack", 17);

add(H3("1.2.7. Mô hình camera và biến đổi phối cảnh ngược (IPM)"));
add(SUB("a) Mô hình camera lỗ kim"));
add(P(`Theo mô hình camera lỗ kim ${cite("hartley")}, một điểm (X, Y, Z) trong hệ tọa độ thế giới được chiếu thành điểm ảnh (u, v):`, { keepNext: true }));
const eqPin = EQ("s · [u, v, 1]ᵀ = K · [R | t] · [X, Y, Z, 1]ᵀ ,   K = [[f, 0, c_x], [0, f, c_y], [0, 0, 1]]");
add(P("trong đó K là ma trận nội tham số (tiêu cự f tính bằng pixel, tâm ảnh (c_x, c_y)), R và t là ma trận quay và vector tịnh tiến mô tả tư thế camera, s là hệ số tỷ lệ."));
add(SUB("b) Homography mặt đường"));
add(P(`Chọn hệ tọa độ thế giới gắn với mặt đường (Z = 0), trục Y hướng theo chiều xe chạy, trục X sang ngang. Khi đó cột thứ ba của R bị triệt tiêu và phép chiếu ${eqPin} trở thành một phép biến đổi giữa hai mặt phẳng - homography:`, { keepNext: true }));
EQ("s · [u, v, 1]ᵀ = K · [r₁ r₂ t] · [X, Y, 1]ᵀ = G · [X, Y, 1]ᵀ");
add(P("Biến đổi phối cảnh ngược dùng ma trận nghịch đảo H = G⁻¹ để đưa một điểm ảnh về tọa độ mét trên mặt đường:", { keepNext: true }));
const eqIPM = EQ("[X·w, Y·w, w]ᵀ = H · [u, v, 1]ᵀ ,   X = (X·w) / w ,   Y = (Y·w) / w");
add(P(`H có 9 phần tử nhưng xác định sai khác một hệ số tỷ lệ nên có 8 bậc tự do. Mỗi cặp điểm tương ứng (ảnh ↔ mặt đường) cho 2 phương trình tuyến tính, vì vậy chỉ cần 4 cặp điểm (không có 3 điểm thẳng hàng) là giải được H bằng phương pháp DLT ${cite("hartley")}. Trên đường cao tốc, 4 điểm thuận tiện nhất là 4 góc của một đoạn làn đường: bề rộng làn đã biết (3,75 m với cao tốc Việt Nam), chiều dài đoạn ước lượng theo các vạch kẻ đứt.`));
add(P(`Biến đổi IPM do Mallot và cộng sự đề xuất ${cite("mallot")}; hệ thống GOLD ${cite("gold")} đã dùng IPM để phát hiện làn đường và vật cản theo thời gian thực. Áp dụng H cho toàn bộ khung hình sẽ được ảnh nhìn từ trên xuống (Bird's-Eye View), trên đó các vạch làn song song và khoảng cách đo trực tiếp bằng mét. Ngược lại, từ H có thể phân rã ra K, R, t (phương pháp của Zhang ${cite("zhang")}) để suy ra tiêu cự, chiều cao camera và góc chúc.`));
add(SUB("c) Đo khoảng cách tới xe phía trước"));
add(P(`IPM chỉ đúng với các điểm nằm trên mặt đường. Với một xe phía trước, điểm thích hợp là điểm tiếp đất - trung điểm cạnh dưới khung bao do YOLO phát hiện (Hình ${nextFig()}). Khi camera đặt ở độ cao h, trục quang học gần song song mặt đường, quan hệ giữa hàng ảnh v của điểm tiếp đất và khoảng cách Y theo tam giác đồng dạng ${cite("stein")}:`, { keepNext: true }));
const eqY = EQ("Y = f · h / (v − v₀)");
figure(TQ("H2_hinh_hoc_camera.png"), 15.5, "Hình học camera - mặt đường khi đo khoảng cách tới xe phía trước");
add(P(`với v₀ là hàng ảnh của đường chân trời. Lấy đạo hàm ${eqY} cho thấy sai số khoảng cách ứng với sai số Δv pixel của điểm tiếp đất tăng theo bình phương khoảng cách:`, { keepNext: true }));
const eqErr = EQ("ΔY ≈ Y² · Δv / (f · h)");
add(P(`Ví dụ với camera hành trình độ phân giải 640×360, f ≈ 430 px, h ≈ 1,2 m, sai số 1 pixel ở đáy khung bao gây sai số khoảng cách như Bảng ${nextTab()}. Đây là lý do cần giới hạn tầm đo tin cậy và làm mượt số đo theo thời gian.`));
table(["Khoảng cách Y (m)", "20", "50", "100", "150"], [
  ["Sai số do lệch 1 pixel (m)", "≈ 0,8", "≈ 4,8", "≈ 19", "≈ 44"],
  ["Sai số tương đối", "≈ 4%", "≈ 10%", "≈ 19%", "≈ 29%"],
], [5.2, 2.7, 2.7, 2.7, 2.7], "Sai số khoảng cách do lệch 1 pixel theo công thức " + eqErr + " (f ≈ 430 px, h ≈ 1,2 m)", { center: [1, 2, 3, 4] });
add(P("Giả định mặt đường phẳng cũng là một nguồn sai số: khi đường lên dốc, xuống dốc hoặc xe chủ chúc ngóc khi phanh, tăng tốc, đường chân trời trên ảnh bị dịch chuyển. Các ảnh hưởng này càng lớn khi khoảng cách càng xa."));

add(H3("1.2.8. Xử lý ảnh trong nhận diện vạch kẻ làn đường"));
add(P(`Để chỉ xét xe cùng làn, hệ thống cần biết làn đường xe chủ đang đi. Vạch kẻ làn là các nét sơn sáng, hẹp trên nền mặt đường tối hơn; trên ảnh nhìn từ trên xuống, các vạch gần như song song và thẳng đứng. Các kỹ thuật xử lý ảnh liên quan ${cite("gonzalez")}:`));
add(B([["Biến đổi top-hat: ", { bold: true }], "hiệu giữa ảnh và phép mở hình thái (opening) của nó với phần tử cấu trúc b rộng hơn nét sơn: T(I) = I − (I ∘ b). Kết quả giữ lại các chi tiết sáng hẹp (vạch sơn), loại bỏ vùng sáng rộng như bóng nắng, mặt đường sáng."]));
add(B([["Biểu đồ cột và cửa sổ trượt: ", { bold: true }], "cộng cường độ ảnh theo từng cột để tìm vị trí chân hai vạch gần xe nhất (hai đỉnh của biểu đồ), sau đó trượt các cửa sổ nhỏ dọc theo từng vạch, trong mỗi cửa sổ lấy trọng tâm các điểm sáng."]));
add(B([["Khớp đa thức: ", { bold: true }], "mỗi vạch được mô tả bởi đa thức bậc 2 X = c₀ + c₁·Y + c₂·Y², xác định bằng phương pháp bình phương tối thiểu trên các điểm thu được; bán kính cong R = (1 + X′²)^(3/2) / |X″| dùng để loại các đường cong phi thực tế."]));
add(B([["Biến đổi Hough ", { bold: true }], `${cite("hough")}: mỗi đường thẳng được biểu diễn bằng (ρ, θ) với ρ = x·cosθ + y·sinθ; mỗi điểm cạnh bỏ phiếu cho các (ρ, θ) đi qua nó, các ô có nhiều phiếu là các đoạn thẳng trong ảnh.`]));
add(B([["RANSAC ", { bold: true }], `${cite("ransac")}: lặp lại việc chọn ngẫu nhiên một tập con tối thiểu, ước lượng mô hình và đếm số điểm phù hợp; giữ mô hình có nhiều điểm phù hợp nhất, nhờ đó bền vững với nhiễu. Dùng để tìm điểm tụ (vanishing point) - giao điểm chung của các vạch làn trên ảnh, ứng với hàng v₀ trong công thức ${eqY}.`]));

add(H3("1.2.9. Làm mượt tín hiệu, tốc độ tiếp cận và thời gian va chạm"));
add(P("Khoảng cách đo từ từng khung hình dao động do khung bao không ổn định. Đề tài dùng các kỹ thuật xử lý tín hiệu đơn giản, phù hợp thời gian thực:"));
add(B([["Trung bình trượt hàm mũ (EMA): ", { bold: true }], "kết hợp giá trị đo mới với giá trị đã làm mượt, hệ số α càng nhỏ thì càng mượt nhưng càng trễ:"]));
EQ("d̃ₜ = α · dₜ + (1 − α) · d̃ₜ₋₁ ,   0 < α < 1");
add(B([["Tốc độ tiếp cận: ", { bold: true }], "độ dốc của đường hồi quy tuyến tính khoảng cách theo thời gian trong một cửa sổ ngắn (khoảng 1 giây), đổi dấu để dương khi hai xe đang tiến lại gần:"]));
EQ("v_tc = − Σ (tᵢ − t̄)(dᵢ − d̄) / Σ (tᵢ − t̄)²");
add(B([["Thời gian còn lại trước va chạm (TTC) ", { bold: true }], `${cite("hayward")}: thời gian để hai xe chạm nhau nếu giữ nguyên tốc độ tương đối hiện tại; chỉ có nghĩa khi v_tc > 0:`]));
const eqTTC = EQ("TTC = d / v_tc");
add(P(`TTC bổ sung cho ngưỡng khoảng cách: một xe còn cách khá xa nhưng đang giảm tốc mạnh (v_tc lớn) vẫn có TTC nhỏ và cần cảnh báo sớm. Các hệ thống FCW thường cảnh báo khi TTC xuống dưới khoảng 2-4 giây.`));

add(H3("1.2.10. Mô hình ngôn ngữ lớn và trợ lý hội thoại"));
add(P(`Mô hình ngôn ngữ lớn (LLM) là mạng nơ-ron dựa trên kiến trúc Transformer ${cite("transformer")}, được huấn luyện trên lượng văn bản rất lớn để dự đoán từ (token) tiếp theo; nhờ đó có khả năng hiểu và sinh văn bản tự nhiên, kể cả tiếng Việt. Ứng dụng tương tác với LLM qua API: gửi lời nhắc hệ thống (system prompt) mô tả vai trò, quy tắc và ngữ cảnh, cùng câu hỏi của người dùng; nhận lại câu trả lời. Claude ${cite("claude")} hỗ trợ yêu cầu đầu ra theo một lược đồ JSON (JSON schema) cố định, nhờ đó chương trình đọc được kết quả dưới dạng dữ liệu có cấu trúc thay vì văn bản tự do.`));
add(P("Hạn chế của LLM qua API là cần kết nối Internet, có chi phí theo lượng token và có độ trễ. Với các tác vụ có tập ý định hữu hạn (ví dụ nhận biết “trời mưa”, “sương mù”, “tôi chạy 90 km/h”), phương án thay thế là bộ luật nhận dạng từ khóa (rule-based) dùng biểu thức chính quy: chạy offline, miễn phí, phản hồi tức thì, nhưng chỉ hiểu các cách diễn đạt đã được định nghĩa trước. Với tiếng Việt cần xử lý thêm trường hợp người dùng gõ không dấu (bỏ dấu cả hai phía trước khi so khớp)."));

add(H3("1.2.11. Các phương pháp đánh giá"));
add(SUB("a) Đánh giá mô hình phát hiện đối tượng"));
add(P(`Một dự đoán được tính là đúng (TP) nếu đúng lớp và có IoU ${eqIoU} với một khung thật lớn hơn ngưỡng (thường 0,5); dự đoán thừa là FP; khung thật bị bỏ sót là FN. Từ đó:`, { keepNext: true }));
EQ("Precision = TP / (TP + FP) ;   Recall = TP / (TP + FN) ;   F1 = 2·P·R / (P + R)");
add(P(`Sắp xếp các dự đoán theo độ tin cậy giảm dần và vẽ đường Precision - Recall; độ chính xác trung bình AP là diện tích dưới đường này. mAP là trung bình AP của các lớp ${cite("voc")}:`, { keepNext: true }));
EQ("AP = ∫₀¹ p(r) dr ;   mAP = (1/N) · Σᵢ APᵢ");
add(P("mAP@0,5 tính ở ngưỡng IoU 0,5; mAP@0,5:0,95 là trung bình mAP ở 10 ngưỡng IoU từ 0,5 đến 0,95 (bước 0,05), đánh giá khắt khe hơn về độ chính xác vị trí khung bao."));
add(SUB("b) Đánh giá đo khoảng cách và hệ thống"));
table(["Đối tượng", "Chỉ số", "Cách tính / ý nghĩa"], [
  ["Đo khoảng cách", "Sai số tuyệt đối trung bình (MAE)", "MAE = (1/n) Σ |d̂ᵢ − dᵢ|, so khoảng cách ước lượng với khoảng cách thật (mốc vạch kẻ đứt, biển báo khoảng cách)"],
  ["Đo khoảng cách", "Sai số tương đối", "|d̂ − d| / d, tính theo từng dải khoảng cách (vì sai số tăng theo khoảng cách)"],
  ["Thời gian thực", "FPS, độ trễ mỗi khung", "FPS = số khung xử lý / thời gian; độ trễ = thời gian xử lý một khung (ms), xét cả trung bình và phân vị 95%"],
  ["Cảnh báo", "Báo đúng, báo nhầm, bỏ sót", "Đối chiếu các cảnh báo của hệ thống với các tình huống vi phạm thật được đánh dấu trên video kịch bản"],
], [3.0, 4.2, 8.8], "Các chỉ số đánh giá đo khoảng cách và hệ thống");

add(H3("1.2.12. Công nghệ phát triển phần mềm"));
const TAB_TECH = nextTab();
table(["Nhóm", "Công nghệ", "Đặc điểm và vai trò"], [
  ["Ngôn ngữ", "Python", "Ngôn ngữ thông dịch, hệ sinh thái AI / thị giác máy tính đầy đủ, phát triển nhanh"],
  ["Học sâu", `PyTorch + CUDA ${cite("pytorch")}`, "Thư viện học sâu, tính toán tensor và lan truyền ngược tự động, tăng tốc bằng GPU NVIDIA"],
  ["Phát hiện đối tượng", `Ultralytics ${cite("yolo11")}`, "Huấn luyện, đánh giá, suy luận YOLOv11; tích hợp sẵn ByteTrack"],
  ["Thị giác máy tính", `OpenCV ${cite("opencv")}, NumPy`, "Đọc video / camera, homography, biến đổi phối cảnh, phép toán hình thái, Hough; tính toán ma trận"],
  ["Giao diện", "PySide6 (Qt 6)", "Thư viện giao diện desktop, mô hình tín hiệu - khe (signal-slot), hỗ trợ đa luồng, hiển thị tiếng Việt"],
  ["Âm thanh", "pygame", "Phát âm thanh cảnh báo"],
  ["Cơ sở dữ liệu", "SQLite", "CSDL quan hệ nhúng, lưu trong một file, không cần máy chủ, hỗ trợ giao dịch và ràng buộc toàn vẹn"],
  ["Trợ lý AI", `Anthropic Claude API ${cite("claude")}`, "Dịch vụ LLM, đầu ra có cấu trúc JSON"],
  ["Dữ liệu", "Roboflow", "Nền tảng gán nhãn, quản lý phiên bản và xuất dataset định dạng YOLO"],
  ["Mô hình hóa, thiết kế", "BPMN 2.0, UML, Figma", "Mô hình hóa quy trình nghiệp vụ, phân tích thiết kế hướng đối tượng, thiết kế giao diện"],
  ["Đóng gói", "PyInstaller", "Đóng gói ứng dụng Python cùng thư viện thành file chạy trên Windows"],
], [3.0, 4.4, 8.6], "Công nghệ sử dụng trong đề tài");
add(P("Python và hệ sinh thái PyTorch - Ultralytics - OpenCV là lựa chọn phổ biến nhất cho các bài toán thị giác máy tính dùng học sâu, cho phép huấn luyện mô hình và xây dựng ứng dụng trên cùng một ngôn ngữ. PySide6 cho giao diện desktop gốc trên Windows và vẽ được chữ tiếng Việt có dấu lên khung hình. SQLite nhúng sẵn trong Python, phù hợp phần mềm chạy độc lập trên máy tính trong xe."));

// ---------------------------------------------------------------- 1.3
add(H2("1.3. Các công trình và hệ thống liên quan"));
add(H3("1.3.1. Hệ thống cảnh báo va chạm phía trước tích hợp trên ô tô"));
add(P("Nhiều hãng xe trang bị FCW / AEB trong các gói an toàn chủ động, dùng radar, camera hoặc kết hợp cả hai. Ưu điểm là cảm biến chuyên dụng, được hiệu chỉnh tại nhà máy nên chính xác và ổn định, có thể can thiệp phanh. Hạn chế: chủ yếu có trên xe đời mới hoặc phiên bản cao cấp; không lắp thêm được cho xe đang lưu hành; ngưỡng cảnh báo do nhà sản xuất đặt sẵn, thường theo thời gian va chạm, không bám bảng khoảng cách của quy định Việt Nam và người dùng không điều chỉnh được."));
add(H3("1.3.2. Thiết bị ADAS gắn thêm và camera hành trình có cảnh báo"));
add(P("Trên thị trường có các thiết bị ADAS gắn thêm và camera hành trình tích hợp chức năng cảnh báo va chạm phía trước, cảnh báo lệch làn. Ưu điểm là lắp được cho xe cũ, giá thành hợp lý. Hạn chế: thuật toán đóng, ngưỡng cố định do nhà sản xuất; người dùng khó điều chỉnh theo tốc độ, theo bảng quy định và điều kiện thời tiết; ít khi lưu nhật ký vi phạm để tra cứu lại."));
add(H3("1.3.3. Các nghiên cứu ước lượng khoảng cách bằng một camera"));
add(B([["Theo hình học mặt đường: ", { bold: true }], `Stein, Mano và Shashua ${cite("stein")} ước lượng khoảng cách tới xe phía trước từ vị trí điểm tiếp đất trên ảnh với giả định mặt đường phẳng và chiều cao camera biết trước, đồng thời chứng minh sai số khoảng cách tăng theo bình phương khoảng cách (công thức ${eqErr}). Đây là cơ sở cho cách đo bằng IPM của đề tài.`]));
add(B([["IPM cho nhận diện làn và vật cản: ", { bold: true }], `Mallot và cộng sự ${cite("mallot")} đề xuất biến đổi phối cảnh ngược; hệ thống GOLD của Bertozzi và Broggi ${cite("gold")} dùng IPM để phát hiện làn đường và vật cản theo thời gian thực trên xe thử nghiệm.`]));
add(B([["Theo kích thước vật thể: ", { bold: true }], "nhiều nghiên cứu kết hợp YOLO với mô hình camera lỗ kim, suy ra khoảng cách từ chiều cao hoặc bề rộng khung bao và kích thước thật giả định của xe (Y ≈ f · H_thật / h_ảnh). Cách này đơn giản, không cần căn chỉnh, nhưng sai số lớn vì kích thước thật của các xe khác nhau (xe con cao khoảng 1,5 m, xe khách trên 3 m) và khung bao dao động."]));
add(H3("1.3.4. Nhận xét và so sánh các giải pháp"));
const TAB_CMP = nextTab();
table(["Giải pháp", "Nguyên lý", "Ưu điểm", "Hạn chế"], [
  ["Tài xế tự ước lượng", "Quan sát bằng mắt, quy tắc 2-3 giây, biển kiểm tra cự ly trên một số tuyến cao tốc",
    "Không cần thiết bị", "Chủ quan; khó ước lượng ở tốc độ cao, khi trời tối, mưa hoặc khi mệt mỏi"],
  ["FCW / AEB tích hợp trên xe", "Radar / camera chuyên dụng của hãng xe",
    "Chính xác, ổn định", "Chủ yếu có trên xe đời mới, giá cao; không lắp thêm được; ngưỡng không theo quy định Việt Nam"],
  ["Thiết bị ADAS gắn thêm", "Camera + thuật toán nhúng trong thiết bị",
    "Lắp được cho xe cũ", "Ngưỡng cố định; khó chỉnh theo quy định và điều kiện đường; ít có nhật ký vi phạm"],
  ["YOLO + kích thước xe", "Camera lỗ kim, khoảng cách từ kích thước khung bao",
    "Đơn giản, không cần căn chỉnh", "Sai số lớn vì kích thước thật của xe khác nhau"],
  [`Hình học mặt đường / IPM ${cite("mallot", "gold", "stein")}`, "Điểm tiếp đất của xe trên mặt đường phẳng",
    "Không phụ thuộc kích thước xe; đo trực tiếp bằng mét", "Cần căn chỉnh camera; giả định đường phẳng; sai số tăng theo khoảng cách"],
], [3.4, 4.2, 3.0, 5.4], "So sánh các giải pháp cảnh báo khoảng cách");
add(P("Từ so sánh trên, chưa có giải pháp phổ thông nào đồng thời: dùng camera thông thường lắp được cho mọi xe; đo khoảng cách không phụ thuộc kích thước xe; áp ngưỡng theo bảng khoảng cách của Thông tư 31 có điều chỉnh theo điều kiện đường; lưu nhật ký vi phạm để tra cứu. Đề tài kết hợp phát hiện xe bằng YOLOv11, bám vết bằng ByteTrack và đo khoảng cách bằng IPM để đáp ứng các yêu cầu này."));

// ---------------------------------------------------------------- 1.4
add(H2("1.4. Định hướng giải quyết"));
add(H3("1.4.1. Định hướng tổng thể"));
add(P("Hệ thống được định hướng như một chuỗi xử lý ảnh theo thời gian thực: mỗi khung hình từ camera hành trình lần lượt đi qua các bước nhận diện xe, ước lượng khoảng cách, đánh giá rủi ro và hiển thị cảnh báo. Khoảng cách được đo trên mặt phẳng đường bằng IPM nên không phụ thuộc loại xe. Ngưỡng cảnh báo bám theo Thông tư 31 và được điều chỉnh theo điều kiện đường; tài xế có thể nhờ Trợ lý AI gợi ý ngưỡng bằng câu mô tả tiếng Việt. Mọi lần vi phạm được ghi lại kèm ảnh để tra cứu sau hành trình."));

add(H3("1.4.2. Định hướng kiến trúc và công nghệ"));
add(P(`Theo yêu cầu của đề cương, kiến trúc gồm 5 tầng nối tiếp: Video Stream → YOLOv11 Detection → IPM Distance Calculation → Alert Engine → GUI (Hình ${nextFig()}, Bảng ${chap}.${tabNo + 1}). Cơ sở dữ liệu cung cấp thông số camera, cấu hình ngưỡng và lưu nhật ký vi phạm; Trợ lý AI nằm ngoài vòng xử lý khung hình, chỉ thay đổi cấu hình ngưỡng. Phần mềm là ứng dụng desktop dùng các công nghệ ở Bảng ${TAB_TECH}.`, { keepNext: true }));
figure(TQ("T1_kien_truc_tong_quan.png"), 15, "Kiến trúc tổng quan của hệ thống", 20);
table(["Tầng", "Nhiệm vụ", "Kỹ thuật", "Đầu ra"], [
  ["① Thu nhận dữ liệu", "Đọc khung hình từ file video, camera USB / IP hoặc ảnh; giữ nhịp thời gian thực", "OpenCV; bỏ khung khi xử lý chậm", "Khung hình + thời điểm"],
  ["② Nhận diện phương tiện", "Phát hiện, phân loại ô tô, xe tải, xe khách; theo dõi từng xe qua các khung", "YOLOv11 + ByteTrack (mục 1.2.5, 1.2.6)", "Khung bao, loại xe, mã xe"],
  ["③ Ước lượng khoảng cách", "Xác định làn xe chủ, đổi vị trí xe sang mét, tính tốc độ tiếp cận và TTC", "IPM, nhận diện vạch làn, EMA, hồi quy tuyến tính (mục 1.2.7 - 1.2.9)", "Khoảng cách (m), cùng làn hay không, TTC"],
  ["④ Đánh giá và cảnh báo", "Tính ngưỡng; phân loại rủi ro; phát âm thanh; ghi nhật ký", "Bảng Thông tư 31 × hệ số điều kiện; chống báo nhầm (mục 1.4.5)", "Mức an toàn / cảnh báo / nguy hiểm"],
  ["⑤ Giao diện", "Hiển thị video có khung màu, khoảng cách, ảnh nhìn từ trên xuống; cấu hình; tra cứu nhật ký", "PySide6", "Màn hình giám sát, cảnh báo"],
], [3.0, 5.2, 4.6, 3.2], "Năm tầng của kiến trúc tổng quan");
add(P(`Luồng xử lý một khung hình trong quá trình giám sát được mô tả ở Hình ${nextFig()}.`, { keepNext: true }));
figure(TQ("T2_luong_xu_ly_khung_hinh.png"), 15, "Luồng xử lý một khung hình", 21);

add(H3("1.4.3. Định hướng nhận diện phương tiện và chuẩn bị dữ liệu"));
add(P(`Dùng YOLOv11n khởi tạo từ trọng số COCO, huấn luyện tinh chỉnh trên tập dữ liệu phương tiện; dùng ByteTrack để bám vết. Cấu hình huấn luyện dự kiến ở Bảng ${nextTab()}; quá trình huấn luyện và kết quả đánh giá trình bày ở Chương 4.`));
table(["Tham số", "Giá trị dự kiến"], [
  ["Mô hình gốc", "YOLOv11n huấn luyện sẵn trên COCO"],
  ["Epoch / batch / kích thước ảnh", "50 / 16 / 640 × 640"],
  ["Tăng cường dữ liệu", "Mosaic, lật ngang, thay đổi độ sáng, màu sắc"],
  ["Chỉ số đánh giá", "Precision, Recall, mAP@0,5, mAP@0,5:0,95 theo từng lớp (mục 1.2.11)"],
  ["Mục tiêu", "mAP@0,5 ≥ 0,80 trên tập kiểm thử độc lập"],
], [5.5, 10.5], "Cấu hình huấn luyện YOLOv11 dự kiến");
add(P(`Tập dữ liệu ban đầu được lấy từ Roboflow (dự án distance-estimation-model, phiên bản 1, giấy phép CC BY 4.0): 13.003 ảnh khung hình camera hành trình, 72.653 đối tượng được gán nhãn thuộc 5 lớp, đã ở định dạng YOLO (mỗi ảnh một file nhãn, mỗi dòng “lớp x_tâm y_tâm rộng cao” chuẩn hóa về 0..1), chia train / valid / test theo tỷ lệ 70 / 20 / 10 (Bảng ${nextTab()}). Ô tô, xe tải, xe khách là 3 lớp mục tiêu; Jeepney (xe khách cỡ nhỏ) được cảnh báo cùng nhóm xe khách; xe máy không theo dõi vì không được lưu thông trên cao tốc.`));
table(["Lớp", "Train", "Valid", "Test", "Tổng", "Tỷ lệ"], [
  ["Ô tô (car)", "29.244", "8.318", "4.078", "41.640", "57,3%"],
  ["Xe máy (motorcycle)", "15.697", "4.669", "2.195", "22.561", "31,1%"],
  ["Xe tải (truck)", "3.841", "1.063", "588", "5.492", "7,6%"],
  ["Jeepney", "1.625", "518", "219", "2.362", "3,3%"],
  ["Xe khách (bus)", "419", "126", "53", "598", "0,8%"],
  [[["Tổng số đối tượng", { bold: true }]], "50.826", "14.694", "7.133", "72.653", "100%"],
  [[["Số ảnh", { bold: true }]], "9.102", "2.601", "1.300", "13.003", ""],
], [4.4, 2.3, 2.3, 2.3, 2.4, 2.3], "Thống kê đối tượng theo lớp trong tập dữ liệu ban đầu", { center: [1, 2, 3, 4, 5] });
figure(HINH("dataset_mau.jpg"), 15, "Ảnh mẫu trong tập dữ liệu kèm nhãn");
add(P("Đánh giá ban đầu cho thấy tập dữ liệu cần được bổ sung trước khi huấn luyện:", { keepNext: true }));
newList();
add(N("gần như toàn bộ ảnh là cảnh đường phố đô thị ban đêm, trích từ 2 video, khác bối cảnh cao tốc Việt Nam ban ngày;"));
add(N("các khung liên tiếp của cùng video được chia ngẫu nhiên nên khoảng 92% ảnh test có khung kề cận nằm trong tập train, kết quả đánh giá trên tập test sẽ cao hơn thực tế;"));
add(N("xe khách chỉ chiếm 0,8% số đối tượng (mất cân bằng lớp); lớp Jeepney là loại xe đặc trưng của Philippines."));
add(P("Hướng xử lý: bổ sung ảnh trích từ video camera hành trình trên cao tốc Việt Nam ban ngày và gán nhãn; chia lại tập theo đoạn video liền (mỗi đoạn nằm trọn trong một tập); dùng riêng bộ video cao tốc làm tập kiểm thử độc lập; báo cáo mAP theo từng lớp; chuẩn bị video kiểm thử theo 3 kịch bản ban ngày, ban đêm, thời tiết xấu."));

add(H3("1.4.4. Định hướng đo khoảng cách và xác định làn xe chủ"));
add(B(`Căn chỉnh camera cho từng nguồn video bằng 4 điểm trên 2 vạch làn xe chủ, ứng với hình chữ nhật bề rộng W = 3,75 m, chiều dài L, cách đầu xe d₀ → tính H theo ${eqIPM}, phân rã K, R; lưu thông số theo nguồn.`));
add(B("Điểm đo của mỗi xe là trung điểm cạnh dưới khung bao; điểm ở trên đường chân trời hoặc xa hơn tầm đo tin cậy (khoảng 150 m, theo Bảng sai số ở mục 1.2.7) chỉ hiển thị là “xa”, không cảnh báo."));
add(B("Xác định làn xe chủ trên ảnh nhìn từ trên xuống bằng top-hat, cửa sổ trượt và đa thức bậc 2 (mục 1.2.8); chỉ xác nhận làn khi thấy đủ hai vạch với bề rộng hợp lý trong vài khung liên tiếp; khi không thấy vạch (ban đêm, vạch mờ) dùng hành lang cố định quanh trục xe. Xe phía trước là xe cùng làn gần nhất."));
add(B(`Làm mượt khoảng cách bằng EMA, tính tốc độ tiếp cận bằng hồi quy tuyến tính trong khoảng 1 giây và TTC theo ${eqTTC}.`));
add(B([["Hướng mở rộng - tự động căn chỉnh: ", { bold: true }], `từ công thức ${eqY}, nếu biết v₀ và tích f·h thì đo được khoảng cách mà không cần chấm điểm. Điểm tụ tìm bằng Hough + RANSAC trên vạch làn; chiều cao camera suy từ bề rộng làn 3,75 m trên ảnh; tích f·h suy từ độ dịch chuyển của các vạch kẻ đứt giữa hai khung khi biết tốc độ xe chủ.`]));

add(H3("1.4.5. Định hướng ngưỡng an toàn và cảnh báo"));
add(P(`Ngưỡng tính theo tốc độ xe chủ V, dựa trên bảng quy định (Bảng ${TAB_LEGAL}) và quy tắc 2 giây cho vùng dưới 60 km/h; d_min là khoảng cách luôn coi là nguy hiểm (ví dụ 5 m):`, { keepNext: true }));
EQ("d_cs = bảng Thông tư 31 (V ≥ 60 km/h)  hoặc  V · 2 s (V < 60 km/h)");
EQ("d_cb = max(d_cs, d_min) × k_đk ;   d_nh = max(d_min, 0,5 · d_cb)");
add(P(`trong đó d_cb là ngưỡng cảnh báo, d_nh là ngưỡng nguy hiểm, k_đk là hệ số điều kiện đường, ước tính theo tỷ số quãng phanh ở công thức ${eqStop}: k_đk ≈ 0,7 / μ, nhân thêm các yếu tố khác (ban đêm, xe chở nặng, tài xế mệt mỏi), tối đa ×3 (Bảng ${nextTab()}).`));
table(["Điều kiện", "Hệ số k_đk", "μ", "TTC cảnh báo / nguy hiểm (s)"], [
  ["Khô ráo, tầm nhìn tốt", "1,0", "0,70", "4 / 2"],
  ["Mặt đường ướt, mưa nhỏ", "1,4", "0,50", "5 / 2,5"],
  ["Mưa to, đọng nước", "2,0", "0,35", "6 / 3"],
  ["Sương mù, tầm nhìn hạn chế", "1,5", "0,60", "5,5 / 3"],
  ["Trơn trượt (dầu, bùn, sỏi)", "2,5", "0,25", "6 / 3"],
], [6.0, 2.6, 2.2, 5.2], "Hệ số điều kiện đường đề xuất", { center: [1, 2, 3] });
add(P("Ví dụ: V = 90 km/h, mưa to → 70 m × 2,0: cảnh báo khi khoảng cách < 140 m, nguy hiểm khi < 70 m. Khi tầm nhìn hạn chế, hệ thống khuyến nghị thêm tốc độ tối đa sao cho quãng đường dừng xe không vượt quá tầm nhìn."));
add(B([["Phân loại rủi ro: ", { bold: true }], "nguy hiểm khi khoảng cách < d_nh hoặc TTC < TTC nguy hiểm; cảnh báo khi khoảng cách < d_cb hoặc TTC < TTC cảnh báo; còn lại là an toàn."]));
add(B([["Chống báo nhầm: ", { bold: true }], `chỉ nâng mức khi điều kiện đúng liên tục ít nhất 0,1 s (và ít nhất 2 khung; tương đương 3 khung ở 30 khung/giây nhưng tính theo thời gian, để máy yếu xử lý 10 khung/giây vẫn báo kịp như máy mạnh) và giữ mức một thời gian tối thiểu trước khi hạ (Hình ${nextFig()}), tránh âm báo bật tắt liên tục do nhận diện chập chờn.`]));
add(B([["Nhật ký theo đợt: ", { bold: true }], "mỗi đợt vi phạm liên tục với cùng một xe được ghi thành một bản ghi (khoảng cách nhỏ nhất, TTC nhỏ nhất, thời lượng, ảnh bằng chứng), không ghi từng khung."]));
figure(TQ("T3_trang_thai_muc_canh_bao.png"), 16, "Trạng thái mức cảnh báo và cơ chế chống báo nhầm");

add(H3("1.4.6. Định hướng Trợ lý AI gợi ý ngưỡng"));
add(P("Tài xế mô tả tình huống bằng tiếng Việt (ví dụ “đang mưa to, tôi chạy 90 km/h”) hoặc chọn nhanh một điều kiện; trợ lý trả về cấu hình ngưỡng mới (hệ số điều kiện, μ, TTC, tầm nhìn) và tốc độ xe chủ nếu tài xế có nêu. Trợ lý có 2 chế độ, dựa trên lý thuyết ở mục 1.2.10:"));
add(B([["Chế độ offline (mặc định): ", { bold: true }], "nhận dạng từ khóa / cụm từ tiếng Việt bằng biểu thức chính quy, chấp nhận cả khi gõ không dấu, tra bảng điều kiện đường; miễn phí, không cần Internet."]));
add(B([["Chế độ Claude (tùy chọn): ", { bold: true }], "gọi Claude API với lời nhắc hệ thống chứa bảng điều kiện đường và quy tắc an toàn, yêu cầu trả lời theo lược đồ JSON cố định; khi lỗi mạng hoặc thiếu khóa API tự chuyển về chế độ offline."]));
add(B([["Ràng buộc an toàn: ", { bold: true }], "mọi giá trị trả về đều bị giới hạn trong phạm vi cho phép; hệ số điều kiện không bao giờ nhỏ hơn 1, tức ngưỡng không bao giờ thấp hơn quy định."]));

add(H3("1.4.7. Phạm vi triển khai và kết quả dự kiến"));
table(["Yêu cầu của đề cương", "Kết quả dự kiến", "Trình bày tại"], [
  ["Mô tả quy trình nghiệp vụ (BPMN)", "Sơ đồ BPMN quy trình tổng quát, chuẩn bị giám sát, giám sát và cảnh báo; biểu mẫu dữ liệu", "Chương 2"],
  ["Yêu cầu chức năng / phi chức năng", "Bảng yêu cầu chức năng, bảng yêu cầu phi chức năng có chỉ tiêu đo", "Chương 2"],
  ["Sơ đồ use case và đặc tả", "Sơ đồ UC tổng quát 5 UC, các sơ đồ phân rã, bảng đặc tả", "Chương 2"],
  ["Thiết kế cấu trúc dữ liệu, kiến trúc", "Sơ đồ lớp, ERD, kiến trúc Video Stream → YOLOv11 → IPM → Alert Engine → GUI", "Chương 3"],
  ["Thiết kế giao diện", "Mockup màn hình giám sát, căn chỉnh camera, nhật ký", "Chương 3"],
  ["Thi công phần mềm", "CSDL; mô hình YOLOv11 đã huấn luyện; module IPM, cảnh báo, Trợ lý AI; giao diện; 5 UC", "Chương 4"],
  ["Triển khai thử nghiệm", "Bản đóng gói chạy trên Windows; dataset và bộ video kịch bản ngày / đêm / thời tiết xấu; kết quả kiểm thử", "Chương 4"],
], [4.6, 8.6, 2.8], "Kết quả dự kiến theo yêu cầu của đề cương", { center: [2] });

add(H2("1.5. Kết luận chương 1"));
add(P("Chương 1 đã trình bày tổng quan đề tài, các cơ sở lý thuyết nền tảng gồm quy định khoảng cách an toàn và quãng đường dừng xe, học sâu và mô hình phát hiện đối tượng YOLOv11, thuật toán bám vết ByteTrack, mô hình camera và biến đổi phối cảnh ngược, kỹ thuật xử lý ảnh nhận diện làn, các phương pháp làm mượt và tính thời gian va chạm, mô hình ngôn ngữ lớn và các phương pháp đánh giá; phân tích các hệ thống và nghiên cứu liên quan; từ đó đề xuất định hướng giải quyết với kiến trúc 5 tầng. Chương 2 sẽ đi vào khảo sát chi tiết và phân tích yêu cầu của hệ thống."));

// ================================================================ CHƯƠNG 2 (khung)
chapter(2, "KHẢO SÁT VÀ PHÂN TÍCH HỆ THỐNG");
add(NOTE("(Nội dung chương đang được hoàn thiện)"));
const skeleton = (items) => items.forEach(([h2, h3s]) => { add(H2(h2)); (h3s || []).forEach((t) => add(H3(t))); });
skeleton([
  ["2.1. Khảo sát và xác định bài toán", ["2.1.1. Bối cảnh giữ khoảng cách trên đường cao tốc", "2.1.2. Khảo sát các giải pháp cảnh báo khoảng cách hiện có", "2.1.3. Phân tích những vấn đề cần giải quyết", "2.1.4. Xác định phạm vi hệ thống"]],
  ["2.2. Khảo sát và mô hình hóa quy trình nghiệp vụ", ["2.2.1. Quy trình chuẩn bị giám sát", "2.2.2. Quy trình giám sát và cảnh báo", "2.2.3. Quy trình tra cứu nhật ký cảnh báo", "2.2.4. Sơ đồ BPMN quy trình tổng quát", "2.2.5. Sơ đồ BPMN quy trình chuẩn bị giám sát", "2.2.6. Sơ đồ BPMN quy trình giám sát và cảnh báo", "2.2.7. Biểu mẫu dữ liệu"]],
  ["2.3. Phân tích yêu cầu chức năng", ["2.3.1. Yêu cầu quản lý nguồn video / camera", "2.3.2. Yêu cầu căn chỉnh camera", "2.3.3. Yêu cầu nhận diện phương tiện và đo khoảng cách", "2.3.4. Yêu cầu cảnh báo và cấu hình ngưỡng", "2.3.5. Yêu cầu nhật ký và cấu hình", "2.3.6. Bảng tổng hợp yêu cầu chức năng"]],
  ["2.4. Phân tích yêu cầu phi chức năng", ["2.4.1. Yêu cầu về hiệu năng và thời gian phản hồi", "2.4.2. Yêu cầu về độ chính xác và độ tin cậy của module AI", "2.4.3. Yêu cầu về tính ổn định và lưu trữ", "2.4.4. Yêu cầu về tính dễ sử dụng", "2.4.5. Bảng tổng hợp yêu cầu phi chức năng"]],
  ["2.5. Xác định tác nhân và Use Case", ["2.5.1. Các tác nhân của hệ thống", "2.5.2. Sơ đồ Use Case tổng quát", "2.5.3. Phân rã UC01 - Quản lý nguồn video/camera", "2.5.4. Phân rã UC02 - Cấu hình thông số IPM", "2.5.5. Phân rã UC03 - Cấu hình ngưỡng cảnh báo", "2.5.6. Phân rã UC04 - Giám sát realtime & cảnh báo", "2.5.7. Phân rã UC05 - Quản lý nhật ký cảnh báo"]],
  ["2.6. Đặc tả Use Case", ["2.6.1. Quy ước và cấu trúc bảng đặc tả Use Case", "2.6.2. Đặc tả UC01 - UC05", "2.6.3. Tổng hợp quan hệ giữa Use Case và yêu cầu chức năng"]],
  ["2.7. Kết luận chương 2"],
]);

// ================================================================ CHƯƠNG 3 (khung)
chapter(3, "THIẾT KẾ HỆ THỐNG");
add(NOTE("(Nội dung chương đang được hoàn thiện)"));
skeleton([
  ["3.1. Thiết kế kiến trúc phần mềm", ["3.1.1. Kiến trúc tổng thể", "3.1.2. Kiến trúc luồng xử lý video", "3.1.3. Sơ đồ gói và thành phần", "3.1.4. Sơ đồ triển khai"]],
  ["3.2. Thiết kế chi tiết chức năng", ["3.2.1. Sơ đồ hoạt động các use case", "3.2.2. Sơ đồ tuần tự các use case"]],
  ["3.3. Thiết kế lớp", ["3.3.1. Sơ đồ lớp tổng quát", "3.3.2. Lớp thực thể", "3.3.3. Lớp điều khiển", "3.3.4. Lớp giao diện"]],
  ["3.4. Thiết kế cơ sở dữ liệu", ["3.4.1. Sơ đồ thực thể - liên kết (ERD)", "3.4.2. Mô tả chi tiết các bảng", "3.4.3. Ràng buộc toàn vẹn dữ liệu"]],
  ["3.5. Thiết kế thuật toán", ["3.5.1. Nhận diện và bám vết phương tiện", "3.5.2. Căn chỉnh camera và tính khoảng cách IPM", "3.5.3. Nhận diện làn xe chủ", "3.5.4. Tính ngưỡng, phân loại rủi ro và chống báo nhầm", "3.5.5. Trợ lý AI gợi ý ngưỡng"]],
  ["3.6. Thiết kế giao diện", ["3.6.1. Màn hình giám sát", "3.6.2. Màn hình căn chỉnh camera", "3.6.3. Màn hình cài đặt ngưỡng", "3.6.4. Màn hình nhật ký cảnh báo"]],
  ["3.7. Kết luận chương 3"],
]);

// ================================================================ CHƯƠNG 4 (khung)
chapter(4, "TRIỂN KHAI");
add(NOTE("(Nội dung chương đang được hoàn thiện)"));
skeleton([
  ["4.1. Môi trường cài đặt và công cụ", ["4.1.1. Phần cứng", "4.1.2. Phần mềm và thư viện"]],
  ["4.2. Chuẩn bị dữ liệu và huấn luyện mô hình", ["4.2.1. Thu thập và gán nhãn dữ liệu", "4.2.2. Huấn luyện mô hình YOLOv11", "4.2.3. Đánh giá mô hình"]],
  ["4.3. Cài đặt các chức năng", ["4.3.1. Cài đặt cơ sở dữ liệu", "4.3.2. Cài đặt các module xử lý", "4.3.3. Cài đặt giao diện và các use case"]],
  ["4.4. Kiểm thử", ["4.4.1. Kịch bản và dữ liệu kiểm thử", "4.4.2. Kiểm thử yêu cầu chức năng", "4.4.3. Kiểm thử yêu cầu phi chức năng", "4.4.4. Đánh giá độ chính xác đo khoảng cách"]],
  ["4.5. Đóng gói và cài đặt", []],
  ["4.6. Hướng dẫn sử dụng", []],
  ["4.7. Kết luận chương 4"],
]);

// ================================================================ PHẦN CUỐI
chap = 0;
add(H1("KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN"));
add(NOTE("(Nội dung đang được hoàn thiện)"));
add(H2("1. Kết quả đạt được"));
add(H2("2. Hạn chế"));
add(H2("3. Hướng phát triển"));

add(H1("TÀI LIỆU THAM KHẢO"));
refOrder.forEach((k, i) => add(new Paragraph({
  children: runs(`[${i + 1}] ${REFS[k]}`), alignment: AlignmentType.LEFT,
  spacing: { after: 80, line: 312 }, indent: { left: 567, hanging: 567 },
})));

add(H1("PHỤ LỤC"));
add(NOTE("(Nội dung đang được hoàn thiện)"));
add(H2("Phụ lục A. Đề cương đồ án tốt nghiệp"));
add(H2("Phụ lục B. Hướng dẫn cài đặt và sử dụng"));

// ---------------------------------------------------------------- tài liệu
const footer = new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
  children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 24 })] })] });
const size = { width: 21 * CM, height: 29.7 * CM };
const margin = { top: 2 * CM, bottom: 2 * CM, left: 3 * CM, right: 2 * CM };
const DBL = { style: BorderStyle.DOUBLE, size: 12, color: "000000", space: 24 };
const props = {
  cover: { page: { size, margin, borders: { pageBorders: { display: PageBorderDisplay.ALL_PAGES, offsetFrom: PageBorderOffsetFrom.PAGE },
    pageBorderTop: DBL, pageBorderBottom: DBL, pageBorderLeft: DBL, pageBorderRight: DBL } } },
  front: { page: { size, margin, pageNumbers: { start: 1, formatType: NumberFormat.LOWER_ROMAN } } },
  body: { page: { size, margin, pageNumbers: { start: 1, formatType: NumberFormat.DECIMAL } } },
};

const doc = new Document({
  creator: "Nguyễn Đức Thắng",
  title: "Báo cáo đồ án tốt nghiệp - Hệ thống cảnh báo khoảng cách an toàn trên cao tốc",
  styles: {
    default: { document: { run: { font: FONT, size: 26 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 28, bold: true, color: "000000" }, paragraph: { outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 26, bold: true, color: "000000" }, paragraph: { outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 26, bold: true, italics: true, color: "000000" }, paragraph: { outlineLevel: 2 } },
      { id: "TieuDePhu", name: "TieuDePhu", basedOn: "Normal", next: "Normal",
        run: { font: FONT, size: 28, bold: true, color: "000000" } },
      { id: "CaptionHinh", name: "CaptionHinh", basedOn: "Normal", next: "Normal",
        run: { font: FONT, size: 24, italics: true } },
      { id: "CaptionBang", name: "CaptionBang", basedOn: "Normal", next: "Normal",
        run: { font: FONT, size: 24 } },
      ...[1, 2, 3].map((l) => ({ id: `TOC${l}`, name: `toc ${l}`, basedOn: "Normal", next: "Normal",
        run: { font: FONT, size: 26, bold: l === 1 }, paragraph: { spacing: { after: 60, line: 300 }, indent: { left: (l - 1) * 400 } } })),
      // TOC4: danh mục hình / bảng (trường TOC 	 "CaptionHinh,4")
      { id: "TOC4", name: "toc 4", basedOn: "Normal", next: "Normal",
        run: { font: FONT, size: 26 }, paragraph: { spacing: { after: 60, line: 300 }, indent: { left: 0 } } },
    ],
  },
  numbering: { config: [
    { reference: "gach", levels: [{ level: 0, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 851, hanging: 284 } } } }] },
    { reference: "so", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1)", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 851, hanging: 340 } } } }] },
  ] },
  sections: sections.map((s) => ({
    properties: props[s.kind],
    footers: s.kind === "cover" ? undefined : { default: footer },
    children: captionsAbove(s.children),
  })),
});

Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(OUT, buf); console.log("OK", OUT, refOrder.length, "tài liệu"); });
