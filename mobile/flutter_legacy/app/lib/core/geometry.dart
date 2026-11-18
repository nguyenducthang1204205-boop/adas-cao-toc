/// Đại số 3x3 cho homography (thay cv2.getPerspectiveTransform / np.linalg.inv của bản desktop).
library;

import 'dart:math' as math;

class Vec2 {
  final double x, y;
  const Vec2(this.x, this.y);
  @override
  String toString() => 'Vec2(${x.toStringAsFixed(3)}, ${y.toStringAsFixed(3)})';
}

/// Ma trận 3x3 lưu theo hàng: [a00, a01, a02, a10, ...].
class Mat3 {
  final List<double> m;
  Mat3(List<double> values) : m = List<double>.unmodifiable(values) {
    assert(values.length == 9);
  }

  double at(int r, int c) => m[r * 3 + c];

  Mat3 operator *(Mat3 o) {
    final out = List<double>.filled(9, 0);
    for (var r = 0; r < 3; r++) {
      for (var c = 0; c < 3; c++) {
        var s = 0.0;
        for (var k = 0; k < 3; k++) {
          s += at(r, k) * o.at(k, c);
        }
        out[r * 3 + c] = s;
      }
    }
    return Mat3(out);
  }

  /// Nhân với vector đồng nhất (x, y, 1) -> (X, Y, W) chưa chia.
  List<double> applyHomog(double x, double y) => [
        m[0] * x + m[1] * y + m[2],
        m[3] * x + m[4] * y + m[5],
        m[6] * x + m[7] * y + m[8],
      ];

  Vec2 apply(double x, double y) {
    final h = applyHomog(x, y);
    return Vec2(h[0] / h[2], h[1] / h[2]);
  }

  Mat3 inverse() {
    final a = m;
    final c00 = a[4] * a[8] - a[5] * a[7];
    final c01 = a[5] * a[6] - a[3] * a[8];
    final c02 = a[3] * a[7] - a[4] * a[6];
    final det = a[0] * c00 + a[1] * c01 + a[2] * c02;
    if (det.abs() < 1e-15) throw StateError('Ma trận suy biến (4 điểm hiệu chỉnh thẳng hàng?)');
    final inv = 1.0 / det;
    return Mat3([
      c00 * inv,
      (a[2] * a[7] - a[1] * a[8]) * inv,
      (a[1] * a[5] - a[2] * a[4]) * inv,
      c01 * inv,
      (a[0] * a[8] - a[2] * a[6]) * inv,
      (a[2] * a[3] - a[0] * a[5]) * inv,
      c02 * inv,
      (a[1] * a[6] - a[0] * a[7]) * inv,
      (a[0] * a[4] - a[1] * a[3]) * inv,
    ]);
  }

  /// Homography ánh xạ 4 điểm src -> 4 điểm dst (giống cv2.getPerspectiveTransform, h33 = 1).
  static Mat3 perspective(List<Vec2> src, List<Vec2> dst) {
    assert(src.length == 4 && dst.length == 4);
    // Hệ 8 phương trình tuyến tính A·h = b
    final a = List.generate(8, (_) => List<double>.filled(9, 0));
    for (var i = 0; i < 4; i++) {
      final u = src[i].x, v = src[i].y, x = dst[i].x, y = dst[i].y;
      a[2 * i]
        ..[0] = u
        ..[1] = v
        ..[2] = 1
        ..[6] = -u * x
        ..[7] = -v * x
        ..[8] = x;
      a[2 * i + 1]
        ..[3] = u
        ..[4] = v
        ..[5] = 1
        ..[6] = -u * y
        ..[7] = -v * y
        ..[8] = y;
    }
    // Khử Gauss có chọn trụ
    for (var col = 0; col < 8; col++) {
      var piv = col;
      for (var r = col + 1; r < 8; r++) {
        if (a[r][col].abs() > a[piv][col].abs()) piv = r;
      }
      if (a[piv][col].abs() < 1e-12) throw StateError('Không tính được homography: 4 điểm suy biến');
      final tmp = a[col];
      a[col] = a[piv];
      a[piv] = tmp;
      for (var r = 0; r < 8; r++) {
        if (r == col) continue;
        final f = a[r][col] / a[col][col];
        if (f == 0) continue;
        for (var c = col; c < 9; c++) {
          a[r][c] -= f * a[col][c];
        }
      }
    }
    final h = [for (var i = 0; i < 8; i++) a[i][8] / a[i][i], 1.0];
    return Mat3(h);
  }
}

double degrees(double rad) => rad * 180 / math.pi;
double radians(double deg) => deg * math.pi / 180;
