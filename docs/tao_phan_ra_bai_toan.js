// Tạo báo cáo Word: phân rã bài toán ADAS thành 4 bài toán con và cách em giải từng bài.
// Chạy: NODE_PATH=<thư mục node_modules có docx@9> node tao_phan_ra_bai_toan.js [PHAN_RA_BAI_TOAN.docx]
// Hình minh họa: python docs/hinh_phan_ra/ve_hinh.py (chạy trước).
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType, ShadingType,
  AlignmentType, BorderStyle, LevelFormat, Footer, PageNumber, VerticalAlign, ImageRun,
} = require("docx");

const OUT = process.argv[2] || "PHAN_RA_BAI_TOAN.docx";
const HINH = path.join(__dirname, "hinh_phan_ra");
const FONT = "Times New Roman";

// ---------------------------------------------------------------- tiện ích
// Đánh dấu trong chuỗi: **đậm**, *nghiêng*
function runs(text, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), ...base }));
    const s = m[0];
    if (s.startsWith("**")) out.push(new TextRun({ text: s.slice(2, -2), bold: true, ...base }));
    else out.push(new TextRun({ text: s.slice(1, -1), italics: true, ...base }));
    last = m.index + s.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), ...base }));
  return out;
}

let stepInst = 0, inSteps = false;      // mỗi danh sách bước đánh số lại từ 1
const brk = (x) => { inSteps = false; return x; };
const P = (text) => brk(new Paragraph({
  children: runs(text), spacing: { after: 120, line: 312 }, alignment: AlignmentType.JUSTIFIED,
  indent: { firstLine: 567 },
}));
const B = (text) => brk(new Paragraph({
  children: runs(text), numbering: { reference: "bullets", level: 0 },
  alignment: AlignmentType.JUSTIFIED, spacing: { after: 60, line: 300 },
}));
const S = (text) => {                   // bước đánh số
  if (!inSteps) { stepInst++; inSteps = true; }
  return new Paragraph({
    children: runs(text), numbering: { reference: "steps", level: 0, instance: stepInst },
    alignment: AlignmentType.JUSTIFIED, spacing: { after: 60, line: 300 },
  });
};
const H1 = (t, br = false) => brk(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)], pageBreakBefore: br }));
const H3 = (t) => brk(new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(t)] }));
const H2 = (t) => brk(new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] }));
const EQ = (...lines) => { inSteps = false; return lines.map((l) => new Paragraph({
  alignment: AlignmentType.CENTER, spacing: { before: 60, after: 60 },
  children: [new TextRun({ text: l, font: "Cambria Math", size: 24 })],
})); };
const IMG = (file, w, h, cap) => { inSteps = false; return [
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 }, keepNext: true,
    children: [new ImageRun({ type: "png", data: fs.readFileSync(path.join(HINH, file)), transformation: { width: w, height: h } })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
    children: [new TextRun({ text: cap, italics: true, size: 24 })] }),
]; };

const cellBorder = { style: BorderStyle.SINGLE, size: 4, color: "808080" };
const borders = { top: cellBorder, bottom: cellBorder, left: cellBorder, right: cellBorder };
function TBL(headers, rows, widths) {
  inSteps = false;
  const mk = (txt, w, head) => new TableCell({
    borders, width: { size: w, type: WidthType.DXA }, verticalAlign: VerticalAlign.CENTER,
    shading: head ? { type: ShadingType.CLEAR, fill: "F2F2F2", color: "auto" } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({ alignment: AlignmentType.CENTER, children: runs(String(txt), head ? { bold: true } : {}), spacing: { after: 0 } })],
  });
  return [new Table({
    alignment: AlignmentType.CENTER, width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA }, columnWidths: widths,
    rows: [new TableRow({ children: headers.map((h, i) => mk(h, widths[i], true)) }),
      ...rows.map((r) => new TableRow({ children: r.map((c, i) => mk(c, widths[i], false)) }))],
  }), new Paragraph({ spacing: { after: 120 }, children: [] })];
}

const body = [];
const add = (...xs) => xs.forEach((x) => (Array.isArray(x) ? body.push(...x) : body.push(x)));

// ===== Mở đầu
add(
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 200, after: 360 },
    children: [new TextRun({ text: "PHÂN RÃ BÀI TOÁN VÀ CÁCH EM GIẢI QUYẾT", bold: true, size: 32 })] }),
  H1("Mở đầu"),
  P("Đề tài của em là phần mềm dùng camera hành trình để cảnh báo khi xe mình đi quá gần xe phía trước. Camera chỉ cho ra ảnh. Ảnh không cho biết đâu là xe, xe cách bao xa hay mình đang chạy bao nhanh. Vì vậy em chia thành 4 bài toán nhỏ:"),
  B("Nhận diện xe: tìm các xe trong ảnh."),
  B("Đo khoảng cách: đổi vị trí xe trong ảnh ra mét."),
  B("Tính tốc độ xe mình: vì khoảng cách an toàn phụ thuộc tốc độ."),
  B("Chatbot: tài xế nói điều kiện đường (mưa, sương mù...), phần mềm tự chỉnh ngưỡng cảnh báo."),
  P("Ba bài đầu chạy nối tiếp nhau trên mỗi khung hình. Bài thứ tư chạy riêng, nó chỉ sửa ngưỡng cảnh báo."),
);

// ===== 1. Nhận diện xe
add(
  H1("1. Nhận diện xe"),
  P("Ở mỗi khung hình, em cần khoanh từng xe bằng một hộp chữ nhật (gọi là hộp bao) và biết đó là loại xe gì. Em cũng cần biết chiếc xe ở khung này có phải chiếc ở khung trước không, để theo dõi khoảng cách tới nó."),
  H2("1.1. Dùng YOLOv11"),
  P("Em dùng YOLOv11, một mạng nơ-ron chuyên tìm vật thể trong ảnh. Ảnh chỉ cần đi qua mạng một lần là ra hết các hộp, nên đủ nhanh cho video 30 khung/giây."),
  P("Bản YOLO gốc học trên 80 loại đồ vật. Em huấn luyện thêm cho nó trên bộ ảnh giao thông gồm 5 loại: ô tô, xe buýt, xe tải, xe máy và Jeepney. Cách này gọi là học chuyển giao. Mô hình đã biết nhìn hình dạng từ trước nên chỉ cần ít ảnh để học thêm."),
  P("Để biết xe nào là xe nào, em dùng thuật toán ByteTrack. Nó đoán vị trí mới của từng xe, rồi ghép với hộp mới nào chồng lên chỗ đoán nhiều nhất. Nhờ vậy mỗi xe giữ một mã số (ID) cố định."),
  H2("1.2. Chạy nhanh hơn trên máy yếu"),
  P("Trên máy không có card đồ họa, YOLO mất khoảng 40 ms mỗi lần, lâu hơn thời gian một khung hình (33 ms). Vì vậy em chỉ chạy YOLO 3 khung một lần. Ở các khung giữa, em cắt một miếng ảnh nhỏ của mỗi xe rồi tìm chỗ giống nó nhất ở khung sau (so khớp mẫu). Giữa hai khung xe chỉ xê dịch một chút, nên cách này nhanh hơn YOLO nhiều."),
  P("Kết quả: thời gian nhận diện giảm từ 10 ms xuống 5,3 ms mỗi khung, mà 98 % số khung vẫn cho cùng mức cảnh báo như khi chạy YOLO ở mọi khung. Trên điện thoại, em đổi mô hình sang TensorFlow Lite, và máy tự chọn chạy bằng GPU hay CPU tùy cái nào nhanh hơn."),
  P("Hạn chế: bộ dữ liệu huấn luyện chủ yếu là đường phố ban đêm, còn ít cảnh cao tốc ban ngày."),
);

// ===== 2. Đo khoảng cách
add(
  H1("2. Đo khoảng cách tới xe khác"),
  P("Bài toán 1 cho vị trí xe tính bằng điểm ảnh. Em cần đổi ra mét: xe cách cản trước xe mình bao xa, và lệch sang trái hay phải bao nhiêu."),
  H2("2.1. Ý tưởng"),
  P("Camera chỉ có một mắt nên không đo trực tiếp được độ sâu. Nhưng em dựa vào hai điều: bánh xe luôn chạm mặt đường, và đường cao tốc gần như phẳng. Trên mặt phẳng, mỗi điểm trong ảnh ứng với đúng một điểm ngoài đường. Điểm càng gần đường chân trời thì càng xa. Em tính theo 3 bước:"),
  S("Lấy trung điểm cạnh dưới hộp bao, là chỗ bánh xe chạm đất."),
  S("Dùng IPM đổi điểm đó ra mét."),
  S("Dùng bộ lọc Kalman để khoảng cách ổn định giữa các khung."),
  H2("2.2. IPM: đổi điểm ảnh ra mét"),
  P("IPM là phép biến đổi phối cảnh ngược. Chụp xiên một tờ giấy hình chữ nhật thì trong ảnh nó thành hình thang. Nếu biết 4 góc của hình thang và kích thước thật của tờ giấy, ta tính được một ma trận H (3×3) để kéo hình thang về lại hình chữ nhật."),
  P("Với mặt đường, em thay tờ giấy bằng một đoạn làn xe. Làn cao tốc rộng 3,75 m. Em lấy đoạn dài 30 m, bắt đầu cách xe mình 6 m. Em chọn 4 điểm trên hai mép làn trong ảnh, rồi dùng OpenCV tính ra H. Sau đó đổi một điểm ảnh (u, v) ra mét như sau:"),
  ...EQ("[x′, y′, w′] = H · [u, v, 1]",
        "X = x′ / w′   (lệch ngang)        Y = y′ / w′   (khoảng cách)"),
  P("Phép chia cho w′ tạo ra hiệu ứng xa gần: điểm càng gần chân trời thì w′ càng nhỏ, nên Y càng lớn."),
  ...IMG("h1_ipm.png", 600, 251, "Hình 1. Đổi điểm chạm đất của xe trong ảnh ra mét bằng IPM"),
  P("Ví dụ ở Hình 1: bánh xe phía trước nằm ở điểm ảnh (330; 226), đổi ra X = 0,76 m, Y = 32,3 m. Tức là xe cách mình 32,3 m, lệch phải 0,76 m, vẫn nằm trong làn mình."),
  P("Hình 1 cũng cho thấy chỗ yếu của IPM. Đoạn từ 10 đến 20 m chiếm 39 hàng ảnh, nhưng đoạn từ 60 đến 100 m chỉ còn 6 hàng. Ở xa, lệch 1 điểm ảnh là sai vài mét, nên em chỉ tin IPM tới khoảng 80–100 m."),
  H2("2.3. Kalman: làm khoảng cách ổn định"),
  P("Hộp bao của YOLO mỗi khung xê dịch vài điểm ảnh, nên khoảng cách nhảy khoảng ±4 %. Ở 40 m là ±1,6 m. Nếu lấy hiệu hai khung để tính xe trước đang lại gần nhanh cỡ nào thì sai tới gần 50 m/s, không dùng được (đường màu xám ở Hình 2)."),
  P("Bộ lọc Kalman giữ cho mỗi xe ba con số: khoảng cách d, tốc độ thay đổi khoảng cách v và gia tốc a. Ở mỗi khung, nó làm hai việc:"),
  S("**Đoán:** tính khoảng cách hiện tại từ ba con số ở khung trước: d mới = d + v·Δt + ½·a·Δt²."),
  S("**Sửa:** so với số đo IPM mới, rồi dịch kết quả về phía số đo: d = d đoán + K·(số đo − d đoán). K nằm từ 0 đến 1. Số đo càng nhiễu thì K càng nhỏ, tức là càng tin lời đoán."),
  P("Nhờ vậy em có khoảng cách mượt, và có luôn tốc độ lại gần (bằng −v). Từ đó em tính thời gian đến va chạm: TTC = khoảng cách ÷ tốc độ lại gần. Ví dụ xe cách 30 m, lại gần với tốc độ 10 m/s thì TTC = 3 giây. Số đo nào lệch quá xa lời đoán (thường do YOLO nhầm) thì bị bỏ qua."),
  ...IMG("h2_kalman.png", 600, 372, "Hình 2. Xe phía trước cách 40 m, phanh gấp ở giây thứ 2"),
  P("Em đưa gia tốc vào mô hình vì khi xe trước phanh gấp, bộ lọc nhận ra sau khoảng 0,4 giây. Bản không có gia tốc phải mất 1,1 giây."),
  H2("2.4. Căn chỉnh camera"),
  P("Ma trận H phụ thuộc camera gắn cao bao nhiêu và chúc xuống bao nhiêu, nên mỗi camera phải căn chỉnh một lần. Em làm 3 cách:"),
  B("Chấm tay 4 điểm lên hai mép làn."),
  B("Căn chỉnh 3 bước: người dùng chọn loại xe để biết chiều cao camera. Phần mềm tự tìm đường chân trời là chỗ các vạch kẻ đường kéo dài gặp nhau (trên điện thoại thì dùng cảm biến trọng lực), rồi tự tính ra 4 điểm."),
  B("Tự căn chỉnh khi xe chạy: phần mềm tự tìm vạch làn, rồi chỉnh sao cho bề rộng làn đo ra đúng 3,75 m."),
  H2("2.5. Chọn xe để cảnh báo"),
  P("Chỉ xe ngay phía trước, trong làn của mình, mới cần cảnh báo. Em dùng H để biến ảnh thành ảnh nhìn từ trên xuống. Ở ảnh này hai vạch làn gần như thẳng đứng nên dễ tìm. Xe gần nhất nằm giữa hai vạch là xe được cảnh báo. Khi chưa thấy vạch, em lấy một hành lang rộng 3,8 m quanh xe mình."),
);

// ===== 3. Tốc độ xe mình
add(
  H1("3. Tính tốc độ xe mình"),
  P("Chạy 60 km/h thì luật yêu cầu giữ ít nhất 35 m, chạy 110 km/h thì 100 m. Phần mềm không đọc được đồng hồ của xe. Điện thoại thì có GPS, nhưng video mở trên máy tính chỉ có hình ảnh, nên em phải đo tốc độ từ video."),
  H2("3.1. Ý tưởng"),
  P("Vạch kẻ đứt đứng yên trên mặt đường. Khi xe chạy, các vạch trôi dần về phía camera. Nhờ IPM, em biết mỗi vạch đang cách xe bao nhiêu mét. Vậy chỉ cần đo vạch trôi được bao xa trong một khoảng thời gian: tốc độ = quãng trôi ÷ thời gian."),
  ...IMG("h3_toc_do.png", 600, 180, "Hình 3. Độ sáng dọc theo vạch kẻ ở hai thời điểm cách nhau 0,1 s"),
  P("Ví dụ ở Hình 3: sau 0,1 giây vạch trôi 2,2 m, nên tốc độ là 22 m/s, khoảng 80 km/h."),
  H2("3.2. Cách làm"),
  S("Dọc theo mỗi vạch làn, trong đoạn 5–26 m trước xe, em đọc độ sáng theo từng mét. Chỗ có sơn thì sáng, chỗ trống thì tối."),
  S("Em chỉ dùng vạch đứt. Vạch liền trôi bao nhiêu trông vẫn y như cũ, nên sẽ đo ra tốc độ bằng 0."),
  S("Em so dãy độ sáng hiện tại với dãy của 0,1–0,4 giây trước để tìm độ dịch khớp nhất. Lấy độ dịch chia cho thời gian là ra tốc độ."),
  S("Mỗi lần đo lệch tới ±8 km/h, nên em lấy trung vị các lần đo trong 1 giây rồi làm mượt."),
  P("So với tốc độ GPS hiện trên video thử, cách này sai trung bình khoảng 1,3 km/h. Hạn chế là nó chỉ đúng khi căn chỉnh đúng, và không đo được khi đường không có vạch đứt. Lúc đó phần mềm dùng tốc độ người dùng nhập."),
  P("Trên điện thoại, em lấy tốc độ từ GPS. Em còn so GPS với tốc độ đo từ vạch kẻ. Nếu video đo ra chậm hơn GPS 10 % thì căn chỉnh đang sai khoảng 10 %, và phần mềm tự sửa lại."),
);

// ===== 4. Chatbot
add(
  H1("4. Chatbot hỗ trợ lái xe"),
  P("Khoảng cách an toàn trong luật được tính cho đường khô. Khi mưa, sương mù hay đường trơn thì quãng phanh dài hơn, nên phải giữ xa hơn. Đang lái thì tài xế không thể chỉnh từng thông số. Vì vậy em làm chatbot: tài xế chỉ cần gõ \"trời mưa to, chở nặng\" là phần mềm tự đổi ngưỡng."),
  P("Chatbot chỉ làm một việc: đọc câu tiếng Việt rồi cho ra bộ thông số (hệ số thời tiết, ngưỡng thời gian va chạm, tầm nhìn, tốc độ), kèm một câu trả lời ngắn. Em làm hai cách."),
  H2("4.1. Không cần mạng (mặc định)"),
  P("Em dùng regex để dò các cụm từ như \"mưa to\", \"sương mù\", \"đường trơn\", \"ban đêm\", \"chở nặng\". Em so khớp cả câu có dấu lẫn câu đã bỏ dấu, để người gõ không dấu cũng dùng được."),
  P("Quãng phanh tỉ lệ nghịch với độ bám của mặt đường, nên em đặt hệ số theo độ bám: đường ướt × 1,4; mưa to × 2; đường trơn × 2,5. Các yếu tố khác nhân thêm: ban đêm × 1,2; chở nặng × 1,3; tài xế mệt × 1,15. Hệ số tổng không quá 3."),
  P("Ví dụ câu \"mưa to, chở nặng\" cho hệ số 2 × 1,3 = 2,6. Khi chạy 100 km/h, luật yêu cầu 70 m, nhân lên thành 70 × 2,6 = 182 m."),
  H2("4.2. Dùng Claude (tùy chọn)"),
  P("Bộ luật chỉ hiểu những cụm từ em đã viết sẵn. Với câu lạ, em gửi sang Claude, một mô hình ngôn ngữ lớn hiểu được tiếng Việt tự do. Em gửi kèm luật khoảng cách và bảng hệ số. Em yêu cầu Claude trả về đúng một khối JSON theo mẫu có sẵn, để phần mềm đọc được thông số."),
  P("Phần mềm vẫn kiểm tra lại mọi giá trị và không bao giờ cho ngưỡng thấp hơn mức luật, nên Claude có trả lời sai cũng không gây nguy hiểm. Mất mạng thì phần mềm tự quay về bộ luật."),
  P("Gọi Claude có thể mất vài giây, nên chatbot chạy ngoài vòng xử lý khung hình. Nó chỉ ghi ngưỡng mới vào cấu hình, và khung hình sau tự dùng ngưỡng đó."),
);

// ===== 5. Ghép lại
add(
  H1("5. Ghép các bài toán lại"),
  P("Có khoảng cách và tốc độ rồi, em tính ngưỡng an toàn. Từ 60 km/h trở lên, em lấy theo bảng của luật:"),
  ...TBL(["Tốc độ (km/h)", "60", "trên 60 đến 80", "trên 80 đến 100", "trên 100 đến 120"],
    [["Khoảng cách tối thiểu (m)", "35", "55", "70", "100"]], [2400, 1200, 1800, 1800, 1871]),
  P("Dưới 60 km/h, em dùng quy tắc 2 giây. Ngưỡng này nhân với hệ số thời tiết từ chatbot là ra ngưỡng cảnh báo (màu vàng). Ngưỡng nguy hiểm (màu đỏ) ngắn hơn, bằng một tỉ lệ của ngưỡng cảnh báo. Nếu TTC quá ngắn thì phần mềm cũng cảnh báo."),
  P("Khi khoảng cách dao động quanh ngưỡng, đèn cảnh báo dễ bị nhấp nháy. Để tránh việc này, em chỉ tăng mức khi mức mới kéo dài ít nhất 0,1 giây, và chờ thêm một lúc mới hạ mức."),
  P("Tóm lại, nhận diện cho vị trí xe, IPM đổi vị trí đó ra mét, tốc độ quyết định ngưỡng, còn chatbot chỉnh ngưỡng theo điều kiện đường. Việc em còn phải làm: bổ sung dữ liệu cao tốc ban ngày, xử lý đường dốc và thử trên xe thật."),
);

// ---------------------------------------------------------------- tài liệu
const doc = new Document({
  creator: "ADAS", title: "Phân rã bài toán ADAS",
  styles: {
    default: { document: { run: { font: FONT, size: 26 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 30, bold: true, font: FONT },
        paragraph: { spacing: { before: 240, after: 160 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 27, bold: true, font: FONT },
        paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, italics: true, font: FONT },
        paragraph: { spacing: { before: 160, after: 80 }, outlineLevel: 2 } },
    ],
  },
  numbering: { config: [
    { reference: "bullets", levels: [
      { level: 0, format: LevelFormat.BULLET, text: "-", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 851, hanging: 284 } } } }] },
    { reference: "steps", levels: [
      { level: 0, format: LevelFormat.DECIMAL, text: "%1)", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 851, hanging: 284 } } } }] },
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
