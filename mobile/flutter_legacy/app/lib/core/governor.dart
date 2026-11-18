/// Bộ điều tốc hiệu năng: chọn mức Cao / Trung bình / Thấp theo năng lực máy, nhiệt độ và mức rủi ro.
///
/// Ý tưởng lấy từ các hệ thống chạy thị giác thời gian thực trên phần cứng hạn chế:
/// - nhịp xử lý cố định, tách khỏi nhịp vẽ giao diện (openpilot chạy vòng 20 Hz);
/// - chỉ giữ khung mới nhất, khung đến khi đang bận bị bỏ (CameraX KEEP_ONLY_LATEST, MediaPipe FlowLimiter);
/// - đọc "dư nhiệt" của máy và chủ động hạ tải trước khi máy tự hạ xung (Android ADPF Thermal API);
/// - dồn tính toán vào lúc cần (CarSafe phân bổ tính toán theo ngữ cảnh): đường trống thì YOLO chạy
///   thưa, có xe gần / TTC nhỏ thì chạy hết tốc lực.
/// Không phụ thuộc Flutter để kiểm thử bằng `flutter test`.
library;

import 'pipeline.dart';
import 'safety.dart';

enum PerfLevel { high, medium, low }

const perfLevelNames = {PerfLevel.high: 'Cao', PerfLevel.medium: 'Trung bình', PerfLevel.low: 'Thấp'};

PerfLevel? perfLevelFromName(String? key) => switch (key) {
      'high' => PerfLevel.high,
      'medium' => PerfLevel.medium,
      'low' => PerfLevel.low,
      _ => null,
    };

/// Tham số xử lý của từng mức.
class LevelParams {
  /// Nhịp bám vết tối đa (Hz); 0 = mọi khung camera.
  final double trackHz;

  /// Số xe gần nhất được bám chi tiết (so khớp mẫu); các xe xa hơn chỉ dự đoán.
  final int maxTracked;
  const LevelParams(this.trackHz, this.maxTracked);
}

const levelParams = {
  PerfLevel.high: LevelParams(0, 4),
  PerfLevel.medium: LevelParams(15, 3),
  PerfLevel.low: LevelParams(10, 2),
};

/// Ngưỡng thời gian YOLO (tiền xử lý + suy luận, ms) giữa các mức: < 50 Cao, 50-120 Trung bình, > 120 Thấp.
const yoloMsHigh = 50.0;
const yoloMsMedium = 120.0;

/// YOLO chậm hơn mức này: máy dưới cấu hình tối thiểu, cảnh báo chỉ mang tính tham khảo.
const yoloMsWeak = 300.0;

/// Trạng thái nhiệt theo thang của Android PowerManager (iOS được quy đổi về cùng thang).
const thermalModerate = 2;
const thermalSevere = 3;

PerfLevel capabilityLevel(double yoloMs, {double margin = 1.0}) {
  if (yoloMs < yoloMsHigh * margin) return PerfLevel.high;
  if (yoloMs <= yoloMsMedium * margin) return PerfLevel.medium;
  return PerfLevel.low;
}

PerfLevel _worse(PerfLevel a, PerfLevel b) => a.index >= b.index ? a : b;

PerfLevel _down(PerfLevel l) => PerfLevel.values[(l.index + 1).clamp(0, PerfLevel.values.length - 1)];

PerfLevel _up(PerfLevel l) => PerfLevel.values[(l.index - 1).clamp(0, PerfLevel.values.length - 1)];

class Governor {
  /// Thời gian điều kiện tốt phải kéo dài trước khi nâng một mức (tránh dao động lên xuống).
  static const upHoldS = 10.0;

  /// Khoảng cách tối thiểu giữa hai lần hạ mức (chờ số đo ổn định theo mức mới).
  static const downGapS = 3.0;

  /// Thời gian xử lý một khung được dùng tối đa ngần này phần ngân sách khung, quá thì hạ mức.
  static const procBudgetShare = 0.6;

  PerfLevel level;
  PerfLevel? forced; // người dùng khóa mức trong Cài đặt
  double? _goodSince;
  double _lastDown = -1e9;
  String reason = '';

  Governor(this.level, {this.forced});

  PerfLevel get effective => forced ?? level;

  /// [yoloMs]: tiền xử lý + suy luận (trung bình trượt), 0 = chưa đo; [procMs]: bám vết + pipeline một khung;
  /// [cameraHz]: nhịp camera (ngân sách khung ở mức Cao); [thermal]: -1 = không rõ; [headroom]: dư nhiệt
  /// (1,0 = ngưỡng hạ xung mạnh), null = không rõ.
  PerfLevel update(double now,
      {required double yoloMs, required double procMs, double cameraHz = 30, int thermal = -1, double? headroom}) {
    if (forced != null) return forced!;
    if (yoloMs <= 0) return level;
    var target = capabilityLevel(yoloMs);
    var why = 'YOLO ${yoloMs.round()} ms';
    // nhiệt: hạ trước khi máy tự hạ xung
    if (thermal >= thermalSevere || (headroom != null && headroom >= 0.95)) {
      target = _worse(target, PerfLevel.low);
      why = 'máy rất nóng';
    } else if (thermal >= thermalModerate || (headroom != null && headroom >= 0.85)) {
      target = _worse(target, PerfLevel.medium);
      if (target == PerfLevel.medium) why = 'máy nóng';
    }
    // luồng xử lý quá tải ở mức hiện tại
    final hz = levelParams[level]!.trackHz > 0 ? levelParams[level]!.trackHz : cameraHz;
    if (hz > 0 && procMs > procBudgetShare * 1000 / hz) {
      target = _worse(target, _down(level));
      why = 'xử lý ${procMs.round()} ms/khung';
    }
    if (target.index > level.index) {
      _goodSince = null;
      if (now - _lastDown >= downGapS) {
        level = _down(level);
        _lastDown = now;
        reason = why;
      }
      return level;
    }
    // nâng mức: cần dư địa rõ ràng (ngưỡng thấp hơn 15 %) liên tục upHoldS giây, mỗi lần một mức
    final roomy = capabilityLevel(yoloMs, margin: 0.85).index < level.index && target.index < level.index;
    if (!roomy) {
      _goodSince = null;
      return level;
    }
    _goodSince ??= now;
    if (now - _goodSince! >= upHoldS) {
      level = _up(level);
      _goodSince = null;
      reason = why;
    }
    return level;
  }
}

/// Khoảng nghỉ tối thiểu (giây) giữa hai lần gửi khung cho YOLO, theo mức rủi ro của kết quả gần nhất.
///
/// - Khẩn (đang cảnh báo, TTC < 4 s, xe trước gần hơn 1,5 lần ngưỡng cảnh báo): chạy hết tốc lực.
/// - Đường trống (không có xe cùng làn, hoặc xe trước xa hơn 2 lần ngưỡng): 3 lần/giây là đủ - các xe đã
///   thấy vẫn được bám vết ở mọi khung, nên xe làn bên chuyển làn vẫn được theo dõi.
/// - Còn lại: hết tốc lực, trừ khi máy nóng.
double yoloIntervalS(FrameResult? last, {int thermal = -1}) {
  if (last == null) return 0;
  final lead = last.lead, thr = last.thresholds;
  final urgent = riskRank(last.level) >= riskRank(Risk.warning) ||
      (lead != null && ((lead.ttcS ?? 99) < 4 || lead.distanceM < 1.5 * thr.safeM));
  if (urgent) return 0;
  if (lead == null || lead.distanceM > 2 * thr.safeM) return 1 / 3;
  return thermal >= thermalModerate ? 0.15 : 0;
}
