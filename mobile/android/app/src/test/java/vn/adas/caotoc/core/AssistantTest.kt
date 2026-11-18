package vn.adas.caotoc.core

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDateTime
import kotlin.math.abs

/**
 * Trợ lý offline + nhật ký vi phạm: Kotlin phải cho kết quả giống hệt bản desktop (Python).
 * Fixture: python tools/make_mobile_fixtures.py -> assistant_python.json (hơn 300 câu, nhiều chính sách nền).
 */
class AssistantTest {
    private fun policy(j: JSONObject) = SafetyPolicy(
        timeGapS = j.getDouble("time_gap_s"),
        bandGapsM = j.getJSONArray("band_gaps_m").let { a -> List(a.length()) { a.getDouble(it) } },
        weatherFactor = j.getDouble("weather_factor"),
        dangerRatio = j.getDouble("danger_ratio"),
        minDistanceM = j.getDouble("min_distance_m"),
        ttcWarningS = j.getDouble("ttc_warning_s"),
        ttcDangerS = j.getDouble("ttc_danger_s"),
        condition = j.getString("condition"),
        roadMu = j.getDouble("road_mu"),
        visibilityM = j.getDouble("visibility_m"),
    )

    private fun close(want: Double, got: Double, why: String) = assertTrue("$why: $want != $got", abs(want - got) <= 1e-9)

    @Test
    fun foldAndCompose() {
        assertEquals("troi mua to, duong tron", foldVi("Trời MƯA to, Đường trơn"))
        assertEquals("e o u y", foldVi("ệ ở ữ ỳ"))
        assertEquals("ệ", nfcVi("ệ"))
        assertEquals("ệ", nfcVi("ệ"))
        assertEquals("mưa", nfcVi("mưa"))
    }

    @Test
    fun numbersLikePython() {
        assertEquals("2", vnNum(2.0)); assertEquals("2,5", vnNum(2.5)); assertEquals("1,15", vnNum(1.15))
        assertEquals("1,0", vnFactor(1.0)); assertEquals("1,4", vnFactor(1.4)); assertEquals("1,15", vnFactor(1.15))
        assertEquals("39,7", vn(39.66))
    }

    @Test
    fun offlineAssistantMatchesPython() {
        val j = JSONObject(javaClass.classLoader!!.getResourceAsStream("fixtures/assistant_python.json")!!
            .use { String(it.readBytes(), Charsets.UTF_8) })
        val basesJ = j.getJSONObject("bases")
        val bases = basesJ.keys().asSequence().associateWith { policy(basesJ.getJSONObject(it)) }
        val cases = j.getJSONArray("cases")
        for (i in 0 until cases.length()) {
            val c = cases.getJSONObject(i)
            val why = "\"${c.getString("message")}\" / ${c.getString("base")} / ${c.get("speed")} km/h"
            val r = OfflineAssistant.advise(c.getString("message"), bases.getValue(c.getString("base")), c.getDouble("speed"))
            assertEquals(why, c.getString("reply"), r.reply)
            assertEquals(why, if (c.isNull("speed_out")) null else c.getDouble("speed_out"), r.speedKmh)
            val p = c.getJSONObject("policy")
            assertEquals(why, p.getString("condition"), r.policy.condition)
            close(p.getDouble("weather_factor"), r.policy.weatherFactor, why)
            close(p.getDouble("visibility_m"), r.policy.visibilityM, why)
            close(p.getDouble("road_mu"), r.policy.roadMu, why)
            close(p.getDouble("ttc_warning_s"), r.policy.ttcWarningS, why)
            close(p.getDouble("ttc_danger_s"), r.policy.ttcDangerS, why)
            assertEquals(why, p.getDouble("time_gap_s"), r.policy.timeGapS, 0.0)
            assertEquals(why, p.getJSONArray("band_gaps_m").let { a -> List(a.length()) { a.getDouble(it) } }, r.policy.bandGapsM)
        }
        assertTrue(cases.length() > 300)
    }

    @Test
    fun reapplyingAssistantConditionGivesSamePolicy() {
        // App lưu (điều kiện, yếu tố, tầm nhìn) rồi dựng lại policy bằng conditionPolicy: phải trùng kết quả trợ lý.
        for (m in listOf("trời mưa, đêm khuya, tôi buồn ngủ", "sương mù tầm nhìn 80 m", "chở nặng", "đã tạnh mưa")) {
            val r = OfflineAssistant.advise(m, SafetyPolicy(), 90.0)
            val again = conditionPolicy(r.conditionKey!!, r.modifierKeys, r.visibilityM)
            assertEquals(m, r.policy.condition, again.condition)
            assertEquals(m, r.policy.weatherFactor, again.weatherFactor, 0.0)
            assertEquals(m, r.policy.visibilityM, again.visibilityM, 0.0)
        }
    }

    private fun frame(level: Risk, d: Double?, track: Int = 1, ttc: Double? = null): FrameResult {
        val thr = Thresholds(90.0, 110.0, 55.0, 50.0, 70.0, 70.0, false, null)
        val lead = d?.let {
            VehicleState(Detection(0.0, 0.0, 10.0, 10.0, 0.9, 2, "car", track), it, 0.0, RangeMethod.IPM, true, null, ttc)
        }
        return FrameResult(listOfNotNull(lead), lead, thr, 90.0, level, level)
    }

    @Test
    fun violationsAreRecordedPerEpisode() {
        var id = 0
        val rec = ViolationRecorder(1, nextId = { ++id }, clock = { LocalDateTime.of(2026, 10, 25, 8, 0) })
        val ev = ArrayList<ViolationEvent>()
        ev += rec.update(frame(Risk.SAFE, 120.0), 0.0, 90.0, "khô", 1.0)
        assertTrue(ev.isEmpty())
        ev += rec.update(frame(Risk.WARNING, 90.0, ttc = 6.0), 1.0, 90.0, "khô", 1.0) // mở
        ev += rec.update(frame(Risk.WARNING, 80.0, ttc = 5.0), 1.1, 90.0, "khô", 1.0) // không ghi
        ev += rec.update(frame(Risk.DANGER, 50.0, ttc = 3.0), 1.2, 90.0, "khô", 1.0) // nâng mức
        ev += rec.update(frame(Risk.DANGER, null), 1.3, 90.0, "khô", 1.0) // mất dấu xe: giữ đợt
        ev += rec.update(frame(Risk.WARNING, 60.0), 1.4, 90.0, "khô", 1.0) // hạ mức: không ghi
        ev += rec.update(frame(Risk.SAFE, 130.0), 3.0, 90.0, "khô", 1.0) // đóng
        assertEquals(listOf(ViolationAction.OPEN, ViolationAction.UPDATE, ViolationAction.CLOSE), ev.map { it.action })
        val v = ev.last().violation
        assertEquals(Risk.DANGER, v.level)
        assertEquals(50.0, v.minDistanceM, 0.0)
        assertEquals(3.0, v.minTtcS!!, 0.0)
        assertEquals(2.0, v.durationS!!, 1e-9)
        // xe phía trước đổi sang xe khác -> đóng đợt cũ, mở đợt mới
        ev.clear()
        ev += rec.update(frame(Risk.WARNING, 90.0, track = 1), 4.0, 90.0, "khô", 1.0)
        ev += rec.update(frame(Risk.WARNING, 85.0, track = 2), 4.1, 90.0, "khô", 1.0)
        assertEquals(listOf(ViolationAction.OPEN, ViolationAction.CLOSE, ViolationAction.OPEN), ev.map { it.action })
        assertEquals(3, rec.count)
        assertEquals(v.toJson().toString(), Violation.fromJson(v.toJson()).toJson().toString())
    }
}
