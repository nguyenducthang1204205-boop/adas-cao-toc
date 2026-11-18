/// IPM - biến đổi phối cảnh ngược (port của adas/ipm.py).
///
/// Giả thiết mặt đường phẳng. H ánh xạ pixel (u, v) -> mét (X lệch ngang, Y khoảng cách từ đầu xe),
/// dựng từ 4 điểm ảnh của một hình chữ nhật W x L mét trên mặt đường.
library;

import 'dart:math' as math;

import 'config.dart';
import 'geometry.dart';

class GroundPlaneMapper {
  final CalibrationConfig calib;
  final double frameW, frameH;
  late final Mat3 h;
  late final Mat3 hInv;
  late final double _validSign;
  late final double? horizonY;
  late final double? focalPx; // tiêu cự phân rã từ H (null nếu suy biến)

  GroundPlaneMapper(this.calib, this.frameW, this.frameH) {
    final src = [for (final p in calib.imagePoints) Vec2(p[0] * frameW, p[1] * frameH)];
    final w = calib.rectWidthM, l = calib.rectLengthM, d0 = calib.nearDistanceM;
    final dst = [Vec2(-w / 2, d0), Vec2(w / 2, d0), Vec2(w / 2, d0 + l), Vec2(-w / 2, d0 + l)];
    h = Mat3.perspective(src, dst);
    hInv = h.inverse();
    // Dấu thành phần đồng nhất tại một điểm chắc chắn trên mặt đường; dấu ngược = trên chân trời
    final ref = h.applyHomog(frameW / 2, src[0].y);
    _validSign = ref[2] >= 0 ? 1.0 : -1.0;
    final h31 = h.at(2, 0), h32 = h.at(2, 1), h33 = h.at(2, 2);
    horizonY = h32.abs() > 1e-12 ? -(h31 * (frameW / 2) + h33) / h32 : null;
    focalPx = _focal();
  }

  /// Tiêu cự từ phân rã G = H⁻¹ ∝ K·[r1 r2 t] (Zhang), tâm ảnh ở giữa khung (giống _decompose).
  double? _focal() {
    final cx = frameW / 2, cy = frameH / 2;
    final s = hInv.at(2, 2);
    final g = [for (var r = 0; r < 3; r++) [for (var c = 0; c < 3; c++) hInv.at(r, c) / s]];
    for (var c = 0; c < 3; c++) {
      g[0][c] -= cx * g[2][c];
      g[1][c] -= cy * g[2][c];
    }
    final g1 = [g[0][0], g[1][0], g[2][0]], g2 = [g[0][1], g[1][1], g[2][1]];
    var f2 = -1.0;
    final den = g2[2] * g2[2] - g1[2] * g1[2];
    if (den.abs() > 1e-12) {
      f2 = ((g1[0] * g1[0] + g1[1] * g1[1]) - (g2[0] * g2[0] + g2[1] * g2[1])) / den;
    }
    if (!(f2 > 0) && (g1[2] * g2[2]).abs() > 1e-12) {
      f2 = -(g1[0] * g2[0] + g1[1] * g2[1]) / (g1[2] * g2[2]);
    }
    return f2 > 0 ? math.sqrt(f2) : null;
  }

  /// Pixel ảnh -> (X, Y) mét; null nếu trên chân trời hoặc ngoài tầm đo.
  Vec2? imageToGround(double u, double v) {
    final p = h.applyHomog(u, v);
    final s = p[2];
    if (s.abs() <= 1e-9 || (s >= 0 ? 1.0 : -1.0) != _validSign) return null;
    final x = p[0] / s, y = p[1] / s;
    if (y < 0 || y > calib.maxRangeM) return null;
    return Vec2(x, y);
  }

  /// (X, Y) mét -> pixel ảnh.
  Vec2 groundToImage(double x, double y) => hInv.apply(x, y);
}
