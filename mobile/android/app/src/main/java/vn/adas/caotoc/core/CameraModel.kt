package vn.adas.caotoc.core

import kotlin.math.abs
import kotlin.math.atan
import kotlin.math.atan2
import kotlin.math.ceil
import kotlin.math.cos
import kotlin.math.floor
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sin
import kotlin.math.sqrt
import kotlin.math.tan

/**
 * Mô hình camera theo tư thế (port của adas/distance/camera_model.py).
 *
 * Người dùng chỉ nhập chiều cao camera và khoảng cách tới đầu xe; điểm tụ ban đầu lấy từ cảm biến trọng lực
 * ([poseFromGravity]), tiêu cự từ thông số ống kính Camera2, rồi được tinh chỉnh khi chạy (OnlineCalib.kt).
 * [calibFromPose] chiếu 1 hình chữ nhật mặt đường lên ảnh để sinh 4 điểm như căn chỉnh thủ công, nên
 * [GroundPlaneMapper] giữ nguyên cách tính. Hệ tọa độ camera: x phải, y xuống, z theo trục quang học.
 */

const val LANE_WIDTH_M = 3.75

/** Số đo điển hình khi gắn máy giữa kính lái: (nhãn, chiều cao m, tới đầu xe m) - giống VEHICLE_PRESETS. */
val VEHICLE_PRESETS = linkedMapOf(
    "car" to Triple("Xe con", 1.25, 2.0),
    "suv" to Triple("SUV / bán tải", 1.55, 2.1),
    "bus" to Triple("Xe khách", 2.30, 0.4),
    "truck" to Triple("Xe tải", 2.20, 0.6),
)

/** Vector 3 chiều tối giản cho phép chiếu. */
data class V3(val x: Double, val y: Double, val z: Double) {
    operator fun plus(o: V3) = V3(x + o.x, y + o.y, z + o.z)
    operator fun minus(o: V3) = V3(x - o.x, y - o.y, z - o.z)
    operator fun times(k: Double) = V3(x * k, y * k, z * k)
    infix fun dot(o: V3) = x * o.x + y * o.y + z * o.z
    infix fun cross(o: V3) = V3(y * o.z - z * o.y, z * o.x - x * o.z, x * o.y - y * o.x)
    fun norm() = sqrt(this dot this)
    fun unit() = this * (1.0 / norm())
}

fun focalPx(pose: CameraPose, w: Double, h: Double, vfovDeg: Double = 55.0): Double =
    if (pose.focalW > 0) pose.focalW * w else (h / 2) / tan(radians(vfovDeg) / 2)

/** Phép chiếu mặt đường <-> ảnh của một tư thế camera. */
class PoseCamera(val pose: CameraPose, val w: Double, val h: Double, vfovDeg: Double = 55.0) {
    val f = focalPx(pose, w, h, vfovDeg)
    val cx = w / 2
    val cy = h / 2
    val vp = Vec2(pose.vpX * w, pose.vpY * h)
    val fwd: V3
    val down: V3
    val right: V3

    init {
        fwd = V3((vp.x - cx) / f, (vp.y - cy) / f, 1.0).unit()
        // đường chân trời qua điểm tụ, nghiêng theo roll; pháp tuyến mặt đường n = Kᵀ·l
        val r = radians(pose.rollDeg)
        val p0 = V3(vp.x, vp.y, 1.0)
        val line = p0 cross (p0 + V3(cos(r), sin(r), 0.0))
        var d = V3(f * line.x, f * line.y, cx * line.x + cy * line.y + line.z)
        d = (d - fwd * (d dot fwd)).unit()
        down = if (d.y < 0) d * -1.0 else d
        right = down cross fwd
    }

    /** > 0: camera chúc xuống. */
    val pitchDeg: Double get() = Math.toDegrees(kotlin.math.asin(down.z.coerceIn(-1.0, 1.0)))

    fun groundToImage(x: Double, y: Double): Vec2 {
        val p = right * x + fwd * (y + pose.bumperM) + down * pose.heightM
        return Vec2(cx + f * p.x / p.z, cy + f * p.y / p.z)
    }

    /** null: trên đường chân trời. */
    fun imageToGround(u: Double, v: Double): Vec2? {
        val ray = V3((u - cx) / f, (v - cy) / f, 1.0)
        val s = ray dot down
        if (s <= 1e-9) return null
        val p = ray * (pose.heightM / s)
        return Vec2(p dot right, (p dot fwd) - pose.bumperM)
    }

    /** 2 đầu đường chân trời ở mép trái / phải ảnh. */
    fun horizonPoints(): Pair<Vec2, Vec2> {
        val k = tan(radians(pose.rollDeg))
        return Vec2(0.0, vp.y - k * vp.x) to Vec2(w, vp.y + k * (w - vp.x))
    }
}

/** Làm tròn như round(v, n) của Python (giá trị nhị phân chính xác, nửa chẵn). */
private fun pyRound(v: Double, n: Int) = fixed(v, n).toDouble()

/** Sinh [CalibrationConfig] (4 điểm của 1 hình chữ nhật trên mặt đường) từ tư thế camera; lỗi -> IllegalArgumentException. */
fun calibFromPose(pose: CameraPose, w: Double, h: Double, base: CalibrationConfig): CalibrationConfig {
    val cam = PoseCamera(pose, w, h, base.cameraVfovDeg)
    val u0 = cam.vp.x; val v0 = cam.vp.y
    val bottom = 0.85 * h
    require(v0 < bottom - 0.05 * h) { "Đường chân trời quá thấp: hãy kéo lên cao hơn" }
    val near = cam.imageToGround(u0, bottom)
    val far = cam.imageToGround(u0, v0 + 0.15 * (bottom - v0))
    require(near != null && far != null) { "Tư thế camera không nhìn thấy mặt đường" }
    val d0 = max(1.0, ceil(near.y * 10) / 10)
    val d1 = max(d0 + 5.0, floor(far.y * 10) / 10)
    var lw = LANE_WIDTH_M
    for (i in 0 until 4) {
        val us = listOf(-lw / 2, lw / 2).map { cam.groundToImage(it, d0).x }
        val half = maxOf(abs(us[0] - u0), abs(us[1] - u0), 1e-6)
        if (us.min() >= 0.02 * w && us.max() <= 0.98 * w) break
        lw *= min(u0 - 0.02 * w, 0.98 * w - u0) / half * 0.98
    }
    val pts = listOf(-lw / 2 to d0, lw / 2 to d0, lw / 2 to d1, -lw / 2 to d1).map { (x, y) -> cam.groundToImage(x, y) }
    return base.copy(
        imagePoints = pts.map { Vec2(it.x / w, it.y / h) },
        rectWidthM = pyRound(lw, 3),
        rectLengthM = pyRound(d1 - d0, 2),
        nearDistanceM = d0,
        cameraVfovDeg = pyRound(Math.toDegrees(2 * atan((h / 2) / cam.f)), 2),
        pose = pose.copy(active = true, focalW = if (pose.focalW > 0) pose.focalW else cam.f / w),
    )
}

/** Quãng đường (m) giữa 2 hàng ảnh theo hiệu chỉnh: thang mà phép đo tốc độ từ video nhìn thấy (null: không đo được). */
fun longitudinalScale(calib: CalibrationConfig, w: Double, h: Double, rowA: Double, rowB: Double, u: Double): Double? {
    val m = GroundPlaneMapper.tryCreate(calib, w, h) ?: return null
    val a = m.imageToGround(u, rowA) ?: return null
    val b = m.imageToGround(u, rowB) ?: return null
    val d = abs(a.y - b.y)
    return if (d.isFinite() && d > 0) d else null
}

/**
 * Điểm tụ + góc nghiêng từ hướng trọng lực trong hệ camera ([downCam]: vector chỉ xuống đất, x phải, y xuống,
 * z theo trục quang học), coi camera nhìn thẳng theo hướng xe chạy (góc lệch ngang 0, tinh chỉnh khi chạy).
 */
fun poseFromGravity(pose: CameraPose, downCam: V3, w: Double, h: Double): CameraPose {
    val n = downCam.unit()
    val ez = V3(0.0, 0.0, 1.0)
    val fwd = (ez - n * (ez dot n)).unit()
    val f = focalPx(pose, w, h)
    val vp = Vec2(w / 2 + f * fwd.x / fwd.z, h / 2 + f * fwd.y / fwd.z)
    // đường chân trời: n·K⁻¹·p = 0 -> hướng (n.y, -n.x) trên ảnh
    val roll = Math.toDegrees(atan2(-n.x, n.y))
    return pose.copy(vpX = (vp.x / w).coerceIn(0.2, 0.8), vpY = (vp.y / h).coerceIn(0.15, 0.8), rollDeg = pyRound(roll, 2))
}
