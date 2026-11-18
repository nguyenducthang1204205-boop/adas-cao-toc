/// Màn hình lái xe - phần logic: camera, isolate xử lý + YOLO nền, GPS, âm thanh. Giao diện: hud.dart.
///
/// Luồng giao diện không xử lý ảnh: mỗi khung camera chỉ được chép sang isolate xử lý (engine/frame_engine.dart)
/// nếu khung trước đã xong, còn không thì bỏ. Overlay vẽ lại theo nhịp kết quả, các cụm đồng hồ dựng lại
/// ~10 lần/giây (số nhảy nhanh hơn mắt cũng không đọc kịp), riêng mức cảnh báo đổi thì cập nhật ngay.
library;

import 'dart:async';
import 'dart:io';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:wakelock_plus/wakelock_plus.dart';

import '../core/config.dart';
import '../core/governor.dart';
import '../core/ipm.dart';
import '../core/pipeline.dart';
import '../core/violations.dart';
import '../detector/preprocess.dart';
import '../engine/engine_host.dart';
import '../engine/frame_engine.dart';
import '../services/alert_player.dart';
import '../services/device_info.dart';
import '../services/gps_speed.dart';
import '../services/settings_store.dart';
import '../services/violation_log.dart';
import 'assistant_sheet.dart';
import 'calibration_screen.dart';
import 'condition_sheet.dart';
import 'hud.dart';
import 'settings_screen.dart';
import 'theme.dart';

/// Gói một khung camera để gửi sang isolate (SendPort chép dữ liệu một lần, không cần chép trước).
FramePacket packetFromCamera(CameraImage img, {required bool rotate180}) {
  final format = switch (img.format.group) {
    ImageFormatGroup.bgra8888 => PixelFormat.bgra8888,
    ImageFormatGroup.nv21 => PixelFormat.nv21,
    _ => PixelFormat.yuv420,
  };
  return FramePacket(
    img.width,
    img.height,
    format,
    [for (final p in img.planes) p.bytes],
    [for (final p in img.planes) p.bytesPerRow],
    [for (final p in img.planes) p.bytesPerPixel ?? 1],
    rotate180,
  );
}

/// Dòng thông số kỹ thuật trên HUD (cũng dùng cho màn hình benchmark).
String techLine(EngineStats st,
    {required double fps, required double camHz, required String backend, required bool dense, int thermal = -1}) {
  final lvl = '${perfLevelNames[st.level]}${st.auto ? '' : ' (khóa)'}';
  final track = dense ? ' · bám vết ${st.procMs.toStringAsFixed(0)} ms, ${st.trackHz.toStringAsFixed(0)}/s' : '';
  final far = st.narrowShare > 0.02 ? ' · thấy xa ${(st.narrowShare * 100).round()} %' : '';
  final crop = st.crop == null ? '' : ' · vùng ${st.crop!.w}x${st.crop!.h}';
  final heat = thermal >= 0 ? ' · nhiệt ${DeviceInfo.thermalName(thermal)}' : '';
  return '${fps.toStringAsFixed(0)} FPS (camera ${camHz.toStringAsFixed(0)}) · mức $lvl$track\n'
      'YOLO ${st.yoloMs.toStringAsFixed(0)} ms (${st.yoloHz.toStringAsFixed(1)}/s)$far$crop$heat\n$backend';
}

class DriveScreen extends StatefulWidget {
  final AppSettings settings;
  const DriveScreen({super.key, required this.settings});

  @override
  State<DriveScreen> createState() => _DriveScreenState();
}

class _DriveScreenState extends State<DriveScreen> with WidgetsBindingObserver {
  AppSettings get s => widget.settings;

  CameraController? _cam;
  CameraDescription? _camDesc;
  bool _camLow = false; // camera đang mở ở 480p
  final _host = EngineHost();
  int _calibVersion = 0;
  FrameResult? _result; // kết quả các cụm đồng hồ đang hiển thị
  final _live = ValueNotifier<FrameResult?>(null); // kết quả mới nhất cho overlay
  double _hudT = -1;
  GroundPlaneMapper? _mapper; // cho overlay (luồng giao diện tự dựng, rẻ)
  int _mapperKey = 0;
  double _imgW = 0, _imgH = 0;
  final _gps = GpsSpeed();
  final _alerts = AlertPlayer();
  final _clock = Stopwatch()..start();
  String? _error;
  bool _paused = false;
  bool _inSettings = false; // camera đóng trong lúc ở Cài đặt; quay về mới mở lại
  // Trợ lý AI + nhật ký vi phạm (giống hai thẻ dưới cột phải của bản desktop)
  final _chat = AssistantChat();
  final _log = ViolationLog();
  ViolationRecorder? _recorder;
  double _lastTouch = 0;

  // hiệu năng
  EngineStats? _stats;
  double _fps = 0, _lastResultT = 0;
  double _camHz = 0, _lastCamT = 0; // tốc độ camera gửi khung (chẩn đoán: máy chậm hay camera chậm)
  ThermalReading _thermal = const ThermalReading(-1, null);
  Timer? _thermalTimer;
  // tự kiểm tra máy (mục "Máy của bạn: mức ...")
  double? _firstYoloT;
  bool _selfTestDone = false;
  String? _perfNotice;
  bool _perfWeak = false;
  Timer? _noticeTimer;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    WakelockPlus.enable();
    _alerts.init();
    _gps.addListener(_onGps);
    if (s.useGps) _gps.start();
    _startCamera();
    _log.load().then((_) {
      if (mounted) setState(() => _recorder = _log.startSession());
    });
    // Android ADPF: đọc nhiệt độ thưa (dư nhiệt chỉ hợp lệ khi gọi cách nhau >= 1 s)
    _thermalTimer = Timer.periodic(const Duration(seconds: 5), (_) => _pollThermal());
    _pollThermal();
  }

  @override
  void dispose() {
    final end = _recorder?.close(_clock.elapsedMicroseconds / 1e6);
    if (end != null) _log.apply([end]);
    _chat.dispose();
    _log.dispose();
    WidgetsBinding.instance.removeObserver(this);
    WakelockPlus.disable();
    _thermalTimer?.cancel();
    _noticeTimer?.cancel();
    _gps.removeListener(_onGps);
    _gps.dispose();
    _alerts.dispose();
    _host.dispose();
    _cam?.dispose();
    _live.dispose();
    super.dispose();
  }

  Future<void> _pollThermal() async {
    final r = await DeviceInfo.thermal();
    _thermal = r;
    _host.engine?.thermal(r.status, r.headroom, _camHz);
  }

  void _onGps() {
    if (mounted && _result == null) setState(() {});
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    final cam = _cam;
    if (state == AppLifecycleState.inactive || state == AppLifecycleState.paused) {
      if (cam != null && cam.value.isInitialized) {
        _cam = null;
        cam.dispose();
        if (mounted) setState(() {});
      }
    } else if (state == AppLifecycleState.resumed && _cam == null && !_inSettings) {
      _startCamera();
    }
  }

  Future<void> _startCamera() async {
    // Mở camera song song với bộ nhận diện (đo GPU/CPU lúc khởi động mất vài giây trên máy yếu): hình
    // hiện ngay, khung camera bị bỏ qua cho tới khi isolate xử lý sẵn sàng.
    final engineReady = _startEngine();
    try {
      final cams = await availableCameras();
      if (cams.isEmpty) throw StateError('Không tìm thấy camera');
      _camDesc = cams.firstWhere((c) => c.lensDirection == CameraLensDirection.back, orElse: () => cams.first);
      _camLow = s.lowCamera;
      final cam = CameraController(
        _camDesc!,
        // 1280x720: đủ cho ô vào 640 px bề ngang; máy yếu (mức Thấp) 480p: bớt 2/3 dữ liệu mỗi khung
        _camLow ? ResolutionPreset.medium : ResolutionPreset.high,
        enableAudio: false,
        imageFormatGroup: Platform.isIOS ? ImageFormatGroup.bgra8888 : ImageFormatGroup.yuv420,
      );
      await cam.initialize();
      await cam.lockCaptureOrientation(DeviceOrientation.landscapeLeft);
      if (!mounted) {
        cam.dispose();
        return;
      }
      _cam = cam;
      _error = null;
      setState(() {});
      await cam.startImageStream(_onImage);
      await engineReady;
    } on CameraException catch (e) {
      setState(() => _error = e.code == 'CameraAccessDenied'
          ? 'Ứng dụng cần quyền camera. Hãy cấp quyền trong Cài đặt của điện thoại.'
          : 'Lỗi camera: ${e.description ?? e.code}');
    } catch (e) {
      setState(() => _error = '$e');
    }
  }

  Future<void> _startEngine() async {
    try {
      await _host.start(s, _calibVersion);
      _host.engine!.onOutput = _onOutput;
      if (mounted) setState(() {});
    } catch (e) {
      if (mounted) setState(() => _error = 'Không khởi động được bộ nhận diện: $e');
    }
  }

  Future<void> _stopStream() async {
    final cam = _cam;
    if (cam != null && cam.value.isStreamingImages) await cam.stopImageStream().catchError((_) {});
  }

  Future<void> _resumeStream() async {
    final cam = _cam;
    if (cam != null && cam.value.isInitialized && !cam.value.isStreamingImages) {
      await cam.startImageStream(_onImage).catchError((_) {});
    }
  }

  /// Ảnh từ cảm biến cần xoay 180° khi cảm biến lắp ngược (sensorOrientation 270) - hiếm gặp.
  bool get _rotate180 => ((_camDesc?.sensorOrientation ?? 90) == 270) != s.rotate180;

  void _onImage(CameraImage img) {
    final t = _clock.elapsedMicroseconds / 1e6;
    final camDt = t - _lastCamT;
    _lastCamT = t;
    if (camDt > 0 && camDt < 2) _camHz = _camHz == 0 ? 1 / camDt : 0.9 * _camHz + 0.1 / camDt;
    final engine = _host.engine;
    if (_paused || engine == null || engine.busy) return; // chỉ giữ khung mới nhất
    if (img.width != _imgW || img.height != _imgH) {
      _imgW = img.width.toDouble();
      _imgH = img.height.toDouble();
    }
    engine.submit(packetFromCamera(img, rotate180: _rotate180), t, _speedKmh, s.policy);
  }

  void _onOutput(EngineOutput o) {
    _stats = o.stats;
    if (o.stats.yoloMs > 0) _firstYoloT ??= o.t;
    if (!_selfTestDone && _firstYoloT != null && o.t - _firstYoloT! >= 4) _selfTest(o.stats);
    final r = o.result;
    if (r == null || !mounted) return;
    final dt = o.t - _lastResultT;
    _lastResultT = o.t;
    if (dt > 0 && dt < 2) _fps = _fps == 0 ? 1 / dt : 0.9 * _fps + 0.1 / dt;
    _publish(r, o.t);
  }

  /// Sau ~4 giây chạy thật: báo mức hiệu năng của máy (lần đầu hoặc khi đổi), máy yếu thì báo mỗi phiên.
  void _selfTest(EngineStats st) {
    _selfTestDone = true;
    final cap = capabilityLevel(st.yoloMs);
    final capName = cap.name;
    final weak = st.yoloMs > yoloMsWeak;
    final changed = s.lastLevel != capName;
    if (changed) {
      s.lastLevel = capName;
      s.save();
    }
    if (!weak && !changed) return;
    final hz = s.denseTracking ? st.trackHz : st.yoloHz;
    _perfWeak = weak;
    _perfNotice = weak
        ? 'Máy yếu: mỗi lần nhận diện mất ${st.yoloMs.round()} ms. Cảnh báo chỉ mang tính tham khảo.'
        : 'Máy của bạn: mức ${perfLevelNames[cap]} · YOLO ${st.yoloMs.round()} ms · '
            'cảnh báo cập nhật ${hz.round()} lần/giây';
    _noticeTimer?.cancel();
    _noticeTimer = Timer(Duration(seconds: weak ? 12 : 7), () {
      if (mounted) setState(() => _perfNotice = null);
    });
    if (mounted) setState(() {});
  }

  GroundPlaneMapper? _mapperFor(double w, double h) {
    if (w <= 0 || h <= 0) return _mapper;
    final key = Object.hash(w, h, _calibVersion);
    if (_mapper == null || _mapperKey != key) {
      try {
        _mapper = GroundPlaneMapper(s.calibration, w, h);
      } catch (_) {
        _mapper = GroundPlaneMapper(CalibrationConfig(), w, h); // 4 điểm suy biến -> mặc định
      }
      _mapperKey = key;
    }
    return _mapper;
  }

  void _publish(FrameResult r, double t) {
    _alerts.update(r.level, t, sound: s.alert.soundEnabled, voice: s.alert.voiceEnabled);
    final rec = _recorder;
    if (rec != null) {
      final p = s.policy;
      final ev = rec.update(r, t, _speedKmh, p.condition, p.weatherFactor);
      if (ev.isNotEmpty) {
        _log.apply(ev);
      } else if (rec.current != null && t - _lastTouch > 0.5) {
        _lastTouch = t; // khoảng cách nhỏ nhất của đợt đang mở: vẽ lại danh sách, không ghi
        _log.touch();
      }
    }
    _live.value = r; // overlay vẽ lại ngay
    final prev = _result;
    final urgent = prev == null || prev.level != r.level || (prev.lead == null) != (r.lead == null);
    if (!urgent && t - _hudT < 0.1) return;
    _hudT = t;
    setState(() => _result = r);
  }

  double get _speedKmh {
    final g = s.useGps ? _gps.speedKmh : null;
    return g ?? s.manualSpeedKmh;
  }

  bool get _speedFromGps => s.useGps && _gps.speedKmh != null;

  void _syncEngine() => _host.configure(s, _calibVersion);

  Future<void> _openCalibration() async {
    final cam = _cam;
    if (cam == null) return;
    _paused = true;
    await _stopStream();
    if (!mounted) return;
    final updated = await Navigator.of(context).push<CalibrationConfig>(MaterialPageRoute(
      builder: (_) => CalibrationScreen(
        preview: CameraPreview(cam),
        initial: s.calibration,
        imageW: _imgW > 0 ? _imgW : 1280,
        imageH: _imgH > 0 ? _imgH : 720,
      ),
    ));
    if (updated != null) {
      s.calibration = updated;
      s.calibrated = true;
      await s.save();
      _calibVersion++;
      _syncEngine();
    }
    _paused = false;
    await _resumeStream();
    if (mounted) setState(() {});
  }

  Future<void> _openSettings() async {
    // Đóng hẳn camera khi ở Cài đặt (chỉ dừng luồng ảnh thì phần xem trước vẫn chạy ngầm): máy rảnh cho
    // benchmark, đỡ pin; quay về thì mở lại (độ phân giải có thể đã đổi theo mức hiệu năng).
    _paused = true;
    _inSettings = true;
    final cam = _cam;
    _cam = null;
    if (mounted) setState(() {});
    await cam?.dispose();
    if (!mounted) return;
    await Navigator.of(context)
        .push(MaterialPageRoute(builder: (_) => SettingsScreen(settings: s, alerts: _alerts)));
    _inSettings = false;
    _calibVersion++; // cấu hình cảnh báo có thể đổi
    if (s.useGps) {
      _gps.start();
    } else {
      _gps.stop();
    }
    if (_host.needsRestart(s)) {
      _host.dispose();
      _selfTestDone = false;
      _firstYoloT = null;
    } else {
      _syncEngine();
    }
    _paused = false;
    if (!mounted) return;
    await _startCamera();
    if (mounted) setState(() {});
  }

  // ------------------------------------------------------------------ UI

  SpeedSource get _speedSource {
    if (!s.useGps) return SpeedSource.manual;
    if (_speedFromGps) return SpeedSource.gps;
    return switch (_gps.state) {
      GpsState.noPermission => SpeedSource.noPermission,
      GpsState.off => SpeedSource.gpsOff,
      _ => SpeedSource.waiting,
    };
  }

  String get _techText {
    final st = _stats;
    final backend = _host.det?.backend ?? '…';
    if (st == null) return 'Đang khởi động…\n$backend';
    return techLine(st,
        fps: _fps, camHz: _camHz, backend: backend, dense: s.denseTracking, thermal: _thermal.status);
  }

  void _stepSpeed(double d) {
    s.manualSpeedKmh = (s.manualSpeedKmh + d).clamp(20, 140);
    s.save();
    setState(() {});
  }

  Future<void> _openConditions() => showConditionSheet(
        context,
        conditionKey: s.conditionKey,
        modifierKeys: s.modifierKeys,
        onCondition: (k) {
          // giống nút "Sương mù" của bản desktop ("…tầm nhìn khoảng 100 m")
          s.applyCondition(k, s.modifierKeys, k == 'fog' ? 100 : 0);
          s.save();
          setState(() {});
        },
        onModifier: (k, on) {
          on ? s.modifierKeys.add(k) : s.modifierKeys.remove(k);
          s.save();
          setState(() {});
        },
      );

  Future<void> _openAssistant() => showAssistantSheet(
        context,
        chat: _chat,
        log: _log,
        onAsk: (text) {
          final wasGps = s.useGps;
          _chat.ask(text, s, _speedKmh);
          if (wasGps && !s.useGps) _gps.stop();
          setState(() {});
        },
      );

  @override
  Widget build(BuildContext context) {
    final cam = _cam;
    final ready = cam != null && cam.value.isInitialized;
    final iw = _imgW > 0 ? _imgW : (_camLow ? 720.0 : 1280.0), ih = _imgH > 0 ? _imgH : (_camLow ? 480.0 : 720.0);
    return Scaffold(
      backgroundColor: AppColors.bg,
      body: DriveHud(
        camera: ready ? CameraPreview(cam) : null,
        live: _live,
        s: HudState(
          result: _result,
          mapper: _mapperFor(iw, ih),
          imageW: iw,
          imageH: ih,
          speedKmh: _speedKmh,
          speedSource: _speedSource,
          policy: s.policy,
          conditionKey: s.conditionKey,
          modifiers: s.modifierKeys,
          calibrated: s.calibrated,
          soundOn: s.alert.soundEnabled,
          cameraReady: ready,
          techText: s.showTech ? _techText : null,
          perfNotice: _perfNotice,
          perfWeak: _perfWeak,
          error: _error,
          violations: _log.sessionCount,
        ),
        onCalibrate: _openCalibration,
        onSettings: _openSettings,
        onToggleSound: () {
          s.alert.soundEnabled = !s.alert.soundEnabled;
          s.save();
          setState(() {});
        },
        onConditions: _openConditions,
        onSpeedStep: _stepSpeed,
        onAssistant: _openAssistant,
        onRetry: () {
          setState(() => _error = null);
          _startCamera();
        },
      ),
    );
  }
}
