/// Nơi lưu nhật ký vi phạm trên điện thoại (shared_preferences, một chuỗi JSON), tương ứng bảng
/// `violations` + `monitoring_sessions` trong CSDL của bản desktop. Chỉ ghi khi mở / nâng mức / đóng đợt.
library;

import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../core/violations.dart';

class ViolationLog extends ChangeNotifier {
  static const _key = 'adas_violations_v1';
  static const maxItems = 500; // giữ các đợt gần nhất

  final List<Violation> items = []; // mới nhất trước
  int _lastId = 0;
  int _lastSession = 0;
  int sessionId = 0; // phiên giám sát hiện tại (mỗi lần mở màn hình lái)

  int get sessionCount => items.where((v) => v.sessionId == sessionId).length;

  ViolationRecorder startSession() {
    sessionId = ++_lastSession;
    _save();
    notifyListeners();
    return ViolationRecorder(sessionId: sessionId, nextId: () => ++_lastId);
  }

  /// Nhận sự kiện từ ViolationRecorder.update / close.
  void apply(List<ViolationEvent> events) {
    if (events.isEmpty) return;
    for (final (action, v) in events) {
      if (action == 'open') {
        items.insert(0, v);
        if (items.length > maxItems) items.removeRange(maxItems, items.length);
      }
    }
    _save();
    notifyListeners();
  }

  /// Khoảng cách nhỏ nhất của đợt đang mở thay đổi theo khung: chỉ vẽ lại, không ghi.
  void touch() => notifyListeners();

  Future<void> clear() async {
    items.clear();
    await _save();
    notifyListeners();
  }

  Future<void> load() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final s = prefs.getString(_key);
      if (s == null) return;
      final j = jsonDecode(s) as Map<String, dynamic>;
      _lastId = j['last_id'] as int? ?? 0;
      _lastSession = j['last_session'] as int? ?? 0;
      items
        ..clear()
        ..addAll([for (final e in j['items'] as List? ?? const []) Violation.fromJson(e as Map<String, dynamic>)]);
    } catch (e) {
      debugPrint('Không đọc được nhật ký vi phạm: $e');
    }
  }

  Future<void> _save() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(
          _key,
          jsonEncode({
            'last_id': _lastId,
            'last_session': _lastSession,
            'items': [for (final v in items) v.toJson()],
          }));
    } catch (e) {
      debugPrint('Không lưu được nhật ký vi phạm: $e');
    }
  }
}
