package vn.adas.caotoc.ui.drive

import android.app.Application
import android.os.SystemClock
import android.util.Log
import androidx.camera.core.Camera
import androidx.camera.core.ImageProxy
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import vn.adas.caotoc.AdasApp
import vn.adas.caotoc.core.CalibStatus
import vn.adas.caotoc.core.CalibrationConfig
import vn.adas.caotoc.core.FrameResult
import vn.adas.caotoc.core.GrayImage
import vn.adas.caotoc.core.OfflineAssistant
import vn.adas.caotoc.core.PerfLevel
import vn.adas.caotoc.core.PerfThresholds
import vn.adas.caotoc.core.ViolationRecorder
import vn.adas.caotoc.core.capabilityLevel
import vn.adas.caotoc.data.AppSettings
import vn.adas.caotoc.detector.FramePacket
import vn.adas.caotoc.detector.Gray
import vn.adas.caotoc.detector.YoloDetector
import vn.adas.caotoc.engine.EngineConfig
import vn.adas.caotoc.engine.EngineOutput
import vn.adas.caotoc.engine.EngineStats
import vn.adas.caotoc.engine.FrameEngine
import vn.adas.caotoc.engine.FrameInput
import vn.adas.caotoc.engine.Nv21Frame
import vn.adas.caotoc.service.AlertPlayer
import vn.adas.caotoc.service.DeviceInfo
import vn.adas.caotoc.service.GpsSpeed
import vn.adas.caotoc.service.LensFocal
import vn.adas.caotoc.service.ThermalReading
import vn.adas.caotoc.service.UsbFrame
import kotlin.math.abs
import kotlin.math.roundToInt

/** Một tin nhắn trong hội thoại với Trợ lý AI. [note]: ghi chú kỹ thuật (vd: đã chuyển sang tốc độ nhập tay). */
data class ChatMessage(val fromUser: Boolean, val text: String, val note: String? = null)

/** Kết quả tự kiểm tra máy ("Máy của bạn: mức Trung bình ..."); [weak]: máy dưới cấu hình tối thiểu. */
data class PerfNotice(val text: String, val weak: Boolean)

/**
 * Trạng thái + logic của màn hình lái (sống theo Activity, giữ qua xoay màn hình / mở Cài đặt):
 * camera -> FrameEngine (bám vết + YOLO nền) -> cảnh báo âm thanh, nhật ký vi phạm, HUD.
 *
 * Luồng giao diện không xử lý ảnh: [onImage] chạy trên luồng phân tích của CameraX (KEEP_ONLY_LATEST: xử lý
 * chậm thì khung bị bỏ ngay tại camera). Overlay cập nhật theo nhịp kết quả ([live]); các cụm đồng hồ
 * ([hud]) ~10 lần/giây vì số nhảy nhanh hơn mắt cũng không đọc kịp - riêng mức cảnh báo đổi thì cập nhật ngay.
 */
class DriveViewModel(app: Application) : AndroidViewModel(app) {
    private val adas = app as AdasApp
    val store = adas.settings
    val log = adas.violations
    val gps = GpsSpeed(app)
    val alerts = AlertPlayer(app)
    /** Camera hành trình USB (màn hình Android ô tô); dùng khi Cài đặt chọn, hoặc "Tự động" và đang cắm. */
    val usb = adas.usbCamera

    private val engineMutex = Mutex()
    @Volatile private var detector: YoloDetector? = null
    @Volatile private var engine: FrameEngine? = null
    private var detectorGpu: Boolean? = null
    private var calibVersion = 0
    private val clock0 = SystemClock.elapsedRealtimeNanos()

    private val _live = MutableStateFlow<FrameResult?>(null)
    val live: StateFlow<FrameResult?> = _live.asStateFlow()
    private val _hud = MutableStateFlow<FrameResult?>(null)
    val hud: StateFlow<FrameResult?> = _hud.asStateFlow()
    private val _stats = MutableStateFlow<EngineStats?>(null)
    val stats: StateFlow<EngineStats?> = _stats.asStateFlow()
    private val _backend = MutableStateFlow<String?>(null)
    val backend: StateFlow<String?> = _backend.asStateFlow()
    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()
    private val _imageSize = MutableStateFlow(1280 to 720)
    val imageSize: StateFlow<Pair<Int, Int>> = _imageSize.asStateFlow()
    private val _perfNotice = MutableStateFlow<PerfNotice?>(null)
    val perfNotice: StateFlow<PerfNotice?> = _perfNotice.asStateFlow()
    private val _chat = MutableStateFlow(listOf(ChatMessage(false, OfflineAssistant.GREETING)))
    val chat: StateFlow<List<ChatMessage>> = _chat.asStateFlow()
    private val _calib = MutableStateFlow<CalibStatus?>(null)
    /** Tự hoàn thiện căn chỉnh khi chạy: tiến độ, kết quả tự kiểm tra, camera xê dịch (null: tắt). */
    val calib: StateFlow<CalibStatus?> = _calib.asStateFlow()
    private val _lens = MutableStateFlow<LensFocal?>(null)
    /** Tiêu cự ống kính đọc từ Camera2 khi camera mở (null: máy không khai báo / chưa mở). */
    val lens: StateFlow<LensFocal?> = _lens.asStateFlow()
    private val _rates = MutableStateFlow(0.0 to 0.0) // (FPS kết quả, nhịp camera)
    val rates: StateFlow<Pair<Double, Double>> = _rates.asStateFlow()
    @Volatile var thermal = ThermalReading(-1, null)
        private set

    private var recorder: ViolationRecorder? = log.startSession()
    private var hudT = -1.0
    private var lastTouch = 0.0
    private var fps = 0.0
    private var lastResultT = 0.0
    private var camHz = 0.0
    private var lastCamT = 0.0
    private var firstYoloT: Double? = null
    @Volatile private var videoKmh: Double? = null // tốc độ đo từ vạch kẻ (dòng thông số kỹ thuật)
    private var selfTestDone = false
    private var noticeJob: Job? = null

    init {
        if (store.value.useGps) gps.start()
        startEngine()
        // Android ADPF: đọc nhiệt độ thưa (dư nhiệt chỉ hợp lệ khi gọi cách nhau >= 1 s)
        viewModelScope.launch(Dispatchers.Default) {
            while (isActive) {
                val r = DeviceInfo.thermal(app)
                thermal = r
                engine?.thermal(r.status, r.headroom, camHz)
                delay(5000)
            }
        }
    }

    fun now(): Double = (SystemClock.elapsedRealtimeNanos() - clock0) / 1e9

    /** Detector chung (cho màn hình đo hiệu năng dùng lại khi màn hình lái không chạy). */
    val sharedDetector: YoloDetector? get() = detector

    private fun engineConfig(s: AppSettings, calibration: CalibrationConfig = s.calibration) = EngineConfig(
        calibration = calibration, alert = s.alert, enabledClasses = s.enabledClasses, confidence = s.confidence,
        denseTracking = s.denseTracking, farDetect = s.farDetect, forcedLevel = s.forcedLevel, version = calibVersion,
        autoCalib = s.autoCalib,
    )

    /** Mức khởi đầu: khóa tay > mức lần chạy trước > ước lượng từ lần đo suy luận lúc khởi động (+ ~10 ms tiền xử lý). */
    fun initialLevel(s: AppSettings, benchMs: Double): PerfLevel =
        s.forcedLevel ?: PerfLevel.fromKey(s.lastLevel) ?: capabilityLevel(benchMs + 10)

    /** Tạo (hoặc dựng lại khi đổi tùy chọn GPU) bộ nhận diện + bộ xử lý. Đo GPU/CPU mất vài giây trên máy yếu. */
    fun startEngine() {
        viewModelScope.launch(Dispatchers.Default) {
            engineMutex.withLock {
                val s = store.value
                try {
                    if (detector == null || detectorGpu != s.preferGpu) {
                        engine.also { engine = null }?.close() // khung mới thôi dùng bộ cũ trước khi đóng
                        detector.also { detector = null }?.close()
                        _backend.value = null
                        detector = YoloDetector.create(getApplication(), s.preferGpu)
                        detectorGpu = s.preferGpu
                        selfTestDone = false
                        firstYoloT = null
                    }
                    val det = detector!!
                    if (engine == null) engine = FrameEngine(det, engineConfig(s), initialLevel(s, det.benchMs))
                    _backend.value = det.backend
                    _error.value = null
                } catch (e: Throwable) {
                    Log.e(TAG, "Không khởi động được bộ nhận diện", e)
                    _error.value = "Không khởi động được bộ nhận diện: ${e.message}"
                }
            }
        }
    }

    /** Sau khi đổi cài đặt / căn chỉnh: gửi cấu hình mới cho bộ xử lý (đổi GPU thì dựng lại). */
    fun applySettings(calibrationChanged: Boolean = false) {
        val s = store.value
        if (calibrationChanged) calibVersion++
        if (s.useGps) gps.start() else gps.stop()
        if (detectorGpu != null && detectorGpu != s.preferGpu) startEngine() else engine?.configure(engineConfig(s))
    }

    fun speedKmh(s: AppSettings = store.value): Double = (if (s.useGps) gps.speedKmh else null) ?: s.manualSpeedKmh

    val speedFromGps: Boolean get() = store.value.useGps && gps.speedKmh != null

    // ------------------------------------------------------------------ camera (luồng phân tích)

    /** Ảnh từ cảm biến cần xoay 180° khi cảm biến lắp ngược - hiếm gặp; cài đặt "Xoay ảnh 180°" để sửa tay. */
    fun onImage(img: ImageProxy) {
        val s = store.value
        val rot180 = (img.imageInfo.rotationDegrees == 180) != s.rotate180
        process(img.width, img.height, s) { e -> ProxyFrame(img, rot180, e) }
    }

    /** Khung NV21 từ camera hành trình USB (luồng thu hình của thư viện UVC). */
    fun onUsbFrame(f: UsbFrame) {
        val s = store.value
        process(f.width, f.height, s) { e -> Nv21Frame(f.buffer, f.width, f.height, s.rotate180, e::reusablePacket) }
    }

    private inline fun process(w: Int, h: Int, s: AppSettings, frame: (FrameEngine) -> FrameInput) {
        val t = now()
        val camDt = t - lastCamT
        lastCamT = t
        if (camDt > 0 && camDt < 2) camHz = if (camHz == 0.0) 1 / camDt else 0.9 * camHz + 0.1 / camDt
        val e = engine ?: return
        if (_imageSize.value != w to h) _imageSize.value = w to h
        val out = e.process(frame(e), t, speedKmh(s), s.policy, if (s.useGps) gps.speedKmh else null)
        onOutput(out, s)
    }

    /** Camera vừa mở (CameraPreview): đọc tiêu cự ống kính cho căn chỉnh. */
    fun onCamera(camera: Camera) {
        LensFocal.of(camera)?.let { _lens.value = it }
    }

    /** Khung camera chưa chép: ảnh xám đọc thẳng kênh Y; chỉ chép ba mặt phẳng khi gửi YOLO. */
    private class ProxyFrame(private val img: ImageProxy, private val rot180: Boolean, private val engine: FrameEngine) : FrameInput {
        override val width = img.width
        override val height = img.height
        override fun gray(): GrayImage = img.planes[0].let { Gray.fromPlane(it.buffer, width, height, it.rowStride, rot180) }
        override fun packet(): FramePacket {
            val p = img.planes
            return FramePacket.copyOf(width, height, p[0].buffer, p[0].rowStride, p[1].buffer, p[2].buffer,
                p[1].rowStride, p[1].pixelStride, rot180, engine.reusablePacket())
        }
    }

    private fun onOutput(o: EngineOutput, s: AppSettings) {
        videoKmh = o.videoKmh
        _stats.value = o.stats
        val st = o.calib
        if (st?.newCalib != null) {
            // tự hoàn thiện xong: lưu như một lần căn chỉnh mới (luồng giao diện: đổi phiên bản cấu hình)
            val c = st.newCalib
            viewModelScope.launch(Dispatchers.Main) { saveCalibration(c) }
        }
        val shown = st?.copy(newCalib = null)
        val prev = _calib.value
        // tiến độ đổi theo từng mẫu: chỉ báo giao diện khi đổi trạng thái / thông báo hoặc mỗi 5 %
        if (shown == null || prev == null || shown.state != prev.state || shown.message != prev.message ||
            abs(shown.progress - prev.progress) >= 5
        ) _calib.value = shown
        if (o.stats.yoloMs > 0 && firstYoloT == null) firstYoloT = o.t
        firstYoloT?.let { if (!selfTestDone && o.t - it >= 4) selfTest(o.stats, s) }
        val r = o.result ?: return
        val dt = o.t - lastResultT
        lastResultT = o.t
        if (dt > 0 && dt < 2) fps = if (fps == 0.0) 1 / dt else 0.9 * fps + 0.1 / dt
        publish(r, o.t, s)
    }

    private fun publish(r: FrameResult, t: Double, s: AppSettings) {
        alerts.update(r.level, t, s.alert.soundEnabled, s.alert.voiceEnabled)
        recorder?.let { rec ->
            val p = s.policy
            val ev = rec.update(r, t, speedKmh(s), p.condition, p.weatherFactor)
            if (ev.isNotEmpty()) {
                log.apply(ev)
            } else if (rec.current != null && t - lastTouch > 0.5) {
                lastTouch = t // khoảng cách nhỏ nhất của đợt đang mở: vẽ lại danh sách, không ghi
                log.touch()
            }
        }
        _live.value = r // overlay vẽ lại ngay
        val prev = _hud.value
        val urgent = prev == null || prev.level != r.level || (prev.lead == null) != (r.lead == null)
        if (!urgent && t - hudT < 0.1) return
        hudT = t
        _hud.value = r
        _rates.value = fps to camHz
    }

    /** Sau ~4 giây chạy thật: báo mức hiệu năng của máy (lần đầu hoặc khi đổi), máy yếu thì báo mỗi phiên. */
    private fun selfTest(st: EngineStats, s: AppSettings) {
        selfTestDone = true
        val cap = capabilityLevel(st.yoloMs)
        val weak = st.yoloMs > PerfThresholds.YOLO_MS_WEAK
        val changed = s.lastLevel != cap.key
        if (changed) store.update { it.copy(lastLevel = cap.key) }
        if (!weak && !changed) return
        val hz = if (s.denseTracking) st.trackHz else st.yoloHz
        val text = if (weak) {
            "Máy yếu: mỗi lần nhận diện mất ${st.yoloMs.roundToInt()} ms. Cảnh báo chỉ mang tính tham khảo."
        } else {
            "Máy của bạn: mức ${cap.label} · YOLO ${st.yoloMs.roundToInt()} ms · cảnh báo cập nhật ${hz.roundToInt()} lần/giây"
        }
        _perfNotice.value = PerfNotice(text, weak)
        noticeJob?.cancel()
        noticeJob = viewModelScope.launch {
            delay(if (weak) 12_000 else 7_000)
            _perfNotice.value = null
        }
    }

    // ------------------------------------------------------------------ thao tác người dùng

    fun stepSpeed(delta: Double) = store.update { it.copy(manualSpeedKmh = (it.manualSpeedKmh + delta).coerceIn(20.0, 140.0)) }

    fun toggleSound() = store.update { it.copy(alert = it.alert.copy(soundEnabled = !it.alert.soundEnabled)) }

    /** Ô chọn điều kiện đường (giống nút "Sương mù" của bản desktop: "…tầm nhìn khoảng 100 m"). */
    fun setCondition(key: String) = store.update { it.withCondition(key, it.modifierKeys, if (key == "fog") 100.0 else 0.0) }

    fun toggleModifier(key: String) = store.update {
        it.copy(modifierKeys = if (key in it.modifierKeys) it.modifierKeys - key else it.modifierKeys + key)
    }

    /** Hỏi trợ lý offline rồi áp dụng kết quả vào cài đặt (giống MainWindow._on_assistant_result). */
    fun ask(text: String) {
        val s = store.value
        val r = OfflineAssistant.advise(text, s.policy, speedKmh(s))
        var note: String? = null
        var next = s
        if (r.changed) next = next.withCondition(r.conditionKey!!, r.modifierKeys, r.visibilityM)
        r.speedKmh?.let { v ->
            next = next.copy(manualSpeedKmh = v.coerceIn(20.0, 140.0))
            if (s.useGps) {
                next = next.copy(useGps = false) // như bản desktop: trợ lý trả về tốc độ thì tắt tự đo
                gps.stop()
                note = "Đã chuyển sang tốc độ nhập tay ${next.manualSpeedKmh.roundToInt()} km/h. Bật lại GPS trong Cài đặt."
            }
        }
        store.update { next }
        _chat.update { it + ChatMessage(true, text) + ChatMessage(false, r.reply, note) }
    }

    fun saveCalibration(c: CalibrationConfig) {
        store.update { it.copy(calibration = c, calibrated = true) }
        applySettings(calibrationChanged = true)
    }

    fun techText(st: EngineStats?, s: AppSettings): String {
        val backend = _backend.value ?: "…"
        if (st == null) return "Đang khởi động…\n$backend"
        val (fps, cam) = _rates.value
        // so tốc độ đo từ vạch kẻ với GPS: lệch nhiều = thang khoảng cách chưa đúng (app tự chỉnh khi chạy đều)
        val speeds = videoKmh?.let { v ->
            "\nTheo vạch kẻ ${v.roundToInt()} km/h" + (gps.speedKmh?.let { " · GPS ${it.roundToInt()} km/h" } ?: "")
        } ?: ""
        return techLine(st, fps, cam, backend, s.denseTracking, thermal.status) + speeds
    }

    override fun onCleared() {
        recorder?.close(now())?.let { log.apply(listOf(it)) }
        recorder = null
        gps.stop()
        alerts.close()
        engine?.close()
        detector?.close()
    }

    companion object {
        private const val TAG = "DriveViewModel"

        /** Dòng thông số kỹ thuật trên HUD (cũng dùng cho màn hình đo hiệu năng). */
        fun techLine(st: EngineStats, fps: Double, camHz: Double, backend: String, dense: Boolean, thermal: Int): String {
            val lvl = st.level.label + if (st.auto) "" else " (khóa)"
            val track = if (dense) " · bám vết ${st.procMs.roundToInt()} ms, ${st.trackHz.roundToInt()}/s" else ""
            val far = if (st.narrowShare > 0.02) " · thấy xa ${(st.narrowShare * 100).roundToInt()} %" else ""
            val crop = st.crop?.let { " · vùng ${it.w}x${it.h}" } ?: ""
            val heat = if (thermal >= 0) " · nhiệt ${DeviceInfo.thermalName(thermal)}" else ""
            return "${fps.roundToInt()} FPS (camera ${camHz.roundToInt()}) · mức $lvl$track\n" +
                "YOLO ${st.yoloMs.roundToInt()} ms (${vn1(st.yoloHz)}/s)$far$crop$heat\n$backend"
        }

        private fun vn1(v: Double) = vn.adas.caotoc.core.vn(v, 1)
    }
}
