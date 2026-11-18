// Trợ lý offline + nhật ký vi phạm: Dart phải cho kết quả giống hệt bản desktop (Python).
// Fixture: python tools/make_mobile_fixtures.py -> test/fixtures/assistant_python.json
import 'dart:convert';
import 'dart:io';

import 'package:adas_caotoc/core/assistant.dart';
import 'package:adas_caotoc/core/config.dart';
import 'package:adas_caotoc/core/distance.dart';
import 'package:adas_caotoc/core/pipeline.dart';
import 'package:adas_caotoc/core/safety.dart';
import 'package:adas_caotoc/core/violations.dart';
import 'package:adas_caotoc/core/vn_text.dart';
import 'package:adas_caotoc/core/yolo.dart';
import 'package:flutter_test/flutter_test.dart';

SafetyPolicy _policy(Map<String, dynamic> j) => SafetyPolicy(
      timeGapS: (j['time_gap_s'] as num).toDouble(),
      bandGapsM: [for (final v in j['band_gaps_m'] as List) (v as num).toDouble()],
      weatherFactor: (j['weather_factor'] as num).toDouble(),
      dangerRatio: (j['danger_ratio'] as num).toDouble(),
      minDistanceM: (j['min_distance_m'] as num).toDouble(),
      ttcWarningS: (j['ttc_warning_s'] as num).toDouble(),
      ttcDangerS: (j['ttc_danger_s'] as num).toDouble(),
      condition: j['condition'] as String,
      roadMu: (j['road_mu'] as num).toDouble(),
      visibilityM: (j['visibility_m'] as num).toDouble(),
    );

FrameResult _frame(Risk level, double? d, {int track = 1, double? ttc}) {
  const thr = Thresholds(90, 110, 55, 50, 70, 70, false, null);
  final lead = d == null
      ? null
      : VehicleState(Detection(0, 0, 10, 10, 0.9, 2, 'car', track), d, 0, 'IPM', true, null, ttc);
  return FrameResult([if (lead != null) lead], lead, thr, 90, level, level);
}

void main() {
  test('bỏ dấu / ghép dấu tiếng Việt', () {
    expect(foldVi('Trời MƯA to, Đường trơn'), 'troi mua to, duong tron');
    expect(foldVi('ệ ở ữ ỳ'), 'e o u y');
    // dấu rời theo thứ tự bất kỳ -> chữ dựng sẵn
    expect(nfcVi('ệ'), 'ệ');
    expect(nfcVi('ệ'), 'ệ');
    expect(nfcVi('mưa'), 'mưa');
    expect(nfcVi('không dấu rời'), 'không dấu rời');
  });

  test('trợ lý offline khớp Python', () {
    final j = jsonDecode(File('test/fixtures/assistant_python.json').readAsStringSync()) as Map<String, dynamic>;
    final bases = {
      for (final e in (j['bases'] as Map<String, dynamic>).entries) e.key: _policy(e.value as Map<String, dynamic>)
    };
    var n = 0;
    for (final c in (j['cases'] as List).cast<Map<String, dynamic>>()) {
      final why = '"${c['message']}" / ${c['base']} / ${c['speed']} km/h';
      final r = offlineAdvice(c['message'] as String, bases[c['base']]!, (c['speed'] as num).toDouble());
      expect(r.reply, c['reply'], reason: why);
      expect(r.speedKmh, (c['speed_out'] as num?)?.toDouble(), reason: why);
      final p = c['policy'] as Map<String, dynamic>;
      expect(r.policy.condition, p['condition'], reason: why);
      expect(r.policy.weatherFactor, closeTo((p['weather_factor'] as num).toDouble(), 1e-9), reason: why);
      expect(r.policy.visibilityM, closeTo((p['visibility_m'] as num).toDouble(), 1e-9), reason: why);
      expect(r.policy.roadMu, closeTo((p['road_mu'] as num).toDouble(), 1e-9), reason: why);
      expect(r.policy.ttcWarningS, closeTo((p['ttc_warning_s'] as num).toDouble(), 1e-9), reason: why);
      expect(r.policy.ttcDangerS, closeTo((p['ttc_danger_s'] as num).toDouble(), 1e-9), reason: why);
      expect(r.policy.timeGapS, (p['time_gap_s'] as num).toDouble(), reason: why);
      expect(r.policy.bandGapsM, [for (final v in p['band_gaps_m'] as List) (v as num).toDouble()], reason: why);
      n++;
    }
    expect(n, greaterThan(300));
  });

  test('áp dụng lại điều kiện trợ lý trả về cho ra cùng chính sách', () {
    // App lưu (điều kiện, yếu tố, tầm nhìn) rồi dựng lại policy bằng conditionPolicy: phải trùng kết quả trợ lý.
    for (final m in ['trời mưa, đêm khuya, tôi buồn ngủ', 'sương mù tầm nhìn 80 m', 'chở nặng', 'đã tạnh mưa']) {
      final r = offlineAdvice(m, const SafetyPolicy(), 90);
      final again = conditionPolicy(r.conditionKey!, r.modifierKeys, visibilityM: r.visibilityM);
      expect(again.condition, r.policy.condition, reason: m);
      expect(again.weatherFactor, r.policy.weatherFactor, reason: m);
      expect(again.visibilityM, r.policy.visibilityM, reason: m);
    }
  });

  test('ghi vi phạm theo đợt', () {
    var id = 0;
    final rec = ViolationRecorder(sessionId: 1, nextId: () => ++id);
    final ev = <ViolationEvent>[];
    ev.addAll(rec.update(_frame(Risk.safe, 120), 0.0, 90, 'khô', 1));
    expect(ev, isEmpty);
    ev.addAll(rec.update(_frame(Risk.warning, 90, ttc: 6), 1.0, 90, 'khô', 1)); // mở
    ev.addAll(rec.update(_frame(Risk.warning, 80, ttc: 5), 1.1, 90, 'khô', 1)); // không ghi
    ev.addAll(rec.update(_frame(Risk.danger, 50, ttc: 3), 1.2, 90, 'khô', 1)); // nâng mức
    ev.addAll(rec.update(_frame(Risk.danger, null), 1.3, 90, 'khô', 1)); // mất dấu xe: giữ đợt
    ev.addAll(rec.update(_frame(Risk.warning, 60), 1.4, 90, 'khô', 1)); // hạ mức: không ghi
    ev.addAll(rec.update(_frame(Risk.safe, 130), 3.0, 90, 'khô', 1)); // đóng
    expect([for (final e in ev) e.$1], ['open', 'update', 'close']);
    final v = ev.last.$2;
    expect(v.level, Risk.danger);
    expect(v.minDistanceM, 50);
    expect(v.minTtcS, 3);
    expect(v.durationS, closeTo(2.0, 1e-9));
    // xe phía trước đổi sang xe khác -> đóng đợt cũ, mở đợt mới
    ev.clear();
    ev.addAll(rec.update(_frame(Risk.warning, 90, track: 1), 4.0, 90, 'khô', 1));
    ev.addAll(rec.update(_frame(Risk.warning, 85, track: 2), 4.1, 90, 'khô', 1));
    expect([for (final e in ev) e.$1], ['open', 'close', 'open']);
    expect(rec.count, 3);
    expect(Violation.fromJson(v.toJson()).toJson(), v.toJson());
  });
}
