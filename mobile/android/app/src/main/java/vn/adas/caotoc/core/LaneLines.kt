package vn.adas.caotoc.core

import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt

/**
 * Dò 2 vạch làn của xe chủ trên ảnh xám - đầu vào cho tự hoàn thiện căn chỉnh trên điện thoại ([OnlineCalibrator]).
 * Bản desktop dùng bộ dò làn đầy đủ trên ảnh nhìn từ trên xuống (adas/distance/lane.py); ở đây chỉ cần vị trí 2
 * vạch trên ảnh nên làm gọn, vài chục phép đọc pixel mỗi hàng:
 *  1. Quét các hàng ảnh cách nhau 2 pixel trong đoạn 6-30 m phía trước (theo hiệu chỉnh đang dùng) - vạch đứt chỉ
 *     phủ ~1/3 số hàng nên phải quét dày.
 *  2. Mỗi hàng, mỗi bên: tìm dải sáng hẹp (vạch sơn: sáng hơn cả 2 bên cách ~0,3 m) trong cửa sổ quanh vị trí dự
 *     kiến - vạch đã thấy ở lần trước, hoặc ±1,875 m theo hiệu chỉnh.
 *  3. Khớp đường thẳng u = a + b·v (bỏ điểm lạc), kiểm tra độ cong (đường cong: chỉ dùng cho hàng điểm tụ), bề
 *     rộng làn hợp lý và làn chứa xe chủ (giống _plausible của lane.py).
 */
class LaneLines {
    private var prev: LaneObservation? = null
    private var misses = 0

    fun reset() {
        prev = null
        misses = 0
    }

    /** [scale]: pixel khung gốc trên 1 pixel ảnh xám. Kết quả theo pixel khung gốc; null = không thấy đủ 2 vạch. */
    fun find(gray: GrayImage, scale: Double, mapper: GroundPlaneMapper): LaneObservation? {
        val obs = detect(gray, scale, mapper)
        if (obs != null) {
            prev = obs
            misses = 0
        } else if (++misses > MAX_MISSES) {
            prev = null
        }
        return obs
    }

    private class Line(val a: Double, val b: Double, val straight: Boolean) {
        fun u(v: Double) = a + b * v
    }

    private fun detect(gray: GrayImage, scale: Double, mapper: GroundPlaneMapper): LaneObservation? {
        val p = prev
        val rows = mutableListOf<Pair<Double, Double>>() // (hàng ảnh xám, Y mét)
        val vTop = max(mapper.groundToImage(0.0, ROW_Y_MAX).y / scale, 1.0)
        val vBottom = min(mapper.groundToImage(0.0, ROW_Y_MIN).y / scale, gray.height - 2.0)
        var row = vTop
        while (row <= vBottom) {
            mapper.imageToGround(gray.width / 2.0 * scale, row * scale)?.let { rows += row to it.y }
            row += ROW_STEP_PX
        }
        if (rows.size < 2 * MIN_POINTS) return null
        val lines = listOf(-1, 1).map { side ->
            val pts = mutableListOf<Vec2>()
            for ((v, y) in rows) {
                val centre = mapper.groundToImage(0.0, y).x / scale
                val pxm = abs(mapper.groundToImage(1.0, y).x / scale - centre) // pixel ảnh xám trên 1 m ngang
                if (pxm < 1.5) continue
                val expect = p?.let { lineU(if (side < 0) it.left else it.right, v * scale) / scale }
                    ?: (mapper.groundToImage(side * LANE_WIDTH_M / 2, y).x / scale)
                val half = (if (p != null) 0.45 else 1.3) * pxm
                var lo = expect - half
                var hi = expect + half
                if (side < 0) hi = min(hi, centre - 0.3 * pxm) else lo = max(lo, centre + 0.3 * pxm)
                ridge(gray, v, lo, hi, max(2, (0.3 * pxm).roundToInt()))?.let { pts += Vec2(it, v) }
            }
            fit(pts) ?: return null
        }
        val (l, r) = lines
        // bề rộng làn hợp lý và làn chứa xe chủ (X = 0 tại đầu xe)
        val vW = mapper.groundToImage(0.0, Y_WIDTH).y
        val gl = mapper.imageToGround(l.u(vW / scale) * scale, vW) ?: return null
        val gr = mapper.imageToGround(r.u(vW / scale) * scale, vW) ?: return null
        val width = gr.x - gl.x
        if (width !in MIN_WIDTH_M..MAX_WIDTH_M || gl.x > EGO_MARGIN_M || gr.x < -EGO_MARGIN_M) return null
        val vN = mapper.groundToImage(0.0, Y_NEAR).y
        val vF = mapper.groundToImage(0.0, Y_FAR).y
        fun ends(line: Line) = Vec2(line.u(vN / scale) * scale, vN) to Vec2(line.u(vF / scale) * scale, vF)
        return LaneObservation(ends(l), ends(r), l.straight && r.straight)
    }

    /** Tâm dải sáng hẹp mạnh nhất trong [lo, hi] trên hàng [v] (dưới ngưỡng: null), nội suy parabol. */
    private fun ridge(gray: GrayImage, v: Double, lo: Double, hi: Double, k: Int): Double? {
        val a = max(lo.roundToInt(), k + 1)
        val b = min(hi.roundToInt(), gray.width - k - 2)
        if (b - a < 2) return null
        fun px(u: Int) = (gray.at(u - 1.0, v) + 2 * gray.at(u.toDouble(), v) + gray.at(u + 1.0, v)) / 4
        fun resp(u: Int) = px(u) - max(px(u - k), px(u + k))
        var best = a
        var bestR = Double.NEGATIVE_INFINITY
        for (u in a..b) {
            val r = resp(u)
            if (r > bestR) { bestR = r; best = u }
        }
        if (bestR < MIN_CONTRAST) return null
        val r0 = resp(best - 1); val r2 = resp(best + 1)
        val den = r0 - 2 * bestR + r2
        return best + if (den < -1e-9) ((0.5 * (r0 - r2) / den).coerceIn(-0.5, 0.5)) else 0.0
    }

    /** Đường thẳng u = a + b·v qua các điểm (bỏ điểm lạc 1 lần); đủ điểm thì xét độ cong bằng parabol. */
    private fun fit(all: List<Vec2>): Line? {
        if (all.size < MIN_POINTS) return null
        var pts = all
        var ab = linear(pts) ?: return null
        val res = pts.map { abs(it.x - (ab.first + ab.second * it.y)) }
        val tol = max(1.5, 2.5 * median(res))
        pts = pts.filterIndexed { i, _ -> res[i] <= tol }
        if (pts.size < MIN_POINTS) return null
        ab = linear(pts) ?: return null
        val span = pts.maxOf { it.y } - pts.minOf { it.y }
        if (span < 8) return null
        val c = quadratic(pts)
        val sagitta = if (c == null) 0.0 else abs(c) * span * span / 4
        return Line(ab.first, ab.second, sagitta < MAX_SAGITTA_PX)
    }

    private fun linear(pts: List<Vec2>): Pair<Double, Double>? {
        val n = pts.size.toDouble()
        val mv = pts.sumOf { it.y } / n; val mu = pts.sumOf { it.x } / n
        val svv = pts.sumOf { (it.y - mv) * (it.y - mv) }
        if (svv < 1e-9) return null
        val b = pts.sumOf { (it.y - mv) * (it.x - mu) } / svv
        return (mu - b * mv) to b
    }

    /** Hệ số bậc 2 của u = c0 + c1·v + c2·v² (bình phương tối thiểu, v đã dời tâm); null nếu ít điểm. */
    private fun quadratic(pts: List<Vec2>): Double? {
        if (pts.size < 6) return null
        val mv = pts.sumOf { it.y } / pts.size
        val s = DoubleArray(5); val t = DoubleArray(3)
        for (p in pts) {
            val x = p.y - mv
            var xp = 1.0
            for (i in 0..4) { s[i] += xp; if (i < 3) t[i] += xp * p.x; xp *= x }
        }
        val m = arrayOf(doubleArrayOf(s[0], s[1], s[2]), doubleArrayOf(s[1], s[2], s[3]), doubleArrayOf(s[2], s[3], s[4]))
        val det = det3(m)
        if (abs(det) < 1e-9) return null
        val m2 = arrayOf(doubleArrayOf(s[0], s[1], t[0]), doubleArrayOf(s[1], s[2], t[1]), doubleArrayOf(s[2], s[3], t[2]))
        return det3(m2) / det
    }

    private fun det3(m: Array<DoubleArray>) =
        m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0]) +
            m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])

    private fun lineU(line: Pair<Vec2, Vec2>, v: Double): Double {
        val (p, q) = line
        return if (abs(q.y - p.y) < 1e-9) p.x else p.x + (v - p.y) * (q.x - p.x) / (q.y - p.y)
    }

    companion object {
        private const val ROW_Y_MIN = 6.0
        private const val ROW_Y_MAX = 30.0
        private const val ROW_STEP_PX = 2.0
        private const val MIN_CONTRAST = 12.0   // vạch sáng hơn mặt đường 2 bên ít nhất ngần này mức xám
        private const val MIN_POINTS = 5
        private const val MAX_SAGITTA_PX = 1.0  // độ võng của parabol so với dây cung: lớn hơn -> đường cong
        private const val MIN_WIDTH_M = 2.2
        private const val MAX_WIDTH_M = 5.2
        private const val EGO_MARGIN_M = 0.4
        private const val MAX_MISSES = 5
    }
}
