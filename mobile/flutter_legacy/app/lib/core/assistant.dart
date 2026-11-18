/// Trợ lý An toàn offline: port 1:1 của offline_advice() trong adas/ai_assistant.py.
///
/// Người dùng mô tả tình huống bằng tiếng Việt (có dấu hoặc không dấu); trợ lý nhận ra điều kiện
/// mặt đường, các yếu tố cộng thêm, tầm nhìn và tốc độ, rồi trả về SafetyPolicy mới + lời khuyên.
/// Câu trả lời giống hệt bản desktop (kiểm bằng test/fixtures/assistant.json).
library;

import 'config.dart';
import 'safety.dart';
import 'vn_text.dart';

/// Giới hạn hợp lệ của từng tham số (giống LIMITS của bản desktop).
const assistantLimits = {
  'time_gap_s': (2.0, 6.0),
  'weather_factor': (1.0, 3.0),
  'danger_ratio': (0.3, 0.8),
  'min_distance_m': (3.0, 20.0),
  'ttc_warning_s': (2.0, 8.0),
  'ttc_danger_s': (1.0, 4.0),
  'road_mu': (0.1, 0.9),
  'visibility_m': (0.0, 1000.0),
};

class AssistantResult {
  final String reply;
  final SafetyPolicy policy;
  final double? speedKmh; // tốc độ người dùng nêu trong câu (null nếu không nêu)
  /// Điều kiện / yếu tố / tầm nhìn đã áp dụng; null khi câu không đổi điều kiện (để app lưu lại).
  final String? conditionKey;
  final List<String> modifierKeys;
  final double visibilityM;
  const AssistantResult(this.reply, this.policy, this.speedKmh, this.conditionKey, this.modifierKeys,
      this.visibilityM);
  bool get changed => conditionKey != null;
}

double _clamp(String k, double v) {
  final (lo, hi) = assistantLimits[k]!;
  return v < lo ? lo : (v > hi ? hi : v);
}

SafetyPolicy clampPolicy(SafetyPolicy p) {
  final ttcW = _clamp('ttc_warning_s', p.ttcWarningS);
  var ttcD = _clamp('ttc_danger_s', p.ttcDangerS);
  if (ttcD >= ttcW) ttcD = ttcW - 1.0 < 1.0 ? 1.0 : ttcW - 1.0;
  return SafetyPolicy(
    timeGapS: _clamp('time_gap_s', p.timeGapS),
    bandGapsM: p.bandGapsM,
    weatherFactor: _clamp('weather_factor', p.weatherFactor),
    dangerRatio: _clamp('danger_ratio', p.dangerRatio),
    minDistanceM: _clamp('min_distance_m', p.minDistanceM),
    ttcWarningS: ttcW,
    ttcDangerS: ttcD,
    useLegalTable: p.useLegalTable,
    condition: p.condition,
    roadMu: _clamp('road_mu', p.roadMu),
    visibilityM: _clamp('visibility_m', p.visibilityM),
  );
}

// ---------------------------------------------------------------- mẫu từ khóa

/// \b của Python (chữ Unicode). \b của Dart chỉ hiểu chữ ASCII: "mù" sẽ không có ranh giới sau "ù".
const _w = r'[\p{L}\p{N}_]';
const _b = '(?:(?<=$_w)(?!$_w)|(?<!$_w)(?=$_w))';
RegExp _re(String pattern) => RegExp(pattern.replaceAll(r'\b', _b), unicode: true);

// Mỗi mục: (khóa, cụm từ, từ đơn). Cụm từ dùng cho cả câu có dấu lẫn không dấu. Từ đơn chỉ dùng
// khi câu có dấu, vì bỏ dấu sẽ trùng từ khác: mù/mưa -> "mu", mệt/mét -> "met", tối/tôi -> "toi",
// bão/báo -> "bao". Thứ tự ưu tiên: điều kiện nặng nhất được nhận trước; "hết mưa" đứng đầu.
const _conditionPatterns = [
  (
    'dry',
    r'hết mưa|tạnh mưa|mưa tạnh|đã tạnh|trời tạnh|hết sương|tan sương|trời quang|'
        r'khô ráo|đường khô|trời nắng|nắng ráo|thời tiết tốt|trời đẹp|bình thường|'
        r'đặt lại|mặc định|reset|khôi phục',
    r'tạnh'
  ),
  (
    'slippery',
    r'trơn trượt|đường trơn|mặt đường trơn|trơn lắm|rất trơn|dầu loang|dầu nhớt|tràn dầu|'
        r'lầy lội|đường bùn|bùn đất|có bùn|đá sỏi|đường sỏi|có sỏi|băng giá|đóng băng',
    r'\btrơn\b|\bbùn\b|\bsỏi\b|\bcát\b'
  ),
  (
    'heavy_rain',
    r'mưa (to|lớn|nặng hạt|rất to|xối xả|như trút|rào|dông|giông|bão)|mưa bão|trời bão|'
        r'có bão|gió bão|giông bão|dông bão|có giông|có dông|đọng nước|ngập nước|'
        r'nước lênh láng|trắng xóa',
    r'\bbão\b|\bgiông\b|\bdông\b|\bngập\b'
  ),
  (
    'fog',
    r'sương mù|sương dày|có sương|nhiều sương|sương xuống|sương đêm|mù mịt|mù dày|trời mù|'
        r'tầm nhìn (kém|hạn chế|thấp|xấu|ngắn)|khói bụi|khói mù|nhiều khói|bụi mù|'
        r'không nhìn rõ|nhìn không rõ|nhìn mờ|mờ mịt',
    r'\bsương\b|\bmù\b|\bkhói\b|\bmờ\b'
  ),
  ('wet', r'mưa|ướt|lất phất', ''),
];
const _modifierPatterns = [
  (
    'night',
    r'ban đêm|buổi tối|trời tối|tối rồi|lúc tối|tối nay|đêm nay|đêm khuya|nửa đêm|'
        r'chạy đêm|lái đêm|thiếu sáng|không có đèn|đèn đường tắt|chạng vạng|hoàng hôn',
    r'\bđêm\b|\btối\b'
  ),
  (
    'heavy_vehicle',
    r'tải nặng|chở nặng|quá tải|đầy hàng|chở hàng|chở khách|lái xe tải|lái xe khách|'
        r'lái xe buýt|lái container|kéo container|chở container|lái xe đầu kéo|'
        r'chạy xe tải|chạy xe khách|xe tôi (là|chở)',
    ''
  ),
  (
    'tired',
    r'mệt mỏi|thấy mệt|hơi mệt|rất mệt|đang mệt|mệt quá|bị mệt|buồn ngủ|mỏi mắt|lái lâu|'
        r'thiếu ngủ|ngủ gật|díp mắt|uể oải',
    r'\bmệt\b|\bmỏi\b'
  ),
];

/// -> [(khóa, mẫu cho câu có dấu, mẫu cho câu không dấu)]. Khớp trọn từ: "trời mù" khác "trời mưa".
List<(String, RegExp, RegExp)> _compile(List<(String, String, String)> patterns) => [
      for (final (k, phrases, short) in patterns)
        (k, _re('\\b(?:$phrases)\\b${short.isEmpty ? '' : '|$short'}'), _re('\\b(?:${foldVi(phrases)})\\b'))
    ];

final _conditionRe = _compile(_conditionPatterns);
final _modifierRe = _compile(_modifierPatterns);
// Các mẫu dưới đây chạy trên chữ đã bỏ dấu
const _notSpeed = r'(?!\s*(m\b|met|giay|s\b|phut))';
final _speedRe = _re(r'(\d{2,3})\s*(km/?h|kmh|km\b|cay so|cay\b)|'
    r'(toc do|chay|di|dang o|vuot|dat)\s*(khoang|tam|khong qua|duoi|tren)?\s*(\d{2,3})\b'
    '$_notSpeed');
final _visibilityRe = _re(r'(tam nhin|nhin (xa|thay|duoc)|thay duoc|chi thay)[^\d]{0,20}(\d{1,4})\s*m\b');
final _helpRe = _re(foldVi(r'giúp|hướng dẫn|làm (sao|gì|được gì)|biết gì|hiểu gì|xin chào|chào bạn|'
    r'\bchào\b|hello|\bhi\b'));
final _lawRe = _re(foldVi(r'quy định|luật|thông tư|bộ gtvt|bảng khoảng cách|bao nhiêu mét|bao xa'));

const assistantHelpText = 'Tôi là trợ lý offline, không cần Internet. Hãy mô tả tình huống, ví dụ: '
    '"trời mưa to", "sương mù tầm nhìn 80 m", "đường trơn do dầu loang", '
    '"lái ban đêm, chở nặng", "tôi đang chạy 100 km/h", "đã tạnh mưa". '
    'Có thể gõ không dấu. Tôi sẽ đổi ngưỡng cảnh báo cho phù hợp.';

const assistantLawText = 'Quy định (đường khô ráo): 60 km/h: 35 m; trên 60–80 km/h: 55 m; trên 80–100 km/h: 70 m; '
    'trên 100–120 km/h: 100 m. Dưới 60 km/h tài xế tự chủ động giữ khoảng cách phù hợp. '
    'Khi mưa, sương mù, đường trơn phải giữ khoảng cách lớn hơn.';

/// Lời chào đầu hội thoại (giống ChatPanel của bản desktop).
const assistantGreeting = 'Xin chào! Tôi là Trợ lý An toàn. Hãy cho tôi biết tốc độ, thời tiết, mặt đường '
    'hoặc tình trạng của bạn - tôi sẽ điều chỉnh ngưỡng cảnh báo khoảng cách cho phù hợp.';

/// Điều kiện mặt đường đang áp dụng, suy từ hệ số bám (để giữ nguyên khi chỉ đổi yếu tố khác).
String currentConditionKey(SafetyPolicy p) {
  RoadCondition? best;
  for (final c in roadConditions.values) {
    if (best == null || (c.mu - p.roadMu).abs() < (best.mu - p.roadMu).abs()) best = c;
  }
  return best!.key;
}

double? _parseSpeed(String text) {
  for (final m in _speedRe.allMatches(text)) {
    final v = int.parse(m.group(1) ?? m.group(5)!);
    if (v >= 10 && v <= 200) return v.toDouble();
  }
  return null;
}

AssistantResult offlineAdvice(String message, SafetyPolicy policy, double speedKmh) {
  final raw = nfcVi(message.toLowerCase());
  final text = foldVi(message);
  final hasMarks = text != raw.replaceAll('đ', 'd'); // người dùng có gõ dấu không
  final speed = _parseSpeed(text);
  final v = speed ?? speedKmh;

  bool found(RegExp marked, RegExp plain) => hasMarks ? marked.hasMatch(raw) : plain.hasMatch(text);

  String? condKey;
  for (final (k, m, p) in _conditionRe) {
    if (found(m, p)) {
      condKey = k;
      break;
    }
  }
  final mods = [
    for (final (k, m, p) in _modifierRe)
      if (found(m, p)) k
  ];
  final vis = _visibilityRe.firstMatch(text);
  if (vis != null && (condKey == null || condKey == 'dry')) condKey = 'fog'; // chỉ nêu tầm nhìn
  var visibility = vis != null
      ? double.parse(vis.group(3)!)
      : (condKey == null || condKey == 'fog' ? policy.visibilityM : 0.0);

  final changed = condKey != null || mods.isNotEmpty || vis != null;
  String? key;
  SafetyPolicy p;
  if (changed) {
    key = condKey ?? currentConditionKey(policy);
    if (key == 'fog' && visibility == 0) visibility = 100.0; // sương mù chưa rõ tầm nhìn
    p = conditionPolicy(key, mods, visibilityM: visibility, base: policy);
  } else {
    p = policy;
  }
  p = clampPolicy(p);
  final thr = computeThresholds(v, p);
  final parts = <String>[];
  if (!changed && speed == null) {
    // Không nhận ra tình huống: trả lời câu hỏi quy định / hướng dẫn cách dùng
    if (_lawRe.hasMatch(text)) {
      parts.add(assistantLawText);
    } else if (_helpRe.hasMatch(text)) {
      parts.add(assistantHelpText);
    } else {
      parts.add('Tôi chưa nhận ra tình huống trong câu này nên giữ nguyên ngưỡng. $assistantHelpText');
    }
  }
  if (changed) {
    final cond = roadConditions[currentConditionKey(p)]!;
    parts.add('Điều kiện: ${p.condition.toLowerCase()}.');
    if (p.weatherFactor > 1.0) {
      parts.add('Quy định yêu cầu giữ khoảng cách lớn hơn khi đường khô; ước tính '
          '×${vnNum(p.weatherFactor)} so với bảng. ${cond.advice}');
    } else {
      parts.add(cond.advice);
    }
  }
  final legal = thr.legalM;
  if (legal != null) {
    final band = thr.bandM!;
    final own = band > legal ? ', ngưỡng bạn đặt cho dải này ${band.round()} m' : '';
    parts.add('Ở ${v.round()} km/h, quy định (đường khô) tối thiểu ${legal.round()} m$own; '
        'hãy giữ ≥ ${thr.safeM.round()} m (dưới ${thr.dangerM.round()} m là nguy hiểm).');
  } else {
    parts.add('Dưới 60 km/h, quy định để tài xế tự chủ động giữ khoảng cách; ước tính theo quy tắc '
        '${vnNum(p.timeGapS)} giây: ≥ ${thr.safeM.round()} m ở ${v.round()} km/h.');
  }
  if (thr.overSpeedLimit) parts.add('Lưu ý: tốc độ vượt mức tối đa 120 km/h trên cao tốc.');
  final rec = thr.recommendedSpeedKmh;
  if (rec != null) {
    parts.add('Với tầm nhìn khoảng ${p.visibilityM.round()} m, không nên chạy quá '
        '${rec.round()} km/h để kịp dừng xe.');
  }
  return AssistantResult(parts.join(' '), p, speed, key, changed ? mods : const [], p.visibilityM);
}
