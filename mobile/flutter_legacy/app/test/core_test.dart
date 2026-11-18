// Kiểm tra phần lõi Dart khớp với bản Python (adas/*.py). Dữ liệu chuẩn trong test/fixtures/ do
// Python sinh ra: ipm_python.json (adas.ipm + adas.safety), yolo_raw_9x5040.bin + yolo_expected.json
// (đầu ra thô mô hình fp16 trên một ảnh test và kết quả hậu xử lý tham chiếu).
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:adas_caotoc/core/config.dart';
import 'package:adas_caotoc/core/ipm.dart';
import 'package:adas_caotoc/core/kalman.dart';
import 'package:adas_caotoc/core/pipeline.dart';
import 'package:adas_caotoc/core/safety.dart';
import 'package:adas_caotoc/core/template_tracker.dart';
import 'package:adas_caotoc/core/tracker.dart';
import 'package:adas_caotoc/core/yolo.dart';
import 'package:adas_caotoc/detector/gray.dart';
import 'package:adas_caotoc/detector/preprocess.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, dynamic> _json(String name) =>
    jsonDecode(File('test/fixtures/$name').readAsStringSync()) as Map<String, dynamic>;

void main() {
  // Python đưa 4 điểm vào cv2.getPerspectiveTransform dạng float32 -> lệch ~1e-6 tương đối so với
  // Dart (float64). Dung sai 1e-5 tương đối / 0,1 mm / 0,01 px, nhỏ hơn mọi sai số đo thực tế.
  group('IPM khớp adas/ipm.py', () {
    final fx = _json('ipm_python.json');
    final frame = (fx['frame'] as List).cast<num>();
    final m = GroundPlaneMapper(CalibrationConfig(), frame[0].toDouble(), frame[1].toDouble());

    test('ma trận H', () {
      final h = (fx['H'] as List).expand((r) => (r as List).cast<num>()).toList();
      for (var i = 0; i < 9; i++) {
        expect(m.h.m[i], closeTo(h[i].toDouble(), 1e-5 * (1 + h[i].abs())));
      }
    });

    test('tiêu cự + chân trời', () {
      expect(m.focalPx!, closeTo((fx['focal_px'] as num).toDouble(), 1e-3));
      expect(m.horizonY!, closeTo((fx['horizon_y'] as num).toDouble(), 1e-3));
    });

    test('ảnh -> mặt đường (NaN = null)', () {
      final pts = fx['image_points'] as List, exp = fx['ground'] as List;
      for (var i = 0; i < pts.length; i++) {
        final p = (pts[i] as List).cast<num>();
        final g = m.imageToGround(p[0].toDouble(), p[1].toDouble());
        if (exp[i] == null) {
          expect(g, isNull, reason: 'điểm $p trên chân trời');
        } else {
          final e = (exp[i] as List).cast<num>();
          expect(g!.x, closeTo(e[0].toDouble(), 1e-4));
          expect(g.y, closeTo(e[1].toDouble(), 1e-4));
        }
      }
    });

    test('mặt đường -> ảnh', () {
      final inp = fx['ground_in'] as List, exp = fx['image_back'] as List;
      for (var i = 0; i < inp.length; i++) {
        final p = (inp[i] as List).cast<num>(), e = (exp[i] as List).cast<num>();
        final q = m.groundToImage(p[0].toDouble(), p[1].toDouble());
        expect(q.x, closeTo(e[0].toDouble(), 1e-2));
        expect(q.y, closeTo(e[1].toDouble(), 1e-2));
      }
    });
  });

  group('Ngưỡng an toàn khớp adas/safety.py', () {
    test('mốc biên bảng quy định', () {
      const expected = [(59.9, null), (60.0, 35.0), (60.1, 55.0), (80.0, 55.0), (80.1, 70.0), (100.0, 70.0),
        (100.1, 100.0), (120.0, 100.0)];
      for (final (v, gap) in expected) {
        expect(legalMinGap(v), gap, reason: '$v km/h');
      }
    });

    test('ngưỡng theo điều kiện', () {
      final thr = _json('ipm_python.json')['thresholds'] as Map<String, dynamic>;
      thr.forEach((k, v) {
        final parts = k.split('|');
        final p = conditionPolicy(parts[0], parts[0] == 'heavy_rain' ? ['night'] : []);
        final t = computeThresholds(double.parse(parts[1]), p);
        final e = (v as List).cast<num>();
        expect(t.safeM, closeTo(e[0].toDouble(), 1e-6), reason: k);
        expect(t.dangerM, closeTo(e[1].toDouble(), 1e-6), reason: k);
      });
    });

    test('ngưỡng theo dải tốc độ do người dùng đặt + câu giải thích', () {
      final j = _json('ipm_python.json');
      final bp = j['band_policy'] as Map<String, dynamic>;
      final user = SafetyPolicy(
          timeGapS: (bp['time_gap_s'] as num).toDouble(),
          bandGapsM: [for (final g in bp['band_gaps_m'] as List) (g as num).toDouble()]);
      for (final c in (j['bands'] as List).cast<Map<String, dynamic>>()) {
        final p = conditionPolicy(c['cond'] as String, const [], base: user);
        final t = computeThresholds((c['v'] as num).toDouble(), p);
        final why = '${c['cond']} ${c['v']} km/h';
        expect(t.safeM, closeTo((c['safe'] as num).toDouble(), 1e-6), reason: why);
        expect(t.dangerM, closeTo((c['danger'] as num).toDouble(), 1e-6), reason: why);
        expect(t.bandM, (c['band'] as num?)?.toDouble(), reason: why);
        expect(thresholdBasis(t, p), c['basis'], reason: why);
      }
    });
  });

  test('Giải mã YOLO + NMS khớp bản Python', () {
    final exp = _json('yolo_expected.json');
    final shape = (exp['shape'] as List).cast<int>();
    final bytes = File('test/fixtures/yolo_raw.bin').readAsBytesSync();
    final out = Float32List.view(Uint8List.fromList(bytes).buffer);
    final src = (exp['src'] as List).cast<int>(), inp = (exp['input'] as List).cast<int>(); // [cao, rộng]
    final dets = decodeYolo(out, shape[1], const ['Jeepney', 'bus', 'car', 'motorcycle', 'truck'],
        Letterbox(src[0], src[1], inp[1], inp[0]));
    final want = (exp['detections'] as List).map((d) => (d as List).cast<num>()).toList();
    expect(dets.length, want.length);
    for (var i = 0; i < want.length; i++) {
      final d = dets[i].toList(), w = want[i];
      for (var k = 0; k < 4; k++) {
        expect(d[k], closeTo(w[k].clamp(0, k.isEven ? src[0] : src[1]).toDouble(), 0.05), reason: 'hộp $i[$k]');
      }
      expect(d[4], closeTo(w[4].toDouble(), 1e-5));
      expect(d[5], w[5].toDouble());
    }
  });

  test('Tiền xử lý: letterbox và đổi màu YUV/BGRA', () {
    const w = 64, h = 36;
    final pre = Preprocessor(64, 64);
    // BGRA một màu (B=10, G=20, R=200)
    final bgra = Uint8List(w * h * 4);
    for (var i = 0; i < w * h; i++) {
      bgra.setAll(i * 4, [10, 20, 200, 255]);
    }
    var t = pre.run(FramePacket(w, h, PixelFormat.bgra8888, [bgra], [w * 4], [4], false));
    final lb = pre.letterbox;
    expect(lb.top, 14); // (64 - 36) / 2
    final mid = ((32 * 64) + 32) * 3;
    expect(t[mid], closeTo(200 / 255, 1e-6));
    expect(t[mid + 2], closeTo(10 / 255, 1e-6));
    expect(t[0], closeTo(114 / 255, 1e-6)); // vùng đệm
    // YUV xám (Y=128, U=V=128) -> RGB 128
    final yp = Uint8List(w * h)..fillRange(0, w * h, 128);
    final uv = Uint8List((w ~/ 2) * (h ~/ 2))..fillRange(0, (w ~/ 2) * (h ~/ 2), 128);
    t = pre.run(FramePacket(w, h, PixelFormat.yuv420, [yp, uv, uv], [w, w ~/ 2, w ~/ 2], [1, 1, 1], false));
    expect(t[mid], closeTo(128 / 255, 1e-6));
    expect(t[mid + 1], closeTo(128 / 255, 1e-6));
  });

  test('Pipeline: xe tiến lại gần -> TTC và nâng mức cảnh báo sau 0,1 s', () {
    final cfg = CalibrationConfig();
    final pipe = AdasPipeline(cfg, AlertConfig(escalateSeconds: 0.1), 1280, 720);
    final m = pipe.mapper;
    FrameResult? r;
    // Xe ô tô trong làn, khoảng cách giảm từ 40 m xuống 20 m trong 2 s (tiếp cận 10 m/s)
    for (var i = 0; i <= 60; i++) {
      final t = i / 30;
      final d = 40 - 10 * t;
      final g = m.groundToImage(0, d), l = m.groundToImage(-0.9, d), rr = m.groundToImage(0.9, d);
      final hgt = (rr.x - l.x) * 0.8;
      final det = Detection(l.x, g.y - hgt, rr.x, g.y, 0.9, 2, 'car');
      r = pipe.process([det], t, 80, const SafetyPolicy());
    }
    final lead = r!.lead!;
    expect(lead.distanceM, closeTo(20, 1.5)); // EMA trễ một chút
    expect(lead.closingSpeedMps!, closeTo(10, 1.0));
    expect(lead.ttcS!, closeTo(2.0, 0.4));
    expect(r.level, Risk.danger); // 20 m < 55 m ở 80 km/h và TTC ~2 s
    expect(lead.det.trackId, 1); // cùng một track suốt 2 s
  });

  test('Bám vết IoU giữ ID, tạo ID mới cho xe mới', () {
    final tr = IouTracker();
    final a = tr.update([Detection(100, 100, 200, 200, 0.9, 2, 'car')], 0);
    final b = tr.update([Detection(105, 102, 205, 203, 0.9, 2, 'car'), Detection(600, 100, 700, 200, 0.8, 4, 'truck')], 0.03);
    expect(a[0].trackId, 1);
    expect(b[0].trackId, 1);
    expect(b[1].trackId, 2);
  });

  test('Kalman khớp adas/kalman.py (xe trước phanh + một khung nhận nhầm)', () {
    final rows = (jsonDecode(File('test/fixtures/kalman_python.json').readAsStringSync()) as List)
        .cast<Map<String, dynamic>>();
    RangeKalman? kf;
    for (final r in rows) {
      final t = (r['t'] as num).toDouble(), z = (r['z'] as num).toDouble();
      bool ok = true;
      if (kf == null) {
        kf = RangeKalman(z, t, measurementSigma(z));
      } else {
        kf.predict(t);
        ok = kf.update(z, measurementSigma(z));
      }
      expect(ok, r['accepted'], reason: 't=$t');
      expect(kf.distance, closeTo((r['d'] as num).toDouble(), 1e-9));
      expect(kf.closingSpeed, closeTo((r['closing'] as num).toDouble(), 1e-9));
      expect(kf.rateStd, closeTo((r['rate_std'] as num).toDouble(), 1e-9));
      expect(kf.rateStd < rateStdReport, r['report']);
    }
  });

  test('Bám vết so khớp mẫu khớp adas/tracking.py', () {
    final fx = _json('tracker_python.json');
    final size = (fx['size'] as List).cast<int>();
    final w = size[0], h = size[1];
    final bytes = File('test/fixtures/tracker_frames.bin').readAsBytesSync();
    final tr = TemplateTracker();
    final frames = (fx['frames'] as List).cast<Map<String, dynamic>>();
    for (var i = 0; i < frames.length; i++) {
      final f = frames[i];
      final t = (f['t'] as num).toDouble();
      final px = Float32List(w * h);
      for (var k = 0; k < w * h; k++) {
        px[k] = bytes[i * w * h + k].toDouble();
      }
      final gray = GrayImage(w, h, px);
      final List<Detection> out;
      if (i == 0) {
        final b = (f['true'] as List).cast<num>().map((v) => v.toDouble()).toList();
        out = tr.refresh([Detection(b[0], b[1], b[2], b[3], 0.9, 2, 'car', 7)], gray, t, 1.0);
      } else {
        out = tr.track(gray, t);
      }
      final want = (f['boxes'] as List).cast<Map<String, dynamic>>();
      expect(out.length, want.length, reason: 'khung $i');
      for (var j = 0; j < want.length; j++) {
        expect(out[j].trackId, want[j]['id']);
        expect(out[j].source, want[j]['source'], reason: 'khung $i');
        final wb = (want[j]['box'] as List).cast<num>();
        final ob = [out[j].x1, out[j].y1, out[j].x2, out[j].y2];
        for (var c = 0; c < 4; c++) {
          // Python lấy mẫu bằng cv2.remap (vị trí làm tròn 1/32 px) -> lệch rất nhỏ so với Dart
          expect(ob[c], closeTo(wb[c].toDouble(), 0.15), reason: 'khung $i, cạnh $c');
        }
      }
    }
  });

  test('YOLO về trễ được dời theo chuyển động đã bám từ lúc chụp', () {
    // Ảnh tổng hợp: một khối có họa tiết trôi sang phải 2 px/khung
    const w = 160, h = 90;
    Float32List frame(int shift) {
      final px = Float32List(w * h)..fillRange(0, w * h, 100);
      for (var y = 30; y < 60; y++) {
        for (var x = 40; x < 80; x++) {
          px[y * w + x + shift] = (((x * 7 + y * 13) % 17) * 12).toDouble();
        }
      }
      return px;
    }

    final tr = TemplateTracker();
    tr.refresh([Detection(40, 30, 80, 60, 0.9, 2, 'car')], GrayImage(w, h, frame(0)), 0, 1.0);
    for (var i = 1; i <= 5; i++) {
      tr.track(GrayImage(w, h, frame(2 * i)), i / 30);
    }
    // YOLO chụp lúc khung 1 (khối ở x=42) nhưng về lúc khung 5 (khối ở x=50): phải dời +8 px
    final out = tr.refresh([Detection(42, 30, 82, 60, 0.9, 2, 'car')], GrayImage(w, h, frame(10)), 5 / 30, 1.0,
        detT: 1 / 30);
    expect(out.length, 1);
    expect(out.first.x1, closeTo(50, 0.6));
    expect(out.first.trackId, isNotNull);
  });

  test('Ảnh xám thu nhỏ: trung bình khối + xoay 180°', () {
    // 1280 x 4 -> f = 2 -> 640 x 2
    const w = 1280, h = 4;
    final plane = Uint8List(w * h);
    for (var i = 0; i < plane.length; i++) {
      plane[i] = (i % w) < 2 ? 200 : 0;
    }
    final g = grayFromPlane(plane, w, h, w);
    expect(g.width, 640);
    expect(g.height, 2);
    expect(g.data[0], 200);
    expect(g.data[1], 0);
    final r = grayFromPlane(plane, w, h, w, rotate180: true);
    expect(r.data.last, 200);
  });
}
