/// Đo hiệu năng (benchmark): chạy đúng pipeline + HUD của màn hình lái trên một đoạn video mẫu đóng gói
/// sẵn (assets/bench, 48 khung của videoplayback.mp4, phát qua lại ở 30 khung/giây), thay cho camera.
///
/// Mọi máy nhận cùng một dữ liệu vào, nên số đo so sánh được giữa các máy và giữa các phiên bản app
/// (bảng cho chương đánh giá). Khung mẫu 640x360 được phóng thành YUV420 1280x720 như camera thật.
library;

import 'dart:convert';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';
import 'package:flutter/services.dart';

import '../core/config.dart';
import '../core/governor.dart';
import '../core/ipm.dart';
import '../core/pipeline.dart';
import '../detector/preprocess.dart';
import '../engine/engine_host.dart';
import '../engine/frame_engine.dart';
import '../services/device_info.dart';
import '../services/settings_store.dart';
import 'drive_screen.dart' show techLine;
import 'hud.dart';
import 'theme.dart';

/// RGBA 640x360 -> YUV420 (I420) gấp đôi kích thước: Y phóng 2x2 láng giềng gần, U/V giữ độ phân giải gốc
/// (đúng bằng nửa kích thước như camera). BT.601 toàn dải, hệ số x256 - nghịch đảo của preprocess.dart.
FramePacket i420Doubled(Uint8List rgba, int w, int h) {
  final ow = 2 * w, oh = 2 * h;
  final yp = Uint8List(ow * oh), up = Uint8List(w * h), vp = Uint8List(w * h);
  for (var y = 0; y < h; y++) {
    for (var x = 0; x < w; x++) {
      final i = (y * w + x) * 4;
      final r = rgba[i], g = rgba[i + 1], b = rgba[i + 2];
      final yy = ((77 * r + 150 * g + 29 * b) >> 8).clamp(0, 255);
      final o = 2 * y * ow + 2 * x;
      yp[o] = yy;
      yp[o + 1] = yy;
      yp[o + ow] = yy;
      yp[o + ow + 1] = yy;
      up[y * w + x] = (((-43 * r - 85 * g + 128 * b) >> 8) + 128).clamp(0, 255);
      vp[y * w + x] = (((128 * r - 107 * g - 21 * b) >> 8) + 128).clamp(0, 255);
    }
  }
  return FramePacket(ow, oh, PixelFormat.yuv420, [yp, up, vp], [ow, w, w], [1, 1, 1], false);
}

double _pct(List<double> v, double q) {
  if (v.isEmpty) return 0;
  final s = [...v]..sort();
  return s[((s.length - 1) * q).round()];
}

double _mean(List<double> v) => v.isEmpty ? 0 : v.reduce((a, b) => a + b) / v.length;

class BenchmarkScreen extends StatefulWidget {
  final AppSettings settings;
  const BenchmarkScreen({super.key, required this.settings});

  @override
  State<BenchmarkScreen> createState() => _BenchmarkScreenState();
}

enum _Phase { idle, loading, running, done }

class _BenchmarkScreenState extends State<BenchmarkScreen> with SingleTickerProviderStateMixin {
  AppSettings get s => widget.settings;

  _Phase _phase = _Phase.idle;
  int _durationS = 30;
  String? _error;
  Map<String, dynamic>? _report;

  // dữ liệu mẫu
  final _images = <ui.Image>[];
  final _packets = <FramePacket>[];
  CalibrationConfig? _calib;
  double _speed = 74;
  GroundPlaneMapper? _mapper;

  // lúc chạy
  final _host = EngineHost();
  late final Ticker _ticker = createTicker(_onTick);
  Duration _elapsed = Duration.zero;
  int _frameIdx = -1, _shown = 0;
  final _live = ValueNotifier<FrameResult?>(null);
  FrameResult? _result;
  double _hudT = -1;
  EngineStats? _stats;
  double _fps = 0, _lastResultT = 0;
  int _results = 0;
  final _proc = <double>[], _yolo = <double>[];
  final _levels = <PerfLevel, int>{};
  int _lastYoloRuns = 0;
  final _timings = <FrameTiming>[];
  bool _timingsOn = false;
  ThermalReading _thermalStart = const ThermalReading(-1, null), _thermal = const ThermalReading(-1, null);
  double _lastThermalPoll = 0;

  @override
  void dispose() {
    _ticker.dispose();
    _timingsOff();
    _host.dispose();
    for (final i in _images) {
      i.dispose();
    }
    _live.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    if (_packets.isNotEmpty) return;
    final meta = jsonDecode(await rootBundle.loadString('assets/bench/bench.json')) as Map<String, dynamic>;
    final c = meta['calibration'] as Map<String, dynamic>;
    _calib = CalibrationConfig(
      imagePoints: [for (final p in c['image_points'] as List) [for (final v in p as List) (v as num).toDouble()]],
      rectWidthM: (c['rect_width_m'] as num).toDouble(),
      rectLengthM: (c['rect_length_m'] as num).toDouble(),
      nearDistanceM: (c['near_distance_m'] as num).toDouble(),
    );
    _speed = (meta['speed_kmh'] as num).toDouble();
    final n = meta['frames'] as int;
    for (var i = 0; i < n; i++) {
      final data = await rootBundle.load('assets/bench/f${i.toString().padLeft(2, '0')}.jpg');
      final codec = await ui.instantiateImageCodec(data.buffer.asUint8List());
      final img = (await codec.getNextFrame()).image;
      final rgba = (await img.toByteData(format: ui.ImageByteFormat.rawRgba))!;
      _images.add(img);
      _packets.add(i420Doubled(rgba.buffer.asUint8List(), img.width, img.height));
    }
    final w = _packets.first.width.toDouble(), h = _packets.first.height.toDouble();
    _mapper = GroundPlaneMapper(_calib!, w, h);
  }

  Future<void> _start() async {
    setState(() {
      _phase = _Phase.loading;
      _error = null;
    });
    try {
      await _load();
      await _host.start(s, 1, calibration: _calib);
      _host.engine!.onOutput = _onOutput;
      _proc.clear();
      _yolo.clear();
      _levels.clear();
      _timings.clear();
      _results = 0;
      _lastYoloRuns = 0;
      _fps = 0;
      _frameIdx = -1;
      _result = null;
      _live.value = null;
      _thermalStart = await DeviceInfo.thermal();
      _thermal = _thermalStart;
      SchedulerBinding.instance.addTimingsCallback(_onTimings);
      _timingsOn = true;
      setState(() => _phase = _Phase.running);
      _ticker.start();
    } catch (e) {
      setState(() {
        _phase = _Phase.idle;
        _error = '$e';
      });
    }
  }

  void _timingsOff() {
    if (_timingsOn) SchedulerBinding.instance.removeTimingsCallback(_onTimings);
    _timingsOn = false;
  }

  void _onTimings(List<FrameTiming> t) {
    if (_phase == _Phase.running) _timings.addAll(t);
  }

  /// Mỗi nhịp màn hình: tới khung mẫu mới (30 khung/s, phát qua lại) thì gửi như camera - bận thì bỏ.
  void _onTick(Duration elapsed) {
    _elapsed = elapsed;
    final t = elapsed.inMicroseconds / 1e6;
    if (t >= _durationS) {
      _finish();
      return;
    }
    final n = _packets.length;
    final k = (t * 30).floor();
    if (k != _frameIdx) {
      _frameIdx = k;
      final period = 2 * (n - 1);
      final ph = k % period;
      _shown = ph < n ? ph : period - ph;
      final engine = _host.engine;
      if (engine != null && !engine.busy) engine.submit(_packets[_shown], t, _speed, s.policy);
    }
    if (t - _lastThermalPoll >= 5) {
      _lastThermalPoll = t;
      DeviceInfo.thermal().then((r) {
        _thermal = r;
        _host.engine?.thermal(r.status, r.headroom, 30);
      });
    }
    setState(() {}); // khung mẫu đổi như hình camera
  }

  void _onOutput(EngineOutput o) {
    if (_phase != _Phase.running) return;
    _stats = o.stats;
    if (o.stats.yoloRuns != _lastYoloRuns) {
      _lastYoloRuns = o.stats.yoloRuns;
      _yolo.add(o.stats.lastYoloMs);
    }
    final r = o.result;
    if (r == null) return;
    _results++;
    if (o.stats.frameProcMs > 0) _proc.add(o.stats.frameProcMs);
    _levels[o.stats.level] = (_levels[o.stats.level] ?? 0) + 1;
    final dt = o.t - _lastResultT;
    _lastResultT = o.t;
    if (dt > 0 && dt < 2) _fps = _fps == 0 ? 1 / dt : 0.9 * _fps + 0.1 / dt;
    _live.value = r;
    if (_result == null || _result!.level != r.level || o.t - _hudT >= 0.1) {
      _hudT = o.t;
      _result = r;
    }
  }

  Future<void> _finish() async {
    _ticker.stop();
    _timingsOff();
    final st = _stats;
    final backend = _host.det?.backend ?? '';
    _host.dispose();
    final thermalEnd = await DeviceInfo.thermal();
    final info = await DeviceInfo.info();
    final dur = _durationS.toDouble();
    final build = [for (final t in _timings) t.buildDuration.inMicroseconds / 1000];
    final raster = [for (final t in _timings) t.rasterDuration.inMicroseconds / 1000];
    final jank = _timings.where((t) => t.buildDuration.inMicroseconds > 16667 || t.rasterDuration.inMicroseconds > 16667);
    final total = _levels.values.fold<int>(0, (a, b) => a + b);
    final report = <String, dynamic>{
      'when': DateTime.now().toIso8601String().substring(0, 16).replaceFirst('T', ' '),
      'device': info['model'] ?? '',
      'soc': info['soc'] ?? '',
      'os': info['os'] ?? '',
      'cores': info['cores'] ?? 0,
      'ram_mb': info['ram_mb'] ?? 0,
      'backend': backend,
      'duration_s': _durationS,
      'mode': s.perfMode,
      'dense': s.denseTracking,
      'far': s.farDetect,
      'ui_fps': _timings.length / dur,
      'jank_pct': _timings.isEmpty ? 0 : 100 * jank.length / _timings.length,
      'build_p95': _pct(build, 0.95),
      'raster_p95': _pct(raster, 0.95),
      'result_hz': _results / dur,
      'proc_avg': _mean(_proc),
      'proc_p95': _pct(_proc, 0.95),
      'yolo_avg': _mean(_yolo),
      'yolo_p95': _pct(_yolo, 0.95),
      'yolo_hz': _yolo.length / dur,
      'levels': {for (final e in _levels.entries) e.key.name: total == 0 ? 0 : 100 * e.value / total},
      'level_end': st?.level.name ?? '',
      'thermal_start': _thermalStart.status,
      'thermal_end': thermalEnd.status,
    };
    s.benchHistory.insert(0, report);
    if (s.benchHistory.length > AppSettings.maxBench) s.benchHistory.removeRange(AppSettings.maxBench, s.benchHistory.length);
    await s.save();
    if (!mounted) return;
    setState(() {
      _report = report;
      _phase = _Phase.done;
    });
  }

  void _stop() {
    _ticker.stop();
    _timingsOff();
    _host.dispose();
    setState(() => _phase = _Phase.idle);
  }

  // ------------------------------------------------------------------ UI

  @override
  Widget build(BuildContext context) {
    if (_phase == _Phase.running) return _running();
    return Scaffold(
      backgroundColor: AppColors.surface,
      appBar: AppBar(
        title: Text('Đo hiệu năng', style: AppText.title.copyWith(fontSize: 20)),
        leading: IconButton(
          tooltip: 'Quay lại',
          icon: const Icon(Icons.arrow_back_rounded),
          onPressed: () => Navigator.maybePop(context),
        ),
      ),
      body: SafeArea(
        top: false,
        child: Align(
          alignment: Alignment.topCenter,
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 760),
            child: ListView(padding: const EdgeInsets.fromLTRB(Space.lg, Space.sm, Space.lg, Space.xxl), children: [
              _card(Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(
                  'Chạy đúng chuỗi xử lý của màn hình lái (YOLO, bám vết, cảnh báo, HUD) trên một đoạn video mẫu '
                  'đóng gói sẵn thay cho camera. Mọi máy nhận cùng dữ liệu nên kết quả so sánh được giữa các máy. '
                  'Bản 5 phút cho biết máy có nóng lên và tự hạ mức hay không.',
                  style: AppText.body.copyWith(color: AppColors.textSecondary),
                ),
                const SizedBox(height: Space.lg),
                Wrap(spacing: Space.sm, children: [
                  for (final d in const [30, 300])
                    ChoiceChip(
                      label: Text(d == 30 ? '30 giây' : '5 phút (đo nhiệt)'),
                      selected: _durationS == d,
                      onSelected: _phase == _Phase.loading ? null : (_) => setState(() => _durationS = d),
                      labelStyle: AppText.caption.copyWith(color: _durationS == d ? AppColors.text : AppColors.textSecondary),
                      selectedColor: AppColors.accentSoft,
                      backgroundColor: AppColors.surfaceRaised,
                      side: BorderSide(color: _durationS == d ? AppColors.accent : AppColors.stroke),
                      shape: const StadiumBorder(),
                    ),
                ]),
                const SizedBox(height: Space.lg),
                SizedBox(
                  height: 52,
                  child: FilledButton.icon(
                    style: FilledButton.styleFrom(backgroundColor: AppColors.accent, foregroundColor: AppColors.onAccent),
                    onPressed: _phase == _Phase.loading ? null : _start,
                    icon: _phase == _Phase.loading
                        ? const SizedBox.square(
                            dimension: 18, child: CircularProgressIndicator(strokeWidth: 2.5, color: AppColors.onAccent))
                        : const Icon(Icons.play_arrow_rounded),
                    label: Text(_phase == _Phase.loading ? 'Đang chuẩn bị…' : 'Bắt đầu đo',
                        style: AppText.bodyStrong.copyWith(color: AppColors.onAccent)),
                  ),
                ),
                if (_error != null) ...[
                  const SizedBox(height: Space.md),
                  Text('Không chạy được: $_error', style: AppText.caption.copyWith(color: AppColors.danger)),
                ],
              ])),
              if (_report != null) ...[
                const SizedBox(height: Space.lg),
                _resultCard(_report!, highlight: true),
              ],
              if (s.benchHistory.length > (_report != null ? 1 : 0)) ...[
                const SizedBox(height: Space.xl),
                Row(children: [
                  Expanded(child: Text('Các lần đo trước', style: AppText.bodyStrong)),
                  TextButton(
                    onPressed: () async {
                      s.benchHistory.clear();
                      await s.save();
                      setState(() => _report = null);
                    },
                    child: const Text('Xóa lịch sử'),
                  ),
                ]),
                for (final r in s.benchHistory.skip(_report != null ? 1 : 0)) ...[
                  const SizedBox(height: Space.sm),
                  _resultCard(r),
                ],
              ],
            ]),
          ),
        ),
      ),
    );
  }

  Widget _card(Widget child, {Color? border}) => Container(
        padding: const EdgeInsets.all(Space.lg),
        decoration: BoxDecoration(
          color: AppColors.surfaceRaised,
          borderRadius: BorderRadius.circular(Radii.md),
          border: Border.all(color: border ?? AppColors.stroke),
        ),
        child: child,
      );

  Widget _resultCard(Map<String, dynamic> r, {bool highlight = false}) {
    final text = benchReportText(r);
    final lines = text.split('\n');
    return _card(
      border: highlight ? AppColors.accent : null,
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(child: Text(lines.first, style: AppText.bodyStrong)),
          IconButton(
            tooltip: 'Sao chép kết quả',
            icon: const Icon(Icons.copy_rounded, size: 20),
            onPressed: () {
              Clipboard.setData(ClipboardData(text: text));
              ScaffoldMessenger.of(context)
                  .showSnackBar(const SnackBar(content: Text('Đã sao chép kết quả đo')));
            },
          ),
        ]),
        const SizedBox(height: Space.xs),
        for (final l in lines.skip(1))
          Padding(
            padding: const EdgeInsets.only(top: 2),
            child: Text(l, style: AppText.caption.copyWith(height: 1.4, color: AppColors.text)),
          ),
      ]),
    );
  }

  Widget _running() {
    final st = _stats;
    final t = _elapsed.inMicroseconds / 1e6;
    final img = _images.isEmpty ? null : _images[_shown];
    final w = _packets.isEmpty ? 1280.0 : _packets.first.width.toDouble();
    final h = _packets.isEmpty ? 720.0 : _packets.first.height.toDouble();
    return Scaffold(
      backgroundColor: AppColors.bg,
      body: Stack(children: [
        Positioned.fill(
          child: DriveHud(
            camera: img == null ? null : RawImage(image: img, fit: BoxFit.fill),
            live: _live,
            s: HudState(
              result: _result,
              mapper: _mapper,
              imageW: w,
              imageH: h,
              speedKmh: _speed,
              speedSource: SpeedSource.manual,
              policy: s.policy,
              conditionKey: s.conditionKey,
              modifiers: s.modifierKeys,
              calibrated: true,
              soundOn: false,
              cameraReady: true,
              techText: st == null
                  ? 'Đang khởi động…'
                  : techLine(st,
                      fps: _fps, camHz: 30, backend: _host.det?.backend ?? '', dense: s.denseTracking,
                      thermal: _thermal.status),
            ),
            onCalibrate: () {},
            onSettings: () {},
            onToggleSound: () {},
            onConditions: () {},
            onSpeedStep: (_) {},
          ),
        ),
        Positioned(
          right: Space.lg,
          bottom: Space.lg,
          child: Row(children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: Space.md, vertical: Space.sm),
              decoration: BoxDecoration(color: AppColors.glassStrong, borderRadius: BorderRadius.circular(Radii.pill)),
              child: Text('Đang đo ${t.floor()}/$_durationS s',
                  style: AppText.caption.copyWith(color: AppColors.text)),
            ),
            const SizedBox(width: Space.sm),
            FilledButton.tonalIcon(
              onPressed: _stop,
              icon: const Icon(Icons.stop_rounded),
              label: const Text('Dừng'),
            ),
          ]),
        ),
      ]),
    );
  }
}

String _n(Object? v, [int digits = 0]) => vn((v as num?)?.toDouble() ?? 0, digits);

/// Báo cáo một lần đo dạng chữ (hiển thị + sao chép vào luận văn).
String benchReportText(Map<String, dynamic> r) {
  final levels = (r['levels'] as Map?)?.cast<String, dynamic>() ?? {};
  final lv = [
    for (final l in PerfLevel.values)
      if ((levels[l.name] as num? ?? 0) > 0) '${perfLevelNames[l]} ${_n(levels[l.name])} %'
  ].join(', ');
  final ram = (r['ram_mb'] as num? ?? 0) > 0 ? ' · RAM ${_n((r['ram_mb'] as num) / 1024, 1)} GB' : '';
  final mode = perfLevelFromName(r['mode'] as String?);
  return [
    '${r['device'] ?? 'Máy không rõ'} · ${r['when']}',
    'Chip: ${r['soc']} · ${r['cores']} nhân$ram · ${r['os']}',
    'Bộ suy luận: ${r['backend']}',
    'Đo ${r['duration_s']} s · mức ${mode == null ? 'tự động' : 'khóa ${perfLevelNames[mode]}'}'
        ' · bám vết ${r['dense'] == true ? 'bật' : 'tắt'} · thấy xa ${r['far'] == true ? 'bật' : 'tắt'}',
    'Giao diện: ${_n(r['ui_fps'])} khung/s, khung giật ${_n(r['jank_pct'], 1)} % '
        '(dựng p95 ${_n(r['build_p95'], 1)} ms, vẽ p95 ${_n(r['raster_p95'], 1)} ms)',
    'Cảnh báo cập nhật ${_n(r['result_hz'], 1)} lần/s · xử lý một khung TB ${_n(r['proc_avg'], 1)} ms '
        '(p95 ${_n(r['proc_p95'], 1)} ms)',
    'YOLO TB ${_n(r['yolo_avg'])} ms (p95 ${_n(r['yolo_p95'])} ms) · ${_n(r['yolo_hz'], 1)} lần/s',
    'Mức hiệu năng: $lv · nhiệt ${DeviceInfo.thermalName(r['thermal_start'] as int? ?? -1)} '
        'sang ${DeviceInfo.thermalName(r['thermal_end'] as int? ?? -1)}',
  ].join('\n');
}
