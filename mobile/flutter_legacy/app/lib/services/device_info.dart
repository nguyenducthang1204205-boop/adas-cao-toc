/// Nhiệt độ và thông tin máy qua kênh native "vn.adas/device" (MainActivity.kt / AppDelegate.swift).
///
/// Thang nhiệt theo Android PowerManager: 0 bình thường ... 3 nặng (máy bắt đầu hạ xung mạnh) ... 6 sắp tắt;
/// -1 = máy không hỗ trợ (Android < 10). Dư nhiệt (headroom) chỉ có từ Android 11.
library;

import 'package:flutter/services.dart';

class ThermalReading {
  final int status;
  final double? headroom;
  const ThermalReading(this.status, this.headroom);
}

class DeviceInfo {
  static const _ch = MethodChannel('vn.adas/device');

  static Future<ThermalReading> thermal() async {
    try {
      final m = await _ch.invokeMapMethod<String, dynamic>('thermal');
      return ThermalReading((m?['status'] as num?)?.toInt() ?? -1, (m?['headroom'] as num?)?.toDouble());
    } catch (_) {
      return const ThermalReading(-1, null);
    }
  }

  /// model, soc, os, cores, ram_mb (rỗng nếu không đọc được).
  static Future<Map<String, dynamic>> info() async {
    try {
      return await _ch.invokeMapMethod<String, dynamic>('info') ?? {};
    } catch (_) {
      return {};
    }
  }

  static String thermalName(int s) => switch (s) {
        0 => 'bình thường',
        1 => 'hơi ấm',
        2 => 'ấm',
        3 => 'nóng',
        4 => 'rất nóng',
        5 || 6 => 'quá nóng',
        _ => 'không rõ',
      };
}
