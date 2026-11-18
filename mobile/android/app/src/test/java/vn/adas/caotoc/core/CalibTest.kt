package vn.adas.caotoc.core

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.zip.GZIPInputStream
import kotlin.math.abs

/**
 * Căn chỉnh theo tư thế + tự hoàn thiện khi chạy phải khớp bản Python (adas/distance/camera_model.py,
 * online_calib.py). Dữ liệu chuẩn: calib_python.json, lane_python.json + lane_frames.bin.gz do
 * tools/make_mobile_fixtures.py sinh ra.
 */
class CalibTest {
    private fun bytes(name: String): ByteArray =
        javaClass.classLoader!!.getResourceAsStream("fixtures/$name")!!.use { it.readBytes() }

    private fun json(name: String) = JSONObject(String(bytes(name), Charsets.UTF_8))

    private fun close(want: Double, got: Double, tol: Double, why: String = "") =
        assertTrue("$why: muốn $want, được $got", abs(want - got) <= tol)

    private fun pair(a: JSONArray) = Vec2(a.getJSONArray(0).getDouble(0), a.getJSONArray(0).getDouble(1)) to
        Vec2(a.getJSONArray(1).getDouble(0), a.getJSONArray(1).getDouble(1))

    private fun sameCalib(want: CalibrationConfig, got: CalibrationConfig, why: String) {
        for (i in 0 until 4) {
            close(want.imagePoints[i].x, got.imagePoints[i].x, 1e-6, "$why điểm $i x")
            close(want.imagePoints[i].y, got.imagePoints[i].y, 1e-6, "$why điểm $i y")
        }
        close(want.rectWidthM, got.rectWidthM, 1e-9, "$why bề rộng")
        close(want.rectLengthM, got.rectLengthM, 1e-9, "$why chiều dài")
        close(want.nearDistanceM, got.nearDistanceM, 1e-9, "$why cạnh gần")
        close(want.cameraVfovDeg, got.cameraVfovDeg, 1e-9, "$why góc nhìn")
        close(want.pose.vpX, got.pose.vpX, 1e-7, "$why điểm tụ x")
        close(want.pose.vpY, got.pose.vpY, 1e-7, "$why điểm tụ y")
        close(want.pose.heightM, got.pose.heightM, 1e-5, "$why chiều cao")
        // tiêu cự chỉnh theo GPS là nghiệm lặp qua nghịch đảo H: numpy và Kotlin lệch ~1e-7
        close(want.pose.focalW, got.pose.focalW, 1e-6, "$why tiêu cự")
        assertEquals(want.pose.active, got.pose.active)
        assertEquals(want.pose.refined, got.pose.refined)
    }

    @Test
    fun poseCalibrationMatchesPython() {
        val fx = json("calib_python.json")
        val w = fx.getJSONArray("frame").getDouble(0); val h = fx.getJSONArray("frame").getDouble(1)
        val poses = fx.getJSONArray("poses")
        for (i in 0 until poses.length()) {
            val c = poses.getJSONObject(i)
            val pose = CameraPose.fromJson(c.getJSONObject("pose"))
            val got = calibFromPose(pose, w, h, CalibrationConfig())
            sameCalib(CalibrationConfig.fromJson(c.getJSONObject("calib")), got, "tư thế $i")
            val cam = PoseCamera(got.pose, w, h)
            close(c.getDouble("pitch_deg"), cam.pitchDeg, 1e-9, "góc chúc $i")
            val probe = c.getJSONArray("probe"); val img = c.getJSONArray("image")
            for (k in 0 until probe.length()) {
                val q = cam.groundToImage(probe.getJSONArray(k).getDouble(0), probe.getJSONArray(k).getDouble(1))
                close(img.getJSONArray(k).getDouble(0), q.x, 1e-6); close(img.getJSONArray(k).getDouble(1), q.y, 1e-6)
                // khứ hồi ảnh -> mặt đường
                val g = cam.imageToGround(q.x, q.y)!!
                close(probe.getJSONArray(k).getDouble(0), g.x, 1e-9); close(probe.getJSONArray(k).getDouble(1), g.y, 1e-9)
            }
            // mapper dựng từ 4 điểm sinh ra phải cho đúng tiêu cự của tư thế
            close(pose.focalW * w, GroundPlaneMapper(got, w, h).focalPx!!, 1e-3, "tiêu cự phân rã $i")
        }
    }

    @Test
    fun onlineCalibrationMatchesPython() {
        val fx = json("calib_python.json")
        val w = fx.getJSONArray("frame").getDouble(0); val h = fx.getJSONArray("frame").getDouble(1)
        val scenarios = fx.getJSONArray("scenarios")
        for (si in 0 until scenarios.length()) {
            val sc = scenarios.getJSONObject(si)
            val name = sc.getString("name")
            val cal = OnlineCalibrator(w, h, sc.getInt("samples_needed"))
            var calib = CalibrationConfig.fromJson(sc.getJSONObject("start"))
            var mapper = GroundPlaneMapper(calib, w, h)
            val steps = sc.getJSONArray("steps")
            var applied = 0
            for (i in 0 until steps.length()) {
                val s = steps.getJSONObject(i)
                val obs = s.optJSONObject("obs")?.let {
                    LaneObservation(pair(it.getJSONArray("left")), pair(it.getJSONArray("right")), it.getBoolean("straight"))
                }
                val speed = if (s.isNull("speed")) null else s.getDouble("speed")
                val gps = if (s.isNull("gps")) null else s.getDouble("gps")
                val st = cal.update(obs, mapper, calib, s.getDouble("t"), speed, gps)
                val why = "$name bước $i (t=${s.getDouble("t")})"
                assertEquals(why, s.getString("state"), st.state)
                assertEquals(why, s.getInt("progress"), st.progress)
                assertEquals(why, s.getString("message"), st.message)
                assertEquals(why, if (s.isNull("ok")) null else s.getBoolean("ok"), st.ok)
                if (s.isNull("new")) {
                    assertNull(why, st.newCalib)
                } else {
                    val got = st.newCalib
                    assertNotNull(why, got)
                    sameCalib(CalibrationConfig.fromJson(s.getJSONObject("new")), got!!, why)
                    calib = got
                    mapper = GroundPlaneMapper(calib, w, h)
                    cal.calibrationChanged(calib)
                    applied++
                }
            }
            if (name == "refine") assertEquals("tự hoàn thiện + hiệu chỉnh lại sau xê dịch", 2, applied)
            if (name == "gps") assertEquals("tự hoàn thiện + chỉnh thang khoảng cách theo GPS", 2, applied)
        }
    }

    /** Tốc độ đo từ vạch kẻ (EgoSpeed.kt) phải khớp ego_speed.py trên các khung liên tiếp của video demo. */
    @Test
    fun egoSpeedMatchesPython() {
        val fx = json("egospeed_python.json")
        val w = fx.getJSONArray("size").getInt(0); val h = fx.getJSONArray("size").getInt(1)
        val mapper = GroundPlaneMapper(CalibrationConfig.fromJson(fx.getJSONObject("calib")), w.toDouble(), h.toDouble())
        val raw = GZIPInputStream(javaClass.classLoader!!.getResourceAsStream("fixtures/egospeed_frames.bin.gz")!!).use { it.readBytes() }
        val steps = fx.getJSONArray("steps")
        assertEquals(steps.length() * w * h, raw.size)
        val est = EgoSpeed(mapper)
        var measured = 0
        for (i in 0 until steps.length()) {
            val s = steps.getJSONObject(i)
            val gray = GrayImage(w, h, FloatArray(w * h) { (raw[i * w * h + it].toInt() and 0xFF).toFloat() })
            val obs = s.optJSONObject("obs")?.let {
                LaneObservation(pair(it.getJSONArray("left")), pair(it.getJSONArray("right")), it.getBoolean("straight"))
            }
            val shown = est.update(gray, 1.0, obs, s.getDouble("t"))
            val why = "khung $i (t=${s.getDouble("t")})"
            if (s.isNull("value")) {
                assertNull(why, est.value)
            } else {
                // ảnh nội suy song tuyến số thực, cv2.remap dùng điểm cố định 1/32 pixel: lệch rất nhỏ
                close(s.getDouble("value"), est.value!!, 0.5, "$why: tốc độ làm mượt")
                close(s.getDouble("shown"), shown!!, 1.0, "$why: tốc độ hiển thị")
                measured++
            }
        }
        assertTrue("phải đo được tốc độ ở phần lớn các khung", measured >= steps.length() / 2)
    }

    /** Bộ dò vạch gọn (Android) phải tìm được điểm tụ gần như bộ dò làn đầy đủ của desktop trên video thật. */
    @Test
    fun laneLinesFindDemoVanishingPoint() {
        val fx = json("lane_python.json")
        val w = fx.getJSONArray("size").getInt(0); val h = fx.getJSONArray("size").getInt(1)
        val calib = CalibrationConfig.fromJson(fx.getJSONObject("calib"))
        val mapper = GroundPlaneMapper(calib, w.toDouble(), h.toDouble())
        val raw = GZIPInputStream(javaClass.classLoader!!.getResourceAsStream("fixtures/lane_frames.bin.gz")!!).use { it.readBytes() }
        val frames = fx.getJSONArray("frames")
        assertEquals(frames.length() * w * h, raw.size)
        for (i in 0 until frames.length()) {
            val gray = GrayImage(w, h, FloatArray(w * h) { (raw[i * w * h + it].toInt() and 0xFF).toFloat() })
            val obs = LaneLines().find(gray, 1.0, mapper)
            val f = frames.getJSONObject(i)
            assertNotNull("khung ${f.getInt("frame")}: không thấy 2 vạch", obs)
            val la = V3(obs!!.left.first.x, obs.left.first.y, 1.0) cross V3(obs.left.second.x, obs.left.second.y, 1.0)
            val lb = V3(obs.right.first.x, obs.right.first.y, 1.0) cross V3(obs.right.second.x, obs.right.second.y, 1.0)
            val p = la cross lb
            val vp = f.getJSONArray("vp")
            close(vp.getDouble(0), p.x / p.z, 4.0, "khung ${f.getInt("frame")}: cột điểm tụ")
            close(vp.getDouble(1), p.y / p.z, 3.0, "khung ${f.getInt("frame")}: hàng điểm tụ")
        }
    }

    /** Trọng lực -> chân trời: camera chúc xuống 3° và nghiêng 2° phải cho ra đúng điểm tụ, góc nghiêng. */
    @Test
    fun gravityGivesHorizon() {
        val w = 1280.0; val h = 720.0
        val pose = CameraPose(focalW = 0.7, focalSource = "camera")
        val pitch = radians(3.0); val roll = radians(2.0)
        // hướng xuống đất trong hệ camera: quay (0,1,0) quanh trục x theo pitch rồi quanh trục z theo roll
        val d0 = V3(0.0, kotlin.math.cos(pitch), kotlin.math.sin(pitch))
        val down = V3(d0.x * kotlin.math.cos(roll) - d0.y * kotlin.math.sin(roll), d0.x * kotlin.math.sin(roll) + d0.y * kotlin.math.cos(roll), d0.z)
        val got = poseFromGravity(pose, down, w, h)
        val cam = PoseCamera(got.copy(active = true), w, h)
        close(3.0, cam.pitchDeg, 0.05, "góc chúc")
        close(2.0, got.rollDeg, 0.05, "góc nghiêng")
        // điểm tụ nằm trên đường chân trời thật: n·K⁻¹·p = 0
        val f = 0.7 * w
        val r = V3((got.vpX * w - w / 2) / f, (got.vpY * h - h / 2) / f, 1.0)
        close(0.0, r dot down.unit(), 1e-9, "điểm tụ trên chân trời")
    }
}
