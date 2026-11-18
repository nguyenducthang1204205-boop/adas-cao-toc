package vn.adas.caotoc.ui.benchmark

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.view.Choreographer
import android.widget.Toast
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.outlined.ContentCopy
import androidx.compose.material.icons.rounded.PlayArrow
import androidx.compose.material.icons.rounded.Stop
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.asCoroutineDispatcher
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import vn.adas.caotoc.core.CalibrationConfig
import vn.adas.caotoc.core.FrameResult
import vn.adas.caotoc.core.GroundPlaneMapper
import vn.adas.caotoc.core.GrayImage
import vn.adas.caotoc.core.PerfLevel
import vn.adas.caotoc.core.Vec2
import vn.adas.caotoc.core.vn
import vn.adas.caotoc.data.AppSettings
import vn.adas.caotoc.data.SettingsStore
import vn.adas.caotoc.detector.FramePacket
import vn.adas.caotoc.detector.Gray
import vn.adas.caotoc.detector.YoloDetector
import vn.adas.caotoc.engine.EngineConfig
import vn.adas.caotoc.engine.EngineStats
import vn.adas.caotoc.engine.FrameEngine
import vn.adas.caotoc.engine.FrameInput
import vn.adas.caotoc.service.DeviceInfo
import vn.adas.caotoc.ui.drive.DriveHud
import vn.adas.caotoc.ui.drive.DriveViewModel
import vn.adas.caotoc.ui.drive.HudActions
import vn.adas.caotoc.ui.drive.HudState
import vn.adas.caotoc.ui.drive.SpeedSource
import vn.adas.caotoc.ui.theme.AppColors
import vn.adas.caotoc.ui.theme.AppText
import vn.adas.caotoc.ui.theme.Radii
import vn.adas.caotoc.ui.theme.Space
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.util.concurrent.Executors
import kotlin.math.roundToInt

/**
 * Đo hiệu năng (benchmark): chạy đúng bộ xử lý + HUD của màn hình lái trên đoạn video mẫu đóng gói sẵn
 * (assets/bench: 48 khung của videoplayback.mp4, phát qua lại ở 30 khung/giây), thay cho camera.
 *
 * Mọi máy nhận cùng một dữ liệu vào, nên số đo so sánh được giữa các máy và giữa các phiên bản app (bảng cho
 * chương đánh giá). Khung mẫu 640x360 được phóng thành YUV420 1280x720 như camera thật.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BenchmarkScreen(store: SettingsStore, onBack: () -> Unit) {
    val context = LocalContext.current
    val s by store.settings.collectAsStateWithLifecycle()
    val scope = rememberCoroutineScope()
    val run = remember { BenchmarkRun(context.applicationContext) }
    val phase by run.phase.collectAsStateWithLifecycle()
    var durationS by remember { mutableIntStateOf(30) }
    DisposableEffect(Unit) { onDispose { run.close() } }

    when (phase) {
        Phase.RUNNING -> RunningView(run, s, durationS) { run.stop() }
        else -> Column(Modifier.fillMaxSize().background(AppColors.surface)) {
            TopAppBar(
                title = { Text("Đo hiệu năng máy", style = AppText.title.copy()) },
                navigationIcon = { IconButton(onBack) { Icon(Icons.AutoMirrored.Rounded.ArrowBack, "Quay lại") } },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = AppColors.surface),
            )
            LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(Space.lg), horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(Space.md)) {
                item {
                    Card {
                        Column {
                            Text("Chạy bộ xử lý thật (YOLO + bám vết + cảnh báo + HUD) trên 48 khung video cao tốc mẫu, " +
                                "phát lặp ở 30 khung/giây như camera. Kết quả lưu lại để so sánh giữa các máy.", style = AppText.caption)
                            Spacer(Modifier.height(Space.md))
                            Row(horizontalArrangement = Arrangement.spacedBy(Space.sm), verticalAlignment = Alignment.CenterVertically) {
                                for ((sec, label) in listOf(30 to "30 giây", 300 to "5 phút")) {
                                    FilterChip(durationS == sec, { durationS = sec }, label = { Text(label) })
                                }
                                Spacer(Modifier.weight(1f))
                                if (phase == Phase.LOADING) {
                                    CircularProgressIndicator(Modifier.size(24.dp), strokeWidth = 2.5.dp)
                                    Spacer(Modifier.width(Space.sm))
                                    Text("Đang nạp mô hình và video mẫu…", style = AppText.caption)
                                } else {
                                    Button({
                                        scope.launch {
                                            val report = run.start(s, durationS)
                                            if (report != null) store.update { it.copy(benchHistory = (listOf(report) + it.benchHistory).take(AppSettings.MAX_BENCH)) }
                                        }
                                    }) {
                                        Icon(Icons.Rounded.PlayArrow, null)
                                        Spacer(Modifier.width(Space.xs))
                                        Text("Bắt đầu đo")
                                    }
                                }
                            }
                            run.error.value?.let { Text(it, style = AppText.caption.copy(color = AppColors.danger)) }
                        }
                    }
                }
                items(s.benchHistory) { r -> ResultCard(context, r, highlight = r === s.benchHistory.firstOrNull() && phase == Phase.DONE) }
            }
        }
    }
}

@Composable
private fun Card(highlight: Boolean = false, content: @Composable () -> Unit) {
    val shape = RoundedCornerShape(Radii.md)
    Box(Modifier.widthIn(max = 760.dp).fillMaxWidth().background(AppColors.surfaceRaised, shape)
        .border(1.dp, if (highlight) AppColors.accent else AppColors.stroke, shape).padding(Space.lg)) { content() }
}

@Composable
private fun ResultCard(context: Context, r: JSONObject, highlight: Boolean) {
    val text = benchReportText(r)
    val lines = text.lines()
    Card(highlight) {
        Column {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(lines.first(), style = AppText.bodyStrong, modifier = Modifier.weight(1f))
                IconButton({
                    (context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager).setPrimaryClip(ClipData.newPlainText("ADAS", text))
                    Toast.makeText(context, "Đã sao chép kết quả đo", Toast.LENGTH_SHORT).show()
                }) { Icon(Icons.Outlined.ContentCopy, "Sao chép kết quả") }
            }
            for (l in lines.drop(1)) Text(l, style = AppText.caption.copy(color = AppColors.text), modifier = Modifier.padding(top = 2.dp))
        }
    }
}

@Composable
private fun RunningView(run: BenchmarkRun, s: AppSettings, durationS: Int, onStop: () -> Unit) {
    val result by run.result.collectAsStateWithLifecycle()
    val shown by run.shown.collectAsStateWithLifecycle()
    val stats by run.stats.collectAsStateWithLifecycle()
    val elapsed by run.elapsed.collectAsStateWithLifecycle()
    val frames = run.bitmaps
    val st = stats
    Box(Modifier.fillMaxSize()) {
        DriveHud(
            HudState(
                result = result, mapper = run.mapper, imageW = 1280.0, imageH = 720.0, speedKmh = run.speedKmh,
                speedSource = SpeedSource.MANUAL, policy = s.policy, conditionKey = s.conditionKey, modifiers = s.modifierKeys,
                calibrated = true, soundOn = false, cameraReady = true,
                techText = if (st == null) "Đang khởi động…" else DriveViewModel.techLine(st, run.fps, 30.0, run.backend, s.denseTracking, -1),
            ),
            HudActions(),
            live = run.result,
            camera = frames.getOrNull(shown)?.let { bmp ->
                { Image(bmp.asImageBitmap(), null, Modifier.fillMaxSize(), contentScale = ContentScale.Crop) }
            },
        )
        Row(Modifier.align(Alignment.BottomEnd).padding(Space.lg), verticalAlignment = Alignment.CenterVertically) {
            Text("Đang đo ${elapsed.toInt()}/$durationS s", style = AppText.caption.copy(color = AppColors.text),
                modifier = Modifier.background(AppColors.glassStrong, RoundedCornerShape(50)).padding(horizontal = Space.md, vertical = Space.sm))
            Spacer(Modifier.width(Space.sm))
            FilledTonalButton(onStop) {
                Icon(Icons.Rounded.Stop, null)
                Spacer(Modifier.width(Space.xs))
                Text("Dừng")
            }
        }
    }
}

private enum class Phase { IDLE, LOADING, RUNNING, DONE }

/** Một lần đo: nạp dữ liệu mẫu, chạy bộ xử lý trên luồng riêng, gom số đo và lập báo cáo. */
private class BenchmarkRun(private val context: Context) {
    val phase = MutableStateFlow(Phase.IDLE)
    val result = MutableStateFlow<FrameResult?>(null)
    val stats = MutableStateFlow<EngineStats?>(null)
    val shown = MutableStateFlow(0)
    val elapsed = MutableStateFlow(0.0)
    val error = mutableStateOf<String?>(null)
    val bitmaps = ArrayList<Bitmap>()
    private val packets = ArrayList<FramePacket>()
    var mapper: GroundPlaneMapper? = null
    var speedKmh = 74.0
    private var calib = CalibrationConfig()
    private var detector: YoloDetector? = null
    var backend = ""
    var fps = 0.0
    @Volatile private var stopRequested = false
    private val worker = Executors.newSingleThreadExecutor { r -> Thread(r, "adas-bench") }

    private fun load() {
        if (packets.isNotEmpty()) return
        val meta = JSONObject(context.assets.open("bench/bench.json").bufferedReader().use { it.readText() })
        val c = meta.getJSONObject("calibration")
        val pts = c.getJSONArray("image_points")
        calib = CalibrationConfig(
            imagePoints = List(pts.length()) { pts.getJSONArray(it).let { p -> Vec2(p.getDouble(0), p.getDouble(1)) } },
            rectWidthM = c.getDouble("rect_width_m"), rectLengthM = c.getDouble("rect_length_m"), nearDistanceM = c.getDouble("near_distance_m"),
        )
        speedKmh = meta.getDouble("speed_kmh")
        for (i in 0 until meta.getInt("frames")) {
            val bmp = context.assets.open("bench/f%02d.jpg".format(i)).use { BitmapFactory.decodeStream(it) }
            bitmaps += bmp
            packets += i420Doubled(bmp)
        }
        mapper = GroundPlaneMapper(calib, packets[0].width.toDouble(), packets[0].height.toDouble())
    }

    /** Chạy hết [durationS] giây (hoặc tới khi bấm Dừng); trả về báo cáo, null nếu lỗi. */
    suspend fun start(s: AppSettings, durationS: Int): JSONObject? {
        error.value = null
        phase.value = Phase.LOADING
        stopRequested = false
        return try {
            withContext(Dispatchers.Default) {
                load()
                if (detector == null) detector = YoloDetector.create(context, s.preferGpu)
            }
            val det = detector!!
            backend = det.backend
            val cfg = EngineConfig(calib, s.alert, s.enabledClasses, s.confidence, s.denseTracking, s.farDetect, s.forcedLevel, 0)
            val engine = FrameEngine(det, cfg, s.forcedLevel ?: PerfLevel.fromKey(s.lastLevel) ?: PerfLevel.HIGH)
            phase.value = Phase.RUNNING
            val report = measure(engine, s, durationS)
            engine.close()
            phase.value = Phase.DONE
            report
        } catch (e: Throwable) {
            error.value = "Không đo được: ${e.message}"
            phase.value = Phase.IDLE
            null
        }
    }

    private suspend fun measure(engine: FrameEngine, s: AppSettings, durationS: Int): JSONObject {
        val proc = ArrayList<Double>(); val yolo = ArrayList<Double>()
        val levels = HashMap<PerfLevel, Int>()
        var results = 0; var lastYoloRuns = 0; var lastResultT = 0.0
        val frameIntervals = ArrayList<Double>()
        var lastVsync = 0L
        val choreographer = withContext(Dispatchers.Main) { Choreographer.getInstance() }
        val callback = object : Choreographer.FrameCallback {
            override fun doFrame(t: Long) {
                if (lastVsync != 0L) frameIntervals += (t - lastVsync) / 1e6
                lastVsync = t
                if (!stopRequested) choreographer.postFrameCallback(this)
            }
        }
        withContext(Dispatchers.Main) { choreographer.postFrameCallback(callback) }
        val thermalStart = DeviceInfo.thermal(context)
        val t0 = System.nanoTime()
        val dispatcher = worker.asCoroutineDispatcher()
        withContext(dispatcher) {
            var lastThermal = 0.0
            while (isActive && !stopRequested) {
                val t = (System.nanoTime() - t0) / 1e9
                if (t >= durationS) break
                // phát qua lại 0..47..0 ở 30 khung/giây; xử lý chậm thì khung bị bỏ như camera thật
                val k = (t * 30).toInt() % (2 * packets.size - 2)
                val idx = if (k < packets.size) k else 2 * packets.size - 2 - k
                val out = engine.process(PacketFrame(packets[idx]), t, speedKmh, s.policy)
                shown.value = idx
                elapsed.value = t
                stats.value = out.stats
                levels.merge(out.stats.level, 1, Int::plus)
                if (out.stats.frameProcMs > 0) proc += out.stats.frameProcMs
                if (out.stats.yoloRuns != lastYoloRuns) { lastYoloRuns = out.stats.yoloRuns; yolo += out.stats.lastYoloMs }
                out.result?.let { r ->
                    results++
                    val dt = t - lastResultT; lastResultT = t
                    if (dt > 0 && dt < 2) fps = if (fps == 0.0) 1 / dt else 0.9 * fps + 0.1 / dt
                    result.value = r
                }
                if (t - lastThermal > 5) {
                    lastThermal = t
                    DeviceInfo.thermal(context).let { engine.thermal(it.status, it.headroom, 30.0) }
                }
                val next = ((t * 30).toInt() + 1) / 30.0
                val waitMs = ((next - (System.nanoTime() - t0) / 1e9) * 1000).toLong()
                if (waitMs > 0) delay(waitMs)
            }
        }
        stopRequested = true
        val dur = (System.nanoTime() - t0) / 1e9
        val thermalEnd = DeviceInfo.thermal(context)
        val info = DeviceInfo.info(context)
        val st = stats.value
        val totalLevels = levels.values.sum().coerceAtLeast(1)
        val jank = frameIntervals.count { it > 25.0 } // khung dài hơn 1,5 chu kỳ 60 Hz
        val report = JSONObject()
            .put("device", info.model).put("soc", info.soc).put("os", info.os).put("cores", info.cores).put("ram_mb", info.ramMb)
            .put("when", LocalDateTime.now().format(DateTimeFormatter.ofPattern("dd/MM/yyyy HH:mm")))
            .put("backend", backend).put("duration_s", dur.roundToInt()).put("mode", s.perfMode)
            .put("dense", s.denseTracking).put("far", s.farDetect)
            .put("ui_fps", if (dur > 0) frameIntervals.size / dur else 0.0)
            .put("jank_pct", if (frameIntervals.isEmpty()) 0.0 else 100.0 * jank / frameIntervals.size)
            .put("frame_p95", pct(frameIntervals, 0.95))
            .put("result_hz", if (dur > 0) results / dur else 0.0)
            .put("proc_avg", proc.average0()).put("proc_p95", pct(proc, 0.95))
            .put("yolo_avg", yolo.average0()).put("yolo_p95", pct(yolo, 0.95)).put("yolo_hz", st?.yoloHz ?: 0.0)
            .put("levels", JSONObject().apply { for (l in PerfLevel.entries) put(l.key, 100.0 * (levels[l] ?: 0) / totalLevels) })
            .put("thermal_start", thermalStart.status).put("thermal_end", thermalEnd.status)
        return report
    }

    fun stop() {
        stopRequested = true
    }

    fun close() {
        stopRequested = true
        worker.shutdown()
        detector?.close()
    }

    /** Khung mẫu đã ở dạng gói YUV: ảnh xám lấy từ kênh Y, gửi YOLO không cần chép. */
    private class PacketFrame(private val p: FramePacket) : FrameInput {
        override val width = p.width
        override val height = p.height
        override fun gray(): GrayImage = Gray.fromPacket(p)
        override fun packet() = p
    }
}

private fun List<Double>.average0() = if (isEmpty()) 0.0 else average()

private fun pct(v: List<Double>, q: Double): Double {
    if (v.isEmpty()) return 0.0
    val s = v.sorted()
    return s[((s.size - 1) * q).roundToInt()]
}

/**
 * RGBA 640x360 -> YUV420 (I420) gấp đôi kích thước: Y phóng 2x2 láng giềng gần, U/V giữ độ phân giải gốc
 * (đúng bằng nửa kích thước như camera). BT.601 toàn dải, hệ số x256 - nghịch đảo của Preprocessor.
 */
fun i420Doubled(bmp: Bitmap): FramePacket {
    val w = bmp.width; val h = bmp.height
    val px = IntArray(w * h).also { bmp.getPixels(it, 0, w, 0, 0, w, h) }
    val ow = 2 * w; val oh = 2 * h
    val yp = ByteArray(ow * oh); val up = ByteArray(w * h); val vp = ByteArray(w * h)
    for (y in 0 until h) for (x in 0 until w) {
        val c = px[y * w + x]
        val r = (c shr 16) and 0xFF; val g = (c shr 8) and 0xFF; val b = c and 0xFF
        val yy = ((77 * r + 150 * g + 29 * b) shr 8).coerceIn(0, 255).toByte()
        val o = 2 * y * ow + 2 * x
        yp[o] = yy; yp[o + 1] = yy; yp[o + ow] = yy; yp[o + ow + 1] = yy
        up[y * w + x] = (((-43 * r - 85 * g + 128 * b) shr 8) + 128).coerceIn(0, 255).toByte()
        vp[y * w + x] = (((128 * r - 107 * g - 21 * b) shr 8) + 128).coerceIn(0, 255).toByte()
    }
    return FramePacket(ow, oh, yp, ow, up, vp, w, 1, false)
}

private fun n(r: JSONObject, key: String, digits: Int = 0) = vn(r.optDouble(key, 0.0), digits)

/** Báo cáo một lần đo dạng chữ (hiển thị + sao chép vào luận văn). */
fun benchReportText(r: JSONObject): String {
    val levels = r.optJSONObject("levels") ?: JSONObject()
    val lv = PerfLevel.entries.filter { levels.optDouble(it.key, 0.0) > 0 }.joinToString(", ") { "${it.label} ${n(levels, it.key)} %" }
    val ram = if (r.optLong("ram_mb", 0) > 0) " · RAM ${vn(r.optLong("ram_mb") / 1024.0, 1)} GB" else ""
    val mode = PerfLevel.fromKey(r.optString("mode"))
    return listOf(
        "${r.optString("device", "Máy không rõ")} · ${r.optString("when")}",
        "Chip: ${r.optString("soc")} · ${r.optInt("cores")} nhân$ram · ${r.optString("os")}",
        "Bộ suy luận: ${r.optString("backend")}",
        "Đo ${r.optInt("duration_s")} s · mức ${mode?.let { "khóa ${it.label}" } ?: "tự động"}" +
            " · bám vết ${if (r.optBoolean("dense")) "bật" else "tắt"} · thấy xa ${if (r.optBoolean("far")) "bật" else "tắt"}",
        "Giao diện: ${n(r, "ui_fps")} khung/s, khung giật ${n(r, "jank_pct", 1)} % (khung p95 ${n(r, "frame_p95", 1)} ms)",
        "Cảnh báo cập nhật ${n(r, "result_hz", 1)} lần/s · xử lý một khung TB ${n(r, "proc_avg", 1)} ms (p95 ${n(r, "proc_p95", 1)} ms)",
        "YOLO TB ${n(r, "yolo_avg")} ms (p95 ${n(r, "yolo_p95")} ms) · ${n(r, "yolo_hz", 1)} lần/s",
        "Mức hiệu năng: $lv · nhiệt ${DeviceInfo.thermalName(r.optInt("thermal_start", -1))} " +
            "sang ${DeviceInfo.thermalName(r.optInt("thermal_end", -1))}",
    ).joinToString("\n")
}
