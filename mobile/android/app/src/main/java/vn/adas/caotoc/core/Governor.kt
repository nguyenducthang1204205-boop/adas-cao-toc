package vn.adas.caotoc.core

import kotlin.math.roundToInt

/**
 * Bộ điều tốc hiệu năng: chọn mức Cao / Trung bình / Thấp theo năng lực máy, nhiệt độ và mức rủi ro.
 *
 * Ý tưởng lấy từ các hệ thống chạy thị giác thời gian thực trên phần cứng hạn chế:
 * - nhịp xử lý cố định, tách khỏi nhịp vẽ giao diện (openpilot chạy vòng 20 Hz);
 * - chỉ giữ khung mới nhất, khung đến khi đang bận bị bỏ (CameraX KEEP_ONLY_LATEST, MediaPipe FlowLimiter);
 * - đọc "dư nhiệt" của máy và chủ động hạ tải trước khi máy tự hạ xung (Android ADPF Thermal API);
 * - dồn tính toán vào lúc cần (CarSafe): đường trống thì YOLO chạy thưa, có xe gần / TTC nhỏ thì hết tốc lực.
 */
enum class PerfLevel(val key: String, val label: String, val trackHz: Double, val maxTracked: Int) {
    /** Bám vết mọi khung camera, 4 xe gần nhất. */
    HIGH("high", "Cao", 0.0, 4),
    MEDIUM("medium", "Trung bình", 15.0, 3),
    LOW("low", "Thấp", 10.0, 2);

    fun down(): PerfLevel = entries[(ordinal + 1).coerceAtMost(entries.size - 1)]
    fun up(): PerfLevel = entries[(ordinal - 1).coerceAtLeast(0)]

    companion object {
        fun fromKey(key: String?): PerfLevel? = entries.firstOrNull { it.key == key }
    }
}

object PerfThresholds {
    /** Thời gian YOLO (tiền xử lý + suy luận, ms) giữa các mức: < 50 Cao, 50-120 Trung bình, > 120 Thấp. */
    const val YOLO_MS_HIGH = 50.0
    const val YOLO_MS_MEDIUM = 120.0

    /** YOLO chậm hơn mức này: máy dưới cấu hình tối thiểu, cảnh báo chỉ mang tính tham khảo. */
    const val YOLO_MS_WEAK = 300.0

    /** Trạng thái nhiệt theo thang của Android PowerManager. */
    const val THERMAL_MODERATE = 2
    const val THERMAL_SEVERE = 3
}

fun capabilityLevel(yoloMs: Double, margin: Double = 1.0): PerfLevel = when {
    yoloMs < PerfThresholds.YOLO_MS_HIGH * margin -> PerfLevel.HIGH
    yoloMs <= PerfThresholds.YOLO_MS_MEDIUM * margin -> PerfLevel.MEDIUM
    else -> PerfLevel.LOW
}

private fun worse(a: PerfLevel, b: PerfLevel) = if (a.ordinal >= b.ordinal) a else b

class Governor(var level: PerfLevel, var forced: PerfLevel? = null) {
    private var goodSince: Double? = null
    private var lastDown = -1e9
    var reason = ""
        private set

    val effective: PerfLevel get() = forced ?: level

    /**
     * [yoloMs]: tiền xử lý + suy luận (trung bình trượt), 0 = chưa đo; [procMs]: bám vết + pipeline một khung;
     * [cameraHz]: nhịp camera (ngân sách khung ở mức Cao); [thermal]: -1 = không rõ; [headroom]: dư nhiệt
     * (1,0 = ngưỡng hạ xung mạnh), null = không rõ.
     */
    fun update(now: Double, yoloMs: Double, procMs: Double, cameraHz: Double = 30.0, thermal: Int = -1, headroom: Double? = null): PerfLevel {
        forced?.let { return it }
        if (yoloMs <= 0) return level
        var target = capabilityLevel(yoloMs)
        var why = "YOLO ${yoloMs.roundToInt()} ms"
        // nhiệt: hạ trước khi máy tự hạ xung
        if (thermal >= PerfThresholds.THERMAL_SEVERE || (headroom != null && headroom >= 0.95)) {
            target = worse(target, PerfLevel.LOW)
            why = "máy rất nóng"
        } else if (thermal >= PerfThresholds.THERMAL_MODERATE || (headroom != null && headroom >= 0.85)) {
            target = worse(target, PerfLevel.MEDIUM)
            if (target == PerfLevel.MEDIUM) why = "máy nóng"
        }
        // luồng xử lý quá tải ở mức hiện tại
        val hz = if (level.trackHz > 0) level.trackHz else cameraHz
        if (hz > 0 && procMs > PROC_BUDGET_SHARE * 1000 / hz) {
            target = worse(target, level.down())
            why = "xử lý ${procMs.roundToInt()} ms/khung"
        }
        if (target.ordinal > level.ordinal) {
            goodSince = null
            if (now - lastDown >= DOWN_GAP_S) {
                level = level.down()
                lastDown = now
                reason = why
            }
            return level
        }
        // nâng mức: cần dư địa rõ ràng (ngưỡng thấp hơn 15 %) liên tục UP_HOLD_S giây, mỗi lần một mức
        val roomy = capabilityLevel(yoloMs, 0.85).ordinal < level.ordinal && target.ordinal < level.ordinal
        if (!roomy) {
            goodSince = null
            return level
        }
        val since = goodSince ?: now.also { goodSince = it }
        if (now - since >= UP_HOLD_S) {
            level = level.up()
            goodSince = null
            reason = why
        }
        return level
    }

    companion object {
        /** Thời gian điều kiện tốt phải kéo dài trước khi nâng một mức (tránh dao động lên xuống). */
        const val UP_HOLD_S = 10.0

        /** Khoảng cách tối thiểu giữa hai lần hạ mức (chờ số đo ổn định theo mức mới). */
        const val DOWN_GAP_S = 3.0

        /** Thời gian xử lý một khung được dùng tối đa ngần này phần ngân sách khung, quá thì hạ mức. */
        const val PROC_BUDGET_SHARE = 0.6
    }
}

/**
 * Khoảng nghỉ tối thiểu (giây) giữa hai lần gửi khung cho YOLO, theo mức rủi ro của kết quả gần nhất.
 *
 * - Khẩn (đang cảnh báo, TTC < 4 s, xe trước gần hơn 1,5 lần ngưỡng cảnh báo): chạy hết tốc lực.
 * - Đường trống (không có xe cùng làn, hoặc xe trước xa hơn 2 lần ngưỡng): 3 lần/giây là đủ - các xe đã
 *   thấy vẫn được bám vết ở mọi khung, nên xe làn bên chuyển làn vẫn được theo dõi.
 * - Còn lại: hết tốc lực, trừ khi máy nóng.
 */
fun yoloIntervalS(last: FrameResult?, thermal: Int = -1): Double {
    if (last == null) return 0.0
    val lead = last.lead
    val thr = last.thresholds
    val urgent = last.level.rank >= Risk.WARNING.rank ||
        (lead != null && ((lead.ttcS ?: 99.0) < 4 || lead.distanceM < 1.5 * thr.safeM))
    if (urgent) return 0.0
    if (lead == null || lead.distanceM > 2 * thr.safeM) return 1.0 / 3
    return if (thermal >= PerfThresholds.THERMAL_MODERATE) 0.15 else 0.0
}
