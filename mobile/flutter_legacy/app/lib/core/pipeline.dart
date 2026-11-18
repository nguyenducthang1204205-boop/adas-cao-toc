/// Xử lý một khung (port của adas/pipeline.py, phần sau YOLO): bám vết -> khoảng cách -> ngưỡng ->
/// mức rủi ro -> chống nhiễu cảnh báo. Không phụ thuộc Flutter để kiểm thử bằng `flutter test`.
///
/// Nhận diện thưa, bám vết dày: YOLO chạy nền khi rảnh; MỌI khung camera đều qua [processFrame] với ảnh
/// xám để TemplateTracker đo lại vị trí xe, nên khoảng cách/TTC cập nhật theo tốc độ camera chứ không
/// theo tốc độ YOLO.
library;

import 'config.dart';
import 'distance.dart';
import 'ipm.dart';
import 'safety.dart';
import 'template_tracker.dart';
import 'tracker.dart';
import 'yolo.dart';

/// Chống nhiễu (giống adas/alert.py): nâng mức khi mức mới kéo dài escalateSeconds (>= 2 khung), hạ mức
/// sau khi mức thấp kéo dài holdSeconds. Tính theo thời gian để nhịp xử lý 10 hay 30 Hz đều báo kịp như nhau.
class AlertHysteresis {
  final AlertConfig cfg;
  Risk level = Risk.safe;
  Risk _candidate = Risk.safe;
  int _count = 0;
  double _since = 0;
  double _lastRaise = 0;

  AlertHysteresis(this.cfg);

  Risk update(Risk raw, double now) {
    raw = (raw == Risk.warning || raw == Risk.danger) ? raw : Risk.safe;
    if (raw == _candidate) {
      _count++;
    } else {
      _candidate = raw;
      _count = 1;
      _since = now;
    }
    final r = riskRank(raw), cur = riskRank(level);
    if (r > cur) {
      if (_confirmed(now)) {
        level = raw;
        _lastRaise = now;
      }
    } else if (r < cur) {
      if (now - _lastRaise >= cfg.holdSeconds) level = raw;
    } else {
      _lastRaise = now;
    }
    return level;
  }

  bool _confirmed(double now) {
    if (cfg.escalateSeconds <= 0) return true;
    return _count >= 2 && now - _since >= cfg.escalateSeconds - 1e-9;
  }

  void reset() {
    level = Risk.safe;
    _candidate = Risk.safe;
    _count = 0;
  }
}

class FrameResult {
  final List<VehicleState> vehicles;
  final VehicleState? lead;
  final Thresholds thresholds;
  final double speedKmh;
  final Risk rawLevel;
  final Risk level;
  const FrameResult(this.vehicles, this.lead, this.thresholds, this.speedKmh, this.rawLevel, this.level);
}

class AdasPipeline {
  final CalibrationConfig calib;
  final AlertConfig alertCfg;
  final double frameW, frameH;
  late final GroundPlaneMapper mapper;
  late final DistanceEstimator estimator;
  final tracker = IouTracker(); // gán id khi không bám vết (tắt tính năng)
  final templates = TemplateTracker();
  late final AlertHysteresis alert;

  AdasPipeline(this.calib, this.alertCfg, this.frameW, this.frameH) {
    mapper = GroundPlaneMapper(calib, frameW, frameH);
    estimator = DistanceEstimator(mapper, calib);
    alert = AlertHysteresis(alertCfg);
  }

  /// Chỉ kết quả YOLO, không bám vết (gán id bằng IoU).
  FrameResult process(List<Detection> dets, double t, double speedKmh, SafetyPolicy policy) {
    tracker.update(dets, t);
    return _evaluate(dets, t, speedKmh, policy);
  }

  /// Mỗi khung camera: [gray] là ảnh xám khung hiện tại (độ phân giải làm việc, xem workScale);
  /// [yolo] là kết quả YOLO mới về (chụp lúc [yoloT] - trễ hơn [t] vì YOLO chạy nền) hoặc null.
  /// [yoloRoi]: vùng YOLO đã nhìn (khung khóa hẹp), xem TemplateTracker.refresh.
  FrameResult processFrame(GrayImage gray, double t, double speedKmh, SafetyPolicy policy,
      {List<Detection>? yolo, double? yoloT, List<double>? yoloRoi}) {
    final dets = yolo != null
        ? templates.refresh(yolo, gray, t, gray.width / frameW, detT: yoloT, roi: yoloRoi)
        : templates.track(gray, t);
    return _evaluate(dets, t, speedKmh, policy);
  }

  FrameResult _evaluate(List<Detection> dets, double t, double speedKmh, SafetyPolicy policy) {
    final vehicles = estimator.estimate(dets, t);
    final thr = computeThresholds(speedKmh, policy);
    var raw = Risk.safe;
    VehicleState? lead;
    for (final vs in vehicles) {
      if ((alertCfg.onlyEgoLane && !vs.inEgoLane) || vs.method == 'Xa') {
        vs.risk = Risk.info; // ngoài làn hoặc ngoài tầm đo tin cậy -> không cảnh báo
        continue;
      }
      vs.risk = classifyRisk(vs.distanceM, vs.ttcS, thr, policy);
      if (riskRank(vs.risk) > riskRank(raw)) raw = vs.risk;
      if (vs.inEgoLane && lead == null) lead = vs; // đã sắp xếp gần -> xa
    }
    final level = alert.update(raw, t);
    return FrameResult(vehicles, lead, thr, speedKmh, raw, level);
  }
}
