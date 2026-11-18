// Ảnh thiết kế bảng "Trợ lý AI | Vi phạm" (tương ứng hai thẻ cuối cột phải của bản desktop).
//   cd mobile/app && flutter test test_preview   ->  build/preview/assistant_*.png
import 'dart:io';
import 'dart:ui' as ui;

import 'package:adas_caotoc/core/safety.dart';
import 'package:adas_caotoc/core/violations.dart';
import 'package:adas_caotoc/services/settings_store.dart';
import 'package:adas_caotoc/services/violation_log.dart';
import 'package:adas_caotoc/ui/assistant_sheet.dart';
import 'package:adas_caotoc/ui/theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

final _out = Directory('build/preview')..createSync(recursive: true);

Future<void> _loadFonts() async {
  final viet = FontLoader(AppText.family);
  for (final w in ['Regular', 'Medium', 'SemiBold', 'Bold', 'ExtraBold']) {
    viet.addFont(rootBundle.load('assets/fonts/BeVietnamPro-$w.ttf'));
  }
  await viet.load();
  final flutterRoot = Platform.environment['FLUTTER_ROOT'] ?? r'C:\Users\Admin\flutter';
  final icons = File('$flutterRoot/bin/cache/artifacts/material_fonts/materialicons-regular.otf').readAsBytesSync();
  await (FontLoader('MaterialIcons')..addFont(Future.value(ByteData.view(icons.buffer)))).load();
}

Violation _sample(int id, Risk level, double minD, {double? ttc, double? duration}) => Violation(
      id: id,
      sessionId: 1,
      startedAt: DateTime.now().subtract(Duration(minutes: 12 - id * 3)),
      level: level,
      trackId: id + 2,
      className: id.isEven ? 'truck' : 'car',
      distanceM: minD + 6,
      minDistanceM: minD,
      minTtcS: ttc,
      safeM: 110,
      dangerM: 55,
      speedKmh: 82,
      condition: 'Mưa to, mặt đường đọng nước',
      weatherFactor: 2.0,
      durationS: duration,
    );

void main() {
  setUpAll(() async {
    await _loadFonts();
  });

  testWidgets('bảng trợ lý + vi phạm', (tester) async {
    tester.view.physicalSize = const Size(2400, 1080);
    tester.view.devicePixelRatio = 2.75;
    addTearDown(tester.view.reset);

    final bg = await tester.runAsync(() async {
      final codec = await ui.instantiateImageCodec(File('test_preview/fixtures/warning.jpg').readAsBytesSync());
      return (await codec.getNextFrame()).image;
    });
    final settings = AppSettings();
    final chat = AssistantChat()
      ..ask('trời mưa to, tôi chạy 90 km/h', settings, 76)
      ..ask('có sương mù, tầm nhìn khoảng 80 m', settings, 90);
    final log = ViolationLog();
    log.startSession();
    log.apply([
      ('open', _sample(1, Risk.danger, 31.4, ttc: 2.6, duration: 3.8)),
      ('open', _sample(2, Risk.warning, 72.0, duration: 6.1)),
    ]);
    log.apply([('open', _sample(3, Risk.danger, 39.7, ttc: 3.1))]); // đang diễn ra

    for (final (tab, name) in [(0, 'assistant_chat'), (1, 'assistant_violations')]) {
      final key = GlobalKey();
      await tester.pumpWidget(RepaintBoundary(
        key: key,
        child: MaterialApp(
          debugShowCheckedModeBanner: false,
          theme: buildTheme(),
          home: Scaffold(body: SizedBox.expand(child: RawImage(image: bg, fit: BoxFit.cover))),
        ),
      ));
      showAssistantSheet(tester.element(find.byType(Scaffold)), chat: chat, log: log, onAsk: (_) {}, initialTab: tab);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 600));
      await tester.runAsync(() async {
        final boundary = key.currentContext!.findRenderObject()! as RenderRepaintBoundary;
        final img = await boundary.toImage(pixelRatio: tester.view.devicePixelRatio);
        final png = await img.toByteData(format: ui.ImageByteFormat.png);
        File('${_out.path}/$name.png').writeAsBytesSync(png!.buffer.asUint8List());
      });
    }
  });
}
