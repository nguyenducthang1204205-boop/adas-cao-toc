package vn.adas.caotoc.core

import org.json.JSONObject
import java.time.LocalDateTime

/**
 * Một đợt vi phạm khoảng cách - tương ứng một dòng bảng `violations` trong CSDL của bản desktop.
 * Các trường thay đổi trong đợt (mức cao nhất, khoảng cách / TTC nhỏ nhất, thời lượng) là `var`.
 */
class Violation(
    val id: Int,
    val sessionId: Int,
    val startedAt: LocalDateTime,
    var level: Risk,
    val trackId: Int?,
    val className: String,
    /** Khoảng cách lúc bắt đầu. */
    val distanceM: Double,
    var minDistanceM: Double,
    var minTtcS: Double?,
    val safeM: Double,
    val dangerM: Double,
    val speedKmh: Double,
    val condition: String,
    val weatherFactor: Double,
    /** null: đang diễn ra. */
    var durationS: Double? = null,
) {
    val open: Boolean get() = durationS == null

    fun toJson(): JSONObject = JSONObject()
        .put("id", id)
        .put("session_id", sessionId)
        .put("started_at", startedAt.toString())
        .put("level", if (level == Risk.DANGER) "danger" else "warning")
        .put("track_id", trackId ?: JSONObject.NULL)
        .put("class", className)
        .put("distance_m", distanceM)
        .put("min_distance_m", minDistanceM)
        .put("min_ttc_s", minTtcS ?: JSONObject.NULL)
        .put("duration_s", durationS ?: JSONObject.NULL)
        .put("safe_m", safeM)
        .put("danger_m", dangerM)
        .put("speed_kmh", speedKmh)
        .put("condition", condition)
        .put("weather_factor", weatherFactor)

    companion object {
        fun fromJson(j: JSONObject) = Violation(
            id = j.getInt("id"),
            sessionId = j.optInt("session_id", 0),
            startedAt = runCatching { LocalDateTime.parse(j.optString("started_at")) }.getOrDefault(LocalDateTime.of(2000, 1, 1, 0, 0)),
            level = if (j.optString("level") == "danger") Risk.DANGER else Risk.WARNING,
            trackId = if (j.isNull("track_id")) null else j.getInt("track_id"),
            className = j.optString("class", "car"),
            distanceM = j.optDouble("distance_m", 0.0),
            minDistanceM = j.optDouble("min_distance_m", 0.0),
            minTtcS = if (j.isNull("min_ttc_s")) null else j.getDouble("min_ttc_s"),
            safeM = j.optDouble("safe_m", 0.0),
            dangerM = j.optDouble("danger_m", 0.0),
            speedKmh = j.optDouble("speed_kmh", 0.0),
            condition = j.optString("condition", ""),
            weatherFactor = j.optDouble("weather_factor", 1.0),
            // đợt chưa đóng khi app tắt: coi như đã đóng
            durationS = if (j.isNull("duration_s")) 0.0 else j.getDouble("duration_s"),
        )
    }
}

enum class ViolationAction { OPEN, UPDATE, CLOSE }

data class ViolationEvent(val action: ViolationAction, val violation: Violation)

/**
 * Ghi nhật ký vi phạm theo ĐỢT (port của adas/alert/violations.py::ViolationRecorder).
 *
 * Một đợt bắt đầu khi mức cảnh báo ổn định (sau chống nhiễu) chuyển sang CẢNH BÁO/NGUY HIỂM với một xe
 * phía trước, và kết thúc khi trở về AN TOÀN hoặc xe phía trước đổi sang xe khác. Trong đợt chỉ cập nhật
 * khoảng cách/TTC nhỏ nhất và mức cao nhất; nơi lưu chỉ được gọi khi mở, nâng mức và đóng đợt.
 */
class ViolationRecorder(
    private val sessionId: Int,
    private val nextId: () -> Int,
    private val clock: () -> LocalDateTime = LocalDateTime::now,
) {
    var current: Violation? = null
        private set
    private var startT = 0.0
    var count = 0
        private set

    /** Gọi mỗi khung. Trả về các sự kiện để nơi lưu ghi lại (rỗng ở hầu hết các khung). */
    fun update(r: FrameResult, t: Double, speedKmh: Double, condition: String, weatherFactor: Double): List<ViolationEvent> {
        val events = ArrayList<ViolationEvent>(2)
        val lead = r.lead
        val alerting = r.level == Risk.WARNING || r.level == Risk.DANGER
        val active = alerting && lead != null
        val ep = current
        if (ep != null && (!active || lead.det.trackId != ep.trackId)) {
            if (alerting && lead == null) return events // mất dấu xe tạm thời nhưng vẫn cảnh báo -> giữ đợt
            events += closeAt(t)
        }
        if (!active) return events

        val cur = current
        if (cur == null) {
            val thr = r.thresholds
            val v = Violation(
                id = nextId(), sessionId = sessionId, startedAt = clock(), level = r.level,
                trackId = lead.det.trackId, className = lead.det.className,
                distanceM = lead.distanceM, minDistanceM = lead.distanceM, minTtcS = lead.ttcS,
                safeM = thr.safeM, dangerM = thr.dangerM, speedKmh = speedKmh,
                condition = condition, weatherFactor = weatherFactor,
            )
            current = v
            startT = t
            count++
            events += ViolationEvent(ViolationAction.OPEN, v)
        } else {
            if (lead.distanceM < cur.minDistanceM) cur.minDistanceM = lead.distanceM
            val ttc = lead.ttcS
            if (ttc != null && (cur.minTtcS == null || ttc < cur.minTtcS!!)) cur.minTtcS = ttc
            if (r.level.rank > cur.level.rank) {
                cur.level = r.level
                events += ViolationEvent(ViolationAction.UPDATE, cur)
            }
        }
        return events
    }

    /** Đóng đợt đang mở (khi dừng giám sát). */
    fun close(t: Double): ViolationEvent? = if (current != null) closeAt(t) else null

    private fun closeAt(t: Double): ViolationEvent {
        val ep = current!!
        ep.durationS = if (t - startT > 0) t - startT else 0.0
        current = null
        return ViolationEvent(ViolationAction.CLOSE, ep)
    }
}
