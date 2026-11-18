/// Khoảng cách, vị trí ngang, tốc độ tiếp cận và TTC từng xe (port của adas/distance.py).
///
/// Chính: IPM tại điểm chạm đất. Dự phòng ("Xa"): Pinhole theo kích thước thật, không nhỏ hơn tầm đo.
/// Khoảng cách và tốc độ tiếp cận theo track lấy từ bộ lọc Kalman (kalman.dart); khung "coast" chỉ dự đoán.
library;

import 'dart:math' as math;

import 'config.dart';
import 'geometry.dart';
import 'ipm.dart';
import 'kalman.dart';
import 'safety.dart';
import 'yolo.dart';

class VehicleState {
  final Detection det;
  final double distanceM;
  final double lateralM;
  final String method; // "IPM" | "Xa"
  final bool inEgoLane;
  final double? closingSpeedMps; // > 0: đang tiến lại gần
  final double? ttcS;
  Risk risk = Risk.safe;

  VehicleState(this.det, this.distanceM, this.lateralM, this.method, this.inEgoLane, this.closingSpeedMps,
      this.ttcS);
}

class _Track {
  final RangeKalman kf;
  double lastSeen;
  _Track(this.kf, this.lastSeen);
}

class DistanceEstimator {
  static const minClosingMps = 0.5;
  static const trackTimeoutS = 2.0;

  final GroundPlaneMapper mapper;
  final CalibrationConfig calib;
  late final double focalPx;
  final _tracks = <int, _Track>{};

  DistanceEstimator(this.mapper, this.calib) {
    focalPx = mapper.focalPx ?? mapper.frameH / (2 * math.tan(radians(calib.cameraVfovDeg) / 2));
  }

  void reset() => _tracks.clear();

  List<VehicleState> estimate(List<Detection> dets, double t) {
    final states = <VehicleState>[];
    for (final det in dets) {
      final (gu, gv) = det.groundPoint;
      final g = mapper.imageToGround(gu, gv);
      double distance, lateral;
      String method;
      if (g != null) {
        distance = g.y;
        lateral = g.x;
        method = 'IPM';
      } else {
        final (d, lat) = _pinhole(det);
        distance = math.max(d, calib.maxRangeM);
        lateral = lat;
        method = 'Xa';
      }
      final (smoothed, closing) =
          _updateTrack(det.trackId, distance, t, far: method == 'Xa', measured: det.source != 'coast');
      final ttc = (closing != null && closing > minClosingMps) ? smoothed / closing : null;
      final inLane = lateral.abs() <= calib.laneHalfWidthM;
      states.add(VehicleState(det, smoothed, lateral, method, inLane, closing, ttc));
    }
    _tracks.removeWhere((_, tr) => t - tr.lastSeen > trackTimeoutS);
    states.sort((a, b) => a.distanceM.compareTo(b.distanceM));
    return states;
  }

  (double, double) _pinhole(Detection det) {
    final f = focalPx;
    final dH = (realHeightsM[det.className] ?? 1.5) * f / math.max(det.height, 1.0);
    final dW = (realWidthsM[det.className] ?? 1.8) * f / math.max(det.width, 1.0);
    final d = math.sqrt(dH * dW);
    final cx = (det.x1 + det.x2) / 2;
    return (d, (cx - mapper.frameW / 2) * d / f);
  }

  /// Kalman theo track: (khoảng cách đã lọc, tốc độ tiếp cận m/s hoặc null khi chưa đủ tin).
  (double, double?) _updateTrack(int? id, double d, double t, {bool far = false, bool measured = true}) {
    if (id == null) return (d, null);
    final sigma = measurementSigma(d, far: far);
    var tr = _tracks[id];
    if (tr == null) {
      tr = _tracks[id] = _Track(RangeKalman(d, t, sigma), t);
    } else {
      tr.kf.predict(t);
      if (measured) tr.kf.update(d, sigma);
    }
    if (measured) tr.lastSeen = t;
    final kf = tr.kf;
    return (kf.distance, kf.rateStd < rateStdReport ? kf.closingSpeed : null);
  }
}
