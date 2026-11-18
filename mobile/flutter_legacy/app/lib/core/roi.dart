/// Vùng ảnh đưa vào YOLO, tính từ hiệu chỉnh camera (giống openpilot nắn ảnh theo hiệu chỉnh về vùng
/// đường trước khi vào mô hình, thay vì đưa cả khung hình).
///
/// - Dải rộng ("wide"): giữ nguyên bề ngang, bỏ phần trời phía trên chân trời và nắp capo phía dưới, sao
///   cho tỉ lệ đúng bằng ô vào của mô hình -> không phí điểm ảnh vào vùng đệm, xe giữ nguyên độ phân giải.
/// - Vùng hẹp ("narrow"): ô quanh điểm tụ ở tỉ lệ ~1:1 điểm ảnh camera - xe ở xa to gấp đôi so với dải
///   rộng (ý tưởng trường nhìn hẹp cho tầm xa của Mobileye, ở đây xen kẽ trên cùng một camera).
library;

import 'dart:math' as math;

import 'config.dart';
import 'ipm.dart';

class CropRect {
  final int x, y, w, h;
  const CropRect(this.x, this.y, this.w, this.h);

  bool get isEmpty => w <= 0 || h <= 0;

  bool isFull(int frameW, int frameH) => x == 0 && y == 0 && w == frameW && h == frameH;

  @override
  bool operator ==(Object other) =>
      other is CropRect && other.x == x && other.y == y && other.w == w && other.h == h;

  @override
  int get hashCode => Object.hash(x, y, w, h);

  @override
  String toString() => 'CropRect($x, $y, $w x $h)';
}

/// Phần trên chân trời giữ lại trong dải rộng (xe tải gần cao hơn camera nên nhô lên trên chân trời).
const wideAboveHorizon = 0.35;

/// Vị trí điểm tụ trong vùng hẹp (tính từ mép trên): xe ở xa nằm ngay dưới chân trời.
const narrowAboveHorizon = 0.45;

/// Hàng chân trời (px) từ hiệu chỉnh; hiệu chỉnh suy biến thì lấy 45 % chiều cao.
double horizonRow(GroundPlaneMapper m) {
  final h = m.horizonY;
  if (h == null || !h.isFinite) return 0.45 * m.frameH;
  return h.clamp(0.15 * m.frameH, 0.75 * m.frameH).toDouble();
}

/// Cột điểm tụ (px): nơi trục xe (X = 0) gặp chân trời.
double vanishingColumn(GroundPlaneMapper m) {
  final far = m.groundToImage(0, 1000);
  if (!far.x.isFinite) return m.frameW / 2;
  return far.x.clamp(0.25 * m.frameW, 0.75 * m.frameW).toDouble();
}

/// Dải rộng cùng tỉ lệ với ô vào [inW] x [inH]. Khung thấp hơn dải (ô vào "cao" hơn khung) thì lấy cả khung.
CropRect wideCrop(GroundPlaneMapper m, CalibrationConfig calib, int frameW, int frameH, int inW, int inH) {
  final bandH = (frameW * inH / inW).round();
  if (bandH >= frameH) return CropRect(0, 0, frameW, frameH);
  var top = horizonRow(m) - wideAboveHorizon * bandH;
  // luôn giữ vùng gần (mép dưới hình chữ nhật hiệu chỉnh + 4 %): xe ngay trước mặt quan trọng nhất
  final nearRow = calib.imagePoints.map((p) => p[1]).reduce(math.max) * frameH;
  final needBottom = math.min(frameH.toDouble(), nearRow + 0.04 * frameH);
  if (top + bandH < needBottom) top = needBottom - bandH;
  final y = top.round().clamp(0, frameH - bandH);
  return CropRect(0, y, frameW, bandH);
}

/// Vùng hẹp quanh điểm tụ, ~1:1 điểm ảnh; null nếu khung quá nhỏ để có lợi (dưới 1,6 lần bề ngang ô vào).
CropRect? narrowCrop(GroundPlaneMapper m, int frameW, int frameH, int inW, int inH) {
  if (frameW < 1.6 * inW) return null;
  final w = inW, h = inH;
  if (h > frameH) return null;
  final x = (vanishingColumn(m) - w / 2).round().clamp(0, frameW - w);
  final y = (horizonRow(m) - narrowAboveHorizon * h).round().clamp(0, frameH - h);
  return CropRect(x, y, w, h);
}
