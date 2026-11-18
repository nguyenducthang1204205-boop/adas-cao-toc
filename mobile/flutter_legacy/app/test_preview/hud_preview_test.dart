// Ảnh thiết kế các màn hình với khung hình thật (videoplayback.mp4) + pipeline Dart thật.
//   cd mobile/app && flutter test test_preview   ->  build/preview/*.png
// Không nằm trong test/ (bộ kiểm thử chính) vì chỉ để xem giao diện.
import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:adas_caotoc/core/config.dart';
import 'package:adas_caotoc/core/pipeline.dart';
import 'package:adas_caotoc/core/safety.dart';
import 'package:adas_caotoc/core/yolo.dart';
import 'package:adas_caotoc/services/alert_player.dart';
import 'package:adas_caotoc/services/settings_store.dart';
import 'package:adas_caotoc/ui/benchmark_screen.dart';
import 'package:adas_caotoc/ui/calibration_screen.dart';
import 'package:adas_caotoc/ui/components.dart';
import 'package:adas_caotoc/ui/condition_sheet.dart';
import 'package:adas_caotoc/ui/hud.dart';
import 'package:adas_caotoc/ui/settings_screen.dart';
import 'package:adas_caotoc/ui/theme.dart';
import 'package:adas_caotoc/ui/welcome_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

const _classes = ['Jeepney', 'bus', 'car', 'motorcycle', 'truck'];
final _out = Directory('build/preview')..createSync(recursive: true);

Future<void> loadFonts() async {
  final viet = FontLoader(AppText.family);
  for (final w in ['Regular', 'Medium', 'SemiBold', 'Bold', 'ExtraBold']) {
    viet.addFont(rootBundle.load('assets/fonts/BeVietnamPro-$w.ttf'));
  }
  await viet.load();
  final flutterRoot = Platform.environment['FLUTTER_ROOT'] ?? r'C:\Users\Admin\flutter';
  final icons = File('$flutterRoot/bin/cache/artifacts/material_fonts/materialicons-regular.otf').readAsBytesSync();
  await (FontLoader('MaterialIcons')..addFont(Future.value(ByteData.view(icons.buffer)))).load();
}

Future<void> capture(WidgetTester tester, GlobalKey key, String name) async {
  await tester.runAsync(() async {
    final boundary = key.currentContext!.findRenderObject()! as RenderRepaintBoundary;
    final img = await boundary.toImage(pixelRatio: tester.view.devicePixelRatio);
    final png = await img.toByteData(format: ui.ImageByteFormat.png);
    File('${_out.path}/$name.png').writeAsBytesSync(png!.buffer.asUint8List());
  });
}

Future<void> shoot(WidgetTester tester, Widget app, String name) async {
  final key = GlobalKey();
  await tester.pumpWidget(RepaintBoundary(key: key, child: app));
  await tester.pump(const Duration(milliseconds: 400));
  await capture(tester, key, name);
}

void main() {
  late Map<String, dynamic> fx;
  final frames = <String, ui.Image>{};

  setUpAll(() async {
    await loadFonts();
    fx = jsonDecode(File('test_preview/fixtures/scenarios.json').readAsStringSync()) as Map<String, dynamic>;
  });

  Future<ui.Image> frame(WidgetTester tester, String name) async {
    if (frames[name] != null) return frames[name]!;
    final img = await tester.runAsync(() async {
      final codec = await ui.instantiateImageCodec(File('test_preview/fixtures/$name.jpg').readAsBytesSync());
      return (await codec.getNextFrame()).image;
    });
    return frames[name] = img!;
  }

  CalibrationConfig calib() => CalibrationConfig(
        imagePoints: [
          for (final p in fx['image_points'] as List) [for (final v in p as List) (v as num).toDouble()]
        ],
        rectWidthM: (fx['rect_width_m'] as num).toDouble(),
        rectLengthM: (fx['rect_length_m'] as num).toDouble(),
        nearDistanceM: (fx['near_distance_m'] as num).toDouble(),
      );

  /// Chạy pipeline thật trên 30 khung YOLO liên tiếp của kịch bản -> FrameResult cuối.
  (FrameResult, AdasPipeline) run(String scenario, double speed, SafetyPolicy policy) {
    final pipe = AdasPipeline(calib(), AlertConfig(), 640, 360);
    late FrameResult r;
    for (final f in (fx['scenarios'][scenario] as List).cast<Map<String, dynamic>>()) {
      final dets = <Detection>[];
      for (final b in (f['boxes'] as List).cast<Map<String, dynamic>>()) {
        final v = (b['box'] as List).cast<num>().map((e) => e.toDouble()).toList();
        final cls = b['cls'] as String;
        dets.add(Detection(v[0], v[1], v[2], v[3], 0.9, _classes.indexOf(cls), cls));
      }
      r = pipe.process(dets, (f['t'] as num).toDouble(), speed, policy);
    }
    return (r, pipe);
  }

  Widget app(ui.Image img, HudState s) => MaterialApp(
        debugShowCheckedModeBanner: false,
        theme: buildTheme(),
        home: Scaffold(
          body: DriveHud(
            camera: RawImage(image: img, fit: BoxFit.fill),
            s: s,
            onCalibrate: () {},
            onSettings: () {},
            onToggleSound: () {},
            onConditions: () {},
            onSpeedStep: (_) {},
            onAssistant: () {},
          ),
        ),
      );

  HudState state(FrameResult r, AdasPipeline p,
          {required double speed,
          required String cond,
          Set<String> mods = const {},
          bool calibrated = true,
          int violations = 0,
          String? tech,
          String? notice}) =>
      HudState(
        result: r,
        mapper: p.mapper,
        imageW: 640,
        imageH: 360,
        speedKmh: speed,
        speedSource: SpeedSource.gps,
        policy: conditionPolicy(cond, mods),
        conditionKey: cond,
        modifiers: mods,
        calibrated: calibrated,
        soundOn: true,
        cameraReady: true,
        techText: tech,
        perfNotice: notice,
        violations: violations,
      );

  testWidgets('màn hình lái: 3 trạng thái + bảng điều kiện', (tester) async {
    tester.view.physicalSize = const Size(2400, 1080); // điện thoại Android 20:9 nằm ngang
    tester.view.devicePixelRatio = 2.75;
    addTearDown(tester.view.reset);

    final (rd, pd) = run('danger', 76, conditionPolicy('heavy_rain', {}));
    await shoot(tester, app(await frame(tester, 'danger'), state(rd, pd, speed: 76, cond: 'heavy_rain', violations: 2)), 'hud_danger');

    final dry = conditionPolicy('dry', {});
    final (rw, pw) = run('warning', 76, dry);
    await shoot(tester, app(await frame(tester, 'warning'), state(rw, pw, speed: 76, cond: 'dry')), 'hud_warning');

    final (rs, ps) = run('safe', 76, dry);
    await shoot(
        tester,
        app(
            await frame(tester, 'safe'),
            state(rs, ps,
                speed: 76,
                cond: 'dry',
                mods: {'night'},
                calibrated: false,
                tech: '29 FPS (camera 30) · bám vết 4 ms · YOLO 118 ms (7.6/s)\nGPU · FP16 (21 ms; CPU 48 ms)')),
        'hud_safe');

    // tự kiểm tra máy sau ~4 giây chạy + dòng kỹ thuật kiểu mới (mức hiệu năng, vùng YOLO, nhiệt)
    await shoot(
        tester,
        app(
            await frame(tester, 'warning'),
            state(rw, pw,
                speed: 76,
                cond: 'dry',
                notice: 'Máy của bạn: mức Trung bình · YOLO 95 ms · cảnh báo cập nhật 15 lần/giây',
                tech: '15 FPS (camera 30) · mức Trung bình · bám vết 6 ms, 15/s\n'
                    'YOLO 95 ms (8.4/s) · thấy xa 31 % · vùng 1280x576 · nhiệt ấm\n'
                    'CPU XNNPACK · INT8 · 2 luồng (78 ms; GPU 131 ms)')),
        'hud_perf');

    // bảng điều kiện đường mở trên trạng thái cảnh báo
    final key = GlobalKey();
    final (rc, pc) = run('warning', 76, conditionPolicy('wet', {'night'}));
    await tester.pumpWidget(RepaintBoundary(
        key: key, child: app(await frame(tester, 'warning'), state(rc, pc, speed: 76, cond: 'wet', mods: {'night'}))));
    showConditionSheet(tester.element(find.byType(DriveHud)),
        conditionKey: 'wet', modifierKeys: {'night'}, onCondition: (_) {}, onModifier: (_, __) {});
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 600));
    await capture(tester, key, 'hud_conditions');
  });

  testWidgets('màn hình chào, cài đặt, căn chỉnh + icon', (tester) async {
    tester.view.physicalSize = const Size(2400, 1080);
    tester.view.devicePixelRatio = 2.75;
    addTearDown(tester.view.reset);
    Widget wrap(Widget home) => MaterialApp(debugShowCheckedModeBanner: false, theme: buildTheme(), home: home);

    await shoot(tester, wrap(WelcomeScreen(onStart: () {})), 'welcome');

    final settings = AppSettings()..showTech = true;
    await shoot(tester, wrap(SettingsScreen(settings: settings, alerts: AlertPlayer())), 'settings');

    // Nhóm "Ngưỡng cảnh báo": người dùng đặt dải 80-100 km/h là 90 m, đang mưa nhỏ
    final custom = AppSettings()
      ..bandGapsM = [35, 55, 90, 100]
      ..conditionKey = 'wet';
    final key = GlobalKey();
    await tester.pumpWidget(RepaintBoundary(key: key, child: wrap(SettingsScreen(settings: custom, alerts: AlertPlayer()))));
    await tester.pump();
    await tester.scrollUntilVisible(find.text('NGƯỠNG CẢNH BÁO'), 200, scrollable: find.byType(Scrollable).first);
    await tester.ensureVisible(find.text('NGƯỠNG CẢNH BÁO'));
    await tester.pump(const Duration(milliseconds: 400));
    await capture(tester, key, 'settings_thresholds');

    // Nhóm "Hiệu năng" + màn hình đo hiệu năng với một kết quả mẫu
    final perf = AppSettings()
      ..lastLevel = 'medium'
      ..benchHistory = [
        {
          'when': '2026-10-18 21:40', 'device': 'Xiaomi Redmi Note 11S', 'soc': 'Mediatek MT6781',
          'os': 'Android 12 (API 31)', 'cores': 8, 'ram_mb': 5800,
          'backend': 'CPU XNNPACK · INT8 · 2 luồng (78 ms; GPU 131 ms)', 'duration_s': 30,
          'mode': 'auto', 'dense': true, 'far': true, 'ui_fps': 59.6, 'jank_pct': 0.8, 'build_p95': 3.1,
          'raster_p95': 6.4, 'result_hz': 15.0, 'proc_avg': 5.8, 'proc_p95': 9.7, 'yolo_avg': 92,
          'yolo_p95': 118, 'yolo_hz': 8.2, 'levels': {'medium': 100.0}, 'level_end': 'medium',
          'thermal_start': 0, 'thermal_end': 1,
        }
      ];
    final pk = GlobalKey();
    await tester.pumpWidget(RepaintBoundary(key: pk, child: wrap(SettingsScreen(settings: perf, alerts: AlertPlayer()))));
    await tester.pump();
    await tester.scrollUntilVisible(find.text('Đo hiệu năng máy'), 200, scrollable: find.byType(Scrollable).first);
    await tester.ensureVisible(find.text('HIỆU NĂNG'));
    await tester.pump(const Duration(milliseconds: 400));
    await capture(tester, pk, 'settings_perf');
    await shoot(tester, wrap(BenchmarkScreen(settings: perf)), 'benchmark');
    final bk = GlobalKey();
    await tester.pumpWidget(RepaintBoundary(key: bk, child: wrap(BenchmarkScreen(settings: perf))));
    await tester.pump();
    await tester.scrollUntilVisible(find.textContaining('Mức hiệu năng:'), 200, scrollable: find.byType(Scrollable).first);
    await tester.pump(const Duration(milliseconds: 400));
    await capture(tester, bk, 'benchmark_result');

    final img = await frame(tester, 'warning');
    await shoot(
        tester,
        wrap(CalibrationScreen(
            preview: RawImage(image: img, fit: BoxFit.fill), initial: calib(), imageW: 640, imageH: 360)),
        'calibration');

    // icon launcher 1024 px (nền tràn - hệ điều hành tự bo góc) + bản bo góc cho tài liệu
    tester.view.physicalSize = const Size(1024, 1024);
    tester.view.devicePixelRatio = 1;
    await shoot(
        tester, CustomPaint(size: const Size.square(1024), painter: AppMarkPainter(fullBleed: true)), 'icon_1024');
    await shoot(
        tester,
        CustomPaint(
            size: const Size.square(1024), painter: AppMarkPainter(fullBleed: true, layer: MarkLayer.background)),
        'icon_bg_1024');
    await shoot(
        tester,
        CustomPaint(
            size: const Size.square(1024), painter: AppMarkPainter(fullBleed: true, layer: MarkLayer.foreground)),
        'icon_fg_1024');
  });
}
