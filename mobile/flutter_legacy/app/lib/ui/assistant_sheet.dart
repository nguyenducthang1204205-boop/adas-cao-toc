/// Bảng "Trợ lý AI | Vi phạm" - tương ứng hai thẻ dưới cùng cột phải của bản desktop
/// (ChatPanel + EventLog trong gui/widgets.py). Mở từ nút trên màn hình lái.
library;

import 'package:flutter/material.dart';

import '../core/assistant.dart';
import '../core/config.dart';
import '../core/violations.dart';
import '../services/settings_store.dart';
import '../services/violation_log.dart';
import 'condition_sheet.dart';
import 'theme.dart';

/// Câu gợi ý nhanh: giống ConditionPanel.QUICK của bản desktop (cùng câu gửi trợ lý).
const quickPrompts = [
  ('dry', 'Khô ráo', 'Đường khô ráo, trời nắng, tầm nhìn tốt'),
  ('wet', 'Mưa nhỏ', 'Trời mưa nhỏ, mặt đường ướt'),
  ('heavy_rain', 'Mưa to', 'Trời đang mưa to, mặt đường đọng nước'),
  ('fog', 'Sương mù', 'Có sương mù dày, tầm nhìn khoảng 100 m'),
  ('slippery', 'Trơn trượt', 'Mặt đường trơn trượt do dầu loang'),
  ('night', 'Ban đêm', 'Đang lái xe ban đêm trên cao tốc'),
  ('heavy_vehicle', 'Chở nặng', 'Tôi lái xe tải đang chở nặng'),
  ('tired', 'Mệt mỏi', 'Tôi đã lái lâu và cảm thấy buồn ngủ'),
];

class ChatMessage {
  final bool fromUser;
  final String text;
  final String? note; // ghi chú kỹ thuật (vd: đã chuyển sang tốc độ nhập tay)
  const ChatMessage(this.fromUser, this.text, [this.note]);
}

/// Hội thoại của phiên lái (giữ khi đóng/mở lại bảng).
class AssistantChat extends ChangeNotifier {
  final messages = <ChatMessage>[const ChatMessage(false, assistantGreeting)];

  /// Hỏi trợ lý offline rồi áp dụng kết quả vào cài đặt (giống MainWindow._on_assistant_result).
  AssistantResult ask(String text, AppSettings s, double speedKmh) {
    messages.add(ChatMessage(true, text));
    final r = offlineAdvice(text, s.policy, speedKmh);
    String? note;
    if (r.changed) s.applyCondition(r.conditionKey!, r.modifierKeys, r.visibilityM);
    final v = r.speedKmh;
    if (v != null) {
      s.manualSpeedKmh = v.clamp(20, 140).toDouble();
      if (s.useGps) {
        s.useGps = false; // như bản desktop: trợ lý trả về tốc độ thì tắt tự đo
        note = 'Đã chuyển sang tốc độ nhập tay ${s.manualSpeedKmh.round()} km/h. Bật lại GPS trong Cài đặt.';
      }
    }
    s.save();
    messages.add(ChatMessage(false, r.reply, note));
    notifyListeners();
    return r;
  }
}

Future<void> showAssistantSheet(
  BuildContext context, {
  required AssistantChat chat,
  required ViolationLog log,
  required ValueChanged<String> onAsk,
  int initialTab = 0,
}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    backgroundColor: AppColors.surface,
    barrierColor: AppColors.scrim,
    constraints: const BoxConstraints(maxWidth: 820),
    shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(Radii.lg))),
    builder: (context) {
      final h = MediaQuery.sizeOf(context).height;
      return Padding(
        padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
        child: SizedBox(
          height: h * 0.94,
          child: DefaultTabController(
            length: 2,
            initialIndex: initialTab,
            child: Column(children: [
              const SizedBox(height: Space.sm),
              Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(color: AppColors.strokeStrong, borderRadius: BorderRadius.circular(2)),
              ),
              Row(children: [
                Expanded(
                  child: ListenableBuilder(
                    listenable: log,
                    builder: (context, _) => TabBar(
                      isScrollable: true,
                      tabAlignment: TabAlignment.start,
                      dividerColor: Colors.transparent,
                      indicatorColor: AppColors.accent,
                      labelColor: AppColors.text,
                      unselectedLabelColor: AppColors.textSecondary,
                      labelStyle: AppText.bodyStrong,
                      unselectedLabelStyle: AppText.bodyStrong,
                      tabs: [
                        const _TabLabel(Icons.smart_toy_outlined, 'Trợ lý AI'),
                        _TabLabel(Icons.receipt_long_outlined,
                            log.sessionCount > 0 ? 'Vi phạm (${log.sessionCount})' : 'Vi phạm'),
                      ],
                    ),
                  ),
                ),
                IconButton(
                  tooltip: 'Đóng',
                  onPressed: () => Navigator.pop(context),
                  icon: const Icon(Icons.close_rounded),
                ),
                const SizedBox(width: Space.sm),
              ]),
              const Divider(height: 1, color: AppColors.stroke),
              Expanded(
                child: TabBarView(children: [
                  _ChatTab(chat: chat, onAsk: onAsk),
                  _ViolationTab(log: log),
                ]),
              ),
            ]),
          ),
        ),
      );
    },
  );
}

class _TabLabel extends StatelessWidget {
  final IconData icon;
  final String text;
  const _TabLabel(this.icon, this.text);

  @override
  Widget build(BuildContext context) => Tab(
        height: 48,
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(icon, size: 20),
          const SizedBox(width: Space.sm),
          Text(text),
        ]),
      );
}

// ------------------------------------------------------------------ Trợ lý AI

class _ChatTab extends StatefulWidget {
  final AssistantChat chat;
  final ValueChanged<String> onAsk;
  const _ChatTab({required this.chat, required this.onAsk});

  @override
  State<_ChatTab> createState() => _ChatTabState();
}

class _ChatTabState extends State<_ChatTab> {
  final _input = TextEditingController();

  @override
  void dispose() {
    _input.dispose();
    super.dispose();
  }

  void _submit(String text) {
    text = text.trim();
    if (text.isEmpty) return;
    _input.clear();
    widget.onAsk(text);
  }

  @override
  Widget build(BuildContext context) {
    return Column(children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(Space.lg, Space.sm, Space.lg, 0),
        child: Row(children: [
          const Icon(Icons.wifi_off_rounded, size: 14, color: AppColors.textSecondary),
          const SizedBox(width: Space.xs + 2),
          Expanded(
            child: Text('Chế độ: trợ lý offline · miễn phí, không cần Internet',
                style: AppText.caption.copyWith(fontSize: 12)),
          ),
        ]),
      ),
      Expanded(
        child: ListenableBuilder(
          listenable: widget.chat,
          builder: (context, _) {
            final msgs = widget.chat.messages;
            return ListView.builder(
              reverse: true, // tin mới nhất ở dưới, luôn trong tầm nhìn
              padding: const EdgeInsets.fromLTRB(Space.lg, Space.md, Space.lg, Space.md),
              itemCount: msgs.length,
              itemBuilder: (context, i) => _Bubble(msgs[msgs.length - 1 - i]),
            );
          },
        ),
      ),
      SizedBox(
        height: 48,
        child: ListView(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: Space.lg),
          children: [
            for (final (key, label, text) in quickPrompts)
              Padding(
                padding: const EdgeInsets.only(right: Space.sm),
                child: ActionChip(
                  avatar: Icon(roadConditions.containsKey(key) ? conditionIcon(key) : modifierIcon(key),
                      size: 18, color: AppColors.accent),
                  label: Text(label),
                  labelStyle: AppText.caption.copyWith(color: AppColors.text),
                  backgroundColor: AppColors.surfaceRaised,
                  side: const BorderSide(color: AppColors.stroke),
                  shape: const StadiumBorder(),
                  tooltip: 'Gửi cho Trợ lý AI: "$text"',
                  onPressed: () => _submit(text),
                ),
              ),
          ],
        ),
      ),
      Padding(
        padding: const EdgeInsets.fromLTRB(Space.lg, Space.sm, Space.lg, Space.md),
        child: Row(children: [
          Expanded(
            child: TextField(
              controller: _input,
              textInputAction: TextInputAction.send,
              onSubmitted: _submit,
              style: AppText.body,
              decoration: InputDecoration(
                hintText: 'Mô tả tình huống, vd: đang mưa, tôi chạy 90 km/h…',
                hintStyle: AppText.body.copyWith(color: AppColors.textSecondary),
                filled: true,
                fillColor: AppColors.surfaceRaised,
                isDense: true,
                contentPadding: const EdgeInsets.symmetric(horizontal: Space.lg, vertical: 14),
                border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(Radii.md),
                    borderSide: const BorderSide(color: AppColors.stroke)),
                enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(Radii.md),
                    borderSide: const BorderSide(color: AppColors.stroke)),
                focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(Radii.md),
                    borderSide: const BorderSide(color: AppColors.accent, width: 1.5)),
              ),
            ),
          ),
          const SizedBox(width: Space.sm),
          SizedBox(
            height: 48,
            child: FilledButton.icon(
              onPressed: () => _submit(_input.text),
              icon: const Icon(Icons.send_rounded, size: 18),
              label: const Text('Gửi'),
            ),
          ),
        ]),
      ),
    ]);
  }
}

class _Bubble extends StatelessWidget {
  final ChatMessage m;
  const _Bubble(this.m);

  @override
  Widget build(BuildContext context) {
    final user = m.fromUser;
    return Align(
      alignment: user ? Alignment.centerRight : Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 560),
        child: Container(
          margin: const EdgeInsets.only(bottom: Space.sm),
          padding: const EdgeInsets.symmetric(horizontal: Space.md + 2, vertical: Space.md - 2),
          decoration: BoxDecoration(
            color: user ? AppColors.accentSoft : AppColors.surfaceRaised,
            border: Border.all(color: user ? AppColors.accent.withValues(alpha: 0.4) : AppColors.stroke),
            borderRadius: BorderRadius.only(
              topLeft: const Radius.circular(Radii.md),
              topRight: const Radius.circular(Radii.md),
              bottomLeft: Radius.circular(user ? Radii.md : 4),
              bottomRight: Radius.circular(user ? 4 : Radii.md),
            ),
          ),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            if (!user)
              Padding(
                padding: const EdgeInsets.only(bottom: Space.xs),
                child: Row(mainAxisSize: MainAxisSize.min, children: [
                  const Icon(Icons.smart_toy_outlined, size: 14, color: AppColors.accent),
                  const SizedBox(width: Space.xs + 2),
                  Text('Trợ lý', style: AppText.overline.copyWith(color: AppColors.accent)),
                ]),
              ),
            Text(m.text, style: AppText.body.copyWith(fontSize: 14)),
            if (m.note != null)
              Padding(
                padding: const EdgeInsets.only(top: Space.xs),
                child: Text(m.note!, style: AppText.caption.copyWith(fontSize: 12)),
              ),
          ]),
        ),
      ),
    );
  }
}

// ------------------------------------------------------------------ Vi phạm

class _ViolationTab extends StatelessWidget {
  final ViolationLog log;
  const _ViolationTab({required this.log});

  Future<void> _confirmClear(BuildContext context) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Xóa nhật ký vi phạm?'),
        content: const Text('Toàn bộ các đợt vi phạm đã lưu trên điện thoại sẽ bị xóa.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Hủy')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: AppColors.dangerFill, foregroundColor: Colors.white),
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Xóa'),
          ),
        ],
      ),
    );
    if (ok == true) await log.clear();
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: log,
      builder: (context, _) {
        final items = log.items;
        return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(Space.lg, Space.sm, Space.sm, 0),
            child: Row(children: [
              Expanded(
                child: Text(
                  'Phiên giám sát #${log.sessionId} · ${log.sessionCount} vi phạm · đã lưu ${items.length}',
                  style: AppText.caption.copyWith(fontSize: 12),
                ),
              ),
              if (items.isNotEmpty)
                TextButton.icon(
                  onPressed: () => _confirmClear(context),
                  icon: const Icon(Icons.delete_outline_rounded, size: 18),
                  label: const Text('Xóa'),
                ),
            ]),
          ),
          Expanded(
            child: items.isEmpty
                ? const _EmptyLog()
                : ListView.separated(
                    padding: const EdgeInsets.fromLTRB(Space.lg, Space.sm, Space.lg, Space.lg),
                    itemCount: items.length,
                    separatorBuilder: (_, __) => const SizedBox(height: Space.sm),
                    itemBuilder: (context, i) => ViolationTile(items[i], currentSession: log.sessionId),
                  ),
          ),
        ]);
      },
    );
  }
}

class _EmptyLog extends StatelessWidget {
  const _EmptyLog();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(Space.xl),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          const Icon(Icons.verified_rounded, size: 40, color: AppColors.safe),
          const SizedBox(height: Space.md),
          Text('Chưa có vi phạm nào', style: AppText.title),
          const SizedBox(height: Space.xs),
          Text('Mỗi lần khoảng cách tới xe phía trước xuống dưới ngưỡng, hệ thống ghi lại một đợt tại đây.',
              textAlign: TextAlign.center, style: AppText.caption),
        ]),
      ),
    );
  }
}

String _two(int v) => v.toString().padLeft(2, '0');

class ViolationTile extends StatelessWidget {
  final Violation v;
  final int currentSession;
  const ViolationTile(this.v, {super.key, required this.currentSession});

  @override
  Widget build(BuildContext context) {
    final c = riskColor(v.level);
    final t = v.startedAt;
    final now = DateTime.now();
    final sameDay = t.year == now.year && t.month == now.month && t.day == now.day;
    final time = '${sameDay ? '' : '${_two(t.day)}/${_two(t.month)} '}${_two(t.hour)}:${_two(t.minute)}:${_two(t.second)}';
    final vehicle = '${classLabelsVi[v.className] ?? v.className}${v.trackId != null ? ' #${v.trackId}' : ''}';
    final ttc = v.minTtcS;
    final duration = v.open ? 'đang diễn ra' : '${vn(v.durationS!)} s';
    return Semantics(
      container: true,
      label: '${riskLabel(v.level)}, $vehicle, nhỏ nhất ${vn(v.minDistanceM)} mét, lúc $time',
      excludeSemantics: true,
      child: Container(
        padding: const EdgeInsets.all(Space.md),
        decoration: BoxDecoration(
          color: AppColors.surfaceRaised,
          borderRadius: BorderRadius.circular(Radii.md),
          border: Border.all(color: v.open ? c : AppColors.stroke, width: v.open ? 1.5 : 1),
        ),
        child: Row(children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(color: c.withValues(alpha: 0.16), shape: BoxShape.circle),
            child: Icon(riskIcon(v.level), size: 22, color: c),
          ),
          const SizedBox(width: Space.md),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Text(riskLabel(v.level), style: AppText.overline.copyWith(color: c)),
                const SizedBox(width: Space.sm),
                Flexible(
                  child: Text(vehicle, style: AppText.bodyStrong.copyWith(fontSize: 14), overflow: TextOverflow.ellipsis),
                ),
              ]),
              const SizedBox(height: 2),
              Text(
                '$time · ${v.speedKmh.round()} km/h · ngưỡng ${v.safeM.round()} m · $duration',
                style: AppText.caption.copyWith(fontSize: 12),
                overflow: TextOverflow.ellipsis,
              ),
              if (v.weatherFactor > 1.0)
                Text('${v.condition} · ×${vnFactor(v.weatherFactor)}',
                    style: AppText.caption.copyWith(fontSize: 12, color: AppColors.textTertiary),
                    overflow: TextOverflow.ellipsis),
            ]),
          ),
          const SizedBox(width: Space.md),
          Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
            Text.rich(TextSpan(children: [
              TextSpan(text: vn(v.minDistanceM), style: AppText.title.copyWith(color: c, fontSize: 20)),
              TextSpan(text: ' m', style: AppText.unit.copyWith(fontSize: 13)),
            ])),
            Text(ttc != null && ttc < 60 ? 'TTC ${vn(ttc)} s' : 'TTC --', style: AppText.caption.copyWith(fontSize: 12)),
          ]),
        ]),
      ),
    );
  }
}
