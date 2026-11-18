/// Bộ nhận diện YOLO chạy trong isolate nền: tiền xử lý (cắt vùng đường) -> TFLite -> giải mã + NMS.
///
/// Isolate xử lý (engine/frame_engine.dart) gửi khung tới đây khi bộ nhận diện rảnh và nhận kết quả thẳng
/// về cổng của nó (không qua luồng giao diện). Ưu tiên GPU (fp16); lỗi hoặc chậm hơn thì dùng CPU XNNPACK
/// (int8 dynamic-range) với số luồng đo thực tế trên máy.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:isolate';
import 'dart:typed_data';

import 'package:flutter/services.dart';
import 'package:tflite_flutter/tflite_flutter.dart';

import '../core/roi.dart';
import '../core/yolo.dart';
import 'preprocess.dart';

class ModelMeta {
  final int inW, inH;
  final List<String> classes;
  final Map<String, String> files;
  ModelMeta(this.inW, this.inH, this.classes, this.files);

  static Future<ModelMeta> load(String asset) async {
    final j = jsonDecode(await rootBundle.loadString(asset)) as Map<String, dynamic>;
    final inp = j['input'] as Map<String, dynamic>;
    return ModelMeta(inp['width'] as int, inp['height'] as int, List<String>.from(j['classes'] as List),
        Map<String, String>.from(j['files'] as Map));
  }
}

class DetectResult {
  final List<Detection> detections; // pixel khung gốc (đã cộng gốc vùng cắt)
  final int imageW, imageH;
  final double prepMs, inferMs, postMs;
  final double tag; // thời điểm chụp khung (đồng hồ của luồng giao diện)
  final CropRect crop;
  final bool narrow;
  DetectResult(this.detections, this.imageW, this.imageH, this.prepMs, this.inferMs, this.postMs, this.tag,
      this.crop, this.narrow);
}

class DetectError {
  final String message;
  final double tag;
  DetectError(this.message, this.tag);
}

class _Init {
  final SendPort reply;
  final Uint8List gpuModel, cpuModel;
  final bool preferGpu;
  final ModelMeta meta;
  final int cores;
  _Init(this.reply, this.gpuModel, this.cpuModel, this.preferGpu, this.meta, this.cores);
}

/// Yêu cầu nhận diện một khung (gửi từ isolate xử lý).
class DetectRequest {
  final FramePacket frame;
  final double conf, iou;
  final Set<String> enabled;
  final CropRect crop;
  final bool narrow;
  final double tag;
  final SendPort replyTo;
  DetectRequest(this.frame, this.conf, this.iou, this.enabled, this.crop, this.narrow, this.tag, this.replyTo);
}

class DetectorService {
  /// Ô vào 288x640: đúng tỉ lệ dải đường cắt từ khung 16:9 (core/roi.dart); mAP như 384x640 cả khung,
  /// ít hơn 25 % tính toán (tools/eval_mobile.py, docs/ket_qua_mobile.json).
  static const metaAsset = 'assets/models/model_meta_288x640.json';

  final Isolate _isolate;
  final ReceivePort _port;
  final SendPort sendPort; // cổng nhận DetectRequest
  final ModelMeta meta;
  final String backend; // mô tả thiết bị suy luận đang dùng, hiển thị trên HUD
  final double benchMs; // thời gian suy luận đo lúc khởi động (bộ đã chọn)

  DetectorService._(this._isolate, this._port, this.sendPort, this.meta, this.backend, this.benchMs);

  static Future<DetectorService> start({required bool preferGpu}) async {
    final meta = await ModelMeta.load(metaAsset);
    Future<Uint8List> asset(String name) async =>
        (await rootBundle.load('assets/models/$name')).buffer.asUint8List();
    final gpu = await asset(meta.files['fp16']!);
    final cpu = await asset(meta.files['int8']!);
    final port = ReceivePort();
    final isolate = await Isolate.spawn(
        _main, _Init(port.sendPort, gpu, cpu, preferGpu, meta, Platform.numberOfProcessors),
        debugName: 'yolo');
    final first = await port.first;
    if (first is String && first.startsWith('ERR:')) {
      isolate.kill();
      throw StateError(first.substring(4));
    }
    final (send, backend, ms) = first as (SendPort, String, double);
    return DetectorService._(isolate, port, send, meta, backend, ms);
  }

  void dispose() {
    _isolate.kill(priority: Isolate.immediate);
    _port.close();
  }

  // ------------------------------------------------------------------ isolate

  static Future<void> _main(_Init init) async {
    final meta = init.meta;
    final dummy = Float32List(meta.inW * meta.inH * 3);

    Interpreter tryCreate(Uint8List model, Delegate? delegate, {int threads = 4}) {
      final opts = InterpreterOptions()..threads = threads;
      if (delegate != null) opts.addDelegate(delegate);
      final it = Interpreter.fromBuffer(model, options: opts);
      it.getInputTensor(0).data = dummy.buffer.asUint8List(); // chạy thử: lỗi delegate lộ ra ở đây
      it.invoke();
      return it;
    }

    double bench(Interpreter it) {
      final times = <int>[];
      for (var i = 0; i < 4; i++) {
        final sw = Stopwatch()..start();
        it.getInputTensor(0).data = dummy.buffer.asUint8List();
        it.invoke();
        times.add(sw.elapsedMicroseconds);
      }
      times.sort();
      return times[1] / 1000; // bỏ lần đầu (khởi động), lấy gần trung vị
    }

    final errors = <String>[];
    Interpreter? gpu;
    if (init.preferGpu) {
      try {
        gpu = tryCreate(init.gpuModel, Platform.isIOS ? GpuDelegate() : GpuDelegateV2());
      } catch (e) {
        errors.add('GPU: $e');
      }
    }
    // CPU: XNNPackDelegate() tạo bằng tùy chọn mặc định của thư viện native = 1 luồng, và
    // InterpreterOptions.threads không áp cho phần đã giao delegate đó. Không dùng XNNPackDelegateOptions
    // của tflite_flutter 0.12.1: struct tạo bằng calloc lệch với bản native, XNNPACK đọc con trỏ rác và
    // SIGSEGV (TfLiteXNNPackDelegateCreateWithThreadpool, gặp trên máy ảo Android 17).
    // Không gắn delegate thì interpreter tự áp XNNPACK mặc định (hoặc nhân tính thường) với đúng số luồng
    // của InterpreterOptions. Chip big.LITTLE (vd. Helio G96: 2 nhân mạnh + 6 nhân yếu) lại thường chậm đi
    // khi quá nhiều luồng, vì việc chia đều phải chờ luồng rơi vào nhân yếu -> đo vài cấu hình, giữ bộ
    // nhanh nhất (gồm cả cấu hình cũ: XNNPackDelegate() 1 luồng).
    final cpuOptions = <(String, Delegate? Function(), int)>[
      ('CPU XNNPACK · INT8 · 1 luồng', () => XNNPackDelegate(), 1),
      for (final n in init.cores <= 2 ? const [2] : const [2, 4]) ('CPU · INT8 · $n luồng', () => null, n),
    ];
    Interpreter? cpu;
    double cpuMs = double.infinity;
    String cpuName = '';
    for (final (name, delegate, n) in cpuOptions) {
      try {
        final it = tryCreate(init.cpuModel, delegate(), threads: n);
        final ms = bench(it);
        if (ms < cpuMs) {
          cpu?.close();
          cpu = it;
          cpuMs = ms;
          cpuName = name;
        } else {
          it.close();
        }
      } catch (e) {
        errors.add('$name: $e');
      }
    }
    if (gpu == null && cpu == null) {
      init.reply.send('ERR:Không tạo được bộ suy luận TFLite: ${errors.join('; ')}');
      return;
    }

    // GPU delegate có thể chỉ nhận một phần mô hình (phép không hỗ trợ chạy lại trên CPU) và khi đó
    // chậm hơn CPU INT8 -> đo thực tế trên máy, giữ bộ nhanh hơn.
    final Interpreter it;
    final String backend;
    final double ms;
    final gpuName = Platform.isIOS ? 'GPU Metal · FP16' : 'GPU · FP16';
    if (gpu != null && cpu != null) {
      final tg = bench(gpu);
      if (tg <= cpuMs) {
        cpu.close();
        it = gpu;
        ms = tg;
        backend = '$gpuName (${tg.round()} ms; CPU ${cpuMs.round()} ms)';
      } else {
        gpu.close();
        it = cpu;
        ms = cpuMs;
        backend = '$cpuName (${cpuMs.round()} ms; GPU ${tg.round()} ms)';
      }
    } else if (gpu != null) {
      it = gpu;
      ms = bench(gpu);
      backend = gpuName;
    } else {
      it = cpu!;
      ms = cpuMs;
      backend = cpuName;
    }
    final outShape = it.getOutputTensor(0).shape; // [1, 4+nc, N]
    final numAnchors = outShape.last;
    final pre = Preprocessor(meta.inW, meta.inH);

    final port = ReceivePort();
    init.reply.send((port.sendPort, backend, ms));
    await for (final msg in port) {
      if (msg is! DetectRequest) continue;
      try {
        final sw = Stopwatch()..start();
        final input = pre.run(msg.frame, msg.crop);
        final tPrep = sw.elapsedMicroseconds;
        it.getInputTensor(0).data = input.buffer.asUint8List();
        it.invoke();
        final raw = Uint8List.fromList(it.getOutputTensor(0).data);
        final tInfer = sw.elapsedMicroseconds;
        final out = Float32List.view(raw.buffer);
        var dets = decodeYolo(out, numAnchors, meta.classes, pre.letterbox,
            confThreshold: msg.conf, iouThreshold: msg.iou, enabledClasses: msg.enabled);
        dets = _toFrame(dets, msg.crop, msg.frame.width, msg.frame.height, msg.narrow);
        final tPost = sw.elapsedMicroseconds;
        msg.replyTo.send(DetectResult(dets, msg.frame.width, msg.frame.height, tPrep / 1000,
            (tInfer - tPrep) / 1000, (tPost - tInfer) / 1000, msg.tag, msg.crop, msg.narrow));
      } catch (e) {
        msg.replyTo.send(DetectError('$e', msg.tag));
      }
    }
  }

  /// Hộp trong vùng cắt -> khung gốc. Vùng hẹp: bỏ hộp chạm mép trong của vùng (xe bị cắt dở, kích thước
  /// sai) - các xe đó đã có ở khung khóa rộng.
  static List<Detection> _toFrame(List<Detection> dets, CropRect c, int frameW, int frameH, bool narrow) {
    if (c.x == 0 && c.y == 0 && !narrow) return dets;
    const edge = 3.0;
    final out = <Detection>[];
    for (final d in dets) {
      if (narrow) {
        final cutL = d.x1 <= edge && c.x > 0, cutT = d.y1 <= edge && c.y > 0;
        final cutR = d.x2 >= c.w - edge && c.x + c.w < frameW, cutB = d.y2 >= c.h - edge && c.y + c.h < frameH;
        if (cutL || cutT || cutR || cutB) continue;
      }
      out.add(Detection(d.x1 + c.x, d.y1 + c.y, d.x2 + c.x, d.y2 + c.y, d.confidence, d.classId, d.className));
    }
    return out;
  }
}
