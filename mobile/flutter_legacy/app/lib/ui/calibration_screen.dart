/// Căn chỉnh camera (IPM): kéo 4 điểm vào mép trong 2 vạch kẻ làn đang đi, nhập kích thước thật.
/// Giống hộp thoại "Căn chỉnh camera" của bản desktop; lưới 10-60 m vẽ ngay để tự kiểm tra.
/// Ảnh xem trước hiển thị trọn khung (contain) để chạm được cả 4 điểm ở mép ảnh.
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../core/config.dart';
import 'overlay_painter.dart';
import 'theme.dart';

class CalibrationScreen extends StatefulWidget {
  final Widget preview; // CameraPreview khi chạy thật; ảnh tĩnh khi chụp ảnh thiết kế
  final CalibrationConfig initial;
  final double imageW, imageH;
  const CalibrationScreen(
      {super.key, required this.preview, required this.initial, required this.imageW, required this.imageH});

  @override
  State<CalibrationScreen> createState() => _CalibrationScreenState();
}

class _CalibrationScreenState extends State<CalibrationScreen> {
  late CalibrationConfig c = widget.initial.copy();
  int? _active;
  late final _width = TextEditingController(text: _fmt(c.rectWidthM));
  late final _length = TextEditingController(text: _fmt(c.rectLengthM));
  late final _near = TextEditingController(text: _fmt(c.nearDistanceM));
  late final _half = TextEditingController(text: _fmt(c.laneHalfWidthM));

  static String _fmt(double v) => (v == v.roundToDouble() ? v.toStringAsFixed(0) : v.toString()).replaceAll('.', ',');

  @override
  void dispose() {
    for (final t in [_width, _length, _near, _half]) {
      t.dispose();
    }
    super.dispose();
  }

  void _readFields() {
    double read(TextEditingController t, double def, double lo, double hi) {
      final v = double.tryParse(t.text.replaceAll(',', '.'));
      return v == null ? def : v.clamp(lo, hi);
    }

    c.rectWidthM = read(_width, c.rectWidthM, 1, 20);
    c.rectLengthM = read(_length, c.rectLengthM, 2, 100);
    c.nearDistanceM = read(_near, c.nearDistanceM, 0, 50);
    c.laneHalfWidthM = read(_half, c.laneHalfWidthM, 0.5, 5);
  }

  @override
  Widget build(BuildContext context) {
    final mapper = tryMapper(c, widget.imageW, widget.imageH);
    return Scaffold(
      backgroundColor: AppColors.bg,
      body: SafeArea(
        child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Expanded(
            child: Padding(
              padding: const EdgeInsets.all(Space.md),
              child: Center(
                child: AspectRatio(
                  aspectRatio: widget.imageW / widget.imageH,
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(Radii.md),
                    child: Stack(fit: StackFit.expand, children: [
                      widget.preview,
                      LayoutBuilder(builder: (context, box) {
                        final size = Size(box.maxWidth, box.maxHeight);
                        return Semantics(
                          label: 'Ảnh camera với 4 điểm căn chỉnh. Kéo từng điểm vào mép trong vạch kẻ làn.',
                          child: GestureDetector(
                            behavior: HitTestBehavior.opaque,
                            onPanStart: (d) => _pick(d.localPosition, size),
                            onPanUpdate: (d) => _drag(d.localPosition, size),
                            onPanEnd: (_) => setState(() => _active = null),
                            child: CustomPaint(
                              size: size,
                              painter: CalibrationPainter(c.imagePoints, mapper, widget.imageW, widget.imageH, _active),
                            ),
                          ),
                        );
                      }),
                    ]),
                  ),
                ),
              ),
            ),
          ),
          SizedBox(width: 340, child: _panel(mapper != null)),
        ]),
      ),
    );
  }

  void _pick(Offset p, Size size) {
    var best = -1;
    var bestD = 52.0; // bán kính chạm (dp) - lớn hơn hình tròn vẽ để dễ trúng
    for (var i = 0; i < 4; i++) {
      final q = Offset(c.imagePoints[i][0] * size.width, c.imagePoints[i][1] * size.height);
      final d = (q - p).distance;
      if (d < bestD) {
        bestD = d;
        best = i;
      }
    }
    if (best >= 0) HapticFeedback.selectionClick();
    setState(() => _active = best >= 0 ? best : null);
  }

  void _drag(Offset p, Size size) {
    final i = _active;
    if (i == null) return;
    setState(() {
      c.imagePoints[i] = [(p.dx / size.width).clamp(0.0, 1.0), (p.dy / size.height).clamp(0.0, 1.0)];
    });
  }

  Widget _field(String label, String hint, TextEditingController t) => TextField(
        controller: t,
        keyboardType: const TextInputType.numberWithOptions(decimal: true),
        style: AppText.bodyStrong,
        decoration: InputDecoration(labelText: label, helperText: hint, suffixText: 'm', isDense: true),
        onChanged: (_) => setState(_readFields),
      );

  Widget _panel(bool valid) {
    return Container(
      decoration: const BoxDecoration(
        color: AppColors.surface,
        border: Border(left: BorderSide(color: AppColors.stroke)),
      ),
      child: Column(children: [
        Expanded(
          child: ListView(padding: const EdgeInsets.fromLTRB(Space.lg, Space.sm, Space.lg, Space.lg), children: [
            Row(children: [
              IconButton(
                tooltip: 'Quay lại, không lưu',
                onPressed: () => Navigator.pop(context),
                icon: const Icon(Icons.arrow_back_rounded),
              ),
              const SizedBox(width: Space.xs),
              Expanded(child: Text('Căn chỉnh camera', style: AppText.title.copyWith(fontSize: 20))),
            ]),
            const SizedBox(height: Space.sm),
            const _Hint(n: '1', text: 'Gắn chắc máy ở vị trí dùng khi lái.'),
            const _Hint(n: '2', text: 'Kéo 1–2 vào mép trong vạch kẻ gần, 3–4 ở xa.'),
            const _Hint(n: '3', text: 'Lưới 10–60 m phải nằm đúng trên mặt đường.'),
            const SizedBox(height: Space.lg),
            Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Expanded(child: _field('Bề rộng làn', 'Cao tốc: 3,75', _width)),
              const SizedBox(width: Space.md),
              Expanded(child: _field('Chiều dài 1–4', 'Theo vạch đứt', _length)),
            ]),
            const SizedBox(height: Space.md),
            Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Expanded(child: _field('Đầu xe tới cạnh gần', 'Tới điểm 1–2', _near)),
              const SizedBox(width: Space.md),
              Expanded(child: _field('Nửa hành lang', 'Vùng cảnh báo', _half)),
            ]),
            if (!valid) ...[
              const SizedBox(height: Space.md),
              Row(children: [
                const Icon(Icons.error_outline_rounded, size: 18, color: AppColors.danger),
                const SizedBox(width: Space.sm),
                Expanded(
                  child: Text('4 điểm chưa tạo thành hình thang hợp lệ',
                      style: AppText.caption.copyWith(color: AppColors.danger)),
                ),
              ]),
            ],
          ]),
        ),
        Container(
          padding: const EdgeInsets.fromLTRB(Space.lg, Space.md, Space.lg, Space.md),
          decoration: const BoxDecoration(border: Border(top: BorderSide(color: AppColors.stroke))),
          child: Row(children: [
            Expanded(
              child: OutlinedButton(
                style: OutlinedButton.styleFrom(padding: const EdgeInsets.symmetric(horizontal: Space.md)),
                onPressed: () => setState(() => c.imagePoints = CalibrationConfig.defaultPoints()),
                child: const Text('Mặc định'),
              ),
            ),
            const SizedBox(width: Space.md),
            Expanded(
              flex: 2,
              child: FilledButton(
                onPressed: valid
                    ? () {
                        _readFields();
                        Navigator.pop(context, c);
                      }
                    : null,
                child: const Text('Lưu căn chỉnh'),
              ),
            ),
          ]),
        ),
      ]),
    );
  }
}

class _Hint extends StatelessWidget {
  final String n, text;
  const _Hint({required this.n, required this.text});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: Space.sm),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Container(
          width: 22,
          height: 22,
          alignment: Alignment.center,
          decoration: const BoxDecoration(color: AppColors.accentSoft, shape: BoxShape.circle),
          child: Text(n,
              style: AppText.caption.copyWith(color: AppColors.accent, fontWeight: FontWeight.w800, fontSize: 12)),
        ),
        const SizedBox(width: Space.sm + 2),
        Expanded(child: Text(text, style: AppText.caption.copyWith(color: AppColors.text, height: 1.45))),
      ]),
    );
  }
}
