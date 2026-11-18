package vn.adas.caotoc.core

import kotlin.math.abs
import kotlin.math.atan

/**
 * Tự hoàn thiện căn chỉnh camera khi chạy (port của adas/distance/online_calib.py, trừ phần chỉnh tiêu cự theo
 * tốc độ nhập tay của video desktop).
 *
 * Mỗi lần thấy đủ 2 vạch làn ([LaneObservation], từ [LaneLines]) là một mẫu điểm tụ. Hàng điểm tụ (chân trời)
 * lấy từ mọi mẫu, cột chỉ từ mẫu trên đoạn thẳng. Đủ mẫu thì: căn chỉnh theo tư thế -> đặt điểm tụ mới, chiều
 * cao chưa đo thì chỉnh theo làn 3,75 m, trả [CalibStatus.newCalib] để lưu; căn chỉnh 4 điểm -> chỉ kiểm tra.
 * Sau đó theo dõi camera bị xê dịch, và khi đã chạy đều đủ lâu thì chỉnh thang khoảng cách (tiêu cự) cho tốc độ
 * đo từ vạch kẻ ([EgoSpeed]) khớp GPS - người dùng không phải nhập gì.
 */

const val Y_NEAR = 6.0
const val Y_FAR = 24.0
const val Y_WIDTH = 10.0

/** 2 vạch làn của xe chủ trên ảnh (2 điểm pixel mỗi vạch) + đoạn đường thẳng hay không. */
data class LaneObservation(val left: Pair<Vec2, Vec2>, val right: Pair<Vec2, Vec2>, val straight: Boolean)

/** [state]: collecting | done | drift. [newCalib]: chỉ có ở lần vừa hoàn tất (cần áp dụng + lưu). */
data class CalibStatus(
    val state: String,
    val progress: Int,
    val message: String,
    val ok: Boolean? = null,
    val newCalib: CalibrationConfig? = null,
)

private class CalibSample(val t: Double, val vp: Vec2, val left: Pair<Vec2, Vec2>, val right: Pair<Vec2, Vec2>, val straight: Boolean)

private fun lineIntersect(a: Pair<Vec2, Vec2>, b: Pair<Vec2, Vec2>): Vec2? {
    val la = V3(a.first.x, a.first.y, 1.0) cross V3(a.second.x, a.second.y, 1.0)
    val lb = V3(b.first.x, b.first.y, 1.0) cross V3(b.second.x, b.second.y, 1.0)
    val p = la cross lb
    if (abs(p.z) < 1e-9) return null
    return Vec2(p.x / p.z, p.y / p.z)
}

/** Trung vị như numpy (số phần tử chẵn: trung bình 2 phần tử giữa). */
fun median(values: List<Double>): Double {
    val s = values.sorted()
    val n = s.size
    return if (n % 2 == 1) s[n / 2] else (s[n / 2 - 1] + s[n / 2]) / 2
}

private fun spreadDeg(values: List<Double>, f: Double): Double {
    val m = median(values)
    val mad = median(values.map { abs(it - m) }) * 1.4826
    return Math.toDegrees(atan(mad / f))
}

/** Trung vị bề rộng làn (m) tại [Y_WIDTH] nếu dùng hiệu chỉnh [calib] cho các vạch đã thấy trên ảnh. */
private fun laneWidthUnder(calib: CalibrationConfig, w: Double, h: Double, samples: List<CalibSample>): Double? {
    val mapper = GroundPlaneMapper.tryCreate(calib, w, h) ?: return null
    val widths = samples.mapNotNull { s ->
        val xs = listOf(s.left, s.right).map { line ->
            val g0 = mapper.imageToGround(line.first.x, line.first.y) ?: return@mapNotNull null
            val g1 = mapper.imageToGround(line.second.x, line.second.y) ?: return@mapNotNull null
            if (abs(g1.y - g0.y) < 1e-6) return@mapNotNull null
            val k = (Y_WIDTH - g0.y) / (g1.y - g0.y)
            g0.x + k * (g1.x - g0.x)
        }
        xs[1] - xs[0]
    }
    return if (widths.isEmpty()) null else median(widths)
}

fun widthVerdict(width: Double): Pair<Boolean, String> {
    val err = abs(width - LANE_WIDTH_M)
    return when {
        err <= 0.25 -> true to "đạt"
        err <= 0.5 -> true to "hơi lệch"
        else -> false to "lệch nhiều, kiểm tra lại chiều cao camera"
    }
}

class OnlineCalibrator(val w: Double, val h: Double, private val samplesNeeded: Int = 90) {
    private val driftWindow = samplesNeeded
    private var samples = mutableListOf<CalibSample>()
    private val recent = ArrayDeque<CalibSample>()
    private var result: CalibStatus? = null
    private var pending: CalibrationConfig? = null
    private var drifted = false
    private var checkOnly = false
    // thang khoảng cách theo GPS (xem scaleSample)
    private val gpsHist = ArrayDeque<Pair<Double, Double>>()
    private val scaleObs = ArrayDeque<Pair<Double, Double>>()
    private var scaleRows: DoubleArray? = null // (hàng gần, hàng xa, cột) cố định từ lần đo đầu
    private var scaleKey: List<Any>? = null
    private var scaleVal: Double? = null
    private var scaleChanged = false
    private var scaleT0 = -1e9
    private var gpsChecked = false
    private var gpsFitT = -1e9
    private var gpsCheckT = -1e9

    fun reset() {
        samples = mutableListOf()
        recent.clear()
        result = null
        pending = null
        drifted = false
        checkOnly = false
        gpsHist.clear()
        scaleObs.clear()
        scaleRows = null
        scaleKey = null
        scaleVal = null
        scaleChanged = false
        scaleT0 = -1e9
        gpsChecked = false
        gpsFitT = -1e9
        gpsCheckT = -1e9
    }

    /** Hiệu chỉnh vừa đổi: do chính bộ này đề xuất -> theo dõi tiếp; do người dùng -> đo lại từ đầu. */
    fun calibrationChanged(calib: CalibrationConfig) {
        if (pending != null && calib == pending) {
            pending = null
            recent.clear()
            return
        }
        reset()
    }

    /**
     * [videoKmh]: tốc độ đo từ vạch kẻ đường theo hiệu chỉnh đang dùng ([EgoSpeed]), null = chưa đo được.
     * [gpsKmh]: tốc độ GPS, null = không có. Lọc đứng yên / chạy chậm theo GPS nếu có, không thì theo [videoKmh].
     */
    fun update(
        obs: LaneObservation?, mapper: GroundPlaneMapper, calib: CalibrationConfig, t: Double,
        videoKmh: Double?, gpsKmh: Double? = null,
    ): CalibStatus {
        scaleSample(calib, t, videoKmh, gpsKmh)
        val sample = sample(obs, t, gpsKmh ?: videoKmh)
        if (result != null) return monitor(sample, mapper, calib, t)
        checkOnly = !calib.pose.active
        if (sample != null) samples.add(sample)
        val n = samples.size
        val span = if (n > 0) samples.last().t - samples.first().t else 0.0
        var progress = (minOf(n.toDouble() / samplesNeeded, span / MIN_SPAN_S, 0.99) * 100).toInt()
        if (n >= samplesNeeded && span >= MIN_SPAN_S) {
            finish(mapper, calib)?.let { return it }
            progress = (samples.size.toDouble() / samplesNeeded * 100).toInt()
        }
        return collecting(progress)
    }

    private fun collecting(progress: Int): CalibStatus {
        val msg = when {
            checkOnly -> "Đang kiểm tra căn chỉnh camera"
            drifted -> "Camera bị xê dịch - đang hiệu chỉnh lại"
            else -> "Đang tự hoàn thiện căn chỉnh camera"
        }
        return CalibStatus("collecting", progress, "$msg (cần thấy rõ 2 vạch làn)")
    }

    private fun sample(obs: LaneObservation?, t: Double, speed: Double?): CalibSample? {
        if (obs == null || (speed != null && speed < MIN_SPEED_KMH)) return null
        val vp = lineIntersect(obs.left, obs.right) ?: return null
        if (!(vp.x in 0.0..w && vp.y in 0.1 * h..0.9 * h)) return null
        return CalibSample(t, vp, obs.left, obs.right, obs.straight)
    }

    private fun finish(mapper: GroundPlaneMapper, calib: CalibrationConfig): CalibStatus? {
        val f = if (calib.pose.active) focalPx(calib.pose, w, h, calib.cameraVfovDeg)
        else mapper.focalPx ?: focalPx(calib.pose, w, h, calib.cameraVfovDeg)
        val straight = samples.filter { it.straight }
        val useU = straight.size >= MIN_STRAIGHT * samples.size
        val spreadU = if (useU) spreadDeg(straight.map { it.vp.x }, f) else 0.0
        if (spreadU > MAX_SPREAD_U_DEG || spreadDeg(samples.map { it.vp.y }, f) > MAX_SPREAD_V_DEG) {
            dropOlderHalf() // xóc / nhận nhầm vạch: bỏ nửa cũ, đo thêm
            return null
        }
        val v = median(samples.map { it.vp.y })
        val u = if (useU) median(straight.map { it.vp.x }) else calib.pose.vpX * w

        if (checkOnly) {
            val width = laneWidthUnder(calib, w, h, samples) ?: run { dropOlderHalf(); return null }
            val (ok, verdict) = widthVerdict(width)
            samples = mutableListOf()
            return CalibStatus("done", 100, "Kiểm tra căn chỉnh: làn đo được ${vn(width, 2)} m - $verdict", ok).also { result = it }
        }

        var pose = calib.pose.copy(vpX = u / w, vpY = v / h, refined = true)
        var new = calibFromPose(pose, w, h, calib)
        val width = laneWidthUnder(new, w, h, samples) ?: run { dropOlderHalf(); return null }
        val ok: Boolean
        val msg: String
        if (pose.heightMeasured) {
            val (good, verdict) = widthVerdict(width)
            ok = good
            msg = "Căn chỉnh xong: làn đo được ${vn(width, 2)} m - $verdict"
        } else {
            // bề rộng mặt đường tỉ lệ thuận với chiều cao camera (cùng các tia nhìn)
            val oldH = pose.heightM
            pose = pose.copy(heightM = (pose.heightM * LANE_WIDTH_M / width).coerceIn(0.6, 4.0))
            // thang dọc (tỉ lệ với f·h) đã khớp tốc độ thật: giữ nguyên khi đổi chiều cao
            if (pose.focalSource == "gps" || pose.focalSource == "speed") pose = pose.copy(focalW = pose.focalW * oldH / pose.heightM)
            new = calibFromPose(pose, w, h, calib)
            ok = pose.heightM / calib.pose.heightM in 0.8..1.25
            msg = "Căn chỉnh xong: camera cao khoảng ${vn(pose.heightM, 2)} m (theo làn ${vn(LANE_WIDTH_M, 2)} m)"
        }
        val target = gpsTarget()
        val extra = if (target != null) {
            new = fitScale(new, target, "gps")
            pose = new.pose
            gpsChecked = true
            gpsFitT = samples.last().t
            " · thang khoảng cách theo GPS"
        } else if (pose.focalSource == "fov") " · chưa có thông số ống kính: sẽ tự chỉnh theo GPS khi chạy đều" else ""
        if (calib.pose.refined && !drifted && samePose(calib.pose, pose)) {
            // lần chạy trước đã tự hoàn thiện, đo lại vẫn vậy: chỉ báo kết quả kiểm tra, không lưu thêm bản trùng
            val checked = laneWidthUnder(calib, w, h, samples) ?: width
            val (good, verdict) = widthVerdict(checked)
            samples = mutableListOf()
            return CalibStatus("done", 100, "Kiểm tra căn chỉnh: làn đo được ${vn(checked, 2)} m - $verdict", good)
                .also { result = it }
        }
        pending = new
        drifted = false
        samples = mutableListOf()
        return CalibStatus("done", 100, msg + extra, ok, new).also { result = it }
    }

    private fun samePose(a: CameraPose, b: CameraPose): Boolean {
        val f = a.focalW * w
        if (f <= 0 || a.heightM <= 0) return false
        val du = Math.toDegrees(atan(abs(a.vpX - b.vpX) * w / f))
        val dv = Math.toDegrees(atan(abs(a.vpY - b.vpY) * h / f))
        return du < SAME_DEG && dv < SAME_DEG && abs(b.heightM / a.heightM - 1) < SAME_REL && abs(b.focalW / a.focalW - 1) < 0.01
    }

    private fun dropOlderHalf() {
        samples = samples.subList(samples.size / 2, samples.size).toMutableList()
    }

    // ------------------------------------------------------------------
    // Thang khoảng cách theo GPS
    // ------------------------------------------------------------------

    /** Quãng đường (m) giữa 2 hàng ảnh cố định theo hiệu chỉnh [calib] (tốc độ đo từ video tỉ lệ với nó). */
    private fun scaleOf(calib: CalibrationConfig): Double? {
        val rows = scaleRows ?: run {
            val m = GroundPlaneMapper.tryCreate(calib, w, h) ?: return null
            val a = m.groundToImage(0.0, 8.0); val b = m.groundToImage(0.0, 22.0)
            doubleArrayOf(a.y, b.y, a.x).also { scaleRows = it }
        }
        val key = listOf(calib.imagePoints, calib.rectWidthM, calib.rectLengthM, calib.nearDistanceM)
        if (key != scaleKey) {
            scaleKey = key
            scaleVal = longitudinalScale(calib, w, h, rows[0], rows[1], rows[2])
            scaleChanged = true
        }
        return scaleVal
    }

    /**
     * Lúc chạy đều: quãng đường thật giữa 2 hàng ảnh cố định = thang hiệu chỉnh đang dùng × GPS / tốc độ video.
     * Không phụ thuộc hiệu chỉnh lúc đo nên gom được qua các lần tự hoàn thiện; GPS trễ ~1 s không ảnh hưởng vì
     * chỉ lấy lúc tốc độ gần như không đổi.
     */
    private fun scaleSample(calib: CalibrationConfig, t: Double, speed: Double?, gps: Double?) {
        if (gps == null) { gpsHist.clear(); return }
        gpsHist.addLast(t to gps)
        while (gpsHist.size > 1 && t - gpsHist[1].first >= GPS_STEADY_S) gpsHist.removeFirst()
        if (!calib.pose.active || drifted || speed == null || speed <= 0 || gps < MIN_SPEED_KMH ||
            t - gpsHist.first().first < GPS_STEADY_S
        ) return
        val s = scaleOf(calib)
        if (scaleChanged) { // hiệu chỉnh vừa đổi: tốc độ video còn làm mượt theo thang cũ vài giây
            scaleChanged = false
            scaleT0 = t
        }
        val spread = gpsHist.maxOf { it.second } - gpsHist.minOf { it.second }
        if (s != null && spread <= GPS_STEADY_KMH && t - scaleT0 >= GPS_SETTLE_S) {
            scaleObs.addLast(t to s * gps / speed)
            if (scaleObs.size > GPS_KEEP) scaleObs.removeFirst()
        }
    }

    /** Quãng đường thật giữa 2 hàng cố định (trung vị) khi đã gom đủ và ổn định; chưa đủ: null. */
    private fun gpsTarget(): Double? {
        if (scaleObs.size < GPS_MIN_PAIRS || scaleObs.last().first - scaleObs.first().first < GPS_MIN_SPAN_S) return null
        val s = scaleObs.map { it.second }
        val med = median(s)
        val spread = median(s.map { abs(it - med) }) * 1.4826 / med
        return if (spread <= GPS_MAX_SPREAD) med else null
    }

    /** Chỉnh tiêu cự cho quãng đường giữa 2 hàng cố định bằng [target] (m). */
    private fun fitScale(start: CalibrationConfig, target: Double, source: String): CalibrationConfig {
        val rows = scaleRows ?: return start
        var new = start
        var pose = start.pose
        repeat(3) {
            val s = longitudinalScale(new, w, h, rows[0], rows[1], rows[2]) ?: return new
            pose = pose.copy(focalW = (pose.focalW * target / s).coerceIn(0.2, 3.0))
            new = calibFromPose(pose, w, h, new)
        }
        return new.copy(pose = new.pose.copy(focalSource = source))
    }

    /** Đang theo dõi: đủ dữ liệu GPS thì chỉnh thang khoảng cách (hoặc báo đã khớp). */
    private fun gpsCheck(calib: CalibrationConfig, t: Double): CalibStatus? {
        if (!calib.pose.active || t - gpsCheckT < 1.0) return null
        gpsCheckT = t
        val refit = calib.pose.focalSource == "gps"
        if (refit && t - gpsFitT < GPS_REFIT_S) return null
        val target = gpsTarget() ?: return null
        val cur = scaleOf(calib) ?: return null
        val err = cur / target - 1
        if (abs(err) < (if (refit || gpsChecked) GPS_REFIT_REL else GPS_FIT_REL)) {
            if (gpsChecked) return null
            gpsChecked = true
            return CalibStatus("done", 100, "Thang khoảng cách khớp GPS (lệch ${vn(err * 100, 1)} %)", true)
                .also { result = it }
        }
        val new = fitScale(calibFromPose(calib.pose, w, h, calib), target, "gps")
        gpsChecked = true
        gpsFitT = t
        pending = new
        return CalibStatus(
            "done", 100, "Đã chỉnh thang khoảng cách theo GPS (tốc độ đo từ vạch kẻ lệch ${vn(err * 100, 1)} %)", true, new,
        ).also { result = it }
    }

    // ------------------------------------------------------------------

    private fun monitor(sample: CalibSample?, mapper: GroundPlaneMapper, calib: CalibrationConfig, t: Double): CalibStatus {
        if (pending == null) gpsCheck(calib, t)?.let { return it }
        val r = result!!
        val status = CalibStatus(r.state, 100, r.message, r.ok)
        if (sample == null || pending != null) return status
        recent.addLast(sample)
        if (recent.size > driftWindow) recent.removeFirst()
        if (recent.size < driftWindow) return status
        val vy = DoubleArray(3) { mapper.hInv.at(it, 1) } // điểm tụ của hướng Y (phía trước) theo hiệu chỉnh đang dùng
        if (abs(vy[2]) < 1e-12) return status
        val f = mapper.focalPx ?: focalPx(calib.pose, w, h, calib.cameraVfovDeg)
        val dv = abs(median(recent.map { it.vp.y }) - vy[1] / vy[2])
        val straight = recent.filter { it.straight }.map { it.vp.x }
        val du = if (straight.size >= MIN_STRAIGHT * recent.size) abs(median(straight) - vy[0] / vy[2]) else 0.0
        if (Math.toDegrees(atan(du / f)) <= DRIFT_U_DEG && Math.toDegrees(atan(dv / f)) <= DRIFT_V_DEG) return status
        recent.clear()
        if (calib.pose.active) { // tư thế: đo lại từ đầu rồi tự áp dụng
            result = null
            samples = mutableListOf()
            drifted = true
            scaleObs.clear() // quãng đường thật giữa 2 hàng ảnh đổi theo tư thế camera: gom lại
            scaleRows = null
            scaleKey = null
            return collecting(0)
        }
        return CalibStatus("drift", 100, "Camera có vẻ đã bị xê dịch so với lúc căn chỉnh - nên căn chỉnh lại", false)
            .also { result = it }
    }

    companion object {
        const val MIN_SPAN_S = 5.0
        const val MIN_SPEED_KMH = 30.0
        const val MIN_STRAIGHT = 0.2
        const val MAX_SPREAD_U_DEG = 1.5
        const val MAX_SPREAD_V_DEG = 1.0
        const val DRIFT_U_DEG = 1.5
        const val DRIFT_V_DEG = 1.0
        /** Đo lại lệch ít hơn (góc điểm tụ, chiều cao): coi như căn chỉnh không đổi. */
        const val SAME_DEG = 0.25
        const val SAME_REL = 0.02
        // thang khoảng cách theo GPS: so tốc độ đo từ vạch kẻ với GPS lúc chạy đều, gom đủ lâu rồi lấy trung vị
        const val GPS_STEADY_S = 2.0      // GPS đổi ít hơn GPS_STEADY_KMH trong ngần này giây: chạy đều (GPS trễ ~1 s)
        const val GPS_STEADY_KMH = 2.0
        const val GPS_SETTLE_S = 2.0      // sau khi hiệu chỉnh đổi: chờ tốc độ video (làm mượt ~1 s) theo thang mới
        const val GPS_MIN_PAIRS = 200
        const val GPS_MIN_SPAN_S = 20.0
        const val GPS_MAX_SPREAD = 0.06   // độ phân tán (MAD tương đối) tối đa của tỉ lệ GPS / video
        const val GPS_KEEP = 3000
        const val GPS_FIT_REL = 0.015     // lần đầu: lệch ít hơn -> chỉ báo "khớp GPS"
        const val GPS_REFIT_REL = 0.03    // đã chỉnh theo GPS: chỉ chỉnh lại khi lệch hơn và đã qua GPS_REFIT_S
        const val GPS_REFIT_S = 30.0
    }
}
