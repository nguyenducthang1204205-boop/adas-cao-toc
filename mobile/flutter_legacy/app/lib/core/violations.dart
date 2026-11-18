/// Ghi nhật ký vi phạm khoảng cách theo ĐỢT (port của adas/violations.py::ViolationRecorder).
///
/// Một đợt bắt đầu khi mức cảnh báo ổn định (sau chống nhiễu) chuyển sang CẢNH BÁO/NGUY HIỂM với một xe
/// phía trước, và kết thúc khi trở về AN TOÀN hoặc xe phía trước đổi sang xe khác. Trong đợt chỉ cập nhật
/// khoảng cách/TTC nhỏ nhất và mức cao nhất; nơi lưu chỉ được gọi khi mở, nâng mức và đóng đợt.
library;

import 'pipeline.dart';
import 'safety.dart';

class Violation {
  final int id;
  final int sessionId;
  final DateTime startedAt;
  Risk level;
  final int? trackId;
  final String className;
  final double distanceM; // lúc bắt đầu
  double minDistanceM;
  double? minTtcS;
  double? durationS; // null: đang diễn ra
  final double safeM, dangerM;
  final double speedKmh;
  final String condition;
  final double weatherFactor;

  Violation({
    required this.id,
    required this.sessionId,
    required this.startedAt,
    required this.level,
    required this.trackId,
    required this.className,
    required this.distanceM,
    required this.minDistanceM,
    required this.minTtcS,
    required this.safeM,
    required this.dangerM,
    required this.speedKmh,
    required this.condition,
    required this.weatherFactor,
    this.durationS,
  });

  bool get open => durationS == null;

  Map<String, dynamic> toJson() => {
        'id': id,
        'session_id': sessionId,
        'started_at': startedAt.toIso8601String(),
        'level': level.name,
        'track_id': trackId,
        'class': className,
        'distance_m': distanceM,
        'min_distance_m': minDistanceM,
        'min_ttc_s': minTtcS,
        'duration_s': durationS,
        'safe_m': safeM,
        'danger_m': dangerM,
        'speed_kmh': speedKmh,
        'condition': condition,
        'weather_factor': weatherFactor,
      };

  factory Violation.fromJson(Map<String, dynamic> j) => Violation(
        id: j['id'] as int,
        sessionId: j['session_id'] as int? ?? 0,
        startedAt: DateTime.tryParse(j['started_at'] as String? ?? '') ?? DateTime(2000),
        level: j['level'] == 'danger' ? Risk.danger : Risk.warning,
        trackId: j['track_id'] as int?,
        className: j['class'] as String? ?? 'car',
        distanceM: (j['distance_m'] as num?)?.toDouble() ?? 0,
        minDistanceM: (j['min_distance_m'] as num?)?.toDouble() ?? 0,
        minTtcS: (j['min_ttc_s'] as num?)?.toDouble(),
        durationS: (j['duration_s'] as num?)?.toDouble() ?? 0, // đợt chưa đóng khi app tắt: coi như đã đóng
        safeM: (j['safe_m'] as num?)?.toDouble() ?? 0,
        dangerM: (j['danger_m'] as num?)?.toDouble() ?? 0,
        speedKmh: (j['speed_kmh'] as num?)?.toDouble() ?? 0,
        condition: j['condition'] as String? ?? '',
        weatherFactor: (j['weather_factor'] as num?)?.toDouble() ?? 1,
      );
}

/// 'open' | 'update' | 'close' - giống sự kiện của bản desktop.
typedef ViolationEvent = (String action, Violation v);

class ViolationRecorder {
  final int sessionId;
  final int Function() nextId;
  Violation? _ep;
  double _startT = 0;
  int count = 0;

  ViolationRecorder({required this.sessionId, required this.nextId});

  Violation? get current => _ep;

  static bool _alerting(Risk r) => r == Risk.warning || r == Risk.danger;

  /// Gọi mỗi khung. Trả về các sự kiện để nơi lưu ghi lại (rỗng ở hầu hết các khung).
  List<ViolationEvent> update(FrameResult r, double t, double speedKmh, String condition, double weatherFactor) {
    final events = <ViolationEvent>[];
    final lead = r.lead;
    final active = _alerting(r.level) && lead != null;
    final ep = _ep;
    if (ep != null && (!active || lead.det.trackId != ep.trackId)) {
      if (_alerting(r.level) && lead == null) return events; // mất dấu xe tạm thời nhưng vẫn cảnh báo -> giữ đợt
      events.add(_close(t));
    }
    if (!active) return events;

    final cur = _ep;
    if (cur == null) {
      final thr = r.thresholds;
      _ep = Violation(
        id: nextId(),
        sessionId: sessionId,
        startedAt: DateTime.now(),
        level: r.level,
        trackId: lead.det.trackId,
        className: lead.det.className,
        distanceM: lead.distanceM,
        minDistanceM: lead.distanceM,
        minTtcS: lead.ttcS,
        safeM: thr.safeM,
        dangerM: thr.dangerM,
        speedKmh: speedKmh,
        condition: condition,
        weatherFactor: weatherFactor,
      );
      _startT = t;
      count++;
      events.add(('open', _ep!));
    } else {
      if (lead.distanceM < cur.minDistanceM) cur.minDistanceM = lead.distanceM;
      final ttc = lead.ttcS;
      if (ttc != null) cur.minTtcS = cur.minTtcS == null || ttc < cur.minTtcS! ? ttc : cur.minTtcS;
      if (riskRank(r.level) > riskRank(cur.level)) {
        cur.level = r.level;
        events.add(('update', cur));
      }
    }
    return events;
  }

  /// Đóng đợt đang mở (khi dừng giám sát).
  ViolationEvent? close(double t) => _ep != null ? _close(t) : null;

  ViolationEvent _close(double t) {
    final ep = _ep!;
    ep.durationS = t - _startT > 0 ? t - _startT : 0.0;
    _ep = null;
    return ('close', ep);
  }
}
