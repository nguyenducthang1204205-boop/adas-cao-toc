/// Bám vết đơn giản theo IoU (thay ByteTrack của Ultralytics ở bản desktop).
///
/// Đủ cho mục đích gán ID ổn định để làm mượt khoảng cách và tính tốc độ tiếp cận theo từng xe.
/// Ghép tham lam theo IoU giảm dần giữa hộp mới và hộp cuối của track (cùng lớp).
library;

import 'dart:math' as math;

import 'yolo.dart';

class _Track {
  final int id;
  Detection last;
  double lastSeen;
  int hits = 1;
  _Track(this.id, this.last, this.lastSeen);
}

class IouTracker {
  final double iouThreshold;
  final double maxAgeS;
  final int minHits;
  final _tracks = <_Track>[];
  int _nextId = 1;

  IouTracker({this.iouThreshold = 0.3, this.maxAgeS = 1.0, this.minHits = 1});

  void reset() {
    _tracks.clear();
    _nextId = 1;
  }

  /// Gán trackId cho các detection (sửa tại chỗ) và trả về chính danh sách đó.
  List<Detection> update(List<Detection> dets, double t) {
    final pairs = <(double, int, int)>[];
    for (var ti = 0; ti < _tracks.length; ti++) {
      for (var di = 0; di < dets.length; di++) {
        if (_tracks[ti].last.classId != dets[di].classId) continue;
        final v = _iou(_tracks[ti].last, dets[di]);
        if (v >= iouThreshold) pairs.add((v, ti, di));
      }
    }
    pairs.sort((a, b) => b.$1.compareTo(a.$1));
    final usedT = <int>{}, usedD = <int>{};
    for (final (_, ti, di) in pairs) {
      if (usedT.contains(ti) || usedD.contains(di)) continue;
      usedT.add(ti);
      usedD.add(di);
      final tr = _tracks[ti]
        ..last = dets[di]
        ..lastSeen = t
        ..hits += 1;
      dets[di].trackId = tr.id;
    }
    for (var di = 0; di < dets.length; di++) {
      if (usedD.contains(di)) continue;
      final tr = _Track(_nextId++, dets[di], t);
      _tracks.add(tr);
      dets[di].trackId = tr.id;
    }
    _tracks.removeWhere((tr) => t - tr.lastSeen > maxAgeS);
    return dets;
  }

  static double _iou(Detection a, Detection b) {
    final xx1 = math.max(a.x1, b.x1), yy1 = math.max(a.y1, b.y1);
    final xx2 = math.min(a.x2, b.x2), yy2 = math.min(a.y2, b.y2);
    final inter = math.max(0.0, xx2 - xx1) * math.max(0.0, yy2 - yy1);
    final union = a.width * a.height + b.width * b.height - inter;
    return union > 0 ? inter / union : 0;
  }
}
