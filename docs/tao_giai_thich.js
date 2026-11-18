// Tạo tài liệu Word giải thích chức năng và thuật toán của dự án ADAS.
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType, ShadingType,
  AlignmentType, BorderStyle, LevelFormat, Footer, PageNumber, TableOfContents, VerticalAlign,
} = require("docx");

const OUT = process.argv[2] || "GIAI_THICH_CHUC_NANG.docx";
const FONT = "Times New Roman";
const TEXT_W = 9071;                       // A4, lề trái 3 cm, phải 2 cm
const ACCENT = "1F4E79";

// ---------------------------------------------------------------- tiện ích
// Đánh dấu trong chuỗi: **đậm**, `mã`
function runs(text, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), ...base }));
    const s = m[0];
    if (s.startsWith("**")) out.push(new TextRun({ text: s.slice(2, -2), bold: true, ...base }));
    else out.push(new TextRun({ text: s.slice(1, -1), font: "Consolas", size: 22, ...base }));
    last = m.index + s.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), ...base }));
  return out;
}

let stepInst = 0, inSteps = false;      // mỗi danh sách bước đánh số lại từ 1
const brk = (x) => { inSteps = false; return x; };
const P = (text, opts = {}) => brk(new Paragraph({
  children: runs(text), spacing: { after: 120, line: 312 },
  alignment: /^(Mã nguồn|Thư mục)/.test(text) ? AlignmentType.LEFT : AlignmentType.JUSTIFIED, ...opts,
}));
const B = (text, level = 0) => brk(new Paragraph({
  children: runs(text), numbering: { reference: "bullets", level },
  alignment: AlignmentType.JUSTIFIED, spacing: { after: 60, line: 300 },
}));
const S = (text, level = 0) => {        // bước đánh số
  if (!inSteps) { stepInst++; inSteps = true; }
  return new Paragraph({
  children: runs(text), numbering: { reference: "steps", level, instance: stepInst },
  alignment: AlignmentType.JUSTIFIED, spacing: { after: 60, line: 300 },
  });
};
const H1 = (t) => brk(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)], pageBreakBefore: true }));
const H2 = (t) => brk(new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] }));
const H3 = (t) => brk(new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(t)] }));
const EQ = (...lines) => lines.map((l) => new Paragraph({
  alignment: AlignmentType.CENTER, spacing: { before: 60, after: 60 },
  children: [new TextRun({ text: l, font: "Cambria Math", size: 24 })],
}));
const NOTE = (text, title = "Ghi nhớ") => brk(new Paragraph({
  children: [new TextRun({ text: title + ": ", bold: true, color: ACCENT }), ...runs(text)],
  alignment: AlignmentType.JUSTIFIED,
  shading: { type: ShadingType.CLEAR, fill: "EAF1F8", color: "auto" },
  border: { left: { style: BorderStyle.SINGLE, size: 18, color: ACCENT, space: 6 } },
  spacing: { before: 120, after: 160, line: 300 }, indent: { left: 120, right: 120 },
}));

const cellBorder = { style: BorderStyle.SINGLE, size: 4, color: "A6A6A6" };
const borders = { top: cellBorder, bottom: cellBorder, left: cellBorder, right: cellBorder };
function TBL(headers, rows, widths) {
  inSteps = false;
  const total = widths.reduce((a, b) => a + b, 0);
  const mk = (txt, w, head) => new TableCell({
    borders, width: { size: w, type: WidthType.DXA }, verticalAlign: VerticalAlign.CENTER,
    shading: head ? { type: ShadingType.CLEAR, fill: "D9E2F3", color: "auto" } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({ children: runs(String(txt), head ? { bold: true } : {}), spacing: { after: 0 } })],
  });
  return [new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: widths,
    rows: [new TableRow({ tableHeader: true, children: headers.map((h, i) => mk(h, widths[i], true)) }),
      ...rows.map((r) => new TableRow({ children: r.map((c, i) => mk(c, widths[i], false)) }))],
  }), new Paragraph({ spacing: { after: 120 }, children: [] })];
}
const CAP = (t) => new Paragraph({
  alignment: AlignmentType.CENTER, spacing: { before: 60, after: 60 },
  children: [new TextRun({ text: t, italics: true, size: 24 })],
});


// Ma trận: bảng có viền trái/phải làm dấu ngoặc
const NONE = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const BRK = { style: BorderStyle.SINGLE, size: 12, color: "000000" };
const mathCell = (txt, w, b = {}, align = AlignmentType.CENTER) => new TableCell({
  width: { size: w, type: WidthType.DXA }, verticalAlign: VerticalAlign.CENTER,
  borders: { top: NONE, bottom: NONE, left: b.left || NONE, right: b.right || NONE },
  margins: { left: 80, right: 80 },
  children: [new Paragraph({ alignment: align, spacing: { after: 0 },
    children: [new TextRun({ text: txt, font: "Cambria Math", size: 24 })] })],
});
function MAT(label, rows, colW = 1300) {
  inSteps = false;
  const n = rows[0].length, labW = 1600;
  const widths = [labW, ...Array(n).fill(colW)];
  return [new Table({
    alignment: AlignmentType.CENTER, width: { size: labW + n * colW, type: WidthType.DXA }, columnWidths: widths,
    borders: { top: NONE, bottom: NONE, left: NONE, right: NONE, insideHorizontal: NONE, insideVertical: NONE },
    rows: rows.map((r, i) => new TableRow({ children: [
      mathCell(i === Math.floor(rows.length / 2) ? label : "", labW, {}, AlignmentType.RIGHT),
      ...r.map((c, j) => mathCell(c, colW, { left: j === 0 ? BRK : undefined, right: j === n - 1 ? BRK : undefined })),
    ] })),
  }), new Paragraph({ spacing: { after: 80 }, children: [] })];
}
// Khối công thức canh thẳng: [công thức, chú thích]
function EQN(lines) {
  inSteps = false;
  const w1 = 5000, w2 = 3800;
  return [new Table({
    alignment: AlignmentType.CENTER, width: { size: w1 + w2, type: WidthType.DXA }, columnWidths: [w1, w2],
    borders: { top: NONE, bottom: NONE, left: NONE, right: NONE, insideHorizontal: NONE, insideVertical: NONE },
    rows: lines.map(([eq, note]) => new TableRow({ children: [
      mathCell(eq, w1, {}, AlignmentType.LEFT),
      new TableCell({ width: { size: w2, type: WidthType.DXA }, borders: { top: NONE, bottom: NONE, left: NONE, right: NONE },
        children: [new Paragraph({ spacing: { after: 0 }, children: [new TextRun({ text: note || "", italics: true, size: 24 })] })] }),
    ] })),
  }), new Paragraph({ spacing: { after: 80 }, children: [] })];
}

// ---------------------------------------------------------------- nội dung
const body = [];
const add = (...xs) => xs.forEach((x) => (Array.isArray(x) ? body.push(...x) : body.push(x)));

// ===== Trang bìa
add(
  new Paragraph({ spacing: { before: 2400 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "TÀI LIỆU GIẢI THÍCH", bold: true, size: 36, color: ACCENT })] }),
  new Paragraph({ spacing: { before: 240, after: 240 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "CHỨC NĂNG VÀ THUẬT TOÁN CỦA HỆ THỐNG ADAS", bold: true, size: 32 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 1200 },
    children: [new TextRun({ text: "Cảnh báo khoảng cách an toàn trên đường cao tốc bằng YOLOv11 và IPM", italics: true, size: 28 })] }),
  P("Tài liệu này giải thích từng chức năng của ứng dụng (bản máy tính và bản Android): chức năng đó làm gì, dùng thuật toán nào, các bước tính toán cụ thể và vì sao lại chọn cách làm đó. Các con số ví dụ được tính trực tiếp từ mã nguồn của dự án với cấu hình mặc định.", { alignment: AlignmentType.CENTER }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 1200 },
    children: [new TextRun({ text: "Ngày 27/10/2026", size: 26 })] }),
);

// ===== Mục lục
add(
  new Paragraph({ pageBreakBefore: true, alignment: AlignmentType.CENTER, spacing: { after: 240 },
    children: [new TextRun({ text: "MỤC LỤC", bold: true, size: 30 })] }),
  new TableOfContents("Mục lục", { hyperlink: true, headingStyleRange: "1-2" }),
);

// ===== 1. Tổng quan
add(
  H1("1. Tổng quan hệ thống"),
  H2("1.1. Bài toán"),
  P("Trên cao tốc, tai nạn đâm từ phía sau thường do người lái giữ khoảng cách quá ngắn so với tốc độ. Hệ thống dùng một camera đặt trước xe để: (1) tìm các xe phía trước, (2) đo khoảng cách thật (mét) tới từng xe, (3) so với ngưỡng an toàn phụ thuộc tốc độ và điều kiện đường, (4) cảnh báo bằng màu và âm thanh khi đi quá gần."),
  P("Hệ thống gồm hai ứng dụng dùng chung thuật toán:"),
  B("**Bản máy tính** (Python + PySide6): thư mục `adas/` chứa toàn bộ thuật toán, không phụ thuộc giao diện; thư mục `gui/` là giao diện."),
  B("**Bản Android** (Kotlin + Jetpack Compose, thư mục `mobile/android`): chuyển 1:1 các thuật toán sang Kotlin, có bộ kiểm thử so kết quả với bản Python."),
  H2("1.2. Luồng xử lý một khung hình"),
  P("Mỗi khung hình đi qua 5 tầng theo sơ đồ kiến trúc của đồ án. Hàm điều phối là `ADASPipeline.process` trong `adas/pipeline.py`; tầng đọc video và vẽ giao diện do luồng nền `gui/worker.py` thực hiện."),
  ...TBL(["Tầng", "Mô-đun", "Đầu vào → Đầu ra"], [
    ["1. Video Stream", "adas/stream", "File video / camera / RTSP / ảnh → khung hình BGR + thời điểm t"],
    ["2. Phát hiện xe", "adas/detection", "Khung hình → danh sách hộp bao xe (bbox), lớp xe, mã track"],
    ["3. Đo khoảng cách", "adas/distance", "Hộp bao → khoảng cách (m), lệch ngang (m), tốc độ tiếp cận, TTC; làn xe; tốc độ xe mình"],
    ["4. Cảnh báo", "adas/alert", "Khoảng cách + tốc độ + điều kiện → ngưỡng → mức an toàn / cảnh báo / nguy hiểm (đã chống nhiễu) + âm thanh"],
    ["5. Giao diện", "gui/", "Kết quả → video có lớp phủ, ảnh nhìn từ trên xuống (BEV), thẻ trạng thái, nhật ký vi phạm"],
  ], [1900, 1800, 5371]),
  P("Song song với vòng xử lý khung hình còn có hai chức năng không chạy mỗi khung: **Trợ lý AI** (đổi bộ tham số ngưỡng theo lời mô tả điều kiện đường) và **Cơ sở dữ liệu** (lưu cấu hình, căn chỉnh camera, phiên giám sát, vi phạm)."),
  H2("1.3. Các đại lượng chính"),
  ...TBL(["Ký hiệu", "Ý nghĩa", "Đơn vị"], [
    ["(u, v)", "Tọa độ điểm ảnh: u theo chiều ngang (cột), v theo chiều dọc (hàng, tăng dần xuống dưới)", "pixel"],
    ["(X, Y)", "Tọa độ trên mặt đường: X lệch ngang so với trục xe (âm = trái), Y khoảng cách phía trước tính từ đầu xe", "m"],
    ["H", "Ma trận đồng nhất (homography) 3×3 đổi pixel → mét trên mặt đường", "–"],
    ["d, d′, d″", "Khoảng cách tới xe trước, tốc độ thay đổi khoảng cách, gia tốc tương đối", "m, m/s, m/s²"],
    ["TTC", "Time-to-collision: thời gian còn lại trước va chạm nếu giữ nguyên tốc độ tiếp cận", "s"],
    ["V", "Tốc độ xe mình (đo từ video, GPS trên Android, hoặc nhập tay)", "km/h"],
  ], [1400, 6371, 1300]),
);

// ===== 2. Nguồn video
add(
  H1("2. Nguồn video (Video Stream)"),
  P("Mã nguồn: `adas/stream/sources.py`. Ứng dụng nhận bốn loại nguồn: file video, webcam USB (nhập số 0, 1…), camera IP qua RTSP, và ảnh tĩnh. Mỗi nguồn trả về khung hình kèm thời điểm t (giây), vì mọi thuật toán phía sau (Kalman, tốc độ, chống nhiễu) đều tính theo thời gian thực chứ không theo số khung."),
  H3("Phát video theo thời gian thực"),
  P("`VideoFileSource` không đọc video nhanh nhất có thể mà bám theo đồng hồ: khung thứ k được hiển thị ở thời điểm k/fps. Nếu xử lý chậm hơn tốc độ video thì bỏ qua các khung đã trễ (drop frame), giống như một camera thật sẽ không chờ ứng dụng. Khi tạm dừng rồi chạy tiếp, `restart_clock()` đặt lại đồng hồ để không bị nhảy cóc."),
  H3("Camera trực tiếp"),
  P("`CameraSource` dùng một luồng riêng liên tục đọc ảnh từ camera và chỉ giữ ảnh mới nhất. Nhờ vậy khi vòng xử lý bị chậm, nó luôn lấy được khung hiện tại thay vì xử lý một hàng đợi ảnh cũ (độ trễ không tích lũy)."),
  H3("Đọc ảnh với đường dẫn có dấu"),
  P("Thư mục dự án có ký tự tiếng Việt (\"Đồ án\") nên `cv2.imread` thất bại. Ứng dụng đọc file bằng `np.fromfile` rồi giải mã bằng `cv2.imdecode`."),
  P("Mỗi nguồn được đăng ký vào bảng `video_sources` (đường dẫn được chuẩn hóa thành đường dẫn tuyệt đối), để lần sau mở lại nguồn đó thì tự nạp lại căn chỉnh camera tương ứng."),
);

// ===== 3. Phát hiện xe
add(
  H1("3. Phát hiện và bám vết phương tiện"),
  H2("3.1. YOLOv11 – phát hiện xe"),
  P("Mã nguồn: `adas/detection/detector.py`. YOLO (You Only Look Once) là mạng nơ-ron tích chập một giai đoạn: chỉ cần chạy mạng một lần trên cả ảnh để có tất cả hộp bao và lớp đối tượng."),
  S("Ảnh được thu/phóng giữ tỉ lệ về kích thước 640×640 (thêm viền – letterbox)."),
  S("Mạng xương sống (backbone) trích xuất đặc trưng ở nhiều độ phân giải; phần cổ (neck, kiểu FPN/PAN) trộn đặc trưng để phát hiện được cả xe to ở gần và xe nhỏ ở xa."),
  S("Phần đầu (head) dự đoán cho mỗi vị trí: tọa độ hộp, độ tin cậy, xác suất từng lớp."),
  S("Bỏ các hộp có độ tin cậy < 0,35, sau đó NMS (Non-Maximum Suppression) loại các hộp trùng nhau có IoU > 0,45, chỉ giữ hộp tốt nhất."),
  P("Mô hình tự huấn luyện `models/best.pt` có 5 lớp: Jeepney, bus, car, motorcycle, truck (mặc định chỉ cảnh báo ô tô, xe tải, xe khách). Nếu không có file này, ứng dụng dùng `yolo11n.pt` (bộ COCO). Thiết bị `auto` chọn GPU CUDA nếu có."),
  P("Mỗi xe được biểu diễn bằng `Detection`: hộp [x1, y1, x2, y2], lớp, độ tin cậy, mã track, và **điểm chạm đất** = trung điểm cạnh dưới của hộp:"),
  EQ("u_đất = (x1 + x2) / 2,     v_đất = y2"),
  P("Đây là điểm bánh xe chạm mặt đường – điểm duy nhất của chiếc xe thực sự nằm trên mặt đường, nên mới dùng IPM được (mục 4)."),
  H2("3.2. ByteTrack – gán mã cho từng xe"),
  P("Để biết xe ở khung này chính là xe ở khung trước (cần cho bộ lọc Kalman và ghi vi phạm), ứng dụng gọi `model.track(persist=True, tracker=\"bytetrack.yaml\")`. ByteTrack hoạt động như sau:"),
  B("Mỗi track có một bộ lọc Kalman riêng dự đoán vị trí hộp ở khung mới."),
  B("Ghép các hộp mới với hộp dự đoán theo IoU (giải bài toán gán bằng thuật toán Hungary). Lượt 1 dùng hộp có điểm cao; lượt 2 dùng cả hộp điểm thấp để không mất xe bị che một phần."),
  B("Hộp không ghép được thì tạo track mới; track không được ghép một thời gian thì xóa."),
  H2("3.3. Phát hiện thưa – bám vết dày (template matching)"),
  P("Mã nguồn: `adas/detection/tracking.py`. YOLO là bước tốn thời gian nhất. Trên CPU mất khoảng 40 ms/khung, không kịp 30 khung/giây. Giải pháp: chỉ chạy YOLO mỗi N khung, các khung ở giữa đo lại vị trí từng xe bằng **so khớp mẫu** – nhanh hơn hàng chục lần."),
  H3("Chọn N tự động"),
  EQ("N = ⌈ thời_gian_YOLO / (0,5 · Δt_khung) ⌉,   giới hạn 1 ≤ N ≤ 4"),
  P("Tức là YOLO chỉ được chiếm tối đa một nửa thời gian của một khung. Trên GPU (YOLO vài ms) N = 1, trên CPU (~40 ms, video 30 fps) N = 3. Lần chạy YOLO đầu tiên (khởi động GPU 1–2 s) không được tính."),
  H3("Thuật toán bám một xe"),
  S("**Lấy mẫu neo** ở khung có YOLO: trên ảnh xám thu nhỏ còn rộng ≤ 640 px, lấy một lưới tối đa 16×16 điểm trong hộp xe (nội suy song tuyến), trừ trung bình và chia độ dài để được vectơ mẫu chuẩn hóa. Mẫu quá phẳng (độ lệch chuẩn < 2, ví dụ ban đêm tối) thì bỏ, không bám."),
  S("**Dò thô**: ở khung tiếp theo, thử các vị trí lệch trong bán kính r = 4 + 0,08·cạnh_hộp (tối đa 10 px), bước 2 px, cùng kích thước hiện tại."),
  S("**Dò tinh**: quanh điểm tốt nhất, thử ±1 px theo mỗi chiều với 3 tỉ lệ 0,97 / 1 / 1,03 (xe tiến lại gần thì to ra, đi xa thì nhỏ lại)."),
  S("**Nội suy parabol dưới pixel**: khớp parabol qua 3 giá trị tương quan quanh đỉnh để tìm đỉnh thật giữa hai pixel. Điều này quan trọng vì ở 20 m, lệch 1 px theo chiều dọc đã ứng với 0,3–0,7 m khoảng cách."),
  S("Nếu độ tương quan cao nhất < 0,6 (bị che, quá tối) thì đánh dấu hộp là `coast`: không có phép đo, khoảng cách chỉ được bộ lọc Kalman dự đoán."),
  P("Độ giống nhau giữa mẫu a và vùng ảnh b là tương quan chéo chuẩn hóa (NCC):"),
  EQ("NCC(a, b) = Σ (aᵢ − ā)(bᵢ − b̄) / ( ‖a − ā‖ · ‖b − b̄‖ ),   −1 ≤ NCC ≤ 1"),
  P("NCC không bị ảnh hưởng khi cả vùng sáng lên hay tối đi (ví dụ đi vào bóng cây), vì đã trừ trung bình và chia độ lệch."),
  H3("Quy tắc giữ / bỏ track"),
  B("Chỉ bám chi tiết 4 xe gần nhất (đáy hộp thấp nhất trong ảnh); các xe xa giữ hộp cũ."),
  B("YOLO bỏ sót một xe 1 lần thì vẫn bám tiếp; bỏ sót 2 lần liên tiếp thì xóa. Trước đây cho phép chờ 1 s, kết quả là có \"xe ma\" dẫn đầu tới 1 giây sau khi xe đã rời làn."),
  B("Mất dấu (coast) quá 0,5 s thì bỏ track."),
  NOTE("Trên video thử với N = 3, thời gian tầng phát hiện giảm từ 10,0 xuống 5,3 ms/khung (bám vết tốn ~1 ms). Khoảng cách tới xe dẫn đầu lệch trung vị 0,63 m so với chạy YOLO mọi khung, và mức cảnh báo trùng nhau 98 % số khung.", "Kết quả"),
);

// ===== 4. IPM
add(
  H1("4. Đo khoảng cách bằng IPM"),
  P("Mã nguồn: `adas/distance/ipm.py` (lớp `GroundPlaneMapper`) và `adas/distance/estimator.py` (lớp `DistanceEstimator`). Đây là phần cốt lõi của đề tài."),
  H2("4.1. Ý tưởng"),
  P("Ảnh camera là hình chiếu phối cảnh: các vạch làn song song trên đường hội tụ về một điểm (điểm tụ), vật càng xa càng nằm cao hơn trong ảnh và càng nhỏ. Một ảnh 2D bình thường không cho biết chiều sâu. Tuy nhiên nếu **giả thiết mặt đường là mặt phẳng**, thì mỗi pixel nằm dưới đường chân trời ứng với đúng một điểm trên mặt đường. Phép ánh xạ giữa hai mặt phẳng (mặt ảnh và mặt đường) là một **phép biến đổi phối cảnh (homography)**, biểu diễn bằng ma trận 3×3."),
  P("IPM (Inverse Perspective Mapping – biến đổi phối cảnh ngược) là dùng ma trận đó theo chiều ngược: từ pixel trên ảnh suy ra vị trí thật trên mặt đường, như thể nhìn từ trên xuống."),
  H2("4.2. Công thức homography"),
  P("Với điểm ảnh (u, v), dùng tọa độ đồng nhất [u, v, 1] và nhân với H:"),
  EQ("[ X·s,  Y·s,  s ]ᵀ  =  H · [ u,  v,  1 ]ᵀ"),
  P("Viết ra từng thành phần, với H = [hᵢⱼ]:"),
  EQ("X = (h₁₁·u + h₁₂·v + h₁₃) / (h₃₁·u + h₃₂·v + h₃₃)",
     "Y = (h₂₁·u + h₂₂·v + h₂₃) / (h₃₁·u + h₃₂·v + h₃₃)"),
  P("Phép chia cho s = h₃₁u + h₃₂v + h₃₃ chính là hiệu ứng phối cảnh: càng gần chân trời thì s càng nhỏ nên Y tăng rất nhanh. Điểm đặc biệt của dự án là **H ánh xạ thẳng sang mét**, nên Y của điểm chạm đất chính là khoảng cách tới xe phía trước, X là độ lệch ngang – không cần bước đổi đơn vị nào thêm."),
  H2("4.3. Tìm H từ 4 điểm căn chỉnh"),
  P("H có 9 phần tử nhưng nhân H với một hằng số bất kỳ vẫn cho cùng kết quả (vì chia cho s), nên chỉ có **8 ẩn**. Mỗi cặp điểm tương ứng (u, v) ↔ (X, Y) cho 2 phương trình tuyến tính, do đó cần đúng **4 cặp điểm** (không có 3 điểm nào thẳng hàng). Hàm `cv2.getPerspectiveTransform` giải hệ 8 phương trình này."),
  P("4 điểm này được tạo theo một trong ba cách ở mục 5. Cách dễ hiểu nhất là cách thủ công trong \"Căn chỉnh nâng cao\": người dùng chọn 4 điểm trên ảnh tạo thành một hình chữ nhật trên mặt đường có kích thước thật đã biết (thường là 2 mép của một làn đường). Thứ tự: dưới-trái, dưới-phải, trên-phải, trên-trái. Các điểm được lưu dưới dạng tỉ lệ 0..1 so với kích thước ảnh, để dùng được cho mọi độ phân giải. Tọa độ thật tương ứng:"),
  ...TBL(["Góc", "X (m)", "Y (m)"], [
    ["Dưới-trái", "−W/2", "d₀"], ["Dưới-phải", "+W/2", "d₀"], ["Trên-phải", "+W/2", "d₀ + L"], ["Trên-trái", "−W/2", "d₀ + L"],
  ], [3000, 3035, 3036]),
  P("Trong đó W là bề rộng hình chữ nhật (làn cao tốc Việt Nam = 3,75 m), L là chiều dài theo hướng xe chạy, d₀ là khoảng cách từ **đầu xe mình** tới cạnh gần của hình chữ nhật. Vì gốc Y đặt ở đầu xe nên khoảng cách đo được là khoảng cách giữa hai đầu-đuôi xe, đúng với khái niệm \"khoảng cách an toàn\" trong luật."),
  H2("4.4. Ví dụ số với cấu hình mặc định"),
  P("Khung 1280×720, cấu hình mặc định: W = 3,75 m, L = 30 m, d₀ = 6 m; 4 điểm ảnh (tỉ lệ) (0,33; 0,90), (0,67; 0,90), (0,535; 0,62), (0,465; 0,62), tức là theo pixel (422,4; 648), (857,6; 648), (684,8; 446,4), (595,2; 446,4). Giải ra (đã chuẩn hóa h₃₃ = 1):"),
  ...MAT("H ≈", [["−0,00555", "0", "3,5521"], ["0", "0,00451", "−6,7875"], ["0", "−0,00254", "1"]]),
  P("Đổi một số điểm ảnh sang mặt đường:"),
  ...TBL(["Điểm ảnh (u, v)", "Kết quả (X, Y)", "Giải thích"], [
    ["(640; 648)", "(0; 6,0 m)", "Giữa cạnh dưới hình chữ nhật: đúng d₀ = 6 m"],
    ["(640; 500)", "(0; 16,9 m)", "Xe có đáy hộp ở hàng 500 cách đầu xe 16,9 m"],
    ["(640; 446,4)", "(0; 36,0 m)", "Cạnh trên hình chữ nhật: d₀ + L = 36 m"],
    ["(700; 470)", "(1,73 m; 24,2 m)", "Lệch phải 1,73 m – vẫn trong làn (nửa làn ≈ 1,9 m)"],
    ["(640; 420)", "(0; 74,6 m)", "Gần chân trời: Y tăng rất nhanh"],
    ["(640; 300)", "không hợp lệ", "Trên đường chân trời (hàng ≈ 394): không phải mặt đường"],
  ], [2200, 2300, 4571]),
  H3("Vì sao sai số tăng nhanh theo khoảng cách"),
  P("Lệch đáy hộp đi 1 pixel theo chiều dọc làm khoảng cách thay đổi:"),
  ...TBL(["Hàng ảnh v", "Khoảng cách Y", "Thay đổi khi lệch 1 px"], [
    ["640", "6,3 m", "0,03 m"], ["500", "16,9 m", "0,18 m"], ["460", "28,2 m", "0,46 m"],
  ], [3000, 3035, 3036]),
  P("Với mô hình đường phẳng, Y ≈ K/(v − v₀) nên ∂Y/∂v ≈ Y²/K: sai số tăng theo **bình phương** khoảng cách. Đó là lý do IPM tin cậy tới khoảng 80–100 m, và vì sao cần bộ lọc Kalman (mục 6) để làm mượt."),
  H2("4.5. Kiểm tra điểm hợp lệ"),
  P("Hàm `image_to_ground` trả về NaN (không hợp lệ) trong các trường hợp:"),
  B("**Trên đường chân trời**: tại chân trời s = 0; phía trên chân trời s đổi dấu. Lúc khởi tạo, ứng dụng ghi lại dấu của s tại một điểm chắc chắn nằm trên mặt đường; điểm nào có dấu ngược lại là không hợp lệ. Hàng chân trời: v_h = −(h₃₁·u + h₃₃)/h₃₂."),
  B("**Y < 0** (sau đầu xe) hoặc **Y > max_range_m** (mặc định 150 m): ngoài tầm đo tin cậy."),
  H2("4.6. Phương pháp dự phòng Pinhole (xe \"Xa\")"),
  P("Khi điểm chạm đất không hợp lệ (xe quá xa, bị che phần dưới), ứng dụng ước lượng theo mô hình camera lỗ kim: vật thật cao H_thực cách camera d thì cao h_px = f·H_thực/d pixel trên ảnh. Dùng cả chiều cao và chiều rộng thật trung bình của từng loại xe (ô tô 1,5 × 1,8 m, xe tải 3,0 × 2,5 m, xe khách 3,2 × 2,5 m…):"),
  EQ("d_h = H_thực · f / h_px,     d_w = W_thực · f / w_px,     d = √(d_h · d_w)"),
  P("Tiêu cự f lấy từ phép phân rã H (mục 4.7) chứ không đoán theo góc nhìn. Kết quả luôn được nâng lên ít nhất `max_range_m`, gắn nhãn phương pháp **\"Xa\"** và mức rủi ro **\"info\"** (không gây cảnh báo). Như vậy thứ tự gần–xa không bị đảo so với các xe đo bằng IPM."),
  H2("4.7. Phân rã H ra ma trận camera"),
  P("Ma trận ngược G = H⁻¹ (mặt đường → ảnh) có dạng G ∝ K·[r₁ r₂ t] (phương pháp Zhang, 2000), trong đó K là ma trận nội tham số (tiêu cự f, tâm ảnh cx, cy), r₁, r₂ là hai trục của mặt đường trong hệ camera, t là vị trí gốc mặt đường. Giả thiết tâm ảnh nằm giữa khung và pixel vuông; vì r₁, r₂ phải có cùng độ dài và vuông góc nên giải ra được f. Từ đó có R = [r₁ r₂ r₁×r₂], t, và vị trí camera C = −Rᵀt (chiều cao camera, khoảng cách camera sau đầu xe, góc chúc)."),
  P("Với cấu hình mặc định ở trên: f ≈ 902 px, camera cao ≈ 2,19 m, nằm sau đầu xe ≈ 1,86 m. Các ma trận K, H, R được lưu vào bảng `camera_calibrations` trong cơ sở dữ liệu."),
  H2("4.8. Ảnh nhìn từ trên xuống (BEV)"),
  P("Cùng ma trận H, ghép thêm ma trận B đổi mét → pixel của ảnh BEV (tỉ lệ sₓ = rộng/(2·X_max), s_y = cao/(Y_max − Y_min), trục Y lật ngược để xa nằm trên), rồi `cv2.warpPerspective` với M = B·H. Chiều ngược lại `ground_to_image` (dùng H⁻¹) để vẽ hành lang làn, vạch ngưỡng 35 m, 70 m… lên video."),
  H2("4.9. Xác định xe dẫn đầu"),
  P("Sau khi có (X, Y) của mọi xe, danh sách được sắp theo khoảng cách tăng dần. Một xe nằm trong làn của mình nếu:"),
  B("có làn nhận diện được (mục 7): x_trái(Y) ≤ X ≤ x_phải(Y) với hai đường cong vạch làn;"),
  B("không có làn: |X| ≤ 1,9 m (nửa bề rộng hành lang cố định)."),
  P("**Xe dẫn đầu** là xe gần nhất trong làn. Khi bật \"chỉ cảnh báo cùng làn\", các xe ngoài làn chỉ hiển thị, không gây cảnh báo."),
);

// ===== 5. Căn chỉnh camera
add(
  H1("5. Căn chỉnh camera"),
  P("IPM chỉ đúng khi ma trận H khớp với camera thật. Ứng dụng có ba cách tạo H, cả ba đều cho ra cùng một dạng kết quả – 4 điểm `image_points` của một hình chữ nhật trên mặt đường (mục 4.3) – nên phần tính khoảng cách, cơ sở dữ liệu và bản Android không phải đổi gì:"),
  ...TBL(["Cách", "Người dùng làm gì", "Mã nguồn"], [
    ["**Theo tư thế camera – trình 3 bước** (mặc định)", "Chọn loại xe hoặc nhập chiều cao camera; kiểm tra đường chân trời app tự tìm", "camera_model.py, calibration_wizard.py"],
    ["**Tự hoàn thiện khi chạy**", "Không làm gì – app tự đo khi thấy rõ 2 vạch làn", "online_calib.py"],
    ["**Căn chỉnh nâng cao**: chấm 4 điểm, hoặc quét video tự động", "Chấm 4 góc một làn đường, hoặc nhập tốc độ xe rồi bấm \"Tự động căn chỉnh\"", "dialogs/calibration.py, autocalib.py"],
  ], [3000, 3671, 2400]),
  H2("5.1. Mô hình camera theo tư thế"),
  P("Mã nguồn: `adas/distance/camera_model.py` (lớp `PoseCamera`, hàm `calib_from_pose`). Ý tưởng giống camera hành trình và openpilot: trên mặt đường phẳng, camera chỉ cần vài đại lượng, hầu hết đo được tự động. Các đại lượng được lưu trong `CameraPose`:"),
  ...TBL(["Đại lượng", "Ý nghĩa", "Lấy từ đâu"], [
    ["h (height_m)", "Chiều cao camera so với mặt đường", "Loại xe (xe con 1,25 m; SUV 1,55 m; xe khách 2,30 m; xe tải 2,20 m) hoặc đo bằng thước"],
    ["bumper_m", "Camera nằm sau đầu xe bao nhiêu mét", "Loại xe (xe con 2,0 m; xe khách 0,4 m…) hoặc đo"],
    ["f (focal_w = f / bề rộng ảnh)", "Tiêu cự", "Android: thông số ống kính Camera2; máy tính: góc nhìn giả định 55°, rồi chỉnh theo tốc độ thật (mục 5.2)"],
    ["Điểm tụ (vp_x, vp_y)", "Vị trí trên ảnh của hướng thẳng phía trước – cho biết góc chúc và góc lệch ngang", "Tự tìm từ vạch kẻ đường; Android: cảm biến trọng lực"],
    ["roll_deg", "Góc nghiêng ngang của camera", "Như điểm tụ"],
  ], [2300, 3171, 3600]),
  P("Điểm tụ được dùng làm tham số thay cho góc, vì đó là thứ nhìn thấy trực tiếp trên ảnh: đổi tiêu cự không làm dịch đường chân trời."),
  H3("Dựng hệ trục camera từ tư thế"),
  P("Gọi K là ma trận nội tham số (tiêu cự f, tâm ảnh ở giữa khung). Từ điểm tụ và góc nghiêng suy ra ba vectơ đơn vị trong hệ camera:"),
  ...EQN([["fwd = K⁻¹ · [u_vp, v_vp, 1]ᵀ", "hướng xe chạy (chuẩn hóa độ dài 1)"],
          ["down ∝ Kᵀ · l_chân_trời", "pháp tuyến mặt đường, hướng xuống (vuông góc với fwd)"],
          ["right = down × fwd", "hướng sang phải"]]),
  P("Trong đó l_chân_trời là đường thẳng trên ảnh đi qua điểm tụ, nghiêng theo roll. Mặt phẳng chứa tâm camera và đường chân trời song song với mặt đường, nên pháp tuyến của nó (Kᵀ·l) chính là hướng thẳng đứng."),
  H3("Chiếu mặt đường ↔ ảnh"),
  ...EQN([["P = X·right + (Y + bumper)·fwd + h·down", "điểm mặt đường (X, Y) trong hệ camera"],
          ["[u, v, 1]ᵀ ∝ K · P", "chiếu lên ảnh"]]),
  P("Chiều ngược lại (ảnh → mặt đường): lấy tia r = K⁻¹·[u, v, 1]ᵀ; nếu s = r·down ≤ 0 thì tia không chạm đất (trên chân trời); ngược lại điểm chạm đất là P = r·h/s, suy ra X = P·right, Y = P·fwd − bumper."),
  H3("Sinh 4 điểm căn chỉnh"),
  P("`calib_from_pose` lấy hai hàng ảnh: hàng gần ở 85 % chiều cao ảnh và hàng xa ở 15 % khoảng từ chân trời xuống hàng gần. Hai hàng này cho khoảng cách d₀ và d₁. Hàm dựng một hình chữ nhật rộng một làn (3,75 m, thu hẹp lại nếu tràn khỏi ảnh) từ d₀ tới d₁, rồi chiếu 4 góc lên ảnh. Kết quả là 4 điểm image_points giống hệt như khi người dùng tự chấm, chỉ khác là chính xác tuyệt đối theo tư thế."),
  H3("Ví dụ số"),
  P("Khung 1280×720, xe con: h = 1,25 m, camera sau đầu xe 2,0 m, điểm tụ ở giữa ảnh theo chiều ngang và ở hàng 324 (45 % chiều cao), tiêu cự theo góc nhìn 55° nên f ≈ 692 px (camera chúc xuống ≈ 3,0°). Hàm sinh ra hình chữ nhật 3,75 m × 16,9 m bắt đầu cách đầu xe 1,0 m, với 4 góc trên ảnh (216; 607), (1064; 607), (705; 367), (575; 367). Phân rã ngược ma trận H này (mục 4.7) cho lại đúng h = 1,25 m, camera sau đầu xe 2,0 m và f ≈ 692 px, tức là hai cách tính khớp nhau. Một vài khoảng cách theo hàng ảnh:"),
  ...TBL(["Hàng ảnh v", "500", "420", "380"], [["Khoảng cách Y", "2,9 m", "7,0 m", "13,4 m"]], [2271, 2266, 2267, 2267]),
  H3("Trình căn chỉnh 3 bước"),
  S("**Xe và số đo**: chọn loại xe (điền sẵn chiều cao và khoảng cách tới đầu xe điển hình), hoặc nhập số đo bằng thước. Chỉ khi nhập bằng thước thì chiều cao mới được giữ cố định (`height_measured`)."),
  S("**Đường chân trời**: trên máy tính, app chạy `estimate_vanishing_point` (Hough + RANSAC như mục 5.3) trên khoảng 3 giây video quanh khung đang xem, rồi vẽ đường chân trời và tâm ngắm. Trên Android, app đọc hướng trọng lực (mục 14.1). Người dùng chỉ cần kiểm tra, kéo trên ảnh hoặc dùng phím mũi tên nếu thấy lệch. Với video, có thể nhập thêm tốc độ in trên hình (`ref_speed_kmh`) để chỉnh tiêu cự sau này."),
  S("**Hoàn tất**: lưu căn chỉnh (phương thức \"pose\") và báo rằng app sẽ tự hoàn thiện khi chạy."),
  H2("5.2. Tự hoàn thiện căn chỉnh khi chạy"),
  P("Mã nguồn: `adas/distance/online_calib.py` (lớp `OnlineCalibrator`), tùy chọn \"Tự hoàn thiện căn chỉnh camera khi chạy\" (`auto_calib`, mặc định bật). Cách làm giống openpilot và Tesla (\"Đang hiệu chỉnh 0–100 %\"): trong lúc chạy, app đo lại điểm tụ từ chính vạch kẻ đường để sửa căn chỉnh ban đầu, và phát hiện khi camera bị xê dịch."),
  H3("Mỗi khung: một mẫu điểm tụ"),
  S("Lấy 2 vạch làn của xe mình mà bộ nhận diện làn (mục 7) **thật sự thấy** ở khung này. Với mỗi vạch, chiếu đoạn từ 6 m đến 24 m về lại ảnh để được một dây cung (2 điểm pixel)."),
  S("Giao điểm của 2 dây cung trên ảnh là một mẫu điểm tụ. Vị trí vạch trên ảnh không phụ thuộc căn chỉnh đang dùng, nên căn chỉnh sai không tự khuếch đại qua phép đo này."),
  S("Bỏ mẫu khi xe chạy dưới 30 km/h (đứng yên, tắc đường) hoặc khi điểm tụ nằm ngoài ảnh."),
  S("Đánh dấu mẫu là **đường thẳng** nếu cả hai vạch có bán kính cong ≥ 1000 m."),
  P("Trên đường cong, hai dây cung của hai vạch song song vẫn song song, nên điểm tụ chỉ dịch **ngang**. Vì vậy **hàng** điểm tụ (đường chân trời, góc chúc) được lấy từ mọi mẫu, còn **cột** điểm tụ (góc lệch ngang) chỉ lấy từ mẫu đường thẳng, khi có ít nhất 20 % mẫu như vậy."),
  H3("Đủ mẫu: tính căn chỉnh mới"),
  B("Cần **150 mẫu** (Android 90 mẫu, vì đo khoảng 15 lần/s) trải trên **ít nhất 5 s**. Tiến độ hiển thị là min(số mẫu/150; thời gian/5 s)."),
  B("Kiểm tra độ phân tán của điểm tụ bằng MAD × 1,4826, đổi ra góc arctan(MAD/f): theo cột phải ≤ 1,5°, theo hàng ≤ 1,0°. Nếu phân tán quá nhiều (xe xóc, nhận nhầm vạch) thì bỏ nửa số mẫu cũ và đo thêm."),
  B("Điểm tụ mới là **trung vị** các mẫu. App đặt điểm tụ này vào tư thế rồi gọi `calib_from_pose`."),
  B("**Chiều cao camera**: nếu chưa đo bằng thước, app dựa vào việc bề rộng làn đo được tỉ lệ thuận với h (cùng các tia nhìn): h_mới = h · 3,75 / bề_rộng_đo. Ví dụ với h = 1,25 m mà làn đo ra 4,2 m thì h_mới ≈ 1,12 m. Nếu chiều cao đã đo bằng thước thì giữ nguyên, bề rộng làn chỉ dùng để tự kiểm tra."),
  B("**Tiêu cự** (chỉ một lần, khi tiêu cự còn là giả định và đã có tốc độ thật `ref_speed_kmh` cùng ≥ 30 lần đo tốc độ từ video): khoảng cách và tốc độ đo từ video cùng tỉ lệ với thang chiều sâu. App chỉnh f, lặp 3 lần, sao cho quãng đường giữa 2 hàng ảnh (ứng với 8 m và 22 m) nhân lên đúng tỉ lệ tốc_độ_thật / tốc_độ_đo."),
  B("Căn chỉnh mới được trả về giao diện để áp dụng ngay và lưu CSDL (phương thức \"online\"), kèm ghi chú kết quả."),
  H3("Tự kiểm tra và theo dõi xê dịch"),
  B("**Kết luận về bề rộng làn đo được** (so với 3,75 m): lệch ≤ 0,25 m là \"đạt\", ≤ 0,5 m là \"hơi lệch\", lớn hơn là \"lệch nhiều, kiểm tra lại chiều cao camera\"."),
  B("**Căn chỉnh 4 điểm** (thủ công hoặc quét video): app không sửa gì, chỉ đo bề rộng làn và báo kết quả kiểm tra."),
  B("**Sau khi xong**: app tiếp tục so trung vị 150 mẫu gần nhất với điểm tụ của căn chỉnh đang dùng (điểm tụ của H là H⁻¹·[0, 1, 0]ᵀ). Nếu lệch > 1,5° theo cột hoặc > 1,0° theo hàng thì coi là **camera bị xê dịch**. Với căn chỉnh theo tư thế, app tự đo lại từ đầu; với căn chỉnh 4 điểm, app nhắc người dùng căn chỉnh lại."),
  B("Người dùng tự đổi căn chỉnh thì bộ này đo lại từ đầu. Nếu căn chỉnh vừa đổi là do chính bộ này đề xuất thì nó chuyển sang chế độ theo dõi."),
  H2("5.3. Căn chỉnh nâng cao: quét video tự động"),
  P("Mã nguồn: `adas/distance/autocalib.py`, nút \"Tự động căn chỉnh\" trong hộp thoại \"Căn chỉnh nâng cao\" (cùng nơi chấm 4 điểm bằng tay). Mục tiêu: tạo 4 điểm căn chỉnh không cần chọn tay, chỉ từ một đoạn video cao tốc và tốc độ xe (đọc trên màn hình camera hành trình)."),
  H3("Mô hình đường phẳng"),
  P("Camera nhìn thẳng theo hướng đường, mặt đường phẳng. Gọi v₀ là hàng chân trời, f tiêu cự, h_c chiều cao camera:"),
  ...EQN([["Y(v) = K / (v − v₀)", "với K = f · h_c"], ["w(v) = c · (v − v₀)", "với c = W_làn / h_c"]]),
  P("Y(v) là khoảng cách tới hàng ảnh v; w(v) là bề rộng làn tính bằng pixel tại hàng đó. Cần đo 3 đại lượng: v₀ (và cột u₀ của điểm tụ), c, và K."),
  H3("Các bước"),
  S("**Đọc video**: lấy khoảng 150 cặp khung cách nhau 2 khung trên tối đa 1800 khung đầu."),
  S("**Tìm điểm tụ (u₀, v₀)**: lọc màu sơn trắng/vàng nhạt (HSV), tìm cạnh Canny, tìm các đoạn thẳng bằng Hough (bỏ đoạn gần ngang hoặc gần dọc). Dùng RANSAC 3000 lần: chọn ngẫu nhiên 2 đường, lấy giao điểm, đếm số đường đi qua gần điểm đó (< 2 px). Điểm được nhiều đường ủng hộ nhất được tinh chỉnh bằng bình phương tối thiểu."),
  S("**Đo hệ số bề rộng làn c**: trên mỗi khung, quét các đường thẳng đi qua điểm tụ x = u₀ + a·(v − v₀), tìm hai đường gần trục xe nhất có nhiều điểm sáng (2 vạch làn của xe mình). Hiệu hai độ dốc a_phải − a_trái chính là c. Lấy trung vị trên mọi khung. Suy ra chiều cao camera h_c = 3,75 / c."),
  S("**Đo thang chiều sâu K từ chuyển động**: khi xe chạy với vận tốc v_xe, mọi điểm trên mặt đường tiến lại gần đúng v_xe·Δt mét. Lấy hồ sơ độ sáng dọc vạch đứt theo biến y′ = 1/(v − v₀) (tuyến tính với Y/K), so khớp giữa 2 khung để tìm độ dịch Δy′ (tương quan > 0,85):"),
  ...EQ("K = v_xe · Δt / Δ(1/(v − v₀)),      f = K / h_c"),
  S("Lấy trung vị K của ≥ 8 lần đo; độ phân tán (IQR/2) được báo là sai số. Nếu không có tốc độ hoặc không đủ mẫu, dùng góc nhìn dọc giả định (55°) để suy ra f."),
  S("**Kiểm tra chéo**: với thang vừa đo, tính độ dài vạch đứt và chu kỳ lặp – phải gần với tiêu chuẩn thực tế."),
  S("**Dựng hình chữ nhật căn chỉnh** đối xứng quanh cột điểm tụ (nên X = 0 là trục hướng xe chạy), rộng 3,75 m, giữa hai hàng v₀ + 0,17h và v₀ + 0,05h; trừ khoảng camera–đầu xe (mặc định 2 m)."),
  NOTE("Trên video thử, căn chỉnh tự động cho tốc độ đo được lệch −6 % so với GPS, trong khi căn chỉnh tay cũ lệch ~ −26 % (55 so với 74 km/h). Sai bao nhiêu % thang chiều sâu thì khoảng cách cũng sai bấy nhiêu %.", "Kết quả"),
);

// ===== 6. Kalman
add(
  H1("6. Bộ lọc Kalman"),
  P("Mã nguồn: `adas/distance/kalman.py` (lớp `RangeKalman`), được `DistanceEstimator._update_track` gọi cho từng xe. Bản Android dùng cùng thuật toán (`core/Kalman.kt`)."),
  H2("6.1. Lọc cái gì?"),
  P("Đầu vào của bộ lọc là **khoảng cách IPM đo được của một xe ở mỗi khung**. Phép đo này bị nhiễu vì hộp bao YOLO/tracker rung vài pixel giữa các khung, và như mục 4.4 cho thấy, ở 28 m chỉ 1 px đã là 0,46 m. Đo trên video thử, phần dư quanh đường cong trơn của từng xe là **khoảng 4 % khoảng cách**. Bộ lọc giải quyết 4 việc:"),
  B("**Làm mượt khoảng cách** hiển thị và dùng để so ngưỡng (không nhấp nháy giữa cảnh báo / an toàn)."),
  B("**Ước lượng tốc độ tiếp cận** d′ (m/s). Nếu lấy hiệu hai lần đo chia Δt thì nhiễu 4 % của 40 m (1,6 m) chia 1/30 s cho ra nhiễu ~48 m/s – vô dụng. Kalman ước lượng đạo hàm một cách thống kê từ cả chuỗi phép đo."),
  B("**Dự đoán** khoảng cách ở các khung không có phép đo (xe bị che, trạng thái `coast`)."),
  B("**Loại bỏ phép đo sai** đột ngột (ví dụ hộp bị nhận nhầm một khung)."),
  H2("6.2. Trạng thái và mô hình chuyển động"),
  P("Mỗi xe (mỗi mã track) có một bộ lọc riêng với vectơ trạng thái 3 phần tử:"),
  EQ("x = [ d,  d′,  d″ ]ᵀ"),
  P("d là khoảng cách (m), d′ là tốc độ thay đổi khoảng cách (m/s, âm = đang tiến lại gần), d″ là gia tốc tương đối (m/s²). Mô hình là **gia tốc không đổi** (constant acceleration) trong một bước Δt, với nhiễu quá trình là độ giật (jerk) ngẫu nhiên:"),
  ...MAT("F =", [["1", "Δt", "Δt²/2"], ["0", "1", "Δt"], ["0", "0", "1"]], 1000),
  EQ("Q = σⱼ² · g · gᵀ,    g = [ Δt³/6,  Δt²/2,  Δt ]ᵀ,    σⱼ = 10 m/s³"),
  P("F mô tả vật lý: d mới = d + d′·Δt + d″·Δt²/2, d′ mới = d′ + d″·Δt. Q nói rằng gia tốc có thể thay đổi bất ngờ (xe trước đạp phanh) với độ lớn đặc trưng σⱼ = 10 m/s³ – tức là trong 0,6 s gia tốc có thể đổi tới 6 m/s² (một cú phanh gấp)."),
  H2("6.3. Mô hình phép đo"),
  P("Chỉ đo được khoảng cách: z = d + nhiễu, ma trận đo H_m = [1 0 0]. Độ lệch chuẩn nhiễu đo phụ thuộc khoảng cách:"),
  EQ("σ_d = max( 0,3 m ;  4 % · d )        (xe \"Xa\" đo bằng Pinhole: 25 % · d)"),
  P("Xe ở 10 m có σ = 0,4 m; xe ở 50 m có σ = 2 m. Xe càng xa thì bộ lọc càng tin vào dự đoán hơn phép đo."),
  H2("6.4. Hai bước của mỗi khung"),
  H3("Bước dự đoán (predict) – tới thời điểm khung mới t"),
  ...EQN([["Δt = t − t_trước", "khoảng thời gian từ lần trước"], ["x⁻ = F · x", "dự đoán trạng thái"],
       ["P⁻ = F · P · Fᵀ + Q", "dự đoán độ không chắc chắn"]]),
  P("P là ma trận hiệp phương sai 3×3 – độ không chắc chắn của trạng thái. Sau khi dự đoán, P lớn lên (càng lâu không đo càng kém chắc chắn). Ở khung `coast` chỉ thực hiện bước này."),
  H3("Bước cập nhật (update) – khi có phép đo z"),
  ...EQN([["y = z − d⁻", "độ lệch giữa đo và dự đoán"], ["S = P⁻₀₀ + σ_d²", "phương sai của độ lệch"],
       ["K = P⁻[:, 0] / S", "độ lợi Kalman (vectơ 3 phần tử)"], ["x = x⁻ + K · y", "trạng thái sau cập nhật"],
       ["P = P⁻ − K · P⁻[0, :]", "độ không chắc chắn giảm đi"]]),
  P("Trực giác: độ lợi K cân bằng giữa \"tin dự đoán\" và \"tin phép đo\". Nếu dự đoán đang không chắc (P⁻₀₀ lớn) thì K gần 1 – theo phép đo; nếu phép đo nhiễu (σ_d lớn) thì K nhỏ – bám theo dự đoán. Quan trọng là K có cả thành phần thứ 2 và 3: một độ lệch y kéo dài sẽ dần sửa d′ và d″ – đó chính là cách bộ lọc \"học\" ra tốc độ tiếp cận và gia tốc."),
  H2("6.5. Khởi tạo, cổng loại ngoại lai, báo kết quả"),
  B("**Khởi tạo** khi thấy xe lần đầu: d = phép đo đầu tiên; d′ = 0 với độ lệch 8 m/s (chưa biết gì); d″ = 0 với độ lệch 1 m/s²."),
  B("**Cổng 5σ**: nếu y² > 25·S (phép đo lệch dự đoán quá 5 độ lệch chuẩn) thì coi là ngoại lai, bỏ qua phép đo. Nếu **3 ngoại lai liên tiếp** thì có lẽ dự đoán sai (đổi xe, lần đo đầu lệch) nên khởi tạo lại bằng phép đo mới."),
  B("**Chỉ báo tốc độ tiếp cận và TTC khi đủ tin**: khi √P₁₁ < 2 m/s, khoảng 0,6 s sau khi thấy xe. Trước đó giá trị là None để không cảnh báo sai lúc xe vừa xuất hiện."),
  B("**Xóa** bộ lọc của xe không được đo trong 2 s."),
  P("Từ trạng thái lọc suy ra:"),
  ...EQN([["v_c = −d′", "tốc độ tiếp cận (> 0 là đang lại gần)"], ["TTC = d / v_c", "chỉ tính khi v_c > 0,5 m/s"]]),
  H2("6.6. Vì sao chọn mô hình gia tốc không đổi"),
  P("Ba phương án được so sánh bằng mô phỏng (xe trước chạy đều ở 40 m rồi phanh 6 m/s², nhiễu đo như thực tế, 200 lần lặp):"),
  ...TBL(["Phương án", "Nhiễu khi chạy đều", "Trễ phát hiện phanh", "Sai số tốc độ khi phanh"], [
    ["Cũ: trung bình mũ + hồi quy 1 s", "0,75 m/s", "608 ms", "3,5 m/s"],
    ["Kalman vận tốc không đổi (CV)", "0,41 m/s", "1124 ms", "6,0 m/s"],
    ["**Kalman gia tốc không đổi (CA), σⱼ = 10**", "0,77 m/s", "**415 ms**", "**1,4 m/s**"],
  ], [3371, 1900, 1900, 1900]),
  P("Mô hình vận tốc không đổi coi cú phanh là nhiễu nên phản ứng rất chậm (1,1 s). Mô hình gia tốc không đổi có trạng thái d″ nên theo kịp cú phanh, phát hiện sớm hơn gần 0,2 s so với cách cũ – ở 90 km/h là 5 m quãng đường."),
  H2("6.7. Ví dụ chạy bộ lọc"),
  P("Mô phỏng 30 khung/giây: xe trước cách 40 m, đến t = 1,5 s thì phanh, khoảng cách bắt đầu giảm với gia tốc 6 m/s². Phép đo có nhiễu 4 %."),
  ...TBL(["t (s)", "d thật", "d đo", "d lọc", "v_c thật", "v_c lọc", "√P₁₁"], [
    ["0,00", "40,00", "40,55", "40,55", "0,0", "0,0", "8,00"],
    ["0,67", "40,00", "40,01", "39,59", "0,0", "1,3", "1,77"],
    ["1,00", "40,00", "**43,39**", "**39,58**", "0,0", "0,5", "1,28"],
    ["1,33", "40,00", "38,04", "39,51", "0,0", "0,4", "1,31"],
    ["2,00", "39,09", "39,18", "39,32", "3,2", "0,5", "1,37"],
    ["2,33", "37,66", "39,50", "38,10", "5,2", "2,2", "1,29"],
    ["2,67", "35,56", "36,66", "36,02", "7,2", "4,8", "1,22"],
    ["3,00", "32,79", "33,94", "33,35", "9,2", "7,2", "1,17"],
  ], [1100, 1300, 1300, 1300, 1300, 1300, 1471]),
  P("Nhận xét: tại t = 1,00 s phép đo nhảy lên 43,39 m nhưng giá trị lọc vẫn 39,58 m (gần 40 m thật). Sau 0,67 s, √P₁₁ đã < 2 m/s nên bắt đầu báo tốc độ tiếp cận. Khi phanh, ước lượng v_c đuổi theo giá trị thật với độ trễ vài trăm mili-giây."),
);

// ===== 7. Làn đường
add(
  H1("7. Nhận diện làn đường của xe mình"),
  P("Mã nguồn: `adas/distance/lane.py` (lớp `EgoLaneDetector`), bật/tắt bằng tùy chọn `auto_lane`. Mục đích: biết chính xác xe nào nằm trong làn mình đang đi (kể cả khi đường cong) để chọn đúng xe dẫn đầu. Vị trí 2 vạch làn tìm được cũng là đầu vào cho việc đo tốc độ (mục 8) và tự hoàn thiện căn chỉnh (mục 5.2)."),
  H2("7.1. Các bước mỗi khung"),
  S("**Chuyển sang BEV đơn vị mét**: dùng chính H đã căn chỉnh, chiếu ảnh xám sang vùng X ∈ [−6; 6] m, Y ∈ [4; 36] m, độ phân giải 0,05 m × 0,1 m mỗi pixel. Trên BEV, vạch làn là các dải sáng hẹp gần như thẳng đứng."),
  S("**Lọc top-hat theo chiều ngang** (phần tử cấu trúc rộng 0,6 m): giữ lại các dải sáng hẹp hơn 0,6 m (vạch sơn rộng 0,15–0,2 m), bỏ mặt đường, dải phân cách, thân xe. Pixel nổi sáng hơn nền ≥ 14 mức xám thì giữ."),
  S("**Che vùng có xe**: tô đen các hộp YOLO (chiếu sang BEV) để đèn hậu, biển số không bị nhầm là vạch."),
  S("**Tìm vị trí vạch**: nếu đã có làn từ khung trước thì tìm quanh đường cũ; nếu chưa thì cộng dồn điểm sáng theo cột (histogram), lấy các đỉnh gần trục xe nhất ở hai bên, chọn cặp có bề rộng hợp lý và gần bề rộng đã biết nhất."),
  S("**Cửa sổ trượt**: chia Y thành 8 dải từ gần ra xa; ở mỗi dải lấy các điểm sáng trong cửa sổ ±0,45 m quanh vị trí dự kiến, rồi dời cửa sổ theo trung vị các điểm vừa thấy (để bám theo đường cong)."),
  S("**Khớp đường cong bậc 2** cho từng vạch: X = c₀ + c₁·Y + c₂·Y². Độ cong bị giới hạn ở bán kính ≥ 300 m (|c₂| ≤ 1/600); vạch lệch hướng quá nhiều (|c₁| > 0,25) bị loại."),
  H2("7.2. Kiểm tra và làm mượt theo thời gian"),
  B("**Bắt làn lần đầu**: phải thấy **cả hai** vạch, bề rộng làn 2,2–5,2 m, làn chứa trục xe (±0,4 m), liên tiếp **3 khung**. Trước đó trả về None (dùng hành lang cố định ±1,9 m). Ảnh tĩnh và đường phố đêm thường không bắt được làn – đây là chủ ý."),
  B("**Thiếu một vạch** (vạch mờ, bị xe che): suy ra từ vạch còn lại và bề rộng làn đã làm mượt."),
  B("**Làm mượt** hệ số đường cong bằng trung bình mũ (hệ số 0,35). Nếu tâm làn nhảy quá nửa làn (xe vừa chuyển làn) thì nhận làn mới ngay, không làm mượt."),
  B("**Mất làn** khi không thấy vạch nào trong 20 khung liên tiếp."),
  NOTE("Bề rộng làn đo được là bề rộng thật, chỉ đúng khi căn chỉnh đúng tỉ lệ ngang. Nếu một làn 3,75 m đo ra ~4,7 m thì 4 điểm căn chỉnh tay đang bị lệch."),
);

// ===== 8. Tốc độ xe mình
add(
  H1("8. Đo tốc độ xe mình từ video"),
  P("Mã nguồn: `adas/distance/ego_speed.py` (lớp `EgoSpeedEstimator`), tùy chọn `auto_speed`. Bản máy tính không có GPS/OBD nên tốc độ (cần để tính ngưỡng luật) được đo từ chính video."),
  H2("8.1. Nguyên lý"),
  P("Khi xe chạy với vận tốc v, mọi điểm trên mặt đường tiến lại gần đúng v·Δt mét. Vạch đứt có hoa văn \"sơn – hở – sơn\". Nếu biết hoa văn này theo khoảng cách thật Y (nhờ IPM), thì so hai khung cách nhau Δt sẽ thấy hoa văn bị dời đi một đoạn s:"),
  EQ("p_hiện_tại(Y) ≈ p_trước(Y + s)     ⇒     v = s / Δt"),
  H2("8.2. Các bước"),
  S("Với mỗi vạch làn **thực sự tìm thấy** ở mục 7, lấy mẫu độ sáng dọc vạch từ Y = 5 đến 26 m, bước 0,05 m; mỗi Y quét ngang ±0,25 m quanh vạch, lấy (sáng nhất − trung vị) để ra \"hồ sơ\" độ nổi của sơn. Lấy mẫu trên ảnh gốc qua `cv2.remap` (nét hơn ảnh BEV)."),
  S("Chỉ giữ **vạch đứt**: có độ tương phản ≥ 20, tỉ lệ phần sơn 5–75 %, có ít nhất 2 lần chuyển sơn/hở. Vạch liền không có thông tin chuyển động dọc nên bị bỏ – nếu đưa vào sẽ kéo kết quả về 0."),
  S("Chọn khung tham chiếu cách 0,08–0,4 s trước. Thử các độ dời s, tính tương quan chuẩn hóa giữa hai hồ sơ, chọn s có tương quan lớn nhất (≥ 0,8), nội suy parabol để có độ phân giải dưới 0,05 m."),
  S("Khi đã có tốc độ, chỉ tìm s trong khoảng 0,6–1,4 lần giá trị dự đoán, để không \"nhảy\" sang vạch đứt kế tiếp (lỗi aliasing)."),
  S("v = s/Δt. Lấy **trung vị** các lần đo trong 1 s, rồi làm mượt hàm mũ với hằng số thời gian τ = 1 s (sau 1 s khởi động bám thẳng trung vị). Số hiển thị chỉ đổi khi lệch ≥ 1 km/h."),
  P("Mỗi lần đo riêng lẻ dao động ±8 km/h; không làm mượt thì số trên màn hình đổi ~8 lần/giây. Sau khi làm mượt, sai số trung bình tuyệt đối so với GPS in trên video thử là **~1,3 km/h**."),
  B("Không đo được (không có vạch đứt, ảnh tĩnh) thì dùng tốc độ người dùng nhập."),
  B("Người dùng bấm chọn tốc độ hoặc trợ lý AI trả về tốc độ thì tự tắt chế độ đo tự động."),
  NOTE("Không dùng tương quan pha trên cả ảnh BEV: ở 640×360, đoạn Y 4–24 m chỉ chiếm ~60 hàng ảnh, vạch liền và nhòe chuyển động kéo đỉnh tương quan về 0."),
);

// ===== 9. Ngưỡng an toàn
add(
  H1("9. Tính ngưỡng khoảng cách an toàn"),
  P("Mã nguồn: `adas/alert/thresholds.py`, hàm `compute_thresholds(speed, policy)`. Mỗi khung tính lại hai ngưỡng: **safe_m** (dưới mức này là CẢNH BÁO) và **danger_m** (dưới mức này là NGUY HIỂM)."),
  H2("9.1. Mức cơ sở khi đường khô"),
  P("Theo Thông tư 31/2019/TT-BGTVT, Điều 11 (đường khô ráo):"),
  ...TBL(["Tốc độ V", "Khoảng cách tối thiểu"], [
    ["V = 60 km/h", "35 m"], ["60 < V ≤ 80 km/h", "55 m"], ["80 < V ≤ 100 km/h", "70 m"], ["100 < V ≤ 120 km/h", "100 m"],
  ], [4535, 4536]),
  B("**V ≥ 60 km/h**: lấy ngưỡng của dải tốc độ. Người dùng được đặt riêng cho từng dải (Cài đặt → \"Ngưỡng cảnh báo\") nhưng không bao giờ thấp hơn mức luật. Trên 120 km/h ngoại suy tuyến tính: 100·V/120."),
  B("**V < 60 km/h**: luật để tài xế tự chủ động, hệ thống ước tính bằng **quy tắc 2 giây**: d = V/3,6 · 2 s."),
  EQ("base = max( ngưỡng_dải(V)  hoặc  V/3,6 · time_gap ;  min_distance = 5 m )"),
  H2("9.2. Hệ số điều kiện đường và hai ngưỡng"),
  ...EQ("safe = base × weather_factor", "danger = max( min_distance ;  safe × danger_ratio )"),
  P("danger_ratio mặc định là 0,5, tức ngưỡng nguy hiểm bằng một nửa ngưỡng cảnh báo."),
  P("Luật chỉ yêu cầu \"giữ khoảng cách lớn hơn\" khi trời mưa, sương mù… mà không nêu số. Hệ thống ước tính hệ số dựa vào vật lý phanh: quãng phanh v²/(2μg) tỉ lệ nghịch với hệ số bám μ, nên hệ số ≈ 0,7/μ (μ đường khô ≈ 0,7):"),
  ...TBL(["Điều kiện", "μ ước tính", "Hệ số", "TTC cảnh báo / nguy hiểm"], [
    ["Khô ráo", "0,70", "1,0", "4,0 / 2,0 s"], ["Ướt, mưa nhỏ", "0,50", "1,4", "5,0 / 2,5 s"],
    ["Mưa to, đọng nước", "0,35", "2,0", "6,0 / 3,0 s"], ["Sương mù", "0,60", "1,5", "5,5 / 3,0 s"],
    ["Trơn trượt (dầu, bùn, sỏi)", "0,25", "2,5", "6,0 / 3,0 s"],
  ], [3371, 1700, 1500, 2500]),
  P("Các yếu tố cộng thêm nhân dồn vào hệ số: ban đêm ×1,2; chở nặng ×1,3; tài xế mệt ×1,15 (mỗi yếu tố cũng tăng ngưỡng TTC thêm 0,5 / 0,25 s). Hệ số tối đa là 3,0. Thời tiết chỉ được tính **một lần** qua hệ số này – không tăng thêm time_gap, nếu không sẽ bị tính hai lần."),
  H2("9.3. Ví dụ tính ngưỡng"),
  ...TBL(["Tình huống", "base", "Hệ số", "safe", "danger"], [
    ["90 km/h, đường khô", "70 m", "1,0", "70 m", "35 m"],
    ["90 km/h, mưa to", "70 m", "2,0", "140 m", "70 m"],
    ["50 km/h, đường khô (quy tắc 2 s)", "27,8 m", "1,0", "27,8 m", "13,9 m"],
    ["110 km/h, sương mù + ban đêm", "100 m", "1,5 × 1,2 = 1,8", "180 m", "90 m"],
  ], [3571, 1200, 1700, 1300, 1300]),
  H2("9.4. Tốc độ khuyến nghị khi tầm nhìn hạn chế"),
  P("Khi có tầm nhìn (ví dụ \"sương mù, tầm nhìn 80 m\"), hệ thống tính tốc độ lớn nhất sao cho quãng đường dừng xe (phản xạ 1,5 s + phanh) không vượt quá tầm nhìn:"),
  EQ("quãng_dừng = v·t_r + v² / (2μg)",
     "v_max = a · ( −t_r + √( t_r² + 2·tầm_nhìn / a ) ),   a = μ·g"),
  P("Ví dụ: sương mù (μ = 0,6), tầm nhìn 80 m → v_max ≈ 83 km/h. Để so sánh, ở 90 km/h quãng dừng trên đường khô là 83 m, trên đường mưa to (μ = 0,35) là 129 m."),
  H2("9.5. Phân loại mức rủi ro của từng xe"),
  P("Hàm `classify_risk` kết hợp khoảng cách và TTC:"),
  B("**NGUY HIỂM** nếu d < danger_m hoặc TTC < ttc_danger_s."),
  B("**CẢNH BÁO** nếu d < safe_m hoặc TTC < ttc_warning_s."),
  B("Ngược lại **AN TOÀN**."),
  P("TTC giúp cảnh báo sớm khi đang lao nhanh vào xe trước dù khoảng cách vẫn còn trên ngưỡng. Xe ngoài làn (khi bật chỉ-cùng-làn) hoặc xe \"Xa\" có mức \"info\", không tính. Mức thô của khung là mức cao nhất trong các xe còn lại."),
  NOTE("Câu giải thích dưới \"GIỮ TỐI THIỂU\" trên giao diện (ví dụ \"Theo luật (đường khô): 70 m\" và \"× 2 do điều kiện đường\") do hàm `threshold_basis` tạo ra, giống hệt từng ký tự với bản Android."),
);

// ===== 10. Cảnh báo
add(
  H1("10. Cảnh báo và chống nhiễu"),
  P("Mã nguồn: `adas/alert/engine.py` (lớp `AlertManager`). Mức thô mỗi khung có thể nhảy (một khung phát hiện sai, khoảng cách dao động quanh ngưỡng). Nếu cảnh báo theo mức thô, đèn và còi sẽ bật/tắt liên tục. Bộ chống nhiễu (hysteresis) biến mức thô thành **mức ổn định**:"),
  B("**Nâng mức** (an toàn → cảnh báo → nguy hiểm) chỉ khi mức mới kéo dài liên tục ≥ `escalate_seconds` = 0,1 s **và** ít nhất 2 khung. Một khung sai đơn lẻ không gây báo động."),
  B("**Hạ mức** chỉ khi mức thấp hơn kéo dài ≥ `hold_seconds` = 0,8 s kể từ lần cuối mức cao còn đúng."),
  B("Tính theo **thời gian** chứ không theo số khung: điện thoại chạy 10 khung/s cũng cảnh báo kịp như máy tính 30 khung/s."),
  P("Âm thanh được tạo bằng tổng hai sóng sin (âm cơ bản + họa âm bậc 2) có đoạn tăng/giảm âm lượng đầu cuối để không bị \"tạch\":"),
  ...TBL(["Mức", "Tần số", "Độ dài", "Nhịp lặp"], [
    ["NGUY HIỂM", "1250 Hz (cao)", "0,16 s", "mỗi 0,28 s (dồn dập)"],
    ["CẢNH BÁO", "820 Hz (trầm)", "0,22 s", "mỗi 0,9 s (thưa)"],
  ], [2271, 2200, 2000, 2600]),
  P("Màu sắc trên giao diện theo mức: xanh (an toàn), vàng cam (cảnh báo), đỏ (nguy hiểm); viền màn hình phát sáng theo màu mức và một nhãn lớn ở trên. Bản Android còn đọc cảnh báo bằng giọng nói tiếng Việt (cách nhau ít nhất 5 s)."),
);

// ===== 11. Trợ lý AI
add(
  H1("11. Trợ lý AI điều chỉnh ngưỡng"),
  P("Mã nguồn: `adas/assistant/` (offline.py, prompt.py, service.py). Người dùng gõ hoặc bấm nút điều kiện (\"mưa to\", \"sương mù tầm nhìn 80 m\", \"chở nặng ban đêm\", \"tôi đang chạy 100 km/h\"…). Trợ lý trả về một **SafetyPolicy** mới (hệ số thời tiết, ngưỡng TTC, hệ số bám, tầm nhìn…) và có thể cả tốc độ. Bộ tham số được chép vào cấu hình chung; vòng xử lý đọc lại ở khung tiếp theo. Trợ lý chạy **ngoài** vòng xử lý khung nên không làm chậm video."),
  H2("11.1. Chế độ ngoại tuyến (mặc định)"),
  P("Không cần Internet, không tốn phí – phù hợp khi đóng gói ứng dụng. Hàm `offline_advice`:"),
  S("Chuẩn hóa chữ (Unicode NFC, chữ thường), đồng thời tạo bản **bỏ dấu** để nhận cả câu gõ không dấu."),
  S("Dò điều kiện mặt đường (khô, ướt, mưa to, sương mù, trơn) và các yếu tố cộng thêm (đêm, chở nặng, mệt) bằng biểu thức chính quy tiếng Việt. Cụm nhiều từ được so trên cả bản có dấu lẫn bỏ dấu; **từ đơn chỉ được so khi người dùng có gõ dấu**, vì bỏ dấu làm các từ trùng nhau: mù/mưa, mệt/mét, tối/tôi, bão/báo."),
  S("Tách tốc độ (\"100 km/h\", \"chạy 90\") và tầm nhìn (\"tầm nhìn 80 m\"). Chỉ nêu tầm nhìn thì coi là sương mù; sương mù không nêu tầm nhìn thì giả định 100 m."),
  S("Tạo policy bằng `condition_policy` (mục 9.2), giữ nguyên ngưỡng theo dải và time_gap người dùng đã đặt."),
  S("Kẹp tham số trong giới hạn an toàn, tính ngưỡng và soạn câu trả lời (luật ở tốc độ này, ngưỡng cần giữ, tốc độ khuyến nghị nếu tầm nhìn hạn chế)."),
  H2("11.2. Chế độ Claude (tùy chọn)"),
  B("Gọi Claude API (mặc định `claude-haiku-4-5` – rẻ nhất) với lời nhắc hệ thống chứa bảng điều kiện được sinh tự động từ `ROAD_CONDITIONS`, và yêu cầu **đầu ra JSON theo lược đồ cố định** (structured output) nên luôn đọc được thành tham số."),
  B("Luôn bật bảng luật (`use_legal_table = True`), giữ ngưỡng theo dải của người dùng – AI chỉ được **tăng** khoảng cách, không được giảm dưới luật."),
  B("Mọi lỗi (không có mạng, sai khóa API, bị từ chối) đều tự chuyển sang chế độ ngoại tuyến."),
  H2("11.3. Giới hạn an toàn cho tham số"),
  P("Hàm `clamp_policy` kẹp mọi giá trị (từ AI hay từ luật offline) trong khoảng:"),
  ...TBL(["Tham số", "Khoảng cho phép", "Lý do"], [
    ["time_gap_s", "2 – 6 s", "Không thấp hơn quy tắc 2 giây"],
    ["weather_factor", "1,0 – 3,0", "Không bao giờ nhỏ hơn bảng luật đường khô"],
    ["danger_ratio", "0,3 – 0,8", ""], ["min_distance_m", "3 – 20 m", ""],
    ["ttc_warning_s / ttc_danger_s", "2 – 8 s / 1 – 4 s", "ttc_danger luôn nhỏ hơn ttc_warning"],
    ["road_mu", "0,1 – 0,9", ""], ["visibility_m", "0 – 1000 m", "0 = không hạn chế"],
  ], [3000, 2400, 3671]),
);

// ===== 12. Vi phạm & CSDL
add(
  H1("12. Ghi vi phạm và cơ sở dữ liệu"),
  H2("12.1. Ghi vi phạm theo đợt"),
  P("Mã nguồn: `adas/alert/violations.py` (lớp `ViolationRecorder`). Không ghi mỗi khung (30 dòng/giây vô nghĩa), mà mỗi **đợt vi phạm** là một dòng:"),
  B("**Mở đợt** khi mức ổn định chuyển sang CẢNH BÁO/NGUY HIỂM và có xe dẫn đầu: ghi thời điểm, xe (lớp, mã track), khoảng cách, TTC, tốc độ tiếp cận, tốc độ xe mình, hai ngưỡng, mức luật, điều kiện đường, hệ số; chụp ảnh khung có lớp phủ vào `data/snapshots/session_<id>/`."),
  B("**Trong đợt**: cập nhật khoảng cách nhỏ nhất, TTC nhỏ nhất; nếu nâng lên NGUY HIỂM thì cập nhật mức và chụp lại ảnh ở thời điểm nguy hiểm nhất."),
  B("**Đóng đợt** khi trở về AN TOÀN hoặc xe dẫn đầu đổi sang xe khác: ghi thời điểm kết thúc và thời lượng. Nếu chỉ mất dấu xe tạm thời mà vẫn đang cảnh báo thì giữ đợt."),
  H2("12.2. Cơ sở dữ liệu SQLite"),
  P("Mã nguồn: `adas/storage/database.py`, file `data/adas.db`. Mỗi thao tác mở một kết nối ngắn ở chế độ WAL, nên luồng xử lý và luồng giao diện cùng dùng được."),
  ...TBL(["Bảng", "Nội dung"], [
    ["system_config", "Cấu hình hiện hành, mỗi dòng một khóa `mục.khóa` với giá trị JSON"],
    ["config_history", "Lịch sử cấu hình – chỉ thêm dòng khi ảnh chụp cấu hình thực sự thay đổi"],
    ["video_sources", "Các nguồn video đã dùng (đường dẫn chuẩn hóa, duy nhất)"],
    ["camera_calibrations", "Mỗi lần căn chỉnh một dòng: K, H, R, tham số, ghi chú và phương thức – `manual` (chấm 4 điểm), `auto` (quét video), `pose` (trình 3 bước), `online` (tự hoàn thiện khi chạy), `imported` (từ CSDL cũ); dòng mới nhất của mỗi nguồn là đang dùng"],
    ["monitoring_sessions", "Mỗi lần bấm Bắt đầu một phiên, gắn với nguồn video"],
    ["violations", "Các đợt vi phạm (mục 12.1) kèm đường dẫn ảnh"],
  ], [2600, 6471]),
  P("Lược đồ có đánh số phiên bản và tự nâng cấp khi mở (v1→v2 thêm nguồn vào phiên; v2→v3 tách bảng căn chỉnh; v3→v4 dựng lại bảng căn chỉnh để ràng buộc CHECK nhận thêm `pose` và `online`). Lần chạy đầu, file cấu hình cũ `config/settings.json` được nhập vào CSDL."),
);

// ===== 13. Giao diện
add(
  H1("13. Giao diện và đa luồng"),
  H2("13.1. Bố cục cửa sổ chính"),
  B("**Thanh trên**: chọn nguồn (video, camera, ảnh, nguồn gần đây), Bắt đầu/Dừng, Ghi hình, Âm thanh, Căn chỉnh, Lịch sử, Cài đặt. Nếu nguồn chưa được căn chỉnh thì hiện dải nhắc."),
  B("**Bên trái**: video có lớp phủ (hành lang làn trung tính, chỉ phần từ đầu xe tới xe dẫn đầu được tô màu theo mức; vạch ngưỡng nguy hiểm/cảnh báo; khung góc quanh xe; nhãn khoảng cách không chồng lên nhau, nhãn xe dẫn đầu được ưu tiên) và ảnh BEV."),
  B("**Bên phải**: thẻ trạng thái (mức, khoảng cách, ngưỡng giữ tối thiểu và lý do), bảng tốc độ (tự đo hoặc chọn tay), nút điều kiện đường, thẻ \"Trợ lý AI / Vi phạm\"."),
  B("Lúc chưa có khung hình đầu tiên, màn hình chào hướng dẫn 3 bước: chọn nguồn → căn chỉnh → bắt đầu."),
  H2("13.2. Đa luồng"),
  P("Vòng xử lý chạy trong `ProcessingWorker` (QThread, `gui/worker.py`): đọc khung → pipeline → vẽ lớp phủ → ghi vi phạm → gửi kết quả lên giao diện bằng tín hiệu Qt. Giao diện không bao giờ bị đơ khi YOLO chạy."),
  B("Cấu hình `AppConfig` được chia sẻ giữa hai luồng; luôn sửa tại chỗ bằng `update_inplace` chứ không gán đối tượng mới, vì bộ cảnh báo và bộ ước lượng đang giữ tham chiếu tới nó."),
  B("Sau khi căn chỉnh lại, worker được báo để dựng lại H ở khung kế tiếp. Khi bộ tự hoàn thiện (mục 5.2) đưa ra căn chỉnh mới, cửa sổ chính áp dụng và lưu CSDL rồi báo lại cho worker theo cùng đường này; tiến độ 0–100 % và kết quả tự kiểm tra được hiển thị trên giao diện."),
  B("Vẽ bằng QPainter trên QImage chứ không dùng `cv2.putText`, vì OpenCV không vẽ được chữ tiếng Việt có dấu."),
  B("Thanh trạng thái hiển thị thời gian từng tầng (stream / YOLO / IPM / cảnh báo / giao diện) để đánh giá hiệu năng."),
);

// ===== 14. Android
add(
  H1("14. Ứng dụng Android"),
  P("Thư mục `mobile/android`, Kotlin + Jetpack Compose. Phần `core/` là Kotlin thuần, chuyển 1:1 từ Python: IPM, khoảng cách, Kalman, bám vết mẫu, ngưỡng, chống nhiễu, ghi vi phạm, trợ lý offline. Bộ kiểm thử đơn vị so kết quả với dữ liệu mẫu sinh từ bản Python (riêng trợ lý: 342 câu, câu trả lời phải giống hệt từng ký tự)."),
  ...TBL(["Khác biệt", "Cách làm trên Android"], [
    ["Chạy YOLO", "LiteRT (TensorFlow Lite). Lúc khởi động tự đo thử GPU FP16 và CPU INT8 với 1/2/4 luồng, giữ cấu hình nhanh nhất"],
    ["Luồng xử lý", "CameraX chỉ giữ khung mới nhất; YOLO chạy trên luồng nền riêng, kết quả về trễ được bù bằng chuyển động mà tracker đã đo"],
    ["Tốc độ xe", "GPS (bỏ các lần đo có sai số tốc độ > 3 m/s, làm mượt nhẹ, quá 3 s coi là cũ); dự phòng nhập tay"],
    ["Bộ điều tiết (Governor)", "Ba mức Cao / Trung bình / Thấp: bám vết mọi khung / 15 Hz / 10 Hz với 4 / 3 / 2 xe chi tiết; tự hạ khi máy yếu hoặc nóng"],
    ["Vùng nhận diện (ROI)", "Cắt vùng rộng và vùng hẹp ở xa; khi yên ổn, cứ 3 lần YOLO thì 1 lần chạy vùng hẹp để thấy xe nhỏ ở xa"],
    ["Cảnh báo", "Tiếng bíp SoundPool + giọng nói tiếng Việt khi nâng mức"],
    ["Căn chỉnh 3 bước", "Tiêu cự đọc từ thông số ống kính Camera2 (ưu tiên LENS_INTRINSIC_CALIBRATION, không có thì tiêu cự mm × số điểm ảnh / bề rộng cảm biến), nên không cần đoán góc nhìn. Đường chân trời lấy từ cảm biến trọng lực (mục 14.1)"],
    ["Tự hoàn thiện khi chạy", "Cùng thuật toán OnlineCalibrator (90 mẫu). Đầu vào là bộ dò vạch gọn LaneLines trên ảnh xám (mục 14.2), vì bộ nhận diện làn đầy đủ chưa được chuyển"],
    ["Chưa có", "Nhận diện làn đầy đủ (để chọn xe trong làn) và đo tốc độ từ video – dùng hành lang cố định ±1,9 m"],
  ], [2400, 6671]),
  H2("14.1. Đường chân trời từ cảm biến trọng lực"),
  P("Mã nguồn: `core/CameraModel.kt` (hàm `poseFromGravity`), `ui/calibration/CalibrationWizard.kt`. Điện thoại gắn trên kính lái có cảm biến trọng lực (không có thì dùng gia tốc kế đã lọc thông thấp). App đổi vectơ trọng lực sang hệ trục của ảnh camera theo hướng xoay màn hình, được hướng \"xuống đất\" n. Coi camera nhìn thẳng theo hướng xe chạy (góc lệch ngang sẽ được tinh chỉnh khi chạy):"),
  ...EQN([["fwd = chuẩn_hóa( e_z − (e_z · n)·n )", "trục quang học chiếu lên mặt phẳng ngang"],
          ["u_vp = cx + f·fwd_x / fwd_z", "cột điểm tụ"],
          ["v_vp = cy + f·fwd_y / fwd_z", "hàng điểm tụ (đường chân trời)"],
          ["roll = atan2(−n_x, n_y)", "góc nghiêng ngang"]]),
  P("Nếu máy nghiêng quá 20° so với mặt đường, trình căn chỉnh nhắc gắn máy nằm ngang. Đường chân trời đi theo cảm biến theo thời gian thực, người dùng vẫn có thể kéo chỉnh tay."),
  H2("14.2. Bộ dò vạch gọn LaneLines"),
  P("Mã nguồn: `core/LaneLines.kt`. Bộ tự hoàn thiện chỉ cần vị trí 2 vạch trên ảnh, nên trên điện thoại dùng cách nhẹ hơn mục 7, mỗi hàng ảnh chỉ đọc vài chục pixel:"),
  S("Quét các hàng ảnh cách nhau 2 pixel trong đoạn 6–30 m phía trước (theo căn chỉnh đang dùng). Vạch đứt chỉ phủ khoảng 1/3 số hàng nên phải quét dày."),
  S("Ở mỗi hàng và mỗi bên, tìm dải sáng hẹp (vạch sơn sáng hơn cả hai bên ở khoảng cách ~0,3 m) trong cửa sổ quanh vị trí dự kiến: vạch đã thấy ở lần trước, hoặc ±1,875 m theo căn chỉnh."),
  S("Khớp đường thẳng u = a + b·v (bỏ điểm lạc) và kiểm tra độ cong (đường cong chỉ dùng cho hàng điểm tụ). Kiểm tra bề rộng làn hợp lý và làn phải chứa xe mình, giống `_plausible` của bản máy tính."),
  P("Kiểm thử `CalibTest.kt` phát lại từng bước các khung và kết quả do bản Python sinh ra (`calib_python.json`, `lane_python.json`) để bảo đảm hai bản cho cùng kết quả."),
);

// ===== 15. Hạn chế
add(
  H1("15. Giới hạn độ chính xác"),
  B("**Căn chỉnh là bắt buộc**: khoảng cách chỉ có nghĩa sau khi căn chỉnh cho đúng camera đang dùng (trình 3 bước, rồi để app tự hoàn thiện khi chạy). Cấu hình mặc định chỉ là phỏng đoán."),
  B("**Tự hoàn thiện cần điều kiện**: phải thấy rõ 2 vạch làn, chạy trên 30 km/h trong ít nhất 5 s. Nếu không biết tốc độ thật lúc quay, tiêu cự trên máy tính vẫn theo góc nhìn giả định, nên khoảng cách ở xa có thể lệch. Chiều cao tự chỉnh theo làn 3,75 m sẽ sai nếu làn thực tế hẹp hơn."),
  B("**Giả thiết đường phẳng**: dốc, xe nhún khi phanh làm sai H; sai số tăng theo bình phương khoảng cách, đáng tin tới khoảng 80–100 m."),
  B("**Tốc độ từ video phụ thuộc căn chỉnh**: với căn chỉnh tay cũ, video thử đo ~55 km/h trong khi GPS ~74 km/h; căn chỉnh tự động chỉ lệch −6 %."),
  B("**Dữ liệu huấn luyện**: chủ yếu cảnh đô thị ban đêm, và 92 % ảnh kiểm thử là khung liền kề ảnh huấn luyện nên mAP 0,819 có thể lạc quan hơn thực tế."),
  B("**Ngưỡng thời tiết là ước tính**: luật không nêu số cho điều kiện bất lợi; hệ số dựa trên hệ số bám μ ước tính."),
  B("**Android** chưa được đo trên điện thoại thật về tốc độ GPU, bản phát hành (R8), hướng ảnh và giọng nói tiếng Việt."),
);

// ---------------------------------------------------------------- tài liệu
const doc = new Document({
  creator: "ADAS", title: "Giải thích chức năng và thuật toán ADAS",
  features: { updateFields: true },
  styles: {
    default: { document: { run: { font: FONT, size: 26 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: FONT, color: ACCENT },
        paragraph: { spacing: { before: 240, after: 200 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: FONT, color: "2E74B5" },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, italics: true, font: FONT },
        paragraph: { spacing: { before: 160, after: 80 }, outlineLevel: 2 } },
    ],
  },
  numbering: { config: [
    { reference: "bullets", levels: [
      { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 567, hanging: 283 } } } },
      { level: 1, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 1134, hanging: 283 } } } }] },
    { reference: "steps", levels: [
      { level: 0, format: LevelFormat.DECIMAL, text: "Bước %1.", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 1134, hanging: 1000 } }, run: { bold: true } } }] },
  ] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 },
      margin: { top: 1134, bottom: 1134, left: 1701, right: 1134 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ children: [PageNumber.CURRENT], size: 22 })] })] }) },
    children: body,
  }],
});

Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(OUT, buf); console.log("Đã ghi", OUT); });
