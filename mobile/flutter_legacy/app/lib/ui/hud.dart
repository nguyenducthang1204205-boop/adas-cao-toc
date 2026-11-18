/// Màn hình lái xe - phần trình bày (không camera, không logic): camera tràn viền, các cụm đồng hồ nổi.
///
/// Thứ bậc thông tin (liếc < 1 giây): 1) màu + chữ trạng thái (banner, viền phát sáng);
/// 2) khoảng cách tới xe trước; 3) tốc độ và khoảng cách cần giữ; 4) điều khiển ở các góc.
/// Tách khỏi DriveScreen để chụp ảnh thiết kế bằng test với khung hình thật (test_preview/).
library;

import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../core/config.dart';
import '../core/distance.dart';
import '../core/ipm.dart';
import '../core/pipeline.dart';
import '../core/safety.dart';
import 'components.dart';
import 'condition_sheet.dart';
import 'overlay_painter.dart';
import 'theme.dart';

enum SpeedSource { gps, manual, waiting, noPermission, gpsOff }

class HudState {
  final FrameResult? result;
  final GroundPlaneMapper? mapper;
  final double imageW, imageH;
  final double speedKmh;
  final SpeedSource speedSource;
  final SafetyPolicy policy;
  final String conditionKey;
  final Set<String> modifiers;
  final bool calibrated;
  final bool soundOn;
  final bool cameraReady;
  final String? techText; // null: ẩn thông số kỹ thuật
  /// Kết quả tự kiểm tra máy ("Máy của bạn: mức Trung bình ..."); null: ẩn.
  final String? perfNotice;
  final bool perfWeak; // máy dưới cấu hình tối thiểu: thông báo màu hổ phách
  final String? error;
  final int violations; // số đợt vi phạm của phiên giám sát này

  const HudState({
    this.result,
    this.mapper,
    this.imageW = 1280,
    this.imageH = 720,
    required this.speedKmh,
    required this.speedSource,
    required this.policy,
    required this.conditionKey,
    required this.modifiers,
    required this.calibrated,
    required this.soundOn,
    required this.cameraReady,
    this.techText,
    this.perfNotice,
    this.perfWeak = false,
    this.error,
    this.violations = 0,
  });

  Thresholds get thresholds => result?.thresholds ?? computeThresholds(speedKmh, policy);
  Risk get level => result?.level ?? Risk.safe;
}

class DriveHud extends StatelessWidget {
  final Widget? camera;
  final HudState s;
  final VoidCallback onCalibrate, onSettings, onToggleSound, onConditions;
  final ValueChanged<double> onSpeedStep;
  final VoidCallback? onRetry;
  final VoidCallback? onAssistant; // bảng Trợ lý AI | Vi phạm

  /// Kết quả mới nhất cho lớp overlay: vẽ lại riêng lớp này theo nhịp xử lý, còn các cụm đồng hồ chỉ dựng
  /// lại theo [s] (DriveScreen cập nhật ~10 lần/giây). null: overlay dùng s.result.
  final ValueListenable<FrameResult?>? live;

  const DriveHud({
    super.key,
    required this.camera,
    required this.s,
    this.live,
    required this.onCalibrate,
    required this.onSettings,
    required this.onToggleSound,
    required this.onConditions,
    required this.onSpeedStep,
    this.onRetry,
    this.onAssistant,
  });

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(builder: (context, box) {
      final w = box.maxWidth, h = box.maxHeight;
      final iw = s.imageW > 0 ? s.imageW : 1280.0, ih = s.imageH > 0 ? s.imageH : 720.0;
      final scale = math.max(w / iw, h / ih); // BoxFit.cover
      final pad = w > 900 ? Space.xl : Space.lg;
      final sideW = (w * 0.26).clamp(212.0, 292.0);
      final level = s.level;
      return Stack(children: [
        const Positioned.fill(child: ColoredBox(color: AppColors.bg)),
        if (camera != null)
          Positioned.fill(
            child: ClipRect(
              child: FittedBox(
                fit: BoxFit.cover,
                child: SizedBox(
                  width: iw,
                  height: ih,
                  child: Stack(fit: StackFit.expand, children: [
                    camera!,
                    RepaintBoundary(
                      child: live == null
                          ? CustomPaint(painter: OverlayPainter(s.result, s.mapper, iw, ih, screenScale: scale))
                          : ValueListenableBuilder<FrameResult?>(
                              valueListenable: live!,
                              builder: (_, r, __) => CustomPaint(
                                  painter: OverlayPainter(r ?? s.result, s.mapper, iw, ih, screenScale: scale)),
                            ),
                    ),
                  ]),
                ),
              ),
            ),
          ),
        // làm tối nhẹ mép trên/dưới để cụm đồng hồ luôn đọc được trên trời sáng
        const Positioned.fill(
          child: IgnorePointer(
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [Color(0x99000000), Color(0x00000000), Color(0x00000000), Color(0x80000000)],
                  stops: [0, 0.32, 0.7, 1],
                ),
              ),
            ),
          ),
        ),
        if (s.error != null)
          Center(child: _ErrorCard(message: s.error!, onRetry: onRetry))
        else if (!s.cameraReady)
          const Center(child: _Starting()),
        Positioned.fill(child: EdgeGlow(level: level)),
        // cụm trái: xe phía trước
        Positioned(
          left: pad,
          top: pad,
          bottom: pad + 52 + Space.md,
          width: sideW,
          child: Align(
            alignment: Alignment.topLeft,
            child: FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.topLeft,
              child: SizedBox(width: sideW, child: DistanceCluster(s: s)),
            ),
          ),
        ),
        // cụm phải: tốc độ + khoảng cách cần giữ + điều kiện đường
        Positioned(
          right: pad,
          top: pad,
          bottom: pad,
          width: sideW,
          child: Align(
            alignment: Alignment.topRight,
            child: FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.topRight,
              child: SizedBox(
                width: sideW,
                child: SpeedCluster(s: s, onConditions: onConditions, onSpeedStep: onSpeedStep),
              ),
            ),
          ),
        ),
        // giữa trên: trạng thái
        Positioned(
          top: pad,
          left: sideW + 2 * pad,
          right: sideW + 2 * pad,
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            AlertBanner(level: level, vehicles: s.result?.vehicles.length, ready: s.result != null),
            if (s.perfNotice != null) ...[
              const SizedBox(height: Space.sm),
              _PerfNotice(text: s.perfNotice!, weak: s.perfWeak),
            ],
            if (s.techText != null) ...[
              const SizedBox(height: Space.sm),
              _TechReadout(text: s.techText!),
            ],
          ]),
        ),
        if (!s.calibrated)
          Positioned(
            bottom: pad,
            left: sideW + 2 * pad,
            right: sideW + 2 * pad,
            child: Center(child: CalibrateNotice(onCalibrate: onCalibrate)),
          ),
        // dock điều khiển: góc dưới trái (xa vùng nhìn đường phía trước)
        Positioned(
          left: pad,
          bottom: pad,
          child: Row(children: [
            RoundAction(
              icon: s.soundOn ? Icons.volume_up_outlined : Icons.volume_off_outlined,
              label: s.soundOn ? 'Tắt âm thanh cảnh báo' : 'Bật âm thanh cảnh báo',
              active: !s.soundOn,
              onPressed: onToggleSound,
            ),
            const SizedBox(width: Space.sm + 2),
            RoundAction(icon: Icons.straighten_outlined, label: 'Căn chỉnh camera', onPressed: onCalibrate),
            const SizedBox(width: Space.sm + 2),
            RoundAction(icon: Icons.tune_outlined, label: 'Cài đặt', onPressed: onSettings),
            if (onAssistant != null) ...[
              const SizedBox(width: Space.sm + 2),
              _Badged(
                count: s.violations,
                child: RoundAction(
                  icon: Icons.smart_toy_outlined,
                  label: s.violations > 0 ? 'Trợ lý AI và ${s.violations} vi phạm' : 'Trợ lý AI và nhật ký vi phạm',
                  onPressed: onAssistant,
                ),
              ),
            ],
          ]),
        ),
      ]);
    });
  }
}

// ---------------------------------------------------------------------- cụm khoảng cách

/// Huy hiệu số đếm ở góc nút (số vi phạm của phiên).
class _Badged extends StatelessWidget {
  final int count;
  final Widget child;
  const _Badged({required this.count, required this.child});

  @override
  Widget build(BuildContext context) {
    if (count <= 0) return child;
    return Stack(clipBehavior: Clip.none, children: [
      child,
      Positioned(
        right: -4,
        top: -4,
        child: ExcludeSemantics(
          child: Container(
            constraints: const BoxConstraints(minWidth: 22),
            height: 22,
            padding: const EdgeInsets.symmetric(horizontal: 6),
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: AppColors.warning,
              borderRadius: BorderRadius.circular(Radii.pill),
              border: Border.all(color: AppColors.bg, width: 2),
            ),
            child: Text(count > 99 ? '99+' : '$count',
                style: AppText.overline.copyWith(color: AppColors.onWarning, letterSpacing: 0, fontSize: 11)),
          ),
        ),
      ),
    ]);
  }
}

class DistanceCluster extends StatelessWidget {
  final HudState s;
  const DistanceCluster({super.key, required this.s});

  @override
  Widget build(BuildContext context) {
    final lead = s.result?.lead;
    final thr = s.thresholds;
    final level = s.level;
    final color = lead == null ? AppColors.textSecondary : riskColor(lead.risk);
    return GlassPanel(
      accent: level == Risk.safe ? null : riskColor(level),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
        const Overline('Xe phía trước', icon: Icons.directions_car_outlined),
        const SizedBox(height: Space.sm),
        if (lead != null)
          Row(crossAxisAlignment: CrossAxisAlignment.baseline, textBaseline: TextBaseline.alphabetic, children: [
            TabularNumber(vn(lead.distanceM), style: AppText.display.copyWith(color: color)),
            const SizedBox(width: Space.xs),
            Text('m', style: AppText.unit.copyWith(fontSize: 20)),
          ])
        else ...[
          Text('—', style: AppText.display.copyWith(color: AppColors.textSecondary)),
          Text('Không có xe cùng làn', style: AppText.caption),
        ],
        const SizedBox(height: Space.md),
        GapGauge(distance: lead?.distanceM, dangerM: thr.dangerM, safeM: thr.safeM),
        const SizedBox(height: Space.md),
        Row(children: [
          Expanded(child: _Metric(label: 'Va chạm sau', value: _ttc(lead), alert: (lead?.ttcS ?? 99) < 4)),
          Expanded(child: _Metric(label: 'Tiếp cận', value: _closing(lead))),
        ]),
      ]),
    );
  }

  static String _ttc(VehicleState? v) => v?.ttcS == null ? '—' : '${vn(v!.ttcS!)} s';

  static String _closing(VehicleState? v) {
    final c = v?.closingSpeedMps;
    if (c == null || c.abs() < 0.5) return '—';
    return c > 0 ? '${(c * 3.6).round()} km/h' : 'Xa dần';
  }
}

class _Metric extends StatelessWidget {
  final String label, value;
  final bool alert;
  const _Metric({required this.label, required this.value, this.alert = false});

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(label, style: AppText.caption.copyWith(fontSize: 12)),
      const SizedBox(height: 2),
      Text(value, style: AppText.bodyStrong.copyWith(fontSize: 17, color: alert ? AppColors.warning : AppColors.text)),
    ]);
  }
}

/// Thước khoảng cách: vạch đỏ / hổ phách / xanh theo 2 ngưỡng, chấm trắng là xe phía trước.
class GapGauge extends StatelessWidget {
  final double? distance;
  final double dangerM, safeM;
  const GapGauge({super.key, required this.distance, required this.dangerM, required this.safeM});

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: distance == null
          ? 'Ngưỡng nguy hiểm ${dangerM.round()} mét, cảnh báo ${safeM.round()} mét'
          : 'Xe phía trước ${distance!.toStringAsFixed(0)} mét; nguy hiểm dưới ${dangerM.round()}, '
              'cảnh báo dưới ${safeM.round()} mét',
      excludeSemantics: true,
      child: SizedBox(height: 34, width: double.infinity, child: CustomPaint(painter: _GaugePainter(distance, dangerM, safeM))),
    );
  }
}

class _GaugePainter extends CustomPainter {
  final double? d;
  final double danger, safe;
  _GaugePainter(this.d, this.danger, this.safe);

  @override
  void paint(Canvas canvas, Size size) {
    final maxD = math.max(safe * 1.6, (d ?? 0) * 1.1);
    double x(double v) => (v / maxD).clamp(0.0, 1.0) * size.width;
    const barH = 6.0, top = 6.0;
    final segs = [
      (0.0, danger, AppColors.danger),
      (danger, safe, AppColors.warning),
      (safe, maxD, AppColors.safe),
    ];
    for (var i = 0; i < segs.length; i++) {
      final (a, b, c) = segs[i];
      final r = RRect.fromRectAndCorners(
        Rect.fromLTRB(x(a) + (i == 0 ? 0 : 1.5), top, x(b) - (i == 2 ? 0 : 1.5), top + barH),
        topLeft: Radius.circular(i == 0 ? 3 : 1),
        bottomLeft: Radius.circular(i == 0 ? 3 : 1),
        topRight: Radius.circular(i == 2 ? 3 : 1),
        bottomRight: Radius.circular(i == 2 ? 3 : 1),
      );
      canvas.drawRRect(r, Paint()..color = c.withValues(alpha: d == null ? 0.35 : 0.85));
    }
    // nhãn ngưỡng
    for (final v in [danger, safe]) {
      final tp = TextPainter(
        text: TextSpan(
            text: '${v.round()}',
            style: const TextStyle(
                fontFamily: AppText.family, fontSize: 11, fontWeight: FontWeight.w600, color: AppColors.textSecondary)),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, Offset((x(v) - tp.width / 2).clamp(0.0, (size.width - tp.width).clamp(0.0, double.infinity)), top + barH + 5));
    }
    if (d != null) {
      final cx = x(d!), cy = top + barH / 2;
      canvas.drawCircle(Offset(cx, cy), 8, Paint()..color = Colors.black.withValues(alpha: 0.5));
      canvas.drawCircle(Offset(cx, cy), 6.5, Paint()..color = Colors.white);
    }
  }

  @override
  bool shouldRepaint(_GaugePainter old) => old.d != d || old.danger != danger || old.safe != safe;
}

// ---------------------------------------------------------------------- cụm tốc độ

class SpeedCluster extends StatelessWidget {
  final HudState s;
  final VoidCallback onConditions;
  final ValueChanged<double> onSpeedStep;
  const SpeedCluster({super.key, required this.s, required this.onConditions, required this.onSpeedStep});

  @override
  Widget build(BuildContext context) {
    final thr = s.thresholds;
    final manual = s.speedSource != SpeedSource.gps;
    final (srcColor, srcText) = switch (s.speedSource) {
      SpeedSource.gps => (AppColors.safe, 'GPS'),
      SpeedSource.manual => (AppColors.info, 'Nhập tay'),
      SpeedSource.waiting => (AppColors.warning, 'Chờ GPS'),
      SpeedSource.noPermission => (AppColors.danger, 'Chưa cấp quyền vị trí'),
      SpeedSource.gpsOff => (AppColors.warning, 'GPS đang tắt'),
    };
    final basis = thresholdBasis(thr, s.policy);
    return GlassPanel(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
        Row(children: [
          const Overline('Tốc độ', icon: Icons.speed_outlined),
          const Spacer(),
          Flexible(child: StatusDot(color: srcColor, text: srcText)),
        ]),
        const SizedBox(height: Space.sm),
        Row(crossAxisAlignment: CrossAxisAlignment.center, children: [
          Row(crossAxisAlignment: CrossAxisAlignment.baseline, textBaseline: TextBaseline.alphabetic, children: [
            TabularNumber('${s.speedKmh.round()}', style: AppText.numeral),
            const SizedBox(width: Space.xs + 2),
            Text('km/h', style: AppText.unit),
          ]),
          const Spacer(),
          if (manual) ...[
            RoundAction(icon: Icons.remove, label: 'Giảm tốc độ nhập tay', size: 48, onPressed: () => onSpeedStep(-10)),
            const SizedBox(width: Space.sm),
            RoundAction(icon: Icons.add, label: 'Tăng tốc độ nhập tay', size: 48, onPressed: () => onSpeedStep(10)),
          ],
        ]),
        if (thr.overSpeedLimit) ...[
          const SizedBox(height: Space.xs),
          Text('Vượt 120 km/h - tốc độ tối đa cao tốc', style: AppText.caption.copyWith(color: AppColors.danger)),
        ],
        const SizedBox(height: Space.md),
        const Divider(),
        const SizedBox(height: Space.md),
        const Overline('Giữ tối thiểu', icon: Icons.social_distance_outlined),
        const SizedBox(height: Space.xs),
        Row(crossAxisAlignment: CrossAxisAlignment.baseline, textBaseline: TextBaseline.alphabetic, children: [
          TabularNumber('${thr.safeM.round()}', style: AppText.numeral.copyWith(fontSize: 38)),
          const SizedBox(width: Space.xs),
          Text('m', style: AppText.unit.copyWith(fontSize: 18)),
        ]),
        const SizedBox(height: Space.xs),
        StatusDot(color: AppColors.danger, text: 'Nguy hiểm dưới ${thr.dangerM.round()} m'),
        const SizedBox(height: 2),
        Text(basis, style: AppText.caption.copyWith(fontSize: 12)),
        const SizedBox(height: Space.md),
        _ConditionButton(conditionKey: s.conditionKey, mods: s.modifiers, onTap: onConditions),
      ]),
    );
  }
}

class _ConditionButton extends StatelessWidget {
  final String conditionKey;
  final Set<String> mods;
  final VoidCallback onTap;
  const _ConditionButton({required this.conditionKey, required this.mods, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final cond = roadConditions[conditionKey]!;
    final extra = [for (final m in mods) modifiers[m]?.$2 ?? m].join(' · ');
    return Semantics(
      button: true,
      label: 'Điều kiện đường: ${cond.name}${extra.isEmpty ? '' : ', $extra'}. Chạm để đổi',
      excludeSemantics: true,
      child: Material(
        color: Colors.white.withValues(alpha: 0.06),
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(Radii.md), side: const BorderSide(color: AppColors.stroke)),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: 52),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: Space.md, vertical: Space.sm),
              child: Row(children: [
                Icon(conditionIcon(conditionKey), size: 22, color: AppColors.accent),
                const SizedBox(width: Space.md),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
                    Text(cond.shortName, style: AppText.bodyStrong.copyWith(fontSize: 14)),
                    if (extra.isNotEmpty)
                      Text(extra, style: AppText.caption.copyWith(fontSize: 12), overflow: TextOverflow.ellipsis),
                  ]),
                ),
                const Icon(Icons.chevron_right_rounded, color: AppColors.textSecondary),
              ]),
            ),
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------- trạng thái & thông báo

class AlertBanner extends StatelessWidget {
  final Risk level;
  final int? vehicles;
  final bool ready;
  const AlertBanner({super.key, required this.level, required this.vehicles, required this.ready});

  @override
  Widget build(BuildContext context) {
    final alert = level == Risk.warning || level == Risk.danger;
    final Widget child;
    if (alert) {
      final fg = onRiskColor(level);
      child = Container(
        key: ValueKey(level),
        padding: const EdgeInsets.symmetric(horizontal: Space.xl - 4, vertical: Space.md - 2),
        decoration: BoxDecoration(
          color: riskFill(level),
          borderRadius: BorderRadius.circular(Radii.pill),
          boxShadow: [BoxShadow(color: riskColor(level).withValues(alpha: 0.45), blurRadius: 28)],
        ),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(riskIcon(level), color: fg, size: 22),
          const SizedBox(width: Space.sm + 2),
          Text(riskLabel(level),
              style: AppText.bodyStrong.copyWith(color: fg, fontWeight: FontWeight.w800, letterSpacing: 1.2)),
          Container(width: 1, height: 18, margin: const EdgeInsets.symmetric(horizontal: Space.md), color: fg.withValues(alpha: 0.4)),
          Flexible(
            child: Text(riskMessage(level),
                style: AppText.bodyStrong.copyWith(color: fg), overflow: TextOverflow.ellipsis),
          ),
        ]),
      );
    } else {
      child = GlassPanel(
        key: ValueKey('ok$ready'),
        radius: Radii.pill,
        padding: const EdgeInsets.symmetric(horizontal: Space.lg, vertical: Space.sm + 2),
        child: StatusDot(
          color: ready ? AppColors.safe : AppColors.info,
          text: !ready
              ? 'Đang khởi động nhận diện…'
              : 'Đang giám sát · ${vehicles ?? 0} xe trong khung',
        ),
      );
    }
    return Semantics(
      liveRegion: true,
      child: AnimatedSwitcher(
        duration: Motion.reduced(context) ? Duration.zero : Motion.base,
        switchInCurve: Motion.curve,
        transitionBuilder: (c, a) => FadeTransition(
          opacity: a,
          child: ScaleTransition(scale: Tween(begin: 0.96, end: 1.0).animate(a), child: c),
        ),
        child: child,
      ),
    );
  }
}

/// Viền phát sáng quanh màn hình theo mức cảnh báo - thấy được bằng thị giác ngoại vi, không cần nhìn
/// thẳng. NGUY HIỂM: nhịp đập 1,1 s (tắt khi hệ điều hành bật giảm chuyển động).
class EdgeGlow extends StatefulWidget {
  final Risk level;
  const EdgeGlow({super.key, required this.level});

  @override
  State<EdgeGlow> createState() => _EdgeGlowState();
}

class _EdgeGlowState extends State<EdgeGlow> with SingleTickerProviderStateMixin {
  late final _c = AnimationController(vsync: this, duration: Motion.pulse);

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _sync();
  }

  @override
  void didUpdateWidget(EdgeGlow old) {
    super.didUpdateWidget(old);
    _sync();
  }

  void _sync() {
    final pulse = widget.level == Risk.danger && !Motion.reduced(context);
    if (pulse && !_c.isAnimating) {
      _c.repeat(reverse: true);
    } else if (!pulse && _c.isAnimating) {
      _c.stop();
      _c.value = 1;
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final on = widget.level == Risk.warning || widget.level == Risk.danger;
    return IgnorePointer(
      child: AnimatedOpacity(
        opacity: on ? 1 : 0,
        duration: Motion.base,
        child: AnimatedBuilder(
          animation: _c,
          builder: (context, _) {
            final t = widget.level == Risk.danger ? (_c.isAnimating ? 0.45 + 0.55 * _c.value : 1.0) : 0.7;
            return CustomPaint(painter: _GlowPainter(riskColor(widget.level), t));
          },
        ),
      ),
    );
  }
}

class _GlowPainter extends CustomPainter {
  final Color color;
  final double strength;
  _GlowPainter(this.color, this.strength);

  @override
  void paint(Canvas canvas, Size size) {
    final w = math.min(size.shortestSide * 0.16, 64.0);
    final c0 = color.withValues(alpha: 0.55 * strength), c1 = color.withValues(alpha: 0);
    void edge(Rect r, Alignment from, Alignment to) {
      canvas.drawRect(r, Paint()..shader = LinearGradient(begin: from, end: to, colors: [c0, c1]).createShader(r));
    }

    edge(Rect.fromLTWH(0, 0, size.width, w), Alignment.topCenter, Alignment.bottomCenter);
    edge(Rect.fromLTWH(0, size.height - w, size.width, w), Alignment.bottomCenter, Alignment.topCenter);
    edge(Rect.fromLTWH(0, 0, w, size.height), Alignment.centerLeft, Alignment.centerRight);
    edge(Rect.fromLTWH(size.width - w, 0, w, size.height), Alignment.centerRight, Alignment.centerLeft);
  }

  @override
  bool shouldRepaint(_GlowPainter old) => old.color != color || old.strength != strength;
}

class CalibrateNotice extends StatelessWidget {
  final VoidCallback onCalibrate;
  const CalibrateNotice({super.key, required this.onCalibrate});

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      radius: Radii.pill,
      accent: AppColors.warning,
      padding: const EdgeInsets.only(left: Space.lg, right: Space.xs, top: Space.xs, bottom: Space.xs),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        const Icon(Icons.straighten_outlined, color: AppColors.warning, size: 20),
        const SizedBox(width: Space.sm + 2),
        Flexible(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
            Text('Chưa căn chỉnh camera', style: AppText.bodyStrong.copyWith(fontSize: 14)),
            Text('Khoảng cách chưa chính xác', style: AppText.caption.copyWith(fontSize: 12)),
          ]),
        ),
        const SizedBox(width: Space.xs),
        TextButton(onPressed: onCalibrate, child: const Text('Căn chỉnh')),
      ]),
    );
  }
}

class _TechReadout extends StatelessWidget {
  final String text;
  const _TechReadout({required this.text});

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      radius: Radii.sm,
      padding: const EdgeInsets.symmetric(horizontal: Space.md, vertical: Space.xs + 2),
      child: Text(text, textAlign: TextAlign.center, style: AppText.caption.copyWith(fontSize: 11, height: 1.35)),
    );
  }
}

/// Kết quả tự kiểm tra máy: mức hiệu năng và nhịp cảnh báo; máy yếu thì nói rõ cảnh báo chỉ để tham khảo.
class _PerfNotice extends StatelessWidget {
  final String text;
  final bool weak;
  const _PerfNotice({required this.text, required this.weak});

  @override
  Widget build(BuildContext context) {
    return Semantics(
      liveRegion: true,
      child: GlassPanel(
        radius: Radii.sm,
        accent: weak ? AppColors.warning : null,
        padding: const EdgeInsets.symmetric(horizontal: Space.md, vertical: Space.sm),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(weak ? Icons.warning_amber_rounded : Icons.speed_outlined,
              size: 18, color: weak ? AppColors.warning : AppColors.textSecondary),
          const SizedBox(width: Space.sm),
          Flexible(
            child: Text(text,
                textAlign: TextAlign.center,
                style: AppText.caption.copyWith(fontSize: 12, height: 1.35, color: AppColors.text)),
          ),
        ]),
      ),
    );
  }
}

class _Starting extends StatelessWidget {
  const _Starting();

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        const SizedBox.square(
            dimension: 20, child: CircularProgressIndicator(strokeWidth: 2.5, color: AppColors.accent)),
        const SizedBox(width: Space.md),
        Text('Đang khởi động camera và mô hình AI…', style: AppText.body),
      ]),
    );
  }
}

class _ErrorCard extends StatelessWidget {
  final String message;
  final VoidCallback? onRetry;
  const _ErrorCard({required this.message, this.onRetry});

  @override
  Widget build(BuildContext context) {
    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 440),
      child: GlassPanel(
        padding: const EdgeInsets.all(Space.xl),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          const Icon(Icons.no_photography_outlined, size: 36, color: AppColors.warning),
          const SizedBox(height: Space.md),
          Text('Không mở được camera', style: AppText.title),
          const SizedBox(height: Space.sm),
          Text(message, style: AppText.caption, textAlign: TextAlign.center),
          if (onRetry != null) ...[
            const SizedBox(height: Space.lg),
            FilledButton(onPressed: onRetry, child: const Text('Thử lại')),
          ],
        ]),
      ),
    );
  }
}
