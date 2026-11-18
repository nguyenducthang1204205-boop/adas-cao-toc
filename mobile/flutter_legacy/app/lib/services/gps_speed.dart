/// Tốc độ xe chủ từ GPS của điện thoại (thay cho đo từ vạch kẻ của bản desktop - chính xác hơn nhiều).
library;

import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:geolocator/geolocator.dart';

enum GpsState { off, noPermission, waiting, ok }

class GpsSpeed extends ChangeNotifier {
  static const staleAfter = Duration(seconds: 3);
  static const maxSpeedAccuracyMps = 3.0; // bỏ số đo có sai số tốc độ > ~11 km/h

  StreamSubscription<Position>? _sub;
  GpsState state = GpsState.off;
  double? _kmh;
  DateTime? _at;
  double? accuracyM;

  /// Tốc độ hợp lệ gần đây (km/h) hoặc null.
  double? get speedKmh =>
      (_kmh != null && _at != null && DateTime.now().difference(_at!) < staleAfter) ? _kmh : null;

  Future<void> start() async {
    if (_sub != null) return;
    if (!await Geolocator.isLocationServiceEnabled()) {
      state = GpsState.off;
      notifyListeners();
      return;
    }
    var perm = await Geolocator.checkPermission();
    if (perm == LocationPermission.denied) perm = await Geolocator.requestPermission();
    if (perm == LocationPermission.denied || perm == LocationPermission.deniedForever) {
      state = GpsState.noPermission;
      notifyListeners();
      return;
    }
    state = GpsState.waiting;
    notifyListeners();
    final LocationSettings settings = switch (defaultTargetPlatform) {
      TargetPlatform.android => AndroidSettings(
          accuracy: LocationAccuracy.bestForNavigation,
          distanceFilter: 0,
          intervalDuration: const Duration(milliseconds: 500)),
      TargetPlatform.iOS => AppleSettings(
          accuracy: LocationAccuracy.bestForNavigation,
          activityType: ActivityType.automotiveNavigation,
          distanceFilter: 0,
          pauseLocationUpdatesAutomatically: false),
      _ => const LocationSettings(accuracy: LocationAccuracy.best, distanceFilter: 0),
    };
    _sub = Geolocator.getPositionStream(locationSettings: settings).listen(_onPosition, onError: (e) {
      state = GpsState.waiting;
      notifyListeners();
    });
  }

  void _onPosition(Position p) {
    accuracyM = p.accuracy;
    // speedAccuracy = 0 nghĩa là thiết bị không báo -> vẫn nhận
    if (p.speed < 0 || (p.speedAccuracy > 0 && p.speedAccuracy > maxSpeedAccuracyMps)) return;
    final v = p.speed * 3.6;
    // làm mượt nhẹ: GPS báo 1-2 lần/giây, đủ nhanh cho ngưỡng khoảng cách
    _kmh = _kmh == null || speedKmh == null ? v : 0.6 * v + 0.4 * _kmh!;
    _at = DateTime.now();
    state = GpsState.ok;
    notifyListeners();
  }

  Future<void> stop() async {
    await _sub?.cancel();
    _sub = null;
    state = GpsState.off;
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }
}
