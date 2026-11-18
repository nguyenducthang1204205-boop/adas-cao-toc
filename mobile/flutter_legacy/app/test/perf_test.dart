// Hiệu năng trên máy yếu: chống nhiễu theo thời gian, bộ điều tốc, vùng cắt cho YOLO, isolate xử lý.
import 'dart:async';
import 'dart:isolate';
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:adas_caotoc/core/config.dart';
import 'package:adas_caotoc/core/distance.dart';
import 'package:adas_caotoc/core/governor.dart';
import 'package:adas_caotoc/core/ipm.dart';
import 'package:adas_caotoc/core/pipeline.dart';
import 'package:adas_caotoc/core/roi.dart';
import 'package:adas_caotoc/core/safety.dart';
import 'package:adas_caotoc/core/template_tracker.dart';
import 'package:adas_caotoc/core/yolo.dart';
import 'package:adas_caotoc/detector/detector_service.dart';
import 'package:adas_caotoc/detector/preprocess.dart';
import 'package:adas_caotoc/engine/frame_engine.dart';
import 'package:adas_caotoc/ui/benchmark_screen.dart' show i420Doubled;
import 'package:flutter_test/flutter_test.dart';

FrameResult _result({VehicleState? lead, Risk level = Risk.safe, double speed = 80}) {
  final thr = computeThresholds(speed, const SafetyPolicy());
  return FrameResult([if (lead != null) lead], lead, thr, speed, level, level);
}

VehicleState _vehicle(double d, {double? ttc}) =>
    VehicleState(Detection(0, 0, 10, 10, 0.9, 2, 'car', 1), d, 0, 'IPM', true, null, ttc);

void main() {
  group('Chống nhiễu theo thời gian (khớp adas/alert.py)', () {
    for (final fps in [30, 10]) {
      test('$fps khung/s: nâng mức sau 0,1 s, bỏ qua khung nhầm đơn lẻ', () {
        final h = AlertHysteresis(AlertConfig(escalateSeconds: 0.1));
        double? up;
        for (var i = 0; i < fps; i++) {
          final t = i / fps;
          if (h.update(Risk.danger, t) == Risk.danger) up ??= t;
        }
        expect(up, isNotNull);
        expect(up!, inInclusiveRange(0.1 - 1e-6, 0.1 + 1 / fps));
        h.reset();
        expect(h.update(Risk.danger, 5), Risk.safe);
        expect(h.update(Risk.safe, 5 + 1 / fps), Risk.safe);
      });
    }
    test('0 giây = nâng ngay', () {
      final h = AlertHysteresis(AlertConfig(escalateSeconds: 0));
      expect(h.update(Risk.warning, 0), Risk.warning);
    });
  });

  group('Bộ điều tốc', () {
    test('năng lực theo thời gian YOLO', () {
      expect(capabilityLevel(30), PerfLevel.high);
      expect(capabilityLevel(95), PerfLevel.medium);
      expect(capabilityLevel(200), PerfLevel.low);
    });

    test('hạ mức ngay (cách nhau >= 3 s), nâng mức sau 10 s dư địa, mỗi lần một mức', () {
      final g = Governor(PerfLevel.high);
      expect(g.update(0, yoloMs: 200, procMs: 5), PerfLevel.medium);
      expect(g.update(1, yoloMs: 200, procMs: 5), PerfLevel.medium); // chưa đủ 3 s
      expect(g.update(3, yoloMs: 200, procMs: 5), PerfLevel.low);
      // máy rảnh trở lại: phải chờ đủ 10 s mới lên một mức
      expect(g.update(4, yoloMs: 30, procMs: 5), PerfLevel.low);
      expect(g.update(13.9, yoloMs: 30, procMs: 5), PerfLevel.low);
      expect(g.update(14, yoloMs: 30, procMs: 5), PerfLevel.medium);
      expect(g.update(15, yoloMs: 30, procMs: 5), PerfLevel.medium); // bắt đầu đếm lại
      expect(g.update(24.9, yoloMs: 30, procMs: 5), PerfLevel.medium);
      expect(g.update(25, yoloMs: 30, procMs: 5), PerfLevel.high);
    });

    test('không nâng khi chỉ vừa sát ngưỡng (tránh dao động)', () {
      final g = Governor(PerfLevel.medium);
      for (var t = 0.0; t < 30; t += 1) {
        expect(g.update(t, yoloMs: 46, procMs: 5), PerfLevel.medium); // < 50 nhưng không < 42,5
      }
    });

    test('nhiệt: nóng thì tối đa Trung bình, rất nóng thì Thấp', () {
      final g = Governor(PerfLevel.high);
      expect(g.update(0, yoloMs: 30, procMs: 5, thermal: thermalModerate), PerfLevel.medium);
      expect(g.update(5, yoloMs: 30, procMs: 5, headroom: 0.97), PerfLevel.low);
    });

    test('luồng xử lý quá tải thì hạ một mức', () {
      final g = Governor(PerfLevel.high);
      // mức Cao, camera 30 Hz: ngân sách 33 ms, dùng quá 60 % (20 ms) là quá tải
      expect(g.update(0, yoloMs: 30, procMs: 25, cameraHz: 30), PerfLevel.medium);
    });

    test('khóa tay', () {
      final g = Governor(PerfLevel.high, forced: PerfLevel.low);
      expect(g.update(0, yoloMs: 10, procMs: 1), PerfLevel.low);
      expect(g.effective, PerfLevel.low);
    });

    test('nhịp YOLO theo mức rủi ro', () {
      expect(yoloIntervalS(null), 0);
      expect(yoloIntervalS(_result()), closeTo(1 / 3, 1e-9)); // đường trống
      expect(yoloIntervalS(_result(lead: _vehicle(200))), closeTo(1 / 3, 1e-9)); // xe trước rất xa
      expect(yoloIntervalS(_result(lead: _vehicle(90))), 0); // 80 km/h: ngưỡng 55 m
      expect(yoloIntervalS(_result(lead: _vehicle(90)), thermal: thermalModerate), 0.15);
      expect(yoloIntervalS(_result(lead: _vehicle(60))), 0); // gần hơn 1,5 lần ngưỡng: khẩn
      expect(yoloIntervalS(_result(lead: _vehicle(200, ttc: 3))), 0); // TTC < 4 s
      expect(yoloIntervalS(_result(level: Risk.warning)), 0);
    });
  });

  group('Vùng ảnh đưa vào YOLO', () {
    final calib = CalibrationConfig();
    final m = GroundPlaneMapper(calib, 1280, 720);

    test('dải rộng 288x640: giữ bề ngang, đúng tỉ lệ, chứa chân trời và vùng gần', () {
      final c = wideCrop(m, calib, 1280, 720, 640, 288);
      expect(c.w, 1280);
      expect(c.h, 576);
      expect(c.x, 0);
      expect(c.y, inInclusiveRange(0, 720 - 576));
      final hz = horizonRow(m);
      expect(hz, greaterThan(c.y));
      expect(0.90 * 720, lessThan(c.y + c.h)); // mép dưới hình chữ nhật hiệu chỉnh
    });

    test('mô hình 384x640 (cao hơn khung 16:9): lấy cả khung', () {
      expect(wideCrop(m, calib, 1280, 720, 640, 384).isFull(1280, 720), isTrue);
    });

    test('vùng hẹp ~1:1 quanh điểm tụ; khung 480p thì không dùng', () {
      final n = narrowCrop(m, 1280, 720, 640, 288)!;
      expect((n.w, n.h), (640, 288));
      final vx = vanishingColumn(m), vy = horizonRow(m);
      expect(vx, inInclusiveRange(n.x.toDouble(), (n.x + n.w).toDouble()));
      expect(vy, inInclusiveRange(n.y.toDouble(), (n.y + n.h).toDouble()));
      expect(narrowCrop(GroundPlaneMapper(calib, 720, 480), 720, 480, 640, 288), isNull);
    });
  });

  test('Tiền xử lý cắt vùng: lấy đúng điểm ảnh của vùng, cả khi xoay 180°', () {
    const w = 64, h = 40;
    final bgra = Uint8List(w * h * 4);
    for (var y = 0; y < h; y++) {
      for (var x = 0; x < w; x++) {
        final i = (y * w + x) * 4;
        bgra[i] = x; // B = cột
        bgra[i + 1] = y; // G = hàng
        bgra[i + 2] = 200;
        bgra[i + 3] = 255;
      }
    }
    final pre = Preprocessor(32, 16);
    const crop = CropRect(0, 8, 64, 32); // tỉ lệ 2:1 như ô vào -> không đệm, thu nhỏ một nửa
    final f = FramePacket(w, h, PixelFormat.bgra8888, [bgra], [w * 4], [4], false);
    var t = pre.run(f, crop);
    expect(pre.letterbox.r, 0.5);
    // điểm (0, 0) của ô vào = điểm (1, 9) của khung (tâm khối 2x2 tính từ gốc vùng cắt)
    expect(t[1], closeTo(9 / 255, 1e-6)); // G
    expect(t[2], closeTo(1 / 255, 1e-6)); // B
    // xoay 180°: vùng cắt tính trên ảnh đã xoay -> điểm (1, 9) của ảnh xoay = (62, 30) của bộ đệm
    final rot = FramePacket(w, h, PixelFormat.bgra8888, [bgra], [w * 4], [4], true);
    t = Preprocessor(32, 16).run(rot, crop);
    expect(t[1], closeTo(30 / 255, 1e-6));
    expect(t[2], closeTo(62 / 255, 1e-6));
  });

  test('Benchmark: khung mẫu RGBA -> YUV420 gấp đôi -> tiền xử lý ra lại đúng màu (sai số làm tròn)', () {
    const w = 8, h = 4;
    final rgba = Uint8List(w * h * 4);
    for (var i = 0; i < w * h; i++) {
      rgba.setAll(i * 4, [200, 100, 50, 255]);
    }
    final p = i420Doubled(rgba, w, h);
    expect((p.width, p.height), (16, 8));
    final t = Preprocessor(16, 8).run(p);
    expect(t[0] * 255, closeTo(200, 3));
    expect(t[1] * 255, closeTo(100, 3));
    expect(t[2] * 255, closeTo(50, 3));
  });

  group('Isolate xử lý + YOLO giả', () {
    const fw = 1280, fh = 720;
    final calib = CalibrationConfig();
    final m = GroundPlaneMapper(calib, fw.toDouble(), fh.toDouble());

    List<double> boxAt(double x, double d) {
      final g = m.groundToImage(x, d), l = m.groundToImage(x - 0.9, d), r = m.groundToImage(x + 0.9, d);
      final bw = r.x - l.x;
      return [g.x - bw / 2, g.y - 0.8 * bw, g.x + bw / 2, g.y];
    }

    // khung YUV420 tĩnh: nền phẳng, mỗi xe là một mảng vân trơn (ảnh thật trơn ở mức vài px - bước dò thô
    // 2 px của bộ bám vết dựa vào điều đó; nhiễu trắng từng điểm ảnh thì lệch 1 px đã mất tương quan)
    FramePacket frame(List<List<double>> boxes) {
      final y = Uint8List(fw * fh)..fillRange(0, fw * fh, 90);
      for (final b in boxes) {
        for (var yy = b[1].floor(); yy < b[3].ceil(); yy++) {
          for (var xx = b[0].floor(); xx < b[2].ceil(); xx++) {
            if (xx >= 0 && xx < fw && yy >= 0 && yy < fh) {
              y[yy * fw + xx] = (130 + 60 * math.sin(xx / 7) + 50 * math.cos(yy / 5 + xx / 11)).round().clamp(0, 255);
            }
          }
        }
      }
      final uv = Uint8List((fw ~/ 2) * (fh ~/ 2))..fillRange(0, (fw ~/ 2) * (fh ~/ 2), 128);
      return FramePacket(fw, fh, PixelFormat.yuv420, [y, uv, uv], [fw, fw ~/ 2, fw ~/ 2], [1, 1, 1], false);
    }

    EngineConfig cfg({bool far = false}) => EngineConfig(
          calibration: calib,
          alert: AlertConfig(),
          enabledClasses: const {'car'},
          confidence: 0.35,
          denseTracking: true,
          farDetect: far,
          forcedLevel: null,
          version: 1,
        );

    /// Chạy [n] khung 30 Hz; YOLO giả trả các hộp nằm trọn trong vùng được yêu cầu.
    Future<(List<EngineOutput>, List<DetectRequest>)> run(List<List<double>> boxes, int n,
        {bool far = false, double speed = 80, int replyDelayMs = 0}) async {
      final requests = <DetectRequest>[];
      final fake = ReceivePort();
      fake.listen((msg) {
        if (msg is! DetectRequest) return;
        requests.add(msg);
        final c = msg.crop;
        final dets = [
          for (final b in boxes)
            if (b[0] >= c.x && b[1] >= c.y && b[2] <= c.x + c.w && b[3] <= c.y + c.h)
              Detection(b[0], b[1], b[2], b[3], 0.9, 2, 'car'),
        ];
        final res = DetectResult(dets, fw, fh, 1, 30, 1, msg.tag, msg.crop, msg.narrow);
        if (replyDelayMs == 0) {
          msg.replyTo.send(res);
        } else {
          Timer(Duration(milliseconds: replyDelayMs), () => msg.replyTo.send(res)); // YOLO chậm như máy thật
        }
      });
      final engine = await FrameEngine.spawn(fake.sendPort, 640, 288, cfg(far: far), PerfLevel.high);
      final outs = <EngineOutput>[];
      final f = frame(boxes);
      for (var i = 0; i < n; i++) {
        final done = Completer<void>();
        engine.onOutput = (o) {
          outs.add(o);
          if (o.ack && !done.isCompleted) done.complete();
        };
        expect(engine.submit(f, i / 30, speed, const SafetyPolicy()), isTrue);
        expect(engine.busy, isTrue);
        expect(engine.submit(f, i / 30, speed, const SafetyPolicy()), isFalse); // đang bận: bỏ khung
        await done.future.timeout(const Duration(seconds: 5));
        await Future<void>.delayed(const Duration(milliseconds: 2)); // cho kết quả YOLO giả kịp về
      }
      engine.dispose();
      fake.close();
      return (outs, requests);
    }

    test('xe cùng làn 30 m: bám vết mọi khung, YOLO nhìn dải đường, khoảng cách đúng', () async {
      final (outs, reqs) = await run([boxAt(0, 30)], 45, replyDelayMs: 60);
      final results = outs.where((o) => o.result != null).map((o) => o.result!).toList();
      expect(results.length, greaterThan(40)); // mức Cao: bám vết ở mọi khung camera
      final lead = results.last.lead!;
      expect(lead.distanceM, closeTo(30, 2));
      expect(results.any((r) => r.vehicles.any((v) => v.det.source == 'track')), isTrue);
      expect(reqs, isNotEmpty);
      expect(reqs.first.crop.h, 576); // dải rộng 1280x576 (ô vào 288x640)
      expect(reqs.any((r) => r.narrow), isFalse); // chưa bật thấy xa
      expect(outs.last.stats.yoloMs, closeTo(31, 1));
    });

    test('đường trống: YOLO thưa đi (~3 lần/giây) nhưng vẫn chạy', () async {
      final (_, reqs) = await run([boxAt(4.5, 25)], 60); // chỉ có xe làn bên
      expect(reqs.length, inInclusiveRange(4, 9)); // 2 s x 3 lần/s (+ lần đầu)
    });

    test('thấy xa: cứ 3 lần có 1 khung hẹp; xe gần ngoài vùng hẹp không bị mất', () async {
      final near = boxAt(-3.75, 8), farCar = boxAt(0, 70); // xe làn trái rất gần: nằm ngoài vùng hẹp
      final (outs, reqs) = await run([near, farCar], 90, far: true, speed: 50);
      final narrow = reqs.where((r) => r.narrow).toList();
      expect(narrow, isNotEmpty);
      expect(narrow.length, lessThanOrEqualTo((reqs.length / 3).ceil()));
      // id của xe gần không đổi suốt quá trình (không bị xóa rồi tạo lại khi khung hẹp không thấy nó)
      final ids = <int>{};
      for (final o in outs) {
        for (final v in o.result?.vehicles ?? const <VehicleState>[]) {
          if (v.distanceM < 15) ids.add(v.det.trackId!);
        }
      }
      expect(ids.length, 1);
      expect(outs.last.result!.lead!.distanceM, closeTo(70, 7));
    });
  });

  test('Bám vết: khung YOLO hẹp không tính "bỏ sót" cho xe ngoài vùng hẹp', () {
    const w = 640, h = 360;
    final px = Float32List(w * h)..fillRange(0, w * h, 90);
    for (var y = 250; y < 300; y++) {
      for (var x = 100; x < 170; x++) {
        px[y * w + x] = 130 + 60 * math.sin(x / 4) + 50 * math.cos(y / 3);
      }
    }
    final gray = GrayImage(w, h, px);
    final det = Detection(100, 250, 170, 300, 0.9, 2, 'car');
    const roi = [160.0, 100.0, 480.0, 244.0]; // vùng hẹp quanh điểm tụ, không chứa xe
    final tr = TemplateTracker()..refresh([det], gray, 0, 1);
    tr.refresh([], gray, 0.1, 1, roi: roi);
    tr.refresh([], gray, 0.2, 1, roi: roi);
    expect(tr.tracks.length, 1); // ngoài vùng: chỉ bám tiếp
    tr.refresh([], gray, 0.3, 1);
    tr.refresh([], gray, 0.4, 1);
    expect(tr.tracks, isEmpty); // khung rộng bỏ sót 2 lần liên tiếp: bỏ (chống "xe ma")
  });
}
