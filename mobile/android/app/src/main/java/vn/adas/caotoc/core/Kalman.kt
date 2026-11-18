package vn.adas.caotoc.core

import kotlin.math.max
import kotlin.math.sqrt

/**
 * Bộ lọc Kalman cho khoảng cách tới một xe phía trước (port 1:1 của adas/distance/kalman.py - xem đó để biết
 * cách chọn tham số bằng mô phỏng).
 *
 * Trạng thái [d, ḋ, d̈], mô hình gia tốc không đổi, nhiễu quá trình là độ giật ngẫu nhiên.
 * Phép đo d (IPM) có σ = max(0,3 m; 4 %·d) - đo trên video thật.
 */
object KalmanParams {
    const val SIGMA_JERK = 10.0      // m/s³
    const val SIGMA_D_MIN = 0.3      // m
    const val SIGMA_D_REL = 0.04     // sai số đo IPM ≈ 4 % khoảng cách
    const val RATE_STD_INIT = 8.0    // m/s
    const val ACC_STD_INIT = 1.0     // m/s²
    const val RATE_STD_REPORT = 2.0  // m/s - dưới mức này mới báo tốc độ tiếp cận / TTC
    const val GATE_SIGMA = 5.0       // lệch dự đoán > 5σ: ngoại lai
    const val MAX_OUTLIERS = 3       // ngoại lai liên tiếp -> khởi tạo lại từ phép đo
}

/** Độ lệch chuẩn phép đo khoảng cách; [far]: ước lượng Pinhole ("Xa") kém tin cậy hơn nhiều. */
fun measurementSigma(d: Double, far: Boolean = false): Double =
    max(KalmanParams.SIGMA_D_MIN, (if (far) 0.25 else KalmanParams.SIGMA_D_REL) * d)

class RangeKalman(d: Double, var t: Double, sigma: Double) {
    private var x = DoubleArray(3)
    private var p = Array(3) { DoubleArray(3) }
    private var outliers = 0

    init {
        reinit(d, sigma)
    }

    private fun reinit(d: Double, sigma: Double) {
        x = doubleArrayOf(d, 0.0, 0.0)
        p = arrayOf(
            doubleArrayOf(sigma * sigma, 0.0, 0.0),
            doubleArrayOf(0.0, KalmanParams.RATE_STD_INIT * KalmanParams.RATE_STD_INIT, 0.0),
            doubleArrayOf(0.0, 0.0, KalmanParams.ACC_STD_INIT * KalmanParams.ACC_STD_INIT),
        )
        outliers = 0
    }

    fun predict(tNew: Double) {
        val dt = tNew - t
        if (dt <= 0) return
        val f = arrayOf(doubleArrayOf(1.0, dt, dt * dt / 2), doubleArrayOf(0.0, 1.0, dt), doubleArrayOf(0.0, 0.0, 1.0))
        val g = doubleArrayOf(dt * dt * dt / 6, dt * dt / 2, dt)
        val q = KalmanParams.SIGMA_JERK * KalmanParams.SIGMA_JERK
        x = DoubleArray(3) { i -> f[i][0] * x[0] + f[i][1] * x[1] + f[i][2] * x[2] }
        val fp = Array(3) { i -> DoubleArray(3) { j -> f[i][0] * p[0][j] + f[i][1] * p[1][j] + f[i][2] * p[2][j] } }
        p = Array(3) { i ->
            DoubleArray(3) { j -> fp[i][0] * f[j][0] + fp[i][1] * f[j][1] + fp[i][2] * f[j][2] + q * g[i] * g[j] }
        }
        t = tNew
    }

    /** Cập nhật với phép đo [z] (đã predict tới thời điểm đo). false nếu bị loại là ngoại lai. */
    fun update(z: Double, sigma: Double): Boolean {
        val s = p[0][0] + sigma * sigma
        val y = z - x[0]
        if (y * y > KalmanParams.GATE_SIGMA * KalmanParams.GATE_SIGMA * s) {
            outliers++
            if (outliers < KalmanParams.MAX_OUTLIERS) return false
            reinit(z, sigma) // dự đoán sai liên tục (đổi xe, lần đầu đo lệch): làm lại
            return true
        }
        outliers = 0
        val k = DoubleArray(3) { i -> p[i][0] / s }
        x = DoubleArray(3) { i -> x[i] + k[i] * y }
        val p0 = p[0].copyOf()
        p = Array(3) { i -> DoubleArray(3) { j -> p[i][j] - k[i] * p0[j] } }
        return true
    }

    val distance: Double get() = x[0]

    /** > 0: đang tiến lại gần (m/s). */
    val closingSpeed: Double get() = -x[1]

    val rateStd: Double get() = sqrt(max(p[1][1], 0.0))
}
