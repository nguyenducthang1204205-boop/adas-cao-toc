/// Thành phần giao diện dùng chung của hệ thống thiết kế (theme.dart).
library;

import 'package:flutter/material.dart';

import 'theme.dart';

/// Khung "kính" nổi trên video: nền đục 84 % (không làm mờ nền - BackdropFilter trên camera tốn GPU
/// mỗi khung), viền mảnh 10 %, bo góc lớn. [accent]: dải màu trạng thái ở cạnh trái.
class GlassPanel extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final double radius;
  final Color? accent;
  final Color color;

  const GlassPanel({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(Space.lg),
    this.radius = Radii.lg,
    this.accent,
    this.color = AppColors.glass,
  });

  @override
  Widget build(BuildContext context) {
    return AnimatedContainer(
      duration: Motion.base,
      curve: Motion.curve,
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(radius),
        border: Border.all(color: accent?.withValues(alpha: 0.55) ?? AppColors.stroke, width: accent != null ? 1.5 : 1),
        boxShadow: const [BoxShadow(color: Color(0x66000000), blurRadius: 24, offset: Offset(0, 8))],
      ),
      padding: padding,
      child: child,
    );
  }
}

/// Nút tròn biểu tượng (≥ 52 dp) có nhãn cho trình đọc màn hình + tooltip, phản hồi chạm bằng gợn sóng.
class RoundAction extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback? onPressed;
  final bool active;
  final double size;

  const RoundAction({
    super.key,
    required this.icon,
    required this.label,
    required this.onPressed,
    this.active = false,
    this.size = 52,
  });

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      toggled: active,
      label: label,
      excludeSemantics: true,
      child: Tooltip(
        message: label,
        child: Material(
          color: active ? AppColors.accent : AppColors.glass,
          shape: CircleBorder(side: BorderSide(color: active ? AppColors.accent : AppColors.stroke)),
          clipBehavior: Clip.antiAlias,
          child: InkWell(
            onTap: onPressed,
            child: SizedBox.square(
              dimension: size,
              child: Icon(icon, size: 24, color: active ? AppColors.onAccent : AppColors.text),
            ),
          ),
        ),
      ),
    );
  }
}

/// Số hiển thị với chữ số rộng bằng nhau. Be Vietnam Pro không có tính năng tnum ("1" hẹp hơn "0" gần
/// một nửa) nên mỗi chữ số được đặt trong một ô cố định -> số nhảy liên tục không làm rung bố cục.
class TabularNumber extends StatelessWidget {
  final String text;
  final TextStyle style;

  const TabularNumber(this.text, {super.key, required this.style});

  @override
  Widget build(BuildContext context) {
    final size = (style.fontSize ?? 14) * MediaQuery.textScalerOf(context).scale(1);
    final digitW = size * 0.6;
    return Semantics(
      label: text,
      excludeSemantics: true,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.baseline,
        textBaseline: TextBaseline.alphabetic,
        children: [
          for (final ch in text.characters)
            if ('0123456789'.contains(ch))
              SizedBox(width: digitW, child: Text(ch, style: style, textAlign: TextAlign.center))
            else
              Text(ch, style: style),
        ],
      ),
    );
  }
}

/// Nhãn chữ in hoa nhỏ đặt trên mỗi cụm số.
class Overline extends StatelessWidget {
  final String text;
  final IconData? icon;
  final Color? color;
  const Overline(this.text, {super.key, this.icon, this.color});

  @override
  Widget build(BuildContext context) {
    final c = color ?? AppColors.textSecondary;
    return Row(mainAxisSize: MainAxisSize.min, children: [
      if (icon != null) ...[
        ExcludeSemantics(child: Icon(icon, size: 14, color: c)),
        const SizedBox(width: Space.xs + 2),
      ],
      Text(text.toUpperCase(), style: AppText.overline.copyWith(color: c)),
    ]);
  }
}

/// Viên thuốc trạng thái: chấm màu + chữ (màu không bao giờ là tín hiệu duy nhất).
class StatusDot extends StatelessWidget {
  final Color color;
  final String text;
  const StatusDot({super.key, required this.color, required this.text});

  @override
  Widget build(BuildContext context) {
    return Row(mainAxisSize: MainAxisSize.min, children: [
      Container(
        width: 8,
        height: 8,
        decoration: BoxDecoration(color: color, shape: BoxShape.circle, boxShadow: [
          BoxShadow(color: color.withValues(alpha: 0.6), blurRadius: 6),
        ]),
      ),
      const SizedBox(width: Space.sm),
      Flexible(child: Text(text, style: AppText.caption, overflow: TextOverflow.ellipsis)),
    ]);
  }
}

/// Biểu tượng app: con đường phối cảnh hội tụ về chân trời + chevron "giữ khoảng cách" màu thương hiệu.
/// Vẽ bằng vector nên sắc nét ở mọi kích thước (dùng cả cho icon launcher - xem test_preview).
class AppMark extends StatelessWidget {
  final double size;
  const AppMark({super.key, this.size = 72});

  @override
  Widget build(BuildContext context) {
    return ExcludeSemantics(child: CustomPaint(size: Size.square(size), painter: AppMarkPainter()));
  }
}

/// Lớp vẽ của biểu tượng: đủ cả hai, chỉ nền, hoặc chỉ tiền cảnh (adaptive icon Android).
enum MarkLayer { all, background, foreground }

class AppMarkPainter extends CustomPainter {
  final bool fullBleed; // true: nền tràn (icon launcher, hệ điều hành tự bo góc)
  final MarkLayer layer;
  AppMarkPainter({this.fullBleed = false, this.layer = MarkLayer.all});

  @override
  void paint(Canvas canvas, Size size) {
    if (layer == MarkLayer.foreground) {
      // tiền cảnh adaptive icon: nội dung nằm trong vùng an toàn 66/108 ở giữa
      final k = 0.74;
      canvas.translate(size.width * (1 - k) / 2, size.height * (1 - k) / 2);
      canvas.scale(k);
    }
    final s = size.width;
    final rect = Offset.zero & size;
    final drawBg = layer != MarkLayer.foreground, drawFg = layer != MarkLayer.background;
    final bg = Paint()
      ..shader = const LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [Color(0xFF1B2B45), Color(0xFF070B12)],
      ).createShader(rect);
    if (!drawBg) {
      // bỏ qua nền
    } else if (fullBleed) {
      canvas.drawRect(rect, bg);
    } else {
      canvas.drawRRect(RRect.fromRectAndRadius(rect, Radius.circular(s * 0.26)), bg);
      canvas.drawRRect(
          RRect.fromRectAndRadius(rect.deflate(0.5), Radius.circular(s * 0.26)),
          Paint()
            ..style = PaintingStyle.stroke
            ..strokeWidth = s * 0.012
            ..color = Colors.white.withValues(alpha: 0.10));
    }
    // quầng sáng chân trời
    if (drawBg) {
      canvas.drawCircle(
          Offset(s * 0.5, s * 0.36),
          s * 0.42,
          Paint()
            ..shader = RadialGradient(
                    colors: [AppColors.accent.withValues(alpha: 0.30), AppColors.accent.withValues(alpha: 0)])
                .createShader(Rect.fromCircle(center: Offset(s * 0.5, s * 0.36), radius: s * 0.42)));
    }
    if (!drawFg) return;
    // mặt đường
    final vp = Offset(s * 0.5, s * 0.30);
    final road = Path()
      ..moveTo(vp.dx - s * 0.015, vp.dy)
      ..lineTo(vp.dx + s * 0.015, vp.dy)
      ..lineTo(s * 0.86, s * 0.86)
      ..lineTo(s * 0.14, s * 0.86)
      ..close();
    canvas.drawPath(
        road,
        Paint()
          ..shader = LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Colors.white.withValues(alpha: 0.05), Colors.white.withValues(alpha: 0.16)],
          ).createShader(rect));
    final edge = Paint()
      ..color = Colors.white.withValues(alpha: 0.85)
      ..strokeWidth = s * 0.028
      ..strokeCap = StrokeCap.round;
    canvas.drawLine(vp, Offset(s * 0.14, s * 0.86), edge);
    canvas.drawLine(vp, Offset(s * 0.86, s * 0.86), edge);
    // chevron giữ khoảng cách
    final chev = Paint()
      ..color = AppColors.accent
      ..style = PaintingStyle.stroke
      ..strokeWidth = s * 0.06
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;
    for (final (y, w, a) in [(0.74, 0.20, 1.0), (0.56, 0.13, 0.7)]) {
      canvas.drawPath(
          Path()
            ..moveTo(s * (0.5 - w), s * (y + w * 0.55))
            ..lineTo(s * 0.5, s * y)
            ..lineTo(s * (0.5 + w), s * (y + w * 0.55)),
          chev..color = AppColors.accent.withValues(alpha: a));
    }
  }

  @override
  bool shouldRepaint(AppMarkPainter old) => old.fullBleed != fullBleed || old.layer != layer;
}
