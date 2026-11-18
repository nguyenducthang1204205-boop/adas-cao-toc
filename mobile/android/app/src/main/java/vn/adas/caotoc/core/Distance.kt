package vn.adas.caotoc.core

import kotlin.math.abs
import kotlin.math.max
import kotlin.math.sqrt
import kotlin.math.tan

/** Cách đo khoảng cách: IPM tại điểm chạm đất, hoặc "Xa" (Pinhole, ngoài tầm IPM - không cảnh báo). */
enum class RangeMethod(val label: String) { IPM("IPM"), FAR("Xa") }

class VehicleState(
    val det: Detection,
    val distanceM: Double,
    val lateralM: Double,
    val method: RangeMethod,
    val inEgoLane: Boolean,
    /** > 0: đang tiến lại gần (m/s); null khi bộ lọc chưa đủ tin. */
    val closingSpeedMps: Double?,
    val ttcS: Double?,
) {
    var risk: Risk = Risk.SAFE
}

/**
 * Khoảng cách, vị trí ngang, tốc độ tiếp cận và TTC từng xe (port của adas/distance/estimator.py).
 *
 * Chính: IPM tại điểm chạm đất. Dự phòng ("Xa"): Pinhole theo kích thước thật, không nhỏ hơn tầm đo.
 * Khoảng cách và tốc độ tiếp cận theo track lấy từ bộ lọc Kalman; khung "coast" chỉ dự đoán.
 */
class DistanceEstimator(private val mapper: GroundPlaneMapper, private val calib: CalibrationConfig) {
    private class Track(val kf: RangeKalman, var lastSeen: Double)

    private val focalPx: Double =
        mapper.focalPx ?: (mapper.frameH / (2 * tan(radians(calib.cameraVfovDeg) / 2)))
    private val tracks = HashMap<Int, Track>()

    fun reset() = tracks.clear()

    fun estimate(dets: List<Detection>, t: Double): List<VehicleState> {
        val states = ArrayList<VehicleState>(dets.size)
        for (det in dets) {
            val gp = det.groundPoint
            val g = mapper.imageToGround(gp.x, gp.y)
            val distance: Double
            val lateral: Double
            val method: RangeMethod
            if (g != null) {
                distance = g.y; lateral = g.x; method = RangeMethod.IPM
            } else {
                val (d, lat) = pinhole(det)
                distance = max(d, calib.maxRangeM); lateral = lat; method = RangeMethod.FAR
            }
            val (smoothed, closing) =
                updateTrack(det.trackId, distance, t, far = method == RangeMethod.FAR, measured = det.source != BoxSource.COAST)
            val ttc = if (closing != null && closing > MIN_CLOSING_MPS) smoothed / closing else null
            val inLane = abs(lateral) <= calib.laneHalfWidthM
            states += VehicleState(det, smoothed, lateral, method, inLane, closing, ttc)
        }
        tracks.entries.removeAll { t - it.value.lastSeen > TRACK_TIMEOUT_S }
        states.sortBy { it.distanceM }
        return states
    }

    private fun pinhole(det: Detection): Pair<Double, Double> {
        val f = focalPx
        val dH = (REAL_HEIGHTS_M[det.className] ?: 1.5) * f / max(det.height, 1.0)
        val dW = (REAL_WIDTHS_M[det.className] ?: 1.8) * f / max(det.width, 1.0)
        val d = sqrt(dH * dW)
        val cx = (det.x1 + det.x2) / 2
        return d to (cx - mapper.frameW / 2) * d / f
    }

    /** Kalman theo track: (khoảng cách đã lọc, tốc độ tiếp cận m/s hoặc null khi chưa đủ tin). */
    private fun updateTrack(id: Int?, d: Double, t: Double, far: Boolean, measured: Boolean): Pair<Double, Double?> {
        if (id == null) return d to null
        val sigma = measurementSigma(d, far)
        var tr = tracks[id]
        if (tr == null) {
            tr = Track(RangeKalman(d, t, sigma), t)
            tracks[id] = tr
        } else {
            tr.kf.predict(t)
            if (measured) tr.kf.update(d, sigma)
        }
        if (measured) tr.lastSeen = t
        val kf = tr.kf
        return kf.distance to (if (kf.rateStd < KalmanParams.RATE_STD_REPORT) kf.closingSpeed else null)
    }

    companion object {
        const val MIN_CLOSING_MPS = 0.5
        const val TRACK_TIMEOUT_S = 2.0
    }
}
