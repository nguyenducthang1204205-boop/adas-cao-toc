package vn.adas.caotoc.core

import java.math.BigDecimal
import java.math.RoundingMode
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

/**
 * Ngưỡng khoảng cách an toàn theo tốc độ và điều kiện đường (port của adas/alert/thresholds.py).
 *
 * Khô ráo, theo Thông tư 31/2019/TT-BGTVT Điều 11: 60 -> 35 m; (60, 80] -> 55 m; (80, 100] -> 70 m;
 * (100, 120] -> 100 m. V < 60 km/h: ước tính quy tắc 2 giây. Người dùng đặt ngưỡng riêng cho từng dải
 * ([SafetyPolicy.bandGapsM], [SafetyPolicy.timeGapS]), không bao giờ thấp hơn luật. Điều kiện bất lợi nhân
 * hệ số một lần.
 */

/** (tốc độ tối đa của dải km/h, khoảng cách tối thiểu m). */
val LEGAL_GAP_TABLE = listOf(60.0 to 35.0, 80.0 to 55.0, 100.0 to 70.0, 120.0 to 100.0)
const val LEGAL_MIN_SPEED = 60.0
const val LEGAL_MAX_SPEED = 120.0
const val DEFAULT_TIME_GAP_S = 2.0
const val GRAVITY = 9.81

enum class Risk(val rank: Int) { INFO(0), SAFE(0), WARNING(1), DANGER(2) }

data class Thresholds(
    val speedKmh: Double,
    /** Dưới ngưỡng -> CẢNH BÁO. */
    val safeM: Double,
    /** Dưới ngưỡng -> NGUY HIỂM. */
    val dangerM: Double,
    val gapM: Double,
    /** Tối thiểu theo luật (null khi < 60 km/h). */
    val legalM: Double?,
    /** Ngưỡng người dùng đặt cho dải tốc độ này, đường khô (>= legalM). */
    val bandM: Double?,
    val overSpeedLimit: Boolean,
    val recommendedSpeedKmh: Double?,
)

fun legalMinGap(speedKmh: Double): Double? {
    if (speedKmh < LEGAL_MIN_SPEED) return null
    for ((vmax, gap) in LEGAL_GAP_TABLE) if (speedKmh <= vmax) return gap
    return LEGAL_GAP_TABLE.last().second * speedKmh / LEGAL_MAX_SPEED
}

/**
 * Ngưỡng cảnh báo (đường khô) của dải tốc độ chứa V, không thấp hơn luật. null khi V < 60 km/h;
 * trên 120 km/h ngoại suy như [legalMinGap] (giống band_gap_m).
 */
fun bandGapM(speedKmh: Double, p: SafetyPolicy): Double? {
    val legal = legalMinGap(speedKmh) ?: return null
    var i = LEGAL_GAP_TABLE.indexOfFirst { speedKmh <= it.first }
    if (i < 0) i = LEGAL_GAP_TABLE.size - 1
    if (i >= p.bandGapsM.size) return legal
    var user = p.bandGapsM[i]
    if (speedKmh > LEGAL_MAX_SPEED) user *= speedKmh / LEGAL_MAX_SPEED
    return max(user, legal)
}

/** Tốc độ tối đa để quãng dừng (phản xạ + phanh v²/(2μg)) không vượt tầm nhìn. */
fun recommendedSpeedKmh(visibilityM: Double, mu: Double, reactionS: Double = 1.5): Double {
    val a = mu * GRAVITY
    val v = a * (-reactionS + sqrt(reactionS * reactionS + 2 * visibilityM / a))
    return v * 3.6
}

fun computeThresholds(speed: Double, p: SafetyPolicy): Thresholds {
    val speedKmh = max(speed, 0.0)
    val gap = speedKmh / 3.6 * p.timeGapS
    val legal = if (p.useLegalTable) legalMinGap(speedKmh) else null
    val band = if (legal != null) bandGapM(speedKmh, p) else null
    // Khô ráo: >= 60 km/h theo ngưỡng của dải (>= luật); < 60 km/h theo quy tắc thời gian
    val base = max(band ?: gap, p.minDistanceM)
    val safe = base * p.weatherFactor
    val danger = max(p.minDistanceM, safe * p.dangerRatio)
    val rec = if (p.visibilityM > 0) recommendedSpeedKmh(p.visibilityM, p.roadMu) else null
    return Thresholds(speedKmh, safe, danger, gap, legal, band, speedKmh > LEGAL_MAX_SPEED, rec)
}

fun classifyRisk(distanceM: Double, ttcS: Double?, thr: Thresholds, p: SafetyPolicy): Risk = when {
    distanceM < thr.dangerM || (ttcS != null && ttcS < p.ttcDangerS) -> Risk.DANGER
    distanceM < thr.safeM || (ttcS != null && ttcS < p.ttcWarningS) -> Risk.WARNING
    else -> Risk.SAFE
}

/** Câu giải thích ngưỡng đang áp dụng; giống hệt threshold_basis() của bản desktop. */
fun thresholdBasis(thr: Thresholds, p: SafetyPolicy): String {
    val legal = thr.legalM
    val band = thr.bandM
    var s = when {
        legal != null && band != null && band > legal -> "Bạn đặt ${band.r()} m (luật ≥ ${legal.r()} m)"
        legal != null -> "Theo luật (đường khô): ${legal.r()} m"
        else -> "Quy tắc ${vnNum(p.timeGapS)} giây: ${thr.gapM.r()} m"
    }
    if (p.weatherFactor > 1.0) s += "\n× ${vnNum(p.weatherFactor)} do điều kiện đường"
    return s
}

/**
 * SafetyPolicy từ một điều kiện mặt đường + các yếu tố cộng thêm (giống condition_policy).
 * Ngưỡng theo dải tốc độ và quy tắc thời gian lấy từ [base] (người dùng đặt), giữ nguyên.
 */
fun conditionPolicy(
    conditionKey: String,
    mods: Iterable<String>,
    visibilityM: Double = 0.0,
    base: SafetyPolicy = SafetyPolicy(),
): SafetyPolicy {
    val cond = ROAD_CONDITIONS.getValue(conditionKey)
    var factor = cond.factor
    val names = mutableListOf(cond.name)
    var ttcW = cond.ttcWarningS
    var ttcD = cond.ttcDangerS
    for (m in mods) {
        val mod = MODIFIERS.getValue(m)
        factor *= mod.factor
        names += mod.label.lowercase()
        ttcW += 0.5
        ttcD += 0.25
    }
    return SafetyPolicy(
        timeGapS = base.timeGapS,
        bandGapsM = base.bandGapsM.toList(),
        // làm tròn theo giá trị thập phân chính xác như round(x, 2) của Python: 1,5 × 1,15 = 1,7249999… -> 1,72
        weatherFactor = BigDecimal(min(factor, MAX_FACTOR)).setScale(2, RoundingMode.HALF_EVEN).toDouble(),
        dangerRatio = base.dangerRatio,
        minDistanceM = base.minDistanceM,
        ttcWarningS = min(ttcW, 8.0),
        ttcDangerS = min(ttcD, 4.0),
        useLegalTable = true,
        condition = names.joinToString(", "),
        roadMu = cond.mu,
        visibilityM = visibilityM,
    )
}
