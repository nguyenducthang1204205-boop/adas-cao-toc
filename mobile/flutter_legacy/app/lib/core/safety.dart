/// Ngưỡng khoảng cách an toàn theo tốc độ và điều kiện đường (port của adas/safety.py).
///
/// Khô ráo, theo Thông tư 31/2019/TT-BGTVT Điều 11: 60 -> 35 m; (60, 80] -> 55 m; (80, 100] -> 70 m;
/// (100, 120] -> 100 m. V < 60 km/h: ước tính quy tắc 2 giây. Người dùng đặt ngưỡng riêng cho từng dải
/// (SafetyPolicy.bandGapsM, timeGapS), không bao giờ thấp hơn luật. Điều kiện bất lợi nhân hệ số một lần.
library;

import 'dart:math' as math;

import 'config.dart';

const legalGapTable = [(60.0, 35.0), (80.0, 55.0), (100.0, 70.0), (120.0, 100.0)];
const legalMinSpeed = 60.0;
const legalMaxSpeed = 120.0;
const defaultTimeGapS = 2.0;
const gravity = 9.81;

enum Risk { info, safe, warning, danger }

int riskRank(Risk r) => switch (r) { Risk.info || Risk.safe => 0, Risk.warning => 1, Risk.danger => 2 };

class Thresholds {
  final double speedKmh;
  final double safeM; // dưới ngưỡng -> CẢNH BÁO
  final double dangerM; // dưới ngưỡng -> NGUY HIỂM
  final double gapM;
  final double? legalM; // tối thiểu theo luật (null khi < 60 km/h)
  final double? bandM; // ngưỡng người dùng đặt cho dải tốc độ này, đường khô (>= legalM)
  final bool overSpeedLimit;
  final double? recommendedSpeedKmh;
  const Thresholds(this.speedKmh, this.safeM, this.dangerM, this.gapM, this.legalM, this.bandM,
      this.overSpeedLimit, this.recommendedSpeedKmh);
}

double? legalMinGap(double speedKmh) {
  if (speedKmh < legalMinSpeed) return null;
  for (final (vmax, gap) in legalGapTable) {
    if (speedKmh <= vmax) return gap;
  }
  return legalGapTable.last.$2 * speedKmh / legalMaxSpeed;
}

/// Ngưỡng cảnh báo (đường khô) của dải tốc độ chứa V, không thấp hơn luật. null khi V < 60 km/h;
/// trên 120 km/h ngoại suy như legalMinGap (giống band_gap_m).
double? bandGapM(double speedKmh, SafetyPolicy p) {
  final legal = legalMinGap(speedKmh);
  if (legal == null) return null;
  var i = legalGapTable.indexWhere((b) => speedKmh <= b.$1);
  if (i < 0) i = legalGapTable.length - 1;
  if (i >= p.bandGapsM.length) return legal;
  var user = p.bandGapsM[i];
  if (speedKmh > legalMaxSpeed) user *= speedKmh / legalMaxSpeed;
  return math.max(user, legal);
}

double recommendedSpeedKmh(double visibilityM, double mu, {double reactionS = 1.5}) {
  final a = mu * gravity;
  final v = a * (-reactionS + math.sqrt(reactionS * reactionS + 2 * visibilityM / a));
  return v * 3.6;
}

Thresholds computeThresholds(double speedKmh, SafetyPolicy p) {
  speedKmh = math.max(speedKmh, 0.0);
  final gap = speedKmh / 3.6 * p.timeGapS;
  final legal = p.useLegalTable ? legalMinGap(speedKmh) : null;
  final band = legal != null ? bandGapM(speedKmh, p) : null;
  // Khô ráo: >= 60 km/h theo ngưỡng của dải (>= luật); < 60 km/h theo quy tắc thời gian
  final base = math.max(band ?? gap, p.minDistanceM);
  final safe = base * p.weatherFactor;
  final danger = math.max(p.minDistanceM, safe * p.dangerRatio);
  final rec = p.visibilityM > 0 ? recommendedSpeedKmh(p.visibilityM, p.roadMu) : null;
  return Thresholds(speedKmh, safe, danger, gap, legal, band, speedKmh > legalMaxSpeed, rec);
}

Risk classifyRisk(double distanceM, double? ttcS, Thresholds thr, SafetyPolicy p) {
  if (distanceM < thr.dangerM || (ttcS != null && ttcS < p.ttcDangerS)) return Risk.danger;
  if (distanceM < thr.safeM || (ttcS != null && ttcS < p.ttcWarningS)) return Risk.warning;
  return Risk.safe;
}

/// Số kiểu Việt Nam, bỏ phần thập phân bằng 0: 2 · 2,5 · 1,15 (giống vn_num của bản desktop).
String vnNum(double v) {
  var s = v.toStringAsFixed(2);
  while (s.endsWith('0')) {
    s = s.substring(0, s.length - 1);
  }
  if (s.endsWith('.')) s = s.substring(0, s.length - 1);
  return s.replaceAll('.', ',');
}

/// Câu giải thích ngưỡng đang áp dụng; giống hệt threshold_basis() của bản desktop.
String thresholdBasis(Thresholds thr, SafetyPolicy p) {
  final legal = thr.legalM, band = thr.bandM;
  var s = legal != null && band != null && band > legal
      ? 'Bạn đặt ${band.round()} m (luật ≥ ${legal.round()} m)'
      : legal != null
          ? 'Theo luật (đường khô): ${legal.round()} m'
          : 'Quy tắc ${vnNum(p.timeGapS)} giây: ${thr.gapM.round()} m';
  if (p.weatherFactor > 1.0) s += '\n× ${vnNum(p.weatherFactor)} do điều kiện đường';
  return s;
}

/// SafetyPolicy từ một điều kiện mặt đường + các yếu tố cộng thêm (giống condition_policy).
/// Ngưỡng theo dải tốc độ và quy tắc thời gian lấy từ [base] (người dùng đặt), giữ nguyên.
SafetyPolicy conditionPolicy(String conditionKey, Iterable<String> mods,
    {double visibilityM = 0, SafetyPolicy base = const SafetyPolicy()}) {
  final cond = roadConditions[conditionKey]!;
  var factor = cond.factor;
  final names = [cond.name];
  var ttcW = cond.ttcWarningS, ttcD = cond.ttcDangerS;
  for (final m in mods) {
    final (label, _, mul) = modifiers[m]!;
    factor *= mul;
    names.add(label.toLowerCase());
    ttcW += 0.5;
    ttcD += 0.25;
  }
  final b = base;
  return SafetyPolicy(
    timeGapS: b.timeGapS,
    bandGapsM: List.unmodifiable(b.bandGapsM),
    // làm tròn theo giá trị thập phân chính xác như round(x, 2) của Python: 1,5 × 1,15 = 1,7249999… -> 1,72
    weatherFactor: double.parse(math.min(factor, maxFactor).toStringAsFixed(2)),
    dangerRatio: b.dangerRatio,
    minDistanceM: b.minDistanceM,
    ttcWarningS: math.min(ttcW, 8.0),
    ttcDangerS: math.min(ttcD, 4.0),
    useLegalTable: true,
    condition: names.join(', '),
    roadMu: cond.mu,
    visibilityM: visibilityM,
  );
}
