package vn.adas.caotoc.core

import kotlin.math.PI
import kotlin.math.abs

/** Điểm / vector 2D (pixel ảnh, mét mặt đường hoặc tỉ lệ 0..1 tùy ngữ cảnh). */
data class Vec2(val x: Double, val y: Double)

/**
 * Ma trận 3x3 lưu theo hàng cho homography (thay cv2.getPerspectiveTransform / np.linalg.inv của bản desktop).
 */
class Mat3(values: DoubleArray) {
    val m: DoubleArray = values.copyOf()

    init {
        require(values.size == 9)
    }

    fun at(r: Int, c: Int): Double = m[r * 3 + c]

    operator fun times(o: Mat3): Mat3 {
        val out = DoubleArray(9)
        for (r in 0 until 3) for (c in 0 until 3) {
            var s = 0.0
            for (k in 0 until 3) s += at(r, k) * o.at(k, c)
            out[r * 3 + c] = s
        }
        return Mat3(out)
    }

    /** Nhân với vector đồng nhất (x, y, 1) -> (X, Y, W) chưa chia. */
    fun applyHomog(x: Double, y: Double): DoubleArray = doubleArrayOf(
        m[0] * x + m[1] * y + m[2],
        m[3] * x + m[4] * y + m[5],
        m[6] * x + m[7] * y + m[8],
    )

    fun apply(x: Double, y: Double): Vec2 {
        val h = applyHomog(x, y)
        return Vec2(h[0] / h[2], h[1] / h[2])
    }

    fun inverse(): Mat3 {
        val a = m
        val c00 = a[4] * a[8] - a[5] * a[7]
        val c01 = a[5] * a[6] - a[3] * a[8]
        val c02 = a[3] * a[7] - a[4] * a[6]
        val det = a[0] * c00 + a[1] * c01 + a[2] * c02
        check(abs(det) >= 1e-15) { "Ma trận suy biến (4 điểm hiệu chỉnh thẳng hàng?)" }
        val inv = 1.0 / det
        return Mat3(doubleArrayOf(
            c00 * inv, (a[2] * a[7] - a[1] * a[8]) * inv, (a[1] * a[5] - a[2] * a[4]) * inv,
            c01 * inv, (a[0] * a[8] - a[2] * a[6]) * inv, (a[2] * a[3] - a[0] * a[5]) * inv,
            c02 * inv, (a[1] * a[6] - a[0] * a[7]) * inv, (a[0] * a[4] - a[1] * a[3]) * inv,
        ))
    }

    companion object {
        /** Homography ánh xạ 4 điểm src -> 4 điểm dst (giống cv2.getPerspectiveTransform, h33 = 1). */
        fun perspective(src: List<Vec2>, dst: List<Vec2>): Mat3 {
            require(src.size == 4 && dst.size == 4)
            // Hệ 8 phương trình tuyến tính A·h = b (cột cuối là b)
            val a = Array(8) { DoubleArray(9) }
            for (i in 0 until 4) {
                val u = src[i].x; val v = src[i].y; val x = dst[i].x; val y = dst[i].y
                a[2 * i].apply { this[0] = u; this[1] = v; this[2] = 1.0; this[6] = -u * x; this[7] = -v * x; this[8] = x }
                a[2 * i + 1].apply { this[3] = u; this[4] = v; this[5] = 1.0; this[6] = -u * y; this[7] = -v * y; this[8] = y }
            }
            // Khử Gauss-Jordan có chọn trụ
            for (col in 0 until 8) {
                var piv = col
                for (r in col + 1 until 8) if (abs(a[r][col]) > abs(a[piv][col])) piv = r
                check(abs(a[piv][col]) >= 1e-12) { "Không tính được homography: 4 điểm suy biến" }
                val tmp = a[col]; a[col] = a[piv]; a[piv] = tmp
                for (r in 0 until 8) {
                    if (r == col) continue
                    val f = a[r][col] / a[col][col]
                    if (f == 0.0) continue
                    for (c in col until 9) a[r][c] -= f * a[col][c]
                }
            }
            return Mat3(DoubleArray(9) { i -> if (i < 8) a[i][8] / a[i][i] else 1.0 })
        }
    }
}

fun radians(deg: Double): Double = deg * PI / 180.0
