package vn.adas.caotoc.core

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.adas.caotoc.detector.FramePacket
import vn.adas.caotoc.detector.Gray
import vn.adas.caotoc.detector.Preprocessor
import vn.adas.caotoc.engine.Nv21Frame
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.abs

/**
 * Lõi Kotlin phải khớp bản Python (adas/). Dữ liệu chuẩn trong src/test/resources/fixtures do
 * tools/make_mobile_fixtures.py sinh ra từ chính mã Python: ipm_python.json (IPM + ngưỡng), kalman_python.json,
 * tracker_python.json + tracker_frames.bin, yolo_raw.bin + yolo_expected.json (đầu ra thô mô hình fp16).
 */
class CoreTest {
    private fun bytes(name: String): ByteArray =
        javaClass.classLoader!!.getResourceAsStream("fixtures/$name")!!.use { it.readBytes() }

    private fun json(name: String) = JSONObject(String(bytes(name), Charsets.UTF_8))

    private fun close(want: Double, got: Double, tol: Double, why: String = "") =
        assertTrue("$why: muốn $want, được $got", abs(want - got) <= tol)

    // Python đưa 4 điểm vào cv2.getPerspectiveTransform dạng float32 -> lệch ~1e-6 tương đối so với
    // float64. Dung sai 1e-5 tương đối / 0,1 mm / 0,01 px, nhỏ hơn mọi sai số đo thực tế.
    @Test
    fun ipmMatchesPython() {
        val fx = json("ipm_python.json")
        val frame = fx.getJSONArray("frame")
        val m = GroundPlaneMapper(CalibrationConfig(), frame.getDouble(0), frame.getDouble(1))
        val h = fx.getJSONArray("H")
        for (i in 0 until 9) {
            val e = h.getJSONArray(i / 3).getDouble(i % 3)
            close(e, m.h.m[i], 1e-5 * (1 + abs(e)), "H[$i]")
        }
        close(fx.getDouble("focal_px"), m.focalPx!!, 1e-3, "tiêu cự")
        close(fx.getDouble("horizon_y"), m.horizonY!!, 1e-3, "chân trời")
        val pts = fx.getJSONArray("image_points"); val exp = fx.getJSONArray("ground")
        for (i in 0 until pts.length()) {
            val p = pts.getJSONArray(i)
            val g = m.imageToGround(p.getDouble(0), p.getDouble(1))
            if (exp.isNull(i)) {
                assertNull("điểm $p trên chân trời", g)
            } else {
                val e = exp.getJSONArray(i)
                close(e.getDouble(0), g!!.x, 1e-4); close(e.getDouble(1), g.y, 1e-4)
            }
        }
        val inp = fx.getJSONArray("ground_in"); val back = fx.getJSONArray("image_back")
        for (i in 0 until inp.length()) {
            val p = inp.getJSONArray(i); val e = back.getJSONArray(i)
            val q = m.groundToImage(p.getDouble(0), p.getDouble(1))
            close(e.getDouble(0), q.x, 1e-2); close(e.getDouble(1), q.y, 1e-2)
        }
    }

    @Test
    fun legalTableBoundaries() {
        val expected = listOf(59.9 to null, 60.0 to 35.0, 60.1 to 55.0, 80.0 to 55.0, 80.1 to 70.0,
            100.0 to 70.0, 100.1 to 100.0, 120.0 to 100.0)
        for ((v, gap) in expected) assertEquals("$v km/h", gap, legalMinGap(v))
    }

    @Test
    fun thresholdsMatchPython() {
        val fx = json("ipm_python.json")
        val thr = fx.getJSONObject("thresholds")
        for (k in thr.keys()) {
            val (cond, speed) = k.split("|")
            val p = conditionPolicy(cond, if (cond == "heavy_rain") listOf("night") else emptyList())
            val t = computeThresholds(speed.toDouble(), p)
            val e = thr.getJSONArray(k)
            close(e.getDouble(0), t.safeM, 1e-6, k); close(e.getDouble(1), t.dangerM, 1e-6, k)
        }
        val bp = fx.getJSONObject("band_policy")
        val user = SafetyPolicy(timeGapS = bp.getDouble("time_gap_s"), bandGapsM = doubles(bp.getJSONArray("band_gaps_m")))
        val bands = fx.getJSONArray("bands")
        for (i in 0 until bands.length()) {
            val c = bands.getJSONObject(i)
            val p = conditionPolicy(c.getString("cond"), emptyList(), base = user)
            val t = computeThresholds(c.getDouble("v"), p)
            val why = "${c.getString("cond")} ${c.get("v")} km/h"
            close(c.getDouble("safe"), t.safeM, 1e-6, why)
            close(c.getDouble("danger"), t.dangerM, 1e-6, why)
            assertEquals(why, if (c.isNull("band")) null else c.getDouble("band"), t.bandM)
            assertEquals(why, c.getString("basis"), thresholdBasis(t, p))
        }
    }

    @Test
    fun yoloDecodeMatchesPython() {
        val exp = json("yolo_expected.json")
        val shape = exp.getJSONArray("shape")
        val raw = bytes("yolo_raw.bin")
        val out = FloatArray(raw.size / 4).also { ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer().get(it) }
        val src = exp.getJSONArray("src"); val inp = exp.getJSONArray("input") // [cao, rộng]
        val dets = decodeYolo(out, shape.getInt(1), listOf("Jeepney", "bus", "car", "motorcycle", "truck"),
            Letterbox.of(src.getInt(0), src.getInt(1), inp.getInt(1), inp.getInt(0)))
        val want = exp.getJSONArray("detections")
        assertEquals(want.length(), dets.size)
        for (i in 0 until want.length()) {
            val w = want.getJSONArray(i); val d = dets[i]
            val box = d.box
            for (k in 0 until 4) {
                val lim = (if (k % 2 == 0) src.getInt(0) else src.getInt(1)).toDouble()
                close(w.getDouble(k).coerceIn(0.0, lim), box[k], 0.05, "hộp $i[$k]")
            }
            close(w.getDouble(4), d.confidence, 1e-5, "độ tin $i")
            assertEquals(w.getInt(5), d.classId)
        }
    }

    @Test
    fun preprocessLetterboxAndYuv() {
        val w = 64; val h = 36
        val pre = Preprocessor(64, 64)
        // YUV xám (Y=128, U=V=128) -> RGB 128
        val y = ByteArray(w * h) { 128.toByte() }
        val uv = ByteArray((w / 2) * (h / 2)) { 128.toByte() }
        val buf = pre.run(FramePacket(w, h, y, w, uv, uv, w / 2, 1, false)).order(ByteOrder.nativeOrder()).asFloatBuffer()
        assertEquals(14, pre.letterbox!!.top) // (64 - 36) / 2
        val mid = ((32 * 64) + 32) * 3
        close(128 / 255.0, buf.get(mid).toDouble(), 1e-6)
        close(128 / 255.0, buf.get(mid + 1).toDouble(), 1e-6)
        close(114 / 255.0, buf.get(0).toDouble(), 1e-6) // vùng đệm
    }

    @Test
    fun pipelineClosingVehicleEscalates() {
        val pipe = AdasPipeline(CalibrationConfig(), AlertConfig(escalateSeconds = 0.1), 1280.0, 720.0)
        val m = pipe.mapper
        var r: FrameResult? = null
        // Xe ô tô trong làn, khoảng cách giảm từ 40 m xuống 20 m trong 2 s (tiếp cận 10 m/s)
        for (i in 0..60) {
            val t = i / 30.0
            val d = 40 - 10 * t
            val g = m.groundToImage(0.0, d); val l = m.groundToImage(-0.9, d); val rr = m.groundToImage(0.9, d)
            val hgt = (rr.x - l.x) * 0.8
            r = pipe.process(listOf(Detection(l.x, g.y - hgt, rr.x, g.y, 0.9, 2, "car")), t, 80.0, SafetyPolicy())
        }
        val lead = r!!.lead!!
        close(20.0, lead.distanceM, 1.5)
        close(10.0, lead.closingSpeedMps!!, 1.0)
        close(2.0, lead.ttcS!!, 0.4)
        assertEquals(Risk.DANGER, r.level) // 20 m < 55 m ở 80 km/h và TTC ~2 s
        assertEquals(1, lead.det.trackId) // cùng một track suốt 2 s
    }

    @Test
    fun iouTrackerKeepsIds() {
        val tr = IouTracker()
        val a = tr.update(listOf(Detection(100.0, 100.0, 200.0, 200.0, 0.9, 2, "car")), 0.0)
        val b = tr.update(listOf(Detection(105.0, 102.0, 205.0, 203.0, 0.9, 2, "car"),
            Detection(600.0, 100.0, 700.0, 200.0, 0.8, 4, "truck")), 0.03)
        assertEquals(1, a[0].trackId); assertEquals(1, b[0].trackId); assertEquals(2, b[1].trackId)
    }

    @Test
    fun kalmanMatchesPython() {
        val rows = JSONArray(String(bytes("kalman_python.json"), Charsets.UTF_8))
        var kf: RangeKalman? = null
        for (i in 0 until rows.length()) {
            val r = rows.getJSONObject(i)
            val t = r.getDouble("t"); val z = r.getDouble("z")
            var ok = true
            if (kf == null) kf = RangeKalman(z, t, measurementSigma(z)) else {
                kf.predict(t)
                ok = kf.update(z, measurementSigma(z))
            }
            assertEquals("t=$t", r.getBoolean("accepted"), ok)
            close(r.getDouble("d"), kf.distance, 1e-9)
            close(r.getDouble("closing"), kf.closingSpeed, 1e-9)
            close(r.getDouble("rate_std"), kf.rateStd, 1e-9)
            assertEquals(r.getBoolean("report"), kf.rateStd < KalmanParams.RATE_STD_REPORT)
        }
    }

    @Test
    fun templateTrackerMatchesPython() {
        val fx = json("tracker_python.json")
        val size = fx.getJSONArray("size")
        val w = size.getInt(0); val h = size.getInt(1)
        val raw = bytes("tracker_frames.bin")
        val tr = TemplateTracker()
        val frames = fx.getJSONArray("frames")
        for (i in 0 until frames.length()) {
            val f = frames.getJSONObject(i)
            val t = f.getDouble("t")
            val gray = GrayImage(w, h, FloatArray(w * h) { (raw[i * w * h + it].toInt() and 0xFF).toFloat() })
            val out = if (i == 0) {
                val b = doubles(f.getJSONArray("true"))
                tr.refresh(listOf(Detection(b[0], b[1], b[2], b[3], 0.9, 2, "car", 7)), gray, t, 1.0)
            } else {
                tr.track(gray, t)
            }
            val want = f.getJSONArray("boxes")
            assertEquals("khung $i", want.length(), out.size)
            for (j in 0 until want.length()) {
                val wj = want.getJSONObject(j)
                assertEquals(wj.getInt("id"), out[j].trackId)
                assertEquals("khung $i", wj.getString("source"), out[j].source.name.lowercase())
                val wb = doubles(wj.getJSONArray("box"))
                // Python lấy mẫu bằng cv2.remap (vị trí làm tròn 1/32 px) -> lệch rất nhỏ
                for (c in 0 until 4) close(wb[c], out[j].box[c], 0.15, "khung $i, cạnh $c")
            }
        }
    }

    @Test
    fun lateYoloIsShiftedByTrackedMotion() {
        // Ảnh tổng hợp: một khối có họa tiết trôi sang phải 2 px/khung
        val w = 160; val h = 90
        fun frame(shift: Int) = GrayImage(w, h, FloatArray(w * h) { 100f }.also { px ->
            for (y in 30 until 60) for (x in 40 until 80) px[y * w + x + shift] = (((x * 7 + y * 13) % 17) * 12).toFloat()
        })
        val tr = TemplateTracker()
        tr.refresh(listOf(Detection(40.0, 30.0, 80.0, 60.0, 0.9, 2, "car")), frame(0), 0.0, 1.0)
        for (i in 1..5) tr.track(frame(2 * i), i / 30.0)
        // YOLO chụp lúc khung 1 (khối ở x=42) nhưng về lúc khung 5 (khối ở x=50): phải dời +8 px
        val out = tr.refresh(listOf(Detection(42.0, 30.0, 82.0, 60.0, 0.9, 2, "car")), frame(10), 5 / 30.0, 1.0, detT = 1 / 30.0)
        assertEquals(1, out.size)
        close(50.0, out.first().x1, 0.6)
        assertNotNull(out.first().trackId)
    }

    @Test
    fun grayDownscaleAndRotate() {
        // 1280 x 4 -> f = 2 -> 640 x 2
        val w = 1280; val h = 4
        val plane = ByteArray(w * h) { if (it % w < 2) 200.toByte() else 0 }
        val g = Gray.fromPlane(ByteBuffer.wrap(plane), w, h, w)
        assertEquals(640, g.width); assertEquals(2, g.height)
        close(200.0, g.data[0].toDouble(), 0.0); close(0.0, g.data[1].toDouble(), 0.0)
        val r = Gray.fromPlane(ByteBuffer.wrap(plane), w, h, w, rotate180 = true)
        close(200.0, r.data.last().toDouble(), 0.0)
    }

    // Camera hành trình USB gửi NV21 (Y rồi V,U xen kẽ): đầu vào YOLO và ảnh xám phải giống hệt cùng ảnh ở dạng I420
    @Test
    fun nv21FrameMatchesI420() {
        val w = 64; val h = 36
        val rnd = java.util.Random(7)
        val y = ByteArray(w * h).also(rnd::nextBytes)
        val u = ByteArray((w / 2) * (h / 2)).also(rnd::nextBytes)
        val v = ByteArray((w / 2) * (h / 2)).also(rnd::nextBytes)
        val nv21 = ByteBuffer.allocateDirect(Nv21Frame.size(w, h))
        nv21.put(y)
        for (i in u.indices) nv21.put(v[i]).put(u[i])
        for (rot in listOf(false, true)) {
            val i420 = FramePacket(w, h, y, w, u, v, w / 2, 1, rot)
            val frame = Nv21Frame(nv21, w, h, rot) { null }
            val a = Preprocessor(64, 64).run(i420).order(ByteOrder.nativeOrder()).asFloatBuffer()
            val b = Preprocessor(64, 64).run(frame.packet()).order(ByteOrder.nativeOrder()).asFloatBuffer()
            for (i in 0 until a.limit()) assertEquals("rot=$rot, chỉ số $i", a.get(i), b.get(i), 0f)
            assertTrue(Gray.fromPacket(i420).data.contentEquals(frame.gray().data))
        }
    }

    @Test
    fun governorDownshiftsAndRecoversSlowly() {
        val g = Governor(PerfLevel.HIGH)
        assertEquals(PerfLevel.MEDIUM, g.update(0.0, yoloMs = 80.0, procMs = 5.0))
        assertEquals(PerfLevel.MEDIUM, g.update(1.0, yoloMs = 200.0, procMs = 5.0)) // hạ cách nhau >= 3 s
        assertEquals(PerfLevel.LOW, g.update(3.5, yoloMs = 200.0, procMs = 5.0))
        for (s in 4..13) g.update(s.toDouble(), yoloMs = 30.0, procMs = 5.0)
        assertEquals(PerfLevel.LOW, g.level) // chưa đủ 10 s
        assertEquals(PerfLevel.MEDIUM, g.update(14.5, yoloMs = 30.0, procMs = 5.0)) // nâng từng mức một
    }

    private fun doubles(a: JSONArray) = List(a.length()) { a.getDouble(it) }
}
