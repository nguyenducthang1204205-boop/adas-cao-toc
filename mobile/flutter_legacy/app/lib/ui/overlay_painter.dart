/// Lớp vẽ trên khung camera (hệ tọa độ pixel ảnh; widget cha co ảnh theo BoxFit.cover).
///
/// [screenScale] = số dp màn hình cho 1 pixel ảnh: nét vẽ và chữ chia cho hệ số này để luôn có cùng
/// kích thước trên màn hình, bất kể độ phân giải camera.
library;

import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../core/config.dart';
import '../core/distance.dart';
import '../core/geometry.dart';
import '../core/ipm.dart';
import '../core/pipeline.dart';
import '../core/safety.dart';
import 'theme.dart';

class OverlayPainter extends CustomPainter {
  final FrameResult? result;
  final GroundPlaneMapper? mapper;
  final double imageW, imageH;
  final double screenScale;

  OverlayPainter(this.result, this.mapper, this.imageW, this.imageH, {this.screenScale = 1});

  double _dp(double v) => v / screenScale; // kích thước dp -> pixel ảnh
  final _labels = <Rect>[]; // nhãn đã vẽ trong khung này (tránh chồng nhau)

  @override
  void paint(Canvas canvas, Size size) {
    if (imageW <= 0 || imageH <= 0) return;
    final sx = size.width / imageW, sy = size.height / imageH;
    Offset px(Vec2 p) => Offset(p.x * sx, p.y * sy);
    final r = result, m = mapper;
    if (m != null && r != null) _corridor(canvas, m, r, px);
    if (r != null) {
      _labels.clear();
      final lead = r.lead;
      if (lead != null) _vehicle(canvas, lead, sx, sy, true); // nhãn xe phía trước được ưu tiên chỗ
      for (final v in r.vehicles.reversed) {
        if (!identical(v, lead)) _vehicle(canvas, v, sx, sy, false);
      }
    }
  }

  // ------------------------------------------------------------------ thảm đường phía trước

  void _corridor(Canvas canvas, GroundPlaneMapper m, FrameResult r, Offset Function(Vec2) px) {
    final half = m.calib.laneHalfWidthM;
    final near = math.max(m.calib.nearDistanceM * 0.5, 2.5);
    final thr = r.thresholds;
    final far = math.min(thr.safeM * 1.35, m.calib.maxRangeM);
    Offset g(double x, double y) => px(m.groundToImage(x, y));

    Path band(double y0, double y1) => Path()
      ..moveTo(g(-half, y0).dx, g(-half, y0).dy)
      ..lineTo(g(half, y0).dx, g(half, y0).dy)
      ..lineTo(g(half, y1).dx, g(half, y1).dy)
      ..lineTo(g(-half, y1).dx, g(-half, y1).dy)
      ..close();

    // hành lang làn trung tính tới ngưỡng an toàn (không tô đỏ khi đang an toàn)
    final lead = r.lead;
    final hasGap = lead != null && lead.method == 'IPM' && lead.distanceM > near;
    final pn = g(0, near), pf = g(0, far);
    canvas.drawPath(
      band(near, far),
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.bottomCenter,
          end: Alignment.topCenter,
          colors: [Colors.white.withValues(alpha: 0.10), Colors.white.withValues(alpha: 0.0)],
        ).createShader(Rect.fromPoints(Offset(pn.dx - 1, pn.dy), Offset(pf.dx + 1, pf.dy))),
    );
    // khoảng trống tới xe phía trước, tô theo mức rủi ro của chính xe đó
    if (hasGap) {
      final color = riskColor(lead.risk);
      final pl = g(0, lead.distanceM);
      canvas.drawPath(
        band(near, lead.distanceM),
        Paint()
          ..shader = LinearGradient(
            begin: Alignment.bottomCenter,
            end: Alignment.topCenter,
            colors: [color.withValues(alpha: 0.08), color.withValues(alpha: 0.38)],
          ).createShader(Rect.fromPoints(Offset(pn.dx - 1, pn.dy), Offset(pl.dx + 1, pl.dy))),
      );
    }

    // mép hành lang: vạch mảnh sáng, mờ dần về xa
    for (final side in [-half, half]) {
      final a = g(side, near), b = g(side, far);
      canvas.drawLine(
          a,
          b,
          Paint()
            ..strokeWidth = _dp(2)
            ..strokeCap = StrokeCap.round
            ..shader = LinearGradient(colors: [
              Colors.white.withValues(alpha: 0.65),
              Colors.white.withValues(alpha: 0.0),
            ]).createShader(Rect.fromPoints(a, b)));
    }

    // vạch mốc ngưỡng: nhãn nguy hiểm bên trái, cảnh báo bên phải -> không bao giờ chồng nhau;
    // không vẽ đè lên xe phía trước
    final limit = hasGap ? lead.distanceM - 1.0 : far;
    for (final (d, color, right) in [(thr.dangerM, AppColors.danger, false), (thr.safeM, AppColors.warning, true)]) {
      if (d >= far || d >= limit || d <= near) continue;
      final a = g(-half, d), b = g(half, d);
      _dashed(canvas, a, b, color, _dp(2));
      final label = '${d.round()} m';
      if (right) {
        _pill(canvas, label, b + Offset(_dp(8), -_dp(8)), color, fontDp: 11, filled: false);
      } else {
        _pill(canvas, label, a + Offset(-_dp(8), -_dp(8)), color, fontDp: 11, filled: false, alignRight: true);
      }
    }

    // chevron dẫn tới xe phía trước (cùng làn, đo bằng IPM)
    if (hasGap && lead.distanceM > near + 2) {
      final color = riskColor(lead.risk);
      for (final f in const [0.3, 0.55, 0.8]) {
        final y = near + (lead.distanceM - near) * f;
        final apex = g(0, y + 1.5), l = g(-half * 0.35, y), rr = g(half * 0.35, y);
        final path = Path()
          ..moveTo(l.dx, l.dy)
          ..lineTo(apex.dx, apex.dy)
          ..lineTo(rr.dx, rr.dy);
        canvas.drawPath(
            path,
            Paint()
              ..style = PaintingStyle.stroke
              ..strokeWidth = _dp(3)
              ..strokeCap = StrokeCap.round
              ..strokeJoin = StrokeJoin.round
              ..color = color.withValues(alpha: 0.35 + 0.5 * f));
      }
    }
  }

  void _dashed(Canvas canvas, Offset a, Offset b, Color color, double w) {
    final len = (b - a).distance;
    if (len < 1) return;
    final dir = (b - a) / len;
    final dash = _dp(8), gap = _dp(6);
    final paint = Paint()
      ..color = color.withValues(alpha: 0.9)
      ..strokeWidth = w
      ..strokeCap = StrokeCap.round;
    for (var s = 0.0; s < len; s += dash + gap) {
      canvas.drawLine(a + dir * s, a + dir * math.min(s + dash, len), paint);
    }
  }

  // ------------------------------------------------------------------ xe

  void _vehicle(Canvas canvas, VehicleState v, double sx, double sy, bool isLead) {
    final d = v.det;
    final rect = Rect.fromLTRB(d.x1 * sx, d.y1 * sy, d.x2 * sx, d.y2 * sy);
    final outOfLane = v.risk == Risk.info;
    final color = isLead ? riskColor(v.risk) : Colors.white.withValues(alpha: outOfLane ? 0.45 : 0.75);
    final w = _dp(isLead ? 3 : 1.6);
    final c = math.min(rect.width, rect.height) * 0.22 + _dp(4);
    final paint = Paint()
      ..color = color
      ..strokeWidth = w
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;
    if (isLead) {
      // quầng nhẹ sau góc ngoặc của xe đang được theo dõi
      canvas.drawRRect(RRect.fromRectAndRadius(rect, Radius.circular(_dp(6))),
          Paint()..color = color.withValues(alpha: 0.10));
    }
    for (final (o, dx, dy) in [
      (rect.topLeft, 1.0, 1.0),
      (rect.topRight, -1.0, 1.0),
      (rect.bottomLeft, 1.0, -1.0),
      (rect.bottomRight, -1.0, -1.0),
    ]) {
      canvas.drawPath(
          Path()
            ..moveTo(o.dx, o.dy + dy * c)
            ..lineTo(o.dx, o.dy)
            ..lineTo(o.dx + dx * c, o.dy),
          paint);
    }
    if (v.method == 'Xa') return;
    if (isLead) {
      var text = '${vn(v.distanceM)} m';
      if (v.ttcS != null) text += '  ·  ${vn(v.ttcS!)} s';
      _pill(canvas, text, Offset(rect.center.dx, rect.top - _dp(8)), riskFill(v.risk),
          fontDp: 14, filled: true, textColor: onRiskColor(v.risk), centered: true, above: true);
    } else if (v.distanceM < 90) {
      final name = classLabelsVi[d.className] ?? d.className;
      _pill(canvas, '$name ${v.distanceM.round()} m', Offset(rect.center.dx, rect.top - _dp(6)),
          const Color(0xCC0C1117),
          fontDp: 11, filled: true, textColor: AppColors.text, centered: true, above: true, avoid: true);
    }
  }

  void _pill(Canvas canvas, String text, Offset at, Color color,
      {required double fontDp,
      bool filled = true,
      Color? textColor,
      bool centered = false,
      bool above = false,
      bool alignRight = false,
      bool avoid = false}) {
    final tp = TextPainter(
      text: TextSpan(
        text: text,
        style: TextStyle(
          fontFamily: AppText.family,
          fontSize: _dp(fontDp),
          fontWeight: FontWeight.w700,
          color: filled ? (textColor ?? Colors.white) : color,
          shadows: filled ? null : [Shadow(blurRadius: _dp(4), color: Colors.black)],
        ),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    final padH = _dp(filled ? 9 : 0), padV = _dp(filled ? 4 : 0);
    final w = tp.width + 2 * padH, h = tp.height + 2 * padV;
    var o = Offset(centered ? at.dx - w / 2 : (alignRight ? at.dx - w : at.dx), above ? at.dy - h : at.dy);
    o = Offset(o.dx, math.max(0, o.dy));
    final rect = Rect.fromLTWH(o.dx, o.dy, w, h);
    if (avoid && _labels.any((r) => r.overlaps(rect.inflate(_dp(2))))) return;
    if (avoid || filled) _labels.add(rect);
    if (filled) {
      canvas.drawRRect(RRect.fromRectAndRadius(Rect.fromLTWH(o.dx, o.dy, w, h), Radius.circular(h / 2)),
          Paint()..color = color);
    }
    tp.paint(canvas, o + Offset(padH, padV));
  }

  @override
  bool shouldRepaint(OverlayPainter old) =>
      old.result != result || old.mapper != mapper || old.imageW != imageW || old.screenScale != screenScale;
}

/// Hình thang hiệu chỉnh + lưới khoảng cách (màn hình căn chỉnh camera).
class CalibrationPainter extends CustomPainter {
  final List<List<double>> points; // tỉ lệ 0..1
  final GroundPlaneMapper? mapper; // null nếu 4 điểm suy biến
  final double imageW, imageH;
  final int? active;

  CalibrationPainter(this.points, this.mapper, this.imageW, this.imageH, this.active);

  @override
  void paint(Canvas canvas, Size size) {
    Offset rp(List<double> p) => Offset(p[0] * size.width, p[1] * size.height);
    final m = mapper;
    if (m != null) {
      final sx = size.width / imageW, sy = size.height / imageH;
      Offset px(Vec2 p) => Offset(p.x * sx, p.y * sy);
      final half = m.calib.laneHalfWidthM;
      var lastLabelY = double.infinity;
      for (var d = 10.0; d <= 60; d += 10) {
        final a = px(m.groundToImage(-half * 1.6, d)), b = px(m.groundToImage(half * 1.6, d));
        if (a.dy < 0 || b.dy < 0 || a.dy > size.height) continue;
        canvas.drawLine(
            a,
            b,
            Paint()
              ..color = Colors.white.withValues(alpha: 0.5)
              ..strokeWidth = 1.2);
        if (lastLabelY - b.dy < 16) continue; // gần chân trời các vạch dồn sát nhau: bỏ nhãn
        lastLabelY = b.dy;
        final tp = TextPainter(
          text: TextSpan(
              text: '${d.round()} m',
              style: const TextStyle(
                  fontFamily: AppText.family,
                  color: Colors.white,
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  shadows: [Shadow(blurRadius: 4, color: Colors.black)])),
          textDirection: TextDirection.ltr,
        )..layout();
        tp.paint(canvas, b + const Offset(6, -8));
      }
    }
    final poly = Path()..addPolygon([for (final p in points) rp(p)], true);
    canvas.drawPath(poly, Paint()..color = AppColors.accent.withValues(alpha: 0.14));
    canvas.drawPath(
        poly,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2
          ..strokeJoin = StrokeJoin.round
          ..color = AppColors.accent);
    for (var i = 0; i < 4; i++) {
      final c = rp(points[i]);
      final on = i == active;
      canvas.drawCircle(c, on ? 26 : 22, Paint()..color = AppColors.accent.withValues(alpha: on ? 0.30 : 0.18));
      canvas.drawCircle(c, on ? 13 : 11, Paint()..color = AppColors.accent);
      final tp = TextPainter(
        text: TextSpan(
            text: '${i + 1}',
            style: const TextStyle(
                fontFamily: AppText.family, color: AppColors.onAccent, fontSize: 13, fontWeight: FontWeight.w800)),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, c - Offset(tp.width / 2, tp.height / 2));
    }
  }

  @override
  bool shouldRepaint(CalibrationPainter old) => true;
}

/// Tạo mapper từ cấu hình; null nếu 4 điểm suy biến.
GroundPlaneMapper? tryMapper(CalibrationConfig c, double w, double h) {
  if (w <= 0 || h <= 0) return null;
  try {
    return GroundPlaneMapper(c, w, h);
  } catch (_) {
    return null;
  }
}
