package vn.adas.caotoc.core

import kotlin.math.abs
import kotlin.math.sqrt

/**
 * IPM - biến đổi phối cảnh ngược (port của adas/distance/ipm.py).
 *
 * Giả thiết mặt đường phẳng. H ánh xạ pixel (u, v) -> mét (X lệch ngang, Y khoảng cách từ đầu xe),
 * dựng từ 4 điểm ảnh của một hình chữ nhật W x L mét trên mặt đường.
 */
class GroundPlaneMapper(val calib: CalibrationConfig, val frameW: Double, val frameH: Double) {
    val h: Mat3
    val hInv: Mat3
    private val validSign: Double
    val horizonY: Double?

    /** Tiêu cự phân rã từ H (null nếu suy biến). */
    val focalPx: Double?

    init {
        val src = calib.imagePoints.map { Vec2(it.x * frameW, it.y * frameH) }
        val w = calib.rectWidthM; val l = calib.rectLengthM; val d0 = calib.nearDistanceM
        val dst = listOf(Vec2(-w / 2, d0), Vec2(w / 2, d0), Vec2(w / 2, d0 + l), Vec2(-w / 2, d0 + l))
        h = Mat3.perspective(src, dst)
        hInv = h.inverse()
        // Dấu thành phần đồng nhất tại một điểm chắc chắn trên mặt đường; dấu ngược = trên chân trời
        val ref = h.applyHomog(frameW / 2, src[0].y)
        validSign = if (ref[2] >= 0) 1.0 else -1.0
        val h31 = h.at(2, 0); val h32 = h.at(2, 1); val h33 = h.at(2, 2)
        horizonY = if (abs(h32) > 1e-12) -(h31 * (frameW / 2) + h33) / h32 else null
        focalPx = focal()
    }

    /** Tiêu cự từ phân rã G = H⁻¹ ∝ K·[r1 r2 t] (Zhang), tâm ảnh ở giữa khung (giống _decompose). */
    private fun focal(): Double? {
        val cx = frameW / 2; val cy = frameH / 2
        val s = hInv.at(2, 2)
        val g = Array(3) { r -> DoubleArray(3) { c -> hInv.at(r, c) / s } }
        for (c in 0 until 3) {
            g[0][c] -= cx * g[2][c]
            g[1][c] -= cy * g[2][c]
        }
        val g1 = doubleArrayOf(g[0][0], g[1][0], g[2][0])
        val g2 = doubleArrayOf(g[0][1], g[1][1], g[2][1])
        var f2 = -1.0
        val den = g2[2] * g2[2] - g1[2] * g1[2]
        if (abs(den) > 1e-12) f2 = ((g1[0] * g1[0] + g1[1] * g1[1]) - (g2[0] * g2[0] + g2[1] * g2[1])) / den
        if (!(f2 > 0) && abs(g1[2] * g2[2]) > 1e-12) f2 = -(g1[0] * g2[0] + g1[1] * g2[1]) / (g1[2] * g2[2])
        return if (f2 > 0) sqrt(f2) else null
    }

    /** Pixel ảnh -> (X, Y) mét; null nếu trên chân trời hoặc ngoài tầm đo. */
    fun imageToGround(u: Double, v: Double): Vec2? {
        val p = h.applyHomog(u, v)
        val s = p[2]
        if (abs(s) <= 1e-9 || (if (s >= 0) 1.0 else -1.0) != validSign) return null
        val x = p[0] / s; val y = p[1] / s
        if (y < 0 || y > calib.maxRangeM) return null
        return Vec2(x, y)
    }

    /** (X, Y) mét -> pixel ảnh. */
    fun groundToImage(x: Double, y: Double): Vec2 = hInv.apply(x, y)

    companion object {
        /** Mapper từ cấu hình; null nếu 4 điểm suy biến. */
        fun tryCreate(c: CalibrationConfig, w: Double, h: Double): GroundPlaneMapper? =
            if (w <= 0 || h <= 0) null else runCatching { GroundPlaneMapper(c, w, h) }.getOrNull()

        /** Như [tryCreate] nhưng 4 điểm suy biến thì dùng hiệu chỉnh mặc định (luôn có mapper để chạy). */
        fun orDefault(c: CalibrationConfig, w: Double, h: Double): GroundPlaneMapper =
            tryCreate(c, w, h) ?: GroundPlaneMapper(CalibrationConfig(), w, h)
    }
}
