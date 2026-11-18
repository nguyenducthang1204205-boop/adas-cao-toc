package vn.adas.caotoc.core

import kotlin.math.abs
import kotlin.math.ceil
import kotlin.math.exp

/**
 * Tốc độ xe chủ đo từ vạch kẻ đường đứt (port của adas/distance/ego_speed.py, đầu vào là 2 vạch thẳng của
 * [LaneLines] thay cho làn đa thức của lane.py).
 *
 * Trên điện thoại tốc độ hiển thị vẫn lấy từ GPS; số đo này chỉ để so với GPS lúc chạy đều: chênh lệch chính là
 * sai số thang khoảng cách của hiệu chỉnh ([OnlineCalibrator] tự chỉnh tiêu cự theo nó). Vì đo theo hiệu chỉnh
 * đang dùng, đổi hiệu chỉnh (mapper mới) thì tạo bộ mới.
 *
 * Mỗi vạch: độ sáng dọc vạch theo mét (Y 5-26 m, quét ngang ±0,25 m lấy max - trung vị), chỉ giữ vạch đứt; so
 * với khung cách 0,08-0,4 s bằng tương quan chuẩn hóa -> quãng đường xe đi -> km/h, trung vị 1 s, làm mượt.
 */
class EgoSpeed(private val mapper: GroundPlaneMapper) {
    private val n = ceil((Y_MAX - Y_MIN) / DY).toInt()
    private val ys = DoubleArray(n) { Y_MIN + it * DY }
    private val lat = DoubleArray(N_LAT) { -0.25 + it * (0.5 / (N_LAT - 1)) }

    private val history = ArrayDeque<Pair<Double, Map<String, DoubleArray>>>()
    private val samples = ArrayDeque<Pair<Double, Double>>()
    /** Tốc độ đã làm mượt (km/h), chưa làm tròn. */
    var value: Double? = null
        private set
    private var shown: Double? = null
    private var lastT: Double? = null
    private var prevT = 0.0
    private var startT = 0.0

    fun reset() {
        history.clear()
        samples.clear()
        value = null
        shown = null
        lastT = null
    }

    /**
     * [gray]: ảnh xám, [scale]: pixel khung gốc trên 1 pixel ảnh xám, [obs]: 2 vạch làn (pixel khung gốc) hoặc null.
     * Trả về tốc độ (km/h, làm tròn có vùng chết 1 km/h) hoặc null khi chưa đo được.
     */
    fun update(gray: GrayImage, scale: Double, obs: LaneObservation?, t: Double): Double? {
        if (history.isNotEmpty() && t < history.last().first) reset() // nguồn mới / tua lại
        val profiles = if (obs != null) profiles(gray, scale, obs) else emptyMap()
        var ref: Pair<Double, Map<String, DoubleArray>>? = null
        for (i in history.indices.reversed()) {
            val gap = t - history[i].first
            if (gap >= REF_GAP_MIN_S && gap <= REF_GAP_MAX_S) { ref = history[i]; break }
        }
        history.addLast(t to profiles)
        if (history.size > HISTORY) history.removeFirst()

        if (ref != null && profiles.isNotEmpty()) {
            val (t0, p0) = ref
            val dt = t - t0
            var best: Pair<Double, Double>? = null
            for ((side, p) in profiles) {
                val pa = p0[side] ?: continue
                val (s, c) = shift(pa, p, dt)
                if (c >= MIN_CORR && (best == null || c > best.second)) best = s to c
            }
            if (best != null) {
                samples.addLast(t to best.first / dt * 3.6)
                lastT = t
            }
        }

        while (samples.isNotEmpty() && t - samples.first().first > WINDOW_S) samples.removeFirst()
        if (samples.size >= MIN_SAMPLES) {
            val med = median(samples.map { it.second })
            val v = value
            if (v == null) startT = t
            value = if (v == null || t - startT < WINDOW_S) med // khởi động: theo sát trung vị
            else v + (1.0 - exp(-(t - prevT) / SMOOTH_TAU_S)) * (med - v)
        }
        val lt = lastT
        if (lt == null || t - lt > STALE_S) value = null
        prevT = t
        val v = value
        val s = shown
        shown = when {
            v == null -> null
            s == null || abs(v - s) >= DISPLAY_STEP -> Math.rint(v)
            else -> s
        }
        return shown
    }

    /** Độ sáng (vạch - mặt đường) dọc mỗi vạch làn, chỉ giữ vạch đứt; NaN = ngoài ảnh. */
    private fun profiles(gray: GrayImage, scale: Double, obs: LaneObservation): Map<String, DoubleArray> {
        val out = LinkedHashMap<String, DoubleArray>()
        for ((side, line) in listOf("l" to obs.left, "r" to obs.right)) {
            // vạch trên ảnh -> đường thẳng trên mặt đường X = c0 + c1·Y
            val g0 = mapper.imageToGround(line.first.x, line.first.y) ?: continue
            val g1 = mapper.imageToGround(line.second.x, line.second.y) ?: continue
            if (abs(g1.y - g0.y) < 1e-6) continue
            val c1 = (g1.x - g0.x) / (g1.y - g0.y)
            val c0 = g0.x - c1 * g0.y
            val p = DoubleArray(n)
            val strip = DoubleArray(N_LAT)
            var nValid = 0
            var maxValid = Double.NEGATIVE_INFINITY
            for (i in 0 until n) {
                val x = c0 + c1 * ys[i]
                var inside = true
                for (k in 0 until N_LAT) {
                    val q = mapper.groundToImage(x + lat[k], ys[i])
                    val u = q.x / scale; val v = q.y / scale
                    if (u < 0 || u >= gray.width - 1 || v < 0 || v >= gray.height - 1) { inside = false; break }
                    strip[k] = gray.at(u, v)
                }
                if (!inside) { p[i] = Double.NaN; continue }
                val mx = strip.max()
                p[i] = mx - strip.sorted()[N_LAT / 2]
                nValid++
                if (p[i] > maxValid) maxValid = p[i]
            }
            if (nValid < n / 3 || maxValid < MIN_CONTRAST) continue
            var on = 0
            var switches = 0
            var prevOn: Boolean? = null
            for (x in p) {
                if (x.isNaN()) continue
                val o = x > 0.5 * maxValid
                if (o) on++
                if (prevOn != null && o != prevOn) switches++
                prevOn = o
            }
            val share = on.toDouble() / nValid
            if (share >= 0.05 && share <= 0.75 && switches >= 2) out[side] = p // vạch đứt: có đoạn sơn và khoảng hở
        }
        return out
    }

    /** s (m) sao cho pb(Y) ≈ pa(Y + s); trả về (s, độ tương quan). */
    private fun shift(pa: DoubleArray, pb: DoubleArray, dt: Double): Pair<Double, Double> {
        var lo = 0.0
        var hi = V_MAX_KMH / 3.6 * dt
        value?.let { v -> // bám quanh tốc độ đã đo để tránh nhảy sang vạch đứt kế tiếp
            val pred = v / 3.6 * dt
            lo = maxOf(0.0, 0.6 * pred - 0.3); hi = minOf(hi, 1.4 * pred + 0.3)
        }
        val kLo = (lo / DY).toInt()
        val kHi = minOf((hi / DY).toInt() + 1, n - n / 3)
        if (kHi - kLo < 3) return 0.0 to -1.0
        val cs = DoubleArray(kHi - kLo) { -1.0 }
        for (i in cs.indices) {
            val k = kLo + i
            var cnt = 0; var sa = 0.0; var sb = 0.0
            for (j in 0 until n - k) {
                val a = pa[k + j]; val b = pb[j]
                if (a.isNaN() || b.isNaN()) continue
                cnt++; sa += a; sb += b
            }
            if (cnt < n / 3) continue
            val ma = sa / cnt; val mb = sb / cnt
            var vaa = 0.0; var vbb = 0.0; var vab = 0.0
            for (j in 0 until n - k) {
                val a = pa[k + j]; val b = pb[j]
                if (a.isNaN() || b.isNaN()) continue
                vaa += (a - ma) * (a - ma); vbb += (b - mb) * (b - mb); vab += (a - ma) * (b - mb)
            }
            val sda = Math.sqrt(vaa / cnt); val sdb = Math.sqrt(vbb / cnt)
            if (sda > 1e-6 && sdb > 1e-6) cs[i] = (vab / cnt) / (sda * sdb)
        }
        var i = 0
        for (j in cs.indices) if (cs[j] > cs[i]) i = j
        var off = 0.0
        if (i > 0 && i < cs.size - 1 && cs[i - 1] > -1 && cs[i + 1] > -1) {
            val d = cs[i - 1] - 2 * cs[i] + cs[i + 1]
            if (d < 0) off = 0.5 * (cs[i - 1] - cs[i + 1]) / d
        }
        return (kLo + i + off) * DY to cs[i]
    }

    companion object {
        const val DY = 0.05                 // bước lấy mẫu dọc vạch (m)
        const val Y_MIN = 5.0
        const val Y_MAX = 26.0
        const val N_LAT = 11                // quét ngang ±0,25 m quanh vạch
        const val MIN_CONTRAST = 20.0
        const val REF_GAP_MIN_S = 0.08
        const val REF_GAP_MAX_S = 0.4
        const val MIN_CORR = 0.8
        const val V_MAX_KMH = 160.0
        const val WINDOW_S = 1.0
        const val MIN_SAMPLES = 3
        const val SMOOTH_TAU_S = 1.0
        const val DISPLAY_STEP = 1.0
        const val STALE_S = 2.0
        private const val HISTORY = 20
    }
}
