/// Bám vết dày giữa các lần chạy YOLO (port 1:1 của adas/tracking.py - xem đó để biết thuật toán).
///
/// Trên điện thoại YOLO chạy nền bất cứ khi nào rảnh, còn tracker chạy trên MỌI khung camera. Kết quả YOLO
/// về trễ (chụp lúc detT < t) được ghép với track theo lịch sử hộp và dời theo chuyển động đã đo từ detT.
library;

import 'dart:math' as math;
import 'dart:typed_data';

import 'yolo.dart';

const workW = 640; // ảnh xám làm việc rộng tối đa 640 px
const grid = 16; // lưới mẫu tối đa grid x grid điểm
const scales = [0.97, 1.0, 1.03];
const minNcc = 0.6;
const searchBase = 4.0;
const searchRel = 0.08;
const searchMax = 10;
const maxTracked = 4; // chỉ bám chi tiết các xe gần nhất
const coastMaxS = 0.5;
const maxYoloMisses = 2; // YOLO bỏ sót 1 lần: bám tiếp; 2 lần liên tiếp: bỏ (tránh "xe ma")
const historyLen = 64;

double workScale(int frameW) => math.min(1.0, workW / frameW);

/// Ảnh xám (giá trị 0..255) ở độ phân giải làm việc.
class GrayImage {
  final int width, height;
  final Float32List data;
  GrayImage(this.width, this.height, this.data);

  /// Nội suy song tuyến, tọa độ bị kẹp trong ảnh (giống _sample của tracking.py).
  double at(double x, double y) {
    if (x < 0) x = 0;
    if (y < 0) y = 0;
    final xm = width - 1.001, ym = height - 1.001;
    if (x > xm) x = xm;
    if (y > ym) y = ym;
    final x0 = x.floor(), y0 = y.floor();
    final fx = x - x0, fy = y - y0;
    final i = y0 * width + x0;
    final v00 = data[i], v01 = data[i + 1], v10 = data[i + width], v11 = data[i + width + 1];
    return (v00 * (1 - fx) + v01 * fx) * (1 - fy) + (v10 * (1 - fx) + v11 * fx) * fy;
  }
}

class _Track {
  final int id;
  Detection det; // hộp hiện tại (pixel khung gốc)
  final Float32List template; // mẫu neo đã chuẩn hóa
  final int nx, ny;
  final double anchorW, anchorH; // px ảnh làm việc
  double scale = 1.0;
  double lastMeasT;
  double ncc = 1.0;
  int yoloMisses = 0;
  final history = <(double, List<double>)>[];

  _Track(this.id, this.det, this.template, this.nx, this.ny, this.anchorW, this.anchorH, this.lastMeasT);

  List<double> get box => [det.x1, det.y1, det.x2, det.y2];

  void remember(double t) {
    history.add((t, box));
    if (history.length > historyLen) history.removeAt(0);
  }
}

class TemplateTracker {
  final tracks = <int, _Track>{};
  int _nextId = 1;
  double k = 1.0;

  /// Số xe gần nhất được so khớp mẫu mỗi khung (bộ điều tốc giảm trên máy yếu; mặc định như tracking.py).
  int trackedLimit = maxTracked;

  void reset() => tracks.clear();

  /// Kết quả YOLO mới (chụp lúc [detT], mặc định = [t]): ghép track, neo lại mẫu ở khung hiện tại.
  /// Trả về các hộp hiện tại: detection YOLO (đã gán id, dời theo chuyển động nếu về trễ) + các track
  /// YOLO bỏ sót lần này (bám tiếp trên khung này).
  ///
  /// [roi] (x1, y1, x2, y2 pixel khung gốc): YOLO chỉ nhìn vùng này (khung khóa hẹp cho xe ở xa). Track không
  /// nằm trọn trong vùng không bị tính là "YOLO bỏ sót" - chỉ bám tiếp như khung thường.
  List<Detection> refresh(List<Detection> dets, GrayImage gray, double t, double scaleK,
      {double? detT, List<double>? roi}) {
    k = scaleK;
    final dt0 = detT ?? t;
    final used = <int>{};
    final out = <Detection>[];
    for (final d in dets) {
      var box = [d.x1, d.y1, d.x2, d.y2];
      _Track? tr = d.trackId != null ? tracks[d.trackId] : null;
      if (tr == null && d.trackId == null) tr = _matchIou(box, d.classId, dt0, used);
      if (tr != null && dt0 < t) {
        final past = _boxAt(tr, dt0);
        if (past != null) {
          final now = tr.box;
          box = [for (var i = 0; i < 4; i++) box[i] + (now[i] - past[i])];
        }
      }
      final id = d.trackId ?? tr?.id ?? _nextId++;
      final det = Detection(box[0], box[1], box[2], box[3], d.confidence, d.classId, d.className, id)
        ..source = 'yolo';
      out.add(det);
      used.add(id);
      final nt = _anchor(id, det, gray, t);
      if (nt == null) {
        tracks.remove(id); // không lấy được mẫu: vẫn báo xe ở khung này, không bám tiếp
        continue;
      }
      if (tr != null) nt.history.addAll(tr.history);
      nt.remember(t);
      tracks[id] = nt;
    }
    for (final id in tracks.keys.toList()) {
      if (used.contains(id)) continue;
      final tr = tracks[id]!;
      if (roi == null || _inside(tr.box, roi)) tr.yoloMisses++;
      if (tr.yoloMisses >= maxYoloMisses) {
        tracks.remove(id);
        continue;
      }
      _step(tr, gray, t);
      if (tr.det.source == 'coast' && t - tr.lastMeasT > coastMaxS) {
        tracks.remove(id);
        continue;
      }
      tr.remember(t);
      out.add(tr.det);
    }
    return out;
  }

  /// Khung không có kết quả YOLO mới: đo lại vị trí các xe bằng so khớp mẫu.
  List<Detection> track(GrayImage gray, double t) {
    final order = tracks.values.toList()..sort((a, b) => b.det.y2.compareTo(a.det.y2)); // gần trước
    final out = <Detection>[];
    for (var i = 0; i < order.length; i++) {
      final tr = order[i];
      if (i < trackedLimit) {
        _step(tr, gray, t);
      } else {
        tr.det = _withSource(tr.det, 'coast');
      }
      if (tr.det.source == 'coast' && t - tr.lastMeasT > coastMaxS) {
        tracks.remove(tr.id);
        continue;
      }
      tr.remember(t);
      out.add(tr.det);
    }
    return out;
  }

  _Track? _matchIou(List<double> box, int cls, double t, Set<int> used) {
    _Track? best;
    var bestIou = 0.3;
    for (final tr in tracks.values) {
      if (used.contains(tr.id) || tr.det.classId != cls) continue;
      final past = _boxAt(tr, t);
      if (past == null) continue;
      final v = _iou(box, past);
      if (v > bestIou) {
        best = tr;
        bestIou = v;
      }
    }
    return best;
  }

  static List<double>? _boxAt(_Track tr, double t) {
    if (tr.history.isEmpty) return null;
    var best = tr.history.first;
    for (final e in tr.history) {
      if ((e.$1 - t).abs() < (best.$1 - t).abs()) best = e;
    }
    return best.$2;
  }

  _Track? _anchor(int id, Detection det, GrayImage gray, double t) {
    final x1 = det.x1 * k, y1 = det.y1 * k, x2 = det.x2 * k, y2 = det.y2 * k;
    final bw = x2 - x1, bh = y2 - y1;
    if (bw < 4 || bh < 4) return null;
    final nx = (bw + 0.5).floor().clamp(4, grid), ny = (bh + 0.5).floor().clamp(4, grid);
    final v = Float32List(nx * ny);
    _sampleInto(gray, (x1 + x2) / 2, (y1 + y2) / 2, bw, bh, nx, ny, v);
    var mean = 0.0;
    for (final e in v) {
      mean += e;
    }
    mean /= v.length;
    var varSum = 0.0;
    for (final e in v) {
      varSum += (e - mean) * (e - mean);
    }
    if (math.sqrt(varSum / v.length) < 2.0) return null; // mẫu phẳng (đêm tối, sương): không bám được
    _normalize(v);
    return _Track(id, det, v, nx, ny, bw, bh, t);
  }

  /// NCC giữa mẫu neo và lưới lấy ở hộp tâm (cx, cy) cỡ bw x bh.
  double _ncc(_Track tr, GrayImage gray, double cx, double cy, double bw, double bh, Float32List buf) {
    _sampleInto(gray, cx, cy, bw, bh, tr.nx, tr.ny, buf);
    var mean = 0.0;
    for (final e in buf) {
      mean += e;
    }
    mean /= buf.length;
    var dot = 0.0, norm = 0.0;
    final tpl = tr.template;
    for (var i = 0; i < buf.length; i++) {
      final c = buf[i] - mean;
      dot += c * tpl[i];
      norm += c * c;
    }
    return dot / math.max(math.sqrt(norm), 1e-6);
  }

  void _step(_Track tr, GrayImage gray, double t) {
    final x1 = tr.det.x1 * k, y1 = tr.det.y1 * k, x2 = tr.det.x2 * k, y2 = tr.det.y2 * k;
    final cx = (x1 + x2) / 2, cy = (y1 + y2) / 2;
    final bw0 = tr.anchorW * tr.scale, bh0 = tr.anchorH * tr.scale;
    final r = math.min(searchMax, (searchBase + searchRel * math.max(bw0, bh0)).ceil());
    final buf = Float32List(tr.nx * tr.ny);
    // dò thô vị trí (bước 2 px) ở tỉ lệ hiện tại; thứ tự duyệt giống numpy (hàng dy ngoài, cột dx trong)
    var best = -2.0, bx = 0, by = 0;
    for (var dy = -r; dy <= r; dy += 2) {
      for (var dx = -r; dx <= r; dx += 2) {
        final c = _ncc(tr, gray, cx + dx, cy + dy, bw0, bh0, buf);
        if (c > best) {
          best = c;
          bx = dx;
          by = dy;
        }
      }
    }
    // dò tinh ±1 px x 3 tỉ lệ quanh điểm tốt nhất + nội suy parabol theo bảng 3x3 của tỉ lệ được chọn
    var bj = -2.0, jx = 1, jy = 1;
    var bs = 1.0;
    var c = List.generate(3, (_) => List<double>.filled(3, 0));
    for (final s in scales) {
      final cs = List.generate(3, (_) => List<double>.filled(3, 0));
      var sj = -2.0, sx = 1, sy = 1;
      for (var fy = 0; fy < 3; fy++) {
        for (var fx = 0; fx < 3; fx++) {
          final v = _ncc(tr, gray, cx + bx + fx - 1, cy + by + fy - 1, bw0 * s, bh0 * s, buf);
          cs[fy][fx] = v;
          if (v > sj) {
            sj = v;
            sx = fx;
            sy = fy;
          }
        }
      }
      if (sj > bj) {
        bj = sj;
        jx = sx;
        jy = sy;
        bs = s;
        c = cs;
      }
    }
    var ox = (bx + jx - 1).toDouble(), oy = (by + jy - 1).toDouble();
    if (jx == 1) ox += _parabola(c[1][0], c[1][1], c[1][2]);
    if (jy == 1) oy += _parabola(c[0][1], c[1][1], c[2][1]);
    tr.ncc = bj;
    if (bj < minNcc) {
      tr.det = _withSource(tr.det, 'coast');
      return;
    }
    tr.scale *= bs;
    final bw = tr.anchorW * tr.scale, bh = tr.anchorH * tr.scale;
    final ncx = cx + ox, ncy = cy + oy;
    tr.det = Detection((ncx - bw / 2) / k, (ncy - bh / 2) / k, (ncx + bw / 2) / k, (ncy + bh / 2) / k,
        tr.det.confidence, tr.det.classId, tr.det.className, tr.id)
      ..source = 'track';
    tr.lastMeasT = t;
  }

  static Detection _withSource(Detection d, String source) =>
      Detection(d.x1, d.y1, d.x2, d.y2, d.confidence, d.classId, d.className, d.trackId)..source = source;

  static void _sampleInto(
      GrayImage g, double cx, double cy, double bw, double bh, int nx, int ny, Float32List out) {
    final sx = bw / nx, sy = bh / ny;
    final x0 = cx - bw / 2 + 0.5 * sx, y0 = cy - bh / 2 + 0.5 * sy;
    final xLast = x0 + (nx - 1) * sx, yLast = y0 + (ny - 1) * sy;
    var o = 0;
    if (x0 < 0 || y0 < 0 || xLast > g.width - 1.001 || yLast > g.height - 1.001) {
      for (var j = 0; j < ny; j++) {
        final y = y0 + j * sy;
        for (var i = 0; i < nx; i++) {
          out[o++] = g.at(x0 + i * sx, y);
        }
      }
      return;
    }
    // nhanh: không cần kẹp tọa độ
    final d = g.data, w = g.width;
    for (var j = 0; j < ny; j++) {
      final y = y0 + j * sy;
      final yi = y.floor();
      final fy = y - yi;
      final row = yi * w;
      for (var i = 0; i < nx; i++) {
        final x = x0 + i * sx;
        final xi = x.floor();
        final fx = x - xi;
        final k = row + xi;
        final top = d[k] + (d[k + 1] - d[k]) * fx;
        final bot = d[k + w] + (d[k + w + 1] - d[k + w]) * fx;
        out[o++] = top + (bot - top) * fy;
      }
    }
  }

  static void _normalize(Float32List v) {
    var mean = 0.0;
    for (final e in v) {
      mean += e;
    }
    mean /= v.length;
    var norm = 0.0;
    for (var i = 0; i < v.length; i++) {
      v[i] -= mean;
      norm += v[i] * v[i];
    }
    norm = math.max(math.sqrt(norm), 1e-6);
    for (var i = 0; i < v.length; i++) {
      v[i] /= norm;
    }
  }

  static double _parabola(double cm, double c0, double cp) {
    final d = cm - 2 * c0 + cp;
    return d < 0 ? 0.5 * (cm - cp) / d : 0.0;
  }

  static bool _inside(List<double> b, List<double> roi) =>
      b[0] >= roi[0] - 2 && b[1] >= roi[1] - 2 && b[2] <= roi[2] + 2 && b[3] <= roi[3] + 2;

  static double _iou(List<double> a, List<double> b) {
    final xx1 = math.max(a[0], b[0]), yy1 = math.max(a[1], b[1]);
    final xx2 = math.min(a[2], b[2]), yy2 = math.min(a[3], b[3]);
    final inter = math.max(0.0, xx2 - xx1) * math.max(0.0, yy2 - yy1);
    final union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter;
    return union > 0 ? inter / union : 0;
  }
}
