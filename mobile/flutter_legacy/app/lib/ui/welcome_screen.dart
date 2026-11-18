/// Màn hình chào lần đầu: giới thiệu, 3 bước trước khi lên đường, lời nhắc an toàn.
library;

import 'package:flutter/material.dart';

import 'components.dart';
import 'theme.dart';

class WelcomeScreen extends StatelessWidget {
  final VoidCallback onStart;
  const WelcomeScreen({super.key, required this.onStart});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bg,
      body: Stack(children: [
        // quầng sáng thương hiệu
        Positioned(
          left: -160,
          top: -200,
          child: Container(
            width: 620,
            height: 620,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: RadialGradient(
                  colors: [AppColors.accent.withValues(alpha: 0.20), AppColors.accent.withValues(alpha: 0)]),
            ),
          ),
        ),
        SafeArea(
          child: LayoutBuilder(builder: (context, box) {
            final wide = box.maxWidth > 700;
            final intro = _Intro(compact: !wide, tall: box.maxHeight > 560);
            final steps = _Steps(onStart: onStart);
            return SingleChildScrollView(
              padding: EdgeInsets.symmetric(horizontal: wide ? Space.xxl + 8 : Space.xl, vertical: Space.xl),
              child: ConstrainedBox(
                constraints: BoxConstraints(minHeight: box.maxHeight - 2 * Space.xl),
                child: wide
                    ? Row(crossAxisAlignment: CrossAxisAlignment.center, children: [
                        Expanded(flex: 5, child: intro),
                        const SizedBox(width: Space.xxl),
                        Expanded(flex: 6, child: steps),
                      ])
                    : Column(children: [intro, const SizedBox(height: Space.xl), steps]),
              ),
            );
          }),
        ),
      ]),
    );
  }
}

class _Intro extends StatelessWidget {
  final bool compact;
  final bool tall; // màn hình đủ cao để hiện thêm chip tính năng
  const _Intro({required this.compact, this.tall = false});

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
      const AppMark(size: 60),
      const SizedBox(height: Space.lg),
      Text('ADAS Cao tốc', style: AppText.headline.copyWith(fontSize: compact ? 28 : 32)),
      const SizedBox(height: Space.sm),
      Text(
        'Trợ lý giữ khoảng cách an toàn trên cao tốc. AI chạy ngay trên điện thoại, không cần Internet.',
        style: AppText.body.copyWith(color: AppColors.textSecondary, fontSize: 15),
      ),
      const SizedBox(height: Space.lg),
      if (tall) ...[
        const Wrap(spacing: Space.sm, runSpacing: Space.sm, children: [
          _Feature(icon: Icons.visibility_outlined, text: 'Nhận diện xe phía trước'),
          _Feature(icon: Icons.social_distance_outlined, text: 'Ngưỡng theo quy định'),
          _Feature(icon: Icons.record_voice_over_outlined, text: 'Cảnh báo bằng giọng nói'),
        ]),
        const SizedBox(height: Space.lg),
      ],
      const _SafetyNote(),
    ]);
  }
}

class _Feature extends StatelessWidget {
  final IconData icon;
  final String text;
  const _Feature({required this.icon, required this.text});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: Space.md, vertical: Space.sm),
      decoration: BoxDecoration(
        color: AppColors.surfaceRaised,
        borderRadius: BorderRadius.circular(Radii.pill),
        border: Border.all(color: AppColors.stroke),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        ExcludeSemantics(child: Icon(icon, size: 18, color: AppColors.accent)),
        const SizedBox(width: Space.sm),
        Text(text, style: AppText.caption.copyWith(color: AppColors.text)),
      ]),
    );
  }
}

class _Steps extends StatelessWidget {
  final VoidCallback onStart;
  const _Steps({required this.onStart});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(Space.xl, Space.lg + 4, Space.xl, Space.xl),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(Radii.lg),
        border: Border.all(color: AppColors.stroke),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
        Text('TRƯỚC KHI LÊN ĐƯỜNG', style: AppText.overline),
        const SizedBox(height: Space.md),
        const _Step(
            n: 1,
            icon: Icons.smartphone_outlined,
            title: 'Gắn chắc điện thoại',
            text: 'Màn hình nằm ngang, camera nhìn thẳng ra đường.'),
        const _Step(
            n: 2,
            icon: Icons.straighten_outlined,
            title: 'Căn chỉnh camera',
            text: 'Kéo 4 điểm vào vạch kẻ làn đang đi.'),
        const _Step(
            n: 3,
            icon: Icons.notifications_active_outlined,
            title: 'Lái xe, app lo phần cảnh báo',
            text: 'Màu, âm thanh, giọng nói khi đi quá gần.',
            last: true),
        const SizedBox(height: Space.xl),
        SizedBox(
          width: double.infinity,
          child: FilledButton.icon(
            onPressed: onStart,
            icon: const Icon(Icons.arrow_forward_rounded),
            label: const Text('Tôi đã hiểu, bắt đầu'),
          ),
        ),
      ]),
    );
  }
}

class _Step extends StatelessWidget {
  final int n;
  final IconData icon;
  final String title, text;
  final bool last;
  const _Step({required this.n, required this.icon, required this.title, required this.text, this.last = false});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: last ? 0 : Space.md),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(color: AppColors.accentSoft, borderRadius: BorderRadius.circular(Radii.sm + 2)),
          child: ExcludeSemantics(child: Icon(icon, size: 22, color: AppColors.accent)),
        ),
        const SizedBox(width: Space.md),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('$n. $title', style: AppText.bodyStrong),
            const SizedBox(height: 2),
            Text(text, style: AppText.caption.copyWith(height: 1.4)),
          ]),
        ),
      ]),
    );
  }
}

class _SafetyNote extends StatelessWidget {
  const _SafetyNote();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(Space.md),
      decoration: BoxDecoration(
        color: AppColors.warning.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(Radii.sm),
        border: Border.all(color: AppColors.warning.withValues(alpha: 0.35)),
      ),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const ExcludeSemantics(child: Icon(Icons.info_outline_rounded, size: 18, color: AppColors.warning)),
        const SizedBox(width: Space.sm),
        Expanded(
          child: Text(
            'Ứng dụng chỉ hỗ trợ, không thay thế sự chú ý của người lái và không phải thiết bị an toàn '
            'được chứng nhận. Không thao tác điện thoại khi xe đang chạy.',
            style: AppText.caption.copyWith(color: AppColors.text, height: 1.45, fontSize: 12.5),
          ),
        ),
      ]),
    );
  }
}
