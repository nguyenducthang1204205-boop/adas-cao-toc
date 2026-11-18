/// ADAS Cao tốc - bản mobile (Flutter, Android + iOS).
/// Cảnh báo khoảng cách an toàn: YOLOv11 (TFLite) + IPM + ngưỡng theo tốc độ GPS và điều kiện đường.
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'services/settings_store.dart';
import 'ui/drive_screen.dart';
import 'ui/theme.dart';
import 'ui/welcome_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await SystemChrome.setPreferredOrientations([DeviceOrientation.landscapeLeft]);
  await SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
  final settings = AppSettings();
  await settings.load();
  runApp(AdasApp(settings: settings));
}

class AdasApp extends StatelessWidget {
  final AppSettings settings;
  const AdasApp({super.key, required this.settings});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'ADAS Cao tốc',
      debugShowCheckedModeBanner: false,
      theme: buildTheme(),
      home: _Gate(settings: settings),
    );
  }
}

/// Màn hình chào (kèm lời nhắc an toàn) ở lần mở đầu tiên, rồi vào màn hình lái xe.
class _Gate extends StatefulWidget {
  final AppSettings settings;
  const _Gate({required this.settings});

  @override
  State<_Gate> createState() => _GateState();
}

class _GateState extends State<_Gate> {
  static const _key = 'disclaimer_ok_v1';
  bool? _ok;

  @override
  void initState() {
    super.initState();
    SharedPreferences.getInstance()
        .then((p) => p.getBool(_key) ?? false)
        .catchError((_) => false) // không đọc được -> hiện lại lời nhắc, không kẹt ở màn hình chờ
        .then((ok) => setState(() => _ok = ok));
  }

  Future<void> _accept() async {
    try {
      final p = await SharedPreferences.getInstance();
      await p.setBool(_key, true);
    } catch (_) {}
    setState(() => _ok = true);
  }

  @override
  Widget build(BuildContext context) {
    if (_ok == null) return const Scaffold(backgroundColor: AppColors.bg);
    if (_ok!) return DriveScreen(settings: widget.settings);
    return WelcomeScreen(onStart: _accept);
  }
}
