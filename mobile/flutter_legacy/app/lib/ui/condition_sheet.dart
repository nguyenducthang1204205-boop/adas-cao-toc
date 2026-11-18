/// Bảng chọn điều kiện đường (mở từ cụm tốc độ). Ô lớn ≥ 72 dp, áp dụng ngay khi chạm.
library;

import 'package:flutter/material.dart';

import '../core/config.dart';
import 'theme.dart';

IconData conditionIcon(String key) => switch (key) {
      'wet' => Icons.water_drop_outlined,
      'heavy_rain' => Icons.thunderstorm_outlined,
      'fog' => Icons.foggy,
      'slippery' => Icons.oil_barrel_outlined,
      _ => Icons.wb_sunny_outlined,
    };

IconData modifierIcon(String key) => switch (key) {
      'night' => Icons.dark_mode_outlined,
      'heavy_vehicle' => Icons.local_shipping_outlined,
      _ => Icons.local_cafe_outlined, // mệt mỏi: gợi ý dừng nghỉ
    };

Future<void> showConditionSheet(
  BuildContext context, {
  required String conditionKey,
  required Set<String> modifierKeys,
  required ValueChanged<String> onCondition,
  required void Function(String key, bool on) onModifier,
}) {
  var cond = conditionKey;
  final mods = {...modifierKeys};
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: AppColors.surface,
    barrierColor: AppColors.scrim,
    constraints: const BoxConstraints(maxWidth: 820),
    shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(Radii.lg))),
    builder: (context) => StatefulBuilder(builder: (context, setSheet) {
      return SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(Space.xl, Space.md, Space.xl, Space.xl),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
            Center(
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(color: AppColors.strokeStrong, borderRadius: BorderRadius.circular(2)),
              ),
            ),
            const SizedBox(height: Space.md),
            Row(children: [
              Expanded(child: Text('Điều kiện đường', style: AppText.title)),
              IconButton(
                tooltip: 'Đóng',
                onPressed: () => Navigator.pop(context),
                icon: const Icon(Icons.close_rounded),
              ),
            ]),
            Text('Khoảng cách cần giữ được nhân theo độ bám mặt đường: đường càng trơn, hệ số càng lớn.', style: AppText.caption),
            const SizedBox(height: Space.lg),
            LayoutBuilder(builder: (context, box) {
              final n = box.maxWidth > 640 ? 5 : 3;
              final w = (box.maxWidth - (n - 1) * Space.md) / n;
              return Wrap(spacing: Space.md, runSpacing: Space.md, children: [
                for (final c in roadConditions.values)
                  SizedBox(
                    width: w,
                    child: _Tile(
                      icon: conditionIcon(c.key),
                      title: c.shortName,
                      subtitle: '×${vnFactor(c.factor)}',
                      selected: cond == c.key,
                      onTap: () {
                        setSheet(() => cond = c.key);
                        onCondition(c.key);
                      },
                    ),
                  ),
              ]);
            }),
            const SizedBox(height: Space.xl),
            Text('YẾU TỐ KHÁC', style: AppText.overline),
            const SizedBox(height: Space.sm),
            LayoutBuilder(builder: (context, box) {
              final w = (box.maxWidth - 2 * Space.md) / 3;
              return Wrap(spacing: Space.md, runSpacing: Space.md, children: [
                for (final e in modifiers.entries)
                  SizedBox(
                    width: w,
                    child: _Tile(
                      icon: modifierIcon(e.key),
                      title: e.value.$2,
                      subtitle: '×${vnFactor(e.value.$3)}',
                      selected: mods.contains(e.key),
                      toggle: true,
                      onTap: () {
                        final on = !mods.contains(e.key);
                        setSheet(() => on ? mods.add(e.key) : mods.remove(e.key));
                        onModifier(e.key, on);
                      },
                    ),
                  ),
              ]);
            }),
            const SizedBox(height: Space.md),
            Text(roadConditions[cond]!.advice, style: AppText.caption),
          ]),
        ),
      );
    }),
  );
}

class _Tile extends StatelessWidget {
  final IconData icon;
  final String title, subtitle;
  final bool selected, toggle;
  final VoidCallback onTap;
  const _Tile({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.selected,
    required this.onTap,
    this.toggle = false,
  });

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      selected: selected,
      toggled: toggle ? selected : null,
      label: '$title, hệ số $subtitle',
      excludeSemantics: true,
      child: AnimatedContainer(
        duration: Motion.fast,
        decoration: BoxDecoration(
          color: selected ? AppColors.accentSoft : AppColors.surfaceRaised,
          borderRadius: BorderRadius.circular(Radii.md),
          border: Border.all(color: selected ? AppColors.accent : AppColors.stroke, width: selected ? 1.5 : 1),
        ),
        child: Material(
          type: MaterialType.transparency,
          child: InkWell(
            borderRadius: BorderRadius.circular(Radii.md),
            onTap: onTap,
            child: ConstrainedBox(
              constraints: const BoxConstraints(minHeight: 76),
              child: Padding(
                padding: const EdgeInsets.all(Space.md),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Row(children: [
                    Icon(icon, size: 24, color: selected ? AppColors.accent : AppColors.text),
                    const Spacer(),
                    if (selected) const Icon(Icons.check_circle_rounded, size: 18, color: AppColors.accent),
                  ]),
                  const SizedBox(height: Space.sm),
                  Text(title, style: AppText.bodyStrong.copyWith(fontSize: 14), overflow: TextOverflow.ellipsis),
                  Text(subtitle, style: AppText.caption.copyWith(fontSize: 12)),
                ]),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
