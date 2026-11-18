/// Giải mã đầu ra YOLOv11 (TFLite) + NMS. Bản tham chiếu Python: tools/export_mobile.py / tflite_infer.py.
///
/// Đầu ra mô hình: (1, 4 + nc, N) - mỗi cột là một anchor [cx, cy, w, h, điểm lớp...].
/// Mô hình xuất bằng tools/export_mobile.py có tọa độ chuẩn hóa 0..1 theo ô vào.
library;

import 'dart:math' as math;
import 'dart:typed_data';

class Detection {
  final double x1, y1, x2, y2; // pixel ảnh gốc (đã xoay đứng)
  final double confidence;
  final int classId;
  final String className;
  int? trackId;
  String source = 'yolo'; // 'yolo' | 'track' (bám vết, có đo) | 'coast' (mất dấu, chỉ dự đoán)

  Detection(this.x1, this.y1, this.x2, this.y2, this.confidence, this.classId, this.className, [this.trackId]);

  double get width => x2 - x1;
  double get height => y2 - y1;

  /// Điểm tiếp xúc mặt đường ≈ trung điểm cạnh dưới bounding box.
  (double, double) get groundPoint => ((x1 + x2) / 2, y2);

  List<double> toList() => [x1, y1, x2, y2, confidence, classId.toDouble()];
}

/// Tham số letterbox giống Ultralytics: giữ tỉ lệ, đệm xám 114 ở giữa.
class Letterbox {
  final int srcW, srcH, inW, inH;
  final double r;
  final int newW, newH, left, top;

  factory Letterbox(int srcW, int srcH, int inW, int inH) {
    final r = math.min(inH / srcH, inW / srcW);
    final nw = (srcW * r).round(), nh = (srcH * r).round();
    return Letterbox._(srcW, srcH, inW, inH, r, nw, nh, (inW - nw) ~/ 2, (inH - nh) ~/ 2);
  }
  Letterbox._(this.srcW, this.srcH, this.inW, this.inH, this.r, this.newW, this.newH, this.left, this.top);
}

double _iou(List<double> a, List<double> b) {
  final xx1 = math.max(a[0], b[0]), yy1 = math.max(a[1], b[1]);
  final xx2 = math.min(a[2], b[2]), yy2 = math.min(a[3], b[3]);
  final inter = math.max(0.0, xx2 - xx1) * math.max(0.0, yy2 - yy1);
  final area = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter;
  return area > 0 ? inter / area : 0;
}

/// [out]: tensor phẳng (4+nc)*N. Trả về hộp trong pixel ảnh gốc sau NMS theo từng lớp.
List<Detection> decodeYolo(
  Float32List out,
  int numAnchors,
  List<String> classNames,
  Letterbox lb, {
  double confThreshold = 0.35,
  double iouThreshold = 0.45,
  bool normalized = true,
  int maxDet = 100,
  Set<String>? enabledClasses,
}) {
  final nc = classNames.length;
  final n = numAnchors;
  final sx = normalized ? lb.inW.toDouble() : 1.0, sy = normalized ? lb.inH.toDouble() : 1.0;
  final cand = <(List<double>, double, int)>[];
  for (var i = 0; i < n; i++) {
    var best = -1.0, cls = 0;
    for (var c = 0; c < nc; c++) {
      final s = out[(4 + c) * n + i];
      if (s > best) {
        best = s;
        cls = c;
      }
    }
    if (best <= confThreshold) continue;
    if (enabledClasses != null && !enabledClasses.contains(classNames[cls])) continue;
    final cx = out[i] * sx, cy = out[n + i] * sy, w = out[2 * n + i] * sx, h = out[3 * n + i] * sy;
    cand.add(([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], best, cls));
  }
  cand.sort((a, b) => b.$2.compareTo(a.$2));
  final keep = <(List<double>, double, int)>[];
  for (final c in cand) {
    var ok = true;
    for (final k in keep) {
      if (k.$3 == c.$3 && _iou(k.$1, c.$1) > iouThreshold) {
        ok = false;
        break;
      }
    }
    if (ok) {
      keep.add(c);
      if (keep.length >= maxDet) break;
    }
  }
  return [
    for (final (b, conf, cls) in keep)
      Detection(
        ((b[0] - lb.left) / lb.r).clamp(0, lb.srcW.toDouble()),
        ((b[1] - lb.top) / lb.r).clamp(0, lb.srcH.toDouble()),
        ((b[2] - lb.left) / lb.r).clamp(0, lb.srcW.toDouble()),
        ((b[3] - lb.top) / lb.r).clamp(0, lb.srcH.toDouble()),
        conf,
        cls,
        classNames[cls],
      ),
  ];
}
