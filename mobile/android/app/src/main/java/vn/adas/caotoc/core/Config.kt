package vn.adas.caotoc.core

import org.json.JSONArray
import org.json.JSONObject

/**
 * Cấu hình dùng chung (giống adas/config.py + bảng điều kiện đường của adas/alert/thresholds.py).
 * Các lớp cấu hình là bất biến: đổi thì tạo bản sao (`copy(...)`), nên chuyển an toàn giữa các luồng.
 */

val CLASS_LABELS_VI = mapOf(
    "car" to "Ô tô",
    "truck" to "Xe tải",
    "bus" to "Xe khách",
    "Jeepney" to "Xe khách",
    "motorcycle" to "Xe máy",
)

/** Chiều cao / bề rộng thực trung bình (m) - cho ước lượng dự phòng Pinhole. */
val REAL_HEIGHTS_M = mapOf("car" to 1.50, "truck" to 3.00, "bus" to 3.20, "Jeepney" to 2.10, "motorcycle" to 1.25)
val REAL_WIDTHS_M = mapOf("car" to 1.80, "truck" to 2.50, "bus" to 2.50, "Jeepney" to 2.00, "motorcycle" to 0.80)

/**
 * Căn chỉnh theo tư thế camera (CameraModel.kt, giống CameraPose của adas/config.py): chiều cao camera, khoảng cách
 * tới đầu xe, điểm tụ (hướng xe chạy trên ảnh). [active]: 4 điểm của [CalibrationConfig] được sinh từ tư thế này.
 */
data class CameraPose(
    val active: Boolean = false,
    val vehicle: String = "car",
    val heightM: Double = 1.25,
    /** Đo bằng thước: giữ nguyên; không: tự chỉnh theo làn 3,75 m khi chạy. */
    val heightMeasured: Boolean = false,
    val bumperM: Double = 2.0,
    /** Tiêu cự / chiều rộng khung; 0 = theo [CalibrationConfig.cameraVfovDeg]. */
    val focalW: Double = 0.0,
    /** camera (thông số ống kính Camera2) | speed | fov (giả định). */
    val focalSource: String = "fov",
    val vpX: Double = 0.5,
    val vpY: Double = 0.5,
    val rollDeg: Double = 0.0,
    val refSpeedKmh: Double = 0.0,
    val refined: Boolean = false,
) {
    fun toJson(): JSONObject = JSONObject()
        .put("active", active).put("vehicle", vehicle).put("height_m", heightM).put("height_measured", heightMeasured)
        .put("bumper_m", bumperM).put("focal_w", focalW).put("focal_source", focalSource)
        .put("vp_x", vpX).put("vp_y", vpY).put("roll_deg", rollDeg).put("ref_speed_kmh", refSpeedKmh)
        .put("refined", refined)

    companion object {
        fun fromJson(j: JSONObject): CameraPose = CameraPose(
            active = j.optBoolean("active", false), vehicle = j.optString("vehicle", "car"),
            heightM = j.optDouble("height_m", 1.25), heightMeasured = j.optBoolean("height_measured", false),
            bumperM = j.optDouble("bumper_m", 2.0), focalW = j.optDouble("focal_w", 0.0),
            focalSource = j.optString("focal_source", "fov"), vpX = j.optDouble("vp_x", 0.5),
            vpY = j.optDouble("vp_y", 0.5), rollDeg = j.optDouble("roll_deg", 0.0),
            refSpeedKmh = j.optDouble("ref_speed_kmh", 0.0), refined = j.optBoolean("refined", false),
        )
    }
}

/**
 * Hiệu chỉnh IPM bằng hình chữ nhật trên mặt đường có kích thước biết trước.
 * [imagePoints]: 4 góc trên ảnh (tỉ lệ 0..1), thứ tự dưới-trái, dưới-phải, trên-phải, trên-trái.
 */
data class CalibrationConfig(
    val imagePoints: List<Vec2> = DEFAULT_POINTS,
    val rectWidthM: Double = 3.75,
    val rectLengthM: Double = 30.0,
    val nearDistanceM: Double = 6.0,
    val laneHalfWidthM: Double = 1.9,
    val maxRangeM: Double = 150.0,
    val cameraVfovDeg: Double = 55.0,
    val pose: CameraPose = CameraPose(),
) {
    fun toJson(): JSONObject = JSONObject()
        .put("image_points", JSONArray(imagePoints.map { JSONArray(listOf(it.x, it.y)) }))
        .put("rect_width_m", rectWidthM)
        .put("rect_length_m", rectLengthM)
        .put("near_distance_m", nearDistanceM)
        .put("lane_half_width_m", laneHalfWidthM)
        .put("max_range_m", maxRangeM)
        .put("camera_vfov_deg", cameraVfovDeg)
        .put("pose", pose.toJson())

    companion object {
        val DEFAULT_POINTS = listOf(Vec2(0.33, 0.90), Vec2(0.67, 0.90), Vec2(0.535, 0.62), Vec2(0.465, 0.62))

        fun fromJson(j: JSONObject): CalibrationConfig {
            val pts = j.optJSONArray("image_points")?.let { a ->
                (0 until a.length()).map { i -> a.getJSONArray(i).let { Vec2(it.getDouble(0), it.getDouble(1)) } }
            }
            return CalibrationConfig(
                imagePoints = if (pts != null && pts.size == 4) pts else DEFAULT_POINTS,
                rectWidthM = j.optDouble("rect_width_m", 3.75),
                rectLengthM = j.optDouble("rect_length_m", 30.0),
                nearDistanceM = j.optDouble("near_distance_m", 6.0),
                laneHalfWidthM = j.optDouble("lane_half_width_m", 1.9),
                maxRangeM = j.optDouble("max_range_m", 150.0),
                cameraVfovDeg = j.optDouble("camera_vfov_deg", 55.0),
                pose = j.optJSONObject("pose")?.let(CameraPose::fromJson) ?: CameraPose(),
            )
        }
    }
}

/** Mức tối thiểu theo luật của từng dải tốc độ (khớp [LEGAL_GAP_TABLE]). */
val DEFAULT_BAND_GAPS_M = listOf(35.0, 55.0, 70.0, 100.0)

/** Chính sách ngưỡng an toàn (xem Safety.kt). */
data class SafetyPolicy(
    /** Quy tắc thời gian, chỉ dùng khi V < 60 km/h. */
    val timeGapS: Double = 2.0,
    /** Ngưỡng cảnh báo (đường khô) người dùng đặt cho từng dải của [LEGAL_GAP_TABLE]; không thấp hơn luật. */
    val bandGapsM: List<Double> = DEFAULT_BAND_GAPS_M,
    val weatherFactor: Double = 1.0,
    val dangerRatio: Double = 0.5,
    val minDistanceM: Double = 5.0,
    val ttcWarningS: Double = 4.0,
    val ttcDangerS: Double = 2.0,
    val useLegalTable: Boolean = true,
    val condition: String = "Đường khô ráo, tầm nhìn tốt",
    val roadMu: Double = 0.7,
    val visibilityM: Double = 0.0,
)

data class AlertConfig(
    val soundEnabled: Boolean = true,
    val voiceEnabled: Boolean = true,
    val onlyEgoLane: Boolean = true,
    /** Mức mới phải kéo dài ngần này giây (>= 2 khung) mới nâng. */
    val escalateSeconds: Double = 0.1,
    val holdSeconds: Double = 0.8,
) {
    fun toJson(): JSONObject = JSONObject()
        .put("sound_enabled", soundEnabled)
        .put("voice_enabled", voiceEnabled)
        .put("only_ego_lane", onlyEgoLane)
        .put("escalate_seconds", escalateSeconds)
        .put("hold_seconds", holdSeconds)

    companion object {
        fun fromJson(j: JSONObject) = AlertConfig(
            soundEnabled = j.optBoolean("sound_enabled", true),
            voiceEnabled = j.optBoolean("voice_enabled", true),
            onlyEgoLane = j.optBoolean("only_ego_lane", true),
            escalateSeconds = j.optDouble("escalate_seconds", 0.1),
            holdSeconds = j.optDouble("hold_seconds", 0.8),
        )
    }
}

data class RoadCondition(
    val key: String,
    val name: String,
    val shortName: String,
    /** Hệ số nhân khoảng cách so với đường khô. */
    val factor: Double,
    /** Hệ số bám ước tính. */
    val mu: Double,
    val ttcWarningS: Double,
    val ttcDangerS: Double,
    val advice: String,
)

/** Hệ số ≈ 0,7/μ (giống ROAD_CONDITIONS của bản desktop). Thứ tự giữ nguyên để hiển thị. */
val ROAD_CONDITIONS: Map<String, RoadCondition> = linkedMapOf(
    "dry" to RoadCondition("dry", "Đường khô ráo, tầm nhìn tốt", "Khô ráo", 1.0, 0.70, 4.0, 2.0,
        "Giữ khoảng cách tối thiểu theo bảng quy định."),
    "wet" to RoadCondition("wet", "Mặt đường ướt, mưa nhỏ", "Mưa nhỏ", 1.4, 0.50, 5.0, 2.5,
        "Độ bám giảm (hệ số bám ≈ 0,5), quãng phanh dài hơn khoảng 1,4 lần."),
    "heavy_rain" to RoadCondition("heavy_rain", "Mưa to, mặt đường đọng nước", "Mưa to", 2.0, 0.35, 6.0, 3.0,
        "Nguy cơ trượt nước (hệ số bám ≈ 0,35): giảm tốc độ, giữ khoảng cách gấp đôi."),
    "fog" to RoadCondition("fog", "Sương mù, tầm nhìn hạn chế", "Sương mù", 1.5, 0.60, 5.5, 3.0,
        "Bật đèn sương mù/đèn cốt, giảm tốc để dừng kịp trong phạm vi nhìn thấy."),
    "slippery" to RoadCondition("slippery", "Mặt đường trơn trượt (dầu, bùn, sỏi)", "Trơn trượt", 2.5, 0.25, 6.0, 3.0,
        "Độ bám rất thấp (hệ số bám ≈ 0,25): giảm tốc rõ rệt, tránh phanh gấp."),
)

/** Yếu tố cộng thêm (nhân dồn). */
data class Modifier(val label: String, val shortName: String, val factor: Double)

val MODIFIERS: Map<String, Modifier> = linkedMapOf(
    "night" to Modifier("Ban đêm, thiếu ánh sáng", "Ban đêm", 1.2),
    "heavy_vehicle" to Modifier("Xe chủ chở nặng", "Chở nặng", 1.3),
    "tired" to Modifier("Tài xế mệt mỏi", "Mệt mỏi", 1.15),
)

const val MAX_FACTOR = 3.0
