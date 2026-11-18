/// Cài đặt của app, lưu bằng shared_preferences (một chuỗi JSON).
library;

import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../core/config.dart';
import '../core/safety.dart';

class AppSettings extends ChangeNotifier {
  static const _key = 'adas_settings_v1';

  CalibrationConfig calibration = CalibrationConfig();
  bool calibrated = false; // người dùng đã căn chỉnh camera cho lần gắn máy này chưa
  AlertConfig alert = AlertConfig();
  String conditionKey = 'dry';
  Set<String> modifierKeys = {};
  double visibilityM = 0; // tầm nhìn (m) trợ lý nhận ra từ câu mô tả; 0 = không giới hạn
  double timeGapS = defaultTimeGapS; // dưới 60 km/h: quy tắc thời gian (2-6 giây)
  List<double> bandGapsM = [...defaultBandGapsM]; // ngưỡng cảnh báo đường khô theo dải tốc độ (>= luật)
  double manualSpeedKmh = 80;
  bool useGps = true;
  bool preferGpu = true;
  bool rotate180 = false;
  bool denseTracking = true; // nhận diện thưa, bám vết dày
  bool showTech = false; // hiện thông số kỹ thuật (FPS, YOLO) trên màn hình lái
  /// Mức hiệu năng: 'auto' (bộ điều tốc tự chọn theo máy, nhiệt độ) hoặc khóa 'high' / 'medium' / 'low'.
  String perfMode = 'auto';
  /// Mức bộ điều tốc chọn ở lần chạy trước: 'low' thì camera mở ở 480p ngay từ đầu (đỡ chép dữ liệu).
  String lastLevel = '';
  bool farDetect = true; // xen kẽ khung khóa hẹp quanh điểm tụ để thấy xe ở xa
  /// Kết quả đo hiệu năng (benchmark) gần nhất trước, tối đa [maxBench] lần - để so sánh giữa các máy/bản.
  List<Map<String, dynamic>> benchHistory = [];
  static const maxBench = 20;

  /// Camera mở ở 480p (mức Thấp: khóa tay, hoặc tự động và lần trước bộ điều tốc chọn Thấp).
  bool get lowCamera => perfMode == 'low' || (perfMode == 'auto' && lastLevel == 'low');
  double confidence = 0.35;
  Set<String> enabledClasses = {'car', 'truck', 'bus', 'Jeepney'};

  /// Yếu tố cộng thêm theo thứ tự của bảng `modifiers` (tên điều kiện giống bản desktop).
  SafetyPolicy get policy => conditionPolicy(conditionKey, modifiers.keys.where(modifierKeys.contains),
      visibilityM: visibilityM, base: SafetyPolicy(timeGapS: timeGapS, bandGapsM: bandGapsM));

  /// Áp dụng điều kiện do Trợ lý AI hoặc ô chọn nhanh đưa ra.
  void applyCondition(String key, Iterable<String> mods, double visibility) {
    conditionKey = key;
    modifierKeys = {...mods};
    visibilityM = visibility.clamp(0, 1000).toDouble();
  }

  /// Giới hạn giống bản desktop: 2-6 giây; mỗi dải từ mức luật đến 300 m.
  static double clampTimeGap(double v) => v.clamp(timeGapRange.$1, timeGapRange.$2).toDouble();
  static double clampBand(int i, double v) => v.clamp(legalGapTable[i].$2, maxBandGapM).toDouble();
  static const timeGapRange = (2.0, 6.0);
  static const maxBandGapM = 300.0;

  void resetBands() {
    timeGapS = defaultTimeGapS;
    bandGapsM = [...defaultBandGapsM];
  }

  /// Không bao giờ ném lỗi: cài đặt hỏng/không đọc được thì dùng mặc định để app vẫn khởi động.
  Future<void> load() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final s = prefs.getString(_key);
      if (s == null) return;
      final j = jsonDecode(s) as Map<String, dynamic>;
      calibration = CalibrationConfig.fromJson(j['calibration'] as Map<String, dynamic>);
      calibrated = j['calibrated'] as bool? ?? false;
      alert = AlertConfig.fromJson(j['alert'] as Map<String, dynamic>);
      final cond = j['condition'] as String? ?? 'dry';
      conditionKey = roadConditions.containsKey(cond) ? cond : 'dry';
      modifierKeys = {...List<String>.from(j['modifiers'] as List? ?? []).where(modifiers.containsKey)};
      visibilityM = ((j['visibility_m'] as num?)?.toDouble() ?? 0).clamp(0, 1000).toDouble();
      timeGapS = clampTimeGap((j['time_gap_s'] as num?)?.toDouble() ?? defaultTimeGapS);
      final bands = (j['band_gaps_m'] as List?)?.map((v) => (v as num).toDouble()).toList() ?? [];
      bandGapsM = [
        for (var i = 0; i < legalGapTable.length; i++) clampBand(i, i < bands.length ? bands[i] : defaultBandGapsM[i])
      ];
      manualSpeedKmh = (j['manual_speed_kmh'] as num?)?.toDouble() ?? 80;
      useGps = j['use_gps'] as bool? ?? true;
      preferGpu = j['prefer_gpu'] as bool? ?? true;
      rotate180 = j['rotate180'] as bool? ?? false;
      denseTracking = j['dense_tracking'] as bool? ?? true;
      showTech = j['show_tech'] as bool? ?? false;
      final pm = j['perf_mode'] as String? ?? 'auto';
      perfMode = const {'auto', 'high', 'medium', 'low'}.contains(pm) ? pm : 'auto';
      lastLevel = j['last_level'] as String? ?? '';
      farDetect = j['far_detect'] as bool? ?? true;
      benchHistory = [
        for (final e in (j['bench_history'] as List? ?? const [])) Map<String, dynamic>.from(e as Map)
      ];
      confidence = (j['confidence'] as num?)?.toDouble() ?? 0.35;
      enabledClasses = {...List<String>.from(j['enabled_classes'] as List? ?? enabledClasses.toList())};
    } catch (e) {
      debugPrint('Không đọc được cài đặt, dùng mặc định: $e');
    }
  }

  Future<void> save() async {
    notifyListeners();
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(
          _key,
          jsonEncode({
            'calibration': calibration.toJson(),
            'calibrated': calibrated,
            'alert': alert.toJson(),
            'condition': conditionKey,
            'modifiers': modifierKeys.toList(),
            'visibility_m': visibilityM,
            'time_gap_s': timeGapS,
            'band_gaps_m': bandGapsM,
            'manual_speed_kmh': manualSpeedKmh,
            'use_gps': useGps,
            'prefer_gpu': preferGpu,
            'rotate180': rotate180,
            'dense_tracking': denseTracking,
            'show_tech': showTech,
            'perf_mode': perfMode,
            'last_level': lastLevel,
            'far_detect': farDetect,
            'bench_history': benchHistory,
            'confidence': confidence,
            'enabled_classes': enabledClasses.toList(),
          }));
    } catch (e) {
      debugPrint('Không lưu được cài đặt: $e');
    }
  }
}
