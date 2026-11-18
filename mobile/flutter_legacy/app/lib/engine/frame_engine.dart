/// Isolate xử lý: mọi việc nặng của một khung camera chạy ở đây, không chạy trên luồng giao diện.
///
/// ```
/// Camera ──(chỉ giữ khung mới nhất)──► Isolate XỬ LÝ (nhịp theo mức hiệu năng)
///                                        │ xám hoá + bám vết + Kalman + ngưỡng + chống nhiễu
///                                        │ YOLO rảnh và đến lượt: gửi khung + vùng đường cần nhìn
///                                        ▼
///                                      Isolate YOLO (detector_service.dart) ── kết quả về thẳng đây
/// Luồng giao diện ◄── FrameResult (vài trăm byte) ── chỉ vẽ: camera, overlay, HUD
/// ```
///
/// Luồng giao diện chỉ gửi khung mới khi khung trước đã được xác nhận (giống CameraX KEEP_ONLY_LATEST): xử
/// lý chậm thì khung bị bỏ ngay tại camera chứ không xếp hàng, nên không bao giờ dồn khung hay tăng trễ.
library;

import 'dart:async';
import 'dart:isolate';

import '../core/config.dart';
import '../core/governor.dart';
import '../core/pipeline.dart';
import '../core/roi.dart';
import '../core/safety.dart';
import '../detector/detector_service.dart';
import '../detector/gray.dart';
import '../detector/preprocess.dart';

/// Cấu hình của isolate xử lý (gửi lại mỗi khi đổi cài đặt / hiệu chỉnh; [version] đổi thì dựng lại pipeline).
class EngineConfig {
  final CalibrationConfig calibration;
  final AlertConfig alert;
  final Set<String> enabledClasses;
  final double confidence;
  final bool denseTracking;
  final bool farDetect; // xen kẽ khung khóa hẹp quanh điểm tụ để thấy xe ở xa
  final PerfLevel? forcedLevel; // null = tự động
  final int version;
  const EngineConfig({
    required this.calibration,
    required this.alert,
    required this.enabledClasses,
    required this.confidence,
    required this.denseTracking,
    required this.farDetect,
    required this.forcedLevel,
    required this.version,
  });
}

/// Số đo hiệu năng (trung bình trượt) gửi kèm mỗi kết quả.
class EngineStats {
  final double procMs; // xám hoá + bám vết + pipeline một khung
  final double trackHz; // nhịp bám vết thực tế
  final double prepMs, inferMs; // YOLO: tiền xử lý, suy luận
  final double yoloHz;
  final PerfLevel level;
  final bool auto; // bộ điều tốc đang tự chọn mức (không bị khóa)
  final String reason; // lý do đổi mức gần nhất
  final double narrowShare; // tỉ lệ khung khóa hẹp (thấy xa)
  final CropRect? crop; // vùng YOLO nhìn ở lần chạy gần nhất (khung khóa rộng)
  final double frameProcMs; // số đo thô của khung này (0 = khung không bám vết) - cho p95 của benchmark
  final double lastYoloMs; // số đo thô của lần YOLO gần nhất (tiền xử lý + suy luận)
  final int yoloRuns; // tổng số lần YOLO đã chạy
  const EngineStats(this.procMs, this.trackHz, this.prepMs, this.inferMs, this.yoloHz, this.level, this.auto,
      this.reason, this.narrowShare, this.crop, this.frameProcMs, this.lastYoloMs, this.yoloRuns);

  double get yoloMs => prepMs + inferMs;
}

class EngineOutput {
  final FrameResult? result; // null: khung chỉ được xác nhận (chưa đến nhịp bám vết)
  final double t;
  final EngineStats stats;
  final bool ack; // trả lời một khung đã gửi (luồng giao diện được gửi khung tiếp)
  EngineOutput(this.result, this.t, this.stats, {required this.ack});
}

class _Frame {
  final FramePacket packet;
  final double t, speedKmh;
  final SafetyPolicy policy;
  _Frame(this.packet, this.t, this.speedKmh, this.policy);
}

class _Thermal {
  final int status;
  final double? headroom;
  final double cameraHz;
  _Thermal(this.status, this.headroom, this.cameraHz);
}

class _Init {
  final SendPort reply, yolo;
  final int inW, inH;
  final EngineConfig cfg;
  final PerfLevel initial;
  _Init(this.reply, this.yolo, this.inW, this.inH, this.cfg, this.initial);
}

/// Phía luồng giao diện của isolate xử lý.
class FrameEngine {
  final Isolate _isolate;
  final ReceivePort _port;
  final SendPort _send;
  bool _busy = false;
  void Function(EngineOutput)? onOutput;

  FrameEngine._(this._isolate, this._port, this._send, Stream<dynamic> rest) {
    rest.listen((msg) {
      if (msg is! EngineOutput) return;
      if (msg.ack) _busy = false;
      onOutput?.call(msg);
    });
  }

  /// Đang xử lý khung trước: khung camera mới bị bỏ.
  bool get busy => _busy;

  static Future<FrameEngine> start(DetectorService det, EngineConfig cfg, PerfLevel initial) =>
      spawn(det.sendPort, det.meta.inW, det.meta.inH, cfg, initial);

  /// [yolo]: cổng nhận DetectRequest (bộ nhận diện thật, hoặc bộ giả trong test).
  static Future<FrameEngine> spawn(SendPort yolo, int inW, int inH, EngineConfig cfg, PerfLevel initial) async {
    final port = ReceivePort();
    final stream = port.asBroadcastStream();
    final isolate =
        await Isolate.spawn(_main, _Init(port.sendPort, yolo, inW, inH, cfg, initial), debugName: 'adas');
    final send = await stream.first as SendPort;
    return FrameEngine._(isolate, port, send, stream);
  }

  /// Gửi một khung; trả về false (khung bị bỏ) nếu khung trước chưa xong.
  bool submit(FramePacket p, double t, double speedKmh, SafetyPolicy policy) {
    if (_busy) return false;
    _busy = true;
    _send.send(_Frame(p, t, speedKmh, policy));
    return true;
  }

  void configure(EngineConfig cfg) => _send.send(cfg);

  void thermal(int status, double? headroom, double cameraHz) => _send.send(_Thermal(status, headroom, cameraHz));

  void dispose() {
    _isolate.kill(priority: Isolate.immediate);
    _port.close();
  }

  static void _main(_Init init) {
    final port = ReceivePort();
    final yolo = ReceivePort();
    final st = _EngineState(init, yolo.sendPort);
    yolo.listen(st.onYolo);
    port.listen(st.onMessage);
    init.reply.send(port.sendPort);
  }
}

double _ema(double cur, double v, double a) => cur == 0 ? v : (1 - a) * cur + a * v;

class _EngineState {
  final SendPort out, yolo, yoloReply;
  final int inW, inH;
  EngineConfig cfg;
  final Governor gov;
  AdasPipeline? _pipe;
  int _pipeKey = 0;

  int thermal = -1;
  double? headroom;
  double cameraHz = 30;

  bool yoloBusy = false;
  double lastYoloT = -1e9, lastYoloTag = -1;
  int yoloCount = 0;
  DetectResult? pending;
  double lastTrackT = -1e9;
  FrameResult? last;
  double speed = 0;
  SafetyPolicy policy = const SafetyPolicy();
  CropRect? wide;

  double procMs = 0, trackHz = 0, prepMs = 0, inferMs = 0, yoloHz = 0, narrowShare = 0;
  double frameProcMs = 0, lastYoloMs = 0;
  int yoloRuns = 0;

  _EngineState(_Init init, this.yoloReply)
      : out = init.reply,
        yolo = init.yolo,
        inW = init.inW,
        inH = init.inH,
        cfg = init.cfg,
        gov = Governor(init.initial, forced: init.cfg.forcedLevel);

  EngineStats get stats => EngineStats(procMs, trackHz, prepMs, inferMs, yoloHz, gov.effective, gov.forced == null,
      gov.reason, narrowShare, wide, frameProcMs, lastYoloMs, yoloRuns);

  AdasPipeline _ensurePipe(int w, int h) {
    final key = Object.hash(w, h, cfg.version);
    if (_pipe == null || _pipeKey != key) {
      try {
        _pipe = AdasPipeline(cfg.calibration, cfg.alert, w.toDouble(), h.toDouble());
      } catch (_) {
        _pipe = AdasPipeline(CalibrationConfig(), cfg.alert, w.toDouble(), h.toDouble()); // 4 điểm suy biến
      }
      _pipeKey = key;
      pending = null;
      last = null;
    }
    return _pipe!;
  }

  void onMessage(dynamic msg) {
    if (msg is _Frame) {
      _frame(msg);
    } else if (msg is EngineConfig) {
      final dense = cfg.denseTracking;
      cfg = msg;
      gov.forced = msg.forcedLevel;
      if (dense != msg.denseTracking) pending = null;
    } else if (msg is _Thermal) {
      thermal = msg.status;
      headroom = msg.headroom;
      if (msg.cameraHz > 0) cameraHz = msg.cameraHz;
    }
  }

  void _frame(_Frame f) {
    final p = f.packet, t = f.t;
    speed = f.speedKmh;
    policy = f.policy;
    final pipe = _ensurePipe(p.width, p.height);

    // 1) YOLO: rảnh và đã hết khoảng nghỉ theo mức rủi ro -> gửi khung này
    if (!yoloBusy && t - lastYoloT >= yoloIntervalS(last, thermal: thermal) - 1e-3) {
      final (crop, narrow) = _chooseCrop(pipe, p.width, p.height);
      yolo.send(DetectRequest(p, cfg.confidence, 0.45, cfg.enabledClasses, crop, narrow, t, yoloReply));
      yoloBusy = true;
      lastYoloT = t;
    }

    // 2) bám vết theo nhịp của mức hiệu năng; có kết quả YOLO mới thì ghép ngay
    FrameResult? r;
    frameProcMs = 0;
    final lp = levelParams[gov.effective]!;
    if (cfg.denseTracking) {
      final due = pending != null || lp.trackHz <= 0 || t - lastTrackT >= 1 / lp.trackHz - 0.004;
      if (due) {
        final sw = Stopwatch()..start();
        final gray = grayFromPlane(p.planes[0], p.width, p.height, p.rowStrides[0],
            bgra: p.format == PixelFormat.bgra8888, rotate180: p.rotate180);
        pipe.templates.trackedLimit = lp.maxTracked;
        final pend = pending;
        pending = null;
        List<double>? roi;
        if (pend != null && pend.narrow) {
          final c = pend.crop;
          roi = [c.x.toDouble(), c.y.toDouble(), (c.x + c.w).toDouble(), (c.y + c.h).toDouble()];
        }
        r = pipe.processFrame(gray, t, speed, policy, yolo: pend?.detections, yoloT: pend?.tag, yoloRoi: roi);
        frameProcMs = sw.elapsedMicroseconds / 1000;
        procMs = _ema(procMs, frameProcMs, 0.1);
        final dt = t - lastTrackT;
        if (dt > 0 && dt < 2) trackHz = _ema(trackHz, 1 / dt, 0.1);
        lastTrackT = t;
        last = r;
      }
    }

    // 3) bộ điều tốc
    gov.update(t,
        yoloMs: prepMs + inferMs, procMs: procMs, cameraHz: cameraHz, thermal: thermal, headroom: headroom);
    out.send(EngineOutput(r, t, stats, ack: true));
  }

  /// Khung khóa rộng (dải đường) hay hẹp (quanh điểm tụ, cứ 3 lần có 1) - chỉ thấy xa khi đường không gấp.
  (CropRect, bool) _chooseCrop(AdasPipeline pipe, int w, int h) {
    final wc = wideCrop(pipe.mapper, cfg.calibration, w, h, inW, inH);
    wide = wc;
    final l = last;
    final calm = l == null ||
        (riskRank(l.level) < riskRank(Risk.warning) && (l.lead == null || l.lead!.distanceM >= 40));
    final canNarrow = cfg.farDetect &&
        cfg.denseTracking &&
        gov.effective != PerfLevel.low &&
        (prepMs + inferMs) < 150 &&
        calm;
    if (canNarrow) {
      yoloCount++;
      if (yoloCount % 3 == 0) {
        final nc = narrowCrop(pipe.mapper, w, h, inW, inH);
        if (nc != null) return (nc, true);
      }
    }
    return (wc, false);
  }

  void onYolo(dynamic msg) {
    yoloBusy = false;
    if (msg is! DetectResult) return; // DetectError: bỏ qua khung này
    lastYoloMs = msg.prepMs + msg.inferMs;
    yoloRuns++;
    prepMs = _ema(prepMs, msg.prepMs, 0.2);
    inferMs = _ema(inferMs, msg.inferMs, 0.2);
    narrowShare = _ema(narrowShare, msg.narrow ? 1 : 0, 0.1);
    final dt = msg.tag - lastYoloTag;
    if (lastYoloTag >= 0 && dt > 0 && dt < 5) yoloHz = _ema(yoloHz, 1 / dt, 0.2);
    lastYoloTag = msg.tag;
    if (cfg.denseTracking) {
      pending = msg; // ghép ở khung camera kế tiếp
      return;
    }
    // không bám vết: kết quả YOLO là kết quả của khung đó (thời điểm = lúc chụp)
    final pipe = _ensurePipe(msg.imageW, msg.imageH);
    final r = pipe.process(msg.detections, msg.tag, speed, policy);
    last = r;
    out.send(EngineOutput(r, msg.tag, stats, ack: false));
  }
}
