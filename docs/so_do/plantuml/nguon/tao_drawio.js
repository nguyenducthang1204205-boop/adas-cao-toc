// Chuyển mỗi sơ đồ PlantUML (nguon/*.puml) thành một file draw.io có HÌNH GỐC sửa được từng phần,
// giống hệt thao tác trong draw.io: Sắp xếp > Chèn > Nâng cao > PlantUML… > "Biểu đồ".
//
//   node nguon/tao_drawio.js [tiền tố…]          (vd: node nguon/tao_drawio.js 15 21)
//
// Bộ chuyển là file js/plantuml/drawio-plantuml.min.js trong mã nguồn mở của draw.io
// (https://github.com/jgraph/drawio, Apache-2.0) – chính là đoạn mã app.diagrams.net dùng.
// Kết quả: drawio/<tên>.drawio (mỗi sơ đồ một file) + drawio/_bao_cao_chuyen_doi.txt.
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const prefixes = process.argv.slice(2);
const libPath = path.join(__dirname, 'drawio-plantuml.min.js');
const ctx = { console };
ctx.globalThis = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(libPath, 'utf8'), ctx, { filename: 'drawio-plantuml.min.js' });
const conv = ctx.mxPlantUmlToDrawio;

const SRC = __dirname;
const OUT = path.join(SRC, '..', 'drawio');
fs.mkdirSync(OUT, { recursive: true });

const esc = (s) => s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const files = fs.readdirSync(SRC).filter((f) => f.endsWith('.puml') && (!prefixes.length || prefixes.some((p) => f.startsWith(p)))).sort();
const report = [];
let bad = 0;
for (const f of files) {
  const name = f.replace(/\.puml$/, '');
  const text = fs.readFileSync(path.join(SRC, f), 'utf8').replace(/^﻿/, '').replace(/\r\n/g, '\n');
  let model;
  try {
    model = conv.parseText(text);
  } catch (e) {
    bad += 1;
    report.push(`[LỖI] ${name}: ${e.message}`);
    continue;
  }
  const warn = (conv.lastWarnings || []).map((w) => (typeof w === 'string' ? w : JSON.stringify(w)));
  const cells = (model.match(/<mxCell /g) || []).length;
  const imageOnly = /shape=image/.test(model) && cells < 6;
  const xml = `<mxfile host="drawio-plantuml" type="device">\n  <diagram id="${esc(name)}" name="${esc(name)}">\n${model.trim()}\n  </diagram>\n</mxfile>\n`;
  fs.writeFileSync(path.join(OUT, `${name}.drawio`), xml, 'utf8');
  report.push(`[${imageOnly ? 'ẢNH' : 'OK'}] ${name}: ${cells} ô${warn.length ? `, ${warn.length} cảnh báo: ${warn.join(' | ')}` : ''}`);
  if (imageOnly) bad += 1;
}
fs.writeFileSync(path.join(OUT, '_bao_cao_chuyen_doi.txt'), report.join('\n') + '\n', 'utf8');
console.log(report.join('\n'));
console.log(`\n${files.length} sơ đồ, ${bad} cần xem lại -> ${OUT}`);
