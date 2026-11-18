package vn.adas.caotoc.core

import java.util.regex.Pattern
import kotlin.math.abs

/**
 * Trợ lý An toàn offline: port 1:1 của adas/assistant/offline.py.
 *
 * Người dùng mô tả tình huống bằng tiếng Việt (có dấu hoặc không dấu); trợ lý nhận ra điều kiện
 * mặt đường, các yếu tố cộng thêm, tầm nhìn và tốc độ, rồi trả về SafetyPolicy mới + lời khuyên.
 * Câu trả lời giống hệt bản desktop (kiểm bằng fixture assistant_python.json).
 */

/** Giới hạn hợp lệ của từng tham số (giống LIMITS của bản desktop). */
object AssistantLimits {
    val TIME_GAP_S = 2.0..6.0
    val WEATHER_FACTOR = 1.0..3.0
    val DANGER_RATIO = 0.3..0.8
    val MIN_DISTANCE_M = 3.0..20.0
    val TTC_WARNING_S = 2.0..8.0
    val TTC_DANGER_S = 1.0..4.0
    val ROAD_MU = 0.1..0.9
    val VISIBILITY_M = 0.0..1000.0
}

data class AssistantResult(
    val reply: String,
    val policy: SafetyPolicy,
    /** Tốc độ người dùng nêu trong câu (null nếu không nêu). */
    val speedKmh: Double?,
    /** Điều kiện / yếu tố / tầm nhìn đã áp dụng; null khi câu không đổi điều kiện (để app lưu lại). */
    val conditionKey: String?,
    val modifierKeys: List<String>,
    val visibilityM: Double,
) {
    val changed: Boolean get() = conditionKey != null
}

fun clampPolicy(p: SafetyPolicy): SafetyPolicy {
    val ttcW = p.ttcWarningS.coerceIn(AssistantLimits.TTC_WARNING_S)
    var ttcD = p.ttcDangerS.coerceIn(AssistantLimits.TTC_DANGER_S)
    if (ttcD >= ttcW) ttcD = maxOf(1.0, ttcW - 1.0)
    return p.copy(
        timeGapS = p.timeGapS.coerceIn(AssistantLimits.TIME_GAP_S),
        weatherFactor = p.weatherFactor.coerceIn(AssistantLimits.WEATHER_FACTOR),
        dangerRatio = p.dangerRatio.coerceIn(AssistantLimits.DANGER_RATIO),
        minDistanceM = p.minDistanceM.coerceIn(AssistantLimits.MIN_DISTANCE_M),
        ttcWarningS = ttcW,
        ttcDangerS = ttcD,
        roadMu = p.roadMu.coerceIn(AssistantLimits.ROAD_MU),
        visibilityM = p.visibilityM.coerceIn(AssistantLimits.VISIBILITY_M),
    )
}

object OfflineAssistant {
    const val HELP_TEXT = "Tôi là trợ lý offline, không cần Internet. Hãy mô tả tình huống, ví dụ: " +
        "\"trời mưa to\", \"sương mù tầm nhìn 80 m\", \"đường trơn do dầu loang\", " +
        "\"lái ban đêm, chở nặng\", \"tôi đang chạy 100 km/h\", \"đã tạnh mưa\". " +
        "Có thể gõ không dấu. Tôi sẽ đổi ngưỡng cảnh báo cho phù hợp."

    const val LAW_TEXT = "Quy định (đường khô ráo): 60 km/h: 35 m; trên 60–80 km/h: 55 m; trên 80–100 km/h: 70 m; " +
        "trên 100–120 km/h: 100 m. Dưới 60 km/h tài xế tự chủ động giữ khoảng cách phù hợp. " +
        "Khi mưa, sương mù, đường trơn phải giữ khoảng cách lớn hơn."

    /** Lời chào đầu hội thoại (giống ChatPanel của bản desktop). */
    const val GREETING = "Xin chào! Tôi là Trợ lý An toàn. Hãy cho tôi biết tốc độ, thời tiết, mặt đường " +
        "hoặc tình trạng của bạn - tôi sẽ điều chỉnh ngưỡng cảnh báo khoảng cách cho phù hợp."

    // Mỗi mục: (khóa, cụm từ, từ đơn). Cụm từ dùng cho cả câu có dấu lẫn không dấu. Từ đơn chỉ dùng
    // khi câu có dấu, vì bỏ dấu sẽ trùng từ khác: mù/mưa -> "mu", mệt/mét -> "met", tối/tôi -> "toi",
    // bão/báo -> "bao". Thứ tự ưu tiên: điều kiện nặng nhất được nhận trước; "hết mưa" đứng đầu.
    private val CONDITION_PATTERNS = listOf(
        Triple("dry", "hết mưa|tạnh mưa|mưa tạnh|đã tạnh|trời tạnh|hết sương|tan sương|trời quang|" +
            "khô ráo|đường khô|trời nắng|nắng ráo|thời tiết tốt|trời đẹp|bình thường|" +
            "đặt lại|mặc định|reset|khôi phục", "tạnh"),
        Triple("slippery", "trơn trượt|đường trơn|mặt đường trơn|trơn lắm|rất trơn|dầu loang|dầu nhớt|tràn dầu|" +
            "lầy lội|đường bùn|bùn đất|có bùn|đá sỏi|đường sỏi|có sỏi|băng giá|đóng băng",
            "\\btrơn\\b|\\bbùn\\b|\\bsỏi\\b|\\bcát\\b"),
        Triple("heavy_rain", "mưa (to|lớn|nặng hạt|rất to|xối xả|như trút|rào|dông|giông|bão)|mưa bão|trời bão|" +
            "có bão|gió bão|giông bão|dông bão|có giông|có dông|đọng nước|ngập nước|" +
            "nước lênh láng|trắng xóa", "\\bbão\\b|\\bgiông\\b|\\bdông\\b|\\bngập\\b"),
        Triple("fog", "sương mù|sương dày|có sương|nhiều sương|sương xuống|sương đêm|mù mịt|mù dày|trời mù|" +
            "tầm nhìn (kém|hạn chế|thấp|xấu|ngắn)|khói bụi|khói mù|nhiều khói|bụi mù|" +
            "không nhìn rõ|nhìn không rõ|nhìn mờ|mờ mịt", "\\bsương\\b|\\bmù\\b|\\bkhói\\b|\\bmờ\\b"),
        Triple("wet", "mưa|ướt|lất phất", ""),
    )
    private val MODIFIER_PATTERNS = listOf(
        Triple("night", "ban đêm|buổi tối|trời tối|tối rồi|lúc tối|tối nay|đêm nay|đêm khuya|nửa đêm|" +
            "chạy đêm|lái đêm|thiếu sáng|không có đèn|đèn đường tắt|chạng vạng|hoàng hôn", "\\bđêm\\b|\\btối\\b"),
        Triple("heavy_vehicle", "tải nặng|chở nặng|quá tải|đầy hàng|chở hàng|chở khách|lái xe tải|lái xe khách|" +
            "lái xe buýt|lái container|kéo container|chở container|lái xe đầu kéo|" +
            "chạy xe tải|chạy xe khách|xe tôi (là|chở)", ""),
        Triple("tired", "mệt mỏi|thấy mệt|hơi mệt|rất mệt|đang mệt|mệt quá|bị mệt|buồn ngủ|mỏi mắt|lái lâu|" +
            "thiếu ngủ|ngủ gật|díp mắt|uể oải", "\\bmệt\\b|\\bmỏi\\b"),
    )

    /**
     * \b và \w hiểu chữ Unicode như re của Python ("mù" có ranh giới sau "ù"). Android luôn dùng lớp ký tự
     * Unicode nhưng ném IllegalArgumentException nếu truyền cờ UNICODE_CHARACTER_CLASS (làm app thoát ngay
     * lần hỏi trợ lý đầu tiên); cờ chỉ cần cho JVM của unit test.
     */
    private val REGEX_FLAGS = try {
        Pattern.compile("a", Pattern.UNICODE_CHARACTER_CLASS)
        Pattern.UNICODE_CHARACTER_CLASS
    } catch (_: IllegalArgumentException) {
        0
    }

    private fun re(pattern: String): Pattern = Pattern.compile(pattern, REGEX_FLAGS)

    private class Rule(val key: String, val marked: Pattern, val plain: Pattern)

    /** Khớp trọn từ: "trời mù" khác "trời mưa". */
    private fun compile(patterns: List<Triple<String, String, String>>) = patterns.map { (k, phrases, short) ->
        Rule(k, re("\\b(?:$phrases)\\b" + if (short.isEmpty()) "" else "|$short"), re("\\b(?:${foldVi(phrases)})\\b"))
    }

    private val CONDITION_RE = compile(CONDITION_PATTERNS)
    private val MODIFIER_RE = compile(MODIFIER_PATTERNS)

    // Các mẫu dưới đây chạy trên chữ đã bỏ dấu
    private const val NOT_SPEED = "(?!\\s*(m\\b|met|giay|s\\b|phut))"
    private val SPEED_RE = re("(\\d{2,3})\\s*(km/?h|kmh|km\\b|cay so|cay\\b)|" +
        "(toc do|chay|di|dang o|vuot|dat)\\s*(khoang|tam|khong qua|duoi|tren)?\\s*(\\d{2,3})\\b" + NOT_SPEED)
    private val VISIBILITY_RE = re("(tam nhin|nhin (xa|thay|duoc)|thay duoc|chi thay)[^\\d]{0,20}(\\d{1,4})\\s*m\\b")
    private val HELP_RE = re(foldVi("giúp|hướng dẫn|làm (sao|gì|được gì)|biết gì|hiểu gì|xin chào|chào bạn|" +
        "\\bchào\\b|hello|\\bhi\\b"))
    private val LAW_RE = re(foldVi("quy định|luật|thông tư|bộ gtvt|bảng khoảng cách|bao nhiêu mét|bao xa"))

    /** Điều kiện mặt đường đang áp dụng, suy từ hệ số bám (để giữ nguyên khi chỉ đổi yếu tố khác). */
    fun currentConditionKey(p: SafetyPolicy): String =
        ROAD_CONDITIONS.values.minBy { abs(it.mu - p.roadMu) }.key

    private fun parseSpeed(text: String): Double? {
        val m = SPEED_RE.matcher(text)
        while (m.find()) {
            val v = (m.group(1) ?: m.group(5)).toInt()
            if (v in 10..200) return v.toDouble()
        }
        return null
    }

    fun advise(message: String, policy: SafetyPolicy, speedKmh: Double): AssistantResult {
        val raw = nfcVi(message.lowercase())
        val text = foldVi(message)
        val hasMarks = text != raw.replace('đ', 'd') // người dùng có gõ dấu không
        val speed = parseSpeed(text)
        val v = speed ?: speedKmh

        fun found(r: Rule) = if (hasMarks) r.marked.matcher(raw).find() else r.plain.matcher(text).find()

        var condKey = CONDITION_RE.firstOrNull { found(it) }?.key
        val mods = MODIFIER_RE.filter { found(it) }.map { it.key }
        val vis = VISIBILITY_RE.matcher(text).let { if (it.find()) it.group(3) else null }
        if (vis != null && (condKey == null || condKey == "dry")) condKey = "fog" // chỉ nêu tầm nhìn
        var visibility = vis?.toDouble() ?: if (condKey == null || condKey == "fog") policy.visibilityM else 0.0

        val changed = condKey != null || mods.isNotEmpty() || vis != null
        var key: String? = null
        var p = policy
        if (changed) {
            key = condKey ?: currentConditionKey(policy)
            if (key == "fog" && visibility == 0.0) visibility = 100.0 // sương mù chưa rõ tầm nhìn
            p = conditionPolicy(key, mods, visibility, policy)
        }
        p = clampPolicy(p)
        val thr = computeThresholds(v, p)
        val parts = ArrayList<String>()
        if (!changed && speed == null) {
            // Không nhận ra tình huống: trả lời câu hỏi quy định / hướng dẫn cách dùng
            parts += when {
                LAW_RE.matcher(text).find() -> LAW_TEXT
                HELP_RE.matcher(text).find() -> HELP_TEXT
                else -> "Tôi chưa nhận ra tình huống trong câu này nên giữ nguyên ngưỡng. $HELP_TEXT"
            }
        }
        if (changed) {
            val cond = ROAD_CONDITIONS.getValue(currentConditionKey(p))
            parts += "Điều kiện: ${p.condition.lowercase()}."
            parts += if (p.weatherFactor > 1.0) {
                "Quy định yêu cầu giữ khoảng cách lớn hơn khi đường khô; ước tính " +
                    "×${vnNum(p.weatherFactor)} so với bảng. ${cond.advice}"
            } else {
                cond.advice
            }
        }
        val legal = thr.legalM
        if (legal != null) {
            val band = thr.bandM!!
            val own = if (band > legal) ", ngưỡng bạn đặt cho dải này ${band.r()} m" else ""
            parts += "Ở ${v.r()} km/h, quy định (đường khô) tối thiểu ${legal.r()} m$own; " +
                "hãy giữ ≥ ${thr.safeM.r()} m (dưới ${thr.dangerM.r()} m là nguy hiểm)."
        } else {
            parts += "Dưới 60 km/h, quy định để tài xế tự chủ động giữ khoảng cách; ước tính theo quy tắc " +
                "${vnNum(p.timeGapS)} giây: ≥ ${thr.safeM.r()} m ở ${v.r()} km/h."
        }
        if (thr.overSpeedLimit) parts += "Lưu ý: tốc độ vượt mức tối đa 120 km/h trên cao tốc."
        thr.recommendedSpeedKmh?.let {
            parts += "Với tầm nhìn khoảng ${p.visibilityM.r()} m, không nên chạy quá ${it.r()} km/h để kịp dừng xe."
        }
        return AssistantResult(parts.joinToString(" "), p, speed, key, if (changed) mods else emptyList(), p.visibilityM)
    }
}
