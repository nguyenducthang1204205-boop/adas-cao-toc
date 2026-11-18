/// Hệ thống thiết kế "Night Drive": token màu, chữ, khoảng cách, bo góc, chuyển động.
/// Bản desktop dùng cùng token ở adas/theme.py - đổi ở đây thì đổi cả bên đó.
///
/// Nguyên tắc (màn hình hỗ trợ lái, nhìn lướt < 1 giây, dùng chủ yếu ban đêm):
///  - Nền OLED đen sâu; chữ trắng ngà (không trắng tinh) để không chói khi lái đêm.
///  - Màu chỉ mang nghĩa: xanh / hổ phách / đỏ dành riêng cho mức rủi ro và luôn đi kèm chữ + biểu tượng.
///    Màu thương hiệu (xanh dương) chỉ cho điều khiển tương tác.
///  - Mọi màn hình dùng token ở đây - không mã màu rời rạc trong widget.
/// Tương phản WCAG (đã đo): trên surface #0F141B - text 16,4:1 · textSecondary 8,2:1 · textTertiary 5,0:1 ·
/// accent 6,7:1 · danger 5,7:1. Trên cụm kính (glass) khi video phía sau là trời trắng (trường hợp xấu
/// nhất): text 10,7:1 · textSecondary 5,3:1 · textTertiary chỉ 3,3:1 -> KHÔNG dùng textTertiary trong HUD.
/// Nền banner: chữ trắng trên dangerFill 4,8:1, chữ onWarning trên warning 10,2:1.
library;

import 'package:flutter/material.dart';

import '../core/safety.dart';

class AppColors {
  // nền & bề mặt
  static const bg = Color(0xFF05070A); // nền app / viền ngoài video
  static const surface = Color(0xFF0F141B); // màn hình đặc (cài đặt, căn chỉnh)
  static const surfaceRaised = Color(0xFF161D26); // thẻ trên surface
  static const glass = Color(0xD60C1117); // cụm đồng hồ nổi trên video (84 % đục: đọc được trên nền sáng)
  static const glassStrong = Color(0xEB0C1117);
  static const stroke = Color(0x1AFFFFFF); // viền mảnh 10 %
  static const strokeStrong = Color(0x29FFFFFF);
  static const scrim = Color(0xB3000000);

  // chữ
  static const text = Color(0xFFEEF2F6);
  static const textSecondary = Color(0xFFA3AEBB);
  static const textTertiary = Color(0xFF7B8794);

  // thương hiệu / tương tác
  static const accent = Color(0xFF4C9EFF);
  static const accentSoft = Color(0x294C9EFF);
  static const onAccent = Color(0xFF04101F);

  // ngữ nghĩa rủi ro
  static const safe = Color(0xFF2FD27A);
  static const warning = Color(0xFFFFB020);
  static const danger = Color(0xFFFF4D4F); // viền / chữ trên nền tối
  static const dangerFill = Color(0xFFD92D20); // nền banner (chữ trắng 4,8:1; danger chỉ 3,3:1)
  static const info = Color(0xFF9AA8B8);
  static const onWarning = Color(0xFF1A1200);

  // tương thích tên cũ
  static const muted = textSecondary;
  static const faint = textTertiary;
  static const videoBg = bg;
  static const border = stroke;
  static const surface2 = surfaceRaised;
}

class Space {
  static const xs = 4.0, sm = 8.0, md = 12.0, lg = 16.0, xl = 24.0, xxl = 32.0;
}

class Radii {
  static const sm = 10.0, md = 16.0, lg = 22.0, pill = 999.0;
}

class Motion {
  static const fast = Duration(milliseconds: 120); // phản hồi chạm
  static const base = Duration(milliseconds: 220); // đổi trạng thái
  static const slow = Duration(milliseconds: 360); // vào / ra panel
  static const pulse = Duration(milliseconds: 1100); // nhịp viền khi NGUY HIỂM
  static const curve = Curves.easeOutCubic;

  /// Người dùng bật "giảm chuyển động" trong hệ điều hành -> bỏ hiệu ứng không thiết yếu.
  static bool reduced(BuildContext context) => MediaQuery.maybeDisableAnimationsOf(context) ?? false;
}

class AppText {
  static const family = 'BeVietnamPro';
  static const _base = TextStyle(fontFamily: family, color: AppColors.text, height: 1.2);

  /// Số đo chính (khoảng cách tới xe trước).
  static const display = TextStyle(fontFamily: family, fontSize: 64, fontWeight: FontWeight.w800, height: 1.0, letterSpacing: -1.5);

  /// Tốc độ xe.
  static const numeral = TextStyle(fontFamily: family, fontSize: 44, fontWeight: FontWeight.w700, height: 1.0, letterSpacing: -1);
  static final title = _base.copyWith(fontSize: 18, fontWeight: FontWeight.w700);
  static final headline = _base.copyWith(fontSize: 26, fontWeight: FontWeight.w800, letterSpacing: -0.4);
  static final body = _base.copyWith(fontSize: 15, fontWeight: FontWeight.w400, height: 1.45);
  static final bodyStrong = _base.copyWith(fontSize: 15, fontWeight: FontWeight.w600);
  static final caption = _base.copyWith(fontSize: 13, fontWeight: FontWeight.w500, color: AppColors.textSecondary);
  static final unit = _base.copyWith(fontSize: 15, fontWeight: FontWeight.w600, color: AppColors.textSecondary);

  /// Nhãn chữ in hoa nhỏ phía trên mỗi cụm số.
  static final overline = _base.copyWith(
      fontSize: 11, fontWeight: FontWeight.w700, letterSpacing: 1.4, color: AppColors.textSecondary);
}

/// Số thập phân kiểu Việt Nam: dấu phẩy ("39,7").
String vn(double v, [int digits = 1]) => v.toStringAsFixed(digits).replaceAll('.', ',');

/// Hệ số nhân: tối đa 2 chữ số thập phân, bỏ số 0 thừa (1,0 · 1,4 · 1,15 · 2,02).
String vnFactor(double v) {
  var s = v.toStringAsFixed(2);
  if (s.endsWith('0')) s = s.substring(0, s.length - 1);
  return s.replaceAll('.', ',');
}

Color riskColor(Risk r) => switch (r) {
      Risk.danger => AppColors.danger,
      Risk.warning => AppColors.warning,
      Risk.safe => AppColors.safe,
      Risk.info => AppColors.info,
    };

Color onRiskColor(Risk r) => r == Risk.warning ? AppColors.onWarning : Colors.white;

/// Màu nền cho khối đặc (banner) theo mức rủi ro - đủ tương phản với chữ onRiskColor.
Color riskFill(Risk r) => r == Risk.danger ? AppColors.dangerFill : riskColor(r);

IconData riskIcon(Risk r) => switch (r) {
      Risk.danger => Icons.warning_rounded,
      Risk.warning => Icons.error_outline_rounded,
      _ => Icons.verified_rounded,
    };

String riskLabel(Risk r) => switch (r) {
      Risk.danger => 'NGUY HIỂM',
      Risk.warning => 'CẢNH BÁO',
      _ => 'AN TOÀN',
    };

String riskMessage(Risk r) => switch (r) {
      Risk.danger => 'Giảm tốc ngay',
      Risk.warning => 'Giữ khoảng cách',
      _ => 'Khoảng cách an toàn',
    };

ThemeData buildTheme() {
  final scheme = ColorScheme.fromSeed(
    seedColor: AppColors.accent,
    brightness: Brightness.dark,
  ).copyWith(
    primary: AppColors.accent,
    onPrimary: AppColors.onAccent,
    surface: AppColors.surface,
    onSurface: AppColors.text,
    onSurfaceVariant: AppColors.textSecondary,
    outline: AppColors.strokeStrong,
    outlineVariant: AppColors.stroke,
    error: AppColors.danger,
  );
  final base = ThemeData(useMaterial3: true, colorScheme: scheme, fontFamily: AppText.family);
  return base.copyWith(
    scaffoldBackgroundColor: AppColors.bg,
    textTheme: base.textTheme.apply(bodyColor: AppColors.text, displayColor: AppColors.text),
    cardTheme: const CardThemeData(
      color: AppColors.surfaceRaised,
      margin: EdgeInsets.zero,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.all(Radius.circular(Radii.md)),
        side: BorderSide(color: AppColors.stroke),
      ),
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: AppColors.surface,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      centerTitle: false,
    ),
    switchTheme: SwitchThemeData(
      thumbColor: WidgetStateProperty.resolveWith((s) => s.contains(WidgetState.selected) ? Colors.white : AppColors.textSecondary),
      trackColor: WidgetStateProperty.resolveWith(
          (s) => s.contains(WidgetState.selected) ? AppColors.accent : AppColors.surfaceRaised),
      trackOutlineColor: WidgetStateProperty.resolveWith(
          (s) => s.contains(WidgetState.selected) ? AppColors.accent : AppColors.strokeStrong),
    ),
    sliderTheme: const SliderThemeData(
      activeTrackColor: AppColors.accent,
      thumbColor: Colors.white,
      inactiveTrackColor: AppColors.surfaceRaised,
      valueIndicatorColor: AppColors.surfaceRaised,
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: AppColors.accent,
        foregroundColor: AppColors.onAccent,
        minimumSize: const Size(64, 52),
        padding: const EdgeInsets.symmetric(horizontal: Space.xl),
        textStyle: const TextStyle(fontFamily: AppText.family, fontSize: 16, fontWeight: FontWeight.w700),
        shape: const StadiumBorder(),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: AppColors.text,
        minimumSize: const Size(64, 52),
        side: const BorderSide(color: AppColors.strokeStrong),
        textStyle: const TextStyle(fontFamily: AppText.family, fontSize: 15, fontWeight: FontWeight.w600),
        shape: const StadiumBorder(),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: AppColors.accent,
        minimumSize: const Size(48, 48),
        textStyle: const TextStyle(fontFamily: AppText.family, fontSize: 15, fontWeight: FontWeight.w600),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: AppColors.surfaceRaised,
      labelStyle: AppText.caption,
      floatingLabelStyle: AppText.caption.copyWith(color: AppColors.accent),
      border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(Radii.sm), borderSide: const BorderSide(color: AppColors.stroke)),
      enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(Radii.sm), borderSide: const BorderSide(color: AppColors.stroke)),
      focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(Radii.sm), borderSide: const BorderSide(color: AppColors.accent, width: 1.5)),
    ),
    dividerTheme: const DividerThemeData(color: AppColors.stroke, thickness: 1, space: 1),
    tooltipTheme: TooltipThemeData(
      decoration: BoxDecoration(color: AppColors.surfaceRaised, borderRadius: BorderRadius.circular(Radii.sm)),
      textStyle: AppText.caption.copyWith(color: AppColors.text),
    ),
    snackBarTheme: SnackBarThemeData(
      backgroundColor: AppColors.surfaceRaised,
      contentTextStyle: AppText.body,
      behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(Radii.md)),
    ),
  );
}
