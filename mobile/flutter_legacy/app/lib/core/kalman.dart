/// Bộ lọc Kalman cho khoảng cách tới một xe phía trước (port 1:1 của adas/kalman.py - xem đó để biết
/// cách chọn tham số bằng mô phỏng).
///
/// Trạng thái [d, ḋ, d̈], mô hình gia tốc không đổi, nhiễu quá trình là độ giật ngẫu nhiên.
/// Phép đo d (IPM) có σ = max(0,3 m; 4 %·d) - đo trên video thật.
library;

import 'dart:math' as math;

const sigmaJerk = 10.0; // m/s³
const sigmaDMin = 0.3; // m
const sigmaDRel = 0.04; // sai số đo IPM ≈ 4 % khoảng cách
const rateStdInit = 8.0; // m/s
const accStdInit = 1.0; // m/s²
const rateStdReport = 2.0; // m/s - dưới mức này mới báo tốc độ tiếp cận / TTC
const gateSigma = 5.0; // lệch dự đoán > 5σ: ngoại lai
const maxOutliers = 3; // ngoại lai liên tiếp -> khởi tạo lại từ phép đo

/// Độ lệch chuẩn phép đo khoảng cách; [far]: ước lượng Pinhole ("Xa") kém tin cậy hơn nhiều.
double measurementSigma(double d, {bool far = false}) => math.max(sigmaDMin, (far ? 0.25 : sigmaDRel) * d);

class RangeKalman {
  List<double> x = [0, 0, 0];
  List<List<double>> p = [];
  double t;
  int outliers = 0;

  RangeKalman(double d, this.t, double sigma) {
    _init(d, sigma);
  }

  void _init(double d, double sigma) {
    x = [d, 0, 0];
    p = [
      [sigma * sigma, 0, 0],
      [0, rateStdInit * rateStdInit, 0],
      [0, 0, accStdInit * accStdInit],
    ];
    outliers = 0;
  }

  void predict(double tNew) {
    final dt = tNew - t;
    if (dt <= 0) return;
    final f = [
      [1.0, dt, dt * dt / 2],
      [0.0, 1.0, dt],
      [0.0, 0.0, 1.0],
    ];
    final g = [dt * dt * dt / 6, dt * dt / 2, dt];
    const q = sigmaJerk * sigmaJerk;
    x = [for (var i = 0; i < 3; i++) f[i][0] * x[0] + f[i][1] * x[1] + f[i][2] * x[2]];
    final fp = [
      for (var i = 0; i < 3; i++)
        [for (var j = 0; j < 3; j++) f[i][0] * p[0][j] + f[i][1] * p[1][j] + f[i][2] * p[2][j]]
    ];
    p = [
      for (var i = 0; i < 3; i++)
        [for (var j = 0; j < 3; j++) fp[i][0] * f[j][0] + fp[i][1] * f[j][1] + fp[i][2] * f[j][2] + q * g[i] * g[j]]
    ];
    t = tNew;
  }

  /// Cập nhật với phép đo [z] (đã predict tới thời điểm đo). false nếu bị loại là ngoại lai.
  bool update(double z, double sigma) {
    final s = p[0][0] + sigma * sigma;
    final y = z - x[0];
    if (y * y > gateSigma * gateSigma * s) {
      outliers++;
      if (outliers < maxOutliers) return false;
      _init(z, sigma); // dự đoán sai liên tục (đổi xe, lần đầu đo lệch): làm lại
      return true;
    }
    outliers = 0;
    final k = [for (var i = 0; i < 3; i++) p[i][0] / s];
    x = [for (var i = 0; i < 3; i++) x[i] + k[i] * y];
    p = [
      for (var i = 0; i < 3; i++) [for (var j = 0; j < 3; j++) p[i][j] - k[i] * p[0][j]]
    ];
    return true;
  }

  double get distance => x[0];

  /// > 0: đang tiến lại gần (m/s).
  double get closingSpeed => -x[1];

  double get rateStd => math.sqrt(math.max(p[1][1], 0.0));
}
