/// Khởi động / cấu hình bộ nhận diện + isolate xử lý từ cài đặt (dùng chung cho màn hình lái và benchmark).
library;

import '../core/config.dart';
import '../core/governor.dart';
import '../detector/detector_service.dart';
import '../services/settings_store.dart';
import 'frame_engine.dart';

class EngineHost {
  DetectorService? det;
  FrameEngine? engine;
  bool _gpu = true;

  bool get ready => engine != null;

  /// Đổi tùy chọn GPU thì phải dựng lại bộ nhận diện.
  bool needsRestart(AppSettings s) => det == null || _gpu != s.preferGpu;

  static EngineConfig configFrom(AppSettings s, int version, {CalibrationConfig? calibration}) => EngineConfig(
        calibration: (calibration ?? s.calibration).copy(),
        alert: AlertConfig.fromJson(s.alert.toJson()),
        enabledClasses: {...s.enabledClasses},
        confidence: s.confidence,
        denseTracking: s.denseTracking,
        farDetect: s.farDetect,
        forcedLevel: perfLevelFromName(s.perfMode),
        version: version,
      );

  /// Mức khởi đầu: khóa tay > mức lần chạy trước > ước lượng từ lần đo suy luận lúc khởi động
  /// (cộng ~10 ms tiền xử lý). Bộ điều tốc chỉnh lại sau vài giây theo số đo thật.
  static PerfLevel initialLevel(AppSettings s, double benchMs) =>
      perfLevelFromName(s.perfMode) ?? perfLevelFromName(s.lastLevel) ?? capabilityLevel(benchMs + 10);

  Future<void>? _starting;

  /// Gọi chồng nhau (vd. app quay lại từ nền khi đang khởi động) thì dùng chung một lần khởi động.
  Future<void> start(AppSettings s, int version, {CalibrationConfig? calibration}) {
    final f = _starting ??= _start(s, version, calibration);
    return f.whenComplete(() {
      if (identical(_starting, f)) _starting = null;
    });
  }

  Future<void> _start(AppSettings s, int version, CalibrationConfig? calibration) async {
    if (needsRestart(s)) {
      dispose();
      _gpu = s.preferGpu;
      det = await DetectorService.start(preferGpu: s.preferGpu);
    }
    engine ??= await FrameEngine.start(
        det!, configFrom(s, version, calibration: calibration), initialLevel(s, det!.benchMs));
  }

  void configure(AppSettings s, int version, {CalibrationConfig? calibration}) =>
      engine?.configure(configFrom(s, version, calibration: calibration));

  void dispose() {
    engine?.dispose();
    engine = null;
    det?.dispose();
    det = null;
  }
}
