package vn.adas.caotoc.core

import java.math.BigDecimal
import java.math.RoundingMode
import java.text.Normalizer

/**
 * Chữ và số tiếng Việt, giống adas/formatting.py và _fold() của trợ lý offline.
 *
 * Số làm tròn trên giá trị nhị phân chính xác với HALF_EVEN như f"{v:.2f}" của Python, để câu trả lời của
 * trợ lý và chú thích ngưỡng giống từng byte với bản desktop (kiểm bằng fixture Python).
 */

/** Số cố định [digits] chữ số thập phân, dấu chấm. */
fun fixed(v: Double, digits: Int): String =
    BigDecimal(v).setScale(digits, RoundingMode.HALF_EVEN).toPlainString()

/** Số thập phân kiểu Việt Nam: dấu phẩy ("39,7"). */
fun vn(v: Double, digits: Int = 1): String = fixed(v, digits).replace('.', ',')

/** Số kiểu Việt Nam, bỏ phần thập phân bằng 0: 2 · 2,5 · 1,15 (giống vn_num của bản desktop). */
fun vnNum(v: Double): String = fixed(v, 2).trimEnd('0').trimEnd('.').replace('.', ',')

/** Hệ số nhân: tối đa 2 chữ số thập phân, bỏ một số 0 thừa (1,0 · 1,4 · 1,15). */
fun vnFactor(v: Double): String {
    var s = fixed(v, 2)
    if (s.endsWith("0")) s = s.dropLast(1)
    return s.replace('.', ',')
}

/** Làm tròn như Dart `.round()` / `int(v + 0.5)` của Python với số dương (nửa lên). */
fun Double.r(): Long = Math.round(this)

private val MARKS = Regex("\\p{Mn}+")

/** Chữ thường, bỏ dấu (đ -> d): "Trời MƯA to" -> "troi mua to". */
fun foldVi(text: String): String =
    Normalizer.normalize(text.lowercase().replace('đ', 'd'), Normalizer.Form.NFD).replace(MARKS, "")

/** Ghép dấu rời (bộ gõ dấu tổ hợp) thành chữ dựng sẵn để so khớp mẫu có dấu. */
fun nfcVi(text: String): String = Normalizer.normalize(text, Normalizer.Form.NFC)
