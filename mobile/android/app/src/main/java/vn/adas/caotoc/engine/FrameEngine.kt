package vn.adas.caotoc.engine

import android.os.Process
import android.os.SystemClock
import android.util.Log
import vn.adas.caotoc.core.AdasPipeline
import vn.adas.caotoc.core.AlertConfig
import vn.adas.caotoc.core.CalibStatus
import vn.adas.caotoc.core.CalibrationConfig
import vn.adas.caotoc.core.CropRect
import vn.adas.caotoc.core.EgoSpeed
import vn.adas.caotoc.core.FrameResult
import vn.adas.caotoc.core.GrayImage
import vn.adas.caotoc.core.Governor
import vn.adas.caotoc.core.LaneLines
import vn.adas.caotoc.core.OnlineCalibrator
import vn.adas.caotoc.core.PerfLevel
import vn.adas.caotoc.core.Risk
import vn.adas.caotoc.core.Roi
import vn.adas.caotoc.core.SafetyPolicy
import vn.adas.caotoc.core.yoloIntervalS
import vn.adas.caotoc.detector.DetectResult
import vn.adas.caotoc.detector.FramePacket
import vn.adas.caotoc.detector.YoloDetector
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.RejectedExecutionException
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

/** Cấu hình của bộ xử lý (đổi cài đặt / hiệu chỉnh thì gửi bản mới; [version] đổi thì dựng lại pipeline). */
data class EngineConfig(
    val calibration: CalibrationConfig,
    val alert: AlertConfig,
    val enabledClasses: Set<String>,
    val confidence: Double,
    val denseTracking: Boolean,
    /** Xen kẽ khung khóa hẹp quanh điểm tụ để thấy xe ở xa. */
    val farDetect: Boolean,
    /** null = bộ điều tốc tự chọn mức. */
    val forcedLevel: PerfLevel?,
    val version: Int,
    /** Tự hoàn thiện căn chỉnh khi chạy + báo camera xê dịch (OnlineCalib.kt). */
    val autoCalib: Boolean = true,
)

/** Số đo hiệu năng (trung bình trượt) gửi kèm mỗi kết quả. */
data class EngineStats(
    /** Xám hoá + bám vết + pipeline một khung. */
    val procMs: Double,
    /** Nhịp bám vết thực tế. */
    val trackHz: Double,
    val prepMs: Double,
    val inferMs: Double,
    val yoloHz: Double,
    val level: PerfLevel,
    /** Bộ điều tốc đang tự chọn mức (không bị khóa). */
    val auto: Boolean,
    val reason: String,
    /** Tỉ lệ khung khóa hẹp (thấy xa). */
    val narrowShare: Double,
    /** Vùng YOLO nhìn ở lần chạy gần nhất (khung khóa rộng). */
    val crop: CropRect?,
    /** Số đo thô của khung này (0 = khung không bám vết) - cho p95 của benchmark. */
    val frameProcMs: Double,
    /** Số đo thô của lần YOLO gần nhất (tiền xử lý + suy luận). */
    val lastYoloMs: Double,
    val yoloRuns: Int,
) {
    val yoloMs: Double get() = prepMs + inferMs
}

/** [result] null: khung chỉ được nhận (chưa đến nhịp bám vết). [calib]: tự hoàn thiện căn chỉnh (null: tắt / chưa đo). */
/** [videoKmh]: tốc độ đo từ vạch kẻ đường theo hiệu chỉnh đang dùng (chỉ để so với GPS / thông số kỹ thuật). */
class EngineOutput(
    val result: FrameResult?, val t: Double, val stats: EngineStats, val calib: CalibStatus? = null,
    val videoKmh: Double? = null,
)

/** Một khung vào: ảnh xám và gói YUV chỉ được tạo khi thật sự cần (bám vết / gửi YOLO). */
interface FrameInput {
    val width: Int
    val height: Int
    fun gray(): GrayImage
    fun packet(): FramePacket
}

/**
 * Bộ xử lý khung: mọi việc nặng chạy ngoài luồng giao diện.
 *
 * ```
 * Camera ──(CameraX KEEP_ONLY_LATEST)──► luồng XỬ LÝ (nhịp theo mức hiệu năng)
 *                                         │ xám hoá + bám vết + Kalman + ngưỡng + chống nhiễu
 *                                         │ YOLO rảnh và đến lượt: chép khung + vùng đường cần nhìn
 *                                         ▼
 *                                       luồng YOLO ── kết quả ghép ở khung kế tiếp
 * Giao diện ◄── EngineOutput (StateFlow) ── chỉ vẽ: camera, overlay, HUD
 * ```
 *
 * [process] chỉ được gọi từ một luồng (luồng xử lý); trạng thái chung với luồng YOLO là các trường volatile
 * và [pending]. Đang bận thì CameraX tự bỏ khung tại nguồn nên không bao giờ dồn khung hay tăng trễ.
 */
class FrameEngine(private val detector: YoloDetector, config: EngineConfig, initial: PerfLevel) : AutoCloseable {
    private val yolo: ExecutorService = Executors.newSingleThreadExecutor { r ->
        Thread({ Process.setThreadPriority(Process.THREAD_PRIORITY_DISPLAY); r.run() }, "adas-yolo")
    }

    @Volatile private var cfg = config
    private val gov = Governor(initial, config.forcedLevel)

    // nhiệt độ + nhịp camera (đặt từ luồng giao diện)
    @Volatile private var thermal = -1
    @Volatile private var headroom: Double? = null
    @Volatile private var cameraHz = 30.0

    // chia sẻ với luồng YOLO
    @Volatile private var yoloBusy = false
    private val pending = AtomicReference<DetectResult?>(null)
    @Volatile private var prepMs = 0.0
    @Volatile private var inferMs = 0.0
    @Volatile private var yoloHz = 0.0
    @Volatile private var narrowShare = 0.0
    @Volatile private var lastYoloMs = 0.0
    @Volatile private var yoloRuns = 0
    private var lastYoloTag = -1.0
    private var packetBuf: FramePacket? = null

    // chỉ luồng xử lý
    private var pipe: AdasPipeline? = null
    private var pipeKey: Triple<Int, Int, Int>? = null
    private var lastYoloT = -1e9
    private var yoloCount = 0
    private var lastTrackT = -1e9
    private var last: FrameResult? = null
    private var wide: CropRect? = null
    private var procMs = 0.0
    private var trackHz = 0.0
    private val laneLines = LaneLines()
    private var egoSpeed: EgoSpeed? = null
    private var calibrator: OnlineCalibrator? = null
    private var lastCalibT = -1e9
    private var calibStatus: CalibStatus? = null
    private var videoKmh: Double? = null

    val backend: String get() = detector.backend

    fun configure(c: EngineConfig) {
        if (c.denseTracking != cfg.denseTracking) pending.set(null)
        cfg = c
    }

    fun thermal(status: Int, headroom: Double?, cameraHz: Double) {
        thermal = status
        this.headroom = headroom
        if (cameraHz > 0) this.cameraHz = cameraHz
    }

    private fun ensurePipe(w: Int, h: Int): AdasPipeline {
        val c = cfg
        val key = Triple(w, h, c.version)
        val cur = pipe
        if (cur != null && pipeKey == key) return cur
        val p = runCatching { AdasPipeline(c.calibration, c.alert, w.toDouble(), h.toDouble()) }
            .getOrElse { AdasPipeline(CalibrationConfig(), c.alert, w.toDouble(), h.toDouble()) } // 4 điểm suy biến
        // căn chỉnh vừa đổi: do bộ tự hoàn thiện đề xuất -> theo dõi tiếp; người dùng căn lại -> đo từ đầu
        val cal = calibrator
        if (cal == null || pipeKey?.first != w || pipeKey?.second != h) calibrator = OnlineCalibrator(w.toDouble(), h.toDouble())
        else cal.calibrationChanged(c.calibration)
        laneLines.reset()
        egoSpeed = EgoSpeed(p.mapper) // đo theo hiệu chỉnh mới
        videoKmh = null
        pipe = p
        pipeKey = key
        pending.set(null)
        last = null
        return p
    }

    private fun stats(frameProcMs: Double) = EngineStats(
        procMs, trackHz, prepMs, inferMs, yoloHz, gov.effective, gov.forced == null, gov.reason, narrowShare, wide,
        frameProcMs, lastYoloMs, yoloRuns,
    )

    /**
     * Xử lý một khung chụp lúc [t] (giây, đồng hồ đơn điệu). [measuredKmh]: tốc độ GPS (null = không có) để bộ tự
     * hoàn thiện căn chỉnh bỏ qua lúc đứng yên / chạy chậm và tự chỉnh thang khoảng cách cho khớp GPS.
     */
    fun process(frame: FrameInput, t: Double, speedKmh: Double, policy: SafetyPolicy, measuredKmh: Double? = null): EngineOutput {
        val c = cfg
        gov.forced = c.forcedLevel
        val pipe = ensurePipe(frame.width, frame.height)
        var grayCache: GrayImage? = null
        fun gray() = grayCache ?: frame.gray().also { grayCache = it }

        // 1) YOLO: rảnh và đã hết khoảng nghỉ theo mức rủi ro -> gửi khung này
        if (!yoloBusy && t - lastYoloT >= yoloIntervalS(last, thermal) - 1e-3) {
            val (crop, narrow) = chooseCrop(pipe, frame.width, frame.height, c)
            val packet = frame.packet()
            yoloBusy = true
            lastYoloT = t
            try {
                yolo.execute { runYolo(packet, crop, narrow, c, t) }
            } catch (_: RejectedExecutionException) {
                yoloBusy = false // đang đóng bộ xử lý
            }
        }

        // 2) bám vết theo nhịp của mức hiệu năng; có kết quả YOLO mới thì ghép ngay
        var r: FrameResult? = null
        var frameProc = 0.0
        val lp = gov.effective
        if (c.denseTracking) {
            val due = pending.get() != null || lp.trackHz <= 0 || t - lastTrackT >= 1 / lp.trackHz - 0.004
            if (due) {
                val t0 = SystemClock.elapsedRealtimeNanos()
                val gray = gray()
                pipe.templates.trackedLimit = lp.maxTracked
                val pend = pending.getAndSet(null)
                val roi = pend?.takeIf { it.narrow }?.crop?.let {
                    doubleArrayOf(it.x.toDouble(), it.y.toDouble(), (it.x + it.w).toDouble(), (it.y + it.h).toDouble())
                }
                r = pipe.processFrame(gray, t, speedKmh, policy, pend?.detections, pend?.tag, roi)
                frameProc = (SystemClock.elapsedRealtimeNanos() - t0) / 1e6
                procMs = ema(procMs, frameProc, 0.1)
                val dt = t - lastTrackT
                if (dt > 0 && dt < 2) trackHz = ema(trackHz, 1 / dt, 0.1)
                lastTrackT = t
                last = r
            }
        } else {
            // không bám vết: kết quả YOLO là kết quả của khung đó (thời điểm = lúc chụp)
            pending.getAndSet(null)?.let { pend ->
                r = pipe.process(pend.detections, pend.tag, speedKmh, policy)
                last = r
            }
        }

        // 3) tự hoàn thiện căn chỉnh: dò 2 vạch làn ~15 lần/giây trên ảnh xám (dùng lại ảnh của bám vết nếu có)
        //    + tốc độ đo từ vạch kẻ đứt trên cùng 2 vạch đó (để so với GPS)
        if (!c.autoCalib) {
            calibStatus = null
            videoKmh = null
        } else if (t - lastCalibT >= CALIB_INTERVAL_S) {
            lastCalibT = t
            val g = gray()
            val scale = frame.width.toDouble() / g.width
            val obs = laneLines.find(g, scale, pipe.mapper)
            videoKmh = egoSpeed?.update(g, scale, obs, t)
            calibStatus = calibrator?.update(obs, pipe.mapper, pipe.calib, t, videoKmh, measuredKmh)
        }

        // 4) bộ điều tốc
        gov.update(t, prepMs + inferMs, procMs, cameraHz, thermal, headroom)
        return EngineOutput(
            r, t, stats(frameProc), calibStatus.also { st -> if (st?.newCalib != null) calibStatus = st.copy(newCalib = null) },
            videoKmh,
        )
    }

    /** Khung khóa rộng (dải đường) hay hẹp (quanh điểm tụ, cứ 3 lần có 1) - chỉ thấy xa khi đường không gấp. */
    private fun chooseCrop(pipe: AdasPipeline, w: Int, h: Int, c: EngineConfig): Pair<CropRect, Boolean> {
        val inW = detector.meta.inW; val inH = detector.meta.inH
        val wc = Roi.wideCrop(pipe.mapper, c.calibration, w, h, inW, inH)
        wide = wc
        val l = last
        val calm = l == null || (l.level.rank < Risk.WARNING.rank && (l.lead == null || l.lead.distanceM >= 40))
        val canNarrow = c.farDetect && c.denseTracking && gov.effective != PerfLevel.LOW && (prepMs + inferMs) < 150 && calm
        if (canNarrow && ++yoloCount % 3 == 0) {
            Roi.narrowCrop(pipe.mapper, w, h, inW, inH)?.let { return it to true }
        }
        return wc to false
    }

    private fun runYolo(packet: FramePacket, crop: CropRect, narrow: Boolean, c: EngineConfig, tag: Double) {
        try {
            val res = detector.detect(packet, crop, narrow, c.confidence, 0.45, c.enabledClasses, tag)
            lastYoloMs = res.prepMs + res.inferMs
            yoloRuns++
            prepMs = ema(prepMs, res.prepMs, 0.2)
            inferMs = ema(inferMs, res.inferMs, 0.2)
            narrowShare = ema(narrowShare, if (res.narrow) 1.0 else 0.0, 0.1)
            val dt = tag - lastYoloTag
            if (lastYoloTag >= 0 && dt > 0 && dt < 5) yoloHz = ema(yoloHz, 1 / dt, 0.2)
            lastYoloTag = tag
            pending.set(res) // ghép ở khung camera kế tiếp
        } catch (e: Throwable) {
            Log.w("FrameEngine", "YOLO lỗi, bỏ khung này", e)
        } finally {
            packetBuf = packet
            yoloBusy = false
        }
    }

    /** Gói YUV dùng lại giữa các lần gửi YOLO (an toàn: chỉ chép khi luồng YOLO đã trả gói cũ). */
    fun reusablePacket(): FramePacket? = packetBuf

    /** Chờ lần YOLO đang chạy xong (tối đa 2 s) để detector có thể đóng an toàn ngay sau đó. */
    override fun close() {
        yolo.shutdown()
        yolo.awaitTermination(2, TimeUnit.SECONDS)
    }

    private companion object {
        const val CALIB_INTERVAL_S = 1 / 15.0
        fun ema(cur: Double, v: Double, a: Double) = if (cur == 0.0) v else (1 - a) * cur + a * v
    }
}
