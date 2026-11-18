/// Chữ tiếng Việt cho trợ lý offline: bỏ dấu (giống _fold của adas/ai_assistant.py) và ghép dấu rời
/// về chữ dựng sẵn (giống unicodedata.normalize("NFC") với chữ tiếng Việt). Dart không có sẵn chuẩn hóa
/// Unicode; hai bảng dưới sinh từ unicodedata của Python.
library;

const _accented = 'àáâãäåçèéêëìíîïñòóôõöùúûüýÿāăąćĉċčďēĕėęěĝğġģĥĩīĭįĵķĺļľńņňōŏőŕŗřśŝşšţťũūŭůűųŵŷźżžơưǎǐǒǔǖǘǚǜǟǡǧǩǫǭǰǵǹǻȁȃȅȇȉȋȍȏȑȓȕȗșțȟȧȩȫȭȯȱȳḁḃḅḇḉḋḍḏḑḓḕḗḙḛḝḟḡḣḥḧḩḫḭḯḱḳḵḷḹḻḽḿṁṃṅṇṉṋṍṏṑṓṕṗṙṛṝṟṡṣṥṧṩṫṭṯṱṳṵṷṹṻṽṿẁẃẅẇẉẋẍẏẑẓẕẖẗẘẙạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ';
const _plain = 'aaaaaaceeeeiiiinooooouuuuyyaaaccccdeeeeegggghiiiijklllnnnooorrrssssttuuuuuuwyzzzouaiouuuuuaagkoojgnaaaeeiioorruusthaeooooyabbbcdddddeeeeefghhhhhiikkkllllmmmnnnnoooopprrrrsssssttttuuuuuvvwwwwwxxyzzzhtwyaaaaaaaaaaaaeeeeeeeeiioooooooooooouuuuuuuyyyy';

final Map<int, String> _foldMap = {
  for (var i = 0; i < _plain.length; i++) _accented.codeUnitAt(i): _plain[i],
};

bool _isMark(int c) => c >= 0x300 && c <= 0x36F;

/// Chữ thường, bỏ dấu (đ -> d): "Trời MƯA to" -> "troi mua to".
String foldVi(String text) {
  final out = StringBuffer();
  for (final c in text.toLowerCase().replaceAll('đ', 'd').runes) {
    if (_isMark(c)) continue;
    out.write(_foldMap[c] ?? String.fromCharCode(c));
  }
  return out.toString();
}

/// Dạng tách dấu chuẩn (NFD) -> chữ dựng sẵn, cho các chữ có dấu của tiếng Việt.
const _compose = <String, String>{
  'a\u0300': 'à',
  'a\u0301': 'á',
  'a\u0303': 'ã',
  'a\u0309': 'ả',
  'a\u0323': 'ạ',
  'a\u0306': 'ă',
  'a\u0306\u0300': 'ằ',
  'a\u0306\u0301': 'ắ',
  'a\u0306\u0303': 'ẵ',
  'a\u0306\u0309': 'ẳ',
  'a\u0323\u0306': 'ặ',
  'a\u0302': 'â',
  'a\u0302\u0300': 'ầ',
  'a\u0302\u0301': 'ấ',
  'a\u0302\u0303': 'ẫ',
  'a\u0302\u0309': 'ẩ',
  'a\u0323\u0302': 'ậ',
  'e\u0300': 'è',
  'e\u0301': 'é',
  'e\u0303': 'ẽ',
  'e\u0309': 'ẻ',
  'e\u0323': 'ẹ',
  'e\u0302': 'ê',
  'e\u0302\u0300': 'ề',
  'e\u0302\u0301': 'ế',
  'e\u0302\u0303': 'ễ',
  'e\u0302\u0309': 'ể',
  'e\u0323\u0302': 'ệ',
  'i\u0300': 'ì',
  'i\u0301': 'í',
  'i\u0303': 'ĩ',
  'i\u0309': 'ỉ',
  'i\u0323': 'ị',
  'o\u0300': 'ò',
  'o\u0301': 'ó',
  'o\u0303': 'õ',
  'o\u0309': 'ỏ',
  'o\u0323': 'ọ',
  'o\u0302': 'ô',
  'o\u0302\u0300': 'ồ',
  'o\u0302\u0301': 'ố',
  'o\u0302\u0303': 'ỗ',
  'o\u0302\u0309': 'ổ',
  'o\u0323\u0302': 'ộ',
  'o\u031B': 'ơ',
  'o\u031B\u0300': 'ờ',
  'o\u031B\u0301': 'ớ',
  'o\u031B\u0303': 'ỡ',
  'o\u031B\u0309': 'ở',
  'o\u031B\u0323': 'ợ',
  'u\u0300': 'ù',
  'u\u0301': 'ú',
  'u\u0303': 'ũ',
  'u\u0309': 'ủ',
  'u\u0323': 'ụ',
  'u\u031B': 'ư',
  'u\u031B\u0300': 'ừ',
  'u\u031B\u0301': 'ứ',
  'u\u031B\u0303': 'ữ',
  'u\u031B\u0309': 'ử',
  'u\u031B\u0323': 'ự',
  'y\u0300': 'ỳ',
  'y\u0301': 'ý',
  'y\u0303': 'ỹ',
  'y\u0309': 'ỷ',
  'y\u0323': 'ỵ',
};

final Map<String, String> _decompose = {for (final e in _compose.entries) e.value: e.key};

/// Thứ tự dấu chuẩn (lớp kết hợp Unicode): móc 216, nặng 220, còn lại 230.
int _ccc(int c) => c == 0x31B ? 216 : (c == 0x323 ? 220 : 230);

/// Ghép dấu rời (bộ gõ dấu tổ hợp) thành chữ dựng sẵn để so khớp mẫu có dấu.
String nfcVi(String text) {
  if (!text.runes.any(_isMark)) return text;
  // 1. tách hết chữ dựng sẵn rồi sắp lại thứ tự các dấu liền nhau (sắp xếp ổn định)
  final cps = <int>[];
  for (final c in text.runes) {
    final d = _decompose[String.fromCharCode(c)];
    cps.addAll(d != null ? d.runes : [c]);
  }
  for (var i = 1; i < cps.length; i++) {
    final x = cps[i];
    if (!_isMark(x)) continue;
    var j = i - 1;
    while (j >= 0 && _isMark(cps[j]) && _ccc(cps[j]) > _ccc(x)) {
      cps[j + 1] = cps[j];
      j--;
    }
    cps[j + 1] = x;
  }
  // 2. ghép tham lam: chữ gốc + tối đa 2 dấu
  final s = String.fromCharCodes(cps);
  final out = StringBuffer();
  var i = 0;
  while (i < s.length) {
    String? hit;
    var n = 3;
    for (; n >= 2 && hit == null; n--) {
      if (i + n <= s.length) hit = _compose[s.substring(i, i + n)];
    }
    if (hit != null) {
      out.write(hit);
      i += n + 1;
    } else {
      out.write(s[i]);
      i++;
    }
  }
  return out.toString();
}
