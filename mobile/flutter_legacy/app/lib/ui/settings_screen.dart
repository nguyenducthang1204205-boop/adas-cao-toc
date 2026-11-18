/// Cài đặt: nhóm theo thẻ (cảnh báo, ngưỡng theo dải tốc độ, tốc độ, hiệu năng, nhận diện, hiển thị, an toàn), hàng ≥ 64 dp.
/// Nhóm "Ngưỡng cảnh báo" giống tab cùng tên trong Cài đặt của bản desktop (gui/settings_dialog.py).
library;

import 'package:flutter/material.dart';

import '../core/config.dart';
import '../core/governor.dart';
import '../core/safety.dart';
import '../services/alert_player.dart';
import '../services/settings_store.dart';
import 'benchmark_screen.dart';
import 'theme.dart';

class SettingsScreen extends StatefulWidget {
  final AppSettings settings;
  final AlertPlayer alerts;
  const SettingsScreen({super.key, required this.settings, required this.alerts});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  AppSettings get s => widget.settings;

  void _set(VoidCallback f) {
    setState(f);
    s.save();
  }

  @override
  Widget build(BuildContext context) {
    final a = s.alert;
    return Scaffold(
      backgroundColor: AppColors.surface,
      appBar: AppBar(
        title: Text('Cài đặt', style: AppText.title.copyWith(fontSize: 20)),
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
              _Group(icon: Icons.notifications_active_outlined, title: 'Cảnh báo', children: [
                _SwitchRow(
                  title: 'Âm bíp cảnh báo',
                  subtitle: 'Bíp thưa khi CẢNH BÁO, dồn dập khi NGUY HIỂM',
                  value: a.soundEnabled,
                  onChanged: (v) => _set(() => a.soundEnabled = v),
                  extra: Row(children: [
                    _PreviewChip(
                        label: 'Nghe thử cảnh báo',
                        color: AppColors.warning,
                        onTap: () => widget.alerts.preview(Risk.warning)),
                    const SizedBox(width: Space.sm),
                    _PreviewChip(
                        label: 'Nghe thử nguy hiểm',
                        color: AppColors.danger,
                        onTap: () => widget.alerts.preview(Risk.danger)),
                  ]),
                ),
                _SwitchRow(
                  title: 'Giọng nói tiếng Việt',
                  subtitle: widget.alerts.voiceAvailable
                      ? 'Nói "Giữ khoảng cách" / "Nguy hiểm, giảm tốc ngay" khi mức cảnh báo tăng'
                      : 'Điện thoại chưa có giọng đọc tiếng Việt - cài trong Cài đặt › Chuyển văn bản thành giọng nói',
                  value: a.voiceEnabled,
                  onChanged: (v) => _set(() => a.voiceEnabled = v),
                ),
                _SwitchRow(
                  title: 'Chỉ cảnh báo xe cùng làn',
                  subtitle: 'Bỏ qua xe ở làn bên cạnh',
                  value: a.onlyEgoLane,
                  onChanged: (v) => _set(() => a.onlyEgoLane = v),
                ),
                _SliderRow(
                  title: 'Chống báo giả',
                  subtitle: 'Nguy hiểm phải kéo dài ngần này mới báo (tránh báo nhầm do nhận diện chập chờn)',
                  value: a.escalateSeconds,
                  min: 0,
                  max: 0.5,
                  divisions: 10,
                  display: '${vn(a.escalateSeconds, 2)} s',
                  onChanged: (v) => _set(() => a.escalateSeconds = (v * 20).round() / 20),
                ),
              ]),
              _Group(icon: Icons.social_distance_outlined, title: 'Ngưỡng cảnh báo', children: _thresholdRows()),
              _Group(icon: Icons.speed_outlined, title: 'Tốc độ xe', children: [
                _SwitchRow(
                  title: 'Lấy tốc độ từ GPS',
                  subtitle: 'Tắt, hoặc khi chưa bắt được GPS: dùng tốc độ nhập tay (nút − / + trên màn hình lái)',
                  value: s.useGps,
                  onChanged: (v) => _set(() => s.useGps = v),
                ),
              ]),
              _Group(icon: Icons.speed_outlined, title: 'Hiệu năng', children: _perfRows()),
              _Group(icon: Icons.memory_outlined, title: 'Nhận diện', children: [
                _SwitchRow(
                  title: 'Tăng tốc GPU',
                  subtitle: 'Tự đo GPU và CPU khi khởi động, dùng bên nhanh hơn',
                  value: s.preferGpu,
                  onChanged: (v) => _set(() => s.preferGpu = v),
                ),
                _SwitchRow(
                  title: 'Bám vết giữa các lần nhận diện',
                  subtitle:
                      'Đo lại vị trí xe giữa hai lần YOLO (vài ms mỗi khung) - khoảng cách cập nhật 10-30 lần/giây '
                      'kể cả khi YOLO chậm',
                  value: s.denseTracking,
                  onChanged: (v) => _set(() => s.denseTracking = v),
                ),
                _SliderRow(
                  title: 'Độ chắc chắn tối thiểu',
                  subtitle: 'Thấp: bắt nhiều xe hơn nhưng dễ nhận nhầm',
                  value: s.confidence,
                  min: 0.15,
                  max: 0.8,
                  divisions: 13,
                  display: '${(s.confidence * 100).round()} %',
                  onChanged: (v) => _set(() => s.confidence = v),
                ),
                Padding(
                  padding: const EdgeInsets.fromLTRB(Space.lg, Space.sm, Space.lg, Space.lg),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text('Loại phương tiện cảnh báo', style: AppText.bodyStrong),
                    const SizedBox(height: Space.sm),
                    Wrap(spacing: Space.sm, runSpacing: Space.sm, children: [
                      for (final c in const ['car', 'truck', 'bus', 'Jeepney', 'motorcycle'])
                        FilterChip(
                          label: Text(c == 'Jeepney' ? 'Xe khách nhỏ' : classLabelsVi[c]!),
                          labelStyle: AppText.caption
                              .copyWith(color: s.enabledClasses.contains(c) ? AppColors.text : AppColors.textSecondary),
                          selected: s.enabledClasses.contains(c),
                          showCheckmark: true,
                          checkmarkColor: AppColors.accent,
                          selectedColor: AppColors.accentSoft,
                          backgroundColor: AppColors.surfaceRaised,
                          side: BorderSide(color: s.enabledClasses.contains(c) ? AppColors.accent : AppColors.stroke),
                          shape: const StadiumBorder(),
                          materialTapTargetSize: MaterialTapTargetSize.padded,
                          onSelected: (on) => _set(() => on ? s.enabledClasses.add(c) : s.enabledClasses.remove(c)),
                        ),
                    ]),
                  ]),
                ),
                _SwitchRow(
                  title: 'Xoay ảnh 180°',
                  subtitle: 'Bật nếu khung xe lệch ngược so với hình (máy gắn ngược chiều)',
                  value: s.rotate180,
                  onChanged: (v) => _set(() => s.rotate180 = v),
                ),
              ]),
              _Group(icon: Icons.dashboard_customize_outlined, title: 'Hiển thị', children: [
                _SwitchRow(
                  title: 'Thông số kỹ thuật',
                  subtitle: 'Hiện FPS, thời gian YOLO và bộ suy luận trên màn hình lái (khi demo, chẩn đoán)',
                  value: s.showTech,
                  onChanged: (v) => _set(() => s.showTech = v),
                ),
              ]),
              _Group(icon: Icons.shield_outlined, title: 'An toàn', children: [
                Padding(
                  padding: const EdgeInsets.all(Space.lg),
                  child: Text(
                    'Ứng dụng chỉ hỗ trợ cảnh báo, không thay thế sự chú ý của người lái và không phải thiết bị ADAS '
                    'được chứng nhận. Khoảng cách chỉ đúng sau khi căn chỉnh camera cho đúng vị trí gắn máy; sai số '
                    'tăng mạnh ngoài khoảng 80 m và khi đường dốc. Không thao tác điện thoại khi xe đang chạy.',
                    style: AppText.caption.copyWith(height: 1.5),
                  ),
                ),
              ]),
              const SizedBox(height: Space.md),
              Center(child: Text('ADAS Cao tốc 1.0 · YOLOv11 + IPM', style: AppText.caption.copyWith(fontSize: 12))),
            ]),
          ),
        ),
      ),
    );
  }
}

extension on _SettingsScreenState {
  /// Mức hiệu năng (tự động / khóa), thấy xa, đo hiệu năng.
  List<Widget> _perfRows() {
    const modes = {'auto': 'Tự động', 'high': 'Cao', 'medium': 'Trung bình', 'low': 'Thấp'};
    final last = s.benchHistory.isEmpty ? null : s.benchHistory.first;
    final lastLevel = perfLevelFromName(s.lastLevel);
    return [
      Padding(
        padding: const EdgeInsets.fromLTRB(Space.lg, Space.md, Space.lg, Space.md),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Mức hiệu năng', style: AppText.bodyStrong),
          const SizedBox(height: 2),
          Text(
            'Tự động: đo máy và nhiệt độ, hạ nhịp xử lý khi máy chậm hoặc nóng; đường trống thì nhận diện thưa đi. '
            'Cao: bám vết mọi khung. Trung bình: 15 lần/giây. Thấp: 10 lần/giây, camera 480p.'
            '${lastLevel != null ? ' Máy này đo được: mức ${perfLevelNames[lastLevel]}.' : ''}',
            style: AppText.caption.copyWith(height: 1.4),
          ),
          const SizedBox(height: Space.sm),
          Wrap(spacing: Space.sm, runSpacing: Space.sm, children: [
            for (final e in modes.entries)
              ChoiceChip(
                label: Text(e.value),
                selected: s.perfMode == e.key,
                onSelected: (_) => _set(() => s.perfMode = e.key),
                labelStyle:
                    AppText.caption.copyWith(color: s.perfMode == e.key ? AppColors.text : AppColors.textSecondary),
                selectedColor: AppColors.accentSoft,
                backgroundColor: AppColors.surfaceRaised,
                side: BorderSide(color: s.perfMode == e.key ? AppColors.accent : AppColors.stroke),
                shape: const StadiumBorder(),
                materialTapTargetSize: MaterialTapTargetSize.padded,
              ),
          ]),
        ]),
      ),
      _SwitchRow(
        title: 'Thấy xe ở xa',
        subtitle: 'Cứ 3 lần nhận diện có 1 lần nhìn kỹ vùng quanh điểm tụ (xe xa to gấp đôi). '
            'Tự bỏ qua khi có xe gần, đang cảnh báo hoặc máy yếu',
        value: s.farDetect,
        onChanged: (v) => _set(() => s.farDetect = v),
      ),
      Material(
        type: MaterialType.transparency, // hiệu ứng chạm vẽ trên nền thẻ của nhóm
        child: ListTile(
          contentPadding: const EdgeInsets.symmetric(horizontal: Space.lg, vertical: Space.xs),
          minVerticalPadding: Space.md,
          title: Text('Đo hiệu năng máy', style: AppText.bodyStrong),
          subtitle: Text(
            last == null
                ? 'Chạy thử 30 giây trên video mẫu: độ mượt, thời gian YOLO, mức hiệu năng'
                : 'Lần gần nhất: YOLO ${(last['yolo_avg'] as num).round()} ms, cảnh báo '
                    '${vn((last['result_hz'] as num).toDouble())} lần/giây, giật ${vn((last['jank_pct'] as num).toDouble())} %',
            style: AppText.caption.copyWith(height: 1.4),
          ),
          trailing: const Icon(Icons.chevron_right_rounded, color: AppColors.textSecondary),
          onTap: () async {
            await Navigator.of(context).push(MaterialPageRoute(builder: (_) => BenchmarkScreen(settings: s)));
            if (mounted) _set(() {}); // hiện kết quả đo mới
          },
        ),
      ),
    ];
  }

  /// Khoảng cách CẢNH BÁO khi đường khô cho từng dải tốc độ; mỗi dải từ 60 km/h không thấp hơn luật.
  List<Widget> _thresholdRows() {
    final p = s.policy;
    Widget applied(double v) {
      final t = computeThresholds(v, p);
      return Text.rich(
        TextSpan(style: AppText.caption.copyWith(fontSize: 12, height: 1.4), children: [
          TextSpan(text: v < legalMinSpeed ? 'Ở ${v.round()} km/h: ' : 'Đang áp dụng: '),
          TextSpan(text: 'cảnh báo < ${t.safeM.round()} m', style: const TextStyle(color: AppColors.warning)),
          const TextSpan(text: ' · '),
          TextSpan(text: 'nguy hiểm < ${t.dangerM.round()} m', style: const TextStyle(color: AppColors.danger)),
        ]),
      );
    }

    final isDefault = s.timeGapS == defaultTimeGapS &&
        [for (var i = 0; i < legalGapTable.length; i++) s.bandGapsM[i] == legalGapTable[i].$2].every((e) => e);
    return [
      Padding(
        padding: const EdgeInsets.fromLTRB(Space.lg, Space.md, Space.lg, Space.sm),
        child: Text(
          'Khoảng cách CẢNH BÁO cho từng dải tốc độ khi đường khô ráo. Từ 60 km/h, mỗi dải không được thấp hơn '
          'mức tối thiểu của Bộ GTVT (Thông tư 31/2019/TT-BGTVT); chỉ được đặt xa hơn.',
          style: AppText.caption.copyWith(height: 1.5),
        ),
      ),
      _StepperRow(
        title: 'Dưới 60 km/h',
        caption: 'Tài xế tự chủ động · giữ quãng đường xe đi trong số giây này',
        detail: applied(50),
        value: '${vnNum(s.timeGapS)} giây',
        what: 'thời gian giữ khoảng cách dưới 60 km/h',
        onMinus: s.timeGapS > AppSettings.timeGapRange.$1
            ? () => _set(() => s.timeGapS = AppSettings.clampTimeGap(s.timeGapS - 0.5))
            : null,
        onPlus: s.timeGapS < AppSettings.timeGapRange.$2
            ? () => _set(() => s.timeGapS = AppSettings.clampTimeGap(s.timeGapS + 0.5))
            : null,
      ),
      for (var i = 0; i < legalGapTable.length; i++)
        _StepperRow(
          title: i == 0 ? '60 km/h' : 'Trên ${legalGapTable[i - 1].$1.round()} đến ${legalGapTable[i].$1.round()} km/h',
          caption: 'Luật tối thiểu ${legalGapTable[i].$2.round()} m',
          detail: applied(legalGapTable[i].$1),
          value: '${s.bandGapsM[i].round()} m',
          what: 'ngưỡng cảnh báo dải ${i == 0 ? '60' : 'đến ${legalGapTable[i].$1.round()}'} km/h',
          onMinus: s.bandGapsM[i] > legalGapTable[i].$2
              ? () => _set(() => s.bandGapsM[i] = AppSettings.clampBand(i, s.bandGapsM[i] - 5))
              : null,
          onPlus: s.bandGapsM[i] < AppSettings.maxBandGapM
              ? () => _set(() => s.bandGapsM[i] = AppSettings.clampBand(i, s.bandGapsM[i] + 5))
              : null,
        ),
      Padding(
        padding: const EdgeInsets.fromLTRB(Space.sm, Space.xs, Space.lg, Space.md),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          TextButton.icon(
            onPressed: isDefault ? null : () => _set(s.resetBands),
            icon: const Icon(Icons.restart_alt_rounded, size: 20),
            label: const Text('Đặt lại bằng mức tối thiểu theo luật'),
            style: TextButton.styleFrom(minimumSize: const Size(48, 48)),
          ),
          Padding(
            padding: const EdgeInsets.only(left: Space.sm),
            child: Text(
              'Khi mưa, sương mù, đường trơn... các ngưỡng trên được nhân thêm hệ số theo điều kiện đường. '
              'Ngưỡng NGUY HIỂM = ngưỡng cảnh báo × ${vnNum(p.dangerRatio)}.',
              style: AppText.caption.copyWith(fontSize: 12, height: 1.5),
            ),
          ),
        ]),
      ),
    ];
  }
}

class _Group extends StatelessWidget {
  final IconData icon;
  final String title;
  final List<Widget> children;
  const _Group({required this.icon, required this.title, required this.children});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: Space.lg),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Padding(
          padding: const EdgeInsets.only(left: Space.xs, bottom: Space.sm),
          child: Row(children: [
            Container(
              width: 28,
              height: 28,
              decoration: BoxDecoration(color: AppColors.accentSoft, borderRadius: BorderRadius.circular(8)),
              child: ExcludeSemantics(child: Icon(icon, size: 17, color: AppColors.accent)),
            ),
            const SizedBox(width: Space.sm + 2),
            Semantics(header: true, child: Text(title.toUpperCase(), style: AppText.overline)),
          ]),
        ),
        Container(
          decoration: BoxDecoration(
            color: AppColors.surfaceRaised,
            borderRadius: BorderRadius.circular(Radii.md),
            border: Border.all(color: AppColors.stroke),
          ),
          clipBehavior: Clip.antiAlias,
          child: Column(children: [
            for (var i = 0; i < children.length; i++) ...[
              if (i > 0) const Divider(indent: Space.lg, endIndent: Space.lg),
              children[i],
            ],
          ]),
        ),
      ]),
    );
  }
}

class _SwitchRow extends StatelessWidget {
  final String title, subtitle;
  final bool value;
  final ValueChanged<bool> onChanged;
  final Widget? extra;
  const _SwitchRow(
      {required this.title, required this.subtitle, required this.value, required this.onChanged, this.extra});

  @override
  Widget build(BuildContext context) {
    return MergeSemantics(
      child: InkWell(
        onTap: () => onChanged(!value),
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: 64),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: Space.lg, vertical: Space.md),
            child: Row(children: [
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(title, style: AppText.bodyStrong),
                  const SizedBox(height: 2),
                  Text(subtitle, style: AppText.caption.copyWith(height: 1.4)),
                  if (extra != null) ...[const SizedBox(height: Space.sm + 2), extra!],
                ]),
              ),
              const SizedBox(width: Space.md),
              Switch(value: value, onChanged: onChanged),
            ]),
          ),
        ),
      ),
    );
  }
}

class _SliderRow extends StatelessWidget {
  final String title, subtitle, display;
  final double value, min, max;
  final int divisions;
  final ValueChanged<double> onChanged;
  const _SliderRow({
    required this.title,
    required this.subtitle,
    required this.value,
    required this.min,
    required this.max,
    required this.divisions,
    required this.display,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(Space.lg, Space.md, Space.lg, Space.xs),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(child: Text(title, style: AppText.bodyStrong)),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: Space.sm + 2, vertical: Space.xs),
            decoration: BoxDecoration(color: AppColors.accentSoft, borderRadius: BorderRadius.circular(Radii.pill)),
            child: Text(display, style: AppText.caption.copyWith(color: AppColors.accent, fontWeight: FontWeight.w700)),
          ),
        ]),
        const SizedBox(height: 2),
        Text(subtitle, style: AppText.caption),
        Slider(value: value, min: min, max: max, divisions: divisions, label: display, onChanged: onChanged),
      ]),
    );
  }
}

/// Hàng có nút − / + (48 dp) chỉnh một số; nút mờ đi khi chạm giới hạn.
class _StepperRow extends StatelessWidget {
  final String title, caption, value, what;
  final Widget detail;
  final VoidCallback? onMinus, onPlus;
  const _StepperRow({
    required this.title,
    required this.caption,
    required this.detail,
    required this.value,
    required this.what,
    required this.onMinus,
    required this.onPlus,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: Space.lg, vertical: Space.md),
      child: Row(children: [
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: AppText.bodyStrong),
            const SizedBox(height: 2),
            Text(caption, style: AppText.caption.copyWith(height: 1.4)),
            const SizedBox(height: 2),
            detail,
          ]),
        ),
        const SizedBox(width: Space.sm),
        _StepButton(icon: Icons.remove, label: 'Giảm $what', onTap: onMinus),
        Semantics(
          liveRegion: true,
          label: '$what: $value',
          excludeSemantics: true,
          child: SizedBox(
            width: 72,
            child: Text(value,
                textAlign: TextAlign.center,
                style: AppText.bodyStrong.copyWith(fontSize: 16, fontWeight: FontWeight.w700)),
          ),
        ),
        _StepButton(icon: Icons.add, label: 'Tăng $what', onTap: onPlus),
      ]),
    );
  }
}

class _StepButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback? onTap;
  const _StepButton({required this.icon, required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final on = onTap != null;
    return Semantics(
      button: true,
      enabled: on,
      label: label,
      excludeSemantics: true,
      child: Material(
        color: on ? AppColors.accentSoft : Colors.transparent,
        shape: CircleBorder(side: BorderSide(color: on ? AppColors.accent.withValues(alpha: 0.5) : AppColors.stroke)),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: SizedBox.square(
            dimension: 48,
            child: Icon(icon, size: 22, color: on ? AppColors.accent : AppColors.textTertiary),
          ),
        ),
      ),
    );
  }
}

class _PreviewChip extends StatelessWidget {
  final String label;
  final Color color;
  final VoidCallback onTap;
  const _PreviewChip({required this.label, required this.color, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: color.withValues(alpha: 0.12),
      shape: StadiumBorder(side: BorderSide(color: color.withValues(alpha: 0.45))),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: 48),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: Space.md),
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              Icon(Icons.play_arrow_rounded, size: 18, color: color),
              const SizedBox(width: Space.xs),
              Text(label, style: AppText.caption.copyWith(color: AppColors.text, fontSize: 12)),
            ]),
          ),
        ),
      ),
    );
  }
}
